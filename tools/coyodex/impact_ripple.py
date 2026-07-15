"""Impact engine — the ripple layer + the ImpactResult payload (PURE half, M2).

Design: internal/docs/impact-and-update-design.md (Part I, "Ripple"). Semantics are PINNED:
typed ripple rules apply ONCE, from the direct-hit set only; a rippled element never re-fires;
data ripple (C→E→C) does not chain. The only multi-hop mechanism is the OPT-IN call-graph ripple,
depth-capped and distance-decayed. (Measured rationale: one-hop cones average ~5 elements on live
maps; the chaining reading saturates dense maps through the repository expander.)

Strength lattice (lower = stronger; drives overlay emphasis and sort order):
  1 direct-line · 2 direct-symbol · 3 direct-file · 4 structural · 5 behavioral · 6 data ·
  7 call-graph (+depth) · 8 territory
An element reached both directly and by ripple keeps its direct cause/change/resolution but takes
the strongest strength (this is the aggregation rule: a subsystem's badge reflects its strongest
member-derived signal, not its own weak territory hit).

Noise defaults: structural + behavioral + persists/writes data ripple ON; reads-only data links,
entity-graph (E↔E card relations) and transitive call-graph OFF (opt-in).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from coyodex.impact_git import ImpactCore
from coyodex.impact_lib import DirectHit
from coyodex.model import FlowStep, ProjectModel

# ── the lattice ───────────────────────────────────────────────────────────────────────────────────

RANK_DIRECT = {"line": 1, "symbol": 2, "file": 3}
R_STRUCTURAL, R_BEHAVIORAL, R_DATA, R_CALLGRAPH, R_TERRITORY = 4, 5, 6, 7, 8

_ID_RE = re.compile(r"^(SD|SF|UC|HP|C|D|E|S)(\d+)$")

_KIND_BY_PREFIX = {"C": "components", "D": "deps", "E": "entities", "S": "subsystems",
                   "SD": "subdomains", "SF": "subflows", "UC": "use_cases", "HP": "happy_path"}
_KIND_BY_SYNTH = {"edge": "edges", "ep": "entry_points", "step": "flow_steps",
                  "glossary": "glossary", "security": "security", "run": "run_commands",
                  "net": "non_entity_types"}

# `changes` severity when one element is hit several ways (a real change outranks a drift)
_CHANGE_ORDER = ["deleted", "added", "modified", "drifted"]

_DATA_STRONG = {"persists", "writes"}     # ownership C→E verbs (on by default)
_DATA_WEAK = {"reads"}                    # consumption (opt-in)


def type_of(eid: str) -> str:
    m = _ID_RE.match(eid)
    if m:
        return _KIND_BY_PREFIX[m.group(1)]
    return _KIND_BY_SYNTH.get(eid.split(":", 1)[0], "other")


@dataclass
class RippleOptions:
    reads: bool = False           # follow read-only C↔E links
    entity_graph: bool = False    # follow E↔E domain-card relations
    callgraph: bool = False       # transitive C↔C along backbone edges
    callgraph_depth: int = 2


@dataclass
class _Impact:
    eid: str
    cause: str                    # "direct" | "ripple"
    change: str                   # added|modified|deleted|drifted | "affected" (ripple)
    resolution: str | None        # direct hits only
    strength: int
    distance: int
    via: list[dict] = field(default_factory=list)   # [{"from": eid, "relation": str}], best path
    files: set = field(default_factory=set)


# ── model lookups (built once per call) ───────────────────────────────────────────────────────────

class _Maps:
    def __init__(self, model: ProjectModel) -> None:
        self.parent_of: dict[str, str] = {}
        for c in model.components:
            if c.subsystem:
                self.parent_of[c.id] = c.subsystem
        for g in list(model.subsystems) + list(model.subdomains):
            if g.parent:
                self.parent_of[g.id] = g.parent
        for e in model.entities:
            if e.subdomain:
                self.parent_of[e.id] = e.subdomain

        ids: set[str] = ({c.id for c in model.components} | {d.id for d in model.deps}
                         | {e.id for e in model.entities})
        # behavioral: element → the use cases whose flow steps touch it; plus edge-pair → use cases.
        # Flows are EXPANDED (sub-flow references replaced by the sub-flow's steps), so a component
        # touched only inside a shared sub-flow still ripples to every referencing use case.
        self.ucs_of: dict[str, set[str]] = {}
        self.pair_ucs: dict[frozenset, set[str]] = {}
        self.sf_ucs: dict[str, set[str]] = {}   # sub-flow id → the use cases whose flows reference it
        self.unmatched_steps: list[str] = []
        seen_unmatched: set[tuple[str, int]] = set()  # a shared sub-flow step warns ONCE, as itself
        edge_pairs = {frozenset((ed.src, ed.dst)) for ed in model.edges}
        sfs = {sf.id: sf for sf in model.subflows}
        for f in model.flows:
            # expand inline, keeping each step's ORIGIN (the flow's uc, or the sub-flow's id) so an
            # unmatched-step warning names the container the step is actually authored in
            steps_with_origin: list[tuple[str, FlowStep]] = []
            for st in f.steps:
                sf = sfs.get(st.subflow or "")
                if st.subflow:
                    self.sf_ucs.setdefault(st.subflow, set()).add(f.uc)
                if sf is None or not sf.steps:
                    steps_with_origin.append((f.uc, st))
                else:
                    steps_with_origin.extend((sf.id, s) for s in sf.steps)
            for origin, st in steps_with_origin:
                ends = [x for x in (st.src, st.dst) if x in ids]
                for x in ends:
                    self.ucs_of.setdefault(x, set()).add(f.uc)
                if len(ends) == 2:
                    pair = frozenset(ends)
                    self.pair_ucs.setdefault(pair, set()).add(f.uc)
                    if pair not in edge_pairs and (origin, st.n) not in seen_unmatched:
                        seen_unmatched.add((origin, st.n))
                        self.unmatched_steps.append(
                            f"{origin} step {st.n}: {st.src} → {st.dst} matches no backbone edge")
        self.hp_of: dict[str, list[str]] = {}
        for hp in model.happy_path:
            if hp.uc:
                self.hp_of.setdefault(hp.uc, []).append(hp.id)

        # data: C→E ownership vs consumption, both directions
        self.owned_entities: dict[str, set[str]] = {}
        self.read_entities: dict[str, set[str]] = {}
        self.owner_comps: dict[str, set[str]] = {}
        self.reader_comps: dict[str, set[str]] = {}
        # call-graph: C↔C adjacency (undirected walk)
        self.adj: dict[str, set[str]] = {}
        comp_ids = {c.id for c in model.components}
        for ed in model.edges:
            if ed.src in comp_ids and ed.dst.startswith("E"):
                if ed.verb in _DATA_STRONG:
                    self.owned_entities.setdefault(ed.src, set()).add(ed.dst)
                    self.owner_comps.setdefault(ed.dst, set()).add(ed.src)
                elif ed.verb in _DATA_WEAK:
                    self.read_entities.setdefault(ed.src, set()).add(ed.dst)
                    self.reader_comps.setdefault(ed.dst, set()).add(ed.src)
            if ed.src in comp_ids and ed.dst in comp_ids:
                self.adj.setdefault(ed.src, set()).add(ed.dst)
                self.adj.setdefault(ed.dst, set()).add(ed.src)

        # entity-graph: E↔E from the domain cards (authored one side; walked both ways)
        self.related: dict[str, set[str]] = {}
        for e in model.entities:
            for r in e.relations:
                self.related.setdefault(e.id, set()).add(r.target)
                self.related.setdefault(r.target, set()).add(e.id)


# ── the ripple (single application from the direct set) ──────────────────────────────────────────

def build_impact_result(model: ProjectModel, core: ImpactCore,
                        opts: RippleOptions | None = None,
                        file_scope: str | None = None) -> dict:
    """The full ImpactResult payload: consolidated direct hits + one application of the typed
    ripple rules, with provenance. `file_scope` restricts the direct set to one changed file's
    cone (path OR its P-frame path)."""
    opts = opts or RippleOptions()
    maps = _Maps(model)
    impacts: dict[str, _Impact] = {}

    def register_ripple(eid: str, strength: int, distance: int, via: list[dict],
                        files: set) -> None:
        cur = impacts.get(eid)
        if cur is None:
            impacts[eid] = _Impact(eid, "ripple", "affected", None, strength, distance,
                                   via, set(files))
            return
        cur.files |= files
        if (strength, distance) < (cur.strength, cur.distance):
            cur.strength, cur.distance = strength, distance
            if cur.cause == "ripple":
                cur.via = via

    # 1. consolidate direct hits (an element may be hit by several anchors/files)
    scoped_files = [f for f in core.files
                    if file_scope is None or file_scope in (f.path, f.p_path)]
    for f in scoped_files:
        for h in f.hits:
            rank = R_TERRITORY if h.territory else RANK_DIRECT[h.resolution]
            cur = impacts.get(h.eid)
            if cur is None or cur.cause == "ripple":
                impacts[h.eid] = _Impact(h.eid, "direct", h.change, h.resolution, rank, 0,
                                         [], {f.path} | (cur.files if cur else set()))
                continue
            cur.files.add(f.path)
            cur.strength = min(cur.strength, rank)
            if RANK_DIRECT.get(h.resolution, 9) < RANK_DIRECT.get(cur.resolution or "", 9):
                cur.resolution = h.resolution
            if _CHANGE_ORDER.index(h.change) < _CHANGE_ORDER.index(cur.change):
                cur.change = h.change

    direct = [i for i in impacts.values() if i.cause == "direct"]

    # 2. one application of the typed rules, from the direct set only (never re-fired)
    for d in list(direct):
        eid, files = d.eid, d.files

        def structural_chain(start: str, first_rel: str) -> None:
            rel, cur_id, via = first_rel, start, []
            while cur_id in maps.parent_of:
                parent = maps.parent_of[cur_id]
                via = via + [{"from": cur_id, "relation": rel}]
                register_ripple(parent, R_STRUCTURAL, 1, via, files)
                cur_id, rel = parent, "parent-of"

        def behavioral(elem: str, via_prefix: list[dict]) -> None:
            for uc in sorted(maps.ucs_of.get(elem, ())):
                via = via_prefix + [{"from": elem, "relation": "flow"}]
                register_ripple(uc, R_BEHAVIORAL, 1, via, files)
                for hp in maps.hp_of.get(uc, ()):
                    register_ripple(hp, R_BEHAVIORAL, 1,
                                    via + [{"from": uc, "relation": "happy-path"}], files)

        if eid.startswith("edge:"):
            src, _verb, dst = eid.removeprefix("edge:").split(">", 2)
            for endpoint in (src, dst):
                register_ripple(endpoint, R_STRUCTURAL, 1,
                                [{"from": eid, "relation": "edge-endpoint"}], files)
            for uc in sorted(maps.pair_ucs.get(frozenset((src, dst)), ())):
                via = [{"from": eid, "relation": "flow-pair"}]
                register_ripple(uc, R_BEHAVIORAL, 1, via, files)
                for hp in maps.hp_of.get(uc, ()):
                    register_ripple(hp, R_BEHAVIORAL, 1,
                                    via + [{"from": uc, "relation": "happy-path"}], files)
            continue
        if eid.startswith("ep:"):
            hit = next((h for f in scoped_files for h in f.hits if h.eid == eid), None)
            owner = hit.owner if hit else None
            if owner:
                register_ripple(owner, R_STRUCTURAL, 1,
                                [{"from": eid, "relation": "entry-point"}], files)
                behavioral(owner, [{"from": eid, "relation": "entry-point"}])
            continue
        if eid.startswith("step:"):
            # A hit flow step (its own `where` changed) ripples to its two element endpoints and —
            # the precise behavioral rung — to its use case(s) + their HP steps. A flow's step
            # names ONE use case directly (no pair-level over-approximation, unlike the edge branch
            # above); a SUB-FLOW's step reaches every use case whose flow references the sub-flow —
            # still precise, via explicit references.
            owner, n_str = eid.removeprefix("step:").split(":", 1)
            if owner.startswith("SF"):
                step = next((st for sf in model.subflows if sf.id == owner
                             for st in sf.steps if str(st.n) == n_str), None)
                ucs = sorted(maps.sf_ucs.get(owner, ()))
            else:
                step = next((st for fl in model.flows if fl.uc == owner
                             for st in fl.steps if str(st.n) == n_str), None)
                ucs = [owner]
            if step is not None:
                for endpoint in (step.src, step.dst):
                    if _ID_RE.match(endpoint):  # element endpoints only — a Role has no node
                        register_ripple(endpoint, R_STRUCTURAL, 1,
                                        [{"from": eid, "relation": "step-endpoint"}], files)
            via = [{"from": eid, "relation": "flow-step"}]
            for uc in ucs:
                register_ripple(uc, R_BEHAVIORAL, 1, via, files)
                for hp in maps.hp_of.get(uc, ()):
                    register_ripple(hp, R_BEHAVIORAL, 1,
                                    via + [{"from": uc, "relation": "happy-path"}], files)
            continue
        kind = type_of(eid)
        if kind == "components":
            structural_chain(eid, "member-of")
            behavioral(eid, [])
            for ent in sorted(maps.owned_entities.get(eid, ())):
                register_ripple(ent, R_DATA, 1, [{"from": eid, "relation": "persists"}], files)
            if opts.reads:
                for ent in sorted(maps.read_entities.get(eid, ())):
                    register_ripple(ent, R_DATA, 1, [{"from": eid, "relation": "reads"}], files)
            if opts.callgraph:
                seen, frontier = {eid}, {eid}
                for depth in range(1, opts.callgraph_depth + 1):
                    frontier = {n for c in frontier for n in maps.adj.get(c, ()) if n not in seen}
                    seen |= frontier
                    for n in sorted(frontier):
                        register_ripple(n, R_CALLGRAPH, depth,
                                        [{"from": eid, "relation": "calls"}], files)
        elif kind == "entities":
            structural_chain(eid, "member-of")
            behavioral(eid, [])
            for comp in sorted(maps.owner_comps.get(eid, ())):
                register_ripple(comp, R_DATA, 1, [{"from": eid, "relation": "persisted-by"}], files)
            if opts.reads:
                for comp in sorted(maps.reader_comps.get(eid, ())):
                    register_ripple(comp, R_DATA, 1, [{"from": eid, "relation": "read-by"}], files)
            if opts.entity_graph:
                for other in sorted(maps.related.get(eid, ())):
                    register_ripple(other, R_DATA, 1, [{"from": eid, "relation": "related"}], files)
        elif kind == "deps":
            behavioral(eid, [])
        elif kind in ("subsystems", "subdomains"):
            structural_chain(eid, "parent-of")

    # 3. the payload
    by_type: dict[str, list[str]] = {}
    for i in impacts.values():
        by_type.setdefault(type_of(i.eid), []).append(i.eid)
    for lst in by_type.values():
        lst.sort(key=lambda e: (impacts[e].strength, impacts[e].distance, e))
    counts = {"direct": sum(1 for i in impacts.values() if i.cause == "direct"),
              "ripple": sum(1 for i in impacts.values() if i.cause == "ripple"),
              "by_change": {}, "by_type": {k: len(v) for k, v in sorted(by_type.items())}}
    for i in impacts.values():
        counts["by_change"][i.change] = counts["by_change"].get(i.change, 0) + 1

    warnings = list(core.warnings)
    if maps.unmatched_steps:
        warnings.append(
            f"map quality: {len(maps.unmatched_steps)} flow step(s) match no backbone edge "
            f"(their impact reaches use cases only via component-level ripple) — e.g. "
            + "; ".join(maps.unmatched_steps[:3]))

    return {
        "spec": {"pin": core.pin, "base": core.base, "target": core.target,
                 "file": file_scope,
                 "options": {"reads": opts.reads, "entity_graph": opts.entity_graph,
                             "callgraph": opts.callgraph,
                             "callgraph_depth": opts.callgraph_depth}},
        "files": [{"path": f.path, "p_path": f.p_path, "status": f.status,
                   "elements": sorted({h.eid for h in f.hits})} for f in scoped_files],
        "impacts": {eid: {"cause": i.cause, "change": i.change, "resolution": i.resolution,
                          "strength": i.strength, "distance": i.distance, "via": i.via,
                          "files": sorted(i.files)}
                    for eid, i in sorted(impacts.items())},
        "byType": by_type,
        "counts": counts,
        "warnings": warnings,
    }
