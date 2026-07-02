#!/usr/bin/env python3
"""The judge layer — the SEMANTIC quality signals the deterministic profile can't see.

Two LLM-backed measures, both aggregated here into a `JudgeReport` (the artifact the comparator diffs
alongside the `MapProfile`):

  L2 grounding pass-rate — the audit already emits an L2 worklist of high-risk "actually-does" claims
    (auth surfaces, enforce/encrypt edges). N skeptics per claim each try to DISPROVE it against the
    code; the claim's verdict is the MAJORITY of the usable votes, and the pass-rate is the fraction of
    claims that survived. Only the top-K risk-ranked claims are grounded (the worklist is already
    ranked, most-dangerous first); a skeptic that returns no verdict is a FAILURE, excluded from the
    denominator — never scored as refuted. Reuses `audit_analysis.l2_worklist` — no new claim extractor.
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

# Grounding defaults — mirrored by eval/method.md Step 4 (change them together).
DEFAULT_N_SKEPTICS = 3     # majority-of-N vote per claim: one dissenting skeptic can't flip a verdict
DEFAULT_GROUNDING_CAP = 40  # K: ground only the top-K risk-ranked claims (the worklist is ranked)


# ── data model ───────────────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GroundingVerdict:
    claim: str
    grounded: bool | None  # True = held · False = refuted · None = NO verdict (a judge failure — the
                           # skeptic produced no usable output; never counted as refuted)
    evidence: str          # a file:line or a short note backing the verdict


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
    n_claims: int                         # claims actually sent to grounding (the top-K sample)
    n_grounded: int
    grounding_passrate: float | None      # n_grounded / (n_claims - n_failures); None when no denominator
    dimensions: list[DimensionScore]
    overall: float | None                 # mean of the dimension medians, or None when no dimensions
    n_worklist: int = 0                   # full worklist size the top-K sample was drawn from
    n_failures: int = 0                   # sampled claims with NO usable verdict — excluded from the
                                          # pass-rate denominator, surfaced separately (never "refuted")

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "JudgeReport":
        d = json.loads(s)
        known = {f.name for f in fields(cls)}
        kw = {k: v for k, v in d.items() if k in known}
        kw["dimensions"] = [DimensionScore(**ds) for ds in kw.get("dimensions", [])]
        # A report written before the sampling cap existed grounded the whole worklist.
        kw.setdefault("n_worklist", kw.get("n_claims", 0))
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

def build_grounding_prompt(claim: str, anchor: str | None, detail: str | None = None) -> str:
    start = f"\nStart from: {anchor}" if anchor else ""
    about = f"\nClaim context (names + files, from the claim itself): {detail}" if detail else ""
    return (
        "You are a skeptic. Your job is to DISPROVE the claim below by reading the actual code — not to "
        "confirm it. If the code does not clearly and fully support the claim, it is REFUTED. Default to "
        "refuted when genuinely unsure.\n\n"
        "Judge ONLY whether the RELATIONSHIP the claim states is true in the code. An imprecise or "
        "drifted anchor (a file:line some lines off) does NOT refute a claim whose relationship is "
        "true — anchor exactness is scored separately, by the drill_accuracy rubric dimension.\n"
        "Resolve names and ids ONLY from the claim text and the code; do NOT read any project-map "
        f"file.\n\nCLAIM: {claim}{about}{start}\n\n"
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

def run_grounding(worklist: list[audit_analysis.WorkItem], judge: Judge, repo_root: Path,
                  n_skeptics: int = DEFAULT_N_SKEPTICS) -> list[list[GroundingVerdict]]:
    """Ground every claim through N independent skeptics, in worklist order — one vote list per claim."""
    return [[judge.ground_claim(w.claim, w.anchor, repo_root) for _ in range(max(1, n_skeptics))]
            for w in worklist]


def majority_verdict(votes: list[GroundingVerdict]) -> bool | None:
    """Majority over the USABLE votes (grounded is not None): a single dissenter can't flip a claim; a
    tie is refuted (the skeptic's default when unsure). No usable vote at all → None (a failure — the
    claim is excluded from the pass-rate denominator, never scored refuted)."""
    usable = [v.grounded for v in votes if v.grounded is not None]
    if not usable:
        return None
    return sum(usable) > len(usable) / 2


def run_dimension(dimension: str, rubric: str, map_text: str, repo_root: Path, judge: Judge,
                  n_judges: int) -> DimensionScore:
    """Score one dimension with N independent judges and take the MEDIAN (noise control)."""
    scores = [judge.score_dimension(dimension, rubric, map_text, repo_root).score
              for _ in range(max(1, n_judges))]
    return DimensionScore(dimension, float(statistics.median(scores)), len(scores))


def build_judge_report(map_text: str, repo_root: Path, rubric: str, judge: Judge,
                       n_judges: int = 3, dimensions: tuple[str, ...] = DIMENSIONS,
                       n_skeptics: int = DEFAULT_N_SKEPTICS,
                       grounding_cap: int = DEFAULT_GROUNDING_CAP) -> JudgeReport:
    """Produce the full JudgeReport: ground the top-K of the audit's risk-ranked L2 worklist by
    majority-of-N skeptics, then score every rubric dimension with N judges. Deterministic given
    `judge`; the model-facing work is entirely inside `judge`."""
    text = schema_v1.strip_fences(map_text)
    worklist = audit_analysis.l2_worklist(text)
    sample = worklist[:grounding_cap] if grounding_cap > 0 else worklist
    outcomes = [majority_verdict(votes) for votes in run_grounding(sample, judge, repo_root, n_skeptics)]
    n_claims = len(outcomes)
    n_failures = sum(1 for o in outcomes if o is None)
    n_grounded = sum(1 for o in outcomes if o is True)
    denom = n_claims - n_failures
    passrate = (n_grounded / denom) if denom else None
    dims = [run_dimension(d, rubric, map_text, repo_root, judge, n_judges) for d in dimensions]
    overall = float(statistics.mean(d.score for d in dims)) if dims else None
    return JudgeReport(n_claims=n_claims, n_grounded=n_grounded, grounding_passrate=passrate,
                       dimensions=dims, overall=overall,
                       n_worklist=len(worklist), n_failures=n_failures)


# ── replaying externally-produced verdicts ────────────────────────────────────────────────────────────

class PrecomputedJudge:
    """A `Judge` that REPLAYS verdicts produced OUTSIDE the tool — by the orchestration layer (a
    workflow, or fresh-context sub-agents) that did the real, model-backed judging — so they aggregate
    through the SAME tested `build_judge_report` path a live judge would use. The tool never calls a
    model; this adapter just hands the orchestrator's results to the pure aggregation.

    `grounding` is one row per SKEPTIC VOTE — the same claim may appear N times (majority vote):
    {"claim": str, "grounded": bool, "evidence"?: str}. A row whose `grounded` is missing or not a
    bool is a FAILED vote (the skeptic produced no usable output) — replayed as `grounded=None`, so
    the aggregation excludes it instead of scoring it refuted. `ground_claim` returns a claim's k-th
    recorded vote on its k-th call; calls beyond the recorded votes are failures. `judges` is one dict
    per judge mapping each dimension name to its 0–4 score; `score_dimension` returns the k-th judge's
    score on the k-th call for a dimension, so `run_dimension`'s N calls see all N judges."""

    def __init__(self, grounding: list[dict[str, object]], judges: list[dict[str, int]]) -> None:
        self._votes: dict[str, list[dict[str, object]]] = {}
        for g in grounding:
            if "claim" in g:
                self._votes.setdefault(str(g["claim"]), []).append(g)
        self._judges = judges
        self._served: dict[str, int] = {}
        self._asked: dict[str, int] = {}

    def max_votes_per_claim(self) -> int:
        """The N the orchestrator actually ran (how many skeptic rows its busiest claim has)."""
        return max((len(v) for v in self._votes.values()), default=1)

    def ground_claim(self, claim: str, anchor: str | None, repo_root: Path) -> GroundingVerdict:
        k = self._served.get(claim, 0)
        self._served[claim] = k + 1
        rows = self._votes.get(claim, [])
        if k >= len(rows):
            return GroundingVerdict(claim, None, "no verdict from the orchestrator")
        g = rows[k]
        verdict = g.get("grounded")
        if not isinstance(verdict, bool):
            return GroundingVerdict(claim, None, "no usable verdict (missing/malformed `grounded`)")
        return GroundingVerdict(claim, verdict, str(g.get("evidence", "")))

    def score_dimension(self, dimension: str, rubric: str, map_text: str,
                        repo_root: Path) -> RubricVerdict:
        k = self._asked.get(dimension, 0)
        self._asked[dimension] = k + 1
        judge = self._judges[k % len(self._judges)] if self._judges else {}
        return RubricVerdict(dimension, int(judge.get(dimension, 0)), "", "")


def report_from_verdicts(map_text: str, repo_root: Path, rubric: str,
                         grounding: list[dict[str, object]], judges: list[dict[str, int]],
                         dimensions: tuple[str, ...] = DIMENSIONS,
                         grounding_cap: int = DEFAULT_GROUNDING_CAP) -> JudgeReport:
    """Aggregate externally-produced verdicts into a JudgeReport via the same path a live judge uses —
    the bridge from an orchestrated judge run (raw verdicts) to the tested majority-vote + median math.
    The skeptic count is inferred from the raw rows (max votes any claim received), so a single-vote
    run and a majority-of-3 run both replay faithfully. NO rubric verdicts at all → NO dimension
    scores (overall None): a crashed rubric stage must read as "not judged", never as all-zeros —
    zeros look like a catastrophically bad map and, blessed as a baseline, would disarm the drop-only
    judge bands forever."""
    pre = PrecomputedJudge(grounding, judges)
    return build_judge_report(map_text, repo_root, rubric, pre,
                              n_judges=len(judges) or 1,
                              dimensions=dimensions if judges else (),
                              n_skeptics=pre.max_votes_per_claim(), grounding_cap=grounding_cap)
