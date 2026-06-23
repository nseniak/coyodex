#!/usr/bin/env python3
"""Generate a self-contained HTML viewer from a parsed graph.

Reads a graph.json (from build_graph.py) and (optionally) a change-impact report; emits a single
HTML file with the graph inlined and Mermaid + svg-pan-zoom loaded from a pinned CDN with SRI.
The viewer offers four altitudes — Context (C4) → Subsystems (expand-in-place) → Components → code
links — wraps Mermaid's SVG with pan/zoom and a click->side-panel bridge, and a baseline<->diff
toggle that recolors added/modified/deleted nodes and the elements they ripple to.

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
    """Per-subsystem drill-down: components inside each top-level subsystem (+ deps they touch)."""
    out: dict[str, str] = {}
    for nid, node in graph["nodes"].items():
        if str(node["kind"]) != "subsystem" or _parent_of(graph, nid) is not None:
            continue
        members = {cid for cid, n in graph["nodes"].items()
                   if str(n["kind"]) == "component" and _top_subsystem(graph, cid) == nid}
        out[nid] = gen_mermaid(graph, None, only=members)
    return out


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
  * { box-sizing: border-box; }
  body { margin: 0; font: 14px/1.5 -apple-system, system-ui, sans-serif; color: #111; }
  header { padding: 8px 14px; background: #1e1b4b; color: #fff; display: flex; gap: 12px; align-items: center; }
  header h1 { font-size: 15px; margin: 0; font-weight: 600; flex: 0 0 auto; }
  header .meta { font-size: 12px; opacity: .8; flex: 1; }
  header button { font: inherit; font-size: 12px; padding: 4px 12px; border: 0; border-radius: 6px;
                  background: #6366f1; color: #fff; cursor: pointer; }
  header button:hover { background: #818cf8; }
  #viewsw { display: inline-flex; border: 1px solid #6366f1; border-radius: 6px; overflow: hidden; }
  #viewsw button { background: transparent; color: #c7d2fe; border-radius: 0; padding: 4px 10px; }
  #viewsw button:hover { background: #312e81; }
  #viewsw button.active { background: #6366f1; color: #fff; }
  main { display: flex; height: calc(100vh - 38px); }
  #stage { flex: 1; position: relative; overflow: hidden; background: #fafafa; }
  #diagram { width: 100%; height: 100%; }
  #diagram svg { width: 100%; height: 100%; }
  #panel { width: 340px; border-left: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fff; }
  #panel .empty { color: #9ca3af; }
  #panel h2 { font-size: 16px; margin: 0 0 6px; }
  #panel .badges { margin-bottom: 12px; }
  #panel .badge { display: inline-block; font-size: 11px; text-transform: uppercase; letter-spacing: .04em;
                  padding: 1px 7px; border-radius: 10px; margin-right: 6px; }
  .badge.kind { background: #eef2ff; color: #3730a3; }
  .badge.edge { background: #e2e8f0; color: #334155; }
  .badge.added { background: #dafbe1; color: #1a7f37; }
  .badge.modified { background: #fff8c5; color: #9a6700; }
  .badge.deleted { background: #ffebe9; color: #cf222e; }
  #panel dl { margin: 0; }
  #panel dt { font-size: 11px; text-transform: uppercase; letter-spacing: .03em; color: #6b7280; margin-top: 10px; }
  #panel dd { margin: 2px 0 0; }
  #panel .src { margin-top: 14px; font-family: ui-monospace, monospace; font-size: 12px; color: #2563eb; }
  .hint { padding: 6px 14px; font-size: 12px; color: #6b7280; background: #f3f4f6; }
  #crumb a { color: #2563eb; cursor: pointer; text-decoration: underline; }
  #legend { position: absolute; left: 12px; bottom: 12px; background: #fff; border: 1px solid #e5e7eb;
            border-radius: 8px; padding: 8px 10px; font-size: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.08); display: none; }
  #legend.on { display: block; }
  #legend .row { display: flex; align-items: center; gap: 7px; margin: 3px 0; }
  #legend svg { display: block; flex: 0 0 auto; }
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
// `mermaid` is the global from the SRI-pinned UMD <script> in <head>.

const GRAPH = __GRAPH_JSON__;
const MERMAID_BASE = __MERMAID_BASE__;
const MERMAID_DIFF = __MERMAID_DIFF__;
const MERMAID_CONTEXT = __MERMAID_CONTEXT__;
const MERMAID_CONTAINER = __MERMAID_CONTAINER__;
const MERMAID_BY_SUB = __MERMAID_BY_SUB__;
const HAS_GROUPING = __HAS_GROUPING__;
const CONTEXT_EDGES = __CONTEXT_EDGES__;
const HAS_DIFF = __HAS_DIFF__;
const META = __META__;
const DIFF_STATE = __DIFF_STATE__;
const SVGNS = 'http://www.w3.org/2000/svg';
const R = 10;
const BADGE = { added: ['#1a7f37', '+', 'new'], modified: ['#9a6700', '✎', 'modified'],
                deleted: ['#cf222e', '×', 'deleted'], rippled: ['#d97706', '≈', 'ripples to'] };
const HILITE = 'drop-shadow(0 0 4px #2563eb) drop-shadow(0 0 2px #2563eb)';  // selection glow (nodes + edge labels)
const HOVER = 'drop-shadow(0 0 3px #60a5fa)';  // softer hover glow: signals "clickable" without competing with HILITE

mermaid.initialize({ startOnLoad: false, securityLevel: 'loose', theme: 'default', flowchart: { curve: 'basis' } });

const diagram = document.getElementById('diagram');
const panel = document.getElementById('panel');
const legend = document.getElementById('legend');
const toggle = document.getElementById('toggle');
const viewsw = document.getElementById('viewsw');
document.getElementById('meta').innerHTML = META;
const stripMd = (s) => (s || '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');

let mode = 'base';
let view = 'context';  // start high (C4 Context); drill Context → Subsystems → Components
let expanded = new Set();  // subsystem ids expanded-in-place in the Subsystems view
let pz = null;
let rc = 0;
let nodeEls = {};    // id -> g.node element (rebuilt each render)
let edgeEls = [];    // { e, path, label } per edge (rebuilt each render)
let containerEdges = {};  // Subsystems view: epKey 'a>b' -> underlying component edges (rebuilt each render)
let selectedKey = null;  // 'node:<id>' or 'edge:<src>><dst>' — for click-again-to-deselect
let downX = 0, downY = 0; // last mousedown, to tell a real click from a drag-pan
const DIM = '0.15';  // opacity for non-focused elements

function showNode(id) {
  const n = GRAPH.nodes[id];
  if (!n) return;
  const chg = n.change ? `<span class="badge ${n.change}">${n.change}</span>` : '';
  const rows = Object.entries(n.fields || {})
    .map(([k, v]) => `<dt>${k}</dt><dd>${stripMd(String(v))}</dd>`).join('');
  const src = n.file ? `<div class="src">${n.file}${n.line ? ':' + n.line : ''}</div>` : '';
  panel.innerHTML = `<h2>${id} · ${n.name}</h2>`
    + `<div class="badges"><span class="badge kind">${n.kind}</span>${chg}</div>`
    + `<dl>${rows}</dl>${src}`;
}

function idOf(el) {
  const cls = [...el.classList].find((c) => c.startsWith('cy-'));
  if (cls) return cls.slice(3);
  const dataId = el.getAttribute('data-id');
  if (dataId && GRAPH.nodes[dataId]) return dataId;
  const m = (el.id || '').match(/(?:^|-)((?:UC|GP|C|D|E|S)\d+)(?:-|$)/);
  return m ? m[1] : null;
}

// One badge builder used by BOTH the diagram and the legend, so they're pixel-identical.
// Inline !important is needed because Mermaid sets SVG text font/fill with !important.
function makeBadge(cx, cy, state) {
  const g = document.createElementNS(SVGNS, 'g');
  const spec = BADGE[state];
  if (!spec) return g;
  const [color, glyph] = spec;
  const c = document.createElementNS(SVGNS, 'circle');
  c.setAttribute('cx', cx); c.setAttribute('cy', cy); c.setAttribute('r', R);
  c.style.setProperty('fill', color, 'important');
  c.style.setProperty('stroke', '#fff', 'important');
  c.style.setProperty('stroke-width', '1.5px', 'important');
  const t = document.createElementNS(SVGNS, 'text');
  t.setAttribute('x', cx); t.setAttribute('y', cy);
  t.setAttribute('text-anchor', 'middle'); t.setAttribute('dominant-baseline', 'central');
  t.style.setProperty('fill', '#fff', 'important');
  t.style.setProperty('font-family', '-apple-system, system-ui, sans-serif', 'important');
  t.style.setProperty('font-size', '13px', 'important');
  t.style.setProperty('font-weight', '700', 'important');
  t.textContent = glyph;
  g.appendChild(c); g.appendChild(t);
  return g;
}

// Overlay technique: inject the badge into the node's SVG group so it pans/zooms with the node.
function addBadge(el, state) {
  const bb = el.getBBox();
  el.appendChild(makeBadge(bb.x + bb.width, bb.y, state));
}

function buildLegend() {
  const d = 2 * R + 4;
  const frag = document.createDocumentFragment();
  for (const state of ['added', 'modified', 'deleted', 'rippled']) {
    const row = document.createElement('div'); row.className = 'row';
    const svg = document.createElementNS(SVGNS, 'svg');
    svg.setAttribute('width', d); svg.setAttribute('height', d); svg.setAttribute('viewBox', '0 0 ' + d + ' ' + d);
    svg.appendChild(makeBadge(d / 2, d / 2, state));
    const span = document.createElement('span'); span.textContent = BADGE[state][2];
    row.appendChild(svg); row.appendChild(span); frag.appendChild(row);
  }
  const note = document.createElement('div'); note.className = 'row'; note.style.color = '#9ca3af';
  note.textContent = 'no badge = unchanged';
  frag.appendChild(note);
  legend.innerHTML = ''; legend.appendChild(frag);
}

// --- container (subsystems) expand-in-place view ---------------------------------
function mlabel(s) { return '"' + String(s || '').replace(/"/g, "'").replace(/`/g, '') + '"'; }
function topSubJS(id) {                          // walk parent pointers to the top-level subsystem
  const n = GRAPH.nodes[id];
  let p = n && n.parent;
  if (!p) return null;
  const seen = new Set();
  while (true) {
    const pn = GRAPH.nodes[p];
    const pp = pn && pn.parent;
    if (!pp || seen.has(p)) return p;
    seen.add(p); p = pp;
  }
}
function topSubsystems() {
  return Object.keys(GRAPH.nodes).filter((k) => GRAPH.nodes[k].kind === 'subsystem' && !GRAPH.nodes[k].parent);
}
// An edge endpoint, lifted to its top-level subsystem UNLESS that subsystem is expanded (then it
// stays the component). null = ungrouped component, not drawn at the container altitude.
function effEndpoint(cid) {
  const top = topSubJS(cid);
  if (!top) return null;
  return expanded.has(top) ? cid : top;
}
// Build the subsystems diagram for the current `expanded` set: expanded subsystems become
// subgraphs holding their components; collapsed ones stay boxes; edges re-derive at mixed
// altitude (count label only when an arrow aggregates >1 underlying component edge).
function buildContainer() {
  const lines = ['flowchart TB'];
  for (const sid of topSubsystems()) {
    if (expanded.has(sid)) {
      lines.push('  subgraph ' + sid + '[' + mlabel(GRAPH.nodes[sid].name) + ']');
      for (const cid in GRAPH.nodes) {
        if (GRAPH.nodes[cid].kind === 'component' && topSubJS(cid) === sid) {
          lines.push('    ' + cid + '[' + mlabel(GRAPH.nodes[cid].name) + ']:::cy-' + cid);
          lines.push('    class ' + cid + ' component');
        }
      }
      lines.push('  end');
    } else {
      lines.push('  ' + sid + '[' + mlabel(GRAPH.nodes[sid].name) + ']:::cy-' + sid);
      lines.push('  class ' + sid + ' subsystem');
    }
  }
  containerEdges = {};
  for (const e of (GRAPH.edges || [])) {
    const a = effEndpoint(e.src), b = effEndpoint(e.dst);
    if (!a || !b || a === b) continue;
    (containerEdges[a + '>' + b] ||= []).push(e);
  }
  for (const k in containerEdges) {
    const a = k.split('>')[0], b = k.split('>')[1];
    const n = containerEdges[k].length;
    lines.push('  ' + a + ' -->' + (n > 1 ? '|' + n + '| ' : ' ') + b);
  }
  lines.push('  classDef subsystem fill:#fef3c7,stroke:#b45309,color:#7c2d12;');
  lines.push('  classDef component fill:#eef2ff,stroke:#3730a3,color:#1e1b4b;');
  return lines.join('\n');
}
// Clicking an expanded subsystem's frame (cluster) collapses it back to a box.
function bindClusters() {
  const byName = {};
  for (const k of topSubsystems()) byName[GRAPH.nodes[k].name] = k;
  diagram.querySelectorAll('g.cluster').forEach((cl) => {
    let m = (cl.id || '').match(/S\d+/);
    let sid = m ? m[0] : null;
    if (!sid) {
      const lblEl = cl.querySelector('.cluster-label, .nodeLabel, span, p');
      const lbl = lblEl && lblEl.textContent ? lblEl.textContent.trim() : '';
      if (byName[lbl]) sid = byName[lbl];
    }
    if (!sid || !GRAPH.nodes[sid]) return;
    cl.style.cursor = 'pointer';
    cl.addEventListener('mouseenter', () => { cl.style.filter = HOVER; });  // clusters never hold a selection
    cl.addEventListener('mouseleave', () => { cl.style.filter = ''; });
    cl.addEventListener('click', (ev) => {
      if (isDrag(ev)) return;
      ev.stopPropagation();
      expanded.delete(sid);
      render();
    });
  });
}

function bind() {
  diagram.querySelectorAll('g.node').forEach((el) => {
    const id = idOf(el);
    if (!id || !GRAPH.nodes[id]) return;
    nodeEls[id] = el;
    el.style.cursor = 'pointer';
    // Hover affordance — skip while this node is the active selection, so HILITE wins.
    el.addEventListener('mouseenter', () => { if (selectedKey !== 'node:' + id) el.style.filter = HOVER; });
    el.addEventListener('mouseleave', () => { if (selectedKey !== 'node:' + id) el.style.filter = ''; });
    el.addEventListener('click', (e) => {
      if (isDrag(e)) return;  // tail of a drag-pan, not a real click
      e.stopPropagation();
      const node = GRAPH.nodes[id];
      if (id === 'SYS') { setView(HAS_GROUPING ? 'container' : 'component'); return; }  // drill: Context → Subsystems
      if (node && node.kind === 'subsystem' && view === 'container') {                  // expand the subsystem in place
        expanded.add(id); render(); return;
      }
      if (selectedKey === 'node:' + id) { reset(); return; }  // click again = deselect
      selectedKey = 'node:' + id;
      showNode(id);
      select(() => {
        el.style.filter = HILITE;
        return () => { el.style.filter = ''; };
      });
      focusNode(id);  // dim non-neighbors (works in both views now that context edges are bound)
    });
    if (mode === 'diff' && DIFF_STATE[id]) addBadge(el, DIFF_STATE[id]);
  });
}

const esc = (s) => (s || '').replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));

// One highlight at a time: select(applyFn) clears the previous highlight and stores its cleanup.
let clearHighlight = null;
function select(applyFn) {
  if (clearHighlight) clearHighlight();
  clearHighlight = applyFn ? applyFn() : null;
}

// Focus: dim everything except a kept set of nodes/edges, so a dense graph reads locally.
function applyFocus(keepNode, keepEdge) {
  for (const nid in nodeEls) nodeEls[nid].style.opacity = keepNode(nid) ? '' : DIM;
  for (const x of edgeEls) {
    const on = keepEdge(x.e);
    x.path.style.opacity = on ? '' : DIM;
    if (x.label) x.label.style.opacity = on ? '' : DIM;
  }
}
function focusNode(id) {
  const keep = new Set([id]);
  for (const x of edgeEls) {
    if (x.e.src === id) keep.add(x.e.dst);
    if (x.e.dst === id) keep.add(x.e.src);
  }
  applyFocus((nid) => keep.has(nid), (e) => e.src === id || e.dst === id);
}
function focusEdge(e0) {
  applyFocus((nid) => nid === e0.src || nid === e0.dst, (e) => e.src === e0.src && e.dst === e0.dst);
}
function clearFocus() {
  for (const nid in nodeEls) nodeEls[nid].style.opacity = '';
  for (const x of edgeEls) { x.path.style.opacity = ''; if (x.label) x.label.style.opacity = ''; }
}
function reset() {
  clearFocus();
  select(null);
  selectedKey = null;
  panel.innerHTML = '<p class="empty">Click a node or edge to see details.</p>';
}

// A click whose pointer moved far from its mousedown is the tail of a drag-pan — ignore it,
// so panning never deselects.
function isDrag(e) { return Math.abs(e.clientX - downX) > 5 || Math.abs(e.clientY - downY) > 5; }

function showEdge(e) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  panel.innerHTML = '<h2>' + esc(nm(e.src)) + ' → ' + esc(nm(e.dst)) + '</h2>'
    + '<div class="badges"><span class="badge edge">' + esc(e.verb) + '</span></div>'
    + '<dl>'
    + (e.why ? '<dt>Why</dt><dd>' + esc(e.why) + '</dd>' : '')
    + '<dt>From</dt><dd>' + e.src + ' · ' + esc(nm(e.src)) + '</dd>'
    + '<dt>To</dt><dd>' + e.dst + ' · ' + esc(nm(e.dst)) + '</dd>'
    + '</dl>'
    + (e.where ? '<div class="src">' + esc(e.where) + '</div>' : '');
}

// Context-edge panel: actor→system shows the role's wants; system→dep shows what it's used for
// and the component edges (with their Why) that realize the dependency.
function showContextEdge(ce) {
  let body = '';
  if (ce.type === 'actor') {
    body = ce.wants ? '<dt>Wants</dt><dd>' + esc(ce.wants) + '</dd>' : '';
  } else {
    const rows = (ce.realizedBy || []).map((r) =>
      '<dd>• ' + esc(r.srcName) + ' — ' + esc(r.verb) + (r.why ? ' — ' + esc(r.why) : '') + '</dd>').join('');
    body = (ce.usedFor ? '<dt>Used for</dt><dd>' + esc(ce.usedFor) + '</dd>' : '')
      + (rows ? '<dt>Realized by</dt>' + rows : '');
  }
  panel.innerHTML = '<h2>' + esc(ce.from) + ' → ' + esc(ce.to) + '</h2>'
    + '<div class="badges"><span class="badge edge">uses</span></div>'
    + '<dl>' + body + '</dl>';
}

// Subsystems-view edge: a derived arrow aggregates one or more component edges. Show them
// (verb + why), like the Context view's "realized by" list.
function showContainerEdge(a, b, ul) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  const rows = ul.map((r) =>
    '<dd>• ' + esc(nm(r.src)) + ' —' + esc(r.verb) + '→ ' + esc(nm(r.dst))
    + (r.why ? ' — ' + esc(r.why) : '') + '</dd>').join('');
  panel.innerHTML = '<h2>' + esc(nm(a)) + ' → ' + esc(nm(b)) + '</h2>'
    + '<div class="badges"><span class="badge edge">' + ul.length + (ul.length > 1 ? ' edges' : ' edge') + '</span></div>'
    + '<dl><dt>Underlying component edges</dt>' + rows + '</dl>';
}

// Edges: paths and labels are emitted in the same order, so zip them by index. The line gets a
// wide transparent hit-path; the label is made clickable too. Both highlight together on select.
function bindEdges() {
  const ctx = view === 'context';
  const compLookup = {};
  if (!ctx) for (const e of GRAPH.edges || []) { (compLookup[e.src + '>' + e.dst] ||= []).push(e); }
  const paths = [...diagram.querySelectorAll('.edgePaths path.flowchart-link')];
  const labels = [...diagram.querySelectorAll('.edgeLabels > g.edgeLabel')];
  paths.forEach((p, i) => {
    const m = p.id.match(/L_([^_]+)_([^_]+)_(\d+)$/);
    if (!m) return;
    const epKey = m[1] + '>' + m[2];
    let e, selKey, showFn;
    if (ctx) {
      e = CONTEXT_EDGES[epKey];
      if (!e) return;
      selKey = 'cedge:' + epKey;
      showFn = () => showContextEdge(e);
    } else if (view === 'container') {
      const arr = containerEdges[epKey];
      if (!arr) return;
      e = { src: m[1], dst: m[2] };  // effective endpoints (rendered ids) for focus/dimming
      selKey = 'cont:' + epKey;
      showFn = () => showContainerEdge(m[1], m[2], arr);
    } else {
      const arr = compLookup[epKey];
      if (!arr) return;
      e = arr[Math.min(+m[3], arr.length - 1)];
      selKey = 'edge:' + e.src + '>' + e.dst;
      showFn = () => showEdge(e);
    }
    const label = labels[i] || null;

    const highlight = () => {
      p.style.setProperty('stroke', '#2563eb', 'important');
      p.style.setProperty('stroke-width', '3px', 'important');
      if (label) label.style.filter = HILITE;  // same glow as a selected component
      return () => {
        p.style.removeProperty('stroke'); p.style.removeProperty('stroke-width');
        if (label) label.style.filter = '';
      };
    };
    // Hover affordance — glow the visible line + its label; skip while this edge is selected.
    const hoverOn = () => { if (selectedKey === selKey) return; p.style.filter = HOVER; if (label) label.style.filter = HOVER; };
    const hoverOff = () => { if (selectedKey === selKey) return; p.style.filter = ''; if (label) label.style.filter = ''; };
    const onClick = (ev) => {
      if (isDrag(ev)) return;  // tail of a drag-pan, not a real click
      ev.stopPropagation();
      hoverOff();  // drop the hover glow before (de)selecting, so it can't linger under HILITE
      if (selectedKey === selKey) { reset(); return; }  // click again = deselect
      selectedKey = selKey;
      showFn(); select(highlight); focusEdge(e);
    };
    edgeEls.push({ e, path: p, label });

    const hit = p.cloneNode(false);
    hit.removeAttribute('id'); hit.removeAttribute('marker-end'); hit.removeAttribute('class');
    hit.dataset.edge = e.src + '>' + e.dst;
    hit.style.setProperty('stroke', 'transparent', 'important');
    hit.style.setProperty('stroke-width', '14px', 'important');
    hit.style.setProperty('fill', 'none', 'important');
    hit.style.setProperty('marker-end', 'none', 'important');
    hit.style.pointerEvents = 'stroke'; hit.style.cursor = 'pointer';
    hit.addEventListener('click', onClick);
    hit.addEventListener('mouseenter', hoverOn);
    hit.addEventListener('mouseleave', hoverOff);
    p.parentNode.appendChild(hit);

    if (label) {
      label.style.cursor = 'pointer';
      label.style.setProperty('pointer-events', 'all', 'important');
      label.addEventListener('click', onClick);
      label.addEventListener('mouseenter', hoverOn);
      label.addEventListener('mouseleave', hoverOff);
    }
  });
}

function setView(v) { if (v !== view) { view = v; render(); } }

async function render() {
  if (pz) { pz.destroy(); pz = null; }
  let text;
  if (view === 'context') text = MERMAID_CONTEXT;
  else if (view === 'container') text = buildContainer();
  else text = (mode === 'diff' ? MERMAID_DIFF : MERMAID_BASE);
  const { svg } = await mermaid.render('coyodexGraph' + (rc++), text);
  diagram.innerHTML = svg;
  clearHighlight = null;  // previous selection's DOM is gone after re-render
  nodeEls = {};
  edgeEls = [];
  selectedKey = null;
  bind();
  bindEdges();
  if (view === 'container') bindClusters();
  const svgEl = diagram.querySelector('svg');
  if (svgEl && window.svgPanZoom) {
    svgEl.removeAttribute('style');
    pz = svgPanZoom(svgEl, { controlIcons: true, fit: true, center: true, minZoom: 0.3, maxZoom: 8 });
  }
  if (svgEl) svgEl.addEventListener('click', (e) => { if (!isDrag(e)) reset(); });  // empty-space click clears (not a drag)
  legend.classList.toggle('on', view === 'component' && mode === 'diff');
  toggle.style.display = (HAS_DIFF && view === 'component') ? '' : 'none';
  toggle.textContent = mode === 'diff' ? 'Show baseline' : 'Show diff';
  viewsw.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.view === view));
  const crumb = document.getElementById('crumb');
  if (view === 'container') {
    crumb.innerHTML = ' · click a subsystem to expand, its frame to collapse · '
      + '<a id="expall">expand all</a> · <a id="collall">collapse all</a>';
    document.getElementById('expall').addEventListener('click', () => {
      topSubsystems().forEach((k) => expanded.add(k)); render();
    });
    document.getElementById('collall').addEventListener('click', () => { expanded.clear(); render(); });
  } else {
    crumb.innerHTML = '';
  }
}

diagram.addEventListener('mousedown', (e) => { downX = e.clientX; downY = e.clientY; }, true);
buildLegend();
viewsw.querySelectorAll('button').forEach((b) => {
  if (b.dataset.view === 'container' && !HAS_GROUPING) { b.style.display = 'none'; return; }
  b.addEventListener('click', () => setView(b.dataset.view));
});
if (HAS_DIFF) {
  toggle.addEventListener('click', () => { mode = mode === 'diff' ? 'base' : 'diff'; render(); });
}
await render();
</script>
</body>
</html>
"""


def gen_html(graph: dict[str, Any], base: str, diff_mm: str, context_mm: str,
             context_edges: dict[str, dict[str, Any]], has_diff: bool, meta: str,
             diff_state: dict[str, str], container_mm: str, by_sub: dict[str, str],
             grouping: bool) -> str:
    return (
        HTML.replace("__GRAPH_JSON__", json.dumps(graph))
        .replace("__MERMAID_BASE__", json.dumps(base))
        .replace("__MERMAID_DIFF__", json.dumps(diff_mm))
        .replace("__MERMAID_CONTEXT__", json.dumps(context_mm))
        .replace("__MERMAID_CONTAINER__", json.dumps(container_mm))
        .replace("__MERMAID_BY_SUB__", json.dumps(by_sub))
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
    mg = merged_graph(graph, diff)
    add_context_nodes(mg, graph)
    html = gen_html(mg, base_mm, diff_mm, context_mm, context_edges, diff is not None, meta, state,
                    container_mm, by_sub, grouping)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote viewer -> {out}  (diff: {'yes' if diff else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
