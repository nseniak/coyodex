// `mermaid` is the global from the SRI-pinned UMD <script> in <head>.

const GRAPH = __GRAPH_JSON__;
const MERMAID_BASE = __MERMAID_BASE__;
const MERMAID_DIFF = __MERMAID_DIFF__;
const MERMAID_CONTEXT = __MERMAID_CONTEXT__;
const MERMAID_CONTAINER = __MERMAID_CONTAINER__;
const MERMAID_BY_SUB = __MERMAID_BY_SUB__;        // subsystem card: sid -> component sub-diagram
const MERMAID_EDGE_CARD = __MERMAID_EDGE_CARD__;  // edge card: 'A>B' -> two-subsystem sub-diagram
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
const DIM = '0.15';  // opacity for non-focused elements
const EMPTY_PANEL = '<p class="empty">Click a node or edge to see details.</p>';

mermaid.initialize({ startOnLoad: false, securityLevel: 'loose', theme: 'default', flowchart: { curve: 'basis' } });

const diagram = document.getElementById('diagram');
const stage = document.getElementById('stage');
const panel = document.getElementById('panel');
const legend = document.getElementById('legend');
const toggle = document.getElementById('toggle');
const viewsw = document.getElementById('viewsw');
document.getElementById('meta').innerHTML = META;
const stripMd = (s) => (s || '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
const esc = (s) => (s || '').replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));

let mode = 'base';
let view = 'context';  // start high (C4 Context); drill Context → Subsystems → Components
let mainPz = null;     // svg-pan-zoom for the main diagram
let cardPz = null;     // svg-pan-zoom for the floating card (null when no card is open)
let rc = 0;
let renderSeq = 0;     // bumped each render(); an in-flight render/card-open bails if it's stale
let downX = 0, downY = 0;  // last mousedown, to tell a real click from a drag-pan

// Component-edge lookup '<src>><dst>' -> [edges]; static (GRAPH.edges never changes). Shared by the
// Components view and the cards, so an in-card arrow resolves to its real component edge.
const COMP_LOOKUP = {};
for (const e of GRAPH.edges || []) (COMP_LOOKUP[e.src + '>' + e.dst] ||= []).push(e);

// --- scenes ---------------------------------------------------------------------
// A "scene" is one interactive diagram (the main map, or a card): its root element, the bound
// node/edge elements, the current selection, and what the side panel shows when nothing is selected.
// Focus/select/reset all operate on a scene, so the main map and a card never fight over state.
let mainScene = null;  // the main diagram's scene
let cardScene = null;  // the open card's scene, or null

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
  const src = n.file ? `<div class="src">${n.file}${n.line ? ':' + n.line : ''}</div>` : '';
  panel.innerHTML = `<h2>${id} · ${n.name}</h2>`
    + `<div class="badges"><span class="badge kind">${n.kind}</span>${chg}</div>`
    + `<dl>${rows}</dl>${src}`;
}

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

// Subsystems-view edge: an inter-subsystem arrow connects two subsystems. The panel shows both
// (name + Purpose); the concrete A→B wiring lives in the edge card the click also opens.
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

// --- shared binding (the select/focus model: context + components + cards) -------
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
    scene.nodeEls[id] = el;
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

// Give an edge's visible path a wide transparent hit-path + make its label clickable. Shared by
// the select-model edges (bindEdges) and the container base map (which opens cards instead).
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

// Edges in the select model: paths and labels are emitted in the same order, so zip them by index.
// `resolve(match)` maps a path id (L_<src>_<dst>_<i>) to { e, selKey, showFn } or null to skip.
function bindEdges(scene, resolve) {
  const paths = [...scene.root.querySelectorAll('.edgePaths path.flowchart-link')];
  const labels = [...scene.root.querySelectorAll('.edgeLabels > g.edgeLabel')];
  paths.forEach((p, i) => {
    const m = p.id.match(/L_([^_]+)_([^_]+)_(\d+)$/);
    if (!m) return;
    const r = resolve(m);
    if (!r) return;
    const { e, selKey, showFn } = r;
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
    const hoverOn = () => { if (scene.selectedKey === selKey) return; p.style.filter = HOVER; if (label) label.style.filter = HOVER; };
    const hoverOff = () => { if (scene.selectedKey === selKey) return; p.style.filter = ''; if (label) label.style.filter = ''; };
    const onClick = (ev) => {
      if (isDrag(ev)) return;  // tail of a drag-pan, not a real click
      ev.stopPropagation();
      hoverOff();  // drop the hover glow before (de)selecting, so it can't linger under HILITE
      if (scene.selectedKey === selKey) { resetScene(scene); return; }  // click again = deselect
      scene.selectedKey = selKey;
      showFn(); sceneSelect(scene, highlight); focusEdge(scene, e);
    };
    scene.edgeEls.push({ e, path: p, label });
    attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff);
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

function mainNodeActivate(id, el) {
  if (id === 'SYS') { setView(HAS_GROUPING ? 'container' : 'component'); return; }  // drill: Context → Subsystems
  selectNode(mainScene, el, id);
}

// --- Subsystems base map: click a box/arrow to open a floating card -------------
// This map never re-lays-out. A box opens its subsystem card; an arrow opens the A→B edge card.
// The clicked element glows while its card is open — no connector is drawn, so nothing to keep in
// sync as the map pans/zooms.
let openCardKey = null;     // 'sub:<sid>' | 'edge:<a>><b>' | null
let baseGlowCleanup = null; // removes the glow on the base-map source element

function glowNode(el) { el.style.filter = HILITE; return () => { el.style.filter = ''; }; }
function glowEdge(p, label) {
  p.style.setProperty('stroke', '#2563eb', 'important');
  p.style.setProperty('stroke-width', '3px', 'important');
  if (label) label.style.filter = HILITE;
  return () => {
    p.style.removeProperty('stroke'); p.style.removeProperty('stroke-width');
    if (label) label.style.filter = '';
  };
}

function bindContainerBase() {
  // subsystem boxes -> open/toggle their subsystem card
  diagram.querySelectorAll('g.node').forEach((el) => {
    const id = idOf(el);
    if (!id || !GRAPH.nodes[id] || GRAPH.nodes[id].kind !== 'subsystem') return;
    el.style.cursor = 'pointer';
    el.addEventListener('mouseenter', () => { if (openCardKey !== 'sub:' + id) el.style.filter = HOVER; });
    el.addEventListener('mouseleave', () => { if (openCardKey !== 'sub:' + id) el.style.filter = ''; });
    el.addEventListener('click', (e) => {
      if (isDrag(e)) return;
      e.stopPropagation();
      toggleSubsystemCard(id, el);
    });
  });
  // inter-subsystem arrows -> open/toggle the A→B edge card
  const paths = [...diagram.querySelectorAll('.edgePaths path.flowchart-link')];
  const labels = [...diagram.querySelectorAll('.edgeLabels > g.edgeLabel')];
  paths.forEach((p, i) => {
    const m = p.id.match(/L_([^_]+)_([^_]+)_(\d+)$/);
    if (!m) return;
    const a = m[1], b = m[2];
    if (!GRAPH.nodes[a] || !GRAPH.nodes[b]) return;
    const label = labels[i] || null;
    const key = 'edge:' + a + '>' + b;
    const hoverOn = () => { if (openCardKey !== key) { p.style.filter = HOVER; if (label) label.style.filter = HOVER; } };
    const hoverOff = () => { if (openCardKey !== key) { p.style.filter = ''; if (label) label.style.filter = ''; } };
    const onClick = (ev) => { if (isDrag(ev)) return; ev.stopPropagation(); hoverOff(); toggleEdgeCard(a, b, p, label); };
    attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff);
  });
}

// --- floating cards -------------------------------------------------------------
function closeCard() {
  if (cardPz) { cardPz.destroy(); cardPz = null; }
  if (baseGlowCleanup) { baseGlowCleanup(); baseGlowCleanup = null; }
  const host = document.getElementById('card');
  if (host) host.remove();
  cardScene = null;
  openCardKey = null;
  panel.innerHTML = EMPTY_PANEL;
}

// Render `mermaidText` into a floating card over the frozen base map. The card is its own scene
// (Components-view interactions inside), with its own pan/zoom; `glowCleanup` un-glows the source.
async function openCard(key, title, mermaidText, defaultPanel, glowCleanup) {
  closeCard();
  openCardKey = key;
  baseGlowCleanup = glowCleanup;
  const host = document.createElement('div');
  host.id = 'card';
  host.innerHTML = '<div class="card-head"><span class="card-title"></span>'
    + '<button class="card-close" title="Close (Esc)">×</button></div><div class="card-body"></div>';
  host.querySelector('.card-title').textContent = title;
  host.querySelector('.card-close').addEventListener('click', (e) => { e.stopPropagation(); closeCard(); });
  stage.appendChild(host);
  const body = host.querySelector('.card-body');
  const { svg } = await mermaid.render('coyodexCard' + (rc++), mermaidText);
  // A newer card opened (different key) or the card was closed during the async render. Our `host`
  // was already detached by that closeCard(), so just drop this stale continuation — otherwise we'd
  // build a scene + svg-pan-zoom on a detached node and leak the pan-zoom instance.
  if (openCardKey !== key) return;
  body.innerHTML = svg;
  cardScene = makeScene(body, defaultPanel);
  bindNodes(cardScene, (cid, cel) => selectNode(cardScene, cel, cid));
  bindEdges(cardScene, resolveComponentEdge);  // in-card arrows behave like Components-view edges
  defaultPanel();
  const svgEl = body.querySelector('svg');
  if (svgEl && window.svgPanZoom) {
    svgEl.removeAttribute('style');
    cardPz = svgPanZoom(svgEl, { controlIcons: true, fit: true, center: true, minZoom: 0.3, maxZoom: 8 });
    svgEl.addEventListener('click', (e) => { if (!isDrag(e)) resetScene(cardScene); });  // empty card space deselects
  }
}

function toggleSubsystemCard(id, el) {
  if (openCardKey === 'sub:' + id) { closeCard(); return; }
  const mm = MERMAID_BY_SUB[id];
  if (!mm) return;
  const n = GRAPH.nodes[id];
  openCard('sub:' + id, n.id + ' · ' + n.name, mm, () => showNode(id), glowNode(el));
}

function toggleEdgeCard(a, b, p, label) {
  const key = 'edge:' + a + '>' + b;
  if (openCardKey === key) { closeCard(); return; }
  const mm = MERMAID_EDGE_CARD[a + '>' + b];
  if (!mm) return;
  const title = GRAPH.nodes[a].name + ' → ' + GRAPH.nodes[b].name;
  openCard(key, title, mm, () => showTwoSubsystems(a, b), glowEdge(p, label));
}

// --- render ---------------------------------------------------------------------
function setView(v) { if (v !== view) { view = v; render(); } }

async function render() {
  const seq = ++renderSeq;
  closeCard();
  if (mainPz) { mainPz.destroy(); mainPz = null; }
  let text;
  if (view === 'context') text = MERMAID_CONTEXT;
  else if (view === 'container') text = MERMAID_CONTAINER;
  else text = (mode === 'diff' ? MERMAID_DIFF : MERMAID_BASE);
  const { svg } = await mermaid.render('coyodexGraph' + (rc++), text);
  if (seq !== renderSeq) return;  // a newer render started during the async layout — drop this stale one
  diagram.innerHTML = svg;
  mainScene = makeScene(diagram, () => { panel.innerHTML = EMPTY_PANEL; });
  if (view === 'container') {
    bindContainerBase();  // boxes/arrows open cards; the base map itself has no selection
  } else {
    bindNodes(mainScene, mainNodeActivate);
    bindEdges(mainScene, view === 'context' ? resolveContextEdge : resolveComponentEdge);
  }
  const svgEl = diagram.querySelector('svg');
  if (svgEl && window.svgPanZoom) {
    svgEl.removeAttribute('style');
    mainPz = svgPanZoom(svgEl, { controlIcons: true, fit: true, center: true, minZoom: 0.3, maxZoom: 8 });
  }
  // empty-space click: close an open card if any, else clear the main selection (ignore drag tails)
  if (svgEl) svgEl.addEventListener('click', (e) => {
    if (isDrag(e)) return;
    if (cardScene) closeCard(); else resetScene(mainScene);
  });
  legend.classList.toggle('on', view === 'component' && mode === 'diff');
  toggle.style.display = (HAS_DIFF && view === 'component') ? '' : 'none';
  toggle.textContent = mode === 'diff' ? 'Show baseline' : 'Show diff';
  viewsw.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.view === view));
  const crumb = document.getElementById('crumb');
  crumb.innerHTML = (view === 'container')
    ? ' · click a subsystem to see its parts · click an arrow to see how two subsystems connect'
    : '';
}

// Track mousedown on the whole stage (capture phase) so the drag-vs-click test works for both the
// base map and a floating card.
stage.addEventListener('mousedown', (e) => { downX = e.clientX; downY = e.clientY; }, true);
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  if (cardScene) closeCard(); else if (mainScene) resetScene(mainScene);
});
buildLegend();
viewsw.querySelectorAll('button').forEach((b) => {
  if (b.dataset.view === 'container' && !HAS_GROUPING) { b.style.display = 'none'; return; }
  b.addEventListener('click', () => setView(b.dataset.view));
});
if (HAS_DIFF) {
  toggle.addEventListener('click', () => { mode = mode === 'diff' ? 'base' : 'diff'; render(); });
}
await render();
