"""`coyodex grounding write` — the record `validate` blocks on, derived instead of hand-tallied."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from coyodex import grounding as G  # noqa: E402
from coyodex.grounding import build_record, main  # noqa: E402


def make_worklist(*claims: str) -> list[str]:
    return list(claims)


def make_votes(*rows: tuple[str, object]) -> list[dict]:
    return [{"claim": c, "grounded": g, "evidence": "a/b.py:1"} for c, g in rows]


def test_the_four_counts_add_up_to_challenged():
    """The arithmetic `validate` BLOCKS on. Derived, so it cannot drift from the verdicts."""
    rec, errs = build_record(make_worklist("A", "B", "C"),
                             make_votes(("A", True), ("B", False), ("C", "unverifiable")))
    assert not errs
    assert rec["claims_confirmed"] + rec["claims_refuted"] + rec["claims_unverifiable"] \
        == rec["claims_challenged"] == 3
    assert (rec["claims_confirmed"], rec["claims_refuted"], rec["claims_unverifiable"]) == (1, 1, 1)


def test_a_tie_is_unverifiable_not_a_silent_win():
    """1-1 is not settled by the code. Crediting either side is the failure the record exists to
    prevent, so an unsettled claim lands in the honest third bucket."""
    rec, errs = build_record(make_worklist("A"), make_votes(("A", True), ("A", False)))
    assert not errs
    assert rec["claims_unverifiable"] == 1 and rec["claims_confirmed"] == 0


def test_it_refuses_a_worklist_snapshot_the_verdicts_do_not_match():
    """The snapshot problem, reproduced from a live build: re-deriving the worklist AFTER the
    refutations are applied leaves verdicts referring to claims the map no longer holds, and the
    resulting record makes `claims_challenged` exceed `claims_total` — which `validate` blocks on."""
    _rec, errs = build_record(make_worklist("A"), make_votes(("A", True), ("GONE", False)))
    assert any("not in the pinned worklist" in e for e in errs)


def test_it_refuses_when_a_claim_has_no_verdict():
    """"The gate did not run" must never read as "the gate passed" — an unchallenged claim would
    otherwise be silently excluded and `claims_challenged` would overstate the pass."""
    _rec, errs = build_record(make_worklist("A", "B"), make_votes(("A", True)))
    assert any("have NO verdict" in e for e in errs)


def test_cli_writes_a_fragment_that_is_a_grounding_block():
    with tempfile.TemporaryDirectory() as td:
        _cli_writes_a_fragment(Path(td))


def _cli_writes_a_fragment(tmp_path: Path) -> None:
    wl = tmp_path / "audit.json"
    wl.write_text(json.dumps({"worklist": [{"claim": "A"}, {"claim": "B"}]}), encoding="utf-8")
    vd = tmp_path / "v.json"
    vd.write_text(json.dumps({"grounding": [
        {"claim": "A", "grounded": True, "evidence": "a.py:1"},
        {"claim": "B", "grounded": False}]}), encoding="utf-8")
    out = tmp_path / "grounding.json"
    assert main(["write", "--worklist", str(wl), "--verdicts", str(vd), "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert set(payload) == {"grounding"}
    assert payload["grounding"]["claims_total"] == 2
    assert payload["grounding"]["claims_refuted"] == 1


def test_cli_exits_nonzero_when_it_refuses():
    """A refusal that exits 0 is the "printed an error and claimed success" failure."""
    with tempfile.TemporaryDirectory() as td:
        _cli_exits_nonzero(Path(td))


def _cli_exits_nonzero(tmp_path: Path) -> None:
    wl = tmp_path / "audit.json"
    wl.write_text(json.dumps({"worklist": [{"claim": "A"}, {"claim": "B"}]}), encoding="utf-8")
    vd = tmp_path / "v.json"
    vd.write_text(json.dumps({"grounding": [{"claim": "A", "grounded": True}]}), encoding="utf-8")
    assert main(["write", "--worklist", str(wl), "--verdicts", str(vd)]) == 1


# --- grounding report, skeptic ids, and the stale pin ------------------------------------------


def test_report_lists_which_claims_were_refuted_not_only_how_many():
    """`write` resolves every claim and emits four counts, so a build that must reconcile each
    refutation had nothing to read — one hand-wrote a 12-line vote aggregator one turn later."""
    claims = ["C1 calls C2", "C3 reads E1", "C4 persists E2"]
    rows = [{"claim": "C1 calls C2", "grounded": True, "evidence": "a.py:1"},
            {"claim": "C3 reads E1", "grounded": False, "evidence": "b.py:2",
             "note": "b.py:2 writes, it never reads"},
            {"claim": "C4 persists E2", "grounded": "unverifiable", "evidence": ""}]
    out = G.format_report(claims, rows)
    assert "REFUTED" in out and "C3 reads E1" in out
    assert "UNVERIFIABLE" in out and "C4 persists E2" in out
    assert "C1 calls C2" not in out.split("confirmed:")[0], "a confirmed claim is not a worklist item"
    assert "confirmed: 1 of 3" in out


def test_report_separates_a_tie_from_a_stated_unverifiable():
    """`_verdict_bucket` files both under `unverifiable` — right for the count, wrong for the
    reader. A live build's grounding note described four unverifiables as one kind when two were
    the other."""
    claims = ["C1 calls C2"]
    rows = [{"claim": "C1 calls C2", "grounded": True, "evidence": "a.py:1", "skeptic": "sec-a"},
            {"claim": "C1 calls C2", "grounded": False, "evidence": "a.py:9", "skeptic": "sec-b"}]
    out = G.format_report(claims, rows)
    assert "TIED" in out
    assert "1 for / 1 against" in out
    assert "sec-a" in out and "sec-b" in out


def test_report_names_the_claims_that_were_never_challenged():
    out = G.format_report(["C1 calls C2", "C3 reads E1"],
                          [{"claim": "C1 calls C2", "grounded": True, "evidence": "a.py:1"}])
    assert "NO VERDICT" in out and "C3 reads E1" in out


def test_two_skeptics_agreeing_are_not_reported_as_a_duplicate_row():
    """The method PRESCRIBES a double read of the security claims, and the note used to tell the
    build to "drop one" for doing exactly what it was asked to do."""
    from coyodex.anchor_drift import load_verdicts
    with tempfile.TemporaryDirectory() as tmp:
        rows = [{"claim": "C1 calls C2", "grounded": True, "evidence": "a.py:1"}]
        a, b = Path(tmp) / "v-a.json", Path(tmp) / "v-b.json"
        a.write_text(json.dumps({"grounding": [{**rows[0], "skeptic": "sec-a"}]}), encoding="utf-8")
        b.write_text(json.dumps({"grounding": [{**rows[0], "skeptic": "sec-b"}]}), encoding="utf-8")
        _loaded, notes = load_verdicts([str(a), str(b)])
        assert notes == [], notes


def test_the_same_skeptic_id_in_two_files_is_still_reported():
    from coyodex.anchor_drift import load_verdicts
    with tempfile.TemporaryDirectory() as tmp:
        row = {"claim": "C1 calls C2", "grounded": True, "evidence": "a.py:1", "skeptic": "sec-a"}
        a, b = Path(tmp) / "v-a.json", Path(tmp) / "agg.json"
        a.write_text(json.dumps({"grounding": [row]}), encoding="utf-8")
        b.write_text(json.dumps({"grounding": [row]}), encoding="utf-8")
        _loaded, notes = load_verdicts([str(a), str(b)])
        assert len(notes) == 1 and "SAME `skeptic` id" in notes[0]


def test_the_record_states_the_delta_when_given_the_live_map():
    """Without `--map` the record cannot say how the shipped map differs from the pinned worklist,
    and a build had no legal answer to the staleness advisory."""
    from coyodex.grounding import build_record, live_claims_digest
    pinned = ["a", "b", "c"]
    rows = [{"claim": c, "grounded": True, "evidence": "f.py:1"} for c in pinned]
    live = ["a", "b", "d"]                       # c was reconciled away; d was authored since
    rec, errors = build_record(pinned, rows, live_claims=live)
    assert not errors
    assert rec["claims_total"] == 3 and rec["claims_challenged"] == 3
    assert rec["claims_superseded"] == 1 and rec["claims_added_since"] == 1
    assert rec["live_claims_digest"] == live_claims_digest(live)


def test_without_the_live_map_the_record_is_exactly_as_before():
    """`--map` is optional: a build that never reconciles a count-changing refutation needs none of
    this, and its record must not grow fields it cannot fill honestly."""
    from coyodex.grounding import build_record
    pinned = ["a", "b"]
    rows = [{"claim": c, "grounded": True, "evidence": "f.py:1"} for c in pinned]
    rec, errors = build_record(pinned, rows)
    assert not errors
    for field in ("claims_superseded", "claims_added_since", "live_claims_digest"):
        assert field not in rec, field


def test_the_digest_ignores_order_and_duplication():
    """Both sides are counted over the de-duplicated claim SET — two sides counted by different
    rules measure the rule instead of the map."""
    from coyodex.grounding import live_claims_digest
    assert live_claims_digest(["b", "a"]) == live_claims_digest(["a", "b"])
    assert live_claims_digest(["a", "a", "b"]) == live_claims_digest(["a", "b"])
    assert live_claims_digest(["a", "b"]) != live_claims_digest(["a", "c"])


def test_the_pinned_split_is_never_recomputed_against_the_live_map():
    """The `refuted 0` trap, pinned as a test. The claims a reconcile deletes are exactly the
    REFUTED ones, so a split measured against the live worklist reports that nothing was ever found
    wrong. The split must stay pinned no matter what `--map` says."""
    from coyodex.grounding import build_record
    pinned = ["kept", "refuted-and-rewritten"]
    rows = [{"claim": "kept", "grounded": True, "evidence": "f.py:1"},
            {"claim": "refuted-and-rewritten", "grounded": False, "note": "wrong"}]
    rec, _ = build_record(pinned, rows, live_claims=["kept", "the rewritten form"])
    assert rec["claims_refuted"] == 1, "the refutation must survive the live comparison"
    assert rec["claims_superseded"] == 1


def test_the_digest_is_not_ambiguous_about_where_a_claim_ends():
    """A separator that can appear inside a claim makes the digest ambiguous: newline-joined,
    `["a\\nb"]` hashed identically to `["a", "b"]`. No claim carries a newline today, which is why
    it was worth removing before one does."""
    from coyodex.grounding import live_claims_digest
    assert live_claims_digest(["a\nb"]) != live_claims_digest(["a", "b"])
