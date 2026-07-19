#!/usr/bin/env python3
"""Build the view bundle a coyodex map's frontend renders — the graph plus every pre-rendered diagram.

Reads a graph.json (from build_graph.py) and (optionally) a change-impact report and produces a
`ViewBundle` (via `build_view_bundle`): the graph, every altitude's Mermaid source, the use-case
flows, colours, and source-link config. `coyodex serve` calls this per request and serves the bundle
as JSON at /p/<slug>/api/view; the generic frontend (viewer.html + viewer.js/css, served from the
same folder) fetches it and renders. Mermaid + svg-pan-zoom load from a pinned CDN with SRI.
The viewer offers these altitudes — Context (C4; external SYSTEMS drawn by name, while in-process
framework/library deps fold into one ⌘-clickable "Libraries" box that drills to the full list) →
Subsystems (click a box to select it + its linked
subsystems, or ⌘-click to drill in; click an arrow to select it — the side panel lists every
component edge it bundles — or ⌘-click to drill into the pair's edge card; while ⌘ is held, drillable
boxes/arrows show a drill-in cursor) → a subsystem's components → code links — navigated as a
back/forward history within one frame, wraps Mermaid's SVG with pan/zoom and a click->side-panel
bridge, and a baseline<->diff toggle (on the Subsystems views) that badges added/modified/deleted/
rippled elements. A map with no subsystem of its own gets one synthetic default subsystem (build_graph),
so the component-level view is always reached by drilling a subsystem. The flat whole-repo component
map (gen_mermaid / MERMAID_BASE / MERMAID_DIFF and the viewer's `component` state) is no longer wired
to a tab — it is kept dormant and restorable.

Node labels are the element name only (no ID prefix) to keep them uncluttered;
the ID still appears in the panel header and drives the bridge via the cy-<ID>
class.

Normally called in-process by `coyodex serve`. For two-stage debugging (dumps the bundle JSON):
    python -m coyodex.viewer.gen_viewer [graph.json] [view-bundle.json] [report.md]
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from html import escape as html_escape
from pathlib import Path
from typing import Any, TypedDict, cast

from coyodex.viewer.build_graph import DiffDict, GraphDict, build_diff
from coyodex.grammar import (  # external-dep Kind fold rule + the purpose-bucket grouping axis
    DEP_BUCKET_FOLD_AT, DEP_KINDS_FOLDED, DEP_KINDS_SYSTEM, canonical_bucket, order_buckets,
    resolve_bucket, unit_name_matches_dep,
)

# Synthetic node id for the collapsed "Libraries" box in the Context view (folds framework + library
# deps out of the C4 Context altitude). Not a real element id (no prefix+digits), so it never
# collides; the viewer resolves it via its `cy-LIBS` class and the synthetic node added to the panel
# graph. The viewer.js side uses the same literal — keep them in step.
LIBS_ID = "LIBS"


def _git(args: list[str], cwd: Path) -> str | None:
    """Run a read-only git command in `cwd`; return stripped stdout, or None on any failure
    (not a repo, git missing, no remote). Build-time only — never blocks rendering."""
    try:
        out = subprocess.run(["git", "-C", str(cwd), *args],
                             capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def repo_root_default(anchor: Path) -> str:
    """Absolute path of the mapped repo, seeded into the viewer as the default source root for
    'open in editor' links. The viewer overrides this with a per-machine value in localStorage, so a
    wrong path on a teammate's checkout is fixable in Settings without a rebuild. Falls back to the
    output file's directory when `anchor` is not inside a git work tree."""
    top = _git(["rev-parse", "--show-toplevel"], anchor)
    return top or str(anchor.resolve())


def gh_repo_url(anchor: Path) -> str | None:
    """GitHub repository URL ('https://github.com/<owner>/<repo>') from the `origin` remote, for the
    'open on GitHub' target. None when there is no `origin` remote or it is not github.com. The viewer
    combines this with the map's commit into blob links and lets the user override the URL in Settings."""
    url = _git(["remote", "get-url", "origin"], anchor)
    if not url:
        return None
    m = re.search(r"github\.com[:/]+([^/]+)/(.+?)(?:\.git)?/?$", url)
    return f"https://github.com/{m.group(1)}/{m.group(2)}" if m else None

SHAPE = {"component": ('["', '"]'), "dep": ('[("', '")]')}
DIAGRAM_KINDS = ("component", "dep")

# Domain (T5) relationship kind -> Mermaid classDiagram arrow. The diamond/triangle sits at the
# `src` (left) end, matching how the relation is authored on the source entity's card.
CLASS_ARROW = {"inheritance": "--|>", "composition": "*--", "aggregation": "o--", "association": "-->"}


def _safe_label(name: str) -> str:
    """Sanitize a node name for a Mermaid label: backticks trigger markdown-string mode,
    brackets/quotes break node-shape syntax."""
    return (
        name.replace('"', "'")
        .replace("`", "")
        .replace("[", "(")
        .replace("]", ")")
    )


def _draw_nodes(graph: GraphDict, diff: DiffDict | None) -> list[tuple[str, str, str]]:
    """(id, label, kind) for every node drawn at component level, incl. added ones."""
    out: list[tuple[str, str, str]] = []
    for nid, node in graph["nodes"].items():
        kind = str(node["kind"])
        if kind in DIAGRAM_KINDS:
            out.append((nid, str(node["name"]), kind))
    if diff:
        for c in diff["changes"]:
            if c["change"] == "added" and c["kind"] in DIAGRAM_KINDS:
                out.append((c["id"], c["name"] or c["id"], c["kind"]))
    return out


def _diagram_edges(graph: GraphDict, diff: DiffDict | None, ids: set[str]) -> list[tuple[str, str, str]]:
    edges: list[tuple[str, str, str]] = [
        (str(e["src"]), str(e["verb"]), str(e["dst"])) for e in graph["edges"]
    ]
    if diff:
        edges += [(e["src"], e["verb"], e["dst"]) for e in diff["new_edges"]]
    return [(s, v, d) for (s, v, d) in edges if s in ids and d in ids]


def gen_mermaid(graph: GraphDict, diff: DiffDict | None = None, only: set[str] | None = None) -> str:
    """Nodes keep their baseline kind styling; change status is shown by JS badges, not fill.
    `only` (a set of ids) restricts the drawing to those components + the deps they touch — used
    for the per-subsystem drill-down view."""
    draw = _draw_nodes(graph, diff)
    if only is not None:
        keep = set(only)
        for e in graph["edges"]:
            s, d = str(e["src"]), str(e["dst"])
            if s in keep and str(graph["nodes"].get(d, {}).get("kind")) == "dep":
                keep.add(d)
            if d in keep and str(graph["nodes"].get(s, {}).get("kind")) == "dep":
                keep.add(s)
        draw = [(nid, name, kind) for (nid, name, kind) in draw if nid in keep]
    ids = {nid for nid, _, _ in draw}
    lines = ["flowchart TB"]
    for nid, name, kind in draw:
        open_b, close_b = SHAPE[kind]
        label = _safe_label(name)  # name only — no ID prefix
        lines.append(f"  {nid}{open_b}{label}{close_b}:::cy-{nid}")
        lines.append(f"  class {nid} {kind}")
    for src, verb, dst in _diagram_edges(graph, diff, ids):
        lines.append(f"  {src} -->|{verb}| {dst}")
    lines.append(f"  classDef component {COMPONENT_STYLE};")
    lines.append(f"  classDef dep {DEP_STYLE};")
    return "\n".join(lines)


def _parent_of(graph: GraphDict, nid: str) -> str | None:
    n = graph["nodes"].get(nid)
    return cast("str | None", n.get("parent")) if n else None


def _top_group(graph: GraphDict, nid: str) -> str | None:
    """Walk parent pointers up to the top-level GROUP above `nid` (or None). Generic over the grouping
    kind — a component resolves to its top subsystem (`S`), an entity to its top subdomain (`SD`) —
    because the two forests share the one `parent` pointer over disjoint id spaces. Callers that mean a
    specific altitude must use _top_subsystem / _top_subdomain, NOT this directly, so the two altitudes
    never bleed (an entity endpoint must not read as an inter-subsystem crossing, and vice versa)."""
    cur = _parent_of(graph, nid)
    if cur is None:
        return None
    seen: set[str] = set()
    while True:
        p = _parent_of(graph, cur)
        if p is None or p in seen:
            return cur
        seen.add(cur)
        cur = p


def _top_subsystem(graph: GraphDict, nid: str) -> str | None:
    """`nid`'s top group, but ONLY when it is a subsystem (`S`) — else None. The component/subsystem
    altitude uses this so an entity endpoint (top group = a SUBDOMAIN) never reads as an inter-subsystem
    crossing. Before subdomains existed an entity had no parent, so C→E / E→E edges were silently
    excluded from the Subsystems overview; now they must be excluded explicitly by kind."""
    g = _top_group(graph, nid)
    return g if g is not None and str(graph["nodes"].get(g, {}).get("kind")) == "subsystem" else None


def _top_subdomain(graph: GraphDict, nid: str) -> str | None:
    """`nid`'s top group, but ONLY when it is a subdomain (`SD`) — else None. The domain-altitude mirror
    of _top_subsystem, so a component/dep endpoint never reads as an inter-subdomain crossing."""
    g = _top_group(graph, nid)
    return g if g is not None and str(graph["nodes"].get(g, {}).get("kind")) == "subdomain" else None


def _child_under(graph: GraphDict, nid: str, ancestor: str | None) -> str | None:
    """The immediate child of `ancestor` on the path down to `nid` — the LEVEL-RELATIVE bucket that
    replaces flatten-to-top. Returns `nid` itself when its direct parent is `ancestor`; the
    intermediate child-group when `nid` is deeper; None when `nid` is not in `ancestor`'s subtree.
    With `ancestor=None` it is `nid`'s top-level ancestor (i.e. `_top_group`), so the root overview
    is just the card of the virtual root. This is what lets a subsystem card show its IMMEDIATE
    children (and bucket a deep endpoint into the child box that contains it) instead of flattening."""
    cur, seen = nid, set()
    while True:
        p = _parent_of(graph, cur)
        if p == ancestor:
            return cur
        if p is None or p in seen:
            return None
        seen.add(cur)
        cur = p


def _sibling_level_box(graph: GraphDict, nid: str, sid: str) -> str | None:
    """The subsystem box to draw `nid` as in `sid`'s card when `nid` is OUTSIDE sid's subtree: the
    ancestor of `nid` that is a sibling of `sid` (shares sid's parent), so neighbours read at sid's
    own altitude. Falls back to nid's top-level subsystem when nid is not under sid's parent (a
    distant link still shows, collapsed). None when no subsystem box applies (e.g. an ungrouped
    component) — matching the old `_top_subsystem` skip. For a top-level `sid` (parent None) this is
    exactly `_top_subsystem(nid)`, so flat maps are unchanged."""
    b = _child_under(graph, nid, _parent_of(graph, sid))
    if b is not None and str(graph["nodes"].get(b, {}).get("kind")) == "subsystem":
        return b
    return _top_subsystem(graph, nid)


def has_grouping(graph: GraphDict) -> bool:
    return any(str(n.get("kind")) == "subsystem" for n in graph["nodes"].values())


def has_domain(graph: GraphDict) -> bool:
    return any(str(n.get("kind")) == "entity" for n in graph["nodes"].values())


def has_subdomains(graph: GraphDict) -> bool:
    """True when the domain model is grouped into subdomains (a `SD` node exists) — gates the Domain
    view's Subdomains overview, exactly as has_grouping gates the Subsystems view."""
    return any(str(n.get("kind")) == "subdomain" for n in graph["nodes"].values())


def _safe_member(s: str) -> str:
    """Sanitize an attribute type/name for a classDiagram member line: `<>{}|"` and backticks break
    member parsing (generics use `~`, not `<>`)."""
    return re.sub(r'[<>{}|`"]', "", s).strip()


def _relation_label(edge: dict[str, Any]) -> str:
    """Arrow label — REAL field name(s) only (an invented relationship verb isn't grounded in code).
    The backing field(s) are resolved once in build_graph (`fk_fields` / `fk_side`); here we only
    format them: forward (fields on the source / arrow-tail) -> the field name (`subscription`,
    `org_id`), or a comma-joined list for a composite key (`user_id, page_id`); reverse (FK on the
    target / arrow-head) -> `↩ field`. When no field backs the relation, a storage key (`keyed_by`)
    draws as `«key» name(s)` — a lookup/partition key the store imposes, marked distinct from a real
    row FK; blank when there is neither (the `{how}` note then explains it in the click-panel)."""
    fields = edge.get("fk_fields") or []
    if not fields:
        keyed = edge.get("keyed_by") or []
        if keyed:  # a storage/lookup key (not a row FK) — marked distinct with «key»
            return "«key» " + _safe_label(", ".join(str(k) for k in keyed))
        return ""
    label = _safe_label(", ".join(str(f) for f in fields))
    return label if edge.get("fk_side") == "src" else "↩ " + label


def _class_box_lines(nid: str, node: dict[str, Any], ent_names: dict[str, str],
                     with_members: bool) -> list[str]:
    """The `classDiagram` lines for one entity box. `with_members=True` renders its attributes
    (`type name`); `with_members=False` renders a bare box — used for a cross-subdomain NEIGHBOUR entity
    in a per-subdomain card, so it reads as collapsed (its detail lives in its own subdomain's view).
    Shared by the flat Domain view and the per-subdomain card so a class renders identically in both."""
    label = _safe_label(str(node["name"]))
    if not with_members:
        return [f'  class {nid}["{label}"]']
    out = [f'  class {nid}["{label}"] {{']
    for a in cast("list[dict[str, str]]", node.get("attrs") or []):
        # an embedded-entity-id type (`mode:E10`) renders with the entity's NAME, not its id
        atype = _safe_member(ent_names.get(str(a.get("type", "")), str(a.get("type", ""))))
        # `[]` is part of the type's SHAPE (it makes the field multi-valued), so show it in the box
        # — unlike PK/FK/?/unique (annotations), which stay in the click-panel. Otherwise a
        # collection reads as single-valued in the box and the `*` lives only on the relation arrow.
        if "[]" in str(a.get("markers", "")).split():
            atype += "[]"
        member = f'{atype} {_safe_member(str(a.get("name", "")))}'.strip()
        if member:
            out.append(f"    {member}")
    out.append("  }")
    return out


def _class_relation_line(e: dict[str, Any]) -> str:
    """The `classDiagram` arrow line for one domain relation (kind + cardinality + backing-field
    label). Shared by the flat Domain view and the per-subdomain card so an edge renders identically."""
    s, d, kind = str(e["src"]), str(e["dst"]), str(e.get("kind"))
    arrow = CLASS_ARROW.get(kind, "-->")
    label = _relation_label(e)
    suffix = f" : {label}" if label else ""
    if kind == "inheritance":
        # The inheritance triangle is a VERB-DERIVED fact: it trusts the authored `isA`/`extends`
        # verb, which no gate verifies against the code (method.md: verbs may prioritize, never
        # gate). Never field-backed, so no cardinality label to clash with the verb.
        return f"  {s} {arrow} {d} : {_safe_label(str(e.get('verb') or 'isA'))}"
    left = f'"{e["src_card"]}" ' if e.get("src_card") else ""
    right = f' "{e["dst_card"]}"' if e.get("dst_card") else ""
    return f"  {s} {left}{arrow}{right} {d}{suffix}"


def _domain_relation_edges(graph: GraphDict) -> list[dict[str, Any]]:
    """The E→E domain-relation edges — a relation `kind` is set AND both endpoints are entity nodes.
    Distinct from component edges (no kind) and the C→E bridge edges (no kind, dst is an entity); the
    source for the Domain view's derived SD→SD arrows and the per-subdomain card's drawn relations."""
    nodes = graph["nodes"]
    return [cast("dict[str, Any]", e) for e in graph["edges"]
            if e.get("kind") and str(nodes.get(str(e["src"]), {}).get("kind")) == "entity"
            and str(nodes.get(str(e["dst"]), {}).get("kind")) == "entity"]


def _entities_of(graph: GraphDict, sdid: str) -> list[tuple[str, str]]:
    """(id, name) of the DIRECT child entities of `sdid` (parent is exactly `sdid`), the domain mirror
    of _components_of. Entities nested in child subdomains are drawn one level down, on those
    subdomains' own cards. Leaf subdomain: direct == all, so flat maps are unchanged."""
    return [(eid, str(n["name"])) for eid, n in graph["nodes"].items()
            if str(n["kind"]) == "entity" and _parent_of(graph, eid) == sdid]


def _child_subdomains(graph: GraphDict, sdid: str) -> list[tuple[str, str]]:
    """(id, name) of the DIRECT child subdomains of `sdid` — drawn inside its card as collapsed,
    drillable boxes (the domain mirror of _child_subsystems). Empty for a leaf subdomain."""
    return [(c, str(n["name"])) for c, n in graph["nodes"].items()
            if str(n["kind"]) == "subdomain" and _parent_of(graph, c) == sdid]


def _descendant_entity_count(graph: GraphDict, sdid: str) -> int:
    """Number of entities anywhere under `sdid` (any depth) — the '(N)' shown on a collapsed neighbour
    box or the Subdomains-overview box, so the label reflects the whole subtree, not just direct kids.
    Flat: equals the direct count."""
    return sum(1 for eid, n in graph["nodes"].items()
               if str(n["kind"]) == "entity" and _child_under(graph, eid, sdid) is not None)


def _sibling_subdomain_box(graph: GraphDict, nid: str, sdid: str) -> str | None:
    """The subdomain box to draw `nid` as in `sdid`'s card when `nid` is OUTSIDE sdid's subtree — the
    domain mirror of _sibling_level_box: the ancestor of `nid` sharing sdid's parent, else nid's
    top-level subdomain. For a top-level `sdid` this is exactly `_top_subdomain(nid)`, so flat maps are
    unchanged."""
    b = _child_under(graph, nid, _parent_of(graph, sdid))
    if b is not None and str(graph["nodes"].get(b, {}).get("kind")) == "subdomain":
        return b
    return _top_subdomain(graph, nid)


def gen_domain_mermaid(graph: GraphDict) -> str:
    """C4 Code altitude: the T5 domain model as a Mermaid `classDiagram` — each entity a class box
    (id = its `E` id, label = its name) holding its attributes (`type name`), with typed, cardinal
    relations between entities. Markers (PK/FK/…) live in the click->panel, since classDiagram boxes
    carry no native key notation. Class id = the `E` id so the viewer's id bridge resolves a click.
    This is the FLAT whole-model view; on a subdomain-grouped map the viewer leads with the Subdomains
    overview (gen_domain_container_mermaid) and drills into one subdomain's card."""
    ents = [(nid, n) for nid, n in graph["nodes"].items() if str(n["kind"]) == "entity"]
    ent_ids = {nid for nid, _ in ents}
    ent_names = {nid: str(n["name"]) for nid, n in ents}
    lines = ["classDiagram"]
    for nid, n in ents:
        lines += _class_box_lines(nid, cast("dict[str, Any]", n), ent_names, with_members=True)
    for nid, _ in ents:  # tint each entity (light fuchsia member) — the flat view has no namespace to inherit from
        lines.append(f"  style {nid} {ENTITY_STYLE}")
    for e in graph["edges"]:
        if e.get("kind") and str(e["src"]) in ent_ids and str(e["dst"]) in ent_ids:
            lines.append(_class_relation_line(cast("dict[str, Any]", e)))
    return "\n".join(lines)


# Element palettes — TINT PER FAMILY: one hue per family, the container box a DEEPER shade of the
# member's hue, so a member visibly belongs to its container while the two families stay distinct.
#   Structural family = INDIGO: component (member, indigo-50) inside subsystem (container, indigo-200).
#   Domain family     = FUCHSIA: entity (member, fuchsia-50) inside subdomain (container, fuchsia-200).
# Within a family the container + member share the stroke and differ only by fill depth; the families
# differ by hue (indigo vs fuchsia), so subsystem≠subdomain AND component≠entity (the old clash, where
# the entity used Mermaid's default lavender ≈ the component's indigo, is gone). Defined once, reused as
# flowchart `classDef`s and as classDiagram per-id `style`s (classDiagram has no classDef-by-name).
# A container's border is also drawn thicker AND dashed (`stroke-width` + `stroke-dasharray`) — a
# SECOND, colour-blind-safe signal (on top of the JS-injected corner icon) that a box is a container,
# not a leaf, since fill depth alone is easy to miss. Only subsystem/subdomain carry it.
_CONTAINER_BORDER = "stroke-width:2.5px,stroke-dasharray:6 3"
COMPONENT_STYLE = "fill:#eef2ff,stroke:#3730a3,color:#1e1b4b"  # indigo-50   — component (C), light member
SUBSYSTEM_STYLE = f"fill:#c7d2fe,stroke:#3730a3,color:#1e1b4b,{_CONTAINER_BORDER}"  # indigo-200  — subsystem (S), deep container
ENTITY_STYLE    = "fill:#fdf4ff,stroke:#86198f,color:#581c87"  # fuchsia-50  — entity (E), light member
SUBDOMAIN_STYLE = f"fill:#f5d0fe,stroke:#86198f,color:#581c87,{_CONTAINER_BORDER}"  # fuchsia-200 — subdomain (SD), deep container
DEP_STYLE       = "fill:#ecfdf5,stroke:#065f46,color:#064e3b"  # emerald     — external dependency (D)
# A dependency/library GROUP container (the Libraries bundle box + folded bucket count boxes): the SAME
# emerald as the deps/libraries it holds, distinguished as a drillable group only by the shared dashed
# container border (the convention subsystems/subdomains already use), never by a foreign hue.
CONTAINER_STYLE = f"fill:#ecfdf5,stroke:#065f46,color:#064e3b,{_CONTAINER_BORDER}"
PROCESS_STYLE   = f"fill:#fef3c7,stroke:#b45309,color:#78350f,{_CONTAINER_BORDER}"  # amber-100 — a deployable process/thread (Deployment view), a runtime container
INFRA_STYLE     = "fill:#f1f5f9,stroke:#475569,color:#1e293b"  # slate       — infrastructure node (broker/store) in the Deployment view
DOMAIN_SUBDOMAIN_CLASSDEF = f"  classDef subdomain {SUBDOMAIN_STYLE};"


def _fill_stroke(style: str) -> dict[str, str]:
    """`{'fill':…, 'stroke':…, 'strokeWidth':…, 'strokeDasharray':…}` parsed from a
    `fill:…,stroke:…,color:…[,stroke-width:…,stroke-dasharray:…]` style string — the stroke-width/dasharray
    keys only present for a container style, so the viewer can tell a drilled subsystem/subdomain CLUSTER
    frame (which `style`/classDef can't reach) apart from a member's."""
    d: dict[str, str] = {}
    for part in style.split(","):
        k, _, v = part.partition(":")
        d[k.strip()] = v.strip()
    out = {"fill": d["fill"], "stroke": d["stroke"]}
    if "stroke-width" in d:
        out["strokeWidth"] = d["stroke-width"]
    if "stroke-dasharray" in d:
        out["strokeDasharray"] = d["stroke-dasharray"]
    return out


# Per-kind fill/stroke, injected into the viewer so it can recolour elements Mermaid renders with a
# default (kind-agnostic) palette: an EXPANDED group's CLUSTER frame (a drilled subsystem subgraph /
# subdomain namespace — defaults to pale yellow, and `style` can't reach a classDiagram namespace) and a
# FLOW sequence diagram's participant boxes (every `participant` is the same default box, so an entity
# would read like a component). Derived from the box styles above — one source for every view.
ELEMENT_TINT = {
    "component": _fill_stroke(COMPONENT_STYLE),
    "dep": _fill_stroke(DEP_STYLE),
    "entity": _fill_stroke(ENTITY_STYLE),
    "subsystem": _fill_stroke(SUBSYSTEM_STYLE),
    "subdomain": _fill_stroke(SUBDOMAIN_STYLE),
    "process": _fill_stroke(PROCESS_STYLE),
    "infra": _fill_stroke(INFRA_STYLE),
    # The Context/Libraries PURPOSE-bucket group frames (`CYBK<i>` clusters) and the folded count boxes:
    # the SAME emerald as the deps/libraries they hold + the dashed container border, so a group reads as
    # "a drillable box of these" rather than a foreign-coloured panel. Matches CONTAINER_STYLE.
    "bucket": {"fill": "#ecfdf5", "stroke": "#065f46", "strokeWidth": "2.5px", "strokeDasharray": "6 3"},
    "bucketfold": {"fill": "#ecfdf5", "stroke": "#065f46", "strokeWidth": "2.5px", "strokeDasharray": "6 3"},
}

def gen_domain_container_mermaid(graph: GraphDict) -> str:
    """Domain Container altitude: each top-level subdomain (`SD`) a box labelled `Name (N)` (N = its
    entity count), with inter-subdomain arrows DERIVED from the E→E relation list (a `SDa → SDb` arrow
    exists iff a domain relation crosses, labelled by count). The exact mirror of
    gen_container_mermaid for components — the scalable entry point into a large domain model."""
    lines = ["flowchart TB"]
    for nid, node in graph["nodes"].items():
        if str(node["kind"]) == "subdomain" and _parent_of(graph, nid) is None:
            n_ent = _descendant_entity_count(graph, nid)
            lines.append(f'  {nid}["{_safe_label(str(node["name"]))} ({n_ent})"]:::cy-{nid}')
            lines.append(f"  class {nid} subdomain")
    counts: dict[tuple[str, str], int] = {}
    for e in _domain_relation_edges(graph):
        ca, cb = _top_subdomain(graph, str(e["src"])), _top_subdomain(graph, str(e["dst"]))
        if ca and cb and ca != cb:
            counts[(ca, cb)] = counts.get((ca, cb), 0) + 1
    for (ca, cb), c in sorted(counts.items()):
        lines.append(f"  {ca} -->|{c}| {cb}")
    lines.append(DOMAIN_SUBDOMAIN_CLASSDEF)
    return "\n".join(lines)


def _subdomain_ancestors(graph: GraphDict, nid: str) -> list[str]:
    """The subdomain ids on `nid`'s parent chain (nearest first) — the domain mirror of
    _subsystem_ancestors, enumerating the boxes `nid` collapses into at successive drill levels."""
    out: list[str] = []
    cur, seen = _parent_of(graph, nid), set()
    while cur and cur not in seen:
        seen.add(cur)
        if str(graph["nodes"].get(cur, {}).get("kind")) == "subdomain":
            out.append(cur)
        cur = _parent_of(graph, cur)
    return out


def _domain_edge_card_pairs(graph: GraphDict) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Every disjoint ordered subdomain pair (a, b) an entity relation crosses between, with the
    crossing relations — the domain mirror of _edge_card_pairs (subdomain ancestors of each endpoint,
    disjoint only), covering the pair at every drill level. The single source for the domain edge-card
    diagrams and the per-arrow crossing lists."""
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for e in _domain_relation_edges(graph):
        s, d = str(e["src"]), str(e["dst"])
        for a in _subdomain_ancestors(graph, s):
            for b in _subdomain_ancestors(graph, d):
                if _disjoint(graph, a, b):
                    out.setdefault((a, b), []).append(e)
    return out


def gen_domain_container_edges(graph: GraphDict) -> dict[str, list[dict[str, str]]]:
    """For each inter-subdomain arrow 'A>B' the viewer can draw — at the Domain overview AND inside any
    (possibly nested) subdomain card — the underlying entity→entity relations crossing from A's subtree
    to B's (endpoints, names, verb, kind), listed in the arrow's hover tooltip / select panel. Derived
    from the one _domain_edge_card_pairs source, keyed 'A>B' to match the relation bridge."""
    out: dict[str, list[dict[str, str]]] = {}
    for (a, b), edges in _domain_edge_card_pairs(graph).items():
        out[f"{a}>{b}"] = [{
            "src": str(e["src"]),
            "dst": str(e["dst"]),
            "srcName": str(graph["nodes"][str(e["src"])]["name"]) if str(e["src"]) in graph["nodes"] else str(e["src"]),
            "dstName": str(graph["nodes"][str(e["dst"])]["name"]) if str(e["dst"]) in graph["nodes"] else str(e["dst"]),
            "verb": str(e["verb"]),
            "kind": str(e.get("kind") or ""),
            "where": str(e["where"]) if e.get("where") else "",  # call-site path:line -> per-row source link
        } for e in edges]
    return out


def _subdomain_namespace(graph: GraphDict, sdid: str,
                         members: list[tuple[str, str]]) -> list[str]:
    """`classDiagram` lines framing a subdomain's entities as `namespace <sdid>["Name"] { … }` —
    each member entity drawn full (attributes). The classDiagram analog of `_component_subgraph`:
    a subdomain always reads as a labelled frame (Mermaid 11 namespaces render as a titled cluster,
    DOM-id `cluster-<sdid>`, with the inner class group ids unchanged so the id bridge still resolves).
    The title is the bare name — NO member count: when zoomed into the frame the entities are drawn
    inside, so the count is redundant (it stays on the COLLAPSED subdomain boxes, where it can't be
    seen). This matches the subsystem frame (`_component_subgraph`), which never carried one.
    Shared by the subdomain card and the domain edge card."""
    nodes = graph["nodes"]
    ent_names = {nid: str(n["name"]) for nid, n in nodes.items() if str(n["kind"]) == "entity"}
    nm = _safe_label(str(nodes[sdid]["name"])) if sdid in nodes else sdid
    out = [f'namespace {sdid}["{nm}"] {{']
    for eid, _ in members:
        out += _class_box_lines(eid, cast("dict[str, Any]", nodes[eid]), ent_names, with_members=True)
    for cid, cname in _child_subdomains(graph, sdid):  # nested child subdomains: collapsed, drillable
        out.append(f'  class {cid}["{_safe_label(cname)} ({_descendant_entity_count(graph, cid)})"]')
    out.append("}")
    for eid, _ in members:  # tint each focal entity (light fuchsia member); `style` lives OUTSIDE the namespace
        out.append(f"  style {eid} {ENTITY_STYLE}")
    return out


def _subsystem_bridge_lines(graph: GraphDict, member_ids: set[str]) -> list[str]:
    """`classDiagram` lines for the reverse structure↔domain bridge over `member_ids`: every subsystem
    whose components touch one of those entities, drawn as a collapsed (indigo) box with an arrow into
    the entity labelled by the COUNT of underlying C→E edges. The mirror of the subsystem card's
    subdomain bridge; shared by the subdomain card and the domain edge card."""
    nodes = graph["nodes"]
    counts: dict[tuple[str, str], int] = {}  # (subsystem box, member entity) -> underlying C→E edge count
    nb_subs: set[str] = set()
    for e in graph["edges"]:
        s, d = str(e["src"]), str(e["dst"])
        if d in member_ids and str(nodes.get(s, {}).get("kind")) == "component":
            sub = _top_subsystem(graph, s)
            if sub:
                nb_subs.add(sub)
                counts[(sub, d)] = counts.get((sub, d), 0) + 1
    out: list[str] = []
    for sub in sorted(nb_subs):  # collapsed neighbour-subsystem boxes (indigo, like a subsystem anywhere)
        out.append(f'  class {sub}["{_safe_label(str(nodes[sub]["name"]))}"]')
        out.append(f"  style {sub} {SUBSYSTEM_STYLE}")
    for (sub, ent), c in sorted(counts.items()):  # bridge arrows: subsystem -> entity (underlying edge count)
        out.append(f"  {sub} --> {ent} : {c}")
    return out


def gen_domain_subdomain_card(graph: GraphDict, sdid: str) -> str:
    """A per-subdomain `classDiagram` neighbourhood: `sdid` framed as a `namespace` holding its own
    entities (full attributes), every OTHER subdomain its entities relate to drawn as a collapsed
    member-less box (one per neighbour subdomain, labelled `Name (N)`), the focal subdomain's internal
    relations drawn in full, and one arrow (labelled by its count of crossing relations) per (focal
    entity, neighbour subdomain) pair. It ALSO draws the structure↔domain bridge in reverse: every
    subsystem whose components touch one of these entities is drawn as a collapsed (indigo) box with an
    arrow into that entity labelled by the count of underlying C→E edges — the mirror of the subsystem
    card's subdomain bridge. The entity analog of gen_subsystem_card_mermaid
    — each screen stays small no matter the total model size, neighbours stay collapsed, and the viewer
    turns a click on a neighbour subdomain box into that subdomain's card, a neighbour subsystem box into
    that subsystem's card, and a click on a cross arrow into the two-subdomain edge card. Node ids +
    relation shapes match the flat Domain view, so the class/relation bridge resolves a click to the
    entity panel or the relation detail."""
    members = _entities_of(graph, sdid)          # direct child entities (drawn full)
    member_ids = {eid for eid, _ in members}
    child_sd_ids = {c for c, _ in _child_subdomains(graph, sdid)}  # nested child subdomains (collapsed, drillable)
    nodes = graph["nodes"]
    if not members and not child_sd_ids:
        # A defined-but-empty subdomain would leave a body-less classDiagram, which Mermaid rejects
        # (the drill would throw). Emit a placeholder class so the card stays a VALID, self-explaining
        # diagram; its id carries no prefix+digits, so the viewer's id bridge skips it. (Returning here
        # also skips the relation/bridge loops below, which would all be empty with no member entities.)
        name = _safe_label(str(nodes[sdid]["name"])) if sdid in nodes else sdid
        return f'classDiagram\n  class EmptySubdomain["{name} — no entities"]'
    internal: list[dict[str, Any]] = []   # both endpoints DIRECT entities of this subdomain — drawn full
    cross: dict[tuple[str, str], int] = {}   # (focal box, neighbour-subdomain box) -> crossing count
    childcross: dict[tuple[str, str], int] = {}  # (box, nested child-subdomain box) -> aggregated count
    nb_sds: set[str] = set()
    # Bucket each relation endpoint at THIS card's level via `_child_under` (the domain mirror of the
    # subsystem card): a direct entity buckets to itself, a deeper one to the child-subdomain box that
    # holds it, an out-of-subtree one to None. Leaf subdomain -> each is the entity itself or None,
    # identical to the old `in member_ids` / `_top_subdomain` flat behaviour.
    for e in _domain_relation_edges(graph):
        s, d = str(e["src"]), str(e["dst"])
        bs, bd = _child_under(graph, s, sdid), _child_under(graph, d, sdid)
        if bs is not None and bd is not None:          # both inside sdid's subtree
            if bs == s and bd == d:
                internal.append(e)                     # two direct entities -> full relation
            elif bs != bd:
                childcross[(bs, bd)] = childcross.get((bs, bd), 0) + 1  # child-subdomain box -> aggregated
        elif bs is not None:                           # outbound crossing to outside sdid
            nb = _sibling_subdomain_box(graph, d, sdid)
            if nb and nb != sdid:
                cross[(bs, nb)] = cross.get((bs, nb), 0) + 1
                nb_sds.add(nb)
        elif bd is not None:                           # inbound crossing from outside sdid
            nb = _sibling_subdomain_box(graph, s, sdid)
            if nb and nb != sdid:
                cross[(nb, bd)] = cross.get((nb, bd), 0) + 1
                nb_sds.add(nb)
    lines = ["classDiagram", *_subdomain_namespace(graph, sdid, members)]
    for cid in sorted(child_sd_ids):  # style the nested child-subdomain boxes (declared inside the namespace)
        lines.append(f"  style {cid} {SUBDOMAIN_STYLE}")
    for nb in sorted(nb_sds):  # collapsed neighbour-subdomain boxes (member-less, count-labelled)
        n_ent = _descendant_entity_count(graph, nb)
        lines.append(f'  class {nb}["{_safe_label(str(nodes[nb]["name"]))} ({n_ent})"]')
        lines.append(f"  style {nb} {SUBDOMAIN_STYLE}")  # fuchsia — same as a subdomain box anywhere else
    lines += _subsystem_bridge_lines(graph, member_ids)  # reverse structure↔domain bridge over DIRECT members
    for e in internal:  # the focal subdomain's own relations, full
        lines.append(_class_relation_line(e))
    for (src, dst), c in sorted(cross.items()):  # crossing arrows to/from collapsed neighbour boxes (click → edge card)
        lines.append(f"  {src} --> {dst} : {c}")
    for (src, dst), c in sorted(childcross.items()):  # nested child-subdomain arrows (aggregated; box drills in)
        lines.append(f"  {src} --> {dst} : {c}")
    return "\n".join(lines)


def domain_subdomain_mermaids(graph: GraphDict) -> dict[str, str]:
    """One per-subdomain card per subdomain at EVERY level (see gen_domain_subdomain_card), so a nested
    child subdomain has its own card to drill into — the domain mirror of subsystem_component_mermaids."""
    return {nid: gen_domain_subdomain_card(graph, nid)
            for nid, node in graph["nodes"].items()
            if str(node["kind"]) == "subdomain"}


def gen_domain_edge_card(graph: GraphDict, a: str, b: str) -> str:
    """Domain edge card: disjoint subdomains `a` and `b` framed as `namespace` blocks holding their
    IMMEDIATE entities (full) + child-subdomain boxes, drawn with the a→b crossings PLUS each frame's own
    internal relations. A crossing between two DIRECT entities keeps its full relation (so the bridge
    resolves it); a crossing into a child subdomain is an aggregated box arrow. It also draws the reverse
    structure↔domain bridge (collapsed subsystem boxes that own/read either frame's direct entities). The
    entity analog of gen_edge_card_mermaid (only the a→b direction; the b→a arrow has its own card)."""
    ents_a = _entities_of(graph, a)            # direct child entities of each frame
    ents_b = _entities_of(graph, b)
    ids_a = {eid for eid, _ in ents_a}
    ids_b = {eid for eid, _ in ents_b}
    lines = ["classDiagram",
             *_subdomain_namespace(graph, a, ents_a),
             *_subdomain_namespace(graph, b, ents_b)]
    for cid, _ in _child_subdomains(graph, a) + _child_subdomains(graph, b):  # style the child boxes drawn in the frames
        lines.append(f"  style {cid} {SUBDOMAIN_STYLE}")
    lines += _subsystem_bridge_lines(graph, ids_a | ids_b)  # subsystems owning/reading either subdomain's direct entities
    agg: dict[tuple[str, str], int] = {}
    for e in _domain_relation_edges(graph):
        s, d = str(e["src"]), str(e["dst"])
        if (s in ids_a and d in ids_a) or (s in ids_b and d in ids_b):  # a frame's inner wiring (both direct)
            lines.append(_class_relation_line(cast("dict[str, Any]", e)))
            continue
        if _in_subtree(graph, s, a) and _in_subtree(graph, d, b):        # the a→b crossing this card is for
            ba, bb = _child_under(graph, s, a), _child_under(graph, d, b)
            if ba == s and bb == d:                                      # both direct entities -> full relation
                lines.append(_class_relation_line(cast("dict[str, Any]", e)))
            else:                                                        # reaches into a child subdomain -> aggregated box arrow
                agg[(str(ba), str(bb))] = agg.get((str(ba), str(bb)), 0) + 1
    for (src, dst), c in sorted(agg.items()):
        lines.append(f"  {src} --> {dst} : {c}")
    return "\n".join(lines)


def domain_edge_card_mermaids(graph: GraphDict) -> dict[str, str]:
    """One edge-card per disjoint subdomain pair with a crossing relation — at every drill level, not
    only top-level — keyed 'A>B' to match the rendered arrow's endpoints. The entity analog of
    edge_card_mermaids, built from the one _domain_edge_card_pairs source."""
    return {f"{a}>{b}": gen_domain_edge_card(graph, a, b) for (a, b) in sorted(_domain_edge_card_pairs(graph))}


def gen_bridge_card_mermaid(graph: GraphDict, sid: str, sdid: str) -> str:
    """Bridge card: subsystem `sid` and subdomain `sdid` framed side by side — the structure↔domain
    relationship — with the component→entity edges between them: a direct link drawn unlabelled (one
    concrete edge, resolves to it on click), a crossing into a child group aggregated into a
    count-labelled box arrow. The analog of
    the edge cards across the two groupings (S×S pairs two subsystems, SD×SD two subdomains; this pairs a
    subsystem with a subdomain). Rendered as a classDiagram so the subsystem's components (member-less,
    simple boxes) and the subdomain's entities (full boxes) share one canvas; node ids + the C→E edges
    match the component view, so the viewer resolves an in-card arrow to its real edge."""
    comps = _components_of(graph, sid)            # direct component members
    ents = _entities_of(graph, sdid)              # direct entity members
    nodes = graph["nodes"]
    lines = ["classDiagram", f'namespace {sid}["{_safe_label(str(nodes[sid]["name"]))}"] {{']
    for cid, name in comps:  # direct components as member-less (simple) boxes
        lines.append(f'  class {cid}["{_safe_label(name)}"]')
    for ssid, sname in _child_subsystems(graph, sid):  # child subsystems as collapsed (drillable) boxes
        lines.append(f'  class {ssid}["{_safe_label(sname)}"]')
    lines.append("}")
    lines += _subdomain_namespace(graph, sdid, ents)  # the subdomain's immediate entities (+ child SD boxes)
    for cid, _ in comps:  # indigo — read as components, not entities
        lines.append(f"  style {cid} {COMPONENT_STYLE}")
    for ssid, _ in _child_subsystems(graph, sid):
        lines.append(f"  style {ssid} {SUBSYSTEM_STYLE}")
    for cid, _ in _child_subdomains(graph, sdid):
        lines.append(f"  style {cid} {SUBDOMAIN_STYLE}")
    # C→E edges crossing sid's subtree -> sdid's subtree, bucketed to each frame's immediate children:
    # a direct member->direct entity link is ONE concrete edge (resolves to it on click, not drillable),
    # drawn UNLABELLED; a crossing into a child group aggregates several edges -> count-labelled box arrow.
    direct: set[tuple[str, str]] = set()
    agg: dict[tuple[str, str], int] = {}
    for e in graph["edges"]:
        s, d = str(e["src"]), str(e["dst"])
        if str(nodes.get(s, {}).get("kind")) != "component" or str(nodes.get(d, {}).get("kind")) != "entity":
            continue
        if not (_in_subtree(graph, s, sid) and _in_subtree(graph, d, sdid)):
            continue
        bs, bd = str(_child_under(graph, s, sid)), str(_child_under(graph, d, sdid))
        if bs == s and bd == d:            # both direct -> one concrete link, unlabelled
            direct.add((bs, bd))
        else:                              # reaches into a child group -> aggregated, count-labelled
            agg[(bs, bd)] = agg.get((bs, bd), 0) + 1
    for bs, bd in sorted(direct):
        lines.append(f"  {bs} --> {bd}")
    for (bs, bd), c in sorted(agg.items()):
        lines.append(f"  {bs} --> {bd} : {c}")
    return "\n".join(lines)


def bridge_card_mermaids(graph: GraphDict) -> dict[str, str]:
    """One bridge card per (subsystem-ancestor, subdomain-ancestor) pair joined by a C→E edge
    — at EVERY drill level, so a NESTED subsystem card's bridge arrow (key `nestedS>SD`) and a nested
    subdomain card's reverse bridge (key `S>nestedSD`) both resolve. Keyed 'S>SD'; the cross-grouping
    analog of edge_card_mermaids (no disjoint check — the two forests never overlap)."""
    nodes = graph["nodes"]
    pairs: set[tuple[str, str]] = set()
    for e in graph["edges"]:
        s, d = str(e["src"]), str(e["dst"])
        if str(nodes.get(s, {}).get("kind")) == "component" and str(nodes.get(d, {}).get("kind")) == "entity":
            for a in _subsystem_ancestors(graph, s):
                for b in _subdomain_ancestors(graph, d):
                    pairs.add((a, b))
    return {f"{sub}>{sd}": gen_bridge_card_mermaid(graph, sub, sd) for sub, sd in sorted(pairs)}


def gen_container_mermaid(graph: GraphDict) -> str:
    """C4 Container: top-level subsystems as boxes, with inter-subsystem edges DERIVED from the
    component edge list (an S->S arrow exists iff a component edge crosses), labeled by count."""
    lines = ["flowchart TB"]
    for nid, node in graph["nodes"].items():
        if str(node["kind"]) == "subsystem" and _parent_of(graph, nid) is None:
            lines.append(f'  {nid}["{_safe_label(str(node["name"]))}"]:::cy-{nid}')
            lines.append(f"  class {nid} subsystem")
    counts: dict[tuple[str, str], int] = {}
    for e in graph["edges"]:
        sa, sb = _top_subsystem(graph, str(e["src"])), _top_subsystem(graph, str(e["dst"]))
        if sa and sb and sa != sb:
            counts[(sa, sb)] = counts.get((sa, sb), 0) + 1
    for (sa, sb), c in sorted(counts.items()):
        lines.append(f"  {sa} -->|{c}| {sb}")
    lines.append(f"  classDef subsystem {SUBSYSTEM_STYLE};")
    return "\n".join(lines)


def _subsystem_ancestors(graph: GraphDict, nid: str) -> list[str]:
    """The subsystem ids on `nid`'s parent chain (nearest first) — the boxes `nid` collapses into at
    successive drill levels. Used to enumerate the disjoint pairs a component edge crosses between."""
    out: list[str] = []
    cur, seen = _parent_of(graph, nid), set()
    while cur and cur not in seen:
        seen.add(cur)
        if str(graph["nodes"].get(cur, {}).get("kind")) == "subsystem":
            out.append(cur)
        cur = _parent_of(graph, cur)
    return out


def _in_subtree(graph: GraphDict, nid: str, anc: str) -> bool:
    """True when `nid` is strictly inside `anc`'s subtree (its level-relative bucket exists)."""
    return _child_under(graph, nid, anc) is not None


def _disjoint(graph: GraphDict, a: str, b: str) -> bool:
    """True when subsystems `a` and `b` are neither equal nor nested — so they can frame a two-box edge
    card without overlapping. Overlapping (ancestor/descendant) pairs are navigated, never carded."""
    return a != b and not _in_subtree(graph, a, b) and not _in_subtree(graph, b, a)


def _edge_card_pairs(graph: GraphDict) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Every disjoint ordered subsystem pair (a, b) a component edge crosses between, with the crossing
    edges. `a`/`b` range over the subsystem ancestors of the edge's endpoints, so this covers the pair
    at EVERY drill level (the top-level overview arrow AND a nested card's cross arrow) — a superset of
    what any single card draws, keyed to match the viewer's edge bridge. The single source for both the
    edge-card diagrams and the per-arrow crossing lists."""
    out: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for e in graph["edges"]:
        s, d = str(e["src"]), str(e["dst"])
        if str(graph["nodes"].get(s, {}).get("kind")) != "component" \
                or str(graph["nodes"].get(d, {}).get("kind")) != "component":
            continue
        for a in _subsystem_ancestors(graph, s):
            for b in _subsystem_ancestors(graph, d):
                if _disjoint(graph, a, b):
                    out.setdefault((a, b), []).append(e)
    return out


def gen_container_edges(graph: GraphDict) -> dict[str, list[dict[str, str]]]:
    """For each inter-subsystem arrow 'A>B' the viewer can draw — at the Subsystems overview AND inside
    any (possibly nested) subsystem card — the underlying component->component edges crossing from A's
    subtree to B's (endpoints, names, verb, why), listed in the arrow's hover tooltip / select panel.
    Derived from the one _edge_card_pairs source, keyed 'A>B' to match the edge bridge."""
    out: dict[str, list[dict[str, str]]] = {}
    for (a, b), edges in _edge_card_pairs(graph).items():
        out[f"{a}>{b}"] = [{
            "src": str(e["src"]),
            "dst": str(e["dst"]),
            "srcName": str(graph["nodes"][str(e["src"])]["name"]) if str(e["src"]) in graph["nodes"] else str(e["src"]),
            "dstName": str(graph["nodes"][str(e["dst"])]["name"]) if str(e["dst"]) in graph["nodes"] else str(e["dst"]),
            "verb": str(e["verb"]),
            "why": str(e["why"]) if e["why"] else "",
            "where": str(e["where"]) if e.get("where") else "",  # call-site path:line -> per-row source link
        } for e in edges]
    return out


def gen_bridge_edges(graph: GraphDict) -> list[dict[str, str]]:
    """Every component->entity edge — the structure<->domain bridge ATOM — with resolved endpoint names
    and call site. A bridge arrow (component->subdomain box in a subsystem card, subsystem box->entity in
    a subdomain/domain view, or a child-box arrow inside a bridge card) bundles a subset of these; the
    viewer filters this ONE flat list by the clicked arrow's drawn endpoints — a leaf end by id, a group
    (subsystem/subdomain) end by subtree membership — to list exactly the C->E links that arrow stands
    for at any level. The bridge analog of gen_container_edges (flat, not pre-keyed, because the same
    edge is reachable from differently-keyed arrow shapes; subtree tests live in the viewer, which
    already walks the parent chain, so no per-level ancestor is baked here)."""
    nodes = graph["nodes"]
    out: list[dict[str, str]] = []
    for e in graph["edges"]:
        s, d = str(e["src"]), str(e["dst"])
        if str(nodes.get(s, {}).get("kind")) != "component" or str(nodes.get(d, {}).get("kind")) != "entity":
            continue
        out.append({
            "src": s,
            "dst": d,
            "srcName": str(nodes[s]["name"]) if s in nodes else s,
            "dstName": str(nodes[d]["name"]) if d in nodes else d,
            "verb": str(e["verb"]),
            "why": str(e["why"]) if e["why"] else "",
            "where": str(e["where"]) if e.get("where") else "",
        })
    return out


def _components_of(graph: GraphDict, sid: str) -> list[tuple[str, str]]:
    """(id, name) of the DIRECT child components of `sid` (its immediate component members — those
    whose `parent` is exactly `sid`, NOT all descendants). Nested components live in `sid`'s child
    subsystems and are drawn one level down, on those subsystems' own cards. For a leaf subsystem
    (no child subsystems) direct == all, so flat maps are unchanged."""
    return [(cid, str(n["name"])) for cid, n in graph["nodes"].items()
            if str(n["kind"]) == "component" and _parent_of(graph, cid) == sid]


def _child_subsystems(graph: GraphDict, sid: str) -> list[tuple[str, str]]:
    """(id, name) of the DIRECT child subsystems of `sid` — drawn inside its card as collapsed,
    drillable boxes (⌘-click opens the child's own card). Empty for a leaf subsystem."""
    return [(s, str(n["name"])) for s, n in graph["nodes"].items()
            if str(n["kind"]) == "subsystem" and _parent_of(graph, s) == sid]


def _component_subgraph(graph: GraphDict, sid: str, indent: str = "  ") -> list[str]:
    """Mermaid lines framing a subsystem's components as `subgraph <sid>["name"] … end`. Shared by
    the subsystem card and the edge card so a subsystem always reads as a labelled frame (matching
    the base-map subsystem boxes)."""
    open_b, close_b = SHAPE["component"]
    out = [f'{indent}subgraph {sid}["{_safe_label(str(graph["nodes"][sid]["name"]))}"]']
    for cid, name in _components_of(graph, sid):
        out.append(f"{indent}  {cid}{open_b}{_safe_label(name)}{close_b}:::cy-{cid}")
        out.append(f"{indent}  class {cid} component")
    for ssid, sname in _child_subsystems(graph, sid):  # nested child subsystems: collapsed, drillable
        out.append(f'{indent}  {ssid}["{_safe_label(sname)}"]:::cy-{ssid}')
        out.append(f"{indent}  class {ssid} subsystem")
    out.append(f"{indent}end")
    return out


def gen_subsystem_card_mermaid(graph: GraphDict, sid: str) -> str:
    """Subsystem card: `sid` drawn as a frame around its components (with their internal wiring),
    the deps those components touch drawn outside the frame, AND the subsystem's neighbourhood —
    every other subsystem its components link to/from is drawn as a collapsed box, with one
    arrow per (component, neighbour) pair labelled by the count of underlying edges. A component
    inside the frame points to the neighbour box (outbound) or is pointed at by it (inbound). The
    viewer turns a click on such an arrow into the matching edge card, and a click on a neighbour
    box into that subsystem's own card. When the subsystem's components touch the domain model
    (`C→E` edges), the subdomains they touch are also drawn as collapsed boxes — the bridge between
    the structural and domain groupings, labelled by the count of underlying C→E edges."""
    members = {cid for cid, _ in _components_of(graph, sid)}   # direct component members (drawn nodes)
    deps: set[str] = set()
    neighbours: set[str] = set()
    cross: dict[tuple[str, str], int] = {}       # (drawn-box, neighbour-subsystem box) -> crossing count
    childcross: dict[tuple[str, str], int] = {}  # (box, nested child-subsystem box) -> aggregated count
    bridges: dict[tuple[str, str], int] = {}     # (drawn box, subdomain box) -> underlying C→E edge count
    # Every endpoint is bucketed at THIS card's level: `_child_under` gives the immediate child of `sid`
    # that contains it — the component itself when a direct member, the child-subsystem box when deeper,
    # None when outside sid's subtree. A leaf subsystem has no child boxes, so each bs/bd is the endpoint
    # itself or None — identical to the old `in members` / `_top_subsystem` flat behaviour.
    for e in graph["edges"]:
        s, d = str(e["src"]), str(e["dst"])
        ks, kd = str(graph["nodes"].get(s, {}).get("kind")), str(graph["nodes"].get(d, {}).get("kind"))
        bs, bd = _child_under(graph, s, sid), _child_under(graph, d, sid)
        if kd == "dep":                                  # a DIRECT member's dep (a child's deps live on its own card)
            if bs == s:
                deps.add(d)
            continue
        if ks == "dep":
            if bd == d:
                deps.add(s)
            continue
        if kd == "entity":                               # bridge: a DIRECT member touches a domain entity
            if bs == s:
                sd = _top_subdomain(graph, d)
                if sd:
                    bridges[(s, sd)] = bridges.get((s, sd), 0) + 1
            continue
        if ks == "entity":
            continue
        if bs is not None and bd is not None:            # both inside sid's subtree
            if not (bs == s and bd == d) and bs != bd:   # a child-subsystem box is involved -> aggregated
                childcross[(bs, bd)] = childcross.get((bs, bd), 0) + 1
            continue                                     # two direct members -> labelled (via keep) below
        if bs is not None:                               # outbound crossing to outside sid
            nb = _sibling_level_box(graph, d, sid)
            if nb and nb != sid:
                neighbours.add(nb)
                cross[(bs, nb)] = cross.get((bs, nb), 0) + 1
            continue
        if bd is not None:                               # inbound crossing from outside sid
            nb = _sibling_level_box(graph, s, sid)
            if nb and nb != sid:
                neighbours.add(nb)
                cross[(nb, bd)] = cross.get((nb, bd), 0) + 1
    keep = members | deps  # the set whose internal (labelled) edges are drawn
    lines = ["flowchart TB", *_component_subgraph(graph, sid)]
    for nb in sorted(neighbours):  # collapsed neighbour-subsystem boxes
        lines.append(f'  {nb}["{_safe_label(str(graph["nodes"][nb]["name"]))}"]:::cy-{nb}')
        lines.append(f"  class {nb} subsystem")
    open_b, close_b = SHAPE["dep"]
    for did in sorted(deps):  # deps belong to no subsystem — draw them outside the frame
        lines.append(f'  {did}{open_b}{_safe_label(str(graph["nodes"][did]["name"]))}{close_b}:::cy-{did}')
        lines.append(f"  class {did} dep")
    bridge_sd = {sd for (_, sd) in bridges}
    for sd in sorted(bridge_sd):  # collapsed subdomain boxes the subsystem's data bridges to
        lines.append(f'  {sd}["{_safe_label(str(graph["nodes"][sd]["name"]))}"]:::cy-{sd}')
        lines.append(f"  class {sd} subdomain")
    for src, verb, dst in _diagram_edges(graph, None, keep):  # internal + dep edges (labelled)
        lines.append(f"  {src} -->|{verb}| {dst}")
    for (src, dst), c in sorted(cross.items()):  # neighbourhood arrows (click -> edge card)
        lines.append(f"  {src} -->|{c}| {dst}")
    for (src, dst), c in sorted(childcross.items()):  # nested child-subsystem arrows (aggregated; box drills in)
        lines.append(f"  {src} -->|{c}| {dst}")
    for (src, sd), c in sorted(bridges.items()):  # bridge arrows: member -> subdomain (underlying edge count)
        lines.append(f"  {src} -->|{c}| {sd}")
    lines.append(f"  classDef component {COMPONENT_STYLE};")
    lines.append(f"  classDef dep {DEP_STYLE};")
    lines.append(f"  classDef subsystem {SUBSYSTEM_STYLE};")
    if bridge_sd:
        lines.append(DOMAIN_SUBDOMAIN_CLASSDEF)
    return "\n".join(lines)


def subsystem_component_mermaids(graph: GraphDict) -> dict[str, str]:
    """One subsystem-card diagram per subsystem at EVERY level (see gen_subsystem_card_mermaid), so a
    nested child subsystem has its own card to drill into. The viewer keys these by id, so a ⌘-click on
    any subsystem box — top-level box in the overview or a child box inside a card — finds its card."""
    return {nid: gen_subsystem_card_mermaid(graph, nid)
            for nid, node in graph["nodes"].items()
            if str(node["kind"]) == "subsystem"}


def gen_edge_card_mermaid(graph: GraphDict, a: str, b: str) -> str:
    """Edge card: disjoint subsystems `a` and `b` as two frames holding their IMMEDIATE children
    (components + child-subsystem boxes), drawn with the a->b crossings between them PLUS each frame's
    own internal component wiring. A crossing between two DIRECT members keeps its `src -->|verb| dst`
    so the viewer's edge bridge resolves it to the real component edge; a crossing reaching into a child
    subsystem is an aggregated box arrow. Deps and other-subsystem edges are omitted, and only the a->b
    direction is drawn (the b->a arrow has its own card)."""
    members_a = {cid for cid, _ in _components_of(graph, a)}
    members_b = {cid for cid, _ in _components_of(graph, b)}
    lines = ["flowchart LR", *_component_subgraph(graph, a), *_component_subgraph(graph, b)]
    for src, verb, dst in _diagram_edges(graph, None, members_a):  # a's inner links
        lines.append(f"  {src} -->|{verb}| {dst}")
    for src, verb, dst in _diagram_edges(graph, None, members_b):  # b's inner links
        lines.append(f"  {src} -->|{verb}| {dst}")
    agg: dict[tuple[str, str], int] = {}
    for e in graph["edges"]:  # the a->b crossings, bucketed to each frame's immediate children
        s, d = str(e["src"]), str(e["dst"])
        if not (_in_subtree(graph, s, a) and _in_subtree(graph, d, b)):
            continue
        ba, bb = _child_under(graph, s, a), _child_under(graph, d, b)
        if ba == s and bb == d:                      # both direct members -> labelled (resolves to the edge)
            lines.append(f"  {s} -->|{e['verb']}| {d}")
        else:                                        # reaches into a child subsystem -> aggregated box arrow
            agg[(str(ba), str(bb))] = agg.get((str(ba), str(bb)), 0) + 1
    for (src, dst), c in sorted(agg.items()):
        lines.append(f"  {src} -->|{c}| {dst}")
    lines.append(f"  classDef component {COMPONENT_STYLE};")
    if _child_subsystems(graph, a) or _child_subsystems(graph, b):  # child boxes present -> style them
        lines.append(f"  classDef subsystem {SUBSYSTEM_STYLE};")
    return "\n".join(lines)


def edge_card_mermaids(graph: GraphDict) -> dict[str, str]:
    """One edge-card diagram per disjoint subsystem pair with a crossing component edge — at every drill
    level, not only top-level — keyed 'A>B' to match the rendered arrow's endpoints (overview or nested
    card). Built from the one _edge_card_pairs source."""
    return {f"{a}>{b}": gen_edge_card_mermaid(graph, a, b) for (a, b) in sorted(_edge_card_pairs(graph))}


def compute_state(graph: GraphDict, diff: DiffDict | None) -> dict[str, str]:
    """Per-node change state for the diff badges: added / modified / deleted / rippled."""
    if not diff:
        return {}
    draw = _draw_nodes(graph, diff)
    ids = {nid for nid, _, _ in draw}
    changed = {c["id"]: c["change"] for c in diff["changes"]}
    state: dict[str, str] = dict(changed)
    for src, _, dst in _diagram_edges(graph, diff, ids):
        if src in changed and dst not in changed:
            state[dst] = "rippled"
    return state


def _field_ci(node: dict[str, Any], key: str) -> str:
    """A node field looked up case-insensitively (table headers vary in case)."""
    for k, v in cast("dict[str, object]", node.get("fields") or {}).items():
        if k.strip().lower() == key:
            return str(v)
    return ""


def _dep_kind(node: dict[str, Any]) -> str:
    """A dep node's Context Kind, defaulting to 'library' (folds) when unset."""
    return str(node.get("dep_kind") or "library")


def _dep_bucket(node: dict[str, Any]) -> str:
    """A dep node's purpose bucket via the shared resolver: the authored `Bucket` field or the
    heuristic fallback. `is_library` follows the dep's Kind so the fallback draws from the right seed
    family and a folded dep never lands in an external bucket (or vice-versa)."""
    is_lib = _dep_kind(node) in DEP_KINDS_FOLDED
    return resolve_bucket(is_lib, _field_ci(node, "bucket"),
                          _field_ci(node, "type"), _field_ci(node, "used for"))


def folded_libs(graph: GraphDict) -> list[dict[str, str]]:
    """(id, name, type, used_for, bucket) for the deps folded into the Context 'Libraries' box — those
    whose Kind is an in-process one (framework / library). The C4 Context view shows external SYSTEMS
    by name and collapses these, since libraries are an implementation concern, not a system the
    project talks to; `bucket` groups them once the box is drilled."""
    out: list[dict[str, str]] = []
    for nid, node in graph["nodes"].items():
        if str(node["kind"]) == "dep" and _dep_kind(node) in DEP_KINDS_FOLDED:
            out.append({"id": nid, "name": str(node["name"]), "type": _field_ci(node, "type"),
                        "used_for": _field_ci(node, "used for"), "bucket": _dep_bucket(node)})
    return out


def _dep_caption(used_for: str) -> str:
    """A short caption drawn under a dep box's name — the LEAD of its 'Used for', link-stripped, cut at
    the first clause and capped, so a box reads 'Scrapfly / scraping' instead of a full sentence. Empty
    'Used for' → no caption (the name stands alone)."""
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", used_for or "")     # md link -> its text
    s = re.split(r"[.;(]| — |, ", s.strip())[0]                     # first clause only
    s = s.replace('"', "'").replace("`", "").replace("[", "(").replace("]", ")")
    s = s.replace("<", "(").replace(">", ")")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= 32:
        return s
    cut = s[:32].rsplit(" ", 1)[0].strip(" -/·")   # trim back to a word boundary
    return (cut or s[:32]) + "…"


def _dep_view(nid: str, node: dict[str, Any]) -> dict[str, str]:
    """The fields the grouped Context/Libraries diagrams need per dep: id, name, its short caption
    source, and its (resolved) purpose bucket."""
    return {"id": nid, "name": str(node["name"]),
            "used_for": _field_ci(node, "used for"), "bucket": _dep_bucket(node)}


def _context_dep_groups(deps: list[dict[str, str]], is_library: bool) -> list[str]:
    """Mermaid lines drawing `deps` grouped into one labelled subgraph per PURPOSE bucket (in seed
    order), each dep a cylinder captioned by the lead of its 'Used for', plus an UNLABELLED `SYS -->
    dep` arrow (the direction already says 'uses'; the repeated word was pure noise). Shared by the
    Context view (external systems) and the Libraries drill (folded in-process code) — the ONE grouping
    implementation, so both diagrams read identically. Cluster ids are `CYBK<i>` (presentational
    frames, not graph nodes) — the viewer tints them via that prefix."""
    open_b, close_b = SHAPE["dep"]
    by_bucket: dict[str, list[dict[str, str]]] = {}
    for d in deps:
        by_bucket.setdefault(canonical_bucket(d["bucket"]), []).append(d)
    lines: list[str] = []
    for i, bucket in enumerate(order_buckets(by_bucket.keys(), is_library)):
        lines.append(f'  subgraph CYBK{i}["{_safe_label(bucket)}"]')
        for d in by_bucket[bucket]:
            cap = _dep_caption(d["used_for"])
            label = _safe_label(d["name"]) + (f"<br/>{cap}" if cap else "")
            lines.append(f'    {d["id"]}{open_b}{label}{close_b}:::cy-{d["id"]}')
            lines.append(f'    class {d["id"]} dep')
        lines.append("  end")
    for d in deps:
        lines.append(f'  SYS --> {d["id"]}')
    return lines


def _context_head(graph: GraphDict) -> list[str]:
    """The System node + actor lifelines — the part of the Context view shared with its drill-downs."""
    title = _safe_label(graph["title"] or "System")
    # LR (not TB): with every dep hanging off SYS at the same rank, TB spreads them across ONE very wide
    # row (unreadable at ~45 deps); LR stacks them into a narrow, tall column of bucket clusters instead.
    lines = ["flowchart LR", f'  SYS["{title}"]:::cy-SYS', "  class SYS system"]
    for i, r in enumerate(graph["roles"]):
        rid = "R" + str(i)
        label = _safe_label(r["name"])
        if r["kind"] == "service":
            lines.append(f'  {rid}{{{{"{label}"}}}}:::cy-{rid}')   # hexagon = service actor
            lines.append(f"  class {rid} svc")
        else:
            lines.append(f'  {rid}(["{label}"]):::cy-{rid}')        # stadium = human actor
            lines.append(f"  class {rid} human")
        lines.append(f"  {rid} --> SYS")                            # direction says 'uses'; no label noise
    return lines


CONTEXT_CLASSDEFS = [
    "  classDef system fill:#1e1b4b,stroke:#312e81,color:#fff;",
    "  classDef human fill:#fff7ed,stroke:#c2410c,color:#7c2d12;",
    "  classDef svc fill:#eef2ff,stroke:#4338ca,color:#312e81;",
    f"  classDef dep {DEP_STYLE};",
    # Group CONTAINERS (the Libraries bundle box + folded bucket count boxes) share one look: the same
    # emerald hue as the individual deps/libraries they hold, but a paler fill and a DASHED border — the
    # convention that says "this is a drillable group", not a leaf.
    f"  classDef libs {CONTAINER_STYLE};",
    f"  classDef bucketfold {CONTAINER_STYLE};",
]


def _external_buckets(graph: GraphDict) -> dict[str, list[dict[str, str]]]:
    """Shown external deps (kinds NOT folded into Libraries) grouped by canonical purpose bucket."""
    by: dict[str, list[dict[str, str]]] = {}
    for nid, node in graph["nodes"].items():
        if str(node["kind"]) == "dep" and _dep_kind(node) not in DEP_KINDS_FOLDED:
            d = _dep_view(nid, node)
            by.setdefault(canonical_bucket(d["bucket"]), []).append(d)
    return by


def _library_buckets(graph: GraphDict) -> dict[str, list[dict[str, str]]]:
    """Folded in-process deps (the Libraries drill's contents) grouped by canonical purpose bucket."""
    by: dict[str, list[dict[str, str]]] = {}
    for d in folded_libs(graph):
        by.setdefault(canonical_bucket(d["bucket"]), []).append(d)
    return by


def _folds(by: dict[str, list[dict[str, str]]], is_library: bool, prefix: str,
           all_or_nothing: bool) -> list[dict[str, Any]]:
    """The buckets that collapse into a drillable count box, in diagram order (seed-first). A bucket
    reaching DEP_BUCKET_FOLD_AT members is 'big'. `all_or_nothing` (the Context view): if ANY bucket is
    big, EVERY bucket folds so the top altitude reads uniformly — no mix of inline clusters and count
    boxes. Not all-or-nothing (the Libraries drill): fold ONLY the big buckets and leave small ones
    inline, so a one-library bucket never becomes a pointless count box. Each fold is
    {id: '<prefix><i>', name, members, is_library} — the ONE source every consumer (count box, drill
    diagram, synthetic node, context edge, roster) derives from, so the ids stay consistent."""
    ordered = order_buckets(by.keys(), is_library)
    if not any(len(by[b]) >= DEP_BUCKET_FOLD_AT for b in ordered):
        return []
    chosen = ordered if all_or_nothing else [b for b in ordered if len(by[b]) >= DEP_BUCKET_FOLD_AT]
    return [{"id": f"{prefix}{i}", "name": b, "members": by[b], "is_library": is_library}
            for i, b in enumerate(chosen)]


def folded_context_buckets(graph: GraphDict) -> list[dict[str, Any]]:
    """The external-system buckets folded into count boxes in the Context view (`BKF<i>`), or []. The
    top altitude folds ALL-OR-NOTHING for a uniform look."""
    return _folds(_external_buckets(graph), is_library=False, prefix="BKF", all_or_nothing=True)


def folded_library_buckets(graph: GraphDict) -> list[dict[str, Any]]:
    """The in-process buckets folded into count boxes in the Libraries drill (`LBKF<i>`), or []. The
    drill folds PARTIALLY — only big buckets fold; small ones stay inline (libraries are excluded from
    the Context view's all-or-nothing consistency rule)."""
    return _folds(_library_buckets(graph), is_library=True, prefix="LBKF", all_or_nothing=False)


def all_folded_buckets(graph: GraphDict) -> list[dict[str, Any]]:
    """Every folded bucket across both diagrams (external Context buckets + library-drill buckets) — the
    synthetic nodes / drill diagrams / context edges / roster all range over this."""
    return folded_context_buckets(graph) + folded_library_buckets(graph)


def _fold_box_lines(fb: dict[str, Any]) -> list[str]:
    """The count box for a folded bucket: `<id>["<name> (N)"]` classed as a container, arrowed from SYS.
    No icon — the dashed container border already signals a drillable group."""
    return [f'  {fb["id"]}["{_safe_label(fb["name"])} ({len(fb["members"])})"]:::cy-{fb["id"]}',
            f'  class {fb["id"]} bucketfold',
            f'  SYS --> {fb["id"]}']


def gen_context_mermaid(graph: GraphDict) -> str:
    """C4 Context: the system as one node, actors (Roles) using it, and the EXTERNAL SYSTEMS it relies
    on — GROUPED by purpose bucket. On a small map every bucket is an inline labelled cluster; once ANY
    bucket is big enough to fold (>= DEP_BUCKET_FOLD_AT), ALL of them collapse into uniform drillable
    count boxes so an integration-heavy map stays legible. In-process deps (framework / library) still
    fold into one `Libraries (N)` box."""
    lines = _context_head(graph)
    by = _external_buckets(graph)
    folded = folded_context_buckets(graph)
    if folded:
        for fb in folded:
            lines += _fold_box_lines(fb)
    else:
        lines += _context_dep_groups([d for b in order_buckets(by.keys(), is_library=False) for d in by[b]],
                                     is_library=False)
    n_folded = len(folded_libs(graph))
    if n_folded:
        lines.append(f'  {LIBS_ID}["Libraries ({n_folded})"]:::cy-{LIBS_ID}')
        lines.append(f"  class {LIBS_ID} libs")
        lines.append(f"  SYS -->|bundles| {LIBS_ID}")
    lines += CONTEXT_CLASSDEFS
    return "\n".join(lines)


def mermaid_by_bucketfold(graph: GraphDict) -> dict[str, str]:
    """The drill diagram for each folded bucket — external (`BKF<i>`) AND library (`LBKF<i>`): the System
    + that ONE bucket's members drawn by name, same shape as its parent view. Reached by drilling the
    count box."""
    out: dict[str, str] = {}
    for fb in all_folded_buckets(graph):
        lines = _context_head(graph)
        lines += _context_dep_groups(fb["members"], is_library=fb["is_library"])
        lines += CONTEXT_CLASSDEFS
        out[fb["id"]] = "\n".join(lines)
    return out


def folded_buckets_roster(graph: GraphDict) -> list[dict[str, Any]]:
    """The folded-bucket roster the viewer carries (count-box preview panel + member routing + which
    parent view a bucket drills out of): [{id, name, count, parent, members: [{id, name}]}]. `parent` is
    'libs' for a library bucket (it drills out of the Libraries view), else 'context'."""
    return [{"id": fb["id"], "name": fb["name"], "count": len(fb["members"]),
             "parent": "libs" if fb["is_library"] else "context",
             "members": [{"id": m["id"], "name": m["name"]} for m in fb["members"]]}
            for fb in all_folded_buckets(graph)]


def gen_libs_mermaid(graph: GraphDict) -> str:
    """The Libraries drill-down (reached by drilling the Context 'Libraries' box): the System + every
    folded in-process dep, GROUPED by purpose bucket. Like the Context view: small → inline clusters;
    once any library bucket is big enough, ALL fold into drillable count boxes (each drills to its
    members). Empty string when nothing is folded into Libraries (the box — hence this view — never
    appears)."""
    libs = folded_libs(graph)
    if not libs:
        return ""
    lines = _context_head(graph)
    by = _library_buckets(graph)
    folded = folded_library_buckets(graph)
    folded_names = {fb["name"] for fb in folded}                        # big buckets → count boxes; the rest stay inline
    inline = [d for b in order_buckets(by.keys(), is_library=True) if b not in folded_names for d in by[b]]
    lines += _context_dep_groups(inline, is_library=True)
    for fb in folded:
        lines += _fold_box_lines(fb)
    lines += CONTEXT_CLASSDEFS
    return "\n".join(lines)


def add_context_nodes(g: dict[str, Any], graph: GraphDict) -> None:
    """Synthetic System + actor nodes in the panel graph so the click bridge resolves them."""
    g["nodes"]["SYS"] = {"id": "SYS", "kind": "system", "name": graph["title"] or "System",
                         "file": None, "line": None,
                         "fields": {"Overview": graph["goal"]} if graph.get("goal") else {}}
    for i, r in enumerate(graph["roles"]):
        rid = "R" + str(i)
        g["nodes"][rid] = {"id": rid, "kind": r["kind"], "name": r["name"], "file": None, "line": None,
                           "fields": ({"Wants": r["wants"]} if r["wants"] else {})}
    # The collapsed Libraries box is a synthetic node so bindNodes binds it (it skips ids absent from
    # the graph) and the click bridge resolves it; its panel/tooltip are driven by FOLDED_LIBS, not fields.
    if folded_libs(graph):
        g["nodes"][LIBS_ID] = {"id": LIBS_ID, "kind": "libs", "name": "Libraries",
                               "file": None, "line": None, "fields": {}}
    # Each folded bucket (external AND library) is a synthetic node too (same reason as LIBS): so
    # bindNodes binds its count box and the click bridge resolves it; panel/tooltip come from the roster.
    for fb in all_folded_buckets(graph):
        g["nodes"][fb["id"]] = {"id": fb["id"], "kind": "bucketfold", "name": fb["name"],
                                "file": None, "line": None, "fields": {}}


# ── Deployment view (processes/threads ↔ subsystems) ──────────────────────────────────────────────
# A process is NOT a model element (it stays a `deployment[]` table row); it is a VIEW-only graph node,
# injected like SYS/roles so the viewer's binders (which skip ids absent from GRAPH.nodes) resolve it.
# Ids are INDEX-based `U_<n>` — never a name slug, which could collide for two units differing only in
# punctuation (mermaid silently merges same-id nodes). The `runs` edges are DERIVED (process → the
# subsystem of each component whose `runs_in` names the unit), never authored in `edges[]`.
_INFRA_DEP_KINDS = ("messaging", "datastore", "service")


def _deployment_unit_ids(graph: GraphDict) -> list[tuple[str, str]]:
    """`[(U_<n>, unit_name)]` for each deployment unit — one shared index→id mapping used by BOTH the
    node injection and the generators, so their ids always agree."""
    return [(f"U_{i}", str(r.get("unit", ""))) for i, r in enumerate(graph["deployment"])]


def has_deployment(graph: GraphDict) -> bool:
    return bool(graph["deployment"])


def _node_runs_in(node: object) -> list[str]:
    """A graph node's `runs_in` as a `list[str]` (components only carry it; missing → [])."""
    v = node.get("runs_in") if isinstance(node, dict) else None
    return [str(x) for x in v] if isinstance(v, list) else []


def _entry_point_runs_in(ep: object) -> list[str]:
    """An entry point's `runs_in` — the precise host unit(s) of a self-started thread (its component may
    run in several). Carried in the graph's flat `entry_points` list (from EntryPoint.runs_in)."""
    v = ep.get("runs_in") if isinstance(ep, dict) else None
    return [str(x) for x in v] if isinstance(v, list) else []


def _process_unit_names(graph: GraphDict) -> set[str]:
    """The deployment units that are real PROCESSES: a unit hosting ≥1 component OR ≥1 entry point via
    `runs_in` (B2 — a worker whose component runs in several units is tagged only at the entry-point
    level; counting components alone would drop that real process). A unit hosting neither is
    infrastructure the app talks to (mongo/redis/nginx), not a code-running process."""
    hosts: set[str] = set()
    for node in graph["nodes"].values():
        if isinstance(node, dict) and str(node.get("kind")) == "component":
            hosts.update(_node_runs_in(node))
    for ep in graph.get("entry_points", []):
        hosts.update(_entry_point_runs_in(ep))
    return {u for u in hosts if u}


def _system_dep_names(graph: GraphDict) -> list[str]:
    """The names of every EXTERNAL (system) dependency box — datastore/messaging/service/platform. A
    no-host deployment unit whose name matches one of these IS that dep's box, not a real process."""
    return [str(node.get("name", "")) for node in graph["nodes"].values()
            if isinstance(node, dict) and str(node.get("kind")) == "dep"
            and node.get("dep_kind") in DEP_KINDS_SYSTEM]


def _unit_matches_system_dep(unit: str, dep_names: list[str]) -> bool:
    """The no-host unit `unit` name-matches a drawn system-dep box (so it needs no process/untraced box)."""
    return any(unit_name_matches_dep(unit, dn) for dn in dep_names)


def add_deployment_nodes(g: dict[str, Any], graph: GraphDict) -> None:
    """Inject one view-only `process` node per deployment unit that HOSTS code (a component or entry
    point runs in it — `_process_unit_names`), so the Deployment view's process boxes bind + drill +
    show a panel. Infrastructure units (mongo/redis/nginx — no `runs_in` points at them) get NO process
    node: they are already the dep box the running components point at, so a process box would be a dead,
    arrow-less duplicate. `_deployment_unit_ids` stays complete (the shared index→id map); the skip is
    HERE, at the usage site (S1). `unit` carries the raw name for the drill/reverse lookup."""
    process_units = _process_unit_names(graph)
    for uid, unit in _deployment_unit_ids(graph):
        if unit not in process_units:
            continue
        r = graph["deployment"][int(uid[2:])]
        fields = {k: str(v) for k, v in (("Runs on", r.get("runs_on")),
                                         ("Exposed as", r.get("exposed_as")),
                                         ("Config source", r.get("config_source"))) if v}
        g["nodes"][uid] = {"id": uid, "kind": "process", "name": unit or uid,
                           "file": None, "line": None, "fields": fields, "unit": unit}


def _subsystem_box_of(graph: GraphDict, cid: str) -> str:
    """The box a component `runs` edge points at: its top subsystem, or the component itself when it is
    ungrouped (still a real node, so it binds)."""
    return _top_subsystem(graph, cid) or cid


def _declare_box(graph: GraphDict, nid: str, default_kind: str) -> list[str]:
    """The two mermaid lines declaring a node box (`id["label"]:::cy-id` + `class id kind`), so an
    endpoint that would otherwise render as a bare inert node binds with the right colour."""
    node = graph["nodes"].get(nid, {})
    name = str(node.get("name", nid))
    kind = str(node.get("kind") or default_kind)
    shape = SHAPE.get(kind, ('["', '"]'))
    cls = kind if kind in ("subsystem", "component", "infra", "dep", "process") else "subsystem"
    return [f'  {nid}{shape[0]}{_safe_label(name)}{shape[1]}:::cy-{nid}', f"  class {nid} {cls}"]


def _deployment_edges(graph: GraphDict, uid_of: dict[str, str]
                      ) -> tuple[set[tuple[str, str]], set[tuple[str, str]], dict[str, set[str]]]:
    """Derive the Deployment view's edges: `runs` (process → the subsystem/ungrouped-component of each
    component it runs) and `infra` (process → a broker/store dep a running component touches). Also
    returns `boxes_by_uid` (the subsystem boxes each process runs) for the core/satellite lane split."""
    runs: set[tuple[str, str]] = set()
    infra: set[tuple[str, str]] = set()
    boxes_by_uid: dict[str, set[str]] = {}
    for nid, node in graph["nodes"].items():
        if str(node.get("kind")) != "component":
            continue
        for unit in _node_runs_in(node):
            uid = uid_of.get(str(unit))
            if not uid:
                continue
            box = _subsystem_box_of(graph, nid)
            runs.add((uid, box))
            boxes_by_uid.setdefault(uid, set()).add(box)
    for e in graph["edges"]:
        dn = graph["nodes"].get(str(e["dst"]))
        cn = graph["nodes"].get(str(e["src"]))
        if not dn or str(dn.get("kind")) != "dep" or dn.get("dep_kind") not in _INFRA_DEP_KINDS:
            continue
        if not cn or str(cn.get("kind")) != "component":
            continue
        for unit in _node_runs_in(cn):
            uid = uid_of.get(str(unit))
            if uid:
                infra.add((uid, str(e["dst"])))
    return runs, infra, boxes_by_uid


def _components_run_by_uid(graph: GraphDict, uid_of: dict[str, str]) -> dict[str, set[str]]:
    """`uid → {component ids that run in that process}`. The packaging fingerprint of each process, used
    to spot an all-in-one unit (a superset of every other process's set)."""
    out: dict[str, set[str]] = {}
    for nid, node in graph["nodes"].items():
        if str(node.get("kind")) != "component":
            continue
        for unit in _node_runs_in(node):
            uid = uid_of.get(str(unit))
            if uid:
                out.setdefault(uid, set()).add(nid)
    return out


def _allinone_uids(process_uids: list[str], comps_by_uid: dict[str, set[str]]) -> set[str]:
    """The process units that are ALL-IN-ONE packagings, not peers: a unit whose component set contains
    the union of every OTHER process unit's components (e.g. a `standalone` that runs everything
    `backend` and `frontend` run between them). Such a unit re-runs the whole mesh, so fanning its arrows
    just re-draws every other arrow — the overview folds it to a label instead.
    Guard: never fold so many that no fanned process remains (the all-equal degenerate case, where every
    unit runs the same set — fold nothing so the overview still shows the processes)."""
    if len(process_uids) < 2:
        return set()
    fold: set[str] = set()
    for u in process_uids:
        mine = comps_by_uid.get(u, set())
        if not mine:
            continue
        others: set[str] = set().union(*(comps_by_uid.get(o, set()) for o in process_uids if o != u))
        if others and others <= mine:
            fold.add(u)
    if len(fold) >= len(process_uids):   # would fold every process → keep them all fanned instead
        return set()
    return fold


def _unit_variants(graph: GraphDict) -> dict[str, set[str]]:
    """`{unit_name: {environment…}}` from the deployment rows — a unit's declared variants. An empty
    set means UNGATED (the unit appears in every environment)."""
    out: dict[str, set[str]] = {}
    for r in graph["deployment"]:
        out[str(r.get("unit", ""))] = {str(v) for v in (r.get("variants") or [])}  # type: ignore[union-attr]
    return out


def deployment_environments(graph: GraphDict) -> list[str]:
    """The declared deployment-variant names, in order — or [] when the project has no environment axis."""
    return [str(e) for e in graph.get("environments", [])]


def gen_deployment_mermaid(graph: GraphDict, env: str | None = None) -> str:
    """The Deployment overview: each deployable unit a `process` box and derived `runs` edges to the
    subsystems it executes. Everything drawn is a real (or injected) graph node, so every box binds
    (the B1 rule).

    `env` (an entry of `graph["environments"]`) filters the overview to one deployment variant: a unit
    is shown iff its `variants` include `env` OR its `variants` are empty (ungated / shared). `env=None`
    is the "All" view (every unit — today's behavior, unchanged when a map declares no environments).
    NB the infra/`runs` derivation is from AGGREGATE component→dep/subsystem edges, so a component that
    runs in units of several environments contributes its infra to each of them (env-specific infra
    needs env-specific components — stated in method.md).

    Two readability rules keep the overview from hairballing (both DERIVED — kind + `runs_in`, no
    authored input):
      * AMBIENT INFRA — the brokers/stores the app talks to are drawn as an Infrastructure band at the
        bottom, but NOT wired with process→infra arrows (adjacency implies use). Each process's actual
        brokers/stores live on its drill card. This drops the fan of infra arrows.
      * ALL-IN-ONE FOLD — a unit that runs everything the other processes run between them (a superset
        packaging, e.g. `standalone`) is not a peer; fanning it re-draws every arrow. It is folded to a
        labelled annotation ("… — all-in-one: runs everything below"), no arrows.
    What remains is the meaningful skeleton: each genuine process → the subsystems it (alone) runs.

    LAYERED layout: nodes band into subgraph lanes — the all-in-one packagings, then the fanned
    processes (shared-runtime apart from standalone when a monolith is present), then the Subsystems
    band, then Infrastructure — so dagre stacks them into readable rows instead of a flat mesh."""
    units = _deployment_unit_ids(graph)
    uid_of = {unit: uid for uid, unit in units}
    # Per-environment filter: a unit is IN `env` when its variants include it or are empty (ungated).
    # `env=None` (All) admits every unit, so the `_deployment_unit_ids` index map stays complete (S1) —
    # only which uids are DRAWN is filtered, never the U_n numbering.
    variants_of = _unit_variants(graph)
    env_uids = {uid for uid, name in units
                if env is None or env in variants_of.get(name, set()) or not variants_of.get(name, set())}
    runs, infra, boxes_by_uid = _deployment_edges(graph, uid_of)
    runs = {(u, b) for (u, b) in runs if u in env_uids}
    infra = {(u, b) for (u, b) in infra if u in env_uids}
    boxes_by_uid = {u: bs for u, bs in boxes_by_uid.items() if u in env_uids}
    # Only units that HOST code are process boxes (B2). A no-host unit is either an infra dep already
    # drawn in the Infrastructure lane (name-match → drawn NOWHERE) or a genuinely-unlinked unit (a real
    # gap → the small "Untraced units" lane, so it is never dropped silently — S2).
    process_units = _process_unit_names(graph)
    dep_names = _system_dep_names(graph)
    process_uids = [uid for uid, name in units if name in process_units and uid in env_uids]
    untraced = [uid for uid, name in units
                if name not in process_units and not _unit_matches_system_dep(name, dep_names)
                and uid in env_uids]
    # ALL-IN-ONE FOLD: superset units are annotated, not fanned. Only the fanned units draw `runs` arrows
    # and drive the core/satellite split, so a monolith's own arrows don't paint every peer as "shared".
    comps_by_uid = _components_run_by_uid(graph, uid_of)
    fold = _allinone_uids(process_uids, comps_by_uid)
    fanned = [uid for uid in process_uids if uid not in fold]
    fanned_set = set(fanned)
    fanned_runs = {(u, b) for (u, b) in runs if u in fanned_set}
    endpoints = {b for _u, b in fanned_runs}
    # core = a fanned process sharing a subsystem with another fanned process; satellite = runs its
    # subsystems alone. (Folded all-in-one units are excluded — they run everything, so counting them
    # would mark every process as shared.)
    runners_of: dict[str, set[str]] = {}
    for uid, box in fanned_runs:
        runners_of.setdefault(box, set()).add(uid)
    def is_core(uid: str) -> bool:
        return any(len(runners_of.get(b, ())) > 1 for b in boxes_by_uid.get(uid, ()))
    core = [uid for uid in fanned if is_core(uid)]
    sat = [uid for uid in fanned if uid not in set(core)]
    # AMBIENT INFRA: the Infrastructure band shows every broker/store any running component touches, as an
    # ambient lane under the processes — NO process→infra arrows on the overview (they live on the cards).
    infra_boxes = sorted({b for _u, b in infra})
    sub_boxes = sorted(endpoints)

    lines = ["flowchart TB"]
    class_lines: list[str] = []
    label_of = {uid: unit for uid, unit in units}  # process ids aren't in the clean graph — label from units
    allinone_label = {uid: f"{label_of.get(uid, uid)} — all-in-one: runs everything below" for uid in fold}

    def _decl(nid: str, default_kind: str) -> tuple[str, str]:
        node = graph["nodes"].get(nid, {})
        name = allinone_label.get(nid) or label_of.get(nid) or str(node.get("name", nid))
        kind = str(node.get("kind") or default_kind)
        shape = SHAPE.get(kind, ('["', '"]'))
        cls = kind if kind in ("subsystem", "component", "infra", "dep", "process") else "subsystem"
        return f'{nid}{shape[0]}{_safe_label(name)}{shape[1]}:::cy-{nid}', f"  class {nid} {cls}"

    def lane(lid: str, title: str, ids: list[str], default_kind: str) -> None:
        if not ids:
            return
        lines.append(f'  subgraph {lid}["{title}"]')
        for nid in ids:
            decl, cls = _decl(nid, default_kind)
            lines.append(f"    {decl}")
            class_lines.append(cls)
        lines.append("  end")

    # Folded all-in-one packagings first — labelled boxes, no arrows (they still bind + drill to a card
    # showing everything they run).
    lane("L_allinone", "All-in-one", sorted(fold), "process")
    if core:                                              # a monolith is present → split the fanned band
        lane("L_core", "Shared runtime", core, "process")
        lane("L_sat", "Standalone services", sat, "process")
    else:
        lane("L_proc", "Processes", fanned, "process")
    lane("L_subs", "Subsystems", sub_boxes, "subsystem")
    lane("L_infra", "Infrastructure", infra_boxes, "infra")
    # A unit hosting no code and matching no infra dep is a real gap — surface it in its own lane rather
    # than dropping it silently (S2). It has no injected graph node (so it stays inert), and the viewer
    # keeps it searchable via a non-process fallback row.
    lane("L_untraced", "Untraced units", untraced, "process")

    lines += class_lines
    for a, b in sorted(fanned_runs):                      # only fanned processes draw arrows; infra is ambient
        lines.append(f"  {a} --> {b}")
    lines.append(f"  classDef process {PROCESS_STYLE};")
    lines.append(f"  classDef subsystem {SUBSYSTEM_STYLE};")
    lines.append(f"  classDef component {COMPONENT_STYLE};")
    lines.append(f"  classDef infra {INFRA_STYLE};")
    return "\n".join(lines)


def gen_deployment_unit_card_mermaid(graph: GraphDict, unit: str) -> str:
    """One process's card: the unit box + the subsystems/components it runs AND the brokers/stores it
    uses. The infra arrows are dropped from the OVERVIEW (ambient band there) and shown HERE instead, so
    a process's actual dependencies are still one click away. Its threads are a panel list on the
    frontend, not diagram nodes. Reuses `_deployment_edges` so the card's runs/infra match the overview's
    exactly (one derivation)."""
    units = _deployment_unit_ids(graph)
    uid_of = {name: u for u, name in units}
    uid = uid_of.get(unit)
    lines = ["flowchart TB"]
    if uid is None:
        return "\n".join(lines + [f'  MISSING["{_safe_label(unit)} — not a deployment unit"]'])
    runs, infra, _boxes = _deployment_edges(graph, uid_of)
    lines.append(f'  {uid}["{_safe_label(unit)}"]:::cy-{uid}')
    lines.append(f"  class {uid} process")
    for nid in sorted({b for u, b in runs if u == uid}):        # subsystems/components it runs
        lines += _declare_box(graph, nid, "subsystem")
        lines.append(f"  {uid} --> {nid}")
    for did in sorted({d for u, d in infra if u == uid}):       # brokers/stores it uses (dropped from overview)
        lines += _declare_box(graph, did, "infra")
        lines.append(f"  {uid} --> {did}")
    lines.append(f"  classDef process {PROCESS_STYLE};")
    lines.append(f"  classDef subsystem {SUBSYSTEM_STYLE};")
    lines.append(f"  classDef component {COMPONENT_STYLE};")
    lines.append(f"  classDef infra {INFRA_STYLE};")
    return "\n".join(lines)


def deployment_cards(graph: GraphDict) -> dict[str, str]:
    """`{unit_name: card_mermaid}` — the per-process drill cards, keyed by unit NAME (the frontend
    drills a process to `{kind:'deploymentUnit', unit:<node.unit>}`). Cards are env-independent (a
    unit's card lists everything it runs); the environment picker only filters the OVERVIEW."""
    return {unit: gen_deployment_unit_card_mermaid(graph, unit)
            for _uid, unit in _deployment_unit_ids(graph) if unit}


def deployment_mermaid_by_env(graph: GraphDict) -> dict[str, str]:
    """`{environment_name: overview_mermaid}` — one filtered Deployment overview per declared
    environment (the "All" view stays `mermaidDeployment`). Empty `{}` when the map declares no
    environments, so the frontend shows no picker and renders the single overview as before."""
    return {e: gen_deployment_mermaid(graph, e) for e in deployment_environments(graph)}


def gen_context_edges(graph: GraphDict) -> dict[str, dict[str, Any]]:
    """Explanations for the Context view's synthetic edges, derived from already-parsed map data:
    actor→system = the role's 'wants'; system→dep = the dep's 'Used for' + the component edges
    (with their Why) that realize it; system→Libraries = the collapsed fold (panel reuses the roster).
    Keyed by '<src>><dst>' to match the rendered edge path ids. Registering the Libraries arrow here is
    what lets the viewer's focus/dim pass treat it like any other edge (keep it lit when the System is
    focused; dim it when a dependency is selected) — without an entry the arrow stays un-bound."""
    title = graph["title"] or "System"
    ce: dict[str, dict[str, Any]] = {}
    for i, r in enumerate(graph["roles"]):
        rid = "R" + str(i)
        ce[rid + ">SYS"] = {"src": rid, "dst": "SYS", "type": "actor",
                            "from": r["name"], "to": title, "wants": r["wants"]}
    # component edges grouped by their target — the "realized by" detail for system→dep
    by_dst: dict[str, list[dict[str, str]]] = {}
    for e in graph["edges"]:
        src, dst = str(e["src"]), str(e["dst"])
        node = graph["nodes"].get(src)
        why = e["why"]
        by_dst.setdefault(dst, []).append({
            "src": src,
            "srcName": str(node["name"]) if node else src,
            "verb": str(e["verb"]),
            "why": str(why) if why else "",
        })
    for nid, node in graph["nodes"].items():
        if str(node["kind"]) != "dep":
            continue
        fields = cast("dict[str, object]", node["fields"])
        ce["SYS>" + nid] = {"src": "SYS", "dst": nid, "type": "dep",
                            "from": title, "to": str(node["name"]),
                            "usedFor": str(fields.get("Used for") or ""),
                            "realizedBy": by_dst.get(nid, [])}
    # The collapsed Libraries fold draws a `SYS -->|bundles| LIBS` arrow (gen_context_mermaid). Register
    # it so the viewer binds it as a real edge; its panel/tooltip reuse the box's roster, not a 'why'.
    if folded_libs(graph):
        ce["SYS>" + LIBS_ID] = {"src": "SYS", "dst": LIBS_ID, "type": "libs",
                                "from": title, "to": "Libraries"}
    # Same for each folded bucket's `SYS --> <id>` arrow (external Context buckets + library-drill
    # buckets) — so the viewer binds it and clicking the arrow opens the bucket's roster (its `type`
    # routes to showBucketFold, not a 'why').
    for fb in all_folded_buckets(graph):
        ce["SYS>" + fb["id"]] = {"src": "SYS", "dst": fb["id"], "type": "bucketfold",
                                 "from": title, "to": fb["name"]}
    return ce


def has_hp(graph: GraphDict) -> bool:
    return bool(graph["happy_path"])


def _safe_msg(s: str) -> str:
    """Sanitize text for a Mermaid sequenceDiagram message / participant label: strip markdown links
    and emphasis, drop the chars that break sequence parsing (`;#<>` + newlines), collapse runs of
    whitespace. Colons are kept (only the FIRST colon delimits a message)."""
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)   # md link -> its text
    s = re.sub(r"[`*]", "", s)
    s = s.replace("\n", " ").replace(";", ",").replace("#", "").replace("<", "(").replace(">", ")")
    return re.sub(r"\s+", " ", s).strip()


def _hp_actor(graph: GraphDict, step: dict[str, Any]) -> str:
    """The actor that drives a GP step = the `Actor` of the use case it realizes (a step IS exactly one
    use case, so no separate actor signal is needed), falling back to a generic 'Actor'."""
    uc = step.get("uc")
    node = graph["nodes"].get(uc) if isinstance(uc, str) else None
    if node:
        for k, v in cast("dict[str, str]", node.get("fields") or {}).items():
            if k.strip().lower() == "actor" and str(v).strip():
                return _safe_msg(str(v))
    return "Actor"


def gen_hp_mermaid(graph: GraphDict) -> str:
    """C4 behavioural overlay, Level 1: the Happy Path as a black-box sequenceDiagram — each step a
    message from its actor to the System, in order. Each label is PREFIXED with its 1-based position
    (`1. …`, `2. …`) — the same numbering the T6 flows use — so a step's `HPn` id (surfaced on a
    Use-cases pill and in the side panel) points at a visible number; the bare `HPn` id itself is kept
    out of the label. The viewer pairs message[i] with step[i] by order. Distinct actors (derived per
    step from its UC) become the lifelines."""
    steps = cast("list[dict[str, Any]]", graph["happy_path"])
    title = _safe_msg(graph["title"] or "System")
    actor_ids: dict[str, str] = {}  # actor name -> stable participant id, in first-appearance order
    for st in steps:
        actor_ids.setdefault(_hp_actor(graph, st), "HPA" + str(len(actor_ids)))
    lines = ["sequenceDiagram"]
    for name, aid in actor_ids.items():
        lines.append(f"  actor {aid} as {name}")
    lines.append(f"  participant HPSYS as {title}")
    for i, st in enumerate(steps):
        aid = actor_ids[_hp_actor(graph, st)]
        title_txt = _safe_msg(str(st["title"])) if st["title"] else ""
        label = title_txt or str(st["id"])  # title only; id lives in the side panel, not the label
        lines.append(f"  {aid}->>HPSYS: {i + 1}. {label}")
    return "\n".join(lines)


def hp_actors(graph: GraphDict) -> list[dict[str, Any]]:
    """Per-actor data for the Happy Path lifelines, in the SAME participant order/ids as
    gen_hp_mermaid (so `HPAn` lines up with the rendered lifeline). Each actor links back to its
    Roles-table entry by name to surface what it wants + its kind, plus the GP steps it drives —
    `stepIdx` are the message positions the viewer highlights when the actor is selected."""
    steps = cast("list[dict[str, Any]]", graph["happy_path"])
    roles_by_name = {_safe_msg(r["name"]).strip().lower(): r for r in graph["roles"]}
    order: dict[str, str] = {}  # actor name -> participant id, first-appearance order (matches gen_hp_mermaid)
    for st in steps:
        order.setdefault(_hp_actor(graph, st), "HPA" + str(len(order)))
    out: list[dict[str, Any]] = []
    for name, aid in order.items():
        idxs = [i for i, st in enumerate(steps) if _hp_actor(graph, st) == name]
        role = roles_by_name.get(name.strip().lower())
        out.append({
            "aid": aid,
            "name": name,
            "kind": str(role["kind"]) if role else "",
            "wants": str(role["wants"]) if role else "",
            "steps": [{"id": str(steps[i]["id"]), "title": str(steps[i]["title"] or "")} for i in idxs],
            "stepIdx": idxs,
        })
    return out


# ── T6 use-case flows: the shared sequence renderer ───────────────────────────────────────────────
# One renderer drives BOTH the use-case view and the Happy-Path step drill-down (an HP step IS a use
# case, so it opens that use case's flow). A flow renders two derived views from ONE source — a Mermaid
# sequenceDiagram (the visual) and a numbered narrative (the readable text) — so the "why" of each step
# is never authored twice. Each step carries its OWN action text; the arrow and the panel render from
# that text alone, so a step describes what happens at that point — not a shared pair-level edge label.

def _edge_index(graph: GraphDict) -> dict[tuple[str, str], tuple[str, str]]:
    """{(src_id, dst_id): (verb, why)} from the backbone edges — the single source for an element↔
    element flow step's label/why. First edge for a pair wins (a pair almost always has one)."""
    idx: dict[tuple[str, str], tuple[str, str]] = {}
    for e in cast("list[dict[str, Any]]", graph["edges"]):
        key = (str(e.get("src")), str(e.get("dst")))
        if key not in idx:
            idx[key] = (str(e.get("verb") or ""), str(e.get("why") or ""))
    return idx


def _flow_step_label(idx: dict[tuple[str, str], tuple[str, str]], st: dict[str, Any]) -> str:
    """A flow step's arrow label: the step's OWN authored text (`phrase`) describing the action at this
    point in the scenario. Every step carries one (`coyodex validate` requires it), so this is the normal
    path. The backbone-edge lookup is only a safety net for a legacy step that predates that rule and left
    its text empty — a pair used by several steps can't be described correctly by one shared edge label,
    which is exactly why the step describes itself. The net prefers the edge's descriptive `Why` over its
    terse verb, then falls back to a neutral 'uses'."""
    phrase = str(st.get("phrase") or "").strip()
    if phrase:
        return phrase
    if st.get("subflow"):  # a DEGRADED reference step (unresolved/empty sub-flow — validate blocks
        return f"runs {st['subflow']}"  # it, but serve renders drafts): name the run, never 'uses'
    if st.get("src_is_id") and st.get("dst_is_id"):
        verb, why = idx.get((str(st["src"]), str(st["dst"])), ("", ""))
        if why:
            return why
        if verb:
            return verb
    return "uses"


def expanded_steps(graph: GraphDict, flow: dict[str, Any]) -> list[dict[str, Any]]:
    """The flow's ok-filtered steps with every sub-flow REFERENCE step replaced inline by the
    referenced sub-flow's own ok steps — the ONE expansion all three per-flow views (mermaid,
    narrative, actors) consume, so `message[i] ↔ FLOWS_NARR[uc][i] ↔ actor stepIdx` stays a single
    index space. Expanded steps carry `sf`/`sfName` (+ `sfFirst` on the run's first step) so the
    frontend renders the grouping FROM the entries — no header rows, every entry is message-backed.
    An unresolved reference or an empty sub-flow (validate blocks both, but serve renders drafts)
    degrades to the bare reference step, so nothing disappears silently."""
    sfs = {str(sf.get("id")): sf for sf in cast("list[dict[str, Any]]", graph.get("subflows") or [])}
    out: list[dict[str, Any]] = []
    for st in cast("list[dict[str, Any]]", flow.get("steps") or []):
        if not st.get("ok"):
            continue
        sf = sfs.get(str(st.get("subflow") or ""))
        inner = [s for s in cast("list[dict[str, Any]]", (sf or {}).get("steps") or []) if s.get("ok")]
        if sf is None or not inner:
            out.append(st)
            continue
        for k, s in enumerate(inner):
            e = dict(s)
            e["sf"] = str(sf["id"])
            e["sfName"] = str(sf.get("name") or sf["id"])
            e["sfFirst"] = k == 0
            out.append(e)
    return out


def gen_flow_mermaid(graph: GraphDict, flow: dict[str, Any]) -> str:
    """One use case's flow as a Mermaid sequenceDiagram: the actor + the touched components/deps/
    entities as lifelines (first-appearance order), each step an ordered message. An element lifeline's
    participant id IS its node id, so the viewer's id→node bridge resolves a click to its panel.
    A sub-flow's expanded run is wrapped in a tinted `rect` named by a `Note` — notes render as
    `.noteText`, never `.messageText`, so the positional message↔narrative pairing is untouched."""
    idx = _edge_index(graph)
    steps = expanded_steps(graph, flow)
    pid: dict[str, str] = {}     # raw endpoint token -> Mermaid participant id
    decls: list[str] = []
    n_actor = 0

    def ensure(token: str, is_id: bool) -> None:
        nonlocal n_actor
        if token in pid:
            return
        if is_id:                                  # an element endpoint: a real node -> its name; an
            # unknown id (the validator blocks the build on it) -> the raw id, still a participant, so a
            # missing element never mis-reads as a person.
            label = _safe_msg(str(graph["nodes"][token]["name"])) if token in graph["nodes"] else token
            pid[token] = token
            decls.append(f"  participant {token} as {label}")
        else:                                      # a Role name (actor step) — no node behind it
            aid = "FA" + str(n_actor)
            n_actor += 1
            pid[token] = aid
            decls.append(f"  actor {aid} as {_safe_msg(token)}")

    for st in steps:
        ensure(str(st["src"]), bool(st.get("src_is_id")))
        ensure(str(st["dst"]), bool(st.get("dst_is_id")))
    lines = ["sequenceDiagram"] + decls
    # Prefix each arrow with its 1-based position so the diagram is self-numbered — the same number the
    # side-panel narrative shows (a plain <ol>) and the step player's "Step n / N" counter uses. The index
    # is over this same expanded, ok-filtered list, so message n <-> FLOWS_NARR[uc][n-1] <-> panel item n
    # line up. A sub-flow run opens a rect (+ its naming Note) and closes it when the run ends.
    open_sf: str | None = None
    for i, st in enumerate(steps):
        sf = cast("str | None", st.get("sf"))
        if sf != open_sf or (sf is not None and st.get("sfFirst") and i > 0 and steps[i - 1].get("sf") == sf):
            if open_sf is not None:
                lines.append("  end")
            if sf is not None:
                lines.append("  rect rgb(238, 242, 255)")
                lines.append(f"  Note over {pid[str(st['src'])]}: ⟨{_safe_msg(str(st.get('sfName') or sf))}⟩")
            open_sf = sf
        lines.append(f"  {pid[str(st['src'])]}->>{pid[str(st['dst'])]}: {i + 1}. {_safe_msg(_flow_step_label(idx, st))}")
    if open_sf is not None:
        lines.append("  end")
    return "\n".join(lines)


def flow_narrative(graph: GraphDict, flow: dict[str, Any]) -> list[dict[str, Any]]:
    """The readable numbered steps for the side panel — the SAME source as gen_flow_mermaid. Each step
    carries its from/to display names + (clickable) node ids, its own action text, and any note. The panel
    describes the step from the step alone — it does NOT pull the shared backbone-edge description, since
    a pair used by several steps has one edge label that can't be right for all of them. `why` stays empty
    for a normal step; the edge lookup is only a safety net for a legacy step with no authored text."""
    idx = _edge_index(graph)
    out: list[dict[str, Any]] = []
    for st in expanded_steps(graph, flow):
        src, dst = str(st["src"]), str(st["dst"])
        src_id = src if (st.get("src_is_id") and src in graph["nodes"]) else None
        dst_id = dst if (st.get("dst_is_id") and dst in graph["nodes"]) else None
        phrase = str(st.get("phrase") or "").strip()
        verb, why = phrase, ""
        if not phrase:                             # safety net: a legacy step that left its text empty
            if st.get("subflow"):                  # a degraded reference step — name the run
                verb = f"runs {st['subflow']}"
            elif st.get("src_is_id") and st.get("dst_is_id"):
                v, w = idx.get((src, dst), ("", ""))
                verb, why = (v or "uses"), w
            else:
                verb = "uses"
        out.append({
            "n": st.get("n"),
            "srcId": src_id, "src": str(graph["nodes"][src]["name"]) if src_id else src,
            "dstId": dst_id, "dst": str(graph["nodes"][dst]["name"]) if dst_id else dst,
            "verb": verb, "why": why, "note": str(st.get("note") or "").strip(),
            "where": str(st.get("where") or "") or None,  # the step's own call site (THE location)
            # sub-flow grouping metadata (None/False for a plain step): the frontend renders the
            # group header/indent from these — entries stay 1:1 with mermaid messages
            "sf": st.get("sf"), "sfName": st.get("sfName"), "sfFirst": bool(st.get("sfFirst")),
        })
    return out


def flow_mermaids(graph: GraphDict) -> dict[str, str]:
    """{uc_id: sequenceDiagram} for every T6 flow — the use-case view and the GP-step drill-down both
    look a flow up here by its use case id."""
    return {str(f["uc"]): gen_flow_mermaid(graph, f) for f in graph["flows"]}


def flow_narratives(graph: GraphDict) -> dict[str, list[dict[str, Any]]]:
    """{uc_id: [narrative step, …]} for every T6 flow — the readable companion to flow_mermaids."""
    return {str(f["uc"]): flow_narrative(graph, f) for f in graph["flows"]}


def flow_actors(graph: GraphDict, flow: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-actor (Role) participants in one use-case flow, in the SAME `FAn` alias order gen_flow_mermaid
    assigns them, so the viewer's actor lifeline lines up with its rendered `data-id`. Mirrors hp_actors
    for the Happy Path, scoped to this one flow: each actor links back to its Roles-table entry (kind +
    wants) and lists which of THIS flow's own steps it drives — `stepIdx` indexes the SAME filtered,
    ordered step list flow_narrative returns (== the viewer's FLOWS_NARR[uc]), so the two stay in
    lockstep. A role can drive more than one step (e.g. it also receives the final reply).
    `is_role` mirrors flow_narrative's srcId/dstId predicate exactly (an id absent from the current
    graph reads as a role, not a dangling element) so the two functions never disagree on a step."""
    steps = expanded_steps(graph, flow)  # the SAME index space as flow_narrative / gen_flow_mermaid

    def is_role(tok: str, is_id: bool) -> bool:
        return not (is_id and tok in graph["nodes"])

    roles_by_name = {_safe_msg(r["name"]).strip().lower(): r for r in graph["roles"]}
    order: dict[str, str] = {}  # role display name -> alias (FAn), first-appearance order
    for st in steps:
        for tok, is_id in ((str(st["src"]), bool(st.get("src_is_id"))), (str(st["dst"]), bool(st.get("dst_is_id")))):
            if is_role(tok, is_id):
                order.setdefault(tok, "FA" + str(len(order)))
    out: list[dict[str, Any]] = []
    for name, aid in order.items():
        idxs = [i for i, st in enumerate(steps)
                if (is_role(str(st["src"]), bool(st.get("src_is_id"))) and str(st["src"]) == name)
                or (is_role(str(st["dst"]), bool(st.get("dst_is_id"))) and str(st["dst"]) == name)]
        role = roles_by_name.get(name.strip().lower())
        out.append({
            "aid": aid,
            "name": name,
            "kind": str(role["kind"]) if role else "",
            "wants": str(role["wants"]) if role else "",
            "stepIdx": idxs,
        })
    return out


def flow_actors_map(graph: GraphDict) -> dict[str, list[dict[str, Any]]]:
    """{uc_id: [actor, …]} for every T6 flow — the flow-level companion to hp_actors, one list per flow."""
    return {str(f["uc"]): flow_actors(graph, f) for f in graph["flows"]}


def merged_graph(graph: GraphDict, diff: DiffDict | None) -> dict[str, Any]:
    """Graph + diff annotations (added nodes inserted, change status on nodes) for the panel."""
    g = cast("dict[str, Any]", copy.deepcopy(graph))
    if diff:
        for c in diff["changes"]:
            nid = c["id"]
            if nid in g["nodes"]:
                g["nodes"][nid]["change"] = c["change"]
                if c["note"]:
                    g["nodes"][nid]["fields"]["Change"] = f'{c["change"]} — {c["note"]}'
            elif c["change"] == "added":
                g["nodes"][nid] = {
                    "id": nid,
                    "kind": c["kind"] or "component",
                    "name": c["name"] or nid,
                    "file": None,
                    "line": None,
                    "fields": {"Change": f'added — {c["note"]}'},
                    "change": "added",
                }
    return g


class ViewBundle(TypedDict):
    """All the per-project view data the frontend needs — the graph plus every pre-rendered diagram
    source, edge-crossing list, flow, colour table, and config flag. Built from the model by
    `build_view_bundle` and served as JSON by `coyodex serve` at /p/<slug>/api/view; the frontend
    fetches it and renders.

    Keys are the viewer's own vocabulary (camelCase); the frontend maps them onto its runtime state
    (see viewer.js `applyBundle` — keep the two in step).
    """
    repoRoot: str
    ghRepo: str | None
    ghCommit: str | None
    graph: dict[str, Any]          # the MERGED graph (base+diff, with Context nodes added)
    mermaidBase: str
    mermaidDiff: str
    mermaidContext: str
    mermaidContainer: str
    mermaidBySub: dict[str, str]
    mermaidEdgeCard: dict[str, str]
    containerEdges: dict[str, list[dict[str, str]]]
    mermaidDomain: str
    mermaidDomainContainer: str
    mermaidDomainSub: dict[str, str]
    mermaidDomainEdgeCard: dict[str, str]
    mermaidBridgeCard: dict[str, str]
    bridgeEdges: list[dict[str, str]]
    domainContainerEdges: dict[str, list[dict[str, str]]]
    mermaidDeployment: str
    deploymentCards: dict[str, str]
    deploymentEnvironments: list[str]
    mermaidDeploymentByEnv: dict[str, str]
    hasDeployment: bool
    mermaidHp: str
    flowsMm: dict[str, str]
    flowsNarr: dict[str, list[dict[str, Any]]]
    hpActors: list[dict[str, Any]]
    flowActors: dict[str, list[dict[str, Any]]]
    elementTint: dict[str, dict[str, str]]
    mermaidLibs: str
    foldedLibs: list[dict[str, str]]
    mermaidByBucketFold: dict[str, str]
    foldedBuckets: list[dict[str, Any]]
    contextEdges: dict[str, dict[str, Any]]
    hasDiff: bool
    hasGrouping: bool
    hasDomain: bool
    hasSubdomains: bool
    hasHp: bool
    meta: str                      # the header meta line (HTML)
    diffState: dict[str, str]


def build_view_bundle(graph: GraphDict, report: Path | None, anchor: Path) -> ViewBundle:
    """Compute every derived view artifact for one map — the pure-data core that `coyodex serve`
    exposes at /p/<slug>/api/view for the frontend to fetch and render.

    `anchor` is the directory that source links resolve against (the map's `.coyodex/` folder): the
    repo root + GitHub URL are derived from the git work tree around it, overridable in the viewer's
    Settings. Nothing here touches the output file or the frontend assets, so it is safe to call per
    request. `report` is the optional change-impact overlay; None renders the plain baseline.
    """
    diff = build_diff(report) if report and report.exists() else None
    base_mm = gen_mermaid(graph, None)
    diff_mm = gen_mermaid(graph, diff) if diff else base_mm
    context_mm = gen_context_mermaid(graph)
    context_edges = gen_context_edges(graph)
    state = compute_state(graph, diff)
    # Source-link config, derived from the mapped repo (the anchor dir sits inside its work tree).
    # Seeded into the viewer; the user can override the root / GitHub URL in Settings (localStorage).
    repo_root = repo_root_default(anchor)
    gh_repo = gh_repo_url(anchor)
    gh_commit = graph["commit"]
    # Repo root name in the header — so the map plainly states which repo its file links resolve into.
    repo_name = Path(repo_root).name or repo_root
    repo_tag = f'<strong class="repo" title="{html_escape(repo_root, quote=True)}">{html_escape(repo_name)}</strong> · '
    if diff:
        meta = f"diff: <code>{diff['base']}</code> → <code>{diff['new']}</code> · {len(diff['changes'])} changes"
    else:
        commit = graph['commit'] or 'unknown'
        committed = graph.get('committed')
        meta = f"baseline @ commit <code>{commit}</code>" + (f" from {committed}" if committed else "")
        built = graph.get('built')
        fmt = graph.get('format')
        if built:
            meta += f" · built {html_escape(built)}"
        if fmt:
            meta += f" · schema <code>{html_escape(fmt)}</code>"
    meta = repo_tag + meta
    grouping = has_grouping(graph)
    domain = has_domain(graph)
    subdomains = has_subdomains(graph)
    hp = has_hp(graph)
    deployment = has_deployment(graph)
    mg = merged_graph(graph, diff)
    add_context_nodes(mg, graph)
    if deployment:
        add_deployment_nodes(mg, graph)
    return ViewBundle(
        repoRoot=repo_root, ghRepo=gh_repo, ghCommit=gh_commit,
        graph=mg,
        mermaidBase=base_mm, mermaidDiff=diff_mm, mermaidContext=context_mm,
        mermaidContainer=gen_container_mermaid(graph) if grouping else "",
        mermaidBySub=subsystem_component_mermaids(graph) if grouping else {},
        mermaidEdgeCard=edge_card_mermaids(graph) if grouping else {},
        containerEdges=gen_container_edges(graph) if grouping else {},
        mermaidDomain=gen_domain_mermaid(graph) if domain else "",
        mermaidDomainContainer=gen_domain_container_mermaid(graph) if subdomains else "",
        mermaidDomainSub=domain_subdomain_mermaids(graph) if subdomains else {},
        mermaidDomainEdgeCard=domain_edge_card_mermaids(graph) if subdomains else {},
        mermaidBridgeCard=bridge_card_mermaids(graph) if (grouping and subdomains) else {},
        bridgeEdges=gen_bridge_edges(graph) if (grouping and subdomains) else [],
        domainContainerEdges=gen_domain_container_edges(graph) if subdomains else {},
        mermaidDeployment=gen_deployment_mermaid(graph) if deployment else "",
        deploymentCards=deployment_cards(graph) if deployment else {},
        deploymentEnvironments=deployment_environments(graph) if deployment else [],
        mermaidDeploymentByEnv=deployment_mermaid_by_env(graph) if deployment else {},
        hasDeployment=deployment,
        mermaidHp=gen_hp_mermaid(graph) if hp else "",
        # Flows are independent of the Happy Path — the use-case view needs them even with no HP — so
        # they come from graph["flows"] directly (empty when the map has no T6 section).
        flowsMm=flow_mermaids(graph),
        flowsNarr=flow_narratives(graph),
        hpActors=hp_actors(graph) if hp else [],
        flowActors=flow_actors_map(graph),
        elementTint=ELEMENT_TINT,
        mermaidLibs=gen_libs_mermaid(graph),
        foldedLibs=folded_libs(graph),
        mermaidByBucketFold=mermaid_by_bucketfold(graph),
        foldedBuckets=folded_buckets_roster(graph),
        contextEdges=context_edges,
        hasDiff=diff is not None,
        hasGrouping=grouping, hasDomain=domain, hasSubdomains=subdomains, hasHp=hp,
        meta=meta, diffState=state,
    )


def main(argv: list[str] | None = None) -> int:
    """Two-stage debug entry: dump the view bundle (the JSON the frontend fetches) for a graph.json.

        python -m coyodex.viewer.gen_viewer [graph.json] [view-bundle.json] [report.md]
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    src = Path(argv[0] if len(argv) > 0 else "build/graph.json")
    out = Path(argv[1] if len(argv) > 1 else "build/view-bundle.json")
    report = Path(argv[2]) if len(argv) > 2 else None
    if not src.exists():
        print(f"ERROR: {src} not found (build the graph first)", file=sys.stderr)
        return 1
    graph = cast(GraphDict, json.loads(src.read_text(encoding="utf-8")))
    bundle = build_view_bundle(graph, report, out.resolve().parent)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    print(f"Wrote view bundle -> {out}  (diff: {'yes' if report and report.exists() else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
