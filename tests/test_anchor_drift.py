"""Tests for `coyodex anchor-drift` (Phase G build command)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyodex import anchor_drift as ad
from coyodex.audit_model import WorkItem


def make_item(claim: str, anchor: str) -> WorkItem:
    return WorkItem(claim=claim, anchor=anchor, why_risky="risk")


def make_vote(claim: str, grounded: bool, evidence: str) -> dict:
    return {"claim": claim, "grounded": grounded, "evidence": evidence}


def test_drift_flags_confirmed_claim_with_drifted_anchor():
    wl = [make_item("C1 reads E1", "org_service.py:245")]
    grounding = [make_vote("C1 reads E1", True, "org_service.py:243"),
                 make_vote("C1 reads E1", True, "org_service.py:243")]
    found = ad.drift_findings(wl, grounding, tolerance=0)
    assert len(found) == 1 and found[0][1].drifted
    assert ad.drift_findings(wl, grounding, tolerance=2) == []  # within tolerance → no drift


def test_drift_skips_unconfirmed_claim():
    # only a tie (1 of 2 grounded) → not a strict majority → not evaluated for drift.
    wl = [make_item("C1 reads E1", "a.py:245")]
    grounding = [make_vote("C1 reads E1", False, "a.py:1"),
                 make_vote("C1 reads E1", True, "a.py:1")]
    assert ad.drift_findings(wl, grounding, tolerance=0) == []


def test_drift_records_carry_the_corrected_where():
    # drift_records (feeds --json and `fix apply-drift`) computes the corrected `path:line` — the
    # consensus (median) grounded evidence — so the two consumers can never disagree.
    wl = [make_item("C1 reads E1", "org_service.py:245")]
    grounding = [make_vote("C1 reads E1", True, "org_service.py:243"),
                 make_vote("C1 reads E1", True, "org_service.py:243")]
    recs = ad.drift_records(wl, grounding, tolerance=0)
    assert len(recs) == 1
    assert recs[0]["claim"] == "C1 reads E1"
    assert recs[0]["corrected"] == "org_service.py:243"
    assert recs[0]["same_file"] is True


def test_consensus_evidence_prefers_the_same_file_group():
    # a stray different-file vote must not pull the consensus off the stored file.
    got = ad.consensus_evidence("a.py:10", ["a.py:12", "a.py:12", "z.py:99"])
    assert got == "a.py:12"


def test_drift_cli_end_to_end():
    # A tiny map with one edge whose `where` is line 245; skeptics confirm the claim but report 243.
    from coyodex.audit_model import l2_worklist_model
    from coyodex.model import FORMAT, load_model
    edge_map = {
        "format": FORMAT, "title": "t", "goal": "g",
        "components": [{"id": "C1", "name": "A", "source": "a.py:1"},
                       {"id": "C2", "name": "B", "source": "b.py:1"}],
        "edges": [{"src": "C1", "verb": "reads", "dst": "C2", "where": "a.py:245"}],
    }
    claim = l2_worklist_model(load_model(json.dumps(edge_map)))[0].claim
    verdicts = {"grounding": [make_vote(claim, True, "a.py:243"),
                              make_vote(claim, True, "a.py:243")]}
    with tempfile.TemporaryDirectory() as td:
        mp = Path(td) / "map.json"
        vp = Path(td) / "verdicts.json"
        mp.write_text(json.dumps(edge_map), encoding="utf-8")
        vp.write_text(json.dumps(verdicts), encoding="utf-8")
        assert ad.main(["--map", str(mp), "--verdicts", str(vp), "--tolerance", "0"]) == 0
        assert ad.main(["--map", str(mp), "--verdicts", str(vp), "--tolerance", "2"]) == 0
