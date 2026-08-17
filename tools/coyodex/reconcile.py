#!/usr/bin/env python3
"""`coyodex assemble --reconcile <file>` — declarative, re-runnable build-time reconcile directives.

Every build used to hand-write bespoke python for the two largest non-harvest writes — the synthesis
assignment pass (subsystem / subdomain / runs_in / bucket on ~every element) and the trace dedup/drop
pass — and neither had a command. The existing `fix` verbs edit the ASSEMBLED map, but the source of
truth is the fragments, so the next `assemble` silently discards the edit. This module makes those two
writes a declarative input to `assemble` that is applied deterministically AFTER the fragment merge and
`_derive_entity_edges`, BEFORE the write — so a re-assemble always re-applies them and the
fragment/model mismatch disappears.

Two directive kinds:

  set        — bulk-assign `subsystem` / `subdomain` / `runs_in` / `bucket` to named elements (replaces
               the per-build patch_synth.py). On the LIST field `runs_in`, `set` REPLACES the list, so a
               re-run is idempotent. `subsystem` targets a component, `subdomain` an entity, `runs_in` a
               component, `bucket` a dependency.
  drop_edges — remove a refuted backbone edge by (src, verb, dst) and heal/report the flow steps that
               rode it, exactly like `fix drop-edge` (replaces consolidate.py's drop). It runs AFTER
               `_derive_entity_edges` so a dropped C→E edge is NOT silently re-derived from its surviving
               step in the same assemble; per directive the default is to REPORT the riding steps, with
               `drop_steps` / `repoint` to heal them (a report-only C→E drop leaves the step, which the
               NEXT assemble re-derives — heal it to make the drop durable).

Validation is scoped to the touched fields (assemble otherwise defers cross-refs to `validate`) and
reuses the existing rules: `check_hierarchy` for `subsystem`=S-id / `subdomain`=SD-id /
no-subdomain-on-a-component, and the `deployment[].unit` resolution `_check_runs_in` enforces. A
0-match `drop_edges` WARNS (never fails), so a reconcile file doesn't rot when a fragment is later fixed
— the tradeoff is that a typo'd triple won't hard-fail. Stdlib-only (the cli.py firewall).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from coyodex.audit_model import apply_anchor_corrections
from coyodex.model import (
    BusinessRule,
    Component,
    Dep,
    Entity,
    FlowStep,
    ProjectModel,
    UseCase,
    all_elements,
)
from coyodex.validate_analysis import check_hierarchy


class ReconcileError(Exception):
    """A malformed reconcile file (bad JSON, unknown key, wrong-shape directive). Raised at load time
    so `assemble` fails loudly with the file named, before anything is written."""


# field name → (target element type, human label) — a `set` field is legal only on its owner type.
# `capability` and `entry_points` target a USE CASE, and both exist here for the same reason the
# others do: they are synthesis-time assignments over ~every element of their kind, and the ids they
# reference (`CAPn`, and especially `EPn`, which assemble mints from content) do not exist when the
# behavioral fragment is authored. Hand-writing them into fragments is the circle `reconcile` was
# built to break. `block` is the same shape one forest over: `BLK` ids are minted at synthesis while
# rules are authored after the trace, so a fragment cannot know them — and a re-synthesis that
# renumbers blocks would otherwise silently re-point every rule it touched.
_SET_FIELD_OWNER: dict[str, tuple[type, str]] = {
    "subsystem": (Component, "component"),
    "subdomain": (Entity, "entity"),
    "capability": (UseCase, "use case"),
    "entry_points": (UseCase, "use case"),
    "runs_in": (Component, "component"),
    "bucket": (Dep, "dependency"),
    "block": (BusinessRule, "business rule"),
}


@dataclass
class SetDirective:
    #: EVERY key of `_SET_FIELD_OWNER` must appear here as an attribute — `assigned_fields()`
    #: iterates that dict and calls `getattr`, so a dict entry with no attribute raises
    #: `AttributeError` on every reconcile run, not just the ones that use the new field.
    ids: list[str]
    subsystem: str | None = None
    subdomain: str | None = None
    capability: str | None = None
    entry_points: list[str] | None = None
    runs_in: list[str] | None = None
    bucket: str | None = None
    block: str | None = None
    #: id → the `source` anchor the author SAW on that entry point, for the witnessed form
    #: `{"id": "EP1", "source": "orders.py:9"}`. Empty when every value was written bare.
    #: `EPn` is minted by `assemble` from harvested content and is order-independent but NOT
    #: add-stable: a new surface that sorts earlier shifts every number after it, so a file authored
    #: against an older harvest silently re-points a use case at a different front door — the id
    #: still resolves, so no existing check has anything to complain about. The witness is what turns
    #: that into a stop.
    entry_point_witness: dict[str, str] = field(default_factory=dict)

    def assigned_fields(self) -> list[str]:
        return [f for f in _SET_FIELD_OWNER if getattr(self, f) is not None]


@dataclass
class DropEdgeDirective:
    src: str
    verb: str
    dst: str
    drop_steps: bool = False
    repoint: str | None = None


@dataclass
class KeepEdgeDirective:
    """Which anchor survives when one (src, verb, dst) is declared at several call sites.

    `fix dedup-edge` resolves these, and wrote its answer into the ASSEMBLED map — which the next
    assemble rebuilds from fragments, discarding it. That is not hypothetical: a shipped map carried
    365 edges while re-assembling its own committed fragments produced 416, so the map could not be
    reproduced from its sources and the difference was 49 silently-restored duplicates. Recording
    the decision here is what makes it survive, exactly as `drop_edges` does for a refuted edge."""

    src: str
    verb: str
    dst: str
    where: str


@dataclass
class AnchorDirective:
    """A skeptic-corrected anchor, keyed by the CLAIM it belongs to.

    `fix apply-drift` writes anchors into the ASSEMBLED map, and the next assemble rebuilds that map
    from fragments — discarding them. A live build corrected 14 anchors, re-assembled to pick up one
    fragment edit, lost all 14, and re-typed them by hand out of the human-readable listing into a
    bespoke script. Recorded here, the correction re-applies on every rebuild, exactly as
    `keep_edges` does for a de-duplication and `drop_edges` for a refuted edge."""

    claim: str
    corrected: str


@dataclass
class DropRelationDirective:
    """Which occurrence of a domain-card relation is removed.

    `fix dedup-relation` resolves a duplicate relation — the same edge declared twice on one card, or
    reciprocally on both — and wrote its answer into the ASSEMBLED map, which the next assemble
    rebuilds from fragments. That is worse than the same gap on `dedup-edge` and `apply-drift`,
    because a duplicate relation is BLOCKING: the resolution is discarded and the very next assemble
    re-blocks on the duplicate it had just resolved. It was the only writing verb with no way to
    record its decision.

    ONE occurrence per directive, matching the verb's own `--drop` semantics: `entity` names the card
    the relation is declared on, so a reciprocal pair is resolved by recording the side to remove."""

    entity: str
    verb: str
    target: str


@dataclass
class Reconcile:
    sets: list[SetDirective] = field(default_factory=list)
    drop_edges: list[DropEdgeDirective] = field(default_factory=list)
    keep_edges: list[KeepEdgeDirective] = field(default_factory=list)
    set_anchors: list[AnchorDirective] = field(default_factory=list)
    drop_relations: list[DropRelationDirective] = field(default_factory=list)

    def is_empty(self) -> bool:
        return (not self.sets and not self.drop_edges and not self.keep_edges
                and not self.set_anchors and not self.drop_relations)


# ── shared riding-step helpers (also used by `fix drop-edge`) ──────────────────────────────────────

def riding_steps(m: ProjectModel, src: str, dst: str) -> list[tuple[str, FlowStep]]:
    """Every flow / sub-flow step whose endpoints are the dropped edge's pair (undirected — a
    return-direction step rides the same edge), tagged with its flow/sub-flow id for reporting."""
    out: list[tuple[str, FlowStep]] = []
    pair = frozenset((src, dst))
    for f in m.flows:
        for st in f.steps:
            if not st.subflow and frozenset((st.src, st.dst)) == pair:
                out.append((f.uc, st))
    for sf in m.subflows:
        for st in sf.steps:
            if not st.subflow and frozenset((st.src, st.dst)) == pair:
                out.append((sf.id, st))
    return out


def repoint_riding(riding: list[tuple[str, FlowStep]], old_dst: str, new_dst: str) -> None:
    """Re-point every riding step's endpoint `old_dst` → `new_dst` in place."""
    for _owner, st in riding:
        if st.src == old_dst:
            st.src = new_dst
        if st.dst == old_dst:
            st.dst = new_dst


def drop_riding(m: ProjectModel, riding: list[tuple[str, FlowStep]]) -> None:
    """Remove every riding step from its flow / sub-flow, matched by object identity."""
    drop_ids = {id(st) for _o, st in riding}
    for f in m.flows:
        f.steps = [st for st in f.steps if id(st) not in drop_ids]
    for sf in m.subflows:
        sf.steps = [st for st in sf.steps if id(st) not in drop_ids]


# ── load ───────────────────────────────────────────────────────────────────────────────────────────

def _as_str_list(value: object, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ReconcileError(f"{where}: expected a list of strings")
    return [str(v) for v in value]


def load_reconcile(text: str, label: str) -> Reconcile:
    """Parse + structurally validate a reconcile file. Cross-refs (ids exist, kinds match) are the
    scoped `validate_reconcile` pass's job — this only checks the file is well-formed."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ReconcileError(f"{label}: not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ReconcileError(f"{label}: top level: expected an object")
    unknown = set(data) - {"set", "drop_edges", "keep_edges", "set_anchors", "drop_relations"}
    if unknown:
        raise ReconcileError(f"{label}: unknown top-level key(s): {', '.join(sorted(unknown))} "
                             f"(only 'set', 'drop_edges', 'keep_edges', 'set_anchors' and 'drop_relations' "
                             f"are allowed)")
    sets: list[SetDirective] = []
    raw_sets = data.get("set", [])
    if not isinstance(raw_sets, list):
        raise ReconcileError(f"{label}: 'set': expected a list")
    for i, d in enumerate(raw_sets):
        if not isinstance(d, dict):
            raise ReconcileError(f"{label}: set[{i}]: expected an object")
        unk = set(d) - ({"ids"} | set(_SET_FIELD_OWNER))
        if unk:
            raise ReconcileError(f"{label}: set[{i}]: unknown key(s): {', '.join(sorted(unk))}")
        if "ids" not in d:
            raise ReconcileError(f"{label}: set[{i}]: missing 'ids'")
        ids = _as_str_list(d["ids"], f"{label}: set[{i}].ids")
        if not ids:
            raise ReconcileError(f"{label}: set[{i}].ids: must name at least one element")
        sd = SetDirective(ids=ids)
        for fld in ("subsystem", "subdomain", "capability", "bucket", "block"):
            if fld in d:
                if not isinstance(d[fld], str):
                    raise ReconcileError(f"{label}: set[{i}].{fld}: expected a string")
                setattr(sd, fld, d[fld])
        if "runs_in" in d:
            sd.runs_in = _as_str_list(d["runs_in"], f"{label}: set[{i}].runs_in")
        if "entry_points" in d:
            raw_eps = d["entry_points"]
            if not isinstance(raw_eps, list):
                raise ReconcileError(f"{label}: set[{i}].entry_points: expected a list")
            eps: list[str] = []
            for j, v in enumerate(raw_eps):
                where = f"{label}: set[{i}].entry_points[{j}]"
                if isinstance(v, str):
                    eps.append(v)
                elif isinstance(v, dict):
                    unk_ep = set(v) - {"id", "source"}
                    if unk_ep:
                        raise ReconcileError(f"{where}: unknown key(s): {', '.join(sorted(unk_ep))} "
                                             f"(a witnessed entry point is {{\"id\", \"source\"}})")
                    eid_v, src_v = v.get("id"), v.get("source")
                    if not isinstance(eid_v, str) or not eid_v:
                        raise ReconcileError(f"{where}: 'id' is required (a non-empty string)")
                    if not isinstance(src_v, str) or not src_v:
                        raise ReconcileError(f"{where}: 'source' is required (the `path:line` you "
                                             f"saw on {eid_v}) — omit the object and write the bare "
                                             f"id if you have no anchor to witness with")
                    eps.append(eid_v)
                    sd.entry_point_witness[eid_v] = src_v
                else:
                    raise ReconcileError(f"{where}: expected an id string or "
                                         f"{{\"id\": …, \"source\": …}}")
            sd.entry_points = eps
        if not sd.assigned_fields():
            raise ReconcileError(f"{label}: set[{i}]: assigns no field — give at least one of "
                                 f"{', '.join(_SET_FIELD_OWNER)}")
        sets.append(sd)
    drops: list[DropEdgeDirective] = []
    raw_drops = data.get("drop_edges", [])
    if not isinstance(raw_drops, list):
        raise ReconcileError(f"{label}: 'drop_edges': expected a list")
    for i, d in enumerate(raw_drops):
        if not isinstance(d, dict):
            raise ReconcileError(f"{label}: drop_edges[{i}]: expected an object")
        unk = set(d) - {"src", "verb", "dst", "drop_steps", "repoint"}
        if unk:
            raise ReconcileError(f"{label}: drop_edges[{i}]: unknown key(s): {', '.join(sorted(unk))}")
        for req in ("src", "verb", "dst"):
            if not isinstance(d.get(req), str) or not d[req]:
                raise ReconcileError(f"{label}: drop_edges[{i}]: '{req}' is required (a non-empty string)")
        drop_steps = bool(d.get("drop_steps", False))
        repoint = d.get("repoint")
        if repoint is not None and not isinstance(repoint, str):
            raise ReconcileError(f"{label}: drop_edges[{i}].repoint: expected a string id")
        if drop_steps and repoint:
            raise ReconcileError(f"{label}: drop_edges[{i}]: 'drop_steps' and 'repoint' are mutually "
                                 f"exclusive")
        drops.append(DropEdgeDirective(src=d["src"], verb=d["verb"], dst=d["dst"],
                                       drop_steps=drop_steps, repoint=repoint))
    keeps: list[KeepEdgeDirective] = []
    raw_keeps = data.get("keep_edges", [])
    if not isinstance(raw_keeps, list):
        raise ReconcileError(f"{label}: 'keep_edges': expected a list")
    for i, d in enumerate(raw_keeps):
        if not isinstance(d, dict):
            raise ReconcileError(f"{label}: keep_edges[{i}]: expected an object")
        unk = set(d) - {"src", "verb", "dst", "where"}
        if unk:
            raise ReconcileError(f"{label}: keep_edges[{i}]: unknown key(s): {', '.join(sorted(unk))}")
        for req in ("src", "verb", "dst", "where"):
            if not isinstance(d.get(req), str) or not d[req].strip():
                raise ReconcileError(
                    f"{label}: keep_edges[{i}]: '{req}' is required (a non-empty string)")
        keeps.append(KeepEdgeDirective(src=d["src"], verb=d["verb"], dst=d["dst"],
                                       where=d["where"]))
    raw_anchors = data.get("set_anchors", [])
    if not isinstance(raw_anchors, list):
        raise ReconcileError(f"{label}: 'set_anchors': expected a list")
    anchors: list[AnchorDirective] = []
    for i, d in enumerate(raw_anchors):
        if not isinstance(d, dict):
            raise ReconcileError(f"{label}: set_anchors[{i}]: expected an object")
        unk = set(d) - {"claim", "corrected"}
        if unk:
            raise ReconcileError(f"{label}: set_anchors[{i}]: unknown key(s): {', '.join(sorted(unk))}")
        for req in ("claim", "corrected"):
            if not isinstance(d.get(req), str) or not d[req].strip():
                raise ReconcileError(
                    f"{label}: set_anchors[{i}]: '{req}' is required (a non-empty string)")
        anchors.append(AnchorDirective(claim=d["claim"], corrected=d["corrected"]))
    raw_relations = data.get("drop_relations", [])
    if not isinstance(raw_relations, list):
        raise ReconcileError(f"{label}: 'drop_relations': expected a list")
    relations: list[DropRelationDirective] = []
    for i, d in enumerate(raw_relations):
        if not isinstance(d, dict):
            raise ReconcileError(f"{label}: drop_relations[{i}]: expected an object")
        unk = set(d) - {"entity", "verb", "target"}
        if unk:
            raise ReconcileError(
                f"{label}: drop_relations[{i}]: unknown key(s): {', '.join(sorted(unk))}")
        for req in ("entity", "verb", "target"):
            if not isinstance(d.get(req), str) or not d[req].strip():
                raise ReconcileError(
                    f"{label}: drop_relations[{i}]: '{req}' is required (a non-empty string)")
        relations.append(DropRelationDirective(entity=d["entity"], verb=d["verb"],
                                               target=d["target"]))
    return Reconcile(sets=sets, drop_edges=drops, keep_edges=keeps, set_anchors=anchors,
                     drop_relations=relations)


# ── validate (scoped to the touched fields) ────────────────────────────────────────────────────────


def _same_anchor(actual: str, seen: str) -> bool:
    """Does a witnessed anchor still identify the same surface?

    Compared leniently on purpose. The witness exists to catch a RENUMBERING — one id now naming a
    different route in a different file — not to police how the anchor was written. So a witness that
    names the file and a line inside the same file matches: the entry point's own `source` may have
    been corrected by a drift fix between authoring and applying, and failing on that would make the
    check fire on the one thing that is not the bug."""
    a, s = actual.strip(), seen.strip()
    if not a or not s:
        return True
    return a == s or a.rsplit(":", 1)[0] == s.rsplit(":", 1)[0]


def validate_reconcile(m: ProjectModel, rec: Reconcile) -> list[str]:
    """Scoped, apply-time validation: every `set` id resolves and is the right KIND for the field, each
    `runs_in` value resolves to a `deployment[].unit`, each `subsystem`/`subdomain` value is a defined
    parent of the right kind (reusing `check_hierarchy`). `drop_edges` and `keep_edges` are NOT
    existence-checked here (a 0-match warns at apply time, never fails — S9b); only structural
    repoint sanity, and CONTRADICTIONS between directives, are checked. A contradiction is a
    different thing from a stale directive: two `keep_edges` naming one triple with different
    anchors cannot both be honoured, so it is the operator's mistake now, not drift to warn about
    later — and at apply time it surfaced as the misleading "declared 1 time(s), nothing to
    de-duplicate", because the first keep had already resolved the triple."""
    problems: list[str] = []
    seen_keep: dict[tuple[str, str, str], str] = {}
    for ki, ke in enumerate(rec.keep_edges):
        triple = (ke.src, ke.verb, ke.dst)
        prior = seen_keep.get(triple)
        if prior is not None and prior != ke.where:
            problems.append(f"reconcile keep_edges[{ki}]: {ke.src} {ke.verb} {ke.dst} is kept at "
                            f"'{prior}' by an earlier directive and at '{ke.where}' here — one "
                            f"triple can only survive at one anchor")
        seen_keep[triple] = prior if prior is not None else ke.where
    dropped = {(d.src, d.verb, d.dst) for d in rec.drop_edges}
    for ki, ke in enumerate(rec.keep_edges):
        if (ke.src, ke.verb, ke.dst) in dropped:
            problems.append(f"reconcile keep_edges[{ki}]: {ke.src} {ke.verb} {ke.dst} is also in "
                            f"`drop_edges` — keeping an anchor and removing the edge cannot both "
                            f"be meant; the drop would win")
    elements = all_elements(m)
    defined = set(elements) | {g.id for g in m.happy_path}
    units = {d.unit for d in m.deployment}
    cap_ids = {c.id for c in m.capabilities}
    blk_ids = {b.id for b in m.blocks}
    ep_ids = {ep.id for ep in m.entry_points if ep.id}
    ep_sources = {ep.id: (ep.source or "").strip() for ep in m.entry_points if ep.id}
    hier_parents: dict[str, str] = {}                # touched child → intended parent, for check_hierarchy
    for si, sd in enumerate(rec.sets):
        for eid in sd.ids:
            el = elements.get(eid)
            if el is None:
                problems.append(f"reconcile set[{si}]: unknown id '{eid}'")
                continue
            for fld in sd.assigned_fields():
                owner_type, owner_label = _SET_FIELD_OWNER[fld]
                if not isinstance(el, owner_type):
                    problems.append(f"reconcile set[{si}]: `{fld}` can only be set on a {owner_label}, "
                                    f"not {eid}")
                    continue
                if fld == "subsystem":
                    hier_parents[eid] = sd.subsystem  # type: ignore[assignment]
                elif fld == "subdomain":
                    hier_parents[eid] = sd.subdomain  # type: ignore[assignment]
                elif fld == "capability":
                    # A capability is a Group like a subsystem, but `check_hierarchy` reads the
                    # child's own kind to pick the expected parent prefix — a use case is not a
                    # component, so resolve it here instead: the target must be a defined CAP id.
                    cap = (sd.capability or "").strip()
                    if cap not in cap_ids:
                        problems.append(f"reconcile set[{si}] {eid}: capability '{cap}' is not a "
                                        f"defined capability (a `CAPn` in `capabilities[]`)")
                elif fld == "block":
                    # Same shape as `capability` one forest over: `check_hierarchy` picks the
                    # expected parent from the CHILD's prefix, and a rule is not a block, so resolve
                    # the target here — it must be a defined BLK id.
                    blk = (sd.block or "").strip()
                    if blk not in blk_ids:
                        problems.append(f"reconcile set[{si}] {eid}: block '{blk}' is not a "
                                        f"defined block (a `BLKn` in `blocks[]`)")
                elif fld == "entry_points":
                    bad_eps = [e for e in (sd.entry_points or []) if e not in ep_ids]
                    if bad_eps:
                        problems.append(f"reconcile set[{si}] {eid}: entry_points names unknown entry "
                                        f"point(s): {', '.join(bad_eps)} — ids are minted by "
                                        f"`assemble` from the harvested T4 rows, so author them "
                                        f"against the ids THIS assemble produces")
                    # The WITNESS check. An `EPn` that resolves is not an `EPn` that still means the
                    # same surface: the ids are minted from content and renumber when a surface is
                    # added, so a file authored against an older harvest points a use case at a
                    # different front door with nothing to see. Blocking, because the failure is
                    # silent and the map ships claiming the wrong door.
                    for ep_id, seen in (sd.entry_point_witness or {}).items():
                        actual = ep_sources.get(ep_id)
                        if actual is None or _same_anchor(actual, seen):
                            continue
                        problems.append(
                            f"reconcile set[{si}] {eid}: entry_points witnesses {ep_id} at "
                            f"'{seen}', but {ep_id} is now '{actual}' — entry-point ids are minted "
                            f"from content and RENUMBER when a surface is added, so this file was "
                            f"authored against an older harvest and would point {eid} at a different "
                            f"front door. Re-author the entry_points assignments against this "
                            f"assemble's ids (`coyodex dump --id {ep_id}` shows what it is now)")
                elif fld == "runs_in":
                    bad = [u for u in (sd.runs_in or []) if u not in units]
                    if bad:
                        problems.append(f"reconcile set[{si}] {eid}: runs_in names unknown deployment "
                                        f"unit(s): {', '.join(bad)} — each must match a `deployment[].unit`")
    if hier_parents:
        hp, _warn = check_hierarchy(hier_parents, defined)
        problems.extend(f"reconcile: {p}" for p in hp)
    for di, de in enumerate(rec.drop_edges):
        if de.repoint is not None and de.repoint not in elements:
            problems.append(f"reconcile drop_edges[{di}]: repoint target '{de.repoint}' is not a "
                            f"defined element")
    return problems


# ── apply (after merge + _derive_entity_edges, before write) ───────────────────────────────────────

def _is_reciprocal_relation(m: ProjectModel, dr: "DropRelationDirective") -> bool:
    """Is this relation ALSO declared from the other card — the reciprocal half of a duplicate?

    `fix dedup-relation` lists two blocking shapes: declared twice on ONE card, and declared on BOTH.
    The second leaves one occurrence per card, so a one-match is still a legitimate drop there and
    must not be mistaken for a stale directive."""
    other = next((e for e in m.entities if e.id == dr.target), None)
    if other is None:
        return False
    return any(r.target == dr.entity for r in other.relations)


def apply_reconcile(m: ProjectModel, rec: Reconcile, stats: dict[str, object]) -> list[str]:
    """Apply the directives in place. Assumes `validate_reconcile` already passed (ids/kinds sound), so
    it skips defensively on any residual mismatch. Fills `stats` for the assemble summary and returns
    per-directive human notes (0-match warnings, riding-step reports/heals). MUST run AFTER
    `_derive_entity_edges` (B1) so a dropped C→E edge is not re-derived from its step in the same run."""
    notes: list[str] = []
    elements = all_elements(m)
    # BEFORE the drops, deliberately: a keep narrows a triple to one row, and a later `drop_edges`
    # for the same triple should then see the single survivor rather than a set it no longer
    # describes. A 0-match keep WARNS and never fails, like `drop_edges` — the anchor may have been
    # corrected since, and a reconcile file must not rot when a fragment is fixed.
    kept_total = 0
    for ke in rec.keep_edges:
        idxs = [i for i, e in enumerate(m.edges)
                if e.src == ke.src and e.verb == ke.verb and e.dst == ke.dst]
        if len(idxs) < 2:
            notes.append(f"keep_edges: {ke.src} {ke.verb} {ke.dst} is declared "
                         f"{len(idxs)} time(s) — nothing to de-duplicate")
            continue
        survivors = [i for i in idxs if (m.edges[i].where or "") == ke.where]
        if not survivors:
            notes.append(f"keep_edges: none of {ke.src} {ke.verb} {ke.dst}'s {len(idxs)} "
                         f"occurrences is anchored at '{ke.where}' — kept them all")
            continue
        drop = {i for i in idxs if i != survivors[0]}
        m.edges = [e for i, e in enumerate(m.edges) if i not in drop]
        kept_total += len(drop)
    if kept_total:
        stats["duplicate_edges_resolved"] = kept_total
    # Anchor corrections, through the SAME writer `fix apply-drift` uses — one matching rule, so the
    # durable record and the in-place edit cannot disagree about which element a claim names. A
    # claim that no longer matches anything NOTES and never fails, like the two directives above: a
    # reconcile file must not rot when a later fragment edit rewrites the claim it was keyed on.
    if rec.set_anchors:
        counts, anchor_notes = apply_anchor_corrections(
            m, [(a.claim, a.corrected) for a in rec.set_anchors])
        notes.extend(n.strip() for n in anchor_notes if not n.startswith("  "))
        applied = sum(counts.values())
        if applied:
            stats["anchors_corrected"] = applied
    set_counts: dict[str, int] = {f: 0 for f in _SET_FIELD_OWNER}
    for sd in rec.sets:
        for eid in sd.ids:
            el = elements.get(eid)
            if el is None:
                continue
            if sd.subsystem is not None and isinstance(el, Component):
                el.subsystem = sd.subsystem
                set_counts["subsystem"] += 1
            if sd.subdomain is not None and isinstance(el, Entity):
                el.subdomain = sd.subdomain
                set_counts["subdomain"] += 1
            if sd.capability is not None and isinstance(el, UseCase):
                el.capability = sd.capability
                set_counts["capability"] += 1
            if sd.entry_points is not None and isinstance(el, UseCase):
                el.entry_points = list(sd.entry_points)    # REPLACE the list → idempotent re-run
                set_counts["entry_points"] += 1
            if sd.runs_in is not None and isinstance(el, Component):
                el.runs_in = list(sd.runs_in)              # REPLACE the list → idempotent re-run (S9c)
                set_counts["runs_in"] += 1
            if sd.bucket is not None and isinstance(el, Dep):
                el.bucket = sd.bucket
                set_counts["bucket"] += 1
            if sd.block is not None and isinstance(el, BusinessRule):
                el.block = sd.block
                set_counts["block"] += 1
    stats["reconcile_set"] = set_counts
    dropped_total = 0
    # Riding steps left unhealed by a report-only drop. Counted here so `assemble` can put the number
    # in its FINAL summary line: the per-directive detail below is multi-line and a live build cut it
    # with `| tail -4`, so the two orphaned steps only surfaced a full round later at the next
    # validate, costing a fragment edit + re-assemble + a re-run of apply-drift. A count that rides
    # the last line cannot be truncated away by reading the tail.
    unhealed_total = 0
    for de in rec.drop_edges:
        verb = de.verb.strip().lower()
        kept = [e for e in m.edges
                if not (e.src == de.src and e.verb.strip().lower() == verb and e.dst == de.dst)]
        removed = len(m.edges) - len(kept)
        if removed == 0:
            notes.append(f"WARNING: reconcile drop_edges '{de.src} {verb} {de.dst}' matched 0 edges — "
                         f"nothing dropped (the directive may outlive the edge; not an error).")
            continue
        m.edges = kept
        dropped_total += removed
        riding = riding_steps(m, de.src, de.dst)
        head = f"reconcile drop_edges '{de.src} {verb} {de.dst}': removed {removed} edge(s)"
        if de.repoint:
            repoint_riding(riding, de.dst, de.repoint)
            notes.append(f"note: {head}; re-pointed {len(riding)} riding step(s) {de.dst} → {de.repoint}.")
        elif de.drop_steps:
            drop_riding(m, riding)
            notes.append(f"note: {head} and {len(riding)} riding step(s).")
        elif riding:
            unhealed_total += len(riding)
            lines = [f"note: {head}. {len(riding)} flow step(s) rode it and now attribute "
                     f"{de.src}↔{de.dst} with no backing edge (validate warns on C↔E; C↔C is silent) — "
                     f"reconcile them via `drop_steps` / `repoint`, or edit by hand:"]
            for owner, st in riding:
                lines.append(f"    {owner} step {st.n}: {st.src} → {st.dst}  ({st.phrase or '—'})")
            notes.append("\n".join(lines))
        else:
            notes.append(f"note: {head}.")
    stats["reconcile_edges_dropped"] = dropped_total
    stats["reconcile_riding_unhealed"] = unhealed_total
    # `drop_relations` LAST, and by itself: a domain-card relation is not an edge and shares none of
    # the riding-step machinery above. A 0-match WARNS rather than fails, like `drop_edges` — a
    # reconcile file must not rot when the fragment that declared the duplicate is later fixed.
    relations_dropped = 0
    for dr in rec.drop_relations:
        ent = next((e for e in m.entities if e.id == dr.entity), None)
        if ent is None:
            notes.append(f"WARNING: reconcile drop_relations: no entity '{dr.entity}' — skipped "
                         f"(the card may have been renamed or removed since).")
            continue
        matches = [k for k, r in enumerate(ent.relations)
                   if r.verb.lower() == dr.verb.lower() and r.target == dr.target]
        if not matches:
            notes.append(f"WARNING: reconcile drop_relations: {dr.entity} declares no "
                         f"'{dr.verb} → {dr.target}' — skipped (already resolved in the fragment?).")
            continue
        # The directive means "drop ONE OCCURRENCE OF A DUPLICATE". Applying it to a lone occurrence
        # deletes a real domain fact, and the normal repair order makes that the DEFAULT outcome:
        # record the directive, then fix the duplicate at source in the fragment, and the next
        # assemble silently removes the survivor — reported as a `note:` and counted as a success.
        # So the precondition is re-checked against the model being assembled, every time.
        if len(matches) == 1 and not _is_reciprocal_relation(m, dr):
            notes.append(f"WARNING: reconcile drop_relations: {dr.entity} declares "
                         f"'{dr.verb} → {dr.target}' ONCE — it is no longer a duplicate, so the "
                         f"directive is stale and was NOT applied (dropping it would delete the only "
                         f"occurrence). Remove the directive.")
            continue
        idx = matches[0]
        del ent.relations[idx]                        # ONE occurrence, like `fix dedup-relation`
        relations_dropped += 1
        notes.append(f"note: reconcile drop_relations '{dr.entity}: {dr.verb} → {dr.target}': "
                     f"removed 1 relation.")
    stats["reconcile_relations_dropped"] = relations_dropped
    return notes
