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

from coyodex_eval.legacy_map import load_model_tolerating_legacy
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
    #: Audit findings of ADVISORY severity — audit ONLY, which is why the name says so. It was
    #: `advisories`, sitting next to `validate_warnings`, and on a map `finalize` called
    #: "ADVISORIES — 12 advisory" this field read 0. A retrospective quoted it as "the map has no
    #: advisories". Renamed with NO back-compat alias by operator decision: profiles written before
    #: this fail to load rather than silently reading 0, and the eval baselines are git-ignored
    #: artifacts that are cheap to re-bless.
    audit_advisories: int
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
    # ── use-case granularity (the flow analog of the fan-out fields — report-only, same opt-in
    #    gating pattern; None when the profile predates the fields). Counts are AUTHORED steps: a
    #    sub-flow reference counts as 1, so extraction is rewarded, not punished. ──
    subflows: int | None = None
    max_flow_len: int | None = None
    flows_over_band_pct: float | None = None   # share of flows over FLOW_STEPS_HI (15)
    # ── use-case & Happy-Path completeness (report-only; band-able per project via a thresholds
    #    entry, like every numeric field — nothing compares them by default; None when the profile
    #    predates the fields or the signal is not computable). Counts are RAW (pre-escape): a
    #    recorded 'Unclaimed surfaces' / 'Happy Path coverage' adjudication silences the validate
    #    warning but not these — the same convention as flows_over_band_pct vs 'Balance exceptions',
    #    so the drift signal survives the adjudication. ──
    entry_points: int | None = None
    external_entry_points: int | None = None   # effective activation (authored-if-valid, else kind)
    unclaimed_entry_points: int | None = None  # external EPs whose component no flow reaches;
    #                                            None when the map has no entry points or no flows
    off_spine_ucs: int | None = None           # use cases with no HP position; None when HP empty
    unclaimed_self_entry_points: int | None = None  # SELF-activated EPs (crons, workers, consumers,
    #                                            startup hooks) no use case reaches. These used to be
    #                                            exempt automatically, which could hide a whole
    #                                            background capability; they are now a decision, and
    #                                            this is the number that shows whether it was taken.
    capabilities: int | None = None            # size of the use-case grouping; None on a map that
    #                                            has not adopted it (the field is additive)
    capabilities_untraced: int | None = None   # capabilities NONE of whose use cases is traced — an
    #                                            empty box in the overlay, i.e. a real part of the
    #                                            product nobody traced. Invisible before this existed.
    use_cases_untraced: int | None = None      # trace debt. The target is 100 %; measured on a real
    #                                            build, closing a 15-of-25 gap costs ~12 % of build
    #                                            tokens, so the shortfall is reported, never redefined
    #                                            as correct.
    off_spine_in_core_capabilities: int | None = None  # the deliberate give-up of the capability-level
    #                                            spine check, made countable: use cases off the walk
    #                                            inside a CORE capability, which no longer warn.
    entities_in_flows: int | None = None       # distinct entities appearing as a flow-step
    #                                            endpoint (sub-flows expanded) — the flow-derived
    #                                            'Used in UC' coverage of the domain model
    entities_in_flows_pct: float | None = None  # share of all entities; both fields None when the
    #                                            map has no entities or no flows (an untraced map
    #                                            is "not yet traced", not "traced and zero")
    # ── business logic (T7 — the decision layer) ────────────────────────────────────────────────
    # None on a map that has not adopted the layer, so an old profile stays loadable and an
    # un-adopted map is distinguishable from one whose sweep found nothing. REPORT-ONLY by default,
    # band-able per project via a thresholds entry — the same treatment `capabilities`, `subflows`
    # and the completeness fields get, and for the same reason: a DEFAULT band on an
    # adoption-dependent metric emits a "skipped, not numeric on both sides" note on every
    # comparison of every map that has not adopted it. `l2_claims` stays unbanded on purpose and
    # rule sites inflate it, so the collapse signal to band here is `rules` / `rule_sites`.
    rules: int | None = None                   # how many decisions the map states
    blocks: int | None = None                  # the decision grouping
    rule_sites: int | None = None              # ANCHORED enforcement sites across all rules — the
    #                                            number that says whether the rules are grounded or
    #                                            merely listed. A `no_call_site` entry is deliberately
    #                                            NOT counted: it is a declared absence, so counting
    #                                            it would inflate exactly the metric it is absent from.
    rules_swept: int | None = None             # rules whose components hold NO uncovered
    #                                            decision-sounding step. DERIVED (validate_model.
    #                                            rules_swept) — there is no authored flag, on
    #                                            purpose: "I searched the whole repo" is
    #                                            unfalsifiable, and a hand-set one would make this
    #                                            metric measure the author's confidence.
    rules_unverified: int | None = None        # rules with AT LEAST ONE anchored site in a file no
    #                                            component claims, so part of the rule renders bare.
    #                                            The debt number, and it matches what the T7 view
    #                                            stamps: counting only rules where EVERY site fails
    #                                            under-reports precisely the partly-grounded rule,
    #                                            which is the interesting one.
    # ── deployment linkage ──────────────────────────────────────────────────────────────────────
    # A Deployment view is only a view if components point at units. A live rebuild kept all eight
    # units, dropped the two components that owned the nginx and vector files, and filled `runs_in`
    # by contiguous component-id range — a formula that can only produce contiguous buckets, so six
    # of the eight boxes ended up empty. Nothing watched it: `runs_in` COVERAGE went 93/96 -> 66/66,
    # a perfect score produced by dumping everything into two units. Coverage is not linkage.
    deployment_units: int = 0
    deployment_units_linked: int = 0             # units named by at least one component's runs_in
    # Linkage counts UNITS, and a unit is cheap to add. A live map scored 3/10 linked where the
    # three linked units — `backend`, `standalone`, `e2e backend shard` — hosted the IDENTICAL 50
    # components: one placement decision, replicated across three deployment shapes of the same
    # process, while the other 30 components (the whole frontend) sat in no unit at all. The gate
    # passed on 2/8 -> 3/10 because a unit had been ADDED, not because code had been placed. This
    # counts DISTINCT non-empty component sets instead, so replicating a shape cannot move it.
    deployment_distinct_hosted_sets: int = 0
    # The EMPTY boxes: units running no component and no entry point that are not system infra
    # either (`validate_model.orphan_deployment_units`, the same list `validate` advises on).
    #
    # Linkage as an absolute count punished a map for getting BETTER. One rebuild named 4 units, all
    # first-party runtimes, all linked; the next named 11 — the same 3 runtimes plus the proxy, two
    # datastores, the log forwarder, two test instances and two test doubles — and correctly folded
    # a unit that was really a mount inside the backend process into that process. Linked went
    # 4 -> 3, the gate FAILED, and the Deployment view it was judging had gained seven honest boxes
    # and lost nothing. Infra units are empty BY NATURE, so counting them as unfilled linkage
    # measures how COMPLETE the section is and reports completeness as a regression.
    deployment_orphan_units: int = 0
    # Did the map RECORD `runs-in/quality`, the literal that tells `validate` those empty boxes are
    # deliberate? The count above stays raw — a profile states facts about a map — and the policy
    # decision lives in the gate, which would otherwise contradict the tool: `validate` honours the
    # record and stays quiet while the gate failed on the same three units. A build reading one
    # green tool and one red gate about one fact has no way to act on either.
    deployment_orphans_excepted: bool = False

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
        raw = json.loads(s)
        known = {f.name for f in fields(cls)}
        # A profile written before `advisories` became `audit_advisories`. It is REFUSED, not
        # adapted: the rename exists because the old name read as "the whole map's advisories" when
        # it only ever counted audit's, and quietly accepting the old key would carry that
        # misreading into the comparison. Baselines are git-ignored artifacts — re-score and re-bless.
        if "advisories" in raw and "audit_advisories" not in raw:
            raise ValueError(
                "this profile predates the `advisories` -> `audit_advisories` rename. It counted "
                "AUDIT advisories only, and the old name was being read as the map's total. "
                "Re-score the map (`coyodex-eval score <map> --repo . --json`) and re-bless the "
                "baseline; there is deliberately no back-compat alias.")
        return cls(**{k: v for k, v in raw.items() if k in known})


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
    audit_advisories = sum(1 for f in findings if f.severity == audit_model.ADVISORY)
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

    # THE AUTH SURFACE, from both storages. `compare.auth_surfaces_must_not_drop` is a hard gate
    # with no tolerance, and phase 8 empties `security[]` into rules with `access: true` — so the
    # union is a no-op while both exist and a no-op again after the fold. Inverted HERE, one phase
    # before the fold, precisely so the gate never sees the transition.
    # De-duplicated as ONE set, not two passes: a list comprehension is evaluated against the
    # pre-`+=` list, so it would dedup rules against security rows and never against other rules —
    # and `security_surfaces = len(surfaces)` feeds `auth_surfaces_must_not_drop`, a hard gate with
    # no tolerance, where one duplicate masks one genuinely dropped surface.
    surfaces: list[str] = []
    for name in ([s.surface.strip() for s in m.security]
                 + [r.statement.strip() for r in m.rules if r.access]):
        if name and name not in surfaces:
            surfaces.append(name)
    owners = validate_model.component_file_owners(m)   # built once; the derivation's shared index
    n_components = len({c.id for c in m.components})
    n_edges = len(m.edges)
    root_fanout, max_fanout, in_band_pct, depth = balance_lib.fanout_summary(m)
    flow_lens = [len(f.steps) for f in m.flows]  # authored counts: a sub-flow reference counts as 1
    over_band = sum(1 for n in flow_lens if n > validate_model.FLOW_STEPS_HI)
    # Completeness — computed by the SAME helpers the validate advisory runs (never a second
    # implementation). Raw signal, pre-escape (see the field comments above).
    n_external = len(validate_model.external_entry_points(m))
    unclaimed = (len(validate_model.unclaimed_external_entry_points(m))
                 if m.entry_points and m.flows else None)
    off_spine = (sum(1 for u in m.use_cases if u.id not in {g.uc for g in m.happy_path})
                 if m.happy_path else None)
    e_in_flows = (len(validate_model.flow_touched_entities(m))
                  if m.entities and m.flows else None)
    unclaimed_self = (len(validate_model.unclaimed_self_entry_points(m))
                      if m.entry_points and m.flows else None)
    counts = validate_model.completeness_counts(m)
    n_caps = len(m.capabilities) or None      # None on a map that has not adopted the grouping
    caps_untraced = counts["capabilities_untraced"] if m.capabilities else None
    ucs_untraced = counts["use_cases_untraced"] if m.use_cases else None
    off_spine_core = counts["off_spine_in_core_capabilities"] if m.capabilities and m.happy_path else None

    # Linkage, not coverage: how many declared units any component actually claims to run in.
    unit_names = [u.unit for u in m.deployment if u.unit]
    claimed = {name for c in m.components for name in (c.runs_in or [])}
    claimed |= {name for ep in m.entry_points for name in (ep.runs_in or [])}
    # What each unit hosts, as a set — two units hosting the same set are one placement decision
    # wearing two names, and only the distinct sets are evidence the view says anything.
    #
    # Components AND entry points, because `deployment_units_linked` above counts both and the two
    # numbers are read side by side. Counting only components made a map that places its frontend
    # via entry-point `runs_in` score `linked > 0` with `distinct_sets == 0` — which passed the gate
    # vacuously AND suppressed the note that explains the gap. Entry points are keyed by index;
    # they carry no id, and only set IDENTITY matters here.
    hosted: dict[str, frozenset[str]] = {}
    for u in unit_names:
        members = frozenset(
            [c.id for c in m.components if u in (c.runs_in or [])]
            + [f"ep:{i}" for i, ep in enumerate(m.entry_points) if u in (ep.runs_in or [])])
        if members:
            hosted[u] = members

    return MapProfile(
        deployment_units=len(unit_names),
        deployment_units_linked=sum(1 for u in unit_names if u in claimed),
        deployment_distinct_hosted_sets=len(set(hosted.values())),
        deployment_orphan_units=len(validate_model.orphan_deployment_units(m)),
        deployment_orphans_excepted="runs-in/quality" in balance_lib._exceptions(m),
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
        audit_advisories=audit_advisories,
        audit_warnings=audit_warnings,
        l2_claims=l2_claims,
        coverage_flags=coverage_flags,
        edges_per_component=round(n_edges / n_components, 3) if n_components else None,
        granularity_expected=granularity_expected,
        root_fanout=root_fanout,
        max_fanout=max_fanout,
        fanout_in_band_pct=in_band_pct,
        nesting_depth=depth,
        subflows=len({sf.id for sf in m.subflows}),
        max_flow_len=max(flow_lens) if flow_lens else None,
        flows_over_band_pct=round(100 * over_band / len(flow_lens), 1) if flow_lens else None,
        entry_points=len(m.entry_points),
        external_entry_points=n_external,
        unclaimed_entry_points=unclaimed,
        off_spine_ucs=off_spine,
        unclaimed_self_entry_points=unclaimed_self,
        capabilities=n_caps,
        capabilities_untraced=caps_untraced,
        use_cases_untraced=ucs_untraced,
        off_spine_in_core_capabilities=off_spine_core,
        entities_in_flows=e_in_flows,
        entities_in_flows_pct=(round(100 * e_in_flows / len(m.entities), 1)
                               if e_in_flows is not None else None),
        rules=len({r.id for r in m.rules}) or None,
        blocks=len({b.id for b in m.blocks}) or None,
        rule_sites=(sum(1 for r in m.rules for s in r.sites if (s.where or "").strip())
                    if m.rules else None),
        rules_swept=(sum(1 for v in validate_model.rules_swept(m).values() if v)
                     if m.rules else None),
        rules_unverified=(sum(1 for r in m.rules
                              if any((s.where or "").strip()
                                     and not validate_model.site_components(m, s, owners)
                                     for s in r.sites))
                          if m.rules else None),
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
        f"· auth-surfaces {p.security_surfaces}"
        + (f"\n  business    : BR {p.rules} in {p.blocks} block(s) · {p.rule_sites} site(s) · "
           f"{p.rules_swept} swept · {p.rules_unverified} unverified"
           if p.rules else ""),
        f"  validate    : {verdict}, {p.validate_warnings} warning(s)",
        f"  audit       : {p.contradictions} contradiction(s) · {p.audit_advisories} advisory · "
        f"{p.audit_warnings} warning(s) · {p.l2_claims} L2 claim(s)",
        f"  coverage    : {cov} compression/absent flag(s)",
        f"  granularity : {gran}",
        ("  balance     : n/a (profile predates the balance fields)"
         if p.fanout_in_band_pct is None else
         f"  balance     : root fan-out {p.root_fanout} · max {p.max_fanout} · "
         f"{p.fanout_in_band_pct:.0%} of diagrams in the 3–9 band · depth {p.nesting_depth} "
         f"(report-only)"),
        ("  completeness: n/a (profile predates the completeness fields)"
         if p.entry_points is None else
         f"  completeness: entry points {p.entry_points} ({p.external_entry_points} external, "
         f"{'n/a' if p.unclaimed_entry_points is None else p.unclaimed_entry_points} unclaimed) "
         f"· off-spine UCs {'n/a' if p.off_spine_ucs is None else p.off_spine_ucs} "
         f"· entities in flows "
         f"{'n/a' if p.entities_in_flows is None else f'{p.entities_in_flows} ({p.entities_in_flows_pct}%)'} "
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
        # READ-ONLY tolerance for a map an older coyodex wrote. `score` looking backwards at the map a
        # rebuild replaced is its whole job in a retrospective, and a schema rename used to make that
        # impossible: exit 1, no profile, and the reviewer hand-patching a copy to get a number.
        # Writing paths (assemble / validate / fix) keep the strict loader and the loud refusal.
        model, notes = load_model_tolerating_legacy(path.read_text(encoding="utf-8"))
        for note in notes:
            print(f"WARNING: {path}: {note}", file=sys.stderr)
        profile = build_profile_from_model(model, repo_root=repo_root)
    except ModelError as e:
        print(f"ERROR: {path}: {e}", file=sys.stderr)
        return 1
    print(profile.to_json() if "--json" in argv else _format(profile))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
