// `mermaid` is the global from the SRI-pinned UMD <script> in <head>.

// Generic frontend: this file ships identical for every map. All per-project data — the graph plus every
// pre-rendered diagram source, use-case flow, colour table, and source-link config — is fetched at boot
// from the coyodex server (/p/<slug>/api/view) and assigned into the module vars below by applyBundle().
// These were `const … = __PLACEHOLDER__` back when the data was baked into a standalone HTML file; that
// portable file:// mode was retired when the data moved server-side, so there is nothing to open offline.
let GRAPH;
let MERMAID_BASE, MERMAID_DIFF, MERMAID_CONTEXT, MERMAID_CONTAINER;
let MERMAID_BY_SUB;         // subsystem neighbourhood: sid -> sub-diagram
let MERMAID_EDGE_CARD;      // edge pair: 'A>B' -> two-subsystem sub-diagram
let CONTAINER_EDGES;        // inter-subsystem arrow 'A>B' -> [crossing component edges]
let MERMAID_DOMAIN;         // T5 domain model as a classDiagram (flat, ungrouped)
let MERMAID_DOMAIN_CONTAINER;   // Subdomains overview (flowchart of SD boxes)
let MERMAID_DOMAIN_SUB;         // per-subdomain card: SD-id -> classDiagram
let MERMAID_DOMAIN_EDGE_CARD;   // subdomain edge pair: 'A>B' -> two-subdomain classDiagram
let MERMAID_BRIDGE_CARD;        // bridge pair 'S>SD' -> subsystem×subdomain classDiagram
let DOMAIN_CONTAINER_EDGES;     // inter-subdomain arrow 'A>B' -> [crossing E->E relations]
let MERMAID_HP;            // Happy Path (Level 1): use cases as a black-box sequence
let FLOWS_MM;             // T6 use-case flows: uc-id -> sequenceDiagram (the inside view)
let FLOWS_NARR;          // uc-id -> [{n,src,srcId,dst,dstId,verb,why,note}] readable steps
let HP_ACTORS;          // Happy-Path lifelines: [{aid,name,kind,wants,steps,stepIdx}]
let FLOW_ACTORS;        // uc-id -> [{aid,name,kind,wants,stepIdx}] flow-level actor lifelines (mirrors HP_ACTORS, scoped to one flow's own steps)
let ELEMENT_TINT;       // per-kind {fill,stroke} for views Mermaid renders kind-agnostically (cluster frames, flow participant boxes)
let MERMAID_LIBS;       // Context "Libraries" drill: System + the folded in-process deps
let FOLDED_LIBS;        // [{id,name,type}] folded out of Context into the Libraries box
const LIBS_ID = 'LIBS';                           // synthetic id of that collapsed box (matches gen_viewer.LIBS_ID)
let HAS_GROUPING, HAS_DOMAIN;
let HAS_SUBDOMAINS;  // domain model grouped into subdomains -> Domain view leads with the overview
let HAS_HP;
let HAS_GLOSSARY;    // gates the Glossary tab (derived from the graph in applyBundle)
let HAS_USECASES;    // gates the Use Cases tab (any use-case node present)
let CONTEXT_EDGES;
let HAS_DIFF;
let META;
let DIFF_STATE;
let REPO_ROOT_DEFAULT;  // absolute repo root for 'open in editor' links (overridable in Settings)
let GH_REPO_DEFAULT;    // GitHub repo URL (overridable in Settings) or null
let GH_COMMIT;          // the map's commit SHA — blob links are pinned to it
const FILE_TREE = null;  // the file tree is fetched live (api/tree), never embedded — kept for the shared build path
// The map's own API base ('…/p/<slug>/api/'). null only under file://, which has no server to talk to.
const API_BASE = /^https?:$/.test(location.protocol) ? new URL('./api/', location.href).href : null;

// Assign one /api/view bundle into the module vars above. Field names are the bundle's (camelCase);
// see gen_viewer.ViewBundle for the shape. Keep this in step with that TypedDict.
function applyBundle(b) {
  GRAPH = b.graph;
  MERMAID_BASE = b.mermaidBase; MERMAID_DIFF = b.mermaidDiff; MERMAID_CONTEXT = b.mermaidContext;
  MERMAID_CONTAINER = b.mermaidContainer; MERMAID_BY_SUB = b.mermaidBySub;
  MERMAID_EDGE_CARD = b.mermaidEdgeCard; CONTAINER_EDGES = b.containerEdges;
  MERMAID_DOMAIN = b.mermaidDomain; MERMAID_DOMAIN_CONTAINER = b.mermaidDomainContainer;
  MERMAID_DOMAIN_SUB = b.mermaidDomainSub; MERMAID_DOMAIN_EDGE_CARD = b.mermaidDomainEdgeCard;
  MERMAID_BRIDGE_CARD = b.mermaidBridgeCard; DOMAIN_CONTAINER_EDGES = b.domainContainerEdges;
  MERMAID_HP = b.mermaidHp; FLOWS_MM = b.flowsMm; FLOWS_NARR = b.flowsNarr;
  HP_ACTORS = b.hpActors; FLOW_ACTORS = b.flowActors; ELEMENT_TINT = b.elementTint;
  MERMAID_LIBS = b.mermaidLibs; FOLDED_LIBS = b.foldedLibs; CONTEXT_EDGES = b.contextEdges;
  HAS_GROUPING = b.hasGrouping; HAS_DOMAIN = b.hasDomain; HAS_SUBDOMAINS = b.hasSubdomains;
  HAS_HP = b.hasHp; HAS_DIFF = b.hasDiff; META = b.meta; DIFF_STATE = b.diffState;
  REPO_ROOT_DEFAULT = b.repoRoot; GH_REPO_DEFAULT = b.ghRepo; GH_COMMIT = b.ghCommit;
  HAS_GLOSSARY = Array.isArray(GRAPH.glossary) && GRAPH.glossary.length > 0;
  HAS_USECASES = Object.values(GRAPH.nodes || {}).some((n) => n.kind === 'usecase');
}

function bootError(msg) {
  const d = document.getElementById('diagram');
  if (d) d.innerHTML = '<div style="padding:2rem;color:#b91c1c;font:14px/1.5 system-ui,sans-serif">' + msg + '</div>';
}

// Fetch the map's data BEFORE the rest of the module runs (top-level await): every statement below —
// the indexes built from GRAPH, the view wiring gated on HAS_*, the initial go() — needs it in place.
if (!API_BASE) {
  bootError('This map is served by the coyodex server. Open it via “coyodex serve”, not as a local file.');
  throw new Error('coyodex: no server (file:// has no data source)');
}
try {
  const _res = await fetch(API_BASE + 'view', { cache: 'no-store' });
  if (!_res.ok) throw new Error('view ' + _res.status);
  applyBundle(await _res.json());
} catch (err) {
  bootError('Could not load this map from the server. Is “coyodex serve” still running?');
  throw err;  // no data -> nothing below can run; stop the module here
}

const SVGNS = 'http://www.w3.org/2000/svg';
const R = 10;
const BADGE = { added: ['#1a7f37', '+', 'new'], modified: ['#9a6700', '✎', 'modified'],
                deleted: ['#cf222e', '×', 'deleted'], rippled: ['#d97706', '≈', 'ripples to'] };
const HILITE = 'drop-shadow(0 0 4px #2563eb) drop-shadow(0 0 2px #2563eb)';  // selection glow (nodes + edge labels)
const HOVER = 'drop-shadow(0 0 3px #60a5fa)';  // softer hover glow: signals "clickable" without competing with HILITE
const HP_SEL = 'drop-shadow(0 0 4px #3b82f6)';  // Happy-Path selection: just a touch stronger than HOVER (not the heavy HILITE)
const DIM = '0.15';  // opacity for non-focused elements
const EMPTY_PANEL = '<p class="empty">Click a node or edge to see details.</p>';
// Shown when a use case has no T6 flow yet, so the flow view still renders (the panel explains it)
// instead of degrading to the generic "could not be rendered" card.
const EMPTY_FLOW_MM = 'sequenceDiagram\n  participant System\n  Note over System: No T6 flow recorded';

// `class.hideEmptyMembersBox`: a member-less class renders as a plain box (no empty UML compartments),
// so the subdomain card's collapsed neighbour boxes (subsystems/subdomains) read as simple boxes, like
// the flowchart cards — only real entities (with attributes) keep the class compartments.
mermaid.initialize({ startOnLoad: false, securityLevel: 'loose', theme: 'default',
  flowchart: { curve: 'basis' }, class: { hideEmptyMembersBox: true } });

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
const flowplayer = document.getElementById('flowplayer');
const flowprev = document.getElementById('flowprev');
const flownext = document.getElementById('flownext');
const flowcount = document.getElementById('flowcount');
document.getElementById('meta').innerHTML = META;
const esc = (s) => (s || '').replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
// Inline markdown -> safe HTML for prose fields (Purpose / Why / Wants / …): a link collapses to its
// text, then we ESCAPE, then wrap `code` and **bold** — escape-first so the only tags are the ones we
// add. Pragmatic, not a full parser: `code` is wrapped before **bold**, so a code span matches first.
const mdInline = (s) => esc(String(s || '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1'))
  .replace(/`([^`]+)`/g, '<code>$1</code>')
  .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

let mode = HAS_DIFF ? 'diff' : 'base';  // a diff render arms the change-impact overlay from the start
let mainPz = null;     // svg-pan-zoom for the current diagram
let rc = 0;
let renderSeq = 0;     // bumped each render(); an in-flight render bails if it's no longer current
let downX = 0, downY = 0;  // last mousedown, to tell a real click from a drag-pan

// Component-edge lookup '<src>><dst>' -> [edges]; static (GRAPH.edges never changes). Shared by the
// Components view and the drilled diagrams, so an arrow resolves to its real component edge.
const COMP_LOOKUP = {};
for (const e of GRAPH.edges || []) (COMP_LOOKUP[e.src + '>' + e.dst] ||= []).push(e);

// Happy Path step lookup 'HP1' -> step record (id, title, uc, why). The step IS a use case; its
// detailed actions live in that use case's T6 flow (FLOWS_MM / FLOWS_NARR), opened when the step drills.
const HP_BY_ID = {};
for (const s of GRAPH.happy_path || []) HP_BY_ID[s.id] = s;
// Happy Path actor lookups: by participant id (HPA0) and by the step it drives (HP1 -> actor record).
const HP_ACTOR_BY_AID = {};
for (const a of HP_ACTORS) HP_ACTOR_BY_AID[a.aid] = a;
const HP_ACTOR_OF_STEP = {};
for (const a of HP_ACTORS) for (const st of a.steps) HP_ACTOR_OF_STEP[st.id] = a;
// The Use Cases catalog: every use-case node in model order (importance), plus the reverse index
// uc -> [Happy Path step ids] that realize it. A use case may occupy several Happy Path positions, so
// this maps to a LIST — the `HPn` pill lists them all and lights every one when clicked. A use case
// with no entry here is off-spine (no pill).
const UC_NODES = Object.values(GRAPH.nodes || {}).filter((n) => n.kind === 'usecase');
const HP_STEPS_BY_UC = {};
for (const s of GRAPH.happy_path || []) if (s.uc) (HP_STEPS_BY_UC[s.uc] ||= []).push(s.id);
// Role lookup by name (lower-cased) -> {name, kind, wants} for the Use Cases actor-section headers.
const ROLE_BY_NAME = {};
for (const r of GRAPH.roles || []) ROLE_BY_NAME[(r.name || '').trim().toLowerCase()] = r;
// Reverse traceability ("Used in UC"): element id -> Set of use-case ids whose T6 flow steps through
// it. The backward view of the flows (derived here, never authored), shown as links on a node's panel.
const USES_BY_NODE = {};
for (const f of GRAPH.flows || []) {
  for (const st of (f.steps || [])) {
    for (const end of [st.src, st.dst]) {
      if (GRAPH.nodes[end]) (USES_BY_NODE[end] ||= new Set()).add(f.uc);
    }
  }
}

// When a click navigates to another view to reveal a node (the file browser, a flow element link, the
// change-impact summary), the node id to select is stashed here and applied once that view has rendered.
let pendingSelect = null;
// A file-tree click on a path with MULTIPLE anchored elements (node_path_index collision) navigates to
// their shared view (if one exists) without selecting anything — the ids to list in the panel once that
// view has rendered are stashed here (see selectFromTreeAnchors / showElementsList).
let pendingElementsList = null;

// node id -> its injected corner-action icon element (see decorateActionIcons), so a ⌘-click / double
// click drill (isDrillClick) can flash the SAME icon a direct icon-click would have used — one visual
// language regardless of which of the three ways you triggered it.
const ACTION_ICONS = {};
let EDGE_ICON_SEQ = 0;  // fallback ACTION_ICONS key for a drillable edge path with no (or a stripped) DOM id
// The step player's live context on a use-case flow view: the flow's uc, its ordered narrative steps, the
// per-step DOM (arrow line + label) and participant columns bindFlow already resolved, and the current
// 0-based step. null on every non-flow view (so the strip stays hidden and the arrow keys stay inert).
let flowPlay = null;

// --- scene ----------------------------------------------------------------------
// A "scene" wraps the diagram currently shown: its root, the bound node/edge elements, the active
// selection, and what the side panel shows when nothing is selected. There's one scene at a time;
// it's rebuilt on every render. Focus/select/reset all operate on it.
let mainScene = null;

function makeScene(root, defaultPanel) {
  // dimEls: a flat list of extra focusable elements (the Happy Path's actor figures, lifelines and
  // message text/lines) that the standard node/edge focus model doesn't cover — dimmed/restored together.
  // selectors: selectedKey -> a zero-arg closure that re-applies that selection (panel + glow + focus),
  //   registered at bind time so back/forward can restore the element that was selected in this view.
  return { root, nodeEls: {}, edgeEls: [], dimEls: [], hpLit: new Set(), selectedKey: null, selectors: {}, clearHighlight: null, defaultPanel };
}
function sceneSelect(scene, applyFn) {  // one highlight at a time within a scene
  if (scene.clearHighlight) scene.clearHighlight();
  scene.clearHighlight = applyFn ? applyFn() : null;
}
function applyFocus(scene, keepNode, keepEdge) {
  // `.dim` mirrors the opacity (see viewer.css) so a dimmed box's corner pill stays hidden even on
  // hover — a box you're not focused on shouldn't invite drilling into it just because the cursor
  // passed over it while dimmed.
  for (const nid in scene.nodeEls) {
    const el = scene.nodeEls[nid], keep = keepNode(nid);
    el.style.opacity = keep ? '' : DIM;
    el.classList.toggle('dim', !keep);
  }
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
// Paint a rect with a kind's injected fill/stroke (ELEMENT_TINT). Shared by the two spots Mermaid
// renders a box kind-agnostically — cluster frames and flow participant boxes. No-op if the rect or the
// kind's tint is missing.
function applyTint(rect, kind) {
  const tint = kind && ELEMENT_TINT[kind];
  if (!rect || !tint) return;
  rect.style.setProperty('fill', tint.fill, 'important');
  rect.style.setProperty('stroke', tint.stroke, 'important');
  // Only a container's (subsystem/subdomain) tint carries a width/dasharray — the second, colour-blind-
  // safe signal that this frame is a container, matching the thicker dashed border its collapsed box
  // gets from its Mermaid classDef (`style`/classDef can't reach a cluster frame directly, hence the JS tint).
  if (tint.strokeWidth) rect.style.setProperty('stroke-width', tint.strokeWidth, 'important');
  if (tint.strokeDasharray) rect.style.setProperty('stroke-dasharray', tint.strokeDasharray, 'important');
}
// An EXPANDED group (a drilled subsystem / subdomain) renders as a Mermaid CLUSTER frame, which
// defaults to pale yellow. Tint each cluster to its family so a group reads the SAME colour collapsed (a
// box) or expanded (a frame). The cluster's DOM id ends with its element id (`<diagramId>-S1` / `-SD1`);
// one pass covers flowchart subgraphs (subsystem cards) AND classDiagram namespaces (subdomain cards +
// the mixed S×SD bridge), where Mermaid's `style` directive can't reach the frame.
function tintClusters(root) {
  root.querySelectorAll('g.cluster').forEach((g) => {
    const m = (g.id || '').match(/-([A-Za-z]+\d+)$/);
    const node = m && GRAPH.nodes[m[1]];
    applyTint(g.querySelector('rect'), node && node.kind);
  });
}
// Emphasise the frame of the group you have zoomed INTO (a drilled subsystem or subdomain): a thicker
// border + a larger, bolder title, so the currently-open container reads as distinct from the child
// boxes drawn inside it. Runs AFTER tintClusters so its stroke-width wins over the tint's `!important`
// one. Scoped to the single-group views (subsystem / domsub); the frame is matched by its DOM-id
// suffix, exactly like tintClusters. Off-diagram views (hp/usecases/glossary) skip it (no clusters).
function emphasizeZoomedFrame(root, s) {
  const gid = s.kind === 'subsystem' ? s.sid : (s.kind === 'domsub' ? s.sd : null);
  if (!gid) return;
  for (const g of root.querySelectorAll('g.cluster')) {
    const m = (g.id || '').match(/-([A-Za-z]+\d+)$/);
    if (!m || m[1] !== gid) continue;
    const rect = g.querySelector('rect');
    const label = g.querySelector('.cluster-label') || g.querySelector('text');
    // Mermaid sizes the label band for the ORIGINAL font, so an enlarged title grows down into the first
    // child. Fix: grow the frame UPWARD by PAD (empty space at the top) and lift the title into it — the
    // content stays put, so a real gap opens BELOW the bigger title instead of overlap.
    const PAD = 20;
    if (rect) {
      rect.style.setProperty('stroke-width', '4px', 'important');  // beats the tint's dashed width
      const y = parseFloat(rect.getAttribute('y')), h = parseFloat(rect.getAttribute('height'));
      if (!Number.isNaN(y) && !Number.isNaN(h)) { rect.setAttribute('y', y - PAD); rect.setAttribute('height', h + PAD); }
    }
    if (label) {
      label.style.fontSize = '1.35em';
      label.style.fontWeight = '700';
      const t = label.getAttribute('transform') || '';
      const m = t.match(/translate\(\s*([-\d.]+)[ ,]+([-\d.]+)\s*\)/);
      if (m) label.setAttribute('transform', 'translate(' + m[1] + ', ' + (parseFloat(m[2]) - PAD) + ')');
      // let a slightly wider title overflow its layout-fixed box rather than clip
      const fo = label.querySelector ? label.querySelector('foreignObject') : null;
      if (fo) fo.style.overflow = 'visible';
    }
    break;  // exactly one frame is the zoomed-in group
  }
}

// --- corner action icon -----------------------------------------------------------
// Every drawn box gets AT MOST ONE corner icon — whatever its one useful secondary action is: a
// container (subsystem/subdomain) drills into the diagram, a leaf with a source ref (component/entity)
// opens that file. Nothing shown otherwise (a dep, or a leaf with no file, has no secondary action).
// Clicking the icon fires the action directly; isDrillClick's ⌘-click / double-click paths flash this
// SAME icon (via ACTION_ICONS) so all three routes teach the one visual language. Hidden until the box
// is hovered (see viewer.css) — keeps a busy diagram uncluttered; double-click-anywhere-on-the-box
// stays the reliably-discoverable path regardless of whether anyone ever notices the icon.
function primaryActionFor(id) {
  if (id === 'SYS') { const t = sysDrillTarget(); return t ? { kind: 'drill', run: () => go(t) } : null; }
  if (id === LIBS_ID) return { kind: 'drill', run: () => go({ kind: 'libs' }) };
  const n = GRAPH.nodes[id];
  if (!n) return null;
  if (n.kind === 'subsystem') return { kind: 'drill', run: () => go({ kind: 'subsystem', sid: id }) };
  if (n.kind === 'subdomain') return { kind: 'drill', run: () => go({ kind: 'domsub', sd: id }) };
  const src = srcNode(id);
  return src ? { kind: 'open', run: () => openSource(src) } : null;
}
// Re-triggerable pulse on the icon (double-click / ⌘-click drilled via the BOX, not the icon itself) —
// closes the loop so the icon's meaning rubs off even on someone who never clicks it directly.
function flashIcon(icon) {
  if (!icon) return;
  clearTimeout(icon._flashTimer);  // a fast repeat (e.g. double-click firing right after an icon click) shouldn't let an earlier timer cut the new flash short
  icon.classList.remove('flash');
  void icon.getBBox();  // force reflow so re-adding the class restarts the animation
  icon.classList.add('flash');
  // `.flash` forces the icon visible (see viewer.css) — MUST be removed once the moment has passed, or
  // an action that doesn't re-render the view (opening a source file, unlike drilling) leaves the icon
  // permanently visible from then on. A timer (not 'animationend') so this still cleans up under
  // prefers-reduced-motion, where the animation itself is disabled and would never fire that event.
  icon._flashTimer = setTimeout(() => icon.classList.remove('flash'), 550);
}
// A drawn vector glyph per action kind, not a text character — a unicode glyph reads as a blurry dot at
// small sizes (font hinting varies by system); a path is crisp at any zoom. `drill` draws a magnifying
// glass with a plus — the exact "zoom in" metaphor the app's own drill cursor already uses (viewer.css
// `body.cmd .drill { cursor: zoom-in }`). `open` draws a diagonal arrow with a corner arrowhead — the
// standard "open externally" shape — and viewer.css's `.opensrc` cursor is hand-drawn to match it, so
// the icon and the ⌘-held cursor still agree on what the action means.
function buildGlyph(kind) {
  const g = document.createElementNS(SVGNS, 'g');
  g.setAttribute('class', 'glyph');
  if (kind === 'drill') {
    const lens = document.createElementNS(SVGNS, 'circle');
    lens.setAttribute('cx', '-2'); lens.setAttribute('cy', '-2'); lens.setAttribute('r', '4.5');
    const handle = document.createElementNS(SVGNS, 'path');
    handle.setAttribute('d', 'M 1.2,1.2 L 6,6');
    const plus = document.createElementNS(SVGNS, 'path');
    plus.setAttribute('d', 'M -4.2,-2 L 0.2,-2 M -2,-4.2 L -2,0.2');
    g.append(lens, handle, plus);
  } else {
    // The standard "open externally" glyph: a diagonal shaft with a corner arrowhead at the tip (the
    // same shape as the common external-link icon). Scale + stroke-width are carried over unchanged
    // from the bracket glyph this replaced — that weight was tuned against the drill glyph's solid lens
    // (a thin stroke reads visually smaller than a filled shape at the same bounding-box size), and this
    // shape has the same "a few open line segments" character, so the same fix still applies. Scaling
    // the whole `.glyph` group (safe here: unlike the outer `.action-icon` group, it carries no
    // position-critical transform of its own to clobber) keeps the shaft-to-arrowhead ratio exactly as
    // drawn, regardless of the scale factor.
    const arrow = document.createElementNS(SVGNS, 'path');
    // The arrowhead legs (3.5) stay well above the stroke width (3.4) on purpose — shortening the SHAFT
    // (tail) is safe, but shortening the arrowhead legs much past the stroke's own width is what turns
    // the corner into a solid blob instead of a readable chevron (that's what happened at legs=1.5).
    arrow.setAttribute('d', 'M -3.5,3.5 L 4,-4 M 4,-0.5 L 4,-4 L 0.5,-4');
    g.append(arrow);
    g.setAttribute('transform', 'scale(1.3)');
  }
  return g;
}
// Paint values per action kind. Applied via inline style + 'important' in addActionIcon, NOT via a CSS
// class — a container (subsystem/subdomain) box carries Mermaid-generated classDef rules like
// `#coyodexGraph7 .subsystem > * { fill: …; stroke-dasharray: 6,3; … !important }` (its own dashed-
// border styling), scoped by an id. An id in a selector outranks any number of classes NO MATTER WHAT,
// and here Mermaid's rule is ALSO `!important` — so a same-!important class-based override can never
// win, and an unset property (fill/stroke/stroke-width/dasharray) simply falls through and inherits
// whatever the container painted itself with. An inline `!important` style is the one thing that beats
// an author stylesheet's `!important` regardless of selector specificity, which is exactly why
// `applyTint` elsewhere in this file already uses the same trick for cluster-frame recolouring.
// Both kinds share the same indigo — the icon SHAPE (magnifying glass vs. arrow) is what tells drill
// and open apart now, not colour. glyphWidth stays thicker for `open`: a few open line segments (the
// arrow) read as visually thinner/smaller than the drill glyph's filled lens ring at the same
// bounding-box size, even at matched colour.
const ICON_PAINT = {
  drill: { stroke: '#6366f1', hoverFill: '#eef2ff', glyphStroke: '#4338ca', glyphWidth: '2.1px' },
  open: { stroke: '#6366f1', hoverFill: '#eef2ff', glyphStroke: '#4338ca', glyphWidth: '2.6px' },
};
const ACTION_ICON_R = 16.5;  // the halo's radius — shared with addLabelActionIcon so its offset can clear the badge without a magic number of its own
function paintImportant(el, props) {
  for (const k in props) el.style.setProperty(k, props[k], 'important');
}
// Inject `action`'s icon (circle + glyph) into `el`'s own top-left corner, in `el`'s local coordinate
// space (getBBox), so it rides along with whatever transform Mermaid gave the node/cluster group.
// `opts.anchor` + `opts.host` override where the icon is placed/attached — for a label that has no box
// of its own to sit in the corner of (see addLabelActionIcon), the caller supplies both instead.
function addActionIcon(el, id, action, opts) {
  let anchor = opts && opts.anchor;
  if (!anchor) { let bbox; try { bbox = el.getBBox(); } catch (_) { return; } anchor = { x: bbox.x, y: bbox.y }; }
  const paint = ICON_PAINT[action.kind];
  const icon = document.createElementNS(SVGNS, 'g');
  icon.setAttribute('class', 'action-icon ' + (action.kind === 'drill' ? 'is-drill' : 'is-open'));
  // The anchor point in DIAGRAM units, kept around so rescaleActionIcons can recompute the transform
  // (translate + a counter-zoom scale) on every zoom change without re-measuring the box.
  icon._anchor = anchor;
  icon.setAttribute('transform', `translate(${anchor.x},${anchor.y})`);
  // A container's own box sits exactly where the icon is anchored (its top-left corner) — with a
  // dashed border (see gen_viewer.py _CONTAINER_BORDER), that border's dashes run directly behind/
  // through the badge at that corner, visually merging with the badge's own thin ring and making it
  // read as dashed too even though its own stroke is solid (confirmed: moving the icon away from the
  // corner alone made it render cleanly). A borderless "halo" plate slightly bigger than the badge,
  // painted first (underneath), gives the badge a clean, opaque area to sit on regardless of what's
  // behind it — the common fix for any icon badge placed over a busy background.
  const halo = document.createElementNS(SVGNS, 'circle');
  halo.setAttribute('r', String(ACTION_ICON_R));
  paintImportant(halo, { fill: '#fff', stroke: 'none' });
  const circle = document.createElementNS(SVGNS, 'circle');
  circle.setAttribute('r', '13');
  paintImportant(circle, { fill: '#fff', stroke: paint.stroke, 'stroke-width': '1.6px', 'stroke-dasharray': 'none' });
  const glyph = buildGlyph(action.kind);
  glyph.querySelectorAll('circle, path').forEach((shape) => {
    paintImportant(shape, { fill: 'none', stroke: paint.glyphStroke, 'stroke-width': paint.glyphWidth, 'stroke-dasharray': 'none' });
  });
  const title = document.createElementNS(SVGNS, 'title');
  title.textContent = action.kind === 'drill' ? 'Drill in' : 'Open source';
  icon.append(halo, circle, glyph, title);
  // The hover tint also goes through JS + !important (not a CSS :hover rule) for the same reason as the
  // base paint above — it's just fill, so it hits the exact same Mermaid collision.
  icon.addEventListener('mouseenter', () => paintImportant(circle, { fill: paint.hoverFill }));
  icon.addEventListener('mouseleave', () => paintImportant(circle, { fill: '#fff' }));
  icon.addEventListener('click', (e) => {
    if (isDrag(e)) return;  // tail of a drag-pan, not a real click
    e.stopPropagation();
    flashIcon(icon);
    action.run();
  });
  (opts && opts.host || el).appendChild(icon);
  ACTION_ICONS[id] = icon;
}
// A message label has no box to anchor a corner badge to — sit the pill just before the label's left
// edge instead (so it reads first, like a bullet), vertically centered on it. Used for a Happy Path
// message's text AND (see bindEdgeActionIcon) any drillable edge with a real label — same convention
// either way: one fixed spot, not one that chases the cursor. Appended to the label's own parent (not
// the label itself: an SVG <text> can't usefully host a child <g>), which shares its coordinate space
// since Mermaid gives these labels no transform of their own.
//
// The gap to the label must be a CONSTANT SCREEN distance, not a constant diagram-unit one: the pill's
// own SIZE is already held constant on screen regardless of zoom (rescaleActionIcons counter-scales
// it), so a fixed diagram-unit gap would drift — shrinking toward (and past, on a wide Happy Path
// that needs a lot of shrink just to fit) zero as the diagram zooms out, overlapping the very label
// it's meant to sit clear of. `_labelRef` (the zoom-invariant point this pill hangs off) + `_labelGap`
// (the desired screen-px clearance) let rescaleActionIcons redo this placement — and the bridge below
// — with the real zoom factor every time it changes, not just once here with an inv=1 guess.
function addLabelActionIcon(label, id, action) {
  let bbox; try { bbox = label.getBBox(); } catch (_) { return; }
  const host = label.parentNode;
  // bbox is in the LABEL's own local space — pointToHostSpace carries its left-middle point (and, a
  // little further right, the bridge's far edge) into `host`'s space, whatever the relationship
  // between the two turns out to be (see pointToHostSpace).
  const ref = pointToHostSpace(label, bbox.x, bbox.y + bbox.height / 2, host);
  const rightEdge = pointToHostSpace(label, bbox.x + 5, bbox.y + bbox.height / 2, host);
  if (!ref || !rightEdge) return;
  const gap = ACTION_ICON_R + 10;
  const anchor = { x: ref.x - gap, y: ref.y };  // inv=1 placeholder for this first paint, before mainPz exists
  // Bridge the gap with an invisible hit area — one continuous hoverable strip from label to pill, so
  // there's never a moment the cursor is over neither. It deliberately overlaps BOTH ends by a few
  // units rather than trying to land exactly on their edges (see `rightEdge`/the pill's own anchor
  // below), so DOM order is what decides who wins each overlap, not exact geometry:
  //  - inserted BEFORE the label (not appended after) so the label — a real, pre-existing, clickable
  //    Mermaid element — stays on top and keeps receiving its own clicks. Appending the bridge after
  //    it was a real bug: the bridge has no click handler, so a click landing in that overlap (a few
  //    units is often most of a short label like a bare connection count) silently went nowhere.
  //  - the pill itself (added last, below) is appended AFTER the bridge, so it wins the OTHER overlap,
  //    at its own end — starting the bridge exactly at the pill's centre guarantees that overlap
  //    regardless of the pill's actual on-screen radius (see the comment above), without needing the
  //    bridge to also be perfectly sized to it.
  const bridge = document.createElementNS(SVGNS, 'rect');
  bridge.style.setProperty('fill', 'transparent');
  bridge.style.setProperty('pointer-events', 'all');
  host.insertBefore(bridge, label);
  addActionIcon(label, id, action, { host, anchor });
  const icon = ACTION_ICONS[id];
  // Lets hpGlow / glowEdge find this pill from the label/path element alone, so selecting the step or
  // edge shows it without the caller threading the icon through separately.
  label._actionIcon = icon;
  icon._bridge = bridge;
  icon._labelRef = ref;
  icon._labelGap = gap;
  icon._labelRight = rightEdge.x;  // bridge's far edge: a little past the label's own left edge
  placeLabelBridge(icon);
}
// (Re)size the bridge from the pill's CURRENT anchor (already zoom-corrected by the caller) out to
// just past the label — kept in sync with rescaleActionIcons so it never lags the pill it bridges to.
function placeLabelBridge(icon) {
  const b = icon._bridge; if (!b) return;
  const x = icon._anchor.x;
  b.setAttribute('x', String(x));
  b.setAttribute('y', String(icon._labelRef.y - 40));
  b.setAttribute('width', String(Math.max(0, icon._labelRight - x)));
  b.setAttribute('height', '80');
}
// Message pills have no enclosing g.node/g.cluster to hang the CSS :hover/.is-selected reveal rule off
// (viewer.css), so their visibility is plain JS opacity/pointer-events toggling instead — called from
// the same hover handlers already glowing the message's text/line.
function showIcon(icon) { if (icon) { icon.style.setProperty('opacity', '1'); icon.style.setProperty('pointer-events', 'auto'); } }
function hideIcon(icon) { if (icon) { icon.style.removeProperty('opacity'); icon.style.removeProperty('pointer-events'); } }
// One pass over every box `render()` just bound (scene.nodeEls) — called once per render, alongside
// tintClusters. Cluster frames (drilled containers shown as a NEIGHBOUR, not the card you're already
// inside) get their icon from bindFrameDrill instead, which already knows which frames are drillable —
// that runs INSIDE bindFor, before this, so ACTION_ICONS is reset once in render() before bindFor, not
// here (resetting here would wipe the cluster icons bindFrameDrill just registered).
function decorateActionIcons(scene) {
  for (const id in scene.nodeEls) {
    const action = primaryActionFor(id);
    if (action) addActionIcon(scene.nodeEls[id], id, action);
  }
}
function clearFocus(scene) {
  for (const nid in scene.nodeEls) { scene.nodeEls[nid].style.opacity = ''; scene.nodeEls[nid].classList.remove('dim'); }
  for (const x of scene.edgeEls) { x.path.style.opacity = ''; if (x.label) x.label.style.opacity = ''; }
  for (const el of scene.dimEls) el.style.opacity = '';
}
function resetScene(scene) {  // clear selection + focus, restore the scene's default panel
  clearFocus(scene);
  sceneSelect(scene, null);
  scene.selectedKey = null;
  scene.defaultPanel();
  highlightTreePath(null);  // drop the file-browser highlight too
  setTreePeek(false);       // and close any transient folder peek
}

// A click whose pointer moved far from its mousedown is the tail of a drag-pan — ignore it,
// so panning never deselects.
function isDrag(e) { return Math.abs(e.clientX - downX) > 5 || Math.abs(e.clientY - downY) > 5; }
// A ⌘-click (⌃-click off Mac), OR a double-click — a native `click` event's second firing reports
// `detail >= 2`, and svg-pan-zoom's own double-click-to-zoom is disabled (see render()) precisely so
// this gesture is free for the diagram to use — turns a select into a drill-in / open-source. Flashes
// that node's corner icon (if it has one) so double-clicking teaches the icon's meaning even to someone
// who never clicks the icon directly; a direct icon click flashes itself already, so this only needs to
// cover the ⌘-click / double-click paths.
function isDrillClick(e) {
  const drill = !!e && (e.metaKey || e.ctrlKey || e.detail >= 2);
  if (drill && e.currentTarget) {
    const id = idOf(e.currentTarget);
    if (id && ACTION_ICONS[id]) flashIcon(ACTION_ICONS[id]);
  }
  return drill;
}

// --- side panel -----------------------------------------------------------------
// The "Used in UC" backward view for an element: the use cases whose T6 flow steps through it, as
// links into each use case's flow. Derived from USES_BY_NODE; '' when no flow touches this element.
function usedInHtml(id) {
  const set = USES_BY_NODE[id];
  if (!set || !set.size) return '';
  const links = [...set].sort().map((uc) =>
    '<a href="#" class="ucref" data-uc="' + esc(uc) + '">'
    + esc(GRAPH.nodes[uc] ? GRAPH.nodes[uc].name : uc) + '</a>').join(', ');
  return '<dt>Used in</dt><dd>' + links + '</dd>';
}
// The one free-text "what/why" field a node kind carries — Purpose (subsystem/subdomain/component),
// Used for (dep), Meaning (entity). Shown as plain prose with no label, since the field IS the
// description (mirrors how showContextEdge/showHPActor treat Wants, and showEdge/showFlowPanel treat Why).
const EXPLANATION_KEYS = ['purpose', 'used for', 'meaning'];
function explanationKey(fields) {
  for (const want of EXPLANATION_KEYS)
    for (const k in fields)
      if (k.toLowerCase() === want && String(fields[k]).trim()) return k;
  return null;
}
// Fields that would just restate what the diagram already shows for this box: its own name (a
// subsystem's/subdomain's "Subsystem"/"Subdomain" field mirrors the <h2>), which box it nests inside
// (the diagram shows that by literally nesting the box there — see kindTagFor for why "Kind" drops too).
// A field whose value equals the node's own name (Subsystem/Subdomain/Component/"Name") is dropped
// unconditionally below — no need to list it here too.
const REDUNDANT_FIELD_BY_KIND = {
  subsystem: ['parent'], subdomain: ['parent'],
  component: ['subsystem'], dep: ['kind'],
};
// The name-tag's label: a dependency's authored sub-type (datastore/service/…) — already what the
// diagram's shape/colour encodes — is more useful than the generic "dep"; fall back to the raw kind
// when none was recorded. Every other kind just shows its own kind.
function kindTagFor(n) {
  return (n.kind === 'dep' && n.fields && n.fields.Kind) || n.kind;
}
// A node's full detail as an HTML string (title + tag + explanation + fields + source link) — no DOM
// writes, no handler wiring. Shared by showNode (one node fills the whole panel) and showElementsList
// (several nodes stack in one panel, each block needing this same markup).
function nodeDetailHtml(id) {
  const n = GRAPH.nodes[id];
  if (!n) return '';
  const fields = n.fields || {};
  const chg = n.change ? `<span class="badge ${n.change}">${n.change}</span>` : '';
  const explainKey = explanationKey(fields);
  const explain = explainKey ? `<p class="explain">${mdInline(fields[explainKey])}</p>` : '';
  const dropped = new Set(REDUNDANT_FIELD_BY_KIND[n.kind] || []);
  // an entity's own fields aren't listed here — the class-diagram box already shows them as compartments.
  const rows = Object.entries(fields)
    .filter(([k, v]) => k !== explainKey && v !== n.name && !dropped.has(k.toLowerCase()))
    .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${mdInline(v)}</dd>`).join('');
  // The node's source ref, shown as plain reference text. Selecting the node already mirrors it into the
  // code viewer (FULL mode); the code viewer's header carries the sole "open externally" control now.
  const ref = n.file ? esc(cleanPath(n.file, n.line)) + (n.line ? ':' + n.line : '') : '';
  const src = ref ? `<div class="src">${ref}</div>` : '';
  return `<div class="pane-title"><h2>${esc(n.name)}</h2><span class="badge kind">${esc(kindTagFor(n))}</span>${chg}</div>`
    + explain
    + `<dl>${rows}${usedInHtml(id)}</dl>${src}`;
}
// Wire the interactive bits inside a just-written detail block: the source-open button + any
// use-case-flow refs. `root` is the panel itself (single-node case) or one `.pblock` div (list case).
function bindNodeDetailHandlers(root, id) {
  root.querySelectorAll('a.ucref').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault(); go({ kind: 'usecase', uc: a.getAttribute('data-uc') });
  }));
}
function showNode(id) {
  if (!GRAPH.nodes[id]) return;
  panel.innerHTML = nodeDetailHtml(id);
  bindNodeDetailHandlers(panel, id);
  // Mirror into the file browser here (not just in selectNode) — showNode is also how a subsystem's/
  // subdomain's OWN card lands on its default panel (applyDefaultPanel) and how a bridge arrow shows its
  // collapsed box (bindBridgeEdge), neither of which went through selectNode before.
  syncTreeToNode(id);
}
// `id`'s file/folder collision set (node_path_index — filetree.py), primary + others, for ANY id in
// that set (not just the primary) — [id] alone when it didn't collide with anything.
function anchorSetFor(id) { return siblingsByNode[id] || [id]; }
// A file/folder anchoring MULTIPLE elements (node_path_index collision): rather than guessing which one
// the reader meant, show all of them — full detail, stacked, separated by a rule — so nothing is hidden
// behind an arbitrary pick. Each block's title is clickable and re-selects that one (selectFromTree),
// which — since it shares this same anchor set — lands right back here with `selectedId` set. Passing
// `selectedId` dims every OTHER block (the same DIM opacity the diagram itself uses for "not focused")
// and scrolls that one block into view, so a long sibling list doesn't leave it hidden off-screen.
// Called with no `selectedId` for the "just landed here, nothing picked yet" state (selectFromTreeAnchors).
function showElementsList(ids, selectedId) {
  const known = ids.filter((id) => GRAPH.nodes[id]);
  panel.innerHTML = known.map((id) =>
    `<div class="pblock" data-id="${esc(id)}">${nodeDetailHtml(id)}</div>`).join('<hr>');
  let activeBlock = null;
  panel.querySelectorAll('.pblock').forEach((block) => {
    const id = block.getAttribute('data-id');
    bindNodeDetailHandlers(block, id);
    const h2 = block.querySelector('h2');
    if (h2) { h2.classList.add('pblock-title'); h2.addEventListener('click', () => selectFromTree(id)); }
    if (selectedId) {
      const active = id === selectedId;
      block.style.opacity = active ? '' : DIM;
      if (active) activeBlock = block;
    }
  });
  if (activeBlock) {
    // Center it, not just scroll it into view — but a block near the END of the list has no content
    // below it for the viewport to scroll into, so plain block:'center' would leave it stuck low. Pad
    // the bottom with exactly the shortfall so even the last block can still be centered.
    const panelRect = panel.getBoundingClientRect(), blockRect = activeBlock.getBoundingClientRect();
    const blockCenter = panel.scrollTop + (blockRect.top - panelRect.top) + blockRect.height / 2;
    const shortfall = blockCenter + panel.clientHeight / 2 - panel.scrollHeight;
    if (shortfall > 0) {
      const spacer = document.createElement('div');
      spacer.style.height = Math.ceil(shortfall) + 'px';
      panel.appendChild(spacer);
    }
    activeBlock.scrollIntoView({ block: 'center' });
  }
}
// The single choke point behind every node selection's panel content: `id`'s OWN plain detail, unless
// it shares an exact file/folder anchor with other elements (anchorSetFor), in which case the full
// sibling list is shown instead — with `id` itself the undimmed, scrolled-to one. So "selecting a box"
// always reads as "here's the file it came from", regardless of whether it was reached via the file
// tree, a sibling's list-title link, or a plain click on the box itself.
function showNodeDetail(id) {
  const ids = anchorSetFor(id);
  if (ids.length > 1) showElementsList(ids, id); else showNode(id);
}
// showNodeDetail already mirrors into the tree for the single-anchor case (showNode does it); only the
// multi-anchor case (showElementsList, which doesn't sync itself) still needs an explicit call. A caller
// that always called both unconditionally was a real bug, not just noise: highlightTreePath's near/far
// centering compares against the PREVIOUS row, so a redundant second call for the same id compared the
// row against itself (trivially "near") and undid the first call's correct centering.
function showNodeDetailSynced(id) {
  showNodeDetail(id);
  if (anchorSetFor(id).length > 1) syncTreeToNode(id);
  updateFolderPeek(id);  // a folder element peeks the file browser open when it's folded (see setTreePeek)
}

function showEdge(e) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  // domain relations carry a kind (composition/…) + cardinality; component edges carry why/where.
  const kindBadge = e.kind ? '<span class="badge kind">' + esc(e.kind) + '</span>' : '';
  const card = (e.src_card || e.dst_card)
    ? '<dt>Cardinality</dt><dd>' + esc((e.src_card || '') + ' → ' + (e.dst_card || '')) + '</dd>' : '';
  // How the relation is implemented: the backing field (resolved in build_graph; `↩`-named when it
  // lives on the target/head), else the authored `{how}` note for a field-less / indirect relation.
  const fkFields = e.fk_fields || [];
  const fkText = fkFields.length > 1 ? '(' + fkFields.join(', ') + ')' : fkFields[0];
  const impl = fkFields.length
    ? esc((e.fk_side === 'dst' ? nm(e.dst) : nm(e.src)) + '.' + fkText)
      + (e.fk_side === 'dst' ? ' <span class="muted">(back-reference)</span>' : '')
    : (e.how ? mdInline(e.how) : '');
  const implRow = impl ? '<dt>Implemented by</dt><dd>' + impl + '</dd>' : '';
  // The edge's `where` source ref, shown as plain reference text. Selecting the edge already mirrors it
  // into the code viewer below; the code viewer's header carries the sole "open externally" control.
  const wn = e.where ? whereNode(e.where) : null;
  const srcHtml = !wn ? ''
    : '<div class="src">' + esc(localRef(wn.file) ? cleanPath(wn.file, wn.line) + (wn.line ? ':' + wn.line : '') : e.where) + '</div>';
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(nm(e.src)) + ' → ' + esc(nm(e.dst)) + '</h2>'
    + '<span class="badge edge">' + esc(e.verb) + '</span>' + kindBadge + '</div>'
    + (e.why ? '<p class="explain">' + mdInline(e.why) + '</p>' : '')
    + '<dl>' + card + implRow + '</dl>'
    + srcHtml;
  // Mirror this edge's own anchor into the file browser too, same as a node selection — clearing
  // whatever was highlighted before when this edge has none of its own (an off-repo `where`, or none).
  highlightFootprint(null);  // an edge has no element footprint — clear any previous one
  highlightTreePath(refTreePath(wn && wn.file, wn && wn.line));
  if (wn) syncCodeView(wn.file, wn.line, []);  // and into the code viewer (FULL mode); no switcher for an edge
}

// Context-edge panel: actor→system shows the role's wants; system→dep shows what it's used for
// and the component edges (with their Why) that realize the dependency.
function showContextEdge(ce) {
  if (ce.type === 'libs') { showLibsFold(); return; }  // SYS→Libraries arrow: same roster panel as the box
  let explain = '', rows = '';
  if (ce.type === 'actor') {
    explain = ce.wants ? '<p class="explain">' + mdInline(ce.wants) + '</p>' : '';
  } else {
    const realized = (ce.realizedBy || []).map((r) =>
      '<dd>• ' + esc(r.srcName) + ' — ' + esc(r.verb) + (r.why ? ' — ' + mdInline(r.why) : '') + '</dd>').join('');
    explain = ce.usedFor ? '<p class="explain">' + mdInline(ce.usedFor) + '</p>' : '';
    rows = realized ? '<dt>Realized by</dt>' + realized : '';
  }
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(ce.from) + ' → ' + esc(ce.to) + '</h2>'
    + '<span class="badge edge">uses</span></div>'
    + explain
    + (rows ? '<dl>' + rows + '</dl>' : '');
}

// The collapsed "Libraries" box: a roster of the in-process deps (frameworks + libraries) folded out
// of the C4 Context view, since they are an implementation concern, not a system the project talks to.
// At-a-glance only — drilling the box is where each one selects to its own details.
function showLibsFold() {
  const items = FOLDED_LIBS.map((d) =>
    '<dd>• ' + esc(d.name) + (d.type ? ' <span class="muted">— ' + esc(d.type) + '</span>' : '') + '</dd>').join('');
  panel.innerHTML = '<div class="pane-title"><h2>Libraries</h2><span class="badge kind">' + FOLDED_LIBS.length + ' in-process</span></div>'
    + '<p class="empty">Frameworks &amp; libraries linked into the process — folded out of the Context view. ⌘-click to drill in.</p>'
    + (items ? '<dl><dt>Bundled</dt>' + items + '</dl>' : '');
}

// Subsystems edge: the panel shows both subsystems (name + Purpose); the concrete A→B wiring is the
// diagram itself (the edge view we navigated to).
function subsystemBlock(id) {
  const n = GRAPH.nodes[id];
  if (!n) return '';
  const purpose = n.fields && (n.fields.Purpose || n.fields.purpose);
  return '<h3>' + esc(n.name) + '</h3>'
    + (purpose ? '<p class="explain">' + mdInline(purpose) + '</p>' : '');
}
function showTwoSubsystems(a, b) {
  panel.innerHTML = '<div class="badges"><span class="badge edge">connection</span></div>'
    + subsystemBlock(a) + '<hr>' + subsystemBlock(b);
}
// The domedge default panel — the two subdomains being framed. subsystemBlock reads only id/name/Purpose,
// which an SD node carries too, so it doubles as the subdomain block.
function showTwoSubdomains(a, b) {
  panel.innerHTML = '<div class="badges"><span class="badge edge">relations</span></div>'
    + subsystemBlock(a) + '<hr>' + subsystemBlock(b);
}
// The bridge-card default panel — the subsystem and subdomain being framed (the structure↔domain pair).
function showBridge(sid, sd) {
  panel.innerHTML = '<div class="badges"><span class="badge edge">bridge</span></div>'
    + subsystemBlock(sid) + '<hr>' + subsystemBlock(sd);
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
// Selecting an inter-subdomain arrow (Domain overview): list every entity→entity relation it bundles as
// `from → to:` with its verb (+ kind) below — the domain analog of showContainerEdge.
function showDomainContainerEdge(a, b) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  const list = DOMAIN_CONTAINER_EDGES[a + '>' + b] || [];
  const items = list.map((r) =>
    '<li><div class="xpair">' + esc(r.srcName) + ' → ' + esc(r.dstName) + ':</div>'
    + '<div class="xwhy">' + esc(r.verb) + (r.kind ? ' <span class="muted">(' + esc(r.kind) + ')</span>' : '') + '</div></li>').join('');
  panel.innerHTML = '<h2>' + esc(nm(a)) + ' → ' + esc(nm(b)) + '</h2>'
    + '<div class="xcount">' + list.length + ' relation' + (list.length === 1 ? '' : 's') + '</div>'
    + (items ? '<ul class="xlist">' + items + '</ul>' : '<p class="empty">no relations recorded</p>');
}

// --- Happy Path + use-case flow panels -----------------------------------------
// A use case's flow as a readable numbered list — the SAME source as its sequence diagram (FLOWS_MM),
// so the "why" of each step is shown once and never drifts. Each element endpoint links to its node;
// the why (from the backbone edge) and any flow note are inline. '' when the use case has no T6 flow.
function flowNarrativeHtml(uc) {
  const steps = FLOWS_NARR[uc] || [];
  if (!steps.length) return '';
  const end = (label, id) => id
    ? '<a href="#" class="flowref" data-id="' + esc(id) + '">' + esc(label) + '</a>' : esc(label);
  const items = steps.map((st) =>
    '<li><span class="flowact">' + end(st.src, st.srcId) + ' <em>' + esc(st.verb) + '</em> ' + end(st.dst, st.dstId) + '</span>'
    + (st.why ? '<span class="floww"> — ' + mdInline(st.why) + '</span>' : '')
    + (st.note ? '<span class="flown"> (' + mdInline(st.note) + ')</span>' : '') + '</li>').join('');
  return '<ol class="flow">' + items + '</ol>';
}
// Wire the narrative's element links: a click locates that node in its home view (its subsystem card,
// domain card, etc.) and selects it — the same routing the file browser uses.
function bindFlowRefs() {
  panel.querySelectorAll('a.flowref').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault();
    selectFromTree(a.getAttribute('data-id'));
  }));
}
// The use-case flow panel — shared by the Happy-Path step drill-down and the use-case view: the use
// case (name + driving actor) + the numbered narrative (the readable twin of the sequence diagram drawn
// at this altitude); each step's element links locate that element in its home view.
function showFlowPanel(uc, title, why) {
  const ucNode = uc ? GRAPH.nodes[uc] : null;
  const ucName = ucNode ? ucNode.name : (uc || '');
  const f = (ucNode && ucNode.fields) || {};
  const actor = f.Actor || f.actor || '';
  const narr = flowNarrativeHtml(uc);
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(title || ucName) + '</h2>'
    + (ucName ? '<span class="badge kind">' + esc(ucName) + '</span>' : '')
    + (actor ? '<span class="badge edge">' + esc(actor) + '</span>' : '') + '</div>'
    + (why ? '<p class="explain">' + mdInline(why) + '</p>' : '')
    + (narr || '<p class="empty">No T6 flow recorded for this use case.</p>');
  // Each step's element links locate that element in its home view; there is no flat full-map view to
  // spotlight the whole flow on, so the "Locate in full map" link is gone with the Components tab.
  bindFlowRefs();
}
// Drilling a Happy Path step opens its use case's flow (the step IS that use case) — the full T6
// narrative. Title = the step title. This is the DRILLED view's panel; a plain arrow-select is lighter
// (showHPArrow below).
function showHPStep(hpId) {
  const s = HP_BY_ID[hpId];
  if (!s) { panel.innerHTML = EMPTY_PANEL; return; }
  showFlowPanel(s.uc, s.title || s.id, s.why);
}
// Selecting a Happy Path ARROW (a step message, plain click on the overview) shows JUST the interaction
// it draws — the black-box `actor → System` handoff for that step — not the use case's full flow (that
// lives behind the drill / on the Use Cases tab). The step title says which step; the drilled view has
// the mechanism.
function showHPArrow(hpId) {
  const s = HP_BY_ID[hpId];
  if (!s) { panel.innerHTML = EMPTY_PANEL; return; }
  const actor = (HP_ACTOR_OF_STEP[hpId] && HP_ACTOR_OF_STEP[hpId].name)
    || ((GRAPH.nodes[s.uc] || {}).fields || {}).Actor || 'Actor';
  const sys = (GRAPH.nodes['SYS'] || {}).name || GRAPH.title || 'System';
  panel.innerHTML = '<div class="pane-title"><h2 class="hp-arrow">' + esc(actor)
    + ' <span class="hp-arrow-to">→</span> ' + esc(sys) + '</h2></div>'
    + (s.title ? '<p class="explain">' + esc(s.title) + '</p>' : '');
}
// The use-case view default panel (reached directly, not via a Happy Path position).
function showUseCase(uc) {
  showFlowPanel(uc, GRAPH.nodes[uc] ? GRAPH.nodes[uc].name : uc, '');
}
// The flow views (hpstep / usecase) are sequence diagrams — wire them like every other diagram, using
// the same sequence-diagram focus machinery the Happy Path uses (hpHighlight/hpFocus over element
// sets, since a participant is split across top box / label / lifeline / bottom mirror). Element
// participants select (focus to their messages + the other ends) / ⌘-open their source (component &
// entity leaves) / tooltip like nodes; message arrows select (the backbone edge, or the actor step) / focus / tooltip
// like edges; the role actor gets a meaning tooltip. message[i] <-> FLOWS_NARR[uc][i] (gen_flow_mermaid
// emits one message per ok step, in the order flow_narrative lists them).
// Mermaid centers a sequence-diagram message label over its arrow (text-anchor: middle, x = midpoint) —
// left-align it instead: pin the label's left edge just past the arrow's leftmost point, with a small
// padding, so a top-to-bottom read of the steps starts every label at the same x instead of one that
// drifts with each arrow's length. getBBox() (not x1/x2) works whether the arrow is a <line> or a <path>.
function leftAlignMessageLabels(texts, lineByIdx) {
  texts.forEach((text, i) => {
    const line = lineByIdx[i];
    if (!text || !line) return;
    let bb; try { bb = line.getBBox(); } catch (_) { return; }
    const em = parseFloat(getComputedStyle(text).fontSize) || 16;  // 1em gap, in the label's own units
    text.setAttribute('x', String(bb.x + em));
    text.setAttribute('text-anchor', 'start');
  });
}
function bindFlow(uc) {
  const scene = mainScene, root = scene.root;
  const steps = FLOWS_NARR[uc] || [];

  // Each participant's DOM parts (top box / lifeline / bottom mirror / label), keyed by the Mermaid
  // `name` attribute (== the participant id) — the one key BOTH box participants and the actor figure
  // carry (data-id sits only on the figure + lifelines). Labels carry no name, so match them by text.
  const elementIds = new Set();
  for (const st of steps) { if (st.srcId) elementIds.add(st.srcId); if (st.dstId) elementIds.add(st.dstId); }
  const labelEls = [...root.querySelectorAll('text.actor-box, text.actor-man')];
  const partsById = {};
  for (const id of elementIds) {
    if (!GRAPH.nodes[id]) continue;
    const sel = '[name="' + id + '"]';
    const parts = [root.querySelector('.actor-top' + sel), root.querySelector('line.actor-line' + sel),
                   root.querySelector('.actor-bottom' + sel)].filter(Boolean);
    for (const t of labelEls) if ((t.textContent || '').trim() === GRAPH.nodes[id].name) parts.push(t);
    if (!parts.length) continue;
    partsById[id] = parts;
    for (const el of parts) scene.dimEls.push(el);
    // colour the box by kind — every Mermaid `participant` is the same default box, so without this an
    // entity reads like a component. Top/bottom are <rect> (boxes); the lifeline <line> stays neutral.
    for (const el of parts) if (el.tagName === 'rect') applyTint(el, GRAPH.nodes[id].kind);
  }

  // messages: text[i] + arrow line[i] (data-id "i<idx>") pair with steps[i] — same pairing as bindHP.
  const texts = [...root.querySelectorAll('text.messageText')];
  const lineByIdx = {};
  root.querySelectorAll('.messageLine0, .messageLine1').forEach((ln) => {
    const m = (ln.getAttribute('data-id') || '').match(/^i(\d+)$/);
    if (m) lineByIdx[+m[1]] = ln;
  });
  leftAlignMessageLabels(texts, lineByIdx);
  const msgEls = steps.map((_, i) => [texts[i], lineByIdx[i]].filter(Boolean));
  for (const els of msgEls) for (const el of els) scene.dimEls.push(el);

  // element participants: select (focus to its messages + their other ends) / ⌘-drill to home / tooltip.
  for (const id of Object.keys(partsById)) {
    const parts = partsById[id], selKey = 'node:' + id;
    const myMsg = steps.map((st, i) => (st.srcId === id || st.dstId === id) ? i : -1).filter((i) => i >= 0);
    const select = () => {
      scene.selectedKey = selKey;
      showNode(id);
      const stepEls = myMsg.flatMap((i) => msgEls[i] || []);
      const keep = new Set([...parts, ...stepEls]);
      for (const i of myMsg) {
        for (const nb of [steps[i].srcId, steps[i].dstId]) for (const el of (partsById[nb] || [])) keep.add(el);
      }
      sceneSelect(scene, () => hpHighlight(scene, [...parts, ...stepEls]));
      hpFocus(scene, keep);
    };
    scene.selectors[selKey] = select;  // so back/forward can restore this participant selection
    const on = () => { if (scene.selectedKey !== selKey) for (const el of parts) el.style.filter = HOVER; };
    const off = () => { if (scene.selectedKey !== selKey) for (const el of parts) el.style.filter = hpRestFilter(scene, el); };
    for (const el of parts) {
      el.style.cursor = 'pointer';
      markOpenSrc(el, id);  // </> cursor on a component/entity leaf with a source ref, like the other diagrams
      el.addEventListener('mouseenter', on);
      el.addEventListener('mouseleave', off);
      attachTip(el, () => actionTipNode(id));  // ⌘-hover shows the open-source action
      el.addEventListener('click', (e) => {
        if (isDrag(e)) return;
        e.stopPropagation();
        if (openSrcClick(id, e)) return;  // ⌘-click opens source (component/entity), consistent with the rest
        select();
      });
    }
  }

  // role (actor) participants: same "select -> highlight my messages, dim the rest" as an element
  // participant above, just addressed differently — a Role has no graph node of its own, so
  // FLOW_ACTORS (gen_viewer.flow_actors) hands us its Mermaid alias (data-id) instead of a node id.
  // Mirrors bindHP's actor loop below, the same DOM shape (stick figure + lifeline).
  const bottoms = [...root.querySelectorAll('g.actor-man.actor-bottom')];
  // A step's endpoint that is a Role has no node id (srcId/dstId are null), so it can't be found via
  // partsById. Index each actor's DOM parts by the steps it drives (a.stepIdx) so selecting a step can
  // keep its actor endpoints lit, the same way partsById keeps its element endpoints. Without this, the
  // first step (typically actor -> component) dims its actor.
  const actorPartsByStep = {};
  for (const a of (FLOW_ACTORS[uc] || [])) {
    const selKey = 'flowactor:' + uc + ':' + a.aid;
    const figT = root.querySelector('.actor-top[data-id="' + a.aid + '"]');
    const life = root.querySelector('line.actor-line[data-id="' + a.aid + '"]');
    const figB = bottoms.find((g) => (g.textContent || '').trim() === a.name) || null;
    const parts = [figT, figB, life].filter(Boolean);
    if (!parts.length) continue;
    for (const el of parts) scene.dimEls.push(el);
    for (const i of a.stepIdx) (actorPartsByStep[i] || (actorPartsByStep[i] = [])).push(...parts);
    const select = () => {
      scene.selectedKey = selKey;
      showFlowActor(uc, a);
      const stepEls = a.stepIdx.flatMap((i) => msgEls[i] || []);
      const keep = new Set([...parts, ...stepEls]);
      for (const i of a.stepIdx) for (const nb of [steps[i].srcId, steps[i].dstId]) for (const el of (partsById[nb] || [])) keep.add(el);
      sceneSelect(scene, () => hpHighlight(scene, [...parts, ...stepEls]));
      hpFocus(scene, keep);
    };
    scene.selectors[selKey] = select;
    const on = () => { if (scene.selectedKey !== selKey) for (const el of parts) el.style.filter = HOVER; };
    const off = () => { if (scene.selectedKey !== selKey) for (const el of parts) el.style.filter = hpRestFilter(scene, el); };
    const click = (e) => { if (isDrag(e)) return; e.stopPropagation(); select(); };
    for (const el of parts) {
      if (el.tagName === 'line') continue;  // the lifeline gets a fat transparent hit (below)
      el.style.cursor = 'pointer';
      el.addEventListener('click', click);
      el.addEventListener('mouseenter', on);
      el.addEventListener('mouseleave', off);
    }
    if (life) attachEdgeHandlers(life, null, click, on, off, null);
  }

  // messages: select (the backbone edge for an element↔element step, else the step's own panel) / focus /
  // tooltip (the why). A step's arrow + label glow together; focus keeps them + both endpoints' columns.
  steps.forEach((st, i) => {
    const els = msgEls[i];
    if (!els.length) return;
    const text = texts[i] || null, line = lineByIdx[i] || null;
    const edge = (st.srcId && st.dstId) ? (COMP_LOOKUP[st.srcId + '>' + st.dstId] || [])[0] : null;
    const selKey = 'flowstep:' + uc + ':' + i;
    const doSelect = () => {
      scene.selectedKey = selKey;
      flowSyncCur(i);  // clicking a step's arrow directly moves the player's counter to it
      if (edge) showEdge(edge); else showFlowStep(uc, i);
      const keep = new Set(els);
      for (const end of [st.srcId, st.dstId]) for (const el of (partsById[end] || [])) keep.add(el);
      for (const el of (actorPartsByStep[i] || [])) keep.add(el);  // Role endpoints have no node id
      sceneSelect(scene, () => hpHighlight(scene, els));
      hpFocus(scene, keep);
    };
    scene.selectors[selKey] = doSelect;  // so back/forward can restore this flow-step selection
    const onClick = (ev) => {
      if (isDrag(ev)) return;
      ev.stopPropagation();
      doSelect();
    };
    const on = () => { if (scene.selectedKey !== selKey) for (const el of els) el.style.filter = HOVER; };
    const off = () => { if (scene.selectedKey !== selKey) for (const el of els) el.style.filter = hpRestFilter(scene, el); };
    if (line) attachEdgeHandlers(line, text, onClick, on, off, null);
    else { text.style.cursor = 'pointer'; text.style.setProperty('pointer-events', 'all', 'important'); text.addEventListener('click', onClick); text.addEventListener('mouseenter', on); text.addEventListener('mouseleave', off); }
  });

  // Hand the step player everything it needs to walk this flow: the ordered steps, each step's arrow+label
  // DOM (msgEls) and its endpoint columns (partsById). render() shows the strip and lands on step 1 once
  // svg-pan-zoom exists (centering needs it). No flow -> null, so the strip stays hidden.
  flowPlay = steps.length ? { uc, steps, msgEls, partsById, cur: -1 } : null;  // -1 = unstarted (see flowInit)
}
// --- use-case flow step player --------------------------------------------------
// Walk a flow's actions one at a time. Each step is selected exactly as a click on its arrow would —
// the same info pane, code viewer, glow and focus — then scrolled into view (only if it isn't already
// fully shown). The step player is just a driver over the arrows' own click selection, so stepping and
// clicking never diverge.
// Pan (not zoom) the diagram by (dx,dy) screen px with an ease-out — a short "scroll" so the eye can
// follow the jump between steps instead of teleporting. panBy is relative, so each frame applies only
// the delta since the last one; a new call cancels the in-flight one (rapid stepping recomputes from the
// current position in flowReveal, so it self-corrects).
let flowPanRAF = 0;
function flowAnimatePanBy(dx, dy) {
  if (flowPanRAF) { cancelAnimationFrame(flowPanRAF); flowPanRAF = 0; }
  if (!mainPz || (!dx && !dy)) return;
  const DUR = 260, start = performance.now();
  let done = 0;  // fraction of the full (dx,dy) already applied
  const ease = (t) => 1 - Math.pow(1 - t, 3);  // easeOutCubic
  const step = (now) => {
    const e = ease(Math.min(1, (now - start) / DUR));
    mainPz.panBy({ x: (e - done) * dx, y: (e - done) * dy });
    done = e;
    flowPanRAF = e < 1 ? requestAnimationFrame(step) : 0;
  };
  flowPanRAF = requestAnimationFrame(step);
}
// Bring step i into view with the LEAST scroll. Preferred target: the arrow + label + its two endpoint
// lifelines (the "from"/"to" columns), padded so those verticals show. If that whole span can't fit the
// viewport (a wide arrow, zoomed in), fall back to just the label — so you at least always see WHICH step
// you're on. Screen-space (getBoundingClientRect + panBy), immune to Mermaid's internal group transforms.
// Only the overflowing side is nudged in, so an already-visible axis never moves; a fully-visible target
// doesn't move at all. PAD keeps the target off the very edge.
const FLOW_PAD = 36;
function flowRect(items) {  // items: [{el, xOnly}] -> padded union rect in screen px, or null
  let l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
  for (const { el, xOnly } of items) {
    const q = el.getBoundingClientRect();
    if (!q || (!q.width && !q.height)) continue;
    l = Math.min(l, q.left); r = Math.max(r, q.right);
    if (!xOnly) { t = Math.min(t, q.top); b = Math.max(b, q.bottom); }
  }
  return isFinite(l) ? { l: l - FLOW_PAD, t: t - FLOW_PAD, r: r + FLOW_PAD, b: b + FLOW_PAD } : null;
}
function flowReveal(els, i) {
  if (!mainPz || !els || !els.length) return;
  const d = diagram.getBoundingClientRect();
  const st = flowPlay.steps[i];
  // preferred target: arrow + label (full extent) + both endpoint lifelines (x only, not the wide box).
  const items = els.map((el) => ({ el, xOnly: false }));
  for (const end of [st.srcId, st.dstId])
    for (const el of (flowPlay.partsById[end] || []))
      if (el.tagName === 'line') items.push({ el, xOnly: true });
  let box = flowRect(items);
  if (!box) return;
  if (box.r - box.l > d.width || box.b - box.t > d.height) {   // too big to show in full -> just the label
    const label = els.find((e) => e.classList && e.classList.contains('messageText'));
    box = label ? flowRect([{ el: label, xOnly: false }]) : null;
    if (!box || box.r - box.l > d.width || box.b - box.t > d.height) return;  // even the label can't fit
  }
  let dx = 0, dy = 0;
  if (box.l < d.left) dx = d.left - box.l; else if (box.r > d.right) dx = d.right - box.r;
  if (box.t < d.top) dy = d.top - box.t; else if (box.b > d.bottom) dy = d.bottom - box.b;
  if (!dx && !dy) return;   // already fully visible -> stay put
  flowAnimatePanBy(dx, dy);
}
// cur === -1 is the "unstarted" state: no step selected yet, but the counter reads "Step 1 / N" so the
// first Next lands on step 1 (not step 2). Stepping wraps around the ends, so once started neither button
// disables; Prev stays disabled only while unstarted (where it does nothing).
function flowCounter() {
  if (!flowPlay) return;
  const n = flowPlay.steps.length, i = flowPlay.cur;
  flowcount.textContent = 'Step ' + (i < 0 ? 1 : i + 1) + ' / ' + n;
  flowprev.disabled = i < 0;   // truly inert only while unstarted; once started, Prev wraps past step 1
  flownext.disabled = false;   // Next is always live: unstarted -> step 1, last -> wraps to step 1
  // Grey (but still clickable) at the ends: Prev on step 1, Next on the last step — the old end-of-list look.
  flowprev.classList.toggle('flowend', i <= 0);       // step 1 (and unstarted, which is also :disabled)
  flownext.classList.toggle('flowend', i >= n - 1);   // last step
}
// Move the counter to step i without re-highlighting — used when a click on the arrow already selected it.
function flowSyncCur(i) { if (flowPlay) { flowPlay.cur = i; flowCounter(); } }
// Go to step i: select its arrow exactly as a manual click would (same info pane, code viewer, glow and
// focus — via the step's registered selector), then scroll it into view if needed. Delegating to the click
// selector keeps stepping and clicking in sync by design.
function flowGoto(i) {
  if (!flowPlay || !flowPlay.steps.length) return;
  const n = flowPlay.steps.length;
  i = Math.max(0, Math.min(n - 1, i));
  const sel = mainScene.selectors['flowstep:' + flowPlay.uc + ':' + i];
  if (sel) sel(); else flowPlay.cur = i;  // sel() runs doSelect, which calls flowSyncCur(i) -> cur + counter
  flowReveal(flowPlay.msgEls[i] || [], i);
  flowCounter();
}
// From the unstarted state, Next selects step 1 (and Prev does nothing); once started, step by ±1 and wrap
// around the ends (Next past the last -> step 1, Prev before step 1 -> the last).
function flowStepBy(d) {
  if (!flowPlay) return;
  const n = flowPlay.steps.length;
  if (flowPlay.cur < 0) { if (d > 0) flowGoto(0); return; }
  flowGoto((flowPlay.cur + d + n) % n);
}
// Called from render() once svg-pan-zoom exists. Shows the strip. A back/forward revisit that restored a
// selected step starts there; a fresh open is UNSTARTED — nothing selected, the overview panel stays, and
// the counter sits ready at step 1 (the first Next selects it).
function flowInit() {
  if (!flowPlay || !flowPlay.steps.length) { flowplayer.hidden = true; return; }
  flowplayer.hidden = false;
  const m = (mainScene.selectedKey || '').match(/^flowstep:.*:(\d+)$/);
  flowPlay.cur = m ? +m[1] : -1;
  flowCounter();
}
// A flow message's side panel for an ACTOR step (an element↔element step shows its backbone edge instead).
// `Why` is this step's one explanation field — plain prose, no label, like every other panel now.
function showFlowStep(uc, i) {
  const st = (FLOWS_NARR[uc] || [])[i];
  if (!st) { panel.innerHTML = EMPTY_PANEL; return; }
  const end = (label, id) => id ? '<a href="#" class="flowref" data-id="' + esc(id) + '">' + esc(label) + '</a>' : esc(label);
  panel.innerHTML = '<div class="pane-title"><h2>' + end(st.src, st.srcId) + ' &rarr; ' + end(st.dst, st.dstId) + '</h2>'
    + '<span class="badge edge">' + esc(st.verb) + '</span></div>'
    + (st.why ? '<p class="explain">' + mdInline(st.why) + '</p>' : '')
    + (st.note ? '<dl><dt>Note</dt><dd>' + mdInline(st.note) + '</dd></dl>' : '');
  bindFlowRefs();
}
// One actor's card: its kind, what its role wants (the explanation), and the Happy Path steps it drives.
function showHPActor(a) {
  const kindBadge = a.kind ? '<span class="badge kind">' + esc(a.kind) + '</span>' : '';
  const drives = (a.steps || []).map((st) =>
    '<dd>' + esc(st.title || st.id) + '</dd>').join('');
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(a.name) + '</h2>' + kindBadge + '</div>'
    + (a.wants ? '<p class="explain">' + mdInline(a.wants) + '</p>' : '')
    + (drives ? '<dl><dt>Drives</dt>' + drives + '</dl>' : '');
}
// A flow-level actor's card — the same idea as showHPActor, scoped to one flow: its kind, what its
// role wants, and which of THIS flow's own steps it drives. Reads those steps straight out of
// FLOWS_NARR by index rather than duplicating their text in FLOW_ACTORS.
function showFlowActor(uc, a) {
  const kindBadge = a.kind ? '<span class="badge kind">' + esc(a.kind) + '</span>' : '';
  const flowSteps = FLOWS_NARR[uc] || [];
  const drives = a.stepIdx.map((i) => flowSteps[i]).filter(Boolean)
    .map((st) => '<dd>' + esc(st.src) + ' <em>' + esc(st.verb) + '</em> ' + esc(st.dst) + '</dd>').join('');
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(a.name) + '</h2>' + kindBadge + '</div>'
    + (a.wants ? '<p class="explain">' + mdInline(a.wants) + '</p>' : '')
    + (drives ? '<dl><dt>Drives</dt>' + drives + '</dl>' : '');
}

// --- hover tooltip --------------------------------------------------------------
// A floating card that, while ⌘ is held, previews the ⌘-click action ("Open in <editor>", "Drill into
// subsystem", …) — a plain hover (no ⌘) shows nothing, since selecting (which fills the side panel) is
// where an element's own description lives. One reused <div id="tip">; pointer-events:none in CSS so it
// never steals the hover or the click. All graph text goes through esc().
function moveTip(x, y) {  // below-right of the cursor; flip toward the cursor if it would overflow the viewport
  const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
  let nx = x + pad, ny = y + pad;
  if (nx + w > window.innerWidth - 6) nx = x - pad - w;
  if (ny + h > window.innerHeight - 6) ny = y - pad - h;
  tip.style.left = Math.max(6, nx) + 'px';
  tip.style.top = Math.max(6, ny) + 'px';
}
function hideTip() { tip.classList.remove('on'); }
// The element currently under the cursor and its `actionFn` (what a ⌘-click does here, or null). Held so
// pressing/releasing ⌘ can swap the tooltip live, without waiting for a new mouse event (see setCmd).
let hover = null;
function renderHoverTip() {
  if (!hover || !hover.actionFn || !document.body.classList.contains('cmd')) { hideTip(); return; }
  const html = hover.actionFn();
  if (!html) { hideTip(); return; }
  tip.innerHTML = html;
  tip.classList.add('action');
  tip.classList.add('on');
  moveTip(hover.x, hover.y);
}
// Wire an element so, while ⌘ is held, it previews `actionFn()`. No `actionFn` -> never shows a tooltip.
function attachTip(el, actionFn) {
  el.addEventListener('mouseenter', (ev) => { hover = { actionFn: actionFn || null, x: ev.clientX, y: ev.clientY }; renderHoverTip(); });
  el.addEventListener('mousemove', (ev) => { if (hover) { hover.x = ev.clientX; hover.y = ev.clientY; } moveTip(ev.clientX, ev.clientY); });
  el.addEventListener('mouseleave', () => { hover = null; hideTip(); });
}
// While ⌘ is held, the hovered element's tooltip describes the ⌘-click action (drill in / open source)
// instead of its meaning. Two lines: a bold action line ("Open in <dest>" / "Open subsystem"), then the
// specific target (file path / name) on its own line so a long path gets full width (see #tip.action).
// Return null for elements with no ⌘ action (the meaning preview then stays).
function openDestName() {
  const id = openTargetId();
  if (id === 'github') return 'GitHub';
  if (id === 'native') return null;            // nothing chosen yet — the click opens Settings first
  if (id === 'custom') return 'your editor';
  const t = OPEN_TARGETS.find((x) => x.id === id);
  return t ? t.label : 'your editor';
}
function actionOpenSrcHtml(n) {
  const path = cleanPath(n.file, n.line) + (n.line ? ':' + n.line : '');
  const dest = openDestName();
  return '<div class="tt">' + (dest ? 'Open in ' + esc(dest) : 'Open source') + '</div>'
       + '<div class="tpath">' + esc(path) + '</div>';
}
function actionTipNode(id) {
  const n = GRAPH.nodes[id];
  if (!n) return null;
  if (id === 'SYS') {
    // ⌘-click on the System drills into its internals — Subsystems when the map groups, else the Domain.
    // Only the Context view wires that drill (markSysDrill tags the box); elsewhere SYS just selects, so
    // gate the action tooltip on the drill affordance actually being present.
    const sys = mainScene.nodeEls['SYS'];
    if (sys && sys.classList.contains('drill'))
      return '<div class="tt">' + (HAS_GROUPING ? 'Show subsystems' : 'Show domain') + '</div>';
    return null;
  }
  if (srcNode(id)) return actionOpenSrcHtml(n);
  if (String(n.kind) === 'subsystem')
    return '<div class="tt">Open subsystem</div><div class="tm">' + esc(n.name) + '</div>';
  if (String(n.kind) === 'subdomain')
    return '<div class="tt">Open subdomain</div><div class="tm">' + esc(n.name) + '</div>';
  if (id === LIBS_ID)
    return '<div class="tt">Open Libraries</div><div class="tm">' + FOLDED_LIBS.length + ' bundled</div>';
  return null;
}
function actionTipEdge(a, b) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  return '<div class="tt">Open</div><div class="tm">' + esc(nm(a)) + ' &rarr; ' + esc(nm(b)) + '</div>';
}
function actionTipHP(hpId) {
  const s = HP_BY_ID[hpId];
  return '<div class="tt">Open step</div>' + (s && s.title ? '<div class="tm">' + esc(s.title) + '</div>' : '');
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

// --- diff overlay on the Subsystems views ---------------------------------------
// The change-impact diff used to be a tab of its own (the flat Components map). It now overlays the
// Subsystems views: per-component badges in the cards are added by bindNodes (mode==='diff'); the two
// things bindNodes can't do live here. (1) The Subsystems OVERVIEW draws subsystem boxes (not via
// bindNodes), so badge each box with its subtree's aggregate change. (2) That overview's default panel
// becomes a change-impact summary listing every changed element — including ADDED ones, which have no
// box anywhere to badge.
function subsystemDiffState(sid) {
  if (DIFF_STATE[sid]) return DIFF_STATE[sid];     // the subsystem itself changed
  let changed = false, rippled = false;
  for (const id in DIFF_STATE) {
    if (!isAncestorOf(sid, id)) continue;          // only changes inside this box's subtree
    if (DIFF_STATE[id] === 'rippled') rippled = true; else changed = true;
  }
  return changed ? 'modified' : (rippled ? 'rippled' : null);
}
function applyDiffOverlay(s) {
  if (s.kind === 'container') {                     // overview: badge each subsystem box with its subtree's change
    for (const id in mainScene.nodeEls) {
      const st = subsystemDiffState(id);
      if (st) addBadge(mainScene.nodeEls[id], st);
    }
  } else if (s.kind === 'subsystem' || s.kind === 'edge' || s.kind === 'component') {  // cards: per-node badge
    for (const id in mainScene.nodeEls) {
      if (DIFF_STATE[id]) addBadge(mainScene.nodeEls[id], DIFF_STATE[id]);
    }
  }
}
// The Subsystems-overview panel in diff mode: every changed element grouped by state, each name
// clickable to locate it in its home view. Added elements appear here even though they badge no box.
function showDiffSummary() {
  const order = ['added', 'modified', 'deleted', 'rippled'];
  const groups = { added: [], modified: [], deleted: [], rippled: [] };
  for (const id in DIFF_STATE) { const st = DIFF_STATE[id]; if (groups[st]) groups[st].push(id); }
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  const total = order.reduce((sum, k) => sum + groups[k].length, 0);
  let html = '<h2>Change impact</h2>'
    + '<div class="badges"><span class="badge kind">' + total + ' change' + (total === 1 ? '' : 's') + '</span></div>';
  for (const st of order) {
    const ids = groups[st];
    if (!ids.length) continue;
    ids.sort((a, b) => nm(a).localeCompare(nm(b)));
    html += '<dl><dt><span class="badge ' + st + '">' + st + '</span></dt>'
      + ids.map((id) => {
          const n = GRAPH.nodes[id];
          const kind = n && n.kind ? ' <span class="muted">' + esc(n.kind) + '</span>' : '';
          return '<dd><a href="#" class="diffref" data-id="' + esc(id) + '">' + esc(nm(id)) + '</a>' + kind + '</dd>';
        }).join('') + '</dl>';
  }
  if (!total) html += '<p class="empty">No changes recorded.</p>';
  panel.innerHTML = html;
  panel.querySelectorAll('a.diffref').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault(); selectFromTree(a.getAttribute('data-id'));
  }));
}

function idOf(el) {
  const cls = [...el.classList].find((c) => c.startsWith('cy-'));
  if (cls) return cls.slice(3);
  const dataId = el.getAttribute('data-id');
  if (dataId && GRAPH.nodes[dataId]) return dataId;
  const m = (el.id || '').match(/(?:^|-)((?:UC|HP|SD|C|D|E|S)\d+)(?:-|$)/);  // SD before S: a subdomain id is not a subsystem
  return m ? m[1] : null;
}
// Walk an id's parent chain up to its top-level subdomain (or null) — the domain mirror of a top
// subsystem. Used to key a bridge card from a domain-edge-card bridge arrow (subsystem → entity).
function topSubdomainOf(id) {
  let cur = id; const seen = new Set();
  while (cur && !seen.has(cur)) {
    seen.add(cur);
    const n = GRAPH.nodes[cur];
    if (!n) return null;
    if (n.kind === 'subdomain') return cur;
    cur = n.parent;
  }
  return null;
}

// --- shared binding -------------------------------------------------------------
// The box's own drawn shape (rect/polygon/path/circle) — the first such descendant in document order,
// which is always the shape Mermaid draws before any label and before the corner action icon (see
// addActionIcon, appended last). A glow filter belongs on THIS, never on the group itself: `filter` on
// an SVG group is a post-process pass over its whole rendered subtree, so a filter on the group would
// bleed onto the action icon (a child of the same group) — there is no way for the icon to "opt out"
// of an ancestor's filter, the filter has to simply not be applied above it in the first place.
function shapeOf(el) { return el.querySelector('rect, polygon, path, circle') || el; }
// Selection highlight for a node/frame — HILITE filter (on the shape, not the group — see shapeOf) +
// an `is-selected` class on the group, so a selected box's corner action icon (if it has one) stays
// visible after the cursor leaves it, instead of only ever showing on hover. The node analog of
// glowEdge (edges have no action icon, so no class needed there).
function glowNode(el) {
  shapeOf(el).style.filter = HILITE;
  el.classList.add('is-selected');
  return () => { shapeOf(el).style.filter = ''; el.classList.remove('is-selected'); };
}
// Hover glow — same shape-only rule as glowNode, so hovering a box's corner action icon (visually
// inside the box) never tints the icon itself; the icon has its own :hover reaction (viewer.css).
// Skipped while the node is the active selection, so glowNode's HILITE wins over a lingering hover.
function bindHoverGlow(scene, el, id) {
  const shape = shapeOf(el);
  el.addEventListener('mouseenter', () => { if (scene.selectedKey !== 'node:' + id) shape.style.filter = HOVER; });
  el.addEventListener('mouseleave', () => { if (scene.selectedKey !== 'node:' + id) shape.style.filter = ''; });
}
// Select a normal node within a scene: show + highlight + focus. Re-selecting the current node just
// re-applies the same state (a harmless no-op) — clicking an already-selected element never deselects
// it; a click on empty canvas space or Escape are the only ways back to the default panel.
function selectNode(scene, el, id) {
  scene.selectedKey = 'node:' + id;
  showNodeDetailSynced(id);  // mirrors into the file browser (graph -> tree) as a side effect
  sceneSelect(scene, () => glowNode(el));
  // Dim to this node's neighbourhood only when the node is drawn in this scene; a box that isn't
  // registered (e.g. a neighbourhood's external subsystem) would otherwise dim everything around it.
  if (scene.nodeEls[id]) focusNode(scene, id); else clearFocus(scene);
}

// Canvas-click selection: applies the selection, then decides what (if anything) happens to the
// camera. A plain click holds the view perfectly still — auto-panning would fight a reader who clicked
// a box precisely BECAUSE it was already comfortably in view. Only a shift-click reframes, zooming to
// match the sidebar's text size (matchTextSize). selectFromTree applies matchTextSize unconditionally
// for a file-tree-driven selection — there's no modifier key on a tree row to gate it on.
function selectNodeFromCanvas(el, id, e) {
  selectNode(mainScene, el, id);
  if (e && e.shiftKey) matchTextSize(el);
}

// The zoom-by-`scale`-then-recenter step behind matchTextSize (scale === 1 skips straight to just
// centering). Measures el/diagram BEFORE any mutation: svg-pan-zoom's zoom() only updates its internal
// state synchronously — the CTM it actually paints is applied on the NEXT animation frame (see
// `updateCTMOnNextFrame` in the vendored lib) — so a getBoundingClientRect() taken right after would
// still read the OLD, pre-zoom geometry. zoomAtPoint anchors on the SVG's own center, which is exactly
// `diagramRect`'s center (the svg fills #diagram, which sits below the header — not the whole #stage) —
// so the post-zoom position is derived analytically (every point scales toward/away from that shared
// center by `scale`) instead of re-measured.
function applyZoomAndCenter(el, scale) {
  const stageRect = diagram.getBoundingClientRect();
  const stageCx = stageRect.left + stageRect.width / 2, stageCy = stageRect.top + stageRect.height / 2;
  const elRect = el.getBoundingClientRect();
  let elCx = elRect.left + elRect.width / 2, elCy = elRect.top + elRect.height / 2;
  if (scale !== 1) {
    mainPz.zoom(mainPz.getZoom() * scale);
    elCx = stageCx + (elCx - stageCx) * scale;
    elCy = stageCy + (elCy - stageCy) * scale;
  }
  const dx = stageCx - elCx;
  const dy = stageCy - elCy;
  if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;  // already centered — skip the no-op pan (+ its animation)
  const vp = diagram.querySelector('.svg-pan-zoom_viewport');
  // A brief transition on the pan/zoom transform (svg-pan-zoom sets it via inline `style.transform`),
  // toggled on JUST for this programmatic move — never left on during a drag-pan, or every mousemove
  // frame would visibly lag behind the cursor. Disabled under prefers-reduced-motion by the matching
  // viewer.css rule, the same way flashIcon's own animation already is.
  if (vp) { vp.classList.add('pan-anim'); setTimeout(() => vp.classList.remove('pan-anim'), 300); }
  mainPz.panBy({ x: dx, y: dy });
}

// Every node's (or container's) zoom-to-match-sidebar-text-size move: reads the panel's normal text
// size and the box's OWN name label's current on-screen size, then zooms so the two match exactly
// (even if that then runs the box past the visible edges — matching the text size wins over fitting on
// screen). Triggered by a shift-click on a box, or ANY file-tree click that resolves to one — a plain
// canvas click never calls this (see selectNodeFromCanvas): it holds the view still instead.
function matchTextSize(el) {
  if (!mainPz || !el) return;
  // The box's own name label: Mermaid renders a flowchart/namespace box's label as HTML — a
  // `.nodeLabel` span inside a `foreignObject` — not an SVG `<text>` element; `text` is only a fallback
  // for any collapsed-box rendering that draws its label directly in SVG.
  const textEl = el.querySelector('.nodeLabel') || el.querySelector('text');
  const vp = diagram.querySelector('.svg-pan-zoom_viewport');
  if (!textEl || !vp) return;
  const rawScale = new DOMMatrixReadOnly(vp.style.transform).a;  // current SVG-unit -> CSS-px scale
  // The label's OWN font-size is in SVG user units and unaffected by the pan/zoom transform (computed
  // style ignores ancestor `transform`) — multiplying by rawScale gives its actual on-screen size.
  const onScreenFontSize = parseFloat(getComputedStyle(textEl).fontSize) * rawScale;
  const targetFontSize = parseFloat(getComputedStyle(panel).fontSize);  // the sidebar's normal text size
  if (!onScreenFontSize || !targetFontSize) return;
  applyZoomAndCenter(el, targetFontSize / onScreenFontSize);
}

// Select the collapsed Libraries box: highlight + show its roster (showLibsFold), and dim to its
// neighbourhood (the System + the SYS→box arrow) just like selecting a dependency — the bundles arrow
// is a registered context edge, so focusNode resolves the connection. Reuses the node selKey so
// bindNodes' hover guard matches and the selection glow isn't overwritten by a passing hover.
function selectLibsFold(scene, el) {
  const selKey = 'node:' + LIBS_ID;
  scene.selectedKey = selKey;
  showLibsFold();
  sceneSelect(scene, () => glowNode(el));
  if (scene.nodeEls[LIBS_ID]) focusNode(scene, LIBS_ID); else clearFocus(scene);
}
// Tag the Libraries box with the drill cursor (it ⌘-drills into the full list), like subsystem boxes.
function markLibsDrill() {
  const el = mainScene.nodeEls[LIBS_ID];
  if (el) el.classList.add('drill');
}
// Where ⌘-clicking the System box drills: the Subsystems overview when the map groups (it always does
// once a default subsystem is injected for component-bearing maps), else the Domain model, else nowhere.
function sysDrillTarget() {
  if (HAS_GROUPING) return { kind: 'container' };
  if (HAS_DOMAIN) return { kind: 'domain' };
  return null;
}
// Tag the System box with the drill cursor — only when there's somewhere to drill into.
function markSysDrill() {
  const el = mainScene.nodeEls['SYS'];
  if (el && sysDrillTarget()) el.classList.add('drill');
}

function bindNodes(scene, onActivate) {
  scene.root.querySelectorAll('g.node').forEach((el) => {
    const id = idOf(el);
    if (!id || !GRAPH.nodes[id]) return;
    // Every drawn box joins the focus set, so selecting a node keeps only its connected boxes lit and
    // dims the rest — collapsed neighbour boxes (subsystems/subdomains) included, the same as the
    // members. (Their bridge/cross arrows are registered as edges, so focus resolves the connection.)
    scene.nodeEls[id] = el;
    el.style.cursor = 'pointer';
    markOpenSrc(el, id);  // leaf with a source ref -> ⌘-held cursor shows the open-source affordance
    bindHoverGlow(scene, el, id);  // hover affordance — skip while this node is the active selection, so HILITE wins
    attachTip(el, () => actionTipNode(id));  // ⌘-hover shows the open-source action
    el.addEventListener('click', (e) => {
      if (isDrag(e)) return;  // tail of a drag-pan, not a real click
      e.stopPropagation();
      if (openSrcClick(id, e)) return;  // ⌘-click a leaf with a source ref opens it instead of selecting
      onActivate(id, el, e);
    });
    // Diff badges are NOT added here: applyDiffOverlay() owns them, so they appear only on the
    // Subsystems-family views (and the dormant Components view) — never as strays in Context/Libraries
    // where bindNodes also runs but the diff legend is hidden.
  });
}

// Convert a real mouse position (client/screen px) into `referenceEl`'s own local coordinate space —
// the same space its `transform="translate(x,y)"` is interpreted in. getScreenCTM() already folds in
// EVERY transform between here and the screen (pan, zoom, nested groups), so this works at any zoom
// without knowing anything about svg-pan-zoom's internals, unlike the counter-scale math elsewhere in
// this file (which has to, because it's deliberately UNDOING one specific transform, not converting
// between spaces). Returns null if the element isn't laid out yet (detached, or a zero-size viewport).
function clientToLocal(referenceEl, clientX, clientY) {
  const svg = referenceEl.ownerSVGElement;
  const ctm = svg && referenceEl.getScreenCTM();
  if (!svg || !ctm) return null;
  const pt = svg.createSVGPoint();
  pt.x = clientX; pt.y = clientY;
  const local = pt.matrixTransform(ctm.inverse());
  return { x: local.x, y: local.y };
}
// Convert a point given in `fromEl`'s own local space (e.g. straight out of `fromEl.getBBox()`) into
// `toEl`'s local space instead — needed whenever the two don't share a coordinate system. A Happy
// Path message's <text> carries no transform of its own, so its bbox already happens to line up with
// its parent's space (addLabelActionIcon relied on exactly that, harmlessly). A Mermaid edge label
// (`g.edgeLabel`) is NOT so simple — Mermaid positions it via a transform on the group itself, so its
// bbox is in a DIFFERENT space than its parent's, and anchoring a pill there with the naive bbox math
// placed it nowhere near the label. Routing through screen space via getScreenCTM (twice) sidesteps
// the question of whose transform is whose entirely — it folds in every transform on both ends,
// whatever they turn out to be, the same trick clientToLocal uses for a real cursor position.
function pointToHostSpace(fromEl, x, y, toEl) {
  const svg = fromEl.ownerSVGElement;
  const fromCtm = svg && fromEl.getScreenCTM();
  const toCtm = svg && toEl.getScreenCTM();
  if (!svg || !fromCtm || !toCtm) return null;
  const pt = svg.createSVGPoint();
  pt.x = x; pt.y = y;
  const screenPt = pt.matrixTransform(fromCtm);
  const hostPt = screenPt.matrixTransform(toCtm.inverse());
  return { x: hostPt.x, y: hostPt.y };
}
// Fallback anchor for an edge's drill pill: the arrow's own midpoint, nudged off to the side (along
// the perpendicular to the line there) so the pill doesn't sit right on top of the stroke. Only used
// when the pill has to show WITHOUT ever having been hovered (see bindEdgeActionIcon) — the normal
// case anchors to the cursor instead, which needs no such geometry.
function edgeMidpointAnchor(p) {
  let len; try { len = p.getTotalLength(); } catch (_) { return null; }
  if (!len) return null;
  const mid = len / 2;
  const a = p.getPointAtLength(Math.max(0, mid - 1));
  const b = p.getPointAtLength(Math.min(len, mid + 1));
  const dx = b.x - a.x, dy = b.y - a.y;
  const segLen = Math.hypot(dx, dy) || 1;
  const OFFSET = 20;
  const c = p.getPointAtLength(mid);
  return { x: c.x + (-dy / segLen) * OFFSET, y: c.y + (dx / segLen) * OFFSET };
}
// A real label (not Mermaid's empty placeholder group every unlabelled arrow still gets) — content
// check, not just existence, since an empty label would otherwise read as "has a label" and anchor a
// pill to a bbox with no actual size.
function edgeLabelHasContent(label) {
  return !!(label && (label.textContent || '').trim());
}
// A drillable edge's pill has no box corner to anchor to. Two cases:
//  - A real label: same fixed convention as a Happy Path message (addLabelActionIcon) — sits just
//    left of the label, one constant spot, not one that chases the cursor around as it moves along
//    the arrow (a moving target is harder to click, not easier, once the label already tells you
//    where to look).
//  - No label at all: there's no fixed spot that makes sense, so the pill appears wherever the cursor
//    first lands on the arrow instead — the pill IS the cursor's own position, so there's no gap to
//    travel and no bridge needed. Falls back to the arrow's own midpoint the one time it has to show
//    without a hover to anchor to (a selection restored from back/forward, or lit up by something else
//    being selected).
// `p` is the real (visible, styled, dimmable) path — its id and its opacity (dim state) are what
// matter for the pill's identity and visibility. `hit` is the wide invisible clone that actually
// catches the pointer (see attachEdgeHandlers) — hovering/leaving THAT, not the thin original stroke,
// is what should show/hide the pill, so listeners go on it, not on `p`. `isSelected` (from
// bindSelectEdge, matching hpGlow's `scene.selectedKey !== selKey` guard) is what lets the pill stay
// up after a selection even once the cursor leaves — without it, hide() would blank a pill glowEdge
// just pinned the moment the mouse moved off the arrow.
function bindEdgeActionIcon(p, hit, label, onDrill, isSelected) {
  const id = p.id || ('edgepill' + (EDGE_ICON_SEQ++));
  const action = { kind: 'drill', run: onDrill };
  const isDim = () => p.style.opacity === DIM || (label && label.style.opacity === DIM);
  const hide = () => { if (!isSelected || !isSelected()) hideIcon(icon); };
  let icon, showAt;
  if (edgeLabelHasContent(label)) {
    addLabelActionIcon(label, id, action);
    icon = ACTION_ICONS[id];
    showAt = () => { if (!isDim()) showIcon(icon); };
    if (icon._bridge) { icon._bridge.addEventListener('mouseenter', showAt); icon._bridge.addEventListener('mouseleave', hide); }
  } else {
    const host = p.parentNode;
    const fallback = edgeMidpointAnchor(p) || { x: 0, y: 0 };
    addActionIcon(p, id, action, { host, anchor: fallback });
    icon = ACTION_ICONS[id];
    const moveTo = (anchor) => {
      icon._anchor = anchor;
      icon.setAttribute('transform', `translate(${anchor.x},${anchor.y}) scale(${curIconInv()})`);
    };
    showAt = (ev) => { if (isDim()) return; moveTo(clientToLocal(host, ev.clientX, ev.clientY) || fallback); showIcon(icon); };
  }
  icon.addEventListener('mouseenter', showAt);
  icon.addEventListener('mouseleave', hide);
  hit.addEventListener('mouseenter', showAt);
  hit.addEventListener('mouseleave', hide);
  if (label) { label.addEventListener('mouseenter', showAt); label.addEventListener('mouseleave', hide); }
  // Lets glowEdge (selection) show/hide this pill the same way hpGlow does for a Happy Path step.
  p._actionIcon = icon;
}
// Give an edge's visible path a wide transparent hit-path + make its label clickable.
// `tipHtml` (optional) wires a hover meaning-preview on the same hit-area + label.
// `onDrill` (falsy for a non-drillable edge) doubles as the drill callback for the corner pill AND the
// flag for the ⌘-held cursor affordance — a drillable edge always gets both together. `isSelected`
// (only meaningful alongside onDrill) is passed straight through to bindEdgeActionIcon.
function attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff, onDrill, actionFn, isSelected) {
  const hit = p.cloneNode(false);
  hit.removeAttribute('id'); hit.removeAttribute('marker-end'); hit.removeAttribute('class');
  hit.style.setProperty('stroke', 'transparent', 'important');
  hit.style.setProperty('stroke-width', '14px', 'important');
  hit.style.setProperty('fill', 'none', 'important');
  hit.style.setProperty('marker-end', 'none', 'important');
  hit.style.pointerEvents = 'stroke'; hit.style.cursor = 'pointer';
  if (onDrill) hit.classList.add('drill');  // ⌘-held cursor affordance
  hit.addEventListener('click', onClick);
  hit.addEventListener('mouseenter', hoverOn);
  hit.addEventListener('mouseleave', hoverOff);
  p.parentNode.appendChild(hit);
  if (label) {
    label.style.cursor = 'pointer';
    label.style.setProperty('pointer-events', 'all', 'important');
    if (onDrill) label.classList.add('drill');
    label.addEventListener('click', onClick);
    label.addEventListener('mouseenter', hoverOn);
    label.addEventListener('mouseleave', hoverOff);
  }
  if (actionFn) { attachTip(hit, actionFn); if (label) attachTip(label, actionFn); }
  if (onDrill) bindEdgeActionIcon(p, hit, label, onDrill, isSelected);
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
  // A drillable edge's pill (see bindEdgeActionIcon) sticks while selected, same as hpGlow does for a
  // Happy Path step — otherwise selecting the edge (without ever hovering it) would leave no way to
  // see its drill option short of hovering again.
  if (p._actionIcon) showIcon(p._actionIcon);
  return () => {
    p.style.removeProperty('stroke'); p.style.removeProperty('stroke-width');
    if (label) label.style.filter = '';
    if (p._actionIcon) hideIcon(p._actionIcon);
  };
}

// Wire one edge for the SELECT model (highlight + focus + panel) — context, components, internal edges.
// `opts.onDrill` (optional) makes a ⌘-click drill instead of select, and marks the arrow with the drill
// cursor; `opts.actionFn` (optional) is what a ⌘-hover previews for that drill.
function bindSelectEdge(scene, p, label, e, selKey, showFn, opts) {
  opts = opts || {};
  const hoverOn = () => { if (scene.selectedKey !== selKey) { p.style.filter = HOVER; if (label) label.style.filter = HOVER; } };
  const hoverOff = () => { if (scene.selectedKey !== selKey) { p.style.filter = ''; if (label) label.style.filter = ''; } };
  const doSelect = () => {
    scene.selectedKey = selKey;
    showFn(); sceneSelect(scene, () => glowEdge(p, label));
    // Dim to the edge only when its endpoints are drawn here; an aggregated arrow whose ends aren't
    // (e.g. a neighbourhood's cross arrow) would otherwise dim the whole view.
    if (scene.nodeEls[e.src] || scene.nodeEls[e.dst]) focusEdge(scene, e); else clearFocus(scene);
  };
  scene.selectors[selKey] = doSelect;  // so back/forward can restore this edge selection
  const onClick = (ev) => {
    if (isDrag(ev)) return;  // tail of a drag-pan, not a real click
    ev.stopPropagation();
    if (opts.onDrill && isDrillClick(ev)) { hoverOff(); opts.onDrill(); return; }  // ⌘-click drills in
    hoverOff();  // drop the hover glow before selecting, so it can't linger under HILITE
    doSelect();
  };
  scene.edgeEls.push({ e, path: p, label });
  attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff, opts.onDrill, opts.actionFn, () => scene.selectedKey === selKey);
}

// An inter-subsystem arrow (Subsystems map + neighbourhood cross arrows): a plain click SELECTS it —
// the sidebar lists every component→component crossing it bundles — and a ⌘-click drills into the
// two-subsystem edge view. Reuses the select-edge machinery with a container-edge panel + tip.
// `focusE` overrides the endpoints used for the focus/dim pass (not the select/drill, which always act
// on the subsystem pair a→b). In the Subsystems overview the drawn arrow IS a→b, so it's omitted; in a
// subsystem card the arrow is drawn component→neighbour, so the caller passes the DRAWN endpoints —
// otherwise selecting the component wouldn't keep its own cross arrow + the neighbour box lit.
function bindContainerEdge(scene, p, label, a, b, focusE) {
  bindSelectEdge(scene, p, label, focusE || { src: a, dst: b }, 'sedge:' + a + '>' + b,
    () => showContainerEdge(a, b),
    { onDrill: () => go({ kind: 'edge', a, b }), actionFn: () => actionTipEdge(a, b) });
}
// A bridge arrow across the structural↔domain groupings (component↔subdomain in a subsystem card,
// subsystem↔entity in a subdomain card, labelled owns/reads). Registered as an edge with its DRAWN
// endpoints so a focus pass keeps it + both ends lit; a plain click shows the collapsed `box`'s panel,
// a ⌘-click drills into `target` (that box's own card). The bridge has no `why`, so the default tip
// shows nothing on hover — consistent with a why-less component edge.
function bindBridgeEdge(scene, p, label, a, b, target, box) {
  bindSelectEdge(scene, p, label, { src: a, dst: b }, 'bridge:' + a + '>' + b,
    () => showNode(box),
    { onDrill: () => go(target), actionFn: () => actionTipNode(box) });
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
// Selecting a node/edge for details is NOT a separate history entry — but the current selection is
// remembered PER VIEW: captured on the state we leave and restored when we step back/forward to it.
//   state = { kind: 'context' | 'container' | 'component' | 'subsystem' | 'edge', sid?, a?, b?, vp?, sel? }
// vp = { zoom, pan } and sel = the selectedKey, both captured when we leave a view, so stepping
// back/forward restores the view exactly as it was (a fresh drill via go() has neither — it
// fits/centers with nothing selected).
let history = [];
let hi = -1;  // index of the current state
// A diagram's last pan/zoom, keyed by its view identity (stateKey), NOT by its history slot. So the
// same diagram reached any way — back/forward, a tab, a breadcrumb crumb, or a fresh drill — reopens at
// the zoom + position it was last left at, instead of a fresh fit. (Per-entry `vp` below covers only the
// exact history slot; this covers the diagram wherever it reappears.)
const vpByView = {};

function stateKey(s) {
  return s.kind + (s.sid ? ':' + s.sid : '') + (s.a ? ':' + s.a + '>' + s.b : '')
    + (s.hp ? ':' + s.hp : '') + (s.uc ? ':' + s.uc : '') + (s.sd ? ':' + s.sd : '');
}
function captureViewState() {  // stash the current pan/zoom + selection on the entry we're about to leave
  if (hi < 0 || !history[hi]) return;
  if (mainPz) {
    const vp = { zoom: mainPz.getZoom(), pan: mainPz.getPan() };
    history[hi].vp = vp;
    vpByView[stateKey(history[hi])] = vp;  // remember this diagram's view so any later return reuses it
  }
  history[hi].sel = mainScene ? mainScene.selectedKey : null;
}
function go(state) {
  if (hi >= 0 && stateKey(history[hi]) === stateKey(state)) return;  // already here
  captureViewState();
  history = history.slice(0, hi + 1);  // a new branch drops any forward history
  history.push(state);
  hi = history.length - 1;
  render();
}
function back() { if (hi > 0) { captureViewState(); hi -= 1; render(); } }
function fwd() { if (hi < history.length - 1) { captureViewState(); hi += 1; render(); } }

// --- per-state binding ----------------------------------------------------------
function bindContext() {
  bindNodes(mainScene, (id, el, e) => {
    if (id === 'SYS') {  // the System box: ⌘-click drills in, a plain click selects (shows its overview)
      if (isDrillClick(e)) { const t = sysDrillTarget(); if (t) go(t); return; }
      selectNodeFromCanvas(el, id, e);
      return;
    }
    if (id === LIBS_ID) {  // collapsed Libraries box: ⌘-click drills to the full list, plain click previews it
      if (isDrillClick(e)) { go({ kind: 'libs' }); return; }
      selectLibsFold(mainScene, el);
      return;
    }
    selectNodeFromCanvas(el, id, e);
  });
  bindEdges(mainScene, resolveContextEdge);
  markSysDrill();
  markLibsDrill();
  // The Libraries fold selects to its own roster panel (not a plain node panel), so pre-register its
  // re-select — the generic node loop in render() then skips it, keeping back/forward faithful.
  const libsEl = mainScene.nodeEls[LIBS_ID];
  if (libsEl) mainScene.selectors['node:' + LIBS_ID] = () => selectLibsFold(mainScene, libsEl);
}
// The Libraries drill-down: the System + every folded in-process dep, same shape as Context. SYS and
// each dep simply select to their panel (no further drill); arrows resolve via the context-edge bridge.
function bindLibs() {
  bindNodes(mainScene, (id, el, e) => selectNodeFromCanvas(el, id, e));
  bindEdges(mainScene, resolveContextEdge);
}
function bindComponent() {
  bindNodes(mainScene, (id, el, e) => selectNodeFromCanvas(el, id, e));
  bindEdges(mainScene, resolveComponentEdge);
}
// A "container" altitude (Subsystems or the Domain Subdomains overview): group boxes that
// SELECT on a plain click (box + its linked neighbours) and DRILL on a ⌘-click, plus derived
// inter-group arrows. `drillFor(id)` is the drill-in state; `edgeBinder` wires each arrow. Shared so
// the component-subsystem and entity-subdomain overviews behave identically (the bridge is symmetry).
function bindGroupContainer(drillFor, edgeBinder) {
  mainScene.root.querySelectorAll('g.node').forEach((el) => {
    const id = idOf(el);
    if (!id || !GRAPH.nodes[id]) return;
    mainScene.nodeEls[id] = el;
    el.style.cursor = 'pointer';
    el.classList.add('drill');
    bindHoverGlow(mainScene, el, id);
    attachTip(el, () => actionTipNode(id));
    el.addEventListener('click', (e) => {
      if (isDrag(e)) return;
      e.stopPropagation();
      if (isDrillClick(e)) { go(drillFor(id)); return; }  // ⌘-click drills in
      selectNodeFromCanvas(el, id, e);
    });
  });
  eachEdge(mainScene.root, (p, label, m) => {
    const a = m[1], b = m[2];
    if (!(GRAPH.nodes[a] && GRAPH.nodes[b])) return;
    edgeBinder(mainScene, p, label, a, b);
  });
}
function bindContainer() { bindGroupContainer((id) => ({ kind: 'subsystem', sid: id }), bindContainerEdge); }
// The Domain Subdomains overview: a subdomain box ⌘-drills to its per-subdomain card; an
// inter-subdomain arrow selects to the crossing entity→entity relations (no further drill).
function bindDomainContainer() { bindGroupContainer((id) => ({ kind: 'domsub', sd: id }), bindDomainContainerEdge); }
// An inter-subdomain arrow (Domain overview + subdomain-card cross arrows): a plain click SELECTS it
// (the sidebar lists every entity→entity relation it bundles) and a ⌘-click drills into the
// two-subdomain edge view. The domain analog of bindContainerEdge.
function bindDomainContainerEdge(scene, p, label, a, b, focusE) {
  bindSelectEdge(scene, p, label, focusE || { src: a, dst: b }, 'dctxedge:' + a + '>' + b,
    () => showDomainContainerEdge(a, b),
    { onDrill: () => go({ kind: 'domedge', a, b }), actionFn: () => actionTipEdge(a, b) });
}
// Subdomain neighbourhood (a classDiagram): the focal subdomain's entities (framed in a namespace)
// SELECT / open-source like the flat Domain view; each collapsed neighbour-subdomain box ⌘-drills
// into its own card; each cross arrow SELECTS its crossings and ⌘-drills the two-subdomain edge view.
// The classDiagram analog of bindSubsystem (entities are g.classGroup, so it can't reuse bindNodes).
function bindDomainSub(sd) {
  fixDomainMarkers(mainScene.root);
  const seen = new Set();
  mainScene.root.querySelectorAll('g.node, g.classGroup').forEach((el) => {
    const id = idOf(el);
    if (!id || !GRAPH.nodes[id] || seen.has(id)) return;
    seen.add(id);
    mainScene.nodeEls[id] = el;  // every drawn box joins the focus set — members + collapsed neighbours
    el.style.cursor = 'pointer';
    bindHoverGlow(mainScene, el, id);
    attachTip(el, () => actionTipNode(id));
    const k = GRAPH.nodes[id].kind;
    if (k === 'subdomain' || k === 'subsystem') {  // a collapsed neighbour box: ⌘ walks into its own card
      el.classList.add('drill');
      const target = k === 'subdomain' ? { kind: 'domsub', sd: id } : { kind: 'subsystem', sid: id };
      el.addEventListener('click', (ev) => {
        if (isDrag(ev)) return; ev.stopPropagation();
        if (isDrillClick(ev)) { go(target); return; }
        selectNodeFromCanvas(el, id, ev);
      });
    } else {  // the focal subdomain's own entity: select / ⌘-open-source, like the flat Domain view
      markOpenSrc(el, id);
      el.addEventListener('click', (ev) => {
        if (isDrag(ev)) return; ev.stopPropagation();
        if (openSrcClick(id, ev)) return;
        selectNodeFromCanvas(el, id, ev);
      });
    }
  });
  eachClassEdge(mainScene.root, (p, label, x, y) => {
    const kx = GRAPH.nodes[x] && GRAPH.nodes[x].kind;
    const ky = GRAPH.nodes[y] && GRAPH.nodes[y].kind;
    if (kx === 'entity' && ky === 'entity') {  // an internal relation — select to its detail
      const arr = COMP_LOOKUP[x + '>' + y];
      if (!arr) return;
      const e = arr[0];
      bindSelectEdge(mainScene, p, label, e, 'edge:' + e.src + '>' + e.dst, () => showEdge(e));
    } else if (kx === 'subsystem' || ky === 'subsystem') {  // a bridge arrow: subsystem -> entity (owns/reads)
      const sub = kx === 'subsystem' ? x : y;
      bindBridgeEdge(mainScene, p, label, x, y, { kind: 'bridge', sid: sub, sd: sd }, sub);  // ⌘ -> the S×SD bridge card
    } else {  // a cross arrow involving a collapsed subdomain box — disjoint pairs card, overlapping ones navigate
      const subX = kx === 'subdomain', subY = ky === 'subdomain';
      if (subX && subY) {  // box <-> box (child subdomain <-> neighbour, or child <-> child)
        if (disjointBoxes(x, y) && MERMAID_DOMAIN_EDGE_CARD[x + '>' + y]) bindDomainContainerEdge(mainScene, p, label, x, y, { src: x, dst: y });
        else bindNavEdge(p, label, x, y, isAncestorOf(x, y) ? y : x);  // descend into the deeper box
      } else {  // entity (focal member) <-> subdomain box; the entity side collapses to this card's subdomain (sd)
        const box = subX ? x : y, a = subX ? x : sd, b = subY ? y : sd;
        if (disjointBoxes(box, sd) && MERMAID_DOMAIN_EDGE_CARD[a + '>' + b]) bindDomainContainerEdge(mainScene, p, label, a, b, { src: x, dst: y });
        else bindNavEdge(p, label, x, y, box);  // box is a child to descend into, or an ancestor to zoom out to
      }
    }
  });
}
// `a` is a strict ancestor of `node` in the group tree (walks parent pointers; seen-set guards a cycle).
function isAncestorOf(a, node) {
  let cur = GRAPH.nodes[node] && GRAPH.nodes[node].parent; const seen = new Set();
  while (cur && !seen.has(cur)) { if (cur === a) return true; seen.add(cur); cur = GRAPH.nodes[cur] && GRAPH.nodes[cur].parent; }
  return false;
}
// Two group boxes can frame a two-box edge card only when neither contains the other.
function disjointBoxes(x, y) { return x !== y && !isAncestorOf(x, y) && !isAncestorOf(y, x); }
// An arrow whose pair OVERLAPS (one box contains the other) can't be a two-box edge card, so it instead
// navigates to a single box: plain click shows that box's panel, ⌘-click opens its card (descend into a
// child, or zoom out to an ancestor). Also the fallback when an edge card happens not to exist.
function bindNavEdge(p, label, a, b, target) {
  const k = GRAPH.nodes[target] && GRAPH.nodes[target].kind;
  const dest = k === 'subdomain' ? { kind: 'domsub', sd: target } : { kind: 'subsystem', sid: target };
  bindSelectEdge(mainScene, p, label, { src: a, dst: b }, 'navedge:' + a + '>' + b,
    () => showNode(target), { onDrill: () => go(dest), actionFn: () => actionTipNode(target) });
}
function bindSubsystem(sid) {  // neighbourhood: component -> detail; ⌘-click on a neighbour box / cross arrow drills
  bindNodes(mainScene, (id, el, ev) => {
    // A neighbour subsystem box: plain click shows its info, ⌘-click walks into it. A bridge subdomain
    // box: ⌘-click crosses into that subdomain's card (the structural↔domain bridge). A component: select.
    if (GRAPH.nodes[id].kind === 'subsystem' && isDrillClick(ev)) { go({ kind: 'subsystem', sid: id }); return; }
    if (GRAPH.nodes[id].kind === 'subdomain' && isDrillClick(ev)) { go({ kind: 'domsub', sd: id }); return; }
    selectNodeFromCanvas(el, id, ev);
  });
  // Neighbour subsystem + bridge subdomain boxes drill on ⌘-click, so tag them `drill` for the cursor.
  mainScene.root.querySelectorAll('g.node').forEach((el) => {
    const id = idOf(el);
    const k = id && GRAPH.nodes[id] && GRAPH.nodes[id].kind;
    if (k === 'subsystem' || k === 'subdomain') el.classList.add('drill');
  });
  eachEdge(diagram, (p, label, m) => {
    const a = m[1], b = m[2];
    const ka = GRAPH.nodes[a] && GRAPH.nodes[a].kind;
    const kb = GRAPH.nodes[b] && GRAPH.nodes[b].kind;
    if (ka === 'subdomain' || kb === 'subdomain') {  // bridge arrow: a member component <-> a subdomain box
      const sd = ka === 'subdomain' ? a : b;
      bindBridgeEdge(mainScene, p, label, a, b, { kind: 'bridge', sid: sid, sd: sd }, sd);  // ⌘ -> the S×SD bridge card
      return;
    }
    const subA = ka === 'subsystem', subB = kb === 'subsystem';
    if (subA && subB) {  // box <-> box: disjoint siblings drill to the pair's edge card; nested ones navigate
      if (disjointBoxes(a, b) && MERMAID_EDGE_CARD[a + '>' + b]) bindContainerEdge(mainScene, p, label, a, b, { src: a, dst: b });
      else bindNavEdge(p, label, a, b, isAncestorOf(a, b) ? b : a);  // descend into the deeper box
      return;
    }
    if (subA || subB) {  // member <-> box. The member side collapses to THIS card's subsystem (sid).
      const box = subA ? a : b, pa = subA ? a : sid, pb = subB ? b : sid;
      if (disjointBoxes(box, sid) && MERMAID_EDGE_CARD[pa + '>' + pb]) bindContainerEdge(mainScene, p, label, pa, pb, { src: a, dst: b });
      else bindNavEdge(p, label, a, b, box);  // box is a child to descend into, or an ancestor to zoom out to
      return;
    }
    const r = resolveComponentEdge(m);  // member <-> member: the real labelled component edge
    if (r) bindSelectEdge(mainScene, p, label, r.e, r.selKey, r.showFn);
  });
}
// `a`/`b` are the two framed subsystems. Most arrows are direct member<->member links (real component
// edges, resolved below) — but one reaching into a NESTED child subsystem of `a` or `b` is drawn as an
// unlabelled, aggregated box arrow (gen_edge_card_mermaid's `agg` set), the same as a subsystem card's
// own cross arrows (see bindSubsystem's box-vs-member branching). Without this branch such an arrow
// never resolves via resolveComponentEdge (its endpoints aren't a real edge) and bindEdges silently
// drops it — never registered in scene.edgeEls, so it never dims and never responds to clicks.
function bindEdgePair(a, b) {
  bindNodes(mainScene, (id, el, e) => selectNodeFromCanvas(el, id, e));
  eachEdge(diagram, (p, label, m) => {
    const s1 = m[1], s2 = m[2];
    const k1 = GRAPH.nodes[s1] && GRAPH.nodes[s1].kind, k2 = GRAPH.nodes[s2] && GRAPH.nodes[s2].kind;
    if (k1 === 'subsystem' || k2 === 'subsystem') {  // aggregated: at least one end elevated to a child-subsystem box
      const pa = k1 === 'subsystem' ? s1 : a, pb = k2 === 'subsystem' ? s2 : b;
      if (disjointBoxes(pa, pb) && MERMAID_EDGE_CARD[pa + '>' + pb]) bindContainerEdge(mainScene, p, label, pa, pb, { src: s1, dst: s2 });
      else bindNavEdge(p, label, s1, s2, k1 === 'subsystem' ? s1 : s2);
      return;
    }
    const r = resolveComponentEdge(m);
    if (r) bindSelectEdge(mainScene, p, label, r.e, r.selKey, r.showFn);
  });
  bindFrameDrill(mainScene);  // ⌘-click either subsystem frame to open its card
}
// An edge card frames two groups (subsystem subgraphs / subdomain namespaces) as Mermaid clusters.
// Make each frame ⌘-drill into that group's card, so an edge card is no longer a dead-end. The framed
// members + arrows keep their own handlers (they live in separate elements / stop propagation), so a
// frame click only fires on the frame's own rect or title.
function bindFrameDrill(scene) {
  scene.root.querySelectorAll('g.cluster').forEach((c) => {
    const id = idOf(c);
    const k = id && GRAPH.nodes[id] && GRAPH.nodes[id].kind;
    const target = k === 'subsystem' ? { kind: 'subsystem', sid: id }
      : k === 'subdomain' ? { kind: 'domsub', sd: id } : null;
    if (!target) return;
    c.classList.add('drill');
    const run = () => go(target);
    c.addEventListener('click', (ev) => {
      if (isDrag(ev) || !isDrillClick(ev)) return;  // only ⌘-click / double-click drills the frame
      ev.stopPropagation();
      run();
    });
    addActionIcon(c, id, { kind: 'drill', run });  // this frame IS a neighbour box here (not the card you're already in), so drilling it is meaningful
  });
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
    // Match entity (E), subdomain (SD), subsystem (S), component (C) and dep (D) endpoints. SD before S
    // so a subdomain id never reads as a subsystem. Needed by the subdomain card (`id_E1_SD2`, `id_S1_E1`)
    // and the bridge card's component→entity arrows (`id_C1_E1`); the flat Domain view + edge cards are
    // all E↔E, a no-op there.
    const m = (p.id || '').match(/[_-]((?:SD|S|C|D|E)\d+)_((?:SD|S|C|D|E)\d+)(?:[_-]|$)/);
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
    bindHoverGlow(mainScene, el, id);
    attachTip(el, () => actionTipNode(id));  // ⌘-hover shows the open-source action
    if (GRAPH.nodes[id].kind === 'subsystem') {  // a bridge box (domain edge card): ⌘ drills into its card
      el.classList.add('drill');
      el.addEventListener('click', (ev) => {
        if (isDrag(ev)) return; ev.stopPropagation();
        if (isDrillClick(ev)) { go({ kind: 'subsystem', sid: id }); return; }
        selectNodeFromCanvas(el, id, ev);
      });
    } else {  // a domain entity: select / ⌘-open-source
      markOpenSrc(el, id);
      el.addEventListener('click', (ev) => { if (isDrag(ev)) return; ev.stopPropagation(); if (openSrcClick(id, ev)) return; selectNodeFromCanvas(el, id, ev); });
    }
  });
  eachClassEdge(mainScene.root, (p, label, src, dst) => {
    const ks = GRAPH.nodes[src] && GRAPH.nodes[src].kind, kd = GRAPH.nodes[dst] && GRAPH.nodes[dst].kind;
    if (ks === 'subsystem' || kd === 'subsystem') {  // a bridge arrow subsystem -> entity (owns/reads)
      const sub = ks === 'subsystem' ? src : dst, ent = ks === 'subsystem' ? dst : src;
      bindBridgeEdge(mainScene, p, label, src, dst, { kind: 'bridge', sid: sub, sd: topSubdomainOf(ent) }, sub);  // ⌘ -> bridge card
      return;
    }
    const arr = COMP_LOOKUP[src + '>' + dst];
    if (!arr) return;
    const e = arr[0];
    bindSelectEdge(mainScene, p, label, e, 'edge:' + e.src + '>' + e.dst, () => showEdge(e));
  });
}

// --- Happy Path (Level 1) selection ---------------------------------------------
// A sequenceDiagram, a different SVG shape again: a step is a message (text + line), an actor is a
// stick figure over a lifeline. Both SELECT (panel + glow + focus-dim); a step also ⌘-clicks to drill.
// Glow one HP element (figure, text, lifeline or arrow) with the soft HP_SEL drop-shadow — a touch
// above the hover glow, never the heavy stroke-recolour the click used to apply. Returns a cleanup.
function hpGlow(el) {
  el.style.filter = HP_SEL;
  if (el._actionIcon) showIcon(el._actionIcon);  // a selected step's pill stays put, not just its glow
  return () => { el.style.filter = ''; if (el._actionIcon) hideIcon(el._actionIcon); };
}
// Glow a set of elements and remember them in scene.hpLit (a step driven by a selected actor is
// glowed but isn't itself the selection, so its own hover handlers must restore THIS glow on leave —
// not blank it). Returns a cleanup that both undoes the glow and forgets the set.
function hpHighlight(scene, els) {
  scene.hpLit = new Set(els);
  const undo = els.map(hpGlow);
  return () => { undo.forEach((f) => f()); scene.hpLit = new Set(); };
}
// The filter an element should rest at given the current selection: the HP_SEL glow if the selection
// lit it, else none. Hover-off restores to this instead of blanking, so a selection glow survives a
// passing hover.
function hpRestFilter(scene, el) {
  return scene.hpLit.has(el) ? HP_SEL : '';
}
function hpFocus(scene, keep) {  // dim every focusable HP element not in the keep set (system stays lit)
  for (const el of scene.dimEls) el.style.opacity = keep.has(el) ? '' : DIM;
}
// Select an actor: its figure + lifeline + every step it drives glow; the rest dims.
function selectHPActor(scene, a) {
  const selKey = 'hpactor:' + a.aid;
  scene.selectedKey = selKey;
  showHPActor(a);
  const stepEls = [];
  for (const i of a.stepIdx) { const m = scene.hpMsg[i]; if (m) { if (m.text) stepEls.push(m.text); if (m.line) stepEls.push(m.line); } }
  const lit = [...scene.hpActor[a.aid].els, ...stepEls];
  sceneSelect(scene, () => hpHighlight(scene, lit));
  hpFocus(scene, new Set(lit));
}
// Select a step: the step (text + line) glows and its driving actor stays lit; the rest dims.
function selectHPStep(scene, i, hpId, aid) {
  const selKey = 'hpstep:' + hpId;
  scene.selectedKey = selKey;
  showHPArrow(hpId);  // plain select = just the X → Y interaction; the full flow is behind the drill
  const m = scene.hpMsg[i] || {};
  const glow = [m.text, m.line].filter(Boolean);
  const rec = aid ? scene.hpActor[aid] : null;
  sceneSelect(scene, () => hpHighlight(scene, glow));
  hpFocus(scene, new Set([...glow, ...(rec ? rec.els : [])]));
}
// Select a whole use case on the Happy Path (reached from a Use-cases `HPn` pill): EVERY step that
// realizes it glows and its driving actor stays lit; the rest dims. A use case can occupy several
// positions, so more than one step may light — that is exactly the "appears twice" signal. The panel
// shows the use case (not a single step), and the selection is keyed by uc so back/forward restores it.
function selectHPUseCase(scene, uc) {
  const selKey = 'hpuc:' + uc;
  scene.selectedKey = selKey;
  showUseCase(uc);
  const glow = [], keep = [];
  (GRAPH.happy_path || []).forEach((step, i) => {
    if (step.uc !== uc) return;
    const m = scene.hpMsg[i]; if (!m) return;
    if (m.text) glow.push(m.text);
    if (m.line) glow.push(m.line);
    const rec = HP_ACTOR_OF_STEP[step.id] ? scene.hpActor[HP_ACTOR_OF_STEP[step.id].aid] : null;
    if (rec) keep.push(...rec.els);
  });
  sceneSelect(scene, () => hpHighlight(scene, glow));
  hpFocus(scene, new Set([...glow, ...keep]));
}

// Bind the Happy Path: steps + actors both select; a step ⌘-clicks to its Level-2 components view.
// The step id is no longer in the label, so message[i] pairs with GRAPH.happy_path[i] by order; an actor's
// figure/lifeline are found by participant id (data-id="GPAn") and its driven steps come from HP_ACTORS.
function bindHP() {
  const scene = mainScene, root = scene.root;
  // message text[i] <-> GRAPH.happy_path[i]; its arrow is the .messageLine with data-id "i<idx>".
  const texts = [...root.querySelectorAll('text.messageText')];
  const lineByIdx = {};
  root.querySelectorAll('.messageLine0, .messageLine1').forEach((ln) => {
    const m = (ln.getAttribute('data-id') || '').match(/^i(\d+)$/);
    if (m) lineByIdx[+m[1]] = ln;
  });
  leftAlignMessageLabels(texts, lineByIdx);
  scene.hpMsg = {};  // step index -> { text, line }
  for (let i = 0; i < (GRAPH.happy_path || []).length; i++) {
    const text = texts[i] || null;
    const line = lineByIdx[i] || null;
    if (text) scene.dimEls.push(text);
    if (line) scene.dimEls.push(line);
    scene.hpMsg[i] = { text, line };
  }
  // resolve each actor's DOM (figure top + bottom mirror + lifeline) by participant id, register for dimming.
  scene.hpActor = {};  // aid -> { els:[…] }
  const bottoms = [...root.querySelectorAll('g.actor-man.actor-bottom')];
  for (const a of HP_ACTORS) {
    const figT = root.querySelector('.actor-top[data-id="' + a.aid + '"]');
    const life = root.querySelector('line.actor-line[data-id="' + a.aid + '"]');
    const figB = bottoms.find((g) => (g.textContent || '').trim() === a.name) || null;  // no data-id on the mirror
    const els = [figT, figB, life].filter(Boolean);
    scene.hpActor[a.aid] = { els };
    for (const el of els) scene.dimEls.push(el);
  }
  const aidOfStep = {};  // step index -> driving actor id (keeps the actor lit when a step is selected)
  for (const a of HP_ACTORS) for (const i of a.stepIdx) aidOfStep[i] = a.aid;
  // Per-use-case selector: arriving from a Use-cases `HPn` pill (state `sel: 'hpuc:<uc>'`) lights every
  // step of that use case. Registered for each use case that occupies ≥1 position; back/forward too.
  for (const uc of Object.keys(HP_STEPS_BY_UC)) scene.selectors['hpuc:' + uc] = () => selectHPUseCase(scene, uc);

  // steps: plain click selects (panel), ⌘-click drills to Level 2.
  (GRAPH.happy_path || []).forEach((step, i) => {
    const { text, line } = scene.hpMsg[i];
    if (!text) return;
    const hpId = step.id, selKey = 'hpstep:' + hpId;
    scene.selectors[selKey] = () => selectHPStep(scene, i, hpId, aidOfStep[i]);  // back/forward restore
    addLabelActionIcon(text, selKey, { kind: 'drill', run: () => go({ kind: 'hpstep', hp: hpId }) });
    const icon = ACTION_ICONS[selKey];
    // A dimmed step (hpFocus set its opacity to DIM because focus is on some other step/actor) isn't a
    // candidate for a next action — the pill stays hidden even while hovered, matching a dimmed box.
    const on = () => { if (scene.selectedKey !== selKey) { text.style.filter = HOVER; if (line) line.style.filter = HOVER; if (text.style.opacity !== DIM) showIcon(icon); } };
    // restore to the resting glow (an actor-selected step keeps its HILITE), not blank — and for the
    // same reason, the pill sticks too: `scene.hpLit` is exactly what hpRestFilter already checks to
    // decide that, so hiding the icon only when this step ISN'T in that lit set keeps it up for as
    // long as its driving actor is selected, not just for as long as the step itself is.
    const off = () => { if (scene.selectedKey !== selKey) { text.style.filter = hpRestFilter(scene, text); if (line) line.style.filter = hpRestFilter(scene, line); if (!scene.hpLit.has(text)) hideIcon(icon); } };
    const click = (ev) => {
      if (isDrag(ev)) return;
      ev.stopPropagation();
      off();
      if (isDrillClick(ev)) { go({ kind: 'hpstep', hp: hpId }); return; }  // ⌘-click drills in
      selectHPStep(scene, i, hpId, aidOfStep[i]);
    };
    for (const el of [text, line]) {
      if (!el) continue;
      el.style.cursor = 'pointer';
      el.style.setProperty('pointer-events', el === text ? 'all' : 'stroke', 'important');
      el.classList.add('drill');  // ⌘-held cursor affordance
      el.addEventListener('click', click);
      el.addEventListener('mouseenter', on);
      el.addEventListener('mouseleave', off);
      attachTip(el, () => actionTipHP(hpId));
    }
    // The pill and its bridge (see addLabelActionIcon) get the same on/off as the text/line, so the
    // whole step — label, arrow, gap, pill — behaves as one continuous hover zone with an instant,
    // lag-free show/hide (no gap ever left uncovered means no grace timer is needed to paper over one).
    icon.addEventListener('mouseenter', on);
    icon.addEventListener('mouseleave', off);
    if (icon._bridge) { icon._bridge.addEventListener('mouseenter', on); icon._bridge.addEventListener('mouseleave', off); }
  });

  // actors: click the figure or anywhere on the lifeline to select the actor (no drill).
  for (const a of HP_ACTORS) {
    const rec = scene.hpActor[a.aid], selKey = 'hpactor:' + a.aid;
    scene.selectors[selKey] = () => selectHPActor(scene, a);  // back/forward restore
    const on = () => { if (scene.selectedKey !== selKey) for (const el of rec.els) el.style.filter = HOVER; };
    const off = () => { if (scene.selectedKey !== selKey) for (const el of rec.els) el.style.filter = hpRestFilter(scene, el); };
    const click = (ev) => { if (isDrag(ev)) return; ev.stopPropagation(); off(); selectHPActor(scene, a); };
    for (const el of rec.els) {
      if (el.tagName === 'line') continue;  // the lifeline gets a fat transparent hit (below)
      el.style.cursor = 'pointer';
      el.addEventListener('click', click);
      el.addEventListener('mouseenter', on);
      el.addEventListener('mouseleave', off);
    }
    const life = rec.els.find((el) => el.tagName === 'line');
    if (life) attachEdgeHandlers(life, null, click, on, off, null);
  }
}

// --- render ---------------------------------------------------------------------
function mermaidFor(s) {
  if (s.kind === 'context') return MERMAID_CONTEXT;
  if (s.kind === 'container') return MERMAID_CONTAINER;
  if (s.kind === 'subsystem') return MERMAID_BY_SUB[s.sid];
  if (s.kind === 'edge') return MERMAID_EDGE_CARD[s.a + '>' + s.b];
  // Domain: the Subdomains overview when grouped (drill a subdomain for its classes), else the
  // flat whole-model classDiagram.
  if (s.kind === 'domain') return HAS_SUBDOMAINS ? MERMAID_DOMAIN_CONTAINER : MERMAID_DOMAIN;
  if (s.kind === 'domsub') return MERMAID_DOMAIN_SUB[s.sd];
  if (s.kind === 'domedge') return MERMAID_DOMAIN_EDGE_CARD[s.a + '>' + s.b];
  if (s.kind === 'bridge') return MERMAID_BRIDGE_CARD[s.sid + '>' + s.sd];
  if (s.kind === 'hp') return MERMAID_HP;
  if (s.kind === 'hpstep') return FLOWS_MM[(HP_BY_ID[s.hp] || {}).uc] || EMPTY_FLOW_MM;  // the step's use case's flow
  if (s.kind === 'usecase') return FLOWS_MM[s.uc] || EMPTY_FLOW_MM;
  if (s.kind === 'libs') return MERMAID_LIBS;
  return mode === 'diff' ? MERMAID_DIFF : MERMAID_BASE;  // component
}
function applyDefaultPanel(s) {
  if (s.kind === 'subsystem') showNode(s.sid);
  else if (s.kind === 'domsub') showNode(s.sd);
  else if (s.kind === 'edge') showTwoSubsystems(s.a, s.b);
  else if (s.kind === 'domedge') showTwoSubdomains(s.a, s.b);
  else if (s.kind === 'bridge') showBridge(s.sid, s.sd);
  else if (s.kind === 'hpstep') showHPStep(s.hp);
  else if (s.kind === 'usecase') showUseCase(s.uc);
  else if (s.kind === 'libs') showLibsFold();
  // The Happy Path overview (nothing selected) opens on the project goal — the SYS node carries the
  // title + T0 goal (fields.Overview). Selecting a step/actor then replaces it with that detail.
  else if (s.kind === 'hp' && GRAPH.nodes['SYS']) showNode('SYS');
  // The Subsystems overview in diff mode leads with the change-impact summary (which subsystems/elements
  // changed), since that is the whole point of opening a diff render.
  else if (s.kind === 'container' && mode === 'diff' && HAS_DIFF) showDiffSummary();
  // Every overview without a more specific default (Context, Subsystems, Domain) opens on the System's
  // overview — its overall functionality — instead of a blank panel.
  else if (GRAPH.nodes['SYS']) showNode('SYS');
  else panel.innerHTML = EMPTY_PANEL;
}
function bindFor(s) {
  if (s.kind === 'context') bindContext();
  else if (s.kind === 'container') bindContainer();
  else if (s.kind === 'subsystem') bindSubsystem(s.sid);
  else if (s.kind === 'edge') bindEdgePair(s.a, s.b);
  else if (s.kind === 'domain') (HAS_SUBDOMAINS ? bindDomainContainer : bindDomain)();
  else if (s.kind === 'domsub') bindDomainSub(s.sd);  // neighbourhood: framed entities + collapsed neighbour boxes + cross arrows
  else if (s.kind === 'domedge') { bindDomain(); bindFrameDrill(mainScene); }  // both subdomains framed; ⌘-click a frame -> its card
  else if (s.kind === 'bridge') { bindDomain(); bindFrameDrill(mainScene); }  // subsystem×subdomain; components+entities+C→E edges, frames drill
  else if (s.kind === 'hp') bindHP();
  else if (s.kind === 'hpstep') bindFlow((HP_BY_ID[s.hp] || {}).uc);  // the step opens its use case's flow
  else if (s.kind === 'usecase') bindFlow(s.uc);
  else if (s.kind === 'libs') bindLibs();
  else bindComponent();
}
function topView(kind) {  // which top-level button a state lives under (container/subsystem/edge → Subsystems)
  if (kind === 'context' || kind === 'component' || kind === 'domain' || kind === 'glossary') return kind;
  if (kind === 'domsub' || kind === 'domedge') return 'domain';  // subdomain card + edge pair live under the Domain button
  if (kind === 'bridge') return 'container';  // a structure↔domain bridge card is anchored on its subsystem
  if (kind === 'usecases' || kind === 'usecase') return 'usecases';  // a use case's flow lives under the Use Cases catalog
  if (kind === 'hp' || kind === 'hpstep') return 'hp';
  if (kind === 'libs') return 'context';  // the Libraries fold drills out of Context
  return 'container';
}
function hpTitle(hp) { const s = HP_BY_ID[hp]; return s ? (s.title || s.id) : hp; }  // breadcrumb crumb: title, not the HPn id
function stateTitle(s) {
  if (s.kind === 'context') return 'Dependencies';
  if (s.kind === 'container') return 'Subsystems';
  if (s.kind === 'component') return 'Components';
  if (s.kind === 'domain') return 'Entities';  // user-facing label for the `domain` view (the tab)
  if (s.kind === 'glossary') return 'Glossary';
  if (s.kind === 'usecases') return 'Use Cases';
  if (s.kind === 'domsub') return (GRAPH.nodes[s.sd] ? GRAPH.nodes[s.sd].name : s.sd);
  if (s.kind === 'domedge') { const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id); return nm(s.a) + ' → ' + nm(s.b); }
  if (s.kind === 'bridge') { const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id); return nm(s.sid) + ' → ' + nm(s.sd); }
  if (s.kind === 'hp') return 'Happy Path';
  if (s.kind === 'hpstep') return hpTitle(s.hp);
  if (s.kind === 'usecase') return (GRAPH.nodes[s.uc] ? GRAPH.nodes[s.uc].name : s.uc);
  if (s.kind === 'libs') return 'Libraries';
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  if (s.kind === 'subsystem') return nm(s.sid);
  return nm(s.a) + ' → ' + nm(s.b);  // edge
}
// The nesting path (top ancestor → id) as breadcrumb states, walking `parent` pointers — so a deep
// drill (Subsystems › Plugins › Social Content) shows EVERY level, each crumb clickable. A seen-set
// guards against a malformed parent cycle.
function groupChain(kind, key, id) {
  const chain = []; const seen = new Set(); let cur = id;
  while (cur && !seen.has(cur)) { seen.add(cur); chain.unshift({ kind, [key]: cur }); const n = GRAPH.nodes[cur]; cur = n && n.parent; }
  return chain;
}
function ancestors(s) {  // structural nesting path (top → s), independent of the click history
  // Each tab's OVERVIEW shows a single crumb (its own name); only a drill-down appends deeper crumbs.
  // So sibling tabs read uniformly — Subsystems, Components, Domain, Happy Path, Context are each one
  // crumb at the top, and ancestry (Subsystems › Auth › … , Context › Libraries) appears only once you
  // zoom in; a nested subsystem/subdomain appends one crumb PER level via groupChain.
  if (s.kind === 'domain') return [{ kind: 'domain' }];
  if (s.kind === 'domsub') return [{ kind: 'domain' }, ...groupChain('domsub', 'sd', s.sd)];  // subdomain card (full nesting path) under Domain
  if (s.kind === 'domedge') return [{ kind: 'domain' }, { kind: 'domedge', a: s.a, b: s.b }];  // subdomain pair beside them
  if (s.kind === 'bridge') return [{ kind: 'container' }, { kind: 'bridge', sid: s.sid, sd: s.sd }];  // S×SD bridge under Subsystems
  if (s.kind === 'hp') return [{ kind: 'hp' }];
  if (s.kind === 'hpstep') return [{ kind: 'hp' }, { kind: 'hpstep', hp: s.hp }];  // step under the Happy Path
  if (s.kind === 'usecases') return [{ kind: 'usecases' }];
  if (s.kind === 'usecase') return [{ kind: 'usecases' }, { kind: 'usecase', uc: s.uc }];  // a use case's flow, under the Use Cases catalog
  if (s.kind === 'libs') return [{ kind: 'context' }, { kind: 'libs' }];  // the fold is a drill-down out of Context
  if (s.kind === 'context') return [{ kind: 'context' }];
  if (s.kind === 'component') return [{ kind: 'component' }];
  if (s.kind === 'glossary') return [{ kind: 'glossary' }];
  const trail = [{ kind: 'container' }];                  // the Subsystems overview is the root of this branch
  if (s.kind === 'subsystem') trail.push(...groupChain('subsystem', 'sid', s.sid));  // full nesting path top → sid
  else if (s.kind === 'edge') trail.push({ kind: 'edge', a: s.a, b: s.b });  // a pair lives beside the subsystems
  return trail;
}
function renderChrome(s) {
  // The baseline⇄diff change-impact overlay lives on the Subsystems views now (overview + cards),
  // not the removed flat Components map: the overview badges each subsystem with its subtree's change,
  // and the cards badge their member components (via bindNodes).
  const diffHost = s.kind === 'container' || s.kind === 'subsystem' || s.kind === 'edge';
  legend.classList.toggle('on', diffHost && mode === 'diff');
  toggle.style.display = (HAS_DIFF && diffHost) ? '' : 'none';
  toggle.textContent = mode === 'diff' ? 'Show baseline' : 'Show diff';
  const tv = topView(s.kind);
  viewsw.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b.dataset.view === tv));
  navback.disabled = hi <= 0;
  navfwd.disabled = hi >= history.length - 1;
  // breadcrumb: the structural nesting down to the current view; each ancestor crumb zooms out to it.
  // Only show the bar once it actually branches (a `›` between crumbs) — a lone crumb (a tab's own
  // overview) is just the tab name repeated, so hide the whole bar there.
  crumb.innerHTML = '';
  const chain = ancestors(s);
  if (crumb.parentElement) crumb.parentElement.hidden = chain.length < 2;
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

// Icons are drawn in DIAGRAM units, so without this they'd shrink right along with the boxes as the
// view zooms out — at a crowded overview (many boxes fitted on screen) that makes them a near-invisible,
// near-unclickable speck. Counter-scaled against the current pan-zoom level (like a map pin that stays
// the same size no matter how far out you zoom the map) so they read as a constant on-screen size at
// any zoom. `_anchor` (set in addActionIcon) is the translate; only the extra `scale` term changes here.
// getSizes().realZoom, NOT getZoom() — getZoom() is ALWAYS 1 right after a fresh fit, no matter the
// diagram's size or node count: it's relative to THAT diagram's own fit, not an absolute scale. A
// confirmed real bug: on a small test diagram this went unnoticed (a few dozen nodes still fit at a
// large-enough per-node scale), but a large real diagram (hundreds of nodes) has to shrink FAR more
// just to fit on screen at its own "100%" — 1/getZoom() never saw that shrink, so the icon rendered
// at just a few CSS pixels there even though it looked fine on the small diagram. realZoom is the
// library's own true diagram-units-to-CSS-pixel ratio (confirmed: doubles when you call zoomBy(2),
// unlike getZoom() which resets to 1 on every fresh fit) — 1/realZoom makes 1 local SVG unit render
// as exactly 1 CSS pixel always, regardless of diagram size or current zoom. Shared by rescaleActionIcons
// (every icon, on a zoom change) and bindEdgeActionIcon (one icon, the moment it's repositioned to the
// cursor) — both need the SAME factor so a freshly-moved icon doesn't render at the wrong size for the
// instant before the next zoom event happens to re-run the loop.
function curIconInv() { return mainPz ? 1 / mainPz.getSizes().realZoom : 1; }
function rescaleActionIcons() {
  const inv = curIconInv();
  for (const id in ACTION_ICONS) {
    const icon = ACTION_ICONS[id];
    let a = icon._anchor;
    // A label-anchored pill's gap to its label is a constant SCREEN distance (see addLabelActionIcon),
    // so its anchor is re-derived here from the zoom-invariant `_labelRef` point every time inv changes
    // — a one-off anchor (like a box's own corner, which needs no such correction) would let the gap
    // drift with zoom instead of staying put. The bridge is re-synced right after so it never lags.
    if (icon._labelRef) { a = { x: icon._labelRef.x - icon._labelGap * inv, y: icon._labelRef.y }; icon._anchor = a; placeLabelBridge(icon); }
    if (a) icon.setAttribute('transform', `translate(${a.x},${a.y}) scale(${inv})`);
  }
}
function updateZoomLevel() {  // reflect the current pan-zoom scale in the header control + the icons
  if (zoomlevel) zoomlevel.textContent = mainPz ? Math.round(mainPz.getZoom() * 100) + '%' : '100%';
  rescaleActionIcons();
}

// Keep the diagram fitted to the stage as the side bars (or the window) resize it. svg-pan-zoom caches
// the container size at init, so without this the content would clip/misalign when #stage's size
// changes. Both variants are coalesced to one call per animation frame (via the shared refitRaf) so a
// drag's mousemove stream stays smooth.
let refitRaf = 0;
function scheduleStage(fn) {
  if (refitRaf) return;
  refitRaf = requestAnimationFrame(() => { refitRaf = 0; if (mainPz) { fn(); updateZoomLevel(); } });
}
// Re-FIT: the SAME content is re-framed in the new size (zoom resets to fit, recentered). Used when the
// stage's WIDTH changes (side bars / window) — the diagram should reflow to the new width.
function refitStage() { scheduleStage(() => { mainPz.resize(); mainPz.fit(); mainPz.center(); }); }
// PRESERVE: keep the user's current zoom level and keep the point that was at the viewport centre at the
// centre — the diagram doesn't jump. Used for the vertical split (info-pane height), where re-fitting
// would throw away a zoom-in every time the reader nudges the divider.
function resizeStagePreserve() {
  scheduleStage(() => {
    const b = mainPz.getSizes();                          // container size + realZoom BEFORE the resize
    const pan = mainPz.getPan();
    const cx = (b.width / 2 - pan.x) / b.realZoom;        // SVG-space point currently under the viewport centre
    const cy = (b.height / 2 - pan.y) / b.realZoom;
    const z = mainPz.getZoom();
    mainPz.resize();
    mainPz.zoom(z);                                       // resize() can snap zoom back to fit — restore it
    const a = mainPz.getSizes();                          // realZoom AFTER (base fit may have shifted)
    mainPz.pan({ x: a.width / 2 - a.realZoom * cx, y: a.height / 2 - a.realZoom * cy });  // re-centre on the same point
  });
}

// The Glossary tab: the ubiquitous-language terms as a scrollable table (term · meaning · a link to
// the term's code home). Not a diagram — written straight into #diagram. Each `where` is a bare
// `path:line`/`path/` anchor; a local one becomes a source-open button (editor/GitHub, exactly like a
// node's ⌘-click), an off-repo/absent one stays plain text.
function renderGlossary() {
  const rows = (GRAPH.glossary || []).map((g) => {
    const where = g.source || '';
    const { file, line } = where ? whereNode(where) : { file: '', line: null };
    let cell = '<span class="gloss-none">—</span>';
    if (where && localRef(where)) {
      const rel = cleanPath(file, line);
      const base = rel.replace(/\/+$/, '').split('/').pop() + (line ? ':' + line : '');
      cell = `<button type="button" class="src srclink gloss-src" data-where="${esc(where)}"`
        + ` title="Open in the code viewer">${esc(base)}</button>`;
    } else if (where) {
      cell = `<span class="gloss-plain">${esc(cleanPath(file, line))}</span>`;
    }
    return `<tr><th scope="row">${esc(g.term)}</th><td>${mdInline(g.meaning || '')}</td><td>${cell}</td></tr>`;
  }).join('');
  diagram.innerHTML = '<div class="glossary-wrap" style="padding-top:20px">'
    + '<table class="glossary"><thead><tr><th>Term</th><th>Meaning</th><th>Defined in</th></tr></thead>'
    + `<tbody>${rows}</tbody></table></div>`;
  diagram.querySelectorAll('.gloss-src').forEach((btn) => {
    const wn = whereNode(btn.getAttribute('data-where'));
    btn.addEventListener('click', () => openInCodeViewer(wn.file, wn.line));
  });
}

// The Use Cases tab: the full catalog, GROUPED BY ACTOR — each actor section header IS the Role (the
// only place roles get a home now that the Context/Dependencies view is deps-focused). Each use case
// shows its trigger → outcome and, when it sits on the Happy Path, an `HPn` pill (all positions when it
// recurs) that jumps to that step. Off-spine use cases have NO pill — that absence is the on/off-spine
// signal in the catalog. A non-diagram HTML view rendered straight into #diagram, like the Glossary.
function renderUseCases() {
  // Group by the single primary actor, keeping model (importance) order within a group and
  // first-appearance order of the actors. A use case whose Actor names no known role (or is blank)
  // falls into an "Other" bucket rather than an invented header — the single-actor invariant made safe.
  const groups = [];               // [{actor, role, ucs:[node]}]
  const byActor = {};
  const OTHER = ' other';
  for (const n of UC_NODES) {
    const actor = ((n.fields && n.fields.Actor) || '').trim();
    const role = ROLE_BY_NAME[actor.toLowerCase()];
    const key = (role && actor) ? actor.toLowerCase() : OTHER;
    if (!byActor[key]) { byActor[key] = { actor: role ? actor : 'Other', role: role || null, ucs: [] }; groups.push(byActor[key]); }
    byActor[key].ucs.push(n);
  }
  const kindBadge = (kind) => {
    const k = (kind || '').trim().toLowerCase();
    if (k !== 'human' && k !== 'service') return '';
    return `<span class="uc-kind uc-kind-${k}">${esc(k)}</span>`;
  };
  const pill = (uc) => {
    const ids = HP_STEPS_BY_UC[uc] || [];
    if (!ids.length) return '';
    const label = ids.join(' · ');
    return `<button type="button" class="uc-hp-pill" data-uc="${esc(uc)}"`
      + ` title="On the Happy Path — jump to ${esc(label)}">${esc(label)}</button>`;
  };
  const sections = groups.map((g) => {
    const wants = g.role && g.role.wants ? `<span class="uc-actor-wants">${mdInline(g.role.wants)}</span>` : '';
    const rows = g.ucs.map((n) => {
      const to = (n.fields && n.fields['Trigger → Outcome']) || '';
      return `<li class="uc-row" data-uc="${esc(n.id)}" tabindex="0">`
        + `<span class="uc-head"><span class="uc-name">${esc(n.name)}</span>${pill(n.id)}</span>`
        + (to ? `<span class="uc-to">${mdInline(to)}</span>` : '')
        + '</li>';
    }).join('');
    return '<section class="uc-group">'
      + `<h3 class="uc-actor">${esc(g.actor)}${kindBadge(g.role && g.role.kind)}${wants}</h3>`
      + `<ul class="uc-list">${rows}</ul></section>`;
  }).join('');
  diagram.innerHTML = `<div class="usecases-wrap">${sections || '<p class="empty">No use cases recorded.</p>'}</div>`;
  // A row opens the use case's flow — the SAME detail a Happy Path step drills into (one home).
  const openUc = (li) => go({ kind: 'usecase', uc: li.getAttribute('data-uc') });
  diagram.querySelectorAll('.uc-row').forEach((li) => {
    li.addEventListener('click', (ev) => { if (!ev.target.closest('.uc-hp-pill')) openUc(li); });
    li.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' && !ev.target.closest('.uc-hp-pill')) openUc(li); });
  });
  // A pill jumps to the Happy Path tab with every step of this use case lit (see selectHPUseCase).
  diagram.querySelectorAll('.uc-hp-pill').forEach((btn) => {
    btn.addEventListener('click', (ev) => { ev.stopPropagation(); go({ kind: 'hp', sel: 'hpuc:' + btn.getAttribute('data-uc') }); });
  });
}

async function render() {
  const seq = ++renderSeq;
  hideTip();  // a re-render replaces the diagram — drop any tooltip from the old one
  if (mainPz) { mainPz.destroy(); mainPz = null; }
  flowPlay = null; flowplayer.hidden = true;  // hide the step player until bindFlow re-arms it for a flow view
  const s = history[hi];
  // The Glossary tab is a term TABLE, not a mermaid diagram — render it straight into the stage and
  // keep the chrome (breadcrumb + active tab). No panZoom/scene/tree machinery to set up, so return
  // before the diagram path, the same shape as the degraded "could not render" branch below.
  if (s.kind === 'glossary') { renderGlossary(); mainScene = null; renderChrome(s); return; }
  // The Use Cases tab is an actor-grouped HTML catalog, not a mermaid diagram — same shape as Glossary.
  if (s.kind === 'usecases') { renderUseCases(); mainScene = null; renderChrome(s); return; }
  // Safety net: a missing baked diagram (an unforeseen drill key) or a mermaid parse error must DEGRADE,
  // not throw an unhandled rejection that freezes the view mid-navigation. Show a message + keep the
  // chrome (back/forward still work) so the user can step out.
  let svg;
  try {
    const src = mermaidFor(s);
    if (!src) throw new Error('no diagram for ' + JSON.stringify(s));
    ({ svg } = await mermaid.render('coyodexGraph' + (rc++), src));
  } catch (_) {
    if (seq !== renderSeq) return;
    diagram.innerHTML = '<p class="empty">This view could not be rendered.</p>';
    renderChrome(s);
    return;
  }
  if (seq !== renderSeq) return;  // a newer render started during the async layout — drop this stale one
  diagram.innerHTML = svg;
  tintClusters(diagram);  // recolour expanded group frames (subsystem/subdomain clusters) to their family
  emphasizeZoomedFrame(diagram, s);  // thicker border + bigger title on the group you drilled into
  mainScene = makeScene(diagram, () => applyDefaultPanel(s));
  for (const id in ACTION_ICONS) delete ACTION_ICONS[id];  // reset before bindFor's bindFrameDrill re-populates it
  bindFor(s);
  decorateActionIcons(mainScene);  // corner icon = each drawn box's one useful secondary action
  // Every drawn box gets a default re-select closure (plain-click select), so back/forward can restore
  // a node selection. Edges, flow steps and HP actors/steps register their own during bindFor; a box
  // with special select behaviour (the Libraries fold) pre-registers too, so it's skipped here.
  for (const id in mainScene.nodeEls) {
    if (!mainScene.selectors['node:' + id]) {
      const el = mainScene.nodeEls[id];
      mainScene.selectors['node:' + id] = () => selectNode(mainScene, el, id);
    }
  }
  // Skip the plain landing panel when a more specific selection below is about to override it anyway —
  // it would just be thrown away, and (since showNode/syncTreeToNode mirror into the file browser) it'd
  // also plant a spurious intermediate tree-highlight that throws off the near/far centering heuristic
  // in highlightTreePath (the REAL previous selection stops being `prevRow` for the one that matters).
  // Landing on a view with nothing selected (a tab / drill, not a folder element click): show its
  // default panel and close any folder peek carried over from the previous view. An explicit selection
  // (pendingSelect below) instead runs through updateFolderPeek, which re-peeks if it's a folder.
  if (!pendingSelect && !pendingElementsList && !(s.sel && mainScene.selectors[s.sel])) { applyDefaultPanel(s); setTreePeek(false); }
  if (mode === 'diff' && HAS_DIFF) applyDiffOverlay(s);  // diff badges that aren't drawn by the binders
  // A file-browser click navigated here to reveal a node: select it now the view has rendered. The
  // box is drawn (we picked the view so it would be) — fall back to its panel + tree row if not.
  // pendingMatchTextId: a node reached this way ALWAYS gets the zoom-to-match-sidebar-text-size move
  // (see matchTextSize) — but mainPz doesn't exist yet at this point (it's still the PREVIOUS view's
  // instance, or null, on a fresh navigation), so it's applied below, once svgPanZoom has been
  // (re)constructed for the new view.
  let pendingMatchTextId = null;
  if (pendingSelect) {
    const id = pendingSelect; pendingSelect = null;
    const el = mainScene.nodeEls[id];
    if (el) selectNode(mainScene, el, id); else showNodeDetailSynced(id);
    if (el) pendingMatchTextId = id;
  } else if (pendingElementsList) {
    // A file/folder anchoring several elements shares this view — land here with nothing selected
    // (see selectFromTreeAnchors) and list them all instead of guessing which one was meant.
    const ids = pendingElementsList; pendingElementsList = null;
    showElementsList(ids);
  } else if (s.sel && mainScene.selectors[s.sel]) {
    mainScene.selectors[s.sel]();  // history revisit: restore the element that was selected in this view
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
    // Restore the pan/zoom this diagram was last left at (zoom first, then absolute pan). `s.vp` is the
    // exact history slot (back/forward); `vpByView` catches the same diagram reached any other way — a
    // tab, a breadcrumb crumb, or a re-drill — so it reopens where it was instead of a fresh fit.
    // SKIP the restore when a matchTextSize move follows (a file-tree selection): it overrides the camera
    // anyway, and — crucially — svg-pan-zoom paints zoom()/pan() only on the NEXT frame (see matchTextSize),
    // so a synchronous matchTextSize would measure the still-showing fit transform while the internal state
    // already held the restored vp. Those two disagreeing is what threw the selected box off-screen; leaving
    // the fresh fit in place (its transform IS applied synchronously) keeps measurement and state in step.
    const vp = pendingMatchTextId ? null : (s.vp || vpByView[stateKey(s)]);
    if (vp) { mainPz.zoom(vp.zoom); mainPz.pan(vp.pan); }
    updateZoomLevel();
    if (pendingMatchTextId) matchTextSize(mainScene.nodeEls[pendingMatchTextId]);
    flowInit();  // a flow view: show the step player (unstarted on a fresh open; nothing auto-selected)
  }
  if (svgEl) svgEl.addEventListener('click', (e) => { if (!isDrag(e)) resetScene(mainScene); });  // empty space deselects
  renderChrome(s);
}

// --- file browser (left pane) ---------------------------------------------------
// A foldable repo tree (VSCode/JetBrains-style) shaded by map coverage, two-way bound to the diagram:
//   • graph -> tree: selecting a node highlights its file/folder row (syncTreeToNode, called by selectNode)
//   • tree -> graph: clicking a row navigates to the view that draws the matching node and selects it
// Rows build lazily as folders expand, so a large repo stays responsive. Data comes pre-resolved from
// Python (filetree.py): each entry carries `cov` (coverage shade), `node` (exact id), and `sel` (the id
// a click selects — exact, else the nearest ancestor folder-node = the "finer grain" rule).
const treeBody = document.getElementById('treebody');
const treeToggleBtn = document.getElementById('treetoggle');
const treeResizer = document.getElementById('treeresizer');
const rowByPath = {};   // path (no trailing slash) -> { row, kids, entry, depth, built }
const pathByNode = {};  // node id -> its exact tree path (graph -> tree highlight for a mapped node)
// node id -> the FULL node_path_index collision set at its exact path (primary + others), for any id
// that collided with at least one other — built eagerly from FILE_TREE (unlike rowByPath, which only
// exists for a path once its row has been lazily expanded/built), so a selection can look this up
// regardless of what the tree happens to have rendered so far. See anchorSetFor.
const siblingsByNode = {};
let treeSelPath = null; // path of the currently highlighted row
let treeSpacer = null;  // bottom filler div added when centering a row near the end of the tree (see highlightTreePath)
// Set by onRowClick right before a click leads to a selection: a row the reader just clicked is already
// visible (that's how they clicked it) — highlightTreePath consumes this to skip its own scroll entirely,
// tree -> graph, distinct from a graph -> tree sync (selecting a node/edge on the canvas), which still
// needs to scroll the row into view since the reader never looked at the tree to begin with.
let suppressTreeScroll = false;

// A dir anchor in the map keeps a trailing slash ('src/api/'); the walked dir row does not ('src/api').
// Strip it so the two always match.
function treeKey(p) { return String(p || '').replace(/\/+$/, ''); }

// --- folder peek ----------------------------------------------------------------
// When the file browser is folded away (tree-hidden), selecting a diagram element that anchors a FOLDER
// reveals the browser IN the code viewer's slot (the CSS `tree-peek` state), expanded to that folder,
// so the reader can drill into it. Picking a file there commits it to the code viewer and ends the peek.
// The fold flag itself (tree-hidden / its localStorage) is never touched — the browser folds right back
// once a file is chosen. Peek only applies to the folded state; when the browser is unfolded it's a no-op.
let treePeek = false;
let suppressPeek = false;  // one-shot: a file the reader just picked in the browser is loading — the
                           // owning-folder reselection that follows must NOT re-peek the browser over it.
function setTreePeek(on) {
  if (on === treePeek) return;
  treePeek = on;
  document.body.classList.toggle('tree-peek', on);
  // The header toggle reads "off" (dimmed) when the browser is folded — but during a peek the browser is
  // visible, so it shouldn't look off then.
  treeToggleBtn.classList.toggle('off', document.body.classList.contains('tree-hidden') && !on);
}
// After an active selection (showNodeDetailSynced): peek the browser open for a folder element, or end
// the peek for one that shows a real file (or the suppress flag, when the reader just picked a file).
function updateFolderPeek(id) {
  if (!SERVED) return;
  const consumed = suppressPeek; suppressPeek = false;
  if (!document.body.classList.contains('tree-hidden')) { setTreePeek(false); return; }  // browser unfolded
  const n = GRAPH.nodes[id];
  const showsFile = !!(n && n.file && localRef(n.file) && !isDirRef(n.file, n.line));
  if (showsFile || consumed) { setTreePeek(false); return; }
  const path = pathByNode[id] || (n ? refTreePath(n.file, n.line) : null);
  if (path && rowByPath[path] && rowByPath[path].entry.dir) { expandDir(path); setTreePeek(true); }
}

// One row: a twisty (folders only), the name, and an id chip when a node points exactly here.
function makeRow(entry, depth) {
  const row = document.createElement('div');
  // `ref` = referenced by a component/entity at all (source OR owned) -> bold "on the map"; broader than
  // cov-self (anchor-only). `foot` = part of the currently-selected element's footprint.
  row.className = 'trow cov-' + entry.cov + (entry.dir ? ' tdir' : ' tfile')
    + (entry.ref ? ' ref' : '') + (!entry.dir && footSet.has(treeKey(entry.path)) ? ' foot' : '');
  row.style.paddingLeft = (8 + depth * 14) + 'px';
  row.title = entry.path || entry.name;
  const caret = document.createElement('span');
  caret.className = 'tcaret' + (entry.dir && entry.children.length ? '' : ' leaf');
  caret.textContent = '▶';  // ▶ (rotates when the folder is open)
  const name = document.createElement('span');
  name.className = 'tname';
  name.textContent = entry.name;
  row.appendChild(caret);
  row.appendChild(name);
  if (entry.node && entry.cov === 'self') {
    // The chip marks a true ANCHOR (a node's own source points exactly here). Owned files also carry
    // entry.node (their owner, for the click) but get no chip — the bold `ref` already marks them.
    const chip = document.createElement('span');
    chip.className = 'tchip';
    chip.textContent = entry.node;
    row.appendChild(chip);
  } else if (entry.dir && entry.mapped > 0) {
    // A partial folder (not itself a mapped unit) carries a count of the mapped components/subsystems
    // inside — a positive "expand me" cue. CSS hides it once the folder is open (children show their own).
    const count = document.createElement('span');
    count.className = 'tcount';
    count.textContent = entry.mapped;
    count.title = entry.mapped + ' mapped inside';
    row.appendChild(count);
  }
  return row;
}
function renderChildrenInto(container, children, depth) {
  for (const entry of children) {
    const key = treeKey(entry.path);
    const row = makeRow(entry, depth);
    container.appendChild(row);
    let kids = null;
    if (entry.dir && entry.children.length) {
      kids = document.createElement('div');
      kids.className = 'tchildren';
      container.appendChild(kids);
    }
    rowByPath[key] = { row, kids, entry, depth, built: false };
    row.addEventListener('click', () => onRowClick(key));
  }
}
function onRowClick(key) {
  const rec = rowByPath[key];
  if (!rec) return;
  const e = rec.entry;
  if (e.dir) {
    // A folder expands; it selects ONLY when it is itself a mapped subsystem/component (e.node set).
    // An intermediate folder that merely sits under a mapped one just expands — opening it must not
    // hijack the selection to the containing subsystem. A folder click stays in a folder peek.
    toggleDir(key);
    // e.node set -> this exact path collided in node_path_index (filetree.py): e.others carries the
    // rest, kept instead of dropped — selectFromTreeAnchors decides whether that's one thing or several.
    if (e.node) { suppressTreeScroll = true; selectFromTreeAnchors([e.node, ...e.others], key); }
    return;
  }
  // A file row: the reader wants its source in the code viewer, so end any folder peek and show it.
  const wasPeeking = treePeek;
  if (wasPeeking) setTreePeek(false);
  if (e.node && e.cov === 'self') {
    // An ANCHOR file (a node's own source): selecting its node also loads it into the code viewer AT the
    // node's line (syncTreeToNode -> syncCodeView), so no separate loadCode is needed here.
    suppressTreeScroll = true;
    selectFromTreeAnchors([e.node, ...e.others], key);  // this exact file collided — e.others carries the rest
  } else if (e.node) {
    // An OWNED file (belongs to a component but isn't its anchor): show THIS file, and select its owner
    // (definition-first, already resolved into e.node). The syncCodeView/syncTreeToNode "belongs" guards
    // keep this file shown + highlighted since it's in the owner's `files`, instead of jumping to source.
    if (wasPeeking) suppressPeek = true;
    const owner = GRAPH.nodes[e.node];
    cvFiles = (owner && owner.files) || [];
    loadCode(e.path, null);
    suppressTreeScroll = true;
    highlightTreePath(key);
    selectFromTree(e.node);
  } else {
    // A file that is not itself a node: show its source directly (no line). If it sits under a mapped
    // folder, also select that owning subsystem/entity — but the file the reader clicked is what the
    // code viewer shows, not the owner's own anchor, and it must NOT re-peek the browser over that file.
    if (wasPeeking) suppressPeek = true;
    loadCode(e.path, null);
    if (e.sel) { suppressTreeScroll = true; selectFromTree(e.sel); }
  }
}
function toggleDir(key) {
  const rec = rowByPath[key];
  if (!rec || !rec.kids) return;
  const open = rec.kids.classList.toggle('open');
  rec.row.classList.toggle('open', open);
  if (open && !rec.built) { renderChildrenInto(rec.kids, rec.entry.children, rec.depth + 1); rec.built = true; }
}
function expandDir(key) {  // ensure a folder is open + its children built (used when revealing a path)
  const rec = rowByPath[key];
  if (!rec || !rec.kids || rec.kids.classList.contains('open')) return;
  rec.kids.classList.add('open');
  rec.row.classList.add('open');
  if (!rec.built) { renderChildrenInto(rec.kids, rec.entry.children, rec.depth + 1); rec.built = true; }
}

// tree -> graph: which view draws `id` (so the box exists to select), and the id to select there.
function selectTargetFor(id) {
  const n = GRAPH.nodes[id];
  if (!n) return null;
  const parentKind = (k) => { const p = n.parent; return p && GRAPH.nodes[p] ? GRAPH.nodes[p].kind === k : false; };
  switch (n.kind) {
    case 'component': {
      // Open the component INSIDE its parent subsystem's card (the zoomed-in neighbourhood), where it's
      // drawn as a member box. A default subsystem is injected when a map has none, so this parent is
      // normally present; fall back to the Subsystems overview if a component is somehow ungrouped.
      const p = n.parent;
      const inSub = !!(p && GRAPH.nodes[p] && GRAPH.nodes[p].kind === 'subsystem');
      return { state: inSub ? { kind: 'subsystem', sid: p } : { kind: 'container' }, selectId: id };
    }
    case 'dep': {
      // A dependency lives at the Context altitude, not in a subsystem: an external SYSTEM is its own
      // box on the Context diagram, while an in-process framework/library is folded into the "Libraries"
      // box and drawn individually only in its drill (kind:'libs'). Route to whichever holds a
      // selectable box for this dep.
      const folded = FOLDED_LIBS.some((d) => d.id === id);
      return { state: folded ? { kind: 'libs' } : { kind: 'context' }, selectId: id };
    }
    case 'usecase':  // a use case opens its T6 flow (sequence diagram + numbered narrative)
      return { state: { kind: 'usecase', uc: id } };
    case 'entity': {
      const sd = HAS_SUBDOMAINS ? topSubdomainOf(id) : null;
      return { state: sd ? { kind: 'domsub', sd } : { kind: 'domain' }, selectId: id };
    }
    case 'subsystem':  // its parent's card draws it as a box; a top-level one lives on the Subsystems overview
      return { state: parentKind('subsystem') ? { kind: 'subsystem', sid: n.parent } : { kind: 'container' }, selectId: id };
    case 'subdomain':
      return { state: parentKind('subdomain') ? { kind: 'domsub', sd: n.parent } : { kind: 'domain' }, selectId: id };
    default:
      return { state: { kind: 'context' }, selectId: id };  // unknown kind -> the always-present root
  }
}
// `allIds`: the full node_path_index collision set at the path this navigation came from (undefined /
// [] for callers that aren't file-tree-driven, e.g. a flow narrative link — no "Also defined here" then).
function selectFromTree(nodeId) {
  const t = selectTargetFor(nodeId);
  if (!t) { suppressTreeScroll = false; return; }  // no selection follows — don't leave the flag stuck for later
  const cur = history[hi];
  if (cur && stateKey(cur) === stateKey(t.state)) {       // already in the right view — select in place
    const el = mainScene && mainScene.nodeEls[t.selectId];
    if (el) selectNode(mainScene, el, t.selectId); else showNodeDetailSynced(t.selectId);
    // A node reached via the file tree ALWAYS gets the zoom-to-match-sidebar-text-size move — there's
    // no modifier key on a tree row to gate it on, unlike a canvas click (see selectNodeFromCanvas).
    if (el) matchTextSize(el);
  } else {                                                // navigate, then render() consumes pendingSelect
    pendingSelect = t.selectId;
    go(t.state);
  }
}
// A file/folder row whose exact path anchors one or more elements (node_path_index — filetree.py).
// One element: select it directly, same as ever (which highlights the row via syncTreeToNode, same as
// any other selection). Several: never guess which one was meant — list every one's full detail in the
// panel instead (showElementsList; each title re-selects that one for real), and switch the diagram to
// their shared view ONLY when they all genuinely live on the exact same one; otherwise leave whatever
// diagram is currently showing untouched. Nothing gets selected in that case, so nothing would
// otherwise mark this row as the source — highlight `path` (this row itself) directly instead.
function selectFromTreeAnchors(allIds, path) {
  if (allIds.length <= 1) { if (allIds.length) selectFromTree(allIds[0]); return; }
  highlightTreePath(path);
  const states = allIds.map((id) => selectTargetFor(id)).filter(Boolean).map((t) => t.state);
  const shared = states.length === allIds.length && states.every((s) => stateKey(s) === stateKey(states[0]))
    ? states[0] : null;
  const cur = history[hi];
  if (shared && (!cur || stateKey(cur) !== stateKey(shared))) {
    pendingElementsList = allIds;  // render() shows the list once the shared view has finished rendering
    go(shared);
  } else {
    showElementsList(allIds);  // already on the shared view (or there isn't one) — just update the panel
  }
}

// A source ref (a node's `file`/`line`, an edge's `where`) -> the tree path it resolves to, or null when
// it isn't a local repo-relative path (an off-repo URL, or no ref at all) — the same test `openSource`
// uses to decide whether a ref is clickable.
function refTreePath(file, line) { return file && localRef(file) ? treeKey(cleanPath(file, line)) : null; }
// graph -> tree: highlight the row for `id`'s source path (exact map, else its file/dir path), expanding
// ancestor folders so the row exists and is visible. No path / no row -> just clear the highlight.
function syncTreeToNode(id) {
  const n = GRAPH.nodes[id];
  highlightFootprint(n ? n.files : null);  // light up the element's WHOLE file set in the browser
  // Keep the 'sel' highlight on a file the reader just clicked if it belongs to this element (an owned
  // file); otherwise move it to the element's own anchor row.
  if (!(treeSelPath && n && (n.files || []).indexOf(treeSelPath) !== -1)) {
    const path = pathByNode[id] || (n ? refTreePath(n.file, n.line) : null);
    highlightTreePath(path);
  }
  if (n) syncCodeView(n.file, n.line, n.files);  // mirror the node's source into the code viewer (FULL mode)
}
// A second, dimmer highlight over EVERY file the selected element covers (its `files`) — the "footprint"
// — distinct from the single 'sel' row. Folders holding a footprint file are expanded so the lit rows are
// visible; `footSet` also lets a row built later (manual expand) pick up the class in makeRow.
let footSet = new Set();
function highlightFootprint(files) {
  footSet = new Set((files || []).map(treeKey));
  for (const k in rowByPath) {
    if (!rowByPath[k].entry.dir) rowByPath[k].row.classList.toggle('foot', footSet.has(k));
  }
  for (const k of footSet) {
    const parts = k.split('/');
    for (let i = 0, acc = ''; i < parts.length - 1; i++) { acc = acc ? acc + '/' + parts[i] : parts[i]; expandDir(acc); }
  }
}
function highlightTreePath(path) {
  const skipScroll = suppressTreeScroll;
  suppressTreeScroll = false;  // one-shot: consume it here, whether this call ran sync or after a navigation
  if (treeSpacer) { treeSpacer.remove(); treeSpacer = null; }  // drop any previous centering filler first
  const prevRow = treeSelPath && rowByPath[treeSelPath] ? rowByPath[treeSelPath].row : null;
  if (prevRow) prevRow.classList.remove('sel');
  treeSelPath = null;
  if (!path) return;
  const parts = path.split('/');
  for (let i = 0, acc = ''; i < parts.length - 1; i++) { acc = acc ? acc + '/' + parts[i] : parts[i]; expandDir(acc); }
  const rec = rowByPath[path];
  if (!rec) return;  // node points at a path not in the walk (excluded / deleted) — nothing to highlight
  rec.row.classList.add('sel');
  treeSelPath = path;
  // A row the reader just clicked in THIS tree is already visible (tree -> graph) — nothing to scroll to.
  if (skipScroll) return;
  // A big jump centers the new row so it's easy to find; a move to a row already right next to the
  // PREVIOUS selection (e.g. the next sibling file) would make that same centering a jarring, pointless
  // jump — just nudge it into view instead. `prevRow.offsetParent` is null when its folder got collapsed
  // in the meantime, so there's nothing visible to compare against — treat that as "not near".
  const NEAR_PX = 48;  // ~2 tree rows
  const near = prevRow && prevRow.offsetParent !== null
    && Math.abs(prevRow.getBoundingClientRect().top - rec.row.getBoundingClientRect().top) < NEAR_PX;
  if (near) { rec.row.scrollIntoView({ block: 'nearest' }); return; }
  // Same shortfall trick as showElementsList: a row near the END of the tree has no content below it
  // for the viewport to scroll into, so plain block:'center' would leave it stuck low. Pad the bottom
  // with exactly the shortfall so even the last row can still be centered.
  const bodyRect = treeBody.getBoundingClientRect(), rowRect = rec.row.getBoundingClientRect();
  const rowCenter = treeBody.scrollTop + (rowRect.top - bodyRect.top) + rowRect.height / 2;
  const shortfall = rowCenter + treeBody.clientHeight / 2 - treeBody.scrollHeight;
  if (shortfall > 0) {
    treeSpacer = document.createElement('div');
    treeSpacer.style.height = Math.ceil(shortfall) + 'px';
    treeBody.appendChild(treeSpacer);
  }
  rec.row.scrollIntoView({ block: 'center' });
}
// Build the file browser from a tree root (embedded FILE_TREE in the legacy path, or the server's
// /api/tree in FULL mode). Indexes node<->path both ways, then renders the top level.
function renderFileTree(root) {
  (function index(e) {
    // Only ANCHOR rows (cov 'self') feed the node->path map: an owned-file row also carries e.node (its
    // owner, for the click) but must NOT claim to be that owner's canonical path, or graph->tree would
    // jump to a random owned file instead of the element's source.
    if (e.node && e.cov === 'self') {
      pathByNode[e.node] = treeKey(e.path);
      const all = [e.node, ...(e.others || [])];
      if (all.length > 1) for (const id of all) siblingsByNode[id] = all;
    }
    for (const c of e.children) index(c);
  })(root);
  const kids = root.children || [];
  treeBody.innerHTML = '';
  if (!kids.length) { treeBody.innerHTML = '<div class="tempty">No files found.</div>'; return; }
  renderChildrenInto(treeBody, kids, 0);
}
function buildFileTree() {
  // The tree is no longer embedded; it arrives from the server (see initServerMode). Kept as the
  // single build entry point so a future embedded fallback can route through the same renderer.
  if (FILE_TREE) renderFileTree(FILE_TREE);
}

// --- the coyodex server: file browser + code viewer ------------------------------
// The map is always served by `coyodex serve` (the view data is fetched from it at boot), so the file
// browser and code viewer are always available: they read files from the server, which serves them
// from git at the map's commit. A /api/health probe confirms the API is reachable before we reveal the
// panes. API_BASE is the map's own directory + "api/" (the page is served at /p/<slug>/); it is declared
// at the top of the module.
let SERVED = false;
// API_BASE is declared at the top of the module (the view bundle is fetched from it at boot).
async function initServerMode() {
  if (!API_BASE) return;  // file:// — degraded mode, nothing to probe
  try {
    const r = await fetch(API_BASE + 'health', { cache: 'no-store' });
    if (!r.ok) return;
    const j = await r.json();
    if (!j || !j.ok) return;
  } catch (_) { return; }  // no server — stay degraded
  SERVED = true;
  document.body.classList.add('served');
  // The header title becomes a link back to the server's landing page (all maps) — only in FULL mode,
  // since a static file:// map has no server root to return to.
  const h1 = document.querySelector('header h1');
  if (h1) { h1.classList.add('home-link'); h1.title = 'Back to all maps'; h1.addEventListener('click', () => { location.href = new URL('/', location.href).href; }); }
  refitStage();  // the diagram column just narrowed to make room for the browser + code panes
  loadServerTree();
}
async function loadServerTree() {
  try {
    const r = await fetch(API_BASE + 'tree', { cache: 'no-store' });
    if (!r.ok) throw new Error('tree ' + r.status);
    renderFileTree(await r.json());
  } catch (_) {
    treeBody.innerHTML = '<div class="tempty">Could not load the file tree.</div>';
  }
}

// --- code viewer -----------------------------------------------------------------
// A first-pass read-only source view: fetch the file from the server (git @ commit), highlight it with
// highlight.js (lazy-loaded from a CDN, SRI-pinned like the other libs), show a line-number gutter, and
// scroll to / highlight the current line. Deliberately simple — richer navigation is a planned follow-up.
const cvbody = document.getElementById('cvbody');
const cvpath = document.getElementById('cvpath');
const cvopen = document.getElementById('cvopen');  // ↗ opens the shown file in the external editor / on GitHub
if (cvopen) cvopen.addEventListener('click', () => { if (cvPath) openSource({ file: cvPath, line: cvLine }); });
let cvPath = null, cvTable = null;  // the file currently shown + its rendered table (for same-file line moves)
let cvLine = null;                  // the line to highlight — a module var so a line that arrives while the
                                    // file is still loading (tree click: file-load then node-select) still lands
let cvReq = 0;                      // request token — a newer load supersedes an in-flight older one
let cvFiles = [];                   // the selected element's files (source first) — the header's switcher list

// The code-viewer header: a plain path, or — when the selected element owns several files — a switcher
// (its `files`, source first) so the reader can page through them without leaving the element. The
// current file stays selected; picking one loads it + highlights its tree row (no graph re-selection).
function renderCvHeader() {
  const suffix = cvLine ? ':' + cvLine : '';
  if (SERVED && cvFiles.length > 1) {
    const opts = cvFiles.map((f) =>
      '<option value="' + esc(f) + '"' + (f === cvPath ? ' selected' : '') + ' title="' + esc(f) + '">'
      + esc(f.split('/').pop()) + '</option>').join('');
    cvpath.innerHTML = '<select class="cvfiles" title="Files in this element">' + opts + '</select>'
      + '<span class="cvpathfull">' + esc((cvPath || '') + suffix) + '</span>';
    const sel = cvpath.querySelector('select.cvfiles');
    if (sel) sel.addEventListener('change', () => {
      suppressTreeScroll = false;
      highlightTreePath(treeKey(sel.value));
      loadCode(sel.value, null);
    });
  } else {
    cvpath.textContent = (cvPath || '') + suffix;
  }
  if (cvopen) cvopen.hidden = !(cvPath && localRef(cvPath));  // the ↗ only shows once a local file is open
}
const HLJS_VER = '11.9.0';
const HLJS_JS = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/' + HLJS_VER + '/highlight.min.js';
const HLJS_JS_SRI = 'sha384-F/bZzf7p3Joyp5psL90p/p89AZJsndkSoGwRpXcZhleCWhd8SnRuoYo4d0yirjJp';
const HLJS_CSS = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/' + HLJS_VER + '/styles/github.min.css';
const HLJS_CSS_SRI = 'sha384-eFTL69TLRZTkNfYZOLM+G04821K1qZao/4QLJbet1pP4tcF+fdXq/9CdqAbWRl/L';
const EXT_LANG = { js: 'javascript', jsx: 'javascript', mjs: 'javascript', cjs: 'javascript', ts: 'typescript', tsx: 'typescript', py: 'python', rb: 'ruby', go: 'go', rs: 'rust', java: 'java', kt: 'kotlin', c: 'c', h: 'c', cpp: 'cpp', cc: 'cpp', hpp: 'cpp', cs: 'csharp', php: 'php', swift: 'swift', scala: 'scala', sh: 'bash', bash: 'bash', zsh: 'bash', sql: 'sql', json: 'json', yaml: 'yaml', yml: 'yaml', toml: 'ini', ini: 'ini', md: 'markdown', html: 'xml', xml: 'xml', css: 'css', scss: 'scss' };
const langOf = (p) => EXT_LANG[(p.split('.').pop() || '').toLowerCase()] || null;
let hljsP = null;
function ensureHljs() {
  if (window.hljs) return Promise.resolve(window.hljs);
  if (!hljsP) hljsP = new Promise((res) => {
    const css = document.createElement('link');
    css.rel = 'stylesheet'; css.href = HLJS_CSS; css.integrity = HLJS_CSS_SRI; css.crossOrigin = 'anonymous';
    document.head.appendChild(css);
    const s = document.createElement('script');
    s.src = HLJS_JS; s.integrity = HLJS_JS_SRI; s.crossOrigin = 'anonymous';
    s.onload = () => res(window.hljs || null);
    s.onerror = () => res(null);  // CDN blocked/offline — fall back to un-highlighted text
    document.head.appendChild(s);
  });
  return hljsP;
}
// Split highlight.js's flat markup into per-line HTML, re-opening any spans that straddle a newline so
// each line's markup is self-balanced (needed for the one-row-per-line table + gutter).
function highlightedToLines(rootEl) {
  const lines = [''];
  const openTag = (el) => {
    const cls = el.getAttribute('class');
    return '<' + el.tagName.toLowerCase() + (cls ? ' class="' + esc(cls) + '"' : '') + '>';
  };
  (function walk(node, stack) {
    for (const ch of node.childNodes) {
      if (ch.nodeType === 3) {
        const parts = ch.nodeValue.split('\n');
        for (let i = 0; i < parts.length; i++) {
          if (i > 0) {
            for (let j = stack.length - 1; j >= 0; j--) lines[lines.length - 1] += '</' + stack[j].tagName.toLowerCase() + '>';
            lines.push(stack.map(openTag).join(''));
          }
          lines[lines.length - 1] += esc(parts[i]);
        }
      } else if (ch.nodeType === 1) {
        lines[lines.length - 1] += openTag(ch);
        stack.push(ch); walk(ch, stack); stack.pop();
        lines[lines.length - 1] += '</' + ch.tagName.toLowerCase() + '>';
      }
    }
  })(rootEl, []);
  return lines;
}
function markLine(line) {
  if (!cvTable) return;
  const prev = cvTable.querySelector('tr.cvcur');
  if (prev) prev.classList.remove('cvcur');
  if (!line) return;
  const row = cvTable.querySelector('tr[data-ln="' + line + '"]');
  if (row) { row.classList.add('cvcur'); row.scrollIntoView({ block: 'center' }); }
}
function renderCode(path, text, token) {
  text = text.replace(/\r\n/g, '\n');  // normalize CRLF so neither path leaves a stray \r under white-space:pre
  ensureHljs().then((hl) => {
    if (token !== cvReq) return;  // superseded by a newer load
    let lineHtml;
    if (hl) {
      const lang = langOf(path);
      let out = null;
      try { out = lang && hl.getLanguage(lang) ? hl.highlight(text, { language: lang, ignoreIllegals: true }) : hl.highlightAuto(text); }
      catch (_) { out = null; }
      const tmp = document.createElement('div');
      tmp.innerHTML = out ? out.value : esc(text);  // hljs output is trusted markup; the fallback is esc()
      lineHtml = highlightedToLines(tmp);
    } else {
      lineHtml = text.split('\n').map(esc);
    }
    if (lineHtml.length && lineHtml[lineHtml.length - 1] === '') lineHtml.pop();  // drop trailing blank line
    const rows = lineHtml.map((h, i) =>
      '<tr data-ln="' + (i + 1) + '"><td class="ln">' + (i + 1) + '</td><td class="code hljs">' + (h || '&nbsp;') + '</td></tr>').join('');
    cvbody.innerHTML = '<table class="cvcode"><tbody>' + rows + '</tbody></table>';
    cvTable = cvbody.querySelector('table.cvcode');
    markLine(cvLine);  // the latest requested line (may have arrived after the fetch started)
  });
}
// Load `path` (repo-relative) into the code viewer, scrolled to `line`. Same file + new line just moves
// the highlight (no refetch). Only meaningful in FULL mode; a no-op otherwise.
async function loadCode(path, line) {
  if (!SERVED || !path) return;
  cvLine = line || null;
  if (path === cvPath) { renderCvHeader(); markLine(cvLine); return; }  // same file — move the line, refresh header
  const token = ++cvReq;
  cvPath = path; cvTable = null;
  renderCvHeader();  // set the header (dropdown marks the new file) AFTER cvPath is updated
  cvbody.innerHTML = '<p class="cvempty">Loading…</p>';
  let text = null;
  try {
    const r = await fetch(API_BASE + 'src?path=' + encodeURIComponent(path), { cache: 'no-store' });
    if (token !== cvReq) return;
    if (!r.ok) {
      cvbody.innerHTML = '<p class="cverr">' + (r.status === 404 ? 'Not tracked in this commit.' : 'Could not load this file.') + '</p>';
      cvPath = null; return;
    }
    text = await r.text();
  } catch (_) {
    if (token === cvReq) { cvbody.innerHTML = '<p class="cverr">Could not load this file.</p>'; cvPath = null; }
    return;
  }
  if (token !== cvReq) return;
  renderCode(path, text, token);
}
// Mirror a selection's source ref into the code viewer — from a node/edge with a local file anchor.
// `files` (the element's whole file list, source first) drives the header switcher. Skips directory
// anchors (a subsystem's folder) and off-repo URLs — but if the element still has member/owned files,
// the first is opened so the switcher has something to show.
function syncCodeView(file, line, files) {
  if (Array.isArray(files)) cvFiles = files;
  const anchor = (file && localRef(file) && !isDirRef(file, line)) ? cleanPath(file, line) : null;
  // Keep the file already shown if it belongs to this element BUT is NOT the element's own anchor — i.e.
  // an OWNED file the reader clicked (show that file, not the element's source). When the element's own
  // anchor IS the shown file, fall through to loadCode so it moves the line highlight to the new
  // element's def line (two elements sharing one file must still jump between their lines).
  if (cvPath && cvFiles.indexOf(cvPath) !== -1 && anchor !== cvPath) { renderCvHeader(); return; }
  if (anchor) { loadCode(anchor, line || null); return; }
  if (SERVED && cvFiles.length) { loadCode(cvFiles[0], null); return; }  // a group's dir anchor -> its first file
  renderCvHeader();  // nothing to load (off-repo / no files) — still refresh the header (clears a stale switcher)
}
// Open a source ref (a glossary term's home, or any standalone file link) into the code viewer — the
// in-app viewer when served, else fall back to the external editor / GitHub (degraded mode has no code
// pane). Not tied to a graph selection, so it clears the element footprint + switcher.
function openInCodeViewer(file, line) {
  if (!file) return;
  if (SERVED && localRef(file)) {
    highlightFootprint(null);
    highlightTreePath(refTreePath(file, line));  // highlights the file's row (or its folder, for a dir home)
    syncCodeView(file, line, []);                // shows the file; a no-op for a directory ref
    return;
  }
  openSource({ file: file, line: line });        // degraded / off-repo: the external editor is the only option
}

// --- startup --------------------------------------------------------------------
stage.addEventListener('mousedown', (e) => { downX = e.clientX; downY = e.clientY; }, true);
document.addEventListener('keydown', (e) => {
  // ⌘/⌥ + ←/→ navigate history (preventDefault so ⌘+arrows don't trigger the browser's back/forward)
  if ((e.metaKey || e.altKey) && e.key === 'ArrowLeft') { e.preventDefault(); back(); return; }
  if ((e.metaKey || e.altKey) && e.key === 'ArrowRight') { e.preventDefault(); fwd(); return; }
  // Bare ←/→ walk the use-case flow step by step (only on a flow view, and not while typing in a field).
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || '') || (e.target && e.target.isContentEditable);
  if (flowPlay && !typing && !e.metaKey && !e.altKey && !e.ctrlKey) {
    if (e.key === 'ArrowLeft') { e.preventDefault(); flowStepBy(-1); return; }
    if (e.key === 'ArrowRight') { e.preventDefault(); flowStepBy(1); return; }
  }
  if (e.key === 'Escape' && mainScene) resetScene(mainScene);
});
// While ⌘ (or ⌃ off Mac) is held, flag the body so drillable subsystems/arrows show the drill-in
// cursor (see .drill in the CSS). Clear on key-up and on blur so a released key never sticks.
const setCmd = (on) => { document.body.classList.toggle('cmd', on); renderHoverTip(); };
document.addEventListener('keydown', (e) => { if (e.key === 'Meta' || e.key === 'Control') setCmd(true); });
document.addEventListener('keyup', (e) => { if (e.key === 'Meta' || e.key === 'Control') setCmd(false); });
window.addEventListener('blur', () => setCmd(false));
window.addEventListener('resize', refitStage);  // keep the diagram fitted when the window itself resizes

// --- open source in an external editor / on GitHub -------------------------------
// A node's source ref (file [+ line]) opens in the user's editor via its URL scheme (vscode://,
// idea://, …) or, as a portable fallback, on GitHub (blob URL pinned to the map's commit). Ported
// from mondrian: a target table + placeholder fill + a scheme allowlist + a hidden-anchor click —
// no server, the OS scheme handler does the opening. The absolute path is built from a repo root the
// user sets once (from REPO_ROOT_DEFAULT, delivered in the view bundle, overridable in Settings/localStorage).
// REPO_ROOT_DEFAULT / GH_REPO_DEFAULT / GH_COMMIT are declared + filled at boot (top of module).
const GH_BAKED = !!(GH_REPO_DEFAULT && GH_COMMIT);  // GitHub target available out of the box
const OPEN_TARGETS = [
  { id: 'native', label: '— choose —', uri: '' },
  { id: 'github', label: 'GitHub (blob, pinned to commit)', uri: '' },  // only listed/usable when GH_BASE is set
  { id: 'vscode', label: 'VS Code', uri: 'vscode://file{abspath}:{line}:{col}' },
  { id: 'cursor', label: 'Cursor', uri: 'cursor://file{abspath}:{line}:{col}' },
  { id: 'vscodium', label: 'VSCodium', uri: 'vscodium://file{abspath}:{line}:{col}' },
  { id: 'windsurf', label: 'Windsurf', uri: 'windsurf://file{abspath}:{line}:{col}' },
  { id: 'intellij', label: 'IntelliJ IDEA', uri: 'idea://open?file={abspath}&line={line}' },
  { id: 'pycharm', label: 'PyCharm', uri: 'pycharm://open?file={abspath}&line={line}' },
  { id: 'webstorm', label: 'WebStorm', uri: 'webstorm://open?file={abspath}&line={line}' },
  { id: 'goland', label: 'GoLand', uri: 'goland://open?file={abspath}&line={line}' },
  { id: 'zed', label: 'Zed', uri: 'zed://file{abspath}:{line}:{col}' },
  { id: 'custom', label: 'Custom…', uri: '' },
];
// The only schemes allowed to land in an <a href> — blocks javascript:/data:/file:/http(s): so a
// hand-typed custom template can't run script or hijack navigation.
const ALLOWED_OPEN_SCHEMES = new Set([
  'vscode', 'vscode-insiders', 'cursor', 'vscodium', 'windsurf', 'zed', 'idea', 'pycharm', 'webstorm',
  'goland', 'clion', 'rubymine', 'phpstorm', 'rider', 'datagrip', 'fleet', 'jetbrains', 'subl',
  'txmt', 'mate', 'mvim', 'emacs', 'atom',
]);
const LS = { editor: 'coyodex.editor', custom: 'coyodex.customUri', root: 'coyodex.srcRoot', ok: 'coyodex.rootOk', repo: 'coyodex.ghRepo', coach: 'coyodex.coachSeen', leftW: 'coyodex.leftW', panelH: 'coyodex.panelH', treeW: 'coyodex.treeW', treeHidden: 'coyodex.treeHidden' };
// The on-disk source root and the GitHub repo URL describe THIS map's repository, so they are stored
// per-repo — namespaced by the map's baked identity (its repo root, or the GitHub URL as a fallback).
// A single global key let a root saved while viewing one repo's map open files from the WRONG repo in
// another map served from the same browser origin (file:// or a shared localhost). Editor choice /
// custom URI / onboarding flag stay global — one editor per machine, shared across every map.
const MAP_NS = REPO_ROOT_DEFAULT || GH_REPO_DEFAULT || 'default';
const PER_REPO = new Set([LS.root, LS.repo]);
const nsKey = (k) => (PER_REPO.has(k) ? k + '::' + MAP_NS : k);
const lsGet = (k) => { try { return localStorage.getItem(nsKey(k)); } catch (_) { return null; } };
const lsSet = (k, v) => { try { localStorage.setItem(nsKey(k), v); } catch (_) { /* private mode: in-session only */ } };
const srcRoot = () => (lsGet(LS.root) || REPO_ROOT_DEFAULT || '').replace(/\/+$/, '');
// Default target: GitHub when the map has a remote+commit (zero setup, works for everyone), else the
// '— choose —' placeholder. A saved choice always wins.
const openTargetId = () => lsGet(LS.editor) || (GH_BAKED ? 'github' : 'native');
const needsRoot = (id) => id !== 'native' && id !== 'github';  // only editor/custom targets need a local root
const customUri = () => lsGet(LS.custom) || '';
// `file` keeps its source anchor as parsed from the map link (e.g. 'src/app.py#L42', 'src/app.py:42',
// or a range like 'src/app.py:42-51'); the line is carried separately in `line`, so strip the anchor +
// any leading slash before joining the path onto the repo root or the GitHub base. The `#L<n>` form
// (with an optional `-L<m>`/`-<m>` range) is unambiguous; the `:<n>` form (with an optional `-<m>`
// range) is stripped only when its start equals the parsed `line`, so a real path ending in
// ':<digits>' survives.
const cleanPath = (file, line) => {
  let p = String(file).replace(/#L\d+(?:-L?\d+)?$/, '');
  if (line) p = p.replace(new RegExp(':' + line + '(?:-\\d+)?$'), '');
  return p.replace(/^\/+/, '');
};
// True when a map href is an in-repo path (a file or a directory) rather than an off-repo URL — only
// those can be opened in the editor / on GitHub. An `http(s)://…` ref is left as plain text. The `://`
// test (not a bare `scheme:`) is deliberate: it must NOT match the `path:line` form like `app.py:42`.
const localRef = (file) => !!file && !/^[a-z][a-z0-9+.-]*:\/\//i.test(String(file));
// An edge's `where` source ref ("path#Lnn" / "path:nn" / "path:nn-mm" / "path") -> {file, line} for
// openSource — `line` is the anchor's START line. The full ref stays as `file` (cleanPath/editorUri/
// ghUrl strip the anchor themselves), like a node's file.
const whereNode = (where) => { const m = String(where).match(/(?:#L|:)(\d+)(?:-L?\d+)?$/); return { file: where, line: m ? +m[1] : null }; };
// A directory ref ends with `/` (the map convention `[dir/](path/)`); it opens differently from a file —
// GitHub `/tree/` not `/blob/`, the editor without a line/column, and no `#L` anchor.
const isDirRef = (file, line) => cleanPath(file, line).endsWith('/');
const uriScheme = (u) => { const m = /^([a-zA-Z][a-zA-Z0-9+.-]*):/.exec(u); return m ? m[1].toLowerCase() : ''; };
const fillUri = (t, v) => t.replace(/\{abspath\}/g, v.abspath).replace(/\{path\}/g, v.path)
  .replace(/\{line\}/g, v.line).replace(/\{col\}/g, v.col);

// Editor URI for a ref, or null when no editor is chosen, no root is set, or the scheme isn't allowed.
function editorUri(file, line) {
  const id = openTargetId();
  if (id === 'native') return null;
  const t = OPEN_TARGETS.find((x) => x.id === id);
  let tmpl = id === 'custom' ? customUri() : (t ? t.uri : '');
  const root = srcRoot();
  if (!tmpl || !root) return null;
  const rel = cleanPath(file, line);
  // A directory has no line/column — drop that suffix so we open the folder, not a phantom `dir:1:1`.
  // Covers both template shapes: `…{abspath}:{line}:{col}` and `…?file={abspath}&line={line}`.
  if (isDirRef(file, line)) tmpl = tmpl.replace(/:\{line\}:\{col\}$/, '').replace(/[?&]line=\{line\}$/, '');
  const uri = fillUri(tmpl, { abspath: root + '/' + rel, path: rel, line: line || 1, col: 1 });
  return ALLOWED_OPEN_SCHEMES.has(uriScheme(uri)) ? uri : null;
}
// GitHub repo URL — a saved override wins over the build-time default; trailing slashes trimmed.
const ghRepo = () => (lsGet(LS.repo) || GH_REPO_DEFAULT || '').replace(/\/+$/, '');
// The GitHub-resolvable ref for the map's commit. The `Commit:` field can hold more than a bare SHA,
// and GitHub 404s on anything that isn't a real commit/tag/branch — so reduce it to one:
//   • short SHA              dc8e5d6                       -> used as-is
//   • dirty build            dc8e5d6-dirty                 -> drop the `-dirty` describe suffix
//   • `git describe --tags`  v1.4.2-5-gdc8e5d6[-dirty]     -> the commit is the `g<sha>` tail
// An exact tag (`v1.4.2`, no `-<N>-g…`) is itself a valid ref, so it's left untouched. The meta line
// still shows the full raw value, so dirty / describe provenance stays visible.
const ghRef = () => {
  const raw = String(GH_COMMIT || '').replace(/-dirty$/, '');
  const m = raw.match(/-\d+-g([0-9a-f]+)$/i);  // `<tag>-<commits-since>-g<abbrev-sha>`
  return m ? m[1] : raw;
};
// Blob URL for a ref, pinned to the map's commit, or null when no repo URL / no commit is known.
const ghUrl = (file, line) => {
  const repo = ghRepo();
  if (!repo || !GH_COMMIT) return null;
  const rel = cleanPath(file, line);
  // A directory lives under /tree/ (no line anchor); a file under /blob/, pinned to the map's commit.
  const dir = isDirRef(file, line);
  return repo + '/' + (dir ? 'tree' : 'blob') + '/' + ghRef() + '/' + rel + (!dir && line ? '#L' + line : '');
};
function fireUri(uri) {
  const a = document.createElement('a');
  a.href = uri; a.style.display = 'none';
  document.body.appendChild(a); a.click(); a.remove();
}
// Open a node's source. On first use (an editor is chosen but the seeded root isn't confirmed yet) we
// route through Settings so the user can confirm/fix the root once — the browser can't check whether a
// path exists, so we ask rather than guess. Side effect only: the editor / GitHub hand-off.
let pendingSrc = null;
function openSource(n) {
  if (!n || !n.file) return;
  // First time ever: pop Settings so the user picks how source opens (editor or GitHub) and confirms
  // the root / URL. After they Save once (LS.ok), later clicks open straight away.
  if (lsGet(LS.ok) !== '1') { pendingSrc = n; openSettings(true); return; }
  doOpenSource(n);
}
function doOpenSource(n) {
  // An editor target builds a scheme URI; the GitHub target (or any fallback) opens the blob URL.
  if (openTargetId() !== 'github') {
    const uri = editorUri(n.file, n.line);
    if (uri) { fireUri(uri); return; }
  }
  const gh = ghUrl(n.file, n.line);
  if (gh) { window.open(gh, '_blank', 'noopener'); return; }
  pendingSrc = n; openSettings(false);   // nothing usable configured yet -> open Settings
}
// ⌘-click a leaf that carries a source ref opens it instead of selecting; `markOpenSrc` tags such
// boxes so the ⌘-held cursor shows the open-source affordance. Shared by the component + domain
// binders so the behaviour lands in one place (see bindNodes / bindDomain).
// Only these leaf kinds open their source on ⌘-click — never a subsystem (it drills) or a dep (its
// `file` is an external manifest, not local source). A subsystem box reached via bindNodes (the
// neighbourhood view) carries a `file` too, so this guard keeps its ⌘-click as a drill.
const SRC_KINDS = new Set(['component', 'entity']);
// The box "open source" affordance (corner ↗ icon, ⌘-click, `</>` cursor, its hover tooltip, and the
// double-click open) is intentionally RETIRED: opening a file externally now lives solely on the code
// viewer's header ↗. Selecting a box already mirrors its source into the in-app code viewer. `srcNode`
// is the single gate every one of those affordances checks, so returning null disables them all at once.
// (markOpenSrc / openSrcClick / actionOpenSrcHtml and the `is-open` icon are now inert — safe to prune.)
const srcNode = (_id) => null;
function markOpenSrc(el, id) { if (srcNode(id)) el.classList.add('opensrc'); }
function openSrcClick(id, ev) { const n = srcNode(id); if (n && isDrillClick(ev)) { openSource(n); return true; } return false; }

// --- settings dialog (editor target + repo root) ---------------------------------
// A small modal that doubles as the first-use confirm. Everything persists to localStorage — no
// server (mondrian's /settings endpoint is dropped). Saving on first use continues the pending open.
const modal = document.getElementById('modal');
const setbtn = document.getElementById('setbtn');
const setEditor = document.getElementById('setEditor');
const setCustomRow = document.getElementById('setCustomRow');
const setCustom = document.getElementById('setCustom');
const setRoot = document.getElementById('setRoot');
const setRootRow = document.getElementById('setRootRow');
const setGhRepo = document.getElementById('setGhRepo');
const setGhRow = document.getElementById('setGhRow');
const setHelp = document.getElementById('setHelp');
const setGhHelp = document.getElementById('setGhHelp');
const setCancel = document.getElementById('setCancel');
const setSave = document.getElementById('setSave');
const modalErr = document.getElementById('modalErr');
const modalIntro = document.getElementById('modalIntro');
const modalTitle = document.getElementById('modalTitle');
OPEN_TARGETS.forEach((t) => {
  if (t.id === 'github' && !GH_BAKED) return;  // GitHub target only when the map has a remote + commit
  const o = document.createElement('option');
  o.value = t.id; o.textContent = t.label; setEditor.appendChild(o);
});
// Show only the rows + help that fit the selected target: GitHub gets its repo-URL field and note;
// editors/custom get the repo-root field, the placeholders blurb, and (for custom) the custom-URI row.
const syncRows = () => {
  const id = setEditor.value;
  const gh = id === 'github';
  setGhRow.hidden = !gh;
  setGhHelp.hidden = !gh;
  setCustomRow.hidden = id !== 'custom';
  setRootRow.hidden = !needsRoot(id);
  setHelp.hidden = !needsRoot(id);  // the {abspath}/{path}… blurb is editor-only
};
function openSettings(firstUse) {
  setEditor.value = openTargetId();
  setCustom.value = customUri();
  setRoot.value = srcRoot();
  setGhRepo.value = ghRepo();
  syncRows();
  modalErr.hidden = true;
  const ref = (firstUse && pendingSrc) ? cleanPath(pendingSrc.file, pendingSrc.line) + (pendingSrc.line ? ':' + pendingSrc.line : '') : '';
  modalTitle.textContent = firstUse ? 'How should source links open?' : 'Open source links';
  modalIntro.hidden = !firstUse;
  modalIntro.textContent = firstUse
    ? 'First time — choose how to open ' + ref + ' (your editor, or GitHub), then Save. Change it anytime with the ⚙ button.' : '';
  modal.hidden = false;
}
function closeSettings() { modal.hidden = true; pendingSrc = null; }
function saveSettings() {
  const id = setEditor.value;
  const custom = setCustom.value.trim();
  const ghRepoVal = setGhRepo.value.trim();
  if (id === 'custom') {
    if (!custom) { modalErr.textContent = 'Enter a custom URI template.'; modalErr.hidden = false; return; }
    if (!ALLOWED_OPEN_SCHEMES.has(uriScheme(custom))) {
      modalErr.textContent = 'Scheme not allowed — use an editor scheme (vscode://, subl://, …).';
      modalErr.hidden = false; return;
    }
  }
  if (id === 'github' && ghRepoVal && !/^https?:\/\//i.test(ghRepoVal)) {
    modalErr.textContent = 'Enter a full GitHub URL (https://github.com/owner/repo).';
    modalErr.hidden = false; return;
  }
  lsSet(LS.editor, id); lsSet(LS.custom, custom); lsSet(LS.root, setRoot.value.trim());
  lsSet(LS.repo, ghRepoVal); lsSet(LS.ok, '1');
  const n = pendingSrc;
  closeSettings();
  if (n && id !== 'native') doOpenSource(n);   // first-use: continue the open the user asked for
}
setbtn.addEventListener('click', () => openSettings(false));
setEditor.addEventListener('change', syncRows);
setCancel.addEventListener('click', closeSettings);
setSave.addEventListener('click', saveSettings);
modal.addEventListener('click', (e) => { if (e.target === modal) closeSettings(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden) closeSettings(); });

// --- first-run navigation guide -------------------------------------------------
// A one-time overlay teaching click-to-focus / ⌘-click-to-drill, remembered in localStorage so it
// shows once (Esc / backdrop / "Got it" dismiss it). The canvas hint is informational, not a reopener.
const coach = document.getElementById('coach');
const dismissCoach = () => { coach.hidden = true; lsSet(LS.coach, '1'); };
document.getElementById('coachok').addEventListener('click', dismissCoach);
coach.addEventListener('click', (e) => { if (e.target === coach) dismissCoach(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !coach.hidden) dismissCoach(); });
if (lsGet(LS.coach) !== '1') coach.hidden = false;  // first visit -> show the guide once

// --- resizable left column (diagram + info) -------------------------------------
// The left column holds the diagram (top) and the info pane (bottom). #resizer sets the whole
// column's WIDTH (the file browser + code viewer share the rest); #vsplit sets the info pane's
// HEIGHT within the column (the diagram takes what's left). Both persist and clamp; the drag starts
// on a handle (not the svg) so svg-pan-zoom never pans.
const leftcol = document.getElementById('leftcol');
const clampLeftW = (w) => Math.min(Math.max(w, 360), Math.round(window.innerWidth * 0.85));
const savedLeftW = parseInt(lsGet(LS.leftW) || '', 10);
if (savedLeftW) leftcol.style.width = clampLeftW(savedLeftW) + 'px';
const resizer = document.getElementById('resizer');
let resizing = false;
resizer.addEventListener('mousedown', (e) => { e.preventDefault(); resizing = true; document.body.classList.add('resizing'); });
document.addEventListener('mousemove', (e) => { if (resizing) { leftcol.style.width = clampLeftW(e.clientX - leftcol.getBoundingClientRect().left) + 'px'; refitStage(); } });
document.addEventListener('mouseup', () => {
  if (!resizing) return;
  resizing = false; document.body.classList.remove('resizing');
  lsSet(LS.leftW, String(parseInt(leftcol.style.width, 10) || ''));
});

// Vertical split: the info pane's height is the distance from the cursor up to the column's bottom.
const vsplit = document.getElementById('vsplit');
const clampPanelH = (h) => Math.min(Math.max(h, 120), Math.round(window.innerHeight * 0.7));
const savedPanelH = parseInt(lsGet(LS.panelH) || '', 10);
if (savedPanelH) panel.style.height = clampPanelH(savedPanelH) + 'px';
let vresizing = false;
vsplit.addEventListener('mousedown', (e) => { e.preventDefault(); vresizing = true; document.body.classList.add('vresizing'); });
document.addEventListener('mousemove', (e) => { if (vresizing) { panel.style.height = clampPanelH(leftcol.getBoundingClientRect().bottom - e.clientY) + 'px'; resizeStagePreserve(); } });
document.addEventListener('mouseup', () => {
  if (!vresizing) return;
  vresizing = false; document.body.classList.remove('vresizing');
  lsSet(LS.panelH, String(parseInt(panel.style.height, 10) || ''));
});

// --- file browser: build + toggle + resize --------------------------------------
// The pane folds away via the header toggle; both its width and folded state survive reloads. #treeresizer
// sits on the tree's RIGHT edge, so its width is the distance from the tree's own left edge to the cursor.
const tree = document.getElementById('tree');
const clampTreeW = (w) => Math.min(Math.max(w, 180), Math.round(window.innerWidth * 0.5));
const savedTreeW = parseInt(lsGet(LS.treeW) || '', 10);
if (savedTreeW) tree.style.width = clampTreeW(savedTreeW) + 'px';
if (lsGet(LS.treeHidden) === '1') { document.body.classList.add('tree-hidden'); treeToggleBtn.classList.add('off'); }
treeToggleBtn.addEventListener('click', () => {
  const hidden = document.body.classList.toggle('tree-hidden');
  treeToggleBtn.classList.toggle('off', hidden);
  lsSet(LS.treeHidden, hidden ? '1' : '0');
  if (!hidden) setTreePeek(false);  // unfolding the browser for real ends any transient folder peek
  refitStage();  // the stage just got wider/narrower — re-fit the diagram into it
});
let treeResizing = false;
treeResizer.addEventListener('mousedown', (e) => { e.preventDefault(); treeResizing = true; document.body.classList.add('resizing'); });
document.addEventListener('mousemove', (e) => { if (treeResizing) { tree.style.width = clampTreeW(e.clientX - tree.getBoundingClientRect().left) + 'px'; refitStage(); } });
document.addEventListener('mouseup', () => {
  if (!treeResizing) return;
  treeResizing = false; document.body.classList.remove('resizing');
  lsSet(LS.treeW, String(parseInt(tree.style.width, 10) || ''));
});
buildFileTree();
initServerMode();  // probe for `coyodex serve`; on success reveal + wire the file browser and code viewer

buildLegend();
viewsw.querySelectorAll('button').forEach((b) => {
  if (b.dataset.view === 'container' && !HAS_GROUPING) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'domain' && !HAS_DOMAIN) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'hp' && !HAS_HP) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'usecases' && !HAS_USECASES) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'glossary' && !HAS_GLOSSARY) { b.style.display = 'none'; return; }
  b.addEventListener('click', () => go({ kind: b.dataset.view }));
});
navback.addEventListener('click', back);
navfwd.addEventListener('click', fwd);
zoomin.addEventListener('click', () => { if (mainPz) { mainPz.zoomIn(); updateZoomLevel(); } });
zoomout.addEventListener('click', () => { if (mainPz) { mainPz.zoomOut(); updateZoomLevel(); } });
zoomlevel.addEventListener('click', () => { if (mainPz) { mainPz.reset(); updateZoomLevel(); } });  // fit to screen
flowprev.addEventListener('click', () => flowStepBy(-1));  // step player: previous / next flow action
flownext.addEventListener('click', () => flowStepBy(1));
if (HAS_DIFF) {
  // Same view, different overlay — capture the live pan/zoom + selection first so the toggle keeps
  // them (render() restores from the state) instead of resetting to a fresh, unselected fit.
  toggle.addEventListener('click', () => { captureViewState(); mode = mode === 'diff' ? 'base' : 'diff'; render(); });
}
// Land on the Subsystems view for a diff render (the change-impact overlay lives there); otherwise the
// Happy Path — the behavioural spine, lead-with-behaviour — falling back to Subsystems, then the
// Dependencies (context) view, when a map has no Happy Path.
go({ kind: (HAS_DIFF && HAS_GROUPING) ? 'container' : (HAS_HP ? 'hp' : (HAS_GROUPING ? 'container' : 'context')) });
