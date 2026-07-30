#!/usr/bin/env python3
"""`load_map_or_fragment` / `dump_preserving` — reading and writing a build FRAGMENT.

There was no read path for a fragment at all: `dump` and `fix` both went through `load_model`, which
requires `format`, so a build inspecting or editing its own fragments had nothing to use and wrote
`python3 - <<'EOF'` heredocs instead — about fifteen times in one live build, against the method's own
instruction to use `dump`. These pin the properties that make the write side SAFE, which shipped
untested in the first version of the change.

Run either way: `python3 tests/test_fragment_io.py` or `pytest tests/test_fragment_io.py`.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyodex.assemble import dump_preserving, load_map_or_fragment
from coyodex.model import FORMAT, ModelError, to_canonical_json

FRAGMENT = {"components": [{"id": "C1", "name": "X", "purpose": "p", "entry_point": "a.py:1"}],
            "edges": [{"src": "C1", "verb": "reads", "dst": "E1", "why": "w", "where": "a.py:3"}]}


def make_file(obj: object, name: str = "frag.json") -> Path:
    d = Path(tempfile.mkdtemp())
    p = d / name
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    return p


def test_a_fragment_is_recognised_by_having_no_format_key():
    m, present = load_map_or_fragment(make_file(FRAGMENT))
    assert present == frozenset({"components", "edges"})
    assert len(m.components) == 1


def test_a_file_carrying_format_is_treated_as_a_full_map():
    m, present = load_map_or_fragment(make_file({**FRAGMENT, "format": FORMAT}))
    assert present is None, "a `format` key means the whole shape may be written back"
    assert len(m.components) == 1


def test_writing_a_fragment_back_does_not_materialise_the_other_sections():
    """The property that makes the write safe. `to_canonical_json` emits all 29 top-level sections, so
    a naive round-trip turns a 2-section fragment into a full-shaped map — and a fragment's key set IS
    its ownership claim, so an agent's file that suddenly declares every section can make the merge
    attribute sections nobody authored."""
    p = make_file(FRAGMENT)
    m, present = load_map_or_fragment(p)
    assert len(json.loads(to_canonical_json(m))) > 20      # the naive path really would balloon it
    out = json.loads(dump_preserving(m, present))
    assert set(out) == {"components", "edges"}


def test_a_no_op_fix_does_not_change_a_fragments_values():
    """A fragment `fix` must not rewrite content it did not touch."""
    p = make_file(FRAGMENT)
    m, present = load_map_or_fragment(p)
    out = json.loads(dump_preserving(m, present))
    assert out["components"] == FRAGMENT["components"]
    assert out["edges"] == FRAGMENT["edges"]


def test_an_edit_to_a_section_the_fragment_declares_is_kept():
    p = make_file(FRAGMENT)
    m, present = load_map_or_fragment(p)
    m.edges[0].where = "a.py:99"
    out = json.loads(dump_preserving(m, present))
    assert out["edges"][0]["where"] == "a.py:99"


def test_an_edit_to_a_section_the_fragment_does_not_declare_is_dropped_by_design():
    """The documented limit, pinned so it cannot become a surprise.

    `dump_preserving` writes back only the fragment's own keys, so adding an element to a section the
    fragment never declared is NOT persisted. That is deliberate — silently widening an agent's file
    is the harm this function exists to prevent — but it means a caller must not use a fragment write
    to introduce a new section. `fix drop-edge` is refused on a fragment for the related reason that
    its healing needs the whole merged model."""
    p = make_file(FRAGMENT)
    m, present = load_map_or_fragment(p)
    m.use_cases.append(type(m.use_cases)().__class__ and __import__(
        "coyodex.model", fromlist=["UseCase"]).UseCase(id="UC1", name="New"))
    out = json.loads(dump_preserving(m, present))
    assert "use_cases" not in out


def test_a_full_map_round_trips_through_the_canonical_serializer():
    p = make_file({**FRAGMENT, "format": FORMAT})
    m, present = load_map_or_fragment(p)
    assert dump_preserving(m, present) == to_canonical_json(m)


def test_malformed_json_and_a_non_object_fail_loudly_with_the_file_named():
    d = Path(tempfile.mkdtemp())
    bad = d / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    try:
        load_map_or_fragment(bad)
        raise AssertionError("expected ModelError")
    except ModelError as e:
        assert "bad.json" in str(e)
    arr = make_file([1, 2, 3], "arr.json")
    try:
        load_map_or_fragment(arr)
        raise AssertionError("expected ModelError")
    except ModelError as e:
        assert "arr.json" in str(e)


def test_an_empty_object_is_a_fragment_that_declares_nothing():
    m, present = load_map_or_fragment(make_file({}))
    assert present == frozenset()
    assert json.loads(dump_preserving(m, present)) == {}


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all fragment-io tests passed")
