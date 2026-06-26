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

Usage:  python3 gen_viewer.py [build/graph.json] [build/project-map.html] [report.md]
"""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from build_graph import DiffDict, GraphDict, build_diff
from schema_v1 import DEP_KINDS_FOLDED  # external-dep Kind vocabulary (Context fold rule)

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
    lines.append("  classDef component fill:#eef2ff,stroke:#3730a3,color:#1e1b4b;")
    lines.append("  classDef dep fill:#ecfdf5,stroke:#065f46,color:#064e3b;")
    return "\n".join(lines)


def _parent_of(graph: GraphDict, nid: str) -> str | None:
    n = graph["nodes"].get(nid)
    return cast("str | None", n.get("parent")) if n else None


def _top_subsystem(graph: GraphDict, nid: str) -> str | None:
    """Walk parent pointers up to the top-level subsystem above `nid` (or None)."""
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


def has_grouping(graph: GraphDict) -> bool:
    return any(str(n.get("kind")) == "subsystem" for n in graph["nodes"].values())


def has_domain(graph: GraphDict) -> bool:
    return any(str(n.get("kind")) == "entity" for n in graph["nodes"].values())


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


def gen_domain_mermaid(graph: GraphDict) -> str:
    """C4 Code altitude: the T5 domain model as a Mermaid `classDiagram` — each entity a class box
    (id = its `E` id, label = its name) holding its attributes (`type name`), with typed, cardinal
    relations between entities. Markers (PK/FK/…) live in the click->panel, since classDiagram boxes
    carry no native key notation. Class id = the `E` id so the viewer's id bridge resolves a click."""
    ents = [(nid, n) for nid, n in graph["nodes"].items() if str(n["kind"]) == "entity"]
    ent_ids = {nid for nid, _ in ents}
    ent_names = {nid: str(n["name"]) for nid, n in ents}
    lines = ["classDiagram"]
    for nid, n in ents:
        lines.append(f'  class {nid}["{_safe_label(str(n["name"]))}"] {{')
        for a in cast("list[dict[str, str]]", n.get("attrs") or []):
            # an embedded-entity-id type (`mode:E10`) renders with the entity's NAME, not its id
            atype = _safe_member(ent_names.get(str(a.get("type", "")), str(a.get("type", ""))))
            # `[]` is part of the type's SHAPE (it makes the field multi-valued), so show it in the box
            # — unlike PK/FK/?/unique (annotations), which stay in the click-panel. Otherwise a
            # collection reads as single-valued in the box and the `*` lives only on the relation arrow.
            if "[]" in str(a.get("markers", "")).split():
                atype += "[]"
            member = f'{atype} {_safe_member(str(a.get("name", "")))}'.strip()
            if member:
                lines.append(f"    {member}")
        lines.append("  }")
    for e in graph["edges"]:
        s, d, kind = str(e["src"]), str(e["dst"]), e.get("kind")
        if not (kind and s in ent_ids and d in ent_ids):
            continue
        arrow = CLASS_ARROW.get(str(kind), "-->")
        label = _relation_label(cast("dict[str, Any]", e))
        suffix = f" : {label}" if label else ""
        if kind == "inheritance":
            lines.append(f"  {s} {arrow} {d}{suffix}")
        else:
            left = f'"{e["src_card"]}" ' if e.get("src_card") else ""
            right = f' "{e["dst_card"]}"' if e.get("dst_card") else ""
            lines.append(f"  {s} {left}{arrow}{right} {d}{suffix}")
    return "\n".join(lines)


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
    lines.append("  classDef subsystem fill:#fef3c7,stroke:#b45309,color:#7c2d12;")
    return "\n".join(lines)


def gen_container_edges(graph: GraphDict) -> dict[str, list[dict[str, str]]]:
    """For each inter-subsystem arrow 'A>B' drawn in the Subsystems view, the underlying
    component->component edges that cross from A to B (endpoints, names, verb, why) — the viewer
    lists their meanings in the arrow's hover tooltip. Mirrors the crossing logic in
    gen_container_mermaid, so each list's length equals that arrow's count label."""
    out: dict[str, list[dict[str, str]]] = {}
    for e in graph["edges"]:
        s, d = str(e["src"]), str(e["dst"])
        sa, sb = _top_subsystem(graph, s), _top_subsystem(graph, d)
        if sa and sb and sa != sb:
            sn, dn = graph["nodes"].get(s), graph["nodes"].get(d)
            out.setdefault(f"{sa}>{sb}", []).append({
                "src": s,
                "dst": d,
                "srcName": str(sn["name"]) if sn else s,
                "dstName": str(dn["name"]) if dn else d,
                "verb": str(e["verb"]),
                "why": str(e["why"]) if e["why"] else "",
            })
    return out


def _components_of(graph: GraphDict, sid: str) -> list[tuple[str, str]]:
    """(id, name) of every component whose top-level subsystem is `sid`."""
    return [(cid, str(n["name"])) for cid, n in graph["nodes"].items()
            if str(n["kind"]) == "component" and _top_subsystem(graph, cid) == sid]


def _component_subgraph(graph: GraphDict, sid: str, indent: str = "  ") -> list[str]:
    """Mermaid lines framing a subsystem's components as `subgraph <sid>["name"] … end`. Shared by
    the subsystem card and the edge card so a subsystem always reads as a labelled frame (matching
    the base-map subsystem boxes)."""
    open_b, close_b = SHAPE["component"]
    out = [f'{indent}subgraph {sid}["{_safe_label(str(graph["nodes"][sid]["name"]))}"]']
    for cid, name in _components_of(graph, sid):
        out.append(f"{indent}  {cid}{open_b}{_safe_label(name)}{close_b}:::cy-{cid}")
        out.append(f"{indent}  class {cid} component")
    out.append(f"{indent}end")
    return out


def gen_subsystem_card_mermaid(graph: GraphDict, sid: str) -> str:
    """Subsystem card: `sid` drawn as a frame around its components (with their internal wiring),
    the deps those components touch drawn outside the frame, AND the subsystem's neighbourhood —
    every other subsystem its components link to/from is drawn as a collapsed box, with one
    unlabelled arrow per (component, neighbour) pair (Q2-style aggregation, no count). A component
    inside the frame points to the neighbour box (outbound) or is pointed at by it (inbound). The
    viewer turns a click on such an arrow into the matching edge card, and a click on a neighbour
    box into that subsystem's own card."""
    members = {cid for cid, _ in _components_of(graph, sid)}
    deps: set[str] = set()
    neighbours: set[str] = set()
    cross: set[tuple[str, str]] = set()  # rendered (src, dst): a component and a neighbour-subsystem box
    for e in graph["edges"]:
        s, d = str(e["src"]), str(e["dst"])
        ks, kd = str(graph["nodes"].get(s, {}).get("kind")), str(graph["nodes"].get(d, {}).get("kind"))
        if s in members and kd == "dep":
            deps.add(d)
        if d in members and ks == "dep":
            deps.add(s)
        if s in members and kd == "component":          # outbound: member -> component elsewhere
            td = _top_subsystem(graph, d)
            if td and td != sid:
                neighbours.add(td)
                cross.add((s, td))
        if d in members and ks == "component":          # inbound: component elsewhere -> member
            ts = _top_subsystem(graph, s)
            if ts and ts != sid:
                neighbours.add(ts)
                cross.add((ts, d))
    keep = members | deps  # the set whose internal (labelled) edges are drawn
    lines = ["flowchart TB", *_component_subgraph(graph, sid)]
    for nb in sorted(neighbours):  # collapsed neighbour-subsystem boxes
        lines.append(f'  {nb}["{_safe_label(str(graph["nodes"][nb]["name"]))}"]:::cy-{nb}')
        lines.append(f"  class {nb} subsystem")
    open_b, close_b = SHAPE["dep"]
    for did in sorted(deps):  # deps belong to no subsystem — draw them outside the frame
        lines.append(f'  {did}{open_b}{_safe_label(str(graph["nodes"][did]["name"]))}{close_b}:::cy-{did}')
        lines.append(f"  class {did} dep")
    for src, verb, dst in _diagram_edges(graph, None, keep):  # internal + dep edges (labelled)
        lines.append(f"  {src} -->|{verb}| {dst}")
    for src, dst in sorted(cross):  # neighbourhood arrows (unlabelled; click -> edge card)
        lines.append(f"  {src} --> {dst}")
    lines.append("  classDef component fill:#eef2ff,stroke:#3730a3,color:#1e1b4b;")
    lines.append("  classDef dep fill:#ecfdf5,stroke:#065f46,color:#064e3b;")
    lines.append("  classDef subsystem fill:#fef3c7,stroke:#b45309,color:#7c2d12;")
    return "\n".join(lines)


def subsystem_component_mermaids(graph: GraphDict) -> dict[str, str]:
    """One subsystem-card diagram per top-level subsystem (see gen_subsystem_card_mermaid)."""
    return {nid: gen_subsystem_card_mermaid(graph, nid)
            for nid, node in graph["nodes"].items()
            if str(node["kind"]) == "subsystem" and _parent_of(graph, nid) is None}


def gen_edge_card_mermaid(graph: GraphDict, a: str, b: str) -> str:
    """Edge card: subsystems `a` and `b` as two subgraph frames holding ALL their components
    (Q2=A), with ONLY the a->b component edges drawn — no internal edges, no deps, no edges to
    other subsystems. Node ids + `src -->|verb| dst` match the component view, so the viewer's
    edge bridge resolves an in-card arrow to its real component edge."""
    lines = ["flowchart LR", *_component_subgraph(graph, a), *_component_subgraph(graph, b)]
    for e in graph["edges"]:
        s, d = str(e["src"]), str(e["dst"])
        if _top_subsystem(graph, s) == a and _top_subsystem(graph, d) == b:
            lines.append(f"  {s} -->|{e['verb']}| {d}")
    lines.append("  classDef component fill:#eef2ff,stroke:#3730a3,color:#1e1b4b;")
    return "\n".join(lines)


def edge_card_mermaids(graph: GraphDict) -> dict[str, str]:
    """One edge-card diagram per directed top-subsystem pair that has a crossing component edge,
    keyed 'A>B' to match the rendered inter-subsystem arrow's endpoints."""
    pairs: set[tuple[str, str]] = set()
    for e in graph["edges"]:
        sa, sb = _top_subsystem(graph, str(e["src"])), _top_subsystem(graph, str(e["dst"]))
        if sa and sb and sa != sb:
            pairs.add((sa, sb))
    return {f"{a}>{b}": gen_edge_card_mermaid(graph, a, b) for a, b in sorted(pairs)}


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
                         "file": None, "line": None, "fields": {}}
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
    (with their Why) that realize it. Keyed by '<src>><dst>' to match the rendered edge path ids."""
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
    lines.append("  classDef component fill:#eef2ff,stroke:#3730a3,color:#1e1b4b;")
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
  <span class="meta" id="meta"></span>
  <span id="drillhint" hidden>&#8984;-click to drill down</span>
  <span id="nav">
    <button id="navback" title="Back (⌘← / ⌥←)">◀</button>
    <button id="navfwd" title="Forward (⌘→ / ⌥→)">▶</button>
  </span>
  <span id="viewsw">
    <button data-view="gp">Golden Path</button>
    <button data-view="container">Subsystems</button>
    <button data-view="domain">Domain</button>
    <button data-view="context">Context</button>
    <button data-view="component">Components</button>
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
  <div id="stage">
    <div id="diagram"></div>
    <div id="legend"></div>
  </div>
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
             gp_mm: str, gp_steps: dict[str, str], gp_actors_list: list[dict[str, Any]], gp: bool,
             libs_mm: str, folded: list[dict[str, str]],
             repo_root: str, gh_repo: str | None, gh_commit: str | None) -> str:
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
        .replace("__MERMAID_GP__", json.dumps(gp_mm))
        .replace("__MERMAID_GP_STEP__", json.dumps(gp_steps))
        .replace("__GP_ACTORS__", json.dumps(gp_actors_list))
        .replace("__MERMAID_LIBS__", json.dumps(libs_mm))
        .replace("__FOLDED_LIBS__", json.dumps(folded))
        .replace("__CONTEXT_EDGES__", json.dumps(context_edges))
        .replace("__HAS_DIFF__", "true" if has_diff else "false")
        .replace("__HAS_GROUPING__", "true" if grouping else "false")
        .replace("__HAS_DOMAIN__", "true" if domain else "false")
        .replace("__HAS_GP__", "true" if gp else "false")
        .replace("__META__", json.dumps(meta))
        .replace("__DIFF_STATE__", json.dumps(diff_state))
    )


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "build/graph.json")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "build/project-map.html")
    report = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    if not src.exists():
        print(f"ERROR: {src} not found (run build_graph.py first)", file=sys.stderr)
        return 1
    graph = cast(GraphDict, json.loads(src.read_text(encoding="utf-8")))
    diff = build_diff(report) if report and report.exists() else None
    base_mm = gen_mermaid(graph, None)
    diff_mm = gen_mermaid(graph, diff) if diff else base_mm
    context_mm = gen_context_mermaid(graph)
    context_edges = gen_context_edges(graph)
    state = compute_state(graph, diff)
    if diff:
        meta = f"diff: <code>{diff['base']}</code> → <code>{diff['new']}</code> · {len(diff['changes'])} changes"
    else:
        meta = f"baseline @ <code>{graph['commit'] or 'unknown'}</code>"
    grouping = has_grouping(graph)
    container_mm = gen_container_mermaid(graph) if grouping else ""
    by_sub = subsystem_component_mermaids(graph) if grouping else {}
    edge_cards = edge_card_mermaids(graph) if grouping else {}
    container_edges = gen_container_edges(graph) if grouping else {}
    domain = has_domain(graph)
    domain_mm = gen_domain_mermaid(graph) if domain else ""
    gp = has_gp(graph)
    gp_mm = gen_gp_mermaid(graph) if gp else ""
    gp_steps = gp_step_mermaids(graph) if gp else {}
    gp_actors_list = gp_actors(graph) if gp else []
    libs_mm = gen_libs_mermaid(graph)
    folded = folded_libs(graph)
    mg = merged_graph(graph, diff)
    add_context_nodes(mg, graph)
    # Source-link config, derived at build time from the mapped repo (the output dir anchors it).
    # Seeded into the viewer; the user can override the root / GitHub URL in Settings (localStorage).
    anchor = out.resolve().parent
    repo_root = repo_root_default(anchor)
    gh_repo = gh_repo_url(anchor)
    gh_commit = graph["commit"]
    html = gen_html(mg, base_mm, diff_mm, context_mm, context_edges, diff is not None, meta, state,
                    container_mm, by_sub, edge_cards, container_edges, grouping, domain_mm, domain,
                    gp_mm, gp_steps, gp_actors_list, gp, libs_mm, folded, repo_root, gh_repo, gh_commit)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote viewer -> {out}  (diff: {'yes' if diff else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
