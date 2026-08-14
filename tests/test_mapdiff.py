#!/usr/bin/env python3
"""`coyodex diff` — what changed between two maps, row by row.

Nothing could answer that: `coyodex-eval compare` compares aggregate COUNTS, so a retrospective read
`auth surfaces 39 -> 21`, got REGRESSED, and needed an hour of hand-reading to find that the rows had
been re-expressed rather than lost.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_mapdiff.py
    pytest tests/test_mapdiff.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from coyodex import mapdiff
from coyodex.mapdiff import diff_arrays, format_diff

FORMAT = "coyodex-map"


def make_map(**overrides) -> dict:
    doc = {
        "format": FORMAT, "title": "t", "goal": "g",
        "use_cases": [{"id": "UC1", "name": "Do"}],
        "components": [{"id": "C1", "name": "A", "source": "a.py:1"}],
        "entities": [{"id": "E1", "name": "Thing"}],
        "edges": [],
        "rules": [],
        "entry_points": [],
    }
    doc.update(overrides)
    return doc


def make_rule(rid: str, statement: str, risk: str = "r") -> dict:
    return {"id": rid, "name": statement[:20], "statement": statement, "risk": risk,
            "sites": [{"where": "a.py:1", "why": "guards"}]}


def by_array(diffs, name):
    return next((d for d in diffs if d.array == name), None)


# --- id-keyed arrays --------------------------------------------------------------------

def test_an_unchanged_map_reports_nothing():
    m = make_map(rules=[make_rule("BR1", "A token is checked")])
    assert diff_arrays(m, json.loads(json.dumps(m))) == []


def test_a_changed_field_names_the_row_and_the_field():
    before = make_map(rules=[make_rule("BR1", "A token is checked", risk="old")])
    after = make_map(rules=[make_rule("BR1", "A token is checked", risk="new")])
    d = by_array(diff_arrays(before, after), "rules")
    assert d is not None and d.changed == [("BR1", ["risk"])]
    assert not d.added and not d.dropped


def test_several_moved_fields_are_all_listed():
    before = make_map(rules=[make_rule("BR1", "A", risk="r1")])
    after = make_map(rules=[make_rule("BR1", "B", risk="r2")])
    d = by_array(diff_arrays(before, after), "rules")
    assert d is not None and d.changed[0][1] == ["name", "risk", "statement"]


def test_an_added_and_a_dropped_row_are_separated():
    before = make_map(rules=[make_rule("BR1", "A token is checked")])
    after = make_map(rules=[make_rule("BR2", "A plan has a cap")])
    d = by_array(diff_arrays(before, after), "rules")
    assert d is not None
    assert d.added == ["BR2"] and d.dropped == ["BR1"] and d.changed == []


def test_a_count_change_is_reported_even_with_no_row_detail():
    d = by_array(diff_arrays(make_map(), make_map(rules=[make_rule("BR1", "x")])), "rules")
    assert d is not None and (d.count_before, d.count_after) == (0, 1)


# --- content-keyed arrays ---------------------------------------------------------------

def make_edge(src: str, verb: str, dst: str, where: str, why: str = "w") -> dict:
    return {"src": src, "verb": verb, "dst": dst, "where": where, "why": why}


def test_edges_match_on_their_triple_and_anchor_since_they_carry_no_id():
    before = make_map(edges=[make_edge("C1", "reads", "E1", "a.py:1", why="old")])
    after = make_map(edges=[make_edge("C1", "reads", "E1", "a.py:1", why="new")])
    d = by_array(diff_arrays(before, after), "edges")
    assert d is not None and d.changed and d.changed[0][1] == ["why"]


def test_a_re_anchored_edge_reads_as_dropped_and_added_not_as_changed():
    """The anchor is part of an edge's identity — `dedup-edge` exists because the same triple at two
    different call sites is two rows, not one."""
    before = make_map(edges=[make_edge("C1", "reads", "E1", "a.py:1")])
    after = make_map(edges=[make_edge("C1", "reads", "E1", "b.py:9")])
    d = by_array(diff_arrays(before, after), "edges")
    assert d is not None and len(d.added) == 1 and len(d.dropped) == 1 and not d.changed


def make_ep(source: str, trigger: str, eid: str = "", cadence: str = "") -> dict:
    row = {"kind": "cli", "trigger": trigger, "source": source, "component": "C1"}
    if eid:
        row["id"] = eid
    if cadence:
        row["cadence"] = cadence
    return row


def test_entry_points_match_on_content_so_a_renumber_alone_is_not_a_change():
    """EP ids are minted and re-sorted on every assemble: one anchor edit moved 22 of 104 on a real
    map. Matching by id would report a fifth of them as replaced when nothing about them changed."""
    before = make_map(entry_points=[make_ep("a.py:1", "run it", eid="EP1"),
                                    make_ep("b.py:2", "serve it", eid="EP2")])
    after = make_map(entry_points=[make_ep("a.py:1", "run it", eid="EP7"),
                                   make_ep("b.py:2", "serve it", eid="EP8")])
    assert by_array(diff_arrays(before, after), "entry_points") is None


def test_a_real_entry_point_change_is_still_caught_under_content_matching():
    before = make_map(entry_points=[make_ep("a.py:1", "run it", eid="EP1")])
    after = make_map(entry_points=[make_ep("a.py:1", "run it", eid="EP1", cadence="daily")])
    d = by_array(diff_arrays(before, after), "entry_points")
    assert d is not None and d.changed[0][1] == ["cadence"]


# --- fields the model does not know about ------------------------------------------------

def test_an_unmodelled_field_is_still_compared():
    """A diff that only saw modelled fields would go quiet exactly on the extras a build writes."""
    before = make_map(rules=[{**make_rule("BR1", "x"), "hand_note": "before"}])
    after = make_map(rules=[{**make_rule("BR1", "x"), "hand_note": "after"}])
    d = by_array(diff_arrays(before, after), "rules")
    assert d is not None and d.changed[0][1] == ["hand_note"]


def test_only_restricts_to_one_array():
    before = make_map(rules=[make_rule("BR1", "a")], entities=[{"id": "E1", "name": "Old"}])
    after = make_map(rules=[make_rule("BR1", "b")], entities=[{"id": "E1", "name": "New"}])
    assert [d.array for d in diff_arrays(before, after, only="rules")] == ["rules"]


# --- rendering --------------------------------------------------------------------------

def test_the_text_view_marks_dropped_added_and_changed_distinctly():
    before = make_map(rules=[make_rule("BR1", "a"), make_rule("BR2", "b")])
    after = make_map(rules=[make_rule("BR2", "b", risk="r2"), make_rule("BR3", "c")])
    text = format_diff(diff_arrays(before, after), "old", "new")
    assert "- BR1" in text and "+ BR3" in text and "~ BR2  [risk]" in text


def test_no_change_says_so_rather_than_printing_an_empty_report():
    assert "no row changed" in format_diff([], "old", "new")


# --- the CLI ----------------------------------------------------------------------------

def write_map(path: Path, doc: dict) -> str:
    path.write_text(json.dumps(doc), encoding="utf-8")
    return str(path)


def test_cli_emits_parseable_json(capsys):
    with tempfile.TemporaryDirectory() as td:
        a = write_map(Path(td) / "a.json", make_map(rules=[make_rule("BR1", "x", risk="r1")]))
        b = write_map(Path(td) / "b.json", make_map(rules=[make_rule("BR1", "x", risk="r2")]))
        assert mapdiff.main([a, b, "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "coyodex-map-diff"
    assert payload["arrays"][0]["changed"] == [{"key": "BR1", "fields": ["risk"]}]


def test_cli_refuses_a_malformed_map_rather_than_diffing_nonsense(capsys):
    with tempfile.TemporaryDirectory() as td:
        a = write_map(Path(td) / "a.json", make_map())
        bad = Path(td) / "b.json"
        bad.write_text('{"format": "coyodex-map", "components": [{"id": "NOPE1"}]}', encoding="utf-8")
        assert mapdiff.main([a, str(bad)]) == 2
        assert "ERROR" in capsys.readouterr().err


def test_cli_names_the_scope_when_an_older_schema_is_handed_to_it(capsys):
    with tempfile.TemporaryDirectory() as td:
        a = write_map(Path(td) / "a.json", make_map())
        old = write_map(Path(td) / "b.json",
                        make_map(grounding={"claims_total": 5, "claims_grounded": 5}))
        assert mapdiff.main([a, old]) == 2
        err = capsys.readouterr().err
        assert "two assembles of the same work" in err.lower(), err


def test_cli_needs_exactly_two_maps(capsys):
    with tempfile.TemporaryDirectory() as td:
        a = write_map(Path(td) / "a.json", make_map())
        assert mapdiff.main([a]) == 2
        assert "exactly two map paths" in capsys.readouterr().err


def test_cli_refuses_an_unknown_option_with_the_usage(capsys):
    assert mapdiff.main(["--nope"]) == 2
    assert "usage: coyodex diff" in capsys.readouterr().err


def test_cli_writes_nothing():
    with tempfile.TemporaryDirectory() as td:
        a = write_map(Path(td) / "a.json", make_map(rules=[make_rule("BR1", "x")]))
        b = write_map(Path(td) / "b.json", make_map(rules=[make_rule("BR1", "y")]))
        before = {p.name: p.read_bytes() for p in Path(td).iterdir()}
        assert mapdiff.main([a, b]) == 0
        assert {p.name: p.read_bytes() for p in Path(td).iterdir()} == before


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


# --- regressions from the adversarial review (2026-08-14) -----------------------------------------

def test_two_rows_sharing_an_identity_are_not_silently_collapsed():
    """A dict comprehension kept the LAST row per key, so `assemble`'s deliberately-preserved pair of
    no-call-site edges on one triple collapsed to one diff key — and deleting one was reported as
    ZERO row-level changes, under a line claiming edges carry no identity to match on."""
    both = [make_edge("C1", "uses", "E1", "", why="first coupling"),
            make_edge("C1", "uses", "E1", "", why="second coupling")]
    d = by_array(diff_arrays(make_map(edges=both), make_map(edges=both[1:])), "edges")
    assert d is not None
    assert len(d.dropped) == 1, d
    assert d.key_collisions, "a repeated identity must be named, not silently paired"


def test_deleting_the_other_of_a_shared_identity_pair_reads_the_same():
    """Deleting the SECOND used to be mis-reported as a field change rather than a deletion."""
    both = [make_edge("C1", "uses", "E1", "", why="first coupling"),
            make_edge("C1", "uses", "E1", "", why="second coupling")]
    d = by_array(diff_arrays(make_map(edges=both), make_map(edges=both[:1])), "edges")
    assert d is not None and len(d.dropped) == 1 and not d.changed, d


def test_a_duplicate_id_in_an_id_keyed_array_is_reported_by_count_not_paired():
    before = make_map(rules=[make_rule("BR1", "a"), make_rule("BR1", "b")])
    after = make_map(rules=[make_rule("BR1", "b")])
    d = by_array(diff_arrays(before, after), "rules")
    assert d is not None and d.dropped == ["BR1"] and not d.changed


def test_a_unique_key_is_still_compared_field_by_field():
    before = make_map(rules=[make_rule("BR1", "x", risk="r1")])
    after = make_map(rules=[make_rule("BR1", "x", risk="r2")])
    d = by_array(diff_arrays(before, after), "rules")
    assert d is not None and d.changed == [("BR1", ["risk"])] and not d.key_collisions


def test_only_with_an_unknown_array_fails_loudly(capsys):
    """`--only edge` (the obvious typo) used to print "no row changed" and exit 0 — a clean answer to
    a question that was never asked."""
    with tempfile.TemporaryDirectory() as td:
        a = write_map(Path(td) / "a.json", make_map(rules=[make_rule("BR1", "x", risk="r1")]))
        b = write_map(Path(td) / "b.json", make_map(rules=[make_rule("BR1", "x", risk="r2")]))
        assert mapdiff.main([a, b, "--only", "edge"]) == 2
        err = capsys.readouterr().err
        assert "not an array in either map" in err and "edges" in err


def test_only_refuses_a_flag_as_its_value(capsys):
    with tempfile.TemporaryDirectory() as td:
        a = write_map(Path(td) / "a.json", make_map())
        b = write_map(Path(td) / "b.json", make_map())
        assert mapdiff.main([a, b, "--only", "--json"]) == 2
        assert "another flag" in capsys.readouterr().err
