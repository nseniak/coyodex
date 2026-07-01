#!/usr/bin/env python3
"""`coyodex eval compare` — score one map PROFILE against a baseline and apply the regression gates.

A map is LLM-authored, so the comparison is RELATIVE to a blessed baseline, never absolute: a real
baseline map carries some validate problems, so the gate is "no NEW problems", not "must pass". Two
kinds of check:

  HARD GATES  → a trip means REGRESSED (block). All relative to baseline:
                validate problems must not increase · contradictions must not increase · coverage
                flags must not increase past an allowance · the number of auth surfaces must not drop.
  BANDS       → a metric that drifts past ±allowance vs baseline is a softer DRIFT (a human look, not
                a block) — counts legitimately wander run-to-run, so this only flags the big moves.

Verdict precedence: REGRESSED (any hard gate) > DRIFT (any band breach) > PASS. Exit codes mirror it
(REGRESSED=1, DRIFT=2, PASS=0) so an unattended run can gate on it.

Deterministic and stdlib-only. Semantic checks (did an auth surface disappear even though the COUNT
held, are the claims still faithful) belong to the Phase-3 judge layer — auth-surface NAMES drift with
LLM wording, so name-level matching here is informational, never a gate.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from coyodex.eval.profile import MapProfile

PASS = "PASS"
DRIFT = "DRIFT"
REGRESSED = "REGRESSED"
_EXIT = {PASS: 0, REGRESSED: 1, DRIFT: 2}

# The structural bands applied by default when no thresholds file is given. Keys end in `_pct` and name
# a numeric MapProfile field; the value is the allowed symmetric fractional drift vs baseline.
DEFAULT_BANDS: dict[str, float] = {
    "use_cases_pct": 0.20,
    "subsystems_pct": 0.25,
    "subdomains_pct": 0.25,
    "components_pct": 0.20,
    "deps_pct": 0.25,
    "entities_pct": 0.20,
    "edges_pct": 0.25,
    "gp_steps_pct": 0.20,
    "flows_pct": 0.20,
    "l2_claims_pct": 0.25,
}


@dataclass(frozen=True)
class Thresholds:
    validate_must_not_regress: bool = True
    no_new_contradictions: bool = True
    coverage_flags_may_increase_by: int = 0
    auth_surfaces_must_not_drop: bool = True
    bands: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_BANDS))

    @classmethod
    def from_config(cls, cfg: dict, project: str | None = None) -> "Thresholds":
        """Build from a parsed thresholds.json: `global` merged with `per_project[project]` overrides."""
        g = cfg.get("global", cfg)
        hard = dict(g.get("hard_gates", {}))
        # Bands MERGE onto the defaults (like hard_gates merge key-by-key). A partial `bands` override
        # tightening one metric must NOT silently drop the others — that would turn off drift detection
        # on the rest and let a real regression PASS (review Finding 2).
        bands = dict(DEFAULT_BANDS)
        bands.update(g.get("bands", {}))
        if project:
            pp = cfg.get("per_project", {}).get(project, {})
            hard.update(pp.get("hard_gates", {}))
            bands.update(pp.get("bands", {}))
        return cls(
            validate_must_not_regress=hard.get("validate_must_not_regress", True),
            no_new_contradictions=hard.get("no_new_contradictions", True),
            coverage_flags_may_increase_by=hard.get("coverage_flags_may_increase_by", 0),
            auth_surfaces_must_not_drop=hard.get("auth_surfaces_must_not_drop", True),
            bands=bands,
        )


@dataclass(frozen=True)
class GateResult:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class BandResult:
    metric: str
    baseline: float
    candidate: float
    delta_pct: float     # signed fractional change vs baseline
    allowed_pct: float
    within: bool


@dataclass(frozen=True)
class DeltaReport:
    verdict: str                  # PASS | DRIFT | REGRESSED
    gates: list[GateResult]
    bands: list[BandResult]
    notes: list[str]              # informational (skipped gates, drifted names) — never gating

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def _band(metric: str, b_val: float, c_val: float, allowed: float) -> BandResult:
    denom = max(abs(b_val), 1.0)
    delta = (c_val - b_val) / denom
    return BandResult(metric, b_val, c_val, delta, allowed, abs(delta) <= allowed + 1e-9)


def compare(baseline: MapProfile, candidate: MapProfile, thresholds: Thresholds | None = None) -> DeltaReport:
    """Apply the relative hard gates + bands, returning a ranked DeltaReport with a PASS/DRIFT/REGRESSED
    verdict. `thresholds` defaults to the built-in defaults (all hard gates on, DEFAULT_BANDS)."""
    t = thresholds or Thresholds()
    gates: list[GateResult] = []
    notes: list[str] = []

    if t.validate_must_not_regress:
        ok = candidate.validate_problems <= baseline.validate_problems
        gates.append(GateResult("validate-no-regress", ok,
            f"validate problems {baseline.validate_problems} -> {candidate.validate_problems}"))
    if t.no_new_contradictions:
        ok = candidate.contradictions <= baseline.contradictions
        gates.append(GateResult("no-new-contradictions", ok,
            f"contradictions {baseline.contradictions} -> {candidate.contradictions}"))
    # Coverage — comparable only when BOTH sides were scored with --repo.
    if baseline.coverage_flags is None or candidate.coverage_flags is None:
        notes.append("coverage gate skipped — a profile was scored without --repo (coverage_flags is null)")
    else:
        delta = candidate.coverage_flags - baseline.coverage_flags
        ok = delta <= t.coverage_flags_may_increase_by
        gates.append(GateResult("coverage-no-regress", ok,
            f"coverage flags {baseline.coverage_flags} -> {candidate.coverage_flags} "
            f"(allowed +{t.coverage_flags_may_increase_by})"))
    if t.auth_surfaces_must_not_drop:
        ok = candidate.security_surfaces >= baseline.security_surfaces
        gates.append(GateResult("auth-surfaces-no-drop", ok,
            f"auth surfaces {baseline.security_surfaces} -> {candidate.security_surfaces}"))
        dropped = [s for s in baseline.auth_surfaces if s not in set(candidate.auth_surfaces)]
        if dropped:
            notes.append("auth surfaces in baseline but not (by name) in candidate — names drift with "
                         f"LLM wording, so verify rather than trust: {', '.join(dropped)}")

    bands: list[BandResult] = []
    for key in sorted(t.bands):
        metric = key[:-4] if key.endswith("_pct") else key
        b_val, c_val = getattr(baseline, metric, None), getattr(candidate, metric, None)
        if not isinstance(b_val, (int, float)) or isinstance(b_val, bool) or \
           not isinstance(c_val, (int, float)) or isinstance(c_val, bool):
            notes.append(f"band '{key}' skipped — '{metric}' is not a numeric profile metric")
            continue
        bands.append(_band(metric, float(b_val), float(c_val), t.bands[key]))

    if any(not g.passed for g in gates):
        verdict = REGRESSED
    elif any(not b.within for b in bands):
        verdict = DRIFT
    else:
        verdict = PASS
    return DeltaReport(verdict, gates, bands, notes)


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────────

def format_report(report: DeltaReport) -> str:
    out = [f"Comparison verdict: {report.verdict}", ""]
    out.append("Hard gates (relative to baseline):")
    for g in report.gates:
        out.append(f"  [{'PASS' if g.passed else 'FAIL'}] {g.name}: {g.detail}")
    if report.bands:
        out.append("\nBands (drift vs baseline):")
        for b in report.bands:
            tag = "ok" if b.within else "DRIFT"
            out.append(f"  [{tag}] {b.metric}: {b.baseline:g} -> {b.candidate:g} "
                       f"({b.delta_pct:+.0%}, allowed ±{b.allowed_pct:.0%})")
    if report.notes:
        out.append("\nNotes:")
        for n in report.notes:
            out.append(f"  - {n}")
    return "\n".join(out)


def load_thresholds(path: Path, project: str | None = None) -> Thresholds:
    return Thresholds.from_config(json.loads(path.read_text(encoding="utf-8")), project)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex eval compare <baseline.json> <candidate.json> "
              "[--thresholds <file>] [--project <name>] [--json]\n\n"
              "Compare two MapProfile JSON files and apply the relative regression gates.\n"
              "Exit: 0 PASS · 2 DRIFT (band breach) · 1 REGRESSED (hard gate).")
        return 0
    project: str | None = None
    thresholds_path: Path | None = None
    positional: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--project":
            i += 1
            if i >= len(argv):
                print("ERROR: --project needs a name", file=sys.stderr)
                return 2
            project = argv[i]
        elif a == "--thresholds":
            i += 1
            if i >= len(argv):
                print("ERROR: --thresholds needs a path", file=sys.stderr)
                return 2
            thresholds_path = Path(argv[i])
        elif a == "--json":
            pass
        elif a.startswith("-"):
            print(f"ERROR: unknown option '{a}'", file=sys.stderr)
            return 2
        else:
            positional.append(a)
        i += 1
    if len(positional) != 2:
        print("ERROR: need exactly <baseline.json> <candidate.json>", file=sys.stderr)
        return 2
    base_path, cand_path = Path(positional[0]), Path(positional[1])
    for p in (base_path, cand_path):
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            return 1
    if thresholds_path is not None and not thresholds_path.exists():
        print(f"ERROR: --thresholds {thresholds_path} not found", file=sys.stderr)
        return 1
    baseline = MapProfile.from_json(base_path.read_text(encoding="utf-8"))
    candidate = MapProfile.from_json(cand_path.read_text(encoding="utf-8"))
    thresholds = load_thresholds(thresholds_path, project) if thresholds_path else Thresholds()
    report = compare(baseline, candidate, thresholds)
    print(report.to_json() if "--json" in argv else format_report(report))
    return _EXIT[report.verdict]


if __name__ == "__main__":
    raise SystemExit(main())
