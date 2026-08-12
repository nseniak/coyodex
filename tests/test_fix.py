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


def test_a_drifted_cadence_anchor_is_written_not_refused(capsys):
    """Two defects, one fixture. FIRST: a cadence claim fell through to the security branch and was
    reported as a security surface matching 0 rows, while the summary said "no drifted edge or
    security anchors to rewrite" — two true statements that together told the operator nothing.
    THEN, once it was named correctly, it was still REFUSED: `cadence_source` is a real schema field
    and `apply-drift` had no writer for it, so a live build had five cadence drifts handed back and
    re-typed them through a bespoke script."""
    m = make_map([], entities=[{"id": "E1", "name": "Thing"}])
    m["entry_points"] = [{"kind": "job", "trigger": "nightly sweep", "component": "C1",
                          "source": "a.py:1", "cadence": "every 24h", "cadence_source": "a.py:2"}]
    claim = "Entry point [job] nightly sweep runs on cadence 'every 24h'"
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "a.py").write_text("x = 1\n" * 40, encoding="utf-8")
        mp, vp = write(td, m, {"grounding": [make_vote(claim, True, "a.py:30")]})
        assert fix.main(["apply-drift", "--map", mp, "--verdicts", vp]) == 0
        out = capsys.readouterr()
        assert load_model_path(Path(mp)).entry_points[0].cadence_source == "a.py:30"
    combined = out.out + out.err
    assert "matches 0 security surfaces" not in combined, combined
    assert "cadence_source" in combined and "1 cadence anchor(s)" in combined


def test_the_not_applicable_count_rides_the_final_line(capsys):
    """A live build read this output with `| tail -12`, so a total that is not on the last line is a
    total the reader never sees — the same lesson as assemble's unhealed-riding-step count."""
    m = make_map([], entities=[{"id": "E1", "name": "Thing", "states": {
        "source": "a.py:2", "states": ["NEW", "DONE"],
        "transitions": [{"src": "NEW", "dst": "DONE", "on": "finish"}]}}])
    claim = "E1 (Thing) has states [NEW, DONE] with 1 transition(s)"
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "a.py").write_text("x = 1\n" * 40, encoding="utf-8")
        mp, vp = write(td, m, {"grounding": [make_vote(claim, True, "a.py:30")]})
        fix.main(["apply-drift", "--map", mp, "--verdicts", vp])
        out = capsys.readouterr()
    last = [ln for ln in out.out.splitlines() if ln.strip()][-1]
    assert "NOT APPLICABLE" in last and "1 drift(s)" in last, last


def test_an_edge_anchor_is_still_rewritten_and_says_so_on_the_last_line(capsys):
    """The other half: the kinds it CAN write must keep working, and the summary stays truthful."""
    m = make_map([{"src": "C1", "verb": "reads", "dst": "E1", "why": "w", "where": "a.py:1"}])
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "a.py").write_text("x = 1\n" * 40, encoding="utf-8")
        mp, vp = write(td, m, {"grounding": [make_vote("C1 reads E1", True, "a.py:30")]})
        assert fix.main(["apply-drift", "--map", mp, "--verdicts", vp]) == 0
        out = capsys.readouterr()
        assert load_model_path(Path(mp)).edges[0].where == "a.py:30"
    last = [ln for ln in out.out.splitlines() if ln.strip()][-1]
    assert "rewrote 1 edge" in last and "NOT APPLICABLE" not in last, last


def test_the_writable_theme_partition_covers_every_theme_the_audit_emits():
    """F10's pin. `_WRITABLE_THEMES` partitions `audit_model._THEMES`, in a different module, with no
    guard — so a new claim kind would silently become "not applicable", and if it were writable
    `apply-drift` would quietly stop applying it. Same shape as the `_THEMES` closed-set test."""
    from coyodex import audit_model
    known = set(audit_model._THEMES)
    assert fix._WRITABLE_THEMES <= known, fix._WRITABLE_THEMES - known
    # Every theme is on exactly one side, and the split is the documented one.
    unwritable = known - fix._WRITABLE_THEMES
    assert unwritable == {"persistence", "messaging", "lifecycle"}, unwritable


def test_an_unparseable_edge_claim_is_not_reported_as_a_missing_security_row(capsys):
    """`validate` accepts a multi-word verb, which `_EDGE_CLAIM`'s `(\\S+)` cannot match. Such a claim
    is edge-THEMED, so the theme gate passes it — and it used to reach the security writer and be
    reported as "matches 0 security surfaces", the very mislabelling this dispatch exists to kill."""
    m = make_map([{"src": "C1", "verb": "writes to", "dst": "E1", "why": "w", "where": "a.py:1"}])
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "a.py").write_text("x = 1\n" * 40, encoding="utf-8")
        mp, vp = write(td, m, {"grounding": [make_vote("C1 writes to E1", True, "a.py:30")]})
        assert fix.main(["apply-drift", "--map", mp, "--verdicts", vp]) == 0
        out = capsys.readouterr()
    combined = out.out + out.err
    assert "matches 0 security surfaces" not in combined, combined
    assert "could not parse back to an edge" in combined
    last = [ln for ln in out.out.splitlines() if ln.strip()][-1]
    assert "NOT APPLICABLE" in last, last


# --- fix dedup-edge -------------------------------------------------------------------------
#
# `validate` warned about (src, verb, dst) declared at DIFFERING call sites and no verb resolved it,
# so a live build hand-wrote a 40-line script for 24 of them and dropped 29 rows unreviewed —
# against this tool's own claim that these mechanical edits are never hand-scripted.


def make_dup_edge_map(tmp: str) -> Path:
    p = Path(tmp) / "project-map.json"
    p.write_text(json.dumps({
        "format": FORMAT, "title": "T", "goal": "g",
        "components": [{"id": "C1", "name": "A", "source": "src/a.py:1"},
                       {"id": "C2", "name": "B", "source": "src/b.py:1"}],
        "edges": [{"src": "C1", "verb": "calls", "dst": "C2", "why": "w", "where": "src/a.py:10"},
                  {"src": "C1", "verb": "calls", "dst": "C2", "why": "w", "where": "tests/a.py:99"}],
    }), encoding="utf-8")
    return p


def test_dedup_edge_lists_the_conflict_and_writes_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        before = p.read_text()
        assert fix.main(["dedup-edge", "--map", str(p)]) == 0
        assert p.read_text() == before, "listing must not edit the map"


def test_dedup_edge_keeps_the_named_anchor_and_drops_the_rest():
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        assert fix.main(["dedup-edge", "--map", str(p),
                         "--keep", "C1:calls:C2:src/a.py:10"]) == 0
        edges = load_model_path(p).edges
        assert len(edges) == 1 and edges[0].where == "src/a.py:10"


def test_dedup_edge_refuses_an_anchor_none_of_the_occurrences_has():
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        assert fix.main(["dedup-edge", "--map", str(p), "--keep", "C1:calls:C2:src/z.py:1"]) == 1
        assert len(load_model_path(p).edges) == 2, "nothing may be dropped on a bad --keep"


def test_dedup_edge_is_silent_when_there_is_no_duplicate():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "m.json"
        p.write_text(json.dumps({
            "format": FORMAT, "title": "T", "goal": "g",
            "components": [{"id": "C1", "name": "A", "source": "src/a.py:1"}],
            "edges": [],
        }), encoding="utf-8")
        assert fix.main(["dedup-edge", "--map", str(p)]) == 0


def test_apply_drift_accepts_the_repo_flag_its_sibling_requires():
    """`anchor-drift` REQUIRES --repo and the two run back-to-back on the same inputs; rejecting it
    here cost a live build a turn on `unknown argument '--repo'`."""
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        v = Path(tmp) / "verdicts.json"
        v.write_text(json.dumps({"grounding": []}), encoding="utf-8")
        assert fix.main(["apply-drift", "--map", str(p), "--verdicts", str(v),
                         "--repo", tmp]) == 0


# ── the retro findings: a sub-verb that answers --help, and an intent the flags could not express ──

def test_every_fix_sub_verb_answers_help_instead_of_erroring(capsys):
    """Four verbs answered `ERROR: unknown argument '--help'` because each per-verb parser treats an
    unknown flag as a usage error. A live build lost seven turns to this on `dedup-edge`."""
    for verb in ("apply-drift", "drop-edge", "dedup-relation", "dedup-edge"):
        assert fix.main([verb, "--help"]) == 0, verb
        out = capsys.readouterr().out
        assert verb in out and out.strip(), f"{verb} printed no help"


def test_dedup_edge_json_is_parseable_and_says_whether_repo_ranked():
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        before = p.read_text()
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            assert fix.main(["dedup-edge", "--map", str(p), "--json"]) == 0
        payload = json.loads(buf.getvalue())
        assert payload["repo_ranked"] is False
        assert len(payload["conflicts"]) == 1
        c = payload["conflicts"][0]
        assert (c["src"], c["verb"], c["dst"]) == ("C1", "calls", "C2")
        assert c["keep_token"].startswith("C1:calls:C2:")
        assert c["suggested"] in c["anchors"]
        assert p.read_text() == before, "--json must not edit the map"


def test_dedup_edge_accept_suggested_resolves_every_conflict():
    """"Take every suggestion" was the intent behind all four failed shell harvests; it had no flag."""
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        assert fix.main(["dedup-edge", "--map", str(p), "--accept-suggested"]) == 0
        edges = load_model_path(p).edges
        assert len(edges) == 1, "every duplicated triple must be resolved to one row"


def test_dedup_edge_says_when_suggestions_are_unranked_for_want_of_repo(capsys):
    """Without --repo the 'exists in the repo' rank term is constant, so the sort degrades to
    shortest-path. A live build passed --repo to the listing it discarded and omitted it from the
    listing it applied, and nothing in the output said the ranking had changed."""
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        assert fix.main(["dedup-edge", "--map", str(p)]) == 0
        assert "no --repo" in capsys.readouterr().out


def test_json_and_accept_suggested_are_refused_as_conflicting_intents():
    """`--json` lists without writing, `--accept-suggested` writes. Together they printed the
    listing, wrote nothing and exited 0 — a script asking to apply and report got a no-op that
    looked like success."""
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        before = p.read_text()
        assert fix.main(["dedup-edge", "--map", str(p), "--json", "--accept-suggested"]) == 2
        assert p.read_text() == before


def test_accept_suggested_never_silently_overrides_an_explicit_keep():
    """A wrong drop is unrecoverable, so the blanket flag must not quietly beat a named choice."""
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        before = p.read_text()
        assert fix.main(["dedup-edge", "--map", str(p), "--accept-suggested",
                         "--keep", "C1:calls:C2:src/b.py:20"]) == 2
        assert p.read_text() == before, "nothing may be dropped while the intent is ambiguous"


def test_grounding_sub_verbs_also_answer_help(capsys):
    """The same hole lived in a second dispatcher; only the `fix` half was covered by a test."""
    from coyodex import grounding
    for verb in ("write", "report"):
        assert grounding.main([verb, "--help"]) == 0, verb
        assert capsys.readouterr().out.strip(), f"grounding {verb} printed no help"


def test_subverb_help_falls_back_to_the_whole_usage_when_no_block_matches():
    """The fallback is the branch production actually takes for 2 of the 6 surfaces, so it is the
    one that must never print nothing."""
    from coyodex import subverb_help
    usage = "usage: tool <verb>\n\n  alpha --x\n      does alpha\n  beta --y\n      does beta\n"
    assert subverb_help.verb_block(usage, "alpha").strip().startswith("alpha")
    assert subverb_help.verb_block(usage, "nosuchverb") is None
    assert subverb_help.handle(usage, "nosuchverb", ["--help"]) == 0
    assert subverb_help.handle(usage, "alpha", []) is None, "no help asked for → carry on parsing"


def test_dedup_edge_can_record_its_decision_where_assemble_will_reread_it():
    """Writing the choice into the assembled map is what made a shipped map irreproducible from its
    own sources: 365 edges committed, 416 when its committed fragments were re-assembled, the
    difference being 49 duplicates the next assemble silently restored."""
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        before = p.read_text()
        rec = Path(tmp) / "reconcile.json"
        assert fix.main(["dedup-edge", "--map", str(p), "--accept-suggested",
                         "--to-reconcile", str(rec)]) == 0
        assert p.read_text() == before, "--to-reconcile must NOT edit the map"
        doc = json.loads(rec.read_text())
        assert len(doc["keep_edges"]) == 1
        k = doc["keep_edges"][0]
        assert (k["src"], k["verb"], k["dst"]) == ("C1", "calls", "C2") and k["where"]


def test_to_reconcile_merges_into_an_existing_file_without_duplicating():
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        rec = Path(tmp) / "reconcile.json"
        rec.write_text(json.dumps({"set": [{"ids": ["C1"], "subsystem": "S1"}]}), encoding="utf-8")
        assert fix.main(["dedup-edge", "--map", str(p), "--accept-suggested",
                         "--to-reconcile", str(rec)]) == 0
        assert fix.main(["dedup-edge", "--map", str(p), "--accept-suggested",
                         "--to-reconcile", str(rec)]) == 0
        doc = json.loads(rec.read_text())
        assert doc["set"], "an existing directive must survive"
        assert len(doc["keep_edges"]) == 1, "the same triple must not be recorded twice"


def test_the_in_place_dedup_now_says_the_edit_is_not_durable(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        assert fix.main(["dedup-edge", "--map", str(p), "--accept-suggested"]) == 0
        assert "next assemble REBUILDS" in capsys.readouterr().out


def test_to_reconcile_refuses_to_record_an_anchorless_winner():
    """`(no call site)` is the listing's DISPLAY text; `apply_reconcile` matches the stored `where`,
    which is empty for such an edge. Recording the placeholder makes a directive that can never
    match — a permanent no-op warning "none of … is anchored at '(no call site)'" on every
    assemble, phrased as drift rather than as the tool bug it is."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "m.json"
        p.write_text(json.dumps({
            "format": FORMAT, "title": "T", "goal": "g",
            "components": [{"id": "C1", "name": "A", "source": "backend/src/a.py:1"},
                           {"id": "C2", "name": "B", "source": "backend/src/b.py:1"}],
            # The sibling path must sort LONGER than "(no call site)" (14 chars), or the ranking
            # never selects the placeholder and this test passes without entering the branch —
            # which is exactly how it first shipped.
            "edges": [{"src": "C1", "verb": "calls", "dst": "C2", "no_call_site": True},
                      {"src": "C1", "verb": "calls", "dst": "C2", "where": "backend/src/a.py:10"}],
        }), encoding="utf-8")
        rec = Path(tmp) / "reconcile.json"
        # NON-ZERO: every conflict in this map was skipped, so nothing was recorded and the
        # duplicates remain. Exit 0 with an empty file is what a script reads as success.
        assert fix.main(["dedup-edge", "--map", str(p), "--accept-suggested",
                         "--to-reconcile", str(rec)]) == 1
        recorded = json.loads(rec.read_text()).get("keep_edges", [])
        assert all(k["where"] != "(no call site)" for k in recorded), recorded
        assert not recorded, "the only conflict here has an anchorless winner — nothing to record"


def test_to_reconcile_updates_a_triple_instead_of_silently_keeping_the_old_anchor(capsys):
    """Re-running with a different anchor printed `kept … at <new>` and then wrote nothing — a
    durable record asserting what the artifact did not support."""
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        rec = Path(tmp) / "reconcile.json"
        assert fix.main(["dedup-edge", "--map", str(p), "--to-reconcile", str(rec),
                         "--keep", "C1:calls:C2:src/a.py:10"]) == 0
        assert fix.main(["dedup-edge", "--map", str(p), "--to-reconcile", str(rec),
                         "--keep", "C1:calls:C2:tests/a.py:99"]) == 0
        out = capsys.readouterr().out
        keeps = json.loads(rec.read_text())["keep_edges"]
        assert len(keeps) == 1 and keeps[0]["where"] == "tests/a.py:99", keeps
        assert "UPDATED" in out


def test_to_reconcile_refuses_when_there_is_no_decision_to_record(capsys):
    """`--to-reconcile` names an OUTPUT, and the listing path returned early without ever looking at
    it: a live build ran `dedup-edge --map … --repo … --to-reconcile <file>`, got exit 0 and a full
    conflict listing, and the file was untouched. It only noticed because it read the file back
    afterwards; a build trusting the exit code ships a map whose fragments re-assemble to a
    different edge count — the exact failure this flag exists to prevent."""
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        rec = Path(tmp) / "reconcile.json"
        assert fix.main(["dedup-edge", "--map", str(p), "--to-reconcile", str(rec)]) == 2
        assert not rec.exists(), "nothing may be written when the run is refused"
        err = capsys.readouterr().err
        assert "--accept-suggested" in err and "--keep" in err, err


def test_to_reconcile_refuses_alongside_json(capsys):
    """Same shape as the existing `--json --accept-suggested` refusal: one flag lists, the other
    writes, and `--json` returns before the write path is ever reached."""
    with tempfile.TemporaryDirectory() as tmp:
        p = make_dup_edge_map(tmp)
        rec = Path(tmp) / "reconcile.json"
        assert fix.main(["dedup-edge", "--map", str(p), "--json",
                         "--to-reconcile", str(rec)]) == 2
        assert not rec.exists()
        assert "--json" in capsys.readouterr().err


def test_a_map_with_no_conflicts_is_not_an_error_whatever_the_flags(capsys):
    """The refusal was placed ABOVE the map load, so the healthy end state — nothing left to
    de-duplicate — exited 2. A pipeline that runs the dedup step unconditionally (which is what a
    durable-decision step should do) then broke precisely when the map was correct, and the message
    pushed the operator toward `--accept-suggested` on a map with nothing to accept."""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "clean.json"
        p.write_text(json.dumps(make_map([
            {"src": "C1", "verb": "calls", "dst": "C2", "why": "w", "where": "src/a.py:10"},
        ])), encoding="utf-8")
        rec = Path(tmp) / "reconcile.json"
        assert fix.main(["dedup-edge", "--map", str(p), "--to-reconcile", str(rec)]) == 0
        assert "no (src, verb, dst) edge is declared more than once" in capsys.readouterr().out


# --- security-row ---------------------------------------------------------------
# The regression these two verbs exist for: a hand script selected a refuted security row with
# `'admin' in surface.lower() and source.startswith(…)`, matched TWO rows, and overwrote a
# CONFIRMED claim with the refuted one's replacement text. Only `grounding report` caught it.


def make_security_map(rows: list[dict]) -> dict:
    return make_map([{"src": "C1", "verb": "calls", "dst": "C1", "where": "a.py:1"}], security=rows)


def test_security_row_refuses_a_selector_matching_two_rows(capsys):
    """THE headline regression, as a refusal. Two DIFFERENT surfaces share one anchor — legal — and
    a selector that cannot tell them apart must write nothing rather than take the first."""
    m = make_security_map([
        {"surface": "Admin pages", "source": "ui/Sidebar.tsx:97", "risk": "hidden only"},
        {"surface": "Role-gated navigation", "source": "ui/Sidebar.tsx:97", "risk": "real"}])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        assert fix.main(["security-row", "--map", str(p), "--at", "ui/Sidebar.tsx:97",
                         "--set-risk", "rewritten"]) == 2
        err = capsys.readouterr().err
        assert "matches 2 security row(s)" in err
        after = load_model_path(p)
        assert [s.risk for s in after.security] == ["hidden only", "real"]


def test_security_row_writes_one_row_when_the_selector_is_unambiguous(capsys):
    m = make_security_map([
        {"surface": "Admin pages", "source": "ui/Sidebar.tsx:97", "risk": "hidden only"},
        {"surface": "Role-gated navigation", "source": "ui/Sidebar.tsx:97", "risk": "real"}])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        assert fix.main(["security-row", "--map", str(p), "--at", "ui/Sidebar.tsx:97",
                         "--surface", "Admin pages", "--set-source", "api/routes.py:12",
                         "--set-risk", "backend 403 is the real gate"]) == 0
        after = load_model_path(p)
        admin = [s for s in after.security if s.surface == "Admin pages"][0]
        other = [s for s in after.security if s.surface == "Role-gated navigation"][0]
        assert admin.source == "api/routes.py:12"
        assert admin.risk == "backend 403 is the real gate"
        # The claim that must NOT have moved.
        assert (other.source, other.risk) == ("ui/Sidebar.tsx:97", "real")
        assert "grounding record no longer names it" in capsys.readouterr().out


def test_security_row_selects_by_the_exact_l2_claim(capsys):
    """The claim string is what a skeptic verdict carries back, so it is the natural selector —
    and it is unique per row even when surfaces or anchors collide."""
    m = make_security_map([
        {"surface": "Admin pages", "source": "ui/Sidebar.tsx:97"},
        {"surface": "Admin pages", "source": "api/routes.py:12"}])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        claim = fix._security_claim("Admin pages", "ui/Sidebar.tsx:97")
        assert fix.main(["security-row", "--map", str(p), "--claim", claim,
                         "--set-risk", "nothing guards the route"]) == 0
        after = load_model_path(p)
        by_anchor = {s.source: s.risk for s in after.security}
        assert by_anchor["ui/Sidebar.tsx:97"] == "nothing guards the route"
        assert by_anchor["api/routes.py:12"] == ""


def test_security_row_refuses_a_set_with_no_selector(capsys):
    m = make_security_map([{"surface": "Admin pages", "source": "ui/Sidebar.tsx:97"}])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        assert fix.main(["security-row", "--map", str(p), "--set-risk", "x"]) == 2
        assert "needs a row to write to" in capsys.readouterr().err


# --- dedup-security -------------------------------------------------------------


def test_dedup_security_keys_on_the_surface_not_the_anchor(capsys):
    """Two surfaces sharing one anchor is LEGAL and must not be offered for de-duplication —
    treating it as duplication is what made a hand script delete a real claim."""
    m = make_security_map([
        {"surface": "Admin pages", "source": "ui/Sidebar.tsx:97"},
        {"surface": "Role-gated navigation", "source": "ui/Sidebar.tsx:97"}])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        assert fix.main(["dedup-security", "--map", str(p)]) == 0
        out = capsys.readouterr().out
        assert "no security surface is authored more than once" in out
        assert "carry MORE THAN ONE surface" in out          # reported, never dropped
        assert len(load_model_path(p).security) == 2


def test_dedup_security_drops_the_duplicate_surface_and_keeps_the_chosen_anchor(capsys):
    m = make_security_map([
        {"surface": "Admin pages", "source": "ui/Sidebar.tsx:97"},
        {"surface": "Admin pages", "source": "api/routes.py:12", "risk": "the real gate"},
        {"surface": "Login", "source": "api/auth.py:5"}])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        assert fix.main(["dedup-security", "--map", str(p),
                         "--keep", "Admin pages::api/routes.py:12"]) == 0
        after = load_model_path(p)
        assert [(s.surface, s.source) for s in after.security] == [
            ("Admin pages", "api/routes.py:12"), ("Login", "api/auth.py:5")]


def test_dedup_security_refuses_an_anchor_that_names_no_row(capsys):
    m = make_security_map([
        {"surface": "Admin pages", "source": "ui/Sidebar.tsx:97"},
        {"surface": "Admin pages", "source": "api/routes.py:12"}])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        assert fix.main(["dedup-security", "--map", str(p),
                         "--keep", "Admin pages::nowhere.py:1"]) == 2
        assert "names no duplicate row" in capsys.readouterr().err
        assert len(load_model_path(p).security) == 2


# --- apply-drift --to-reconcile --------------------------------------------------
# An anchor written into the ASSEMBLED map is discarded by the next assemble. A live build
# corrected 14 anchors, re-assembled to pick up one fragment edit, lost all 14, and re-typed them
# by hand out of the human-readable listing.


def test_apply_drift_to_reconcile_records_instead_of_editing_the_map():
    m = make_map([{"src": "C1", "verb": "reads", "dst": "E1", "why": "w", "where": "a.py:1"}])
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "a.py").write_text("x = 1\n" * 40, encoding="utf-8")
        mp, vp = write(td, m, {"grounding": [make_vote("C1 reads E1", True, "a.py:30")]})
        rec = Path(td) / "reconcile.json"
        assert fix.main(["apply-drift", "--map", mp, "--verdicts", vp,
                         "--to-reconcile", str(rec)]) == 0
        # the MAP is untouched …
        assert load_model_path(Path(mp)).edges[0].where == "a.py:1"
        # … and the decision is durable
        doc = json.loads(rec.read_text(encoding="utf-8"))
        assert doc["set_anchors"] == [{"claim": "C1 reads E1", "corrected": "a.py:30"}]


def test_a_recorded_anchor_is_applied_by_the_reconcile_pass():
    """The round trip: what `--to-reconcile` records, `assemble --reconcile` must apply — through
    the SAME writer, so the durable record and the in-place edit cannot disagree."""
    from coyodex.model import load_model
    from coyodex.reconcile import apply_reconcile, load_reconcile
    m = load_model(json.dumps(make_map(
        [{"src": "C1", "verb": "reads", "dst": "E1", "why": "w", "where": "a.py:1"}])))
    rec = load_reconcile(json.dumps(
        {"set_anchors": [{"claim": "C1 reads E1", "corrected": "a.py:30"}]}), "rec")
    apply_reconcile(m, rec, {})
    assert m.edges[0].where == "a.py:30"


def test_a_recorded_anchor_whose_claim_is_gone_notes_and_never_fails():
    """A reconcile file must not rot when a later fragment edit rewrites the claim it was keyed on —
    the same 0-match rule `drop_edges` and `keep_edges` already follow."""
    from coyodex.model import load_model
    from coyodex.reconcile import apply_reconcile, load_reconcile
    m = load_model(json.dumps(make_map(
        [{"src": "C1", "verb": "reads", "dst": "E1", "why": "w", "where": "a.py:1"}])))
    rec = load_reconcile(json.dumps(
        {"set_anchors": [{"claim": "Auth surface 'gone' is protected by: nothing",
                          "corrected": "b.py:9"}]}), "rec")
    notes = apply_reconcile(m, rec, {})
    assert m.edges[0].where == "a.py:1"
    assert any("matches no edge, security surface, rule site or cadenced entry point" in n
               for n in notes)


def test_dedup_security_resolves_rows_that_share_surface_AND_anchor(capsys):
    """The ORDINARY duplicate: two fragments harvested one auth check, so the rows agree on
    everything. Refusing it made the command unable to resolve the case it exists for — and
    `validate`'s advisory points the operator straight here, with no other answer than the hand
    script this replaces."""
    m = make_security_map([
        {"surface": "Admin pages", "source": "ui/Sidebar.tsx:97", "risk": "hidden only"},
        {"surface": "Admin pages", "source": "ui/Sidebar.tsx:97", "risk": "hidden only"},
        {"surface": "Login", "source": "api/auth.py:5"}])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        assert fix.main(["dedup-security", "--map", str(p), "--accept-suggested"]) == 0
        after = load_model_path(p)
        assert [(s.surface, s.source) for s in after.security] == [
            ("Admin pages", "ui/Sidebar.tsx:97"), ("Login", "api/auth.py:5")]
        assert "identical rows" in capsys.readouterr().out


def test_dedup_security_refuses_same_anchor_rows_that_differ(capsys):
    """Byte-identical rows are not a choice; rows differing in `who`/`risk` still are."""
    m = make_security_map([
        {"surface": "Admin pages", "source": "ui/Sidebar.tsx:97", "risk": "hidden only"},
        {"surface": "Admin pages", "source": "ui/Sidebar.tsx:97", "risk": "the real gate"}])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        assert fix.main(["dedup-security", "--map", str(p), "--accept-suggested"]) == 2
        assert "IS a decision" in capsys.readouterr().err
        assert len(load_model_path(p).security) == 2


def test_a_keep_token_never_drops_a_row_of_another_surface(capsys):
    """`partition("::")` read the token the tool ITSELF printed for surface `A::B` as surface `A`,
    dropped a row under `A`, and reported success — the original wrong-row-deletion bug class,
    reproduced inside its own fix. Tokens are resolved against the real candidates now."""
    m = make_security_map([
        {"surface": "A", "source": "n.ts:1"},
        {"surface": "A", "source": "B::m.ts:2"},
        {"surface": "A::B", "source": "m.ts:2"},
        {"surface": "A::B", "source": "z.ts:3"}])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        assert fix.main(["dedup-security", "--map", str(p), "--keep", "A::B::m.ts:2"]) == 2
        assert "ambiguous" in capsys.readouterr().err
        assert len(load_model_path(p).security) == 4      # nothing dropped


def test_dedup_security_json_with_a_decision_is_refused(capsys):
    m = make_security_map([{"surface": "A", "source": "a.ts:1"},
                           {"surface": "A", "source": "b.ts:2"}])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        assert fix.main(["dedup-security", "--map", str(p), "--json",
                         "--keep", "A::a.ts:1"]) == 2
        assert "Pick one" in capsys.readouterr().err
        assert len(load_model_path(p).security) == 2


def test_apply_drift_to_reconcile_names_the_drifts_it_cannot_write(capsys):
    """The tail said "N drift(s) NOT APPLICABLE … (see above)" with nothing above: the report ran
    only on the in-place path, so the claims needing a hand re-anchor were counted, never named."""
    m = make_map([], entities=[{"id": "E1", "name": "Thing", "states": {
        "source": "a.py:2", "states": ["NEW", "DONE"],
        "transitions": [{"src": "NEW", "dst": "DONE", "on": "finish"}]}}])
    claim = "E1 (Thing) has states [NEW, DONE] with 1 transition(s)"
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "a.py").write_text("x = 1\n" * 40, encoding="utf-8")
        mp, vp = write(td, m, {"grounding": [make_vote(claim, True, "a.py:30")]})
        rec = Path(td) / "reconcile.json"
        assert fix.main(["apply-drift", "--map", mp, "--verdicts", vp,
                         "--to-reconcile", str(rec)]) == 0
        out = capsys.readouterr()
    combined = out.out + out.err
    assert "NOT APPLICABLE" in combined
    assert "[lifecycle]" in combined and "E1 (Thing) has states" in combined


def test_apply_drift_to_reconcile_leaves_the_file_alone_when_there_is_nothing_to_record(capsys):
    m = make_map([{"src": "C1", "verb": "reads", "dst": "E1", "why": "w", "where": "a.py:30"}])
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "a.py").write_text("x = 1\n" * 40, encoding="utf-8")
        mp, vp = write(td, m, {"grounding": [make_vote("C1 reads E1", True, "a.py:30")]})
        rec = Path(td) / "reconcile.json"
        assert fix.main(["apply-drift", "--map", mp, "--verdicts", vp,
                         "--to-reconcile", str(rec)]) == 0
        assert not rec.exists()
        assert "was not touched" in capsys.readouterr().out


def test_security_row_refuses_an_empty_surface(capsys):
    """The surface is the row's identity; an unset shell variable would anonymise it silently."""
    m = make_security_map([{"surface": "/signup", "source": "api/signup.py:1"}])
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        assert fix.main(["security-row", "--map", str(p), "--surface", "/signup",
                         "--set-surface", ""]) == 2
        assert "cannot be empty" in capsys.readouterr().err
        assert load_model_path(p).security[0].surface == "/signup"


def test_two_corrections_landing_on_one_row_are_both_refused():
    """A single-pass writer matched against the model it was mutating, so the outcome depended on
    worklist order: one order applied both corrections, the other skipped the second and left two
    byte-identical security rows behind."""
    from coyodex.audit_model import apply_anchor_corrections, security_claim
    from coyodex.model import load_model
    m = load_model(json.dumps(make_security_map([
        {"surface": "S", "source": "a.py:1"}, {"surface": "S", "source": "b.py:2"}])))
    c0 = (security_claim("S", "a.py:1"), "b.py:2")
    c1 = (security_claim("S", "b.py:2"), "c.py:3")
    counts, notes = apply_anchor_corrections(m, [c0, c1])
    assert counts["security"] == 2
    assert [s.source for s in m.security] == ["b.py:2", "c.py:3"]
    # and the reverse order gives the SAME map
    m2 = load_model(json.dumps(make_security_map([
        {"surface": "S", "source": "a.py:1"}, {"surface": "S", "source": "b.py:2"}])))
    apply_anchor_corrections(m2, [c1, c0])
    assert [s.source for s in m2.security] == ["b.py:2", "c.py:3"]


def test_two_corrections_targeting_the_same_element_are_skipped_not_ordered():
    from coyodex.audit_model import apply_anchor_corrections
    from coyodex.model import load_model
    m = load_model(json.dumps(make_map(
        [{"src": "C1", "verb": "reads", "dst": "E1", "why": "w", "where": "a.py:1"}])))
    counts, notes = apply_anchor_corrections(
        m, [("C1 reads E1", "b.py:2"), ("C1 reads E1", "c.py:3")])
    assert counts["edge"] == 0
    assert m.edges[0].where == "a.py:1"
    assert any("accident of order" in n for n in notes)
