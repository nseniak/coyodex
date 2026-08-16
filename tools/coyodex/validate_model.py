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
import json
import re
import sys
from collections.abc import Callable, Container, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from coyodex import balance_lib, records, grammar
from coyodex.audit_model import l2_worklist_model
from coyodex.reporting import clip as _clip, reset_full_lists, set_full_lists, shown as _shown
from coyodex.anchors import (
    DIR_ANCHOR as _DIR_ANCHOR,
    FILE_ANCHOR as _ANCHOR_LINE,
    FILE_LINE_ANCHOR,
    non_operative_reason,
    parse_anchor,
    strip_anchor,
)
from coyodex.impact_git import Extents, load_map_extents
from coyodex.impact_lib import enclosing_extent
from coyodex.pysrc import parse_python
from coyodex.model import (
    ID_ARRAYS,
    ID_SHAPE,
    BusinessRule,
    access_rules,
    Dep,
    Entity,
    EntryPoint,
    FlowStep,
    Grounding,
    MessagingRow,
    ModelError,
    ProjectModel,
    RuleSite,
    UseCase,
    all_elements,
    expanded_flow_steps,
    expanded_steps_with_container,
    group_forests,
    load_model,
)
from coyodex.validate_analysis import (
    _ALTITUDE_MIN,
    _COVERAGE_SAMPLE,
    _ISOLATED_FRACTION,
    _ISOLATED_MIN,
    _ISOLATED_MIN_ENTITIES,
    _LIST_ITEM,
    _REF_BARE,
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
    ignore_disclosure,
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
    """child id -> parent id, across all FOUR forests (C→S, S→S, SD→SD, E→SD, UC→CAP, CAP→CAP,
    BR→BLK, BLK→BLK) — single-source, on the child.

    The capability arms were missing when capabilities shipped, and everything downstream of this
    map went with them: an undefined `capability`, an undefined capability `parent` and a CYCLE in
    the capability forest were all accepted in silence, while the exact same mistakes are blocking
    on the other two forests. That is the worst direction for this particular field — a typo'd
    capability turns the Happy-Path coverage check OFF for that use case rather than failing loudly."""
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
    for cap in m.capabilities:
        if cap.parent:
            out[cap.id] = cap.parent
    for u in m.use_cases:
        if u.capability:
            out[u.id] = u.capability
    for blk in m.blocks:
        if blk.parent:
            out[blk.id] = blk.parent
    for br in m.rules:
        if br.block:
            out[br.id] = br.block
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


#: A CONTAINER id — a subsystem or a subdomain. Containers group other elements; they are not
#: themselves an end of a relationship, which is why they may never appear as an edge endpoint.
#: Written against the exact id shape (not a prefix test) so a `SD`-prefixed word in free text can
#: never reach it, and so `SF` (sub-flow) stays out.
_CONTAINER_ID = re.compile(r"^(?:S|SD)\d+$")


def _is_container_id(i: str) -> bool:
    return bool(_CONTAINER_ID.fullmatch((i or "").strip()))


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
        + [(c.id, "parent", c.parent) for c in m.capabilities]
        + [(u.id, "capability", u.capability) for u in m.use_cases]
        + [(b.id, "parent", b.parent) for b in m.blocks]
        + [(r.id, "block", r.block) for r in m.rules]
        + [(u.id, "entry_points", ep) for u in m.use_cases for ep in u.entry_points]
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
        if u.capability:
            refs.add(u.capability)
        refs.update(u.entry_points)                  # EPn — resolved against the minted T4 ids below
    for cap in m.capabilities:
        if cap.parent:
            refs.add(cap.parent)
    for blk in m.blocks:
        if blk.parent:
            refs.add(blk.parent)
    for br in m.rules:
        if br.block:
            refs.add(br.block)                       # BLKn — a dangling block is a broken forest
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
    for mr in m.messaging:
        if mr.broker:
            refs.add(mr.broker)
        refs.update(mr.publishers)
        refs.update(mr.consumers)
        if mr.payload:
            refs.add(mr.payload)
    for en in m.entities:
        if en.subdomain:
            refs.add(en.subdomain)
        if en.store and en.store.dep:
            refs.add(en.store.dep)                     # the physical datastore dep holding it
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
    # Entry points are not an `ID_ARRAYS` family (their ids are minted by `assemble`, not authored),
    # so they are not in `all_elements` — but a use case's trigger link references them, and a
    # reference that resolves to nothing is the same defect here as anywhere else.
    defined = (set(all_elements(m)) | {g.id for g in m.happy_path}
               | {ep.id for ep in m.entry_points if ep.id})
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
    return problems, warnings


def subflow_refcount_warnings(m: ProjectModel) -> list[str]:
    """Advisory (NON-BLOCKING, and — unlike the rest of the flow rulebook — deliberately NOT
    promoted by `lint_fragment_problems`): a sub-flow's reason to exist is REUSE, so one referenced
    once (or never) is indirection for free. This is judgment-shaped (the roleless-verb precedent):
    riding the blocking fragment channel made one live rebuild inline three legitimate sub-flows,
    duplicate a shared trace, and ship a fragment its author believed had passed. Counts reference
    STEPS (two references inside one flow are still reuse), matching the wording — the old
    'referenced by N flow(s)' text counted steps while saying flows, so lint and validate could
    disagree on the same fragment."""
    ref_counts: dict[str, int] = {}
    for f in m.flows:
        for st in f.steps:
            if st.subflow:
                ref_counts[st.subflow] = ref_counts.get(st.subflow, 0) + 1
    out: list[str] = []
    for sf in m.subflows:
        n_refs = ref_counts.get(sf.id, 0)
        if n_refs < 2:
            out.append(f"{sf.id} ({sf.name}) is referenced {n_refs} time(s) — a sub-flow earns its "
                       "keep at ≥2 references; consider inlining it (advisory: another fragment's "
                       "flow may hold the other reference)")
    return out


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
    literal-duplication detector.

    A flow/sub-flow id recorded under the 'Balance exceptions' extras heading is exempt from the
    WHOLE granularity family — the step band AND the fused-goal name smell (same escape valve the
    fan-out rule uses). That is a deliberate design assertion, not an accident: both signals are
    readings of ONE question about ONE element ("is this one goal, at the right size?"), and an
    operator who has adjudicated the element has adjudicated the question.

    But it IS an assertion, so it is made visible twice over — the same discipline the `runs-in`
    family follows. Each message says what recording the id will silence, and one summary line
    names every (element, signal) pair the recorded ids actually swallowed. On a live map
    `SF20: three steps is the whole session handshake` — a BAND justification — silently removed an
    unrelated `SF20 name … joins two clauses with 'and'`, and nothing on screen said so. The band
    advisory was not even firing there, so a "only when it silenced two" rule would still have shown
    nothing: the visible line therefore reports every suppression, not just the multi-signal ones.
    A silence you cannot see reads exactly like having no findings."""
    warnings: list[str] = []
    excepted = balance_lib._exceptions(m)
    # (element id, short signal name, message) in emission order: bands first, then name smells.
    family: list[tuple[str, str, str]] = []
    for fid, name, steps in ([(f.uc, f.title, f.steps) for f in m.flows]
                             + [(sf.id, sf.name, sf.steps) for sf in m.subflows]):
        n = len(steps)
        if n > FLOW_STEPS_HI:
            family.append((fid, "the step-count band", (
                f"{fid} ({name}): {n} steps — over the ≤{FLOW_STEPS_HI} band. Split a fused goal, "
                "compress step altitude, extract shared machinery into a sub-flow, or record "
                f"'{fid}: <why>' under a 'Balance exceptions' extras heading — which exempts "
                f"{fid} from the WHOLE granularity family, this band AND the fused-goal name smell")))
        elif n < FLOW_STEPS_LO:  # includes n == 0: an empty flow/sub-flow is a silent no-op everywhere
            family.append((fid, "the step-count band", (
                f"{fid} ({name}): only {n} step(s) — under the ≥{FLOW_STEPS_LO} band; is the flow "
                f"traced to its outcome? If it genuinely ends there, record '{fid}: <why>' under a "
                "'Balance exceptions' extras heading — which exempts "
                f"{fid} from the WHOLE granularity family, this band AND the fused-goal name smell")))
    for eid, name in ([(u.id, u.name) for u in m.use_cases]
                      + [(sf.id, sf.name) for sf in m.subflows]):
        if " and " in name.lower():
            family.append((eid, "the fused-goal name smell", (
                f"{eid} name '{name}' joins two clauses with 'and' — two goals in one? Split it, "
                f"rename it, or record '{eid}: <why>' under a 'Balance exceptions' extras heading "
                f"— which exempts {eid} from the WHOLE granularity family, this name smell AND its "
                "step-count band (never reword to dodge the heuristic)")))
    silenced: list[str] = []
    for eid, signal, msg in family:
        if eid in excepted:
            silenced.append(f"{eid} ({signal})")
        else:
            warnings.append(msg)
    if silenced:
        warnings.append(
            f"{len(silenced)} granularity advisory/advisories suppressed by recorded flow/sub-flow "
            f"id(s): {', '.join(silenced)}. A recorded id exempts its element from the WHOLE "
            f"granularity family — the step-count band AND the fused-goal name smell — so a why "
            f"written about one of them silences the other too; if that is not what was meant, "
            f"re-read the rest by validating a copy with the id removed from the 'Balance "
            f"exceptions' extras heading.")
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


def flow_endpoint_ids_by_uc(m: ProjectModel) -> dict[str, set[str]]:
    """Per use case, the element ids its flow touches — sub-flow references expanded
    (`model.expanded_flow_steps`), so machinery hidden behind an `SFn` is never invisible.

    The per-use-case grain is the primitive everything capability-shaped is built from: union it
    over a capability's members and you have that capability's element set; invert it and you have
    how many capabilities touch an element. Use cases with NO flow are absent (not empty) — an
    untraced use case must stay distinguishable from one whose flow touches nothing."""
    out: dict[str, set[str]] = {}
    for f in m.flows:
        if not f.uc:
            continue
        ends = out.setdefault(f.uc, set())
        for st in expanded_flow_steps(m, f):
            for end in (st.src, st.dst):
                if grammar.is_step_id(end):
                    ends.add(end)
    return out


def flow_endpoint_ids(m: ProjectModel) -> set[str]:
    """Every element id appearing as a step endpoint in any flow, sub-flow references expanded
    (`model.expanded_flow_steps`) — what the traced use cases actually touch."""
    out: set[str] = set()
    for ends in flow_endpoint_ids_by_uc(m).values():
        out |= ends
    return out


def flow_touched_entities(m: ProjectModel) -> set[str]:
    """Entity ids appearing as a step endpoint in any flow (sub-flows expanded) — the entities
    with real flow-derived 'Used in UC' traceability. Shared by the no-entity-in-any-flow canary
    and the eval profile, so the two can never diverge."""
    return {end for end in flow_endpoint_ids(m) if end.startswith("E")}


# ── the capability touch primitive (plan/60-capabilities Step 2) ──────────────────────────────────
# ONE implementation, shared by the completeness checks, the viewer transport and the eval profile.
# Scope note: this covers whatever the flows actually touch — components, and entities/deps where
# the trace authored them as steps. An earlier revision restricted it to components, justified by
# "0 of 35 entities are flow endpoints" on the mcpolis fixture; that number measures a fixture
# `validate` itself flags (its own no-entity-in-any-flow canary fires there), not a structural fact.
# This repo's own map has 12 of 74 entities and 9 of 18 deps as flow endpoints.
#
# What this primitive does NOT do: decide that a component is "platform machinery". Measured on the
# reference map, the maximum spread was 4 capabilities of 7, so no threshold separates machinery
# from product, and that classification was dropped rather than tuned. Touch counts answer "which
# capabilities reach this element" and nothing more.

def capability_members(m: ProjectModel) -> dict[str, set[str]]:
    """Per capability, the use cases it holds INCLUDING those of its nested capabilities.

    Capabilities are a forest like subsystems and subdomains, so a parent may hold no use case
    directly and still own everything under it. Reading direct membership only made such a parent
    look empty — its overlay lit nothing, and it counted as 'untraced', which is the one signal that
    is supposed to mean a real part of the product was never walked."""
    kids: dict[str, list[str]] = {}
    for c in m.capabilities:
        if c.parent:
            kids.setdefault(c.parent, []).append(c.id)
    direct: dict[str, set[str]] = {c.id: set() for c in m.capabilities}
    for u in m.use_cases:
        if (cap := (u.capability or "").strip()) in direct:
            direct[cap].add(u.id)

    def walk(cid: str, seen: set[str]) -> set[str]:
        if cid in seen:                      # cycle-safe (a cycle is validate's problem, not ours)
            return set()
        seen = seen | {cid}
        out = set(direct.get(cid, ()))
        for k in kids.get(cid, ()):
            out |= walk(k, seen)
        return out

    return {c.id: walk(c.id, set()) for c in m.capabilities}


def capability_elements(m: ProjectModel) -> dict[str, set[str]]:
    """Per capability, the element ids its use cases' flows touch — its whole subtree's union.
    Every DEFINED capability appears, including one whose use cases are all untraced: that empty
    set is the signal that a real part of the product was never traced, so it must not vanish."""
    by_uc = flow_endpoint_ids_by_uc(m)
    return {cap: {e for uc in ucs for e in by_uc.get(uc, set())}
            for cap, ucs in capability_members(m).items()}


def element_capabilities(m: ProjectModel) -> dict[str, set[str]]:
    """The inverse: per element id, the capabilities whose flows touch it. Absent = touched by no
    capability, which means untraced or reached by no flow — reported as a number, never a warning."""
    out: dict[str, set[str]] = {}
    for cap, ends in capability_elements(m).items():
        for eid in ends:
            out.setdefault(eid, set()).add(cap)
    return out


# ── the business-rule derivation primitive (T7) ───────────────────────────────────────────────────
# ONE implementation. A rule's components, the use-case steps that enforce it and the entities it
# touches are DERIVED from its sites against the rest of the map — nothing about them is authored,
# so nothing about them can be asserted without being computable. Every consumer (the checks, the
# markdown view, the viewer transport, the eval profile) reads THESE functions; a second copy in
# `views.py` or in JS is the drift this repo already pays for, and here it would silently
# re-introduce the hand-assigned data the layer exists to make impossible.
#
# TWO measured facts shape the API and must not be designed away:
#
#   1. `Component.files` IS NOT DISJOINT. On this repo's own map, 5 files are claimed by 2-5
#      components each and hold 71 of its 260 call-site anchors (27%) — all decision-dense. So
#      `site_components` returns a LIST and never picks: ambiguity is data the UI renders, not an
#      error to resolve by taking `[0]`.
#   2. THE STEP JOIN IS WEAK ON BYTE EQUALITY. Measured on the Mio map, only 15% of security-row
#      anchors and 23% of edge anchors are byte-equal to a flow-step anchor, while 57% merely share
#      a file. So the join has two STRENGTHS — byte-equal, and same enclosing symbol — and sharing a
#      file alone is NOT a link. The weak strength needs a symbol table it cannot derive from the
#      model, so it degrades to exact-only rather than silently widening to file equality.

def element_sort_key(eid: str) -> tuple[str, int, str]:
    """Sort key putting `UC2` before `UC10` — element ids are prefix + NUMBER, so plain lexicographic
    order reads them as strings and interleaves the tens with the ones."""
    hit = re.match(r"^([A-Za-z]+)(\d+)$", eid or "")
    return (hit.group(1), int(hit.group(2)), "") if hit else ("", 0, eid or "")


#: How a site reaches a flow step. `exact` = the two anchors are the same string. `symbol` = both
#: lines sit inside the SAME innermost definition (the site enforces the rule inside the function
#: the step names, at a different line). There is deliberately no `file` strength.
STEP_LINK_EXACT = "exact"
STEP_LINK_SYMBOL = "symbol"


@dataclass(frozen=True)
class RuleStepLink:
    """One (use case, step) a rule's site reaches, and how strongly."""
    uc: str                   # the use case whose flow surfaces the step (a sub-flow step reaches
                              # EVERY flow that references it — content inside an SFn is not hidden)
    container: str            # the id that AUTHORED the step: the flow's `uc`, or the `SFn`.
                              # `n` is unique per CONTAINER, never per use case, so this is half the
                              # step's identity — see `model.expanded_steps_with_container`.
    n: int                    # the step's number within that container
    strength: str             # STEP_LINK_EXACT | STEP_LINK_SYMBOL
    site: str                 # the rule site anchor that reached it
    phrase: str = ""          # the step's own action text — display only


def component_file_owners(m: ProjectModel) -> dict[str, list[str]]:
    """repo path -> EVERY component id whose `files` claims it, sorted.

    `Component.files` carries no line ranges and is not required to be disjoint, so this is a
    one-to-many index by construction. Deliberately built from `files` ALONE: a component's
    `source` is where it LIVES (often a directory), and letting a directory prefix claim a site
    would manufacture an owner for a file nobody listed — exactly the "component's home passed off
    as evidence" failure. A map whose components declare no `files` therefore derives nothing, which
    `validate` BLOCKS rather than rendering bare (`check_rules_model`).

    A DIRECTORY entry is dropped rather than trimmed: `files: ["src/"]` normalized to `src` would
    be matched by the shape-legal site anchor `src:12`, manufacturing the very owner the paragraph
    above forbids. A line suffix IS stripped — `files: ["src/v.py:1"]` names one file, and keying it
    verbatim would lose the owner of every site in it."""
    out: dict[str, list[str]] = {}
    for c in m.components:
        for f in c.files:
            raw = (f or "").strip()
            if not raw or raw.endswith("/"):
                continue                       # a directory claims no site (see above)
            path = strip_anchor(raw)
            if path:
                out.setdefault(path, []).append(c.id)
    return {path: sorted(set(ids), key=element_sort_key) for path, ids in out.items()}


def site_components(m: ProjectModel, site: RuleSite,
                    owners: dict[str, list[str]] | None = None) -> list[str]:
    """EVERY component owning the file a site anchors, sorted. Empty = no component claims it.

    Never picks, never falls back, never guesses: a 4-owner file returns all four and the UI shows
    all four. Silently picking one would reproduce the exact failure this layer exists to prevent."""
    if owners is None:
        owners = component_file_owners(m)
    path = strip_anchor((site.where or "").strip())
    return list(owners.get(path, ()))


def rule_components(m: ProjectModel, rule: BusinessRule,
                    owners: dict[str, list[str]] | None = None) -> list[str]:
    """Every component any of a rule's sites lands in, sorted and de-duplicated."""
    if owners is None:
        owners = component_file_owners(m)
    seen: set[str] = set()
    for site in rule.sites:
        seen.update(site_components(m, site, owners))
    return sorted(seen, key=element_sort_key)


def anchored_flow_steps(m: ProjectModel) -> list[tuple[str, str, FlowStep]]:
    """(use case id, authoring container id, step) for every ANCHORED step, sub-flows expanded.

    A sub-flow step appears once per referencing flow, under that flow's use case but keeping its
    OWN container id — the same rule `flow_endpoint_ids_by_uc` follows for reach, so a rule enforced
    inside shared machinery still lands on every use case that rides it, without two steps that
    merely share an `n` collapsing into one."""
    out: list[tuple[str, str, FlowStep]] = []
    for f in m.flows:
        if not f.uc:
            continue
        for container, st in expanded_steps_with_container(m, f):
            if (st.where or "").strip():
                out.append((f.uc, container, st))
    return out


@lru_cache(maxsize=8192)
def _anchor_line(raw: str) -> tuple[str, int | None] | None:
    """(path, start line) of an anchor, or None when it is not a parseable file anchor.

    Memoized: `rule_steps` compares every SITE against every anchored STEP, so a map with 55 rules
    over 165 sites re-parsed the same ~200 anchor strings 57,000 times — 90 ms of the viewer
    transport, nearly all of it one regex. The key space is bounded by the map's distinct anchors."""
    loc = parse_anchor(raw)
    return None if loc is None else (loc.path, loc.lo)


def rule_steps(m: ProjectModel, rule: BusinessRule,
               extents: Extents | None = None,
               steps: list[tuple[str, str, FlowStep]] | None = None) -> list[RuleStepLink]:
    """The use-case steps a rule's sites reach, strongest link per (use case, container, step) first.

    `extents` is the pre-index symbol table (`impact_git.load_map_extents`). WITHOUT it only exact
    links are produced — the honest degradation, since "the same enclosing function" is not
    derivable from the map. Sharing a FILE is never a link: measured, 57% of anchors share a file
    with some step, so a file-level join would light up nearly every row and mean nothing.

    EXACT is same path + same START line, not raw string equality. A site spelled `a.py:22-24`
    names the same operative line as a step at `a.py:22`; deciding link strength on how the author
    punctuated the anchor would make the UI's strongest signal a formatting artifact."""
    if steps is None:
        steps = anchored_flow_steps(m)
    ext = extents or {}
    best: dict[tuple[str, str, int], RuleStepLink] = {}

    def offer(link: RuleStepLink) -> None:
        key = (link.uc, link.container, link.n)
        cur = best.get(key)
        if cur is None or (cur.strength == STEP_LINK_SYMBOL and link.strength == STEP_LINK_EXACT):
            best[key] = link

    for site in rule.sites:
        raw = (site.where or "").strip()
        if not raw:
            continue
        here = _anchor_line(raw)
        if here is None:
            continue
        site_path, site_lo = here
        site_ext = (enclosing_extent(ext.get(site_path, []), site_lo)
                    if site_lo is not None else None)
        for uc, container, st in steps:
            there = _anchor_line((st.where or "").strip())
            if there is None:
                continue
            step_path, step_lo = there
            if (step_path, step_lo) == (site_path, site_lo):
                offer(RuleStepLink(uc, container, st.n, STEP_LINK_EXACT, raw, st.phrase))
                continue
            if site_ext is None or step_lo is None or step_path != site_path:
                continue                       # no symbol table / no enclosing symbol: exact only
            if enclosing_extent(ext.get(step_path, []), step_lo) == site_ext:
                offer(RuleStepLink(uc, container, st.n, STEP_LINK_SYMBOL, raw, st.phrase))
    # Exact before symbol; within a use case, its OWN steps before the ones it inherits from a
    # sub-flow (`SF1` would otherwise sort ahead of `UC1` and read as the use case's first step).
    return sorted(best.values(),
                  key=lambda l: (l.strength != STEP_LINK_EXACT, element_sort_key(l.uc),
                                 l.container != l.uc, element_sort_key(l.container), l.n))


def rule_entities(m: ProjectModel, rule: BusinessRule,
                  extents: Extents | None = None,
                  steps: list[tuple[str, str, FlowStep]] | None = None) -> list[str]:
    """The entity ids a rule reaches — ONLY through a step that itself names one as an endpoint.

    Deliberately narrow. A rule does not get to claim an entity because its component happens to
    touch one somewhere: the step it is enforced at has to name the entity, or the link is a guess.
    The endpoint is matched against the DEFINED entity ids, not a prefix test — `ID_SHAPE` accepts
    `EP1`, so `startswith("E")` alone would let an entry point through as an entity."""
    if steps is None:
        steps = anchored_flow_steps(m)
    defined = {e.id for e in m.entities}
    by_key = {(uc, container, st.n): st for uc, container, st in steps}
    out: set[str] = set()
    for link in rule_steps(m, rule, extents, steps):
        st = by_key.get((link.uc, link.container, link.n))
        if st is None:
            continue
        out.update(e for e in (st.src, st.dst) if e in defined)
    return sorted(out, key=element_sort_key)


# ── sweep state: DERIVED, never authored ──────────────────────────────────────────────────────────
# There is deliberately no `swept` field. An authored boolean asserting "I searched the whole repo"
# is unfalsifiable, and every one of the prototype's worst errors was hand-assigned data rendered as
# derived. Sweep state comes from a CANARY instead: the map already anchors the decisions it walked,
# so an anchored flow step whose wording reads like a decision that no rule claims is either a rule
# nobody wrote or a step that is not a decision. Both need a human; neither can be asserted away.

#: Wording that reads like a DECISION rather than a mechanical action. A heuristic worklist, and a
#: FLOOR in the same sense as the operative-line check: it catches the sweep that stopped early, it
#: does not prove the sweep was complete. Tuned for precision over recall, because a false positive
#: holds a swept rule unswept — sweep state is derived FROM this list. Noun forms are excluded on
#: purpose: `validat(e|ing)` matches "the validation run", while `validator` is a component.
#:
#: MEASURED, on this repo's own map: 13 of its 89 distinct anchored steps match. Most are genuinely
#: conditional once read with their `note` ("only with `--open`", "a blocked CDN falls back to plain
#: text"), and a minority are not — `\bonly\b` also catches "only judges the difference" and
#: "removes it only now". Those are the cost of keeping the single most decision-bearing word in
#: English, and the 'Sweep debt' record is what an author writes for one. RECALL IS UNTESTED and
#: known-incomplete: a decision phrased without a marker word ("returns 403 for a non-member",
#: "scoped to the tenant") is missed, which is why this is a worklist rather than a gate.
_DECISION_MARKERS: tuple[str, ...] = (
    r"\bif\b", r"\bunless\b", r"\bonly\b", r"\botherwise\b", r"\belse\b",
    r"\breject", r"\bden(?:y|ies|ied)\b", r"\brefus", r"\bforbid",
    r"\ballow", r"\bpermit", r"\bgrants?\b",
    r"\brequire", r"\bmust\b", r"\benforce",
    r"\bvalidat(?:e|es|ed|ing)\b", r"\bverif(?:y|ies|ied|ying)\b", r"\bguard",
    r"\blimits?\b", r"\bthrottl", r"\bquota", r"\bthreshold",
    r"\bat most\b", r"\bat least\b", r"\bno more than\b",
    r"\bdefaults? to\b", r"\bfalls? back\b", r"\bfallback\b", r"\bprefer",
    r"\bskips?\b", r"\bexpir", r"\bstale\b",
    r"\bpriorit", r"\bwins\b", r"\bprecede",
    r"\bdecid", r"\bchoos", r"\bpicks?\b",
    r"\bblocks on\b", r"\bfails? the\b",
)
_DECISION_RE = re.compile("|".join(_DECISION_MARKERS), re.IGNORECASE)

#: A block small enough that "nearly all single-site" says nothing — two one-site rules are not a
#: pattern. The share is deliberately high: fusion is a judgement, and this points, it never gates.
_GRANULAR_BLOCK_MIN = 4
_GRANULAR_BLOCK_SHARE = 0.8

# The 'Sweep debt' extras heading records "this decision-sounding step is not a business rule",
# keyed by the step's own ANCHOR (`path:line: why`). Anchor-keyed rather than `UCn/step`, because
# `_RECORD_LINE` only matches `(?:CAP|EP|UC|HP|R|C|E)\d+` line-leaders — a `BR7:` or `UC4/11:` line
# would silence nothing, silently. Read with `_recorded_line_keys`, like 'Accepted duplications',
# and written as a LITERAL at each use site (the contract test derives the machine-read list from
# exactly those literals).


def decision_sounding_steps(m: ProjectModel) -> list[tuple[str, str, FlowStep]]:
    """Anchored flow steps whose phrase (or note) reads like a decision — the sweep worklist."""
    return [(uc, container, st) for uc, container, st in anchored_flow_steps(m)
            if _DECISION_RE.search(f"{st.phrase} {st.note}")]


def rule_claimed_step_keys(m: ProjectModel, extents: Extents | None = None,
                           steps: list[tuple[str, str, FlowStep]] | None = None) -> set[tuple[str, int]]:
    """The `(container, n)` of every step SOME rule covers — the canary's coverage test.

    TWO forms, and the second one is what keeps this honest.

    ANCHOR coverage: a rule site links to the step, exact or same-enclosing-symbol. The symbol
    strength has to count — the authoring contract tells the sweep to anchor the true operative line
    "even when a different line would join a flow step", so a site a few lines from the step inside
    one function is the systematic case. Without `extents` this degrades to exact-only, which
    reports more debt (the safe direction); "the same enclosing function" is not derivable from the
    map.

    STRUCTURAL coverage: a rule is enforced in a component the step NAMES as an endpoint. This is
    deliberately generous, and the alternative is worse than generosity. A flow step's `where` is
    the CALLER's line (`C1 → C2 : checks the owner` anchors where C1 calls C2) while the rule's
    operative line is inside C2 — a different file, so no anchor link can ever exist. Requiring one
    would make "the worklist is empty" unreachable by honest anchoring, and the only way to a clean
    `validate` would be to add a decoy site on the step's own line: the exact corruption the
    contract forbids in capitals, rewarded by the gate. A canary that pays for dishonest anchors is
    worse than a canary that clears a step early.

    Keyed by `(container, n)`, not `(uc, container, n)`: the anchors decide the link, and they do
    not vary by which use case rides a sub-flow."""
    if steps is None:
        steps = anchored_flow_steps(m)
    owners = component_file_owners(m)
    enforcing: set[str] = set()
    for r in m.rules:
        enforcing.update(rule_components(m, r, owners))
    covered = {(l.container, l.n)
               for r in m.rules
               for l in rule_steps(m, r, extents, steps)}
    covered |= {(container, st.n) for _uc, container, st in steps
                if enforcing.intersection((st.src, st.dst))}
    return covered


def sweep_debt(m: ProjectModel, extents: Extents | None = None) -> list[tuple[str, FlowStep]]:
    """Distinct `(container, step)` pairs that read like a decision, that no rule claims, and that no
    'Sweep debt' line adjudicates — the whole-map worklist, and the input to per-rule sweep state.

    Keyed by the AUTHORING container so a sub-flow step is reported once as `SF50 step 4` rather
    than once per riding use case as `UC9 step 4` — which is both a double count and the wrong row
    (UC9 has its own step 4), and breaks the labelling convention `_check_anchor_format` uses.

    EMPTY on a map with no rules: the canary answers "did the sweep miss something?", and on a map
    nobody swept every decision is trivially unclaimed. Firing there would put a permanent advisory
    on every existing map, which is exactly the "flag conflating nobody-looked with no-line-exists"
    the prototype shipped."""
    return _sweep_debt_split(m, extents)[0]


def _sweep_debt_split(m: ProjectModel,
                      extents: Extents | None = None) -> tuple[list[tuple[str, FlowStep]], list[str]]:
    """`(debt, silenced anchors)` — the worklist, and what a recorded line took out of it.

    The two are returned together because a silence you cannot see reads exactly like having no
    findings, and this escape does not merely quieten an advisory: it changes `rules_swept`, a
    DERIVED state. The suppression report is what keeps that visible."""
    if not m.rules:
        return [], []
    steps = anchored_flow_steps(m)
    claimed = rule_claimed_step_keys(m, extents, steps)
    recorded = _recorded_line_keys(m, "sweep debt")
    out: dict[tuple[str, int], tuple[str, FlowStep]] = {}
    silenced: set[str] = set()
    for _uc, container, st in decision_sounding_steps(m):
        if (container, st.n) in claimed:
            continue
        where = (st.where or "").strip()
        if _records_key(recorded, where):
            silenced.add(where)
            continue
        out[(container, st.n)] = (container, st)
    return ([out[k] for k in sorted(out, key=lambda k: (element_sort_key(k[0]), k[1]))],
            sorted(silenced))


def rules_swept(m: ProjectModel, extents: Extents | None = None) -> dict[str, bool]:
    """Per rule id, whether the code it governs holds NO uncovered decision-sounding step.

    This IS the sweep state — computed, not asserted; there is no field to set. READ IT FOR EXACTLY
    WHAT IT SAYS, and no more. It is a FLOOR, in the same sense as the operative-line check: it
    catches decision-shaped code nothing claims, never that a sweep was exhaustive. Three limits,
    all real:

      * a rule whose components hold no decision-sounding step at all is swept TRIVIALLY;
      * `_DECISION_MARKERS` recall is untested and known-incomplete, so a decision phrased without a
        marker word is invisible to it;
      * coverage counts a rule enforced in a component the step NAMES, so one rule in a component
        clears every decision-sounding step that names it.

    The two halves are asymmetric on purpose. COVERAGE asks which components a step NAMES;
    ATTRIBUTION asks which components own the file the step is ANCHORED IN. So an uncovered step
    anchored inside a rule's own file holds that rule unswept — there is decision-shaped code in the
    code it governs that nothing claims. A rule that resolves to no component is NOT swept: there is
    no territory to have finished sweeping."""
    owners = component_file_owners(m)
    debt_comps: set[str] = set()
    for _container, st in sweep_debt(m, extents):
        debt_comps.update(owners.get(strip_anchor((st.where or "").strip()), ()))
    out: dict[str, bool] = {}
    for r in m.rules:
        comps = rule_components(m, r, owners)
        out[r.id] = bool(comps) and not any(cid in debt_comps for cid in comps)
    return out


# ── the rule checks ───────────────────────────────────────────────────────────────────────────────

def rule_row_problems(m: ProjectModel) -> list[str]:
    """The ROW-LOCAL blocking rules — a statement, at least one site, a well-formed site, and no two
    rules stating the same decision at the same lines.

    Split out because `lint_fragment` runs these on ONE block's fragment. The whole-map rules stay
    in `check_rules_model`: `Component.files` lives in a different fragment entirely, so asking a
    block agent about it fails its lint on a defect it does not own and cannot fix."""
    problems: list[str] = []
    for r in m.rules:
        if not (r.name or "").strip():
            problems.append(f"{r.id} has no `name` — a rule needs a SHORT title beside its "
                            "statement, the way a use case has one beside its trigger→outcome. "
                            "Without it every list of rules is a wall of sentences and every "
                            "breadcrumb truncates one mid-word")
        if not (r.statement or "").strip():
            problems.append(f"{r.id} states no decision — `statement` is the rule; a site list "
                            "without one is a set of anchors nobody can read")
        if not r.sites:
            problems.append(f"{r.id} lists no enforcement site — a rule nothing enforces is a "
                            "belief about the product, not a claim about this code. Anchor the "
                            "operative line(s), or set `no_call_site` on a site that is enforced "
                            "by construction (a type, a schema constraint, a config-wired guard)")
        for i, site in enumerate(r.sites):
            where = (site.where or "").strip()
            if not where and not site.no_call_site:
                problems.append(f"{r.id} site[{i}] has no `where` — anchor the OPERATIVE line "
                                "(the one that acts), or set `no_call_site`")
            elif where and site.no_call_site:
                problems.append(f"{r.id} site[{i}] sets `no_call_site` but carries a `where` "
                                f"('{where}') — a site is one or the other; drop whichever is wrong")
            elif where and not FILE_LINE_ANCHOR.match(where):
                problems.append(f"{r.id} site[{i}]: '{where}' names a whole file — a site claims "
                                "that ONE line enforces the rule, so it must carry a `:line` "
                                "(that claim is what the operative-line check reads)")

    # Two block agents can state the same rule with different authored ids, so the duplicate-id
    # check stays silent. Identity is the NORMALIZED statement plus the site set — the same
    # content-identity discipline `assemble._merge_duplicate_messaging` applies to a channel.
    # `assemble` MERGES these, so a normal build never reaches this line; it stands for the
    # hand-edited map, where deleting one row is the whole fix.
    by_identity: dict[tuple[str, tuple[str, ...]], list[str]] = {}
    for r in m.rules:
        by_identity.setdefault(rule_identity(r), []).append(r.id)
    for ids in sorted((ids for ids in by_identity.values() if len(ids) > 1),
                      key=lambda ids: element_sort_key(ids[0])):
        problems.append(f"Business rules {', '.join(ids)} state the same decision at the same "
                        "sites — two block agents wrote one rule twice; keep one")
    return problems


def check_rules_model(m: ProjectModel,
                      extents: Extents | None = None) -> tuple[list[str], list[str]]:
    """(problems, warnings) for the T7 decision layer — the row-local rules plus the whole-map ones.
    A STRICT NO-OP on a ruleless map: 10+ tests assert on the exact advisory set of maps that carry
    none, and the trapdoor golden must stay problem-free."""
    if not m.rules and not m.blocks:
        return [], []
    problems: list[str] = rule_row_problems(m)
    warnings: list[str] = []

    # The derivation INPUTS. Without `files` on any component, every rule resolves to no component,
    # renders bare, and is indistinguishable from a rule nobody enforces. Fail loudly rather than
    # render nothing — the map is the thing that is broken, not the rules.
    if m.rules and not any(c.files for c in m.components):
        problems.append(
            f"The map carries {len(m.rules)} business rule(s) but NO component declares `files` — "
            "a rule's components, its use-case steps and its sweep state are all DERIVED by "
            "resolving its sites through `Component.files`, so every rule would render bare and "
            "look like a rule nobody enforces. Harvest the components' file lists, or drop the rules")

    # The interim `access`-rule / `security[].source` exact-duplication guard is RETIRED here.
    # Rules are the storage now, so a map carrying both is an UN-REBUILT map rather than a mistake,
    # and this repo's own precedent (`duplicate_security_warnings`) already says an anchor is not a
    # claim identity — one line can legitimately guard two surfaces.
    recorded_debt = _recorded_line_keys(m, "sweep debt")

    # A rule that resolves to no component renders with nothing to show. Advisory, not blocking:
    # the map-wide `files` gate above catches the systemic case, and a single unresolved site is
    # debt the viewer already stamps `unverified`.
    owners = component_file_owners(m)
    orphan = sorted((r.id for r in m.rules
                     if any(not s.no_call_site for s in r.sites)
                     and not rule_components(m, r, owners)
                     and not _records_key(recorded_debt, r.id)),
                    key=element_sort_key)
    if orphan:
        warnings.append(
            f"Business rule(s) whose sites land in files no component claims, so they render with "
            f"no component and cannot be verified: {_shown(orphan, 12)}. Add the file to the owning "
            "component's `files`, re-anchor the site, or record '<BRn>: <why>' under a "
            "'Sweep debt' extras heading")

    # GRANULARITY. "Synthetic, not granular" is the objective, and a block whose rules are nearly
    # all single-site is the signature of a flow-step list wearing rule clothing — 55 one-site rules
    # pass every other check here AND maximise the swept count the eval prints, so nothing else in
    # the pipeline notices. Advisory: fusion is a judgement, and a genuinely one-site-per-decision
    # area is legitimate; recording the block id under 'Balance exceptions' is how you say so.
    granular = _recorded_line_keys(m, "balance exceptions")
    by_block: dict[str, list[BusinessRule]] = {}
    for r in m.rules:
        by_block.setdefault(r.block or "", []).append(r)
    thin = []
    for bid, rules in sorted(by_block.items(), key=lambda kv: element_sort_key(kv[0])):
        anchored = [r for r in rules if any(not s.no_call_site for s in r.sites)]
        singles = [r for r in anchored if len(r.sites) == 1]
        if (bid and len(anchored) >= _GRANULAR_BLOCK_MIN
                and len(singles) >= len(anchored) * _GRANULAR_BLOCK_SHARE
                and not _records_key(granular, bid)):
            thin.append(f"{bid} ({len(singles)} of {len(anchored)})")
    if thin:
        warnings.append(
            f"Block(s) whose rules are nearly all single-site: {_shown(thin, 8)} — the signature of "
            "a flow-step list wearing rule clothing. The objective is SYNTHETIC, not granular: one "
            "decision enforced in several places is ONE rule with several sites, and a drift toward "
            "one rule per anchor is a failure even when every rule verifies. Fuse them, or record "
            "'<BLKn>: <why this area really is one decision per site>' under a 'Balance exceptions' "
            "extras heading")

    # GRANULARITY OF THE ACCESS SURFACE. method.md requires the choice be recorded, "precisely
    # because the two readings differ ~5x on the same code" — one row per surface FAMILY versus one
    # per endpoint-and-condition. The safeguard that echoed it was gated on `if m.security:` and the
    # fold empties that, so it went dead exactly when the surface moved: two real builds recorded
    # nothing and nothing asked them to. Advisory, and only when the map HAS an access surface — a
    # map with no access rules has no choice to declare.
    if access_rules(m) and not recorded_security_granularity(m):
        warnings.append(
            f"{len(access_rules(m))} `access: true` rule(s) and no granularity record — one rule per "
            "surface FAMILY and one per endpoint-and-condition are both defensible and differ ~5x in "
            "row count on the same code, so a later reader cannot tell a re-scoped surface from a "
            "lost one. Record 'security-granularity: <family | endpoint-and-condition> — <why>' "
            "under a 'Balance exceptions' extras heading")

    debt, silenced = _sweep_debt_split(m, extents)
    if debt:
        listed = [f"{container} step {st.n} ({st.where}) — {_clip(st.phrase)}"
                  for container, st in debt]
        warnings.append(
            f"{len(debt)} anchored flow step(s) read like a DECISION that no business rule claims — "
            f"the sweep worklist: {_shown(listed, 10, sep='; ', unit='step(s)')}. "
            "Write the rule, or record "
            "'<the step's anchor>: <why it is not a decision>' under a 'Sweep debt' "
            "extras heading")
    if silenced:
        # A silence you cannot see reads exactly like having no findings — and this escape does not
        # only quieten an advisory, it flips `rules_swept`, a DERIVED state. Same disclosure the
        # granularity and runs-in families already print.
        warnings.append(
            f"{len(silenced)} decision-sounding step(s) suppressed by a recorded "
            "'Sweep debt' line, and counted as SWEPT because of it: "
            f"{_shown(silenced, 10, unit='step(s)')}. Re-read one by validating a copy with that "
            "line removed")

    return problems, warnings


def rule_identity(r: BusinessRule) -> tuple[str, tuple[str, ...]]:
    """A rule's CONTENT identity: normalized statement + the sorted set of its site anchors.

    Ids cannot carry it — rules are authored by one agent per block, from disjoint id ranges, so
    two agents stating one rule produce two different ids and the duplicate-id check stays silent."""
    statement = re.sub(r"[^a-z0-9]+", " ", (r.statement or "").lower()).strip()
    sites = tuple(sorted({(s.where or "").strip() for s in r.sites if (s.where or "").strip()}))
    return (statement, sites)


def triggered_entry_point_ids(m: ProjectModel) -> set[str]:
    """Entry-point ids named by some use case's `entry_points` — the TRIGGER arm of claiming."""
    return {e.strip() for u in m.use_cases for e in u.entry_points if e.strip()}


def unclaimed_external_entry_points(m: ProjectModel) -> list[EntryPoint]:
    """Externally-activated entry points that NEITHER arm of claiming reaches.

    Two arms, because one cannot carry it. A use case relates to the entry surface in two different
    ways, and an earlier revision of this design conflated them:

      * **trigger** — the front door an actor hits to START the use case. Authored on the use case
        (`entry_points`), so it can be cross-checked right after the harvest, before any tracing.
      * **traversal** — surfaces the scenario merely passes THROUGH. Derived from the flow's
        component reach, and this arm stays PRIMARY.

    Making the authored link the only test inverts on real maps. On this repo's own map ~16 of 61
    entry points are not triggers of anything a person does (fetches the browser app makes after the
    reader already clicked, plus middleware); a per-entry-point trigger test reports every one as a
    missing use case. On the mcpolis map the harvest recorded route GROUPS — the whole SPA is one
    row — so a dozen use cases would have to name zero surfaces, which the forward rule reads as
    "stale docs, drop it". The signal swings ~5x on granularity nothing regulates, so the derived
    arm carries the check and the authored arm refines it.

    Empty when the map has no flows AND no use case names a surface (additivity: an untraced map is
    'not yet traced', not 'all unclaimed'). Rows whose component is empty (its own advisory) or
    dangling (the blocking reference check owns those) are skipped."""
    triggered = triggered_entry_point_ids(m)
    if not m.flows and not triggered:
        return []
    claimed = flow_endpoint_ids(m)
    comp_ids = {c.id for c in m.components}
    return [ep for ep in external_entry_points(m)
            if (comp := ep.component.strip()) and comp in comp_ids and comp not in claimed
            and not (ep.id and ep.id in triggered)]


def unclaimed_self_entry_points(m: ProjectModel) -> list[EntryPoint]:
    """Self-activated entry points (crons, workers, consumers, startup hooks) that no flow reaches.

    These used to be exempt automatically, on the reasoning that nobody outside asks so no use case
    has to claim them. That exemption hid a whole class: a scheduled job IS an actor with a goal by
    the method's own Roles rule, and a background capability could be missing from the use-case list
    with no signal at all.

    But the honest half matters too, and the warning says it: for a cron or a startup hook there is
    often NO actor to claim it, so the answer is frequently a recorded line rather than a use case.
    Dropping the exemption makes that a decision instead of a silence."""
    if not m.flows and not triggered_entry_point_ids(m):
        return []
    triggered = triggered_entry_point_ids(m)
    claimed = flow_endpoint_ids(m)
    comp_ids = {c.id for c in m.components}
    return [ep for ep in m.entry_points
            if grammar.effective_activation(ep.activation, ep.kind) == "self"
            and (comp := ep.component.strip()) and comp in comp_ids and comp not in claimed
            and not (ep.id and ep.id in triggered)]


def _group_unclaimed_by_component(m: ProjectModel, eps: list[EntryPoint]
                                  ) -> list[tuple[str, list[EntryPoint]]]:
    """Group unclaimed entry points by owning component, MINUS the ones already adjudicated (a `Cn`
    recorded under an 'Unclaimed surfaces' heading) or folded under a recorded 'Coverage exceptions'
    dir — i.e. the surfaces that would still WARN.

    The escape stays keyed on the owning component's directory, which is coarser than the finding
    now is: with the trigger arm in play a single component can hold both a claimed and an unclaimed
    surface. That is deliberate — the escape exists to let an operator retire a whole area in one
    line, and narrowing it to the entry point would put the wall of records back."""
    if not (m.entry_points and eps):
        return []
    accepted = _recorded_ids(m, "unclaimed surfaces", ("C",))
    cov_dirs = _recorded_coverage_dirs(m)  # a 'Coverage exceptions' dir also silences its components
    comp_dir: dict[str, str] = {}
    for c in m.components:
        if c.source:
            rel = strip_anchor(c.source).rstrip("/")
            comp_dir[c.id] = rel.rsplit("/", 1)[0] if "/" in rel else rel
    by_comp: dict[str, list[EntryPoint]] = {}
    for ep in eps:
        by_comp.setdefault(ep.component.strip(), []).append(ep)
    out: list[tuple[str, list[EntryPoint]]] = []
    for cid, group in sorted(by_comp.items()):
        if cid in accepted:
            continue  # adjudicated by the operator — recorded in the map, so it stays quiet
        if cov_dirs and cid in comp_dir and _under_recorded(comp_dir[cid], cov_dirs):
            continue  # the owning component sits under a recorded 'Coverage exceptions' dir
        out.append((cid, group))
    return out


def unclaimed_surface_components(m: ProjectModel) -> list[tuple[str, list[EntryPoint]]]:
    """The EXTERNAL unclaimed surfaces, grouped per component. Shared by the completeness warning
    and `validate --emit-unclaimed`, which prints this same set as a ready extras block so the lead
    adjudicates ~a hundred surfaces at once instead of hand-typing them."""
    return _group_unclaimed_by_component(m, unclaimed_external_entry_points(m))


def unclaimed_self_components(m: ProjectModel) -> list[tuple[str, list[EntryPoint]]]:
    """The SELF-activated unclaimed surfaces, grouped per component — the class that used to be
    exempt automatically."""
    return _group_unclaimed_by_component(m, unclaimed_self_entry_points(m))


def completeness_counts(m: ProjectModel) -> dict[str, int]:
    """The completeness picture as NUMBERS rather than a wall of advisories.

    Two things live here that are deliberately not warnings:

      * **trace debt.** The target is every use case traced — measured on a real build, closing the
        gap costs ~12 % of build tokens, which does not justify a coverage rule that redefines the
        shortfall as correct. So the shortfall is a number you can see and act on.
      * **off-spine use cases inside CORE capabilities.** Moving the spine check to capability
        altitude gives up the per-use-case signal: on the reference map six use cases (including
        "Remove a team member") sit off the walk inside a core capability and now warn about
        nothing. Counting them keeps them visible without reinstating eleven written records.

    `capabilities_untraced` is the empty-capability signal — a whole part of the product nobody
    traced, which today is invisible."""
    traced = set(flow_endpoint_ids_by_uc(m))
    cap_of = {u.id: (u.capability or "").strip() for u in m.use_cases}
    labels = {c.id: (c.label or "").strip().lower() for c in m.capabilities}
    on_spine = {g.uc for g in m.happy_path if g.uc}
    ext = external_entry_points(m)
    return {
        "use_cases": len(m.use_cases),
        "use_cases_traced": len([u for u in m.use_cases if u.id in traced]),
        "use_cases_untraced": len([u for u in m.use_cases if u.id not in traced]),
        "use_cases_naming_no_surface": len([u for u in m.use_cases if not u.entry_points]),
        "entry_points": len(m.entry_points),
        "entry_points_external": len(ext),
        "entry_points_unclaimed_external": len(unclaimed_external_entry_points(m)),
        "entry_points_unclaimed_self": len(unclaimed_self_entry_points(m)),
        "capabilities": len(m.capabilities),
        "capabilities_untraced": len([cid for cid, ends in capability_elements(m).items()
                                      if not ends]),
        "off_spine_in_core_capabilities": len(
            [u for u in m.use_cases
             if u.id not in on_spine and labels.get(cap_of.get(u.id, ""), "") == "core"]),
    }


# A recorded-exception line under one of the completeness headings names its subject id at the
# LINE START (optionally after a list bullet / bold marker) FOLLOWED BY A SEPARATOR — canonical
# form "C713: ops/debug routes — deliberate"; "UC15 (its name) — why" is tolerated (a live map
# wrote its record that way). One id per line. Deliberately stricter than balance_lib._exceptions'
# anywhere-in-body scan: these bodies carry multi-paragraph prose that names OTHER ids mid-sentence
# — an id mentioned in an explanation, or a prose sentence merely STARTING with an id and running
# on with no separator ("C9 handles this"), must not silently pre-exempt that element.
# `En` joined the vocabulary for 'Persistence exceptions', which now carries BOTH sides of the same
# question: a `Cn` line adjudicates a writer no entity explains, an `En` line adjudicates an entity
# no writer owns. Mixing them under one heading is unambiguous because every reader passes its own
# `prefixes` filter — a C line can never satisfy an E lookup, and vice versa.
# `CAP` and `EP` lead the alternation for the usual first-match reason (`CAP3` also starts with "C",
# `EP1` with "E") — without that, a recorded `CAP3: <why>` line matched the `C` branch, failed on
# "AP3", and silently adjudicated nothing.
#: How many records may restate ONE reason before the section is worth collapsing. Three is the
#: point where the repetition is unmistakable and a multi-key line is plainly shorter.
_REPEATED_REASON_MIN = 3


def _recorded_ids(m: ProjectModel, heading: str, prefixes: tuple[str, ...]) -> set[str]:
    """Ids adjudicated under a machine-read extras heading, read from line-leading tokens only.

    A token MAY carry a `/scope` suffix (`CAP4/spine`) when one id is the subject of two different
    checks — the same device `balance_lib.RUNS_IN_SCOPES` already uses, and for the same reason it
    was introduced there: a bare token silenced a whole family at once, which is the one thing the
    method says a record must never do. Both the bare and the scoped form are returned verbatim, so
    each caller asks for exactly the token its own check honours.

    ONE line reader (`records`), shared with every other escape family, so a fix to the line shape
    lands once — and so a record may name SEVERAL ids for one reason (`C101, C148: <why>`) without
    each family re-inventing the list."""
    return {k for k in records.recorded_keys(m, heading) if k.startswith(prefixes)}


# A recorded coverage-exception line names a repo-relative DIRECTORY at the line start followed by a
# separator — "mee6/plugins/: coarse whole-monorepo altitude". Line-leading + separator, one per line
# (the same discipline every family shares through `records`), so prose naming another path
# mid-sentence can't pre-exempt it. The separator excludes a BARE hyphen and accepts a SPACED one:
# a hyphen is legal inside a directory name, and when the path token was non-greedy a bare hyphen
# ended the match at the first one — `third-party/: vendored` recorded `third`, `mee6-legacy/
# plugins/: coarse` recorded `mee6`, silencing coverage findings across every sibling sharing the
# truncated prefix. This escape OVER-exempts when it misreads, which is the dangerous direction.


def _recorded_coverage_dirs(m: ProjectModel) -> set[str]:
    """Repo-relative directory prefixes recorded under a **'Coverage exceptions'** extras heading — the
    operator's conscious "this area is folded at a coarse altitude" decision. Silences the
    `--check-coverage` compression / absent-dir / no-entity-card warnings AND the unclaimed-surface
    completeness warning for anything AT OR UNDER the path (boundary-aware — `plugins` never silences
    `plugins-legacy`). Scoped by directory, so a real gap in an UNLISTED dir still warns; the trailing
    slash is normalized off so it matches the slash-less repo-relative dir keys the coverage walk uses."""
    return {p for k in records.recorded_keys(m, "coverage exceptions", records.DIR_KEY, records.SEP)
            if (p := k.strip().rstrip("/"))}


def _under_recorded(path: str, dirs: frozenset[str] | set[str]) -> bool:
    """`path` (repo-relative, no trailing slash) is at or under one of the recorded dirs, on a path
    BOUNDARY (`covered_under`'s rule) — `plugins` matches `plugins` and `plugins/x`, never `plugins-legacy`."""
    return any(path == d or path.startswith(d + "/") for d in dirs)


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
        for cid, eps in unclaimed_self_components(m):
            shown = "; ".join(f"[{ep.kind}] {_clip(ep.trigger)}" for ep in eps)
            warnings.append(
                f"{cid} ({comp_name.get(cid, cid)}): {len(eps)} self-activated entry point(s) no "
                f"use case reaches ({shown}) — a scheduled job or consumer is an actor with a goal, "
                "so this may be a missing use case; but a cron or a startup hook often has no actor "
                f"to claim it, in which case record '{cid}: <why>' under an 'Unclaimed surfaces' "
                "extras heading")
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
        recorded = _recorded_ids(m, "happy path coverage", ("R", "UC", "CAP", "HP"))
        on_spine = {g.uc for g in m.happy_path if g.uc}
        for r in m.roles:
            driven = {u.id for u in m.use_cases if r.id in u.actors}
            if driven and not driven & on_spine and r.id not in recorded:
                warnings.append(
                    f"{r.id} ({r.name}) drives no on-spine use case — the Happy Path involves all "
                    "relevant actors: give one of its use cases a spine step, or record "
                    f"'{r.id}: <why>' under a 'Happy Path coverage' extras heading")
        warnings.extend(_spine_membership_warnings(m, on_spine, recorded))
    return warnings


def _spine_membership_warnings(m: ProjectModel, on_spine: Container[str],
                               recorded: set[str]) -> list[str]:
    """Who belongs on the Happy Path — asked at CAPABILITY altitude once capabilities exist.

    Without capabilities this stays what it always was: every off-spine use case demands a written
    `UCn: <why>`. That is the additive path for a map that has not adopted the grouping, and it is
    also the shape that does not scale — on the reference map it is 11 records, and the method's own
    history is of records that cost more to write than to skip.

    With capabilities the question moves up a level and runs in BOTH directions:

      * forward — a **core** capability no spine step reaches. About five checks, each a real gap.
      * converse — a spine step whose use case sits in a NON-core capability. This is the direction a
        single-direction check cannot produce, and it is the one that catches a walk quietly padded
        with supporting work (on the reference map: the audit-log step).

    A non-core capability that HOLDS off-spine use cases still leaves a record — one line for the
    capability, not one per use case. Without that, relabelling a capability core→supporting would
    silence its whole membership with no trace anywhere, which is exactly the escape the label must
    not become.

    What is deliberately given up: an individual core use case falling off the walk no longer warns,
    because its capability still passes. On the reference map that is six use cases (including
    "Remove a team member"), so they are REPORTED by `completeness_counts` rather than dropped —
    visible without reinstating the per-use-case paperwork."""
    if not m.capabilities:
        return [f"{u.id} ({u.name}) is off the Happy-Path spine and unrecorded — the Coverage "
                f"rule NOTES the use cases left off: record '{u.id}: <why>' under a "
                "'Happy Path coverage' extras heading (or give it a spine step)"
                for u in m.use_cases if u.id not in on_spine and u.id not in recorded]
    warnings: list[str] = []
    caps = {c.id: c for c in m.capabilities}
    # A use case in NO capability falls through every check below, because all of them key off
    # membership — so an off-spine use case with an empty or typo'd `capability` was reported by
    # nothing at all, and was not counted either. That is a silent loss, not the documented trade
    # (which is "an off-spine member of a CORE capability is counted instead of warned"). The
    # symmetric advisory already exists for the other two forests ("Entities with no SUBDOMAIN").
    if ungrouped := [u for u in m.use_cases
                     if (u.capability or "").strip() not in caps and u.id not in recorded]:
        warnings.append(
            f"Use cases in no capability: {_shown([u.id for u in ungrouped], 8)} — the map groups use "
            "cases, and an ungrouped one is invisible to every Happy-Path coverage check; assign a "
            "capability (via `reconcile`), or record it under a 'Happy Path coverage' extras heading")
    by_id = {u.id: u for u in m.use_cases}
    # The forward check reads the WHOLE SUBTREE — a parent capability is reached when any descendant's
    # use case is on the walk. The non-core check below deliberately reads DIRECT membership instead:
    # the record belongs to the capability that actually holds the off-spine use cases, and rolling up
    # would make a parent and its child each demand a line for the same ones.
    subtree = capability_members(m)
    direct: dict[str, list[UseCase]] = {}
    for u in m.use_cases:
        if (cap := (u.capability or "").strip()) in caps:
            direct.setdefault(cap, []).append(u)
    # The highest core ancestor that no spine step reaches — reporting a whole unreached subtree once
    # instead of at every level. Without this a three-node core tree produced three warnings for one
    # absence, and a record on the root silenced only the root while its children kept firing, which
    # breaks the "one line covers it" promise exactly where the tree is deepest.
    # The forward (core-off-the-walk) check honours a SCOPED record, `CAPn/spine`. The non-core check
    # keeps the bare `CAPn`. Sharing one token let a line written about a supporting capability's
    # off-spine members keep hiding a real core-coverage gap after that capability was relabelled
    # core — one record silencing a check it was never written for.
    unreached_core = {cid for cid, c in caps.items()
                      if (c.label or "").strip().lower() == "core"
                      and subtree.get(cid) and not any(uc in on_spine for uc in subtree[cid])}
    spine_recorded = {r[:-len("/spine")] for r in recorded if r.endswith("/spine")}
    covered_by_ancestor: set[str] = set()
    for cid in unreached_core:
        anc, guard = caps[cid].parent, 0
        while anc and guard < 12:
            if anc in unreached_core or anc in spine_recorded:
                covered_by_ancestor.add(cid)
                break
            anc, guard = (caps[anc].parent if anc in caps else None), guard + 1
    for cap_id, cap in caps.items():
        label = (cap.label or "").strip().lower()
        mine = direct.get(cap_id, [])
        if not subtree.get(cap_id):
            continue
        if label == "core":
            # The `recorded` test is INSIDE each branch, not above them. Sharing it let one `CAPn`
            # line silence both checks: record a supporting capability's off-spine members, later
            # relabel it core, and the stale record went on hiding a genuine core-coverage gap.
            # One record silences exactly one (check, id) pair — the rule the HP-step case follows.
            if (cap_id in unreached_core and cap_id not in spine_recorded
                    and cap_id not in covered_by_ancestor):
                mine = [by_id[uc] for uc in sorted(subtree.get(cap_id, ())) if uc in by_id]
                warnings.append(
                    f"{cap_id} ({cap.name}) is a core capability that no Happy-Path step reaches — "
                    f"the walk traverses all main functionality: give one of its {len(mine)} use "
                    f"case(s) a spine step, or record '{cap_id}/spine: <why>' under a 'Happy Path "
                    "coverage' extras heading")
        elif (cap_id not in recorded) and (off := [u for u in mine if u.id not in on_spine]):
            warnings.append(
                f"{cap_id} ({cap.name}) is labelled '{label or 'unlabelled'}' and holds "
                f"{len(off)} off-spine use case(s) — one record covers them all: write "
                f"'{cap_id}: <why>' under a 'Happy Path coverage' extras heading (or, if this is "
                "really product functionality, label the capability core)")
    for g in m.happy_path:
        cap_id = (next((u.capability for u in m.use_cases if u.id == g.uc), "") or "").strip()
        cap = caps.get(cap_id)
        if (g.uc and cap is not None and g.id not in recorded
                and (cap.label or "").strip().lower() != "core"):
            # The escape is the STEP's id, never the capability's: recording `CAPn` already means
            # "this non-core capability's off-spine use cases are fine", a different judgement. One
            # record must silence exactly one (check, id) pair.
            warnings.append(
                f"{g.id} realizes {g.uc}, which sits in {cap_id} ({cap.name}) — labelled "
                f"'{(cap.label or 'unlabelled').strip()}', not core. Either the label is wrong or "
                f"the step does not belong on the main walk; record '{g.id}: <why>' under a "
                "'Happy Path coverage' extras heading to keep it")
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


def confidence_warnings(m: ProjectModel) -> list[str]:
    """`confidence` must be one of the two words the dispatch template asks for.

    The schema enumerates it, but `method/project-map.schema.json` is a generated DOCUMENT that
    nothing validates against at runtime — a fragment carrying `confidence: "high"` linted clean.
    An enum nothing enforces is the "shipped, tested and unreachable" defect this project keeps
    hitting, so the check lives here, where `lint-fragment` reaches it in the authoring agent's own
    turn."""
    ok = {*grammar.CONFIDENCE_VALUES, ""}
    bad: list[str] = []
    for label, rows in (("subsystem", m.subsystems), ("component", m.components),
                        ("dep", m.deps), ("test", m.tests)):
        for r in rows:
            val = getattr(r, "confidence", "")
            if val not in ok:
                bad.append(f"{label} {getattr(r, 'id', getattr(r, 'area', '?'))}: '{val}'")
    if not bad:
        return []
    return [f"{len(bad)} row(s) carry a `confidence` outside the vocabulary "
            f"({' / '.join(grammar.CONFIDENCE_VALUES)}): {_shown(bad, 8)} — the dispatch "
            f"template asks for those two words; anything else is a synonym nobody can group on."]


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
    # A project whose real vocabulary needs a bucket the seed list does not have (an MCP gateway
    # genuinely has an 'MCP protocol' bucket) would otherwise be told to rename it on EVERY rebuild,
    # forever, with no way to say "this one is deliberate". Worse, the stable-spelling advice and the
    # nudge pull against each other: a build that reuses last map's spelling for stability earns the
    # warning for doing so. `Bucket vocabulary` is the escape — one `<bucket>: <why>` line per
    # project-specific bucket, read here.
    declared = _recorded_line_keys(m, "bucket vocabulary")
    silenced_buckets = [b for b in minted if _records_key(declared, b)]
    for bucket, is_lib in minted.items():
        if _records_key(declared, bucket):
            continue
        if is_lib:
            warnings.append(f"Library bucket '{bucket}' is minted (not a seed) — a synonym of a seed? "
                            f"Reuse the exact spelling on rebuild, or record "
                            f"'{bucket}: <why this project needs it>' under a 'Bucket vocabulary' "
                            f"extras heading (seeds: "
                            f"{', '.join(grammar.DEP_BUCKET_SEEDS_LIBRARY)}).")
        else:
            warnings.append(f"External bucket '{bucket}' is minted (not a seed) — fine if it's a real "
                            f"product purpose (splitting the '{grammar.DEP_BUCKET_CATCHALL_EXTERNAL}' "
                            f"catch-all this way is encouraged); reuse the exact spelling on rebuild.")
    if silenced_buckets:
        warnings.append(f"{len(silenced_buckets)} minted bucket(s) declared under 'Bucket "
                        f"vocabulary' and NOT re-nudged: {', '.join(sorted(silenced_buckets))}. "
                        f"Re-read one by validating a copy with that line removed.")
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


def _check_entry_kinds(m: ProjectModel) -> list[str]:
    """Entry-point `kind` hygiene — ALL advisory (the vocabulary is seeded-open like dep buckets,
    never a gate: real maps legitimately mint project-specific kinds such as `mcp-tool` on one map,
    `gateway-loop` on another). What this kills is SPELLING drift of the common kinds: live maps grew
    `http` vs `http-route` and `event` vs `event-consumer` for the same thing, which splits the
    System-tab grouping and any per-kind coverage statement. A kind that folds to a seed via
    `grammar.canonical_entry_kind` (case drift or a known alias) nudges toward the canonical
    spelling, aggregated per distinct spelling; a minted kind gets ONE "synonym of a seed?" nudge."""
    warnings: list[str] = []
    alias_count: dict[str, int] = {}          # authored drift spelling -> row count
    alias_canon: dict[str, str] = {}          # authored drift spelling -> canonical seed
    minted: set[str] = set()
    for ep in m.entry_points:
        authored = (ep.kind or "").strip()
        if not authored:
            continue
        canonical = grammar.canonical_entry_kind(authored)
        if canonical != authored:
            alias_count[authored] = alias_count.get(authored, 0) + 1
            alias_canon[authored] = canonical
        elif canonical not in grammar.ENTRY_POINT_KINDS:
            minted.add(canonical)
    for authored in sorted(alias_count):
        warnings.append(
            f"entry-point kind '{authored}' ({alias_count[authored]} row(s)) is a drift spelling — "
            f"write the canonical '{alias_canon[authored]}' so grouping and per-kind coverage "
            "statements don't split")
    if minted:  # ONE aggregated line — an older map can carry a dozen minted kinds, and repeating
        # the seed list per kind would drown the report (the `_clip`/aggregation hygiene).
        warnings.append(
            "entry-point kind(s) minted (not a seed): "
            + ", ".join(f"'{k}'" for k in sorted(minted))
            + " — fine where the seeds name nothing close; where one is a synonym of a seed, reuse "
              f"that exact spelling on rebuild (seeds: {', '.join(grammar.ENTRY_POINT_KINDS)})")
    return warnings


# A recorded entry-point coverage line: a line-leading KIND token followed by a separator and one of
# the contract words — "http-route: complete — enumerated from FastAPI app.routes". The same
# line-leading + separator discipline as `_RECORD_LINE` / `_COVERAGE_DIR_LINE`, so prose mentioning
# a kind mid-sentence can't record a contract for it. The kind token ALLOWS spaces (minted kinds
# like "Mounted ASGI" are legal and must be recordable — the non-greedy match stops at the
# separator+contract-word, adversarial-review finding #1) and is compared CASEFOLDED (finding #4:
# minted kinds have no canonical spelling to converge on, so `Gateway-loop:` covers `gateway-loop`).
_KIND_COVERAGE_LINE = re.compile(
    r"^\s*(?:[-*]\s+)?\**\s*([A-Za-z][\w -]*?)\**\s*[:(—–-]\s*\**(complete|sampled|partial)\b",
    re.IGNORECASE)


def _recorded_kind_coverage(m: ProjectModel) -> dict[str, str]:
    """The per-kind completeness contract recorded under an **'Entry-point coverage'** extras heading:
    CASEFOLDED canonical kind -> `complete` / `sampled` / `partial`. Keys fold through
    `grammar.canonical_entry_kind` so a contract written as `http` covers the `http-route` rows."""
    out: dict[str, str] = {}
    for body in balance_lib.extras_bodies(m, "entry-point coverage"):
        for line in body.splitlines():
            hit = _KIND_COVERAGE_LINE.match(line)
            if hit:
                out[grammar.canonical_entry_kind(hit.group(1)).lower()] = hit.group(2).lower()
    return out


def _kind_coverage_warnings(m: ProjectModel) -> list[str]:
    """The per-kind completeness contract (advisory, ONE aggregated line): live maps proved that
    T4 exhaustiveness is silently build-dependent — one map enumerated 38 http routes, a bigger one
    recorded 7 for a far larger API, and nothing in the map said which inventory was complete. The
    remedy is an honesty statement per kind, recorded under an **'Entry-point coverage'** extras
    heading (`<kind>: complete|sampled|partial — how it was enumerated`), read by
    `_recorded_kind_coverage`. A kind present in `entry_points` with no statement gets nudged —
    aggregated into one warning so a fresh map reads one actionable line, not one per kind."""
    if not m.entry_points:
        return []
    recorded = _recorded_kind_coverage(m)
    present = sorted({grammar.canonical_entry_kind(ep.kind)
                      for ep in m.entry_points if (ep.kind or "").strip()})
    missing = [k for k in present if k.lower() not in recorded]
    if not missing:
        return []
    return ["Entry-point coverage: no completeness statement for kind(s) "
            + ", ".join(f"'{k}'" for k in missing)
            + " — is each inventory complete or a sample? Record '<kind>: complete|sampled|partial "
              "— <how it was enumerated>' under an 'Entry-point coverage' extras heading"]


def _cadence_row_warnings(m: ProjectModel) -> list[str]:
    """The ROW-LOCAL cadence nudges (advisory) — shared with `lint_fragment_warnings`, so the
    authoring agent hears them in its own turn (review #6):

      * a cadence on an effectively-EXTERNAL entry point — a schedule on a caller-driven surface is
        a contradiction (fix the activation/kind, or drop the cadence);
      * a set cadence citing no `cadence_source` — inferred, aggregated (the deployment-variant
        rule: cite the declaring line or say it's inferred);
      * a `cadence_source` with NO cadence — a dangling anchor that labels nothing (review #7)."""
    warnings: list[str] = []
    inferred = 0
    for ep in m.entry_points:
        act = grammar.effective_activation(ep.activation, ep.kind)
        has_cadence = bool((ep.cadence or "").strip())
        has_source = bool((ep.cadence_source or "").strip())
        if has_cadence and act != "self":
            warnings.append(
                f"entry_points[{ep.component} {ep.kind}] records cadence '{_clip(ep.cadence)}' but "
                "is externally activated — a schedule on a caller-driven surface is a "
                "contradiction; fix the activation/kind, or drop the cadence")
        if has_cadence and not has_source:
            inferred += 1
        if has_source and not has_cadence:
            warnings.append(
                f"entry_points[{ep.component} {ep.kind}] cites a `cadence_source` but records no "
                "`cadence` — the anchor labels nothing; author the cadence value, or drop the anchor")
    if inferred:
        warnings.append(
            f"{inferred} entry-point cadence value(s) cite no `cadence_source` — inferred; anchor "
            "the line that DECLARES the schedule (beat/cron config, compose, the loop's sleep)")
    return warnings


def _cadence_warnings(m: ProjectModel) -> list[str]:
    """Cadence hygiene (all advisory). A self-activated entry point IS the map's answer to "what
    runs with no user?" — but live maps stopped there: the jobs were named, the WHEN was nowhere
    (no cron/interval detail on any of three real maps). The row-local signals live in
    `_cadence_row_warnings` (shared with fragment lint); this adds the whole-map family:
    self-activated entry points with NO cadence — aggregated + capped; the escape is the literal
    `cadence` (line-leading) under a 'Balance exceptions' extras heading (a project whose loops
    are all genuinely continuous/caller-shaped may silence the family)."""
    warnings = _cadence_row_warnings(m)
    missing: list[str] = []
    for ep in m.entry_points:
        if (not (ep.cadence or "").strip()
                and grammar.effective_activation(ep.activation, ep.kind) == "self"):
            missing.append(f"[{ep.kind}] {_clip(ep.trigger)}")
    if missing and "cadence" not in balance_lib._exceptions(m):
        shown = _shown(missing, 6, sep="; ")
        warnings.append(
            f"{len(missing)} self-activated entry point(s) record no cadence ({shown}) — when does "
            "each run? Author `cadence` (a cron expr / 'every 30s' / 'on-boot' / 'continuous') "
            "with its `cadence_source`, or record the literal `cadence` under a "
            "'Balance exceptions' extras heading")
    return warnings


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


def _check_messaging(m: ProjectModel) -> tuple[list[str], list[str]]:
    """Messaging-catalog rules. The rows CATALOG, the edges CLAIM — so the shape rules are
    blocking (row-local: unique name, D-shaped broker / C-shaped participants / E-shaped payload,
    non-folded broker, `source` anchor shape via `_check_anchor_format`; id RESOLUTION rides
    `_check_references`), while everything relating a row to the rest of the map is advisory:

      * a broker that classifies as neither messaging nor datastore — a channel usually lives on
        a bus or a store; a `service` broker is worth a second look;
      * a publisher/consumer with NO backbone `C→broker` edge — the diagrams and the change-impact
        ripple only walk edges, so an edge-less participation is INVISIBLE to both (the
        `unbacked_entity_steps` rule, applied to messaging); author the edge;
      * a channel with no consumers — a dead letter (or an external consumer worth a dep); escape =
        the literal `channel-ends` under a 'Balance exceptions' extras heading, for a catalog whose
        far ends genuinely live outside the mapped repo.

    The fourth messaging advisory — a channel no participant's `runs_in` can place — is NOT here:
    it answers to the `runs-in` literal, so it lives in `_messaging_placement_warnings` with the
    rest of that family and is silenced (and counted) at the family's one exit."""
    problems: list[str] = []
    warnings: list[str] = []
    excepted = balance_lib._exceptions(m)
    deps_by_id = {d.id: d for d in m.deps}
    counts: dict[str, int] = {}
    for mr in m.messaging:
        counts[mr.name] = counts.get(mr.name, 0) + 1
    dups = sorted(n for n, c in counts.items() if c > 1)
    if dups:
        problems.append(f"Duplicate messaging channel name(s): {', '.join(dups)} — channel names "
                        "must be unique (they are the row's key, like deployment units)")
    edge_pairs = {(e.src, e.dst) for e in m.edges}
    for i, mr in enumerate(m.messaging):
        label = f"messaging[{i}] ('{mr.name}')"
        if not mr.name.strip():
            problems.append(f"messaging[{i}]: empty channel name")
        if mr.broker and not _STORE_DEP_SHAPE.match(mr.broker):
            problems.append(f"{label} broker '{mr.broker}' is not a D-id")
        for role, ids in (("publisher", mr.publishers), ("consumer", mr.consumers)):
            for cid in ids:
                if not re.fullmatch(r"C\d+", cid):
                    problems.append(f"{label} {role} '{cid}' is not a C-id")
        if mr.payload and not re.fullmatch(r"E\d+", mr.payload):
            problems.append(f"{label} payload '{mr.payload}' is not an E-id")
        d = deps_by_id.get(mr.broker)
        if d is not None:
            dk = grammar.classify_dep(d.kind or "", d.type)
            if dk in grammar.DEP_KINDS_FOLDED:
                problems.append(f"{label} broker {mr.broker} ({d.name}) classifies as a folded "
                                "framework/library — a channel lives on a real bus/store dep")
            elif dk not in ("messaging", "datastore"):
                warnings.append(f"{label}: broker {mr.broker} ({d.name}) classifies as '{dk}', "
                                "not messaging/datastore — is this really where the channel lives?")
            for role, ids in (("publisher", mr.publishers), ("consumer", mr.consumers)):
                unbacked = [c for c in ids if (c, mr.broker) not in edge_pairs]
                if unbacked:
                    warnings.append(
                        f"{label}: {role}(s) {', '.join(unbacked)} carry no backbone edge to "
                        f"{mr.broker} — the diagrams and impact ripple only walk edges, so this "
                        "participation is invisible to both; author the C→broker edge")
        # A one-sided row is a claim with a hole in it, and the hole is INVISIBLE in every view: the
        # Deployment view composes its process→process arrows from publishers × consumers (each
        # resolved through `runs_in`), so a row missing either side silently produces no arrow at
        # all. On a live map 5 of 25 channels were one-sided; the traffic then showed up only as a
        # link to the broker box, which says "this process uses Redis" but not who it is talking to.
        # Advisory, not blocking: a channel whose other end lives OUTSIDE the mapped repo (an
        # external publisher, a third-party consumer) is legitimately one-sided — it just has to be
        # a decision rather than an omission.
        missing = _messaging_missing_sides(mr)
        if missing and "channel-ends" not in excepted:
            warnings.append(
                f"{label}: no {' and no '.join(missing)} recorded — the Deployment view "
                "composes process→process arrows from publishers × consumers, so this channel "
                "draws none and its traffic shows only as a link to the broker. Record the "
                "missing side, model an out-of-repo end as a dep, or record the literal "
                "`channel-ends` under a 'Balance exceptions' extras heading when the far ends "
                "genuinely live outside the mapped repo")
    return problems, warnings


def _messaging_missing_sides(mr: MessagingRow) -> list[str]:
    """The participant side(s) a channel row leaves empty. Shared by the one-sided-channel advisory
    (which OWNS that shape) and by `_messaging_placement_warnings` (which must skip it): a row with
    a hole on one side has no placement question to answer yet, and reporting both would bill one
    gap twice under two different escapes."""
    return [r for r, ids in (("publishers", mr.publishers), ("consumers", mr.consumers)) if not ids]


def _messaging_placement_warnings(m: ProjectModel) -> list[str]:
    """Advisory: both channel sides are named, but the Deployment view still cannot place the
    channel — no participant says which process runs it, so the row draws no process→process arrow.
    Same invisible outcome as a one-sided row, different cause, so a different fix (tag `runs_in`)
    and a different owner than `_check_messaging`.

    A `runs_in`-tagging gap wearing a messaging hat: it answers to the recorded `runs-in/messaging` literal
    like every other `runs_in` advisory, which is why it is produced RAW here and routed through
    `_runs_in_family_warnings` — the one place that applies (and counts) that literal."""
    if not m.deployment:
        return []                        # no process boxes at all → no topology to be missing
    out: list[str] = []
    for i, mr in enumerate(m.messaging):
        if _messaging_missing_sides(mr):
            continue                     # one-sided → `_check_messaging` owns it
        placed = {r: [c for c in ids if _runs_in_of(m, c)]
                  for r, ids in (("publisher", mr.publishers), ("consumer", mr.consumers))}
        unplaced = [r for r, ids in placed.items() if not ids]
        if unplaced:
            out.append(
                f"messaging[{i}] ('{mr.name}'): no {' and no '.join(unplaced)} sets `runs_in`, so "
                "the Deployment view cannot place this channel and draws no process→process arrow "
                "— tag the participating component(s) with the unit whose process runs them, or "
                "record the literal `runs-in/messaging` under a 'Balance exceptions' extras heading (the "
                "same literal that adjudicates the rest of this map's `runs_in` tagging)")
    return out


def _runs_in_of(m: ProjectModel, cid: str) -> list[str]:
    """The units a component id runs in ([] when unknown or untagged)."""
    for c in m.components:
        if c.id == cid:
            return list(c.runs_in or [])
    return []


_PAYLOAD_CANARY_MIN = 3   # below this, an all-empty column is too weak to read as a gap


def _messaging_payload_warnings(m: ProjectModel) -> list[str]:
    """ADVISORY: a catalog where NO channel names a payload, on a map that has entities.

    `payload: ""` means "untyped / carries no domain entity" — a positive claim, not a blank. One
    channel legitimately making it is unremarkable; EVERY channel making it is the signature of a
    field nobody filled, which is the same shape the method already records for two other columns
    (three rebuilds shipped rich broker edges with an empty catalog; two shipped `dep: null` on every
    entity, silently disabling the persistence-coverage rule). Measured on a live map: 25 of 25
    channels claimed no payload — including `shard.events`, `job_queue` and `analytics_events` —
    with 134 entities available to reference. Deliberately fires only on the ALL-empty case, so a
    map that types most of its channels and leaves a couple genuinely untyped stays quiet.

    "Confirm they really are untyped" is a judgement, and a judgement with nowhere to live re-fires
    at every validate — so the confirmation is recordable: the literal `channel-payload`,
    line-leading under a 'Balance exceptions' extras heading. Its own literal rather than the
    catalog-level `messaging` one, because the two say different things (`messaging` = there are no
    nameable channels at all; `channel-payload` = the channels exist and carry no domain type)."""
    if len(m.messaging) < _PAYLOAD_CANARY_MIN or not m.entities:
        return []
    if any(c.payload for c in m.messaging):
        return []
    if "channel-payload" in balance_lib._exceptions(m):
        return []
    return [f"None of the {len(m.messaging)} messaging channel(s) names a `payload`, on a map with "
            f"{len(m.entities)} entities — an empty payload CLAIMS the channel carries no domain "
            f"type, so an unfilled column reads as {len(m.messaging)} untyped channels. Name the "
            f"entity each message carries, or record the literal `channel-payload` under a "
            f"'Balance exceptions' extras heading if they really are untyped"]


def _messaging_gap_warnings(m: ProjectModel) -> list[str]:
    """The async-catalog canary (advisory, ONE aggregated line): three live rebuilds shipped
    `messaging: []` while their edges plainly showed a bus in use (one map had 20 emit + 13
    listen edges into its Redis broker and ~8 nameable channels). The row-local messaging rules
    only fire when rows EXIST — this canary fires on the absence: emit/listen-family C→D edges
    into a messaging- OR datastore-kind dep (a Redis authored as datastore routinely doubles as
    the bus — a live map's pub/sub rode exactly that) with an EMPTY catalog. Service/platform deps
    are excluded: `emits Sentry` / `emits StatsD` is observability, not a channel. Escape = the
    literal `messaging` (line-leading) under a 'Balance exceptions' extras heading (a bus used
    only through an abstraction with genuinely no nameable channels)."""
    if m.messaging or not m.edges:
        return []
    deps_by_id = {d.id: d for d in m.deps}
    bus_edges: list[str] = []
    for e in m.edges:
        v = e.verb.strip().lower()
        if not (e.src.startswith("C") and e.dst.startswith("D")):
            continue
        if v not in grammar.EMIT_VERBS and v not in grammar.LISTEN_VERBS:
            continue
        d = deps_by_id.get(e.dst)
        if d is not None and grammar.classify_dep(d.kind or "", d.type) in ("messaging", "datastore"):
            bus_edges.append(f"{e.src} {e.verb} {e.dst}")
    if not bus_edges:
        return []
    if "messaging" in balance_lib._exceptions(m):
        return []
    shown = _shown(bus_edges, 6)
    return [f"{len(bus_edges)} emit/listen edge(s) touch a messaging dep ({shown}) but the "
            "`messaging` catalog is empty — name the channels/queues (one row each: name, broker, "
            "publishers, consumers, payload), or record the literal `messaging` under a "
            "'Balance exceptions' extras heading"]


ISOLATED_COMPONENT_SHOWN = 8       # ids listed inline before the "+N more" tail

def _isolated_component_warnings(m: ProjectModel) -> list[str]:
    """The disconnected-code canary (advisory, ONE aggregated line): components that appear in NO
    backbone edge (either end) and in NO `messaging` row (publisher or consumer).

    Every derived view walks edges and channels — the Subsystems arrows, the change-impact ripple, and
    the Deployment view's process→process topology (both its async and its synchronous half). A
    component wired to nothing is therefore invisible in all of them, however well its `Purpose` prose
    describes what it talks to. This canary was added after a live map's custom-shard fleet drew no
    arrow to the bot it demonstrably feeds: its purpose text said "pushes their events to the same
    broker", but neither an edge nor a channel row recorded it, so nothing could be drawn.

    Advisory and aggregated on purpose: a real map carries some genuinely standalone code (a leaf
    utility, a plugin nothing else calls), and a per-component warning at this rate would be noise
    nobody reads. Escape = the literal `isolated` (line-leading) under a 'Balance exceptions' extras
    heading, for a map whose components legitimately stand alone."""
    if not m.components:
        return []
    wired: set[str] = set()
    for e in m.edges:
        wired.add(e.src)
        wired.add(e.dst)
    for mr in m.messaging:
        wired.update(mr.publishers)
        wired.update(mr.consumers)
    isolated = [c for c in m.components if c.id not in wired]
    if not isolated:
        return []
    if "isolated" in balance_lib._exceptions(m):
        return []
    shown = _shown([f"{c.id} ({c.name})" for c in isolated], ISOLATED_COMPONENT_SHOWN)
    return [f"{len(isolated)} of {len(m.components)} component(s) carry no backbone edge and no "
            f"`messaging` role: {shown} — every view walks "
            "edges and channels, so these are drawn connected to nothing (a relationship stated only "
            "in `Purpose` prose is invisible). Author the edge, or add the component as a channel "
            "publisher/consumer; record the literal `isolated` under a 'Balance exceptions' extras "
            "heading for code that genuinely stands alone"]


_GROUNDING_THIN = 0.60   # below this share of the claim surface, say so out loud


def _any_grounding_count(g: Grounding) -> bool:
    """Whether the record carries any number at all — the gate for every check below.

    Gating on `claims_challenged > 0` was wrong: a record of `total 42, challenged 0, confirmed 39,
    refuted 3` — 42 verdicts against 0 challenges — slipped past the arithmetic entirely."""
    # The pin-delta fields are here too: a record carrying ONLY `claims_added_since: 4` would
    # otherwise skip every check below, which is the same shape of hole this function was written
    # to close.
    return bool(g.claims_total or g.claims_challenged or g.claims_confirmed
                or g.claims_refuted or g.claims_unverifiable
                or g.claims_superseded or g.claims_added_since or g.live_claims_digest)


def _grounding_split_sum(g: Grounding) -> int:
    return g.claims_confirmed + g.claims_refuted + g.claims_unverifiable


def _grounding_split_recorded(g: Grounding) -> bool:
    """The split is COMPLETE: every challenged claim is attributed to exactly one outcome.

    Two earlier versions of this predicate were each wrong in one direction, and the shapes that
    caught them are worth stating because they look alike on paper:

      `challenged 5,   refuted 5`  → complete. Everything was refuted; nothing is missing.
      `challenged 399, refuted 3`  → the PRE-SPLIT format (`total/grounded/refuted`), where the other
                                     396 verdicts were simply never broken out.

    Both have `confirmed == unverifiable == 0`, so keying on "is confirmed or unverifiable set" called
    the first incomplete and nagged a correct record. Keying on "is the sum non-zero" called the second
    complete and BLOCKED a map written in the older format. Only the sum-versus-challenged comparison
    separates them."""
    return g.claims_challenged > 0 and _grounding_split_sum(g) == g.claims_challenged


def _grounding_split_attempted(g: Grounding) -> bool:
    """A split was attempted but does NOT add up — the genuinely broken case, as against the older
    format that simply never carried one. `confirmed`/`unverifiable` exist only in the new shape, and a
    sum ABOVE `challenged` cannot be an under-filled record."""
    return bool(g.claims_confirmed or g.claims_unverifiable
                or _grounding_split_sum(g) > g.claims_challenged)


def _grounding_warnings(m: ProjectModel) -> list[str]:
    """ADVISORY: how much of the L2 claim surface was actually GROUNDED — including "none".

    A map that never ran the grounding pass and a fully-challenged one are indistinguishable in
    every view and pass every gate identically. Since the refutation rate on challenged claims runs
    3-11% on live builds, silence here is the difference between "verified" and "plausible". Only
    ever advisory: grounding is a judgement about effort, never a well-formedness property."""
    g = m.grounding
    if g is None:
        claim_surface = len(l2_worklist_model(m))     # only needed for this message
        if claim_surface >= 20:
            return [f"No `grounding` record: this map's {claim_surface} L2 claims (the same worklist "
                    "`coyodex audit` builds) were never challenged by fresh-context skeptics, and "
                    "nothing in the map says so. Run the Phase-4 grounding pass, or record the "
                    "decision in `grounding` (claims_total/claims_challenged + the verdict split "
                    "confirmed/refuted/unverifiable + note)"]
        return []
    out: list[str] = []
    # The split check runs BEFORE (and independently of) the coverage share, which needs a non-zero
    # `claims_total`. Ordering it after a `claims_total <= 0` early return meant a record of
    # `{challenged: 42, refuted: 3}` with no total — the documented pre-split shape — produced NO
    # output at all: not this advisory, not the blocking check. Silence on a half-written record.
    out.extend(_grounding_split_findings(g))
    if g.claims_total > 0:
        # Coverage is measured on CONFIRMED claims once the split exists, never on "challenged". An
        # unverifiable verdict means the claim is NOT grounded (`eval`'s judge counts it the same way),
        # so counting it as coverage overstates by exactly the unverifiable count — and a map where
        # NOTHING could be verified (`challenged 42, confirmed 0, unverifiable 42`) summed correctly,
        # read as 100% coverage, and produced no finding at all.
        split = _grounding_split_recorded(g)
        grounded = g.claims_confirmed if split else g.claims_challenged
        basis = "confirmed" if split else "challenged"
        share = grounded / g.claims_total
        if share < _GROUNDING_THIN:
            unv = (f", {g.claims_unverifiable} unverifiable (NOT grounded — the code could not settle "
                   f"them either way)" if g.claims_unverifiable else "")
            out.append(f"Grounding is partial: {grounded} of {g.claims_total} claims {basis} "
                       f"({share:.0%}), {g.claims_refuted} refuted{unv}. At that refutation rate the "
                       f"{g.claims_total - grounded} remaining claims are good leads, not facts — say "
                       "which claims were prioritized in `grounding.note`"
                       + ("" if g.note else " (currently empty)"))
    return out


def _grounding_split_findings(g: Grounding) -> list[str]:
    """ADVISORY: the verdict split is absent, so nothing can be checked against it.

    Separate from the blocking arithmetic check (`_check_grounding_arithmetic`) because the two say
    different things. This one fires when a map records only "N challenged" — the shape that let a
    live map claim `total 399, grounded 399, refuted 3` and read as "399 held up AND 3 were refuted".
    Without the split there is no sum to verify, so the record cannot be wrong and cannot be right."""
    if (not _any_grounding_count(g) or _grounding_split_recorded(g)
            or _grounding_split_attempted(g)):
        return []       # complete, or broken-and-blocking — neither wants this nudge
    return [f"`grounding` records {g.claims_challenged} challenged claim(s) but no verdict SPLIT — "
            f"add `claims_confirmed` / `claims_refuted` / `claims_unverifiable`. Without them "
            f"'challenged' is the only number, so a reader cannot tell how many claims actually HELD "
            f"UP, and the arithmetic `confirmed + refuted + unverifiable == challenged` has nothing "
            f"to check. An unverifiable verdict is a real outcome — record it rather than folding it "
            f"into either of the others."]


def _check_grounding_arithmetic(m: ProjectModel) -> list[str]:
    """BLOCKING: the recorded grounding counts must add up, and must be counts.

    Blocking, not advisory, because this is arithmetic on the map's own numbers — there is no judgement
    to defer to and no repo to re-read. A record that does not add up is malformed, in the one field
    whose entire job is telling a reader how much of the map was actually verified.

    The version this replaces asserted `refuted <= challenged <= total`, an inequality that PASSED on
    the very map that motivated it (3 <= 399 <= 399) and therefore checked nothing."""
    g = m.grounding
    if g is None or not _any_grounding_count(g):
        return []
    problems: list[str] = []
    negatives = {name: val for name, val in (
        ("claims_total", g.claims_total), ("claims_challenged", g.claims_challenged),
        ("claims_confirmed", g.claims_confirmed), ("claims_refuted", g.claims_refuted),
        ("claims_unverifiable", g.claims_unverifiable),
        ("claims_superseded", g.claims_superseded),
        ("claims_added_since", g.claims_added_since)) if val < 0}
    if negatives:
        # A negative count can BALANCE the equality below (confirmed 13 + refuted -3 == challenged 10),
        # so the sum check alone does not make the record meaningful.
        problems.append(f"`grounding` has negative count(s): "
                        f"{', '.join(f'{k}={v}' for k, v in sorted(negatives.items()))} — these are "
                        f"tallies of claims, so every one is zero or more.")
    if g.claims_superseded > g.claims_total:
        # Bounded by TOTAL, not by `challenged`. A superseded claim is one that was PINNED and then
        # rewritten away; whether it also got a verdict is a different question. The two are equal
        # today only because `grounding write` refuses an unvoted pinned claim, and its own error
        # message already offers "challenge a smaller worklist deliberately" as the way out — so a
        # record of total 100 / challenged 50 with 60 claims reconciled away is legitimate, and
        # bounding by `challenged` would block it for being correct.
        problems.append(f"`grounding` records {g.claims_superseded} superseded claim(s) against a "
                        f"pinned worklist of {g.claims_total} — a superseded claim is one that WAS "
                        f"pinned, so this cannot exceed `claims_total`.")
    if _grounding_split_attempted(g):
        split = _grounding_split_sum(g)
        if split != g.claims_challenged:
            problems.append(f"`grounding` counts do not add up: confirmed {g.claims_confirmed} + "
                            f"refuted {g.claims_refuted} + unverifiable {g.claims_unverifiable} = "
                            f"{split}, but claims_challenged is {g.claims_challenged}. Every "
                            f"challenged claim came back as exactly one of the three, so the split "
                            f"must equal it — correct whichever count is wrong (a verdict silently "
                            f"dropped from the tally is the usual cause).")
    if g.claims_total > 0 and g.claims_challenged > g.claims_total:
        problems.append(f"`grounding` claims_challenged ({g.claims_challenged}) exceeds claims_total "
                        f"({g.claims_total}) — you cannot challenge more claims than the worklist "
                        f"held. `claims_total` is the audit worklist size at grounding time; re-read "
                        f"it with `coyodex audit --json`.")
    return problems


def _inheritance_runs_in_warnings(m: ProjectModel) -> list[str]:
    """ADVISORY: a base class not tagged to run where its SUBCLASS runs.

    A hard invariant of the code, checkable with no code reading: a subclass cannot exist in a
    process that does not load its base class, so for an `extends`/`implements` edge the source's
    host units must be a SUBSET of the target's. A gap means the base's `runs_in` is incomplete —
    which is not cosmetic, because the Deployment view composes process topology from `runs_in`
    differences. A live map tagged a shared connector framework with eight scraper units but omitted
    a ninth whose plugin extends it, and that one missing tag drew eight false arrows from that
    plugin's process to all its siblings.

    THE SUBCLASS'S OWN PLACEMENT IS THE ONLY GUARD. The check fires when the subclass runs
    somewhere and the base is not tagged there — INCLUDING the base tagged nowhere at all, which
    is the state a real build actually produces: the subclass owns a directory and gets tagged,
    the abstract base sits in a shared module and is forgotten. Requiring the base to be tagged
    somewhere before checking it (the earlier `if not src or not dst`) inverted the rule — it
    reported the half-done job and stayed silent on the un-started one.

    That single guard is also what keeps the two no-op maps quiet, with no separate special case:
    a map with no `deployment[]` units has no unit any `runs_in` can resolve against (returned
    empty above), and a map that uses `runs_in` NOWHERE gives every subclass an empty host set, so
    no pair is ever reached. Placement is only checkable against a map that places things.

    The two states get DIFFERENT text because the remedy differs. A partially-tagged base needs a
    unit ADDED; a wholly-untagged base needs to be tagged at all, and until it is, it belongs to no
    process box in the Deployment view — the unit that runs the subclass is drawn holding half the
    code it loads."""
    units = {d.unit for d in m.deployment}
    if not units:
        return []
    host = {c.id: {u for u in (c.runs_in or []) if u in units} for c in m.components}
    names = {c.id: c.name for c in m.components}
    out: list[str] = []
    for e in m.edges:
        if e.verb not in ("extends", "implements"):
            continue
        src, dst = host.get(e.src), host.get(e.dst)
        if src is None or dst is None:      # an endpoint that is not a component: no `runs_in`
            continue
        if not src:                         # the SUBCLASS runs nowhere — nothing to place it under
            continue
        missing = src - dst
        if not missing:
            continue
        if dst:
            out.append(
                f"{e.dst} ({names.get(e.dst, e.dst)}) is {e.verb.rstrip('s')}ed by {e.src} "
                f"({names.get(e.src, e.src)}), which runs in {', '.join(sorted(missing))} — but "
                f"{e.dst} is not tagged to run there. A base cannot be absent from a process that "
                f"loads its subclass: add the unit(s) to {e.dst}'s `runs_in`")
        else:
            out.append(
                f"{e.dst} ({names.get(e.dst, e.dst)}) is {e.verb.rstrip('s')}ed by {e.src} "
                f"({names.get(e.src, e.src)}), which runs in {', '.join(sorted(missing))} — but "
                f"{e.dst} sets no `runs_in` at all, so it lands in no process box while its "
                f"subclass lands in one. A base cannot be absent from a process that loads its "
                f"subclass: give {e.dst} a `runs_in` — those unit(s) at minimum")
    return out


def _check_states(m: ProjectModel) -> tuple[list[str], list[str]]:
    """State-machine well-formedness (row-local — safe per-fragment). Blocking: an empty `states`
    list (a machine with no states claims nothing), duplicate state names, a transition endpoint
    not declared in `states` (the diagram would draw an orphan box). Advisory: a machine citing no
    `source` (inferred — cite the enum/constants/dispatch line, aggregated); a state with no
    transition in or out while OTHER transitions exist (isolated — a typo'd name usually)."""
    problems: list[str] = []
    warnings: list[str] = []
    inferred: list[str] = []
    for el in (*m.entities, *m.components):
        sm = el.states
        if sm is None:
            continue
        label = f"{el.id} states"
        names = [s.strip() for s in sm.states]
        if not names or not any(names):
            problems.append(f"{label}: empty state list — name the states, or drop the machine")
            continue
        dups = sorted({n for n in names if names.count(n) > 1})
        if dups:
            problems.append(f"{label}: duplicate state name(s): {', '.join(dups)}")
        declared = set(names)
        touched: set[str] = set()
        for t in sm.transitions:
            for end in (t.src, t.dst):
                if end not in declared:
                    problems.append(f"{label}: transition endpoint '{end}' is not a declared "
                                    f"state (states: {', '.join(names)})")
                else:
                    touched.add(end)
        if sm.transitions:
            isolated = sorted(declared - touched)
            if isolated:
                warnings.append(f"{label}: state(s) with no transition in or out: "
                                f"{', '.join(isolated)} — a typo'd name, or a state worth wiring")
        if not sm.source.strip():
            inferred.append(el.id)
    if inferred:
        warnings.append(
            f"{len(inferred)} state machine(s) cite no `source` ({_shown(inferred, 8)}"
            f") — inferred; anchor the line DECLARING the "
            "states (the enum / status constants / dispatch table)")
    return problems, warnings


_STORE_DEP_SHAPE = re.compile(r"^D\d+$")


def _check_stores(m: ProjectModel) -> list[str]:
    """Structured-store shape rules (blocking, row-local — safe per-fragment): `store.dep` is a
    D-id; `store.mode` is the closed `grammar.STORE_MODES` vocabulary (EXACT match, the
    `activation` discipline — a near-miss like 'Collection' would silently escape every
    mode-driven grouping); a resolvable `dep` must be a real store (datastore/messaging/…), never
    a folded framework/library (a wrapper module is not where data lives). Resolution itself rides
    `_check_references` via `_referenced_ids`."""
    problems: list[str] = []
    deps_by_id = {d.id: d for d in m.deps}
    for e in m.entities:
        st = e.store
        if st is None:
            continue
        if st.dep and not _STORE_DEP_SHAPE.match(st.dep):
            problems.append(f"{e.id} store.dep '{st.dep}' is not a D-id — name the physical "
                            "datastore dep (e.g. D1), not a prose store name")
        if st.mode and st.mode not in grammar.STORE_MODES:
            problems.append(f"{e.id} store.mode '{st.mode}' is invalid — use one of: "
                            f"{', '.join(grammar.STORE_MODES)}, or leave it empty")
        d = deps_by_id.get(st.dep or "")
        if d is not None and grammar.classify_dep(d.kind or "", d.type) in grammar.DEP_KINDS_FOLDED:
            problems.append(f"{e.id} store.dep {st.dep} ({d.name}) classifies as a folded "
                            "framework/library — data lives in a datastore/messaging/service/"
                            "platform dep, never in an in-process library (name the real store)")
    return problems


def unexplained_persistence_pairs(m: ProjectModel) -> list[tuple[str, str, Dep]]:
    """The shared core of the persistence-coverage rule (reused by the validator's warning and the
    viewer's Data-view coverage strip, so the two can never disagree): the deduped,
    exception-filtered, adoption-gated list of write-family `C→D` edges into a store-shaped dep
    (datastore/messaging) that NO entity's structured store explains — directly, or through the
    writing component as a one-hop store ADAPTER (`C1 persists C30`, and C30 carries the physical
    `writes D1` — the layered-architecture shape a live rebuild false-positived on).

    Returns `(component_id, lowercased_verb, dep)` triples in first-seen edge order, one per unique
    `(src, dst)` pair. Empty when no entity has structured its store (`store.dep` set) — the
    adoption gate. `Cn` ids recorded under a 'Persistence exceptions' extras heading are filtered out
    (the operator's escape for an infra-only writer); the same heading's `En` lines answer the
    mirror advisory in `validate_model` (an entity no component owns), and the two never collide —
    each reader filters by its own id prefix. The verb is lowercased and the `Dep` object is
    returned (its `.id == component's edge dst`) so the validator's warning stays byte-identical."""
    pairs: list[tuple[str, str, Dep]] = []
    write_verbs = grammar.PERSIST_VERBS | grammar.WRITE_VERBS
    structured = [e for e in m.entities if e.store and e.store.dep]
    if not structured:
        return pairs
    deps_by_id = {d.id: d for d in m.deps}
    excepted = _recorded_ids(m, "persistence exceptions", ("C",))
    entities_of_dep: dict[str, set[str]] = {}
    for e in structured:
        entities_of_dep.setdefault(e.store.dep, set()).add(e.id)  # type: ignore[union-attr]
    writers_of_entity: dict[str, set[str]] = {}
    writers_into_component: dict[str, set[str]] = {}  # C -> components with a write-family edge INTO it
    for ed in m.edges:
        if ed.src.startswith("C") and ed.verb.strip().lower() in write_verbs:
            if ed.dst.startswith("E"):
                writers_of_entity.setdefault(ed.dst, set()).add(ed.src)
            elif ed.dst.startswith("C"):
                writers_into_component.setdefault(ed.dst, set()).add(ed.src)
    seen_pairs: set[tuple[str, str]] = set()
    for ed in m.edges:
        verb = ed.verb.strip().lower()
        if not (ed.src.startswith("C") and ed.dst.startswith("D") and verb in write_verbs):
            continue
        d = deps_by_id.get(ed.dst)
        if d is None or grammar.classify_dep(d.kind or "", d.type) not in ("datastore", "messaging"):
            continue
        if ed.src in excepted or (ed.src, ed.dst) in seen_pairs:
            continue
        seen_pairs.add((ed.src, ed.dst))
        dep_owner_ids = {cid for eid in entities_of_dep.get(ed.dst, set())
                        for cid in writers_of_entity.get(eid, set())}
        # Explained when the writing component itself owns an entity stored in this dep, OR — the
        # layered-architecture case a live rebuild false-positived on — when it is a store ADAPTER:
        # some entity-owning service has a write-family edge INTO it. One hop, write-family only.
        explained = (ed.src in dep_owner_ids
                     or bool(dep_owner_ids & writers_into_component.get(ed.src, set())))
        if not explained:
            pairs.append((ed.src, verb, d))
    return pairs


def _persistence_coverage_warnings(m: ProjectModel) -> list[str]:
    """The persistence-coverage rule (advisory, ADOPTION-GATED): once any entity structures its
    store (`store.dep` set), every write-family `C→D` edge into a store-shaped dep must be
    EXPLAINED — some entity records that dep as its store AND that component writes the entity.
    An unexplained pair is exactly how real collections escaped the map (a live build persisted
    OAuth-token and lock collections that appeared nowhere in the domain model, because they had
    no named type). Escape: the C id recorded under a **'Persistence exceptions'** extras heading
    (an infra-only writer — a lock, a migration, a schema-hash doc — adjudicated by the operator).
    A second aggregated nudge lists entities still carrying an UNSTRUCTURED store (notes-only);
    the literal `store` under 'Balance exceptions' silences that one."""
    warnings: list[str] = []
    for src, verb, d in unexplained_persistence_pairs(m):
        warnings.append(
            f"{src} {verb} into {d.id} ({d.name}) but no entity both records {d.id} "
            f"as its store AND is written by {src} (directly, or through it as a store "
            "adapter) — a real container may be missing from the domain model (the "
            "unmodeled-collection class); add the entity (with its structured store), or "
            f"record '{src}: <why>' under a 'Persistence exceptions' extras heading")
    # Store-hygiene family (one aggregated nudge each; escape = the literal `store`, line-leading,
    # under 'Balance exceptions'):
    #  * notes-only stores (no dep, no mode) — fully unstructured;
    #  * a CONTAINER named but no `dep` linked — the live-rebuild failure mode: the T5 agent ran
    #    without the deps legend, wrote `dep: null` on every row, and the coverage rule above
    #    (adoption-gated on `dep`) silently never engaged. Modes that legitimately have no dep
    #    (embedded rides its parent; transient/in-code/enum live nowhere) are exempt.
    # The `store` literal guards THREE distinct findings, so — exactly like `runs-in` — they are
    # gathered RAW and the escape is applied once, with a count. A record written about one of them
    # silences the other two, and a suppression you cannot see is indistinguishable from having no
    # findings (the failure this codebase keeps re-learning: see `_runs_in_family_warnings`).
    hygiene: list[tuple[str, str]] = []   # (group label for the count line, warning text)
    unstructured = [e.id for e in m.entities
                    if e.store is not None and not e.store.dep and not e.store.mode]
    if unstructured:
        hygiene.append((
            "unstructured (notes-only) stores",
            f"{len(unstructured)} entity store(s) are unstructured (notes-only: "
            f"{_shown(unstructured, 8)}) — set "
            "`store.dep`/`container`/`mode` so persistence is queryable, or record the literal "
            "`store` under a 'Balance exceptions' extras heading (which silences the WHOLE store "
            "family, not just this one)"))
    deplinkable = [e.id for e in m.entities
                   if e.store is not None and not e.store.dep and e.store.container
                   and e.store.mode in ("collection", "cache")]
    if deplinkable:
        hygiene.append((
            "a container named but no `dep` linked",
            f"{len(deplinkable)} entity store(s) name a container but link no `dep` "
            f"({_shown(deplinkable, 8)}) — the "
            "persistence-coverage rule can't engage without the D-id; link `store.dep` to the "
            "datastore dep (give the domain agent the deps legend, or backfill at synthesis), "
            "or record the literal `store` under a 'Balance exceptions' extras heading (which "
            "silences the WHOLE store family, not just this one)"))
        #  * a container that reads as PROSE, not a name — the live-map failure this caught: a map
        #    recorded `memberships subscriptions` where the code says
        #    `__collection__ = "memberships_subscriptions"`, and `character features` / `rank card
        #    configs` for their real snake_case collections. The agent described the compartment
        #    instead of naming it, which makes the container unusable for the thing it exists for:
        #    finding the real collection. A space is the tell — real container names (collections,
        #    tables, buckets, key prefixes) don't carry one. Only the modes whose container IS a
        #    physical name are checked: `transient`/`in-code`/`enum` legitimately describe ("derived",
        #    "Chargebee API") and `embedded` rides its parent, so none of them can trip this.
    prose = [e.id for e in m.entities
             if e.store is not None and e.store.mode in ("collection", "cache")
             and " " in (e.store.container or "").strip()]
    if prose:
        hygiene.append((
            "a container that reads as prose, not a name",
            f"{len(prose)} entity store(s) name a container that reads as prose, not a name "
            f"({_shown(prose, 8)}) — `container` is the "
            "LITERAL compartment name (`memberships_subscriptions`), not a description of it "
            "('memberships subscriptions'); a name with a space in it is almost never the real "
            "one, and a reader can't find the collection from a paraphrase. Correct the rows "
            "against the code, or record the literal `store` under a 'Balance exceptions' "
            "extras heading (which silences the WHOLE store family, not just this one)"))
    if "store" not in balance_lib._exceptions(m):
        warnings.extend(text for _label, text in hygiene)
    elif hygiene:
        # Suppressed, but never silently — name every group the one literal swallowed, so a record
        # written about one of them cannot hide the other two.
        warnings.append(
            f"{len(hygiene)} store-hygiene advisory/advisories suppressed by the recorded `store` "
            f"exception — {'; '.join(label for label, _t in hygiene)}. That one literal silences "
            "EVERY store-hygiene finding, not just the one it was written about; if the "
            "justification only covered one, re-read the rest by validating a copy without it.")
    return warnings


def _check_group_tech(m: ProjectModel) -> tuple[list[str], list[str]]:
    """`tech` is a SUBSYSTEM field (one honest stack label off the manifests). The `Group`
    dataclass backs both forests, so nothing structural stops a subdomain from carrying one — but
    a bounded context has no stack, and letting it through would seed a parallel, contradictable
    tech axis on the domain side. Blocking: cheap and unambiguous to fix (drop it or move it to
    the owning subsystem). Advisory: a subsystem citing a `tech_source` with no `tech` label — the
    anchor is existence-checked yet labels nothing (review #7)."""
    problems = [f"{sd.id} carries `tech` ('{(sd.tech or sd.tech_source).strip()}') — tech is a "
                "subsystem field (a bounded context has no stack); drop it, or move it to the "
                "subsystem that implements this subdomain"
                for sd in m.subdomains
                if (sd.tech or "").strip() or (sd.tech_source or "").strip()]
    warnings = [f"{s.id} cites a `tech_source` but records no `tech` — the anchor labels "
                "nothing; author the tech label, or drop the anchor"
                for s in m.subsystems
                if (s.tech_source or "").strip() and not (s.tech or "").strip()]
    # A capability groups USE CASES and a block groups DECISIONS, so neither has a stack — same
    # argument as the subdomain. One `Group` dataclass now backs FOUR forests: every per-kind guard
    # here must enumerate all four, or the field it refuses is simply legal in the forest it forgot.
    problems += [f"{c.id} carries `tech` ('{(c.tech or c.tech_source).strip()}') — tech is a "
                 f"subsystem field; a {kind} groups {what}, not code"
                 for arr, kind, what in ((m.capabilities, "capability", "use cases"),
                                         (m.blocks, "block", "decisions"))
                 for c in arr
                 if (c.tech or "").strip() or (c.tech_source or "").strip()]
    return problems, warnings


def _check_group_label(m: ProjectModel) -> list[str]:
    """`label` (core | supporting | platform) is a CAPABILITY field, and the mirror of
    `_check_group_tech`: one `Group` dataclass backs FOUR forests, so nothing structural stops a
    subsystem, a subdomain or a block from carrying one.

    Blocking on the wrong forest is the point. The label is an authored judgement about USE CASES —
    it is what lets the Happy-Path rule ask "does every core capability reach the walk?" instead of
    demanding a written record per off-spine use case. On a subsystem it would read as a claim that
    some CODE is platform machinery, and nothing derives or checks such a claim: the touch-count
    primitive says which elements a capability reaches, never whether a component is machinery
    (measured on the reference map, the maximum spread was 4 capabilities of 7 — no threshold
    separates the two, which is why that classification was dropped rather than tuned). An
    unbacked label on the structural side would be exactly the parallel, contradictable axis the
    `tech`-on-a-subdomain rule already refuses."""
    problems = [f"{g.id} carries `label` ('{g.label.strip()}') — label is a capability field "
                f"(an authored judgement about use cases); drop it from this {kind}"
                for arr, kind in ((m.subsystems, "subsystem"), (m.subdomains, "subdomain"),
                                  (m.blocks, "block"))
                for g in arr if (g.label or "").strip()]
    problems += [f"{c.id} has an unknown `label` '{c.label.strip()}' — one of "
                 f"{', '.join(grammar.CAP_LABELS)}"
                 for c in m.capabilities
                 if (c.label or "").strip() and c.label.strip().lower() not in grammar.CAP_LABELS]
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
        bad = [v.env for v in d.variants if v.env not in valid]
        if bad:
            problems.append(f"deployment[{i}] ('{d.unit}') variants name undeclared environment(s): "
                            f"{', '.join(bad)} — each must match a `environments` entry"
                            + ("" if valid else " (and no `environments` are declared)"))
    return problems


def system_dep_names(m: ProjectModel) -> list[str]:
    """Names of the deps that are real SYSTEM infrastructure (a bus, a store, a proxy).

    A deployment unit that matches one of these hosts no first-party code BY NATURE — a `mongo` or
    `nginx` box is expected to be empty — which is why two checks here and one gate in
    `coyodex-eval` all need the same list."""
    return [d.name for d in m.deps
            if grammar.classify_dep(d.kind or "", d.type) in grammar.DEP_KINDS_SYSTEM]


def orphan_deployment_units(m: ProjectModel) -> list[str]:
    """Deployment units that run no traced component or entry point AND are not system infra.

    These are the genuinely EMPTY boxes in the Deployment view: a unit the map declares, draws, and
    then puts nothing in, with no infrastructure story to explain it.

    Public because `coyodex-eval`'s deployment gate needs exactly this number and had been counting
    something else. It compared linked units as an absolute count, so a map that ENRICHED its
    deployment section — naming the proxy, the two datastores, the log forwarder and the test
    doubles alongside the three real runtimes — read as a linkage drop (4/4 → 3/11) and failed the
    gate, while the section it was judging had got strictly more accurate. Orphans answer the
    question the gate is actually asking, and they are what `validate` already advises on.

    **The `used` guard is part of the definition, not an optimisation.** A map that places nothing
    at all has not "orphaned" its units — it has not adopted `runs_in`, which is a different finding
    under a different recordable literal (`runs-in/unlinked`, `_deployment_unlinked_warning`).
    Without this guard the function reported every non-infra unit as an orphan on such a map while
    `validate` said nothing about them, so the gate failed a map its own tool had adjudicated — and
    the whole point of making this shared was that the two cannot drift apart."""
    if not (any(c.runs_in for c in m.components) or any(ep.runs_in for ep in m.entry_points)):
        return []
    hosted: set[str] = set()
    for c in m.components:
        hosted.update(c.runs_in)
    for ep in m.entry_points:
        hosted.update(ep.runs_in)
    dep_names = system_dep_names(m)
    return sorted({d.unit for d in m.deployment if d.unit and d.unit not in hosted
                   and not any(grammar.unit_name_matches_dep(d.unit, dn) for dn in dep_names)})


def _deployment_placement_warnings(m: ProjectModel) -> list[str]:
    """Advisory: once the map USES `runs_in` (the Deployment view is in play), a self-activated entry
    point with no host unit — neither its own `runs_in` nor its component's — is invisible in that view.
    Surface it (the same no-silent-no-op spirit as the completeness canaries), don't drop it. Silent
    when the map has no deployment units, or when `runs_in` is nowhere used yet (un-adopted, not a gap).

    It is a `runs_in` advisory that happens to sit outside `_deployment_quality_warnings_raw`'
    family, so it honours the SAME recorded `runs-in/entry-hosts` literal: an operator who has decided this
    map's background threads are not worth placing has decided it once, and should not have to keep
    re-reading the consequence. It is produced RAW here — the literal is applied (and counted)
    exactly once, in `_runs_in_family_warnings`. It used to be applied here with a silent `return []`,
    which is how a `runs-in/entry-hosts` record written about something else swallowed this finding invisibly
    on two live maps."""
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
    shown = _shown(unplaced, 8)
    return [f"{len(unplaced)} self-started entry point(s) have no deployment unit and will be "
            f"'Unplaced' in the Deployment view — tag `runs_in` on them or their component, or "
            f"record the literal `runs-in/entry-hosts` under a 'Balance exceptions' extras heading if these "
            f"threads are deliberately unplaced: {shown}"]


def _deployment_unlinked_warning(m: ProjectModel) -> list[str]:
    """Advisory: deployment units were harvested but NOTHING links code to them — every component's
    and entry point's `runs_in` is empty. The Deployment view then renders with zero code↔process
    mapping (its whole point). `_deployment_placement_warnings` stays silent on this case ('un-adopted,
    not a gap'), so without this canary a build ships an empty Deployment view with no signal at all —
    exactly what happened on both fresh builds this check was added for. Fires only when units exist:
    no `deployment[]` means the dimension was legitimately not harvested (a different, coarser choice).

    Raw, like its siblings: the recorded `runs-in/unlinked` literal (deliberately unmapped — everything runs
    in one unit) is applied and COUNTED once, in `_runs_in_family_warnings`.

    The all-or-nothing test below leaves a graded hole, so a second, weaker canary follows it: ONE
    tagged component out of eighty-six satisfies `any(...)` and buys silence for the other eighty-five,
    and the Deployment view is then 99% empty with no signal at all — the same failure this check was
    written for, one component short of triggering it. `_deployment_mostly_unplaced_warning` covers
    that. It is deliberately NOT the check a review proposed here (report that no ENTRY POINT carries
    `runs_in`): measured on two real maps, zero self-started entry points had an ambiguous or missing
    host, because every entry point inherits an unambiguous unit from its placed component, so that
    check would fire on both maps and on every well-built map — a noise generator, not a signal. The
    one real sub-case (a self-started entry point with no host at all) is already reported by
    `_deployment_placement_warnings`."""
    if not m.deployment:
        return []
    if any(c.runs_in for c in m.components) or any(ep.runs_in for ep in m.entry_points):
        return []
    return [f"{len(m.deployment)} deployment unit(s) enumerated but no component or entry point sets "
            f"`runs_in` — the Deployment view will have no code↔process mapping. On each component, "
            f"name the deployment unit(s) whose process runs it (method.md 'Deployment & topology'); "
            f"`runs` edges are then derived. If the code truly runs as one unit, record the literal "
            f"`runs-in/unlinked` under a 'Balance exceptions' extras heading to silence this."]


#: Below this share of components carrying `runs_in`, the Deployment view is mostly empty and says so.
#: Set well under the two reference maps (100% and 97% placed) so a real, near-complete map is silent;
#: the shape this catches is a token tagging of a handful of components, which the all-or-nothing
#: canary above cannot see because one tagged component satisfies its `any(...)`.
_RUNS_IN_PLACED_THIN = 0.60
#: …AND this many components must actually be unplaced. A share alone is meaningless on a small map:
#: 1-of-2 placed is 50% and reads as a finding, when the "gap" is a single component. The absolute
#: count is what makes the Deployment view empty, so both conditions must hold. Caught immediately by
#: an existing 2-component fixture, which the share-only version nagged.
_RUNS_IN_UNPLACED_MIN = 8


def _deployment_mostly_unplaced_warning(m: ProjectModel) -> list[str]:
    """Advisory: units exist and SOME component is placed, but most are not — the graded version of
    `_deployment_unlinked_warning`, whose `any(...)` early-return a single tagged component defeats.

    Same family as its siblings, so the recorded `runs-in/unplaced` literal silences it with them."""
    if not m.deployment or not m.components:
        return []
    placed = sum(1 for c in m.components if c.runs_in)
    # Defer to the all-or-nothing canary ONLY when it actually fires. It early-returns on
    # `any(c.runs_in) or any(ep.runs_in)`, so with zero components placed but one ENTRY POINT tagged
    # it stays silent — and an unconditional `placed == 0: return []` here left that case, the worst
    # one, reported by nobody.
    if placed == 0 and not any(ep.runs_in for ep in m.entry_points):
        return []
    unplaced = len(m.components) - placed
    share = placed / len(m.components)
    if share >= _RUNS_IN_PLACED_THIN or unplaced < _RUNS_IN_UNPLACED_MIN:
        return []
    return [f"only {placed} of {len(m.components)} component(s) set `runs_in` ({share:.0%}) across "
            f"{len(m.deployment)} deployment unit(s) — the Deployment view maps the other {unplaced} "
            f"to nothing. A partial tagging reads as a finished topology, so name the unit(s) for "
            f"those {unplaced}, or record the literal `runs-in/unplaced` under a 'Balance exceptions' extras "
            f"heading if they are deliberately unplaced."]


def _deployment_quality_warnings_raw(m: ProjectModel) -> list[str]:
    """Advisory: the Deployment view is only trustworthy if `runs_in` was GROUNDED (read off the deploy
    manifests), not formula-guessed. `validate` used to check only PRESENCE, so a hand-script that
    blanket-tagged every component to one unit (no manifest read, 0 entry points placed) passed clean.
    These four canaries catch the low-quality shapes — all in the deployment family, so the one recorded
    `runs-in/quality` literal silences them together (like `_deployment_unlinked_warning`):

    - non-atomic unit NAME (S5): a `deployment[].unit` holding a separator — one row is one process;
    - formula-fill (S3): one unit blankets EVERY component AND another unit hosts nothing AND no entry
      point carries `runs_in` — the exact co-occurrence a per-id-range guess leaves (a real all-in-one
      app trips none of the other two, so a legit monolith never nags);
    - unlinked unit: a unit hosting no component/entry point whose name matches no system dep;
    - ambiguous thread host: a self-started entry point whose component runs in >1 unit but which sets
      no `runs_in` of its own — the view then picks a host arbitrarily."""
    if not m.deployment:
        return []
    warnings: list[str] = []
    # Inferred variant tags (WS1): a variant with NO manifest anchor is a soft claim — surface it so an
    # invented tag can't hide, but never block (an inference may be legit). Aggregated + capped (one
    # line, not one per tag) and in the deployment family, so the first re-validate of a just-shipped
    # `variants: ["cloud"]` map (all sources now empty) is a single nudge, not a wall (T8).
    inferred = [f"{d.unit}:{v.env}" for d in m.deployment for v in d.variants if not v.source]
    if inferred:
        shown = _shown(inferred, 8)
        warnings.append(f"{len(inferred)} deployment variant tag(s) are inferred (no manifest anchor): "
                        f"{shown} — cite the compose profile / overlay / stage line that places each unit "
                        f"in that environment (else confirm it's a real inference). Record the literal "
                        f"`runs-in/quality` under a 'Balance exceptions' extras heading to silence this.")
    if m.environments and not any(d.variants for d in m.deployment):
        warnings.append(f"{len(m.environments)} environment(s) declared but no deployment unit is tagged "
                        f"with a `variants` value — the Deployment view can't split by environment "
                        f"(every unit shows in all). Tag each unit with the environment(s) it runs in. "
                        f"Record the literal `runs-in/quality` under a 'Balance exceptions' extras heading to "
                        f"silence this.")
    elif m.environments:
        # THE MIXED STATE, which the all-or-nothing check above cannot see. An empty `variants` means
        # "ungated — runs in EVERY environment", so on a partly-tagged map a FORGOTTEN unit does not
        # go missing, it silently claims to run everywhere. That is the same shape as the `runs_in`
        # gap that drew eight false process arrows on a live map: an absence read as a positive
        # claim. When some units are tagged and others are not, the untagged ones are worth a second
        # look — being genuinely shared is possible, but it is now a decision rather than a default.
        untagged = [d.unit for d in m.deployment if not d.variants]
        if untagged:
            shown = _shown(untagged, 6)
            warnings.append(
                f"{len(untagged)} of {len(m.deployment)} deployment unit(s) carry no `variants` while "
                f"others do: {shown} — an untagged unit reads as 'runs in every environment' "
                f"({', '.join(m.environments)}), so a forgotten tag becomes a claim rather than a gap. "
                f"Tag the environment(s) each really runs in, or confirm it is genuinely ungated by "
                f"recording the literal `runs-in/quality` under a 'Balance exceptions' extras heading.")
    # a real unit name may contain spaces ('api worker'); only a SEPARATOR (shared with the dep-match
    # guard) signals two units crammed into one row (S5)
    non_atomic = [d.unit for d in m.deployment
                  if d.unit and not grammar.is_atomic_unit_name(d.unit)]
    if non_atomic:
        warnings.append(f"Deployment unit name(s) look non-atomic (contain a separator): "
                        f"{', '.join(non_atomic)} — a unit is ONE process; split each '<a> / <b>' into "
                        f"separate `deployment[]` rows so a `runs_in` value resolves to exactly one host. "
                        f"Record the literal `runs-in/quality` under a 'Balance exceptions' extras heading if the "
                        f"name really is one process.")
    used = any(c.runs_in for c in m.components) or any(ep.runs_in for ep in m.entry_points)
    if not used:
        return warnings                        # fully un-adopted → `_deployment_unlinked_warning` owns it
    comp_units = {c.id: set(c.runs_in) for c in m.components}
    hosted: set[str] = set()
    for c in m.components:
        hosted.update(c.runs_in)
    for ep in m.entry_points:
        hosted.update(ep.runs_in)
    dep_names = system_dep_names(m)
    orphan_units = orphan_deployment_units(m)
    if orphan_units:
        warnings.append(f"Deployment unit(s) run no traced component or entry point and match no known "
                        f"system dependency: {', '.join(orphan_units)} — is each infra (add it as a "
                        f"dependency), or an un-traced `runs_in` (tag the component/entry point that runs "
                        f"there)? Record the literal `runs-in/quality` under a 'Balance exceptions' extras heading "
                        f"if each is deliberately code-less.")
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
                        f"(method.md), or record `runs-in/quality` under 'Balance exceptions' if it truly runs as "
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
        shown = _shown(ambiguous, 8)
        warnings.append(f"{len(ambiguous)} self-started entry point(s) whose owning component runs in >1 "
                        f"unit but which set no `runs_in` — the host process is ambiguous (the view picks "
                        f"one). Set `runs_in` on the entry point to pin its exact process, or record the "
                        f"literal `runs-in/quality` under a 'Balance exceptions' extras heading if the ambiguity "
                        f"is accepted: {shown}")
    return warnings


#: EVERY advisory group the recorded `runs-in/quality` literal silences, paired with the short label the
#: count line uses to name it. This tuple is the ONLY place that mapping exists: each producer is
#: raw (it never reads the literal itself), and `_runs_in_family_warnings` below is the single exit
#: that applies the literal and reports what it swallowed. A FIFTH group is added by appending a row
#: here — there is no other wiring, so it cannot arrive with a private, uncounted `return []`.
#:
#: Why that matters: the literal used to be honoured at four separate sites and counted at ONE.
#: On two live maps a `runs-in/quality` record written about something else ("the Mongo units run no
#: first-party code"; environment tags on one unit) silently swallowed unrelated placement
#: findings, while the count line named a smaller number — and when the counted group happened to
#: be empty the suppression was invisible entirely. `tests/test_validate_model.py` pins the
#: invariant by AST: no other function in this module may read the `runs-in/quality` literal.
_RUNS_IN_FAMILY: tuple[tuple[str, str, Callable[[ProjectModel], list[str]]], ...] = (
    ("runs-in/quality",
     "deployment quality (unit naming, formula-filled `runs_in`, unlinked units, thread hosts, "
     "variant tagging)", _deployment_quality_warnings_raw),
    ("runs-in/unlinked",
     "deployment units enumerated but nothing links code to them", _deployment_unlinked_warning),
    ("runs-in/unplaced",
     "most components unplaced across the enumerated units", _deployment_mostly_unplaced_warning),
    ("runs-in/entry-hosts",
     "self-started entry points with no host unit", _deployment_placement_warnings),
    ("runs-in/messaging",
     "messaging channels no participant's `runs_in` can place", _messaging_placement_warnings),
)


def _runs_in_family_warnings(m: ProjectModel) -> list[str]:
    """Every `runs_in` advisory in the map, with the recorded `runs-in` exception applied ONCE — at
    this single exit, across ALL the groups in `_RUNS_IN_FAMILY`.

    The escape hatch is honoured but NOT silently. That one literal switches off every `runs_in`
    finding the map has, while the justification behind it is usually about a single one. A live map
    recorded `runs-in` for exactly one reason ("two test-profile units run no product code") and
    thereby hid two unrelated findings, including a real variant-tagging gap. Suppression you cannot
    see is indistinguishable from having no findings, so the COUNT — and the name of every group it
    covered — stays visible even when the detail does not."""
    recorded = balance_lib._exceptions(m)
    found: list[tuple[str, str, list[str]]] = []
    for scope, label, produce in _RUNS_IN_FAMILY:
        group = produce(m)
        if group:
            found.append((scope, label, group))
    out: list[str] = []
    suppressed: list[tuple[str, str, int]] = []
    for scope, label, group in found:
        if scope in recorded:
            suppressed.append((scope, label, len(group)))
        else:
            out.extend(group)
    if suppressed:
        detail = "; ".join(f"{n} × {label} (`{scope}`)" for scope, label, n in suppressed)
        out.append(f"{sum(n for _, _, n in suppressed)} deployment advisory/advisories suppressed by "
                   f"recorded scoped exception(s), across {len(suppressed)} finding group(s) — "
                   f"{detail}. Each silences only its own group; re-read one by validating a copy "
                   f"with that line removed.")
    # A correctly-spelled key whose group is EMPTY is the same failure wearing the other hat: it
    # suppresses nothing, and the count line above cannot say so because it only reports what it
    # swallowed. On a live map three scoped keys were recorded and the line named two groups; the
    # third (`runs-in/unplaced`) matched no finding, and removing it changed no output at all — so
    # a correct-but-inert record and a typo'd one were indistinguishable, and the build read that
    # line three times without noticing. `assemble` already says "nothing to de-duplicate" for a
    # keep_edges directive that matches nothing and `reconcile` reports every rule that matched
    # nothing; this was the one escape family with no such signal.
    fired = {scope for scope, _l, _g in found}
    inert = [scope for scope, _label, _produce in _RUNS_IN_FAMILY
             if scope in recorded and scope not in fired]
    if inert:
        # "Remove the line" was the first wording and it was WRONG ADVICE. These groups fire on
        # thresholds, so a record can be DORMANT rather than dead: on a live map `runs-in/unplaced`
        # suppressed nothing while sitting two components below the unplaced-share threshold, and
        # the justification behind it ("the React dashboard runs in the browser, which is not a
        # deployment process") was correct and would be needed the moment the map crossed it.
        # Nothing here can tell a typo from a not-yet-firing group, so the line reports the fact and
        # asks for a check — it does not prescribe a deletion it has no basis for.
        out.append("recorded `runs_in` exception(s) currently suppressing nothing: "
                   + ", ".join(f"`{s}`" for s in inert)
                   + " — the advisory each one names is not firing on this map. Either the key is "
                     "not the one you meant (an inert record and a typo look identical), or the "
                     "group is simply below its threshold today and the record is holding a "
                     "decision for later. Check which, and keep it if it is the latter.")
    # A near-miss key silences nothing and says nothing, so the operator believes the finding is
    # adjudicated while validate keeps firing. Scoping replaced one short word with five
    # slash-and-hyphen keys typed free-hand into `record --line`, which multiplies that surface.
    typos = balance_lib.near_miss_runs_in_keys(m)
    if typos:
        out.append(f"recorded `runs_in` exception key(s) no check reads: {', '.join(typos)} — these "
                   f"silence nothing. The five that work are "
                   + ", ".join(f"`{scope}`" for scope, _l, _p in _RUNS_IN_FAMILY) + ".")
    if "runs-in" in recorded:
        # A BARE `runs-in` silences nothing, deliberately. It used to switch off all five groups at
        # once while the justification behind it was about a single one — the family escape the
        # method forbids ("a recorded line silences exactly one (check, id) pair — never a family").
        # On a live map a record about two test-profile containers thereby hid a real regression:
        # six of eight deployment units had stopped hosting any component. Rejecting the bare form
        # is what makes the operator say which finding they actually judged.
        out.append("a bare `runs-in` exception is recorded and silences NOTHING — it used to switch "
                   "off every `runs_in` advisory in the map at once, while the justification behind "
                   "it was about one of them. Replace it with the scoped line for the finding you "
                   "actually judged: "
                   + ", ".join(f"`{scope}` ({label})" for scope, label, _p in _RUNS_IN_FAMILY) + ".")
    return out


def recorded_line_warnings(m: ProjectModel) -> list[str]:
    """Two advisories about the RECORDS themselves — the shape of the adjudication log, not the map.

    1. REPEATED REASONS. One reason written out once per element is how a recorded section grows
       into a wall: a live map carried 66 lines holding 15 distinct reasons, the same sentence up to
       seventeen times in a row. A record may name every element it answers on ONE line, which is
       the same adjudication in a form a person can read.

       Only for a family whose reader ACCEPTS a comma list, and only when the repeated lines' own
       keys parse under it. The first version advised every heading alike, and on the seven families
       with no list grammar — a quoted claim, a `path:line`, a bucket name, a kind plus a contract
       word — following that advice destroyed the record with nothing said: the tool causing the
       silent over-suppression this whole module exists to prevent.

    2. A LINE THAT TRIED TO BE A RECORD AND ADJUDICATES NOTHING — a list holding a token that is not
       a key, a key with no why, or (in the audit family) a list that has lost the check name that
       scopes it. It must be said out loud, because a dropped record and an answered finding look
       identical from the outside."""
    out: list[str] = []
    for spec in records.HEADINGS:
        heading = spec.heading
        lines = records.lines(m, heading)
        if not lines:
            continue
        if spec.key is not None:
            groups: dict[str, list[str]] = {}
            for ln in lines:
                keys = records.keys_on_line(ln, spec.key, spec.seps, spec.lead, spec.strict_multi)
                _, sep, why = ln.partition(": ")
                # Only a line THIS family can read, keyed by a single element, can be merged with
                # another — a line already carrying a list is the fixed form, not the problem.
                if len(keys) == 1 and sep and (w := _norm_reason(why)):
                    groups.setdefault(w, []).append(keys[0])
            repeated = sorted((len(ks), ks) for ks in groups.values() if len(ks) >= _REPEATED_REASON_MIN)
            if repeated:
                worst = repeated[-1]
                out.append(f"'{heading}' repeats one reason across several records: "
                           f"{sum(n for n, _ in repeated)} of {len(lines)} line(s) restate "
                           f"{len(repeated)} reason(s), one of them {worst[0]} times — write each "
                           f"reason ONCE and name every element it answers on that line "
                           f"({', '.join(worst[1][:3])}{', …' if worst[0] > 3 else ''}: <why>).")
        for bad in records.malformed_records(m, heading):
            out.append(f"'{heading}' has a line that tries to be a record and adjudicates NOTHING "
                       f"(the form is `{spec.merged_form}`): {bad[:96]}")
    return out


#: A recorded reason, compared for repetition. Casefolded, whitespace-collapsed and stripped of
#: trailing punctuation — the shallowest normalisation that still catches the walls seen in the wild,
#: where the repeats were byte-identical. It does NOT catch a wall of PARAPHRASES (one live map wrote
#: 67 lines that restate five sentences in 67 spellings); that one is answered at the source instead,
#: by `grammar.STORE_MODES_UNOWNED` making most of those lines unnecessary to write at all.
def _norm_reason(why: str) -> str:
    return " ".join(why.strip().rstrip(".;,").casefold().split())


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
        # A CONTAINER is not an endpoint. `_check_references` resolves an `S`/`SD` id happily (it is a
        # defined element), so nothing else here notices — and both the promotion recipe
        # (`method/change-impact.md`) and `method.md` tell the lead that a leftover edge to a retired
        # component's replacement subsystem "fails validation". It did not. Promotion is exactly when
        # this happens: a component becomes a subsystem, and an edge nobody re-pointed now claims a
        # whole container calls something, which the viewer cannot draw at any single altitude.
        for side, eid in (("src", e.src), ("dst", e.dst)):
            if _is_container_id(eid):
                problems.append(
                    f"Edge {e.src} → {e.dst}: {side} '{eid}' is a subsystem/subdomain, which cannot be "
                    "an edge endpoint (edges run C↔C, C↔D, C→E) — re-point it at a specific child "
                    "component")
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


_recorded_line_keys = records.lines   # the shared line reader; see `records` for the whole contract


_records_key = records.records_key   # the free-text key test; see `records` for why it stays single-key


def duplicate_security_warnings(m: ProjectModel) -> list[str]:
    """Advisory (NON-BLOCKING): the same auth SURFACE authored more than once.

    Two fragments harvesting one auth check is the ordinary cause, and it survives assembly because
    security rows carry no id to collide on. It matters more than it looks: a duplicate surface is
    the shape that made a live build read two DISTINCT rows as one and hand-delete a CONFIRMED
    grounding claim. `coyodex fix dedup-security` resolves it.

    Rows merely sharing an ANCHOR are deliberately not flagged — one line can legitimately guard two
    surfaces, and calling that a duplicate is the mistake this warning exists to prevent.

    The escape is the existing 'Accepted duplications' extras heading, keyed by the surface text —
    the same heading and the same shape the UC/SF duplication advisory already uses. A suppression
    is reported on its own line, never silently: a silence you cannot see reads as no finding."""
    by_surface: dict[str, list[str]] = {}
    for s in m.security:
        by_surface.setdefault(s.surface, []).append(s.source or "(no anchor)")
    accepted = _recorded_line_keys(m, "accepted duplications")
    out: list[str] = []
    silenced: list[str] = []
    for surface, anchors in sorted(by_surface.items()):
        if len(anchors) <= 1:
            continue
        if surface and _records_key(accepted, surface):
            silenced.append(surface)
            continue
        out.append(f"security surface '{surface}' is authored {len(anchors)} times "
                   f"({', '.join(sorted(set(anchors)))}) — two fragments harvested the same auth "
                   f"check; resolve with `coyodex fix dedup-security`, or record "
                   f"'{surface}: <why>' under an 'Accepted duplications' extras heading. Identity "
                   f"is the surface, not the anchor: two surfaces sharing one anchor is legal.")
    if silenced:
        out.append(f"{len(silenced)} duplicate security surface(s) suppressed by a recorded "
                   f"'Accepted duplications' line: {', '.join(silenced)}. Re-read one by validating "
                   f"a copy with that line removed.")
    return out


def roleless_cd_verb_warnings(m: ProjectModel) -> list[str]:
    """Advisory (NON-BLOCKING): a C→D edge (dst is a dep) whose verb names no role — `C uses D` erases
    whether D is a bus, a store, or a service. Surface the roleless edges so the author picks a
    role-revealing verb (the role is then DERIVED from the verb — `grammar.dep_roles` — never a stored
    field). Aggregated + capped (one line, not one warning per edge).

    Deliberately NOT a `_check_edges` warning: `lint_fragment_problems` PROMOTES those to blocking
    problems, which would FAIL the fragment lint and force an agent to rewrite a legitimately-generic
    verb (trap T7). Instead this rides the non-blocking channel — whole-map `validate` warnings and
    `lint_fragment_warnings`. Scoped strictly to C→D (a C→C / C→E generic `uses` is fine and would
    otherwise flood). FOLDED framework/library deps are exempt: `uses` IS the honest verb for an
    in-process framework (three live rebuilds justified exactly those firings instead of fixing
    them — a nudge nobody ever acts on is noise)."""
    folded = {d.id for d in m.deps
              if grammar.classify_dep(d.kind or "", d.type) in grammar.DEP_KINDS_FOLDED}
    roleless = [f"{e.src} {e.verb} {e.dst}" for e in m.edges
                if e.dst.startswith("D") and e.dst not in folded
                and grammar.edge_role(e.verb) is None]
    if not roleless:
        return []
    shown = _shown(roleless, 8)
    return [f"{len(roleless)} C→D edge(s) name no role (generic verb): {shown} — use a role-revealing "
            f"verb so the dependency's role is legible: publishes/emits/listens-to (message bus), "
            f"reads/writes/persists/queries (data store), calls (service)."]


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
            # The vocabulary is CLOSED (`grammar.CARDINALITIES`). Published as a validation rule since
            # the first domain-cards doc and enforced by nothing, so `many→ONE` and `0..n` rode into
            # the class diagram unchallenged. Blocking, like the half-stated-pair rule right above it:
            # a cardinality is either the map's notation or it is noise, and a reader cannot tell.
            for side, card in (("src", r.src_card), ("dst", r.dst_card)):
                if card is not None and card.strip() not in grammar.CARDINALITIES:
                    problems.append(
                        f"Domain card {e.id}: relation '{r.verb} … {r.target}' has an unknown {side} "
                        f"cardinality '{card}' — use one of "
                        f"{', '.join(sorted(grammar.CARDINALITIES))}")
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


def domain_card_shape_problems(entities: list[Entity]) -> list[str]:
    """BLOCKING per-card shape: a meaning, a source, fields, and a type on every field.

    Shared with `lint_fragment` on purpose. It lived only here, on the ASSEMBLED map, so a T5 agent
    could lint its fragment clean, hand it back, and blow the lead's `validate` a phase later — one
    live build lost seven turns to eight cards failing this after the fragment had passed its own
    self-check. The check the agent cannot run is the check the agent cannot fix cheaply.

    An `enum` card is EXEMPT from the fields rule: `store.mode == "enum"` says the card describes a
    closed value set, whose members are its relations/meaning, not typed fields. Requiring fields
    there is asking for a shape the thing does not have — the same eight cards were "fixed" by
    hand-injecting the enum members into `fields` to get past the gate, which is the tool teaching
    the map to lie."""
    problems: list[str] = []
    for e in entities:
        if not e.meaning:
            problems.append(f"Domain card {e.id} is missing a MEANING line")
        if not e.source:
            problems.append(f"Domain card {e.id} is missing a SOURCE link")
        is_enum = bool(e.store and e.store.mode == "enum")
        if not e.fields and not is_enum:
            problems.append(f"Domain card {e.id} has no FIELDS")
        for f in e.fields:
            if not f.type:
                problems.append(f"Domain card {e.id} field '{f.name}' has no type")
    return problems


def reciprocal_relation_problems(entities: list[Entity]) -> list[str]:
    """One relation authored on BOTH cards — blocking, and answerable from the entities alone.

    Its own function because `lint-fragment` needs it: it ran the other two domain-card checks and
    not this one, so a T5 fragment self-checked OK and `validate` then failed the assembled map on
    33 of these, every one of them inside that fragment. A self-check that cannot fail on the
    commonest domain-card mistake sends the agent home with a fragment that bounces at assembly.

    Sorted: the caller prints these, and iterating a set of pairs made the list churn between
    identical runs."""
    directed: set[tuple[str, str]] = set()
    for e in entities:
        for r in e.relations:
            directed.add((e.id, r.target))
    return [f"Relation between {a} and {b} is declared on both cards — author it on one side only"
            for a, b in sorted(directed) if a < b and (b, a) in directed]


def _check_domain_cards(m: ProjectModel) -> tuple[list[str], list[str]]:
    problems, warnings = check_domain_relations(m.entities)
    problems.extend(domain_card_shape_problems(m.entities))
    problems.extend(reciprocal_relation_problems(m.entities))
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
    for el in (*m.entities, *m.components):     # a state machine's declaring line is a file anchor
        if el.states is not None:
            bad_file(f"{el.id} states.source", el.states.source)
    for i, mr in enumerate(m.messaging):        # a channel's declaring line is a file anchor
        bad_file(f"messaging[{i}] ('{mr.name}') source", mr.source)
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
        bad_file(f"entry_points[{ep.component} {ep.kind}].cadence_source", ep.cadence_source)
    for e in m.entities:
        bad_anchor(f"{e.id} source", e.source)
    for g in m.glossary:
        bad_anchor(f"glossary '{g.term}' source", g.source)
    for r in m.rules:
        for i, site in enumerate(r.sites):
            # A site is the map's strongest "this line acts" claim, so its anchor must NAME a line —
            # `bad_file` would accept a bare `src/guard.py`, which skips the operative-line check
            # and makes the claim unfalsifiable.
            if site.where and not FILE_LINE_ANCHOR.match(site.where):
                problems.append(f"{r.id} site[{i}] where: '{site.where}' is not a valid "
                                "`path:line` anchor — an enforcement site names ONE operative "
                                "line, so the `:line` is required")
    for group in group_forests(m):
        bad_anchor(f"{group.id} source", group.source)
        bad_file(f"{group.id} tech_source", group.tech_source)
    # Operational-table source fields that the viewer turns into code links — same bare-anchor rule as
    # every other source (the deployment/observability location fields stay free prose, so they are NOT
    # checked here: they describe topology, not a single line, and the viewer renders them as text).
    for i, r in enumerate(m.run_commands):
        bad_file(f"run_commands[{i}].source", r.source)
    for i, s in enumerate(m.security):
        bad_file(f"security[{i}].source", s.source)
    for i, d in enumerate(m.deployment):
        for v in d.variants:                   # a cited variant anchor is a bare `path:line`, like security's
            bad_file(f"deployment[{i}] ('{d.unit}') variant '{v.env}' source", v.source)
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
    for group in group_forests(m):
        if group.source and not url.match(group.source):
            out.append((f"{group.id} source", group.source))
        if group.tech_source and not url.match(group.tech_source):
            out.append((f"{group.id} tech", group.tech_source))
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
    for el in (*m.entities, *m.components):
        # a CITED state-machine anchor rides the same existence path (an empty one is the
        # inferred case — an advisory elsewhere, not here).
        if el.states is not None and el.states.source and not url.match(el.states.source):
            out.append((f"{el.id} states", el.states.source))
    for mr in m.messaging:
        if mr.source and not url.match(mr.source):
            out.append((f"messaging '{mr.name}'", mr.source))
    for g in m.glossary:
        if g.source and not url.match(g.source):
            out.append((f"glossary '{g.term}'", g.source))
    for ep in m.entry_points:
        if ep.source and not url.match(ep.source):
            out.append((f"entry_points[{ep.component} {ep.kind}]", ep.source))
        # a CITED cadence anchor rides the same existence path as variants' (an empty one is the
        # inferred case — surfaced as an advisory elsewhere, not here).
        if ep.cadence_source and not url.match(ep.cadence_source):
            out.append((f"entry_points[{ep.component} {ep.kind}] cadence", ep.cadence_source))
    for br in m.rules:
        # a rule SITE is an L2 claim that this exact line enforces the decision — a dead anchor is
        # a rule nobody can check, so it rides the same existence path as a security source.
        for i, site in enumerate(br.sites):
            if site.where and not url.match(site.where):
                out.append((f"{br.id} site[{i}]", site.where))
    for s in m.security:
        # the Auth-check anchor is an L2 grounding claim — verify the enforcement site exists.
        # The canonical `security[].source` is a bare `path:line` (like Entity.source), so take the
        # raw source; a legacy markdown-link source is still honored via `_first_link_of`.
        href = _first_link_of(s, [s.source]) or (s.source or None)
        if href and not url.match(href):
            out.append((f"security '{s.surface}'", href))
    for d in m.deployment:
        # a variant's grounding anchor rides the SAME existence path as security anchors (T6): a CITED
        # `source` that doesn't resolve is a hard block under `--check-sources`. An empty source is the
        # inferred case (no anchor to check) — surfaced as an advisory elsewhere, not here.
        for v in d.variants:
            if v.source and not url.match(v.source):
                out.append((f"deployment '{d.unit}' variant '{v.env}'", v.source))
    return out


def check_anchor_existence_model(m: ProjectModel, roots: list[Path]) -> list[str]:
    """BLOCKING under `--check-sources`: every anchor must resolve to a real file (or directory), and
    a cited LINE must exist in it.

    The line half was missing for a long time while `method.md` told the build that "`--check-sources`
    verifies that line exists, so a fabricated anchor is a hard block". It did not: only the file was
    tested, so `some/real/file.py:999999` passed all-green. That gap points the wrong way — an agent
    that cannot find the true line is told a gate will catch a guess, so guessing looks safe.

    A line PAST THE END OF THE FILE is the only line error decidable here, and it is decisive: the
    citation cannot be true of this file at this commit. Whether a line that DOES exist is the right
    one is a reading question, left to the advisory operative-line pass and the Phase-4 skeptics.
    """
    out: list[str] = []
    line_count: dict[str, int | None] = {}
    for label, href in _anchor_pairs(m):
        rel = strip_anchor(href)
        is_dir = rel.endswith("/")
        rel = rel.rstrip("/")
        if not rel:
            continue
        hit = next((r / rel for r in roots if ((r / rel).is_dir() if is_dir else (r / rel).is_file())),
                   None)
        if hit is None:
            out.append(f"{label}: '{href}' does not resolve to a "
                       f"{'directory' if is_dir else 'file'} in the repo")
            continue
        loc = parse_anchor(href)
        if is_dir or loc is None or loc.lo is None:
            continue                                   # a whole-file / directory anchor cites no line
        key = str(hit)
        if key not in line_count:
            try:
                line_count[key] = len(hit.read_text(encoding="utf-8", errors="ignore").splitlines())
            except OSError:
                line_count[key] = None                 # unreadable (binary, permissions): not a claim
                                                       # about the map, so it is not this gate's finding
        n = line_count[key]
        if n is None:
            continue
        hi = loc.hi or loc.lo
        if loc.lo < 1 or hi > n:
            out.append(f"{label}: '{href}' cites a line the file does not have — "
                       f"{rel} is {n} line(s) long")
    return out


# Prose/markup files have no "operative statement" — a leading `#` there is a heading, not a comment.
_PROSE_SUFFIXES = frozenset({".md", ".markdown", ".rst", ".txt", ".adoc"})


def call_site_anchors(m: ProjectModel) -> list[tuple[str, str]]:
    """(label, anchor) for every anchor that claims AN ACTION FIRES AT THAT LINE.

    Deliberately NOT every anchor: a component/entity/entry-point `source` is supposed to point at a
    definition, so running the operative-line check over those would flag correct anchors. Only four
    families make a "this line acts" claim — backbone edge `where`, flow/sub-flow step `where`, a
    security surface's enforcement `source`, and a business rule's enforcement SITE."""
    out: list[tuple[str, str]] = []
    for e in m.edges:
        # `extends`/`implements` are DECLARED by the definition header — `class Sub(Base):` IS the
        # operative statement for them, so the header is correct here, not drift.
        if e.where and e.verb not in ("extends", "implements"):
            out.append((f"edge {e.src} —{e.verb}→ {e.dst} `where`", e.where))
    for f in m.flows:
        for st in f.steps:
            if st.where:
                out.append((f"{f.uc} flow step {st.n} `where`", st.where))
    for sf in m.subflows:
        for st in sf.steps:
            if st.where:
                out.append((f"{sf.id} step {st.n} `where`", st.where))
    for s in m.security:
        if s.source:
            out.append((f"security '{s.surface}' auth check", s.source))
    for r in m.rules:
        # a site claims THIS LINE enforces the decision — the strongest "this line acts" claim in
        # the map, so it belongs here more than any other family.
        for i, site in enumerate(r.sites):
            if site.where:
                out.append((f"{r.id} site[{i}] ({site.why or 'enforcement site'})", site.where))
    return out


def check_operative_lines_model(m: ProjectModel, roots: list[Path]) -> list[str]:
    """ADVISORY: a call-site anchor pointing at a line that cannot be the acting statement.

    The deterministic half of what the Phase-4 skeptics find by reading (see
    `anchors.non_operative_reason`). Non-blocking on purpose: a drifted anchor does NOT refute the
    relationship — the edge is usually real and only its `where` is wrong — so this points, it does
    not fail the build."""
    out: list[str] = []
    cache: dict[str, list[str] | None] = {}
    for label, anchor in call_site_anchors(m):
        loc = parse_anchor(anchor)
        if loc is None or loc.lo is None:
            continue                       # a whole-file/dir anchor claims no single line
        src = _resolve_source_file(anchor, roots)
        if src is None:
            continue                       # existence is `check_anchor_existence_model`'s job
        if src.suffix.lower() in _PROSE_SUFFIXES:
            continue                       # "the operative statement" means nothing in prose
        key = str(src)
        if key not in cache:
            try:
                cache[key] = src.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                cache[key] = None
        lines = cache[key]
        if lines is None or not (1 <= loc.lo <= len(lines)):
            continue
        why = non_operative_reason(lines[loc.lo - 1])
        if why:
            out.append(f"{label}: '{anchor}' points at {why} — anchor the operative statement "
                       f"(the call / write / enforce line itself), or set no_call_site")
    return out


def check_state_sources_model(m: ProjectModel, roots: list[Path]) -> list[str]:
    """ADVISORY: state names that do not appear in the file the machine cites.

    A `states` machine is the one map claim NO other gate can reach: it has no per-state anchor, so
    `--check-sources` only ever proved the machine's own `source` file exists. Live evidence that
    this matters — a fresh build shipped ~11 lifecycles and the Phase-4 skeptics refuted 5 of them:
    states lifted from docstring PROSE, and a start state bolted onto an otherwise-real enum. Both
    shapes leave the same fingerprint: the invented names are not in the cited file. The same
    lenient token match `check_entity_sources_model` uses, so a `PENDING` declared as `pending`
    still passes."""
    out: list[str] = []
    for el in (*m.entities, *m.components):
        sm = el.states
        if sm is None or not sm.source or not sm.states:
            continue
        src = _resolve_source_file(sm.source, roots)
        if src is None:
            continue
        try:
            code = src.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        missing = [s for s in sm.states if s.strip() and s.strip().lower() not in code]
        if missing:
            out.append(
                f"{el.id} states: {len(missing)} of {len(sm.states)} state name(s) do not appear in "
                f"the cited source ({strip_anchor(sm.source)}): {_shown(missing, 6)}"
                f" — either the name is COINED for a state the "
                "code expresses without naming (the false side of a boolean flag), in which case "
                "keep the machine but use the code's own vocabulary; or the lifecycle was read off "
                "prose rather than a declaration, in which case drop it")
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
    # Repo-root FILES, matched by name so a bare `Makefile` / `manage.py` anchor counts as a
    # reference (B1: `_REF_INLINE` needs a `/`, so root files were invisible to this scan).
    # Files ONLY — never directories. A root dir shares its name with words that appear in ordinary
    # map prose ("assets", "docs", "voice", "output"), so accepting directories let a Why sentence
    # mark a whole tree as referenced: on a live map it silenced a true "i18n/ has no path
    # referenced in the map — likely an unmapped module" finding because the word appeared in an
    # edge's `Why`. Only root files were ever needed here.
    try:
        root_names = {p.name for p in root.iterdir() if p.is_file()}
    except OSError:
        root_names = set()
    cands: set[str] = set()
    for s in _strings(m):
        cands.update(_REF_LINK.findall(s))
        cands.update(_REF_INLINE.findall(s))
        if root_names:
            cands.update(t for t in _REF_BARE.findall(s) if t in root_names)
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
    plumbing marker — with the v1 suffix/base heuristic kept as the fallback.

    Each half is answerable. (a) is a whole-map judgement with nothing per-row to mark, so it gets
    a literal: `entity-relations`, line-leading under a 'Balance exceptions' extras heading, for a
    domain whose cards legitimately relate to nothing (an event log, a settings bag). (b) already
    had two escapes and named neither: a 'Coverage exceptions' dir drops a whole folded area from
    BOTH the uncovered list and the denominator, and `non_entity_types` drops a single type by name
    — the better record of the two, because it travels with the type it describes."""
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
            and len(isolated) > _ISOLATED_FRACTION * n
            and "entity-relations" not in balance_lib._exceptions(m)):
        out.append(
            f"Isolated entities: {len(isolated)} of {n} entity cards have NO E↔E relation "
            f"({round(100 * len(isolated) / n)}% of the domain model) — a sparse class graph is the "
            f"signature of an under-harvested domain model (did one T5 harvest agent author "
            f"per-entity RELATIONS?); author the relations, or record the literal `entity-relations` "
            f"under a 'Balance exceptions' extras heading for a genuinely flat domain: "
            f"{_shown(isolated, _COVERAGE_SAMPLE)}"
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
            shown = _shown(uncovered, _COVERAGE_SAMPLE)
            out.append(
                f"Under-harvested domain model: {len(uncovered)} of {len(types)} named types in the "
                f"entities' source dirs have no entity card (possible under-harvested domain model; "
                f"Python types only, measured at validate time) — add the missing cards, mark a "
                f"plumbing type by name in `non_entity_types`, or record a deliberately folded "
                f"directory under a 'Coverage exceptions' extras heading: {shown}"
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
                   repo_root: Path | None = None,
                   stats: dict[str, int] | None = None) -> tuple[list[str], list[str]]:
    """Every semantic check over a structurally-valid model; returns (problems, warnings) exactly
    like the v1 validator did, so the profiler and the CLI share one orchestration.

    `stats` is an optional out-param (same shape as `assemble`'s reconcile stats) recording HOW MUCH
    the repo-reading flags actually read. It exists because `validate` and `validate --check-sources`
    printed byte-identical output on a clean map — so a lead who passed the flag on every run could
    not tell whether it did anything, and a silent flag is indistinguishable from a no-op one. Counts
    come from the same iterators the checks walk, never a re-derivation, so the number cannot drift
    from the work."""
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
    warnings.extend(subflow_refcount_warnings(m))
    warnings.extend(_granularity_warnings(m))
    warnings.extend(_completeness_warnings(m))
    problems.extend(_check_roles(m))
    problems.extend(_check_actors(m))
    warnings.extend(_check_actor_kinds(m))
    warnings.extend(confidence_warnings(m))
    problems.extend(_check_dep_kinds(m))
    dep_bucket_problems, dep_bucket_warnings = _check_dep_buckets(m)
    problems.extend(dep_bucket_problems)
    warnings.extend(dep_bucket_warnings)
    problems.extend(_check_activations(m))
    warnings.extend(_check_entry_kinds(m))
    warnings.extend(_kind_coverage_warnings(m))
    warnings.extend(_cadence_warnings(m))
    tech_problems, tech_warnings = _check_group_tech(m)
    problems.extend(tech_problems)
    warnings.extend(tech_warnings)
    problems.extend(_check_group_label(m))
    problems.extend(_check_runs_in(m))
    problems.extend(_check_environments(m))
    warnings.extend(_runs_in_family_warnings(m))   # the whole `runs_in` family, through ONE counted exit
    warnings.extend(recorded_line_warnings(m))    # the shape of the adjudication log itself
    edge_problems, edge_warnings = _check_edges(m)
    problems.extend(edge_problems)
    warnings.extend(edge_warnings)
    warnings.extend(roleless_cd_verb_warnings(m))
    warnings.extend(duplicate_security_warnings(m))
    # The pre-index symbol table committed beside the map, when there is one: it is what tells "the
    # rule is enforced inside the function this step names" from "no rule claims this step".
    # Without it the canary is conservative (more debt), never wrong in the other direction.
    rule_problems, rule_warnings = check_rules_model(
        m, load_map_extents(model_path) if model_path is not None else None)
    problems.extend(rule_problems)
    warnings.extend(rule_warnings)
    card_problems, card_warnings = _check_domain_cards(m)
    problems.extend(card_problems)
    warnings.extend(card_warnings)
    problems.extend(_check_stores(m))
    warnings.extend(_persistence_coverage_warnings(m))
    state_problems, state_warnings = _check_states(m)
    problems.extend(state_problems)
    warnings.extend(state_warnings)
    msg_problems, msg_warnings = _check_messaging(m)
    problems.extend(msg_problems)
    warnings.extend(msg_warnings)
    warnings.extend(_messaging_gap_warnings(m))
    warnings.extend(_messaging_payload_warnings(m))
    warnings.extend(_isolated_component_warnings(m))
    warnings.extend(_grounding_warnings(m))
    warnings.extend(_inheritance_runs_in_warnings(m))
    problems.extend(_check_anchor_format(m))
    problems.extend(_check_evidence(m))
    problems.extend(_check_grounding_arithmetic(m))
    extra_problems, extra_warnings = _check_extra_conventions(m)
    problems.extend(extra_problems)
    warnings.extend(extra_warnings)

    roots = _source_roots(model_path, repo_root) if model_path is not None else (
        [repo_root.resolve()] if repo_root is not None else [])
    if check_sources:
        if stats is not None:
            # The same two iterators the checks below walk, so the reported count IS the work done.
            stats["anchors_checked"] = len(_anchor_pairs(m))
            stats["call_sites_checked"] = len(call_site_anchors(m))
        problems.extend(check_entity_sources_model(m, roots))
        # A nonexistent-file anchor means a wrong repo-root prefix or a stale path reached the map — a
        # real error, not a nudge. Blocking (B3) so `validate --check-sources` is the deterministic
        # backstop for the source-side prefix rule (a missing file can never slip through all-green).
        problems.extend(check_anchor_existence_model(m, roots))
        # ADVISORY, not blocking: the anchor resolves but points at a line that cannot act (a `def`
        # header, an import, a comment). The relationship is usually real — only its `where` drifted
        # — so this points at work, it never fails the build.
        warnings.extend(check_operative_lines_model(m, roots))
        warnings.extend(check_state_sources_model(m, roots))

    parents = _parents(m)
    hier_problems, hier_warnings = check_hierarchy(parents, defined)
    problems.extend(hier_problems)
    warnings.extend(hier_warnings)
    warnings.extend(_check_altitude(m))
    walk_root = repo_root if repo_root is not None else (
        model_path.resolve().parent.parent if model_path is not None else None)
    # UNCONDITIONAL, and BEFORE the `check_coverage` block: `.coyodex/.ignore` narrows the tree every
    # check below measures, and the cheap `validate --check-sources` pass (the one method.md tells a
    # lead to run first) is the invocation a coverage-gated disclosure would hide it from. Emitted
    # first, so the reader learns the tree was narrowed before reading any "no gaps here" result
    # computed over the narrowed tree.
    if walk_root is not None:
        warnings.extend(ignore_disclosure(walk_root))
    if check_coverage:
        cov_dirs = frozenset(_recorded_coverage_dirs(m))  # 'Coverage exceptions': conscious coarse-fold
        if walk_root is not None:
            refs = referenced_paths(m, walk_root.resolve())
            if stats is not None:
                stats["coverage_refs"] = len(refs)
                stats["coverage_recorded_dirs"] = len(cov_dirs)
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
        # The escape is the E id under a 'Persistence exceptions' heading — the SAME heading the
        # coverage rule reads `Cn` lines from, because this is the same question from the other
        # side (there, a writer no entity explains; here, an entity no writer owns). Three separate
        # live leads independently invented exactly this heading for exactly this advisory before
        # it read anything: the vocabulary was already obvious, only the wiring was missing.
        adjudicated = _recorded_ids(m, "persistence exceptions", ("E",))
        # The MODE answers this on its own where the model can hold the answer: an entity that lives
        # in a parent's row, in the source, or only for the length of a call HAS no writer by
        # definition, and saying so as a validated `store.mode` puts the claim on the Data tab next
        # to the element instead of in a prose footnote on another tab. One live map wrote that
        # footnote 67 times, restating five sentences in eleven shapes — every one of them a mode.
        # The recorded line stays for what a mode cannot say — a library that owns its own tables, a
        # view the database refreshes, a throwaway CI database.
        by_mode = {e.id for e in m.entities
                   if e.store and e.store.mode in grammar.STORE_MODES_UNOWNED}
        unowned = sorted(e.id for e in m.entities
                         if e.id not in owned and e.id not in embedded
                         and e.id not in adjudicated and e.id not in by_mode)
        if unowned:
            shown = _shown(unowned, 12)
            warnings.append(f"Entities with no owning component (no persists/writes C→E edge): "
                            f"{shown} — author the owning component's persists/writes edge, set the "
                            f"entity's `store.mode` when nothing writes it "
                            f"({', '.join(grammar.STORE_MODES_UNOWNED)}), or record '<En>: <why>' "
                            f"under a 'Persistence exceptions' extras heading for what a mode "
                            f"cannot say (a library's own tables, a database-refreshed view)")
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
            shown = _shown(orphan_deps, 12)
            warnings.append(f"External deps with no incoming edge (un-traced — which component "
                            f"uses each?): {shown}")
        # The mirror nudge: a dep marked `deployment_linked` (declares NO code call site) that is
        # nonetheless an edge target has a real call site — the marker is wrong (a harvest agent
        # over-marked it). Drop the marker (or, if the edge is `no_call_site`, drop that edge).
        mislabeled = sorted(d.id for d in m.deps if d.deployment_linked and d.id in targets)
        if mislabeled:
            shown = _shown(mislabeled, 12)
            warnings.append(f"Deps marked `deployment_linked` but which are a code call target "
                            f"(they have a real call site — drop the marker, or drop the edge if it "
                            f"is `no_call_site`): {shown}")

    if model_path is not None:
        warnings.extend(_check_view_fresh(m, model_path))
    return problems, warnings


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────

#: The recorded security-table granularity: `security-granularity: <family | endpoint-and-condition>`
#: under a 'Balance exceptions' heading. NOT one of `balance_lib._LITERAL_ESCAPES` — it silences
#: nothing, it DECLARES a choice. It is read here so the choice is visible in every validate run and
#: in `finalize`'s report, beside the row count it explains: two maps of one repo went from 103
#: security rows to 19 while validate, audit and balance were all clean, because one row per surface
#: FAMILY and one row per endpoint-and-condition are both defensible and differ 5x on the same code.
#: Echoing it is what makes a change in that choice legible instead of silent. An absent record is not
#: nagged — the method asks for it, and a validate that scolds every pre-existing map is noise.
_SECURITY_GRANULARITY = re.compile(r"^\s*-?\s*security-granularity\s*[:—–]\s*(\S[^—–\n]*)",
                                   re.IGNORECASE | re.MULTILINE)


def recorded_security_granularity(m: ProjectModel) -> str | None:
    """The declared granularity, or None. Read from the same heading every other record uses."""
    for body in balance_lib.extras_bodies(m, "Balance exceptions"):
        hit = _SECURITY_GRANULARITY.search(body)
        if hit:
            return hit.group(1).strip().rstrip(".").strip()
    return None


def _inventory(m: ProjectModel) -> str:
    counts = {"UC": len(m.use_cases), "HP": len(m.happy_path), "S": len(m.subsystems),
              "C": len(m.components), "D": len(m.deps), "SD": len(m.subdomains),
              "E": len(m.entities)}
    out = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()) if v)
    # The access surface is read from `rules[access]`, NOT `security[]`. The T7 fold made an auth
    # surface a business rule and left `security[]` empty by design, so this whole block was dead
    # code on every post-fold map: two real builds carrying 47 and 44 access rules printed no access
    # count and no granularity state at all.
    access = access_rules(m)
    if access or m.security:
        gran = recorded_security_granularity(m)
        if access:
            out += f", access:{len(access)}"
        if m.security:
            out += f", security:{len(m.security)} (legacy)"
        out += f" (granularity: {gran})" if gran else " (granularity NOT recorded)"
    return out


def _checked_summary(stats: dict[str, int], check_sources: bool, check_coverage: bool) -> str:
    """One phrase naming what the repo-reading flags read, or "" when neither flag ran."""
    parts: list[str] = []
    if check_sources:
        # "considered", not "read": the operative-line check skips prose files, unresolvable paths
        # and out-of-range lines, so the count is what was handed to it, not what it opened.
        parts.append(f"{stats.get('anchors_checked', 0)} anchor(s) resolved against the repo, "
                     f"{stats.get('call_sites_checked', 0)} call-site anchor(s) considered for an "
                     f"operative line")
    if check_coverage:
        parts.append(f"coverage measured over {stats.get('coverage_refs', 0)} map-referenced path(s) "
                     f"with {stats.get('coverage_recorded_dirs', 0)} recorded coverage exception(s)")
    return " · ".join(parts)


def main(argv: list[str] | None = None) -> int:
    """Thin wrapper: whole-list mode is process-wide, so it is reset on EVERY exit path.

    Without this a `--json` run permanently widens every later list in the same process — harmless
    for the one-subcommand-per-process CLI, and a silent cross-test contaminant the moment anything
    calls `main([..., "--json"])` in-process."""
    try:
        return _run(argv)
    finally:
        reset_full_lists()


def _run(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex validate [--check-sources] [--check-coverage] [--ignore-exceptions] [--repo <root>] "
              "[--emit-unclaimed] [--json] [.coyodex/project-map.json]\n\n"
              "Validate a model: structural schema validation, then the semantic\n"
              "checks (IDs resolve, hierarchy sound, cards complete, view fresh, …).\n"
              "--emit-unclaimed: print a ready-to-paste 'Unclaimed surfaces' extras block for every\n"
              "  externally-activated entry point no use case reaches (adjudicate the wall at once).\n"
              "--json: {problems, warnings, inventory, checked, checked_counts} on stdout, with every\n""  finding list\n"
              "  emitted WHOLE — no `+N more` tail, no clipped trigger text. Read this instead of\n"
              "  regex-parsing the human report or re-deriving a hidden id list in a script.")
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
    as_json = "--json" in argv
    if as_json:
        # Set BEFORE any check runs: `shown`/`clip` read it while building their messages, so a JSON
        # consumer gets whole lists and whole trigger text. Reset in a `finally` below so an
        # in-process caller cannot inherit the mode from a previous JSON run.
        set_full_lists(True)
    ignore_exceptions = "--ignore-exceptions" in argv
    unknown = [a for a in argv if a.startswith("-")
               and a not in ("--check-sources", "--check-coverage", "--emit-unclaimed", "--json",
                             "--ignore-exceptions")]
    if unknown:
        print(f"ERROR: unknown option(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    if as_json and emit_unclaimed:
        print("ERROR: --json and --emit-unclaimed are different output contracts (a JSON report vs a "
              "paste-ready extras block) — pass one", file=sys.stderr)
        return 2
    args = [a for a in argv if not a.startswith("-")]
    path = Path(args[0] if args else ".coyodex/project-map.json")
    if not path.exists():
        # A map directory holding only the GENERATED views is a state nothing named, and it reads
        # as "no coyodex here" when in fact a build ran and its source was lost. One repo sits in it:
        # `project-map.md` and `project-map.html` are present, the model is gone, so nothing can be
        # validated, audited, fixed, scored or re-rendered — and the views still look authoritative
        # to a reader. Name it, because the recovery (re-assemble from the fragments, or rebuild) is
        # different from the recovery for an empty directory.
        views = [v.name for v in (path.with_suffix(".md"), path.with_suffix(".html")) if v.is_file()]
        if views:
            print(f"ERROR: {path} not found — but {' and '.join(views)} are. This map has only its "
                  f"GENERATED views; the model they were rendered from is missing, so nothing here "
                  f"can be validated, audited, fixed or re-rendered. Re-assemble from "
                  f"{path.parent / 'build-fragments'}/ if it survives, or rebuild the map.",
                  file=sys.stderr)
            return 1
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    try:
        m = load_model(path.read_text(encoding="utf-8"))
    except ModelError as e:
        print("\nVALIDATION FAILED (schema):")
        print(f"  - {e}")
        return 1
    if ignore_exceptions:
        # THE RE-READ. Several suppression messages end with "re-read the rest by validating a copy
        # with the exception removed" — an instruction that asks the operator to hand-edit a copy of
        # the map, which nobody ever did. A recorded id exempts its element from a whole FAMILY (the
        # step-count band AND the fused-goal name smell; every `runs_in` advisory, not just the one
        # the exception was written about), so what a literal actually silences is routinely more
        # than its author meant. This flag is that copy, made by the tool.
        dropped = sum(len(x.body.splitlines()) for x in m.extras
                      if x.heading.strip().lower().endswith("exceptions")
                      or x.heading.strip().lower() in ("accepted duplications", "unclaimed surfaces",
                                                       "happy path coverage",
                                                       "entry-point coverage"))
        m.extras = [x for x in m.extras
                    if not (x.heading.strip().lower().endswith("exceptions")
                            or x.heading.strip().lower() in ("accepted duplications",
                                                             "unclaimed surfaces",
                                                             "happy path coverage",
                                                             "entry-point coverage"))]
        print(f"NOTE: --ignore-exceptions — {dropped} recorded line(s) were dropped for this run, so "
              f"every advisory a recorded exception would have silenced is shown below. Nothing was "
              f"written; this is a READ of the map you have, not a different map.\n")
    if emit_unclaimed:
        # BOTH activations. Self-activated surfaces used to be exempt automatically, so they never
        # reached this block; now that they are a decision, the bulk-adjudication path has to carry
        # them too — otherwise the one class most likely to end in a record is the one class you
        # would have to hand-type.
        ext_rows = unclaimed_surface_components(m)
        self_rows = unclaimed_self_components(m)
        if not ext_rows and not self_rows:
            print("# No unclaimed surfaces — nothing to record.")
            return 0
        comp_name = {c.id: c.name for c in m.components}
        print("Unclaimed surfaces")
        print("<!-- paste under an 'Unclaimed surfaces' extras heading; replace each <why> "
              "(dead surface / dev-only / missing use case) or trace a use case instead -->")
        # One line per component is the DECISION unit, not the writing unit. This block is where the
        # walls came from: a live map answered 66 of these and wrote 15 distinct reasons, one of them
        # seventeen times. Say it here, at the moment the lead is about to fill them in.
        print("<!-- one reason usually covers several: merge those ids onto ONE line — "
              "`C1, C2, C3: <why>` — instead of repeating the sentence per component -->")
        for cid, eps in ext_rows:
            triggers = "; ".join(f"[{ep.kind}] {_clip(ep.trigger)}" for ep in eps)
            print(f"- {cid} ({comp_name.get(cid, cid)}): <why>   # {triggers}")
        if self_rows:
            print("<!-- self-activated (cron / worker / consumer / startup): no outside actor asks, "
                  "so a record is often the honest answer rather than a use case -->")
            for cid, eps in self_rows:
                triggers = "; ".join(f"[{ep.kind}] {_clip(ep.trigger)}" for ep in eps)
                print(f"- {cid} ({comp_name.get(cid, cid)}): <why>   # self-activated: {triggers}")
        return 0
    vstats: dict[str, int] = {}
    problems, warnings = validate_model(m, path, check_sources=check_sources,
                                        check_coverage=check_coverage, repo_root=repo_root,
                                        stats=vstats)
    # What the repo-reading flags actually read. Without this, `validate` and
    # `validate --check-sources` print byte-identical output on a clean map, so passing the flag is
    # indistinguishable from forgetting it — and a lead cannot tell a silent pass from a no-op.
    checked = _checked_summary(vstats, check_sources, check_coverage)
    if as_json:
        json.dump({"problems": problems, "warnings": warnings,
                   "inventory": _inventory(m), "checked": checked or None,
                   "checked_counts": vstats}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 1 if problems else 0
    print(f"Inventory — {_inventory(m)}")
    if checked:
        print(f"Checked — {checked}")
    if warnings:
        print("\nVALIDATION WARNINGS (non-blocking):")
        for w in warnings:
            print(f"  - {w}")
    if problems:
        print("\nVALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    # "Schema OK" is the line a reader treats as "the gates are clean", so it must say what clean was
    # measured OVER. The counts are on the `Checked —` line above rather than repeated here; what this
    # line adds is the scope — and, when no repo-reading flag ran, the fact that it did not.
    print("Schema OK — structure valid, all IDs defined once, all references resolve, every HP "
          "step names a use case, every flow step well-formed."
          + (" Repo-reading checks ran (see `Checked —` above)." if checked else
             " NOTE: no repo-reading check ran — pass --check-sources / --check-coverage for the "
             "anchor-existence and coverage passes."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
