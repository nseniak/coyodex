// `mermaid` is the global from the SRI-pinned UMD <script> in <head>.

const GRAPH = __GRAPH_JSON__;
const MERMAID_BASE = __MERMAID_BASE__;
const MERMAID_DIFF = __MERMAID_DIFF__;
const MERMAID_CONTEXT = __MERMAID_CONTEXT__;
const MERMAID_CONTAINER = __MERMAID_CONTAINER__;
const MERMAID_BY_SUB = __MERMAID_BY_SUB__;        // subsystem neighbourhood: sid -> sub-diagram
const MERMAID_EDGE_CARD = __MERMAID_EDGE_CARD__;  // edge pair: 'A>B' -> two-subsystem sub-diagram
const MERMAID_DOMAIN = __MERMAID_DOMAIN__;        // T5 domain model as a classDiagram
const HAS_GROUPING = __HAS_GROUPING__;
const HAS_DOMAIN = __HAS_DOMAIN__;
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
const DIM = '0.15';  // opacity for non-focused elements
const EMPTY_PANEL = '<p class="empty">Click a node or edge to see details.</p>';

mermaid.initialize({ startOnLoad: false, securityLevel: 'loose', theme: 'default', flowchart: { curve: 'basis' } });

const diagram = document.getElementById('diagram');
const stage = document.getElementById('stage');
const panel = document.getElementById('panel');
const legend = document.getElementById('legend');
const toggle = document.getElementById('toggle');
const viewsw = document.getElementById('viewsw');
const navback = document.getElementById('navback');
const navfwd = document.getElementById('navfwd');
const crumb = document.getElementById('crumb');
document.getElementById('meta').innerHTML = META;
const stripMd = (s) => (s || '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
const esc = (s) => (s || '').replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));

let mode = 'base';
let mainPz = null;     // svg-pan-zoom for the current diagram
let rc = 0;
let renderSeq = 0;     // bumped each render(); an in-flight render bails if it's no longer current
let downX = 0, downY = 0;  // last mousedown, to tell a real click from a drag-pan

// Component-edge lookup '<src>><dst>' -> [edges]; static (GRAPH.edges never changes). Shared by the
// Components view and the drilled diagrams, so an arrow resolves to its real component edge.
const COMP_LOOKUP = {};
for (const e of GRAPH.edges || []) (COMP_LOOKUP[e.src + '>' + e.dst] ||= []).push(e);

// --- scene ----------------------------------------------------------------------
// A "scene" wraps the diagram currently shown: its root, the bound node/edge elements, the active
// selection, and what the side panel shows when nothing is selected. There's one scene at a time;
// it's rebuilt on every render. Focus/select/reset all operate on it.
let mainScene = null;

function makeScene(root, defaultPanel) {
  return { root, nodeEls: {}, edgeEls: [], selectedKey: null, clearHighlight: null, defaultPanel };
}
function sceneSelect(scene, applyFn) {  // one highlight at a time within a scene
  if (scene.clearHighlight) scene.clearHighlight();
  scene.clearHighlight = applyFn ? applyFn() : null;
}
function applyFocus(scene, keepNode, keepEdge) {
  for (const nid in scene.nodeEls) scene.nodeEls[nid].style.opacity = keepNode(nid) ? '' : DIM;
  for (const x of scene.edgeEls) {
    const on = keepEdge(x.e);
    x.path.style.opacity = on ? '' : DIM;
    if (x.label) x.label.style.opacity = on ? '' : DIM;
  }
}
function focusNode(scene, id) {
  const keep = new Set([id]);
  for (const x of scene.edgeEls) {
    if (x.e.src === id) keep.add(x.e.dst);
    if (x.e.dst === id) keep.add(x.e.src);
  }
  applyFocus(scene, (nid) => keep.has(nid), (e) => e.src === id || e.dst === id);
}
function focusEdge(scene, e0) {
  applyFocus(scene, (nid) => nid === e0.src || nid === e0.dst, (e) => e.src === e0.src && e.dst === e0.dst);
}
function clearFocus(scene) {
  for (const nid in scene.nodeEls) scene.nodeEls[nid].style.opacity = '';
  for (const x of scene.edgeEls) { x.path.style.opacity = ''; if (x.label) x.label.style.opacity = ''; }
}
function resetScene(scene) {  // clear selection + focus, restore the scene's default panel
  clearFocus(scene);
  sceneSelect(scene, null);
  scene.selectedKey = null;
  scene.defaultPanel();
}

// A click whose pointer moved far from its mousedown is the tail of a drag-pan — ignore it,
// so panning never deselects.
function isDrag(e) { return Math.abs(e.clientX - downX) > 5 || Math.abs(e.clientY - downY) > 5; }

// --- side panel -----------------------------------------------------------------
function showNode(id) {
  const n = GRAPH.nodes[id];
  if (!n) return;
  const chg = n.change ? `<span class="badge ${n.change}">${n.change}</span>` : '';
  const rows = Object.entries(n.fields || {})
    // a subsystem's first field IS its name (already in the title) — don't repeat it
    .filter(([k]) => !(n.kind === 'subsystem' && k.toLowerCase() === 'subsystem'))
    .map(([k, v]) => `<dt>${k}</dt><dd>${stripMd(String(v))}</dd>`).join('');
  // entity attributes (T5 domain cards): `type name` + any markers (PK/FK/unique/…)
  const attrs = (n.attrs && n.attrs.length)
    ? '<dt>Fields</dt><dd>' + n.attrs.map((a) =>
        esc(((a.type ? a.type + ' ' : '') + (a.name || '') + (a.markers ? '  ·  ' + a.markers : '')).trim())
      ).join('<br>') + '</dd>'
    : '';
  const src = n.file ? `<div class="src">${n.file}${n.line ? ':' + n.line : ''}</div>` : '';
  panel.innerHTML = `<h2>${id} · ${n.name}</h2>`
    + `<div class="badges"><span class="badge kind">${n.kind}</span>${chg}</div>`
    + `<dl>${rows}${attrs}</dl>${src}`;
}

function showEdge(e) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  // domain relations carry a kind (composition/…) + cardinality; component edges carry why/where.
  const kindBadge = e.kind ? '<span class="badge kind">' + esc(e.kind) + '</span>' : '';
  const card = (e.src_card || e.dst_card)
    ? '<dt>Cardinality</dt><dd>' + esc((e.src_card || '') + ' → ' + (e.dst_card || '')) + '</dd>' : '';
  panel.innerHTML = '<h2>' + esc(nm(e.src)) + ' → ' + esc(nm(e.dst)) + '</h2>'
    + '<div class="badges"><span class="badge edge">' + esc(e.verb) + '</span>' + kindBadge + '</div>'
    + '<dl>'
    + (e.why ? '<dt>Why</dt><dd>' + esc(e.why) + '</dd>' : '')
    + card
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

// Subsystems edge: the panel shows both subsystems (name + Purpose); the concrete A→B wiring is the
// diagram itself (the edge view we navigated to).
function subsystemBlock(id) {
  const n = GRAPH.nodes[id];
  if (!n) return '';
  const purpose = n.fields && (n.fields.Purpose || n.fields.purpose);
  return '<h3>' + esc(id) + ' · ' + esc(n.name) + '</h3>'
    + (purpose ? '<dl><dt>Purpose</dt><dd>' + stripMd(String(purpose)) + '</dd></dl>' : '');
}
function showTwoSubsystems(a, b) {
  panel.innerHTML = '<div class="badges"><span class="badge edge">connection</span></div>'
    + subsystemBlock(a) + '<hr>' + subsystemBlock(b);
}

// --- diff badges + legend -------------------------------------------------------
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

function idOf(el) {
  const cls = [...el.classList].find((c) => c.startsWith('cy-'));
  if (cls) return cls.slice(3);
  const dataId = el.getAttribute('data-id');
  if (dataId && GRAPH.nodes[dataId]) return dataId;
  const m = (el.id || '').match(/(?:^|-)((?:UC|GP|C|D|E|S)\d+)(?:-|$)/);
  return m ? m[1] : null;
}

// --- shared binding -------------------------------------------------------------
// Select a normal node within a scene: toggle off if already selected, else show + highlight + focus.
function selectNode(scene, el, id) {
  if (scene.selectedKey === 'node:' + id) { resetScene(scene); return; }
  scene.selectedKey = 'node:' + id;
  showNode(id);
  sceneSelect(scene, () => { el.style.filter = HILITE; return () => { el.style.filter = ''; }; });
  focusNode(scene, id);
}

function bindNodes(scene, onActivate) {
  scene.root.querySelectorAll('g.node').forEach((el) => {
    const id = idOf(el);
    if (!id || !GRAPH.nodes[id]) return;
    // Subsystem boxes (a neighbourhood diagram's collapsed neighbours) stay out of the focus set, so
    // selecting a component dims the internal neighbourhood — not the external boxes. Still clickable.
    if (GRAPH.nodes[id].kind !== 'subsystem') scene.nodeEls[id] = el;
    el.style.cursor = 'pointer';
    // Hover affordance — skip while this node is the active selection, so HILITE wins.
    el.addEventListener('mouseenter', () => { if (scene.selectedKey !== 'node:' + id) el.style.filter = HOVER; });
    el.addEventListener('mouseleave', () => { if (scene.selectedKey !== 'node:' + id) el.style.filter = ''; });
    el.addEventListener('click', (e) => {
      if (isDrag(e)) return;  // tail of a drag-pan, not a real click
      e.stopPropagation();
      onActivate(id, el);
    });
    if (mode === 'diff' && DIFF_STATE[id]) addBadge(el, DIFF_STATE[id]);
  });
}

// Give an edge's visible path a wide transparent hit-path + make its label clickable.
function attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff) {
  const hit = p.cloneNode(false);
  hit.removeAttribute('id'); hit.removeAttribute('marker-end'); hit.removeAttribute('class');
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
}

// Iterate a diagram's edges, pairing each path with its label by index. Mermaid emits one label
// element per edge in path order (an empty one for an unlabelled arrow), so the index pairing stays
// aligned even when some arrows carry no label. `fn(path, label, match)` gets the L_<src>_<dst>_<i>.
function eachEdge(root, fn) {
  const paths = [...root.querySelectorAll('.edgePaths path.flowchart-link')];
  const labels = [...root.querySelectorAll('.edgeLabels > g.edgeLabel')];
  paths.forEach((p, i) => {
    const m = p.id.match(/L_([^_]+)_([^_]+)_(\d+)$/);
    if (m) fn(p, labels[i] || null, m);
  });
}

// Stroke an edge's path + glow its label (selection highlight); returns a cleanup fn.
function glowEdge(p, label) {
  p.style.setProperty('stroke', '#2563eb', 'important');
  p.style.setProperty('stroke-width', '3px', 'important');
  if (label) label.style.filter = HILITE;
  return () => {
    p.style.removeProperty('stroke'); p.style.removeProperty('stroke-width');
    if (label) label.style.filter = '';
  };
}

// Wire one edge for the SELECT model (highlight + focus + panel) — context, components, internal edges.
function bindSelectEdge(scene, p, label, e, selKey, showFn) {
  const hoverOn = () => { if (scene.selectedKey !== selKey) { p.style.filter = HOVER; if (label) label.style.filter = HOVER; } };
  const hoverOff = () => { if (scene.selectedKey !== selKey) { p.style.filter = ''; if (label) label.style.filter = ''; } };
  const onClick = (ev) => {
    if (isDrag(ev)) return;  // tail of a drag-pan, not a real click
    ev.stopPropagation();
    hoverOff();  // drop the hover glow before (de)selecting, so it can't linger under HILITE
    if (scene.selectedKey === selKey) { resetScene(scene); return; }  // click again = deselect
    scene.selectedKey = selKey;
    showFn(); sceneSelect(scene, () => glowEdge(p, label)); focusEdge(scene, e);
  };
  scene.edgeEls.push({ e, path: p, label });
  attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff);
}

// Wire one edge to NAVIGATE on click (no in-scene selection) — subsystem-map arrows + cross arrows.
function bindNavEdge(p, label, onNavigate) {
  const hoverOn = () => { p.style.filter = HOVER; if (label) label.style.filter = HOVER; };
  const hoverOff = () => { p.style.filter = ''; if (label) label.style.filter = ''; };
  const onClick = (ev) => { if (isDrag(ev)) return; ev.stopPropagation(); hoverOff(); onNavigate(); };
  attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff);
}

// `resolve(match)` maps a path id (L_<src>_<dst>_<i>) to { e, selKey, showFn } or null to skip.
function bindEdges(scene, resolve) {
  eachEdge(scene.root, (p, label, m) => {
    const r = resolve(m);
    if (r) bindSelectEdge(scene, p, label, r.e, r.selKey, r.showFn);
  });
}

function resolveContextEdge(m) {
  const epKey = m[1] + '>' + m[2];
  const e = CONTEXT_EDGES[epKey];
  if (!e) return null;
  return { e, selKey: 'cedge:' + epKey, showFn: () => showContextEdge(e) };
}
function resolveComponentEdge(m) {
  const arr = COMP_LOOKUP[m[1] + '>' + m[2]];
  if (!arr) return null;
  const e = arr[Math.min(+m[3], arr.length - 1)];
  return { e, selKey: 'edge:' + e.src + '>' + e.dst, showFn: () => showEdge(e) };
}

// --- navigation history ---------------------------------------------------------
// A linear stack of view "states" (one per diagram-changing click); back/forward move the index.
// Selecting a node/edge for details is NOT a navigation — it only updates the side panel.
//   state = { kind: 'context' | 'container' | 'component' | 'subsystem' | 'edge', sid?, a?, b? }
let history = [];
let hi = -1;  // index of the current state

function stateKey(s) {
  return s.kind + (s.sid ? ':' + s.sid : '') + (s.a ? ':' + s.a + '>' + s.b : '');
}
function go(state) {
  if (hi >= 0 && stateKey(history[hi]) === stateKey(state)) return;  // already here
  history = history.slice(0, hi + 1);  // a new branch drops any forward history
  history.push(state);
  hi = history.length - 1;
  render();
}
function back() { if (hi > 0) { hi -= 1; render(); } }
function fwd() { if (hi < history.length - 1) { hi += 1; render(); } }
function jump(i) { if (i >= 0 && i < history.length && i !== hi) { hi = i; render(); } }

// --- per-state binding ----------------------------------------------------------
function bindContext() {
  bindNodes(mainScene, (id, el) => {
    if (id === 'SYS') { go({ kind: HAS_GROUPING ? 'container' : 'component' }); return; }  // drill in
    selectNode(mainScene, el, id);
  });
  bindEdges(mainScene, resolveContextEdge);
}
function bindComponent() {
  bindNodes(mainScene, (id, el) => selectNode(mainScene, el, id));
  bindEdges(mainScene, resolveComponentEdge);
}
function bindContainer() {  // subsystem boxes + inter-subsystem arrows both drill in
  bindNodes(mainScene, (id) => go({ kind: 'subsystem', sid: id }));
  eachEdge(diagram, (p, label, m) => {
    const a = m[1], b = m[2];
    if (GRAPH.nodes[a] && GRAPH.nodes[b]) bindNavEdge(p, label, () => go({ kind: 'edge', a, b }));
  });
}
function bindSubsystem(sid) {  // neighbourhood: component -> detail; neighbour box / cross arrow -> drill
  bindNodes(mainScene, (id, el) => {
    if (GRAPH.nodes[id].kind === 'subsystem') go({ kind: 'subsystem', sid: id });  // walk to the neighbour
    else selectNode(mainScene, el, id);
  });
  eachEdge(diagram, (p, label, m) => {
    const a = m[1], b = m[2];
    const aSub = GRAPH.nodes[a] && GRAPH.nodes[a].kind === 'subsystem';
    const bSub = GRAPH.nodes[b] && GRAPH.nodes[b].kind === 'subsystem';
    if (aSub || bSub) {  // cross arrow -> the pair's edge view, keeping direction
      const pa = aSub ? a : sid, pb = bSub ? b : sid;
      bindNavEdge(p, label, () => go({ kind: 'edge', a: pa, b: pb }));
    } else {
      const r = resolveComponentEdge(m);
      if (r) bindSelectEdge(mainScene, p, label, r.e, r.selKey, r.showFn);
    }
  });
}
function bindEdgePair() {  // both subsystems framed; arrows are component edges
  bindNodes(mainScene, (id, el) => selectNode(mainScene, el, id));
  bindEdges(mainScene, resolveComponentEdge);
}

// classDiagram (the Domain view) emits a different SVG shape than flowchart, so it gets its own
// node/edge finders. A class box's group id is `…-classId-E1-N` (resolved by idOf's id regex); a
// relation path's id is `…-id_E1_E2_N` (endpoints encoded). classDiagram emits several `.edgeLabel`
// per relation (verb twice + each cardinality), so index-pairing a label is unreliable — bind the
// path only (its wide hit-area is clickable); the label just won't glow.
function eachClassEdge(root, fn) {
  for (const p of root.querySelectorAll('path.relation, .edgePaths path, g.edgePath path')) {
    const m = (p.id || '').match(/[_-](E\d+)_(E\d+)(?:[_-]|$)/);
    if (m) fn(p, null, m[1], m[2]);
  }
}
function bindDomain() {
  mainScene.root.querySelectorAll('g.node, g.classGroup').forEach((el) => {
    const id = idOf(el);
    if (!id || !GRAPH.nodes[id] || mainScene.nodeEls[id]) return;
    mainScene.nodeEls[id] = el;
    el.style.cursor = 'pointer';
    el.addEventListener('mouseenter', () => { if (mainScene.selectedKey !== 'node:' + id) el.style.filter = HOVER; });
    el.addEventListener('mouseleave', () => { if (mainScene.selectedKey !== 'node:' + id) el.style.filter = ''; });
    el.addEventListener('click', (ev) => { if (isDrag(ev)) return; ev.stopPropagation(); selectNode(mainScene, el, id); });
  });
  eachClassEdge(mainScene.root, (p, label, src, dst) => {
    const arr = COMP_LOOKUP[src + '>' + dst];
    if (!arr) return;
    const e = arr[0];
    bindSelectEdge(mainScene, p, label, e, 'edge:' + e.src + '>' + e.dst, () => showEdge(e));
  });
}

// --- render ---------------------------------------------------------------------
function mermaidFor(s) {
  if (s.kind === 'context') return MERMAID_CONTEXT;
  if (s.kind === 'container') return MERMAID_CONTAINER;
  if (s.kind === 'subsystem') return MERMAID_BY_SUB[s.sid];
  if (s.kind === 'edge') return MERMAID_EDGE_CARD[s.a + '>' + s.b];
  if (s.kind === 'domain') return MERMAID_DOMAIN;
  return mode === 'diff' ? MERMAID_DIFF : MERMAID_BASE;  // component
}
function applyDefaultPanel(s) {
  if (s.kind === 'subsystem') showNode(s.sid);
  else if (s.kind === 'edge') showTwoSubsystems(s.a, s.b);
  else panel.innerHTML = EMPTY_PANEL;
}
function bindFor(s) {
  if (s.kind === 'context') bindContext();
  else if (s.kind === 'container') bindContainer();
  else if (s.kind === 'subsystem') bindSubsystem(s.sid);
  else if (s.kind === 'edge') bindEdgePair();
  else if (s.kind === 'domain') bindDomain();
  else bindComponent();
}
function topView(kind) {  // which top-level button a state lives under (container/subsystem/edge → Subsystems)
  if (kind === 'context' || kind === 'component' || kind === 'domain') return kind;
  return 'container';
}
function stateTitle(s) {
  if (s.kind === 'context') return 'Context';
  if (s.kind === 'container') return 'Subsystems';
  if (s.kind === 'component') return 'Components';
  if (s.kind === 'domain') return 'Domain';
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  if (s.kind === 'subsystem') return nm(s.sid);
  return nm(s.a) + ' → ' + nm(s.b);  // edge
}
function renderChrome(s) {
  legend.classList.toggle('on', s.kind === 'component' && mode === 'diff');
  toggle.style.display = (HAS_DIFF && s.kind === 'component') ? '' : 'none';
  toggle.textContent = mode === 'diff' ? 'Show baseline' : 'Show diff';
  const tv = topView(s.kind);
  viewsw.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.view === tv));
  navback.disabled = hi <= 0;
  navfwd.disabled = hi >= history.length - 1;
  // breadcrumb: the trail taken to get here (history[0..hi]); each earlier crumb jumps back to it
  crumb.innerHTML = '';
  for (let i = 0; i <= hi; i += 1) {
    if (i) crumb.appendChild(document.createTextNode(' › '));
    const cur = i === hi;
    const seg = document.createElement(cur ? 'span' : 'a');
    seg.className = 'crumbseg' + (cur ? ' cur' : '');
    seg.textContent = stateTitle(history[i]);
    if (!cur) seg.addEventListener('click', () => jump(i));
    crumb.appendChild(seg);
  }
}

async function render() {
  const seq = ++renderSeq;
  if (mainPz) { mainPz.destroy(); mainPz = null; }
  const s = history[hi];
  const { svg } = await mermaid.render('coyodexGraph' + (rc++), mermaidFor(s));
  if (seq !== renderSeq) return;  // a newer render started during the async layout — drop this stale one
  diagram.innerHTML = svg;
  mainScene = makeScene(diagram, () => applyDefaultPanel(s));
  bindFor(s);
  applyDefaultPanel(s);
  const svgEl = diagram.querySelector('svg');
  if (svgEl && window.svgPanZoom) {
    svgEl.removeAttribute('style');
    mainPz = svgPanZoom(svgEl, { controlIcons: true, fit: true, center: true, minZoom: 0.3, maxZoom: 8 });
  }
  if (svgEl) svgEl.addEventListener('click', (e) => { if (!isDrag(e)) resetScene(mainScene); });  // empty space deselects
  renderChrome(s);
}

// --- startup --------------------------------------------------------------------
stage.addEventListener('mousedown', (e) => { downX = e.clientX; downY = e.clientY; }, true);
document.addEventListener('keydown', (e) => {
  // ⌘/⌥ + ←/→ navigate history (preventDefault so ⌘+arrows don't trigger the browser's back/forward)
  if ((e.metaKey || e.altKey) && e.key === 'ArrowLeft') { e.preventDefault(); back(); return; }
  if ((e.metaKey || e.altKey) && e.key === 'ArrowRight') { e.preventDefault(); fwd(); return; }
  if (e.key === 'Escape' && mainScene) resetScene(mainScene);
});
buildLegend();
viewsw.querySelectorAll('button').forEach((b) => {
  if (b.dataset.view === 'container' && !HAS_GROUPING) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'domain' && !HAS_DOMAIN) { b.style.display = 'none'; return; }
  b.addEventListener('click', () => go({ kind: b.dataset.view }));
});
navback.addEventListener('click', back);
navfwd.addEventListener('click', fwd);
if (HAS_DIFF) {
  toggle.addEventListener('click', () => { mode = mode === 'diff' ? 'base' : 'diff'; render(); });
}
go({ kind: 'context' });  // start high (C4 Context); drill down from there
