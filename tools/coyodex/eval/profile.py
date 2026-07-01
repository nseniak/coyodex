#!/usr/bin/env python3
"""`coyodex score` — the deterministic quality PROFILE of a built map (the eval's reusable heart).

A map is LLM-authored, so two runs on the same repo differ in IDs, wording, and ordering — you cannot
regress a map by diffing its text. This module reduces a map to a `MapProfile`: a set of measurable
quality signals that ARE comparable run-to-run:

  well-formedness  — `validate` problems / warnings (via the shared `validate_analysis.validate_map`)
  self-consistency — `audit` findings, by severity, + the L2 grounding worklist size
  coverage         — compression / absent-module flags (needs the repo; else omitted)
  structure        — counts of use cases, subsystems, subdomains, components, deps, entities, edges,
                     Golden-Path steps, T6 flows, security surfaces
  concept sets     — auth-surface / use-case / entity NAMES, for the comparator's set diffs and the
                     "an auth surface must not silently disappear" gate

Everything here is DETERMINISTIC and stdlib-only. It reuses the validator's and audit's exact parse
(`schema_v1`, `validate_analysis`, `audit_analysis`) — never a second grammar. The comparator (baseline
vs candidate → verdict) and the LLM-judge layer build ON this profile; they are separate modules.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from coyodex import audit_analysis, schema_v1, validate_analysis

_PREFIX = re.compile(r"[A-Z]+")


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
    gp_steps: int
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


# ── parsing helpers (all through the shared schema-v1 grammar) ──────────────────────────────────────

def _counts_by_prefix(defined_counts: dict[str, int]) -> dict[str, int]:
    """{id-prefix: number of DISTINCT ids} — e.g. {'UC': 6, 'C': 12, 'E': 9, 'S': 3, 'SD': 2}. Counts
    each id once (a duplicate id is a validation error, not two elements)."""
    out: dict[str, int] = {}
    for i in defined_counts:
        m = _PREFIX.match(i)
        pre = m.group(0) if m else i
        out[pre] = out.get(pre, 0) + 1
    return out


def _security_surfaces(text: str) -> list[str]:
    """The `Surface` cells of the Security & auth table (header starts `surface` + has `auth check`).
    The same table the audit's L2 worklist reads; we keep the surface NAMES (and skip a blank-named
    row — a malformed row is not a real surface, so this count can sit one below the audit's L2 surface
    count on such a row) so the comparator can flag a baseline surface a later map drops."""
    for _start, block in validate_analysis.iter_tables(text):
        headers = [c.lower() for c in schema_v1.split_cells(block[0])]
        if not headers or headers[0] != "surface" or "auth check" not in headers:
            continue
        out: list[str] = []
        for row in block[2:]:
            if schema_v1.is_separator_row(row):
                continue
            cells = schema_v1.split_cells(row)
            if cells and cells[0].strip():
                out.append(cells[0].strip())
        return out
    return []


def _use_case_names(text: str) -> list[str]:
    """UC display names from the Use-cases table (header has a `use case` column, id in the first cell).
    Mirrors `audit_analysis.collect_use_case_actors`, keeping the name column instead of the actor."""
    for _start, block in validate_analysis.iter_tables(text):
        headers = [c.lower() for c in schema_v1.split_cells(block[0])]
        # Require an `actor` column too, EXACTLY as the audit's collect_use_case_actors does. That guard
        # is what excludes the Roles table — its `use cases they drive` header also starts with "use
        # case" and, being emitted first by iter_tables, would otherwise shadow the real Use-cases table
        # and make this return no names (review Finding 1).
        if "actor" not in headers:
            continue
        ui = next((i for i, h in enumerate(headers) if h.startswith("use case")), None)
        if ui is None:
            continue
        out: list[str] = []
        for row in block[2:]:
            if schema_v1.is_separator_row(row):
                continue
            cells = schema_v1.split_cells(row)
            if not cells or ui >= len(cells):
                continue
            uc = schema_v1.ID_TOKEN.search(cells[0])
            if uc and uc.group(0).startswith("UC") and cells[ui].strip():
                out.append(cells[ui].strip())
        return out
    return []


# ── the profile ─────────────────────────────────────────────────────────────────────────────────────

def build_profile(map_text: str, repo_root: Path | None = None,
                  map_path: Path | None = None) -> MapProfile:
    """Reduce a project map to its deterministic `MapProfile`. `repo_root` (the mapped source) enables
    the coverage signal; without it `coverage_flags` is None. `map_path` is only used to resolve the
    map's own location for validation (unused by the default checks)."""
    raw = map_text
    fence_line = schema_v1.unterminated_fence_line(raw)
    text = schema_v1.strip_fences(raw)
    lines = text.splitlines()

    # well-formedness — the shared orchestration the CLI `validate` also runs.
    problems, warnings = validate_analysis.validate_map(text, map_path)
    if fence_line is not None:
        # strip_fences blanked everything after the fence, so validate_map ran on truncated text and
        # can't see the real cause; surface it as the first (blocking) problem, as `validate` does.
        problems = [f"Unterminated code fence opened at line {fence_line} — parse is truncated"] + list(problems)

    # self-consistency — the audit's L1 findings + the size of its L2 grounding worklist.
    findings = audit_analysis.audit(text)
    contradictions = sum(1 for f in findings if f.severity == audit_analysis.CONTRADICTION)
    advisories = sum(1 for f in findings if f.severity == audit_analysis.ADVISORY)
    audit_warnings = sum(1 for f in findings if f.severity == audit_analysis.WARNING)
    l2_claims = len(audit_analysis.l2_worklist(text))

    # structure.
    defined_counts, gp_order = validate_analysis.collect_defined(text)
    by_prefix = _counts_by_prefix(defined_counts)
    surfaces = _security_surfaces(text)

    # coverage — re-measure the repo tree (opt-in, needs the source).
    coverage_flags: int | None = None
    if repo_root is not None:
        coverage_flags = len(validate_analysis.check_compression_coverage(text, Path(repo_root).resolve()))

    return MapProfile(
        use_cases=by_prefix.get("UC", 0),
        subsystems=by_prefix.get("S", 0),
        subdomains=by_prefix.get("SD", 0),
        components=by_prefix.get("C", 0),
        deps=by_prefix.get("D", 0),
        entities=by_prefix.get("E", 0),
        edges=len(validate_analysis.collect_edges(text)),
        gp_steps=len(gp_order),
        flows=sum(1 for _ in schema_v1.iter_flows(lines)),
        security_surfaces=len(surfaces),
        validate_ok=not problems,
        validate_problems=len(problems),
        validate_warnings=len(warnings),
        contradictions=contradictions,
        advisories=advisories,
        audit_warnings=audit_warnings,
        l2_claims=l2_claims,
        coverage_flags=coverage_flags,
        auth_surfaces=surfaces,
        use_case_names=_use_case_names(text),
        entity_names=[c.name for c in schema_v1.iter_domain_cards(lines)],
    )


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────────

def _format(p: MapProfile) -> str:
    cov = "n/a (no --repo)" if p.coverage_flags is None else str(p.coverage_flags)
    verdict = "OK" if p.validate_ok else f"FAILED ({p.validate_problems} problem(s))"
    return "\n".join([
        "Map profile — deterministic quality signals",
        "",
        f"  structure   : UC {p.use_cases} · S {p.subsystems} · SD {p.subdomains} · C {p.components} "
        f"· D {p.deps} · E {p.entities} · edges {p.edges} · GP {p.gp_steps} · flows {p.flows} "
        f"· auth-surfaces {p.security_surfaces}",
        f"  validate    : {verdict}, {p.validate_warnings} warning(s)",
        f"  audit       : {p.contradictions} contradiction(s) · {p.advisories} advisory · "
        f"{p.audit_warnings} warning(s) · {p.l2_claims} L2 claim(s)",
        f"  coverage    : {cov} compression/absent flag(s)",
    ])


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex score [.coyodex/project-map.md] [--repo <source-root>] [--json]\n\n"
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
    path = Path(positional[0] if positional else ".coyodex/project-map.md")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    if repo_root is not None and not repo_root.exists():
        print(f"ERROR: --repo {repo_root} not found", file=sys.stderr)
        return 1
    profile = build_profile(path.read_text(encoding="utf-8"), repo_root=repo_root, map_path=path)
    print(profile.to_json() if "--json" in argv else _format(profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
