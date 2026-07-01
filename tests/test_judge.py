#!/usr/bin/env python3
"""Tests for the judge layer — grounding pass-rate + N-judge median rubric scoring.

No live LLM: a deterministic `ScriptedJudge` is injected through the `Judge` seam (DI). Stdlib-only.
    python3 tests/test_judge.py        # built-in runner
    pytest tests/test_judge.py         # if pytest is installed
"""
from __future__ import annotations

from pathlib import Path

from coyodex.eval.judge import (DIMENSIONS, GroundingVerdict, JudgeReport, RubricVerdict,
                                build_grounding_prompt, build_judge_report, build_rubric_prompt,
                                report_from_verdicts, run_dimension)

HERE = Path(".")


# --- the injected fake (DI double — not a test class) ----------------------------
class ScriptedJudge:
    """Deterministic Judge double: grounds a claim unless it contains `refute_marker`; returns each
    dimension's score from `score_lists` (cycled) else `default_score`."""

    def __init__(self, refute_marker: str = "REFUTE", score_lists: dict[str, list[int]] | None = None,
                 default_score: int = 3) -> None:
        self.refute_marker = refute_marker
        self.score_lists = score_lists or {}
        self.default_score = default_score
        self._idx: dict[str, int] = {}

    def ground_claim(self, claim: str, anchor: str | None, repo_root: Path) -> GroundingVerdict:
        return GroundingVerdict(claim, self.refute_marker not in claim, anchor or "n/a")

    def score_dimension(self, dimension: str, rubric: str, map_text: str,
                        repo_root: Path) -> RubricVerdict:
        lst = self.score_lists.get(dimension)
        if lst:
            i = self._idx.get(dimension, 0)
            self._idx[dimension] = i + 1
            return RubricVerdict(dimension, lst[i % len(lst)], "j", "f.py:1")
        return RubricVerdict(dimension, self.default_score, "j", "f.py:1")


# --- builders -------------------------------------------------------------------
def make_l2_map(refute_surface: bool = False) -> str:
    """A map with the two L2-worklist sources: a Security & auth row and an `enforces` edge → 2 claims.
    `refute_surface` puts the marker in the surface name so the ScriptedJudge refutes that one claim."""
    surface = "REFUTE /admin" if refute_surface else "/admin"
    return (
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | Gate | x | f | C2 |\n| **C2** | Policy | x | f |  |\n\n"
        "### Security & auth\n"
        "| Surface | Who can reach | Auth check | Risk note |\n|---|---|---|---|\n"
        f"| {surface} | admins | [require_admin](auth.py#L10) | escalation |\n\n"
        "### edges\n| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | enforces | C2 | policy | gate.py#L5 |\n"
    )


def make_no_claims_map() -> str:
    return ("## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
            "| **C1** | X | x | f |  |\n")


# --- grounding pass-rate --------------------------------------------------------
def test_grounding_passrate_counts_refuted_claims() -> None:
    rep = build_judge_report(make_l2_map(refute_surface=True), HERE, "RUBRIC", ScriptedJudge(), n_judges=1)
    assert rep.n_claims == 2, rep
    assert rep.n_grounded == 1, rep          # the enforces edge survives; the surface is refuted
    assert rep.grounding_passrate == 0.5, rep


def test_no_claims_gives_none_passrate() -> None:
    rep = build_judge_report(make_no_claims_map(), HERE, "R", ScriptedJudge(), n_judges=1)
    assert rep.n_claims == 0 and rep.grounding_passrate is None, rep


# --- rubric median --------------------------------------------------------------
def test_dimension_score_is_the_median_of_the_judges() -> None:
    j = ScriptedJudge(score_lists={"faithfulness": [2, 4, 3]})
    dim = run_dimension("faithfulness", "R", "MAP", HERE, j, n_judges=3)
    assert dim.score == 3.0 and dim.n_judges == 3, dim


def test_overall_is_mean_of_dimension_medians_and_covers_all_dimensions() -> None:
    rep = build_judge_report(make_l2_map(), HERE, "R", ScriptedJudge(default_score=3), n_judges=1)
    assert rep.overall == 3.0, rep
    assert tuple(d.dimension for d in rep.dimensions) == DIMENSIONS, rep


# --- prompts --------------------------------------------------------------------
def test_grounding_prompt_carries_claim_and_anchor_and_is_adversarial() -> None:
    p = build_grounding_prompt("C1 enforces C2", "gate.py#L5")
    assert "C1 enforces C2" in p and "gate.py#L5" in p and "DISPROVE" in p, p


def test_rubric_prompt_carries_dimension_rubric_and_map() -> None:
    p = build_rubric_prompt("faithfulness", "MY RUBRIC", "MAP TEXT")
    assert "faithfulness" in p and "MY RUBRIC" in p and "MAP TEXT" in p, p


# --- replaying externally-produced verdicts (PrecomputedJudge) ------------------
def test_precomputed_judge_replays_grounding_and_median_scores() -> None:
    """report_from_verdicts feeds orchestrator verdicts through the SAME aggregation a live judge uses:
    grounding matched per claim, each dimension the median of the N judges."""
    grounding = [
        {"claim": "Auth surface '/admin' is protected by: require_admin", "grounded": True, "evidence": "auth.py:10"},
        {"claim": "C1 enforces C2", "grounded": False, "evidence": "gate.py:5"},
    ]
    judges = [
        {"faithfulness": 2, "completeness": 3, "drill_accuracy": 3, "altitude": 3, "golden_path": 3},
        {"faithfulness": 4, "completeness": 3, "drill_accuracy": 3, "altitude": 3, "golden_path": 3},
        {"faithfulness": 4, "completeness": 3, "drill_accuracy": 3, "altitude": 3, "golden_path": 3},
    ]
    rep = report_from_verdicts(make_l2_map(), HERE, "R", grounding, judges)
    assert (rep.n_claims, rep.n_grounded, rep.grounding_passrate) == (2, 1, 0.5), rep
    faith = next(d for d in rep.dimensions if d.dimension == "faithfulness")
    assert faith.score == 4.0 and faith.n_judges == 3, faith   # median([2, 4, 4]) == 4


# --- serialization --------------------------------------------------------------
def test_judge_report_round_trips_including_nested_dimensions() -> None:
    rep = build_judge_report(make_l2_map(), HERE, "R", ScriptedJudge(), n_judges=1)
    assert JudgeReport.from_json(rep.to_json()) == rep


# --- built-in runner ------------------------------------------------------------
def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
