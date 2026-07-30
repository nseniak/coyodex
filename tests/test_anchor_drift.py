"""Tests for `coyodex anchor-drift` (Phase G build command)."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
from pathlib import Path

from coyodex import anchor_drift as ad
from coyodex import audit_model
from coyodex.audit_model import WorkItem, l2_worklist_model
from coyodex.model import FORMAT, load_model


def make_item(claim: str, anchor: str, drift_eligible: bool = True) -> WorkItem:
    return WorkItem(claim=claim, anchor=anchor, why_risky="risk", drift_eligible=drift_eligible)


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


# --- report-only claims are never anchor-nudged -------------------------------------------------
# A structured-store claim ("E1 (Guild) is stored in D1 container 'guilds'") is anchored at the
# entity's TYPE DEFINITION by the domain-card contract — deliberately NOT the line the write happens
# on. So when the Phase-4 skeptics confirm it and report the WRITE site, that gap is not drift: it is
# the contract working. A real build produced 13 drift findings of which NINE were this class, and
# the lead had to hand-filter them out before `fix apply-drift` — the hand-scripting method.md
# forbids. The suppression is a property of the claim (`drift_eligible`), never a text match.

def make_store_map() -> dict:
    """A map with BOTH an entity store claim (report-only, anchored at the type definition) and a
    plain backbone edge (drift-eligible, anchored at the call site). Both anchors are 40 lines away
    from where the skeptics will say the action happens."""
    return {
        "format": FORMAT, "title": "t", "goal": "g",
        "components": [{"id": "C1", "name": "Repo", "source": "repo.py:1"},
                       {"id": "C2", "name": "Api", "source": "api.py:1"}],
        "deps": [{"id": "D1", "name": "MongoDB", "kind": "datastore", "type": "document db"}],
        "entities": [{"id": "E1", "name": "Guild", "source": "domain/guild.py:9",
                      "store": {"dep": "D1", "container": "guilds", "mode": "collection"}}],
        "edges": [{"src": "C1", "verb": "reads", "dst": "C2", "where": "repo.py:245"}],
    }


def make_claims() -> tuple[list[WorkItem], str, str]:
    """(worklist, store-claim text, edge-claim text) built by the real worklist builder — so the
    test exercises the shipped `drift_eligible` wiring, not a hand-set flag."""
    wl = l2_worklist_model(load_model(json.dumps(make_store_map())))
    store = next(w.claim for w in wl if "is stored in" in w.claim)
    edge = next(w.claim for w in wl if w.claim.startswith("C1 "))
    return wl, store, edge


def test_store_claim_is_marked_report_only_in_the_worklist():
    wl, store, edge = make_claims()
    by_claim = {w.claim: w for w in wl}
    assert by_claim[store].drift_eligible is False
    assert by_claim[store].anchor == "domain/guild.py:9"   # the TYPE definition, by contract
    assert by_claim[edge].drift_eligible is True


def test_confirmed_store_claim_yields_no_drift_finding_and_no_apply_drift_record():
    wl, store, _edge = make_claims()
    # skeptics confirm the claim and report the WRITE site — 200 lines from the type definition.
    grounding = [make_vote(store, True, "repo/guild_repo.py:212"),
                 make_vote(store, True, "repo/guild_repo.py:212")]
    assert ad.drift_findings(wl, grounding, tolerance=0) == []
    assert ad.drift_records(wl, grounding, tolerance=0) == []


def test_confirmed_edge_claim_still_drifts_when_a_store_claim_is_present():
    # the suppression is per-claim, not a global off switch: the edge in the SAME worklist,
    # confirmed by the SAME verdicts file, must still be flagged and still reach `fix apply-drift`.
    wl, store, edge = make_claims()
    grounding = [make_vote(store, True, "repo/guild_repo.py:212"),
                 make_vote(store, True, "repo/guild_repo.py:212"),
                 make_vote(edge, True, "repo.py:243"),
                 make_vote(edge, True, "repo.py:243")]
    found = ad.drift_findings(wl, grounding, tolerance=0)
    assert [w.claim for w, _d in found] == [edge]
    recs = ad.drift_records(wl, grounding, tolerance=0)
    assert [r["claim"] for r in recs] == [edge]
    assert recs[0]["corrected"] == "repo.py:243"


def test_refuted_store_claim_still_surfaces_to_the_skeptics():
    # ONLY the anchor nudge is suppressed. The store claim is still in the worklist the skeptics are
    # farmed from, and still carried by `audit --json` — so a skeptic can still refute it and the
    # lead still re-authors the row. Marking it report-only must not hide the claim.
    wl, store, _edge = make_claims()
    assert store in [w.claim for w in wl]
    with tempfile.TemporaryDirectory() as td:
        mp = Path(td) / "map.json"
        mp.write_text(json.dumps(make_store_map()), encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert audit_model.main([str(mp), "--json"]) == 0
        payload = json.loads(buf.getvalue())
    claims = [w["claim"] for w in payload["worklist"]]
    assert store in claims
    # `audit --json` keeps its published shape — the new flag is in-process only (anchor-drift
    # rebuilds the worklist from the map), so no Phase-4 consumer of this JSON has to change.
    assert all(set(w) == {"claim", "anchor", "detail", "why_risky", "theme", "drift_eligible"}
               for w in payload["worklist"])
    # the store claim is report-only by contract, and the payload now says so out loud
    assert all(w["theme"] == "persistence" and w["drift_eligible"] is False
               for w in payload["worklist"] if w["claim"] == store)


def test_refuted_report_only_claim_produces_no_drift_either():
    # a refuted claim was never drift-evaluated (no strict majority) — that stays true, and the
    # report-only skip must not turn a refutation into a silent confirmation.
    wl, store, _edge = make_claims()
    grounding = [make_vote(store, False, "domain/guild.py:9"),
                 make_vote(store, False, "domain/guild.py:9")]
    assert ad.drift_findings(wl, grounding, tolerance=0) == []
    assert ad.drift_records(wl, grounding, tolerance=0) == []


def make_declaration_anchored_doc() -> dict:
    """A map carrying one of each declaration-anchored claim kind, every one CITING its own
    declaring line (`messaging.source`, `states.source`, `cadence_source`)."""
    return {
        "format": FORMAT, "title": "t", "goal": "g",
        "components": [{"id": "C1", "name": "Worker", "source": "w.py:1"},
                       {"id": "C2", "name": "Consumer", "source": "c.py:1"}],
        "deps": [{"id": "D1", "name": "Redis", "kind": "messaging", "type": "queue broker"}],
        "messaging": [{"name": "JOB_QUEUE", "kind": "job-queue", "broker": "D1",
                       "publishers": ["C1"], "consumers": ["C2"], "source": "queues.py:3"}],
        "entities": [{"id": "E1", "name": "Job", "source": "job.py:2",
                      "store": {"dep": "D1", "container": "jobs", "mode": "collection"},
                      "states": {"states": ["NEW", "DONE"], "source": "job.py:20"}}],
        "entry_points": [{"kind": "cron", "trigger": "nightly", "component": "C1",
                          "cadence": "0 3 * * *", "cadence_source": "cron.py:7"}],
    }


def _row(wl: list, needle: str):
    return next(w for w in wl if needle in w.claim)


def test_a_claim_sent_to_a_different_kind_of_line_than_its_anchor_is_not_drift_evaluated():
    # Store and messaging anchors point at a DECLARATION while the skeptic is sent to a CALL SITE
    # (the write site, the enqueue/consume site). A difference between two different kinds of line
    # is not evidence of anything, so it must not be reported as drift.
    wl = l2_worklist_model(load_model(json.dumps(make_declaration_anchored_doc())))
    for needle in ("is stored in", "Channel '"):
        row = _row(wl, needle)
        assert row.drift_eligible is False, row.claim
        votes = [make_vote(row.claim, True, "elsewhere.py:900")] * 2
        assert ad.drift_findings(wl, votes, tolerance=0) == []


def test_a_claim_sent_to_the_SAME_line_its_anchor_cites_IS_drift_evaluated():
    # The opposite case, and the one an over-broad sweep silently broke. A state machine citing its
    # own `source` sends the skeptic to *the declaring enum* — the very line the anchor points at —
    # so a difference IS drift. Same for a cadence that cites `cadence_source`. This is the ONLY
    # line-level check these anchors have: `check_state_sources_model` reads the whole file text, so
    # a declaration that MOVES INSIDE its file is invisible to it.
    wl = l2_worklist_model(load_model(json.dumps(make_declaration_anchored_doc())))
    for needle in ("has states [", "runs on cadence"):
        row = _row(wl, needle)
        assert row.drift_eligible is True, row.claim
        votes = [make_vote(row.claim, True, "job.py:46")] * 2
        assert any(needle in w.claim for w, _d in ad.drift_findings(wl, votes, tolerance=0)), \
            f"a moved declaration must be reported for {needle!r}"
        assert any(needle in r["claim"] for r in ad.drift_records(wl, votes, tolerance=0)), \
            f"and must reach the apply-drift record for {needle!r}"


def test_an_UNCITED_declaration_anchor_falls_back_to_a_different_line_and_is_not_evaluated():
    # Without its own `source`, a state machine anchors the ENTITY's line and an inferred cadence
    # anchors the ENTRY POINT's line — neither ever declared the thing being claimed, so the
    # same different-kind-of-line reasoning applies and drift there is noise.
    doc = make_declaration_anchored_doc()
    doc["entities"][0]["states"].pop("source")
    doc["entry_points"][0].pop("cadence_source")
    wl = l2_worklist_model(load_model(json.dumps(doc)))
    for needle in ("has states [", "runs on cadence"):
        assert _row(wl, needle).drift_eligible is False, needle


def test_a_split_vote_is_a_tie_in_either_order_and_votes_are_never_deduped():
    """Two facts, one of which cost a reverted change.

    First: a review claimed a split vote was "decided by file-sort order". That is FALSE — the tally
    has always been a strict majority, so 1-grounded/1-refuted is a tie whichever order the rows
    arrive in.

    Second, and the reason there is NO dedupe here: collapsing identical `(claim, grounded, evidence)`
    triples looks like a fix for double-counted verdicts files and is worse in both directions.
    Refutations carry no evidence line by convention, so every refutation of a claim would collapse to
    ONE vote — turning a genuine 2-2 tie into 2-1 confirmed, exactly the failure it was meant to
    prevent. And two independent skeptics that agree on the same line are indistinguishable from one
    row seen twice: on this repo's own recorded build, two independent reads of the security batch
    agree exactly on 37 of 40 claims. A correct fix needs a per-vote identity the verdicts format does
    not carry."""
    from coyodex.anchor_drift import _confirmed_drifts
    from coyodex.audit_model import WorkItem
    w = WorkItem(claim="C1 reads E1", anchor="a.py:10", why_risky="x", theme="ownership")
    yes = {"claim": "C1 reads E1", "grounded": True, "evidence": "a.py:40"}
    no = {"claim": "C1 reads E1", "grounded": False, "evidence": ""}

    assert not _confirmed_drifts([w], [yes, no], 2)                 # a tie is not a majority
    assert not _confirmed_drifts([w], [no, yes], 2)                 # …in either order
    assert not _confirmed_drifts([w], [yes, no, dict(no)], 2)       # 1-2 against
    # Two independent agreeing skeptics outvote one dissenter — the case a dedupe would have broken.
    assert _confirmed_drifts([w], [yes, dict(yes), no], 2)
    # …and N refutations are N votes, not one: a real 2-2 tie stays a tie.
    assert not _confirmed_drifts([w], [yes, {**yes, "evidence": "a.py:41"}, no, dict(no)], 2)
