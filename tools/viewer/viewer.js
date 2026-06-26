// `mermaid` is the global from the SRI-pinned UMD <script> in <head>.

const GRAPH = __GRAPH_JSON__;
const MERMAID_BASE = __MERMAID_BASE__;
const MERMAID_DIFF = __MERMAID_DIFF__;
const MERMAID_CONTEXT = __MERMAID_CONTEXT__;
const MERMAID_CONTAINER = __MERMAID_CONTAINER__;
const MERMAID_BY_SUB = __MERMAID_BY_SUB__;        // subsystem neighbourhood: sid -> sub-diagram
const MERMAID_EDGE_CARD = __MERMAID_EDGE_CARD__;  // edge pair: 'A>B' -> two-subsystem sub-diagram
const CONTAINER_EDGES = __CONTAINER_EDGES__;      // inter-subsystem arrow 'A>B' -> [crossing component edges]
const MERMAID_DOMAIN = __MERMAID_DOMAIN__;        // T5 domain model as a classDiagram
const MERMAID_GP = __MERMAID_GP__;                // Golden Path (Level 1): black-box sequence diagram
const MERMAID_GP_STEP = __MERMAID_GP_STEP__;      // GP step (Level 2): GP-id -> components-used sub-diagram
const GP_ACTORS = __GP_ACTORS__;                  // Golden-Path lifelines: [{aid,name,kind,wants,steps,stepIdx}]
const HAS_GROUPING = __HAS_GROUPING__;
const HAS_DOMAIN = __HAS_DOMAIN__;
const HAS_GP = __HAS_GP__;
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
const GP_SEL = 'drop-shadow(0 0 4px #3b82f6)';  // Golden-Path selection: just a touch stronger than HOVER (not the heavy HILITE)
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
const tip = document.getElementById('tip');
const zoomin = document.getElementById('zoomin');
const zoomout = document.getElementById('zoomout');
const zoomlevel = document.getElementById('zoomlevel');
const drillhint = document.getElementById('drillhint');
document.getElementById('meta').innerHTML = META;
const esc = (s) => (s || '').replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
// Inline markdown -> safe HTML for prose fields (Purpose / Why / Wants / …): a link collapses to its
// text, then we ESCAPE, then wrap `code` and **bold** — escape-first so the only tags are the ones we
// add. Pragmatic, not a full parser: `code` is wrapped before **bold**, so a code span matches first.
const mdInline = (s) => esc(String(s || '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1'))
  .replace(/`([^`]+)`/g, '<code>$1</code>')
  .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

let mode = 'base';
let mainPz = null;     // svg-pan-zoom for the current diagram
let rc = 0;
let renderSeq = 0;     // bumped each render(); an in-flight render bails if it's no longer current
let downX = 0, downY = 0;  // last mousedown, to tell a real click from a drag-pan

// Component-edge lookup '<src>><dst>' -> [edges]; static (GRAPH.edges never changes). Shared by the
// Components view and the drilled diagrams, so an arrow resolves to its real component edge.
const COMP_LOOKUP = {};
for (const e of GRAPH.edges || []) (COMP_LOOKUP[e.src + '>' + e.dst] ||= []).push(e);

// Golden Path step lookup 'GP1' -> step record (id, title, story, under_the_hood, touches, uc).
const GP_BY_ID = {};
for (const s of GRAPH.gp || []) GP_BY_ID[s.id] = s;
// Golden Path actor lookups: by participant id (GPA0) and by the step it drives (GP1 -> actor record).
const GP_ACTOR_BY_AID = {};
for (const a of GP_ACTORS) GP_ACTOR_BY_AID[a.aid] = a;
const GP_ACTOR_OF_STEP = {};
for (const a of GP_ACTORS) for (const st of a.steps) GP_ACTOR_OF_STEP[st.id] = a;

// When the GP-step panel's "Locate in full map" link navigates to the Components view, the set of ids
// to spotlight there is stashed here and applied once that view has rendered (then cleared).
let pendingFocus = null;

// --- scene ----------------------------------------------------------------------
// A "scene" wraps the diagram currently shown: its root, the bound node/edge elements, the active
// selection, and what the side panel shows when nothing is selected. There's one scene at a time;
// it's rebuilt on every render. Focus/select/reset all operate on it.
let mainScene = null;

function makeScene(root, defaultPanel) {
  // dimEls: a flat list of extra focusable elements (the Golden Path's actor figures, lifelines and
  // message text/lines) that the standard node/edge focus model doesn't cover — dimmed/restored together.
  return { root, nodeEls: {}, edgeEls: [], dimEls: [], gpLit: new Set(), selectedKey: null, clearHighlight: null, defaultPanel };
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
  for (const el of scene.dimEls) el.style.opacity = '';
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
// A ⌘-click (⌃-click off Mac) — the modifier that turns a select into a drill-in on subsystems/arrows.
function isDrillClick(e) { return !!e && (e.metaKey || e.ctrlKey); }

// --- side panel -----------------------------------------------------------------
function showNode(id) {
  const n = GRAPH.nodes[id];
  if (!n) return;
  const chg = n.change ? `<span class="badge ${n.change}">${n.change}</span>` : '';
  const rows = Object.entries(n.fields || {})
    // a subsystem's first field IS its name (already in the title) — don't repeat it
    .filter(([k]) => !(n.kind === 'subsystem' && k.toLowerCase() === 'subsystem'))
    .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${mdInline(v)}</dd>`).join('');
  // entity attributes (T5 domain cards): `type name` + any markers (PK/FK/unique/…)
  const attrs = (n.attrs && n.attrs.length)
    ? '<dt>Fields</dt><dd>' + n.attrs.map((a) => {
        const ty = (a.type && GRAPH.nodes[a.type]) ? GRAPH.nodes[a.type].name : a.type;  // embedded entity id -> name
        return esc(((ty ? ty + ' ' : '') + (a.name || '') + (a.markers ? '  ·  ' + a.markers : '')).trim());
      }).join('<br>') + '</dd>'
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
  // How the relation is implemented: the backing field (resolved in build_graph; `↩`-named when it
  // lives on the target/head), else the authored `{how}` note for a field-less / indirect relation.
  const impl = e.fk_field
    ? esc((e.fk_side === 'dst' ? nm(e.dst) : nm(e.src)) + '.' + e.fk_field)
      + (e.fk_side === 'dst' ? ' <span class="muted">(back-reference)</span>' : '')
    : (e.how ? mdInline(e.how) : '');
  const implRow = impl ? '<dt>Implemented by</dt><dd>' + impl + '</dd>' : '';
  panel.innerHTML = '<h2>' + esc(nm(e.src)) + ' → ' + esc(nm(e.dst)) + '</h2>'
    + '<div class="badges"><span class="badge edge">' + esc(e.verb) + '</span>' + kindBadge + '</div>'
    + '<dl>'
    + (e.why ? '<dt>Why</dt><dd>' + mdInline(e.why) + '</dd>' : '')
    + card
    + implRow
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
    body = ce.wants ? '<dt>Wants</dt><dd>' + mdInline(ce.wants) + '</dd>' : '';
  } else {
    const rows = (ce.realizedBy || []).map((r) =>
      '<dd>• ' + esc(r.srcName) + ' — ' + esc(r.verb) + (r.why ? ' — ' + mdInline(r.why) : '') + '</dd>').join('');
    body = (ce.usedFor ? '<dt>Used for</dt><dd>' + mdInline(ce.usedFor) + '</dd>' : '')
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
    + (purpose ? '<dl><dt>Purpose</dt><dd>' + mdInline(purpose) + '</dd></dl>' : '');
}
function showTwoSubsystems(a, b) {
  panel.innerHTML = '<div class="badges"><span class="badge edge">connection</span></div>'
    + subsystemBlock(a) + '<hr>' + subsystemBlock(b);
}
// Selecting (not drilling) a Subsystems arrow: list every component→component crossing it bundles as
// `from → to:` with its explanation indented below — one uniform font, no verb — so the wiring is
// readable without leaving the map.
function showContainerEdge(a, b) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  const list = CONTAINER_EDGES[a + '>' + b] || [];
  const items = list.map((r) =>
    '<li><div class="xpair">' + esc(r.srcName) + ' → ' + esc(r.dstName) + ':</div>'
    + (r.why ? '<div class="xwhy">' + mdInline(r.why) + '</div>' : '') + '</li>').join('');
  panel.innerHTML = '<h2>' + esc(nm(a)) + ' → ' + esc(nm(b)) + '</h2>'
    + '<div class="xcount">' + list.length + ' connection' + (list.length === 1 ? '' : 's') + '</div>'
    + (items ? '<ul class="xlist">' + items + '</ul>' : '<p class="empty">no connections recorded</p>');
}

// --- Golden Path panels ---------------------------------------------------------
// The C/D/E ids a step touches that actually exist as graph nodes — the Level-2 subgraph + spotlight set.
function gpTouched(s) {
  return new Set((s && s.touches || []).filter((t) => GRAPH.nodes[t]
    && ['component', 'dep', 'entity'].includes(GRAPH.nodes[t].kind)));
}
// Level-1 default panel: the Golden Path at a glance; the diagram is where you click a step.
function showGPOverview() {
  const n = (GRAPH.gp || []).length;
  panel.innerHTML = '<h2>Golden Path</h2>'
    + '<div class="badges"><span class="badge kind">' + n + ' step' + (n === 1 ? '' : 's') + '</span></div>'
    + '<p class="empty">Click a step to see the components it uses.</p>';
}
// One step's narrative (actor · story · under the hood) + a link back to the full Components map with
// this step's touched nodes spotlighted. Used as the Level-2 default panel AND when a step is selected
// at Level 1, so a plain click reads the same detail without drilling. The driving actor comes from
// GP_ACTOR_OF_STEP (the same mapping that builds the diagram), so it always matches the lifeline.
function showGPStep(gpId) {
  const s = GP_BY_ID[gpId];
  if (!s) { panel.innerHTML = EMPTY_PANEL; return; }
  const actor = (GP_ACTOR_OF_STEP[gpId] || {}).name || '';
  panel.innerHTML = '<h2>' + esc(s.id) + ' · ' + esc(s.title) + '</h2>'
    + '<div class="badges">' + (s.uc ? '<span class="badge kind">' + esc(s.uc) + '</span>' : '')
      + (actor ? '<span class="badge edge">' + esc(actor) + '</span>' : '') + '</div>'
    + '<dl>'
    + (s.story ? '<dt>Story</dt><dd>' + mdInline(s.story) + '</dd>' : '')
    + (s.under_the_hood ? '<dt>Under the hood</dt><dd>' + mdInline(s.under_the_hood) + '</dd>' : '')
    + '</dl>'
    + '<a class="locate" href="#">Locate in full map →</a>';
  const link = panel.querySelector('.locate');
  if (link) link.addEventListener('click', (ev) => { ev.preventDefault(); pendingFocus = gpTouched(s); go({ kind: 'component' }); });
}
// One actor's card: its kind, what its role wants (the explanation), and the Golden Path steps it drives.
function showGPActor(a) {
  const kindBadge = a.kind ? '<span class="badge kind">' + esc(a.kind) + '</span>' : '';
  const drives = (a.steps || []).map((st) =>
    '<dd>' + esc(st.id) + (st.title ? ' — ' + esc(st.title) : '') + '</dd>').join('');
  panel.innerHTML = '<h2>' + esc(a.name) + '</h2>'
    + '<div class="badges">' + kindBadge + '</div>'
    + '<dl>'
    + (a.wants ? '<dt>Wants</dt><dd>' + mdInline(a.wants) + '</dd>' : '')
    + (drives ? '<dt>Drives</dt>' + drives : '')
    + '</dl>';
}

// --- hover tooltip --------------------------------------------------------------
// A floating card that previews an element's MEANING on hover, so you can read it without
// selecting (selecting is what fills the side panel). One reused <div id="tip">; pointer-events:none
// in CSS so it never steals the hover or the click. All graph text goes through esc().
const MEANING_KEYS = ['purpose', 'used for', 'meaning', 'wants'];  // the per-kind "meaning" column, by priority
function meaningOf(n) {
  const f = n.fields || {};
  for (const want of MEANING_KEYS)
    for (const k in f)
      if (k.toLowerCase() === want && String(f[k]).trim()) return String(f[k]);  // raw; rendered by mdInline in the builder
  return null;
}
function tipNodeHtml(id) {
  const n = GRAPH.nodes[id];
  if (!n) return '';
  const meaning = meaningOf(n);
  // A subsystem box already prints its name, and you only hover one inside the Subsystems view,
  // so the name + "subsystem" tag are redundant — show just the explanatory text (nothing if none).
  if (n.kind === 'subsystem')
    return meaning ? '<div class="tm">' + mdInline(meaning) + '</div>' : '';
  return '<div class="tt">' + esc(n.name) + '</div><div class="tk">' + esc(n.kind) + '</div>'
    + (meaning ? '<div class="tm">' + mdInline(meaning) + '</div>'
               : '<div class="tn">no description recorded</div>');
}
function tipEdgeHtml(e) {
  // context edges (actor→system / system→dep) carry from/to + wants/usedFor under the verb "uses";
  // component/domain edges carry src/dst + verb + why.
  if (e.type === 'actor' || e.type === 'dep') {
    const meaning = e.type === 'actor' ? e.wants : e.usedFor;
    return '<div class="tt">' + esc(e.from) + ' → ' + esc(e.to) + '</div><div class="tk">uses</div>'
      + (meaning ? '<div class="tm">' + mdInline(meaning) + '</div>'
                 : '<div class="tn">no description recorded</div>');
  }
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  return '<div class="tt">' + esc(nm(e.src)) + ' → ' + esc(nm(e.dst)) + '</div>'
    + '<div class="tk">' + esc(e.verb) + '</div>'
    + (e.why ? '<div class="tm">' + mdInline(e.why) + '</div>'
             : '<div class="tn">no why recorded</div>');
}
// Hover an inter-subsystem arrow (Subsystems view) -> just the explanation (Why) of every
// component→component edge it aggregates. You're already on that arrow, so no subsystem/component
// names: a single link reads as plain text, several as a bullet list. Capped so a busy pair stays legible.
const TIP_EDGE_CAP = 14;
function tipContainerEdgeHtml(a, b) {
  const list = CONTAINER_EDGES[a + '>' + b] || [];
  const whys = list.map((r) => r.why).filter((w) => w && String(w).trim());
  if (!whys.length) return '<div class="tn">no description recorded</div>';
  const shown = whys.slice(0, TIP_EDGE_CAP);
  const more = whys.length > TIP_EDGE_CAP
    ? '<div class="tn">+' + (whys.length - TIP_EDGE_CAP) + ' more…</div>' : '';
  if (shown.length === 1) return '<div class="tm">' + mdInline(shown[0]) + '</div>' + more;
  return '<ul class="tl">' + shown.map((w) => '<li>' + mdInline(w) + '</li>').join('') + '</ul>' + more;
}
function tipGPHtml(gpId) {  // hover a GP step (message) -> just its story (the explanation), like a subsystem tip
  const s = GP_BY_ID[gpId];
  if (!s) return '';
  return s.story ? '<div class="tm">' + mdInline(s.story) + '</div>'
                 : '<div class="tn">no story recorded</div>';
}
function tipGPActorHtml(a) {  // hover an actor / its lifeline -> just what its role wants (the explanation)
  return a && a.wants ? '<div class="tm">' + mdInline(a.wants) + '</div>'
                      : '<div class="tn">no description recorded</div>';
}
function moveTip(x, y) {  // below-right of the cursor; flip toward the cursor if it would overflow the viewport
  const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
  let nx = x + pad, ny = y + pad;
  if (nx + w > window.innerWidth - 6) nx = x - pad - w;
  if (ny + h > window.innerHeight - 6) ny = y - pad - h;
  tip.style.left = Math.max(6, nx) + 'px';
  tip.style.top = Math.max(6, ny) + 'px';
}
function showTip(html, x, y) { if (!html) return; tip.innerHTML = html; tip.classList.add('on'); moveTip(x, y); }
function hideTip() { tip.classList.remove('on'); }
// Wire an element to preview `htmlFn()` while hovered — added alongside the existing glow handlers.
function attachTip(el, htmlFn) {
  el.addEventListener('mouseenter', (ev) => showTip(htmlFn(), ev.clientX, ev.clientY));
  el.addEventListener('mousemove', (ev) => moveTip(ev.clientX, ev.clientY));
  el.addEventListener('mouseleave', hideTip);
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
  // Dim to this node's neighbourhood only when the node is drawn in this scene; a box that isn't
  // registered (e.g. a neighbourhood's external subsystem) would otherwise dim everything around it.
  if (scene.nodeEls[id]) focusNode(scene, id); else clearFocus(scene);
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
    attachTip(el, () => tipNodeHtml(id));  // hover -> meaning preview (no selection needed)
    el.addEventListener('click', (e) => {
      if (isDrag(e)) return;  // tail of a drag-pan, not a real click
      e.stopPropagation();
      onActivate(id, el, e);
    });
    if (mode === 'diff' && DIFF_STATE[id]) addBadge(el, DIFF_STATE[id]);
  });
}

// Give an edge's visible path a wide transparent hit-path + make its label clickable.
// `tipHtml` (optional) wires a hover meaning-preview on the same hit-area + label.
function attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff, tipHtml, drillable) {
  const hit = p.cloneNode(false);
  hit.removeAttribute('id'); hit.removeAttribute('marker-end'); hit.removeAttribute('class');
  hit.style.setProperty('stroke', 'transparent', 'important');
  hit.style.setProperty('stroke-width', '14px', 'important');
  hit.style.setProperty('fill', 'none', 'important');
  hit.style.setProperty('marker-end', 'none', 'important');
  hit.style.pointerEvents = 'stroke'; hit.style.cursor = 'pointer';
  if (drillable) hit.classList.add('drill');  // ⌘-held cursor affordance
  hit.addEventListener('click', onClick);
  hit.addEventListener('mouseenter', hoverOn);
  hit.addEventListener('mouseleave', hoverOff);
  p.parentNode.appendChild(hit);
  if (label) {
    label.style.cursor = 'pointer';
    label.style.setProperty('pointer-events', 'all', 'important');
    if (drillable) label.classList.add('drill');
    label.addEventListener('click', onClick);
    label.addEventListener('mouseenter', hoverOn);
    label.addEventListener('mouseleave', hoverOff);
  }
  if (tipHtml) { attachTip(hit, tipHtml); if (label) attachTip(label, tipHtml); }
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
// `opts.onDrill` (optional) makes a ⌘-click drill instead of select, and marks the arrow with the
// drill cursor; `opts.tipFn` overrides the hover preview (defaults to the plain edge tip).
function bindSelectEdge(scene, p, label, e, selKey, showFn, opts) {
  opts = opts || {};
  const hoverOn = () => { if (scene.selectedKey !== selKey) { p.style.filter = HOVER; if (label) label.style.filter = HOVER; } };
  const hoverOff = () => { if (scene.selectedKey !== selKey) { p.style.filter = ''; if (label) label.style.filter = ''; } };
  const onClick = (ev) => {
    if (isDrag(ev)) return;  // tail of a drag-pan, not a real click
    ev.stopPropagation();
    if (opts.onDrill && isDrillClick(ev)) { hoverOff(); opts.onDrill(); return; }  // ⌘-click drills in
    hoverOff();  // drop the hover glow before (de)selecting, so it can't linger under HILITE
    if (scene.selectedKey === selKey) { resetScene(scene); return; }  // click again = deselect
    scene.selectedKey = selKey;
    showFn(); sceneSelect(scene, () => glowEdge(p, label));
    // Dim to the edge only when its endpoints are drawn here; an aggregated arrow whose ends aren't
    // (e.g. a neighbourhood's cross arrow) would otherwise dim the whole view.
    if (scene.nodeEls[e.src] || scene.nodeEls[e.dst]) focusEdge(scene, e); else clearFocus(scene);
  };
  scene.edgeEls.push({ e, path: p, label });
  attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff, opts.tipFn || (() => tipEdgeHtml(e)), !!opts.onDrill);
}

// An inter-subsystem arrow (Subsystems map + neighbourhood cross arrows): a plain click SELECTS it —
// the sidebar lists every component→component crossing it bundles — and a ⌘-click drills into the
// two-subsystem edge view. Reuses the select-edge machinery with a container-edge panel + tip.
function bindContainerEdge(scene, p, label, a, b) {
  bindSelectEdge(scene, p, label, { src: a, dst: b }, 'sedge:' + a + '>' + b,
    () => showContainerEdge(a, b),
    { onDrill: () => go({ kind: 'edge', a, b }), tipFn: () => tipContainerEdgeHtml(a, b) });
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
//   state = { kind: 'context' | 'container' | 'component' | 'subsystem' | 'edge', sid?, a?, b?, vp? }
// vp = { zoom, pan } captured when we leave a view, so stepping back/forward through history
// restores it exactly as it was (a fresh drill via go() has no vp yet — it fits/centers).
let history = [];
let hi = -1;  // index of the current state

function stateKey(s) {
  return s.kind + (s.sid ? ':' + s.sid : '') + (s.a ? ':' + s.a + '>' + s.b : '') + (s.gp ? ':' + s.gp : '');
}
function captureViewport() {  // stash the current pan/zoom on the entry we're about to leave
  if (mainPz && hi >= 0 && history[hi]) history[hi].vp = { zoom: mainPz.getZoom(), pan: mainPz.getPan() };
}
function go(state) {
  if (hi >= 0 && stateKey(history[hi]) === stateKey(state)) return;  // already here
  captureViewport();
  history = history.slice(0, hi + 1);  // a new branch drops any forward history
  history.push(state);
  hi = history.length - 1;
  render();
}
function back() { if (hi > 0) { captureViewport(); hi -= 1; render(); } }
function fwd() { if (hi < history.length - 1) { captureViewport(); hi += 1; render(); } }

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
function bindContainer() {
  // Subsystem boxes: a plain click SELECTS the box + its linked subsystems (like selecting a
  // component); a ⌘-click drills in. Register every box in the scene so focusNode can dim the
  // non-linked ones, and tag it `drill` so the cursor shows the drill-in affordance while ⌘ is held.
  mainScene.root.querySelectorAll('g.node').forEach((el) => {
    const id = idOf(el);
    if (!id || !GRAPH.nodes[id]) return;
    mainScene.nodeEls[id] = el;
    el.style.cursor = 'pointer';
    el.classList.add('drill');
    el.addEventListener('mouseenter', () => { if (mainScene.selectedKey !== 'node:' + id) el.style.filter = HOVER; });
    el.addEventListener('mouseleave', () => { if (mainScene.selectedKey !== 'node:' + id) el.style.filter = ''; });
    attachTip(el, () => tipNodeHtml(id));
    el.addEventListener('click', (e) => {
      if (isDrag(e)) return;
      e.stopPropagation();
      if (isDrillClick(e)) { go({ kind: 'subsystem', sid: id }); return; }  // ⌘-click drills in
      selectNode(mainScene, el, id);
    });
  });
  // Inter-subsystem arrows: plain click selects (crossings show in the sidebar), ⌘-click drills the
  // pair. bindContainerEdge registers each in the scene so a selected box keeps its linked neighbours.
  eachEdge(mainScene.root, (p, label, m) => {
    const a = m[1], b = m[2];
    if (!(GRAPH.nodes[a] && GRAPH.nodes[b])) return;
    bindContainerEdge(mainScene, p, label, a, b);
  });
}
function bindSubsystem(sid) {  // neighbourhood: component -> detail; ⌘-click on a neighbour box / cross arrow drills
  bindNodes(mainScene, (id, el, ev) => {
    // A neighbour subsystem box: plain click shows its info, ⌘-click walks into it. A component: select.
    if (GRAPH.nodes[id].kind === 'subsystem' && isDrillClick(ev)) { go({ kind: 'subsystem', sid: id }); return; }
    selectNode(mainScene, el, id);
  });
  // Neighbour boxes aren't drilled by a plain click any more, so tag them `drill` for the ⌘ cursor.
  mainScene.root.querySelectorAll('g.node').forEach((el) => {
    const id = idOf(el);
    if (id && GRAPH.nodes[id] && GRAPH.nodes[id].kind === 'subsystem') el.classList.add('drill');
  });
  eachEdge(diagram, (p, label, m) => {
    const a = m[1], b = m[2];
    const aSub = GRAPH.nodes[a] && GRAPH.nodes[a].kind === 'subsystem';
    const bSub = GRAPH.nodes[b] && GRAPH.nodes[b].kind === 'subsystem';
    if (aSub || bSub) {  // cross arrow: select shows its crossings; ⌘-click drills the pair (keeping direction)
      const pa = aSub ? a : sid, pb = bSub ? b : sid;
      bindContainerEdge(mainScene, p, label, pa, pb);
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
// relation path's id is `…-id_E1_E2_N` (endpoints encoded). Its role label lives in
// `.edgeLabels > g.edgeLabel`, one per relation in path order (empty when unlabelled) — same shape
// as flowchart — so pair path[i] with label[i] by index (guarded by an equal-count check).
function eachClassEdge(root, fn) {
  const paths = [...root.querySelectorAll('path.relation')];
  const labels = [...root.querySelectorAll('.edgeLabels > g.edgeLabel')];
  const aligned = labels.length === paths.length;
  paths.forEach((p, i) => {
    const m = (p.id || '').match(/[_-](E\d+)_(E\d+)(?:[_-]|$)/);
    if (m) fn(p, aligned ? labels[i] || null : null, m[1], m[2]);
  });
}
// Mermaid's classDiagram markers are oversized (an ~18-unit diamond/triangle on a 1px line) and
// default to markerUnits="strokeWidth", so the selection highlight's 3px stroke scales them 3x.
// Pin them to a fixed user-space size and shrink them, so they stay proportional AND steady on select.
function fixDomainMarkers(root) {
  const s = 0.55;
  root.querySelectorAll('marker').forEach((m) => {
    if (m.dataset.fixed) return;
    m.setAttribute('refX', ((parseFloat(m.getAttribute('refX')) || 0) * s).toFixed(2));
    m.setAttribute('refY', ((parseFloat(m.getAttribute('refY')) || 0) * s).toFixed(2));
    m.setAttribute('markerUnits', 'userSpaceOnUse');
    m.setAttribute('markerWidth', '11');
    m.setAttribute('markerHeight', '11');
    [...m.children].forEach((c) => {
      c.setAttribute('transform', `scale(${s}) ${c.getAttribute('transform') || ''}`.trim());
    });
    m.dataset.fixed = '1';
  });
}
function bindDomain() {
  fixDomainMarkers(mainScene.root);
  mainScene.root.querySelectorAll('g.node, g.classGroup').forEach((el) => {
    const id = idOf(el);
    if (!id || !GRAPH.nodes[id] || mainScene.nodeEls[id]) return;
    mainScene.nodeEls[id] = el;
    el.style.cursor = 'pointer';
    el.addEventListener('mouseenter', () => { if (mainScene.selectedKey !== 'node:' + id) el.style.filter = HOVER; });
    el.addEventListener('mouseleave', () => { if (mainScene.selectedKey !== 'node:' + id) el.style.filter = ''; });
    attachTip(el, () => tipNodeHtml(id));  // hover -> meaning preview (no selection needed)
    el.addEventListener('click', (ev) => { if (isDrag(ev)) return; ev.stopPropagation(); selectNode(mainScene, el, id); });
  });
  eachClassEdge(mainScene.root, (p, label, src, dst) => {
    const arr = COMP_LOOKUP[src + '>' + dst];
    if (!arr) return;
    const e = arr[0];
    bindSelectEdge(mainScene, p, label, e, 'edge:' + e.src + '>' + e.dst, () => showEdge(e));
  });
}

// --- Golden Path (Level 1) selection ---------------------------------------------
// A sequenceDiagram, a different SVG shape again: a step is a message (text + line), an actor is a
// stick figure over a lifeline. Both SELECT (panel + glow + focus-dim); a step also ⌘-clicks to drill.
// Glow one GP element (figure, text, lifeline or arrow) with the soft GP_SEL drop-shadow — a touch
// above the hover glow, never the heavy stroke-recolour the click used to apply. Returns a cleanup.
function gpGlow(el) {
  el.style.filter = GP_SEL;
  return () => { el.style.filter = ''; };
}
// Glow a set of elements and remember them in scene.gpLit (a step driven by a selected actor is
// glowed but isn't itself the selection, so its own hover handlers must restore THIS glow on leave —
// not blank it). Returns a cleanup that both undoes the glow and forgets the set.
function gpHighlight(scene, els) {
  scene.gpLit = new Set(els);
  const undo = els.map(gpGlow);
  return () => { undo.forEach((f) => f()); scene.gpLit = new Set(); };
}
// The filter an element should rest at given the current selection: the GP_SEL glow if the selection
// lit it, else none. Hover-off restores to this instead of blanking, so a selection glow survives a
// passing hover.
function gpRestFilter(scene, el) {
  return scene.gpLit.has(el) ? GP_SEL : '';
}
function gpFocus(scene, keep) {  // dim every focusable GP element not in the keep set (system stays lit)
  for (const el of scene.dimEls) el.style.opacity = keep.has(el) ? '' : DIM;
}
// Select an actor: its figure + lifeline + every step it drives glow; the rest dims. Toggle off if re-clicked.
function selectGPActor(scene, a) {
  const selKey = 'gpactor:' + a.aid;
  if (scene.selectedKey === selKey) { resetScene(scene); return; }
  scene.selectedKey = selKey;
  showGPActor(a);
  const stepEls = [];
  for (const i of a.stepIdx) { const m = scene.gpMsg[i]; if (m) { if (m.text) stepEls.push(m.text); if (m.line) stepEls.push(m.line); } }
  const lit = [...scene.gpActor[a.aid].els, ...stepEls];
  sceneSelect(scene, () => gpHighlight(scene, lit));
  gpFocus(scene, new Set(lit));
}
// Select a step: the step (text + line) glows and its driving actor stays lit; the rest dims.
function selectGPStep(scene, i, gpId, aid) {
  const selKey = 'gpstep:' + gpId;
  if (scene.selectedKey === selKey) { resetScene(scene); return; }
  scene.selectedKey = selKey;
  showGPStep(gpId);
  const m = scene.gpMsg[i] || {};
  const glow = [m.text, m.line].filter(Boolean);
  const rec = aid ? scene.gpActor[aid] : null;
  sceneSelect(scene, () => gpHighlight(scene, glow));
  gpFocus(scene, new Set([...glow, ...(rec ? rec.els : [])]));
}

// Bind the Golden Path: steps + actors both select; a step ⌘-clicks to its Level-2 components view.
// The step id is no longer in the label, so message[i] pairs with GRAPH.gp[i] by order; an actor's
// figure/lifeline are found by participant id (data-id="GPAn") and its driven steps come from GP_ACTORS.
function bindGP() {
  const scene = mainScene, root = scene.root;
  // message text[i] <-> GRAPH.gp[i]; its arrow is the .messageLine with data-id "i<idx>".
  const texts = [...root.querySelectorAll('text.messageText')];
  const lineByIdx = {};
  root.querySelectorAll('.messageLine0, .messageLine1').forEach((ln) => {
    const m = (ln.getAttribute('data-id') || '').match(/^i(\d+)$/);
    if (m) lineByIdx[+m[1]] = ln;
  });
  scene.gpMsg = {};  // step index -> { text, line }
  for (let i = 0; i < (GRAPH.gp || []).length; i++) {
    const text = texts[i] || null;
    const line = lineByIdx[i] || null;
    if (text) scene.dimEls.push(text);
    if (line) scene.dimEls.push(line);
    scene.gpMsg[i] = { text, line };
  }
  // resolve each actor's DOM (figure top + bottom mirror + lifeline) by participant id, register for dimming.
  scene.gpActor = {};  // aid -> { els:[…] }
  const bottoms = [...root.querySelectorAll('g.actor-man.actor-bottom')];
  for (const a of GP_ACTORS) {
    const figT = root.querySelector('.actor-top[data-id="' + a.aid + '"]');
    const life = root.querySelector('line.actor-line[data-id="' + a.aid + '"]');
    const figB = bottoms.find((g) => (g.textContent || '').trim() === a.name) || null;  // no data-id on the mirror
    const els = [figT, figB, life].filter(Boolean);
    scene.gpActor[a.aid] = { els };
    for (const el of els) scene.dimEls.push(el);
  }
  const aidOfStep = {};  // step index -> driving actor id (keeps the actor lit when a step is selected)
  for (const a of GP_ACTORS) for (const i of a.stepIdx) aidOfStep[i] = a.aid;

  // steps: plain click selects (panel), ⌘-click drills to Level 2.
  (GRAPH.gp || []).forEach((step, i) => {
    const { text, line } = scene.gpMsg[i];
    if (!text) return;
    const gpId = step.id, selKey = 'gpstep:' + gpId;
    const on = () => { if (scene.selectedKey !== selKey) { text.style.filter = HOVER; if (line) line.style.filter = HOVER; } };
    // restore to the resting glow (an actor-selected step keeps its HILITE), not blank
    const off = () => { if (scene.selectedKey !== selKey) { text.style.filter = gpRestFilter(scene, text); if (line) line.style.filter = gpRestFilter(scene, line); } };
    const click = (ev) => {
      if (isDrag(ev)) return;
      ev.stopPropagation();
      off();
      if (isDrillClick(ev)) { go({ kind: 'gpstep', gp: gpId }); return; }  // ⌘-click drills in
      selectGPStep(scene, i, gpId, aidOfStep[i]);
    };
    for (const el of [text, line]) {
      if (!el) continue;
      el.style.cursor = 'pointer';
      el.style.setProperty('pointer-events', el === text ? 'all' : 'stroke', 'important');
      if (el === text) el.classList.add('drill');  // ⌘-held cursor affordance
      el.addEventListener('click', click);
      el.addEventListener('mouseenter', on);
      el.addEventListener('mouseleave', off);
      attachTip(el, () => tipGPHtml(gpId));
    }
  });

  // actors: click the figure or anywhere on the lifeline to select the actor (no drill).
  for (const a of GP_ACTORS) {
    const rec = scene.gpActor[a.aid], selKey = 'gpactor:' + a.aid;
    const on = () => { if (scene.selectedKey !== selKey) for (const el of rec.els) el.style.filter = HOVER; };
    const off = () => { if (scene.selectedKey !== selKey) for (const el of rec.els) el.style.filter = gpRestFilter(scene, el); };
    const click = (ev) => { if (isDrag(ev)) return; ev.stopPropagation(); off(); selectGPActor(scene, a); };
    for (const el of rec.els) {
      if (el.tagName === 'line') continue;  // the lifeline gets a fat transparent hit (below)
      el.style.cursor = 'pointer';
      el.addEventListener('click', click);
      el.addEventListener('mouseenter', on);
      el.addEventListener('mouseleave', off);
      attachTip(el, () => tipGPActorHtml(a));
    }
    const life = rec.els.find((el) => el.tagName === 'line');
    if (life) attachEdgeHandlers(life, null, click, on, off, () => tipGPActorHtml(a), false);
  }
}

// --- render ---------------------------------------------------------------------
function mermaidFor(s) {
  if (s.kind === 'context') return MERMAID_CONTEXT;
  if (s.kind === 'container') return MERMAID_CONTAINER;
  if (s.kind === 'subsystem') return MERMAID_BY_SUB[s.sid];
  if (s.kind === 'edge') return MERMAID_EDGE_CARD[s.a + '>' + s.b];
  if (s.kind === 'domain') return MERMAID_DOMAIN;
  if (s.kind === 'gp') return MERMAID_GP;
  if (s.kind === 'gpstep') return MERMAID_GP_STEP[s.gp];
  return mode === 'diff' ? MERMAID_DIFF : MERMAID_BASE;  // component
}
function applyDefaultPanel(s) {
  if (s.kind === 'subsystem') showNode(s.sid);
  else if (s.kind === 'edge') showTwoSubsystems(s.a, s.b);
  else if (s.kind === 'gp') showGPOverview();
  else if (s.kind === 'gpstep') showGPStep(s.gp);
  else panel.innerHTML = EMPTY_PANEL;
}
function bindFor(s) {
  if (s.kind === 'context') bindContext();
  else if (s.kind === 'container') bindContainer();
  else if (s.kind === 'subsystem') bindSubsystem(s.sid);
  else if (s.kind === 'edge') bindEdgePair();
  else if (s.kind === 'domain') bindDomain();
  else if (s.kind === 'gp') bindGP();
  else if (s.kind === 'gpstep') bindComponent();  // step subgraph = a Components view scoped to the step
  else bindComponent();
}
function topView(kind) {  // which top-level button a state lives under (container/subsystem/edge → Subsystems)
  if (kind === 'context' || kind === 'component' || kind === 'domain') return kind;
  if (kind === 'gp' || kind === 'gpstep') return 'gp';
  return 'container';
}
function gpTitle(gp) { const s = GP_BY_ID[gp]; return s ? s.id + (s.title ? ' — ' + s.title : '') : gp; }
function stateTitle(s) {
  if (s.kind === 'context') return 'Context';
  if (s.kind === 'container') return 'Subsystems';
  if (s.kind === 'component') return 'Components';
  if (s.kind === 'domain') return 'Domain';
  if (s.kind === 'gp') return 'Golden Path';
  if (s.kind === 'gpstep') return gpTitle(s.gp);
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  if (s.kind === 'subsystem') return nm(s.sid);
  return nm(s.a) + ' → ' + nm(s.b);  // edge
}
function ancestors(s) {  // structural nesting path (top → s), independent of the click history
  if (s.kind === 'domain') return [{ kind: 'domain' }];   // a standalone behavioural lens, not nested in Context
  if (s.kind === 'gp') return [{ kind: 'gp' }];           // the Golden Path is its own behavioural lens
  if (s.kind === 'gpstep') return [{ kind: 'gp' }, { kind: 'gpstep', gp: s.gp }];  // step nested under it
  const trail = [{ kind: 'context' }];                    // Context is the root of the structural zoom
  if (s.kind === 'context') return trail;
  if (s.kind === 'component') { trail.push({ kind: 'component' }); return trail; }
  trail.push({ kind: 'container' });                      // Subsystems sit inside the Context
  if (s.kind === 'subsystem') trail.push({ kind: 'subsystem', sid: s.sid });
  else if (s.kind === 'edge') trail.push({ kind: 'edge', a: s.a, b: s.b });  // a pair lives beside the subsystems
  return trail;
}
function renderChrome(s) {
  legend.classList.toggle('on', s.kind === 'component' && mode === 'diff');
  toggle.style.display = (HAS_DIFF && s.kind === 'component') ? '' : 'none';
  toggle.textContent = mode === 'diff' ? 'Show baseline' : 'Show diff';
  const tv = topView(s.kind);
  viewsw.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.view === tv));
  // The drill hint only applies where ⌘-click drills: the Subsystems map + a subsystem neighbourhood,
  // and the Golden Path (⌘-click a step opens its components view).
  drillhint.hidden = !(s.kind === 'container' || s.kind === 'subsystem' || s.kind === 'gp');
  navback.disabled = hi <= 0;
  navfwd.disabled = hi >= history.length - 1;
  // breadcrumb: the structural nesting down to the current view; each ancestor crumb zooms out to it
  crumb.innerHTML = '';
  const chain = ancestors(s);
  chain.forEach((node, i) => {
    if (i) crumb.appendChild(document.createTextNode(' › '));
    const cur = i === chain.length - 1;
    const seg = document.createElement(cur ? 'span' : 'a');
    seg.className = 'crumbseg' + (cur ? ' cur' : '');
    seg.textContent = stateTitle(node);
    if (!cur) seg.addEventListener('click', () => go(node));
    crumb.appendChild(seg);
  });
}

function updateZoomLevel() {  // reflect the current pan-zoom scale in the header control
  if (zoomlevel) zoomlevel.textContent = mainPz ? Math.round(mainPz.getZoom() * 100) + '%' : '100%';
}

async function render() {
  const seq = ++renderSeq;
  hideTip();  // a re-render replaces the diagram — drop any tooltip from the old one
  if (mainPz) { mainPz.destroy(); mainPz = null; }
  const s = history[hi];
  const { svg } = await mermaid.render('coyodexGraph' + (rc++), mermaidFor(s));
  if (seq !== renderSeq) return;  // a newer render started during the async layout — drop this stale one
  diagram.innerHTML = svg;
  mainScene = makeScene(diagram, () => applyDefaultPanel(s));
  bindFor(s);
  applyDefaultPanel(s);
  // "Locate in full map" arrived here: spotlight the GP step's touched nodes in the Components view.
  if (pendingFocus && s.kind === 'component') {
    const keep = pendingFocus; pendingFocus = null;
    applyFocus(mainScene, (nid) => keep.has(nid), (e) => keep.has(e.src) && keep.has(e.dst));
  }
  const svgEl = diagram.querySelector('svg');
  if (svgEl && window.svgPanZoom) {
    svgEl.removeAttribute('style');
    // No practical zoom cap: bounds are wide enough to act unbounded while still keeping the
    // diagram recoverable. The header zoom control (zoomctl) replaces the old overlay icons.
    mainPz = svgPanZoom(svgEl, {
      controlIcons: false, fit: true, center: true, minZoom: 0.01, maxZoom: 1000,
      dblClickZoomEnabled: false,  // double-click is for selecting/reading nodes, not zooming
      onZoom: updateZoomLevel,
    });
    // history revisit: restore the pan/zoom we left this view with (zoom first, then absolute pan)
    if (s.vp) { mainPz.zoom(s.vp.zoom); mainPz.pan(s.vp.pan); }
    updateZoomLevel();
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
// While ⌘ (or ⌃ off Mac) is held, flag the body so drillable subsystems/arrows show the drill-in
// cursor (see .drill in the CSS). Clear on key-up and on blur so a released key never sticks.
const setCmd = (on) => document.body.classList.toggle('cmd', on);
document.addEventListener('keydown', (e) => { if (e.key === 'Meta' || e.key === 'Control') setCmd(true); });
document.addEventListener('keyup', (e) => { if (e.key === 'Meta' || e.key === 'Control') setCmd(false); });
window.addEventListener('blur', () => setCmd(false));
buildLegend();
viewsw.querySelectorAll('button').forEach((b) => {
  if (b.dataset.view === 'container' && !HAS_GROUPING) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'domain' && !HAS_DOMAIN) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'gp' && !HAS_GP) { b.style.display = 'none'; return; }
  b.addEventListener('click', () => go({ kind: b.dataset.view }));
});
navback.addEventListener('click', back);
navfwd.addEventListener('click', fwd);
zoomin.addEventListener('click', () => { if (mainPz) { mainPz.zoomIn(); updateZoomLevel(); } });
zoomout.addEventListener('click', () => { if (mainPz) { mainPz.zoomOut(); updateZoomLevel(); } });
zoomlevel.addEventListener('click', () => { if (mainPz) { mainPz.reset(); updateZoomLevel(); } });  // fit to screen
if (HAS_DIFF) {
  toggle.addEventListener('click', () => { mode = mode === 'diff' ? 'base' : 'diff'; render(); });
}
go({ kind: HAS_GP ? 'gp' : 'context' });  // land on the Golden Path (the behavioural spine); fall back to Context
