#!/usr/bin/env python3
"""Tests for `coyodex fix` — the in-place reconcile verbs (apply-drift / drop-edge / dedup-relation).

Run either way (needs an editable install: `make deps`):
    python3 tests/test_fix.py
    pytest tests/test_fix.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyodex import fix
from coyodex.model import FORMAT, load_model_path


# --- builders -------------------------------------------------------------------

def make_map(edges: list[dict], *, security: list[dict] | None = None,
             flows: list[dict] | None = None, entities: list[dict] | None = None) -> dict:
    return {
        "format": FORMAT, "title": "t", "goal": "g",
        "use_cases": [{"id": "UC1", "name": "Do"}],
        "components": [{"id": "C1", "name": "A", "source": "a.py:1"}],
        "entities": entities if entities is not None else [{"id": "E1", "name": "Thing"},
                                                           {"id": "E2", "name": "Other"}],
        "edges": edges,
        "security": security or [],
        "flows": flows or [],
    }


def make_vote(claim: str, grounded: bool, evidence: str) -> dict:
    return {"claim": claim, "grounded": grounded, "evidence": evidence}


def write(td: str, m: dict, verdicts: dict | None = None) -> tuple[str, str]:
    mp = Path(td) / "map.json"
    mp.write_text(json.dumps(m), encoding="utf-8")
    vp = Path(td) / "verdicts.json"
    if verdicts is not None:
        vp.write_text(json.dumps(verdicts), encoding="utf-8")
    return str(mp), str(vp)


# --- apply-drift ----------------------------------------------------------------

def test_apply_drift_does_not_swap_paired_persists_reads_edges():
    # THE headline regression: two edges share endpoints (C1↔E1) but differ in verb. The old hand
    # script matched on (src,dst) only and swapped their anchors. Matching the FULL (src,verb,dst)
    # triple keeps each on its own corrected line.
    m = make_map([
        {"src": "C1", "verb": "persists", "dst": "E1", "where": "a.py:10"},
        {"src": "C1", "verb": "reads", "dst": "E1", "where": "a.py:20"}])
    verdicts = {"grounding": [
        make_vote("C1 persists E1", True, "a.py:15"), make_vote("C1 persists E1", True, "a.py:15"),
        make_vote("C1 reads E1", True, "a.py:25"), make_vote("C1 reads E1", True, "a.py:25")]}
    with tempfile.TemporaryDirectory() as td:
        mp, vp = write(td, m, verdicts)
        assert fix.main(["apply-drift", "--map", mp, "--verdicts", vp, "--tolerance", "0"]) == 0
        out = load_model_path(mp)
        where = {e.verb: e.where for e in out.edges}
        assert where["persists"] == "a.py:15"     # each edge got ITS OWN corrected line
        assert where["reads"] == "a.py:25"         # NOT swapped


def test_apply_drift_rewrites_drifted_security_source():
    # The worklist carries a security claim ("Auth surface '…' is protected by: …") whose bare
    # `source` anchor is an L2 grounding claim. When the skeptics confirm it drifted, apply-drift now
    # rewrites `security[].source` (WS5) — same treatment as a drifted edge `where`.
    m = make_map([], security=[{"surface": "POST /pay", "who": "admin", "source": "a.py:5"}])
    claim_prefix = "Auth surface 'POST /pay' is protected by:"
    with tempfile.TemporaryDirectory() as td:
        mp, vp = write(td, m, {"grounding": []})
        # find the exact security claim string the worklist builds, then drift it
        from coyodex.audit_model import l2_worklist_model
        sec_claim = next(w.claim for w in l2_worklist_model(load_model_path(mp))
                         if w.claim.startswith(claim_prefix))
        Path(vp).write_text(json.dumps({"grounding": [
            make_vote(sec_claim, True, "a.py:99"), make_vote(sec_claim, True, "a.py:99")]}),
            encoding="utf-8")
        assert fix.main(["apply-drift", "--map", mp, "--verdicts", vp, "--tolerance", "0"]) == 0
        assert load_model_path(mp).security[0].source == "a.py:99"   # rewritten to the skeptics' line


def test_apply_drift_rewrites_security_and_leaves_a_paired_edge_untouched():
    # A drifted security anchor AND a same-file edge whose anchor is NOT in the verdicts: only the
    # security `source` moves; the edge's `where` stays put (apply-drift touches only drifted claims).
    m = make_map([{"src": "C1", "verb": "reads", "dst": "E1", "where": "a.py:10"}],
                 security=[{"surface": "POST /pay", "who": "admin", "source": "a.py:5"}])
    with tempfile.TemporaryDirectory() as td:
        mp, vp = write(td, m)
        from coyodex.audit_model import l2_worklist_model
        sec_claim = next(w.claim for w in l2_worklist_model(load_model_path(mp))
                         if w.claim.startswith("Auth surface 'POST /pay'"))
        Path(vp).write_text(json.dumps({"grounding": [
            make_vote(sec_claim, True, "a.py:88"), make_vote(sec_claim, True, "a.py:88")]}),
            encoding="utf-8")
        assert fix.main(["apply-drift", "--map", mp, "--verdicts", vp, "--tolerance", "0"]) == 0
        out = load_model_path(mp)
        assert out.security[0].source == "a.py:88"                  # security anchor rewritten
        assert out.edges[0].where == "a.py:10"                      # the edge (not in verdicts) untouched


def test_apply_drift_skips_ambiguous_multi_where_edge():
    # Two edges share (src,verb,dst) but different call sites → one worklist claim matches 2 edges.
    # Blind-writing both is wrong, so apply-drift skips them.
    m = make_map([
        {"src": "C1", "verb": "persists", "dst": "E1", "where": "a.py:10"},
        {"src": "C1", "verb": "persists", "dst": "E1", "where": "b.py:10"}])
    verdicts = {"grounding": [make_vote("C1 persists E1", True, "a.py:50"),
                              make_vote("C1 persists E1", True, "a.py:50")]}
    with tempfile.TemporaryDirectory() as td:
        mp, vp = write(td, m, verdicts)
        assert fix.main(["apply-drift", "--map", mp, "--verdicts", vp, "--tolerance", "0"]) == 0
        wheres = sorted(e.where for e in load_model_path(mp).edges)
        assert wheres == ["a.py:10", "b.py:10"]    # both untouched


# --- drop-edge ------------------------------------------------------------------

def _flow_map() -> dict:
    return make_map(
        [{"src": "C1", "verb": "persists", "dst": "E1", "where": "a.py:10"}],
        flows=[{"uc": "UC1", "title": "Do", "steps": [
            {"n": 1, "src": "C1", "dst": "E1", "phrase": "writes it", "where": "a.py:10"}]}])


def test_drop_edge_removes_edge_and_reports_riding_steps():
    with tempfile.TemporaryDirectory() as td:
        mp, _ = write(td, _flow_map())
        assert fix.main(["drop-edge", "--map", mp, "C1", "persists", "E1"]) == 0
        out = load_model_path(mp)
        assert out.edges == []                          # edge gone
        assert out.flows[0].steps[0].dst == "E1"        # step left in place for a hand reconcile


def test_drop_edge_repoint_heals_the_riding_step():
    with tempfile.TemporaryDirectory() as td:
        mp, _ = write(td, _flow_map())
        assert fix.main(["drop-edge", "--map", mp, "C1", "persists", "E1", "--repoint", "E2"]) == 0
        out = load_model_path(mp)
        assert out.edges == []
        assert out.flows[0].steps[0].dst == "E2"        # step re-pointed


def test_drop_edge_missing_edge_errors():
    with tempfile.TemporaryDirectory() as td:
        mp, _ = write(td, _flow_map())
        assert fix.main(["drop-edge", "--map", mp, "C1", "reads", "E1"]) == 1


# --- dedup-relation -------------------------------------------------------------

def _reciprocal_map() -> dict:
    return make_map([], entities=[
        {"id": "E1", "name": "Org", "relations": [{"verb": "contains", "target": "E2"}]},
        {"id": "E2", "name": "Member", "relations": [{"verb": "references", "target": "E1"}]}])


def test_dedup_relation_lists_then_drops_chosen_side():
    with tempfile.TemporaryDirectory() as td:
        mp, _ = write(td, _reciprocal_map())
        assert fix.main(["dedup-relation", "--map", mp]) == 0            # list mode
        assert fix.main(["dedup-relation", "--map", mp, "--drop", "E2:references:E1"]) == 0
        out = load_model_path(mp)
        assert out.entities[1].relations == []                          # dropped side
        assert len(out.entities[0].relations) == 1                      # kept side intact


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
