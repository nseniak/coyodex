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
