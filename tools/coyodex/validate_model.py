#!/usr/bin/env python3
"""Validate a model (`project-map.json`) — `coyodex validate`.

Two layers:

  1. STRUCTURE — `model.load_model` already validated shape/types/id-prefixes. This module starts
     where structure ends.
  2. SEMANTICS — every referenced ID resolves, hierarchy sound (right-kind parents, no cycles,
     deep-nest advisory), HP steps name their use case, flow actors resolve to Roles, dep Kinds in
     the closed vocabulary, domain-card completeness, plus every advisory nudge (altitude, empty
     groups, unowned entities, orphan deps honoring the `deployment_linked` marker) and the opt-in
     repo-reading checks (`--check-sources` anchors + entity grounding, `--check-coverage`
     compression + under-harvest, with `--repo` carried over).

One extra check: the committed markdown VIEW must match the model (it is generated, never edited)
— a stale or hand-edited `project-map.md` next to the JSON is flagged.

Stdlib-only.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

from coyodex import balance_lib, grammar
from coyodex.anchors import DIR_ANCHOR as _DIR_ANCHOR, FILE_ANCHOR as _ANCHOR_LINE
from coyodex.pysrc import parse_python
from coyodex.model import (
    ID_ARRAYS,
    ID_SHAPE,
    Entity,
    EntryPoint,
    FlowStep,
    ModelError,
    ProjectModel,
    all_elements,
    expanded_flow_steps,
    load_model,
)
from coyodex.validate_analysis import (
    _ALTITUDE_MIN,
    _COVERAGE_SAMPLE,
    _ISOLATED_FRACTION,
    _ISOLATED_MIN,
    _ISOLATED_MIN_ENTITIES,
    _LIST_ITEM,
    _REF_INLINE,
    _REF_LINK,
    _UNCOVERED_FRACTION,
    _UNCOVERED_MIN,
    _is_non_entity_type,
    _resolve_source_file,
    _source_roots,
    _type_covered,
    _where_href,
    check_hierarchy,
    compression_coverage_from_refs,
    file_level_coverage,
    granularity_advisory,
    strip_anchor,
)

_WRITE_VERBS = ("persists", "writes")  # ownership verbs for the unowned-entities nudge (as in v1)


# ── shared extraction ────────────────────────────────────────────────────────────────────────────

def _strings(value: object, skip_keys: frozenset[str] = frozenset({"format"})) -> list[str]:
    """Every string stored in the model (recursively), the analog of scanning the whole markdown
    document — ID references and path references live anywhere in authored text."""
    out: list[str] = []
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import fields
        for f in fields(value):  # type: ignore[arg-type]
            if f.name not in skip_keys:
                out.extend(_strings(getattr(value, f.name)))
    elif isinstance(value, list):
        for v in value:
            out.extend(_strings(v))
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_strings(v))
    elif isinstance(value, str):
        out.append(value)
    return out


def _parents(m: ProjectModel) -> dict[str, str]:
    """child id -> parent id, across both forests (C→S, S→S, SD→SD, E→SD) — single-source, on the
    child."""
    out: dict[str, str] = {}
    for c in m.components:
        if c.subsystem:
            out[c.id] = c.subsystem
    for s in m.subsystems:
        if s.parent:
            out[s.id] = s.parent
    for sd in m.subdomains:
        if sd.parent:
            out[sd.id] = sd.parent
    for e in m.entities:
        if e.subdomain:
            out[e.id] = e.subdomain
    return out


def _first_link_of(el: object, cells: list[str | None]) -> str | None:
    """A definition's first markdown link, across a set of candidate free-text cells."""
    link = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for c in cells:
        if c:
            hit = link.search(c)
            if hit:
                return hit.group(1).strip()
    return None


def _is_subsystem_id(i: str) -> bool:
    return i.startswith("S") and not i.startswith("SD") and not i.startswith("SF")


# ── semantic checks ──────────────────────────────────────────────────────────────────────────────

def _check_ids(m: ProjectModel) -> list[str]:
    problems: list[str] = []
    counts: dict[str, int] = {}
    for attr in ID_ARRAYS:
        if attr == "happy_path":
            continue  # a use case may occupy several HP positions; HP ids ride their own check
        for el in getattr(m, attr):
            counts[el.id] = counts.get(el.id, 0) + 1
    duplicates = sorted(i for i, n in counts.items() if n > 1)
    if duplicates:
        problems.append(f"Duplicate element definitions: {', '.join(duplicates)}")

    # Pointer fields must be well-shaped ids (the `S12a` class — invisible to the reference scan
    # because a suffixed token is not an ID token at all).
    pointers: list[tuple[str, str, str | None]] = (
        [(c.id, "subsystem", c.subsystem) for c in m.components]
        + [(s.id, "parent", s.parent) for s in m.subsystems]
        + [(sd.id, "parent", sd.parent) for sd in m.subdomains]
        + [(e.id, "subdomain", e.subdomain) for e in m.entities]
        + [(g.id, "uc", g.uc) for g in m.happy_path]
        + [(e.id, "relation target", r.target) for e in m.entities for r in e.relations]
        + [(f"{f.uc} step {st.n}", "subflow", st.subflow) for f in m.flows for st in f.steps]
        + [(f"{sf.id} step {st.n}", "subflow", st.subflow) for sf in m.subflows for st in sf.steps]
    )
    for owner, field_name, val in pointers:
        if val is not None and not ID_SHAPE.match(val):
            problems.append(f"{owner}: {field_name} '{val}' is not a valid schema ID "
                            f"(prefix + digits only)")
    for e in m.edges:
        for end in (e.src, e.dst):
            if not ID_SHAPE.match(end):
                problems.append(f"Edge {e.src} → {e.dst}: endpoint '{end}' is not a valid schema ID")
    # An entry point's owning `component` is a C-id pointer (json_schema publishes `^C\d+$`), not a
    # general element id — an `S1`/`E3` owner is a shape error here, while empty stays legal (an
    # ownerless EXTERNAL row gets its own completeness warning, never a blocking problem). Checked
    # on the RAW value: a padded ' C1' matches the strip-tolerant semantic checks but detaches in
    # the viewer (it keys components by the exact string), so the padding itself is the error.
    for i, ep in enumerate(m.entry_points):
        if ep.component.strip() and not re.fullmatch(r"C\d+", ep.component):
            problems.append(f"entry_points[{i}] ({ep.kind}): component '{ep.component}' is not a "
                            "C id (the owning component — prefix C + digits, e.g. C3)")
    return problems


# An explicit in-prose cross-reference: `[[C12]]`. A BARE id-shaped token in prose or an anchor
# (the PKCE value `S256`, a `D3`/`C4` library name, an `infra/S3/` path segment) is NOT a reference —
# `_referenced_ids` reads ids only from typed id fields and these `[[...]]` markers, so a domain string
# is never misread as a dangling ref (the class the whole-document scan used to false-positive on).
_BRACKET_REF = re.compile(r"\[\[([^\]]+)\]\]")


def _referenced_ids(m: ProjectModel) -> set[str]:
    """The ids the model genuinely cross-references, gathered ONLY from typed id-bearing fields and
    explicit `[[ID]]` prose markers — never scanned out of free prose or anchor strings."""
    refs: set[str] = set()
    for c in m.components:
        if c.subsystem:
            refs.add(c.subsystem)
    for s in m.subsystems:
        if s.parent:
            refs.add(s.parent)
    for sd in m.subdomains:
        if sd.parent:
            refs.add(sd.parent)
    for g in m.happy_path:
        if g.uc:
            refs.add(g.uc)
    for u in m.use_cases:
        refs.update(u.actors)                        # a use case's actors are role ids
    for f in m.flows:
        if f.uc:
            refs.add(f.uc)
    for steps in ([f.steps for f in m.flows] + [sf.steps for sf in m.subflows]):
        for st in steps:  # sub-flow steps are ordinary steps — their endpoints must resolve too
            for end in (st.src, st.dst):              # backbone-element OR role-id (actor step) endpoints
                if end and (grammar.is_step_id(end) or grammar.is_role_id(end)):
                    refs.add(end)
            if st.subflow:
                refs.add(st.subflow)
    for e in m.edges:
        refs.add(e.src)
        refs.add(e.dst)
    for ep in m.entry_points:
        comp = ep.component.strip()
        if comp:  # the owning component — a dangling owner was invisible to the reference scan
            refs.add(comp)
    for en in m.entities:
        if en.subdomain:
            refs.add(en.subdomain)
        for r in en.relations:
            if r.target:
                refs.add(r.target)
        for fld in en.fields:
            refs |= grammar.fk_targets(fld.markers)            # FK→En markers
            refs.update(grammar.ID_TOKEN.findall(fld.type))    # entity-typed field, e.g. `auth:E7`
    for r in m.roles:
        refs.update(grammar.ID_TOKEN.findall(r.drives))        # `drives` holds the UC ids a role drives
    for tr in m.tests:
        refs.update(tr.targets)                                # test-completeness rows name element ids
    for s in _strings(m):                                      # deliberate prose cross-refs `[[ID]]`
        for inner in _BRACKET_REF.findall(s):
            tok = inner.strip()
            if grammar.ID_TOKEN.fullmatch(tok):
                refs.add(tok)
    return refs


def _check_references(m: ProjectModel) -> list[str]:
    """Every cross-referenced ID resolves to a defined element. References are read only from typed id
    fields + `[[ID]]` markers (`_referenced_ids`), never scanned out of prose/anchors — so a domain
    string shaped like an id (`S256`, `D3`) is never a false dangling ref. Additivity: stray S/SD refs
    are ignored while the map has no grouping/subdomains."""
    defined = set(all_elements(m)) | {g.id for g in m.happy_path}
    referenced = _referenced_ids(m)
    parents = _parents(m)
    grouping_present = (any(_is_subsystem_id(i) for i in defined)
                        or any(_is_subsystem_id(p) for p in parents.values()))
    subdomains_present = (any(i.startswith("SD") for i in defined)
                          or any(p.startswith("SD") for p in parents.values()))

    def suppress(r: str) -> bool:
        if r.startswith("SD"):
            return not subdomains_present
        if r.startswith("SF"):
            return False  # a dangling sub-flow ref is never additivity — always flag it
        if r.startswith("S"):
            return not grouping_present
        return False

    unresolved = sorted(r for r in referenced - defined if not suppress(r))
    return [f"References to undefined IDs: {', '.join(unresolved)}"] if unresolved else []


def _check_hp(m: ProjectModel) -> list[str]:
    missing = [g.id for g in m.happy_path if not g.uc]
    return ([f"Happy Path steps missing a use-case reference (`uc`): {', '.join(missing)}"]
            if missing else [])


def _check_flows(m: ProjectModel) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}
    for f in m.flows:
        counts[f.uc] = counts.get(f.uc, 0) + 1
    dups = sorted(uc for uc, c in counts.items() if c > 1)
    if dups:
        problems.append("Use cases with more than one T6 flow block (each use case has exactly one "
                        f"flow): {', '.join(dups)}")
    role_ids = {r.id for r in m.roles}
    sf_ids = {sf.id for sf in m.subflows}
    # flows and sub-flows share ONE per-step rulebook — a sub-flow's steps are ordinary steps
    containers: list[tuple[str, bool, list]] = (
        [(f"{f.uc} flow step", False, f.steps) for f in m.flows]
        + [(f"{sf.id} step", True, sf.steps) for sf in m.subflows])
    for prefix, in_subflow, steps in containers:
        seen_n: set[int] = set()
        for st in steps:
            tag = f"{prefix} {st.n}"
            if st.n in seen_n:  # `step:<uc|sf>:<n>` is the impact engine's synthetic id — unique `n`
                problems.append(f"{tag}: duplicate step number {st.n} — step numbers identify a "
                                "step (impact, navigation), so each appears once")
            seen_n.add(st.n)
            if not st.src or not st.dst:
                problems.append(f"{tag} is missing an endpoint (`from → to` needs both)")
                continue
            if st.subflow:  # a REFERENCE step: "runs SFn here"
                if in_subflow:
                    problems.append(f"{tag}: a sub-flow's step may not reference a sub-flow "
                                    "(one level only — inline the steps instead)")
                elif st.subflow not in sf_ids:
                    problems.append(f"{tag}: references undefined sub-flow '{st.subflow}'")
                if st.where or st.no_call_site:
                    problems.append(f"{tag}: a reference step carries no location of its own — its "
                                    "location IS the sub-flow's steps' anchors; drop "
                                    "`where`/`no_call_site`")
            elif not st.phrase.strip():  # reference steps may leave phrase empty (defaults to SF name)
                problems.append(f"{tag} has no action text (`phrase`) — every step describes what "
                                "happens at that point; it is not derived from the backbone edge")
            # An element↔element step is one concrete interaction — it carries ITS OWN call site
            # (`where` is THE location, unlike an edge's example `where`). Actor steps (a Role
            # endpoint fails `is_step_id`) are human actions — no call site to demand; reference
            # steps ground through the sub-flow's own anchors.
            if not st.subflow and grammar.is_step_id(st.src) and grammar.is_step_id(st.dst) \
                    and not st.where and not st.no_call_site:
                problems.append(
                    f"{tag}: no `where` call-site anchor — add the bare `path:line` of this step's own "
                    "interaction, or set `no_call_site` if it truly has no single site "
                    "(event-driven / shared-state / config-wired)")
            elif st.where and st.no_call_site:
                warnings.append(f"{tag}: `no_call_site` is set but a `where` is present — "
                                "drop one so the intent is unambiguous")
            if role_ids:  # a non-backbone endpoint is an actor step — it must be a defined Role id
                for end in (st.src, st.dst):
                    if not grammar.is_step_id(end) and end not in role_ids:
                        problems.append(f"{tag}: actor '{end}' is not a defined Role id")
    # A sub-flow's reason to exist is REUSE: referenced once (or never), it's indirection for free
    ref_counts: dict[str, int] = {}
    for f in m.flows:
        for st in f.steps:
            if st.subflow:
                ref_counts[st.subflow] = ref_counts.get(st.subflow, 0) + 1
    for sf in m.subflows:
        n_refs = ref_counts.get(sf.id, 0)
        if n_refs < 2:
            warnings.append(f"{sf.id} ({sf.name}) is referenced by {n_refs} flow(s) — a sub-flow "
                            "earns its keep at ≥2; consider inlining it")
    return problems, warnings


# ── use-case granularity (advisory) — the flow analog of the diagram fan-out band ────────────────
# The RULE (one use case = one actor goal) lives in method.md; these are its teeth. Kept apart from
# `_check_flows` so `lint-fragment` can surface them WITHOUT failing a fragment (an authoring agent
# may legitimately return a long flow pending the lead's judgment).

FLOW_STEPS_LO = 3     # under this, the flow is likely under-traced (advisory)
FLOW_STEPS_HI = 15    # over this: a fused goal, wire-grain step altitude, or inline shared machinery
_SHARED_RUN_MIN = 4   # contiguous identical (src, dst) hops that count as literal duplication


def _step_hop(st: FlowStep, k: int) -> tuple[object, ...]:
    """One step's identity token for the duplication detector. Two steps are 'identical' only when
    src, dst AND their code grounding (`where` / the referenced sub-flow) all match — endpoint-only
    matching counted "stores the snapshot" and "loads both snapshots" as duplicates (a false positive
    by construction, seen on a live map). An ACTOR step gets a per-step unique token: a sub-flow may
    not contain actor endpoints, so a run through an actor step is unextractable by rule and must
    never be reported (`k` provides the uniqueness)."""
    if not (grammar.is_step_id(st.src) and grammar.is_step_id(st.dst)):
        return ("actor", k)
    return (st.src, st.dst, st.subflow or st.where)


def _shared_runs(hops: list[tuple[str, list[tuple[object, ...]]]]) -> list[tuple[str, str, int, tuple[object, ...]]]:
    """Longest contiguous run of identical hops (see `_step_hop`) for each container pair, reported
    when ≥ `_SHARED_RUN_MIN`: (id_a, id_b, run_length, first_hop). Maps are small (tens of flows ×
    tens of steps), so the per-pair DP is plenty. NOTE this finds LITERAL duplication only — the
    same machinery retold at different depths has non-identical sequences by definition; that case
    is a judgment check on the Phase-4 grounding checklist, not a mechanical one."""
    out: list[tuple[str, str, int, tuple[object, ...]]] = []
    for i in range(len(hops)):
        for j in range(i + 1, len(hops)):
            (ida, a), (idb, b) = hops[i], hops[j]
            best, best_end = 0, 0
            prev = [0] * (len(b) + 1)
            for x in range(1, len(a) + 1):
                cur = [0] * (len(b) + 1)
                for y in range(1, len(b) + 1):
                    if a[x - 1] == b[y - 1] and a[x - 1][0] != "actor":
                        cur[y] = prev[y - 1] + 1
                        if cur[y] > best:
                            best, best_end = cur[y], x
                prev = cur
            if best >= _SHARED_RUN_MIN:
                out.append((ida, idb, best, a[best_end - best]))
    return out


_DUP_PAIR = re.compile(r"\b(UC\d+|SF\d+)\s*(?:&|\+|/|and)\s*(UC\d+|SF\d+)\b")


def _accepted_duplications(m: ProjectModel) -> set[frozenset[str]]:
    """Pairs the operator has durably adjudicated under an 'Accepted duplications' extras heading
    (e.g. "UC4 & UC9: the 4-step UI-kickoff prefix is deliberate, not shared machinery"). The
    machine-readable escape for the duplication advisory — without it, a justified warning re-fires
    at every future validate and no later session can tell 'accepted' from 'never seen'."""
    out: set[frozenset[str]] = set()
    for body in balance_lib.extras_bodies(m, "accepted duplications"):
        for a, b in _DUP_PAIR.findall(body):
            out.add(frozenset((a, b)))
    return out


def _granularity_warnings(m: ProjectModel) -> list[str]:
    """Advisory use-case-granularity signals: the flow-length band (authored steps — a sub-flow
    reference counts as 1, the reward for extracting), the fused-goal name smell, and the
    literal-duplication detector. A flow/sub-flow id recorded under the 'Balance exceptions'
    extras heading is exempt from the band (same escape valve the fan-out rule uses)."""
    warnings: list[str] = []
    excepted = balance_lib._exceptions(m)
    for fid, name, steps in ([(f.uc, f.title, f.steps) for f in m.flows]
                             + [(sf.id, sf.name, sf.steps) for sf in m.subflows]):
        n = len(steps)
        if fid in excepted:
            continue
        if n > FLOW_STEPS_HI:
            warnings.append(
                f"{fid} ({name}): {n} steps — over the ≤{FLOW_STEPS_HI} band. Split a fused goal, "
                "compress step altitude, extract shared machinery into a sub-flow, or record the "
                "exception under a 'Balance exceptions' extras heading")
        elif n < FLOW_STEPS_LO:  # includes n == 0: an empty flow/sub-flow is a silent no-op everywhere
            warnings.append(f"{fid} ({name}): only {n} step(s) — under the ≥{FLOW_STEPS_LO} band; "
                            "is the flow traced to its outcome?")
    for eid, name in ([(u.id, u.name) for u in m.use_cases]
                      + [(sf.id, sf.name) for sf in m.subflows]):
        if " and " in name.lower():
            warnings.append(f"{eid} name '{name}' joins two clauses with 'and' — two goals in one? "
                            "Split it, rename it, or ignore knowingly")
    accepted = _accepted_duplications(m)
    hops = ([(f.uc, [_step_hop(st, k) for k, st in enumerate(f.steps)]) for f in m.flows]
            + [(sf.id, [_step_hop(st, k) for k, st in enumerate(sf.steps)]) for sf in m.subflows])
    for ida, idb, run, first in _shared_runs(hops):
        if frozenset((ida, idb)) in accepted:
            continue  # adjudicated by the operator — recorded in the map, so it stays quiet
        warnings.append(f"{ida} and {idb} share a run of {run} identical steps (starting "
                        f"{first[0]} → {first[1]}) — literal duplication; extract a sub-flow, or "
                        f"record '{ida} & {idb}: <why>' under an 'Accepted duplications' extras heading")
    return warnings


# ── use-case & Happy-Path completeness (advisory) — the front-door verification's teeth ──────────
# The RULE (cross-check the use-case list against the REAL entry surface, both directions; the
# Happy Path involves all relevant actors and NOTES the use cases left off) lives in method.md;
# these are its teeth. Whole-map signals — they relate T4 ↔ flows ↔ HP ↔ roles — so they run in
# `validate` ONLY, never `lint-fragment` (a T4 harvest fragment has entry points but no flows; a
# trace fragment has one flow and no entry points — per-fragment the signal is vacuous or a
# guaranteed false positive).

def external_entry_points(m: ProjectModel) -> list[EntryPoint]:
    """The T4 rows whose EFFECTIVE activation is external (`grammar.effective_activation` — the
    authored value when valid, else inferred from `kind`): the front-door surface the use-case
    list must account for. Self-activated rows (crons, workers, consumers) are the automatic
    internal/ops cut — nobody outside asks, so no use case has to claim them."""
    return [ep for ep in m.entry_points
            if grammar.effective_activation(ep.activation, ep.kind) == "external"]


def flow_endpoint_ids(m: ProjectModel) -> set[str]:
    """Every element id appearing as a step endpoint in any flow, sub-flow references expanded
    (`model.expanded_flow_steps`) — what the traced use cases actually touch."""
    out: set[str] = set()
    for f in m.flows:
        for st in expanded_flow_steps(m, f):
            for end in (st.src, st.dst):
                if grammar.is_step_id(end):
                    out.add(end)
    return out


def flow_touched_entities(m: ProjectModel) -> set[str]:
    """Entity ids appearing as a step endpoint in any flow (sub-flows expanded) — the entities
    with real flow-derived 'Used in UC' traceability. Shared by the no-entity-in-any-flow canary
    and the eval profile, so the two can never diverge."""
    return {end for end in flow_endpoint_ids(m) if end.startswith("E")}


def unclaimed_external_entry_points(m: ProjectModel) -> list[EntryPoint]:
    """Externally-activated entry points whose owning component appears as an endpoint in NO
    flow — each is a missing use case or a dead surface. Empty when the map has no flows yet
    (additivity: an untraced map is 'not yet traced', not 'all unclaimed'). Rows whose component
    is empty (its own advisory) or dangling (the blocking reference check owns those) are
    skipped. Shared by the validate advisory and the eval profile — one implementation."""
    if not m.flows:
        return []
    claimed = flow_endpoint_ids(m)
    comp_ids = {c.id for c in m.components}
    return [ep for ep in external_entry_points(m)
            if (comp := ep.component.strip()) and comp in comp_ids and comp not in claimed]


def unclaimed_surface_components(m: ProjectModel) -> list[tuple[str, list[EntryPoint]]]:
    """Components with externally-activated entry points no use-case flow reaches, MINUS the ones
    already adjudicated (a `Cn` recorded under an 'Unclaimed surfaces' heading) or folded under a
    recorded 'Coverage exceptions' dir — i.e. the surfaces that would still WARN. Shared by the
    completeness warning and `validate --emit-unclaimed`, which prints this same set as a ready
    extras block so the lead adjudicates ~a hundred surfaces at once instead of hand-typing them."""
    if not (m.entry_points and m.flows):
        return []
    accepted = _recorded_ids(m, "unclaimed surfaces", ("C",))
    cov_dirs = _recorded_coverage_dirs(m)  # a 'Coverage exceptions' dir also silences its components
    comp_dir: dict[str, str] = {}
    for c in m.components:
        if c.source:
            rel = strip_anchor(c.source).rstrip("/")
            comp_dir[c.id] = rel.rsplit("/", 1)[0] if "/" in rel else rel
    by_comp: dict[str, list[EntryPoint]] = {}
    for ep in unclaimed_external_entry_points(m):
        by_comp.setdefault(ep.component.strip(), []).append(ep)
    out: list[tuple[str, list[EntryPoint]]] = []
    for cid, eps in sorted(by_comp.items()):
        if cid in accepted:
            continue  # adjudicated by the operator — recorded in the map, so it stays quiet
        if cov_dirs and cid in comp_dir and _under_recorded(comp_dir[cid], cov_dirs):
            continue  # the owning component sits under a recorded 'Coverage exceptions' dir
        out.append((cid, eps))
    return out


# A recorded-exception line under one of the completeness headings names its subject id at the
# LINE START (optionally after a list bullet / bold marker) FOLLOWED BY A SEPARATOR — canonical
# form "C713: ops/debug routes — deliberate"; "UC15 (its name) — why" is tolerated (a live map
# wrote its record that way). One id per line. Deliberately stricter than balance_lib._exceptions'
# anywhere-in-body scan: these bodies carry multi-paragraph prose that names OTHER ids mid-sentence
# — an id mentioned in an explanation, or a prose sentence merely STARTING with an id and running
# on with no separator ("C9 handles this"), must not silently pre-exempt that element.
_RECORD_LINE = re.compile(r"^\s*(?:[-*]\s+)?\**\s*((?:UC|R|C)\d+)\**\s*[:(—–-]")


def _recorded_ids(m: ProjectModel, heading: str, prefixes: tuple[str, ...]) -> set[str]:
    """Ids adjudicated under a machine-read extras heading, read from line-leading tokens only."""
    out: set[str] = set()
    for body in balance_lib.extras_bodies(m, heading):
        for line in body.splitlines():
            hit = _RECORD_LINE.match(line)
            if hit and hit.group(1).startswith(prefixes):
                out.add(hit.group(1))
    return out


# A recorded coverage-exception line names a repo-relative DIRECTORY at the line start followed by a
# separator — "mee6/plugins/: coarse whole-monorepo altitude". Line-leading + separator, one per line
# (the same discipline as `_RECORD_LINE`), so prose naming another path mid-sentence can't pre-exempt it.
_COVERAGE_DIR_LINE = re.compile(r"^\s*(?:[-*]\s+)?\**\s*([\w./\-]+?)/?\**\s*[:(—–-]")


def _recorded_coverage_dirs(m: ProjectModel) -> set[str]:
    """Repo-relative directory prefixes recorded under a **'Coverage exceptions'** extras heading — the
    operator's conscious "this area is folded at a coarse altitude" decision. Silences the
    `--check-coverage` compression / absent-dir / no-entity-card warnings AND the unclaimed-surface
    completeness warning for anything AT OR UNDER the path (boundary-aware — `plugins` never silences
    `plugins-legacy`). Scoped by directory, so a real gap in an UNLISTED dir still warns; the trailing
    slash is normalized off so it matches the slash-less repo-relative dir keys the coverage walk uses."""
    out: set[str] = set()
    for body in balance_lib.extras_bodies(m, "coverage exceptions"):
        for line in body.splitlines():
            hit = _COVERAGE_DIR_LINE.match(line)
            if hit and (p := hit.group(1).strip().rstrip("/")):
                out.add(p)
    return out


def _under_recorded(path: str, dirs: frozenset[str] | set[str]) -> bool:
    """`path` (repo-relative, no trailing slash) is at or under one of the recorded dirs, on a path
    BOUNDARY (`covered_under`'s rule) — `plugins` matches `plugins` and `plugins/x`, never `plugins-legacy`."""
    return any(path == d or path.startswith(d + "/") for d in dirs)


def _clip(text: str, n: int = 60) -> str:
    """Trigger text is free prose — clip it so one row can't flood the warning report."""
    text = " ".join(text.split())
    return text if len(text) <= n else text[:n].rstrip() + "…"


def _completeness_warnings(m: ProjectModel) -> list[str]:
    """Advisory use-case & Happy-Path completeness signals (see the family comment above):

      * an externally-activated T4 entry point whose owning component no flow reaches, grouped per
        component (the remedy — trace a use case through it, or adjudicate — is per component);
        escape = the C id recorded under an **'Unclaimed surfaces'** extras heading;
      * an external entry point owned by no component at all (unclaimable by construction);
      * a use case with no T6 flow — a phantom capability (stale docs) or a missing trace;
      * NO entity in any flow step (map-wide canary): the domain model then has zero flow-derived
        'Used in UC' traceability — the method prescribes authoring each flow's CENTRAL entity
        touches as C→E steps; escape = the literal `entity-flows` under 'Balance exceptions';
      * an entity step no backbone edge backs (a C+E step pair, matched undirected, with no C→E
        edge): the step claims entity use the aggregate layer doesn't — add the edge or fix the
        step (no escape: both remedies are cheap and unambiguous);
      * a role that drives no use case and appears in no flow — a dead role;
      * a role with no ON-SPINE use case, and an off-spine use case left unrecorded — both
        adjudicated under a **'Happy Path coverage'** extras heading (the escape IS the record the
        Happy-Path Coverage rule already demands).

    All guards keep a partial map silent (no flows / no HP yet); during a parallel build's trace
    phase the surviving warnings drain as traces land."""
    warnings: list[str] = []
    if m.entry_points and m.flows:
        comp_name = {c.id: c.name for c in m.components}
        for cid, eps in unclaimed_surface_components(m):
            shown = "; ".join(f"[{ep.kind}] {_clip(ep.trigger)}" for ep in eps)
            warnings.append(
                f"{cid} ({comp_name.get(cid, cid)}): {len(eps)} externally-activated entry "
                f"point(s) unclaimed by any use case ({shown}) — a missing use case or a dead "
                f"surface; trace a use case through {cid}, or record '{cid}: <why>' under an "
                "'Unclaimed surfaces' extras heading")
        for i, ep in enumerate(m.entry_points):
            if (grammar.effective_activation(ep.activation, ep.kind) == "external"
                    and not ep.component.strip()):
                warnings.append(
                    f"entry_points[{i}] [{ep.kind}] {_clip(ep.trigger)}: externally activated but "
                    "owned by no component — name its owning C id so the entry-surface coverage "
                    "check can relate it to a use case")
    if m.flows:
        with_flow = {f.uc for f in m.flows}
        for u in m.use_cases:
            if u.id not in with_flow:
                warnings.append(f"{u.id} ({u.name}) has no T6 flow — a phantom capability "
                                "(stale docs?) or a missing trace; trace it or drop it")
    # The no-entity canary: a whole deliverable (the domain model's flow-derived 'Used in UC'
    # view) can otherwise go missing with every gate green — a live rebuild shipped exactly that.
    if (m.flows and m.entities and not flow_touched_entities(m)
            and "entity-flows" not in balance_lib._exceptions(m)):
        warnings.append(
            "No flow step touches any entity — the domain model has no flow-derived 'Used in UC' "
            "traceability, and an entity-code change can't reach a use case in impact. Author "
            "each flow's central entity touches as C→E steps (method.md, T6 entity steps), or "
            "record the literal `entity-flows` under a 'Balance exceptions' extras heading")
    # An entity step must ride a C→E backbone edge (the edge = the aggregate claim, the step =
    # this scenario's instance). `assemble` now DERIVES these edges from the step, so a surviving
    # warning here means the step reached validate without being assembled (a partial / hand-built
    # map), or the derivation was declined — still worth surfacing.
    for prefix, st, _c, _e in unbacked_entity_steps(m):
        warnings.append(
            f"{prefix} {st.n}: {st.src} → {st.dst} claims entity use the backbone "
            "doesn't — add the C→E edge (direct use only), or fix the step")
    if m.use_cases and m.roles and m.flows:  # flows gate the dead-role call too: a mid-flow-only
        # role (an approver, a notified party) is only visible once tracing has begun — judging it
        # "dead" before any flow exists would be a guaranteed pre-trace false positive
        driving = {a for u in m.use_cases for a in u.actors}
        step_actors: set[str] = set()
        for f in m.flows:
            for st in expanded_flow_steps(m, f):
                for end in (st.src, st.dst):
                    if grammar.is_role_id(end):
                        step_actors.add(end)
        for r in m.roles:
            if r.id not in driving and r.id not in step_actors:
                warnings.append(f"{r.id} ({r.name}) drives no use case and appears in no flow — "
                                "a dead role (stale docs?), or its use case is missing")
    if m.happy_path:
        recorded = _recorded_ids(m, "happy path coverage", ("R", "UC"))
        on_spine = {g.uc for g in m.happy_path if g.uc}
        for r in m.roles:
            driven = {u.id for u in m.use_cases if r.id in u.actors}
            if driven and not driven & on_spine and r.id not in recorded:
                warnings.append(
                    f"{r.id} ({r.name}) drives no on-spine use case — the Happy Path involves all "
                    "relevant actors: give one of its use cases a spine step, or record "
                    f"'{r.id}: <why>' under a 'Happy Path coverage' extras heading")
        for u in m.use_cases:
            if u.id not in on_spine and u.id not in recorded:
                warnings.append(
                    f"{u.id} ({u.name}) is off the Happy-Path spine and unrecorded — the Coverage "
                    f"rule NOTES the use cases left off: record '{u.id}: <why>' under a "
                    "'Happy Path coverage' extras heading (or give it a spine step)")
    return warnings


def _check_roles(m: ProjectModel) -> list[str]:
    if m.roles and all(not r.kind.strip() for r in m.roles):
        return ["Roles carry no Kind (human/service) — every role states one"]
    return []


def _check_actors(m: ProjectModel) -> list[str]:
    """Loud guard (the anti-silent-no-op): when roles are defined, EVERY use case must name at least one
    actor (a role id). Otherwise `check_actor_attribution` has nothing to compare and silently passes —
    the exact failure the role-id model exists to prevent. A roles-less map legitimately has no actors."""
    if not m.roles:
        return []
    missing = [u.id for u in m.use_cases if not u.actors]
    if not missing:
        return []
    return [f"Use cases with no actor (roles are defined, so each names ≥1 role id): {', '.join(missing)}"]


def _check_actor_kinds(m: ProjectModel) -> list[str]:
    """Advisory: a use case that pairs a HUMAN actor with a SERVICE actor. An actor is who the use case
    is FOR (has the goal); a service listed alongside a human is almost always the internal machinery
    that merely relays the human's action inward — a gateway, a shard / gateway connection, an event
    dispatcher, a worker. That belongs in the FLOW as a component, not in the actor list (it clutters
    every happy-path row the use case drives with a phantom co-actor). One use case, one actor: keep
    the human, model the delivery in the steps. Genuinely-interchangeable initiators are same-kind, so
    a human+service mix is the reliable tell — same-kind multi-actor lists (admin OR moderator) pass."""
    kind = {r.id: (r.kind or "").strip().lower() for r in m.roles}
    name = {r.id: r.name for r in m.roles}
    out: list[str] = []
    for u in m.use_cases:
        humans = [a for a in u.actors if kind.get(a) == "human"]
        services = [a for a in u.actors if kind.get(a) == "service"]
        if humans and services:
            h = ", ".join(f"{a} ({name.get(a, a)})" for a in humans)
            s = ", ".join(f"{a} ({name.get(a, a)})" for a in services)
            out.append(f"{u.id} ({u.name}) mixes a human actor [{h}] with a service actor [{s}] — an "
                       "actor is who the use case is FOR; a service beside a human is usually the "
                       "internal delivery mechanism (gateway/shard/dispatcher/worker). Model it as a "
                       "flow component and keep the one human actor (or, if truly a distinct external "
                       "initiator, leave it).")
    return out


def _check_dep_kinds(m: ProjectModel) -> list[str]:
    return [f"{d.id} has an invalid dependency Kind '{d.kind}' — use one of: "
            f"{', '.join(grammar.DEP_KINDS)}"
            for d in m.deps if d.kind and d.kind.strip().lower() not in grammar.DEP_KINDS]


def _check_dep_buckets(m: ProjectModel) -> tuple[list[str], list[str]]:
    """Purpose-bucket hygiene — the deterministic half of keeping the seeded-open vocabulary from
    drifting (the fuzzy half, synonym detection, lives in the method prompt, not here). All findings
    are ADVISORY: a diagram (external systems OR libraries, counted separately since they render as
    two diagrams) with more than the cap of distinct buckets — a proliferation nudge, NOT a gate,
    because an integration-heavy product legitimately spans many purposes; an authored bucket that is
    neither a seed nor the catch-all (a minted synonym worth a second look); and an over-long label. A
    missing bucket is silent — the heuristic groups it and the method prompts it."""
    problems: list[str] = []
    warnings: list[str] = []
    ext: set[str] = set()
    lib: set[str] = set()
    counts: dict[str, int] = {}    # resolved bucket -> dep count (to spot a bloated catch-all)
    minted: dict[str, bool] = {}   # distinct minted (non-seed) bucket -> is_library (one nudge each, not per dep)
    for d in m.deps:
        is_lib = grammar.classify_dep(d.kind or "", d.type) in grammar.DEP_KINDS_FOLDED
        seeds = grammar.DEP_BUCKET_SEEDS_LIBRARY if is_lib else grammar.DEP_BUCKET_SEEDS_EXTERNAL
        catchall = grammar.DEP_BUCKET_CATCHALL_LIBRARY if is_lib else grammar.DEP_BUCKET_CATCHALL_EXTERNAL
        resolved = grammar.resolve_bucket(is_lib, d.bucket, d.type, d.used_for)
        (lib if is_lib else ext).add(resolved)
        counts[resolved] = counts.get(resolved, 0) + 1
        authored = (d.bucket or "").strip()
        if not authored:
            continue
        if len(authored) > 40:
            warnings.append(f"{d.id} bucket '{authored}' is long (>40 chars) — keep it a short "
                            "purpose label, not a sentence.")
        canon = grammar.canonical_bucket(authored)
        if canon not in seeds and canon != catchall:
            minted.setdefault(canon, is_lib)
    # Minting nudge — asymmetric by design. LIBRARY vocabulary is fairly closed, so a minted lib bucket
    # is likely a synonym of a seed (nudge to fold). EXTERNAL purposes are open-ended and product-
    # specific (Payments, Social, Blockchain…), so minting one is EXPECTED, not a smell — the only
    # concern is spelling stability across rebuilds. Treating them the same is what pushed a fresh
    # build to dump 35 services into the 'Integrations' catch-all rather than split by purpose.
    for bucket, is_lib in minted.items():
        if is_lib:
            warnings.append(f"Library bucket '{bucket}' is minted (not a seed) — a synonym of a seed? "
                            f"Reuse the exact spelling on rebuild (seeds: "
                            f"{', '.join(grammar.DEP_BUCKET_SEEDS_LIBRARY)}).")
        else:
            warnings.append(f"External bucket '{bucket}' is minted (not a seed) — fine if it's a real "
                            f"product purpose (splitting the '{grammar.DEP_BUCKET_CATCHALL_EXTERNAL}' "
                            f"catch-all this way is encouraged); reuse the exact spelling on rebuild.")
    # Bloated catch-all — the mirror of the proliferation cap. The catch-all is the "no specific
    # purpose" bucket, so a large one is guaranteed heterogeneous: real sub-purposes are hiding in it.
    for label, catchall in (("external systems", grammar.DEP_BUCKET_CATCHALL_EXTERNAL),
                            ("libraries", grammar.DEP_BUCKET_CATCHALL_LIBRARY)):
        n = counts.get(catchall, 0)
        if n > grammar.DEP_BUCKET_CATCHALL_SPLIT_AT:
            warnings.append(f"The '{catchall}' catch-all among {label} holds {n} deps — it is the "
                            "'no specific purpose' fallback, so a large one means real purposes are "
                            "hiding in it. Split by sub-purpose (e.g. Payments, Social, Blockchain, "
                            "Content) — mint a short purpose name per group (the seed list is a floor, "
                            "not a ceiling).")
    for label, buckets in (("external systems", ext), ("libraries", lib)):
        if len(buckets) > grammar.DEP_BUCKET_CAP:
            warnings.append(f"Many purpose buckets among {label}: {len(buckets)} > soft cap "
                            f"{grammar.DEP_BUCKET_CAP} ({', '.join(sorted(buckets))}) — check for "
                            "near-duplicates to merge (fine if the product genuinely spans this many).")
    return problems, warnings


def _check_activations(m: ProjectModel) -> list[str]:
    """`activation` is a closed vocabulary (`grammar.ACTIVATIONS`; the JSON schema publishes the
    enum) — EXACT match, deliberately stricter than the folded dep-Kind check: every consumer
    routes through `grammar.effective_activation`, where a near-miss ('External', 'mounted') is
    truthy-but-unknown and would silently fall back to the kind heuristic — a misspelled 'external'
    could silently reclassify an entry point (an invalid value shipped on a live map this way)."""
    return [f"entry_points[{i}] ({ep.kind}): invalid activation '{ep.activation}' — use one of: "
            f"{', '.join(grammar.ACTIVATIONS)}, or leave it empty to infer from `kind`"
            for i, ep in enumerate(m.entry_points)
            if ep.activation and ep.activation not in grammar.ACTIVATIONS]


def _check_runs_in(m: ProjectModel) -> list[str]:
    """`runs_in` (on components and self-started entry points) is the Deployment-view link to a
    deployment unit. It must name a REAL unit, and unit names must be unique so a value resolves
    unambiguously. Free-text unit names are not element ids, so this can't ride `_check_references`.
    Blocking: a dangling `runs_in` is a broken view reference; a duplicate unit name is ambiguous."""
    problems: list[str] = []
    counts: dict[str, int] = {}
    for d in m.deployment:
        counts[d.unit] = counts.get(d.unit, 0) + 1
    dups = sorted(u for u, n in counts.items() if n > 1)
    if dups:
        problems.append(f"Duplicate deployment unit name(s): {', '.join(dups)} — unit names must be "
                        "unique so a `runs_in` value resolves to exactly one unit")
    valid = set(counts)
    for c in m.components:
        bad = [u for u in c.runs_in if u not in valid]
        if bad:
            problems.append(f"{c.id} runs_in names unknown deployment unit(s): {', '.join(bad)} — "
                            "each must match a `deployment[].unit` name")
    for i, ep in enumerate(m.entry_points):
        bad = [u for u in ep.runs_in if u not in valid]
        if bad:
            problems.append(f"entry_points[{i}] runs_in names unknown deployment unit(s): "
                            f"{', '.join(bad)} — each must match a `deployment[].unit` name")
    return problems


def _check_environments(m: ProjectModel) -> list[str]:
    """Each `deployment[].variants` value must name a declared `environments` entry (the same
    resolve-or-die rule `_check_runs_in` applies to `runs_in`→unit). Blocking: a variant that names no
    declared environment is a broken view reference (and a variant set with NO `environments` declared
    at all is an inconsistency — you cannot gate a unit to an environment you never named). Silent when
    the project uses no environments AND no unit tags a variant (the axis is un-adopted, not a gap)."""
    valid = set(m.environments)
    problems: list[str] = []
    for i, d in enumerate(m.deployment):
        bad = [v for v in d.variants if v not in valid]
        if bad:
            problems.append(f"deployment[{i}] ('{d.unit}') variants name undeclared environment(s): "
                            f"{', '.join(bad)} — each must match a `environments` entry"
                            + ("" if valid else " (and no `environments` are declared)"))
    return problems


def _deployment_placement_warnings(m: ProjectModel) -> list[str]:
    """Advisory: once the map USES `runs_in` (the Deployment view is in play), a self-activated entry
    point with no host unit — neither its own `runs_in` nor its component's — is invisible in that view.
    Surface it (the same no-silent-no-op spirit as the completeness canaries), don't drop it. Silent
    when the map has no deployment units, or when `runs_in` is nowhere used yet (un-adopted, not a gap)."""
    if not m.deployment:
        return []
    used = any(c.runs_in for c in m.components) or any(ep.runs_in for ep in m.entry_points)
    if not used:
        return []
    comp_units = {c.id: set(c.runs_in) for c in m.components}
    unplaced: list[str] = []
    for i, ep in enumerate(m.entry_points):
        if grammar.effective_activation(ep.activation, ep.kind) != "self":
            continue
        if set(ep.runs_in) or comp_units.get(ep.component.strip()):
            continue
        unplaced.append(f"entry_points[{i}] [{ep.kind}] {_clip(ep.trigger)}")
    if not unplaced:
        return []
    shown = ", ".join(unplaced[:8]) + (f", +{len(unplaced) - 8} more" if len(unplaced) > 8 else "")
    return [f"{len(unplaced)} self-started entry point(s) have no deployment unit and will be "
            f"'Unplaced' in the Deployment view — tag `runs_in` on them or their component: {shown}"]


def _deployment_unlinked_warning(m: ProjectModel) -> list[str]:
    """Advisory: deployment units were harvested but NOTHING links code to them — every component's
    and entry point's `runs_in` is empty. The Deployment view then renders with zero code↔process
    mapping (its whole point). `_deployment_placement_warnings` stays silent on this case ('un-adopted,
    not a gap'), so without this canary a build ships an empty Deployment view with no signal at all —
    exactly what happened on both fresh builds this check was added for. Fires only when units exist:
    no `deployment[]` means the dimension was legitimately not harvested (a different, coarser choice)."""
    if not m.deployment:
        return []
    if any(c.runs_in for c in m.components) or any(ep.runs_in for ep in m.entry_points):
        return []
    if "runs-in" in balance_lib._exceptions(m):
        return []  # deliberately unmapped (e.g. everything runs in one unit) — recorded, so quiet
    return [f"{len(m.deployment)} deployment unit(s) enumerated but no component or entry point sets "
            f"`runs_in` — the Deployment view will have no code↔process mapping. On each component, "
            f"name the deployment unit(s) whose process runs it (method.md 'Deployment & topology'); "
            f"`runs` edges are then derived. If the code truly runs as one unit, record the literal "
            f"`runs-in` under a 'Balance exceptions' extras heading to silence this."]


def _deployment_quality_warnings(m: ProjectModel) -> list[str]:
    """Advisory: the Deployment view is only trustworthy if `runs_in` was GROUNDED (read off the deploy
    manifests), not formula-guessed. `validate` used to check only PRESENCE, so a hand-script that
    blanket-tagged every component to one unit (no manifest read, 0 entry points placed) passed clean.
    These four canaries catch the low-quality shapes — all in the deployment family, so the one recorded
    `runs-in` literal silences them together (like `_deployment_unlinked_warning`):

    - non-atomic unit NAME (S5): a `deployment[].unit` holding a separator — one row is one process;
    - formula-fill (S3): one unit blankets EVERY component AND another unit hosts nothing AND no entry
      point carries `runs_in` — the exact co-occurrence a per-id-range guess leaves (a real all-in-one
      app trips none of the other two, so a legit monolith never nags);
    - unlinked unit: a unit hosting no component/entry point whose name matches no system dep;
    - ambiguous thread host: a self-started entry point whose component runs in >1 unit but which sets
      no `runs_in` of its own — the view then picks a host arbitrarily."""
    if not m.deployment:
        return []
    if "runs-in" in balance_lib._exceptions(m):
        return []                              # deliberately unmapped / justified — silence the family
    warnings: list[str] = []
    if m.environments and not any(d.variants for d in m.deployment):
        warnings.append(f"{len(m.environments)} environment(s) declared but no deployment unit is tagged "
                        f"with a `variants` value — the Deployment view can't split by environment "
                        f"(every unit shows in all). Tag each unit with the environment(s) it runs in.")
    # a real unit name may contain spaces ('api worker'); only a SEPARATOR (shared with the dep-match
    # guard) signals two units crammed into one row (S5)
    non_atomic = [d.unit for d in m.deployment
                  if d.unit and not grammar.is_atomic_unit_name(d.unit)]
    if non_atomic:
        warnings.append(f"Deployment unit name(s) look non-atomic (contain a separator): "
                        f"{', '.join(non_atomic)} — a unit is ONE process; split each '<a> / <b>' into "
                        f"separate `deployment[]` rows so a `runs_in` value resolves to exactly one host.")
    used = any(c.runs_in for c in m.components) or any(ep.runs_in for ep in m.entry_points)
    if not used:
        return warnings                        # fully un-adopted → `_deployment_unlinked_warning` owns it
    comp_units = {c.id: set(c.runs_in) for c in m.components}
    hosted: set[str] = set()
    for c in m.components:
        hosted.update(c.runs_in)
    for ep in m.entry_points:
        hosted.update(ep.runs_in)
    dep_names = [d.name for d in m.deps
                 if grammar.classify_dep(d.kind or "", d.type) in grammar.DEP_KINDS_SYSTEM]
    orphan_units = sorted({d.unit for d in m.deployment if d.unit and d.unit not in hosted
                           and not any(grammar.unit_name_matches_dep(d.unit, dn) for dn in dep_names)})
    if orphan_units:
        warnings.append(f"Deployment unit(s) run no traced component or entry point and match no known "
                        f"system dependency: {', '.join(orphan_units)} — is each infra (add it as a "
                        f"dependency), or an un-traced `runs_in` (tag the component/entry point that runs "
                        f"there)?")
    # Formula-fill smell: every component crammed into ONE unit with NO real spread, while a REAL
    # (non-infra) process unit sits empty and no entry point is placed. Two guards keep a legitimately
    # grounded map quiet: (a) an empty INFRA unit (mongo/redis) is EXPECTED — it hosts no code by
    # nature — so only an empty NON-infra unit counts as the smell (mirrors `orphan_units`); (b) if a
    # component also runs in another non-infra unit (a real backend/frontend split, or a dual all-in-one
    # + split deployment), that IS grounding, not a formula — stay silent.
    infra_units = {d.unit for d in m.deployment
                   if d.unit and any(grammar.unit_name_matches_dep(d.unit, dn) for dn in dep_names)}
    comp_unit_sets = [set(c.runs_in) for c in m.components]
    blanket = next(iter(set.intersection(*comp_unit_sets)), None) if comp_unit_sets else None
    ep_placed = any(ep.runs_in for ep in m.entry_points)
    spread = any(u != blanket and u not in infra_units for cs in comp_unit_sets for u in cs)
    empty_real_unit = any(d.unit and d.unit not in hosted and d.unit not in infra_units
                          for d in m.deployment)
    if blanket and not ep_placed and not spread and empty_real_unit:
        warnings.append(f"`runs_in` looks formula-filled, not grounded: every component is tagged to one "
                        f"unit ('{blanket}') while another real (non-infra) unit hosts nothing and no "
                        f"entry point carries `runs_in`. A per-component manifest read (docker-compose / "
                        f"Dockerfiles / Procfile) would spread components across their real processes and "
                        f"place the background threads — re-derive `runs_in` from the manifests "
                        f"(method.md), or record `runs-in` under 'Balance exceptions' if it truly runs as "
                        f"one unit.")
    ambiguous: list[str] = []
    for i, ep in enumerate(m.entry_points):
        if grammar.effective_activation(ep.activation, ep.kind) != "self":
            continue
        if set(ep.runs_in):
            continue                            # precise host already set → unambiguous
        if len(comp_units.get(ep.component.strip(), set())) > 1:
            ambiguous.append(f"entry_points[{i}] [{ep.kind}] {_clip(ep.trigger)}")
    if ambiguous:
        shown = ", ".join(ambiguous[:8]) + (f", +{len(ambiguous) - 8} more" if len(ambiguous) > 8 else "")
        warnings.append(f"{len(ambiguous)} self-started entry point(s) whose owning component runs in >1 "
                        f"unit but which set no `runs_in` — the host process is ambiguous (the view picks "
                        f"one). Set `runs_in` on the entry point to pin its exact process: {shown}")
    return warnings


def unbacked_entity_steps(m: ProjectModel) -> list[tuple[str, FlowStep, str, str]]:
    """C↔E flow steps whose entity touch NO backbone edge carries — returns
    `(container_label, step, c_id, e_id)`. The edge is C→E regardless of the step's authored
    direction (a return-direction `E → C` step still means 'this component uses this entity'), so
    the endpoints are resolved by prefix, not by position. Matched UNDIRECTED so an `E → C` step
    rides the same edge; C↔C pairs stay unchecked. Empty when no edges exist yet (a pre-edge-trace
    partial is 'not yet traced', not 'unbacked'). Shared by `validate` (warns — author the edge) and
    `assemble` (derives it — the step IS the evidence, so at scale a forgotten edge self-heals)."""
    if not m.edges:
        return []
    edge_pairs = {frozenset((e.src, e.dst)) for e in m.edges}
    containers = ([(f"{f.uc} flow step", f.steps) for f in m.flows]
                  + [(f"{sf.id} step", sf.steps) for sf in m.subflows])
    out: list[tuple[str, FlowStep, str, str]] = []
    for label, steps in containers:
        for st in steps:
            if st.subflow:
                continue  # a reference step grounds through the sub-flow's own steps
            if not (grammar.is_step_id(st.src) and grammar.is_step_id(st.dst)):
                continue  # an actor step — a Role DISPLAY NAME ("End user") may start with E/C,
                # so kinds are only read off endpoints known to be element ids
            kinds = {"E" if end.startswith("E") else
                     "C" if end.startswith("C") else "?" for end in (st.src, st.dst)}
            if kinds == {"C", "E"} and frozenset((st.src, st.dst)) not in edge_pairs:
                c_id = st.src if st.src.startswith("C") else st.dst
                e_id = st.dst if st.dst.startswith("E") else st.src
                out.append((label, st, c_id, e_id))
    return out


def _check_edges(m: ProjectModel) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    for e in m.edges:
        if not e.verb.strip():
            problems.append(f"Edge {e.src} → {e.dst} has an empty Verb")
        has_where = bool(e.where)                          # a PRESENT-but-malformed `where` (incl. a
        if not has_where and not e.no_call_site:           # whitespace-only one) is owned by the anchor-
                                                           # format gate; here we own only the ABSENT case
            problems.append(
                f"{e.src} → {e.dst}: no `Where` anchor — add a bare `path:line` EXAMPLE call site where "
                f"{e.src} invokes {e.dst} (the witness grounding this edge), or set `no_call_site` if this "
                "relationship has no code call site (event-driven / shared-state / config-wired coupling)")
        elif has_where and e.no_call_site:
            warnings.append(f"{e.src} → {e.dst}: `no_call_site` is set but a `Where` is present — "
                            "drop one so the intent is unambiguous")
    # Duplicate backbone edges: `assemble` collapses same-call-site duplicates (identical anchor), so
    # any (src,verb,dst) left here more than once points at DIFFERENT call sites (or is a no-call-site
    # pair) — a real conflict (which call site is the true one? a duplicate once masked a wrong
    # anchor). Flag for the lead to pick the primary site and move the other rationales to the T6 flow
    # steps; a warning (non-blocking) so the map still renders.
    triples: dict[tuple[str, str, str], int] = {}
    for e in m.edges:
        triples[(e.src, e.verb, e.dst)] = triples.get((e.src, e.verb, e.dst), 0) + 1
    for (s, v, d), n in triples.items():
        if n > 1:
            warnings.append(f"{s} → {d}: the '{v}' edge is declared {n} times with differing call "
                            "sites — keep the primary one, move the other rationales to the T6 flow "
                            "steps (or set `no_call_site` if the coupling truly has no single site)")
    return problems, warnings


def check_domain_relations(entities: list[Entity]) -> tuple[list[str], list[str]]:
    """Per-relation problems + warnings for a set of domain cards: verb alias, half-cardinality,
    duplicate relation, and the `keyed_by` rules (empty entry / names a real field / redundant with a
    backing FK), plus the field-less-association nudge. Shared by `_check_domain_cards` (the whole map)
    and `lint-fragment` (one fragment) so a `keyed_by` misuse is caught in the AUTHORING agent's own
    turn, not only at the lead's `validate` — a fix lands once. Operates on whatever entities it is
    given: a relation whose target lives in another fragment simply skips the target-side field checks
    (the `r.target in backing` guard). The whole-map-only checks — entity completeness and the
    'declared on both cards' direction rule — stay in `_check_domain_cards`."""
    problems: list[str] = []
    warnings: list[str] = []
    backing = {e.id: [(f.name, f.type, grammar.fk_targets(f.markers)) for f in e.fields]
               for e in entities}
    field_names = {eid: {n for n, _t, _fk in flds} for eid, flds in backing.items()}
    for e in entities:
        seen_pairs: set[tuple[str, str]] = set()
        for r in e.relations:
            if r.verb.lower() in grammar.REL_ALIAS:
                problems.append(f"Domain card {e.id}: relation verb '{r.verb}' is a non-canonical "
                                f"alias — use '{grammar.REL_ALIAS[r.verb.lower()]}'")
            if (r.src_card is None) != (r.dst_card is None):
                problems.append(f"Domain card {e.id}: relation '{r.verb} … {r.target}' has a "
                                f"half-stated cardinality — state both sides (`sc→dc`) or neither")
            if (r.verb, r.target) in seen_pairs:
                problems.append(f"Domain card {e.id} declares the relation "
                                f"'{r.verb} … {r.target}' twice")
            seen_pairs.add((r.verb, r.target))
            # resolve the backing field(s) ONCE — reused by the keyed_by XOR rule and the
            # field-less-association nudge below (either side: forward source field or reverse FK).
            back_names: list[str] = []
            if r.target in backing:
                back_names, _side = grammar.resolve_backing(e.id, r.target, backing[e.id],
                                                            backing[r.target])
            if r.keyed_by:
                if any(not k.strip() for k in r.keyed_by):
                    problems.append(f"Domain card {e.id}: relation '{r.verb} … {r.target}' has an "
                                    f"empty `keyed_by` entry")
                # keyed_by is for a key that is NOT a field on either row. If it NAMES a declared field
                # (source or target) it is really a (reverse) foreign key — mark the field, don't key
                # it. This catches the unmarked by-name FK the XOR rule (FK-marked only) misses.
                clash = sorted({k for k in r.keyed_by
                                if k in field_names.get(e.id, set())
                                or k in field_names.get(r.target, set())})
                if clash:
                    problems.append(
                        f"Domain card {e.id}: relation '{r.verb} … {r.target}' keys on "
                        f"{', '.join(clash)}, which is a declared field — that's a foreign key; mark "
                        f"the field `FK→{r.target}` (or `FK→{e.id}` on {r.target}), not `keyed_by`. "
                        f"(If it is an unrelated key that only shares the name, rename the key.)")
                elif back_names:
                    problems.append(
                        f"Domain card {e.id}: relation '{r.verb} … {r.target}' declares `keyed_by` "
                        f"but a real field ({', '.join(back_names)}) already backs it — a storage "
                        f"key is for FIELD-LESS relations only; drop one")
            kind = grammar.REL_KIND.get(r.verb.lower(), "association")
            # a keyed_by storage key counts as "explained" exactly like a {how} note, so the nudge
            # doesn't false-fire once the key moves out of the free-text note into keyed_by.
            if (kind == "association" and r.target in backing and not r.how and not r.keyed_by
                    and not back_names):
                warnings.append(
                    f"Domain card {e.id}: relation '{r.verb} … {r.target}' is not backed by a "
                    f"field and has no {{…}} note — mark the implementing field `FK→{r.target}` "
                    f"(or `FK→{e.id}` on {r.target}), or add a `{{how}}` note explaining the link")
            elif (kind == "association" and r.target in backing and not back_names
                    and not r.keyed_by):
                # HEURISTIC: a field-less association whose note/label NAMES a source field is likely
                # a by-name foreign key dodging the marker via prose (the role→RoleDefinition class).
                # A warning only (scans free text). The `r.target in backing` + `not back_names` guard
                # keeps it from firing on an entity-TYPED field whose target sits in another fragment.
                note = f"{r.display} {r.how or ''}"
                named = sorted({n for n in field_names.get(e.id, set())
                                if re.search(rf"\b{re.escape(n)}\b", note)})
                if named:
                    warnings.append(
                        f"Domain card {e.id}: relation '{r.verb} … {r.target}' is field-less but its "
                        f"note/label names the field(s) {', '.join(named)} — if that field references "
                        f"{r.target}, mark it `FK→{r.target}` for a grounded arrow, not a prose note")
    return problems, warnings


def _check_domain_cards(m: ProjectModel) -> tuple[list[str], list[str]]:
    problems, warnings = check_domain_relations(m.entities)
    directed: set[tuple[str, str]] = set()
    for e in m.entities:
        if not e.meaning:
            problems.append(f"Domain card {e.id} is missing a MEANING line")
        if not e.source:
            problems.append(f"Domain card {e.id} is missing a SOURCE link")
        if not e.fields:
            problems.append(f"Domain card {e.id} has no FIELDS")
        for f in e.fields:
            if not f.type:
                problems.append(f"Domain card {e.id} field '{f.name}' has no type")
        for r in e.relations:
            directed.add((e.id, r.target))
    for a, b in directed:
        if a < b and (b, a) in directed:
            problems.append(f"Relation between {a} and {b} is declared on both cards — author it "
                            f"on one side only")
    return problems, warnings


# The canonical anchor shapes live in one place now — `coyodex.anchors` (method/model.md's 'Anchor
# formats'): a repo-relative file ref with an optional `:line`/`:line-line` (extension optional, so
# `Dockerfile:1` is valid), or a bare directory ref (`_DIR_ANCHOR`) additionally valid for `source`.


def _check_anchor_format(m: ProjectModel) -> list[str]:
    """Every source-location field matches the one shape it's required to have."""
    problems: list[str] = []

    def bad_file(label: str, val: str | None) -> None:
        if val and not _ANCHOR_LINE.match(val):
            problems.append(f"{label}: '{val}' is not a valid `path:line` anchor")

    def bad_anchor(label: str, val: str | None) -> None:  # a file OR a directory
        if val and not (_ANCHOR_LINE.match(val) or _DIR_ANCHOR.match(val)):
            problems.append(f"{label}: '{val}' is not a valid anchor (bare `path:line` or `path/`)")

    for c in m.components:
        bad_anchor(f"{c.id} source", c.source)
        bad_file(f"{c.id} entry_point", c.entry_point)
    for d in m.deps:
        bad_file(f"{d.id} where_configured", d.where_configured)
    for el in (*m.components, *m.deps):                     # evidence citations are file:line anchors too
        for i, ev in enumerate(el.evidence):
            bad_file(f"{el.id} evidence[{i}].file", ev.file)
    for e in m.edges:
        bad_file(f"{e.src} → {e.dst} where", e.where)
    for f in m.flows:
        for st in f.steps:
            bad_file(f"{f.uc} flow step {st.n} where", st.where)
    for sf in m.subflows:
        for st in sf.steps:
            bad_file(f"{sf.id} step {st.n} where", st.where)
    for ep in m.entry_points:
        bad_file(f"entry_points[{ep.component} {ep.kind}].source", ep.source)
    for e in m.entities:
        bad_anchor(f"{e.id} source", e.source)
    for g in m.glossary:
        bad_anchor(f"glossary '{g.term}' source", g.source)
    for group in (*m.subsystems, *m.subdomains):
        bad_anchor(f"{group.id} source", group.source)
    # Operational-table source fields that the viewer turns into code links — same bare-anchor rule as
    # every other source (the deployment/observability location fields stay free prose, so they are NOT
    # checked here: they describe topology, not a single line, and the viewer renders them as text).
    for i, r in enumerate(m.run_commands):
        bad_file(f"run_commands[{i}].source", r.source)
    for i, s in enumerate(m.security):
        bad_file(f"security[{i}].source", s.source)
    for t in m.non_entity_types:
        bad_anchor(f"non_entity_types '{t.name}' source", t.source)
    # Test-completeness rows cite exercising suites as {file, why} — `file` is a bare anchor (a
    # `path:line` OR a `path/` test dir), so the viewer renders it as a clickable code link.
    for i, tr in enumerate(m.tests):
        for j, ev in enumerate(tr.tests):
            bad_anchor(f"tests[{i}].tests[{j}].file", ev.file)
    return problems


# `extra` is freeform by design — but the moment a key's shape is enforced (below) or the method
# names it as a convention, it has already become a de facto field, so it graduates to a real one
# instead of staying a "standardized" extra column. These are the promoted names' old spellings —
# authoring any of them under `extra` is a mistake, not a valid alternative spelling.
_PROMOTED_EXTRA_KEYS = {
    "files": "files", "files_count": "files", "members": "files",
    "evidence": "evidence",
    "package": "package", "sdk": "package", "client_library": "package",
    "alternative": "alternative", "standalone_alternative": "alternative",
}
_FORBIDDEN_EXTRA_KEYS = {"loc"}  # mechanical (line count) — compute it, don't hand-author it
_DEPLOYMENT_FLAVORED_EXTRA_KEYS = {
    "flags", "modes", "scaling", "sticky_sessions", "mode", "api_key", "noop_without", "wired_by",
}


def _check_extra_conventions(m: ProjectModel) -> tuple[list[str], list[str]]:
    """`extra` may only hold what the method has no opinion about — see the module constants above
    for the promoted/forbidden/advisory key lists."""
    problems: list[str] = []
    warnings: list[str] = []
    for el in (*m.components, *m.deps):
        for key in el.extra:
            if key in _PROMOTED_EXTRA_KEYS:
                problems.append(f"{el.id} extra.{key}: retired — use the top-level "
                                f"`{_PROMOTED_EXTRA_KEYS[key]}` field instead")
            elif key in _FORBIDDEN_EXTRA_KEYS:
                problems.append(f"{el.id} extra.{key}: not hand-authored — compute it, don't author it")
            elif key in _DEPLOYMENT_FLAVORED_EXTRA_KEYS:
                warnings.append(f"{el.id} extra.{key}: looks like deployment/config info — check "
                                f"whether it belongs in the Deployment or Config table instead")
    return problems, warnings


def _check_evidence(m: ProjectModel) -> list[str]:
    """`evidence[].file` is a bare `path:line` anchor (method/model.md's 'Anchor formats');
    `evidence[].why` must be a real explanation, not left blank."""
    problems: list[str] = []
    for el in (*m.components, *m.deps):
        for i, ev in enumerate(el.evidence):
            if not _ANCHOR_LINE.match(ev.file):
                problems.append(f"{el.id} evidence[{i}].file: '{ev.file}' is not a valid "
                                f"`path:line` anchor")
            if not ev.why.strip():
                problems.append(f"{el.id} evidence[{i}].why: must be a non-empty explanation")
    return problems


def _check_altitude(m: ProjectModel) -> list[str]:
    out: list[str] = []
    excepted = balance_lib._exceptions(m)  # a C id recorded under 'Balance exceptions' is adjudicated
    for c in m.components:
        if c.id in excepted:  # the honest escape — rewording the Purpose to dodge the heuristic isn't
            continue
        n = sum(1 for s in (seg.strip() for seg in c.purpose.split(",")) if _LIST_ITEM.match(s))
        if n >= _ALTITUDE_MIN:
            out.append(f"Component {c.id} lists {n} sub-units in its Purpose — if these are real "
                       f"units, consider promoting {c.id} to a subsystem (its members then get "
                       f"their own drill level), or record '{c.id}: <why>' under a "
                       "'Balance exceptions' extras heading")
    return out


def _anchor_pairs(m: ProjectModel) -> list[tuple[str, str]]:
    """(label, href) for every drill-to-code anchor: each edge's `Where`, each element definition's
    first link (plus the canonical `anchor`), each card's SOURCE. Off-repo URLs excluded. Used by
    the opt-in `--check-sources` existence check — shape validity is `_check_anchor_format`'s job,
    not this collector's."""
    url = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)
    out: list[tuple[str, str]] = []
    for e in m.edges:
        href = _where_href(e.where or "")
        if href:
            out.append((f"{e.src} → {e.dst} `Where`", href))
    for f in m.flows:
        for st in f.steps:
            href = _where_href(st.where or "")
            if href:
                out.append((f"{f.uc} flow step {st.n} `where`", href))
    for sf in m.subflows:
        for st in sf.steps:
            href = _where_href(st.where or "")
            if href:
                out.append((f"{sf.id} step {st.n} `where`", href))
    for u in m.use_cases:
        href = _first_link_of(u, [u.name, u.trigger_outcome])  # actors are role ids now, not a link cell
        if href and not url.match(href):
            out.append((u.id, href))
    for group in (*m.subsystems, *m.subdomains):
        if group.source and not url.match(group.source):
            out.append((f"{group.id} source", group.source))
    for c in m.components:
        if c.source and not url.match(c.source):
            out.append((f"{c.id} source", c.source))
        href = c.entry_point or _first_link_of(c, [c.purpose, c.depends_on,
                                  *(v for v in c.extra.values() if isinstance(v, str))])
        if href and not url.match(href):
            out.append((c.id, href))
    for d in m.deps:
        href = d.where_configured or _first_link_of(d, [d.name, d.type, d.used_for,
                                  *(v for v in d.extra.values() if isinstance(v, str))])
        if href and not url.match(href):
            out.append((d.id, href))
    for e in m.entities:
        if e.source and not url.match(e.source):
            out.append((e.id, e.source))
    for g in m.glossary:
        if g.source and not url.match(g.source):
            out.append((f"glossary '{g.term}'", g.source))
    for ep in m.entry_points:
        if ep.source and not url.match(ep.source):
            out.append((f"entry_points[{ep.component} {ep.kind}]", ep.source))
    for s in m.security:
        # the Auth-check anchor is an L2 grounding claim — verify the enforcement site exists.
        # The canonical `security[].source` is a bare `path:line` (like Entity.source), so take the
        # raw source; a legacy markdown-link source is still honored via `_first_link_of`.
        href = _first_link_of(s, [s.source]) or (s.source or None)
        if href and not url.match(href):
            out.append((f"security '{s.surface}'", href))
    return out


def check_anchor_existence_model(m: ProjectModel, roots: list[Path]) -> list[str]:
    out: list[str] = []
    for label, href in _anchor_pairs(m):
        rel = strip_anchor(href)
        is_dir = rel.endswith("/")
        rel = rel.rstrip("/")
        if not rel:
            continue
        ok = any((r / rel).is_dir() if is_dir else (r / rel).is_file() for r in roots)
        if not ok:
            out.append(f"{label}: '{href}' does not resolve to a "
                       f"{'directory' if is_dir else 'file'} in the repo")
    return out


def check_entity_sources_model(m: ProjectModel, roots: list[Path]) -> list[str]:
    """Each entity's name must appear in its SOURCE file — the anti-synthesized-entity gate, a
    lenient token-substring match against the file's text."""
    problems: list[str] = []
    for e in m.entities:
        if not e.source or e.name == e.id:
            continue
        src = _resolve_source_file(e.source, roots)
        if src is None:
            continue
        try:
            code = src.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        tokens = re.findall(r"[A-Za-z_]\w{2,}", e.name)
        if tokens and not any(tok.lower() in code for tok in tokens):
            rel = strip_anchor(e.source)
            problems.append(f"Domain card {e.id} '{e.name}' is not defined in its SOURCE ({rel}) — "
                            f"likely synthesized or a wrong anchor; entities must be real named types")
    return problems


def referenced_paths(m: ProjectModel, root: Path) -> set[str]:
    """Repo-relative paths the model points at, extracted from every stored string (link targets +
    inline paths), kept only when they exist. The model-native analog of the retired markdown
    reader's per-map referenced-paths scan."""
    cands: set[str] = set()
    for s in _strings(m):
        cands.update(_REF_LINK.findall(s))
        cands.update(_REF_INLINE.findall(s))
    rootstr = str(root)
    refs: set[str] = set()
    for c in cands:
        c = strip_anchor(c.strip())
        if c.startswith("file://"):
            c = c[7:]
        if c.startswith(rootstr):
            c = c[len(rootstr):]
        c = c.strip("/")
        if c and not c.startswith(".coyodex") and (root / c).exists():
            refs.add(c)
    return refs


def check_domain_coverage_model(m: ProjectModel, roots: list[Path],
                                skip_dirs: frozenset[str] = frozenset()) -> list[str]:
    """The under-harvest advisory, ported: (a) relation-isolated entities (model-only), (b) named
    Python types in the entities' source dirs with no entity card (stdlib `ast` re-measurement).
    v2 refinement: a type explicitly listed in `non_entity_types` is excluded by NAME — the model's
    plumbing marker — with the v1 suffix/base heuristic kept as the fallback."""
    if not m.entities:
        return []
    out: list[str] = []
    related: set[str] = set()
    for e in m.entities:
        for r in e.relations:
            related.add(e.id)
            related.add(r.target)
    ids = [e.id for e in m.entities]
    isolated = [i for i in ids if i not in related]
    n = len(ids)
    if (n >= _ISOLATED_MIN_ENTITIES and len(isolated) >= _ISOLATED_MIN
            and len(isolated) > _ISOLATED_FRACTION * n):
        out.append(
            f"Isolated entities: {len(isolated)} of {n} entity cards have NO E↔E relation "
            f"({round(100 * len(isolated) / n)}% of the domain model) — a sparse class graph is the "
            f"signature of an under-harvested domain model (did one T5 harvest agent author "
            f"per-entity RELATIONS?): {', '.join(isolated[:_COVERAGE_SAMPLE])}"
            + (f", +{len(isolated) - _COVERAGE_SAMPLE} more" if len(isolated) > _COVERAGE_SAMPLE else "")
        )
    domain_dirs: dict[Path, str] = {}       # absolute source dir → its repo-relative path
    for e in m.entities:
        if e.source:
            src = _resolve_source_file(e.source, roots)
            if src is not None:
                rel_file = strip_anchor(e.source)
                domain_dirs[src.parent] = rel_file.rsplit("/", 1)[0] if "/" in rel_file else ""
    marked = {t.name for t in m.non_entity_types}
    types: dict[str, Path] = {}
    for d, rel_dir in sorted(domain_dirs.items()):
        if skip_dirs and _under_recorded(rel_dir, skip_dirs):
            continue  # a recorded 'Coverage exceptions' dir: drop its types from BOTH uncovered AND
            # the `N of M` denominator, so a fully-recorded dir can't mask an un-recorded one
        for f in sorted(d.glob("*.py")):
            try:
                tree = parse_python(f.read_text(encoding="utf-8", errors="ignore"), str(f))
            except (OSError, SyntaxError, ValueError):
                continue
            for node in tree.body:
                if (isinstance(node, ast.ClassDef) and node.name not in marked
                        and not _is_non_entity_type(node)):
                    types.setdefault(node.name, f)
    if types:
        entity_names = [e.name for e in m.entities if e.name != e.id]
        uncovered = sorted(t for t in types if not _type_covered(t, entity_names))
        if len(uncovered) >= _UNCOVERED_MIN and len(uncovered) >= _UNCOVERED_FRACTION * len(types):
            shown = ", ".join(uncovered[:_COVERAGE_SAMPLE]) + (
                f", +{len(uncovered) - _COVERAGE_SAMPLE} more"
                if len(uncovered) > _COVERAGE_SAMPLE else "")
            out.append(
                f"Under-harvested domain model: {len(uncovered)} of {len(types)} named types in the "
                f"entities' source dirs have no entity card (possible under-harvested domain model; "
                f"Python types only, measured at validate time): {shown}"
            )
    return out


def _check_view_fresh(m: ProjectModel, model_path: Path) -> list[str]:
    """The committed markdown view must equal the regenerated one — it is a generated artifact
    (maintainer decision: the view IS committed for readable diffs, so staleness must be visible)."""
    from coyodex.views import model_to_markdown
    view = model_path.with_name("project-map.md")
    if not view.exists():
        return [f"generated markdown view missing next to the model — write it with "
                f"`coyodex render {model_path.name} {view.name}`"]
    if view.read_text(encoding="utf-8") != model_to_markdown(m):
        return [f"{view.name} differs from the view generated from {model_path.name} — it is a "
                f"GENERATED file (stale, or hand-edited); regenerate with `coyodex render`"]
    return []


# ── orchestration ────────────────────────────────────────────────────────────────────────────────

def validate_model(m: ProjectModel, model_path: Path | None = None, *,
                   check_sources: bool = False, check_coverage: bool = False,
                   repo_root: Path | None = None) -> tuple[list[str], list[str]]:
    """Every semantic check over a structurally-valid model; returns (problems, warnings) exactly
    like the v1 validator did, so the profiler and the CLI share one orchestration."""
    if (check_sources or check_coverage) and model_path is None and repo_root is None:
        raise ValueError("model_path or repo_root is required when check_sources/check_coverage is set")
    problems: list[str] = []
    warnings: list[str] = []
    defined = set(all_elements(m)) | {g.id for g in m.happy_path}

    problems.extend(_check_ids(m))
    problems.extend(_check_references(m))
    problems.extend(_check_hp(m))
    flow_problems, flow_warnings = _check_flows(m)
    problems.extend(flow_problems)
    warnings.extend(flow_warnings)
    warnings.extend(_granularity_warnings(m))
    warnings.extend(_completeness_warnings(m))
    problems.extend(_check_roles(m))
    problems.extend(_check_actors(m))
    warnings.extend(_check_actor_kinds(m))
    problems.extend(_check_dep_kinds(m))
    dep_bucket_problems, dep_bucket_warnings = _check_dep_buckets(m)
    problems.extend(dep_bucket_problems)
    warnings.extend(dep_bucket_warnings)
    problems.extend(_check_activations(m))
    problems.extend(_check_runs_in(m))
    problems.extend(_check_environments(m))
    warnings.extend(_deployment_placement_warnings(m))
    warnings.extend(_deployment_unlinked_warning(m))
    warnings.extend(_deployment_quality_warnings(m))
    edge_problems, edge_warnings = _check_edges(m)
    problems.extend(edge_problems)
    warnings.extend(edge_warnings)
    card_problems, card_warnings = _check_domain_cards(m)
    problems.extend(card_problems)
    warnings.extend(card_warnings)
    problems.extend(_check_anchor_format(m))
    problems.extend(_check_evidence(m))
    extra_problems, extra_warnings = _check_extra_conventions(m)
    problems.extend(extra_problems)
    warnings.extend(extra_warnings)

    roots = _source_roots(model_path, repo_root) if model_path is not None else (
        [repo_root.resolve()] if repo_root is not None else [])
    if check_sources:
        problems.extend(check_entity_sources_model(m, roots))
        # A nonexistent-file anchor means a wrong repo-root prefix or a stale path reached the map — a
        # real error, not a nudge. Blocking (B3) so `validate --check-sources` is the deterministic
        # backstop for the source-side prefix rule (a missing file can never slip through all-green).
        problems.extend(check_anchor_existence_model(m, roots))

    parents = _parents(m)
    hier_problems, hier_warnings = check_hierarchy(parents, defined)
    problems.extend(hier_problems)
    warnings.extend(hier_warnings)
    warnings.extend(_check_altitude(m))
    if check_coverage:
        cov_dirs = frozenset(_recorded_coverage_dirs(m))  # 'Coverage exceptions': conscious coarse-fold
        walk_root = repo_root if repo_root is not None else (
            model_path.resolve().parent.parent if model_path is not None else None)
        if walk_root is not None:
            refs = referenced_paths(m, walk_root.resolve())
            warnings.extend(compression_coverage_from_refs(refs, walk_root, cov_dirs))
            # File-level coverage: the loose-file slice-seam gap the directory-granular check above
            # misses (a component-less .py inside an otherwise-covered dir). Same refs + recorded dirs.
            warnings.extend(file_level_coverage(refs, walk_root.resolve(), cov_dirs))
            # The granularity anchor: component (leaf) count vs the code-derived expectation E —
            # re-computed from the tree here (GR4), advisory-only, silent inside the ±40% band.
            # The literal `granularity` under 'Balance exceptions' records the operator's conscious
            # altitude decision and silences this (else a justified overshoot nags every validate).
            if "granularity" not in balance_lib._exceptions(m):
                warnings.extend(granularity_advisory(len(m.components), walk_root))
        warnings.extend(check_domain_coverage_model(m, roots, cov_dirs))

    # Redundant nesting (a group whose only child is a group of the same kind).
    child_count: dict[str, int] = {}
    only_child: dict[str, str] = {}
    for c, p in parents.items():
        child_count[p] = child_count.get(p, 0) + 1
        only_child[p] = c
    redundant = sorted(
        p for p, n in child_count.items() if n == 1
        and ((_is_subsystem_id(p) and _is_subsystem_id(only_child[p]))
             or (p.startswith("SD") and only_child[p].startswith("SD")))
    )
    if redundant:
        warnings.append("Groups whose only child is another group of the same kind (redundant "
                        f"nesting level): {', '.join(redundant)}")

    # Diagram balance (advisory, never blocking): per-diagram fan-out vs the 5±2 target —
    # sparse roots, over-dense screens, single-child wrapper levels. Model-only, so always on.
    warnings.extend(balance_lib.balance_warnings(m))

    # Grouping guards + nudges (unchanged semantics from v1).
    comp_ids = {c.id for c in m.components}
    if m.subsystems and comp_ids and not any(c.subsystem for c in m.components):
        problems.append("Subsystems (S) defined but no component is assigned to one — every "
                        "component's `subsystem` is empty")
    assigned_s = {c.subsystem for c in m.components if c.subsystem}
    if assigned_s:
        parent_s = {s.parent for s in m.subsystems if s.parent}
        empty_s = sorted(s.id for s in m.subsystems
                         if s.id not in assigned_s and s.id not in parent_s)
        if empty_s:
            warnings.append("Subsystems with no members (empty box — no component assigned, no "
                            f"child subsystem): {', '.join(empty_s)}")
    if m.subdomains and m.entities and not any(e.subdomain for e in m.entities):
        problems.append("Subdomains (SD) defined but no entity is assigned to one — every entity's "
                        "`subdomain` is empty")
    if m.subdomains and any(e.subdomain for e in m.entities):
        ungrouped = sorted(e.id for e in m.entities if not e.subdomain)
        if ungrouped:
            warnings.append(f"Entities with no SUBDOMAIN (ungrouped / top-level): "
                            f"{', '.join(ungrouped)}")
    assigned_sd = {e.subdomain for e in m.entities if e.subdomain}
    parent_sd = {sd.parent for sd in m.subdomains if sd.parent}
    empty_sd = sorted(sd.id for sd in m.subdomains
                      if sd.id not in assigned_sd and sd.id not in parent_sd)
    if empty_sd:
        warnings.append(f"Subdomains with no entities: {', '.join(empty_sd)}")

    # Ownership + orphan-dep nudges over the backbone.
    owned = {e.dst for e in m.edges
             if e.src.startswith("C") and e.dst.startswith("E") and e.verb.lower() in _WRITE_VERBS}
    if owned and m.entities:
        embedded = {r.target for ent in m.entities for r in ent.relations
                    if grammar.REL_KIND.get(r.verb.lower()) in ("composition", "aggregation")}
        unowned = sorted(e.id for e in m.entities if e.id not in owned and e.id not in embedded)
        if unowned:
            shown = ", ".join(unowned[:12]) + (f", +{len(unowned) - 12} more"
                                               if len(unowned) > 12 else "")
            warnings.append(f"Entities with no owning component (no persists/writes C→E edge): {shown}")
    if m.edges:
        targets = {e.dst for e in m.edges}
        # v2: a dep marked deployment_linked has no code call site BY DECLARATION — the nudge must
        # not pressure anyone to invent an edge for it (the audit→Elastic false-edge class).
        # v3: in-process libraries/frameworks (FastAPI/uvicorn/motor/pydantic…) correctly fold into the
        # Libraries box and per method must NOT get invented edges — skip the folded kinds, so only
        # system deps (datastore/messaging/service/platform) nudge for a missing call site.
        orphan_deps = sorted(d.id for d in m.deps
                             if d.id not in targets and not d.deployment_linked
                             and grammar.classify_dep(d.kind or "", d.type) not in grammar.DEP_KINDS_FOLDED)
        if orphan_deps:
            shown = ", ".join(orphan_deps[:12]) + (f", +{len(orphan_deps) - 12} more"
                                                   if len(orphan_deps) > 12 else "")
            warnings.append(f"External deps with no incoming edge (un-traced — which component "
                            f"uses each?): {shown}")
        # The mirror nudge: a dep marked `deployment_linked` (declares NO code call site) that is
        # nonetheless an edge target has a real call site — the marker is wrong (a harvest agent
        # over-marked it). Drop the marker (or, if the edge is `no_call_site`, drop that edge).
        mislabeled = sorted(d.id for d in m.deps if d.deployment_linked and d.id in targets)
        if mislabeled:
            shown = ", ".join(mislabeled[:12]) + (f", +{len(mislabeled) - 12} more"
                                                  if len(mislabeled) > 12 else "")
            warnings.append(f"Deps marked `deployment_linked` but which are a code call target "
                            f"(they have a real call site — drop the marker, or drop the edge if it "
                            f"is `no_call_site`): {shown}")

    if model_path is not None:
        warnings.extend(_check_view_fresh(m, model_path))
    return problems, warnings


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────

def _inventory(m: ProjectModel) -> str:
    counts = {"UC": len(m.use_cases), "HP": len(m.happy_path), "S": len(m.subsystems),
              "C": len(m.components), "D": len(m.deps), "SD": len(m.subdomains),
              "E": len(m.entities)}
    return ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()) if v)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex validate [--check-sources] [--check-coverage] [--repo <root>] "
              "[--emit-unclaimed] [.coyodex/project-map.json]\n\n"
              "Validate a model: structural schema validation, then the semantic\n"
              "checks (IDs resolve, hierarchy sound, cards complete, view fresh, …).\n"
              "--emit-unclaimed: print a ready-to-paste 'Unclaimed surfaces' extras block for every\n"
              "  externally-activated entry point no use case reaches (adjudicate the wall at once).")
        return 0

    repo_root: Path | None = None
    if "--repo" in argv:
        i = argv.index("--repo")
        if i + 1 >= len(argv):
            print("ERROR: --repo needs a path (the analyzed repo's root)", file=sys.stderr)
            return 2
        repo_root = Path(argv[i + 1])
        del argv[i:i + 2]
        if not repo_root.is_dir():
            print(f"ERROR: --repo {repo_root} is not a directory", file=sys.stderr)
            return 2
    check_sources = "--check-sources" in argv
    check_coverage = "--check-coverage" in argv
    emit_unclaimed = "--emit-unclaimed" in argv
    unknown = [a for a in argv if a.startswith("-")
               and a not in ("--check-sources", "--check-coverage", "--emit-unclaimed")]
    if unknown:
        print(f"ERROR: unknown option(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    args = [a for a in argv if not a.startswith("-")]
    path = Path(args[0] if args else ".coyodex/project-map.json")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    try:
        m = load_model(path.read_text(encoding="utf-8"))
    except ModelError as e:
        print("\nVALIDATION FAILED (schema):")
        print(f"  - {e}")
        return 1
    if emit_unclaimed:
        rows = unclaimed_surface_components(m)
        if not rows:
            print("# No unclaimed external surfaces — nothing to record.")
            return 0
        comp_name = {c.id: c.name for c in m.components}
        print("Unclaimed surfaces")
        print("<!-- paste under an 'Unclaimed surfaces' extras heading; replace each <why> "
              "(dead surface / dev-only / missing use case) or trace a use case instead -->")
        for cid, eps in rows:
            triggers = "; ".join(f"[{ep.kind}] {_clip(ep.trigger)}" for ep in eps)
            print(f"- {cid} ({comp_name.get(cid, cid)}): <why>   # {triggers}")
        return 0
    problems, warnings = validate_model(m, path, check_sources=check_sources,
                                        check_coverage=check_coverage, repo_root=repo_root)
    print(f"Inventory — {_inventory(m)}")
    if warnings:
        print("\nVALIDATION WARNINGS (non-blocking):")
        for w in warnings:
            print(f"  - {w}")
    if problems:
        print("\nVALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Schema OK — structure valid, all IDs defined once, all references resolve, every HP "
          "step names a use case, every flow step well-formed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
