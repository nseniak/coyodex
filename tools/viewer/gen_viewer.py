#!/usr/bin/env python3
"""Generate a self-contained HTML viewer from a parsed graph.

Reads a graph.json (from build_graph.py) and (optionally) a change-impact report; emits a single
HTML file with the graph inlined and Mermaid + svg-pan-zoom loaded from a pinned CDN with SRI.
The viewer's own CSS/JS are authored in viewer.css / viewer.js next to this module and inlined at
build time, so the emitted HTML stays standalone — it carries no path back to this repo (see the
"Generated artifacts are standalone w.r.t. the coyodex repo" design note).
The viewer offers four altitudes — Context (C4) → Subsystems (click a box/arrow to open a floating
card) → Components → code links — wraps Mermaid's SVG with pan/zoom and a click->side-panel bridge,
and a baseline<->diff toggle that recolors added/modified/deleted nodes and the elements they ripple
to.

Node labels are the element name only (no ID prefix) to keep them uncluttered;
the ID still appears in the panel header and drives the bridge via the cy-<ID>
class.

Usage:  python3 gen_viewer.py [build/graph.json] [build/project-map.html] [report.md]
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, cast

from build_graph import DiffDict, GraphDict, build_diff

_ASSETS = Path(__file__).resolve().parent  # viewer.css/js live here; inlined into the HTML at build time

SHAPE = {"component": ('["', '"]'), "dep": ('[("', '")]')}
DIAGRAM_KINDS = ("component", "dep")


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


def subsystem_component_mermaids(graph: GraphDict) -> dict[str, str]:
    """Subsystem card: components inside each top-level subsystem, their internal wiring, and the
    deps they touch (Q1=B — the card shows the subsystem's full content, not just bare boxes)."""
    out: dict[str, str] = {}
    for nid, node in graph["nodes"].items():
        if str(node["kind"]) != "subsystem" or _parent_of(graph, nid) is not None:
            continue
        members = {cid for cid, n in graph["nodes"].items()
                   if str(n["kind"]) == "component" and _top_subsystem(graph, cid) == nid}
        out[nid] = gen_mermaid(graph, None, only=members)
    return out


def _components_of(graph: GraphDict, sid: str) -> list[tuple[str, str]]:
    """(id, name) of every component whose top-level subsystem is `sid`."""
    return [(cid, str(n["name"])) for cid, n in graph["nodes"].items()
            if str(n["kind"]) == "component" and _top_subsystem(graph, cid) == sid]


def gen_edge_card_mermaid(graph: GraphDict, a: str, b: str) -> str:
    """Edge card: subsystems `a` and `b` as two subgraph frames holding ALL their components
    (Q2=A), with ONLY the a->b component edges drawn — no internal edges, no deps, no edges to
    other subsystems. Node ids + `src -->|verb| dst` match the component view, so the viewer's
    edge bridge resolves an in-card arrow to its real component edge."""
    open_b, close_b = SHAPE["component"]
    lines = ["flowchart LR"]
    for sid in (a, b):
        lines.append(f'  subgraph {sid}["{_safe_label(str(graph["nodes"][sid]["name"]))}"]')
        for cid, name in _components_of(graph, sid):
            lines.append(f"    {cid}{open_b}{_safe_label(name)}{close_b}:::cy-{cid}")
            lines.append(f"    class {cid} component")
        lines.append("  end")
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


def gen_context_mermaid(graph: GraphDict) -> str:
    """C4 Context: the system as one node, actors (Roles) using it, external deps it relies on."""
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
    for nid, node in graph["nodes"].items():
        if str(node["kind"]) == "dep":
            lines.append(f'  SYS -->|uses| {nid}[("{_safe_label(str(node["name"]))}")]:::cy-{nid}')
            lines.append(f"  class {nid} dep")
    lines.append("  classDef system fill:#1e1b4b,stroke:#312e81,color:#fff;")
    lines.append("  classDef human fill:#fff7ed,stroke:#c2410c,color:#7c2d12;")
    lines.append("  classDef svc fill:#eef2ff,stroke:#4338ca,color:#312e81;")
    lines.append("  classDef dep fill:#ecfdf5,stroke:#065f46,color:#064e3b;")
    return "\n".join(lines)


def add_context_nodes(g: dict[str, Any], graph: GraphDict) -> None:
    """Synthetic System + actor nodes in the panel graph so the click bridge resolves them."""
    g["nodes"]["SYS"] = {"id": "SYS", "kind": "system", "name": graph["title"] or "System",
                         "file": None, "line": None, "fields": {}}
    for i, r in enumerate(graph["roles"]):
        rid = "R" + str(i)
        g["nodes"][rid] = {"id": rid, "kind": r["kind"], "name": r["name"], "file": None, "line": None,
                           "fields": ({"Wants": r["wants"]} if r["wants"] else {})}


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
  <span id="viewsw">
    <button data-view="context">Context</button>
    <button data-view="container">Subsystems</button>
    <button data-view="component">Components</button>
  </span>
  <button id="toggle" style="display:none"></button>
</header>
<div class="hint">Scroll to zoom · drag to pan · click a node for details.<span id="crumb"></span></div>
<main>
  <div id="stage">
    <div id="diagram"></div>
    <div id="legend"></div>
  </div>
  <aside id="panel"><p class="empty">Click a node or edge to see details.</p></aside>
</main>
<script type="module">
__SCRIPT__
</script>
</body>
</html>
"""


def gen_html(graph: dict[str, Any], base: str, diff_mm: str, context_mm: str,
             context_edges: dict[str, dict[str, Any]], has_diff: bool, meta: str,
             diff_state: dict[str, str], container_mm: str, by_sub: dict[str, str],
             edge_cards: dict[str, str], grouping: bool) -> str:
    css = (_ASSETS / "viewer.css").read_text(encoding="utf-8")
    js = (_ASSETS / "viewer.js").read_text(encoding="utf-8")
    return (
        HTML.replace("__STYLE__", css)
        .replace("__SCRIPT__", js)
        .replace("__GRAPH_JSON__", json.dumps(graph))
        .replace("__MERMAID_BASE__", json.dumps(base))
        .replace("__MERMAID_DIFF__", json.dumps(diff_mm))
        .replace("__MERMAID_CONTEXT__", json.dumps(context_mm))
        .replace("__MERMAID_CONTAINER__", json.dumps(container_mm))
        .replace("__MERMAID_BY_SUB__", json.dumps(by_sub))
        .replace("__MERMAID_EDGE_CARD__", json.dumps(edge_cards))
        .replace("__CONTEXT_EDGES__", json.dumps(context_edges))
        .replace("__HAS_DIFF__", "true" if has_diff else "false")
        .replace("__HAS_GROUPING__", "true" if grouping else "false")
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
    mg = merged_graph(graph, diff)
    add_context_nodes(mg, graph)
    html = gen_html(mg, base_mm, diff_mm, context_mm, context_edges, diff is not None, meta, state,
                    container_mm, by_sub, edge_cards, grouping)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote viewer -> {out}  (diff: {'yes' if diff else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
