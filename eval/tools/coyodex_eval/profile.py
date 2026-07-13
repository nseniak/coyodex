#!/usr/bin/env python3
"""`coyodex-eval score` — the deterministic quality PROFILE of a built map (the eval's reusable heart).

A map is LLM-authored, so two runs on the same repo differ in IDs, wording, and ordering — you cannot
regress a map by diffing its text. This module reduces a map to a `MapProfile`: a set of measurable
quality signals that ARE comparable run-to-run:

  well-formedness  — `validate` problems / warnings (via the shared `validate_model.validate_model`)
  self-consistency — `audit` findings, by severity, + the L2 grounding worklist size
  coverage         — compression / absent-module flags (needs the repo; else omitted)
  structure        — counts of use cases, subsystems, subdomains, components, deps, entities, edges,
                     Happy-Path steps, T6 flows, security surfaces
  concept sets     — auth-surface / use-case / entity NAMES, for the comparator's set diffs and the
                     "an auth surface must not silently disappear" gate

Everything here is DETERMINISTIC and stdlib-only. It reads the map through the model pipeline
(`load_model` + `validate_model` + `audit_model`) — never a second grammar. The comparator
(baseline vs candidate → verdict) and the LLM-judge layer build ON this profile; they are separate
modules.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from coyodex import audit_model, balance_lib, validate_model
from coyodex.model import ModelError, ProjectModel, load_model
from coyodex.preindex_lib import expected_components  # the granularity expectation E, RE-COMPUTED
# from the repo tree at score time (shared code, never the pre-index's JSON — GR4)
from coyodex.validate_analysis import compression_coverage_from_refs  # repo-tree coverage (not a
# markdown parse — the same helper validate_model's --check-coverage runs)


@dataclass(frozen=True)
class MapProfile:
    """The deterministic quality signals of one built map. Serialized to `profile.json`; the comparator
    diffs two of these. Field order is the report order."""
    # ── structure (counts of the map's elements) ──
    use_cases: int
    subsystems: int
    subdomains: int
    components: int
    deps: int
    entities: int
    edges: int
    hp_steps: int
    flows: int
    security_surfaces: int
    # ── well-formedness (coyodex validate) ──
    validate_ok: bool
    validate_problems: int
    validate_warnings: int
    # ── self-consistency (coyodex audit) ──
    contradictions: int
    advisories: int
    audit_warnings: int
    l2_claims: int
    # ── coverage (None when scored without the repo) ──
    coverage_flags: int | None
    # ── density (scale-invariant ratios — the drift signal that stays steady when a map merely gets
    #    finer or coarser uniformly; None when the denominator is 0 or the profile predates the field) ──
    edges_per_component: float | None = None
    # ── granularity (the code-derived component expectation E — the leaf anchor both maps are
    #    measured against; None when scored without the repo, or the profile predates the field) ──
    granularity_expected: int | None = None
    # ── diagram balance (fan-out of the rendered S-forest diagrams — report-only, no gate; None
    #    when the profile predates the fields. Gating is opt-in per project via thresholds bands.) ──
    root_fanout: int | None = None
    max_fanout: int | None = None
    fanout_in_band_pct: float | None = None    # share of diagrams inside [3,9], exemptions included
    nesting_depth: int | None = None
    # ── concept sets (names, for the comparator's set diffs + the auth-surface gate) ──
    auth_surfaces: list[str] = field(default_factory=list)
    use_case_names: list[str] = field(default_factory=list)
    entity_names: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "MapProfile":
        # Filter to KNOWN fields so a baseline written by a newer profile version (e.g. once the judge
        # layer adds scores) still loads instead of raising on an unexpected keyword. A missing field
        # falls back to its dataclass default.
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in json.loads(s).items() if k in known})


# ── the profile ─────────────────────────────────────────────────────────────────────────────────────

def build_profile(map_text: str, repo_root: Path | None = None,
                  map_path: Path | None = None) -> MapProfile:
    """Reduce a project map to its deterministic `MapProfile`. `repo_root` (the mapped source) enables
    the coverage signal; without it `coverage_flags` is None. `map_path` is kept for signature
    compatibility (unused — view freshness is repo hygiene, not map quality)."""
    del map_path
    return build_profile_from_model(load_model(map_text), repo_root=repo_root)


def build_profile_from_model(m: ProjectModel, repo_root: Path | None = None) -> MapProfile:
    """The MapProfile computed from a model — every signal through the model-side checks
    (`validate_model`, `audit_model`). The Phase-2 golden-equivalence run proved these score a map
    exactly as the (now retired) markdown pipeline scored its v1 equivalent."""
    problems, warnings = validate_model.validate_model(m)  # no model_path: view-freshness is a
    # repo-hygiene signal, not map quality — it must not shift an eval profile
    findings = audit_model.audit_model(m)
    contradictions = sum(1 for f in findings if f.severity == audit_model.CONTRADICTION)
    advisories = sum(1 for f in findings if f.severity == audit_model.ADVISORY)
    audit_warnings = sum(1 for f in findings if f.severity == audit_model.WARNING)
    l2_claims = len(audit_model.l2_worklist_model(m))

    coverage_flags: int | None = None
    granularity_expected: int | None = None
    if repo_root is not None:
        root = Path(repo_root).resolve()
        coverage_flags = len(compression_coverage_from_refs(
            validate_model.referenced_paths(m, root), root))
        e = expected_components(root).expected
        granularity_expected = e if e > 0 else None  # a tree with no component-forming source anchors nothing

    surfaces = [s.surface for s in m.security if s.surface.strip()]
    n_components = len({c.id for c in m.components})
    n_edges = len(m.edges)
    root_fanout, max_fanout, in_band_pct, depth = balance_lib.fanout_summary(m)

    return MapProfile(
        use_cases=len({u.id for u in m.use_cases}),
        subsystems=len({s.id for s in m.subsystems}),
        subdomains=len({s.id for s in m.subdomains}),
        components=n_components,
        deps=len({d.id for d in m.deps}),
        entities=len({e.id for e in m.entities}),
        edges=n_edges,
        hp_steps=len(m.happy_path),
        flows=len(m.flows),
        security_surfaces=len(surfaces),
        validate_ok=not problems,
        validate_problems=len(problems),
        validate_warnings=len(warnings),
        contradictions=contradictions,
        advisories=advisories,
        audit_warnings=audit_warnings,
        l2_claims=l2_claims,
        coverage_flags=coverage_flags,
        edges_per_component=round(n_edges / n_components, 3) if n_components else None,
        granularity_expected=granularity_expected,
        root_fanout=root_fanout,
        max_fanout=max_fanout,
        fanout_in_band_pct=in_band_pct,
        nesting_depth=depth,
        auth_surfaces=surfaces,
        use_case_names=[u.name for u in m.use_cases if u.name.strip()],
        entity_names=[e.name for e in m.entities],
    )


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────────

def _format(p: MapProfile) -> str:
    cov = "n/a (no --repo)" if p.coverage_flags is None else str(p.coverage_flags)
    gran = ("n/a (no --repo)" if p.granularity_expected is None
            else f"{p.components} components vs code-derived expectation ~{p.granularity_expected}")
    verdict = "OK" if p.validate_ok else f"FAILED ({p.validate_problems} problem(s))"
    return "\n".join([
        "Map profile — deterministic quality signals",
        "",
        f"  structure   : UC {p.use_cases} · S {p.subsystems} · SD {p.subdomains} · C {p.components} "
        f"· D {p.deps} · E {p.entities} · edges {p.edges} · HP {p.hp_steps} · flows {p.flows} "
        f"· auth-surfaces {p.security_surfaces}",
        f"  validate    : {verdict}, {p.validate_warnings} warning(s)",
        f"  audit       : {p.contradictions} contradiction(s) · {p.advisories} advisory · "
        f"{p.audit_warnings} warning(s) · {p.l2_claims} L2 claim(s)",
        f"  coverage    : {cov} compression/absent flag(s)",
        f"  granularity : {gran}",
        ("  balance     : n/a (profile predates the balance fields)"
         if p.fanout_in_band_pct is None else
         f"  balance     : root fan-out {p.root_fanout} · max {p.max_fanout} · "
         f"{p.fanout_in_band_pct:.0%} of diagrams in the 3–9 band · depth {p.nesting_depth} "
         f"(report-only)"),
    ])


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex-eval score [.coyodex/project-map.json] [--repo <source-root>] [--json]\n\n"
              "Emit the deterministic quality profile of a built map (structure / validate / audit /\n"
              "coverage). `--repo` enables the coverage signal by re-measuring the source tree.\n"
              "`--json` prints the machine-readable MapProfile (for the eval baseline / comparator).")
        return 0
    repo_root: Path | None = None
    positional: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--repo":
            i += 1
            if i >= len(argv):
                print("ERROR: --repo needs a path", file=sys.stderr)
                return 2
            repo_root = Path(argv[i])
        elif a == "--json":
            pass
        elif a.startswith("-"):
            print(f"ERROR: unknown option '{a}'", file=sys.stderr)
            return 2
        else:
            positional.append(a)
        i += 1
    path = Path(positional[0] if positional else ".coyodex/project-map.json")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    if repo_root is not None and not repo_root.exists():
        print(f"ERROR: --repo {repo_root} not found", file=sys.stderr)
        return 1
    try:
        profile = build_profile(path.read_text(encoding="utf-8"), repo_root=repo_root)
    except ModelError as e:
        print(f"ERROR: {path}: {e}", file=sys.stderr)
        return 1
    print(profile.to_json() if "--json" in argv else _format(profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
