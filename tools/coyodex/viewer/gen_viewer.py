#!/usr/bin/env python3
"""Generate a self-contained HTML viewer from a parsed graph.

Reads a graph.json (from build_graph.py) and (optionally) a change-impact report; emits a single
HTML file with the graph inlined and Mermaid + svg-pan-zoom loaded from a pinned CDN with SRI.
The viewer's own CSS/JS are authored in viewer.css / viewer.js next to this module and inlined at
build time, so the emitted HTML stays standalone — it carries no path back to this repo (see the
"Generated artifacts are standalone w.r.t. the coyodex repo" design note).
The viewer offers four altitudes — Context (C4; external SYSTEMS drawn by name, while in-process
framework/library deps fold into one ⌘-clickable "Libraries" box that drills to the full list) →
Subsystems (click a box to select it + its linked
subsystems, or ⌘-click to drill in; click an arrow to select it — the side panel lists every
component edge it bundles — or ⌘-click to drill into the pair's edge card; while ⌘ is held, drillable
boxes/arrows show a drill-in cursor) → Components → code links — navigated as a
back/forward history within one frame, wraps Mermaid's SVG with pan/zoom and a click->side-panel
bridge, and a baseline<->diff toggle that recolors added/modified/deleted nodes and the elements they
ripple to.

Node labels are the element name only (no ID prefix) to keep them uncluttered;
the ID still appears in the panel header and drives the bridge via the cy-<ID>
class.

Normally driven in-process by `coyodex render`. For two-stage debugging:
    python -m coyodex.viewer.gen_viewer [graph.json] [out.html] [report.md]
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from html import escape as html_escape
from pathlib import Path
from typing import Any, cast

from coyodex.viewer.build_graph import DiffDict, GraphDict, build_diff
from coyodex.viewer.filetree import FileTreeNode, build_file_tree  # repo file tree + map-coverage overlay (browser pane)
from coyodex.schema_v1 import DEP_KINDS_FOLDED  # external-dep Kind vocabulary (Context fold rule)

_ASSETS = Path(__file__).resolve().parent  # viewer.css/js live here; inlined into the HTML at build time

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
# Golden-Path step view also draws entities (rounded box) alongside components/deps.
GP_SHAPE = {**SHAPE, "entity": ('("', '")')}
GP_STEP_KINDS = ("component", "dep", "entity")

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
    lines.append("  classDef dep fill:#ecfdf5,stroke:#065f46,color:#064e3b;")
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
    """Arrow label — a REAL field name only (an invented relationship verb isn't grounded in code).
    The backing field is resolved once in build_graph (`fk_field` / `fk_side`); here we only format it:
    forward (field on the source / arrow-tail) -> the field name (`subscription`, `org_id`);
    reverse (FK on the target / arrow-head) -> `↩ field` (`↩ org_id`);
    blank when no field backs the relation (the `{how}` note then explains it in the click-panel)."""
    field = edge.get("fk_field")
    if not field:
        return ""
    label = _safe_label(str(field))
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
        return f"  {s} {arrow} {d}{suffix}"
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
    for e in graph["edges"]:
        if e.get("kind") and str(e["src"]) in ent_ids and str(e["dst"]) in ent_ids:
            lines.append(_class_relation_line(cast("dict[str, Any]", e)))
    return "\n".join(lines)


# Group-box palettes, defined once and reused as a flowchart `classDef` and as a classDiagram `style`
# (Mermaid's classDiagram has no classDef-by-name, so collapsed boxes there are styled per-id). Amber =
# the structural family (subsystem `S` boxes); magenta = the domain family (subdomain `SD` boxes). A
# subsystem and a subdomain therefore read identically wherever they appear — overview, subsystem card,
# or subdomain card — so the two altitudes never blur.
SUBSYSTEM_STYLE = "fill:#fef3c7,stroke:#b45309,color:#7c2d12"
SUBDOMAIN_STYLE = "fill:#fdf4ff,stroke:#86198f,color:#581c87"
COMPONENT_STYLE = "fill:#eef2ff,stroke:#3730a3,color:#1e1b4b"  # indigo — component (C) boxes
DOMAIN_SUBDOMAIN_CLASSDEF = f"  classDef subdomain {SUBDOMAIN_STYLE};"

# The bridge verb split (C→E edges): a component that `persists`/`writes` an entity OWNS that
# subdomain's data; any other verb (typically `reads`) merely CONSUMES it. Drives the subsystem-card
# bridge arrow label, surfacing a subdomain that many subsystems own/read as a shared kernel.
_OWN_VERBS = {"persists", "writes"}


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
        } for e in edges]
    return out


def _subdomain_namespace(graph: GraphDict, sdid: str,
                         members: list[tuple[str, str]]) -> list[str]:
    """`classDiagram` lines framing a subdomain's entities as `namespace <sdid>["Name (N)"] { … }` —
    each member entity drawn full (attributes). The classDiagram analog of `_component_subgraph`:
    a subdomain always reads as a labelled frame (Mermaid 11 namespaces render as a titled cluster,
    DOM-id `cluster-<sdid>`, with the inner class group ids unchanged so the id bridge still resolves).
    Shared by the subdomain card and the domain edge card."""
    nodes = graph["nodes"]
    ent_names = {nid: str(n["name"]) for nid, n in nodes.items() if str(n["kind"]) == "entity"}
    nm = _safe_label(str(nodes[sdid]["name"])) if sdid in nodes else sdid
    out = [f'namespace {sdid}["{nm} ({len(members)})"] {{']
    for eid, _ in members:
        out += _class_box_lines(eid, cast("dict[str, Any]", nodes[eid]), ent_names, with_members=True)
    for cid, cname in _child_subdomains(graph, sdid):  # nested child subdomains: collapsed, drillable
        out.append(f'  class {cid}["{_safe_label(cname)} ({_descendant_entity_count(graph, cid)})"]')
    out.append("}")
    return out


def _subsystem_bridge_lines(graph: GraphDict, member_ids: set[str]) -> list[str]:
    """`classDiagram` lines for the reverse structure↔domain bridge over `member_ids`: every subsystem
    whose components own/read one of those entities, drawn as a collapsed (amber) box with an owns/reads
    arrow into the entity. The mirror of the subsystem card's subdomain bridge; shared by the subdomain
    card and the domain edge card. owns = persists/writes, reads = anything else."""
    nodes = graph["nodes"]
    bridges: set[tuple[str, str, str]] = set()  # (subsystem box, member entity, 'owns'|'reads')
    nb_subs: set[str] = set()
    for e in graph["edges"]:
        s, d = str(e["src"]), str(e["dst"])
        if d in member_ids and str(nodes.get(s, {}).get("kind")) == "component":
            sub = _top_subsystem(graph, s)
            if sub:
                nb_subs.add(sub)
                bridges.add((sub, d, "owns" if str(e["verb"]).lower() in _OWN_VERBS else "reads"))
    out: list[str] = []
    for sub in sorted(nb_subs):  # collapsed neighbour-subsystem boxes (amber, like a subsystem anywhere)
        out.append(f'  class {sub}["{_safe_label(str(nodes[sub]["name"]))}"]')
        out.append(f"  style {sub} {SUBSYSTEM_STYLE}")
    for sub, ent, rel in sorted(bridges):  # bridge arrows: subsystem -> entity (owns / reads)
        out.append(f"  {sub} --> {ent} : {rel}")
    return out


def gen_domain_subdomain_card(graph: GraphDict, sdid: str) -> str:
    """A per-subdomain `classDiagram` neighbourhood: `sdid` framed as a `namespace` holding its own
    entities (full attributes), every OTHER subdomain its entities relate to drawn as a collapsed
    member-less box (one per neighbour subdomain, labelled `Name (N)`), the focal subdomain's internal
    relations drawn in full, and one arrow per (focal entity, neighbour subdomain) crossing pair. It
    ALSO draws the structure↔domain bridge in reverse: every subsystem whose components own/read one of
    these entities is drawn as a collapsed (amber) box with a `owns`/`reads` arrow into that entity —
    the mirror of the subsystem card's subdomain bridge. The entity analog of gen_subsystem_card_mermaid
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
    cross: set[tuple[str, str]] = set()   # focal box ↔ a neighbour-subdomain box (direction kept)
    childcross: set[tuple[str, str]] = set()  # aggregated arrows touching a nested child-subdomain box
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
                childcross.add((bs, bd))               # a child-subdomain box is involved -> aggregated
        elif bs is not None:                           # outbound crossing to outside sdid
            nb = _sibling_subdomain_box(graph, d, sdid)
            if nb and nb != sdid:
                cross.add((bs, nb))
                nb_sds.add(nb)
        elif bd is not None:                           # inbound crossing from outside sdid
            nb = _sibling_subdomain_box(graph, s, sdid)
            if nb and nb != sdid:
                cross.add((nb, bd))
                nb_sds.add(nb)
    lines = ["classDiagram", *_subdomain_namespace(graph, sdid, members)]
    for cid in sorted(child_sd_ids):  # style the nested child-subdomain boxes (declared inside the namespace)
        lines.append(f"  style {cid} {SUBDOMAIN_STYLE}")
    for nb in sorted(nb_sds):  # collapsed neighbour-subdomain boxes (member-less, count-labelled)
        n_ent = _descendant_entity_count(graph, nb)
        lines.append(f'  class {nb}["{_safe_label(str(nodes[nb]["name"]))} ({n_ent})"]')
        lines.append(f"  style {nb} {SUBDOMAIN_STYLE}")  # magenta — same as a subdomain box anywhere else
    lines += _subsystem_bridge_lines(graph, member_ids)  # reverse structure↔domain bridge over DIRECT members
    for e in internal:  # the focal subdomain's own relations, full
        lines.append(_class_relation_line(e))
    for src, dst in sorted(cross):  # crossing arrows to/from collapsed neighbour boxes (click → edge card)
        lines.append(f"  {src} --> {dst}")
    for src, dst in sorted(childcross):  # nested child-subdomain arrows (aggregated; box drills in)
        lines.append(f"  {src} --> {dst}")
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
    agg: set[tuple[str, str]] = set()
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
                agg.add((str(ba), str(bb)))
    for src, dst in sorted(agg):
        lines.append(f"  {src} --> {dst}")
    return "\n".join(lines)


def domain_edge_card_mermaids(graph: GraphDict) -> dict[str, str]:
    """One edge-card per disjoint subdomain pair with a crossing relation — at every drill level, not
    only top-level — keyed 'A>B' to match the rendered arrow's endpoints. The entity analog of
    edge_card_mermaids, built from the one _domain_edge_card_pairs source."""
    return {f"{a}>{b}": gen_domain_edge_card(graph, a, b) for (a, b) in sorted(_domain_edge_card_pairs(graph))}


def gen_bridge_card_mermaid(graph: GraphDict, sid: str, sdid: str) -> str:
    """Bridge card: subsystem `sid` and subdomain `sdid` framed side by side — the structure↔domain
    relationship — with every component→entity owns/reads edge between them drawn in full. The analog of
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
    # owns/reads C→E edges crossing sid's subtree -> sdid's subtree, bucketed to each frame's immediate
    # children: a direct member->direct entity edge stays labelled (resolves to the real edge); a
    # crossing into a child group is an aggregated arrow.
    bridges: set[tuple[str, str, str]] = set()
    for e in graph["edges"]:
        s, d = str(e["src"]), str(e["dst"])
        if str(nodes.get(s, {}).get("kind")) != "component" or str(nodes.get(d, {}).get("kind")) != "entity":
            continue
        if _in_subtree(graph, s, sid) and _in_subtree(graph, d, sdid):
            rel = "owns" if str(e["verb"]).lower() in _OWN_VERBS else "reads"
            bridges.add((str(_child_under(graph, s, sid)), str(_child_under(graph, d, sdid)), rel))
    for bs, bd, rel in sorted(bridges):
        lines.append(f"  {bs} --> {bd} : {rel}")
    return "\n".join(lines)


def bridge_card_mermaids(graph: GraphDict) -> dict[str, str]:
    """One bridge card per (subsystem-ancestor, subdomain-ancestor) pair joined by a C→E owns/reads edge
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
        } for e in edges]
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
    unlabelled arrow per (component, neighbour) pair (Q2-style aggregation, no count). A component
    inside the frame points to the neighbour box (outbound) or is pointed at by it (inbound). The
    viewer turns a click on such an arrow into the matching edge card, and a click on a neighbour
    box into that subsystem's own card. When the subsystem's components touch the domain model
    (`C→E` edges), the subdomains they own/read are also drawn as collapsed boxes — the bridge between
    the structural and domain groupings (owns = persists/writes, reads = anything else)."""
    members = {cid for cid, _ in _components_of(graph, sid)}   # direct component members (drawn nodes)
    deps: set[str] = set()
    neighbours: set[str] = set()
    cross: set[tuple[str, str]] = set()       # drawn-box -> neighbour-subsystem box (or reverse), unlabelled
    childcross: set[tuple[str, str]] = set()  # aggregated arrows touching a nested child-subsystem box
    bridges: set[tuple[str, str, str]] = set()  # (drawn box, subdomain box, 'owns'|'reads')
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
                    bridges.add((s, sd, "owns" if str(e["verb"]).lower() in _OWN_VERBS else "reads"))
            continue
        if ks == "entity":
            continue
        if bs is not None and bd is not None:            # both inside sid's subtree
            if not (bs == s and bd == d) and bs != bd:   # a child-subsystem box is involved -> aggregated
                childcross.add((bs, bd))
            continue                                     # two direct members -> labelled (via keep) below
        if bs is not None:                               # outbound crossing to outside sid
            nb = _sibling_level_box(graph, d, sid)
            if nb and nb != sid:
                neighbours.add(nb)
                cross.add((bs, nb))
            continue
        if bd is not None:                               # inbound crossing from outside sid
            nb = _sibling_level_box(graph, s, sid)
            if nb and nb != sid:
                neighbours.add(nb)
                cross.add((nb, bd))
    keep = members | deps  # the set whose internal (labelled) edges are drawn
    lines = ["flowchart TB", *_component_subgraph(graph, sid)]
    for nb in sorted(neighbours):  # collapsed neighbour-subsystem boxes
        lines.append(f'  {nb}["{_safe_label(str(graph["nodes"][nb]["name"]))}"]:::cy-{nb}')
        lines.append(f"  class {nb} subsystem")
    open_b, close_b = SHAPE["dep"]
    for did in sorted(deps):  # deps belong to no subsystem — draw them outside the frame
        lines.append(f'  {did}{open_b}{_safe_label(str(graph["nodes"][did]["name"]))}{close_b}:::cy-{did}')
        lines.append(f"  class {did} dep")
    bridge_sd = {sd for _, sd, _ in bridges}
    for sd in sorted(bridge_sd):  # collapsed subdomain boxes the subsystem's data bridges to
        lines.append(f'  {sd}["{_safe_label(str(graph["nodes"][sd]["name"]))}"]:::cy-{sd}')
        lines.append(f"  class {sd} subdomain")
    for src, verb, dst in _diagram_edges(graph, None, keep):  # internal + dep edges (labelled)
        lines.append(f"  {src} -->|{verb}| {dst}")
    for src, dst in sorted(cross):  # neighbourhood arrows (unlabelled; click -> edge card)
        lines.append(f"  {src} --> {dst}")
    for src, dst in sorted(childcross):  # nested child-subsystem arrows (aggregated; box drills in)
        lines.append(f"  {src} --> {dst}")
    for src, sd, rel in sorted(bridges):  # bridge arrows: member -> subdomain (owns / reads)
        lines.append(f"  {src} -->|{rel}| {sd}")
    lines.append(f"  classDef component {COMPONENT_STYLE};")
    lines.append("  classDef dep fill:#ecfdf5,stroke:#065f46,color:#064e3b;")
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
    agg: set[tuple[str, str]] = set()
    for e in graph["edges"]:  # the a->b crossings, bucketed to each frame's immediate children
        s, d = str(e["src"]), str(e["dst"])
        if not (_in_subtree(graph, s, a) and _in_subtree(graph, d, b)):
            continue
        ba, bb = _child_under(graph, s, a), _child_under(graph, d, b)
        if ba == s and bb == d:                      # both direct members -> labelled (resolves to the edge)
            lines.append(f"  {s} -->|{e['verb']}| {d}")
        else:                                        # reaches into a child subsystem -> aggregated box arrow
            agg.add((str(ba), str(bb)))
    for src, dst in sorted(agg):
        lines.append(f"  {src} --> {dst}")
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


def folded_libs(graph: GraphDict) -> list[dict[str, str]]:
    """(id, name, type) for the deps folded into the Context 'Libraries' box — those whose Kind is an
    in-process one (framework / library). The C4 Context view shows external SYSTEMS by name and
    collapses these, since libraries are an implementation concern, not a system the project talks to."""
    out: list[dict[str, str]] = []
    for nid, node in graph["nodes"].items():
        if str(node["kind"]) == "dep" and _dep_kind(node) in DEP_KINDS_FOLDED:
            out.append({"id": nid, "name": str(node["name"]), "type": _field_ci(node, "type")})
    return out


def _context_dep_lines(deps: list[tuple[str, str]]) -> list[str]:
    """Mermaid lines drawing each (id, name) dep as a cylinder the System `uses`. Shared by the
    Context view (external systems only) and the Libraries drill-down (the folded libs)."""
    lines: list[str] = []
    for nid, name in deps:
        lines.append(f'  SYS -->|uses| {nid}[("{_safe_label(name)}")]:::cy-{nid}')
        lines.append(f"  class {nid} dep")
    return lines


def _context_head(graph: GraphDict) -> list[str]:
    """The System node + actor lifelines — the part of the Context view shared with its drill-downs."""
    title = _safe_label(graph["title"] or "System")
    lines = ["flowchart TB", f'  SYS["{title}"]:::cy-SYS', "  class SYS system"]
    for i, r in enumerate(graph["roles"]):
        rid = "R" + str(i)
        label = _safe_label(r["name"])
        if r["kind"] == "service":
            lines.append(f'  {rid}{{{{"{label}"}}}}:::cy-{rid}')   # hexagon = service actor
            lines.append(f"  class {rid} svc")
        else:
            lines.append(f'  {rid}(["{label}"]):::cy-{rid}')        # stadium = human actor
            lines.append(f"  class {rid} human")
        lines.append(f"  {rid} -->|uses| SYS")
    return lines


CONTEXT_CLASSDEFS = [
    "  classDef system fill:#1e1b4b,stroke:#312e81,color:#fff;",
    "  classDef human fill:#fff7ed,stroke:#c2410c,color:#7c2d12;",
    "  classDef svc fill:#eef2ff,stroke:#4338ca,color:#312e81;",
    "  classDef dep fill:#ecfdf5,stroke:#065f46,color:#064e3b;",
    "  classDef libs fill:#f1f5f9,stroke:#475569,color:#1e293b;",
]


def gen_context_mermaid(graph: GraphDict) -> str:
    """C4 Context: the system as one node, actors (Roles) using it, and the EXTERNAL SYSTEMS it relies
    on drawn by name (datastore / messaging / service / platform). In-process deps (framework /
    library) are collapsed into one `📚 Libraries (N)` box — drillable in the viewer — so the highest
    altitude stays a clean C4 picture instead of a star of every imported library."""
    lines = _context_head(graph)
    shown = [(nid, str(node["name"])) for nid, node in graph["nodes"].items()
             if str(node["kind"]) == "dep" and _dep_kind(node) not in DEP_KINDS_FOLDED]
    lines += _context_dep_lines(shown)
    n_folded = len(folded_libs(graph))
    if n_folded:
        lines.append(f'  {LIBS_ID}["📚 Libraries ({n_folded})"]:::cy-{LIBS_ID}')
        lines.append(f"  class {LIBS_ID} libs")
        lines.append(f"  SYS -->|bundles| {LIBS_ID}")
    lines += CONTEXT_CLASSDEFS
    return "\n".join(lines)


def gen_libs_mermaid(graph: GraphDict) -> str:
    """The Libraries drill-down (reached by drilling the Context 'Libraries' box): the System with
    every folded in-process dep drawn by name. Same `SYS -->|uses| <id>` shape as the Context view, so
    the viewer's context-edge bridge resolves each arrow to its 'Used for' detail and each box to its
    panel. Empty string when nothing is folded (the box — hence this view — never appears)."""
    libs = folded_libs(graph)
    if not libs:
        return ""
    lines = _context_head(graph)
    lines += _context_dep_lines([(d["id"], d["name"]) for d in libs])
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
    return ce


def has_gp(graph: GraphDict) -> bool:
    return bool(graph["gp"])


def _safe_msg(s: str) -> str:
    """Sanitize text for a Mermaid sequenceDiagram message / participant label: strip markdown links
    and emphasis, drop the chars that break sequence parsing (`;#<>` + newlines), collapse runs of
    whitespace. Colons are kept (only the FIRST colon delimits a message)."""
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)   # md link -> its text
    s = re.sub(r"[`*]", "", s)
    s = s.replace("\n", " ").replace(";", ",").replace("#", "").replace("<", "(").replace(">", ")")
    return re.sub(r"\s+", " ", s).strip()


def _gp_actor(graph: GraphDict, step: dict[str, Any]) -> str:
    """The actor that drives a GP step. An explicit `Actor:` line wins (the only reliable signal when
    a step bundles several UCs with different actors); otherwise fall back to the `Actor` cell of the
    step's FIRST use case, then to a generic 'Actor'."""
    explicit = step.get("actor")
    if isinstance(explicit, str) and explicit.strip():
        return _safe_msg(explicit)
    uc = step.get("uc")
    node = graph["nodes"].get(uc) if isinstance(uc, str) else None
    if node:
        for k, v in cast("dict[str, str]", node.get("fields") or {}).items():
            if k.strip().lower() == "actor" and str(v).strip():
                return _safe_msg(str(v))
    return "Actor"


def gen_gp_mermaid(graph: GraphDict) -> str:
    """C4 behavioural overlay, Level 1: the Golden Path as a black-box sequenceDiagram — each step a
    message from its actor to the System, in order. Labels carry the step TITLE only (no `GPn` id —
    that clutters the spine); the viewer pairs message[i] with step[i] by order instead. Distinct
    actors (derived per step from its UC) become the lifelines."""
    steps = cast("list[dict[str, Any]]", graph["gp"])
    title = _safe_msg(graph["title"] or "System")
    actor_ids: dict[str, str] = {}  # actor name -> stable participant id, in first-appearance order
    for st in steps:
        actor_ids.setdefault(_gp_actor(graph, st), "GPA" + str(len(actor_ids)))
    lines = ["sequenceDiagram"]
    for name, aid in actor_ids.items():
        lines.append(f"  actor {aid} as {name}")
    lines.append(f"  participant GPSYS as {title}")
    for st in steps:
        aid = actor_ids[_gp_actor(graph, st)]
        title_txt = _safe_msg(str(st["title"])) if st["title"] else ""
        label = title_txt or str(st["id"])  # title only; id lives in the side panel, not the label
        lines.append(f"  {aid}->>GPSYS: {label}")
    return "\n".join(lines)


def gp_actors(graph: GraphDict) -> list[dict[str, Any]]:
    """Per-actor data for the Golden Path lifelines, in the SAME participant order/ids as
    gen_gp_mermaid (so `GPAn` lines up with the rendered lifeline). Each actor links back to its
    Roles-table entry by name to surface what it wants + its kind, plus the GP steps it drives —
    `stepIdx` are the message positions the viewer highlights when the actor is selected."""
    steps = cast("list[dict[str, Any]]", graph["gp"])
    roles_by_name = {_safe_msg(r["name"]).strip().lower(): r for r in graph["roles"]}
    order: dict[str, str] = {}  # actor name -> participant id, first-appearance order (matches gen_gp_mermaid)
    for st in steps:
        order.setdefault(_gp_actor(graph, st), "GPA" + str(len(order)))
    out: list[dict[str, Any]] = []
    for name, aid in order.items():
        idxs = [i for i, st in enumerate(steps) if _gp_actor(graph, st) == name]
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


def gen_gp_step_mermaid(graph: GraphDict, gp_id: str) -> str:
    """Behavioural overlay, Level 2: the components-used diagram for one GP step — the induced
    subgraph of the C/D/E nodes the step `Touches:`, plus the verbed edges among them. Same node ids
    and `src -->|verb| dst` shape as the Components view, so the viewer's id/edge bridge resolves a
    click to its node panel (-> file:line) or its real edge."""
    step = next((s for s in graph["gp"] if s["id"] == gp_id), None)
    touched = [t for t in cast("list[str]", step["touches"] if step else [])
               if t in graph["nodes"] and str(graph["nodes"][t]["kind"]) in GP_STEP_KINDS]
    ids = set(touched)
    lines = ["flowchart LR"]
    for nid in touched:
        node = graph["nodes"][nid]
        kind = str(node["kind"])
        open_b, close_b = GP_SHAPE.get(kind, SHAPE["component"])
        lines.append(f"  {nid}{open_b}{_safe_label(str(node['name']))}{close_b}:::cy-{nid}")
        lines.append(f"  class {nid} {kind}")
    for src, verb, dst in _diagram_edges(graph, None, ids):
        lines.append(f"  {src} -->|{verb}| {dst}")
    lines.append(f"  classDef component {COMPONENT_STYLE};")
    lines.append("  classDef dep fill:#ecfdf5,stroke:#065f46,color:#064e3b;")
    lines.append("  classDef entity fill:#fdf4ff,stroke:#86198f,color:#581c87;")
    return "\n".join(lines)


def gp_step_mermaids(graph: GraphDict) -> dict[str, str]:
    """One step-detail diagram per GP step, keyed by GP id (see gen_gp_step_mermaid)."""
    return {str(s["id"]): gen_gp_step_mermaid(graph, str(s["id"])) for s in graph["gp"]}


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


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>coyodex viewer</title>
<!-- Inline data-URI favicon (two nodes + an edge, the viewer's palette): gives the page an icon AND
     stops the browser's default /favicon.ico request 404ing. Inline so the HTML stays self-contained. -->
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iNyIgZmlsbD0iIzFlMWI0YiIvPjxsaW5lIHgxPSIxMS41IiB5MT0iMTEuNSIgeDI9IjIwLjUiIHkyPSIyMC41IiBzdHJva2U9IiNjN2QyZmUiIHN0cm9rZS13aWR0aD0iMi4yIiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48Y2lyY2xlIGN4PSIxMCIgY3k9IjEwIiByPSIzLjQiIGZpbGw9IiNhNWI0ZmMiLz48Y2lyY2xlIGN4PSIyMiIgY3k9IjIyIiByPSIzLjQiIGZpbGw9IiNmMGFiZmMiLz48L3N2Zz4=">
<style>
__STYLE__
</style>
<!-- CDN libs pinned to exact versions + Subresource-Integrity (browser rejects a tampered file).
     Mermaid uses its self-contained UMD bundle (exposes window.mermaid) so SRI covers the whole
     library — the ESM build splits into runtime chunks that SRI on the entry would not cover. -->
<script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"
        integrity="sha384-yc/c2Lk1s2V2ir1rxvjo8YyVD9PlOlYTqpNr3Wm1WIuAA30GlDYNx6U5104OiavY"
        crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11.15.0/dist/mermaid.min.js"
        integrity="sha384-yQ4mmBBT+vhTAwjFH0toJXNYJ6O4usWnt6EPIdWwrRvx2V/n5lXuDZQwQFeSFydF"
        crossorigin="anonymous"></script>
</head>
<body>
<header>
  <h1>coyodex viewer</h1>
  <button id="treetoggle" title="Toggle file browser">&#9776; Files</button>
  <span class="meta" id="meta"></span>
  <span id="viewsw">
    <button data-view="context">Context</button>
    <button data-view="gp">Golden Path</button>
    <button data-view="container">Subsystems</button>
    <button data-view="domain">Domain</button>
    <button data-view="component">Components</button>
  </span>
  <span id="nav">
    <button id="navback" title="Back (⌘← / ⌥←)">◀</button>
    <button id="navfwd" title="Forward (⌘→ / ⌥→)">▶</button>
  </span>
  <span id="zoomctl">
    <button id="zoomout" title="Zoom out">−</button>
    <button id="zoomlevel" title="Fit to screen">100%</button>
    <button id="zoomin" title="Zoom in">+</button>
  </span>
  <button id="setbtn" title="Source link settings (editor + repo root)">&#9881;</button>
  <button id="toggle" style="display:none"></button>
</header>
<div class="hint"><span id="crumb"></span></div>
<main>
  <!-- File browser: the mapped repo's real tree, shaded by map coverage. Selecting a graph element
       highlights its file here; clicking a file/folder selects the matching component/subsystem. -->
  <aside id="tree">
    <div id="treehead">
      <span id="treetitle">Files</span>
      <span id="treelegend">
        <span class="tdot tdot-self"></span>mapped
        <span class="tdot tdot-has"></span>partial
        <span class="tdot tdot-none"></span>unmapped
      </span>
    </div>
    <div id="treebody"></div>
  </aside>
  <!-- Drag handle to resize the file browser (width persisted in localStorage). -->
  <div id="treeresizer" title="Drag to resize"></div>
  <div id="stage">
    <div id="diagram"></div>
    <div id="legend"></div>
    <!-- Always-on, informational navigation caption overlaid on the canvas bottom-left (filled in JS).
         Lives over the diagram, not in the header chrome users skip. Not interactive (pointer-events:none). -->
    <div id="drillhint" hidden></div>
  </div>
  <!-- Drag handle to resize the side panel (width persisted in localStorage). -->
  <div id="resizer" title="Drag to resize"></div>
  <aside id="panel"><p class="empty">Click a node or edge to see details.</p></aside>
</main>
<div id="tip"></div>
<div id="modal" class="modal" hidden>
  <div class="modal-card">
    <h2 id="modalTitle">Open source links</h2>
    <p id="modalIntro" class="modal-help"></p>
    <label class="modal-row">Open in
      <select id="setEditor"></select>
    </label>
    <label class="modal-row" id="setCustomRow" hidden>Custom URI
      <input id="setCustom" type="text" placeholder="subl://open?url=file://{abspath}&amp;line={line}">
    </label>
    <label class="modal-row" id="setGhRow" hidden>GitHub repository URL
      <input id="setGhRepo" type="text" placeholder="https://github.com/owner/repo">
    </label>
    <label class="modal-row" id="setRootRow">Repository root <span class="modal-sub">(absolute path on this machine)</span>
      <input id="setRoot" type="text" placeholder="/Users/you/code/your-repo">
    </label>
    <p class="modal-help" id="setHelp">Placeholders: <code>{abspath}</code> <code>{path}</code> <code>{line}</code> <code>{col}</code>.
       The browser cannot pick a folder for you — type or paste the absolute path. Stored only in this browser.</p>
    <p class="modal-help" id="setGhHelp" hidden>Files open on GitHub at this repository, pinned to the map's commit. Stored only in this browser.</p>
    <p id="modalErr" class="modal-err" hidden></p>
    <div class="modal-btns">
      <button id="setCancel" type="button">Cancel</button>
      <button id="setSave" type="button" class="primary">Save</button>
    </div>
  </div>
</div>
<!-- First-run navigation guide: shown once (localStorage), reopened from the canvas hint. -->
<div id="coach" class="modal" hidden>
  <div class="modal-card">
    <h2>Getting around the map</h2>
    <ul class="coach-list">
      <li><b>Select a view</b> in the top bar</li>
      <li><b>Scroll</b> to zoom, <b>drag</b> to move</li>
      <li><b>Click</b> a box or arrow &mdash; shows its details</li>
      <li><b>&#8984;-click</b> (Ctrl-click) &mdash; drills in</li>
    </ul>
    <div class="modal-btns">
      <button id="coachok" type="button" class="primary">Got it</button>
    </div>
  </div>
</div>
<script type="module">
__SCRIPT__
</script>
</body>
</html>
"""


def gen_html(graph: dict[str, Any], base: str, diff_mm: str, context_mm: str,
             context_edges: dict[str, dict[str, Any]], has_diff: bool, meta: str,
             diff_state: dict[str, str], container_mm: str, by_sub: dict[str, str],
             edge_cards: dict[str, str], container_edges: dict[str, list[dict[str, str]]],
             grouping: bool, domain_mm: str, domain: bool,
             domain_container_mm: str, domain_sub: dict[str, str],
             domain_edge_cards: dict[str, str], bridge_cards: dict[str, str],
             domain_container_edges: dict[str, list[dict[str, str]]], subdomains: bool,
             gp_mm: str, gp_steps: dict[str, str], gp_actors_list: list[dict[str, Any]], gp: bool,
             libs_mm: str, folded: list[dict[str, str]],
             repo_root: str, gh_repo: str | None, gh_commit: str | None,
             file_tree: FileTreeNode | None) -> str:
    css = (_ASSETS / "viewer.css").read_text(encoding="utf-8")
    js = (_ASSETS / "viewer.js").read_text(encoding="utf-8")
    return (
        HTML.replace("__STYLE__", css)
        .replace("__SCRIPT__", js)
        .replace("__REPO_ROOT__", json.dumps(repo_root))
        .replace("__GH_REPO__", json.dumps(gh_repo))
        .replace("__GH_COMMIT__", json.dumps(gh_commit))
        .replace("__GRAPH_JSON__", json.dumps(graph))
        .replace("__MERMAID_BASE__", json.dumps(base))
        .replace("__MERMAID_DIFF__", json.dumps(diff_mm))
        .replace("__MERMAID_CONTEXT__", json.dumps(context_mm))
        .replace("__MERMAID_CONTAINER__", json.dumps(container_mm))
        .replace("__MERMAID_BY_SUB__", json.dumps(by_sub))
        .replace("__MERMAID_EDGE_CARD__", json.dumps(edge_cards))
        .replace("__CONTAINER_EDGES__", json.dumps(container_edges))
        .replace("__MERMAID_DOMAIN__", json.dumps(domain_mm))
        .replace("__MERMAID_DOMAIN_CONTAINER__", json.dumps(domain_container_mm))
        .replace("__MERMAID_DOMAIN_SUB__", json.dumps(domain_sub))
        .replace("__MERMAID_DOMAIN_EDGE_CARD__", json.dumps(domain_edge_cards))
        .replace("__MERMAID_BRIDGE_CARD__", json.dumps(bridge_cards))
        .replace("__DOMAIN_CONTAINER_EDGES__", json.dumps(domain_container_edges))
        .replace("__MERMAID_GP__", json.dumps(gp_mm))
        .replace("__MERMAID_GP_STEP__", json.dumps(gp_steps))
        .replace("__GP_ACTORS__", json.dumps(gp_actors_list))
        .replace("__MERMAID_LIBS__", json.dumps(libs_mm))
        .replace("__FOLDED_LIBS__", json.dumps(folded))
        .replace("__CONTEXT_EDGES__", json.dumps(context_edges))
        .replace("__HAS_DIFF__", "true" if has_diff else "false")
        .replace("__HAS_GROUPING__", "true" if grouping else "false")
        .replace("__HAS_DOMAIN__", "true" if domain else "false")
        .replace("__HAS_SUBDOMAINS__", "true" if subdomains else "false")
        .replace("__HAS_GP__", "true" if gp else "false")
        .replace("__META__", json.dumps(meta))
        .replace("__DIFF_STATE__", json.dumps(diff_state))
        .replace("__FILE_TREE__", json.dumps(file_tree))
    )


def write_html(graph: GraphDict, out: Path, report: Path | None = None) -> None:
    """Render a parsed graph (+ optional change-impact report) to a standalone HTML viewer file.

    The in-process entry point used by `coyodex render`; `main()` is the thin file-based wrapper.
    """
    diff = build_diff(report) if report and report.exists() else None
    base_mm = gen_mermaid(graph, None)
    diff_mm = gen_mermaid(graph, diff) if diff else base_mm
    context_mm = gen_context_mermaid(graph)
    context_edges = gen_context_edges(graph)
    state = compute_state(graph, diff)
    # Source-link config, derived at build time from the mapped repo (the output dir anchors it).
    # Seeded into the viewer; the user can override the root / GitHub URL in Settings (localStorage).
    anchor = out.resolve().parent
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
    meta = repo_tag + meta
    grouping = has_grouping(graph)
    container_mm = gen_container_mermaid(graph) if grouping else ""
    by_sub = subsystem_component_mermaids(graph) if grouping else {}
    edge_cards = edge_card_mermaids(graph) if grouping else {}
    container_edges = gen_container_edges(graph) if grouping else {}
    domain = has_domain(graph)
    domain_mm = gen_domain_mermaid(graph) if domain else ""
    subdomains = has_subdomains(graph)
    domain_container_mm = gen_domain_container_mermaid(graph) if subdomains else ""
    domain_sub = domain_subdomain_mermaids(graph) if subdomains else {}
    domain_edge_cards = domain_edge_card_mermaids(graph) if subdomains else {}
    bridge_cards = bridge_card_mermaids(graph) if (grouping and subdomains) else {}
    domain_container_edges = gen_domain_container_edges(graph) if subdomains else {}
    gp = has_gp(graph)
    gp_mm = gen_gp_mermaid(graph) if gp else ""
    gp_steps = gp_step_mermaids(graph) if gp else {}
    gp_actors_list = gp_actors(graph) if gp else []
    libs_mm = gen_libs_mermaid(graph)
    folded = folded_libs(graph)
    # File-browser pane: the mapped repo's real tree (rooted at the same repo_root the source links
    # resolve against) overlaid with map coverage. None when repo_root isn't a walkable repo.
    file_tree = build_file_tree(graph, repo_root)
    mg = merged_graph(graph, diff)
    add_context_nodes(mg, graph)
    html = gen_html(mg, base_mm, diff_mm, context_mm, context_edges, diff is not None, meta, state,
                    container_mm, by_sub, edge_cards, container_edges, grouping, domain_mm, domain,
                    domain_container_mm, domain_sub, domain_edge_cards, bridge_cards, domain_container_edges, subdomains,
                    gp_mm, gp_steps, gp_actors_list, gp, libs_mm, folded, repo_root, gh_repo, gh_commit, file_tree)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    src = Path(argv[0] if len(argv) > 0 else "build/graph.json")
    out = Path(argv[1] if len(argv) > 1 else "build/project-map.html")
    report = Path(argv[2]) if len(argv) > 2 else None
    if not src.exists():
        print(f"ERROR: {src} not found (build the graph first)", file=sys.stderr)
        return 1
    graph = cast(GraphDict, json.loads(src.read_text(encoding="utf-8")))
    write_html(graph, out, report)
    print(f"Wrote viewer -> {out}  (diff: {'yes' if report and report.exists() else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
