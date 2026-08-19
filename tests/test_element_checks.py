#!/usr/bin/env python3
"""Tests for `coyodex grounding by-element` — what the pass DID, beside what the author TYPED.

Nothing in the tooling ever writes `confidence`. So an element three skeptics confirmed reads
exactly as its harvesting agent left it, and a reader cannot tell a proved claim from an unopened
one. These tests pin the two halves of the fix: every pinned claim resolves back onto the element
that makes it, and an authored label the votes do not support is called out rather than trusted.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_element_checks.py
    pytest tests/test_element_checks.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyodex.audit_model import (apply_anchor_corrections, resolve_claim, rule_site_claim,
                                 store_claim)
from coyodex.grounding import element_checks, format_element_checks, main
from coyodex.model import FORMAT, load_model


# --- builders -------------------------------------------------------------------

def make_map(*, rules: list[dict] | None = None, confidence: str = "inferred",
             component_confidence: str = "verified") -> dict:
    """One component, one stored entity and (by default) one single-site rule."""
    return {
        "format": FORMAT, "title": "t", "goal": "g",
        "use_cases": [{"id": "UC1", "name": "Do"}],
        "components": [{"id": "C1", "name": "A", "source": "a.py:1", "purpose": "does a thing",
                        "confidence": component_confidence}],
        "entities": [{"id": "E1", "name": "Thing",
                      "store": {"dep": "D1", "container": "things", "mode": "collection"}}],
        "deps": [{"id": "D1", "name": "db"}],
        "edges": [],
        "blocks": [{"id": "BLK1", "name": "Access"}],
        "rules": rules if rules is not None else [
            {"id": "BR1", "name": "Owner only", "statement": "Only an owner may delete an org.",
             "block": "BLK1", "confidence": confidence,
             "sites": [{"where": "a.py:7", "why": "refuses a non-owner"}]}],
    }


def make_model(**kw: object):
    return load_model(json.dumps(make_map(**kw)))    # type: ignore[arg-type]


def make_vote(claim: str, grounded: object) -> dict:
    return {"claim": claim, "grounded": grounded, "evidence": "a.py:7"}


def site_claim(m, rule_index: int = 0, site_index: int = 0) -> str:
    """The worklist's wording for one rule site, built the one way the worklist builds it."""
    br = m.rules[rule_index]
    site = br.sites[site_index]
    return rule_site_claim(br.statement, (site.where or "").strip(), site.why)


def row_for(rows: list, element_id: str):
    hits = [r for r in rows if r.element_id == element_id]
    assert len(hits) == 1, f"expected exactly one row for {element_id}, got {len(hits)}"
    return hits[0]


# --- the headline: a label the votes do not support ------------------------------

def test_a_rule_three_skeptics_confirmed_still_reads_inferred_and_the_row_says_so():
    """THE defect. On a live map every business rule read `inferred` after each of its sites had
    been confirmed by three independent skeptics, because no code path writes the field. The row
    keeps both facts side by side instead of picking one."""
    m = make_model(confidence="inferred")
    claim = site_claim(m)
    rows, _ = element_checks(m, [claim], [make_vote(claim, True)] * 3)
    r = row_for(rows, "BR1")
    assert r.stated == "inferred"          # what the author typed, untouched
    assert r.status == "confirmed"         # what the pass actually did
    assert r.disagrees                     # and the pair is flagged, not silently reconciled


def test_a_verified_element_nobody_challenged_is_flagged_the_same_way():
    """The opposite direction, and the more dangerous one: the author asserted `verified` and no
    skeptic ever opened the claim. Reading the label alone, that element is indistinguishable from
    one three skeptics proved."""
    m = make_model(confidence="verified")
    rows, _ = element_checks(m, [site_claim(m)], [])
    r = row_for(rows, "BR1")
    assert (r.stated, r.status, r.unvoted) == ("verified", "unchecked", 1)
    assert r.disagrees


def test_a_verified_element_the_pass_confirmed_is_not_flagged():
    """The agreeing case must stay quiet, or the flag means nothing."""
    m = make_model(confidence="verified")
    claim = site_claim(m)
    rows, _ = element_checks(m, [claim], [make_vote(claim, True)])
    assert not row_for(rows, "BR1").disagrees


def test_an_element_whose_kind_carries_no_confidence_is_never_flagged():
    """An edge and a cadenced entry point have no `confidence` field, so there is no authored label
    to contradict. Flagging them would report the map's schema as a defect on every row."""
    m = make_model()
    claim = store_claim("E1", "Thing", "D1", "things", "collection")
    rows, _ = element_checks(m, [claim], [make_vote(claim, True)])
    r = row_for(rows, "E1")
    assert r.stated == "" and not r.disagrees


# --- one row per element ---------------------------------------------------------

def test_a_rule_with_three_sites_is_one_row_and_not_three():
    """A rule makes one claim per site. Keying the tally on the SITE printed the same rule three
    times, so a reader counting rows over-counted the map's rules."""
    m = make_model(rules=[{"id": "BR1", "name": "Owner only",
                           "statement": "Only an owner may delete an org.", "block": "BLK1",
                           "confidence": "verified",
                           "sites": [{"where": "a.py:7", "why": "refuses a non-owner"},
                                     {"where": "b.py:9", "why": "refuses it again on the API"},
                                     {"where": "c.py:3", "why": "and once more in the worker"}]}])
    claims = [site_claim(m, 0, i) for i in range(3)]
    rows, unresolved = element_checks(m, claims, [make_vote(c, True) for c in claims])
    assert not unresolved
    assert len([r for r in rows if r.element_id == "BR1"]) == 1
    assert row_for(rows, "BR1").claims == 3        # all three sites still counted


def test_one_refuted_site_outranks_two_confirmed_ones():
    """The element makes three claims and one of them is wrong. A majority-of-rows reading would
    call the rule confirmed, which is exactly the reassurance the row exists to withhold."""
    m = make_model(rules=[{"id": "BR1", "name": "Owner only",
                           "statement": "Only an owner may delete an org.", "block": "BLK1",
                           "confidence": "verified",
                           "sites": [{"where": "a.py:7", "why": "one"},
                                     {"where": "b.py:9", "why": "two"},
                                     {"where": "c.py:3", "why": "three"}]}])
    claims = [site_claim(m, 0, i) for i in range(3)]
    votes = [make_vote(claims[0], True), make_vote(claims[1], True), make_vote(claims[2], False)]
    r = row_for(element_checks(m, claims, votes)[0], "BR1")
    assert r.status == "refuted" and (r.confirmed, r.refuted) == (2, 1)


def test_a_partly_voted_element_is_not_called_confirmed():
    """"Some of it was checked" is not "it was checked" — the same distinction the record keeps
    between a tie and a stated `unverifiable`."""
    m = make_model(rules=[{"id": "BR1", "name": "Owner only",
                           "statement": "Only an owner may delete an org.", "block": "BLK1",
                           "confidence": "verified",
                           "sites": [{"where": "a.py:7", "why": "one"},
                                     {"where": "b.py:9", "why": "two"}]}])
    claims = [site_claim(m, 0, i) for i in range(2)]
    r = row_for(element_checks(m, claims, [make_vote(claims[0], True)])[0], "BR1")
    assert r.status == "part-checked" and (r.confirmed, r.unvoted) == (1, 1)
    assert r.disagrees          # it says `verified`, and half of it was never opened


def test_a_tie_lands_on_unverifiable_not_on_a_silent_win():
    """Reuses `_verdict_bucket`, so the per-element view and the record cannot disagree about what
    an unsettled claim is."""
    m = make_model(confidence="verified")
    claim = site_claim(m)
    r = row_for(element_checks(m, [claim], [make_vote(claim, True), make_vote(claim, False)])[0],
                "BR1")
    assert r.status == "unverifiable"


# --- claims that name no element -------------------------------------------------

def test_a_claim_naming_no_element_is_reported_and_never_dropped():
    """The pinned worklist is a snapshot. A claim whose wording the method changed afterwards
    resolves to nothing, and a growing unresolved list is how a reader LEARNS that — silently
    dropping it would report a map as fully checked on the strength of verdicts it cannot place."""
    m = make_model()
    stale = "Auth surface 'gone' is protected by: nothing"
    rows, unresolved = element_checks(m, [stale], [make_vote(stale, True)])
    assert unresolved == [stale]
    # The verdict is placed on nothing, so nothing in the map may claim it: every element of this
    # map still reads `unchecked`, which is the honest state.
    assert rows and all(r.status == "unchecked" for r in rows)


def test_an_element_the_worklist_never_claimed_still_appears_as_unchecked():
    """ABSENCE IS THE FALSE NEGATIVE. A rule missing from the table reads exactly like a rule that
    passed. On a live map two rules the author had labelled `verified` carried no pinned claim at
    all, so a report built only from the worklist would have shown neither."""
    m = make_model(confidence="verified")
    other = store_claim("E1", "Thing", "D1", "things", "collection")
    rows, _ = element_checks(m, [other], [make_vote(other, True)])
    r = row_for(rows, "BR1")
    assert (r.claims, r.status) == (0, "unchecked")
    assert r.disagrees          # it says `verified` and nobody ever opened it


def test_an_element_the_worklist_would_never_claim_is_not_called_unchecked():
    """A rule whose every site declares `no_call_site` makes no L2 claim, so nothing was ever going
    to check it. Listing it as a gap would invent one."""
    m = make_model(rules=[{"id": "BR1", "name": "By construction",
                           "statement": "An org id is a type the database refuses to widen.",
                           "block": "BLK1", "confidence": "verified",
                           "sites": [{"why": "enforced by the column type", "no_call_site": True}]}])
    rows, _ = element_checks(m, [], [])
    assert not [r for r in rows if r.element_id == "BR1"]


def test_a_repeated_claim_is_counted_once():
    """De-duplicated exactly as the record is, so the two cannot disagree about the same map."""
    m = make_model()
    claim = site_claim(m)
    rows, _ = element_checks(m, [claim, claim], [make_vote(claim, True)])
    assert row_for(rows, "BR1").claims == 1


# --- the resolver, which both the writer and this report now share ---------------

def test_resolve_claim_names_the_rule_a_site_claim_belongs_to():
    m = make_model()
    t = resolve_claim(m, site_claim(m)).target
    assert t is not None
    assert (t.kind, t.element_id, t.sub) == ("rule_site", "BR1", 0)


def test_resolve_claim_names_the_entity_a_store_claim_belongs_to():
    """The store claim was built inline in the worklist and had no resolver, so every persistence
    verdict resolved to nothing and no entity could show that it had been checked."""
    m = make_model()
    t = resolve_claim(m, store_claim("E1", "Thing", "D1", "things", "collection")).target
    assert t is not None
    assert (t.kind, t.element_id) == ("store", "E1")


def test_resolve_claim_reports_the_kind_when_nothing_matches():
    m = make_model()
    match = resolve_claim(m, "Auth surface 'gone' is protected by: nothing")
    assert match.target is None and match.kind == "" and match.count == 0


def test_the_writer_refuses_a_store_claim_in_words_rather_than_by_accident():
    """A store row is anchored at the entity's DECLARING line, not at the write site a skeptic
    reads, so its anchor must not be nudged toward the evidence. That refusal used to happen by
    falling through every branch and writing nothing; now it is stated."""
    m = make_model()
    claim = store_claim("E1", "Thing", "D1", "things", "collection")
    counts, notes = apply_anchor_corrections(m, [(claim, "z.py:99")])
    assert sum(counts.values()) == 0
    assert any("carries no anchor a correction may move" in n for n in notes)


def test_the_writer_still_names_a_claim_that_matches_nothing():
    """The legacy wording other tests and a live reconcile depend on."""
    m = make_model()
    _counts, notes = apply_anchor_corrections(
        m, [("Auth surface 'gone' is protected by: nothing", "z.py:9")])
    assert any("matches no edge, security surface, rule site," in n for n in notes)


# --- the report and the CLI ------------------------------------------------------

def test_the_report_names_the_disagreeing_elements_before_the_agreeing_ones():
    m = make_model(confidence="inferred")
    claim = site_claim(m)
    store = store_claim("E1", "Thing", "D1", "things", "collection")
    rows, unresolved = element_checks(m, [claim, store],
                                      [make_vote(claim, True), make_vote(store, True)])
    text = format_element_checks(rows, unresolved)
    assert "disagrees" in text
    assert text.index("BR1") < text.index("E1")


def test_the_report_can_be_narrowed_to_one_kind():
    m = make_model()
    claim = site_claim(m)
    store = store_claim("E1", "Thing", "D1", "things", "collection")
    rows, unresolved = element_checks(m, [claim, store],
                                      [make_vote(claim, True), make_vote(store, True)])
    text = format_element_checks(rows, unresolved, only_kind="rule_site")
    assert "BR1" in text and "\nE1" not in text


def test_the_json_report_carries_the_unresolved_claims_too():
    m = make_model()
    stale = "Auth surface 'gone' is protected by: nothing"
    claim = site_claim(m)
    rows, unresolved = element_checks(m, [claim, stale], [make_vote(claim, True)])
    doc = json.loads(format_element_checks(rows, unresolved, as_json=True))
    assert doc["unresolved_claims"] == [stale]
    br1 = [e for e in doc["elements"] if e["id"] == "BR1"]
    assert br1 and br1[0]["disagrees"] is True and br1[0]["status"] == "confirmed"


def test_the_cli_refuses_without_a_map_rather_than_printing_an_empty_table():
    """An empty table reads like "nothing was checked" — the exact false negative this command
    exists to expose."""
    with tempfile.TemporaryDirectory() as td:
        wl = Path(td) / "wl.json"
        wl.write_text(json.dumps({"worklist": [{"claim": "C1 reads E1"}]}), encoding="utf-8")
        vp = Path(td) / "v.json"
        vp.write_text(json.dumps({"grounding": [make_vote("C1 reads E1", True)]}), encoding="utf-8")
        assert main(["by-element", "--worklist", str(wl), "--verdicts", str(vp)]) == 2


def test_the_cli_prints_the_table_when_given_a_map(capsys):
    m = make_map(confidence="inferred")
    claim = rule_site_claim("Only an owner may delete an org.", "a.py:7", "refuses a non-owner")
    with tempfile.TemporaryDirectory() as td:
        mp = Path(td) / "map.json"
        mp.write_text(json.dumps(m), encoding="utf-8")
        wl = Path(td) / "wl.json"
        wl.write_text(json.dumps({"worklist": [{"claim": claim}]}), encoding="utf-8")
        vp = Path(td) / "v.json"
        vp.write_text(json.dumps({"grounding": [make_vote(claim, True)]}), encoding="utf-8")
        assert main(["by-element", "--worklist", str(wl), "--verdicts", str(vp),
                     "--map", str(mp)]) == 0
    out = capsys.readouterr().out
    assert "BR1" in out and "inferred" in out and "confirmed" in out


if __name__ == "__main__":     # pragma: no cover
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
