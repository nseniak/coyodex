// `mermaid` is the global from the SRI-pinned UMD <script> in <head>.

const GRAPH = __GRAPH_JSON__;
const MERMAID_BASE = __MERMAID_BASE__;
const MERMAID_DIFF = __MERMAID_DIFF__;
const MERMAID_CONTEXT = __MERMAID_CONTEXT__;
const MERMAID_CONTAINER = __MERMAID_CONTAINER__;
const MERMAID_BY_SUB = __MERMAID_BY_SUB__;        // subsystem neighbourhood: sid -> sub-diagram
const MERMAID_EDGE_CARD = __MERMAID_EDGE_CARD__;  // edge pair: 'A>B' -> two-subsystem sub-diagram
const CONTAINER_EDGES = __CONTAINER_EDGES__;      // inter-subsystem arrow 'A>B' -> [crossing component edges]
const MERMAID_DOMAIN = __MERMAID_DOMAIN__;        // T5 domain model as a classDiagram (flat, ungrouped)
const MERMAID_DOMAIN_CONTAINER = __MERMAID_DOMAIN_CONTAINER__;  // Subdomains overview (flowchart of SD boxes)
const MERMAID_DOMAIN_SUB = __MERMAID_DOMAIN_SUB__;             // per-subdomain card: SD-id -> classDiagram
const MERMAID_DOMAIN_EDGE_CARD = __MERMAID_DOMAIN_EDGE_CARD__; // subdomain edge pair: 'A>B' -> two-subdomain classDiagram
const MERMAID_BRIDGE_CARD = __MERMAID_BRIDGE_CARD__;           // bridge pair 'S>SD' -> subsystem×subdomain classDiagram
const DOMAIN_CONTAINER_EDGES = __DOMAIN_CONTAINER_EDGES__;     // inter-subdomain arrow 'A>B' -> [crossing E->E relations]
const MERMAID_GP = __MERMAID_GP__;                // Golden Path (Level 1): use cases as a black-box sequence
const FLOWS_MM = __FLOWS_MM__;                    // T6 use-case flows: uc-id -> sequenceDiagram (the inside view)
const FLOWS_NARR = __FLOWS_NARR__;                // uc-id -> [{n,src,srcId,dst,dstId,verb,why,note}] readable steps
const GP_ACTORS = __GP_ACTORS__;                  // Golden-Path lifelines: [{aid,name,kind,wants,steps,stepIdx}]
const ELEMENT_TINT = __ELEMENT_TINT__;            // per-kind {fill,stroke} for views Mermaid renders kind-agnostically (cluster frames, flow participant boxes)
const MERMAID_LIBS = __MERMAID_LIBS__;            // Context "Libraries" drill: System + the folded in-process deps
const FOLDED_LIBS = __FOLDED_LIBS__;              // [{id,name,type}] folded out of Context into the Libraries box
const LIBS_ID = 'LIBS';                           // synthetic id of that collapsed box (matches gen_viewer.LIBS_ID)
const HAS_GROUPING = __HAS_GROUPING__;
const HAS_DOMAIN = __HAS_DOMAIN__;
const HAS_SUBDOMAINS = __HAS_SUBDOMAINS__;  // domain model grouped into subdomains -> Domain view leads with the overview
const HAS_GP = __HAS_GP__;
const CONTEXT_EDGES = __CONTEXT_EDGES__;
const HAS_DIFF = __HAS_DIFF__;
const META = __META__;
const DIFF_STATE = __DIFF_STATE__;
const FILE_TREE = __FILE_TREE__;  // mapped repo's file tree + map-coverage overlay (null when no walkable repo)
const SVGNS = 'http://www.w3.org/2000/svg';
const R = 10;
const BADGE = { added: ['#1a7f37', '+', 'new'], modified: ['#9a6700', '✎', 'modified'],
                deleted: ['#cf222e', '×', 'deleted'], rippled: ['#d97706', '≈', 'ripples to'] };
const HILITE = 'drop-shadow(0 0 4px #2563eb) drop-shadow(0 0 2px #2563eb)';  // selection glow (nodes + edge labels)
const HOVER = 'drop-shadow(0 0 3px #60a5fa)';  // softer hover glow: signals "clickable" without competing with HILITE
const GP_SEL = 'drop-shadow(0 0 4px #3b82f6)';  // Golden-Path selection: just a touch stronger than HOVER (not the heavy HILITE)
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
const drillhint = document.getElementById('drillhint');
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

// Golden Path step lookup 'GP1' -> step record (id, title, uc, why). The step IS a use case; its
// detailed actions live in that use case's T6 flow (FLOWS_MM / FLOWS_NARR), opened when the step drills.
const GP_BY_ID = {};
for (const s of GRAPH.gp || []) GP_BY_ID[s.id] = s;
// Golden Path actor lookups: by participant id (GPA0) and by the step it drives (GP1 -> actor record).
const GP_ACTOR_BY_AID = {};
for (const a of GP_ACTORS) GP_ACTOR_BY_AID[a.aid] = a;
const GP_ACTOR_OF_STEP = {};
for (const a of GP_ACTORS) for (const st of a.steps) GP_ACTOR_OF_STEP[st.id] = a;
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

// --- scene ----------------------------------------------------------------------
// A "scene" wraps the diagram currently shown: its root, the bound node/edge elements, the active
// selection, and what the side panel shows when nothing is selected. There's one scene at a time;
// it's rebuilt on every render. Focus/select/reset all operate on it.
let mainScene = null;

function makeScene(root, defaultPanel) {
  // dimEls: a flat list of extra focusable elements (the Golden Path's actor figures, lifelines and
  // message text/lines) that the standard node/edge focus model doesn't cover — dimmed/restored together.
  // selectors: selectedKey -> a zero-arg closure that re-applies that selection (panel + glow + focus),
  //   registered at bind time so back/forward can restore the element that was selected in this view.
  return { root, nodeEls: {}, edgeEls: [], dimEls: [], gpLit: new Set(), selectedKey: null, selectors: {}, clearHighlight: null, defaultPanel };
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
function paintImportant(el, props) {
  for (const k in props) el.style.setProperty(k, props[k], 'important');
}
// Inject `action`'s icon (circle + glyph) into `el`'s own top-left corner, in `el`'s local coordinate
// space (getBBox), so it rides along with whatever transform Mermaid gave the node/cluster group.
function addActionIcon(el, id, action) {
  let bbox; try { bbox = el.getBBox(); } catch (_) { return; }
  const paint = ICON_PAINT[action.kind];
  const icon = document.createElementNS(SVGNS, 'g');
  icon.setAttribute('class', 'action-icon ' + (action.kind === 'drill' ? 'is-drill' : 'is-open'));
  // The anchor point in DIAGRAM units, kept around so rescaleActionIcons can recompute the transform
  // (translate + a counter-zoom scale) on every zoom change without re-measuring the box.
  icon._anchor = { x: bbox.x, y: bbox.y };
  icon.setAttribute('transform', `translate(${bbox.x},${bbox.y})`);
  // A container's own box sits exactly where the icon is anchored (its top-left corner) — with a
  // dashed border (see gen_viewer.py _CONTAINER_BORDER), that border's dashes run directly behind/
  // through the badge at that corner, visually merging with the badge's own thin ring and making it
  // read as dashed too even though its own stroke is solid (confirmed: moving the icon away from the
  // corner alone made it render cleanly). A borderless "halo" plate slightly bigger than the badge,
  // painted first (underneath), gives the badge a clean, opaque area to sit on regardless of what's
  // behind it — the common fix for any icon badge placed over a busy background.
  const halo = document.createElementNS(SVGNS, 'circle');
  halo.setAttribute('r', '16.5');
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
  el.appendChild(icon);
  ACTION_ICONS[id] = icon;
}
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
  for (const nid in scene.nodeEls) scene.nodeEls[nid].style.opacity = '';
  for (const x of scene.edgeEls) { x.path.style.opacity = ''; if (x.label) x.label.style.opacity = ''; }
  for (const el of scene.dimEls) el.style.opacity = '';
}
function resetScene(scene) {  // clear selection + focus, restore the scene's default panel
  clearFocus(scene);
  sceneSelect(scene, null);
  scene.selectedKey = null;
  scene.defaultPanel();
  highlightTreePath(null);  // drop the file-browser highlight too
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
// Leaves (components under a subsystem, entities under a subdomain) anywhere beneath `id`, any depth —
// the size hint shown next to a collapsed child group in the panel. Seen-set guards a malformed cycle.
function descendantLeafCount(id, parentKind) {
  const leaf = parentKind === 'subsystem' ? 'component' : 'entity';
  let c = 0;
  for (const k in GRAPH.nodes) {
    if (GRAPH.nodes[k].kind !== leaf) continue;
    let cur = GRAPH.nodes[k].parent; const seen = new Set();
    while (cur && !seen.has(cur)) { if (cur === id) { c += 1; break; } seen.add(cur); cur = GRAPH.nodes[cur] && GRAPH.nodes[cur].parent; }
  }
  return c;
}
// A group node's panel lists its IMMEDIATE children (child groups first, each tagged with how many
// leaves nest under it, then direct leaves) — so the panel mirrors the card: one level down, with a
// size hint for what a child box would expand into. Empty for a non-group or a leaf group.
function groupMembersHtml(id) {
  const n = GRAPH.nodes[id];
  if (!n || (n.kind !== 'subsystem' && n.kind !== 'subdomain')) return '';
  const kids = Object.keys(GRAPH.nodes).filter((k) => GRAPH.nodes[k].parent === id);
  if (!kids.length) return '';
  const order = (k) => (GRAPH.nodes[k].kind === n.kind ? 0 : 1);  // child groups before leaves
  kids.sort((a, b) => order(a) - order(b) || (GRAPH.nodes[a].name || '').localeCompare(GRAPH.nodes[b].name || ''));
  const items = kids.map((k) => {
    const kn = GRAPH.nodes[k];
    const tag = kn.kind === n.kind ? ` <span class="muted">(${descendantLeafCount(k, n.kind)})</span>` : '';
    return `<dd>• ${esc(kn.name)}${tag}</dd>`;
  }).join('');
  return '<dt>Contains</dt>' + items;
}
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
// A node's full detail as an HTML string (title + badges + fields + source link) — no DOM writes, no
// handler wiring. Shared by showNode (one node fills the whole panel) and showElementsList (several
// nodes stack in one panel, each block needing this same markup).
function nodeDetailHtml(id) {
  const n = GRAPH.nodes[id];
  if (!n) return '';
  const chg = n.change ? `<span class="badge ${n.change}">${n.change}</span>` : '';
  const rows = Object.entries(n.fields || {})
    // a subsystem's / subdomain's first field IS its name (already in the title) — don't repeat it
    .filter(([k]) => !((n.kind === 'subsystem' && k.toLowerCase() === 'subsystem')
                       || (n.kind === 'subdomain' && k.toLowerCase() === 'subdomain')))
    .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${mdInline(v)}</dd>`).join('');
  // entity attributes (T5 domain cards): `type name` + any markers (PK/FK/unique/…)
  const attrs = (n.attrs && n.attrs.length)
    ? '<dt>Fields</dt><dd>' + n.attrs.map((a) => {
        const ty = (a.type && GRAPH.nodes[a.type]) ? GRAPH.nodes[a.type].name : a.type;  // embedded entity id -> name
        return esc(((ty ? ty + ' ' : '') + (a.name || '') + (a.markers ? '  ·  ' + a.markers : '')).trim());
      }).join('<br>') + '</dd>'
    : '';
  // Any node with a local source ref — a component/entity FILE or a subsystem/subdomain entry DIRECTORY —
  // gets a clickable link that opens it exactly the way the diagram's ⌘-click does (editor or GitHub). An
  // off-repo URL (e.g. a dep pointing at a website) stays plain text, since openSource can't resolve it.
  const ref = n.file ? esc(cleanPath(n.file, n.line)) + (n.line ? ':' + n.line : '') : '';
  const src = !n.file ? ''
    : localRef(n.file) ? `<button type="button" class="src srclink" title="Open in editor or on GitHub">${ref}</button>`
    : `<div class="src">${ref}</div>`;
  return `<h2>${esc(n.name)}</h2>`
    + `<div class="badges"><span class="badge kind">${n.kind}</span>${chg}</div>`
    + `<dl>${rows}${attrs}${usedInHtml(id)}${groupMembersHtml(id)}</dl>${src}`;
}
// Wire the interactive bits inside a just-written detail block: the source-open button + any
// use-case-flow refs. `root` is the panel itself (single-node case) or one `.pblock` div (list case).
function bindNodeDetailHandlers(root, id) {
  const n = GRAPH.nodes[id];
  const sl = root.querySelector('.srclink');
  if (sl) sl.addEventListener('click', () => openSource(n));
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
  // The edge's `where` source ref — clickable (opens in editor / on GitHub) when it's an in-repo path,
  // exactly like a node's source link; plain text for an off-repo URL. (Was a non-clickable div.)
  const wn = e.where ? whereNode(e.where) : null;
  const srcHtml = !wn ? ''
    : (localRef(wn.file)
        ? '<button type="button" class="src srclink" title="Open in editor or on GitHub">'
          + esc(cleanPath(wn.file, wn.line) + (wn.line ? ':' + wn.line : '')) + '</button>'
        : '<div class="src">' + esc(e.where) + '</div>');
  panel.innerHTML = '<h2>' + esc(nm(e.src)) + ' → ' + esc(nm(e.dst)) + '</h2>'
    + '<div class="badges"><span class="badge edge">' + esc(e.verb) + '</span>' + kindBadge + '</div>'
    + '<dl>'
    + (e.why ? '<dt>Why</dt><dd>' + mdInline(e.why) + '</dd>' : '')
    + card
    + implRow
    + '</dl>'
    + srcHtml;
  const sl = panel.querySelector('.srclink');
  if (sl) sl.addEventListener('click', () => openSource(wn));
  // Mirror this edge's own anchor into the file browser too, same as a node selection — clearing
  // whatever was highlighted before when this edge has none of its own (an off-repo `where`, or none).
  highlightTreePath(refTreePath(wn && wn.file, wn && wn.line));
}

// Context-edge panel: actor→system shows the role's wants; system→dep shows what it's used for
// and the component edges (with their Why) that realize the dependency.
function showContextEdge(ce) {
  if (ce.type === 'libs') { showLibsFold(); return; }  // SYS→Libraries arrow: same roster panel as the box
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

// The collapsed "Libraries" box: a roster of the in-process deps (frameworks + libraries) folded out
// of the C4 Context view, since they are an implementation concern, not a system the project talks to.
// At-a-glance only — drilling the box is where each one selects to its own details.
function showLibsFold() {
  const items = FOLDED_LIBS.map((d) =>
    '<dd>• ' + esc(d.name) + (d.type ? ' <span class="muted">— ' + esc(d.type) + '</span>' : '') + '</dd>').join('');
  panel.innerHTML = '<h2>Libraries</h2>'
    + '<div class="badges"><span class="badge kind">' + FOLDED_LIBS.length + ' in-process</span></div>'
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
    + (purpose ? '<dl><dt>Purpose</dt><dd>' + mdInline(purpose) + '</dd></dl>' : '');
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

// --- Golden Path + use-case flow panels -----------------------------------------
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
// The use-case flow panel — shared by the Golden-Path step drill-down and the use-case view: the use
// case (name + driving actor) + the numbered narrative (the readable twin of the sequence diagram drawn
// at this altitude); each step's element links locate that element in its home view.
function showFlowPanel(uc, title, why) {
  const ucNode = uc ? GRAPH.nodes[uc] : null;
  const ucName = ucNode ? ucNode.name : (uc || '');
  const f = (ucNode && ucNode.fields) || {};
  const actor = f.Actor || f.actor || '';
  const narr = flowNarrativeHtml(uc);
  panel.innerHTML = '<h2>' + esc(title || ucName) + '</h2>'
    + '<div class="badges">' + (ucName ? '<span class="badge kind">' + esc(ucName) + '</span>' : '')
      + (actor ? '<span class="badge edge">' + esc(actor) + '</span>' : '') + '</div>'
    + (why ? '<dl><dt>Why here</dt><dd>' + mdInline(why) + '</dd></dl>' : '')
    + (narr || '<p class="empty">No T6 flow recorded for this use case.</p>');
  // Each step's element links locate that element in its home view; there is no flat full-map view to
  // spotlight the whole flow on, so the "Locate in full map" link is gone with the Components tab.
  bindFlowRefs();
}
// A Golden Path step opens its use case's flow (the step IS that use case). Title = the step title.
function showGPStep(gpId) {
  const s = GP_BY_ID[gpId];
  if (!s) { panel.innerHTML = EMPTY_PANEL; return; }
  showFlowPanel(s.uc, s.title || s.id, s.why);
}
// The use-case view default panel (reached directly, not via a Golden Path position).
function showUseCase(uc) {
  showFlowPanel(uc, GRAPH.nodes[uc] ? GRAPH.nodes[uc].name : uc, '');
}
// The flow views (gpstep / usecase) are sequence diagrams — wire them like every other diagram, using
// the same sequence-diagram focus machinery the Golden Path uses (gpHighlight/gpFocus over element
// sets, since a participant is split across top box / label / lifeline / bottom mirror). Element
// participants select (focus to their messages + the other ends) / ⌘-open their source (component &
// entity leaves) / tooltip like nodes; message arrows select (the backbone edge, or the actor step) / focus / tooltip
// like edges; the role actor gets a meaning tooltip. message[i] <-> FLOWS_NARR[uc][i] (gen_flow_mermaid
// emits one message per ok step, in the order flow_narrative lists them).
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

  // messages: text[i] + arrow line[i] (data-id "i<idx>") pair with steps[i] — same pairing as bindGP.
  const texts = [...root.querySelectorAll('text.messageText')];
  const lineByIdx = {};
  root.querySelectorAll('.messageLine0, .messageLine1').forEach((ln) => {
    const m = (ln.getAttribute('data-id') || '').match(/^i(\d+)$/);
    if (m) lineByIdx[+m[1]] = ln;
  });
  const msgEls = steps.map((_, i) => [texts[i], lineByIdx[i]].filter(Boolean));
  for (const els of msgEls) for (const el of els) scene.dimEls.push(el);

  // element participants: select (focus to its messages + their other ends) / ⌘-drill to home / tooltip.
  for (const id of Object.keys(partsById)) {
    const parts = partsById[id], selKey = 'node:' + id;
    const myMsg = steps.map((st, i) => (st.srcId === id || st.dstId === id) ? i : -1).filter((i) => i >= 0);
    const select = () => {
      scene.selectedKey = selKey;
      showNode(id);
      const keep = new Set(parts);
      for (const i of myMsg) {
        for (const el of msgEls[i]) keep.add(el);
        for (const nb of [steps[i].srcId, steps[i].dstId]) for (const el of (partsById[nb] || [])) keep.add(el);
      }
      sceneSelect(scene, () => gpHighlight(scene, parts));
      gpFocus(scene, keep);
    };
    scene.selectors[selKey] = select;  // so back/forward can restore this participant selection
    const on = () => { if (scene.selectedKey !== selKey) for (const el of parts) el.style.filter = HOVER; };
    const off = () => { if (scene.selectedKey !== selKey) for (const el of parts) el.style.filter = gpRestFilter(scene, el); };
    for (const el of parts) {
      el.style.cursor = 'pointer';
      markOpenSrc(el, id);  // </> cursor on a component/entity leaf with a source ref, like the other diagrams
      el.addEventListener('mouseenter', on);
      el.addEventListener('mouseleave', off);
      attachTip(el, () => tipNodeHtml(id), () => actionTipNode(id));  // ⌘-hover shows the open-source action
      el.addEventListener('click', (e) => {
        if (isDrag(e)) return;
        e.stopPropagation();
        if (openSrcClick(id, e)) return;  // ⌘-click opens source (component/entity), consistent with the rest
        select();
      });
    }
  }

  // role actor: a meaning tooltip (what the role wants). The figure isn't a graph node — no focus/drill.
  const wantsByName = {};
  for (const r of GRAPH.roles || []) wantsByName[(r.name || '').trim().toLowerCase()] = r.wants;
  const roleNames = new Set();
  for (const st of steps) if (!st.srcId && st.src) roleNames.add(st.src.toLowerCase());
  for (const t of root.querySelectorAll('text.actor-man')) {
    const nm = (t.textContent || '').trim().toLowerCase();
    if (roleNames.has(nm) && wantsByName[nm]) attachTip(t, () => '<div class="tm">' + mdInline(wantsByName[nm]) + '</div>');
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
      if (edge) showEdge(edge); else showFlowStep(uc, i);
      const keep = new Set(els);
      for (const end of [st.srcId, st.dstId]) for (const el of (partsById[end] || [])) keep.add(el);
      sceneSelect(scene, () => gpHighlight(scene, els));
      gpFocus(scene, keep);
    };
    scene.selectors[selKey] = doSelect;  // so back/forward can restore this flow-step selection
    const onClick = (ev) => {
      if (isDrag(ev)) return;
      ev.stopPropagation();
      doSelect();
    };
    const on = () => { if (scene.selectedKey !== selKey) for (const el of els) el.style.filter = HOVER; };
    const off = () => { if (scene.selectedKey !== selKey) for (const el of els) el.style.filter = gpRestFilter(scene, el); };
    if (line) attachEdgeHandlers(line, text, onClick, on, off, () => flowStepTip(st), false);
    else { text.style.cursor = 'pointer'; text.style.setProperty('pointer-events', 'all', 'important'); text.addEventListener('click', onClick); text.addEventListener('mouseenter', on); text.addEventListener('mouseleave', off); attachTip(text, () => flowStepTip(st)); }
  });
}
// A flow message's side panel for an ACTOR step (an element↔element step shows its backbone edge instead).
function showFlowStep(uc, i) {
  const st = (FLOWS_NARR[uc] || [])[i];
  if (!st) { panel.innerHTML = EMPTY_PANEL; return; }
  const end = (label, id) => id ? '<a href="#" class="flowref" data-id="' + esc(id) + '">' + esc(label) + '</a>' : esc(label);
  panel.innerHTML = '<h2>' + end(st.src, st.srcId) + ' &rarr; ' + end(st.dst, st.dstId) + '</h2>'
    + '<div class="badges"><span class="badge edge">' + esc(st.verb) + '</span></div>'
    + '<dl>' + (st.why ? '<dt>Why</dt><dd>' + mdInline(st.why) + '</dd>' : '')
    + (st.note ? '<dt>Note</dt><dd>' + mdInline(st.note) + '</dd>' : '') + '</dl>';
  bindFlowRefs();
}
// A flow message's hover tooltip: the explanation only (why for an element step, else a note). The verb
// is already drawn on the arrow, so — like every other edge tooltip — show only what isn't on screen.
function flowStepTip(st) {
  const m = st.why || st.note || '';
  return m ? '<div class="tm">' + mdInline(m) + '</div>' : '';
}
// One actor's card: its kind, what its role wants (the explanation), and the Golden Path steps it drives.
function showGPActor(a) {
  const kindBadge = a.kind ? '<span class="badge kind">' + esc(a.kind) + '</span>' : '';
  const drives = (a.steps || []).map((st) =>
    '<dd>' + esc(st.title || st.id) + '</dd>').join('');
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
// Hover the collapsed Libraries box -> the names it folds (capped), so you can read them without drilling.
const TIP_LIBS_CAP = 16;
function tipLibsHtml() {
  if (!FOLDED_LIBS.length) return '<div class="tn">no libraries</div>';
  const names = FOLDED_LIBS.map((d) => d.name);
  const shown = names.slice(0, TIP_LIBS_CAP);
  const more = names.length > TIP_LIBS_CAP
    ? '<div class="tn">+' + (names.length - TIP_LIBS_CAP) + ' more…</div>' : '';
  return '<ul class="tl">' + shown.map((nm) => '<li>' + esc(nm) + '</li>').join('') + '</ul>' + more;
}
function tipNodeHtml(id) {
  if (id === LIBS_ID) return tipLibsHtml();  // the synthetic fold box has no fields — list its members
  const n = GRAPH.nodes[id];
  if (!n) return '';
  const meaning = meaningOf(n);
  // The box you're hovering already prints its name, and its kind reads from the shape/colour, so a
  // name header + kind tag only restate what's on screen — show just the explanatory text. No meaning
  // recorded -> no tooltip at all (don't pop a bare "no description" placeholder).
  return meaning ? '<div class="tm">' + mdInline(meaning) + '</div>' : '';
}
function tipEdgeHtml(e) {
  // Tooltips show only the explanation — you're hovering the arrow, so its endpoints (and, for most
  // edges, its verb) are already on screen. Context edges explain via wants/usedFor (the Libraries fold
  // arrow has neither); component edges via why. With nothing to explain, show no tooltip at all rather
  // than a bare placeholder. DOMAIN relations are the deliberate exception: the verb/kind is their
  // content and is NOT drawn on the arrow (the label is the backing field name) — so keep that card.
  if (e.type === 'actor' || e.type === 'dep' || e.type === 'libs') {
    const meaning = e.type === 'actor' ? e.wants : e.usedFor;  // libs has neither -> no tooltip
    return meaning ? '<div class="tm">' + mdInline(meaning) + '</div>' : '';
  }
  if (e.kind) {  // domain relation — keep endpoints + verb (the relation's content, not on the arrow)
    const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
    return '<div class="tt">' + esc(nm(e.src)) + ' → ' + esc(nm(e.dst)) + '</div>'
      + '<div class="tk">' + esc(e.verb) + '</div>'
      + (e.why ? '<div class="tm">' + mdInline(e.why) + '</div>' : '');
  }
  // component edge: endpoints + verb are already on the diagram — show only the why (none -> no tooltip).
  return e.why ? '<div class="tm">' + mdInline(e.why) + '</div>' : '';
}
// Hover an inter-subsystem arrow (Subsystems view) -> just the explanation (Why) of every
// component→component edge it aggregates. You're already on that arrow, so no subsystem/component
// names: a single link reads as plain text, several as a bullet list. Capped so a busy pair stays legible.
const TIP_EDGE_CAP = 14;
function tipContainerEdgeHtml(a, b) {
  const list = CONTAINER_EDGES[a + '>' + b] || [];
  const whys = list.map((r) => r.why).filter((w) => w && String(w).trim());
  if (!whys.length) return '';  // nothing recorded -> no tooltip
  const shown = whys.slice(0, TIP_EDGE_CAP);
  const more = whys.length > TIP_EDGE_CAP
    ? '<div class="tn">+' + (whys.length - TIP_EDGE_CAP) + ' more…</div>' : '';
  if (shown.length === 1) return '<div class="tm">' + mdInline(shown[0]) + '</div>' + more;
  return '<ul class="tl">' + shown.map((w) => '<li>' + mdInline(w) + '</li>').join('') + '</ul>' + more;
}
// Hover an inter-subdomain arrow (Domain overview) -> the crossing entity→entity relations (from → to ·
// verb). The domain analog of tipContainerEdgeHtml; capped so a busy pair stays legible.
function tipDomainContainerEdgeHtml(a, b) {
  const list = DOMAIN_CONTAINER_EDGES[a + '>' + b] || [];
  if (!list.length) return '';  // nothing recorded -> no tooltip
  const shown = list.slice(0, TIP_EDGE_CAP);
  const more = list.length > TIP_EDGE_CAP ? '<div class="tn">+' + (list.length - TIP_EDGE_CAP) + ' more…</div>' : '';
  return '<ul class="tl">' + shown.map((r) =>
    '<li>' + esc(r.srcName) + ' → ' + esc(r.dstName) + ' · ' + esc(r.verb) + '</li>').join('') + '</ul>' + more;
}
function tipGPHtml(gpId) {  // hover a GP step (message) -> its use case's trigger→outcome (the explanation)
  const s = GP_BY_ID[gpId];
  if (!s) return '';
  const f = (s.uc && GRAPH.nodes[s.uc] && GRAPH.nodes[s.uc].fields) || {};
  let txt = '';
  for (const k in f) { const kl = k.toLowerCase(); if (kl.includes('outcome') || kl.includes('trigger')) { txt = String(f[k]); break; } }
  return txt ? '<div class="tm">' + mdInline(txt) + '</div>' : '';  // nothing recorded -> no tooltip
}
function tipGPActorHtml(a) {  // hover an actor / its lifeline -> just what its role wants (the explanation)
  return a && a.wants ? '<div class="tm">' + mdInline(a.wants) + '</div>' : '';  // no wants -> no tooltip
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
// The element currently under the cursor and how to describe it: `htmlFn` is the meaning preview,
// `actionFn` (optional) the "what a ⌘-click does here" text. Held so pressing/releasing ⌘ can swap the
// tooltip live, without waiting for a new mouse event (see setCmd).
let hover = null;
function renderHoverTip() {
  if (!hover) return;
  let html = '', action = false;
  if (document.body.classList.contains('cmd') && hover.actionFn) { const a = hover.actionFn(); if (a) { html = a; action = true; } }
  if (!html) html = hover.htmlFn() || '';
  if (html) { tip.innerHTML = html; tip.classList.toggle('action', action); tip.classList.add('on'); moveTip(hover.x, hover.y); }
  else hideTip();
}
// Wire an element to preview `htmlFn()` while hovered (and, while ⌘ is held, `actionFn()` instead).
function attachTip(el, htmlFn, actionFn) {
  el.addEventListener('mouseenter', (ev) => { hover = { htmlFn, actionFn: actionFn || null, x: ev.clientX, y: ev.clientY }; renderHoverTip(); });
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
function actionTipGP(gpId) {
  const s = GP_BY_ID[gpId];
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
  const m = (el.id || '').match(/(?:^|-)((?:UC|GP|SD|C|D|E|S)\d+)(?:-|$)/);  // SD before S: a subdomain id is not a subsystem
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
// centering). Measures el/stage BEFORE any mutation: svg-pan-zoom's zoom() only updates its internal
// state synchronously — the CTM it actually paints is applied on the NEXT animation frame (see
// `updateCTMOnNextFrame` in the vendored lib) — so a getBoundingClientRect() taken right after would
// still read the OLD, pre-zoom geometry. zoomAtPoint anchors on the SVG's own center, which
// #diagram/#stage's CSS (width/height:100%, no padding) makes exactly `stageRect`'s center — so the
// post-zoom position is derived analytically (every point scales toward/away from that shared center
// by `scale`) instead of re-measured.
function applyZoomAndCenter(el, scale) {
  const stageRect = stage.getBoundingClientRect();
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
    attachTip(el, () => tipNodeHtml(id), () => actionTipNode(id));  // hover -> meaning; ⌘ -> the action
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

// Give an edge's visible path a wide transparent hit-path + make its label clickable.
// `tipHtml` (optional) wires a hover meaning-preview on the same hit-area + label.
function attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff, tipHtml, drillable, actionFn) {
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
  if (tipHtml) { attachTip(hit, tipHtml, actionFn); if (label) attachTip(label, tipHtml, actionFn); }
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
  attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff, opts.tipFn || (() => tipEdgeHtml(e)), !!opts.onDrill, opts.actionFn);
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
    { onDrill: () => go({ kind: 'edge', a, b }), tipFn: () => tipContainerEdgeHtml(a, b),
      actionFn: () => actionTipEdge(a, b) });
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

function stateKey(s) {
  return s.kind + (s.sid ? ':' + s.sid : '') + (s.a ? ':' + s.a + '>' + s.b : '')
    + (s.gp ? ':' + s.gp : '') + (s.uc ? ':' + s.uc : '') + (s.sd ? ':' + s.sd : '');
}
function captureViewState() {  // stash the current pan/zoom + selection on the entry we're about to leave
  if (hi < 0 || !history[hi]) return;
  if (mainPz) history[hi].vp = { zoom: mainPz.getZoom(), pan: mainPz.getPan() };
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
    attachTip(el, () => tipNodeHtml(id), () => actionTipNode(id));
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
    { onDrill: () => go({ kind: 'domedge', a, b }), tipFn: () => tipDomainContainerEdgeHtml(a, b),
      actionFn: () => actionTipEdge(a, b) });
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
    attachTip(el, () => tipNodeHtml(id), () => actionTipNode(id));
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
function bindEdgePair() {  // both subsystems framed; arrows are component edges
  bindNodes(mainScene, (id, el, e) => selectNodeFromCanvas(el, id, e));
  bindEdges(mainScene, resolveComponentEdge);
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
    attachTip(el, () => tipNodeHtml(id), () => actionTipNode(id));  // hover -> meaning; ⌘ -> the action
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
// Select an actor: its figure + lifeline + every step it drives glow; the rest dims.
function selectGPActor(scene, a) {
  const selKey = 'gpactor:' + a.aid;
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
    scene.selectors[selKey] = () => selectGPStep(scene, i, gpId, aidOfStep[i]);  // back/forward restore
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
      attachTip(el, () => tipGPHtml(gpId), () => actionTipGP(gpId));
    }
  });

  // actors: click the figure or anywhere on the lifeline to select the actor (no drill).
  for (const a of GP_ACTORS) {
    const rec = scene.gpActor[a.aid], selKey = 'gpactor:' + a.aid;
    scene.selectors[selKey] = () => selectGPActor(scene, a);  // back/forward restore
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
  // Domain: the Subdomains overview when grouped (drill a subdomain for its classes), else the
  // flat whole-model classDiagram.
  if (s.kind === 'domain') return HAS_SUBDOMAINS ? MERMAID_DOMAIN_CONTAINER : MERMAID_DOMAIN;
  if (s.kind === 'domsub') return MERMAID_DOMAIN_SUB[s.sd];
  if (s.kind === 'domedge') return MERMAID_DOMAIN_EDGE_CARD[s.a + '>' + s.b];
  if (s.kind === 'bridge') return MERMAID_BRIDGE_CARD[s.sid + '>' + s.sd];
  if (s.kind === 'gp') return MERMAID_GP;
  if (s.kind === 'gpstep') return FLOWS_MM[(GP_BY_ID[s.gp] || {}).uc] || EMPTY_FLOW_MM;  // the step's use case's flow
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
  else if (s.kind === 'gpstep') showGPStep(s.gp);
  else if (s.kind === 'usecase') showUseCase(s.uc);
  else if (s.kind === 'libs') showLibsFold();
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
  else if (s.kind === 'edge') bindEdgePair();
  else if (s.kind === 'domain') (HAS_SUBDOMAINS ? bindDomainContainer : bindDomain)();
  else if (s.kind === 'domsub') bindDomainSub(s.sd);  // neighbourhood: framed entities + collapsed neighbour boxes + cross arrows
  else if (s.kind === 'domedge') { bindDomain(); bindFrameDrill(mainScene); }  // both subdomains framed; ⌘-click a frame -> its card
  else if (s.kind === 'bridge') { bindDomain(); bindFrameDrill(mainScene); }  // subsystem×subdomain; components+entities+C→E edges, frames drill
  else if (s.kind === 'gp') bindGP();
  else if (s.kind === 'gpstep') bindFlow((GP_BY_ID[s.gp] || {}).uc);  // the step opens its use case's flow
  else if (s.kind === 'usecase') bindFlow(s.uc);
  else if (s.kind === 'libs') bindLibs();
  else bindComponent();
}
function topView(kind) {  // which top-level button a state lives under (container/subsystem/edge → Subsystems)
  if (kind === 'context' || kind === 'component' || kind === 'domain') return kind;
  if (kind === 'domsub' || kind === 'domedge') return 'domain';  // subdomain card + edge pair live under the Domain button
  if (kind === 'bridge') return 'container';  // a structure↔domain bridge card is anchored on its subsystem
  if (kind === 'gp' || kind === 'gpstep' || kind === 'usecase') return 'gp';
  if (kind === 'libs') return 'context';  // the Libraries fold drills out of Context
  return 'container';
}
function gpTitle(gp) { const s = GP_BY_ID[gp]; return s ? (s.title || s.id) : gp; }  // breadcrumb crumb: title, not the GPn id
function stateTitle(s) {
  if (s.kind === 'context') return 'Context';
  if (s.kind === 'container') return 'Subsystems';
  if (s.kind === 'component') return 'Components';
  if (s.kind === 'domain') return 'Entities';  // user-facing label for the `domain` view (the tab)
  if (s.kind === 'domsub') return (GRAPH.nodes[s.sd] ? GRAPH.nodes[s.sd].name : s.sd);
  if (s.kind === 'domedge') { const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id); return nm(s.a) + ' → ' + nm(s.b); }
  if (s.kind === 'bridge') { const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id); return nm(s.sid) + ' → ' + nm(s.sd); }
  if (s.kind === 'gp') return 'Golden Path';
  if (s.kind === 'gpstep') return gpTitle(s.gp);
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
  // So sibling tabs read uniformly — Subsystems, Components, Domain, Golden Path, Context are each one
  // crumb at the top, and ancestry (Subsystems › Auth › … , Context › Libraries) appears only once you
  // zoom in; a nested subsystem/subdomain appends one crumb PER level via groupChain.
  if (s.kind === 'domain') return [{ kind: 'domain' }];
  if (s.kind === 'domsub') return [{ kind: 'domain' }, ...groupChain('domsub', 'sd', s.sd)];  // subdomain card (full nesting path) under Domain
  if (s.kind === 'domedge') return [{ kind: 'domain' }, { kind: 'domedge', a: s.a, b: s.b }];  // subdomain pair beside them
  if (s.kind === 'bridge') return [{ kind: 'container' }, { kind: 'bridge', sid: s.sid, sd: s.sd }];  // S×SD bridge under Subsystems
  if (s.kind === 'gp') return [{ kind: 'gp' }];
  if (s.kind === 'gpstep') return [{ kind: 'gp' }, { kind: 'gpstep', gp: s.gp }];  // step under the Golden Path
  if (s.kind === 'usecase') return [{ kind: 'gp' }, { kind: 'usecase', uc: s.uc }];  // a use case's flow, under the Golden Path
  if (s.kind === 'libs') return [{ kind: 'context' }, { kind: 'libs' }];  // the fold is a drill-down out of Context
  if (s.kind === 'context') return [{ kind: 'context' }];
  if (s.kind === 'component') return [{ kind: 'component' }];
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
  // One shared hint pill across every view: a plain click focuses (dims to the clicked element's own
  // links + connected boxes); a double-click, its corner icon, or a ⌘-click all drill down — into the
  // next altitude where one exists, or to the source at a leaf (Components / Domain entities / a GP
  // step). All three are "drilling in", so the pill reads the same everywhere instead of splitting
  // "drill down" vs "open source" (⌘-click stays as a shortcut for anyone who already learned it).
  drillhint.hidden = false;
  drillhint.innerHTML = 'Click to focus · double-click (or its icon) to drill in';
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

// Icons are drawn in DIAGRAM units, so without this they'd shrink right along with the boxes as the
// view zooms out — at a crowded overview (many boxes fitted on screen) that makes them a near-invisible,
// near-unclickable speck. Counter-scaled against the current pan-zoom level (like a map pin that stays
// the same size no matter how far out you zoom the map) so they read as a constant on-screen size at
// any zoom. `_anchor` (set in addActionIcon) is the translate; only the extra `scale` term changes here.
function rescaleActionIcons() {
  // getSizes().realZoom, NOT getZoom() — getZoom() is ALWAYS 1 right after a fresh fit, no matter the
  // diagram's size or node count: it's relative to THAT diagram's own fit, not an absolute scale. A
  // confirmed real bug: on a small test diagram this went unnoticed (a few dozen nodes still fit at a
  // large-enough per-node scale), but a large real diagram (hundreds of nodes) has to shrink FAR more
  // just to fit on screen at its own "100%" — 1/getZoom() never saw that shrink, so the icon rendered
  // at just a few CSS pixels there even though it looked fine on the small diagram. realZoom is the
  // library's own true diagram-units-to-CSS-pixel ratio (confirmed: doubles when you call zoomBy(2),
  // unlike getZoom() which resets to 1 on every fresh fit) — 1/realZoom makes 1 local SVG unit render
  // as exactly 1 CSS pixel always, regardless of diagram size or current zoom.
  const inv = mainPz ? 1 / mainPz.getSizes().realZoom : 1;
  for (const id in ACTION_ICONS) {
    const a = ACTION_ICONS[id]._anchor;
    if (a) ACTION_ICONS[id].setAttribute('transform', `translate(${a.x},${a.y}) scale(${inv})`);
  }
}
function updateZoomLevel() {  // reflect the current pan-zoom scale in the header control + the icons
  if (zoomlevel) zoomlevel.textContent = mainPz ? Math.round(mainPz.getZoom() * 100) + '%' : '100%';
  rescaleActionIcons();
}

// Keep the diagram fitted to the stage as the side bars (or the window) resize it. svg-pan-zoom caches
// the container size at init, so without this the content would clip/misalign when #stage's width
// changes. We re-fit (not just resize) so the SAME content stays framed in the new width — the diagram
// rescales with the stage instead of getting cut off. Coalesced to one re-fit per animation frame so a
// drag's mousemove stream stays smooth.
let refitRaf = 0;
function refitStage() {
  if (refitRaf) return;
  refitRaf = requestAnimationFrame(() => {
    refitRaf = 0;
    if (!mainPz) return;
    mainPz.resize(); mainPz.fit(); mainPz.center();
    updateZoomLevel();
  });
}

async function render() {
  const seq = ++renderSeq;
  hideTip();  // a re-render replaces the diagram — drop any tooltip from the old one
  if (mainPz) { mainPz.destroy(); mainPz = null; }
  const s = history[hi];
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
  mainScene = makeScene(diagram, () => applyDefaultPanel(s));
  for (const id in ACTION_ICONS) delete ACTION_ICONS[id];  // reset before bindFor's bindFrameDrill re-populates it
  bindFor(s);
  decorateActionIcons(mainScene);  // corner icon = each drawn box's one useful secondary action
  // Every drawn box gets a default re-select closure (plain-click select), so back/forward can restore
  // a node selection. Edges, flow steps and GP actors/steps register their own during bindFor; a box
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
  if (!pendingSelect && !pendingElementsList && !(s.sel && mainScene.selectors[s.sel])) applyDefaultPanel(s);
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
    // history revisit: restore the pan/zoom we left this view with (zoom first, then absolute pan)
    if (s.vp) { mainPz.zoom(s.vp.zoom); mainPz.pan(s.vp.pan); }
    updateZoomLevel();
    if (pendingMatchTextId) matchTextSize(mainScene.nodeEls[pendingMatchTextId]);
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

// A dir anchor in the map keeps a trailing slash ('src/api/'); the walked dir row does not ('src/api').
// Strip it so the two always match.
function treeKey(p) { return String(p || '').replace(/\/+$/, ''); }

// One row: a twisty (folders only), the name, and an id chip when a node points exactly here.
function makeRow(entry, depth) {
  const row = document.createElement('div');
  row.className = 'trow cov-' + entry.cov + (entry.dir ? ' tdir' : ' tfile');
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
  if (entry.node) {
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
    // hijack the selection to the containing subsystem.
    toggleDir(key);
    // e.node set -> this exact path collided in node_path_index (filetree.py): e.others carries the
    // rest, kept instead of dropped — selectFromTreeAnchors decides whether that's one thing or several.
    if (e.node) selectFromTreeAnchors([e.node, ...e.others], key);
  } else if (e.node) {
    selectFromTreeAnchors([e.node, ...e.others], key);  // this exact file collided — e.others carries the rest
  } else if (e.sel) {
    selectFromTree(e.sel);     // no exact match here — its owning subsystem/entity (finer grain), single target
  } else {
    flashNoMap(rec.row);       // unmapped file: a click does nothing -> brief hint
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
function flashNoMap(row) { row.classList.add('flash'); setTimeout(() => row.classList.remove('flash'), 450); }

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
  if (!t) return;
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
  const path = pathByNode[id] || (n ? refTreePath(n.file, n.line) : null);
  highlightTreePath(path);
}
function highlightTreePath(path) {
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
function buildFileTree() {
  if (!FILE_TREE) { document.body.classList.add('no-tree'); return; }
  (function index(e) {
    if (e.node) {
      pathByNode[e.node] = treeKey(e.path);
      const all = [e.node, ...(e.others || [])];
      if (all.length > 1) for (const id of all) siblingsByNode[id] = all;
    }
    for (const c of e.children) index(c);
  })(FILE_TREE);
  const kids = FILE_TREE.children || [];
  if (!kids.length) { treeBody.innerHTML = '<div class="tempty">No files found.</div>'; return; }
  renderChildrenInto(treeBody, kids, 0);
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
// user sets once (seeded at build time in REPO_ROOT_DEFAULT, overridable in Settings/localStorage).
const REPO_ROOT_DEFAULT = __REPO_ROOT__;
const GH_REPO_DEFAULT = __GH_REPO__;   // GitHub repo URL (overridable in Settings) or null
const GH_COMMIT = __GH_COMMIT__;       // the map's commit SHA — blob links are pinned to it
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
const LS = { editor: 'coyodex.editor', custom: 'coyodex.customUri', root: 'coyodex.srcRoot', ok: 'coyodex.rootOk', repo: 'coyodex.ghRepo', coach: 'coyodex.coachSeen', panelW: 'coyodex.panelW', treeW: 'coyodex.treeW', treeHidden: 'coyodex.treeHidden' };
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
const srcNode = (id) => { const n = GRAPH.nodes[id]; return (n && n.file && SRC_KINDS.has(String(n.kind))) ? n : null; };
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

// --- resizable side panel -------------------------------------------------------
// Drag the handle to set the panel width; persisted so it survives reloads, clamped so both the canvas
// and the panel stay usable. The drag starts on the handle (not the svg), so svg-pan-zoom never pans.
const resizer = document.getElementById('resizer');
const clampPanelW = (w) => Math.min(Math.max(w, 240), Math.round(window.innerWidth * 0.7));
const savedPanelW = parseInt(lsGet(LS.panelW) || '', 10);
if (savedPanelW) panel.style.width = clampPanelW(savedPanelW) + 'px';
let resizing = false;
resizer.addEventListener('mousedown', (e) => { e.preventDefault(); resizing = true; document.body.classList.add('resizing'); });
// The panel now sits between the file browser and the diagram (not flush against the window's right
// edge), so its width is the distance from ITS OWN left edge to the cursor — not from the window edge.
document.addEventListener('mousemove', (e) => { if (resizing) { panel.style.width = clampPanelW(e.clientX - panel.getBoundingClientRect().left) + 'px'; refitStage(); } });
document.addEventListener('mouseup', () => {
  if (!resizing) return;
  resizing = false; document.body.classList.remove('resizing');
  lsSet(LS.panelW, String(parseInt(panel.style.width, 10) || ''));
});

// --- file browser: build + toggle + resize --------------------------------------
// Same persist-and-clamp model as the side panel, mirrored to the left edge. The pane folds away via
// the header toggle; both its width and folded state survive reloads.
const tree = document.getElementById('tree');
const clampTreeW = (w) => Math.min(Math.max(w, 180), Math.round(window.innerWidth * 0.5));
const savedTreeW = parseInt(lsGet(LS.treeW) || '', 10);
if (savedTreeW) tree.style.width = clampTreeW(savedTreeW) + 'px';
if (lsGet(LS.treeHidden) === '1') { document.body.classList.add('tree-hidden'); treeToggleBtn.classList.add('off'); }
treeToggleBtn.addEventListener('click', () => {
  const hidden = document.body.classList.toggle('tree-hidden');
  treeToggleBtn.classList.toggle('off', hidden);
  lsSet(LS.treeHidden, hidden ? '1' : '0');
  refitStage();  // the stage just got wider/narrower — re-fit the diagram into it
});
let treeResizing = false;
treeResizer.addEventListener('mousedown', (e) => { e.preventDefault(); treeResizing = true; document.body.classList.add('resizing'); });
document.addEventListener('mousemove', (e) => { if (treeResizing) { tree.style.width = clampTreeW(e.clientX) + 'px'; refitStage(); } });
document.addEventListener('mouseup', () => {
  if (!treeResizing) return;
  treeResizing = false; document.body.classList.remove('resizing');
  lsSet(LS.treeW, String(parseInt(tree.style.width, 10) || ''));
});
buildFileTree();

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
  // Same view, different overlay — capture the live pan/zoom + selection first so the toggle keeps
  // them (render() restores from the state) instead of resetting to a fresh, unselected fit.
  toggle.addEventListener('click', () => { captureViewState(); mode = mode === 'diff' ? 'base' : 'diff'; render(); });
}
// Land on the Subsystems view for a diff render (the change-impact overlay lives there); otherwise the
// Context view — the highest, C4 system-in-the-world altitude.
go({ kind: (HAS_DIFF && HAS_GROUPING) ? 'container' : 'context' });
