#!/usr/bin/env python3
"""Tests for `coyodex assemble` — structured-row fragments → the canonical model.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_assemble.py
    pytest tests/test_assemble.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex.assemble import load_fragment, merge_fragments
from coyodex.model import ModelError, load_model

ASSEMBLE = [sys.executable, "-m", "coyodex.assemble"]


# --- builders -------------------------------------------------------------------

def make_header_fragment() -> str:
    return json.dumps({"title": "Demo", "goal": "A demo.", "commit": "abc1234"})


def make_harvest_fragment(cid: str = "C1") -> str:
    return json.dumps({
        "components": [{"id": cid, "name": f"Component {cid}", "purpose": "does things"}],
        "deps": [] if cid != "C1" else [{"id": "D1", "name": "Postgres", "kind": "datastore",
                                         "type": "SQL database"}],
    })


def make_trace_fragment() -> str:
    return json.dumps({
        "edges": [{"src": "C1", "verb": "uses", "dst": "D1", "why": "query",
                   "where": "src/a.py:3"}],
    })


# --- merge ----------------------------------------------------------------------

def test_merge_concatenates_arrays_and_takes_singletons():
    parts = [("header.json", load_fragment(make_header_fragment(), "header.json")),
             ("h1.json", load_fragment(make_harvest_fragment("C1"), "h1.json")),
             ("h2.json", load_fragment(make_harvest_fragment("C2"), "h2.json")),
             ("t1.json", load_fragment(make_trace_fragment(), "t1.json"))]
    model, problems = merge_fragments(parts)
    assert problems == []
    assert model.title == "Demo" and model.commit == "abc1234"
    assert [c.id for c in model.components] == ["C1", "C2"]
    assert len(model.edges) == 1 and model.edges[0].dst == "D1"


def test_duplicate_id_across_fragments_is_a_conflict():
    parts = [("a.json", load_fragment(make_harvest_fragment("C1"), "a.json")),
             ("b.json", load_fragment(make_harvest_fragment("C1"), "b.json"))]
    _model, problems = merge_fragments(parts)
    assert any("duplicate id C1" in p and "a.json" in p and "b.json" in p for p in problems)


def test_conflicting_singletons_are_a_conflict():
    a = load_fragment(json.dumps({"title": "One"}), "a.json")
    b = load_fragment(json.dumps({"title": "Two"}), "b.json")
    _model, problems = merge_fragments([("a.json", a), ("b.json", b)])
    assert any("'title'" in p for p in problems)


def test_malformed_fragment_fails_alone_with_its_path():
    try:
        load_fragment(json.dumps({"components": [{"id": "C1"}]}), "h.json")  # name missing
        raise AssertionError("expected ModelError")
    except ModelError as e:
        assert "h.json" in str(e)


# --- CLI end-to-end ---------------------------------------------------------------

def test_assemble_cli_writes_canonical_map_and_views():
    with tempfile.TemporaryDirectory() as td:
        frags = []
        for name, content in (("header.json", make_header_fragment()),
                              ("h1.json", make_harvest_fragment("C1")),
                              ("t1.json", make_trace_fragment())):
            p = Path(td) / name
            p.write_text(content, encoding="utf-8")
            frags.append(str(p))
        out = Path(td) / "map"
        proc = subprocess.run(ASSEMBLE + frags + ["--out", str(out)],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        model = load_model((out / "project-map.json").read_text(encoding="utf-8"))
        assert model.title == "Demo" and [c.id for c in model.components] == ["C1"]
        assert (out / "project-map.md").exists() and (out / "project-map.html").exists()


def test_assemble_cli_fails_on_duplicate_ids_and_writes_nothing():
    with tempfile.TemporaryDirectory() as td:
        p1, p2 = Path(td) / "a.json", Path(td) / "b.json"
        p1.write_text(make_harvest_fragment("C1"), encoding="utf-8")
        p2.write_text(make_harvest_fragment("C1"), encoding="utf-8")
        out = Path(td) / "map"
        proc = subprocess.run(ASSEMBLE + [str(p1), str(p2), "--out", str(out)],
                              capture_output=True, text=True)
        assert proc.returncode == 1
        assert "duplicate id C1" in proc.stderr
        assert not out.exists()


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    raise SystemExit(1 if failures else 0)
