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

from coyodex.model import Component, Dep, Entity, FlowStep, ProjectModel, all_elements
from coyodex.validate_analysis import check_hierarchy


class ReconcileError(Exception):
    """A malformed reconcile file (bad JSON, unknown key, wrong-shape directive). Raised at load time
    so `assemble` fails loudly with the file named, before anything is written."""


# field name → (target element type, human label) — a `set` field is legal only on its owner type.
_SET_FIELD_OWNER: dict[str, tuple[type, str]] = {
    "subsystem": (Component, "component"),
    "subdomain": (Entity, "entity"),
    "runs_in": (Component, "component"),
    "bucket": (Dep, "dependency"),
}


@dataclass
class SetDirective:
    ids: list[str]
    subsystem: str | None = None
    subdomain: str | None = None
    runs_in: list[str] | None = None
    bucket: str | None = None

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
class Reconcile:
    sets: list[SetDirective] = field(default_factory=list)
    drop_edges: list[DropEdgeDirective] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.sets and not self.drop_edges


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
    unknown = set(data) - {"set", "drop_edges"}
    if unknown:
        raise ReconcileError(f"{label}: unknown top-level key(s): {', '.join(sorted(unknown))} "
                             f"(only 'set' and 'drop_edges' are allowed)")
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
        for fld in ("subsystem", "subdomain", "bucket"):
            if fld in d:
                if not isinstance(d[fld], str):
                    raise ReconcileError(f"{label}: set[{i}].{fld}: expected a string")
                setattr(sd, fld, d[fld])
        if "runs_in" in d:
            sd.runs_in = _as_str_list(d["runs_in"], f"{label}: set[{i}].runs_in")
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
    return Reconcile(sets=sets, drop_edges=drops)


# ── validate (scoped to the touched fields) ────────────────────────────────────────────────────────

def validate_reconcile(m: ProjectModel, rec: Reconcile) -> list[str]:
    """Scoped, apply-time validation: every `set` id resolves and is the right KIND for the field, each
    `runs_in` value resolves to a `deployment[].unit`, each `subsystem`/`subdomain` value is a defined
    parent of the right kind (reusing `check_hierarchy`). `drop_edges` are NOT existence-checked here
    (a 0-match warns at apply time, never fails — S9b); only structural repoint sanity is checked."""
    problems: list[str] = []
    elements = all_elements(m)
    defined = set(elements) | {g.id for g in m.happy_path}
    units = {d.unit for d in m.deployment}
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

def apply_reconcile(m: ProjectModel, rec: Reconcile, stats: dict[str, object]) -> list[str]:
    """Apply the directives in place. Assumes `validate_reconcile` already passed (ids/kinds sound), so
    it skips defensively on any residual mismatch. Fills `stats` for the assemble summary and returns
    per-directive human notes (0-match warnings, riding-step reports/heals). MUST run AFTER
    `_derive_entity_edges` (B1) so a dropped C→E edge is not re-derived from its step in the same run."""
    notes: list[str] = []
    elements = all_elements(m)
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
            if sd.runs_in is not None and isinstance(el, Component):
                el.runs_in = list(sd.runs_in)              # REPLACE the list → idempotent re-run (S9c)
                set_counts["runs_in"] += 1
            if sd.bucket is not None and isinstance(el, Dep):
                el.bucket = sd.bucket
                set_counts["bucket"] += 1
    stats["reconcile_set"] = set_counts
    dropped_total = 0
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
            lines = [f"note: {head}. {len(riding)} flow step(s) rode it and now attribute "
                     f"{de.src}↔{de.dst} with no backing edge (validate warns on C↔E; C↔C is silent) — "
                     f"reconcile them via `drop_steps` / `repoint`, or edit by hand:"]
            for owner, st in riding:
                lines.append(f"    {owner} step {st.n}: {st.src} → {st.dst}  ({st.phrase or '—'})")
            notes.append("\n".join(lines))
        else:
            notes.append(f"note: {head}.")
    stats["reconcile_edges_dropped"] = dropped_total
    return notes
