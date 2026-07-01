#!/usr/bin/env python3
"""The judge layer — the SEMANTIC quality signals the deterministic profile can't see.

Two LLM-backed measures, both aggregated here into a `JudgeReport` (the artifact the comparator diffs
alongside the `MapProfile`):

  L2 grounding pass-rate — the audit already emits an L2 worklist of high-risk "actually-does" claims
    (auth surfaces, enforce/encrypt edges). A skeptic that tries to DISPROVE each claim against the
    code yields a pass-rate = fraction that survived. Reuses `audit_analysis.l2_worklist` — no new
    claim extractor.
  Rubric scores — N judges independently score each rubric dimension (faithfulness, completeness,
    drill-accuracy, altitude, golden-path) 0–4 against the code; the median per dimension tames the
    noise.

THIS MODULE IS PURE + STDLIB-ONLY. It never calls a model itself: the actual LLM work is behind the
injectable `Judge` seam (dependency injection — tests pass a deterministic fake; the Phase-4
orchestrator injects a real sub-agent-backed judge). What lives here is the SEAM, the prompt builders,
the aggregation math, and the data model — all deterministic given a `Judge`.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Protocol

from coyodex import audit_analysis, schema_v1

# The rubric dimensions scored 0–4, in report order. Keys match config/rubric.md (external workspace);
# the rubric TEXT is passed in, so the wording can evolve without touching this constant.
DIMENSIONS = ("faithfulness", "completeness", "drill_accuracy", "altitude", "golden_path")


# ── data model ───────────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GroundingVerdict:
    claim: str
    grounded: bool       # True = the skeptic could NOT refute it against the code (the claim holds)
    evidence: str        # a file:line or a short note backing the verdict


@dataclass(frozen=True)
class RubricVerdict:
    dimension: str
    score: int           # one judge's 0–4 for this dimension
    justification: str
    evidence: str        # a file:line the score is grounded in


@dataclass(frozen=True)
class DimensionScore:
    dimension: str
    score: float         # median of the N judges' scores for this dimension
    n_judges: int


@dataclass(frozen=True)
class JudgeReport:
    """The semantic-quality artifact stored beside a MapProfile; the comparator diffs two of these."""
    n_claims: int
    n_grounded: int
    grounding_passrate: float | None      # n_grounded / n_claims, or None when there are no claims
    dimensions: list[DimensionScore]
    overall: float | None                 # mean of the dimension medians, or None when no dimensions

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "JudgeReport":
        d = json.loads(s)
        known = {f.name for f in fields(cls)}
        kw = {k: v for k, v in d.items() if k in known}
        kw["dimensions"] = [DimensionScore(**ds) for ds in kw.get("dimensions", [])]
        return cls(**kw)


# ── the injectable seam ──────────────────────────────────────────────────────────────────────────────

class Judge(Protocol):
    """The DI boundary to the model. A real implementation runs a fresh-context sub-agent with read
    access to `repo_root`; the aggregation below is agnostic to which. Kept deliberately tiny so a
    test fake is trivial to write."""

    def ground_claim(self, claim: str, anchor: str | None, repo_root: Path) -> GroundingVerdict:
        """Try to DISPROVE `claim` against the code under `repo_root` (start at `anchor` if given).
        `grounded=False` means the skeptic refuted it — default to refuted when genuinely unsure."""
        ...

    def score_dimension(self, dimension: str, rubric: str, map_text: str,
                        repo_root: Path) -> RubricVerdict:
        """Score one rubric `dimension` 0–4 for `map_text` against the code, grounded in a file:line."""
        ...


# ── prompt builders (what a REAL Judge sends; kept here so the text is reusable + testable) ────────────

def build_grounding_prompt(claim: str, anchor: str | None) -> str:
    start = f"\nStart from: {anchor}" if anchor else ""
    return (
        "You are a skeptic. Your job is to DISPROVE the claim below by reading the actual code — not to "
        "confirm it. If the code does not clearly and fully support the claim, it is REFUTED. Default to "
        f"refuted when genuinely unsure.\n\nCLAIM: {claim}{start}\n\n"
        "Return: grounded (true only if the code clearly supports the claim), and one file:line as "
        "evidence for your verdict."
    )


def build_rubric_prompt(dimension: str, rubric: str, map_text: str) -> str:
    return (
        f"Score the coyodex map below on ONE dimension: '{dimension}'. Use the rubric. Read the code to "
        "check — a score you cannot back with a file:line must be scored DOWN, not guessed.\n\n"
        f"=== RUBRIC ===\n{rubric}\n\n=== MAP ===\n{map_text}\n\n"
        f"Return: score (0–4 for '{dimension}'), a one-line justification, and a file:line as evidence."
    )


# ── aggregation (deterministic given a Judge) ──────────────────────────────────────────────────────────

def run_grounding(worklist: list[audit_analysis.WorkItem], judge: Judge,
                  repo_root: Path) -> list[GroundingVerdict]:
    """Ground every L2 claim through the judge, in worklist order."""
    return [judge.ground_claim(w.claim, w.anchor, repo_root) for w in worklist]


def run_dimension(dimension: str, rubric: str, map_text: str, repo_root: Path, judge: Judge,
                  n_judges: int) -> DimensionScore:
    """Score one dimension with N independent judges and take the MEDIAN (noise control)."""
    scores = [judge.score_dimension(dimension, rubric, map_text, repo_root).score
              for _ in range(max(1, n_judges))]
    return DimensionScore(dimension, float(statistics.median(scores)), len(scores))


def build_judge_report(map_text: str, repo_root: Path, rubric: str, judge: Judge,
                       n_judges: int = 3, dimensions: tuple[str, ...] = DIMENSIONS) -> JudgeReport:
    """Produce the full JudgeReport: ground the audit's L2 worklist, then score every rubric dimension
    with N judges. Deterministic given `judge`; the model-facing work is entirely inside `judge`."""
    text = schema_v1.strip_fences(map_text)
    worklist = audit_analysis.l2_worklist(text)
    verdicts = run_grounding(worklist, judge, repo_root)
    n_claims = len(verdicts)
    n_grounded = sum(1 for v in verdicts if v.grounded)
    passrate = (n_grounded / n_claims) if n_claims else None
    dims = [run_dimension(d, rubric, map_text, repo_root, judge, n_judges) for d in dimensions]
    overall = float(statistics.mean(d.score for d in dims)) if dims else None
    return JudgeReport(n_claims=n_claims, n_grounded=n_grounded, grounding_passrate=passrate,
                       dimensions=dims, overall=overall)
