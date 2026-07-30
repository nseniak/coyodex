"""`coyodex grounding write` — the record `validate` blocks on, derived instead of hand-tallied."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

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
