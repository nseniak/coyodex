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
let BRIDGE_EDGES;               // flat list of every component->entity edge (structure<->domain bridge atoms)
let DOMAIN_CONTAINER_EDGES;     // inter-subdomain arrow 'A>B' -> [crossing E->E relations]
let ENTITY_FIELD_LINKS;         // entity id -> [{i, type, target}] : the class-box field lines whose
                                // TYPE is another entity, so the viewer can link the type word
let ENTITY_STORE_LINKS;         // entity id -> {i, text, dep} : the class-box store line, so the
                                // viewer can link it into the Data tab
let MERMAID_DEPLOYMENT;    // Deployment overview (the "All" view): processes + infra + derived `runs` edges
let DEPLOYMENT_CARDS;      // per-process drill: unit-name -> flowchart card of the subsystems it runs
let COMPLETENESS = {};        // the four-state counts shown on the System tab
let HAS_CAPABILITIES = false;
let CAP_OF_UC = {};           // use-case id -> its capability NODE (names on screen, never ids)
let DEPLOYMENT_GROUP_CARDS;   // product-area container id -> its members' diagram (the container drill)
let DEPLOYMENT_GROUP_MEMBERS; // product-area container id -> the unit names inside it
let DEPLOYMENT_EDGES;      // process->process arrow 'U_a>U_b' -> [async channels it carries]
let DEPLOYMENT_INFRA_EDGES;  // process->infra arrow 'U_a>Dn' -> [component->dep calls behind it]
let DEPLOYMENT_CALL_EDGES;   // process->process arrow 'U_a>U_b' -> [synchronous cross-process calls]
let DEPLOY_ENVS;           // declared deployment environments (variant names), or [] — gates the env picker
let DEPLOY_ENV = null;     // the selected environment (null = All); persists across the session
let HAS_DEPLOYMENT;        // gates the Deployment tab (any deployment[] unit present)
let MERMAID_HP;            // Happy Path (Level 1): use cases as a black-box sequence
let REPO_STATE = 'ok';    // 'ok' | 'no-repo' | 'no-commit' — whether the server can read this map's code
let FLOWS_MM;             // T6 use-case flows: uc-id -> sequenceDiagram (the inside view)
let FLOWS_MAP;            // the SAME flows as leaf-only maps: uc-id -> flowchart (the Map rendering)
let FLOWS_NARR;          // uc-id -> [{n,src,srcId,dst,dstId,verb,why,note}] readable steps
let HP_ACTORS;          // Happy-Path lifelines: [{aid,name,kind,wants,steps,stepIdx}]
let HP_STEP_MARKS;      // per Happy-Path step, the participant ids its ONE arrow crosses — a use case's
                        // other interchangeable actors ([] for the normal one-actor step)
let FLOW_ACTORS;        // uc-id -> [{aid,name,kind,wants,stepIdx}] flow-level actor lifelines (mirrors HP_ACTORS, scoped to one flow's own steps)
let ELEMENT_TINT;       // per-kind {fill,stroke} for views Mermaid renders kind-agnostically (cluster frames, flow participant boxes)
let MERMAID_LIBS;       // Context "Libraries" drill: System + the folded in-process deps
let FOLDED_LIBS;        // [{id,name,type}] folded out of Context into the Libraries box
let MERMAID_BY_BUCKETFOLD;  // Context big-bucket drill: BKF-id -> that bucket's members diagram
let FOLDED_BUCKETS;         // [{id,name,count,members:[{id,name}]}] big external buckets collapsed to a count box
const LIBS_ID = 'LIBS';                           // synthetic id of that collapsed box (matches gen_viewer.LIBS_ID)
let HAS_GROUPING, HAS_DOMAIN;
let HAS_SUBDOMAINS;  // domain model grouped into subdomains -> Domain view leads with the overview
let HAS_HP;
let HAS_GLOSSARY;    // gates the Glossary tab (derived from the graph in applyBundle)
let HAS_USECASES;    // gates the Use Cases tab (any use-case node present)
let HAS_SYSTEM;      // gates the System tab (any operational/reference collection present)
let HAS_DATA;        // gates the Data tab (any physical store present in data_view)
let DATA_VIEW;       // the store-centric Data-view payload (GRAPH.data_view)
let MERMAID_CHANNELS; // per-broker async flowchart source, keyed by broker dep id
let HAS_TESTS;       // gates the Tests tab (a test-completeness table or honesty note present)
let HAS_RULES;       // gates the Business logic tab (the map states at least one T7 rule)
let RULES_VIEW;      // the T7 payload (GRAPH.rules_view) — blocks, rules, and the two inversions.
                     // EVERYTHING derived (a site's components, a rule's steps/entities/sweep state)
                     // is computed server-side by the one Python implementation; re-deriving any of
                     // it here is the drift the layer exists to prevent.
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
  MERMAID_BRIDGE_CARD = b.mermaidBridgeCard; BRIDGE_EDGES = b.bridgeEdges; DOMAIN_CONTAINER_EDGES = b.domainContainerEdges;
  ENTITY_FIELD_LINKS = b.entityFieldLinks || {};
  ENTITY_STORE_LINKS = b.entityStoreLinks || {};
  MERMAID_DEPLOYMENT = b.mermaidDeployment; DEPLOYMENT_CARDS = b.deploymentCards; HAS_DEPLOYMENT = b.hasDeployment;
  DEPLOYMENT_GROUP_CARDS = b.deploymentGroupCards || {}; DEPLOYMENT_GROUP_MEMBERS = b.deploymentGroupMembers || {};
  DEPLOY_ENVS = b.deploymentEnvironments || [];
  DEPLOYMENT_EDGES = b.deploymentEdges || {}; DEPLOYMENT_INFRA_EDGES = b.deploymentInfraEdges || {};
  DEPLOYMENT_CALL_EDGES = b.deploymentCallEdges || {};
  MERMAID_HP = b.mermaidHp; FLOWS_MM = b.flowsMm; FLOWS_NARR = b.flowsNarr;
  FLOWS_MAP = b.flowsMap || {};
  HP_ACTORS = b.hpActors; HP_STEP_MARKS = b.hpStepMarks || []; FLOW_ACTORS = b.flowActors; ELEMENT_TINT = b.elementTint;
  MERMAID_LIBS = b.mermaidLibs; FOLDED_LIBS = b.foldedLibs; CONTEXT_EDGES = b.contextEdges;
  MERMAID_BY_BUCKETFOLD = b.mermaidByBucketFold || {}; FOLDED_BUCKETS = b.foldedBuckets || [];
  HAS_GROUPING = b.hasGrouping; HAS_DOMAIN = b.hasDomain; HAS_SUBDOMAINS = b.hasSubdomains;
  HAS_HP = b.hasHp; HAS_DIFF = b.hasDiff; META = b.meta; DIFF_STATE = b.diffState;
  REPO_ROOT_DEFAULT = b.repoRoot; GH_REPO_DEFAULT = b.ghRepo; GH_COMMIT = b.ghCommit;
  REPO_STATE = b.repoState || 'ok';   // the notice is painted at boot (below), not here:
                                      // applyBundle runs under top-level await, before the
                                      // code-pane elements are bound.
  HAS_GLOSSARY = Array.isArray(GRAPH.glossary) && GRAPH.glossary.length > 0;
  HAS_USECASES = Object.values(GRAPH.nodes || {}).some((n) => n.kind === 'usecase');
  // ── the capability overlay's data (plan/60-capabilities). Computed server-side by the ONE Python
  // helper; a second implementation here is the drift this repo keeps paying for elsewhere.
  COMPLETENESS = GRAPH.completeness || {};
  HAS_CAPABILITIES = Object.values(GRAPH.nodes || {}).some((n) => n.kind === 'capability');
  CAP_OF_UC = {};
  for (const n of Object.values(GRAPH.nodes || {})) {
    if (n.kind === 'usecase' && n.parent && (GRAPH.nodes[n.parent] || {}).kind === 'capability') {
      CAP_OF_UC[n.id] = GRAPH.nodes[n.parent];
    }
  }
  // `deployment` / `messaging` are deliberately absent: the tab no longer tables them (each is drawn
  // and paned in the Deployment / Data views), so a map carrying only those must NOT open an empty tab.
  HAS_SYSTEM = ['run_commands', 'entry_points', 'non_entity_types', 'observability',
    'security', 'config', 'extras'].some((k) => Array.isArray(GRAPH[k]) && GRAPH[k].length > 0);
  DATA_VIEW = GRAPH.data_view || {}; MERMAID_CHANNELS = b.mermaidChannels || {};
  HAS_DATA = Array.isArray(DATA_VIEW.stores) && DATA_VIEW.stores.length > 0;
  HAS_TESTS = (Array.isArray(GRAPH.tests) && GRAPH.tests.length > 0) || !!(GRAPH.tests_note || '').trim();
  RULES_VIEW = GRAPH.rules_view || {};
  HAS_RULES = !!b.hasBusinessRules;
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
const BADGE = { added: ['#1a7f37', '+', 'new'], modified: ['#9a6700', '✎', 'modified'],
                deleted: ['#cf222e', '×', 'deleted'], rippled: ['#d97706', '≈', 'ripples to'],
                drifted: ['#8250df', '↷', 'anchor drifted (code moved, not changed)'] };
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
// `panel` is the side detail pane. It is normally the real #panel element, but while a multi-selection's
// stacked cards are rendered (see renderSelPanel) it is TEMPORARILY re-pointed at the card being filled,
// so every existing `show*` fn keeps writing + wiring into the right card with no per-fn changes. Hence
// `let`, not `const`. PANEL_HOST is the stable real element (never reassigned) for direct host writes.
let panel = document.getElementById('panel');
const PANEL_HOST = panel;
// SOURCE LINKS ARE DELEGATED, not bound per render. Every `.srclink` button carries its own
// `data-where`, so one listener per container serves them all — including markup written after this
// runs. The previous approach called `wireSrcLinks(root)` after each render, which works only if
// every one of ~28 panel writers remembers: `showNode`, the most-used one of the lot, did not, so
// the Environments row rendered its manifest anchors as buttons that did nothing. Delegation makes
// forgetting impossible rather than catchable.
[PANEL_HOST, diagram].forEach((root) => root && root.addEventListener('click', (ev) => {
  const btn = ev.target && ev.target.closest && ev.target.closest('.srclink');
  if (!btn || !root.contains(btn)) return;
  const wn = whereNode(btn.getAttribute('data-where'));
  openInCodeViewer(wn.file, wn.line);
}));
const legend = document.getElementById('legend');
const legendbtn = document.getElementById('legendbtn');
const envpicker = document.getElementById('envpicker');
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
// Escape for HTML output. Covers BOTH contexts esc() feeds: text content AND double/single-quoted
// attributes (e.g. data-term="${esc(...)}"). Quotes must be escaped so a value can't break out of an
// attribute and inject markup; in text content the quote entities render identically, so it's safe
// everywhere. esc() output only ever lands in innerHTML, never textContent, so the entities decode back.
const esc = (s) => (s || '').replace(/[<>&"']/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' }[c]));
// Inline markdown -> safe HTML for prose fields (Purpose / Why / Wants / …): a link collapses to its
// text, then we ESCAPE, then wrap `code` and **bold** — escape-first so the only tags are the ones we
// add. Pragmatic, not a full parser: `code` is wrapped before **bold**, so a code span matches first.
const mdInline = (s) => esc(String(s || '').replace(/\[([^\]]+)\]\([^)]+\)/g, '$1'))
  .replace(/`([^`]+)`/g, '<code>$1</code>')
  .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

let mode = HAS_DIFF ? 'diff' : 'base';  // a diff render arms the change-impact overlay from the start
// Live mechanical diff (fetched from api/diff for a chosen range), distinct from the baked AI-report
// diff that may arrive in the bundle. When LIVE_DIFF is set it OWNS the overlay: DIFF_STATE is derived
// from it and the base diagram (not MERMAID_DIFF, which only the baked report has) carries the badges.
// BAKED_DIFF_STATE snapshots the bundle's diffState so clearing a live diff restores the baked one.
const DIFF_WORKTREE = 'WORKTREE';  // sentinel target = the current working tree (mirrors diffmap.WORKTREE)
const BAKED_DIFF_STATE = DIFF_STATE || null;
let LIVE_DIFF = null;  // {base,target,mapSide,direction,elements,changes,counts} or null
// Impact explorer (design: impact-and-update-design.md). When armed it OWNS the diff overlay rails:
// LIVE_DIFF gets a synthesized {impact:true,...} range (tree badges + code-diff mode ride along) and
// DIFF_STATE is projected from the ImpactResult, filtered by the ripple-depth threshold.
let IMPACT = null;     // the api/impact payload, or null
let impactTh = 6;      // strength threshold: 0 direct-only · 4 +structural · 6 +behavioral/data · 7 +call-graph
function hasDiff() { return !!(LIVE_DIFF || HAS_DIFF); }  // any diff overlay available for this render
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
// Happy Path actor lookups: by participant id (HPA0) and by the step it drives (HP1 -> actor records).
// A step maps to a LIST: its use case may name several interchangeable actors, and each of them really
// does drive it — keeping only one lit while a step is selected would dim a driver of that very step.
const HP_ACTOR_BY_AID = {};
for (const a of HP_ACTORS) HP_ACTOR_BY_AID[a.aid] = a;
const HP_ACTORS_OF_STEP = {};
for (const a of HP_ACTORS) for (const st of a.steps) (HP_ACTORS_OF_STEP[st.id] || (HP_ACTORS_OF_STEP[st.id] = [])).push(a);
// The Use Cases catalog: every use-case node in model order (importance), plus the reverse index
// uc -> [Happy Path step ids] that realize it. A use case may occupy several Happy Path positions, so
// this maps to a LIST — the `HPn` pill lists them all and lights every one when clicked. A use case
// with no entry here is off-spine (no pill).
const UC_NODES = Object.values(GRAPH.nodes || {}).filter((n) => n.kind === 'usecase');
const HP_STEPS_BY_UC = {};
for (const s of GRAPH.happy_path || []) if (s.uc) (HP_STEPS_BY_UC[s.uc] ||= []).push(s.id);
// Role lookup by name (lower-cased) -> {name, kind, wants} for the Use Cases actor-section headers.
// Keyed in the AUTHORED name space, because its tokens are `usecase.actors[]`, which the server builds
// from the roles table's own names. Keep it that way: a role name has a second, SANITISED form (what
// the diagrams draw), and every bug in this area has been an index in one space read with a token from
// the other — the server-side twin of this table carries both spellings for exactly that reason
// (gen_viewer._roles_by_name).
const ROLE_BY_NAME = {};
for (const r of GRAPH.roles || []) ROLE_BY_NAME[(r.name || '').trim().toLowerCase()] = r;
// Reverse traceability ("Used in UC"): element id -> Set of use-case ids whose T6 flow steps through
// it. The backward view of the flows (derived here, never authored), shown as links on a node's panel.
// Sub-flow references are EXPANDED: an element touched only inside a shared sub-flow is used by every
// referencing use case (the same treatment impact ripple and the audit give sub-flow content).
const USES_BY_NODE = {};
{
  const sfSteps = {};
  for (const sf of GRAPH.subflows || []) sfSteps[sf.id] = sf.steps || [];
  for (const f of GRAPH.flows || []) {
    for (const st of (f.steps || [])) {
      for (const s of (st.subflow && sfSteps[st.subflow] ? sfSteps[st.subflow] : [st])) {
        for (const end of [s.src, s.dst]) {
          if (GRAPH.nodes[end]) (USES_BY_NODE[end] ||= new Set()).add(f.uc);
        }
      }
    }
  }
}

// When a click navigates to another view to reveal a node (the file browser, a flow element link, the
// change-impact summary), the node id to select is stashed here and applied once that view has rendered.
let pendingSelect = null;
// An entry point to highlight once its component's detail pane renders — set by selectEntryPoint (a
// search hit / a System-tab component link), consumed in bindNodeDetailHandlers so the selection survives
// the (possibly async) navigation's final pane render instead of being wiped by it.
let pendingEpSelect = null;
// A focus-drill (⌘-drill a single component/entity cross arrow) stashes that node id here so the target
// edge card, once rendered, centers it (at the fresh-fit zoom) — guaranteeing the focused element is
// on-screen instead of restoring the pair card's last camera, which could leave it off-screen. One-shot:
// the next non-transient render consumes and clears it, so a plain history revisit (which sets no
// pendingCenter) still restores the camera where it was left.
let pendingCenter = null;

// node id -> its injected corner-action icon element (see decorateActionIcons), so a ⌘-click / double
// click drill (isDrillClick) can flash the SAME icon a direct icon-click would have used — one visual
// language regardless of which of the three ways you triggered it.
const ACTION_ICONS = {};
let EDGE_ICON_SEQ = 0;  // fallback ACTION_ICONS key for a drillable edge path with no (or a stripped) DOM id
// The front overlay layer that box + cluster action icons and diff badges are homed in. SVG has no
// z-index — stacking is document order only — so an icon appended into its OWN node/cluster group is
// painted over by any sibling group Mermaid draws later (a cluster's inner nodes, an overlapping
// neighbour box). This <g> is appended LAST inside the diagram's content group (see ensureIconOverlay),
// so everything in it paints on top of every box/edge — which is what keeps the drill pill from hiding
// behind a component. Recreated per render; null between renders.
let iconOverlay = null;
// Label-to-icon hover bridges share the overlay coordinate system but live in their own first child,
// beneath every visible action icon. This keeps the bridge reachable above Mermaid content without a
// later bridge stealing pointer events from an earlier icon on tightly-spaced sequence rows.
let iconBridgeOverlay = null;
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
  // selection: the ordered list of selected-element DESCRIPTORS (click order = card/stack order; the LAST
  //   is the "primary" that drives the tree + code viewer). Each selected descriptor also carries
  //   `revealAction`: true only when that item was selected by a direct diagram click. selKeys mirrors
  //   their keys for O(1) membership
  //   (hover-glow / already-selected tests). selectedKey = the primary's key (or null) — a compat handle
  //   for the few spots that want "the/most-recent" selection. A descriptor is { key, glow, focus, show }:
  //     glow(revealAction) -> apply this element's highlight, optionally pin its action icon, return cleanup
  //     focus   -> flowchart: { nodes:Set<id>, edge:(e)=>bool }; sequence: { els:Set<DOMEl> }; null = don't dim
  //     show()  -> fill `panel` with this element's detail (an existing show* fn; also syncs tree/code when primary)
  // focusUnion(scene, selection) dims to the UNION of every selected element's neighbourhood — the default
  //   is the node/edge model; bindHP/bindFlow swap in the sequence-diagram variant.
  // selectors: key -> a zero-arg closure that ADDS that element to the selection (selAdd), registered at
  //   bind time so back/forward can restore a whole multi-selection (and single-select navigations replay one).
  // noAction: node ids that must NOT get a corner action icon or an ⌥-drill in this view — the box you
  //   are already zoomed INTO (e.g. a process on its own card), which has nothing further to drill to.
  return { root, nodeEls: {}, edgeEls: [], dimEls: [], hpLit: new Set(), noAction: new Set(),
           selection: [], selKeys: new Set(), selectedKey: null, selectors: {}, _selClear: null,
           focusUnion: focusUnionNodes, defaultPanel };
}
function selHas(scene, key) { return scene.selKeys.has(key); }
// Re-apply the whole selection as one atomic state: tear down the previous glows, re-glow every selected
// element, dim to the UNION of their neighbourhoods, and (re)stack their detail cards — or, when nothing is
// selected, restore the scene's default panel + full-lit diagram. Glow is fully rebuilt each time (a plain
// CSS-filter swap, no visible flicker) so an element leaving the set can't strand a highlight, and shared
// highlights (a step lit by both a participant and its own selection) stay consistent.
function selApply(scene) {
  if (scene._selClear) { scene._selClear(); scene._selClear = null; }
  const undos = scene.selection.map((d) => d.glow(!!d.revealAction));
  scene._selClear = () => undos.forEach((f) => f && f());
  if (scene.selection.length) scene.focusUnion(scene, scene.selection); else clearFocus(scene);
  renderSelPanel(scene);
  flowSuspendIfDeselected(scene);
  flowMapRefreshStepLabels();
  // Deselecting the last element (⌘-click it off) returns to the empty state: clear the file-browser
  // highlight + default the code slot to browse, the same cleanup empty-canvas click / Escape do.
  if (!scene.selection.length) { highlightTreePath(null); setBrowsing(true); }
}
function selAdd(scene, desc, revealAction = false) {
  if (scene.selKeys.has(desc.key)) { scene.selectedKey = desc.key; return; }  // already in the set (dedupe restore)
  scene.selection.push({ ...desc, revealAction: !!revealAction });
  scene.selKeys.add(desc.key); scene.selectedKey = desc.key;
  selApply(scene);
}
function selRevealsAction(scene, key) {
  const d = scene.selection.find((x) => x.key === key);
  return !!(d && d.revealAction);
}
function selRemove(scene, key) {
  const i = scene.selection.findIndex((d) => d.key === key);
  if (i < 0) return;
  scene.selection.splice(i, 1); scene.selKeys.delete(key);
  scene.selectedKey = scene.selection.length ? scene.selection[scene.selection.length - 1].key : null;
  selApply(scene);
}
function selToggle(scene, desc, revealAction = false) {
  if (scene.selKeys.has(desc.key)) selRemove(scene, desc.key);
  else selAdd(scene, desc, revealAction);
}
function selClear(scene) {  // drop every selected element (tear down glows) WITHOUT touching the panel/focus
  if (scene._selClear) { scene._selClear(); scene._selClear = null; }
  scene.selection = []; scene.selKeys = new Set(); scene.selectedKey = null;
  flowSuspend();
  flowMapRefreshStepLabels();
}
function selReplace(scene, desc, revealAction = false) { selClear(scene); selAdd(scene, desc, revealAction); }
// The click-time router: a multi-select modifier (⌘ / ⌃) toggles the element in/out of the running
// selection; a plain click replaces the selection with just this element. Every plain-select entry point
// goes through here so the two gestures behave uniformly across every view.
function pickSel(scene, desc, e) {
  if (isMultiSelectClick(e)) selToggle(scene, desc, true);
  else selReplace(scene, desc, true);
}
// The full click-gesture handler for a BOX (node / fold): shift-click is a pure camera move (frame the box
// via matchTextSize — never selects), ⌘-click toggles it in/out of the multi-selection, a plain click
// replaces. Every box entry point routes here so all three gestures behave identically for regular boxes
// AND fold boxes (Libraries / external-system buckets), which previously bypassed the shift/⌘ handling.
function pickSelBox(scene, desc, el, e) {
  if (e && e.shiftKey) { matchTextSize(el); return; }
  pickSel(scene, desc, e);
}
// `box` is `node`, or an ancestor of it in the group tree (subsystem/subdomain containment).
function isAncestorOrSelf(box, node) { return box === node || isAncestorOf(box, node); }
// The keys of the drawn arrows in THIS scene that COVER any of the bundle's underlying links — a drawn
// arrow src→dst covers a link a.src→a.dst when each drawn end is that link end or an ancestor of it. This
// is how a synthetic-arrow drill selects the right arrows without predicting the target card's grouping:
// a card that drew the links individually matches them one-to-one; a card that re-bundled them under a
// child box matches that one aggregated arrow (its endpoints are ancestors of the links'). Reuses the SAME
// ancestor test the card itself used, run against the arrows it really drew — so nothing can drift.
function coverKeys(scene, atoms) {
  const keys = new Set();
  for (const x of scene.edgeEls) {
    if (!x.key) continue;  // a focus-only edge (a derived deployment arrow) has no selector — skip
    if (atoms.some((a) => isAncestorOrSelf(x.e.src, a.src) && isAncestorOrSelf(x.e.dst, a.dst))) keys.add(x.key);
  }
  return [...keys];
}
// The selection keys a state wants restored on arrival, in priority order: an exact captured multi-selection
// (`sels`, from history), else a synthetic arrow's covered arrows (`selCover`, resolved against what the
// target card drew), else a single requested key (`sel`, a focus-drill / flow-step / bridge leaf). Filtered
// to keys whose selectors exist in this scene.
function selectionKeysFor(scene, s) {
  let keys = (s.sels || []).filter((k) => scene.selectors[k]);
  if (!keys.length && s.selCover) keys = coverKeys(scene, s.selCover);
  if (!keys.length && s.sel && scene.selectors[s.sel]) keys = [s.sel];
  return keys;
}
// Restore a saved selection onto the freshly-bound scene: replay each resolved key's selector (adds it back).
// Returns whether anything was applied.
function restoreSelection(scene, s) {
  const keys = selectionKeysFor(scene, s);
  if (!keys.length) return false;
  selClear(scene);
  for (const k of keys) scene.selectors[k]();
  return true;
}
// Shown ONCE, the first time a selection dims the diagram: the fade is a focus, not a failure, and a
// first-time reader has no way to tell those apart. Auto-clears; the guide behind `?` carries the rest.
function noteFirstDim() {
  if (lsGet(LS.dimSeen) === '1') return;
  lsSet(LS.dimSeen, '1');
  const el = document.createElement('div');
  el.id = 'dimnote';
  el.textContent = 'Faded boxes are just unrelated — click empty space to clear the selection.';
  (document.getElementById('stage') || document.body).appendChild(el);
  setTimeout(() => { el.classList.add('out'); setTimeout(() => el.remove(), 400); }, 5200);
}
function applyFocus(scene, keepNode, keepEdge) {
  noteFirstDim();
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
  refreshAllPills();  // a box that just became dimmed must drop its pill even if it's under the cursor
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
// Flowchart focus for a multi-selection: keep the UNION of every selected element's neighbourhood lit, dim
// the rest. A descriptor whose element isn't drawn in this scene carries focus:null and contributes nothing
// — matching the old single-select behaviour of not dimming at all for an off-scene selection (so a lone
// off-scene pick leaves the whole diagram lit, while it rides along invisibly when mixed with on-scene picks).
function focusUnionNodes(scene, selection) {
  const withFocus = selection.filter((d) => d.focus);
  if (!withFocus.length) { clearFocus(scene); return; }
  const keepN = new Set();
  for (const d of withFocus) d.focus.nodes.forEach((n) => keepN.add(n));
  applyFocus(scene, (n) => keepN.has(n), (e) => withFocus.some((d) => d.focus.edge(e)));
}
// Sequence-diagram focus (Happy Path / use-case flow): keep the union of every selected element's lit DOM
// parts, dim the rest. Swapped in for focusUnionNodes by bindHP/bindFlow.
function focusUnionEls(scene, selection) {
  const keep = new Set();
  for (const d of selection) if (d.focus && d.focus.els) d.focus.els.forEach((x) => keep.add(x));
  hpFocus(scene, keep);
}
// Render the side panel for the current selection as a STACK of cards, one per selected element, in click
// order (the primary — most-recently-clicked — is last). Each card is filled by the element's existing
// show* fn with the global `panel` temporarily re-pointed at that card, so every show* keeps writing +
// wiring exactly as it did for a single selection. Because show* also mirror into the tree + code viewer
// (a global side effect), rendering the primary LAST makes its tree/code sync the one that sticks. Nothing
// selected -> the scene's default panel. A single selection is one card (styled to read like the old flat
// panel), so single and multi share this one path.
function renderSelPanel(scene) {
  panel = PANEL_HOST;
  PANEL_HOST.innerHTML = '';
  if (!scene.selection.length) { scene.defaultPanel(); return; }
  for (const d of scene.selection) {
    const card = document.createElement('section');
    card.className = 'sel-card';  // multi vs single is styled by `.sel-card + .sel-card` (a divider), no host class
    PANEL_HOST.appendChild(card);
    panel = card;
    try { d.show(); } finally { panel = PANEL_HOST; }
  }
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
// A sequence-diagram actor figure, given the SAME identity the Dependencies view gives that role, so the
// two views speak ONE vocabulary: a person keeps the stick figure in the human tint; a SERVICE actor is
// redrawn as the indigo hexagon the Dependencies view draws it as. The distinction is the method's, not
// decoration — a service actor is an outside initiator with its own goal (a scheduled job, a poller, an
// inbound caller), never the internal machinery that relays someone else's action, and a reader who
// can't tell the two apart reads the delivery mechanism as the party who acted.
//
// Both sequence views call this (the Happy Path and the per-use-case flows) with the `kind` their actor
// list already carries from the Roles table — build_graph normalizes it to exactly human/service, and an
// actor with no matching role keeps Mermaid's default rather than being painted as a guess.
const SEQ_ACTOR_TINT = { human: 'human', service: 'svc' };
const HEX_ACTOR_PAD = 18;      // how much wider than the stick figure's own footprint the hexagon sits
const HEX_ACTOR_RATIO = 0.72;  // its height, as a fraction of that width — the Dependencies view's squat shape
function styleSeqActor(root, aid, kind) {
  const tint = ELEMENT_TINT[SEQ_ACTOR_TINT[kind]];
  if (!tint) return;
  // Mermaid draws BOTH the top figure and its bottom mirror as `g.actor-man[name=<participant id>]`
  // (only the top one carries data-id), so the name attribute reaches the pair in one query.
  for (const g of root.querySelectorAll('g.actor-man[name="' + aid + '"]')) {
    // Stroke on the GROUP, the way Mermaid itself sets it: the head, the limbs, the label outline and a
    // part added below (the hexagon) all inherit it, so one property recolours the whole figure. FILL is
    // set per shape instead — the label is a group child too, and filling it would repaint the text.
    g.style.setProperty('stroke', tint.stroke, 'important');
    if (kind === 'service') hexagonifyActor(g);
    for (const shape of g.querySelectorAll('circle, polygon')) shape.style.setProperty('fill', tint.fill, 'important');
  }
}
// The Happy Path's System lifeline, painted like the System box every other view draws it — the same
// dark indigo, with its label repainted so it stays readable on that fill. Mermaid renders it as a plain
// default participant, so without this the one box that IS the system reads as the greyest thing on
// screen. In THIS diagram the boxed participant is the system and every other lifeline is a stick figure
// or a hexagon, so `text.actor-box` reaches its label with no name to match on (Mermaid puts none there).
const HP_SYS_ID = 'HPSYS';  // the participant id gen_hp_mermaid gives the System lifeline
function styleSeqSystem(root) {
  const tint = ELEMENT_TINT.system;
  if (!tint) return;
  for (const rect of root.querySelectorAll('rect.actor[name="' + HP_SYS_ID + '"]')) applyTint(rect, 'system');
  // The label AND its tspans: Mermaid wraps the text in a `tspan` that carries its own (black) fill, so
  // painting only the `text` leaves a black label on the dark box — the box read as empty. `fill` is not
  // inherited past an element that sets it, so every drawn node in the label has to be told.
  const color = tint.color || '#fff';   // a dark box with no colour to pair it with is unreadable, never bare
  for (const t of root.querySelectorAll('text.actor-box')) {
    for (const el of [t, ...t.querySelectorAll('tspan')]) el.style.setProperty('fill', color, 'important');
  }
}
// Swap one stick figure for the hexagon outline, in place: the hexagon is centred on the figure's own
// footprint and the label is left untouched, so the lifeline, the label and every message keep the exact
// position Mermaid gave them — nothing is relaid out, so there is no second layout to keep in sync.
function hexagonifyActor(g) {
  if (g.querySelector('polygon')) return;  // already swapped (a re-bind over the same rendered scene)
  // The head + the four limbs. The LIFELINE is a sibling of this group, not a child, so it cannot be
  // caught here — the class guard states that anyway, since deleting it would erase the actor's column.
  const parts = [...g.querySelectorAll('circle, line')].filter((el) => !el.classList.contains('actor-line'));
  if (!parts.length) return;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const el of parts) {
    let b; try { b = el.getBBox(); } catch (_) { return; }
    x0 = Math.min(x0, b.x); y0 = Math.min(y0, b.y); x1 = Math.max(x1, b.x + b.width); y1 = Math.max(y1, b.y + b.height);
  }
  const w = (x1 - x0) + HEX_ACTOR_PAD, h = w * HEX_ACTOR_RATIO;
  const hex = document.createElementNS(SVGNS, 'polygon');
  hex.setAttribute('points', hexPoints((x0 + x1) / 2 - w / 2, (y0 + y1) / 2 - h / 2, w, h));
  hex.setAttribute('stroke-width', '2');  // the weight Mermaid strokes the stick figure with
  for (const el of parts) el.remove();
  g.insertBefore(hex, g.firstChild);
}
// The flowchart half of the same vocabulary: a HUMAN actor box in the Dependencies view (and its
// drill-downs) becomes the stick figure too, so a person looks like a person on every view that draws
// one — a box, however rounded, read as another piece of the system. Mermaid has no person shape here,
// so the node's own outline path is re-pathed in place: same element, same id, same tint, same handlers
// — only its `d` changes. The room it needs was allocated up front by the generator's blank first label
// line, so the name already sits BELOW the figure and nothing had to be moved.
const STICK_NODE_INSET = 2;  // how far inside the box's top edge the head starts
const STICK_NODE_GAP = 3;    // the breathing space the feet keep above the name
function stickFigureNode(el) {
  const label = el.querySelector('g.label');
  // Mermaid draws this outline as TWO paths over the same geometry — one carrying the fill, one the
  // stroke. Both have to become the figure, or the untouched one keeps drawing the box around it.
  const paths = [...el.querySelectorAll('path')];
  if (!label || !paths.length || paths[0].dataset.stick) return;
  // The blank line IS the room. Without it (a diagram generated before this rule) the figure would be
  // drawn straight over the name, so the box is left exactly as Mermaid drew it instead.
  if (!/<br/i.test(label.innerHTML)) return;
  let box = null;
  for (const p of paths) {
    let b; try { b = p.getBBox(); } catch (_) { continue; }
    if (!box || b.height > box.height) box = b;
  }
  if (!box) return;
  // The label is two lines — blank, then the name — and is centred on the node's origin, so the blank
  // one owns the whole top half and the figure's feet stop just short of the origin.
  const top = box.y + STICK_NODE_INSET, h = -STICK_NODE_GAP - top;
  if (h <= 0) return;
  const d = stickFigurePath(0, top, h);
  for (const p of paths) {
    p.setAttribute('d', d);
    p.style.setProperty('stroke-width', '1.8', 'important');  // a box outline's hairline reads as a broken figure
    p.dataset.stick = '1';
  }
}
// Container kinds — the group boxes (subsystem/subdomain) the diagram draws with a thick dashed frame.
const CONTAINER_KINDS = new Set(['subsystem', 'subdomain']);
function isContainerKind(kind) { return CONTAINER_KINDS.has(kind); }
// Leaf kinds that own a file set worth grouping in the tree when selected (see selection pills). Excludes
// containers (they carry their own anchor pill) and the System node (its "files" would be the whole repo).
const LEAF_KINDS = new Set(['component', 'entity', 'dep']);
// The element currently selected on the diagram — file-browser pills for this element are emphasised
// (`.pill-sel`). Kept in sync by setTreeSelection; a pill built while it's set is born emphasised.
let treeSelId = null;
// A readable, capitalised kind name ('dep' -> 'Dependency') for tooltips.
function kindLabel(kind) {
  const k = kind === 'dep' ? 'dependency' : (kind || '');
  return k ? k.charAt(0).toUpperCase() + k.slice(1) : '';
}
// A coloured element pill: the element's NAME in its kind's diagram tint (pale fill + matching border +
// text), with a thick DASHED border when it's a container — the same colour code + container signal the
// boxes use. ONE builder, reused by the file browser (a file's container tag) and the code viewer (the
// owning-element pill beside the path), so the look stays identical. Returns a <span>, or null when `id`
// isn't a real element — only the tinted kinds get a pill, so the System / actor / use-case nodes (no
// tint) never render a blank one.
function elementPill(id) {
  const n = id && GRAPH.nodes[id];
  if (!n || !(isContainerKind(n.kind) || LEAF_KINDS.has(n.kind))) return null;
  const pill = document.createElement('span');
  pill.className = 'pill' + (isContainerKind(n.kind) ? ' pill-container' : '');
  const tint = ELEMENT_TINT[n.kind];
  if (tint) { pill.style.background = tint.fill; pill.style.borderColor = tint.stroke; pill.style.color = tint.stroke; }
  pill.textContent = n.name;
  pill.title = 'Select ' + kindLabel(n.kind).toLowerCase() + ': ' + n.name;
  pill.dataset.id = id;
  if (id === treeSelId) pill.classList.add('pill-sel');  // born emphasised if its element is the selection
  // Clicking a pill selects its element in the diagram (navigating to whichever view draws it). Stop the
  // click bubbling so a pill inside a tree row doesn't also fire the row's own select/expand.
  pill.addEventListener('click', (ev) => { ev.stopPropagation(); selectFromTree(id); });
  return pill;
}
// An EXPANDED group (a drilled subsystem / subdomain) renders as a Mermaid CLUSTER frame, which
// defaults to pale yellow. Tint each cluster to its family so a group reads the SAME colour collapsed (a
// box) or expanded (a frame). The cluster's DOM id ends with its element id (`<diagramId>-S1` / `-SD1`);
// one pass covers flowchart subgraphs (subsystem cards) AND classDiagram namespaces (subdomain cards +
// the mixed S×SD bridge), where Mermaid's `style` directive can't reach the frame.
// ── entity-box detail toggle ──────────────────────────────────────────────────────────────────────
// The extras on an entity box — a field's key markers (` · PK FK ?`) and the retention / lifecycle
// lines — are ALWAYS baked into the diagram source, so Mermaid lays every box out WITH them. Turning
// them off therefore never re-runs the layout: it rewrites glyphs in the already-drawn SVG (a marker
// suffix is swapped for its stripped text; a whole extra line goes `visibility:hidden`, which keeps
// its space). Nothing moves — the cost is that a box stays sized for its "details on" state.
// Entity boxes ALWAYS carry their full detail — the field key markers (PK/FK/uniq/opt), retention and
// lifecycle lines the generator draws. There used to be a "Details" toggle that hid them, defaulting to
// on; it was one more control to discover for a choice nobody needs to make, and a reader who happened
// to leave it off would silently see a poorer diagram with nothing saying so. The generator is the one
// place that decides what a box says.

function tintClusters(root) {
  root.querySelectorAll('g.cluster').forEach((g) => {
    const m = (g.id || '').match(/-([A-Za-z]+\d+)$/);
    // A `CYBK<i>` frame is a Context/Libraries purpose-bucket group — presentational, backed by no
    // graph node — so it takes the neutral 'bucket' tint; every other frame tints to its element kind.
    if (m && /^CYBK\d+$/.test(m[1])) { applyTint(g.querySelector('rect'), 'bucket'); return; }
    const node = m && GRAPH.nodes[m[1]];
    applyTint(g.querySelector('rect'), node && node.kind);
  });
}
// Bold a cluster's title and open a gap BELOW it: Mermaid sizes the label band for the ORIGINAL font +
// position, so a bolded/enlarged title otherwise crowds the first child. Fix: grow the frame UPWARD by
// `pad` (empty space at the top) and lift the title into it — the content stays put, so a real gap opens
// below the title. `fontSize` (optional) enlarges the title too. Shared by the drilled-frame emphasis
// and the Deployment lane styling, so a container title reads the same wherever it's drawn.
function padClusterTitle(g, pad, fontSize) {
  const rect = g.querySelector('rect');
  const label = g.querySelector('.cluster-label') || g.querySelector('text');
  if (rect) {
    const y = parseFloat(rect.getAttribute('y')), h = parseFloat(rect.getAttribute('height'));
    if (!Number.isNaN(y) && !Number.isNaN(h)) { rect.setAttribute('y', y - pad); rect.setAttribute('height', h + pad); }
  }
  if (label) {
    label.style.fontWeight = '700';
    if (fontSize) label.style.fontSize = fontSize;
    const t = label.getAttribute('transform') || '';
    const m = t.match(/translate\(\s*([-\d.]+)[ ,]+([-\d.]+)\s*\)/);
    if (m) label.setAttribute('transform', 'translate(' + m[1] + ', ' + (parseFloat(m[2]) - pad) + ')');
    // let a slightly wider title overflow its layout-fixed box rather than clip
    const fo = label.querySelector ? label.querySelector('foreignObject') : null;
    if (fo) fo.style.overflow = 'visible';
  }
  return rect;
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
    const rect = padClusterTitle(g, 20, '1.35em');
    if (rect) rect.style.setProperty('stroke-width', '4px', 'important');  // beats the tint's dashed width
    break;  // exactly one frame is the zoomed-in group
  }
}
// The Deployment view's lanes are Mermaid subgraphs; give their titles the SAME bold weight + breathing
// room a drilled container frame gets, so a lane reads as a labelled band (like a subsystem container),
// not a hairline box with cramped 400-weight text. Every cluster in these views is a lane.
function styleDeploymentLanes(root) {
  for (const g of root.querySelectorAll('g.cluster')) padClusterTitle(g, 10);
}

// --- corner action icon -----------------------------------------------------------
// Every drawn box gets AT MOST ONE corner icon — whatever its one useful secondary action is: a
// container (subsystem/subdomain) drills into the diagram, a leaf with a source ref (component/entity)
// opens that file. On a use-case Map, the one action instead locates the box in its canonical structural
// diagram. Nothing shown otherwise (a dep, or a leaf with no file, has no secondary action).
// Clicking the icon fires the action directly; isDrillClick's ⌘-click / double-click paths flash this
// SAME icon (via ACTION_ICONS) so all three routes teach the one visual language. Hidden until the box
// is hovered (see viewer.css) — keeps a busy diagram uncluttered; double-click-anywhere-on-the-box
// stays the reliably-discoverable path regardless of whether anyone ever notices the icon.
function isDeploymentGroup(id) { return !!(DEPLOYMENT_GROUP_MEMBERS && DEPLOYMENT_GROUP_MEMBERS[id]); }
function primaryActionFor(id) {
  // A product-area container is drawn by the deployment renderer, not the model, so it has no GRAPH
  // node — match it by id before the node lookup below bails out.
  if (isDeploymentGroup(id)) return { kind: 'drill', run: () => go({ kind: 'deploymentGroup', gid: id }) };
  if (id === 'SYS') { const t = sysDrillTarget(); return t ? { kind: 'drill', run: () => go(t) } : null; }
  if (id === LIBS_ID) return { kind: 'drill', run: () => go({ kind: 'libs' }) };
  const n = GRAPH.nodes[id];
  if (!n) return null;
  if (n.kind === 'bucketfold') return { kind: 'drill', run: () => go({ kind: 'bucketfold', bkid: id }) };
  if (n.kind === 'subsystem') return { kind: 'drill', run: () => go({ kind: 'subsystem', sid: id }) };
  if (n.kind === 'subdomain') return { kind: 'drill', run: () => go({ kind: 'domsub', sd: id }) };
  if (n.kind === 'process') return { kind: 'drill', run: () => go(deploymentDrill(id)) };  // a process box drills to its unit card
  const dd = dataDrillFor(id);  // a store/broker box drills to its Data-tab section (beats opening its config file)
  if (dd) return { kind: 'drill', run: () => go(dd) };
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
// `body.cmd .drill { cursor: zoom-in }`). `locate` uses Lucide's fixed target, and `open` draws the
// standard diagonal "open externally" arrow that viewer.css's `.opensrc` cursor matches.
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
  } else if (kind === 'locate') {
    // Lucide LocateFixed, recentered around 0,0 for the existing circular action badge. The outer
    // target identifies a location; the four short cardinal marks keep it distinct from drill's
    // magnifying glass even at the map's fit zoom.
    const outer = document.createElementNS(SVGNS, 'circle');
    outer.setAttribute('cx', '0'); outer.setAttribute('cy', '0'); outer.setAttribute('r', '6');
    const inner = document.createElementNS(SVGNS, 'circle');
    inner.setAttribute('cx', '0'); inner.setAttribute('cy', '0'); inner.setAttribute('r', '2.25');
    const marks = document.createElementNS(SVGNS, 'path');
    marks.setAttribute('d', 'M -10,0 L -8,0 M 8,0 L 10,0 M 0,-10 L 0,-8 M 0,8 L 0,10');
    g.append(outer, inner, marks);
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
// All kinds share the same indigo — the icon SHAPE is what tells drill, locate and open apart, not
// colour. glyphWidth stays thicker for `open`: a few open line segments (the
// arrow) read as visually thinner/smaller than the drill glyph's filled lens ring at the same
// bounding-box size, even at matched colour.
const ICON_PAINT = {
  drill: { stroke: '#6366f1', hoverFill: '#eef2ff', glyphStroke: '#4338ca', glyphWidth: '2.1px' },
  open: { stroke: '#6366f1', hoverFill: '#eef2ff', glyphStroke: '#4338ca', glyphWidth: '2.6px' },
  locate: { stroke: '#6366f1', hoverFill: '#eef2ff', glyphStroke: '#4338ca', glyphWidth: '1.8px' },
};
const ACTION_ICON_R = 16.5;  // the halo's radius — shared with addLabelActionIcon so its offset can clear the badge without a magic number of its own
function paintImportant(el, props) {
  for (const k in props) el.style.setProperty(k, props[k], 'important');
}
// Action icons live in the front overlay (iconOverlay), NOT inside their node/edge/label group,
// so the CSS descendant reveal rule (`g.node:hover .action-icon`) can no longer reach them — their
// show/hide is driven here in JS instead. A box pill is visible while its owner is hovered, or while a
// DIRECT diagram click selected it; automatic selections keep the pill hover-only. A dimmed box never
// reveals under the cursor (a box you're not focused on shouldn't invite drilling just because the
// pointer passed over it). A label/edge pill (opts.host) keeps its own showIcon/hideIcon path.
function refreshPillReveal(icon) {
  const owner = icon._owner;
  const dimmed = owner && owner.classList.contains('dim');
  const show = !!icon._selected || (!!icon._hover && !dimmed);
  icon.classList.toggle('revealed', show);
}
function setPillHover(icon, hovering) { icon._hover = hovering; refreshPillReveal(icon); }
// Recompute every box/cluster pill's visibility — called whenever the shared dim state changes
// (applyFocus/clearFocus), so a pill on a box that just became (or stopped being) dimmed updates even
// with no fresh hover event to trigger it.
function refreshAllPills() { for (const id in ACTION_ICONS) { const ic = ACTION_ICONS[id]; if (ic && ic._owner) refreshPillReveal(ic); } }
// The front overlay layer for action icons + badges: a <g> appended LAST directly to the Mermaid SVG,
// so it paints on top of every top-level group. This matters for sequence diagrams, which have several
// sibling groups rather than one shared content root. Added BEFORE svg-pan-zoom wraps all SVG children
// into its viewport, so it rides inside the same pan/zoom transform the boxes do — the icons'
// own counter-zoom (rescaleActionIcons) then holds them at a fixed screen size, exactly as it did when
// they lived in their box group. The old <g> is thrown away with the rest of the SVG on each re-render.
function ensureIconOverlay(container) {
  const svg = container.querySelector('svg');
  if (!svg) { iconBridgeOverlay = null; return null; }
  const g = document.createElementNS(SVGNS, 'g');
  g.setAttribute('class', 'coyodex-icon-overlay');
  iconBridgeOverlay = document.createElementNS(SVGNS, 'g');
  iconBridgeOverlay.setAttribute('class', 'coyodex-icon-bridge-overlay');
  g.appendChild(iconBridgeOverlay);
  svg.appendChild(g);
  return g;
}
const ACTION_ICON_TIP_DELAY_MS = 250;
let actionIconTipTimer = null;
let actionIconHover = null;
function hideActionIconTip() {
  if (actionIconTipTimer) clearTimeout(actionIconTipTimer);
  actionIconTipTimer = null;
  actionIconHover = null;
  hideTip();
}
function scheduleActionIconTip(label, ev) {
  hideActionIconTip();
  actionIconHover = { label, x: ev.clientX, y: ev.clientY };
  actionIconTipTimer = setTimeout(() => {
    actionIconTipTimer = null;
    if (!actionIconHover) return;
    tip.textContent = actionIconHover.label;
    tip.classList.remove('action');
    tip.classList.add('on');
    moveTip(actionIconHover.x, actionIconHover.y);
  }, ACTION_ICON_TIP_DELAY_MS);
}
function moveActionIconTip(ev) {
  if (!actionIconHover) return;
  actionIconHover.x = ev.clientX;
  actionIconHover.y = ev.clientY;
  if (!actionIconTipTimer) moveTip(ev.clientX, ev.clientY);
}
// Inject `action`'s icon (circle + glyph) into the final foreground overlay. `opts.anchor` supplies an
// overlay-space position for an edge/label icon; `opts.host` is its fallback parent if the overlay is
// unavailable and also marks it as independently revealed. A box icon needs neither: its own top-left
// corner is converted from the box's local coordinates into the overlay here.
function addActionIcon(el, id, action, opts) {
  const host = opts && opts.host;
  // The overlay comes first even for edge pills. Keeping those inside a Mermaid label/edge group lets
  // nodes and cluster frames drawn later cover them. The host remains only as a defensive fallback.
  const parent = iconOverlay || host || el;
  let anchor = opts && opts.anchor;
  if (!anchor) {
    let bbox; try { bbox = el.getBBox(); } catch (_) { return; }
    if (parent === el) anchor = { x: bbox.x, y: bbox.y };
    else { anchor = pointToHostSpace(el, bbox.x, bbox.y, parent); if (!anchor) return; }
  }
  const paint = ICON_PAINT[action.kind];
  const icon = document.createElementNS(SVGNS, 'g');
  icon.setAttribute('class', 'action-icon is-' + action.kind);
  const actionLabel = action.title || (action.kind === 'drill' ? 'Drill in' : 'Open source');
  icon.setAttribute('role', 'button');
  icon.setAttribute('aria-label', actionLabel);
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
  icon.append(halo, circle, glyph);
  // The hover tint also goes through JS + !important (not a CSS :hover rule) for the same reason as the
  // base paint above — it's just fill, so it hits the exact same Mermaid collision.
  icon.addEventListener('mouseenter', (ev) => {
    paintImportant(circle, { fill: paint.hoverFill });
    scheduleActionIconTip(actionLabel, ev);
  });
  icon.addEventListener('mousemove', moveActionIconTip);
  icon.addEventListener('mouseleave', () => {
    paintImportant(circle, { fill: '#fff' });
    hideActionIconTip();
  });
  icon.addEventListener('click', (e) => {
    if (isDrag(e)) return;  // tail of a drag-pan, not a real click
    e.stopPropagation();
    flashIcon(icon);
    action.run();
  });
  parent.appendChild(icon);
  ACTION_ICONS[id] = icon;
  // A box/cluster pill: link it to its owner box and drive its reveal off the box's hover + selection.
  // The icon carries its OWN hover listeners too — now that it's not a child of the box, the box's
  // mouseleave fires the moment the cursor crosses onto the pill, so without this the pill would vanish
  // just as you reach it. The two hover regions overlap at the box corner, so the paired leave/enter
  // fire in the same tick (no repaint between) and the pill never flickers. Selection reveal: glowNode.
  if (!host) {
    el._actionIcon = icon;
    icon._owner = el;
    el.addEventListener('mouseenter', () => setPillHover(icon, true));
    el.addEventListener('mouseleave', () => setPillHover(icon, false));
    icon.addEventListener('mouseenter', () => setPillHover(icon, true));
    icon.addEventListener('mouseleave', () => setPillHover(icon, false));
  }
}
// A message label has no box to anchor a corner badge to — sit the pill just before the label's left
// edge instead (so it reads first, like a bullet), vertically centered on it. Used for a Happy Path
// message's text AND (see bindEdgeActionIcon) any drillable edge with a real label — same convention
// either way: one fixed spot, not one that chases the cursor. The visible pill goes in iconOverlay so
// every box and cluster stays behind it. Its invisible hover bridge uses the dedicated first overlay
// child: above Mermaid content, below every icon, and ending at the label's left edge so label clicks
// remain the label's own.
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
  const parent = iconOverlay || host;
  const bridgeParent = iconBridgeOverlay || parent;
  // The pill and bridge are in sibling overlay layers with the same effective coordinate system. Keep
  // their references separately for the fallback path where no overlay exists.
  const ref = pointToHostSpace(label, bbox.x, bbox.y + bbox.height / 2, parent);
  const bridgeRef = pointToHostSpace(label, bbox.x, bbox.y + bbox.height / 2, bridgeParent);
  if (!ref || !bridgeRef) return;
  const gap = ACTION_ICON_R + 10;
  const anchor = { x: ref.x - gap, y: ref.y };  // inv=1 placeholder for this first paint, before mainPz exists
  // Bridge the gap with one continuous hover strip. It starts at the pill's centre (the icon wins that
  // overlap because its layer is above this one) and stops exactly at the label's left edge.
  const bridge = document.createElementNS(SVGNS, 'rect');
  bridge.style.setProperty('fill', 'transparent');
  bridge.style.setProperty('pointer-events', 'all');
  bridgeParent.appendChild(bridge);
  addActionIcon(label, id, action, { host, anchor });
  const icon = ACTION_ICONS[id];
  // Lets hpGlow / glowEdge find this pill from the label/path element alone, so selecting the step or
  // edge shows it without the caller threading the icon through separately.
  label._actionIcon = icon;
  icon._bridge = bridge;
  icon._bridgeHost = bridgeParent;
  icon._bridgeRef = bridgeRef;
  icon._labelRef = ref;
  icon._labelGap = gap;
  placeLabelBridge(icon);
}
// (Re)size the bridge from the pill's CURRENT anchor (already zoom-corrected by the caller) out to
// just past the label — kept in sync with rescaleActionIcons so it never lags the pill it bridges to.
function placeLabelBridge(icon) {
  const b = icon._bridge; if (!b) return;
  const anchor = pointToHostSpace(icon.parentNode, icon._anchor.x, icon._anchor.y, icon._bridgeHost);
  if (!anchor) return;
  const inv = curIconInv();
  const x = Math.min(anchor.x, icon._bridgeRef.x);
  b.setAttribute('x', String(x));
  b.setAttribute('y', String(icon._bridgeRef.y - 5 * inv));
  b.setAttribute('width', String(Math.abs(icon._bridgeRef.x - anchor.x)));
  b.setAttribute('height', String(10 * inv));
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
function locateActionFor(id) {
  const t = selectTargetFor(id);
  if (!t || !t.selectId) return null;  // excludes actor aliases and anything without a structural home
  const target = { ...t.state, sel: 'node:' + t.selectId };
  const tab = stateTitle({ kind: topView(t.state.kind) });
  return { kind: 'locate', title: 'Locate in ' + tab, run: () => {
    pendingCenter = t.selectId;
    go(target);
  } };
}
// The structural diagram that actually draws a flow arrow's backbone relationship. The destination
// carries `selCover`, resolved after render against the arrows the target diagram chose to draw: one
// concrete arrow, several parallel arrows, or one collapsed arrow that represents them all.
function relationshipLocateTarget(srcId, dstId) {
  const src = GRAPH.nodes[srcId], dst = GRAPH.nodes[dstId];
  const pairEdges = COMP_LOOKUP[srcId + '>' + dstId] || [];
  if (!src || !dst || !pairEdges.length) return null;
  const withEdges = (state) => ({ ...state, selCover: bundleAtoms(pairEdges) });
  const parentOfKind = (node, kind) => {
    const p = node.parent && GRAPH.nodes[node.parent];
    return p && p.kind === kind ? p.id : null;
  };

  if (src.kind === 'component' && dst.kind === 'component') {
    const a = parentOfKind(src, 'subsystem'), b = parentOfKind(dst, 'subsystem');
    if (!a || !b) return withEdges({ kind: 'component' });
    if (a === b) return withEdges({ kind: 'subsystem', sid: a });
    if (MERMAID_EDGE_CARD[a + '>' + b]) return withEdges({ kind: 'edge', a, b });
    if (isAncestorOf(a, b)) return withEdges({ kind: 'subsystem', sid: a });
    if (isAncestorOf(b, a)) return withEdges({ kind: 'subsystem', sid: b });
    return null;
  }

  if ((src.kind === 'component' && dst.kind === 'dep')
      || (src.kind === 'dep' && dst.kind === 'component')) {
    const component = src.kind === 'component' ? src : dst;
    const sid = parentOfKind(component, 'subsystem');
    return withEdges(sid ? { kind: 'subsystem', sid } : { kind: 'component' });
  }

  if (src.kind === 'entity' && dst.kind === 'entity') {
    if (!HAS_SUBDOMAINS) return withEdges({ kind: 'domain' });
    const a = topSubdomainOf(srcId), b = topSubdomainOf(dstId);
    if (!a || !b) return null;
    if (a === b) return withEdges({ kind: 'domsub', sd: a });
    if (MERMAID_DOMAIN_EDGE_CARD[a + '>' + b]) return withEdges({ kind: 'domedge', a, b });
    if (isAncestorOf(a, b)) return withEdges({ kind: 'domsub', sd: a });
    if (isAncestorOf(b, a)) return withEdges({ kind: 'domsub', sd: b });
    return null;
  }

  if (src.kind === 'component' && dst.kind === 'entity') {
    const sid = parentOfKind(src, 'subsystem'), sd = topSubdomainOf(dstId);
    if (sid && sd && MERMAID_BRIDGE_CARD[sid + '>' + sd]) {
      return withEdges({ kind: 'bridge', sid, sd });
    }
  }
  return null;
}
function relationshipLocateAction(srcId, dstId) {
  if (!srcId || !dstId) return null;  // actor endpoints have no structural relationship to locate
  // A sequence response commonly points opposite to the structural call it is answering. Prefer an
  // exact directed relationship; only when none exists, locate the reverse pair's stored arrows.
  const direct = COMP_LOOKUP[srcId + '>' + dstId] || [];
  const target = direct.length
    ? relationshipLocateTarget(srcId, dstId)
    : relationshipLocateTarget(dstId, srcId);
  if (!target) return null;
  const tab = stateTitle({ kind: topView(target.kind) });
  return { kind: 'locate', title: 'Locate in ' + tab, run: () => go(target) };
}
function decorateActionIcons(scene, s) {
  const locating = s.kind === 'usecase' && FLOW_VIEW === 'map';
  for (const id in scene.nodeEls) {
    if (scene.noAction.has(id)) continue;  // the box you're already zoomed into — no self-drill icon
    const action = locating ? locateActionFor(id) : primaryActionFor(id);
    if (action) addActionIcon(scene.nodeEls[id], id, action);
  }
}
function clearFocus(scene) {
  for (const nid in scene.nodeEls) { scene.nodeEls[nid].style.opacity = ''; scene.nodeEls[nid].classList.remove('dim'); }
  for (const x of scene.edgeEls) { x.path.style.opacity = ''; if (x.label) x.label.style.opacity = ''; }
  for (const el of scene.dimEls) el.style.opacity = '';
  refreshAllPills();  // un-dimming restores hover-reveal for a box the cursor is still over
}
function resetScene(scene) {  // clear selection + focus, restore the scene's default panel
  selClear(scene);          // tear down every selected element's glow + empty the selection set
  clearFocus(scene);
  panel = PANEL_HOST;
  PANEL_HOST.innerHTML = '';
  scene.defaultPanel();
  highlightTreePath(null);  // drop the file-browser highlight too
  setBrowsing(true);        // nothing selected -> the code slot defaults to the file browser
}

// A click whose pointer moved far from its mousedown is the tail of a drag-pan — ignore it,
// so panning never deselects.
function isDrag(e) { return Math.abs(e.clientX - downX) > 5 || Math.abs(e.clientY - downY) > 5; }
// A ⌥-click (Option / Alt), OR a double-click — a native `click` event's second firing reports
// `detail >= 2`, and svg-pan-zoom's own double-click-to-zoom is disabled (see render()) precisely so
// this gesture is free for the diagram to use — turns a select into a drill-in / open-source. (⌘/⌃ is
// reserved for multi-select — see isMultiSelectClick — so drilling moved to ⌥.) Flashes that node's
// corner icon (if it has one) so double-clicking teaches the icon's meaning even to someone who never
// clicks the icon directly; a direct icon click flashes itself already, so this only needs to cover the
// ⌥-click / double-click paths.
function isDrillClick(e) {
  const drill = !!e && (e.altKey || e.detail >= 2);
  if (drill && e.currentTarget) {
    const id = idOf(e.currentTarget);
    if (id && ACTION_ICONS[id]) flashIcon(ACTION_ICONS[id]);
  }
  return drill;
}
// A ⌘-click (⌃-click off Mac) adds/removes the clicked element from the running multi-selection (Finder /
// spreadsheet muscle memory). A double-click never counts (that drills). Kept separate from isDrillClick so
// the two gestures can never both fire for one event.
function isMultiSelectClick(e) { return !!e && (e.metaKey || e.ctrlKey) && e.detail < 2; }

// --- side panel -----------------------------------------------------------------
// The backward trace for an element: the use cases whose T6 flow steps through it, grouped under their
// capabilities and linked into each flow. A subsystem/subdomain rolls up every descendant's traces,
// so its pane answers for the whole box rather than for an id no flow step normally names directly.
// "Runs in" — the deployment units whose process runs this subsystem / component. ONE row for the
// code→process relation, under the map's own vocabulary (`runs_in`): a component's authored text
// version is dropped server-side when this replaces it, so the unit is never printed twice under two
// labels. The Deployment overview draws one aggregate `runs` arrow (a per-process fan would swamp it),
// so this pane is where placement is actually read — each unit opens its own card. '' when nothing is
// recorded as running this code, which is itself the signal that its `runs_in` tagging is missing.
// "Environments" — which deployment variants a unit belongs to, each with the manifest line that
// grounds it (or `inferred` when the tag cites none). Lives on the process box's pane, and on the dep
// box standing in for an infrastructure unit. Empty `variants` = ungated (present in every
// environment), which the env picker already shows by never filtering it out — so no row.
function variantsPaneHtml(id) {
  const n = GRAPH.nodes[id];
  const v = (n && n.variants) || [];
  if (!v.length) return '';
  return '<dt>Environments</dt><dd>' + variantsCell(v) + '</dd>';
}
function runByHtml(id) {
  const n = GRAPH.nodes[id];
  const units = (n && n.run_by) || [];
  if (!units.length) return '';
  const links = units.map((u) =>
    '<a href="#" class="procref" data-unit="' + esc(u) + '">' + esc(u) + '</a>').join(', ');
  return '<dt>Runs in</dt><dd>' + links + '</dd>';
}
function tracedUseCasesFor(id) {
  const n = GRAPH.nodes[id];
  const out = new Set(USES_BY_NODE[id] || []);
  if (n && (n.kind === 'subsystem' || n.kind === 'subdomain')) {
    for (const eid in USES_BY_NODE) {
      if (isAncestorOf(id, eid)) for (const uc of USES_BY_NODE[eid]) out.add(uc);
    }
  }
  return out;
}
function usedInHtml(id) {
  const n = GRAPH.nodes[id];
  if (!n || !['component', 'subsystem', 'entity', 'subdomain', 'dep'].includes(n.kind)) return '';
  const set = tracedUseCasesFor(id);
  if (!set.size) {
    return HAS_USECASES
      ? '<dt>In use cases</dt><dd><span class="used-none">No traced use case reaches it.</span></dd>'
      : '';
  }
  const link = (uc) => '<a href="#" class="ucref" data-uc="' + esc(uc.id) + '">'
    + esc(uc.name || uc.id) + '</a>';
  const ordered = UC_NODES.filter((uc) => set.has(uc.id));
  if (!HAS_CAPABILITIES) {
    return '<dt>In use cases</dt><dd>' + ordered.map(link).join(', ') + '</dd>';
  }
  const groups = Object.values(GRAPH.nodes || {})
    .filter((x) => x.kind === 'capability')
    .map((cap) => ({ cap, ucs: ordered.filter((uc) => CAP_OF_UC[uc.id] === cap) }))
    .filter((g) => g.ucs.length);
  const loose = ordered.filter((uc) => !CAP_OF_UC[uc.id]);
  if (loose.length) groups.push({ cap: null, ucs: loose });
  const html = groups.map((g) => '<div class="used-cap-group">'
    + '<div class="used-cap-name">' + esc(g.cap ? g.cap.name : 'Other use cases') + '</div>'
    + '<ul class="used-uc-list">' + g.ucs.map((uc) => '<li>' + link(uc) + '</li>').join('')
    + '</ul></div>').join('');
  return '<dt>In use cases</dt><dd class="used-by-cap">' + html + '</dd>';
}
// "How it decides" — the T7 rules this component enforces, on its info pane. Modelled on
// `usedInHtml`: grouped, with an explicit empty state so "this component decides nothing" reads
// differently from "the map has no decision layer". The membership is DERIVED (a rule's site
// resolved through Component.files, server-side) and arrives pre-inverted as `byComponent`; a
// component that shares a file with others appears under EVERY rule sited in it, which is the
// honest answer, not a rendering accident.
function decidesHtml(id) {
  const n = GRAPH.nodes[id];
  if (!HAS_RULES || !n || n.kind !== 'component') return '';
  const ids = ((RULES_VIEW.byComponent || {})[id]) || [];
  if (!ids.length) {
    return '<dt>How it decides</dt><dd><span class="used-none">No business rule is enforced here.</span></dd>';
  }
  const byId = new Map((RULES_VIEW.rules || []).map((r) => [r.id, r]));
  const blockName = new Map((RULES_VIEW.blocks || []).map((b) => [b.id, b.name]));
  const groups = new Map();
  for (const rid of ids) {
    const r = byId.get(rid);
    if (!r) continue;
    const key = r.block || '';
    groups.set(key, (groups.get(key) || []).concat([r]));
  }
  const html = [...groups.entries()].map(([bid, rs]) => '<div class="used-cap-group">'
    + '<div class="used-cap-name">' + esc(blockName.get(bid) || 'Not assigned to a block') + '</div>'
    + '<div class="used-uc-list">' + rs.map((r) =>
        '<a href="#" class="brref" data-blk="' + esc(r.block || '') + '" data-br="' + esc(r.id) + '">'
        + esc(r.statement) + '</a>').join(', ')
    + '</div></div>').join('');
  return '<dt>How it decides</dt><dd class="used-by-cap">' + html + '</dd>';
}
// The "Triggered by" forward view for a component: its T4 entry points — how the outside world reaches
// it (an HTTP route, a CLI command, a cron, an event). Like the arrow/crossing rows, each entry point is
// a SELECTABLE paragraph (no source pill): selecting it highlights the paragraph and — when it has a
// local source — reveals that source in the code viewer (see bindTriggeredBy). '' when none. The same
// entry points also appear (grouped by kind) on the System tab, and a search hit / a System component
// link selects the exact row here (selectEntryPoint).
function triggeredByHtml(id) {
  const n = GRAPH.nodes[id];
  const eps = (n && n.entry_points) || [];
  if (!eps.length) return '';
  const rows = eps.map((e, i) => {
    const self = e.activation === 'self';
    const kind = e.kind ? `<span class="tb-kind${self ? ' tb-kind--self' : ''}">${esc(e.kind)}</span>` : '';
    const trig = e.trigger ? `<span class="tb-trig">${mdInline(e.trigger)}</span>` : '<span class="muted">(entry point)</span>';
    const where = (e.source && localRef(e.source)) ? ` data-where="${esc(e.source)}"` : '';
    return `<li class="tb-ep${self ? ' tb-ep--self' : ''}" data-ep-idx="${i}"${where}>${kind}${trig}</li>`;
  }).join('');
  return `<dt>Triggered by</dt><dd><ul class="tb-list" data-comp="${esc(id)}">${rows}</ul></dd>`;
}
// Wire the "Triggered by" entry-point rows: every row is selectable (click highlights it, like an arrow
// row); a row with a local source also reveals it in the code viewer on select.
function bindTriggeredBy(root) {
  const rows = [...root.querySelectorAll('.tb-list .tb-ep')];
  rows.forEach((li) => li.addEventListener('click', () => {
    rows.forEach((o) => o.classList.remove('sel'));
    li.classList.add('sel');
    if (li.hasAttribute('data-where')) { const wn = whereNode(li.getAttribute('data-where')); openInCodeViewer(wn.file, wn.line); }
  }));
}
// Programmatically select the `epIdx`-th entry point in a component's "Triggered by" pane list — highlight
// the paragraph + reveal its source. Guarded on the owning component id; returns false if that row isn't
// in the pane yet (the pane may still be rendering after a navigation).
function selectTriggeredBy(componentId, epIdx) {
  const list = panel.querySelector(`.tb-list[data-comp="${componentId}"]`);
  const li = list && list.querySelector(`.tb-ep[data-ep-idx="${epIdx}"]`);
  if (!li) return false;
  list.querySelectorAll('.tb-ep').forEach((o) => o.classList.remove('sel'));
  li.classList.add('sel');
  li.scrollIntoView({ block: 'nearest' });
  if (li.hasAttribute('data-where')) { const wn = whereNode(li.getAttribute('data-where')); openInCodeViewer(wn.file, wn.line); }
  return true;
}
// Navigate to a component (showing its pane) AND select one of its entry points — used by the search list
// and the System tab's entry-point rows. The selection is stashed in pendingEpSelect and applied when the
// component's pane renders (bindNodeDetailHandlers → applyPendingEpSelect), which handles both the
// in-place select (pane renders synchronously inside selectFromTree) and the async navigation case.
function selectEntryPoint(componentId, epIdx) {
  pendingEpSelect = { comp: componentId, idx: epIdx };
  selectFromTree(componentId);
}
// Apply a stashed entry-point selection if the just-rendered pane is showing its component; clears the
// stash once applied so it fires exactly once.
function applyPendingEpSelect() {
  if (pendingEpSelect && selectTriggeredBy(pendingEpSelect.comp, pendingEpSelect.idx)) pendingEpSelect = null;
}
// Entity info-pane rows: WHERE it's persisted (the store dep chip + container/mode) and — reusing the
// Data view's C→E derivation — WHO writes and reads it. Every chip (store dep, writer, reader)
// navigates to that element, whose own node carries its source link (the "link every element to its
// code" rule). The "See in Data view" link deep-links to this entity's row in the Data tab.
function persistedInHtml(id) {
  const n = GRAPH.nodes[id];
  // Only for an entity with a PHYSICAL store (store.dep). A not-persisted entity (transient/embedded/
  // in-code) keeps its plain "Stored" text row instead (set server-side), so storage shows exactly once.
  if (!n || n.kind !== 'entity' || !n.store || !n.store.dep) return '';
  const st = n.store; const parts = [];
  if (GRAPH.nodes[st.dep]) parts.push(dvChip(st.dep, GRAPH.nodes[st.dep].name, 'dv-ent'));
  else parts.push(esc(st.dep));
  if (st.container) parts.push(`<span class="dv-coll">${esc(st.container)}</span>`);
  // `collection` is the default mode (a plain table/collection/bucket) — showing it adds no info and
  // reads as Mongo-flavoured to SQL users ("table"), so only surface a mode that says something else.
  if (st.mode && st.mode !== 'collection') parts.push(`<span class="dv-tag">${esc(st.mode)}</span>`);
  if (st.notes) parts.push(`<span class="dv-tag">${esc(st.notes)}</span>`);
  if (!parts.length) return '';
  let dd = parts.join(' ');
  if (HAS_DATA) dd += ` <a href="#" class="dv-seelink" data-store="${esc(st.dep)}" data-entity="${esc(id)}">See in Data view →</a>`;
  return `<dt>Persisted in</dt><dd class="dv-panerow">${dd}</dd>`;
}
function accessRowsHtml(id) {
  const n = GRAPH.nodes[id];
  const a = (DATA_VIEW.access || {})[id];
  if (!n || n.kind !== 'entity' || !a) return '';
  const wl = (a.writers || []).map((c) => dvChip(c.id, c.name, c.owner ? 'dv-write dv-persist' : 'dv-write', c.verb));
  const rl = (a.readers || []).concat(a.other || []).map((c) => dvChip(c.id, c.name, 'dv-read', c.verb));
  let out = '';
  if (wl.length) out += `<dt>Written by</dt><dd class="dv-panerow"><div class="dv-chips">${wl.join('')}</div></dd>`;
  if (rl.length) out += `<dt>Read by</dt><dd class="dv-panerow"><div class="dv-chips">${rl.join('')}</div></dd>`;
  return out;
}
// Datastore/messaging dep info-pane row: a link into the Data tab focused on this store's pane.
function persistedDataLinkHtml(id) {
  if (!dataStoreOf(id)) return '';
  return `<dt>Data</dt><dd class="dv-panerow"><a href="#" class="dv-seelink" data-store="${esc(id)}">`
    + `View persisted data (${esc(dataDrillLabel(id))}) →</a></dd>`;
}
// The one free-text "what/why" field a node kind carries — Purpose (subsystem/subdomain/component),
// Used for (dep), Meaning (entity). Shown as plain prose with no label, since the field IS the
// description (mirrors how showContextEdge/showHPActor treat Wants, and showEdge treats Why).
const EXPLANATION_KEYS = ['purpose', 'used for', 'meaning'];
function explanationKey(fields) {
  for (const want of EXPLANATION_KEYS)
    for (const k in fields)
      if (k.toLowerCase() === want && String(fields[k]).trim()) return k;
  return null;
}
// Fields that would just restate what the diagram already shows for this box: its own name (a
// subsystem's/subdomain's "Subsystem"/"Subdomain" field mirrors the <h2>), which box it nests inside
// (the diagram shows that by literally nesting the box there — see kindPills for why "Kind" drops too).
// A field whose value equals the node's own name (Subsystem/Subdomain/Component/"Name") is dropped
// unconditionally below — no need to list it here too.
const REDUNDANT_FIELD_BY_KIND = {
  subsystem: ['parent'], subdomain: ['parent'],
  component: ['subsystem'], dep: ['kind', 'bucket'],
};
// A derived dependency ROLE → its short display label. The role SET is derived from the dep's incoming
// C→D edge verbs (grammar.dep_roles); a dual-role dep (Redis as bus + store) shows both ('bus', 'store').
const ROLE_LABEL = { datastore: 'store', messaging: 'bus', service: 'service', security: 'crypto' };
// The type pill(s) after a box's title. Every box leads with its element type; a dependency adds a
// pill for its structural Context sub-type (datastore/service/…, the shape/colour the diagram encodes),
// its purpose bucket (Observability/…, the group it clusters into), AND its DERIVED role(s) (bus/store/…
// read off its incoming edge verbs) — the axes at a glance, so the generic "dependency" alone isn't the
// whole story. Kind + bucket drop from the field rows below (shown here); roles are edge-derived, not a field.
//: The reader's word for a node kind where the internal one would leak — the pane's pill is the one
//: place the raw `kind` string reaches the screen.
const KIND_LABEL = { dep: 'dependency', block: 'decision area', rule: 'business rule' };
function kindPills(n) {
  const type = KIND_LABEL[n.kind] || n.kind;
  const sub = n.kind === 'dep' && n.fields ? n.fields.Kind : '';
  const bucket = n.kind === 'dep' && n.fields ? n.fields.Bucket : '';
  const roles = (n.kind === 'dep' && Array.isArray(n.roles)) ? n.roles : [];
  const roleBadges = roles.map((r) =>
    `<span class="badge role" title="derived from this dependency's incoming edge verbs">${esc(ROLE_LABEL[r] || r)}</span>`).join('');
  return `<span class="badge kind">${esc(type)}</span>`
    + (sub ? `<span class="badge kind">${esc(sub)}</span>` : '')
    + (bucket ? `<span class="badge kind">${esc(bucket)}</span>` : '')
    + roleBadges;
}
// A node's full detail as an HTML string (title + tag + explanation + fields + source link) — no DOM
// writes, no handler wiring. Used by showNode to fill the panel with a single element's detail.
function nodeDetailHtml(id) {
  const n = GRAPH.nodes[id];
  if (!n) return '';
  const fields = n.fields || {};
  const chg = n.change ? `<span class="badge ${n.change}">${n.change}</span>` : '';
  const explainKey = explanationKey(fields);
  const explain = explainKey ? `<p class="explain">${mdInline(fields[explainKey])}</p>` : '';
  const dropped = new Set(REDUNDANT_FIELD_BY_KIND[n.kind] || []);
  // an entity's own fields aren't listed here — the class-diagram box already shows them as compartments.
  // A lifecycle renders ONE TRANSITION PER LINE (each carries its own trigger prose, so joined into a
  // single string they read as an unparseable wall); every other field stays inline.
  const lifecycle = (k) => k === 'States' && Array.isArray(n.states_lines) && n.states_lines.length;
  const rows = Object.entries(fields)
    .filter(([k, v]) => k !== explainKey && v !== n.name && !dropped.has(k.toLowerCase()))
    .map(([k, v]) => `<dt>${esc(k)}</dt><dd>` + (lifecycle(k)
      ? `<ul class="st-list">${n.states_lines.map((t) => `<li>${mdInline(t)}</li>`).join('')}</ul>`
      : mdInline(v)) + '</dd>').join('');
  // No source ref in the panel: selecting the node already mirrors its location into the file browser +
  // code viewer, which carry the path and the sole "open externally" control.
  return `<div class="pane-title"><h2>${esc(n.name)}</h2>${kindPills(n)}${chg}</div>`
    + explain
    + `<dl>${rows}${variantsPaneHtml(id)}${runByHtml(id)}${persistedInHtml(id)}${accessRowsHtml(id)}${persistedDataLinkHtml(id)}${usedInHtml(id)}${decidesHtml(id)}${triggeredByHtml(id)}</dl>`
    + impactSectionHtml(id);
}
// Wire the interactive bits inside the just-written detail panel: the use-case-flow refs and the
// selectable "Triggered by" entry-point rows.
function bindNodeDetailHandlers(root) {
  root.querySelectorAll('a.ucref').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault(); go({ kind: 'usecase', uc: a.getAttribute('data-uc') });
  }));
  // "Runs in": each unit opens its own process card, the same target its box drills to.
  root.querySelectorAll('a.procref').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault(); go({ kind: 'deploymentUnit', unit: a.getAttribute('data-unit') });
  }));
  // "How it decides" / a flow step's rules: deep-link into the Business logic tab, focused on the
  // rule's block pane and scrolled to the rule.
  root.querySelectorAll('a.brref').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault();
    go({ kind: 'rules', blk: a.getAttribute('data-blk') || 'none', br: a.getAttribute('data-br') });
  }));
  // Data-view rows in the panel: element chips navigate; the "See in Data view" / "View persisted
  // data" links deep-link into the Data tab focused on a store pane (and, for an entity, its row).
  root.querySelectorAll('.dv-chip[data-id]').forEach((b) =>
    b.addEventListener('click', () => selectFromTree(b.getAttribute('data-id'))));
  root.querySelectorAll('a.dv-seelink').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault();
    const st = { kind: 'data', store: a.getAttribute('data-store') };
    if (a.getAttribute('data-entity')) st.entity = a.getAttribute('data-entity');
    go(st);
  }));
  bindTriggeredBy(root);
  bindImpactSection(root);
  applyPendingEpSelect();  // a search hit / System link asked to select one of this component's entry points
}
function showNode(id) {
  if (!GRAPH.nodes[id]) return;
  panel.innerHTML = nodeDetailHtml(id);
  bindNodeDetailHandlers(panel);
  // Source buttons in the pane need binding too. `bindNodeDetailHandlers` wires the navigation
  // links (use case / process / data chips) but not `.srclink`, and this is the ONE panel builder
  // that never made the second call — so the Environments row rendered its manifest anchors as
  // buttons that did nothing. Every other srclink in the app sits on a path that wires them.
  // Mirror into the file browser here (not just in selectNode) — showNode is also how a subsystem's/
  // subdomain's OWN card lands on its default panel (applyDefaultPanel) and how a bridge arrow shows its
  // collapsed box (bindBridgeEdge), neither of which went through selectNode before.
  syncTreeToNode(id);
}
// Every node selection shows exactly that one element's detail — never a stacked list. When the element's
// file also anchors OTHER elements (a node_path_index collision — filetree.py), they aren't crammed into
// the panel: the code viewer tags each one on its own source line instead (anchorsByPath / paintCodeTags),
// so "selecting a box" reads as "here's this one element", and its file-mates are discoverable in the code.
function showNodeDetailSynced(id) {
  if (isDeploymentGroup(id)) { showDeploymentGroup(id); return; }
  showNode(id);          // fills the panel with `id` alone and mirrors into the tree + code viewer (syncTreeToNode)
  updateFolderPeek(id);  // auto-opens browsing for a folder element (see updateFolderPeek)
}

// One arrow's detail BODY: the from→to pair + a why line, with the structured relation facts
// (cardinality / implemented-by / keyed-by) beneath. Shared by the concrete-arrow card (showEdge — as bare
// card content, no bullet/selected-row bar) and the arrow-LIST rows (edgeRowHtml / showPairEdges).
function edgeRowInner(e) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  // domain relations carry a kind (composition/…) + cardinality; component edges carry why/where. The
  // verb + kind ride in the row's why line (or the Verb fact row); cardinality/impl/keyed sit below.
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
  // A storage/lookup key the store imposes to relate the two — NOT a field on the row (so it's shown
  // apart from "Implemented by", with the «key» marker and an explicit note).
  const keyed = e.keyed_by || [];
  const keyedRow = keyed.length
    ? '<dt>Keyed by</dt><dd>«key» ' + esc(keyed.join(', '))
      + ' <span class="muted">(storage key, not a row field)</span></dd>'
    : '';
  // Present the arrow like a SELECTED crossings-list row (the from→to pair + a why/verb line), then the
  // structured relation facts beneath — so selecting an arrow directly reads the same as picking it from
  // an arrow list. The why line mirrors each list's convention: an explanation when there is one, else
  // the verb (+ kind). The verb goes to a `dl` row when the explanation already fills the why line, so
  // it is never lost. The row itself is an inert arrow row (see arrowRow — no code link by design).
  // The why line mirrors each list's convention exactly: a component arrow shows its explanation and NO
  // verb (like the connections list); a domain relation shows `verb (kind)` (like the relations list).
  // The verb is not repeated as a fact — only cardinality / implemented-by / keyed-by hang below (the
  // richer relation detail a bare list row doesn't carry).
  const kindTag = e.kind ? ' <span class="muted">(' + esc(e.kind) + ')</span>' : '';
  const whyLine = e.why ? mdInline(e.why) : (e.verb ? esc(e.verb) + kindTag : '');
  const facts = card + implRow + keyedRow;
  return arrowRowInner(nm(e.src), nm(e.dst), whyLine,
                       facts ? '<dl class="xfacts">' + facts + '</dl>' : '');
}
// The arrow as a LIST row (a parallel-pair list); the concrete-arrow card uses edgeRowInner directly.
function edgeRowHtml(e, sel) {
  return '<li class="xrow' + (sel ? ' sel' : '') + '">' + edgeRowInner(e) + '</li>';
}
// Selecting an arrow shows its relationship facts ONLY. An arrow deliberately does NOT point at code:
// its `where` is an example call site (a witness kept for validation/impact/drift), never THE location
// of the interaction — so there is no source link, the code viewer is left untouched, and the tree
// highlight is cleared so a previous selection's path can't read as this arrow's location.
function showEdge(e) {
  // A concrete arrow is now its own selection card, so it renders as bare card content — no list bullet,
  // no selected-row side bar (the card frames it). List views (parallel pairs, crossings) still use rows.
  panel.innerHTML = '<div class="xarrow">' + edgeRowInner(e) + '</div>';
  cvElement = null;  // an edge has no single owning element -> no header pill
  setTreeSelection(null);  // clear pill emphasis + selection pills
  highlightTreePath(null);
}
// A drawn arrow names only its endpoint PAIR; with parallel edges (same pair, different verbs) the
// SVG carries no index to pick one, so selecting the arrow lists EVERY edge of the pair instead of
// silently showing the first. A single-edge pair reads exactly like a plain showEdge.
function showPairEdges(arr) {
  if (arr.length === 1) { showEdge(arr[0]); return; }
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  const e0 = arr[0];
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(nm(e0.src)) + ' → ' + esc(nm(e0.dst)) + '</h2>'
    + '<span class="badge edge">' + arr.length + ' relations</span></div>'
    + '<ul class="xlist">' + arr.map((e) => edgeRowHtml(e, false)).join('') + '</ul>';
  cvElement = null;
  setTreeSelection(null);
  highlightTreePath(null);
}

// Context-edge panel: actor→system shows the role's wants; system→dep shows what it's used for
// and the component edges (with their Why) that realize the dependency.
function showContextEdge(ce) {
  if (ce.type === 'libs') { showLibsFold(); return; }  // SYS→Libraries arrow: same roster panel as the box
  if (ce.type === 'bucketfold') { showBucketFold(ce.dst); return; }  // SYS→bucket arrow: same roster panel as the box
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
  panel.innerHTML = '<div class="pane-title"><h2>Libraries</h2><span class="badge kind">libraries</span></div>'
    + '<p class="empty">Frameworks &amp; libraries linked into the process — folded out of the Context view. ⌥-click to drill in.</p>'
    + (items ? '<dl><dt>Bundled (' + FOLDED_LIBS.length + ' in-process)</dt>' + items + '</dl>' : '');
}

// A folded big-bucket count box (external systems sharing one purpose, collapsed at the Context
// altitude so an integration-heavy map stays legible). Same at-a-glance roster as the Libraries fold;
// drilling the box (⌘-click) is where each member selects to its own details.
function bucketFoldOf(bkid) { return (FOLDED_BUCKETS || []).find((b) => b.id === bkid) || null; }
function bucketFoldName(bkid) { const b = bucketFoldOf(bkid); return b ? b.name : bkid; }
// Which view a bucket fold drills OUT of: a library bucket sits inside the Libraries drill, an external
// one directly under Context — so back / breadcrumbs land one extra level up for library buckets.
function bucketFoldParent(bkid) { const b = bucketFoldOf(bkid); return b && b.parent ? b.parent : 'context'; }
function showBucketFold(bkid) {
  const b = bucketFoldOf(bkid);
  if (!b) { panel.innerHTML = EMPTY_PANEL; return; }
  const items = b.members.map((m) => '<dd>• ' + esc(m.name) + '</dd>').join('');
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(b.name) + '</h2><span class="badge kind">bucket</span></div>'
    + '<p class="empty">External systems grouped by purpose — folded out of the Context view. ⌥-click to drill in.</p>'
    + (items ? '<dl><dt>' + b.count + ' dependencies</dt>' + items + '</dl>' : '');
}
// Select a folded-bucket count box: roster panel + dim to its neighbourhood (SYS + the arrow), exactly
// like selecting the Libraries fold. Reuses the node selKey so the hover guard matches.
function bucketFoldDesc(scene, el, bkid) {
  return { key: 'node:' + bkid, glow: (reveal) => glowNode(el, reveal),
           focus: nodeFocus(scene, bkid), show: () => showBucketFold(bkid) };
}
function selectBucketFold(scene, el, bkid) { selReplace(scene, bucketFoldDesc(scene, el, bkid)); }
// Tag every folded-bucket box with the drill cursor (⌘-drills into its members), like subsystem boxes.
function markBucketFoldDrill() {
  (FOLDED_BUCKETS || []).forEach((b) => { const el = mainScene.nodeEls[b.id]; if (el) el.classList.add('drill'); });
}
// The bucket drill-down: the System + that one bucket's members, same shape as Context — each simply
// selects to its panel (no further drill); arrows resolve via the context-edge bridge.
function bindBucketFold() {
  bindNodes(mainScene, (id, el, e) => {
    if (tryDataDrillClick(id, e)) return;
    selectNodeFromCanvas(el, id, e);
  });
  bindEdges(mainScene, resolveContextEdge);
  markDataDrill();
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
// The bridge-card default panel — the subsystem and subdomain being framed (the structure↔domain pair).
function showBridge(sid, sd) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(nm(sid)) + ' → ' + esc(nm(sd)) + '</h2>'
    + '<span class="badge edge">bridge</span></div>'
    + subsystemBlock(sid) + '<hr>' + subsystemBlock(sd);
}
// One crossings-list row: the from→to pair + a why line. INERT text by design: an arrow's `where` is
// only an EXAMPLE call site (a witness among possibly many), so rows deliberately do NOT link to code —
// no click, no hover glow — to never present the example as "the" location of the interaction. Precise
// anchors (element sources, flow-step `where`) keep their code links elsewhere. `sel` renders the
// single-arrow view's own row (showEdge) in the selected state.
function arrowRowInner(srcName, dstName, whyHtml, extra) {
  return '<div class="xpair">' + esc(srcName) + ' → ' + esc(dstName) + ':</div>'
    + (whyHtml ? '<div class="xwhy">' + whyHtml + '</div>' : '') + (extra || '');
}
function arrowRow(srcName, dstName, whyHtml, sel, extra) {
  return '<li class="xrow' + (sel ? ' sel' : '') + '">' + arrowRowInner(srcName, dstName, whyHtml, extra) + '</li>';
}
// Selecting (not drilling) a Subsystems arrow: list every component→component crossing it bundles as
// `from → to:` with its explanation (and a link to its call site) indented below — one uniform font, no
// verb — so the wiring is readable without leaving the map.
// The crossing component→component edges an inter-subsystem arrow bundles — CONTAINER_EDGES[a>b],
// narrowed to a member component's own crossings when the DRAWN arrow ends on one (a subsystem card's
// member arrow; in the Subsystems overview both ends are subsystems, so nothing is filtered). Shared by
// showContainerEdge (the panel list) AND the drill (which pre-selects exactly these arrows in the edge card).
function containerEdgeList(a, b, drawn) {
  let list = CONTAINER_EDGES[a + '>' + b] || [];
  const isComp = (id) => GRAPH.nodes[id] && GRAPH.nodes[id].kind === 'component';
  const srcC = drawn && isComp(drawn.src) ? drawn.src : null;
  const dstC = drawn && isComp(drawn.dst) ? drawn.dst : null;
  if (srcC) list = list.filter((r) => r.src === srcC);
  if (dstC) list = list.filter((r) => r.dst === dstC);
  return list;
}
// The entity→entity relations an inter-subdomain arrow bundles — the domain analog of containerEdgeList.
function domainContainerEdgeList(a, b, drawn) {
  let list = DOMAIN_CONTAINER_EDGES[a + '>' + b] || [];
  const isEnt = (id) => GRAPH.nodes[id] && GRAPH.nodes[id].kind === 'entity';
  const srcE = drawn && isEnt(drawn.src) ? drawn.src : null;
  const dstE = drawn && isEnt(drawn.dst) ? drawn.dst : null;
  if (srcE) list = list.filter((r) => r.src === srcE);
  if (dstE) list = list.filter((r) => r.dst === dstE);
  return list;
}
// The underlying links a synthetic arrow bundles, as endpoint atoms {src, dst}. Carried on the drill state
// (`selCover`) and resolved AFTER the target card renders — see coverKeys — so we select whatever arrows the
// card actually drew for these links, at whatever grouping level it chose, instead of predicting keys.
function bundleAtoms(list) {
  const seen = new Set(); const atoms = [];
  for (const r of list) { const k = r.src + '>' + r.dst; if (!seen.has(k)) { seen.add(k); atoms.push({ src: r.src, dst: r.dst }); } }
  return atoms;
}
function showContainerEdge(a, b, drawn) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  const list = containerEdgeList(a, b, drawn);
  const items = list.map((r) => arrowRow(r.srcName, r.dstName, r.why ? mdInline(r.why) : '')).join('');
  const headA = drawn ? drawn.src : a, headB = drawn ? drawn.dst : b;
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(nm(headA)) + ' → ' + esc(nm(headB)) + '</h2>'
    + '<span class="badge edge">connections</span></div>'
    + '<div class="xcount">' + list.length + ' connection' + (list.length === 1 ? '' : 's') + '</div>'
    + (items ? '<ul class="xlist">' + items + '</ul>' : '<p class="empty">no connections recorded</p>');
}
// Selecting an inter-subdomain arrow (Domain overview): list every entity→entity relation it bundles as
// `from → to:` with its verb (+ kind) below — the domain analog of showContainerEdge.
function showDomainContainerEdge(a, b, drawn) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  const list = domainContainerEdgeList(a, b, drawn);
  const items = list.map((r) => arrowRow(r.srcName, r.dstName,
    esc(r.verb) + (r.kind ? ' <span class="muted">(' + esc(r.kind) + ')</span>' : ''))).join('');
  const headA = drawn ? drawn.src : a, headB = drawn ? drawn.dst : b;
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(nm(headA)) + ' → ' + esc(nm(headB)) + '</h2>'
    + '<span class="badge edge">relations</span></div>'
    + '<div class="xcount">' + list.length + ' relation' + (list.length === 1 ? '' : 's') + '</div>'
    + (items ? '<ul class="xlist">' + items + '</ul>' : '<p class="empty">no relations recorded</p>');
}
// Selecting a BRIDGE arrow (structure↔domain): the component↔subdomain arrow in a subsystem card, or the
// subsystem↔entity arrow in a subdomain/domain view. It bundles component→entity edges; list each as
// `component → entity:` with its verb, explanation, and call-site link — the bridge analog of
// showContainerEdge. BRIDGE_EDGES is one flat list of every C→E edge; narrow it to the arrow's drawn
// endpoints by KIND (component→src, entity→dst, subsystem→sub, subdomain→sd), which covers both arrow
// orientations, so the panel count matches the arrow's label.
// The component→entity edges a bridge arrow bundles — BRIDGE_EDGES narrowed to the arrow's drawn endpoints
// by KIND (a leaf end matches its own id; a group end matches any atom in its subtree, at any nesting
// level). Shared by showBridgeEdge (the panel list) AND the drill (which pre-selects these C→E arrows in
// the bridge card, where each is keyed 'edge:component>entity' just like a component edge — see bindDomain).
function bridgeEdgeList(drawn) {
  const ends = [drawn.src, drawn.dst];
  return (BRIDGE_EDGES || []).filter((r) => ends.every((id) => {
    const k = GRAPH.nodes[id] && GRAPH.nodes[id].kind;
    return k === 'component' ? r.src === id
      : k === 'entity' ? r.dst === id
        : k === 'subsystem' ? isAncestorOf(id, r.src)
          : k === 'subdomain' ? isAncestorOf(id, r.dst)
            : true;
  }));
}
function showBridgeEdge(drawn) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  const list = bridgeEdgeList(drawn);
  const items = list.map((r) => arrowRow(r.srcName, r.dstName,
    esc(r.verb) + (r.why ? ' — ' + mdInline(r.why) : ''))).join('');
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(nm(drawn.src)) + ' → ' + esc(nm(drawn.dst)) + '</h2>'
    + '<span class="badge edge">bridge</span></div>'
    + '<div class="xcount">' + list.length + ' link' + (list.length === 1 ? '' : 's') + '</div>'
    + (items ? '<ul class="xlist">' + items + '</ul>' : '<p class="empty">no links recorded</p>');
}

// --- Happy Path + use-case panels -----------------------------------------------
// Wire an element link inside a flow-step panel: a click locates that node in its home view (its
// subsystem card, domain card, etc.) and selects it — the same routing the file browser uses.
function bindFlowRefs() {
  panel.querySelectorAll('a.flowref').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault();
    selectFromTree(a.getAttribute('data-id'));
  }));
}
// The use case's OUTSIDE view — the SAME facts the Use Cases list shows for it: its name, its actor,
// and its trigger → outcome. Shown when a Happy Path step/use case is SELECTED (not drilled); the full
// T6 flow (the inside view) stays behind the drill and on the Use Cases tab.
function showUseCaseSummary(uc) {
  const n = uc ? GRAPH.nodes[uc] : null;
  if (!n) { panel.innerHTML = EMPTY_PANEL; return; }
  const f = n.fields || {};
  const actor = f.Actor || '';
  const to = f['Trigger → Outcome'] || '';
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(n.name) + '</h2>'
    + '<span class="badge kind">use case</span>'
    + (actor ? '<span class="badge edge">' + esc(actor) + '</span>' : '') + '</div>'
    + (to ? '<p class="explain">' + mdInline(to) + '</p>' : '');
}
// Selecting a Happy Path step (plain click on the overview) shows that use case's summary — the same
// facts as its row in the Use Cases list. The mechanism (T6 flow) is behind the drill.
function showHPArrow(hpId) {
  const s = HP_BY_ID[hpId];
  showUseCaseSummary(s ? s.uc : null);
}
// The use-case flow view's default panel. Reached by drilling a use case (from the Use Cases list or a
// Happy Path step). The sequence diagram IS the flow; the panel shows the same outside summary as a
// plain selection, so it doesn't repeat every arrow the diagram already draws. A step's own detail
// opens when that step is clicked in the diagram.
function showUseCase(uc) {
  showUseCaseSummary(uc);
}
// The use-case flow view is a sequence diagram — wire it like every other diagram, using
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
// `texts` and `lines` are both in document order — the i-th label pairs with the i-th arrow (see the
// callers on why positional, not id-keyed).
function leftAlignMessageLabels(texts, lines) {
  texts.forEach((text, i) => {
    const line = lines[i];
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

  // messages: the i-th label (text[i]) + the i-th arrow (line[i]) pair with steps[i] — same pairing as
  // bindHP. Pair POSITIONALLY (document order), NOT by Mermaid's `data-id="i<n>"`: that <n> is a global
  // element counter that also advances for every sub-flow `rect` and its naming `Note`, so once the first
  // sub-box appears the arrow ids develop gaps (…i4, i7, i8…) and an id-keyed lookup would slide every
  // later label onto the wrong arrow's column. Notes/rects emit no `.messageText`/`.messageLine`, so the
  // DOM order of these two selectors is exactly the message order.
  const texts = [...root.querySelectorAll('text.messageText')];
  const lines = [...root.querySelectorAll('.messageLine0, .messageLine1')];
  leftAlignMessageLabels(texts, lines);
  scene.focusUnion = focusUnionEls;  // this is a sequence diagram — union selections dim by DOM-part set
  const msgEls = steps.map((_, i) => [texts[i], lines[i]].filter(Boolean));
  for (const els of msgEls) for (const el of els) scene.dimEls.push(el);

  // element participants: select (focus to its messages + their other ends) / ⌥-open source / tooltip.
  for (const id of Object.keys(partsById)) {
    const parts = partsById[id], selKey = 'node:' + id;
    const myMsg = steps.map((st, i) => (st.srcId === id || st.dstId === id) ? i : -1).filter((i) => i >= 0);
    const stepEls = myMsg.flatMap((i) => msgEls[i] || []);
    const glowEls = [...parts, ...stepEls];
    const keep = new Set(glowEls);
    for (const i of myMsg) for (const nb of [steps[i].srcId, steps[i].dstId]) for (const el of (partsById[nb] || [])) keep.add(el);
    const desc = { key: selKey, glow: () => hpHighlight(scene, glowEls, false),
                   focus: { els: keep }, show: () => showNode(id) };
    scene.selectors[selKey] = () => selAdd(scene, desc);  // so back/forward can restore this participant selection
    const on = () => { if (!selHas(scene, selKey)) for (const el of parts) el.style.filter = HOVER; };
    const off = () => { if (!selHas(scene, selKey)) for (const el of parts) el.style.filter = hpRestFilter(scene, el); };
    for (const el of parts) {
      el.style.cursor = 'pointer';
      markOpenSrc(el, id);  // </> cursor on a component/entity leaf with a source ref, like the other diagrams
      el.addEventListener('mouseenter', on);
      el.addEventListener('mouseleave', off);
      attachTip(el, () => actionTipNode(id));  // ⌥-hover shows the open-source action
      el.addEventListener('click', (e) => {
        if (isDrag(e)) return;
        e.stopPropagation();
        if (openSrcClick(id, e)) return;  // ⌥-click opens source (component/entity), consistent with the rest
        if (e.shiftKey) { frameArrow(parts[0]); return; }  // shift-click is a pure camera move — frame the participant, never select
        pickSel(scene, desc, e);  // ⌘-click toggles into the multi-selection, a plain click replaces
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
    styleSeqActor(root, a.aid, a.kind);  // same person/service vocabulary as the Happy Path and Dependencies
    for (const el of parts) scene.dimEls.push(el);
    for (const i of a.stepIdx) (actorPartsByStep[i] || (actorPartsByStep[i] = [])).push(...parts);
    const stepEls = a.stepIdx.flatMap((i) => msgEls[i] || []);
    const glowEls = [...parts, ...stepEls];
    const keep = new Set(glowEls);
    for (const i of a.stepIdx) for (const nb of [steps[i].srcId, steps[i].dstId]) for (const el of (partsById[nb] || [])) keep.add(el);
    const desc = { key: selKey, glow: () => hpHighlight(scene, glowEls, false),
                   focus: { els: keep }, show: () => showFlowActor(uc, a) };
    scene.selectors[selKey] = () => selAdd(scene, desc);
    const on = () => { if (!selHas(scene, selKey)) for (const el of parts) el.style.filter = HOVER; };
    const off = () => { if (!selHas(scene, selKey)) for (const el of parts) el.style.filter = hpRestFilter(scene, el); };
    const click = (e) => { if (isDrag(e)) return; e.stopPropagation();
      if (e.shiftKey) { frameArrow(parts[0]); return; }  // shift-click frames the actor, never selects
      pickSel(scene, desc, e); };
    for (const el of parts) {
      if (el.tagName === 'line') continue;  // the lifeline gets a fat transparent hit (below)
      el.style.cursor = 'pointer';
      el.addEventListener('click', click);
      el.addEventListener('mouseenter', on);
      el.addEventListener('mouseleave', off);
    }
    if (life) attachEdgeHandlers(life, null, click, on, off, null);
  }

  // messages: select (the step's OWN panel — showFlowStep grounds it via the step's `where`) / locate
  // the backbone relationship from the arrow's action / focus / tooltip (the why). A step's arrow +
  // label glow together; focus keeps them + both endpoints' columns.
  steps.forEach((st, i) => {
    const els = msgEls[i];
    if (!els.length) return;
    const text = texts[i] || null, line = lines[i] || null;
    const selKey = 'flowstep:' + uc + ':' + i;
    const keep = new Set(els);
    for (const end of [st.srcId, st.dstId]) for (const el of (partsById[end] || [])) keep.add(el);
    for (const el of (actorPartsByStep[i] || [])) keep.add(el);  // Role endpoints have no node id
    const desc = { key: selKey,
                   glow: (reveal) => hpHighlight(scene, els, reveal),
                   focus: { els: keep },
                   show: () => { flowSyncCur(i); showFlowStep(uc, i); } };
    scene.selectors[selKey] = () => selAdd(scene, desc);  // so back/forward + the step player can restore this flow-step selection
    const onClick = (ev) => {
      if (isDrag(ev)) return;
      ev.stopPropagation();
      if (ev.shiftKey) { frameArrow(line || text); return; }  // shift-click is a pure camera move — frame, no select, no counter move
      flowSyncCur(i);  // clicking a step's arrow directly moves the player's counter to it
      pickSel(scene, desc, ev);  // ⌘-click toggles into the multi-selection, a plain click replaces
    };
    const on = () => { if (!selHas(scene, selKey)) for (const el of els) el.style.filter = HOVER; };
    const off = () => { if (!selHas(scene, selKey)) for (const el of els) el.style.filter = hpRestFilter(scene, el); };
    const locate = relationshipLocateAction(st.srcId, st.dstId);
    if (line) attachEdgeHandlers(line, text, onClick, on, off, null, null,
      () => selRevealsAction(scene, selKey), locate);
    else {
      text.style.cursor = 'pointer'; text.style.setProperty('pointer-events', 'all', 'important');
      if (locate) {
        addLabelActionIcon(text, 'flowloc:' + uc + ':' + i, locate);
        const icon = text._actionIcon;
        const showLocate = () => showIcon(icon);
        const hideLocate = () => {
          if (!selRevealsAction(scene, selKey)) hideIcon(icon);
        };
        text.addEventListener('mouseenter', showLocate);
        text.addEventListener('mouseleave', hideLocate);
        icon.addEventListener('mouseenter', showLocate);
        icon.addEventListener('mouseleave', hideLocate);
        if (icon._bridge) {
          icon._bridge.addEventListener('mouseenter', showLocate);
          icon._bridge.addEventListener('mouseleave', hideLocate);
        }
      }
      text.addEventListener('click', onClick); text.addEventListener('mouseenter', on); text.addEventListener('mouseleave', off);
    }
  });

  // Hand the step player everything it needs to walk this flow: the ordered steps, each step's arrow+label
  // DOM (msgEls) and its endpoint columns (partsById). A fresh visit is inactive with no remembered step;
  // its first Next lands on step 1. No flow -> null, so the strip stays hidden.
  flowPlay = steps.length
    ? { uc, kind: 'sequence', steps, msgEls, partsById, cur: -1, active: false }
    : null;
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
  // Preferred target: the arrow + its label (full extent) plus both endpoints. What an "endpoint" is
  // depends on the rendering: a sequence lifeline is a tall column, so only its x matters (including its
  // full height would always overflow); a map endpoint is a box, which is exactly what should be in view.
  const map = flowPlay.kind === 'map';
  const items = els.map((el) => ({ el, xOnly: false }));
  // On the map an actor endpoint is a drawn box like any other, so it is addressed by its `FAn` alias;
  // in the sequence view actor parts live outside partsById (see bindFlow), so only element ids apply.
  const ends = map
    ? [flowMapBoxId(flowPlay.uc, st.srcId, st.src), flowMapBoxId(flowPlay.uc, st.dstId, st.dst)]
    : [st.srcId, st.dstId];
  for (const end of ends)
    for (const el of (flowPlay.partsById[end] || []))
      if (map) items.push({ el, xOnly: false });
      else if (el.tagName === 'line') items.push({ el, xOnly: true });
  let box = flowRect(items);
  if (!box) return;
  if (box.r - box.l > d.width || box.b - box.t > d.height) {   // too big to show in full -> just the label
    // The label carries the step number, so it is the one part worth keeping when the whole target
    // cannot fit. Mermaid names it differently per diagram type: `messageText` in a sequence diagram,
    // `edgeLabel` in a flowchart.
    const label = els.find((e) => e.classList
      && (e.classList.contains('messageText') || e.classList.contains('edgeLabel')));
    box = label ? flowRect([{ el: label, xOnly: false }]) : null;
    if (!box || box.r - box.l > d.width || box.b - box.t > d.height) return;  // even the label can't fit
  }
  let dx = 0, dy = 0;
  if (box.l < d.left) dx = d.left - box.l; else if (box.r > d.right) dx = d.right - box.r;
  if (box.t < d.top) dy = d.top - box.t; else if (box.b > d.bottom) dy = d.bottom - box.b;
  if (!dx && !dy) return;   // already fully visible -> stay put
  flowAnimatePanBy(dx, dy);
}
// `cur` remembers the last step reached during THIS visit; `active` says whether that step is selected
// now. Inactive shows an honest dash, disables Previous and leaves Next available. With no remembered
// step Next starts at 1; after a deselection it resumes the remembered step. Once active, stepping wraps.
function flowCounter() {
  if (!flowPlay) return;
  const n = flowPlay.steps.length, i = flowPlay.cur, active = flowPlay.active;
  flowcount.textContent = 'Step ' + (active ? i + 1 : '\u2013') + ' / ' + n;
  flowprev.disabled = !active;
  flownext.disabled = false;
  // Grey (but still clickable) at the ends: Prev on step 1, Next on the last step — the old end-of-list look.
  flowprev.classList.toggle('flowend', !active || i <= 0);
  flownext.classList.toggle('flowend', active && i >= n - 1);
}
// The step number is view state, just like selection and camera position. `active` distinguishes a
// selected step from a suspended player that only remembers where Next should resume.
function flowSnapshot() {
  return flowPlay ? { cur: flowPlay.cur, active: flowPlay.active } : null;
}
function restoreFlowSnapshot(saved) {
  if (!flowPlay || !saved) return false;
  const i = Number(saved.cur);
  if (!Number.isInteger(i) || i < -1 || i >= flowPlay.steps.length) return false;
  flowPlay.cur = i;
  flowPlay.active = !!saved.active && i >= 0;
  flowCounter();
  flowMapRefreshStepLabels();
  return true;
}
// Move the counter to step i without re-highlighting — used when a click on the arrow already selected it.
function flowSyncCur(i) {
  if (!flowPlay) return;
  flowPlay.cur = i;
  flowPlay.active = true;
  flowCounter();
  flowMapRefreshStepLabels();
}
// Selection is what makes the remembered step active. Clearing the canvas, pressing Escape, selecting
// another element or toggling the step off suspends the player but deliberately retains `cur`, so Next
// can restore that exact step's selection, pane, source and framing.
function flowSuspend() {
  if (!flowPlay || !flowPlay.active) return;
  flowPlay.active = false;
  flowCounter();
}
function flowSuspendIfDeselected(scene) {
  if (!flowPlay || !flowPlay.active || scene !== mainScene) return;
  const stepKey = 'flowstep:' + flowPlay.uc + ':' + flowPlay.cur;
  const pairPrefix = 'flowpair:' + flowPlay.uc + ':';
  const selected = scene.selKeys.has(stepKey)
    || [...scene.selKeys].some((key) => key.startsWith(pairPrefix));
  if (!selected) flowSuspend();
}
// Go to step i: select its arrow exactly as a manual click would (same info pane, code viewer, glow and
// focus — via the step's registered selector), then scroll it into view if needed. Delegating to the click
// selector keeps stepping and clicking in sync by design.
function flowGoto(i) {
  if (!flowPlay || !flowPlay.steps.length) return;
  const n = flowPlay.steps.length;
  i = Math.max(0, Math.min(n - 1, i));
  flowPlay.cur = i;
  flowPlay.active = true;  // the player walks one step at a time -> REPLACE the selection with this step
  const sel = mainScene.selectors['flowstep:' + flowPlay.uc + ':' + i];
  // selClear + selAdd = a single-step selection (not additive). A step with NO selector — a rendering
  // that could not draw this step's arrow — resets the scene INSTEAD: landing on step n while the
  // previous step's arrow is lit, the diagram is dimmed to its neighbourhood and its card is open
  // would read as "this is step n" about the wrong step. `selClear` alone would only drop the glow and
  // leave both of the others standing, so it takes the full reset (glow + focus + panel) to make the
  // absence honest.
  if (sel) { selClear(mainScene); sel(); }
  else resetScene(mainScene);
  flowReveal(flowPlay.msgEls[i] || [], i);
  flowCounter();
}
// Inactive: Previous does nothing; Next resumes the remembered step, or starts at step 1 on a fresh visit.
// Active: step by +/-1 and wrap around the ends.
function flowStepBy(d) {
  if (!flowPlay) return;
  const n = flowPlay.steps.length;
  if (!flowPlay.active) { if (d > 0) flowGoto(flowPlay.cur >= 0 ? flowPlay.cur : 0); return; }
  flowGoto((flowPlay.cur + d + n) % n);
}
// Called from render() once svg-pan-zoom exists. Shows the strip. A back/forward revisit that restored a
// selected step starts there; a fresh drill is inactive with no memory, so its first Next selects step 1.
// A Map/Sequence switch is not a fresh drill: it preserves both the remembered index and active state.
function flowInit(s) {
  const switched = flowResume;
  flowResume = null;   // consumed either way: a pending resume must never outlive the render it was set for
  if (!flowPlay || !flowPlay.steps.length) { flowplayer.hidden = true; return; }
  flowplayer.hidden = false;
  const m = (mainScene.selectedKey || '').match(/^flowstep:.*:(\d+)$/);
  flowPlay.cur = m ? +m[1] : -1;
  flowPlay.active = !!m;
  // A rendering switch carries the live state directly. Otherwise use the history point's snapshot,
  // which restores selected and suspended step numbers alike after Back/Forward navigation.
  const saved = switched || (s && s.flow);
  if (restoreFlowSnapshot(saved)) {
    if (switched && flowPlay.active) { flowGoto(flowPlay.cur); return; }
    return;
  }
  flowCounter();
}
// One flow step's complete information. The sequence message and a single-step map arrow render this
// verbatim; a bundled map arrow reuses it once per carried step, adding only a Step N badge.
function flowStepInfoHtml(uc, i, numbered) {
  const st = (FLOWS_NARR[uc] || [])[i];
  if (!st) return EMPTY_PANEL;
  const wn = st.where ? whereNode(st.where) : null;
  const local = !!(wn && localRef(wn.file));
  const srcRow = st.where
    ? '<dl><dt>Source</dt><dd>' + (local
        ? '<a href="#" class="stepwhere">' + esc(st.where) + '</a>' : esc(st.where)) + '</dd></dl>'
    : '';
  // The step's action is the title (a full sentence for actor steps — too long for a pill). Its arrow
  // owns structural navigation, so the pane stays focused on the step's authored facts and call site.
  const stepBadge = numbered ? '<span class="badge edge">Step ' + (i + 1) + '</span>' : '';
  return '<div class="pane-title"><h2>' + (st.verb ? mdInline(st.verb) : 'Step') + '</h2>' + stepBadge + '</div>'
    + (st.sf ? '<dl><dt>Part of sub-flow</dt><dd>&#10216;' + esc(st.sfName || st.sf)
       + '&#10217; <span class="muted">(' + esc(st.sf) + ' — a shared sequence this flow includes)</span></dd></dl>' : '')
    + (st.why ? '<p class="explain">' + mdInline(st.why) + '</p>' : '')
    + (st.note ? '<dl><dt>Note</dt><dd>' + mdInline(st.note) + '</dd></dl>' : '')
    + srcRow
    + stepRulesHtml(uc, st);
}
// The T7 rules enforced at THIS step. Keyed by `(use case, authoring container, n)` — a step's `n`
// is unique per container, never per use case, so a sub-flow's step 2 and the flow's own step 2 are
// two different rows and keying on `(uc, n)` would show one rule under both.
//
// A NEW class name on purpose. `tests/test_viewer_js.py` holds a negative contract over this pane,
// naming the four ref classes that must not reappear in it: the pane stays step-specific, and
// structural relationship navigation belongs to the drawn arrow. (Naming them here would trip that
// contract on the comment alone — it is a plain substring check.)
function stepRulesHtml(uc, st) {
  if (!HAS_RULES) return '';
  const key = uc + ':' + (st.sf || uc) + ':' + st.n;
  const ids = ((RULES_VIEW.byStep || {})[key]) || [];
  if (!ids.length) return '';
  const byId = new Map((RULES_VIEW.rules || []).map((r) => [r.id, r]));
  const links = ids.map((rid) => byId.get(rid)).filter(Boolean).map((r) => {
    const link = (r.steps || []).find((l) => l.uc === uc && l.container === (st.sf || uc) && l.n === st.n);
    // "this exact step" and "inside the same function as this step" are different claims; saying so
    // is the difference between a readout and a pretended proof.
    const near = link && link.strength !== 'exact'
      ? ' <span class="muted">(enforced inside the same function)</span>' : '';
    return '<a href="#" class="brref" data-blk="' + esc(r.block || '') + '" data-br="' + esc(r.id)
      + '">' + esc(r.statement) + '</a>' + near;
  });
  return '<dl><dt>Decides</dt><dd class="br-steprules">' + links.join('<br>') + '</dd></dl>';
}
function bindFlowStepInfo(host, uc, i) {
  const st = (FLOWS_NARR[uc] || [])[i];
  if (!st) return;
  const sw = host.querySelector('a.stepwhere');
  if (sw) sw.addEventListener('click', (ev) => {
    ev.preventDefault();
    const wn = whereNode(st.where);
    openInCodeViewer(wn.file, wn.line);
  });
  // The "Decides" rows deep-link into the Business logic tab, focused on the rule.
  host.querySelectorAll('a.brref').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault();
    go({ kind: 'rules', blk: a.getAttribute('data-blk') || 'none', br: a.getAttribute('data-br') });
  }));
}
// A flow step's side panel — EVERY step shows ITSELF (its phrase, note, and its own call
// site), never the backbone arrow's text: one element pair appears in several steps meaning different
// things, so the shared arrow description can't be right for each — and the arrow's `where` is only an
// example site, while the step's `where` is THE location. Structural navigation belongs to the Locate
// action on the drawn arrow, where it remains available without repeating the endpoints in this pane.
function showFlowStep(uc, i) {
  const st = (FLOWS_NARR[uc] || [])[i];
  if (!st) { panel.innerHTML = EMPTY_PANEL; return; }
  panel.innerHTML = flowStepInfoHtml(uc, i, false);
  bindFlowStepInfo(panel, uc, i);
  // Mirror the step's own anchor into the tree + code viewer — and degrade gracefully when the step
  // has none (`no_call_site`, or a map from before step anchors): clear the stale tree highlight so a
  // previous selection's path can't read as this step's location, and leave the code viewer alone.
  const wn = st.where ? whereNode(st.where) : null;
  const local = !!(wn && localRef(wn.file));
  cvElement = null;  // a step has no single owning element -> no header pill
  setTreeSelection(null);
  highlightTreePath(local ? refTreePath(wn.file, wn.line) : null);
  if (local) syncCodeView(wn.file, wn.line, []);
}
// One actor's card, in ANY view that draws an actor. `drives` is the only part that differs by view (the
// Happy Path lists step titles, a flow lists its own steps), so everything else lives here once — and
// `Wants` is a TITLED row, exactly as the Dependencies view's actor panel renders it. It was an untitled
// paragraph here, which reads as a description of the actor rather than as what they are after; the same
// fact should not change its name between two views.
function actorPanelHtml(a, drives) {
  const kindBadge = a.kind ? '<span class="badge kind">' + esc(a.kind) + '</span>' : '';
  const wants = a.wants ? '<dt>Wants</dt><dd>' + mdInline(a.wants) + '</dd>' : '';
  const driveRows = drives ? '<dt>Drives</dt>' + drives : '';
  return '<div class="pane-title"><h2>' + esc(a.name) + '</h2>'
    + '<span class="badge kind">actor</span>' + kindBadge + '</div>'
    + (wants || driveRows ? '<dl>' + wants + driveRows + '</dl>' : '');
}
// The Happy Path's actor card: the steps it drives are that walk's own positions.
function showHPActor(a) {
  panel.innerHTML = actorPanelHtml(a, (a.steps || []).map((st) =>
    '<dd>' + esc(st.title || st.id) + '</dd>').join(''));
}
// A flow-level actor's card — the same card, scoped to one flow: which of THIS flow's own steps it
// drives. Reads those steps straight out of FLOWS_NARR by index rather than duplicating their text in
// FLOW_ACTORS.
function showFlowActor(uc, a) {
  const flowSteps = FLOWS_NARR[uc] || [];
  panel.innerHTML = actorPanelHtml(a, a.stepIdx.map((i) => flowSteps[i]).filter(Boolean)
    .map((st) => '<dd>' + esc(st.src) + ' <em>' + esc(st.verb) + '</em> ' + esc(st.dst) + '</dd>').join(''));
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
// The element currently under the cursor and its `actionFn` (what an ⌥-click does here, or null). Held so
// pressing/releasing ⌥ can swap the tooltip live, without waiting for a new mouse event (see setDrillMod).
let hover = null;
function renderHoverTip() {
  if (!hover || !hover.actionFn || !document.body.classList.contains('altmod')) { hideTip(); return; }
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
  // Checked BEFORE the source: a store box's primary action is its data, not its config file — keep
  // the tooltip in step with primaryActionFor, which prefers the same drill.
  if (dataDrillFor(id))
    return '<div class="tt">Open its data</div><div class="tm">' + esc(dataDrillLabel(id)) + '</div>';
  if (srcNode(id)) return actionOpenSrcHtml(n);
  if (String(n.kind) === 'subsystem')
    return '<div class="tt">Open subsystem</div><div class="tm">' + esc(n.name) + '</div>';
  if (String(n.kind) === 'subdomain')
    return '<div class="tt">Open subdomain</div><div class="tm">' + esc(n.name) + '</div>';
  if (id === LIBS_ID)
    return '<div class="tt">Open Libraries</div><div class="tm">' + FOLDED_LIBS.length + ' bundled</div>';
  if (n && n.kind === 'bucketfold') { const b = bucketFoldOf(id);
    return '<div class="tt">Open ' + esc(n.name) + '</div><div class="tm">' + (b ? b.count : 0) + ' dependencies</div>'; }
  return null;
}
function actionTipEdge(a, b, drawn) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  // Preview the DRAWN endpoints when given (a card's single-component cross arrow), so the ⌘-hover tip
  // names what the zoom will land focused on rather than the whole collapsed pair. Falls back to a/b.
  const ha = drawn ? drawn.src : a, hb = drawn ? drawn.dst : b;
  return '<div class="tt">Open</div><div class="tm">' + esc(nm(ha)) + ' &rarr; ' + esc(nm(hb)) + '</div>';
}
function actionTipHP(hpId) {
  const s = HP_BY_ID[hpId];
  return '<div class="tt">Open step</div>' + (s && s.title ? '<div class="tm">' + esc(s.title) + '</div>' : '');
}

// --- diff badges + legend -------------------------------------------------------
// The diff badge is the drill/open action icon's TWIN: same plate construction (a white halo of
// ACTION_ICON_R so it sits cleanly over a dashed container border + a disc + a glyph), the same
// paintImportant styling (to beat Mermaid's id-scoped !important box rules), and the same
// constant-on-screen sizing (built at the origin; addBadge/rescaleDiffBadges position it with
// `translate(corner) scale(curIconInv())`). It differs only in what an action icon must NOT be: a
// SOLID colour-filled disc + a +/✎/× glyph (the change state), and it sits on the RIGHT corner where
// the drill icon takes the LEFT — so a box can carry both without collision. Used by the legend too,
// so the key and the diagram badge are pixel-identical.
const BADGE_R = 13;   // disc radius — matches the action icon's circle (addActionIcon)
function makeBadge(state) {
  const g = document.createElementNS(SVGNS, 'g');
  g.setAttribute('class', 'diff-badge');
  const spec = BADGE[state];
  if (!spec) return g;
  const [color, glyph] = spec;
  const halo = document.createElementNS(SVGNS, 'circle');
  halo.setAttribute('r', String(ACTION_ICON_R));
  paintImportant(halo, { fill: '#fff', stroke: 'none' });
  const disc = document.createElementNS(SVGNS, 'circle');
  disc.setAttribute('r', String(BADGE_R));
  paintImportant(disc, { fill: color, stroke: '#fff', 'stroke-width': '1.6px', 'stroke-dasharray': 'none' });
  const t = document.createElementNS(SVGNS, 'text');
  t.setAttribute('text-anchor', 'middle'); t.setAttribute('dominant-baseline', 'central');
  paintImportant(t, { fill: '#fff', 'font-family': '-apple-system, system-ui, sans-serif',
                      'font-size': '15px', 'font-weight': '700' });
  t.textContent = glyph;
  g.append(halo, disc, t);
  return g;
}
// Injected diagram diff badges, tracked so a zoom change can re-hold their screen size constant.
const DIFF_BADGES = [];
// The node's VISIBLE box shape (the largest rect) — its geometry is the true corner. The node GROUP's
// getBBox can extend past the box (a wider hit-area / hover glow / label), which would float the badge
// off the corner; the box rect does not. A direct child of the group, so its bbox is in the same space.
function boxShape(el) {
  const rects = [...el.querySelectorAll('rect')];
  if (!rects.length) return el;
  const area = (r) => { try { const b = r.getBBox(); return b.width * b.height; } catch (_) { return -1; } };
  return rects.reduce((big, r) => (area(r) > area(big) ? r : big));
}
// Anchor the badge at a box CORNER (default top-RIGHT — the drill icon takes top-LEFT; the coverage
// overlay passes 'br' for bottom-right so it never collides with a diff badge), then hold it at a
// constant on-screen size with the same counter-zoom the action icons use.
function addBadge(el, state, corner) {
  const shape = boxShape(el);
  let bb; try { bb = shape.getBBox(); } catch (_) { return; }
  const g = makeBadge(state);
  // Same front-overlay home as the action icons (see iconOverlay), so a badge on a container's corner
  // isn't painted over by that container's inner boxes. The chosen corner, read in the box shape's own
  // space, is carried into the overlay's space so the on-screen spot is unchanged.
  const parent = iconOverlay || el;
  const pt = { x: bb.x + bb.width, y: corner === 'br' ? bb.y + bb.height : bb.y };
  const anchor = parent === el ? pt : pointToHostSpace(shape, pt.x, pt.y, parent);
  if (!anchor) return;
  g._anchor = anchor;
  g.setAttribute('transform', `translate(${anchor.x},${anchor.y}) scale(${curIconInv()})`);
  parent.appendChild(g);
  DIFF_BADGES.push(g);
}
function rescaleDiffBadges() {   // counter-zoom every live badge so it stays a fixed screen size (mirrors rescaleActionIcons)
  const inv = curIconInv();
  for (const g of DIFF_BADGES) if (g && g._anchor) g.setAttribute('transform', `translate(${g._anchor.x},${g._anchor.y}) scale(${inv})`);
}
// --- view captions, the map legend, and empty-state notes -------------------------
// The question each view answers, shown in the info pane's top-level state. Keyed by the top-level view
// id (topView), so a drilled card keeps its tab's caption.
const VIEW_LABEL = {};   // view id -> its tab label, filled from the buttons at boot (one source)
const VIEW_Q = {
  hp: 'What does this system do, end to end?',
  usecases: 'Who uses it, and what does each of them get done?',
  container: 'How is the code organised, and what depends on what?',
  domain: 'What things does this system know about, and how do they relate?',
  context: 'What does it rely on from the outside world?',
  data: 'What is stored, where, and who reads and writes it?',
  deployment: 'What runs as its own process, and how do those talk to each other?',
  system: 'The operational facts no diagram holds — how to run it, watch it, secure it, configure it.',
  glossary: 'What do this project’s words mean?',
  tests: 'What is covered by tests, and what is not?',
  rules: 'What does this product DECIDE, and where is each decision enforced?',
};
// ONE legend for the whole map, not a guess per view. The per-view lists this replaced were hardcoded
// and therefore wrong wherever a view's content is data-dependent: the Dependencies view draws bare
// dependency boxes on a small map but only folded groups on a large one; the Deployment view has no
// infrastructure lane when nothing is shared; the Happy Path is a sequence diagram that uses none of
// these styles at all. A single, complete vocabulary is right on every map by construction — the reader
// looks up what they see, and simply never meets the rows their map has no use for.
//
// Rows are GROUPED BY THE VIEW THAT DRAWS THEM, because that is how they are looked up: the reader is
// on one view, meets one shape, and scans for the heading naming the view they are already on. A flat
// "Boxes" list made them read every row to find the one that applies. Sections are keyed by VIEW ID and
// titled from the tab's own label (VIEW_LABEL), so a heading can never drift from the tab it names.
// Sections run in TAB ORDER, so scanning the legend and scanning the view switcher are the same scan.
// Each shape is listed ONCE, under the first view that draws it: the vocabulary is shared across views
// by design (a person is the same figure everywhere), and repeating a row under every view that uses it
// turned the legend into a list with the same swatch three times over.
//
// [view ids, [[tint kind, shape, label], …]]. Colours come from ELEMENT_TINT — the SAME styles the
// generators paint the boxes with — and the shape mirrors the generators' SHAPE map, so a swatch cannot
// claim a look the diagrams never draw. A row whose shape belongs to no diagram would go under a
// trailing ['', …] section (rendered as "Boxes"); today every shape has a home view, so there is none.
const LEGEND_SECTIONS = [
  // The two sequence views. Both draw a Role as a lifeline, and the kind is the whole point of the
  // pair: a person acts, a service actor (a scheduled job, a poller, an inbound caller) starts on its
  // own. The Happy Path also draws the System, in the same dark box the Dependencies view gives it.
  [['hp', 'usecases'], [
    ['system', 'rect', 'the system'],
    ['human', 'man', 'a person'],
    ['svc', 'hex', 'a service actor'],
  ]],
  [['container'], [
    ['subsystem', 'rect', 'subsystem'],
    ['component', 'rect', 'component'],
  ]],
  [['domain'], [
    ['subdomain', 'rect', 'subdomain'],
    ['entity', 'rect', 'entity'],
  ]],
  // The system + both actor shapes are drawn here too — listed above, under the first view that draws
  // them, so this section holds only what is new when you arrive at it.
  [['context'], [
    ['dep', 'cyl', 'dependency'],
    ['bucketfold', 'rect', 'a collapsed group'],
  ]],
  // The infrastructure rows keep the wording of the lanes they label ("Used as a message bus"), which
  // states what the band measures — a dep's DERIVED role — rather than claiming it as an identity.
  [['deployment'], [
    ['process', 'rect', 'process'],
    ['infraBus', 'cyl', 'used as a message bus'],
    ['infraStore', 'cyl', 'used as a data store'],
    ['infraSvc', 'cyl', 'used as a service'],
    ['infraSec', 'cyl', 'used for security'],
  ]],
];
// The two stroke conventions. They carry meaning no colour can, and are the most misread part of the
// language: "dashed" reads as provisional to most people, when here it means "there is more inside".
const LEGEND_STROKES = [
  ['box', 'dashed border = collapsed; open it'],
  ['edge', 'dashed arrow = several links bundled; open it'],
];
// The hexagon outline as polygon points for a box — ONE definition, shared by the legend swatch and the
// sequence-diagram service-actor figure, so the two can't drift into drawing different hexagons for the
// same meaning. The notch is a fifth of the width (capped at half the height, so a squat box stays a
// hexagon instead of collapsing into a rhombus).
function hexPoints(x, y, w, h) {
  const n = Math.min(w * 0.2, h / 2), my = y + h / 2;
  return [[x + n, y], [x + w - n, y], [x + w, my], [x + w - n, y + h], [x + n, y + h], [x, my]]
    .map((p) => p[0].toFixed(2) + ',' + p[1].toFixed(2)).join(' ');
}
// The stick figure as ONE path `d`, centred on `cx` and filling `h` downward from `top` — shared by the
// legend swatch and the Dependencies view's human actor, so the two can't drift. Every limb is a single
// straight subpath, which encloses no area: the path can therefore take a fill (it lands on the head
// alone, like every other box's fill) without the limbs smearing into filled wedges. Proportions are
// fractions of the height, so the same call draws a 13-unit swatch and a 27-unit node figure.
function stickFigurePath(cx, top, h) {
  const r = 0.17 * h, hip = top + 0.66 * h, arm = top + 0.40 * h;
  const n = (v) => v.toFixed(2);
  return `M${n(cx - r)},${n(top + r)}a${n(r)},${n(r)} 0 1,0 ${n(2 * r)},0a${n(r)},${n(r)} 0 1,0 ${n(-2 * r)},0Z`
    + `M${n(cx)},${n(top + 2 * r)}L${n(cx)},${n(hip)}`
    + `M${n(cx - 0.30 * h)},${n(arm)}L${n(cx + 0.30 * h)},${n(arm)}`
    + `M${n(cx - 0.26 * h)},${n(top + h)}L${n(cx)},${n(hip)}`
    + `M${n(cx)},${n(hip)}L${n(cx + 0.26 * h)},${n(top + h)}`;
}
function legendSwatch(kind, shape) {
  const t = (ELEMENT_TINT || {})[kind] || {};
  const svg = document.createElementNS(SVGNS, 'svg');
  svg.setAttribute('width', 22); svg.setAttribute('height', 15); svg.setAttribute('viewBox', '0 0 22 15');
  const paint = (el) => {
    el.setAttribute('fill', t.fill || '#fff');
    el.setAttribute('stroke', t.stroke || '#9ca3af');
    el.setAttribute('stroke-width', t.strokeWidth ? '1.8' : '1.25');
    if (t.strokeDasharray) el.setAttribute('stroke-dasharray', '3.5 2');
    return el;
  };
  if (shape === 'hex') {
    const el = document.createElementNS(SVGNS, 'polygon');
    el.setAttribute('points', hexPoints(1, 1.5, 20, 12));
    svg.appendChild(paint(el));
  } else if (shape === 'man') {
    const el = document.createElementNS(SVGNS, 'path');
    el.setAttribute('d', stickFigurePath(11, 1, 13));
    svg.appendChild(paint(el));
  } else if (shape === 'cyl') {
    const body = document.createElementNS(SVGNS, 'rect');
    body.setAttribute('x', 3); body.setAttribute('y', 3.5); body.setAttribute('width', 16);
    body.setAttribute('height', 9); body.setAttribute('rx', 1);
    svg.appendChild(paint(body));
    const lid = document.createElementNS(SVGNS, 'ellipse');
    lid.setAttribute('cx', 11); lid.setAttribute('cy', 3.5); lid.setAttribute('rx', 8); lid.setAttribute('ry', 2.4);
    svg.appendChild(paint(lid));
  } else {
    const el = document.createElementNS(SVGNS, 'rect');
    el.setAttribute('x', 1.5); el.setAttribute('y', 1.5); el.setAttribute('width', 19);
    el.setAttribute('height', 12); el.setAttribute('rx', shape === 'stadium' ? 6 : 2);
    svg.appendChild(paint(el));
  }
  return svg;
}
function strokeSwatch(kind) {
  const svg = document.createElementNS(SVGNS, 'svg');
  svg.setAttribute('width', 22); svg.setAttribute('height', 15); svg.setAttribute('viewBox', '0 0 22 15');
  const el = document.createElementNS(SVGNS, kind === 'box' ? 'rect' : 'line');
  if (kind === 'box') {
    el.setAttribute('x', 1.5); el.setAttribute('y', 1.5); el.setAttribute('width', 19);
    el.setAttribute('height', 12); el.setAttribute('rx', 2); el.setAttribute('fill', 'none');
  } else {
    el.setAttribute('x1', 1); el.setAttribute('y1', 7.5); el.setAttribute('x2', 21); el.setAttribute('y2', 7.5);
  }
  el.setAttribute('stroke', '#475569'); el.setAttribute('stroke-width', '2');
  el.setAttribute('stroke-dasharray', '3.5 2');
  svg.appendChild(el);
  return svg;
}
function legendRow(swatch, label) {
  const row = document.createElement('div'); row.className = 'row';
  const span = document.createElement('span'); span.textContent = label;
  row.appendChild(swatch); row.appendChild(span);
  return row;
}
// Why this view looks EMPTY, when it does. A lane a rule found nothing for looks exactly like one
// nobody recorded anything for, and only the view itself can tell them apart — so it says so, in its
// own terms. Derived, never authored, so it cannot go stale.
//
// Deliberately NOT coverage counts ("N of M components have no recorded connection"). Those report
// uncertainty, which is a given for every map: they never change how to read the diagram or what to do
// next, so on every view they were noise. Completeness is `validate`'s job, where it comes with the
// specific ids to fix.
function viewNotes(view) {
  const n = [];
  if (view === 'deployment' && !(MERMAID_DEPLOYMENT || '').includes('L_infra')) {
    n.push('no infrastructure is used by 2+ processes');
  } else if (view === 'data' && !(DATA_VIEW.stores || []).length) {
    n.push('no physical store recorded');
  }
  return n;
}
// The TOP-LEVEL state of the info pane for a view: its name as the title, the question it answers
// beneath, then a note if the view is empty. This is what the pane shows when nothing is selected —
// selecting an element replaces it with that element's detail, as before.
function viewIntroHtml(view) {
  const notes = viewNotes(view);
  return `<div class="pane-title"><h2>${esc(VIEW_LABEL[view] || view)}</h2></div>`
    + (VIEW_Q[view] ? `<p class="viewq">${esc(VIEW_Q[view])}</p>` : '')
    + (notes.length ? `<div class="viewnotes">${notes.map((t) => `<span class="vnote">${esc(t)}</span>`).join('')}</div>` : '');
}
// Build the one legend. The change badges join it as a section in diff mode, so there is still exactly
// one place to look up what anything on screen means.
function buildLegend() {
  const frag = document.createDocumentFragment();
  const close = document.createElement('button');
  close.id = 'legendclose'; close.type = 'button'; close.textContent = '\u00d7';
  close.title = 'Hide the legend (reopen with ? beside the views)';
  close.setAttribute('aria-label', 'Hide the legend');
  close.addEventListener('click', () => setLegendOpen(false));
  frag.appendChild(close);
  for (const [views, rows] of LEGEND_SECTIONS) {
    // The heading IS the tab's own label (the same read as viewIntroHtml's title), so the reader looks
    // up the word they clicked. A section naming no view holds the shapes no diagram owns — "Boxes".
    const title = views.map((v) => VIEW_LABEL[v] || v).join(' & ') || 'Boxes';
    const h = document.createElement('div'); h.className = 'lgh'; h.textContent = title;
    frag.appendChild(h);
    for (const [kind, shape, label] of rows) frag.appendChild(legendRow(legendSwatch(kind, shape), label));
  }
  const h2 = document.createElement('div'); h2.className = 'lgh'; h2.textContent = 'Lines';
  frag.appendChild(h2);
  for (const [kind, label] of LEGEND_STROKES) frag.appendChild(legendRow(strokeSwatch(kind), label));
  if (mode === 'diff') {
    const h3 = document.createElement('div'); h3.className = 'lgh'; h3.textContent = 'Changes';
    frag.appendChild(h3);
    const states = IMPACT ? ['added', 'modified', 'deleted', 'drifted', 'rippled']
                          : ['added', 'modified', 'deleted', 'rippled'];
    const d = 2 * ACTION_ICON_R + 2;
    for (const st of states) {
      const svg = document.createElementNS(SVGNS, 'svg');
      svg.setAttribute('width', 22); svg.setAttribute('height', 15);
      svg.setAttribute('viewBox', `${-d / 2} ${-d / 2} ${d} ${d}`);
      svg.appendChild(makeBadge(st));
      frag.appendChild(legendRow(svg, BADGE[st][2]));
    }
  }
  legend.innerHTML = ''; legend.appendChild(frag);
  legend.dataset.mode = mode;
}
// Open/closed is the reader's choice and persists. Closed = shown NOWHERE; open = shown on every view
// that actually draws a diagram (a colour key over a table of text explains nothing).
let LEGEND_OPEN = null;
function legendOpen() {
  if (LEGEND_OPEN === null) LEGEND_OPEN = lsGet(LS.legend) !== 'off';
  return LEGEND_OPEN;
}
function setLegendOpen(on) {
  LEGEND_OPEN = on;
  lsSet(LS.legend, on ? 'on' : 'off');
  syncLegend(history[hi]);
}
// The text tabs render HTML tables, not diagrams — nothing there has a shape or a colour to look up.
const TEXT_VIEWS = new Set(['glossary', 'usecases', 'system', 'data', 'tests', 'rules']);
function syncLegend(s) {
  const on = legendOpen() && !!s && !TEXT_VIEWS.has(topView(s.kind));
  legend.classList.toggle('on', on);
  legendbtn.classList.toggle('on', legendOpen());
  legendbtn.setAttribute('aria-pressed', String(legendOpen()));
  if (on && legend.dataset.mode !== mode) buildLegend();   // rebuilt only when the diff section changes
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
  DIFF_BADGES.length = 0;                            // this render re-adds them; drop the old (now-detached) refs
  if (s.kind === 'container') {                     // overview: badge each subsystem box with its subtree's change
    for (const id in mainScene.nodeEls) {
      const st = subsystemDiffState(id);
      if (st) addBadge(mainScene.nodeEls[id], st);
    }
  } else if (s.kind === 'subsystem' || s.kind === 'edge' || s.kind === 'component') {  // cards: per-node badge
    for (const id in mainScene.nodeEls) {
      if (DIFF_STATE[id]) addBadge(mainScene.nodeEls[id], DIFF_STATE[id]);
    }
  } else if (IMPACT) {  // impact spans every view: badge whatever impacted elements this diagram draws
    for (const id in mainScene.nodeEls) {
      if (DIFF_STATE[id]) addBadge(mainScene.nodeEls[id], DIFF_STATE[id]);
    }
  }
}
// A use case "contains changes" when any element its T6 flow touches is changed (FLOWS_NARR × DIFF_STATE)
// — the behavioural layer of the diff, DERIVED from the element changes, not a separate source.
function usecaseDiffState(uc) {
  for (const st of (FLOWS_NARR[uc] || [])) {
    for (const id of [st.srcId, st.dstId]) {
      if (id && DIFF_STATE[id] && DIFF_STATE[id] !== 'rippled') return 'modified';
    }
  }
  return null;
}
function changedUseCaseIds() { return (UC_NODES || []).map((n) => n.id).filter((uc) => usecaseDiffState(uc)); }
// The Subsystems-overview panel in diff mode: every changed element grouped by state, each name
// clickable to locate it in its home view. Added elements appear here even though they badge no box.
function showDiffSummary() {
  const order = ['added', 'modified', 'deleted', 'rippled'];
  const groups = { added: [], modified: [], deleted: [], rippled: [] };
  for (const id in DIFF_STATE) { const st = DIFF_STATE[id]; if (groups[st]) groups[st].push(id); }
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  const total = order.reduce((sum, k) => sum + groups[k].length, 0);
  let html = '<h2>Change impact</h2>';
  if (LIVE_DIFF) {   // show the range being compared + the changed-file count for a live mechanical diff
    const short = (r) => (r === DIFF_WORKTREE ? 'working tree' : (r || '').slice(0, 8));
    const files = (LIVE_DIFF.counts && LIVE_DIFF.counts.files) || (LIVE_DIFF.changes || []).length;
    html += '<p class="muted" style="margin:0 0 8px">' + esc(short(LIVE_DIFF.base)) + ' → '
      + esc(short(LIVE_DIFF.target)) + ' · ' + files + ' file' + (files === 1 ? '' : 's') + ' changed</p>';
  }
  html += '<div class="badges"><span class="badge kind">' + total + ' change' + (total === 1 ? '' : 's') + '</span></div>';
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
  // Behavioural layer: which use cases a code change reaches, via their flow steps. Derived, so it
  // rides the same element diff — each links to that use case's flow.
  const changedUCs = changedUseCaseIds().sort((a, b) => nm(a).localeCompare(nm(b)));
  if (changedUCs.length) {
    html += '<dl class="diff-uc"><dt><span class="badge modified">use cases affected</span></dt>'
      + changedUCs.map((uc) => '<dd><a href="#" class="diffucref" data-uc="' + esc(uc) + '">' + esc(nm(uc)) + '</a></dd>').join('')
      + '</dl>';
  }
  if (!total) html += '<p class="empty">No changes recorded.</p>';
  panel.innerHTML = html;
  panel.querySelectorAll('a.diffref').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault(); selectFromTree(a.getAttribute('data-id'));
  }));
  panel.querySelectorAll('a.diffucref').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault(); go({ kind: 'usecase', uc: a.getAttribute('data-uc') });
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
// an `is-selected` class on the group. `revealAction` distinguishes a direct diagram click (pin the
// corner action after the cursor leaves) from an automatic selection (highlight only; action stays
// hover-driven). The node analog of glowEdge.
function glowNode(el, revealAction = true) {
  shapeOf(el).style.filter = HILITE;
  el.classList.add('is-selected');
  // Keep the box's corner pill visible after the cursor leaves it while it's the selection. The pill now
  // lives in the front overlay (not this group), so this is a JS flag rather than the old `.is-selected`
  // descendant CSS rule; `_actionIcon` is set by addActionIcon for every box/cluster pill.
  const icon = el._actionIcon;
  if (icon) { icon._selected = !!revealAction; refreshPillReveal(icon); }
  return () => {
    shapeOf(el).style.filter = ''; el.classList.remove('is-selected');
    if (icon) { icon._selected = false; refreshPillReveal(icon); }
  };
}
// Hover glow — same shape-only rule as glowNode, so hovering a box's corner action icon (visually
// inside the box) never tints the icon itself; the icon has its own :hover reaction (viewer.css).
// Skipped while the node is the active selection, so glowNode's HILITE wins over a lingering hover.
function bindHoverGlow(scene, el, id) {
  const shape = shapeOf(el);
  el.addEventListener('mouseenter', () => { if (!selHas(scene, 'node:' + id)) shape.style.filter = HOVER; });
  el.addEventListener('mouseleave', () => { if (!selHas(scene, 'node:' + id)) shape.style.filter = ''; });
}
// A node's focus contribution: its own box + its immediate neighbours (kept lit), and its own edges. null
// when the node isn't drawn in this scene (a neighbourhood's external box) — so it doesn't dim everything.
function nodeFocus(scene, id) {
  if (!scene.nodeEls[id]) return null;
  const keep = new Set([id]);
  for (const x of scene.edgeEls) { if (x.e.src === id) keep.add(x.e.dst); if (x.e.dst === id) keep.add(x.e.src); }
  return { nodes: keep, edge: (e) => e.src === id || e.dst === id };
}
// A normal node's selection descriptor: glow the box, dim to its neighbourhood, show its detail (+ mirror
// into the file browser / code viewer when it's the primary card).
function nodeDesc(scene, el, id) {
  return { key: 'node:' + id, glow: (reveal) => glowNode(el, reveal),
           focus: nodeFocus(scene, id), show: () => showNodeDetailSynced(id) };
}
// Select a normal node within a scene: REPLACE the selection with just this node (glow + dim + panel).
// Used by every non-modifier select path (tree click, search hit, history restore's single-key case).
function selectNode(scene, el, id) { selReplace(scene, nodeDesc(scene, el, id)); }

// Canvas-click selection: a ⌘-click toggles this box in/out of the multi-selection; a plain click replaces
// the selection with it and holds the camera still (auto-panning would fight a reader who clicked a box
// precisely BECAUSE it was already comfortably in view). Only a shift-click reframes, zooming to match the
// sidebar's text size (matchTextSize). A ⌘-click never reframes — piling several boxes into view then
// zooming to the last one would be jarring while building a selection.
function selectNodeFromCanvas(el, id, e) {
  pickSelBox(mainScene, nodeDesc(mainScene, el, id), el, e);  // shift=frame, ⌘=toggle, plain=replace
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

// Map/Figma-style wheel handling on the diagram: a plain wheel / two-finger trackpad scroll PANS the
// canvas (natural direction, like a scrollable document); Ctrl/Cmd + wheel, or a trackpad PINCH (which
// the browser reports as a wheel event with ctrlKey=true), zooms — anchored on the cursor so the point
// under the pointer stays put. The library's own wheel-zoom is disabled (mouseWheelZoomEnabled:false).
function wheelNavigate(e) {
  if (!mainPz) return;
  e.preventDefault();  // stop the page from scrolling, and Ctrl+wheel from triggering browser zoom
  let dx = e.deltaX, dy = e.deltaY;
  if (e.deltaMode === 1) { dx *= 16; dy *= 16; }  // line units (some mice) -> approx pixels
  if (e.ctrlKey || e.metaKey) {
    // Zoom, anchored on the cursor. f is the zoom multiplier for this event; the pan formula keeps the
    // content point under the pointer fixed on screen (mx,my measured from the svg/#diagram top-left).
    const f = Math.min(Math.max(Math.exp(-dy * 0.0025), 0.5), 2);
    const rect = diagram.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const pan = mainPz.getPan();
    mainPz.zoom(mainPz.getZoom() * f);                                    // zoom() re-pans to hold the center...
    mainPz.pan({ x: mx * (1 - f) + f * pan.x, y: my * (1 - f) + f * pan.y });  // ...override it to hold the cursor
    updateZoomLevel();
    return;
  }
  // Pan. Shift with a vertical-only wheel (typical mouse) scrolls horizontally instead.
  if (e.shiftKey && dx === 0) { dx = dy; dy = 0; }
  mainPz.panBy({ x: -dx, y: -dy });  // negative: content moves opposite the scroll, like a document
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
// The arrow analog of matchTextSize: a shift-click on ANY arrow (a flowchart edge, or a Happy Path /
// use-case message) centers it and zooms so its extent fills a comfortable slice of the viewport. Unlike
// matchTextSize (which sizes a box against its name label), this measures the arrow's own bounding box, so
// it works the same whether or not the arrow carries a label — every arrow type frames identically.
function frameArrow(el) {
  if (!mainPz || !el) return;
  const r = el.getBoundingClientRect();
  const stage = diagram.getBoundingClientRect();
  if ((r.width < 1 && r.height < 1) || !stage.width) return;
  // Fit the arrow's bounding box into ~70% of the viewport in BOTH axes (the tighter axis binds), so a
  // wide, near-horizontal message arrow zooms only enough to frame it end-to-end centered, while a short
  // arrow zooms in — never the axis-mismatched over-zoom of sizing one dimension against the other.
  const fitW = r.width >= 1 ? stage.width / r.width : Infinity;
  const fitH = r.height >= 1 ? stage.height / r.height : Infinity;
  // Clamp to a sane band: at most ~2.5x in (a very short arrow just gets a moderate zoom, not a jarring
  // leap) and at most 2x out (a diagram-spanning arrow zooms out enough to see end-to-end, no further).
  const scale = Math.min(Math.max(0.7 * Math.min(fitW, fitH), 0.5), 2.5);
  applyZoomAndCenter(el, scale);
}

// Select the collapsed Libraries box: highlight + show its roster (showLibsFold), and dim to its
// neighbourhood (the System + the SYS→box arrow) just like selecting a dependency — the bundles arrow
// is a registered context edge, so focusNode resolves the connection. Reuses the node selKey so
// bindNodes' hover guard matches and the selection glow isn't overwritten by a passing hover.
function libsFoldDesc(scene, el) {
  return { key: 'node:' + LIBS_ID, glow: (reveal) => glowNode(el, reveal),
           focus: nodeFocus(scene, LIBS_ID), show: () => showLibsFold() };
}
function selectLibsFold(scene, el) { selReplace(scene, libsFoldDesc(scene, el)); }
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
// A store/broker dependency drills into ITS OWN section of the Data tab — what is persisted in it,
// who writes and reads that, and the channels it carries. The box IS the store, so drilling it should
// land on its data, the same way a subsystem box drills into its components; the info pane keeps its
// "View persisted data" link for the times you arrive from somewhere else. null when this dep has no
// Data-view section (an ordinary service dep, or a map with no stores at all).
function dataStoreOf(id) {
  const n = GRAPH.nodes[id];
  if (!HAS_DATA || !n || n.kind !== 'dep') return null;
  return (DATA_VIEW.stores || []).find((s) => s.dep === id) || null;
}
function dataDrillFor(id) {
  return dataStoreOf(id) ? { kind: 'data', store: id } : null;
}
// What that store holds, as a count phrase — the ONE wording shared by the box's action tooltip and
// the info pane's "View persisted data" link, so the two can never describe the same store differently.
function dataDrillLabel(id) {
  const st = dataStoreOf(id);
  if (!st) return '';
  const nrows = st.rows.length; const nch = st.channels.length;
  return nrows ? `${nrows} collection${nrows === 1 ? '' : 's'}`
    : (nch ? `${nch} channel${nch === 1 ? '' : 's'}` : 'no modelled data');
}
function markDataDrill() {
  for (const id in mainScene.nodeEls) {
    if (dataDrillFor(id)) mainScene.nodeEls[id].classList.add('drill');
  }
}
// The store-box drill gesture, shared by every view that draws dep boxes (Dependencies itself, a
// purpose-bucket drill, the Libraries fold) so the affordance can't work in one and not the next.
// Returns true when it handled the click.
function tryDataDrillClick(id, e) {
  const dd = dataDrillFor(id);
  if (!dd || !isDrillClick(e)) return false;
  go(dd);
  return true;
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
    // Only the Context family draws a `human` box, so this reaches every view that has one (Dependencies
    // itself, the Libraries drill, a bucket drill) and is a no-op on the rest.
    if (el.classList.contains('human')) stickFigureNode(el);
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
// bindSelectEdge, matching hpGlow's selection guard) is what lets the pill stay up after a direct
// selection even once the cursor leaves. Flow-step callers narrow it when a stepper owns the selection.
function bindEdgeActionIcon(p, hit, label, action, isSelected) {
  const id = p.id || ('edgepill' + (EDGE_ICON_SEQ++));
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
    const parent = iconOverlay || host;
    const localFallback = edgeMidpointAnchor(p) || { x: 0, y: 0 };
    const fallback = pointToHostSpace(p, localFallback.x, localFallback.y, parent) || { x: 0, y: 0 };
    addActionIcon(p, id, action, { host, anchor: fallback });
    icon = ACTION_ICONS[id];
    const moveTo = (anchor) => {
      icon._anchor = anchor;
      icon.setAttribute('transform', `translate(${anchor.x},${anchor.y}) scale(${curIconInv()})`);
    };
    showAt = (ev) => { if (isDim()) return; moveTo(clientToLocal(parent, ev.clientX, ev.clientY) || fallback); showIcon(icon); };
  }
  icon.addEventListener('mouseenter', showAt);
  icon.addEventListener('mouseleave', hide);
  hit.addEventListener('mouseenter', showAt);
  hit.addEventListener('mouseleave', hide);
  if (label) { label.addEventListener('mouseenter', showAt); label.addEventListener('mouseleave', hide); }
  p._actionIcon = icon;
}
// Give an edge's visible path a wide transparent hit-path + make its label clickable.
// `tipHtml` (optional) wires a hover meaning-preview on the same hit-area + label.
// `onDrill` (falsy for a non-drillable edge) controls the ⌘-held cursor and direct drill gesture.
// `action` can instead put another explicit action on the arrow, such as Locate on a flow relationship.
function attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff, onDrill, actionFn, isSelected, action) {
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
  const edgeAction = action || (onDrill ? { kind: 'drill', run: onDrill } : null);
  if (edgeAction) bindEdgeActionIcon(p, hit, label, edgeAction, isSelected);
}

// Iterate a diagram's edges, pairing each path with its label by index. Mermaid emits one label
// element per edge in path order (an empty one for an unlabelled arrow), so the index pairing stays
// aligned even when some arrows carry no label. `fn(path, label, match)` gets the L_<src>_<dst>_<i>.
function eachEdge(root, fn) {
  const paths = [...root.querySelectorAll('.edgePaths path.flowchart-link')];
  const labels = [...root.querySelectorAll('.edgeLabels > g.edgeLabel')];
  paths.forEach((p, i) => {
    // Mermaid edge id: `<graph>-L_<src>_<dst>_<index>` — so the pattern stays UNANCHORED at the front
    // (the diagram-name prefix is not ours to match). Both endpoints are spelled out as EITHER a
    // process id (`U_<n>` — the only ids carrying an underscore) or an underscore-free id, so the
    // split is unambiguous at either end: `L_U_0_S1_0` -> (U_0, S1, 0) and, now that the Deployment
    // view draws process->process channel arrows, `L_U_0_U_15_0` -> (U_0, U_15, 0). A greedy `.+`
    // source would mis-split the latter into src=`U_0_U`, dst=`15`. A lane-to-lane arrow
    // (`L_L_proc_L_subs_0`) matches nothing and is skipped — scaffolding with no node behind it.
    const m = p.id.match(/L_(U_\d+|[^_]+)_(U_\d+|[^_]+)_(\d+)$/);
    if (m) fn(p, labels[i] || null, m);
  });
}

// Stroke an edge's path + glow its label (selection highlight); returns a cleanup fn.
function glowEdge(p, label, revealAction = true) {
  // Preserve any BASE inline stroke/width the arrow already carries (a synthetic arrow sets its own thick
  // dashed base — see markSyntheticEdge) so deselecting restores it, not Mermaid's default. dasharray is
  // never touched here, so a dashed synthetic arrow stays dashed through the whole select cycle.
  const s0 = p.style.getPropertyValue('stroke'), sp0 = p.style.getPropertyPriority('stroke');
  const w0 = p.style.getPropertyValue('stroke-width'), wp0 = p.style.getPropertyPriority('stroke-width');
  p.style.setProperty('stroke', '#2563eb', 'important');
  p.style.setProperty('stroke-width', '3px', 'important');
  if (label) label.style.filter = HILITE;
  if (p._actionIcon) {
    p._actionIcon._selected = !!revealAction;
    if (revealAction) showIcon(p._actionIcon); else hideIcon(p._actionIcon);
  }
  return () => {
    if (s0) p.style.setProperty('stroke', s0, sp0); else p.style.removeProperty('stroke');
    if (w0) p.style.setProperty('stroke-width', w0, wp0); else p.style.removeProperty('stroke-width');
    if (label) label.style.filter = '';
    if (p._actionIcon) { p._actionIcon._selected = false; hideIcon(p._actionIcon); }
  };
}
// Synthetic (aggregated, count-labelled) arrows — the ones that bundle several sub-arrows and drill to a
// card — take the same visual language as a container BOX border: dashed, and (SYN_EDGE_THICK) a medium
// weight. So a dashed line reads as "a collapsed bundle, open it", mirroring a dashed box = "a collapsed
// container". The width sits BETWEEN a normal arrow and the 2.5px container border, so a bundle stands
// out without shouting like a frame. Set inline !important because an id-scoped Mermaid rule would
// otherwise outrank a class; glowEdge save/restores the width across a selection.
const SYN_EDGE_THICK = true;      // B: dashed + medium weight. Flip to false for A: dashed only.
const SYN_EDGE_WIDTH = '2px';     // between a normal arrow and the 2.5px container border (tune to taste)
function markSyntheticEdge(p) {
  if (!p) return;
  p.style.setProperty('stroke-dasharray', '6 3', 'important');
  if (SYN_EDGE_THICK) p.style.setProperty('stroke-width', SYN_EDGE_WIDTH, 'important');
}

// Wire one edge for the SELECT model (highlight + focus + panel) — context, components, internal edges.
// An edge's focus contribution: keep both endpoints + the edge itself lit. null when neither endpoint is
// drawn here (an aggregated arrow whose ends aren't in this scene) — so it doesn't dim the whole view.
function edgeFocus(scene, e) {
  if (!(scene.nodeEls[e.src] || scene.nodeEls[e.dst])) return null;
  return { nodes: new Set([e.src, e.dst]), edge: (x) => x.src === e.src && x.dst === e.dst };
}
function edgeDesc(scene, p, label, e, selKey, showFn) {
  return { key: selKey, glow: (reveal) => glowEdge(p, label, reveal),
           focus: edgeFocus(scene, e), show: showFn };
}
// `opts.onDrill` (optional) makes an ⌥-click drill instead of select, and marks the arrow with the drill
// cursor; `opts.actionFn` is its preview. `opts.action` adds an explicit icon action without changing
// the arrow's ordinary click behavior.
function bindSelectEdge(scene, p, label, e, selKey, showFn, opts) {
  opts = opts || {};
  const desc = edgeDesc(scene, p, label, e, selKey, showFn);
  const hoverOn = () => { if (!selHas(scene, selKey)) { p.style.filter = HOVER; if (label) label.style.filter = HOVER; } };
  const hoverOff = () => { if (!selHas(scene, selKey)) { p.style.filter = ''; if (label) label.style.filter = ''; } };
  scene.selectors[selKey] = () => selAdd(scene, desc);  // so back/forward can restore this edge selection
  const onClick = (ev) => {
    if (isDrag(ev)) return;  // tail of a drag-pan, not a real click
    ev.stopPropagation();
    if (opts.onDrill && isDrillClick(ev)) { hoverOff(); opts.onDrill(); return; }  // ⌥-click drills in
    hoverOff();  // drop the hover glow before selecting, so it can't linger under HILITE
    if (ev.shiftKey) { frameArrow(p); return; }  // shift-click is a pure camera move — frame the arrow, never select
    pickSel(scene, desc, ev);  // ⌘-click toggles into the multi-selection, a plain click replaces
  };
  scene.edgeEls.push({ e, path: p, label, key: selKey });  // `key` lets coverKeys select this arrow for a synthetic-arrow drill
  attachEdgeHandlers(p, label, onClick, hoverOn, hoverOff, opts.onDrill, opts.actionFn,
    () => selRevealsAction(scene, selKey), opts.action);
}

// An inter-subsystem arrow (Subsystems map + neighbourhood cross arrows): a plain click SELECTS it —
// the sidebar lists every component→component crossing it bundles — and a ⌘-click drills into the
// two-subsystem edge view. Reuses the select-edge machinery with a container-edge panel + tip.
// `focusE` overrides the endpoints used for the focus/dim pass (not the select/drill, which always act
// on the subsystem pair a→b). In the Subsystems overview the drawn arrow IS a→b, so it's omitted; in a
// subsystem card the arrow is drawn component→neighbour, so the caller passes the DRAWN endpoints —
// otherwise selecting the component wouldn't keep its own cross arrow + the neighbour box lit.
function bindContainerEdge(scene, p, label, a, b, focusE) {
  markSyntheticEdge(p);
  const drawn = focusE || { src: a, dst: b };
  const isComp = (id) => GRAPH.nodes[id] && GRAPH.nodes[id].kind === 'component';
  // When the clicked arrow is a single member component's cross arrow, ⌘-drill lands on the pair's edge
  // card with THAT component selected (its crossings lit, the rest of the pair dimmed) — so the zoom
  // keeps the same focus as the click instead of widening to the whole subsystem. A box↔box arrow (the
  // Subsystems overview) has no component end, so it opens the pair unfocused, as before. If the picked
  // component isn't drawn in the edge card, render falls back to the plain two-subsystem panel.
  const focusComp = isComp(drawn.src) ? drawn.src : (isComp(drawn.dst) ? drawn.dst : null);
  // Drill lands on the crossings LIST. For a member's cross-arrow, carry the drawn endpoints as `efocus`
  // so the list is narrowed to just that member's crossings; a box↔box arrow lists the whole pair. `sels`
  // pre-selects, in the edge card, exactly the real arrows this one synthetic arrow stood for.
  const edge = focusComp ? { kind: 'edge', a, b, efocus: { src: drawn.src, dst: drawn.dst } } : { kind: 'edge', a, b };
  edge.selCover = bundleAtoms(containerEdgeList(a, b, drawn));
  // Key the selection by the DRAWN endpoints, not the collapsed pair: a card can draw several arrows to
  // the same neighbour (one per member component), and each is its own selectable arrow with its own
  // filtered panel.
  bindSelectEdge(scene, p, label, drawn, 'sedge:' + drawn.src + '>' + drawn.dst,
    () => showContainerEdge(a, b, drawn),
    { onDrill: () => go(edge), actionFn: () => actionTipEdge(a, b, drawn) });
}
// A bridge arrow across the structural↔domain groupings (component↔subdomain in a subsystem card,
// subsystem↔entity in a subdomain card, labelled owns/reads). Registered as an edge with its DRAWN
// endpoints so a focus pass keeps it + both ends lit; a plain click shows the collapsed `box`'s panel,
// a ⌘-click drills into `target` (that box's own card). The bridge has no `why`, so the default tip
// shows nothing on hover — consistent with a why-less component edge.
function bindBridgeEdge(scene, p, label, a, b, target) {
  markSyntheticEdge(p);
  const drawn = { src: a, dst: b };
  const kindOf = (id) => GRAPH.nodes[id] && GRAPH.nodes[id].kind;
  // Focus the LEAF end (the component or entity) on drill: it's a real, selectable node in the bridge
  // card (the subsystem/subdomain end is a frame), and highlighting it lights exactly its C→E links —
  // the bridge analog of the container drill focusing its member. pendingCenter centres it on arrival.
  const leaf = (kindOf(a) === 'component' || kindOf(a) === 'entity') ? a
    : (kindOf(b) === 'component' || kindOf(b) === 'entity') ? b : null;
  // Pre-select, in the bridge card, the arrows that cover the component→entity links this one synthetic
  // arrow stood for (`selCover` — resolved against whatever the card drew, individual or re-bundled); the
  // leaf `sel` stays as a fallback if the card drew none of them.
  const tgt = { ...target, selCover: bundleAtoms(bridgeEdgeList(drawn)) };
  if (leaf) tgt.sel = 'node:' + leaf;
  bindSelectEdge(scene, p, label, drawn, 'bridge:' + a + '>' + b,
    () => showBridgeEdge(drawn),
    { onDrill: () => { if (leaf) pendingCenter = leaf; go(tgt); }, actionFn: () => actionTipEdge(a, b, drawn) });
}

// `resolve(match)` maps a path id (L_<src>_<dst>_<i>) to { e, selKey, showFn, opts? } or null to skip.
function bindEdges(scene, resolve) {
  eachEdge(scene.root, (p, label, m) => {
    const r = resolve(m);
    if (r) bindSelectEdge(scene, p, label, r.e, r.selKey, r.showFn, r.opts);
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
  // Parallel component edges are separate rendered arrows. Keep their selectors distinct so a
  // relationship Locate can select every one instead of whichever selector happened to register last.
  return { e, selKey: 'edge:' + e.src + '>' + e.dst + ':' + m[3], showFn: () => showEdge(e) };
}

// --- navigation history ---------------------------------------------------------
// A linear stack of view "states" (one per diagram-changing click); back/forward move the index.
// Selecting a node/edge for details is NOT a separate history entry — but the current selection is
// remembered PER VIEW: captured on the state we leave and restored when we step back/forward to it.
//   state = { kind: 'context' | 'container' | 'component' | 'subsystem' | 'edge', ..., vp?, sels?, flow? }
// vp = { zoom, pan }, sels = selection keys, and flow = {cur, active}; all are captured when we leave
// a view, so stepping back/forward restores it exactly as it was (a fresh drill via go() has none and
// fits/centers with nothing selected).
let history = [];
let hi = -1;  // index of the current state
// A diagram's last pan/zoom, keyed by its view identity (stateKey), NOT by its history slot. So the
// same diagram reached any way — back/forward, a tab, a breadcrumb crumb, or a fresh drill — reopens at
// the zoom + position it was last left at, instead of a fresh fit. (Per-entry `vp` below covers only the
// exact history slot; this covers the diagram wherever it reappears.)
const vpByView = {};
// The last state visited under each top-level tab (keyed by topView(kind)), so switching AWAY from a tab
// and back reopens it exactly where it was left — drill depth, selection, camera and right-pane included —
// instead of resetting to the tab's overview. Updated on every leave (see captureViewState). Clicking the
// tab you are ALREADY on ignores this and resets to the overview (see goTab/resetTab).
const tabLast = {};

function stateKey(s) {
  return s.kind + (s.sid ? ':' + s.sid : '') + (s.a ? ':' + s.a + '>' + s.b : '')
    + (s.hp ? ':' + s.hp : '') + (s.uc ? ':' + s.uc : '') + (s.sd ? ':' + s.sd : '')
    + (s.unit ? ':' + s.unit : '')  // deploymentUnit cards are keyed by unit name (else they collide)
    + (s.store ? ':' + s.store : '')  // Data-view cross-links focus a store pane — key on it so a
    + (s.entity ? '#' + s.entity : '')  // store→store / row jump actually re-renders (not a no-op)
    + (s.blk ? ':' + s.blk : '')    // Business-logic cross-links focus a BLOCK pane — same reason
    + (s.br ? '#' + s.br : '')      // …and a rule row inside it
    + (s.bkid ? ':' + s.bkid : '');  // bucketfold drills are keyed by their BKF id
}
// The RIGHT-PANE state a history point remembers, on top of the diagram + selection: a file open at a
// scroll offset, or the file browser showing. Restored on back/forward so returning to a point reopens
// the exact file (where you were) or the browser — not merely whatever the selection would imply.
function snapContent() {
  if (!SERVED) return null;
  if (treeBrowsing) return { browse: true };
  if (cvPath) return { file: cvPath, top: cvscroll ? cvscroll.scrollTop : 0 };
  return null;
}
// A transition sometimes needs the LEAVING pane recorded as something other than "what's showing right
// now" — e.g. "the browser", captured before the browser is torn down to reveal the opened file. Set
// this and the next captureViewState uses it once.
let pendingLeaveContent;
// Apply a remembered pane. A file already fully shown just gets its scroll restored (no refetch);
// otherwise the file loads (renderCode applies cvPendingTop once its table exists) or the browser opens.
let cvPendingTop = null;
function applyContent(c) {
  if (!SERVED || !c) return;
  if (c.browse) { setBrowsing(true); return; }
  if (c.file) {
    suppressBrowse = true; setBrowsing(false);
    if (c.file === cvPath && cvTable) { cvscroll.scrollTop = c.top || 0; return; }
    cvPendingTop = { file: c.file, top: c.top || 0 };
    loadCode(c.file, null);
  }
}
// Consume a pending scroll offset once the matching file's table has been (re)built by renderCode/-Diff.
function applyPendingScroll(path) {
  if (cvPendingTop && path && cvPendingTop.file === path && cvscroll) {
    cvscroll.scrollTop = cvPendingTop.top;
    cvPendingTop = null;
  }
}
// Drop a pending scroll for `path` without applying it — for an exit that renders no table (a failed /
// empty / binary / too-large load), so a stale offset can't fire on a later successful load.
function clearPendingScroll(path) {
  if (cvPendingTop && path && cvPendingTop.file === path) cvPendingTop = null;
}
function captureViewState() {  // stash the leaving entry's pan/zoom + selection + right-pane content
  if (hi < 0 || !history[hi]) { pendingLeaveContent = undefined; return; }
  if (mainPz) {
    const vp = { zoom: mainPz.getZoom(), pan: mainPz.getPan() };
    history[hi].vp = vp;
    vpByView[stateKey(history[hi])] = vp;  // remember this diagram's view so any later return reuses it
  }
  // Capture the WHOLE multi-selection (ordered keys), so back/forward restores every selected element, not
  // just the primary. `sels` supersedes the old scalar `sel`; a freshly-built navigation state may still
  // carry a single requested `sel` (a focus-drill / flow-step link) — restoreSelection handles both.
  history[hi].sels = mainScene ? mainScene.selection.map((d) => d.key) : null;
  history[hi].flow = flowSnapshot();
  history[hi].content = (pendingLeaveContent !== undefined) ? pendingLeaveContent : snapContent();
  pendingLeaveContent = undefined;
  // Remember where this tab was left (a shallow clone so later mutation of the history entry can't
  // rewrite it), so a return to the tab restores this exact spot rather than the overview.
  tabLast[topView(history[hi].kind)] = { ...history[hi] };
}
// Record a new history point that keeps the CURRENT diagram view + selection and changes only the right
// pane (a file switch in the menu, or opening a file from the browser). Back/forward step through these
// like any other point; the caller has already applied `content` to the pane.
function pushContentPoint(content) {
  if (hi < 0) return;
  captureViewState();
  const c = history[hi];
  history = history.slice(0, hi + 1);
  // EVERY field `stateKey` reads has to survive, or opening a file from a focused pane silently
  // drops back to that tab's overview. `store`/`entity` were already missing when this list was
  // written by hand; `blk`/`br` are the same shape one view over.
  history.push({ kind: c.kind, sid: c.sid, a: c.a, b: c.b, hp: c.hp, uc: c.uc, sd: c.sd,
                 unit: c.unit, store: c.store, entity: c.entity, blk: c.blk, br: c.br,
                 bkid: c.bkid, sels: c.sels, flow: c.flow, content });
  hi = history.length - 1;
  renderChrome(history[hi]);  // refresh the nav buttons (Back is now enabled)
}
function go(state, instant) {
  if (hi >= 0 && stateKey(history[hi]) === stateKey(state)) return;  // already here
  const from = history[hi];
  captureViewState();
  history = history.slice(0, hi + 1);  // a new branch drops any forward history
  history.push(state);
  hi = history.length - 1;
  driveTransition(from, instant);
}
function back() { if (hi > 0) { const from = history[hi]; captureViewState(); hi -= 1; driveTransition(from); } }
function fwd() { if (hi < history.length - 1) { const from = history[hi]; captureViewState(); hi += 1; driveTransition(from); } }
// A top-bar tab click. Switching to a DIFFERENT tab reopens it where it was last left (its remembered
// drill + selection + camera + pane); its first visit lands on the overview. Clicking the tab you are
// ALREADY on is a "reset" — it zooms back out to that tab's plain overview (see resetTab).
function goTab(view) {
  const cur = hi >= 0 ? topView(history[hi].kind) : null;
  if (view === cur) { resetTab(view); return; }
  const saved = tabLast[view];
  go(saved ? { ...saved } : { kind: view }, true);  // instant: a tab switch never plays the drill zoom
}
// Reset the current tab to its overview: fresh fit, nothing selected, default panel. Drop the remembered
// camera for the overview so it re-fits instead of reopening at an old zoom. A tab click never animates,
// so a reset from a drill-down cuts straight to the overview (instant); already sitting on the overview,
// go() would no-op, so re-render in place after stripping this entry's camera/selection/pane.
function resetTab(view) {
  const root = { kind: view };
  delete vpByView[stateKey(root)];
  if (hi >= 0 && stateKey(history[hi]) === stateKey(root)) { history[hi] = root; render(); }
  else go(root, true);
}

// --- drill "dive" transition ----------------------------------------------------
// Drilling into a container is a full re-render of a different diagram, so on its own it reads as a hard
// cut. To make the descent legible, the swap is bracketed by a "dive": the leaving view scales UP into the
// target container's box (it grows to fill the pane) and fades, then the entering card settles in from
// slightly oversized. Going back up plays the reverse (a zoom-out). A jump that skips levels (A ▸ B ▸ C
// straight to C) dives once PER level, briefly flashing each intermediate card, so the multi-level descent
// is explicit. Honors prefers-reduced-motion (instant) and bails cleanly if a newer navigation interrupts.
const REDUCE_MOTION = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
const DIVE_EXIT_MS = 190, DIVE_ENTER_MS = 200, DIVE_FLASH_MS = 150;
let navSeq = 0;  // bumped per navigation; a running dive bails when it changes (interrupted by a newer one)
function focusOf(s) {  // the container a view sits "inside" (null = an overview / non-container view)
  if (!s) return null;
  if (s.kind === 'subsystem') return s.sid;
  if (s.kind === 'domsub') return s.sd;
  if (s.kind === 'deploymentUnit') return unitProcessNodeId(s.unit);  // a process card sits "inside" its process box
  return null;
}
function cardStateFor(fid) {  // the view that shows container `fid` as its own card
  const n = GRAPH.nodes[fid];
  if (!n) return null;
  if (n.kind === 'subsystem') return { kind: 'subsystem', sid: fid };
  if (n.kind === 'subdomain') return { kind: 'domsub', sd: fid };
  if (n.kind === 'process') return { kind: 'deploymentUnit', unit: n.unit };
  return null;
}
// The focus nodes to descend through from container `from` (null = an overview) down to `to`, inclusive of
// `to`. null when `to` isn't nested under `from` (i.e. not a drill-in at all). A node with no parent
// (undefined) is normalized to null so it reads as top-level (reaches an overview `from` of null) — a
// process box has no parent pointer but drills straight out of the Deployment overview.
function drillChain(from, to) {
  const chain = []; let cur = to; const seen = new Set();
  while (cur && cur !== from && !seen.has(cur)) { seen.add(cur); chain.unshift(cur); cur = (GRAPH.nodes[cur] && GRAPH.nodes[cur].parent) || null; }
  return cur === from ? chain : null;
}
function diagramBoxCenter(id) {  // on-screen centre of a drawn box in the current diagram (null if absent)
  const el = mainScene && mainScene.nodeEls[id];
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return r.width ? { x: (r.left + r.right) / 2, y: (r.top + r.bottom) / 2 } : null;
}
function clearDiveStyle() { const d = diagram; d.style.transition = d.style.transform = d.style.transformOrigin = d.style.opacity = ''; }
function delay(ms) { return new Promise((res) => setTimeout(res, ms)); }
function diveOut(center, up) {  // scale the current #diagram away (toward `center` when diving in) + fade out
  return new Promise((res) => {
    const d = diagram, r = d.getBoundingClientRect();
    const c = center || { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    d.style.transformOrigin = (c.x - r.left) + 'px ' + (c.y - r.top) + 'px';
    d.style.transition = 'transform ' + DIVE_EXIT_MS + 'ms ease-in, opacity ' + DIVE_EXIT_MS + 'ms ease-in';
    void d.offsetWidth;
    d.style.transform = 'scale(' + (up ? 2.6 : 0.5) + ')';
    d.style.opacity = '0';
    setTimeout(res, DIVE_EXIT_MS);
  });
}
function diveIn(up) {  // the freshly-rendered #diagram settles in from slightly off-scale
  return new Promise((res) => {
    const d = diagram;
    d.style.transition = 'none'; d.style.transformOrigin = '50% 50%';
    d.style.transform = 'scale(' + (up ? 1.06 : 0.94) + ')'; d.style.opacity = '0';
    void d.offsetWidth;
    d.style.transition = 'transform ' + DIVE_ENTER_MS + 'ms ease-out, opacity ' + DIVE_ENTER_MS + 'ms ease-out';
    d.style.transform = 'scale(1)'; d.style.opacity = '1';
    setTimeout(() => { clearDiveStyle(); res(); }, DIVE_ENTER_MS);
  });
}
// Select the container we zoomed out FROM in the view we land on — so the reader sees where they were.
// It may not be drawn directly (a nested container isn't on the top-level overview), so walk up its
// lineage to the first box the new view actually draws (e.g. its top-level ancestor).
function selectLeftContainer(fromF) {
  let cur = fromF; const seen = new Set();
  while (cur && !seen.has(cur)) {
    seen.add(cur);
    const el = mainScene && mainScene.nodeEls[cur];
    if (el) { selectNode(mainScene, el, cur); return; }
    cur = GRAPH.nodes[cur] && GRAPH.nodes[cur].parent;
  }
}
// Decide whether a navigation is a container drill and, if so, animate it; otherwise render straight.
function driveTransition(from, instant) {
  const to = history[hi];
  // A content-only step (same diagram view — a file switch, or a browser open/close): leave the diagram
  // untouched and just restore the right pane (+ any selection change) and refresh the chrome.
  if (from && to && mainScene && stateKey(from) === stateKey(to)) {
    if (!restoreSelection(mainScene, to)) resetScene(mainScene);  // replay the whole saved selection, else clear
    restoreFlowSnapshot(to.flow);
    applyContent(to.content);
    renderChrome(to);
    return;
  }
  const my = ++navSeq;
  clearDiveStyle();
  // A tab switch is not a drill — render the target straight (its remembered camera restored inside
  // render), never the zoom-in/out dive, regardless of how the two views nest.
  if (instant) { render(); return; }
  const fromF = from ? focusOf(from) : null, toF = focusOf(to);
  const inChain = (from && toF) ? drillChain(fromF, toF) : null;
  // drill OUT: leaving a container UP to an ancestor container's card, or to the overview tab it belongs to
  // (NOT a lateral tab switch — going from a card to Dependencies/Domain/Happy Path stays instant).
  const fromKind = fromF && GRAPH.nodes[fromF] && GRAPH.nodes[fromF].kind;
  const isOut = !!fromF && ((toF && drillChain(toF, fromF))
    || (toF == null && ((fromKind === 'subsystem' && to.kind === 'container') || (fromKind === 'subdomain' && to.kind === 'domain')
      || (fromKind === 'process' && to.kind === 'deployment'))));
  if (REDUCE_MOTION || !from) {  // no animation — still select the left-behind container on a zoom-out
    render().then(() => { if (my === navSeq && isOut) selectLeftContainer(fromF); });
    return;
  }
  if (inChain && inChain.length) { runDrill(inChain, my).catch(() => { clearDiveStyle(); render(); }); return; }
  if (isOut) { runDrillOut(my, fromF).catch(() => { clearDiveStyle(); render(); }); return; }
  render();  // lateral / unrelated navigation — no dive
}
async function runDrill(chain, my) {
  for (let i = 0; i < chain.length; i++) {
    const center = diagramBoxCenter(chain[i]);  // where the next container sits in the current view
    await diveOut(center, true); if (my !== navSeq) return;
    diagram.style.transition = 'none'; diagram.style.transform = 'none';  // untransform for the render's fit (still opacity 0)
    const last = i === chain.length - 1;
    await render(last ? undefined : cardStateFor(chain[i]), !last);  // final via history; intermediates transient
    if (my !== navSeq) return;
    await diveIn(true); if (my !== navSeq) return;
    if (!last) { await delay(DIVE_FLASH_MS); if (my !== navSeq) return; }
  }
}
async function runDrillOut(my, leftF) {
  await diveOut(null, false); if (my !== navSeq) return;
  diagram.style.transition = 'none'; diagram.style.transform = 'none';
  await render(); if (my !== navSeq) return;
  selectLeftContainer(leftF);  // highlight the container we zoomed out from, so the reader keeps their place
  await diveIn(false);
}

// --- per-state binding ----------------------------------------------------------
function bindContext() {
  bindNodes(mainScene, (id, el, e) => {
    if (id === 'SYS') {  // the System box: ⌘-click drills in, a plain click selects (shows its overview)
      if (isDrillClick(e)) { const t = sysDrillTarget(); if (t) go(t); return; }
      selectNodeFromCanvas(el, id, e);
      return;
    }
    if (id === LIBS_ID) {  // collapsed Libraries box: ⌥-click drills to the full list, shift=frame, ⌘=multi-select, plain=select
      if (isDrillClick(e)) { go({ kind: 'libs' }); return; }
      pickSelBox(mainScene, libsFoldDesc(mainScene, el), el, e);
      return;
    }
    if (tryFoldNodeClick(id, el, e)) return;
    if (tryDataDrillClick(id, e)) return;   // a store/broker box drills into its Data-tab section
    selectNodeFromCanvas(el, id, e);
  });
  bindEdges(mainScene, resolveContextEdge);
  markSysDrill();
  markLibsDrill();
  markDataDrill();
  registerFoldSelectors();
  // The Libraries fold selects to its own roster panel (not a plain node panel), so pre-register its
  // re-select — the generic node loop in render() then skips it, keeping back/forward faithful.
  const libsEl = mainScene.nodeEls[LIBS_ID];
  if (libsEl) mainScene.selectors['node:' + LIBS_ID] = () => selAdd(mainScene, libsFoldDesc(mainScene, libsEl));
}
// A folded-bucket count box click (shared by the Context view and the Libraries drill, which both draw
// them): ⌥-click drills to its members, a plain/⌘ click previews/multi-selects its roster. Returns true when handled.
function tryFoldNodeClick(id, el, e) {
  const n = GRAPH.nodes[id];
  if (!n || n.kind !== 'bucketfold') return false;
  if (isDrillClick(e)) { go({ kind: 'bucketfold', bkid: id }); return true; }
  pickSelBox(mainScene, bucketFoldDesc(mainScene, el, id), el, e);
  return true;
}
// Tag every present count box with the drill cursor + pre-register its roster re-select (the generic
// node loop then skips it, keeping back/forward faithful). Only boxes drawn in THIS scene get wired.
function registerFoldSelectors() {
  markBucketFoldDrill();
  (FOLDED_BUCKETS || []).forEach((b) => {
    const bel = mainScene.nodeEls[b.id];
    if (bel) mainScene.selectors['node:' + b.id] = () => selAdd(mainScene, bucketFoldDesc(mainScene, bel, b.id));
  });
}
// The Libraries drill-down: the System + every folded in-process dep (grouped by purpose bucket — big
// buckets themselves fold into drillable count boxes here too). A count box drills; SYS and each leaf
// dep select to their panel; arrows resolve via the context-edge bridge.
function bindLibs() {
  bindNodes(mainScene, (id, el, e) => {
    if (tryFoldNodeClick(id, el, e)) return;
    if (tryDataDrillClick(id, e)) return;
    selectNodeFromCanvas(el, id, e);
  });
  bindEdges(mainScene, resolveContextEdge);
  markDataDrill();
  registerFoldSelectors();
}
function bindComponent() {
  bindNodes(mainScene, (id, el, e) => selectNodeFromCanvas(el, id, e));
  bindEdges(mainScene, resolveComponentEdge);
}
// A "container" altitude (Subsystems or the Domain Subdomains overview): group boxes that
// SELECT on a plain click (box + its linked neighbours) and DRILL on a ⌘-click, plus derived
// inter-group arrows. `drillFor(id)` is the drill-in state; `edgeBinder` wires each arrow. Shared so
// the component-subsystem and entity-subdomain overviews behave identically (the bridge is symmetry).
// `noDrillId` (optional) is a box drawn here that you are already zoomed INTO — it keeps plain-click
// select but gets no drill class, no ⌘-drill and (via scene.noAction) no corner icon. `drillFor` may
// also return NULL for a box that leads nowhere from this view (an external service on the Deployment
// overview): same treatment. A box only ever shows the drill cursor when a ⌘-click will actually take
// you somewhere — promising a zoom and then re-rendering the same view reads as a broken control.
function bindGroupContainer(drillFor, edgeBinder, noDrillId) {
  mainScene.root.querySelectorAll('g.node').forEach((el) => {
    const id = idOf(el);
    // A product-area container is drawn by the deployment renderer, not the model, so it has no
    // GRAPH node — without this it fell through the gate and got no handler at all, leaving the
    // box inert (visible, but neither selectable nor drillable).
    if (!id || !(GRAPH.nodes[id] || isDeploymentGroup(id))) return;
    mainScene.nodeEls[id] = el;
    el.style.cursor = 'pointer';
    const target = id === noDrillId ? null : drillFor(id);
    if (target) el.classList.add('drill'); else mainScene.noAction.add(id);
    bindHoverGlow(mainScene, el, id);
    attachTip(el, () => actionTipNode(id));
    el.addEventListener('click', (e) => {
      if (isDrag(e)) return;
      // Excluded by the environment filter: inert. `pointer-events:none` already stops a real cursor,
      // but the guard also covers a click that arrives any other way, so "not selectable" is a property
      // of the box rather than of CSS hit-testing.
      if (el.classList.contains('envout')) return;
      e.stopPropagation();
      if (target && isDrillClick(e)) { go(target); return; }  // ⌘-click drills in
      selectNodeFromCanvas(el, id, e);
    });
  });
  eachEdge(mainScene.root, (p, label, m) => {
    const a = m[1], b = m[2];
    const known = (x) => !!(GRAPH.nodes[x] || isDeploymentGroup(x));
    if (!(known(a) && known(b))) return;
    edgeBinder(mainScene, p, label, a, b);
  });
}
function bindContainer() { bindGroupContainer((id) => ({ kind: 'subsystem', sid: id }), bindContainerEdge); }
// The Deployment view (overview + per-process card): a process box ⌘-drills to its unit card, a
// subsystem box ⌘-drills (cross-navigates) to its subsystem card, a store/broker box opens its
// Data-tab section, and anything else returns null — bindGroupContainer then leaves it without a drill
// cursor or corner icon, instead of offering a zoom that lands back on the same view.
function deploymentDrill(id) {
  if (isDeploymentGroup(id)) return { kind: 'deploymentGroup', gid: id };
  const n = GRAPH.nodes[id];
  if (n && n.kind === 'process') return { kind: 'deploymentUnit', unit: n.unit };
  if (n && n.kind === 'subsystem') return { kind: 'subsystem', sid: id };
  // A store/broker box drills into its Data-tab section here too — the same gesture it already has on
  // Dependencies, the Libraries fold and the bucket drills. An affordance that works in one view and
  // not the next is worse than no affordance.
  return dataDrillFor(id);  // null for an ungrouped component / a service with no data — no drill at all
}
// The async channels a process→process arrow carries — DEPLOYMENT_EDGES['U_a>U_b'], the deployment
// analog of containerEdgeList. Empty for a `runs`/infra arrow (those bundle nothing selectable).
function deploymentEdgeList(a, b) { return (DEPLOYMENT_EDGES && DEPLOYMENT_EDGES[a + '>' + b]) || []; }
// Where ⌘-clicking a process→process arrow drills: the Data tab's section for the broker the channels
// ride, where each one already has a full card (publishers, consumers, payload). Only when every
// channel on the arrow shares ONE broker — otherwise the drill would have to pick a winner. null when
// the broker has no Data-view section, and the arrow then only selects.
function channelDrillFor(chans) {
  const brokers = new Set(chans.map((c) => c.broker).filter(Boolean));
  return brokers.size === 1 ? dataDrillFor([...brokers][0]) : null;
}
// The broker the drill actually lands on — resolved the SAME way channelDrillFor picks it, so the
// ⌥-hover tip can never name a different broker than the one it opens (the first channel on the arrow
// may carry no broker at all).
function channelDrillBroker(chans) {
  const withBroker = chans.filter((c) => c.broker);
  return withBroker.length ? withBroker[0].brokerName : '';
}
// A Deployment arrow. A process→process one carries real per-edge detail (the channels it was derived
// from), so it SELECTS to a panel listing them and ⌘-drills to its broker's data section — the same
// idiom as an inter-subsystem arrow. A `runs`/infra arrow bundles nothing, so it stays inert: marked
// synthetic and registered in the scene (src→dst) only so selecting a process dims to its
// neighbourhood — its targets stay lit while the rest fades.
function markDeploymentEdge(scene, p, label, a, b) {
  const chans = deploymentEdgeList(a, b);
  const xproc = (DEPLOYMENT_CALL_EDGES && DEPLOYMENT_CALL_EDGES[a + '>' + b]) || [];
  const calls = (DEPLOYMENT_INFRA_EDGES && DEPLOYMENT_INFRA_EDGES[a + '>' + b]) || [];
  markSyntheticEdge(p);
  if (chans.length || xproc.length) {   // process→process: one arrow, either or both mechanisms
    const drill = channelDrillFor(chans);
    bindSelectEdge(scene, p, label, { src: a, dst: b }, 'uedge:' + a + '>' + b,
      () => showDeploymentEdge(a, b, chans, xproc),
      drill ? { onDrill: () => go(drill), actionFn: () => actionTipChannels(chans) } : undefined);
    return;
  }
  if (calls.length) {   // a coupling-point arrow: it stands for real call sites, so it is selectable too
    const drill = dataDrillFor(b);
    bindSelectEdge(scene, p, label, { src: a, dst: b }, 'uedge:' + a + '>' + b,
      () => showDeploymentInfraEdge(a, b, calls),
      drill ? { onDrill: () => go(drill), actionFn: () => actionTipNode(b) } : undefined);
    return;
  }
  scene.edgeEls.push({ e: { src: a, dst: b }, path: p, label });  // `runs` lane arrow: nothing to show
}
function actionTipChannels(chans) {
  const nm = channelDrillBroker(chans);
  return '<div class="tt">Open data</div>' + (nm ? '<div class="tm">' + esc(nm) + '</div>' : '');
}
// Selecting a process→process arrow: list the async channels it stands for — name, kind, the broker
// they ride and the line that declares each — so the wiring between two processes is readable without
// leaving the map. Mirrors showContainerEdge's shape (title + count + one uniform list).
function showDeploymentEdge(a, b, chans, calls) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  chans = chans || []; calls = calls || [];
  // Async rows lead with the channel; sync rows lead with `caller → callee`, since both ends vary.
  const chanRows = chans.map((c) => '<li class="xrow"><div class="xpair">' + esc(c.name) + '</div>'
    + '<div class="xwhy"><span class="tb-kind">' + esc(c.kind || 'channel') + '</span>'
    + (c.brokerName ? 'via ' + esc(c.brokerName) + ' ' : '') + srcCell(c.source || '')
    + '</div></li>').join('');
  const callRows = calls.map((c) => '<li class="xrow">'
    + '<div class="xpair">' + esc(c.srcName) + ' &rarr; ' + esc(c.dstName) + '</div>'
    + '<div class="xwhy">' + (c.verb ? '<span class="tb-kind">' + esc(c.verb) + '</span>' : '')
    + (c.why ? mdInline(c.why) + ' ' : '') + srcCell(c.where || '')
    + '</div></li>').join('');
  const n = (k, one) => k + ' ' + one + (k === 1 ? '' : 's');
  const badge = (chans.length && calls.length) ? 'links' : (chans.length ? 'channels' : 'calls');
  let body = '';
  if (chans.length) body += '<div class="xcount">' + n(chans.length, 'channel') + '</div>'
    + '<ul class="xlist">' + chanRows + '</ul>';
  if (calls.length) body += '<div class="xcount"' + (chans.length ? ' style="margin-top:16px"' : '') + '>'
    + n(calls.length, 'call') + '</div><ul class="xlist">' + callRows + '</ul>';
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(nm(a)) + ' &rarr; ' + esc(nm(b)) + '</h2>'
    + '<span class="badge edge">' + badge + '</span></div>' + body;
}
// Selecting a coupling-point arrow (process → shared infrastructure): list the components INSIDE that
// process which actually reach the store/broker — each with its verb, its reason and its call site — so
// "why does this process need this" is answered on the spot. Same shape as showDeploymentEdge, its
// sibling arrow in this view: the thing the arrow stands for as the lead, its detail beneath.
function showDeploymentInfraEdge(a, b, calls) {
  const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  const items = calls.map((c) => '<li class="xrow"><div class="xpair">' + esc(c.srcName) + '</div>'
    + '<div class="xwhy">' + (c.verb ? '<span class="tb-kind">' + esc(c.verb) + '</span>' : '')
    + (c.why ? mdInline(c.why) + ' ' : '') + srcCell(c.where || '')
    + '</div></li>').join('');
  panel.innerHTML = '<div class="pane-title"><h2>' + esc(nm(a)) + ' &rarr; ' + esc(nm(b)) + '</h2>'
    + '<span class="badge edge">connections</span></div>'
    + '<div class="xcount">' + calls.length + ' connection' + (calls.length === 1 ? '' : 's')
    + ' from the code this process runs</div>'
    + '<ul class="xlist">' + items + '</ul>';
}
// `focalUnit` (set on a process card) is the process you're already zoomed into: it drills nowhere
// further, so it gets no drill affordance/icon — only the OTHER boxes (subsystems it runs) drill.
function bindDeployment(focalUnit) {
  bindGroupContainer(deploymentDrill, markDeploymentEdge, focalUnit ? unitProcessNodeId(focalUnit) : null);
  applyEnvDim(mainScene);
}
// Resolve which unit(s) actually run a self-started entry point: its own `runs_in` wins (precise),
// else the owning component's `runs_in` (coarser — a loop whose component runs in >1 unit then shows
// under each). Empty => unplaced (surfaced by showDeployment).
function threadHostUnits(ep) {
  const own = Array.isArray(ep.runs_in) ? ep.runs_in : [];
  if (own.length) return own;
  const c = ep.component && GRAPH.nodes[ep.component];
  return (c && Array.isArray(c.runs_in)) ? c.runs_in : [];
}
// The product-area container a unit belongs to (null when it is drawn as its own box).
function groupOfUnit(unit) {
  for (const gid in (DEPLOYMENT_GROUP_MEMBERS || {}))
    if ((DEPLOYMENT_GROUP_MEMBERS[gid] || []).indexOf(unit) >= 0) return gid;
  return null;
}
// A container's display text, read off the overview's own box label so the two never disagree.
function groupTitle(gid) {
  const m = new RegExp('\\b' + gid + '\\["([^"]+)"\\]').exec(MERMAID_DEPLOYMENT || '');
  // Never fall back to the raw id: a container id is internal plumbing, and "PG_3" on screen tells
  // a reader nothing. A generic label is a worse title but an honest one.
  return m ? m[1] : 'Grouped processes';
}
function unitProcessNodeId(unit) {
  for (const id in (GRAPH.nodes || {})) if (GRAPH.nodes[id].kind === 'process' && GRAPH.nodes[id].unit === unit) return id;
  return null;
}
function threadRowsHtml(eps) {
  const rows = eps.map((e) => `<tr><td>${esc(e.kind || '')}</td><td>${mdInline(e.trigger || '')}</td>`
    + `<td>${e.source ? srcCell(e.source) : ''}</td></tr>`).join('');
  return `<table class="glossary"><tbody>${rows}</tbody></table>`;
}
// Deployment overview default panel: surface the UNPLACED self-started threads (no runs_in) so they
// are never silently dropped from the view; otherwise the project overview (SYS).
function showDeployment() {
  const unplaced = (GRAPH.entry_points || []).filter((e) => e.activation === 'self' && threadHostUnits(e).length === 0);
  if (unplaced.length) {
    panel.innerHTML = `<section class="uc-group"><h3 class="uc-actor">Unplaced (${unplaced.length})</h3>`
      + `<div class="gloss-plain">These start themselves, but nothing records which process runs `
      + `them — so they appear on no process box below.</div>${threadRowsHtml(unplaced)}</section>`;
  } else if (GRAPH.nodes['SYS']) { showNode('SYS'); } else { panel.innerHTML = EMPTY_PANEL; }
}
// The environment picker (deployment variants). Present only when the map declares `environments`;
// selecting one filters the overview to that variant (empty variants = shared, shown in every env).
// The selection is module state (DEPLOY_ENV) and re-renders the current deployment scene.
// Is this box part of the selected environment? A node with no `variants` is UNGATED — present in
// every environment — so it always stays live. Only a unit that names its environments can fall out of
// one. Process boxes carry `variants` from their deployment row; an infrastructure unit's row lands on
// the dependency box standing in for it, so those dim correctly too.
function inSelectedEnv(node) {
  if (!DEPLOY_ENV) return true;
  const v = (node && node.variants) || [];
  return !v.length || v.some((x) => x && x.env === DEPLOY_ENV);
}
// Dim — rather than remove — everything the selected environment excludes, and make it unclickable.
// Removing the boxes (what the per-environment diagrams used to do) answered no question: a unit simply
// vanished, and the reader could not tell "not deployed here" from "not in the map at all". Dimmed in
// place, the answer is on screen, and the layout never moves when you switch.
function applyEnvDim(scene) {
  if (!scene) return;
  const out = new Set();
  for (const id in scene.nodeEls) {
    const off = !inSelectedEnv(GRAPH.nodes[id]);
    scene.nodeEls[id].classList.toggle('envout', off);
    if (off) out.add(id);
  }
  // An arrow is only as live as its ends: dim it when either endpoint is out of this environment.
  for (const e of scene.edgeEls) {
    const off = out.has(e.e.src) || out.has(e.e.dst);
    e.path.classList.toggle('envout', off);
    if (e.label) e.label.classList.toggle('envout', off);
  }
}
// The capability OVERLAY (a "Serving" picker that dimmed everything a chosen capability did not
// touch) was removed: choosing from a control that showed only names meant picking blind, and the
// result — a third dimming channel over the same diagram — read as noise rather than as an answer.

// ── a use case's two renderings: Map and Sequence ─────────────────────────────────────────────────
// One traced flow, drawn two ways. The SEQUENCE answers "in what order"; the MAP answers "what does
// this use case touch", in the structural views' own visual language — one kind-coloured box per
// element, entities and dependencies included, no subsystem frames (scoped to one use case a frame
// holds one or two members and reads as noise; each box names its area instead).
//
// Both are generated from the SAME expanded steps (gen_viewer.gen_flow_mermaid / gen_flow_map_mermaid),
// so they cannot disagree — and the map's arrows carry the sequence's own step numbers, so a number
// read on one rendering finds the same step on the other.
//
// Map is the default because it preserves the structural vocabulary used by the rest of the viewer;
// the choice is sticky across navigation (like DEPLOY_ENV), so a reader who switches to Sequence keeps
// it while drilling from use case to use case.
let FLOW_VIEW = 'map';   // 'map' | 'sequence'
let flowResume = null;        // {cur, active} carried only across a Map/Sequence rendering switch
const EMPTY_FLOW_MAP = 'flowchart LR\n  NOFLOW["No T6 flow recorded"]';

function flowMermaidFor(uc) {
  return FLOW_VIEW === 'map' ? (FLOWS_MAP[uc] || EMPTY_FLOW_MAP) : (FLOWS_MM[uc] || EMPTY_FLOW_MM);
}

// The card. Floats bottom-left over the diagram like the environment and capability pickers, and for
// the same reason: it changes what the diagram says, so it belongs beside it rather than in a pane that
// vanishes the moment something is selected.
//
// TWO PLACES, for any control that floats over the diagram: this function SHOWS it, and render()'s
// up-front loop HIDES it before the table tabs' early returns (those never reach the end of render, so
// a control shown on a diagram would keep floating over the table you switched to). Add a control here
// and you must add it there. `#envpicker` needs neither, because it is synced from renderChrome, which
// every exit path calls — the tidier arrangement, kept in mind if a fourth control ever appears.
// Only the MODE half is rebuilt here — the step player is
// static markup inside the same card, shown and driven by flowInit/flowCounter, so re-rendering the
// switch can never tear out the player's buttons.
function syncFlowPicker(s) {
  const card = document.getElementById('flowpicker'), el = document.getElementById('flowmode');
  if (!card || !el) return;
  const on = !!(s && s.kind === 'usecase');
  card.hidden = !on;
  if (!on) { el.innerHTML = ''; return; }
  const btn = (v, label) =>
    `<button type="button" data-fv="${v}"${FLOW_VIEW === v ? ' class="on"' : ''}>${label}</button>`;
  el.innerHTML = '<label class="cappick-lbl">Flow as</label>'
    + `<span class="uc-seg">${btn('map', 'Map')}${btn('sequence', 'Sequence')}</span>`;
  el.querySelectorAll('.uc-seg button').forEach((b) => b.addEventListener('click', () => {
    const v = b.getAttribute('data-fv');
    if (v === FLOW_VIEW) return;
    FLOW_VIEW = v;
    // Keep the reader's place: the two renderings walk the SAME steps, so switching mid-walk lands on
    // the same step in the other drawing rather than resetting to the start. flowInit consumes this.
    // `render()` nulls flowPlay synchronously but repaints asynchronously, so a second click while the
    // repaint is in flight must not overwrite a pending position with "unstarted".
    if (flowPlay) flowResume = { cur: flowPlay.cur, active: flowPlay.active };
    // Same view identity, a completely different layout (lifelines vs a box graph), so the camera
    // remembered for this view would frame the new drawing wrongly — drop it and let the new
    // rendering fit fresh. (`resetTab` drops it the same way for the same reason.)
    const cur = history[hi];
    if (cur) { delete vpByView[stateKey(cur)]; delete cur.vp; }
    render();          // same state, the other rendering of the same flow
  }));
}

// A map box's Mermaid id IS its element id — except an actor, which carries an `FAn` alias (a Role has
// no node, so there is no id to use). These two helpers cross that boundary in both directions:
// `flowMapToken` turns a drawn box id into the token a narrative step carries as its endpoint, and
// `flowMapBoxId` goes the other way — the direction the step player needs.
//
// Both go through FLOW_ACTORS, which is the ONE table in the RAW name space the narrative steps use.
// Two rejected alternatives, each of which was tried:
//   * trusting the roster's numbering while the generators numbered by a different rule — the two
//     disagreed on a draft map carrying a dangling element id. Fixed at the source instead: the
//     generators and `flow_actors` now share `is_role_endpoint`, so one alias means one participant,
//     and a test pins that agreement (test_flow_map_and_flow_actors_agree_on_every_alias).
//   * reading the names off the DRAWN boxes, which sounds authoritative but is not: a box label is
//     `_safe_label(name)`, so a role named `Ops|Team` is drawn `Ops/Team` and would never match the
//     step's raw token — its box goes inert and its steps lose their arrows.
// The lesson both times: cross the alias boundary in ONE text space, and it must be the authored one.
function flowMapToken(uc, mid) {
  if (!/^FA\d+$/.test(mid)) return mid;
  const a = (FLOW_ACTORS[uc] || []).find((x) => x.aid === mid);
  return a ? a.name : mid;
}
function flowMapBoxId(uc, id, name) {
  if (id) return id;
  const a = (FLOW_ACTORS[uc] || []).find((x) => x.name === name);
  return a ? a.aid : name;
}
// A map arrow's label is the list of flow-step numbers carried by that ordered pair. When the player
// selects one step on a MULTI-step arrow, keep that number at full opacity and dim the others so the
// shared arrow says which of its several moments is current without changing the number format.
// Rebuilding the numeric paragraph is safe: these are generated integers, and the click handlers live
// on the enclosing Mermaid edge-label group, not on this paragraph.
function flowMapPaintStepLabel(label, stepIdx, current) {
  const p = label && label.querySelector('foreignObject p');
  if (!p) return;
  const active = stepIdx.length > 1 && stepIdx.includes(current);
  const parts = [];
  stepIdx.forEach((i, k) => {
    if (k) {
      const separator = document.createElement('span');
      separator.textContent = ', ';
      if (active) separator.className = 'flow-other-step';
      parts.push(separator);
    }
    const number = document.createElement('span');
    number.textContent = String(i + 1);
    if (active && i !== current) number.className = 'flow-other-step';
    if (active && i === current) number.setAttribute('aria-current', 'step');
    parts.push(number);
  });
  p.replaceChildren(...parts);
}
// Only an actively selected STEP controls the emphasis. Selecting a bundled pair outside the stepper
// must leave every number neutral; its pane describes all of them and none is artificially current.
function flowMapRefreshStepLabels() {
  if (!flowPlay || flowPlay.kind !== 'map' || !flowPlay.mapArrows || !mainScene) return;
  const i = flowPlay.cur;
  const stepSelected = flowPlay.active && i >= 0 && selHas(mainScene, 'flowstep:' + flowPlay.uc + ':' + i);
  for (const arrow of Object.values(flowPlay.mapArrows)) {
    const current = stepSelected && arrow.stepIdx.includes(i) ? i : -1;
    flowMapPaintStepLabel(arrow.label, arrow.stepIdx, current);
  }
}
// The steps riding one arrow of the map. An arrow is a PAIR, and a pair can carry several steps (that
// is why the arrow is labelled with their numbers). A single one uses the ordinary sequence-step pane;
// a bundle stacks that same complete pane for every step with a divider between them.
function flowMapSteps(uc, a, b) {
  const ta = flowMapToken(uc, a), tb = flowMapToken(uc, b);
  const out = [];
  (FLOWS_NARR[uc] || []).forEach((st, i) => {
    if ((st.srcId || st.src) === ta && (st.dstId || st.dst) === tb) out.push({ st, i });
  });
  return out;
}
function showFlowPair(uc, a, b) {
  const steps = flowMapSteps(uc, a, b);
  if (!steps.length) { panel.innerHTML = EMPTY_PANEL; return; }
  if (steps.length === 1) { showFlowStep(uc, steps[0].i); return; }
  panel.innerHTML = steps.map(({ i }, k) => (k ? '<hr class="flow-step-separator">' : '')
    + '<section class="flow-step-detail" data-step="' + i + '">'
    + flowStepInfoHtml(uc, i, true) + '</section>').join('');
  panel.querySelectorAll('.flow-step-detail').forEach((section) => {
    bindFlowStepInfo(section, uc, +section.getAttribute('data-step'));
  });
  // An arrow bundles several steps, each grounded at a DIFFERENT call site, so this pane grounds
  // nothing: clear the code-viewer/tree highlight rather than leave the previous step's file standing
  // under a panel that no longer describes it (the same clear showEdge and showFlowStep do).
  cvElement = null;
  setTreeSelection(null);
  highlightTreePath(null);
}
function bindFlowMap(uc) {
  const scene = mainScene;
  const steps = FLOWS_NARR[uc] || [];

  // Every element box selects exactly as it does in any other diagram (glow, neighbourhood dim, its own
  // card, code-viewer sync). An ACTOR box has no GRAPH node, so bindNodes skips it — register it in the
  // scene by hand so it is a first-class box too: same glow, same neighbourhood dim (nodeFocus reads
  // scene.nodeEls/edgeEls, both of which now know the alias), only its card differs (a Role's card, not
  // an element's).
  bindNodes(scene, (id, el, ev) => {
    const locate = locateActionFor(id);
    if (locate && isDrillClick(ev)) { locate.run(); return; }
    selectNodeFromCanvas(el, id, ev);
  });
  scene.root.querySelectorAll('g.node').forEach((el) => {
    const aid = idOf(el);
    if (!aid || !/^FA\d+$/.test(aid)) return;
    // Matched by alias, which the generators and `flow_actors` allocate under one shared rule (see
    // flowMapToken). A box with no matching roster entry is left inert rather than handed some other
    // actor's card — silence beats a confident wrong name.
    const a = (FLOW_ACTORS[uc] || []).find((x) => x.aid === aid);
    if (!a) return;
    scene.nodeEls[aid] = el;
    if (el.classList.contains('human')) stickFigureNode(el);
    el.style.cursor = 'pointer';
    // Built lazily (like every other node descriptor): `nodeFocus` reads scene.edgeEls, which bindEdges
    // below fills in after this runs.
    const desc = () => ({ key: 'node:' + aid, glow: (reveal) => glowNode(el, reveal),
                          focus: nodeFocus(scene, aid), show: () => showFlowActor(uc, a) });
    scene.selectors['node:' + aid] = () => selAdd(scene, desc());
    bindHoverGlow(scene, el, aid);
    el.addEventListener('click', (ev) => {
      if (isDrag(ev)) return;
      ev.stopPropagation();
      pickSelBox(scene, desc(), el, ev);   // shift=frame, ⌘=toggle, plain=replace — as any box
    });
  });

  // Arrows: index them by pair, so both consumers below read one source — the arrow's own selection
  // (which lists every step riding it) and the step player (which needs the DOM of the arrow carrying
  // step i).
  const arrows = {};                       // 'src>dst' -> {path, label}
  bindEdges(scene, (m) => {
    const key = m[1] + '>' + m[2];
    const on = flowMapSteps(uc, m[1], m[2]);
    if (!on.length) return null;
    return { e: { src: m[1], dst: m[2] },
             selKey: 'flowpair:' + uc + ':' + key,
             opts: { action: relationshipLocateAction(m[1], m[2]) },
             // A one-step arrow is that step, exactly like a sequence message. A bundle is not one
             // particular step: show every step and leave the inactive player's saved index untouched.
             showFn: () => {
               if (on.length === 1) { flowSyncCur(on[0].i); showFlowStep(uc, on[0].i); }
               else showFlowPair(uc, m[1], m[2]);
             } };
  });
  eachEdge(scene.root, (p, label, m) => {
    const key = m[1] + '>' + m[2];
    if (!arrows[key]) arrows[key] = {
      path: p,
      label,
      stepIdx: flowMapSteps(uc, m[1], m[2]).map((x) => x.i),
    };
  });

  // One selector per STEP, keyed exactly as the sequence view keys its own (`flowstep:<uc>:<i>`), so the
  // step player, the history restore and the pair panel's step links all drive the map through the same
  // door they drive the sequence through. Selecting step i glows the arrow that carries it and dims to
  // its two boxes — the map's equivalent of lighting one message and its two lifelines.
  const msgEls = [];
  steps.forEach((st, i) => {
    const a = flowMapBoxId(uc, st.srcId, st.src), b = flowMapBoxId(uc, st.dstId, st.dst);
    const arrow = arrows[a + '>' + b];
    msgEls[i] = arrow ? [arrow.path, arrow.label].filter(Boolean) : [];
    if (!arrow) return;                    // a step whose pair was not drawn: no glow, but it still counts
    const desc = { key: 'flowstep:' + uc + ':' + i,
                   glow: (reveal) => glowEdge(arrow.path, arrow.label, reveal),
                   focus: { nodes: new Set([a, b]), edge: (e) => e.src === a && e.dst === b },
                   show: () => { flowSyncCur(i); showFlowStep(uc, i); } };
    scene.selectors[desc.key] = () => selAdd(scene, desc);
  });

  // Hand the player the same shape the sequence view hands it: the ordered steps, each step's arrow DOM,
  // and the endpoint boxes to keep in view. `kind` tells flowReveal which geometry it is looking at —
  // lifeline columns (x only) there, whole boxes here.
  const partsById = {};
  for (const id in scene.nodeEls) partsById[id] = [scene.nodeEls[id]];
  flowPlay = steps.length
    ? { uc, kind: 'map', steps, msgEls, partsById, mapArrows: arrows, cur: -1, active: false }
    : null;
}

// Draw (or hide) the environment filter. It sits OVER THE DIAGRAM, not in the info pane: it changes
// what the diagram draws, so it belongs beside it — and in the pane it disappeared as soon as anything
// was selected, leaving a filtered diagram with no visible way back to `All`. Shown only on the
// Deployment overview: the per-process cards are environment-independent, so it would do nothing there.
function syncEnvPicker(s) {
  const on = !!(DEPLOY_ENVS && DEPLOY_ENVS.length) && s && s.kind === 'deployment';
  envpicker.hidden = !on;
  if (!on) { envpicker.innerHTML = ''; return; }
  const opts = ['All'].concat(DEPLOY_ENVS);
  envpicker.innerHTML = `<div class="env-picker"><span class="env-picker-label">Environment</span>`
    + opts.map((o) => {
      const val = o === 'All' ? '' : o;
      const active = (DEPLOY_ENV || '') === val;
      return `<button class="env-opt${active ? ' active' : ''}" data-env="${esc(val)}">${esc(o)}</button>`;
    }).join('') + `</div>`;
  envpicker.querySelectorAll('.env-opt').forEach((btn) => btn.addEventListener('click', () => {
    DEPLOY_ENV = btn.dataset.env || null;
    syncEnvPicker(history[hi]);   // repaint the picker's own active state
    applyEnvDim(mainScene);       // ...and re-dim in place: no re-render, no layout jump
  }));
}
// A process card's default panel: the process node's own detail + the threads/loops it hosts.
// A product-area container's panel: what it is, and every process inside it. Each member row opens
// that process's own card, so the container is a way IN rather than a wall.
function showDeploymentGroup(gid) {
  const members = (DEPLOYMENT_GROUP_MEMBERS && DEPLOYMENT_GROUP_MEMBERS[gid]) || [];
  const rows = members.map((u) =>
    `<tr><td><a href="#" class="procref" data-unit="${esc(u)}">${esc(u)}</a></td></tr>`).join('');
  panel.innerHTML = `<section class="uc-group"><h3 class="uc-actor">${esc(groupTitle(gid))}</h3>`
    + `<div class="gloss-plain">Processes running the same product area, grouped so the overview stays `
    + `readable. The arrows on the overview are the sum of these processes' own arrows; open a `
    + `process for its real ones.</div>`
    + `<table class="glossary"><tbody>${rows}</tbody></table></section>`;
  bindNodeDetailHandlers(panel);
}
function showDeploymentUnit(unit) {
  const uid = unitProcessNodeId(unit);
  const eps = (GRAPH.entry_points || []).filter((e) => e.activation === 'self' && threadHostUnits(e).includes(unit));
  let html = uid ? nodeDetailHtml(uid) : `<section class="uc-group"><h3 class="uc-actor">${esc(unit)}</h3></section>`;
  // A clear gap between the process's own detail (dl + impact) and the threads it hosts — the node
  // detail ends with no bottom margin, so without this the box reads as glued to the fields above it.
  if (eps.length) html += `<section class="uc-group" style="margin-top:20px"><h3 class="uc-actor">Threads / loops (${eps.length})</h3>${threadRowsHtml(eps)}</section>`;
  panel.innerHTML = html;
  bindNodeDetailHandlers(panel);
  if (uid) syncTreeToNode(uid);
}
// The Domain Subdomains overview: a subdomain box ⌘-drills to its per-subdomain card; an
// inter-subdomain arrow selects to the crossing entity→entity relations (no further drill).
function bindDomainContainer() { bindGroupContainer((id) => ({ kind: 'domsub', sd: id }), bindDomainContainerEdge); }
// An inter-subdomain arrow (Domain overview + subdomain-card cross arrows): a plain click SELECTS it
// (the sidebar lists every entity→entity relation it bundles) and a ⌘-click drills into the
// two-subdomain edge view. The domain analog of bindContainerEdge.
function bindDomainContainerEdge(scene, p, label, a, b, focusE) {
  markSyntheticEdge(p);
  const drawn = focusE || { src: a, dst: b };
  const isEnt = (id) => GRAPH.nodes[id] && GRAPH.nodes[id].kind === 'entity';
  // Mirror bindContainerEdge: ⌘-drill a single focal-entity relation arrow lands on the pair's edge
  // card with THAT entity selected (its relations lit, the rest of the pair dimmed); a box↔box arrow
  // (the Domain overview) opens the pair unfocused, as before.
  const focusEnt = isEnt(drawn.src) ? drawn.src : (isEnt(drawn.dst) ? drawn.dst : null);
  // Drill lands on the relations LIST — narrowed to the focal entity's relations for a member arrow,
  // the whole pair for a box↔box arrow (see bindContainerEdge for the same shape). `sels` pre-selects the
  // real relation arrows this synthetic arrow stood for, in the domain edge card.
  const dom = focusEnt ? { kind: 'domedge', a, b, efocus: { src: drawn.src, dst: drawn.dst } } : { kind: 'domedge', a, b };
  dom.selCover = bundleAtoms(domainContainerEdgeList(a, b, drawn));
  bindSelectEdge(scene, p, label, drawn, 'dctxedge:' + drawn.src + '>' + drawn.dst,
    () => showDomainContainerEdge(a, b, drawn),
    { onDrill: () => go(dom), actionFn: () => actionTipEdge(a, b, drawn) });
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
  bindEntityBoxLinks();  // every box is in nodeEls now — link its entity-typed fields + its store line
  eachClassEdge(mainScene.root, (p, label, x, y, i) => {
    const kx = GRAPH.nodes[x] && GRAPH.nodes[x].kind;
    const ky = GRAPH.nodes[y] && GRAPH.nodes[y].kind;
    if (kx === 'entity' && ky === 'entity') {  // an internal relation — select to its detail
      const arr = COMP_LOOKUP[x + '>' + y];
      if (!arr) return;
      const e = arr[0];
      // parallel relations of one pair share the drawn arrow — the panel lists them ALL (showPairEdges)
      bindSelectEdge(mainScene, p, label, e, 'edge:' + e.src + '>' + e.dst + ':' + i, () => showPairEdges(arr));
    } else if (kx === 'subsystem' || ky === 'subsystem') {  // a bridge arrow: subsystem -> entity (owns/reads)
      const sub = kx === 'subsystem' ? x : y;
      bindBridgeEdge(mainScene, p, label, x, y, { kind: 'bridge', sid: sub, sd: sd });  // ⌘ -> the S×SD bridge card
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
  markSyntheticEdge(p);  // an overlapping-pair nav arrow is also an aggregate (count-labelled) bundle
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
      bindBridgeEdge(mainScene, p, label, a, b, { kind: 'bridge', sid: sid, sd: sd });  // ⌘ -> the S×SD bridge card
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
    if (m) fn(p, aligned ? labels[i] || null : null, m[1], m[2], i);
  });
}
// Mermaid's classDiagram markers default to markerUnits="strokeWidth", so the selection highlight's
// 3px stroke would scale them 3x. Pinning them to a fixed user-space size keeps them steady on select;
// the scale below then sets how big a relation's arrowhead / diamond reads.
const MARKER_SCALE = 0.85;
function fixDomainMarkers(root) {
  // The one knob for relation-marker size. Mermaid's own shape is ~18 user units; `MARKER_SCALE` is
  // applied to it (and to refX/refY, so the tip still meets the line where it should). The marker
  // VIEWPORT must grow with it or the bigger shape is clipped — hence the 20× coupling, which
  // reproduces the box this used at its original scale. Raise the scale to make heads/diamonds bigger.
  const s = MARKER_SCALE;
  const box = String(Math.round(20 * s));
  root.querySelectorAll('marker').forEach((m) => {
    if (m.dataset.fixed) return;
    m.setAttribute('refX', ((parseFloat(m.getAttribute('refX')) || 0) * s).toFixed(2));
    m.setAttribute('refY', ((parseFloat(m.getAttribute('refY')) || 0) * s).toFixed(2));
    m.setAttribute('markerUnits', 'userSpaceOnUse');
    m.setAttribute('markerWidth', box);
    m.setAttribute('markerHeight', box);
    [...m.children].forEach((c) => {
      c.setAttribute('transform', `scale(${s}) ${c.getAttribute('transform') || ''}`.trim());
    });
    m.dataset.fixed = '1';
  });
}
// ── clickable links inside a class box ───────────────────────────────────────────────────────────
// An entity box says two things that name somewhere else in the map, and both were drawn as inert
// text — the reader had to hunt the target down by eye:
//   * a field whose TYPE is another entity (`Role[] roles`) -> SELECT that entity;
//   * the store line (`🛢 guilds(MongoDB)`) -> the Data tab, focused on that store's pane and this
//     entity's row (exactly the jump the info pane's "See in Data view" link makes).
// WHICH lines are linkable, and the exact text each link covers, comes from the generator
// (ENTITY_FIELD_LINKS / ENTITY_STORE_LINKS, keyed by the line's index in its compartment) — the
// generator is the one place that decides what a box line says, so a link can't drift from the drawn
// text. Each entry is still re-checked against the text actually rendered before it is linked: a
// mismatch means the two went out of step, and drawing no link beats a wrong one.

// Turn the leading `text` of one drawn box line into a link running `run`. Returns false when the line
// doesn't start with that text (the generator and the render are out of step) — the caller then leaves
// it alone. `row` is a Mermaid class-box label group; its first text node carries the whole line.
function linkifyBoxRow(row, text, title, run) {
  const host = row && row.querySelector('.nodeLabel');
  if (!host) return false;
  const node = document.createTreeWalker(host, NodeFilter.SHOW_TEXT).nextNode();
  if (!node || node.data.slice(0, text.length) !== text) return false;
  node.splitText(text.length);                      // `node` now holds exactly `text`, the rest follows
  const link = document.createElement('span');
  link.className = 'boxlink';
  link.textContent = node.data;
  link.title = title;
  link.addEventListener('click', (ev) => {
    if (isDrag(ev)) return;
    ev.stopPropagation();                           // the box's own click must not also select the box
    run();
  });
  node.parentNode.replaceChild(link, node);
  return true;
}
function bindEntityBoxLinks() {
  for (const id in mainScene.nodeEls) {
    const el = mainScene.nodeEls[id];
    // A field's type is the member line's PREFIX, so only that word becomes the link — it is the type
    // that names another element, not the property. A collapsed neighbour box draws no members at all.
    const members = el.querySelectorAll('g.members-group > g.label');
    for (const link of (ENTITY_FIELD_LINKS[id] || [])) {
      const target = GRAPH.nodes[link.target];
      if (target && members[link.i])
        linkifyBoxRow(members[link.i], link.type, 'Select entity: ' + target.name,
          () => selectFromTree(link.target));
    }
    // The store line is a WHOLE line in the box's second compartment, and all of it means "this lives
    // there" — so the link covers the line, not a word of it. Gated on the Data tab existing, the same
    // condition the info pane's "See in Data view" link is gated on (persistedInHtml).
    const store = ENTITY_STORE_LINKS[id];
    const extras = el.querySelectorAll('g.methods-group > g.label');
    if (HAS_DATA && store && extras[store.i])
      linkifyBoxRow(extras[store.i], store.text, 'See in Data view',
        () => go({ kind: 'data', store: store.dep, entity: id }));
  }
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
  bindEntityBoxLinks();  // every box is in nodeEls now — link its entity-typed fields + its store line
  eachClassEdge(mainScene.root, (p, label, src, dst, i) => {
    const ks = GRAPH.nodes[src] && GRAPH.nodes[src].kind, kd = GRAPH.nodes[dst] && GRAPH.nodes[dst].kind;
    if (ks === 'subsystem' || kd === 'subsystem') {  // a bridge arrow subsystem -> entity (owns/reads)
      const sub = ks === 'subsystem' ? src : dst, ent = ks === 'subsystem' ? dst : src;
      bindBridgeEdge(mainScene, p, label, src, dst, { kind: 'bridge', sid: sub, sd: topSubdomainOf(ent) });  // ⌘ -> bridge card
      return;
    }
    const arr = COMP_LOOKUP[src + '>' + dst];
    if (!arr) return;
    const e = arr[0];
    // parallel relations of one pair share the drawn arrow — the panel lists them ALL (showPairEdges)
    bindSelectEdge(mainScene, p, label, e, 'edge:' + e.src + '>' + e.dst + ':' + i, () => showPairEdges(arr));
  });
}

// --- Happy Path (Level 1) selection ---------------------------------------------
// A sequenceDiagram, a different SVG shape again: a step is a message (text + line), an actor is a
// stick figure over a lifeline. Both SELECT (panel + glow + focus-dim); a step also ⌘-clicks to drill.
// Glow one HP element (figure, text, lifeline or arrow) with the soft HP_SEL drop-shadow — a touch
// above the hover glow, never the heavy stroke-recolour the click used to apply. Returns a cleanup.
function hpGlow(el, revealAction = true) {
  el.style.filter = HP_SEL;
  if (el._actionIcon) {
    el._actionIcon._selected = !!revealAction;
    if (revealAction) showIcon(el._actionIcon); else hideIcon(el._actionIcon);
  }
  return () => {
    el.style.filter = '';
    if (el._actionIcon) { el._actionIcon._selected = false; hideIcon(el._actionIcon); }
  };
}
// Glow a set of elements and remember them in scene.hpLit (a step driven by a selected actor is
// glowed but isn't itself the selection, so its own hover handlers must restore THIS glow on leave —
// not blank it). ADDITIVE, so several selected sequence elements can be lit at once (multi-select): each
// call adds its els to the running lit set and its cleanup removes exactly those. selApply rebuilds the
// whole set from scratch on every change, so a shared el (lit by two selections) can't be stranded.
function hpHighlight(scene, els, revealAction = true) {
  const undo = els.map((el) => hpGlow(el, revealAction));
  for (const el of els) scene.hpLit.add(el);
  return () => { undo.forEach((f) => f()); for (const el of els) scene.hpLit.delete(el); };
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
// One step's drawn parts: its label, its arrow, and any junction dots marking the alternative actors
// that arrow passes. The dots belong to the step everywhere the step is treated as a unit (hover, glow,
// dim), so they are collected here once rather than at each of the four call sites.
function hpMsgEls(m) { return [m.text, m.line, ...(m.dots || [])].filter(Boolean); }
function hpActorDesc(scene, a) {
  const stepEls = [];
  for (const i of a.stepIdx) { const m = scene.hpMsg[i]; if (m) stepEls.push(...hpMsgEls(m)); }
  const lit = [...scene.hpActor[a.aid].els, ...stepEls];
  return { key: 'hpactor:' + a.aid, glow: () => hpHighlight(scene, lit, false),
           focus: { els: new Set(lit) }, show: () => showHPActor(a) };
}
function selectHPActor(scene, a) { selReplace(scene, hpActorDesc(scene, a)); }
// Select a step: the step (label + arrow + its junction dots) glows and EVERY actor that can drive it
// stays lit — for a use case with interchangeable actors that is more than one; dimming the others
// would hide drivers of the very step being read. The rest dims.
function hpStepDesc(scene, i, hpId, aids) {
  const m = scene.hpMsg[i] || {};
  const glow = hpMsgEls(m);
  const keep = new Set(glow);
  for (const aid of (aids || [])) for (const el of ((scene.hpActor[aid] || {}).els || [])) keep.add(el);
  return { key: 'hpstep:' + hpId, glow: (reveal) => hpHighlight(scene, glow, reveal),
           focus: { els: keep }, show: () => showHPArrow(hpId) };
}
function selectHPStep(scene, i, hpId, aids) { selReplace(scene, hpStepDesc(scene, i, hpId, aids)); }
// Select a whole use case on the Happy Path (reached from a Use-cases `HPn` pill): EVERY step that
// realizes it glows and its driving actor stays lit; the rest dims. A use case can occupy several
// positions, so more than one step may light — that is exactly the "appears twice" signal. The panel
// shows the use case (not a single step), and the selection is keyed by uc so back/forward restores it.
function hpUseCaseDesc(scene, uc) {
  const glow = [], keep = [];
  (GRAPH.happy_path || []).forEach((step, i) => {
    if (step.uc !== uc) return;
    const m = scene.hpMsg[i]; if (!m) return;
    glow.push(...hpMsgEls(m));
    for (const a of (HP_ACTORS_OF_STEP[step.id] || [])) {
      const rec = scene.hpActor[a.aid];
      if (rec) keep.push(...rec.els);
    }
  });
  return { key: 'hpuc:' + uc, glow: () => hpHighlight(scene, glow, false),
           focus: { els: new Set([...glow, ...keep]) }, show: () => showUseCaseSummary(uc) };
}
function selectHPUseCase(scene, uc) { selReplace(scene, hpUseCaseDesc(scene, uc)); }

// Bind the Happy Path: steps + actors both select; a step ⌘-clicks to its Level-2 components view.
// The step id is no longer in the label, so message[i] pairs with GRAPH.happy_path[i] by order; an actor's
// figure/lifeline are found by participant id (data-id="GPAn") and its driven steps come from HP_ACTORS.
// A step whose use case names SEVERAL interchangeable actors still gets one arrow (a sequence diagram
// has no "or" — a second arrow would read as a second thing that happened). The arrow leaves the
// leftmost of them, and each of the others is marked with a junction dot where the arrow crosses its
// lifeline: "any of these can drive this step", said on the arrow itself, with no invented step.
//
// The dot is a plain circle in the diagram's own coordinates, so it zooms with the arrow it sits on
// (unlike the action icons, which are counter-scaled to stay a fixed screen size). The crossing is
// guaranteed by the generator's leftmost rule, but it is re-checked here anyway: a dot that missed its
// arrow would read as a mark on some other step entirely, so it is dropped rather than drawn adrift.
const HP_JUNCTION_R = 4.5;
function hpJunctionDots(root, line, aids) {
  const out = [];
  if (!line || !aids || !aids.length) return out;
  let lb; try { lb = line.getBBox(); } catch (_) { return out; }
  const stroke = getComputedStyle(line).stroke;  // the arrow's own colour — the dot is part of it
  for (const aid of aids) {
    const life = root.querySelector('line.actor-line[data-id="' + aid + '"]');
    if (!life) continue;
    const x = parseFloat(life.getAttribute('x1'));
    if (!isFinite(x) || x < lb.x || x > lb.x + lb.width) continue;
    const dot = document.createElementNS(SVGNS, 'circle');
    dot.setAttribute('cx', x); dot.setAttribute('cy', lb.y + lb.height / 2);
    dot.setAttribute('r', HP_JUNCTION_R);
    dot.setAttribute('fill', stroke || '#333');
    dot.setAttribute('stroke', 'none');
    dot.setAttribute('pointer-events', 'none');  // the arrow beneath keeps the whole hit area
    line.parentNode.appendChild(dot);
    out.push(dot);
  }
  return out;
}
function bindHP() {
  const scene = mainScene, root = scene.root;
  // message text[i] <-> GRAPH.happy_path[i]; its arrow is the i-th .messageLine in document order. Pair
  // POSITIONALLY, not by Mermaid's `data-id="i<n>"` — see bindFlow: <n> is a global element counter that
  // sub-flow rects/notes advance, so an id-keyed lookup mis-pairs once a sub-box exists. The HP overlay
  // has none today, but keeping both paths positional makes it robust to that and matches bindFlow.
  const texts = [...root.querySelectorAll('text.messageText')];
  const lines = [...root.querySelectorAll('.messageLine0, .messageLine1')];
  leftAlignMessageLabels(texts, lines);
  scene.focusUnion = focusUnionEls;  // this is a sequence diagram — union selections dim by DOM-part set
  scene.hpMsg = {};  // step index -> { text, line, dots }
  for (let i = 0; i < (GRAPH.happy_path || []).length; i++) {
    const text = texts[i] || null;
    const line = lines[i] || null;
    const dots = hpJunctionDots(root, line, HP_STEP_MARKS[i]);
    scene.hpMsg[i] = { text, line, dots };
    for (const el of hpMsgEls(scene.hpMsg[i])) scene.dimEls.push(el);
  }
  // resolve each actor's DOM (figure top + bottom mirror + lifeline) by participant id, register for dimming.
  scene.hpActor = {};  // aid -> { els:[…] }
  styleSeqSystem(root);  // the System lifeline, in the same dark box the other views draw it as
  const bottoms = [...root.querySelectorAll('g.actor-man.actor-bottom')];
  for (const a of HP_ACTORS) {
    const figT = root.querySelector('.actor-top[data-id="' + a.aid + '"]');
    const life = root.querySelector('line.actor-line[data-id="' + a.aid + '"]');
    const figB = bottoms.find((g) => (g.textContent || '').trim() === a.name) || null;  // no data-id on the mirror
    const els = [figT, figB, life].filter(Boolean);
    scene.hpActor[a.aid] = { els };
    for (const el of els) scene.dimEls.push(el);
    styleSeqActor(root, a.aid, a.kind);  // person vs service actor, in the Dependencies view's vocabulary
  }
  // step index -> EVERY actor that can drive it (a use case may name interchangeable initiators), so a
  // selected step keeps all of them lit rather than just whichever one the arrow starts from.
  const aidsOfStep = {};
  for (const a of HP_ACTORS) for (const i of a.stepIdx) (aidsOfStep[i] || (aidsOfStep[i] = [])).push(a.aid);
  // Per-use-case selector: arriving from a Use-cases `HPn` pill (state `sel: 'hpuc:<uc>'`) lights every
  // step of that use case. Registered for each use case that occupies ≥1 position; back/forward too.
  for (const uc of Object.keys(HP_STEPS_BY_UC)) scene.selectors['hpuc:' + uc] = () => selAdd(scene, hpUseCaseDesc(scene, uc));

  // steps: plain click selects (panel), ⌘-click adds to the multi-selection, ⌥-click drills to Level 2.
  (GRAPH.happy_path || []).forEach((step, i) => {
    const { text, line } = scene.hpMsg[i];
    if (!text) return;
    // The junction dots are part of the arrow, so they take the hover/rest treatment with it.
    const dots = scene.hpMsg[i].dots || [];
    const hpId = step.id, selKey = 'hpstep:' + hpId;
    scene.selectors[selKey] = () => selAdd(scene, hpStepDesc(scene, i, hpId, aidsOfStep[i]));  // back/forward restore
    // Drilling a step opens its use case's flow — the SAME view (and breadcrumb: "Use Cases › …") a
    // click from the Use Cases tab lands on, so a use case's flow has ONE home regardless of entry.
    addLabelActionIcon(text, selKey, { kind: 'drill', run: () => go({ kind: 'usecase', uc: step.uc }) });
    const icon = ACTION_ICONS[selKey];
    // A dimmed step (hpFocus set its opacity to DIM because focus is on some other step/actor) isn't a
    // candidate for a next action — the pill stays hidden even while hovered, matching a dimmed box.
    const on = () => { if (!selHas(scene, selKey)) { text.style.filter = HOVER; if (line) line.style.filter = HOVER; for (const d of dots) d.style.filter = HOVER; if (text.style.opacity !== DIM) showIcon(icon); } };
    // restore to the resting glow (an actor-selected step keeps its HILITE), not blank — and for the
    // same reason, a directly selected step's pill stays visible. An automatically selected or merely
    // indirectly lit step returns to hover-only when the pointer leaves.
    const off = () => { if (!selHas(scene, selKey)) { text.style.filter = hpRestFilter(scene, text); if (line) line.style.filter = hpRestFilter(scene, line); for (const d of dots) d.style.filter = hpRestFilter(scene, d); if (!icon._selected) hideIcon(icon); } };
    const click = (ev) => {
      if (isDrag(ev)) return;
      ev.stopPropagation();
      off();
      if (isDrillClick(ev)) { go({ kind: 'usecase', uc: step.uc }); return; }  // ⌥-click drills into the use case's flow
      if (ev.shiftKey) { frameArrow(line || text); return; }  // shift-click is a pure camera move — frame, never select
      pickSel(scene, hpStepDesc(scene, i, hpId, aidsOfStep[i]), ev);
    };
    for (const el of [text, line]) {
      if (!el) continue;
      el.style.cursor = 'pointer';
      el.style.setProperty('pointer-events', el === text ? 'all' : 'stroke', 'important');
      el.classList.add('drill');  // ⌥-held cursor affordance
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
    scene.selectors[selKey] = () => selAdd(scene, hpActorDesc(scene, a));  // back/forward restore
    const on = () => { if (!selHas(scene, selKey)) for (const el of rec.els) el.style.filter = HOVER; };
    const off = () => { if (!selHas(scene, selKey)) for (const el of rec.els) el.style.filter = hpRestFilter(scene, el); };
    const click = (ev) => { if (isDrag(ev)) return; ev.stopPropagation(); off();
      if (ev.shiftKey) { frameArrow(rec.els.find((x) => x.tagName !== 'line') || rec.els[0]); return; }  // shift-click frames the actor, never selects
      pickSel(scene, hpActorDesc(scene, a), ev); };
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
  if (s.kind === 'deployment') return MERMAID_DEPLOYMENT;  // one diagram; the env dims, never filters
  if (s.kind === 'deploymentGroup') return DEPLOYMENT_GROUP_CARDS[s.gid];
  if (s.kind === 'deploymentUnit') return DEPLOYMENT_CARDS[s.unit];
  if (s.kind === 'hp') return MERMAID_HP;
  if (s.kind === 'usecase') return flowMermaidFor(s.uc);  // Sequence or Map — the flow picker's choice
  if (s.kind === 'libs') return MERMAID_LIBS;
  if (s.kind === 'bucketfold') return MERMAID_BY_BUCKETFOLD[s.bkid];
  // component: the baked report ships a diff-styled diagram (MERMAID_DIFF); a live diff has none, so it
  // renders the base diagram and lets applyDiffOverlay badge it.
  return (mode === 'diff' && MERMAID_DIFF && !LIVE_DIFF) ? MERMAID_DIFF : MERMAID_BASE;  // component
}
// A tab's OWN overview (not a drilled card) — `container` yes, `subsystem` no. Those are the states
// whose pane leads with the view intro.
function topLevelView(s) {
  const tv = topView(s.kind);
  return s.kind === tv ? tv : null;
}
// The pane for a table view (Glossary / Use Cases / System / Data / Tests): it renders no diagram and
// builds no scene, so it never reaches applyDefaultPanel — it sets its own pane to the view intro.
function showViewIntro(s) {
  const top = topLevelView(s);
  panel.innerHTML = top ? viewIntroHtml(top) : EMPTY_PANEL;
}
function applyDefaultPanel(s) {
  applyDefaultPanelBody(s);
  // Prepended AFTER the body so it leads the pane whatever the body wrote (including the deployment
  // env picker, which inserts itself at the top too).
  const top = topLevelView(s);
  if (top) panel.insertAdjacentHTML('afterbegin', viewIntroHtml(top));
}
function applyDefaultPanelBody(s) {
  setTreeSelection(null);  // a default panel / canvas deselect drops pill emphasis + selection pills
  if (s.kind === 'subsystem') showNode(s.sid);
  else if (s.kind === 'domsub') showNode(s.sd);
  else if (s.kind === 'edge') showContainerEdge(s.a, s.b, s.efocus || { src: s.a, dst: s.b });
  else if (s.kind === 'domedge') showDomainContainerEdge(s.a, s.b, s.efocus || { src: s.a, dst: s.b });
  else if (s.kind === 'bridge') showBridge(s.sid, s.sd);
  else if (s.kind === 'usecase') showUseCase(s.uc);
  else if (s.kind === 'deployment') { showDeployment(); return; }        // overview: surfaces unplaced threads
  else if (s.kind === 'deploymentUnit') { showDeploymentUnit(s.unit); return; }  // card: process detail + its threads
  else if (s.kind === 'libs') showLibsFold();
  else if (s.kind === 'bucketfold') showBucketFold(s.bkid);
  // The Happy Path overview (nothing selected) opens on the project goal — the SYS node carries the
  // title + T0 goal (fields.Overview). Selecting a step/actor then replaces it with that detail.
  else if (s.kind === 'hp' && GRAPH.nodes['SYS']) showNode('SYS');
  // The Subsystems overview in diff mode leads with the change-impact summary (which subsystems/elements
  // changed), since that is the whole point of opening a diff render.
  else if (s.kind === 'container' && mode === 'diff' && hasDiff()) (IMPACT ? showImpactSummary() : showDiffSummary());
  // An overview with no more specific default is the view intro alone (added by applyDefaultPanel).
  // It used to open on the System's card, which repeated the same project description under every tab;
  // the Happy Path branch above keeps it where it belongs — on the view that tells the whole story.
  else if (topLevelView(s)) panel.innerHTML = '';
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
  else if (s.kind === 'usecase') (FLOW_VIEW === 'map' ? bindFlowMap : bindFlow)(s.uc);
  else if (s.kind === 'deployment') bindDeployment();
  else if (s.kind === 'deploymentUnit') bindDeployment(s.unit);  // same binder; the focal process (s.unit) drills nowhere further
  else if (s.kind === 'libs') bindLibs();
  else if (s.kind === 'bucketfold') bindBucketFold();
  else bindComponent();
}
function topView(kind) {  // which top-level button a state lives under (container/subsystem/edge → Subsystems)
  if (kind === 'context' || kind === 'component' || kind === 'domain' || kind === 'glossary' || kind === 'system' || kind === 'data' || kind === 'tests' || kind === 'rules') return kind;
  if (kind === 'domsub' || kind === 'domedge') return 'domain';  // subdomain card + edge pair live under the Domain button
  if (kind === 'bridge') return 'container';  // a structure↔domain bridge card is anchored on its subsystem
  if (kind === 'usecases' || kind === 'usecase') return 'usecases';  // a use case's flow lives under the Use Cases catalog (incl. a Happy Path drill)
  if (kind === 'deployment' || kind === 'deploymentUnit' || kind === 'deploymentGroup') return 'deployment';  // a process/container card lives under the Deployment tab
  if (kind === 'hp') return 'hp';
  if (kind === 'libs' || kind === 'bucketfold') return 'context';  // the Context folds drill out of Context
  return 'container';
}
function stateTitle(s) {
  if (s.kind === 'context') return 'Dependencies';
  if (s.kind === 'container') return 'Subsystems';
  if (s.kind === 'component') return 'Components';
  if (s.kind === 'domain') return 'Entities';  // user-facing label for the `domain` view (the tab)
  if (s.kind === 'rules') return 'Business logic';
  if (s.kind === 'glossary') return 'Glossary';
  if (s.kind === 'system') return 'System';
  if (s.kind === 'data') return 'Data';
  if (s.kind === 'tests') return 'Tests';
  if (s.kind === 'usecases') return 'Use Cases';
  if (s.kind === 'deployment') return 'Deployment';
  if (s.kind === 'deploymentGroup') return groupTitle(s.gid);
  if (s.kind === 'deploymentUnit') return s.unit;
  if (s.kind === 'domsub') return (GRAPH.nodes[s.sd] ? GRAPH.nodes[s.sd].name : s.sd);
  if (s.kind === 'domedge') { const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id); return nm(s.a) + ' → ' + nm(s.b); }
  if (s.kind === 'bridge') { const nm = (id) => (GRAPH.nodes[id] ? GRAPH.nodes[id].name : id); return nm(s.sid) + ' → ' + nm(s.sd); }
  if (s.kind === 'hp') return 'Happy Path';
  if (s.kind === 'usecase') return (GRAPH.nodes[s.uc] ? GRAPH.nodes[s.uc].name : s.uc);
  if (s.kind === 'libs') return 'Libraries';
  if (s.kind === 'bucketfold') return bucketFoldName(s.bkid);
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
  if (s.kind === 'usecases') return [{ kind: 'usecases' }];
  if (s.kind === 'usecase') return [{ kind: 'usecases' }, { kind: 'usecase', uc: s.uc }];  // a use case's flow, under the Use Cases catalog
  if (s.kind === 'deployment') return [{ kind: 'deployment' }];
  if (s.kind === 'deploymentGroup') return [{ kind: 'deployment' }, { kind: 'deploymentGroup', gid: s.gid }];
  if (s.kind === 'deploymentUnit') {
    // A member's card sits under its container, so the trail reads overview -> product area -> process.
    const gid = groupOfUnit(s.unit);
    const trail = [{ kind: 'deployment' }];
    if (gid) trail.push({ kind: 'deploymentGroup', gid });
    trail.push({ kind: 'deploymentUnit', unit: s.unit });
    return trail;
  }
  if (s.kind === 'libs') return [{ kind: 'context' }, { kind: 'libs' }];  // the fold is a drill-down out of Context
  if (s.kind === 'bucketfold') return bucketFoldParent(s.bkid) === 'libs'   // library bucket: Context › Libraries › <bucket>
    ? [{ kind: 'context' }, { kind: 'libs' }, { kind: 'bucketfold', bkid: s.bkid }]
    : [{ kind: 'context' }, { kind: 'bucketfold', bkid: s.bkid }];          // external bucket: Context › <bucket>
  if (s.kind === 'context') return [{ kind: 'context' }];
  if (s.kind === 'component') return [{ kind: 'component' }];
  if (s.kind === 'rules') return [{ kind: 'rules' }];
  if (s.kind === 'glossary') return [{ kind: 'glossary' }];
  if (s.kind === 'system') return [{ kind: 'system' }];
  if (s.kind === 'data') return [{ kind: 'data' }];
  if (s.kind === 'tests') return [{ kind: 'tests' }];
  const trail = [{ kind: 'container' }];                  // the Subsystems overview is the root of this branch
  if (s.kind === 'subsystem') trail.push(...groupChain('subsystem', 'sid', s.sid));  // full nesting path top → sid
  else if (s.kind === 'edge') trail.push({ kind: 'edge', a: s.a, b: s.b });  // a pair lives beside the subsystems
  return trail;
}
function renderChrome(s) {
  // The baseline⇄diff change-impact overlay lives on the Subsystems views now (overview + cards),
  // not the removed flat Components map: the overview badges each subsystem with its subtree's change,
  // and the cards badge their member components (via bindNodes).
  const diffHost = IMPACT ? true
    : (s.kind === 'container' || s.kind === 'subsystem' || s.kind === 'edge');
  const tv = topView(s.kind);
  syncLegend(s);
  syncEnvPicker(s);
  toggle.style.display = (hasDiff() && diffHost) ? '' : 'none';
  toggle.textContent = mode === 'diff' ? 'Show baseline' : 'Show diff';
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
  rescaleDiffBadges();
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
// whole window resizes, or the file browser is toggled on/off — a large, discrete size change where a
// fresh fit is the least surprising result.
function refitStage() { scheduleStage(() => { mainPz.resize(); mainPz.fit(); mainPz.center(); }); }
// PRESERVE: keep the user's current zoom level and keep the point that was at the viewport centre at the
// centre — the diagram doesn't jump. Used for EVERY drag-handle resize — the vertical info-pane split
// AND the two horizontal splits (left-column width, file-browser width) — where re-fitting would throw
// away the reader's zoom-in every time they nudge a divider.
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
// A `path:line`/`path/` code anchor as a table cell: a clickable code-viewer link for an in-repo
// ref, plain text for an off-repo ref, an em-dash when absent. Every button carries `srclink` +
// `data-where`, which the delegated container listener (see PANEL_HOST) reads on click.
// Shared by the Glossary, System and Tests reference tables (the one source-link contract).
function srcCell(where) {
  where = where || '';
  const { file, line } = where ? whereNode(where) : { file: '', line: null };
  if (where && localRef(where)) {
    const rel = cleanPath(file, line);
    const base = rel.replace(/\/+$/, '').split('/').pop() + (line ? ':' + line : '');
    return `<button type="button" class="src srclink" data-where="${esc(where)}"`
      + ` title="Open in the code viewer">${esc(base)}</button>`;
  }
  if (where) return `<span class="gloss-plain">${esc(cleanPath(file, line))}</span>`;
  return '<span class="gloss-none">—</span>';
}
function renderGlossary() {
  const rows = (GRAPH.glossary || []).map((g) =>
    `<tr data-term="${esc(g.term)}"><th scope="row">${esc(g.term)}</th><td>${mdInline(g.meaning || '')}</td><td>${srcCell(g.source || '')}</td></tr>`
  ).join('');
  diagram.innerHTML = '<div class="glossary-wrap" style="padding-top:20px">'
    + '<table class="glossary"><thead><tr><th>Term</th><th>Meaning</th><th>Defined in</th></tr></thead>'
    + `<tbody>${rows}</tbody></table></div>`;
}

// The Use Cases tab: the full catalog, GROUPED BY ACTOR — each actor section header IS the Role (the
// only place roles get a home now that the Context/Dependencies view is deps-focused). Each use case
// shows its trigger → outcome and, when it sits on the Happy Path, an `HPn` pill (all positions when it
// recurs) that jumps to that step. Off-spine use cases have NO pill — that absence is the on/off-spine
// signal in the catalog. A non-diagram HTML view rendered straight into #diagram, like the Glossary.
// The Use Cases catalog groups two ways, and BOTH are kept. "What can this role do?" and "what does
// this product do?" are different questions, and neither derives the other — replacing the actor
// grouping with the capability one would have been a silent downgrade for anyone reading the map to
// answer a permissions question. Only the heading key changes; rows, badges and behaviour do not.
let UC_GROUP_BY = 'capability';   // 'capability' | 'actor'; falls back to actor on a map with none

function ucGroupBy() {
  // A map that never adopted capabilities has nothing to group by — never show an empty switch.
  return HAS_CAPABILITIES ? UC_GROUP_BY : 'actor';
}

function actorTextOf(n) {
  return ((n.fields && n.fields.Actor) || (n.actors || []).join(', ') || 'Other').trim();
}

function roleKindOf(n) {
  const names = (n.actors && n.actors.length ? n.actors : []).map((s) => String(s).trim().toLowerCase());
  const kinds = new Set(names.map((nm) => ((ROLE_BY_NAME[nm] || {}).kind || '').trim().toLowerCase()));
  const k = kinds.size === 1 ? [...kinds][0] : '';
  return (k === 'human' || k === 'service') ? k : 'human';
}

function capabilityGroups() {
  // Capability order is the model's (importance), and membership rides `parent` — the same channel a
  // component uses for its subsystem — so no second lookup table travels beside the nodes.
  const groups = [];
  const byCap = {};
  for (const n of Object.values(GRAPH.nodes || {})) {
    if (n.kind !== 'capability') continue;
    byCap[n.id] = { cap: n, label: (n.fields && n.fields.Label) || '', ucs: [] };
    groups.push(byCap[n.id]);
  }
  const loose = { cap: null, label: '', ucs: [] };
  for (const n of UC_NODES) {
    const g = byCap[n.parent];
    (g || loose).ucs.push(n);
  }
  if (loose.ucs.length) groups.push(loose);
  return groups.filter((g) => g.ucs.length);
}

function renderUseCases() {
  // Group by ACTOR, keeping model (importance) order within a group and first-appearance order of the
  // actors. A use case may name several INTERCHANGEABLE actors (either can start it) — that pair is a
  // group of its own, headed by both names, not a use case filed under one of them and hidden from the
  // other. It used to land in the "Other" bucket: the group key was the joined display string, which
  // matched no single role, so the catalog quietly lost it. "Other" now means what it says — an actor
  // this map never declared as a role, or none at all.
  const groups = [];               // [{actor, roles:[role], ucs:[node]}]
  const byActor = {};
  const OTHER = '\x00other';
  for (const n of UC_NODES) {
    // `actors` is the structured list; the `Actor` field is the readable rendering of that same list
    // (and the only form a graph built before `actors` existed carries).
    const names = (n.actors && n.actors.length ? n.actors : [((n.fields && n.fields.Actor) || '')])
      .map((s) => String(s).trim()).filter(Boolean);
    const roles = names.map((nm) => ROLE_BY_NAME[nm.toLowerCase()]);
    const known = names.length && roles.every(Boolean);
    const key = known ? names.map((s) => s.toLowerCase()).join('\x00') : OTHER;
    if (!byActor[key]) {
      // The header text is the `Actor` FIELD, which is already the readable rendering of this same list
      // ("Team member and Organization admin"), so the conjunction is spelled in one place — the view
      // builder — instead of once per view.
      const title = ((n.fields && n.fields.Actor) || '').trim() || names.join(', ');
      byActor[key] = { actor: known ? title : 'Other', roles: known ? roles : [], ucs: [] };
      groups.push(byActor[key]);
    }
    byActor[key].ucs.push(n);
  }
  const kindBadge = (kind) => {
    const k = (kind || '').trim().toLowerCase();
    if (k !== 'human' && k !== 'service') return '';
    return `<span class="uc-kind uc-kind-${k}">${esc(k)}</span>`;
  };
  const pill = (uc) => {
    // On the Happy Path? -> a "Happy Path" pill that jumps there (and lights this use case's step(s)).
    // The label is the plain words, not the `HPn` position: the click already lands on the right step,
    // so the number added nothing. No pill at all = off-spine.
    if (!(HP_STEPS_BY_UC[uc] || []).length) return '';
    return `<button type="button" class="uc-hp-pill" data-uc="${esc(uc)}"`
      + ' title="On the Happy Path — click to jump there">Happy Path</button>';
  };
  const byCapability = ucGroupBy() === 'capability';
  const shown = byCapability ? capabilityGroups() : groups;
  const sections = shown.map((g) => {
    // One actor: its kind and what it wants, as before. SEVERAL interchangeable actors: the kind only
    // when they agree on it (they normally do — a human "or" a service is the method's tell that one of
    // them isn't really an actor), and no "wants", because each of them wants something of their own and
    // one header cannot speak for both. Clicking either name's own group still shows theirs.
    const kinds = new Set((g.roles || []).map((r) => (r.kind || '').trim().toLowerCase()));
    const kind = kinds.size === 1 ? [...kinds][0] : '';
    const w = (g.roles || []).length === 1 ? g.roles[0].wants : '';
    // Its OWN line under the heading, always — inline beside the name it sat on the same line for a
    // short want and wrapped onto the next for a long one, so the section headers never lined up. The
    // label carries the weight, since without it the sentence reads as a description of the actor.
    const wants = w ? `<p class="uc-wants"><span class="uc-wants-lbl">Wants:</span> ${mdInline(w)}</p>` : '';
    const rows = g.ucs.map((n) => {
      const to = (n.fields && n.fields['Trigger → Outcome']) || '';
      // In diff mode, flag a use case whose flow touches changed code (derived from the element diff).
      const changed = (mode === 'diff' && hasDiff() && usecaseDiffState(n.id)) ? '<span class="badge modified">changed</span>' : '';
      // The badge on the row is whichever axis is NOT the heading — actor when grouped by
      // capability, capability when grouped by actor — so the other dimension stays visible either way.
      const cross = byCapability
        ? `<span class="uc-kind uc-kind-${esc(roleKindOf(n))}">${esc(actorTextOf(n))}</span>`
        : (CAP_OF_UC[n.id] ? `<span class="uc-caplabel">${esc(CAP_OF_UC[n.id].name)}</span>` : '');
      const untraced = FLOWS_MM && FLOWS_MM[n.id] ? ''
        : '<span class="uc-untraced" title="Described, but no flow was traced — the map cannot say how it works">not traced</span>';
      return `<li class="uc-row${changed ? ' uc-changed' : ''}" data-uc="${esc(n.id)}" tabindex="0">`
        + `<span class="uc-head"><span class="uc-name">${esc(n.name)}</span>${cross}${changed}${pill(n.id)}${untraced}</span>`
        + (to ? `<span class="uc-to">${mdInline(to)}</span>` : '')
        + '</li>';
    }).join('');
    if (byCapability) {
      const title = g.cap ? g.cap.name : 'Not assigned to a capability';
      const lab = g.label ? `<span class="uc-caplabel uc-lab-${esc(g.label.toLowerCase())}">${esc(g.label)}</span>` : '';
      // A plain section, exactly like the actor grouping's: no twisty, nothing to fold. `platform`
      // capabilities used to start collapsed so the background use cases would not bury the product
      // ones — but a section that hides itself is a second thing to learn on a screen whose whole job
      // is to list what the product does, and the `platform` label already says which is which.
      return `<section class="uc-group" data-cap="${esc(g.cap ? g.cap.id : '')}">`
        + `<h3 class="uc-actor">${esc(title)}${lab}`
        + `<span class="uc-actor-wants">${g.ucs.length} use case${g.ucs.length > 1 ? 's' : ''}</span></h3>`
        + `<ul class="uc-list">${rows}</ul></section>`;
    }
    return '<section class="uc-group">'
      + `<h3 class="uc-actor">${esc(g.actor)}${kindBadge(kind)}</h3>${wants}`
      + `<ul class="uc-list">${rows}</ul></section>`;
  }).join('');
  const sw = HAS_CAPABILITIES ? '<div class="uc-groupby"><span class="uc-groupby-lbl">Group by</span>'
    + `<span class="uc-seg"><button type="button" data-gb="capability"${byCapability ? ' class="on"' : ''}>Capability</button>`
    + `<button type="button" data-gb="actor"${byCapability ? '' : ' class="on"'}>Actor</button></span>`
    + `<span class="uc-groupby-why">${byCapability ? 'What does this product do?' : 'What can each role do?'}</span></div>` : '';
  diagram.innerHTML = `<div class="usecases-wrap">${sw}${sections || '<p class="empty">No use cases recorded.</p>'}</div>`;
  diagram.querySelectorAll('.uc-seg button').forEach((b) => {
    b.addEventListener('click', () => { UC_GROUP_BY = b.getAttribute('data-gb'); renderUseCases(); });
  });
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

// One titled reference table's BODY on the System tab: a `.glossary`-styled table. `cols` = [{head, get}];
// get(row) returns a prose string (rendered via mdInline) or {src:'path:line'} for a code link. Returns ''
// for an empty collection so the section is omitted (mirrors the markdown view's `if m.x:` guards). The
// caller wraps it in a titled `<section>` (see the `sec` helper). Reuses `.glossary` inside `.system-wrap`.
function refTable(rows, cols) {
  if (!rows || !rows.length) return '';
  const head = cols.map((c) => `<th>${esc(c.head)}</th>`).join('');
  const body = rows.map((r) => '<tr>' + cols.map((c) => {
    const v = c.get(r);
    const cell = (v && typeof v === 'object' && 'src' in v) ? srcCell(v.src)
      : (v && typeof v === 'object' && 'html' in v) ? v.html   // pre-built HTML (e.g. a list of src links)
      : mdInline(v || '');
    return `<td>${cell}</td>`;
  }).join('') + '</tr>').join('');
  return `<table class="glossary"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}
// A deployment unit's variant tags, each with its grounding: `env · <anchor link>` when the tag cites a
// manifest source, `env · inferred` when it doesn't (no manifest witness — a soft claim). Empty = the
// unit is ungated (shared across every environment). The src buttons are wired by the enclosing
// the delegated source-link listener.
function variantsCell(variants) {
  if (!variants || !variants.length) return '<span class="gloss-none">— (all envs)</span>';
  return variants.map((v) => {
    const env = esc((v && v.env) || '');
    const g = (v && v.source) ? srcCell(v.source) : '<span class="gloss-plain">inferred</span>';
    return `${env} · ${g}`;
  }).join('<br>');
}
// The System tab: the operational / reference collections the diagram doesn't hold (run commands, entry
// points, deployment, observability, security, config, non-entity types, freeform extras). A stack of
// titled tables rendered straight into #diagram, led by a pinned section index (scroll-spy + click-to-jump,
// see bindSysIndex) so you see all sections at once and know which one you're in. Entry points are grouped
// by kind and link to their owning component; source cells open the code viewer.
function renderSystem() {
  const G = GRAPH;
  const nodeName = (id) => (G.nodes && G.nodes[id] ? G.nodes[id].name : id);
  const secs = [];  // {id, title} per rendered section — drives the pinned index
  const usedIds = new Set();
  // Wrap a section body in a titled, id'd `<section>` and register it for the index. '' body -> omitted.
  const sec = (title, inner) => {
    if (!inner) return '';
    let id = 'sys-' + String(title).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    const base = id || 'sys-section';
    for (let n = 2; usedIds.has(id); n++) id = base + '-' + n;  // dedupe (e.g. an extra named like a table)
    usedIds.add(id);
    secs.push({ id, title });
    return `<section class="uc-group" id="${id}"><h3 class="uc-actor">${esc(title)}</h3>${inner}</section>`;
  };
  const parts = [];
  // Map completeness — NUMBERS, not a wall of advisories. Two of these deliberately do not warn
  // anywhere: trace debt (the target is every use case traced; the shortfall is reported rather than
  // redefined as acceptable) and off-spine use cases inside a CORE capability (the give-up of moving
  // the spine check to capability altitude, kept visible so it stays a trade, not a silent loss).
  const C = COMPLETENESS || {};
  if (Object.keys(C).length) {
    const tile = (k, v, of, sub, tone) => {
      const pct = of ? Math.round(100 * v / of) : 0;
      return `<div class="sys-tile${tone ? ' sys-' + tone : ''}"><div class="sys-k">${esc(k)}</div>`
        + `<div class="sys-v">${v}${of ? `<span class="sys-of"> / ${of}</span>` : ''}</div>`
        + (of ? `<div class="sys-bar"><i style="width:${pct}%"></i></div>` : '')
        + (sub ? `<div class="sys-s">${esc(sub)}</div>` : '') + '</div>';
    };
    const tiles = [
      tile('Use cases traced', C.use_cases_traced || 0, C.use_cases || 0,
           (C.use_cases_untraced || 0) ? `${C.use_cases_untraced} untraced — trace debt` : 'no debt',
           (C.use_cases_untraced || 0) ? 'warn' : 'ok'),
      HAS_CAPABILITIES ? tile('Capabilities traced',
           (C.capabilities || 0) - (C.capabilities_untraced || 0), C.capabilities || 0,
           (C.capabilities_untraced || 0) ? 'a whole capability was never walked' : 'all reached',
           (C.capabilities_untraced || 0) ? 'warn' : 'ok') : '',
      tile('External surfaces unclaimed', C.entry_points_unclaimed_external || 0,
           C.entry_points_external || 0, 'no use case reaches them',
           (C.entry_points_unclaimed_external || 0) ? 'warn' : 'ok'),
      tile('Self-started unclaimed', C.entry_points_unclaimed_self || 0, 0,
           'crons / workers / boot hooks — often a record, not a use case',
           (C.entry_points_unclaimed_self || 0) ? 'warn' : 'ok'),
      HAS_CAPABILITIES ? tile('Off-spine in a core capability', C.off_spine_in_core_capabilities || 0, 0,
           'reported, not warned — the capability-level check does not see these', '') : '',
    ].join('');
    parts.push(sec('Map completeness', `<div class="sys-tiles">${tiles}</div>`));
  }
  // Entry points — grouped by CANONICAL kind (the server folds alias spellings: `http` and
  // `http-route` rows land in one group, WS-A8); each kind heading carries a small self/external
  // tag, and the self-starting kinds are listed first so "what runs with no user?" clusters at the
  // top without a separate section. Each row links to its owning component.
  const eps = G.entry_points || [];
  if (eps.length) {
    const byKind = {};
    const order = [];
    for (const e of eps) {
      const k = (e.canonical_kind || e.kind || 'other').trim() || 'other';
      if (!byKind[k]) { byKind[k] = []; order.push(k); }
      byKind[k].push(e);
    }
    // a kind is self-starting if any of its rows is; self kinds sort first (stable → first-seen order
    // preserved within each activation).
    const kindAct = (k) => (byKind[k].some((e) => e.activation === 'self') ? 'self' : 'external');
    order.sort((a, b) => (kindAct(a) === 'self' ? 0 : 1) - (kindAct(b) === 'self' ? 0 : 1));
    let inner = '';
    for (const k of order) {
      const act = kindAct(k);
      const rows = byKind[k].map((e) => {
        const comp = (e.component && G.nodes && G.nodes[e.component])
          ? `<button type="button" class="src sys-node" data-id="${esc(e.component)}" data-idx="${e.index || 0}">${esc(nodeName(e.component))}</button>`
          : '<span class="gloss-none">—</span>';
        // WS-A2: a recorded cadence renders as a small tag after the trigger ("when does it run?"
        // answered inline); clicking its source anchor is served by the Cadence md column instead.
        const cad = e.cadence ? ` <span class="sys-kind-tag">${esc(e.cadence)}</span>` : '';
        return `<tr><td>${mdInline(e.trigger || '')}${cad}</td><td>${comp}</td><td>${srcCell(e.source || '')}</td></tr>`;
      }).join('');
      const tag = act === 'self' ? '<span class="sys-kind-tag sys-kind-tag--self">auto-run</span>' : '';
      inner += `<h4 class="sys-subhead">${esc(k)}${tag}</h4>`
        + '<table class="glossary"><thead><tr><th>Trigger</th><th>Component</th><th>Source</th></tr></thead>'
        + `<tbody>${rows}</tbody></table>`;
    }
    parts.push(sec('Entry points', inner));
  }
  parts.push(sec('Run commands', refTable(G.run_commands, [
    { head: 'Action', get: (r) => r.action }, { head: 'Command', get: (r) => r.command },
    { head: 'Source', get: (r) => ({ src: r.source }) }])));
  // NO "Deployment & topology" and NO "Messaging" tables here. Both restated, less completely, what a
  // diagram now draws: every deployment row's Unit/Runs on/Exposed as/Config source/Variants is the
  // pane of its box on the Deployment view (a process box, or — for an infrastructure unit that hosts
  // no code — the dependency box standing in for it), and every channel is a Data-tab card with the
  // same fields, its broker implied by the pane it sits in. This tab is for facts NO diagram holds;
  // duplicating a table here just gave each fact two homes that could drift.
  parts.push(sec('Observability', refTable(G.observability, [
    { head: 'Signal', get: (r) => r.signal }, { head: 'Where emitted', get: (r) => r.where_emitted },
    { head: 'Where viewed', get: (r) => r.where_viewed }, { head: 'Alerts', get: (r) => r.alerts }])));
  parts.push(sec('Security & auth', refTable(G.security, [
    { head: 'Surface', get: (r) => r.surface }, { head: 'Who can reach', get: (r) => r.who },
    { head: 'Auth check', get: (r) => ({ src: r.source }) }, { head: 'Risk', get: (r) => r.risk }])));
  parts.push(sec('Config & environments', refTable(G.config, [
    { head: 'Key', get: (r) => r.key }, { head: 'Purpose', get: (r) => r.purpose },
    { head: 'Default', get: (r) => r.default }, { head: 'Per-env / secret?', get: (r) => r.per_env }])));
  parts.push(sec('Types deliberately not modelled', refTable(G.non_entity_types, [
    { head: 'Type', get: (r) => r.name }, { head: 'Source', get: (r) => ({ src: r.source }) },
    { head: 'Why', get: (r) => r.why }])));
  for (const x of (G.extras || [])) {
    if (!x || !x.heading) continue;
    parts.push(sec(x.heading, `<div class="sys-extra">${mdInline(x.body || '')}</div>`));
  }
  const body = parts.filter(Boolean).join('');
  const nav = secs.length
    ? `<nav class="sys-index">${secs.map((s) =>
        `<button type="button" class="sys-index-chip" data-target="${s.id}">${esc(s.title)}</button>`).join('')}</nav>`
    : '';
  diagram.innerHTML = `<div class="usecases-wrap system-wrap">${body ? nav + body : '<p class="empty">No system facts recorded.</p>'}</div>`;
  // A System-tab entry-point Component link navigates to that component AND selects the exact entry
  // point in its "Triggered by" pane list (same as a search hit).
  diagram.querySelectorAll('.sys-node').forEach((btn) => {
    btn.addEventListener('click', () => selectEntryPoint(
      btn.getAttribute('data-id'), parseInt(btn.getAttribute('data-idx'), 10) || 0));
  });
  bindSysIndex();
}
// Wire the System tab's pinned section index: click a chip to jump to its section, and highlight the chip
// of the section you're currently scrolled into (scroll-spy). Also measures the index bar's height into a
// CSS var so the sticky section headers sit just below it.
function bindSysIndex() {
  const wrap = diagram.querySelector('.system-wrap');
  const nav = wrap && wrap.querySelector('.sys-index');
  if (!wrap || !nav) return;
  const chips = [...nav.querySelectorAll('.sys-index-chip')];
  const sections = chips.map((c) => wrap.querySelector('#' + c.dataset.target));
  // Two stacked sticky offsets: the pinned index (top), then each section header below it, then each
  // table's column headers below THAT. Measure both heights into CSS vars so the stack lines up even when
  // the index bar / a header wraps on a narrow pane.
  const header0 = wrap.querySelector('.uc-actor');
  const setH = () => {
    wrap.style.setProperty('--sys-index-h', nav.offsetHeight + 'px');
    wrap.style.setProperty('--sys-header-h', (header0 ? header0.offsetHeight : 30) + 'px');
  };
  setH();
  if (window.ResizeObserver) new ResizeObserver(setH).observe(wrap);  // recompute when the pane resizes
  chips.forEach((chip, i) => chip.addEventListener('click', () => {
    if (sections[i]) sections[i].scrollIntoView({ block: 'start', behavior: 'smooth' });
  }));
  const spy = () => {
    const line = nav.getBoundingClientRect().bottom + 6;  // just under the pinned index
    let active = 0;
    sections.forEach((sec2, i) => { if (sec2 && sec2.getBoundingClientRect().top <= line) active = i; });
    chips.forEach((c, i) => c.classList.toggle('active', i === active));
  };
  wrap.addEventListener('scroll', spy, { passive: true });
  spy();
}

// ── Data tab (store-centric) ──────────────────────────────────────────────────────────────────────
// A rail of physical stores → a pane each: the collections (entities keyed by their structured store)
// with who writes / reads them, the coverage gaps, and — for a broker — its async channels (cards + a
// lazily-rendered per-broker flowchart). All data is server-derived (GRAPH.data_view); source cells and
// element chips honour the "link every element to its code" rule. A cross-link carries s.store (open
// that pane) and s.entity (highlight that row).
function dvChip(id, name, cls, title, def) {  // an element chip that navigates to `id` on click (tstref idiom)
  // Shows the NAME only — element ids stay internal (the `data-id` handle drives navigation), matching
  // every other view. Never surface the raw id in the UI unless the user explicitly asks.
  return `<button type="button" class="dv-chip ${cls}" data-id="${esc(id)}"`
    + (def ? ' data-def=""' : '')   // THE line that presents this entity — what a jump reveals
    + (title ? ` title="${esc(title)}"` : '')
    + `>${esc(name)}</button>`;
}
// A chip that navigates WITHIN the Data tab, to the line presenting that entity (its collection row,
// or its own row under "Stored elsewhere" when it is embedded too) — used for the parent of an
// embedded entity, where leaving for the diagram would lose the thread you are pulling. Carries
// `data-entity` rather than `data-id` so the plain element-navigation binding skips it.
function dvJumpChip(id, name) {
  return `<button type="button" class="dv-chip dv-ent dv-jump" data-entity="${esc(id)}"`
    + ` title="Show where this entity is stored">${esc(name)}</button>`;
}
// The line presenting `id` in the Data tab (marked with data-def), and the row it sits in — a
// collections-table `tr` or a "stored inside" row. Used to focus a cross-link's target.
function dvDefRow(id) {
  const sel = '.dv-chip[data-def][data-id="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]';
  const def = diagram.querySelector(sel);
  return def ? { def, row: def.closest('tr, .dv-embrow'), pane: def.closest('.dv-pane') } : null;
}
// One async-channel card — publishers → consumers → payload entity + the declaring source line. Shared
// by a broker store's pane and the "unassigned channels" pane so the two can never drift.
function dvChannelCard(ch) {
  const chips = (arr, cls) => arr && arr.length
    ? arr.map((c) => dvChip(c.id, c.name, cls)).join('') : '<span class="dv-none">—</span>';
  return `<div class="dv-card"><h4>${esc(ch.name)} <span class="dv-kindpill">${esc(ch.kind || 'channel')}</span></h4>`
    + `<div class="dv-cardrow"><span class="dv-lbl">Publishers</span><div class="dv-chips">${chips(ch.publishers, 'dv-write')}</div></div>`
    + `<div class="dv-cardrow"><span class="dv-lbl">Consumers</span><div class="dv-chips">${chips(ch.consumers, 'dv-read')}</div></div>`
    + `<div class="dv-cardrow"><span class="dv-lbl">Payload</span><div class="dv-chips">${ch.payload ? dvChip(ch.payload, ch.payload_name, 'dv-ent') : '<span class="dv-none">untyped</span>'}</div></div>`
    + `<div class="dv-cardrow"><span class="dv-lbl">Declared</span>${srcCell(ch.source || '')}</div></div>`;
}
function dvRenderChannels(pane) {  // lazily render each broker flowchart in a shown pane (once)
  pane.querySelectorAll('.dv-chan[data-dep]').forEach(async (ph) => {
    if (ph.dataset.rendered) return;
    const src = MERMAID_CHANNELS[ph.getAttribute('data-dep')];
    if (!src) { ph.remove(); return; }
    ph.dataset.rendered = '1';
    const seq = renderSeq;
    let svg;
    try { ({ svg } = await mermaid.render('dvChan' + (rc++), src)); }
    catch (_) { return; }
    if (seq !== renderSeq || !document.body.contains(ph)) return;  // navigated away mid-layout — drop
    ph.innerHTML = svg;
    // Best-effort: bind a mermaid component node (id like `flowchart-C116-3`) to navigate to it.
    ph.querySelectorAll('g.node').forEach((g) => {
      const m = /-((?:C|D|E|S|SD|UC)\d+)-\d+$/.exec(g.id || '');
      if (m && GRAPH.nodes[m[1]]) { g.style.cursor = 'pointer'; g.addEventListener('click', () => selectFromTree(m[1])); }
    });
  });
}
function dvShow(paneId) {
  diagram.querySelectorAll('.dv-pane').forEach((p) => p.classList.toggle('active', p.id === paneId));
  diagram.querySelectorAll('.dv-store').forEach((b) => b.setAttribute('aria-current', String(b.dataset.pane === paneId)));
  const pane = diagram.querySelector('#' + paneId);
  if (pane) { dvRenderChannels(pane); const c = diagram.querySelector('.dv-content'); if (c) c.scrollTop = 0; }
}
function renderData(s) {
  const dv = DATA_VIEW || {};
  const stores = dv.stores || [];
  const nodeName = (id) => (GRAPH.nodes && GRAPH.nodes[id] ? GRAPH.nodes[id].name : id);
  const gapsByDep = {}; for (const g of (dv.gaps || [])) gapsByDep[g.dep] = g.pairs;
  const paneId = (dep) => 'dv-pane-' + dep;
  const rail = [];    // rail button HTML
  const panes = [];   // pane HTML

  // Writer/reader/other chip lists for one collection row.
  const rwCell = (list, cls, empty) => list && list.length
    ? `<div class="dv-chips">${list.map((c) => dvChip(c.id, c.name, cls + (c.owner ? ' dv-persist' : ''), c.verb)).join('')}</div>`
    : `<span class="dv-none">${empty}</span>`;

  const dbRail = [];
  const busRail = [];
  for (const st of stores) {
    const gaps = gapsByDep[st.dep];
    const warn = gaps && gaps.length ? '<span class="dv-warn-dot" title="coverage gap"></span>' : '';
    const isBus = st.kind === 'messaging';
    const cnt = st.rows.length || (st.channels.length ? st.channels.length : 0);
    const dot = `<span class="dv-dot${isBus ? ' bus' : ''}${st.rows.length || st.channels.length ? '' : ' ghost'}"></span>`;
    const btn = `<button type="button" class="dv-store" data-pane="${paneId(st.dep)}">${dot}`
      + `<span class="dv-nm">${esc(st.name)}</span>${warn}<span class="dv-ct">${cnt || '·'}</span></button>`;
    (isBus ? busRail : dbRail).push(btn);

    // ── pane ──
    const roleTag = (st.roles || []).length ? `<span class="dv-roles">${(st.roles).map(esc).join(' · ')}</span>` : '';
    let body = `<div class="dv-panehead"><h2>${esc(st.name)}</h2>`
      + `<span class="dv-kindpill">${esc(st.kind || 'store')}</span>${roleTag}`
      + `<span class="dv-stat"><b>${st.rows.length}</b> ${st.rows.length === 1 ? 'collection' : 'collections'}</span>`
      + (st.channels.length ? `<span class="dv-stat"><b>${st.channels.length}</b> ${st.channels.length === 1 ? 'channel' : 'channels'}</span>` : '')
      + (st.where ? `<span class="dv-stat">${srcCell(st.where)}</span>` : '') + '</div>';
    if (gaps && gaps.length) {
      body += `<div class="dv-coverage"><span aria-hidden="true">&#9888;</span> <span><b>`
        + `${gaps.length} write${gaps.length === 1 ? '' : 's'} into ${esc(st.name)} not explained by any entity:</b> `
        + gaps.map((p) => dvChip(p.component, nodeName(p.component), 'dv-write', p.verb)).join(' ')
        + ` — a real container may be missing from the domain model.</span></div>`;
    }
    if (st.rows.length) {
      const access = dv.access || {};
      const rows = st.rows.map((r) => {
        const notes = [];
        if (r.mode && r.mode !== 'collection') notes.push(`<span class="dv-tag">${esc(r.mode)}</span>`);
        if (r.notes) notes.push(`<span class="dv-tag">${esc(r.notes)}</span>`);
        const a = access[r.entity] || {};
        const readers = (a.readers || []).concat(a.other || []);
        return `<tr><td class="dv-coll">${r.container ? esc(r.container) : '<span class="dv-none">—</span>'}</td>`
          + `<td>${dvChip(r.entity, r.name, 'dv-ent', '', true)}</td>`
          + `<td class="dv-meaning">${mdInline(r.meaning || '')}</td>`
          + `<td>${notes.join(' ')}</td>`
          + `<td>${rwCell(a.writers, 'dv-write', 'no mapped writers')}</td>`
          + `<td>${rwCell(readers, 'dv-read', 'no mapped readers')}</td></tr>`;
      }).join('');
      body += `<div class="dv-tablewrap"><table class="dv-table"><thead><tr><th>Collection</th><th>Entity</th>`
        + `<th>Meaning</th><th>Notes</th><th>Written by</th><th>Read by</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    } else if (!st.channels.length) {
      body += `<p class="dv-derived">No entity in the domain model is recorded as living here — this `
        + `store is reached by code, but nothing says which data it holds.</p>`;
    }
    if (st.channels.length) {
      body += `<h3 class="dv-subhead">Async channels</h3>`;
      if (MERMAID_CHANNELS[st.dep]) body += `<div class="dv-chan" data-dep="${esc(st.dep)}"></div>`;
      body += '<div class="dv-cards">' + st.channels.map(dvChannelCard).join('') + '</div>';
    }
    panes.push(`<div class="dv-pane" id="${paneId(st.dep)}" role="region" aria-label="${esc(st.name)}">${body}</div>`);
  }

  // Unassigned channels (broker: '') — a pane so catalogued channels are never silently dropped.
  const unassigned = dv.unassigned_channels || [];
  if (unassigned.length) {
    busRail.push(`<button type="button" class="dv-store" data-pane="dv-pane-unassigned"><span class="dv-dot bus"></span>`
      + `<span class="dv-nm">Unassigned channels</span><span class="dv-ct">${unassigned.length}</span></button>`);
    const cards = unassigned.map(dvChannelCard).join('');
    panes.push(`<div class="dv-pane" id="dv-pane-unassigned" role="region" aria-label="Unassigned channels">`
      + `<div class="dv-panehead"><h2>Unassigned channels</h2><span class="dv-stat">no broker dependency recorded</span></div>`
      + `<div class="dv-cards">${cards}</div></div>`);
  }

  // Entities with no collection of their own. Split by SECTION, because "not persisted" was wrong for
  // the biggest of them: an embedded entity IS stored, inside a parent's document — so that group also
  // names the parent and the collection it ultimately lands in (dv.not_persisted[].entities[].home).
  const np = dv.not_persisted || [];
  const npSections = dv.np_sections || [];
  const SECTION_BLURB = {
    elsewhere: 'Durable data with no collection of its own — it rides inside another entity’s document, so it lives wherever that parent lives.',
    outside: 'Never written to a datastore — derived at request time, or living in the source itself.',
  };
  const npPaneId = (key) => 'dv-pane-np-' + key;
  const embRow = (e) => {
    const parents = (e.parents || []).map((p) => dvJumpChip(p.id, p.name)).join('');
    const home = e.home
      ? `<span class="dv-home">🛢 ${esc(e.home.container || e.home.name)}</span>`
      : '<span class="dv-none">no physical home found</span>';
    return `<div class="dv-embrow">${dvChip(e.id, e.name, 'dv-ent', '', true)}`
      + `<span class="dv-in">inside</span>${parents || '<span class="dv-none">—</span>'}${home}</div>`;
  };
  const npGroupHtml = (grp) => `<div class="dv-grouprow"><h3>${esc(grp.label)} (${grp.entities.length})`
    + (grp.warn ? ' <span class="dv-tag dv-tag-warn">no store linked</span>' : '') + '</h3>'
    + (grp.mode === 'embedded'
      ? `<div class="dv-embtable">${grp.entities.map(embRow).join('')}</div>`
      : `<div class="dv-chips">${grp.entities.map((e) =>
          dvChip(e.id, e.name, 'dv-ent', e.container || e.mode, true)).join('')}</div>`)
    + '</div>';
  const npRailBySection = {};
  for (const sec of npSections) {
    const groups = np.filter((g) => g.section === sec.key);
    if (!groups.length) continue;
    const total = groups.reduce((n, g) => n + g.entities.length, 0);
    panes.push(`<div class="dv-pane" id="${npPaneId(sec.key)}" role="region" aria-label="${esc(sec.label)}">`
      + `<div class="dv-panehead"><h2>${esc(sec.label)}</h2>`
      + `<span class="dv-stat"><b>${total}</b> ${total === 1 ? 'entity' : 'entities'}</span></div>`
      + `<p class="dv-derived">${SECTION_BLURB[sec.key] || ''}</p>`
      + `<div class="dv-grouplist">${groups.map(npGroupHtml).join('')}</div></div>`);
    npRailBySection[sec.key] = { label: sec.label, buttons: groups.map((grp) =>
      `<button type="button" class="dv-store" data-pane="${npPaneId(sec.key)}">`
      + `<span class="dv-dot ghost"></span><span class="dv-nm">${esc(grp.label)}</span>`
      + (grp.warn ? '<span class="dv-warn-dot"></span>' : '')
      + `<span class="dv-ct">${grp.entities.length}</span></button>`).join('') };
  }

  if (dbRail.length) rail.push(`<div class="dv-railgroup">Data stores</div>${dbRail.join('')}`);
  if (busRail.length) rail.push(`<div class="dv-railgroup">Message bus</div>${busRail.join('')}`);
  for (const sec of npSections) {   // one rail heading per section — each states what it actually is
    const g = npRailBySection[sec.key];
    if (g) rail.push(`<div class="dv-railgroup">${esc(g.label)}</div>${g.buttons}`);
  }

  diagram.innerHTML = `<div class="dv-wrap"><nav class="dv-rail" aria-label="Physical stores">${rail.join('')}</nav>`
    + `<section class="dv-content">${panes.join('')}</section></div>`;
  diagram.querySelectorAll('.dv-store').forEach((b) => b.addEventListener('click', () => dvShow(b.dataset.pane)));
  diagram.querySelectorAll('.dv-chip[data-id]').forEach((b) =>
    b.addEventListener('click', () => selectFromTree(b.getAttribute('data-id'))));
  // Stay in the tab: reveal that entity's own line wherever it is presented.
  diagram.querySelectorAll('.dv-jump[data-entity]').forEach((b) =>
    b.addEventListener('click', () => go({ kind: 'data', entity: b.getAttribute('data-entity') })));

  // Which pane to open: the pane holding the target ENTITY's own line (it may be a collection row in a
  // store pane, or a "stored inside" row — a jump doesn't know which, and shouldn't have to), else the
  // named store, else the store with the most collections, else the first pane.
  const hit = (s && s.entity) ? dvDefRow(s.entity) : null;
  let target = (hit && hit.pane) ? hit.pane.id : null;
  if (!target && s && s.store && diagram.querySelector('#' + paneId(s.store))) target = paneId(s.store);
  if (!target && stores.length) {
    const best = stores.reduce((a, b) => (b.rows.length > a.rows.length ? b : a), stores[0]);
    target = paneId(best.dep);
  }
  if (!target) target = (diagram.querySelector('.dv-pane') || {}).id;
  if (target) dvShow(target);
  if (hit && hit.row) { hit.row.classList.add('dv-flash'); hit.row.scrollIntoView({ block: 'center' }); }
}

// A test row's Target cell: each target element by NAME (the server already resolved id -> name +
// node, so there is NO client-side id parsing). A target that is a drawn node links out to locate it
// in its home view; an unresolved one is plain text. The optional grouping `label` prefixes them.
function testTargets(t) {
  const refs = (t.targets || []).map((g) => g.node
    ? `<a href="#" class="tstref" data-id="${esc(g.node)}">${esc(g.name)}</a>`
    : `<span>${esc(g.name)}</span>`).join(', ');
  const label = (t.label || '').trim();
  if (label && refs) return `${esc(label)} <span class="muted">(${refs})</span>`;
  return label ? esc(label) : refs;
}
// The Tests tab: the test-completeness gap table (tests[]) led by the honesty note (tests_note — was the
// suite actually run, or is every row inferred?). Rendered like the System/Glossary tabs.
function renderTests() {
  const note = (GRAPH.tests_note || '').trim();
  const noteHtml = note ? `<div class="tests-note">${mdInline(note)}</div>` : '';
  const rows = (GRAPH.tests || []).map((t) => {
    const tested = (t.tested || '').trim();
    const low = tested.toLowerCase();
    const cls = low.startsWith('y') ? 'tested' : (low.includes('partial') ? 'partial' : 'untested');
    const pill = tested ? `<span class="tst-pill tst-${cls}">${esc(tested)}</span>` : '';
    // Each test suite/file is a bare anchor rendered by the shared srcCell -> a clickable code link,
    // plus its optional "what it covers" note. Same source-link contract as Glossary / System.
    const testsCell = (t.tests || []).map((ev) =>
      srcCell(ev.file || '') + (ev.why ? ' — ' + esc(ev.why) : '')).join(' · ');
    return `<tr><td>${testTargets(t)}</td><td>${pill}</td><td>${testsCell}</td>`
      + `<td>${mdInline(t.gap || '')}</td><td>${mdInline(t.confidence || '')}</td></tr>`;
  }).join('');
  const table = (GRAPH.tests || []).length
    ? '<table class="glossary"><thead><tr><th>Target</th><th>Tested?</th><th>Test(s)</th>'
      + '<th>Gap / risk</th><th>Confidence</th></tr></thead>'
      + `<tbody>${rows}</tbody></table>`
    : '<p class="empty">No test-completeness rows recorded.</p>';
  diagram.innerHTML = `<div class="usecases-wrap system-wrap">${noteHtml}${table}</div>`;
  diagram.querySelectorAll('a.tstref').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault(); selectFromTree(a.getAttribute('data-id'));
  }));
}

// The Business logic tab (T7): the decisions this product makes, grouped by block. A rail of blocks
// on the left, one pane of rules per block on the right — the shape the Data tab uses, because a
// reader browses decision AREAS the way they browse stores.
//
// NOTHING HERE IS DERIVED IN JS. A site's owning components, a rule's use-case steps and entities,
// and whether it has been swept all arrive computed by the one Python implementation
// (validate_model / views._build_rules_view). Re-deriving any of them from `sites` would be a second
// answer that eventually disagrees — the exact drift this layer was built to make impossible.
function renderRules(s) {
  const rv = RULES_VIEW || {};
  const blocks = rv.blocks || [];
  const rules = rv.rules || [];
  // The pane KEY, not the block id: the "not assigned" group has no id, and an empty-string key
  // makes its `stateKey` identical to the tab's own — `go()` then no-ops and the group can never be
  // opened. `none` is the key for that group everywhere: state, pane id, and rail button.
  const paneId = (key) => 'br-pane-' + (key || 'none');
  const byBlock = new Map();
  for (const r of rules) byBlock.set(r.block || 'none', (byBlock.get(r.block || 'none') || []).concat([r]));

  // A site: line — component(s). EVERY owner is listed; one nobody claims says so rather than
  // rendering blank, and a declared absence says what it is instead of pretending to be a gap.
  const siteRow = (site) => {
    if (site.declared && !site.where) {
      return '<li class="br-site br-declared"><span class="br-nowhere">enforced by construction</span>'
        + (site.why ? ' <span class="br-why">' + esc(site.why) + '</span>' : '') + '</li>';
    }
    const owners = site.components || [];
    const who = owners.length
      ? owners.map((c) => `<button type="button" class="br-comp" data-id="${esc(c.id)}">${esc(c.name)}</button>`).join('')
      : '<span class="br-unverified">no component claims this file</span>';
    return `<li class="br-site${owners.length ? '' : ' br-bare'}">${srcCell(site.where || '')}`
      + `<span class="br-owners">${who}</span>`
      + (site.why ? ` <span class="br-why">${esc(site.why)}</span>` : '') + '</li>';
  };

  // A step link says WHICH step and HOW STRONGLY: the exact line, or the same enclosing function.
  // The distinction is the honest half — "inside the same function as this step" is a weaker claim
  // than "this step", and collapsing them would be the readout pretending to be a proof.
  const stepChip = (l) => {
    // The sub-flow's NAME, never its id: the viewer speaks the reader's language.
    const via = l.container === l.uc ? '' : ' \u00b7 ' + esc(l.containerName || l.container);
    const exact = l.strength === 'exact';
    return `<button type="button" class="br-step${exact ? '' : ' br-near'}" data-uc="${esc(l.uc)}" `
      + `data-container="${esc(l.container)}" data-n="${esc(String(l.n))}" `
      + `title="${exact ? 'this exact step' : 'inside the same function as this step'}">`
      + `${esc(l.ucName)} step ${esc(String(l.n))}${via}</button>`;
  };

  const ruleCard = (r) => {
    const tags = (r.access ? '<span class="br-tag br-access">access</span>' : '')
      + (r.swept ? '' : '<span class="br-tag br-debt">sweep debt</span>')
      + (r.unverified ? '<span class="br-tag br-warn">unverified</span>' : '')
      + (r.confidence ? `<span class="br-tag">${esc(r.confidence)}</span>` : '');
    const steps = (r.steps || []).map(stepChip).join('');
    const ents = (r.entities || []).map((e) =>
      `<button type="button" class="br-ent" data-id="${esc(e.id)}">${esc(e.name)}</button>`).join('');
    return `<article class="br-rule" id="br-${esc(r.id)}"><h3>${esc(r.statement)}${tags}</h3>`
      + `<ul class="br-sites">${(r.sites || []).map(siteRow).join('')}</ul>`
      + (steps ? `<div class="br-line"><span class="br-lbl">Enforced at</span>${steps}</div>` : '')
      + (ents ? `<div class="br-line"><span class="br-lbl">Touches</span>${ents}</div>` : '')
      + '</article>';
  };

  const rail = [];
  const panes = [];
  // Blocks nest (validate supports BLK2.parent = BLK1), so the rail walks the forest depth-first
  // and indents a child under its parent. Rendering them flat drew a child as its parent's sibling.
  const kids = new Map();
  for (const b of blocks) kids.set(b.parent || '', (kids.get(b.parent || '') || []).concat([b]));
  const groups = [];
  const walk = (parent, depth, seen) => {
    for (const b of kids.get(parent) || []) {
      if (seen.has(b.id)) continue;          // cycle-safe (a cycle is validate's problem, not ours)
      seen.add(b.id);
      groups.push([b.id, b.name, b.purpose, depth]);
      walk(b.id, depth + 1, seen);
    }
  };
  walk('', 0, new Set());
  const placed = new Set(blocks.map((b) => b.id));
  if (rules.some((r) => !placed.has(r.block))) groups.push(['none', 'Not assigned to a block', '', 0]);
  for (const [bid, name, purpose, depth] of groups) {
    const mine = byBlock.get(bid) || [];
    const debt = mine.filter((r) => !r.swept).length;
    rail.push(`<button type="button" class="dv-store" data-pane="${paneId(bid)}"`
      + `${depth ? ` style="padding-left:${14 + depth * 14}px"` : ''}>`
      + `<span class="dv-dot${mine.length ? '' : ' ghost'}"></span>`
      + `<span class="dv-nm">${esc(name)}</span>`
      + (debt ? '<span class="br-dot" title="sweep debt"></span>' : '')
      + `<span class="dv-ct">${mine.length || '\u00b7'}</span></button>`);
    panes.push(`<section class="dv-pane" id="${paneId(bid)}" role="region" aria-label="${esc(name)}">`
      + `<div class="dv-panehead"><h2>${esc(name)}</h2>`
      + `<span class="dv-stat"><b>${mine.length}</b> ${mine.length === 1 ? 'rule' : 'rules'}</span></div>`
      + (purpose ? `<p class="br-purpose">${mdInline(purpose)}</p>` : '')
      + (mine.length ? mine.map(ruleCard).join('')
                     : '<p class="empty">No rules assigned to this block yet.</p>')
      + '</section>');
  }

  diagram.innerHTML = '<div class="dv-wrap">'
    + `<nav class="dv-rail"><div class="dv-railgroup"><h3>Decision areas</h3>${rail.join('')}</div></nav>`
    + `<div class="dv-panes">${panes.join('')}</div></div>`;

  // The same show/hide contract the Data tab uses — `.dv-pane.active` + `aria-current` on the rail
  // button, not a second mechanism with its own CSS.
  const open = (bid) => {
    const pid = paneId(bid);
    diagram.querySelectorAll('.dv-pane').forEach((el) => el.classList.toggle('active', el.id === pid));
    diagram.querySelectorAll('.dv-store').forEach((b) =>
      b.setAttribute('aria-current', String(b.dataset.pane === pid)));
  };
  const first = (s && s.blk) || (groups[0] ? groups[0][0] : 'none');
  open(first);
  diagram.querySelectorAll('.dv-rail .dv-store').forEach((el) => el.addEventListener('click', () => {
    go({ kind: 'rules', blk: el.getAttribute('data-pane').slice('br-pane-'.length) });
  }));
  // A component chip locates that component in its structural diagram; an entity chip its card.
  diagram.querySelectorAll('.br-comp, .br-ent').forEach((el) => el.addEventListener('click', () => {
    selectFromTree(el.getAttribute('data-id'));
  }));
  // A step chip opens the flow AT that step — the same jump the flow-step pane offers back. The
  // narrative index is not the authored `n` (a sub-flow's steps are spliced in), so resolve it
  // through the flow's own narration by `(authoring container, n)`, the pair that identifies a step.
  diagram.querySelectorAll('.br-step').forEach((el) => el.addEventListener('click', () => {
    const uc = el.getAttribute('data-uc');
    const container = el.getAttribute('data-container');
    const n = Number(el.getAttribute('data-n'));
    const cur = (FLOWS_NARR[uc] || []).findIndex((st) => st.n === n && (st.sf || uc) === container);
    go({ kind: 'usecase', uc, flow: cur >= 0 ? { cur, active: true } : undefined });
  }));
  if (s && s.br) {
    const card = diagram.querySelector('#br-' + s.br);
    if (card) card.scrollIntoView({ block: 'center' });
  }
}

// `sArg` renders a specific state (defaults to the current history entry); `transient` renders it purely
// for the drill animation's intermediate "flash" — no panel/selection/camera-restore side effects, so it
// doesn't disturb history or the info pane.
async function render(sArg, transient) {
  const seq = ++renderSeq;
  hideActionIconTip();  // a re-render replaces the diagram — drop any tooltip from the old one
  if (mainPz) { mainPz.destroy(); mainPz = null; }
  flowPlay = null; flowplayer.hidden = true;  // hide the step player until bindFlow re-arms it for a flow view
  const s = sArg || history[hi];
  // Hide the floating over-the-diagram control HERE, before the HTML-tab early returns below.
  // syncFlowPicker runs at the END of render, which the table views (Glossary / Use Cases / System /
  // Data / Tests) and the degraded "could not render" branch never reach — so a control shown on a
  // diagram would otherwise still be floating over the table you switched to.
  const fp = document.getElementById('flowpicker');
  if (fp) fp.hidden = true;
  // The Glossary tab is a term TABLE, not a mermaid diagram — render it straight into the stage and
  // keep the chrome (breadcrumb + active tab). No panZoom/scene/tree machinery to set up, so return
  // before the diagram path, the same shape as the degraded "could not render" branch below.
  if (s.kind === 'glossary') { renderGlossary(); mainScene = null; showViewIntro(s); renderChrome(s); return; }
  // The Use Cases tab is an actor-grouped HTML catalog, not a mermaid diagram — same shape as Glossary.
  if (s.kind === 'usecases') { renderUseCases(); mainScene = null; showViewIntro(s); renderChrome(s); return; }
  // The System tab is a set of operational reference tables (HTML), not a mermaid diagram — same shape.
  if (s.kind === 'system') { renderSystem(); mainScene = null; showViewIntro(s); renderChrome(s); return; }
  // The Data tab is the store-centric rail+panes view (HTML + lazily-rendered broker diagrams) — same shape.
  if (s.kind === 'data') { renderData(s); mainScene = null; showViewIntro(s); renderChrome(s); return; }
  // The Tests tab is the test-completeness gap table (HTML) — same shape as the System/Glossary tabs.
  if (s.kind === 'tests') { renderTests(); mainScene = null; showViewIntro(s); renderChrome(s); return; }
  // The Business logic tab is the block rail + rule panes (HTML) — the same shape as Data.
  if (s.kind === 'rules') { renderRules(s); mainScene = null; showViewIntro(s); renderChrome(s); return; }
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
  if (s.kind === 'deployment' || s.kind === 'deploymentUnit') styleDeploymentLanes(diagram);  // bold lane titles + gap
  mainScene = makeScene(diagram, () => applyDefaultPanel(s));
  iconOverlay = ensureIconOverlay(diagram);  // front layer for corner icons + badges — must exist before bindFor/decorate add any
  for (const id in ACTION_ICONS) delete ACTION_ICONS[id];  // reset before bindFor's bindFrameDrill re-populates it
  bindFor(s);
  decorateActionIcons(mainScene, s);  // corner icon = each drawn box's one useful secondary action
  // Every drawn box gets a default re-select closure (plain-click select), so back/forward can restore
  // a node selection. Edges, flow steps and HP actors/steps register their own during bindFor; a box
  // with special select behaviour (the Libraries fold) pre-registers too, so it's skipped here.
  for (const id in mainScene.nodeEls) {
    if (!mainScene.selectors['node:' + id]) {
      const el = mainScene.nodeEls[id];
      mainScene.selectors['node:' + id] = () => selAdd(mainScene, nodeDesc(mainScene, el, id));
    }
  }
  // Whether this state carries a selection we can restore below (its captured multi-selection, or a single
  // requested key) — used to skip the plain landing panel that a restore would just overwrite.
  const willRestore = selectionKeysFor(mainScene, s).length > 0;
  // Skip the plain landing panel when a more specific selection below is about to override it anyway —
  // it would just be thrown away, and (since showNode/syncTreeToNode mirror into the file browser) it'd
  // also plant a spurious intermediate tree-highlight that throws off the near/far centering heuristic
  // in highlightTreePath (the REAL previous selection stops being `prevRow` for the one that matters).
  // Landing on a view with nothing selected (a tab / drill, not a folder element click): show its
  // default panel and default the code slot to the file browser (nothing selected -> browse). An explicit
  // selection (pendingSelect below) instead runs through updateFolderPeek, which browses only for a folder.
  if (!transient && !pendingSelect && !willRestore) { applyDefaultPanel(s); setBrowsing(true); }
  if (mode === 'diff' && hasDiff()) applyDiffOverlay(s);  // diff badges that aren't drawn by the binders
  // Some binders append decorative SVG marks (for example Happy Path junction dots) after the overlay
  // was created. Raise the whole overlay once decoration is complete so controls and hover bridges are
  // the final painted and hit-tested layer in every Mermaid diagram shape.
  if (iconOverlay && iconOverlay.parentNode) iconOverlay.parentNode.appendChild(iconOverlay);
  // The capability overlay re-applies on EVERY render, so it survives a drill, a dive, back/forward
  // and a tab restore — unlike the environment filter, which is re-applied from its own screen only
  // because it is scoped to that screen. A scope the reader chose should not evaporate on navigation.
  syncFlowPicker(s);
  // A file-browser click navigated here to reveal a node: select it now the view has rendered. The
  // box is drawn (we picked the view so it would be) — fall back to its panel + tree row if not.
  // pendingMatchTextId: a node reached this way ALWAYS gets the zoom-to-match-sidebar-text-size move
  // (see matchTextSize) — but mainPz doesn't exist yet at this point (it's still the PREVIOUS view's
  // instance, or null, on a fresh navigation), so it's applied below, once svgPanZoom has been
  // (re)constructed for the new view.
  let pendingMatchTextId = null;
  let pendingCenterId = null;
  if (!transient && pendingSelect) {
    const id = pendingSelect; pendingSelect = null;
    const el = mainScene.nodeEls[id];
    if (el) selectNode(mainScene, el, id); else showNodeDetailSynced(id);
    if (el) pendingMatchTextId = id;
  } else if (!transient && restoreSelection(mainScene, s)) {
    // history revisit (the whole captured multi-selection) OR a fresh focus-drill (a single requested key)
    // — restoreSelection replayed it above. A fresh focus-drill (pendingCenter set at drill time) centers
    // its focused node at the fit zoom so it can't land off-screen; a plain history revisit leaves
    // pendingCenter null and keeps the camera.
    if (pendingCenter && s.sel === 'node:' + pendingCenter && mainScene.nodeEls[pendingCenter]) pendingCenterId = pendingCenter;
  }
  if (!transient) pendingCenter = null;
  const svgEl = diagram.querySelector('svg');
  if (svgEl && window.svgPanZoom) {
    svgEl.removeAttribute('style');
    // No practical zoom cap: bounds are wide enough to act unbounded while still keeping the
    // diagram recoverable. The header zoom control (zoomctl) replaces the old overlay icons.
    mainPz = svgPanZoom(svgEl, {
      controlIcons: false, fit: true, center: true, minZoom: 0.01, maxZoom: 1000,
      dblClickZoomEnabled: false,  // double-click is for selecting/reading nodes, not zooming
      mouseWheelZoomEnabled: false,  // wheel/trackpad-scroll pans; only Ctrl/Cmd/pinch zooms — see wheelNavigate
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
    // A focus-drill centre (pendingCenterId) skips the restore for the same reason a matchTextSize does:
    // it re-aims the camera, and it must measure against the synchronously-applied fresh fit, not a
    // restored vp that svg-pan-zoom won't paint until the next frame.
    const vp = (transient || pendingMatchTextId || pendingCenterId) ? null : (s.vp || vpByView[stateKey(s)]);
    if (vp) { mainPz.zoom(vp.zoom); mainPz.pan(vp.pan); }
    updateZoomLevel();
    if (pendingMatchTextId) matchTextSize(mainScene.nodeEls[pendingMatchTextId]);
    else if (pendingCenterId) applyZoomAndCenter(mainScene.nodeEls[pendingCenterId], 1);  // centre only, keep the fit zoom
    flowInit(s);  // a flow view: restore this history point's selected/saved step, or start fresh
  }
  // Empty-space click behaviour, mirroring the on-element gestures: a plain click deselects; a shift-click
  // is a pure camera move — with no element under it, it fits+centers the WHOLE diagram (the background
  // analog of shift-clicking an element to frame it); a ⌘-click is a no-op (Finder semantics), so a
  // ⌘-click that just misses an element while building a multi-selection can't wipe what's selected.
  if (svgEl) svgEl.addEventListener('click', (e) => {
    if (isDrag(e)) return;
    if (e.shiftKey) { if (mainPz) { mainPz.reset(); updateZoomLevel(); } return; }  // fit + center the whole diagram
    if (isMultiSelectClick(e)) return;
    resetScene(mainScene);
  });
  // Restore this point's remembered right pane (file+scroll or browser), overriding the selection-derived
  // pane above — so back/forward reopens the exact file/browser the point was left with, not just the
  // selection's source. Only history points carry `content` (set on leave); a fresh go() has none.
  if (!transient && s.content) applyContent(s.content);
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
const treeHead = document.getElementById('treehead');      // browser header — hosts the selected-element pill
const treePinBtn = document.getElementById('treepin');     // pins the browser as its own pane / unpins (hides) it
const cvFilesBtn = document.getElementById('cvfilesbtn');  // code-viewer button: shows the browser in the code slot
const treeCodeBtn = document.getElementById('treecodebtn'); // browser button: switches the code slot back to code
const treeResizer = document.getElementById('treeresizer');
const rowByPath = {};   // path (no trailing slash) -> { row, kids, entry, depth, built }
const pathByNode = {};  // node id -> its exact tree path (graph -> tree highlight for a mapped node)
// file path (no trailing slash) -> every element anchored there (node_path_index — filetree.py), primary
// first. The code viewer reads this to tag each element on its own source line (paintCodeTags). Built
// eagerly from FILE_TREE (unlike rowByPath, which exists for a path only once its row has been lazily
// built), so a file can be tagged the moment it's shown, whatever the tree happens to have rendered.
const anchorsByPath = {};
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

// --- file browser show/hide: pinned vs browsing ---------------------------------
// The browser has two ways to appear. PINNED (persisted) shows it as its own pane, left of the code
// viewer. BROWSING (transient) shows it IN the code viewer's slot instead — opened by the code viewer's
// Files button, or auto-opened when a selected element anchors a FOLDER (so the reader can drill).
// Picking a file ends browsing (the code viewer returns with that file). Pinning subsumes browsing; while
// pinned the browser is already visible, so the Files button is disabled and no auto-browse happens.
let treePinned = false;
let treeBrowsing = false;
let suppressBrowse = false;  // one-shot: a file the reader just picked in the browser is loading — the
                             // owning-folder reselection that follows must NOT re-open browsing over it.
function applyTreeState() {
  document.body.classList.toggle('tree-pinned', treePinned);
  document.body.classList.toggle('tree-browsing', treeBrowsing && !treePinned);
  if (cvFilesBtn) cvFilesBtn.disabled = treePinned;
  if (treeCodeBtn) treeCodeBtn.disabled = treePinned;  // the browser's Code button: no-op (disabled) while pinned
  if (treePinBtn) {
    treePinBtn.classList.toggle('pinned', treePinned);
    treePinBtn.title = treePinned ? 'Unpin (hide) the file browser' : 'Pin the file browser beside the code';
  }
}
function setBrowsing(on) {
  on = !!on && !treePinned && !document.body.classList.contains('no-tree');  // no browsing when pinned or no tree
  if (on === treeBrowsing) return;
  treeBrowsing = on;
  applyTreeState();
}
function setPinned(on) {
  on = !!on;
  if (on === treePinned) return;
  treePinned = on;
  // pinning subsumes browsing; unpinning falls back to the default — browse when the code slot has no file
  // to show (nothing selected), else keep showing that file.
  treeBrowsing = on ? false : !cvPath;
  lsSet(LS.treePinned, on ? '1' : '0');
  applyTreeState();
}
// After an active selection (showNodeDetailSynced): auto-open browsing for a folder element, or end it for
// one that shows a real file (or the suppress flag, when the reader just picked a file). No-op while pinned.
function updateFolderPeek(id) {
  if (!SERVED || treePinned) { return; }
  const consumed = suppressBrowse; suppressBrowse = false;
  const n = GRAPH.nodes[id];
  const fileCount = (n && Array.isArray(n.files)) ? n.files.length : 0;
  // An element that spans SEVERAL files opens the file BROWSER (the reader picks which one) — its files
  // are already filtered into the tree by the selection footprint. A single-file element opens that one
  // file directly. `consumed` means the reader just clicked a file IN the browser, so keep that file
  // shown instead of re-opening the browser over it.
  if (fileCount > 1 && !consumed) { setBrowsing(true); return; }
  const showsFile = !!(n && n.file && localRef(n.file) && !isDirRef(n.file, n.line));
  if (showsFile || consumed) { setBrowsing(false); return; }
  const path = pathByNode[id] || (n ? refTreePath(n.file, n.line) : null);
  if (path && rowByPath[path] && rowByPath[path].entry.dir) { expandDir(path); setBrowsing(true); }
}

// One row: a twisty (folders only), the name, and an id chip when a node points exactly here.
function makeRow(entry, depth) {
  const row = document.createElement('div');
  // `ref` = referenced by a component/entity at all (source OR owned) -> bold "on the map"; broader than
  // cov-self (anchor-only).
  row.className = 'trow cov-' + entry.cov + (entry.dir ? ' tdir' : ' tfile')
    + (entry.ref ? ' ref' : '');
  row.style.paddingLeft = (8 + depth * 14) + 'px';
  row.title = entry.path || entry.name;
  const caret = document.createElement('span');
  caret.className = 'tcaret' + (entry.dir && entry.children.length ? '' : ' leaf');
  caret.textContent = '▶';  // ▶ (rotates when the folder is open)
  if (entry.dir && entry.children.length) {
    // The twisty just expands/collapses — it must NOT reach the row's click (which would also SELECT the
    // directory). Only the rest of the row selects.
    caret.addEventListener('click', (ev) => { ev.stopPropagation(); toggleDir(treeKey(entry.path)); });
  }
  const name = document.createElement('span');
  name.className = 'tname';
  name.textContent = entry.name;
  row.appendChild(caret);
  row.appendChild(name);
  // Container pill: the row that is a container's MAIN file/directory carries that container's pill (name +
  // kind colour + dashed border) — marking where the container lives in the tree. Several containers
  // anchored at one path (rare — e.g. a folder that is both a subsystem and a subdomain) stack their pills.
  const anchored = entry.cov === 'self' ? [entry.node, ...(entry.others || [])].filter(Boolean) : [];
  const containers = anchored.filter((id) => GRAPH.nodes[id] && isContainerKind(GRAPH.nodes[id].kind));
  if (containers.length) {
    row.classList.add('has-groups');  // keep the name at natural width; the pill box scrolls (CSS)
    const box = document.createElement('span');
    box.className = 'tgroups';
    for (const cid of containers) { const pill = elementPill(cid); if (pill) box.appendChild(pill); }
    box.addEventListener('scroll', () => updatePillFade(box));  // keep the edge fade in sync while scrolling
    row.appendChild(box);
  }
  return row;  // the selection filter/count is applied in renderChildrenInto, once the row's rec exists
}
function renderChildrenInto(container, children, depth) {
  for (const entry of children) {
    const key = treeKey(entry.path);
    const row = makeRow(entry, depth);
    container.appendChild(row);
    const gbox = row.querySelector('.tgroups');
    if (gbox) updatePillFade(gbox);  // now in the live tree -> measurable; set the initial edge fade
    let kids = null;
    if (entry.dir && entry.children.length) {
      kids = document.createElement('div');
      kids.className = 'tchildren';
      container.appendChild(kids);
    }
    rowByPath[key] = { row, kids, entry, depth, built: false };
    applySelToRow(rowByPath[key]);  // a row built while a selection is active is filtered/counted immediately
    badgeDiffRow(row, entry);           // and badged/filtered if a live diff is armed
    applyDiffFilterToRow(rowByPath[key]);
    row.addEventListener('click', () => onRowClick(key));
  }
}
function onRowClick(key) {
  const rec = rowByPath[key];
  if (!rec) return;
  const e = rec.entry;
  cvPinned = null;  // a fresh click: drop any pin left by a previous unmapped-file open
  if (e.dir) {
    // A folder expands; it selects ONLY when it is itself a mapped subsystem/component (e.node set).
    // An intermediate folder that merely sits under a mapped one just expands — opening it must not
    // hijack the selection to the containing subsystem. A folder click stays in a folder peek.
    toggleDir(key);
    // e.node set -> this exact path collided in node_path_index (filetree.py): e.others carries the
    // rest — selectFromTreeAnchors selects the primary, the others are tagged in the code viewer.
    if (e.node) { suppressTreeScroll = true; selectFromTreeAnchors([e.node, ...e.others]); }
    return;
  }
  // A file row: the reader wants its source in the code viewer, so end any folder peek and show it. If we
  // were BROWSING, the point we leave is the browser (item 3: Back returns here in one step) — record that
  // before the pane is torn down, and note whether the select below navigates the diagram (a go()).
  const wasBrowsing = treeBrowsing;
  const hiBefore = hi;
  if (wasBrowsing) { pendingLeaveContent = { browse: true }; setBrowsing(false); }
  if (e.node && e.node !== treeSelId && selMemberFiles.has(key)) {
    // A file that shows an owner pill — its primary element differs from the current selection AND it sits
    // in the selection's footprint — PREVIEWS the source WITHOUT changing the selection (the pill is the
    // explicit way to switch). Keep the selection; show file + switcher.
    const owner = GRAPH.nodes[e.node];
    cvElement = e.node;
    cvFiles = (owner && owner.files) || [];
    loadCode(e.path, (e.cov === 'self' && owner) ? owner.line : null);
    suppressTreeScroll = true;
    highlightTreePath(key);
  } else if (e.node && e.cov === 'self') {
    // An ANCHOR file (a node's own source): load it AT the node's line FIRST, then select the node. The
    // explicit load matters when the reader was already viewing ANOTHER of this same node's files (an owned
    // file): without it, selecting the node hits the syncCodeView "belongs" guard, which keeps that other
    // file shown and never jumps to the anchor the reader just clicked.
    if (wasBrowsing) suppressBrowse = true;  // picked in the browser -> keep it shown (a multi-file element would else re-peek the browser)
    const an = GRAPH.nodes[e.node];
    cvElement = e.node;  // owning-element pill correct from the first header render (before selection)
    loadCode(e.path, an ? an.line : null);
    suppressTreeScroll = true;
    highlightTreePath(key);  // light up THIS row now, so a stale owned-file highlight doesn't linger on it
    selectFromTreeAnchors([e.node, ...e.others]);  // this exact file collided — e.others carries the rest
  } else if (e.node) {
    // An OWNED file (belongs to a component but isn't its anchor): show THIS file, and select its owner
    // (definition-first, already resolved into e.node). The syncCodeView/syncTreeToNode "belongs" guards
    // keep this file shown + highlighted since it's in the owner's `files`, instead of jumping to source.
    if (wasBrowsing) suppressBrowse = true;
    const owner = GRAPH.nodes[e.node];
    cvFiles = (owner && owner.files) || [];
    cvElement = e.node;
    loadCode(e.path, null);
    suppressTreeScroll = true;
    highlightTreePath(key);
    selectFromTree(e.node);
  } else {
    // A file that is not itself a node: show its OWN source (no line) and highlight its row. If it sits
    // under a mapped folder, also select that container for graph context — but PIN this file so the
    // container selection's tree/code sync keeps it shown + lit, instead of overriding to the container's
    // own anchor (the file isn't in the container's `files`, so the normal "belongs" guard wouldn't
    // protect it). The pin must NOT re-peek the browser over that file.
    if (wasBrowsing) suppressBrowse = true;
    cvElement = e.sel || null;  // the container (for context) drives the pill; a truly-unmapped file gets none
    cvFiles = [];               // a standalone file belongs to no element -> its switcher lists only itself
    loadCode(e.path, null);
    suppressTreeScroll = true;
    highlightTreePath(key);
    if (e.sel) { cvPinned = e.path; selectFromTree(e.sel); }
  }
  // Record the browser->file step. If the select above navigated the diagram, go() already pushed the new
  // point (and stashed {browse:true} on the one we left) — just tag its pane as this file. Otherwise no
  // point was pushed, so push a content point now. Back then returns to the browser in one step.
  if (wasBrowsing) {
    if (hi === hiBefore) pushContentPoint({ file: e.path, top: 0 });
    else history[hi].content = { file: e.path, top: 0 };
    pendingLeaveContent = undefined;
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
      const inBucket = (FOLDED_BUCKETS || []).find((b) => b.members.some((m) => m.id === id));
      if (inBucket) return { state: { kind: 'bucketfold', bkid: inBucket.id }, selectId: id };
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
    case 'process':  // a deployment-unit box lives on the Deployment view; open its card
      return { state: { kind: 'deploymentUnit', unit: n.unit }, selectId: id };
    // Neither is DRAWN, so neither has a `selectId` — the Business logic tab opens focused on the
    // block's pane (and, for a rule, scrolled to its card). Without these both fell through to the
    // default and landed the reader on Dependencies, showing nothing.
    case 'block':
      return { state: { kind: 'rules', blk: id } };
    case 'rule':
      return { state: { kind: 'rules', blk: n.parent || 'none', br: id } };
    default:
      return { state: { kind: 'context' }, selectId: id };  // unknown kind -> the always-present root
  }
}
// `allIds`: the full node_path_index collision set at the path this navigation came from (undefined /
// [] for callers that aren't file-tree-driven, e.g. a flow narrative link — no "Also defined here" then).
function selectFromTree(nodeId) {
  const t = selectTargetFor(nodeId);
  if (!t) { suppressTreeScroll = false; suppressBrowse = false; return; }  // no selection follows — don't leave the one-shots stuck
  const cur = history[hi];
  // Select in place when the target box is ALREADY drawn in the current view — even if this isn't the
  // node's "home" view (e.g. a component shown inside a two-subsystem edge card, or beside another
  // container). Routing to the home view in that case would needlessly swap the diagram out from under a
  // node that's already on screen (and often already selected). Only when the box isn't drawn here do we
  // navigate to a view that draws it.
  const el = mainScene && mainScene.nodeEls[t.selectId];
  if (el || (cur && stateKey(cur) === stateKey(t.state))) {  // drawn here, or already in the home view
    // Read BEFORE selectNode overwrites it: re-selecting the ALREADY-selected element (e.g. picking
    // another file of the same element in the tree) must hold the camera perfectly still — the reader
    // is browsing files, not asking to be re-framed on a box they already see.
    const alreadySelected = mainScene && selHas(mainScene, 'node:' + t.selectId);
    if (el) selectNode(mainScene, el, t.selectId); else showNodeDetailSynced(t.selectId);
    // A node NEWLY reached via the file tree gets the zoom-to-match-sidebar-text-size move — there's
    // no modifier key on a tree row to gate it on, unlike a canvas click (see selectNodeFromCanvas).
    if (el && !alreadySelected) matchTextSize(el);
  } else {                                                // navigate, then render() consumes pendingSelect
    pendingSelect = t.selectId;
    go(t.state);
  }
}
// A file/folder row whose exact path anchors one or more elements (node_path_index — filetree.py).
// Select the PRIMARY element — the collision set's first (leaves before groups, ordered in filetree.py).
// Its file-mates aren't stacked in the panel anymore; the code viewer tags each on its own source line
// (paintCodeTags), so they stay discoverable there. Selecting highlights this row via syncTreeToNode,
// same as any other selection (the primary's own anchor IS this path).
function selectFromTreeAnchors(allIds) {
  if (allIds.length) selectFromTree(allIds[0]);
}

// A source ref (a node's `file`/`line`, an edge's `where`) -> the tree path it resolves to, or null when
// it isn't a local repo-relative path (an off-repo URL, or no ref at all) — the same test `openSource`
// uses to decide whether a ref is clickable.
function refTreePath(file, line) { return file && localRef(file) ? treeKey(cleanPath(file, line)) : null; }

// --- selection footprint: bold files/dirs + per-dir counts -----------------------
// A selected element (container OR leaf) FILTERS the tree down to just its footprint: its member files
// (a container's `files` is already its whole subtree, recursively) and the directories holding them —
// everything else is hidden. Each kept directory shows a COUNT of the member files inside it (recursive),
// and the header pill shows the total. The tree auto-expands so the whole footprint is visible; the
// current/shown file keeps its `.sel` row highlight. Cleared (full tree restored) for an edge / the System
// node / no selection.
let selMemberFiles = new Set();   // member file paths (treeKey'd) — the files to keep
let selDirCount = new Map();      // footprint dir path -> count of member files under it (recursive)
function selActive() { return selMemberFiles.size > 0; }
function computeSelection(id) {
  selMemberFiles = new Set();
  selDirCount = new Map();
  const n = id && GRAPH.nodes[id];
  if (!n || !(isContainerKind(n.kind) || LEAF_KINDS.has(n.kind))) return;
  // The footprint is exactly the element's file set — the SAME list the code-viewer switcher shows, so a
  // shared file appears under every element that owns it and the tree + switcher always agree.
  for (const f of (n.files || [])) {
    const key = treeKey(f);
    if (!key) continue;
    selMemberFiles.add(key);
    const parts = key.split('/');
    for (let i = 0; i < parts.length - 1; i++) {
      const dir = parts.slice(0, i + 1).join('/');
      selDirCount.set(dir, (selDirCount.get(dir) || 0) + 1);
    }
  }
}
// Apply the current filter to one row (rec = { row, kids, entry }): keep it if it's in the footprint (a
// member file, or a directory that holds member files) — a kept directory carries its recursive count;
// hide the row AND its child subtree otherwise. Idempotent: clears prior state first. No selection -> keep
// everything and drop the badges.
function applySelToRow(rec) {
  const { row, kids, entry } = rec;
  row.classList.remove('filtered-out', 'has-owner');
  if (kids) kids.classList.remove('filtered-out');
  const oldBadge = row.querySelector(':scope > .tselcount'); if (oldBadge) oldBadge.remove();
  // Strip any owner pill left by a prior selection — it may sit in the row's own container pill-box or in a
  // hover-only box we created just for it; drop that created box too so nothing empty lingers.
  row.querySelectorAll('.pill.towner').forEach((p) => p.remove());
  const ownBox = row.querySelector(':scope > .tgroups.towner-box'); if (ownBox) ownBox.remove();
  if (!selActive()) return;
  const key = treeKey(entry.path);
  const keep = entry.dir ? selDirCount.has(key) : selMemberFiles.has(key);
  if (!keep) {
    row.classList.add('filtered-out');
    if (kids) kids.classList.add('filtered-out');  // hide the whole hidden subtree, not just its top row
    return;
  }
  if (entry.dir) {
    const c = selDirCount.get(key);
    const badge = document.createElement('span');
    badge.className = 'tselcount';
    badge.textContent = c;
    badge.title = c + ' file' + (c === 1 ? '' : 's') + ' of the selected element, here';
    row.querySelector('.tname').insertAdjacentElement('afterend', badge);
  } else if (entry.node && entry.node !== treeSelId) {
    // A kept file whose primary owner is a DIFFERENT element than the selection shows that owner's pill —
    // so the reader sees the file is co-located with (or drills into) another component. Applies to both a
    // container selection (files owned by its sub-elements) and a leaf (files it shares with a sibling);
    // the `!== treeSelId` guard drops the common case where the file belongs to the selection itself.
    // The pill goes in a horizontally-scrollable line, exactly like a container's anchor pills: it reuses
    // the row's existing pill-box when there is one, else a hover-only box of its own — so a long filename
    // shrinks/scrolls the box instead of letting a bare pill overflow and overlap the name (or a sibling
    // pill). Hover-only to keep the filtered list clean.
    const pill = elementPill(entry.node);
    if (pill) {
      pill.classList.add('towner');
      row.classList.add('has-owner');
      let box = row.querySelector(':scope > .tgroups');
      if (!box) {
        box = document.createElement('span');
        box.className = 'tgroups towner-box';
        box.addEventListener('scroll', () => updatePillFade(box));
        row.appendChild(box);
      }
      box.appendChild(pill);
      updatePillFade(box);
    }
  }
}
function setSelPills(id) {  // (name kept for its callers) recompute the footprint, reveal it, re-filter every row
  computeSelection(id);
  // Auto-expand the footprint dirs (shallowest first, so each parent is built before its child) so every
  // member file is actually visible under the filter.
  [...selDirCount.keys()].sort((a, b) => a.split('/').length - b.split('/').length).forEach(expandDir);
  for (const k in rowByPath) applySelToRow(rowByPath[k]);
}
// Emphasise every already-built tree pill whose element is the current selection (`treeSelId`); pills
// built later are born emphasised in elementPill.
function highlightTreePills() {
  treeBody.querySelectorAll('.pill[data-id]').forEach((p) => p.classList.toggle('pill-sel', p.dataset.id === treeSelId));
}
// When the selected container's pill sits in a horizontally-scrollable box (a path anchoring many
// containers), scroll that box so the emphasised pill is visible. Horizontal-only — never moves the row
// or the page. Called after the anchor row is built/revealed (syncTreeToNode).
function scrollSelectedPillsIntoView() {
  treeBody.querySelectorAll('.tgroups .pill.pill-sel').forEach((p) => {
    const box = p.closest('.tgroups');
    if (!box || box.scrollWidth <= box.clientWidth) return;  // fits — nothing to scroll
    const b = box.getBoundingClientRect(), r = p.getBoundingClientRect();
    // 16px clears the edge fade (14px) so the selected pill lands fully visible, not under the gradient
    if (r.left < b.left) box.scrollLeft -= (b.left - r.left) + 16;
    else if (r.right > b.right) box.scrollLeft += (r.right - b.right) + 16;
    updatePillFade(box);
  });
}
// Fade hint on an overflowing pill box: a CSS mask fades the edge(s) that still hide pills, hinting "more
// pills — scroll". `scrollable` turns the mask on; `at-start`/`at-end` drop the fade on a fully-scrolled
// side. Recomputed on scroll, on build, and when the pane/window resizes.
function updatePillFade(box) {
  const overflow = box.scrollWidth - box.clientWidth;
  box.classList.toggle('scrollable', overflow > 1);
  box.classList.toggle('at-start', box.scrollLeft <= 1);
  box.classList.toggle('at-end', box.scrollLeft >= overflow - 1);
}
function updateAllPillFades() { treeBody.querySelectorAll('.tgroups').forEach(updatePillFade); }
// The selected element's pill in the browser header — the same pill the code viewer shows beside the path,
// so while browsing (code viewer hidden) the reader still sees what's selected. Cleared for no selection.
function renderTreeHeadPill() {
  const old = treeHead.querySelector('.treeheadpill');
  if (old) old.remove();
  const n = treeSelId && GRAPH.nodes[treeSelId];
  if (!n || !(isContainerKind(n.kind) || LEAF_KINDS.has(n.kind))) return;  // real elements only (not the System node)
  const pill = elementPill(treeSelId);
  if (!pill) return;
  pill.classList.add('treeheadpill');
  if (selMemberFiles.size) {  // the element's total file count (same tally as the per-directory badges)
    const c = document.createElement('span');
    c.className = 'pillcount';
    c.textContent = selMemberFiles.size;
    pill.appendChild(c);
  }
  treeHead.insertBefore(pill, treePinBtn);
}
// One entry point for "the diagram selection changed": remember it (for pill emphasis), paint a selected
// leaf element's footprint bolding, re-emphasise matching pills, and refresh the header pill. `null` clears.
function setTreeSelection(id) {
  treeSelId = (id && GRAPH.nodes[id]) ? id : null;
  setSelPills(id);
  highlightTreePills();
  renderTreeHeadPill();
}

// graph -> tree: highlight the row for `id`'s source path (exact map, else its file/dir path), expanding
// ancestor folders so the row exists and is visible. No path / no row -> just clear the highlight.
function syncTreeToNode(id) {
  const n = GRAPH.nodes[id];
  cvElement = id;  // the shown file's owning element -> the code-viewer header pill
  setTreeSelection(id);  // emphasise this element's pills + paint a leaf element's footprint pills
  // Highlight ONLY the element's main file (its own anchor) — not its whole file set. Keep the 'sel'
  // highlight on a file the reader just clicked if it belongs to this element (an owned file) OR is a file
  // the reader pinned open directly from the browser (an unmapped file under this container); otherwise
  // move it to the anchor row.
  if (!(treeSelPath && (treeSelPath === cvPinned || (n && (n.files || []).indexOf(treeSelPath) !== -1)))) {
    const path = pathByNode[id] || (n ? refTreePath(n.file, n.line) : null);
    highlightTreePath(path);
  }
  if (n) syncCodeView(n.file, n.line, n.files);  // mirror the node's source into the code viewer (FULL mode)
  scrollSelectedPillsIntoView();  // reveal the selected container's pill if its row's pill box overflows
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
  // A row near the END of the tree has no content below it for the viewport to scroll into, so plain
  // block:'center' would leave it stuck low. Pad the bottom with exactly the shortfall so even the last
  // row can still be centered.
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
  SEARCH_FILES = [];  // rebuilt from this tree — feeds the search sidebar's file/folder results
  (function index(e) {
    // Only ANCHOR rows (cov 'self') feed the node->path map: an owned-file row also carries e.node (its
    // owner, for the click) but must NOT claim to be that owner's canonical path, or graph->tree would
    // jump to a random owned file instead of the element's source.
    if (e.node && e.cov === 'self') {
      pathByNode[e.node] = treeKey(e.path);
      anchorsByPath[treeKey(e.path)] = [e.node, ...(e.others || [])];  // every element anchored at this file
    }
    if (e.path) SEARCH_FILES.push({ path: e.path, dir: !!e.dir });  // every file + folder, for search
    for (const c of e.children) index(c);
  })(root);
  const kids = root.children || [];
  treeBody.innerHTML = '';
  if (!kids.length) {
    treeBody.innerHTML = '<div class="tempty">No files found.</div>';
    document.body.classList.add('no-tree');  // hide the browser controls + never default to browsing over the code
    setBrowsing(false);
    return;
  }
  document.body.classList.remove('no-tree');
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
    document.body.classList.add('no-tree');  // no browser to show -> keep the code viewer visible
    setBrowsing(false);
  }
}

// --- code viewer -----------------------------------------------------------------
// A first-pass read-only source view: fetch the file from the server (git @ commit), highlight it with
// highlight.js (lazy-loaded from a CDN, SRI-pinned like the other libs), show a line-number gutter, and
// scroll to / highlight the current line. Deliberately simple — richer navigation is a planned follow-up.
const cvscroll = document.getElementById('cvscroll');  // the scrolling source area (the table lives here)

// A map whose CODE the server cannot read: the folder is not in a git work tree (a `.coyodex/` copied
// somewhere on its own), or the repo it is in does not have the pinned commit. Say it ONCE, up front,
// where the source would go — the per-file 404 ("Not tracked in this commit") arrives only after a
// click and blames the commit for what is usually a missing repo.
function noCodeMessage() {
  return REPO_STATE === 'no-commit'
    ? 'This map is pinned to commit ' + esc((GH_COMMIT || '').slice(0, 10)) + ', which is not in the repo'
      + ' beside it — the code cannot be read at the version the map describes.'
    : 'No code beside this map: its folder is not inside a git repository, so there are no files to'
      + ' read. Open the map that sits in the repo itself to browse its source.';
}
function showNoCodeNotice() {
  cvscroll.innerHTML = '<p class="cvempty">' + noCodeMessage() + '</p>';
}
// Painted HERE, at module scope, as soon as the code pane exists: the bundle has already been
// applied (it arrives under the top-level await above), and nothing else writes this pane until a
// file is opened, so the notice is what a reader sees instead of "select a node" that leads nowhere.
if (REPO_STATE !== 'ok') showNoCodeNotice();
const cvminimap = document.getElementById('cvminimap');  // the overview ruler beside it
const cvpath = document.getElementById('cvpath');
const cvopen = document.getElementById('cvopen');  // ↗ opens the shown file in the external editor / on GitHub
if (cvopen) cvopen.addEventListener('click', () => { if (cvPath) openSource({ file: cvPath, line: cvLine }); });
// The ruler's viewport band tracks the scroll live, and the ruler doubles as a scrollbar: press or drag
// anywhere on it (except a dot, which jumps to its line) scrubs the source, centring the view on the
// pointer. Listeners wired once — updateViewport / scrollCodeToLine are hoisted.
if (cvscroll) cvscroll.addEventListener('scroll', updateViewport);
window.addEventListener('resize', updateViewport);
if (cvminimap) cvminimap.addEventListener('mousedown', (e) => {
  if (e.target.classList.contains('cvmark')) return;  // a dot handles its own click
  const rect = cvminimap.getBoundingClientRect();
  const scrub = (y) => {
    const frac = Math.max(0, Math.min(1, (y - rect.top) / rect.height));
    cvscroll.scrollTop = frac * cvscroll.scrollHeight - cvscroll.clientHeight / 2;  // centre the view on the point
  };
  scrub(e.clientY);
  const move = (ev) => scrub(ev.clientY);
  const up = () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', up); document.body.classList.remove('cv-scrubbing'); };
  window.addEventListener('mousemove', move);
  window.addEventListener('mouseup', up);
  document.body.classList.add('cv-scrubbing');
  e.preventDefault();  // don't start a text selection while scrubbing
});
let cvPath = null, cvTable = null;  // the file currently shown + its rendered table (for same-file line moves)
let cvLine = null;                  // the line to highlight — a module var so a line that arrives while the
                                    // file is still loading (tree click: file-load then node-select) still lands
let cvLineCount = 0;                // total lines in the shown file (positions the overview-ruler marks)
let cvReq = 0;                      // request token — a newer load supersedes an in-flight older one
let cvFiles = [];                   // the selected element's files (source first) — the header's switcher list
let cvElement = null;               // the element that owns the shown file (drives the header's owning-element
                                    // pill). Set by syncTreeToNode; nulled for a file with no owner (an edge's
                                    // anchor, a standalone/glossary open, an unmapped file under no container).
let cvPinned = null;                // a file the reader opened DIRECTLY from the browser that no element owns
                                    // (an unmapped file under a mapped folder): keep it shown + its row lit
                                    // even though the container we then select for context doesn't list it in
                                    // its `files`, so the normal "belongs" guard wouldn't protect it. Set by
                                    // onRowClick, consumed by syncCodeView, cleared at the next click.
let suppressCodeScroll = false;     // one-shot: skip the next markLine re-centering (a tag click on a line
                                    // already in view must not yank the scroll — see paintCodeTags)

// The code-viewer header: the full file path IS the file switcher. When the selected element owns several
// files the path becomes a dropdown trigger (a caret + a custom menu of its files, source first); a
// single-file element shows a plain path. Beside it sits the owning-element pill (name + kind colour,
// dashed for a container). Picking a file loads it + highlights its tree row (no graph re-selection).
function renderCvHeader() {
  closeCvMenu();  // a re-render (e.g. a line move) drops any open menu; it's rebuilt from the fresh state
  const full = (cvPath || '') + (cvLine ? ':' + cvLine : '');
  const multi = SERVED && cvFiles.length > 1;
  cvpath.innerHTML = '';
  const pathEl = document.createElement(multi ? 'button' : 'span');
  pathEl.className = 'cvpathtext' + (multi ? ' cvpathbtn' : '');
  const label = document.createElement('span');
  label.className = 'cvpathlabel';
  label.textContent = full;
  label.title = full;  // the path truncates on a narrow pane — hover shows it in full
  pathEl.appendChild(label);
  if (multi) {
    pathEl.type = 'button';
    pathEl.title = 'Switch file in this element';
    const caret = document.createElement('span');
    caret.className = 'cvcaret';
    caret.textContent = '▾';
    pathEl.appendChild(caret);
    pathEl.addEventListener('click', (ev) => { ev.stopPropagation(); toggleCvMenu(); });
  }
  cvpath.appendChild(pathEl);
  const pill = elementPill(cvElement);           // the element that owns the shown file
  if (pill) { pill.classList.add('cvpill'); cvpath.appendChild(pill); }
  if (cvopen) cvopen.hidden = !(cvPath && localRef(cvPath));  // the ↗ only shows once a local file is open
}
// The custom file switcher menu (replaces the native <select>): a floating list of the element's files,
// current one marked, each shown as filename + muted folder. Anchored under the path trigger inside
// #cvpath (position:relative). Closes on pick, outside click, or Escape.
let cvMenuEl = null;
function closeCvMenu() {
  if (!cvMenuEl) return;
  cvMenuEl.remove();
  cvMenuEl = null;
  document.removeEventListener('mousedown', cvMenuOutside, true);
  document.removeEventListener('keydown', cvMenuKey, true);
}
function cvMenuOutside(ev) { if (cvMenuEl && !cvMenuEl.contains(ev.target) && !cvpath.contains(ev.target)) closeCvMenu(); }
function cvMenuKey(ev) { if (ev.key === 'Escape') closeCvMenu(); }
// Order paths the way the file browser lists them: a depth-first walk where, at each folder level,
// sub-directories (alpha, case-insensitive) come before files (alpha). Sorts the switcher to match the tree.
function treeOrder(a, b) {
  const pa = a.split('/'), pb = b.split('/');
  const n = Math.min(pa.length, pb.length);
  for (let i = 0; i < n; i++) {
    if (pa[i] === pb[i]) continue;
    const aFile = i === pa.length - 1, bFile = i === pb.length - 1;
    if (aFile !== bFile) return aFile ? 1 : -1;  // a directory sorts before a file at the same level
    const x = pa[i].toLowerCase(), y = pb[i].toLowerCase();
    return x < y ? -1 : (x > y ? 1 : 0);
  }
  return pa.length - pb.length;
}
function toggleCvMenu() {
  if (cvMenuEl) { closeCvMenu(); return; }
  const menu = document.createElement('div');
  menu.className = 'cvmenu';
  cvFiles.slice().sort(treeOrder).forEach((f) => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'cvmenu-item' + (f === cvPath ? ' current' : '');
    const name = document.createElement('span');
    name.className = 'cvmenu-name';
    name.textContent = f.split('/').pop();
    item.appendChild(name);
    const dir = f.split('/').slice(0, -1).join('/');
    if (dir) {
      const d = document.createElement('span');
      d.className = 'cvmenu-dir';
      d.textContent = dir;
      item.appendChild(d);
    }
    item.addEventListener('click', () => {
      if (f === cvPath) { closeCvMenu(); return; }   // already showing this file — no history churn
      closeCvMenu();
      suppressTreeScroll = false;
      highlightTreePath(treeKey(f));
      pushContentPoint({ file: f, top: 0 });  // record a point so Back returns to the previous file (at its scroll)
      loadCode(f, null);
    });
    menu.appendChild(item);
  });
  cvpath.appendChild(menu);
  cvMenuEl = menu;
  document.addEventListener('mousedown', cvMenuOutside, true);
  document.addEventListener('keydown', cvMenuKey, true);
  const cur = menu.querySelector('.cvmenu-item.current');
  if (cur) cur.scrollIntoView({ block: 'nearest' });
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
  if (!cvTable) { suppressCodeScroll = false; return; }
  const prev = cvTable.querySelector('tr.cvcur');
  if (prev) prev.classList.remove('cvcur');
  if (line) {
    const row = cvTable.querySelector('tr[data-ln="' + line + '"]');
    // Skip the re-centering when a tag click asked us to (suppressCodeScroll): the line is already on
    // screen — the reader just clicked its pill — so yanking the scroll would be jarring.
    if (row) { row.classList.add('cvcur'); if (!suppressCodeScroll) row.scrollIntoView({ block: 'center' }); }
  }
  suppressCodeScroll = false;  // one-shot: always consumed by the next mark, scrolled or not
}
// The element's type, as one short word for its on-the-line tag — the thing the code itself can't tell
// you (the name is already right there on the line). A dependency shows its Context sub-type (service /
// datastore / …) when it has one, since the generic "dependency" is less informative — same choice
// kindPills makes for the info-pane pill.
function nodeTypeLabel(n) {
  if (n.kind === 'dep') return (n.fields && n.fields.Kind) || 'dependency';
  return n.kind;
}
// file path -> the use-case flow steps anchored there, via each step's OWN `where` (THE location).
// Steps without one (`no_call_site`, or a map from before step anchors) simply don't decorate — an
// arrow's `where` is only an example call site and must never stamp a "use case" pill on a line the
// flow doesn't actually walk. Built once, lazily — FLOWS_NARR is set at boot, well before any file
// is shown.
let stepsByPathCache = null;
function stepsByPath() {
  if (stepsByPathCache) return stepsByPathCache;
  stepsByPathCache = {};
  for (const uc in (FLOWS_NARR || {})) {
    (FLOWS_NARR[uc] || []).forEach((st, i) => {
      if (!st.where) return;
      const wn = whereNode(st.where);
      if (!wn.line || !localRef(wn.file)) return;
      const key = treeKey(cleanPath(wn.file, wn.line));
      (stepsByPathCache[key] ||= []).push({ uc, i, line: wn.line, verb: st.verb, src: st.src, dst: st.dst });
    });
  }
  return stepsByPathCache;
}
// Navigate to use case `uc` and select step `i`. stateKey ignores `sel`, so a plain go() to the same
// use case we're already viewing would no-op — select in place then (mirrors selectFromTree's fallback).
function selectFlowStep(uc, i) {
  const state = { kind: 'usecase', uc: uc, sel: 'flowstep:' + uc + ':' + i };
  const cur = history[hi];
  if (cur && stateKey(cur) === stateKey(state) && mainScene && mainScene.selectors[state.sel]) {
    selClear(mainScene); mainScene.selectors[state.sel]();  // select this one step in place (replace)
  } else {
    go(state);
  }
}
// Every taggable item in the shown file — structural elements anchored here AND use-case steps that pass
// through here — as a uniform list the code tags and the overview ruler both render. `select` runs the
// item's own selection (suppressing the re-center, since the reader clicked a line already on screen).
function codeItemsForPath(path) {
  const key = treeKey(path), items = [];
  for (const id of (anchorsByPath[key] || [])) {
    const n = GRAPH.nodes[id];
    if (!n || !n.line) continue;
    items.push({ line: n.line, kind: 'element', name: n.name, label: nodeTypeLabel(n),
      select: () => { suppressCodeScroll = true; selectFromTree(id); } });
  }
  // One use-case tag per LINE, not per step: a single line (one edge) is often walked by several use
  // cases — four identical "use case" pills would just eat the width. Collapse them: the pill's hover
  // card names them all, a plain click selects a lone use case directly, and a pill covering 2+ opens
  // a small picker (see showUcPick) so every use case on the line stays reachable from the code.
  const byLine = {};
  for (const s of (stepsByPath()[key] || [])) (byLine[s.line] ||= []).push(s);
  for (const ln in byLine) {
    const seen = new Set(), choices = [];
    for (const s of byLine[ln]) {
      if (seen.has(s.uc)) continue;  // several steps of ONE use case on the line -> one entry (its first step)
      seen.add(s.uc);
      choices.push({ name: (GRAPH.nodes[s.uc] && GRAPH.nodes[s.uc].name) || s.uc,
        select: () => { suppressCodeScroll = true; selectFlowStep(s.uc, s.i); } });
    }
    const name = choices.length === 1 ? choices[0].name
      : choices.length + ' use cases: ' + choices.map((c) => c.name).join(', ');
    items.push({ line: +ln, kind: 'usecase', name: name, label: 'use case',
      choices: choices, select: choices[0].select });
  }
  return items;
}
// Tag each item on its own source line: a small pill pinned to the code view's right edge (so it never
// depends on line length), clicking it selects that item. The element pill on the current line (cvLine —
// the selected element's line) is emphasized. Re-run on every table build and line move. Two items sharing
// one line get two pills; an item with no line can't be tagged (it isn't shown in the code at all).
function paintCodeTags() {
  if (!cvTable || !cvPath) return;
  hideUcPick();  // a repaint replaces the pill the picker was anchored to
  cvpop.hidden = true;  // and drops any hover card pinned to an about-to-be-removed pill
  cvTable.querySelectorAll('td.cvtag').forEach((td) => { td.textContent = ''; });  // clear a previous paint
  for (const it of codeItemsForPath(cvPath)) {
    const row = cvTable.querySelector('tr[data-ln="' + it.line + '"]');
    const cell = row && row.querySelector('td.cvtag');
    if (!cell) continue;
    const pill = document.createElement('span');
    pill.className = 'cvtag-pill ' + it.kind + (it.kind === 'element' && it.line === cvLine ? ' cur' : '');
    pill.textContent = it.label;                    // textContent, not innerHTML — labels are plain text
    attachMarkPop(pill, it.name, it.label, it.kind);  // hover card: the item's name (all names on a shared line)
    // A pill covering several use cases opens the picker instead of selecting blindly. stopPropagation
    // keeps the document-level click-away handler from closing the picker it just opened.
    pill.addEventListener('click', (it.choices && it.choices.length > 1)
      ? (ev) => { ev.stopPropagation(); showUcPick(pill, it.choices); }
      : it.select);
    cell.appendChild(pill);
  }
}
// A hover popup on a ruler mark (a dot): the item's NAME next to its type pill — since a dot alone can't
// say what it is. Its own light card (#cvpop, created once) — appears instantly, pinned to the LEFT of the
// dot and vertically centred on it (flips to the right only if there's no room on the left).
const cvpop = document.createElement('div');
cvpop.id = 'cvpop'; cvpop.hidden = true; document.body.appendChild(cvpop);
function showMarkPop(el, name, label, kind) {
  cvpop.innerHTML = '<span class="cvpop-name">' + esc(name) + '</span>'
    + '<span class="cvpop-pill ' + kind + '">' + esc(label) + '</span>';
  cvpop.hidden = false;
  const r = el.getBoundingClientRect(), pw = cvpop.offsetWidth, ph = cvpop.offsetHeight, gap = 8;
  let left = r.left - gap - pw;
  if (left < 6) left = Math.min(r.right + gap, window.innerWidth - pw - 6);  // no room left -> flip right
  const top = Math.max(6, Math.min(r.top + r.height / 2 - ph / 2, window.innerHeight - ph - 6));
  cvpop.style.left = left + 'px';
  cvpop.style.top = top + 'px';
}
function attachMarkPop(el, name, label, kind) {
  el.addEventListener('mouseenter', () => showMarkPop(el, name, label, kind));
  el.addEventListener('mouseleave', () => { cvpop.hidden = true; });
  // Clicking the pill navigates (and repaints the tags), which removes this pill from the DOM — so its
  // mouseleave never fires and the hover card would otherwise linger. Dismiss it explicitly on click.
  el.addEventListener('click', () => { cvpop.hidden = true; });
}
// The picker for a use-case pill covering SEVERAL use cases (they share the line's edge): a small
// floating card listing each one; picking runs the same selection a plain click performs when the pill
// covers only one. A singleton like #cvpop, but interactive. Closed by picking, clicking the pill again,
// clicking away, Escape, or scrolling the code (the anchor pill moves with the code, the card would not).
const cvpick = document.createElement('div');
cvpick.id = 'cvpick'; cvpick.hidden = true; document.body.appendChild(cvpick);
let cvpickAnchor = null;   // the pill the open picker belongs to (null when hidden)
function hideUcPick() { cvpick.hidden = true; cvpickAnchor = null; }
function showUcPick(anchor, choices) {
  if (cvpickAnchor === anchor) { hideUcPick(); return; }  // a second click on the pill toggles it closed
  cvpick.textContent = '';
  for (const c of choices) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = c.name;                       // textContent, not innerHTML — names are plain text
    b.addEventListener('click', () => { hideUcPick(); c.select(); });
    cvpick.appendChild(b);
  }
  cvpick.hidden = false;
  cvpickAnchor = anchor;
  // Right-align under the pill (it sits at the code view's right edge); flip above when there's no room.
  const r = anchor.getBoundingClientRect(), pw = cvpick.offsetWidth, ph = cvpick.offsetHeight, gap = 4;
  const left = Math.max(6, Math.min(r.right - pw, window.innerWidth - pw - 6));
  let top = r.bottom + gap;
  if (top + ph > window.innerHeight - 6) top = Math.max(6, r.top - gap - ph);
  cvpick.style.left = left + 'px';
  cvpick.style.top = top + 'px';
}
document.addEventListener('click', (ev) => { if (!cvpick.hidden && !cvpick.contains(ev.target)) hideUcPick(); });
document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') hideUcPick(); });
if (cvscroll) cvscroll.addEventListener('scroll', hideUcPick);
// The overview ruler: one clickable mark per item, placed at its line's relative depth in the whole file
// (like a diff view's marker gutter). Clicking a mark jumps the source to that line — it does NOT select
// (that's what the pill is for), so scanning the file's shape stays cheap. A viewport band (updated on
// scroll) shows the slice of the file currently on screen, so the ruler doubles as a scrollbar.
function paintMinimap() {
  if (!cvminimap) return;
  cvminimap.textContent = '';
  if (!cvTable || !cvPath || cvLineCount < 1) return;
  const vp = document.createElement('div');  // the viewport band — the part of the file currently on screen
  vp.className = 'cvviewport';
  cvminimap.appendChild(vp);
  for (const it of codeItemsForPath(cvPath)) {
    const mark = document.createElement('button');
    mark.type = 'button';
    mark.className = 'cvmark ' + it.kind;
    mark.style.top = ((it.line - 1) / Math.max(1, cvLineCount - 1) * 100) + '%';
    attachMarkPop(mark, it.name, it.label, it.kind);  // hover card: the item's name + its type pill
    mark.addEventListener('click', () => scrollCodeToLine(it.line));
    cvminimap.appendChild(mark);
  }
  updateViewport();
}
// Size + place the viewport band to match what's visible in the scroller. Hidden when the whole file fits
// (nothing to scroll). Runs on every scroll / resize, so the band tracks the view live.
function updateViewport() {
  const vp = cvminimap && cvminimap.querySelector('.cvviewport');
  if (!vp || !cvscroll) return;
  const sh = cvscroll.scrollHeight, ch = cvscroll.clientHeight;
  if (sh <= ch + 1) { vp.style.display = 'none'; return; }
  vp.style.display = '';
  vp.style.top = (cvscroll.scrollTop / sh * 100) + '%';
  vp.style.height = (ch / sh * 100) + '%';
}
function scrollCodeToLine(line) {
  if (!cvTable) return;
  const row = cvTable.querySelector('tr[data-ln="' + line + '"]');
  if (!row) return;
  row.scrollIntoView({ block: 'center' });
  row.classList.add('cvflash');
  setTimeout(() => row.classList.remove('cvflash'), 700);  // brief flash so the eye catches the landing
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
    cvLineCount = lineHtml.length;  // total lines — positions the overview-ruler marks
    const rows = lineHtml.map((h, i) =>
      '<tr data-ln="' + (i + 1) + '"><td class="ln">' + (i + 1) + '</td><td class="code hljs">' + (h || '&nbsp;')
      + '</td><td class="cvtag"></td></tr>').join('');
    // A few empty trailing rows past the last line: they carry no data-ln (so nothing targets them), just
    // continuing the gutter + pill columns blank so the end reads as "nothing more here", not a hard cut.
    const pad = '<tr class="cvpad"><td class="ln"></td><td class="code hljs">&nbsp;</td><td class="cvtag"></td></tr>'.repeat(3);
    cvscroll.innerHTML = '<table class="cvcode"><tbody>' + rows + pad + '</tbody></table>';
    cvTable = cvscroll.querySelector('table.cvcode');
    markLine(cvLine);  // the latest requested line (may have arrived after the fetch started)
    paintCodeTags();   // tag every element / use-case step anchored in this file on its own line
    paintMinimap();    // and place its marks on the overview ruler
    sbOnFileChanged(); // if the sidebar is showing a "@" outline, re-list it for the newly shown file
    applyPendingScroll(path);  // a history restore asked to reopen this file at a saved scroll offset
  });
}
// --- code-view diff mode --------------------------------------------------------
// When a live diff is armed, opening a changed file shows its inline diff (from api/srcdiff) instead
// of the plain blob. cvDiffMode tracks which mode the currently shown file is in, so a same-file call
// re-renders when the mode should flip (diff armed/cleared).
let cvDiffMode = false;
let cvDiffKey = null;   // the range (base+target) the current inline diff was rendered for
// A file is shown as a diff when a live diff is armed and it changed in that range. The changed-path
// set is DIFF_FILE_STATUS (built once per (un)load by recomputeDiffPaths) — no per-call rebuild.
function wantDiffFor(path) { return !!LIVE_DIFF && DIFF_FILE_STATUS[path] != null; }
function diffKeyFor(asDiff) { return asDiff && LIVE_DIFF ? (LIVE_DIFF.base + '\x00' + LIVE_DIFF.target) : null; }
function diffRangeQS() {  // the active range as query params for api/srcdiff (mirrors the loaded diff)
  if (!LIVE_DIFF) return '';
  return '&base=' + encodeURIComponent(LIVE_DIFF.base || '') + '&target=' + encodeURIComponent(LIVE_DIFF.target || '');
}
// --- file-browser diff overlay (badges + "changed only" filter) ------------------
// Rebuilt whenever a live diff is (un)loaded: which files changed (path -> A/M/D) and which folders
// contain a change (so an ancestor dir stays visible under the filter).
let DIFF_FILE_STATUS = {};
let DIFF_ANCESTOR_DIRS = new Set();
let diffOnly = false;   // "changed files only" filter state
function recomputeDiffPaths() {
  DIFF_FILE_STATUS = {};
  DIFF_ANCESTOR_DIRS = new Set();
  if (!LIVE_DIFF || !Array.isArray(LIVE_DIFF.changes)) return;
  for (const c of LIVE_DIFF.changes) {
    for (const p of [c.path, c.oldPath]) {   // badge both sides so a rename lights up whichever exists at the pin
      if (!p) continue;
      DIFF_FILE_STATUS[p] = c.status;
      for (let i = p.lastIndexOf('/'); i > 0; i = p.lastIndexOf('/', i - 1)) DIFF_ANCESTOR_DIRS.add(p.slice(0, i));
    }
  }
}
const _DIFF_LABEL = { A: 'added', M: 'modified', D: 'deleted', R: 'renamed' };
function badgeDiffRow(row, entry) {   // add/remove one row's change dot; called at build + on (un)load
  row.classList.remove('diff-row', 'diff-A', 'diff-M', 'diff-D', 'diff-R', 'diff-anc');
  const old = row.querySelector(':scope > .tdiffdot'); if (old) old.remove();
  if (!LIVE_DIFF) return;
  const st = entry.dir ? null : DIFF_FILE_STATUS[entry.path];
  if (st) {
    row.classList.add('diff-row', 'diff-' + st);
    const dot = document.createElement('span');
    dot.className = 'tdiffdot diff-' + st;
    dot.title = _DIFF_LABEL[st] || 'changed';
    row.querySelector('.tname').insertAdjacentElement('afterend', dot);
  } else if (entry.dir && DIFF_ANCESTOR_DIRS.has(treeKey(entry.path))) {
    row.classList.add('diff-anc');
  }
}
function applyDiffBadges() { for (const k in rowByPath) badgeDiffRow(rowByPath[k].row, rowByPath[k].entry); }
function diffFilterActive() { return diffOnly && !!LIVE_DIFF; }
function applyDiffFilterToRow(rec) {   // hide a row (and its subtree) unless it is/holds a change
  const { row, kids, entry } = rec;
  row.classList.remove('diff-hidden');
  if (kids) kids.classList.remove('diff-hidden');
  if (!diffFilterActive()) return;
  const keep = entry.dir ? DIFF_ANCESTOR_DIRS.has(treeKey(entry.path)) : (DIFF_FILE_STATUS[entry.path] != null);
  if (!keep) { row.classList.add('diff-hidden'); if (kids) kids.classList.add('diff-hidden'); }
}
function applyDiffFilterAll() {
  if (diffFilterActive()) {   // expand every changed folder (shallowest first) so its files are reachable
    [...DIFF_ANCESTOR_DIRS].sort((a, b) => a.split('/').length - b.split('/').length).forEach(expandDir);
  }
  for (const k in rowByPath) applyDiffFilterToRow(rowByPath[k]);
}
// Reflect the current live diff into the file browser: badge rows, (re)apply the filter, show/hide the
// "Changed only" control. Called from loadImpact (impact armed) and clearLiveDiff (dropped).
function syncTreeDiff() {
  recomputeDiffPaths();
  const btn = document.getElementById('treediffonly');
  if (!LIVE_DIFF) { diffOnly = false; if (btn) { btn.hidden = true; btn.classList.remove('on'); } }
  else if (btn) btn.hidden = false;
  applyDiffBadges();
  applyDiffFilterAll();
}
// Render one file's inline diff (server rows) into the code table. No hljs (per-line highlight loses
// cross-line context); +/- rows are coloured, `@@` hunks separate. Reuses the .cvcode table shell.
function renderCodeDiff(data, token) {
  if (token !== cvReq) return;
  // Any exit that renders no table must also drop a pending scroll for this file, so a failed restore
  // can't leave the offset armed to fire on some later successful load of the same path.
  const noTable = (msg) => { cvscroll.innerHTML = '<p class="cvempty">' + msg + '</p>'; cvTable = null; clearPendingScroll(cvPath); };
  if (data && data.binary) { noTable('Binary file — no text diff.'); return; }
  if (data && data.tooLarge) { noTable('Diff too large to show.'); return; }
  const rows = data && Array.isArray(data.rows) ? data.rows : [];
  if (!rows.length) { noTable('No changes in this file for the selected range.'); return; }
  const sign = { add: '+', del: '-', ctx: ' ' };
  const body = rows.map((r) => {
    if (r.op === 'hunk') return '<tr class="cvhunk"><td class="ln"></td><td class="code">' + esc(r.text) + '</td><td class="cvtag"></td></tr>';
    const ln = r.op === 'del' ? r.oldLn : r.newLn;
    return '<tr class="cv' + r.op + '"' + (r.newLn ? ' data-ln="' + r.newLn + '"' : '') + '>'
      + '<td class="ln">' + (ln == null ? '' : ln) + '</td>'
      + '<td class="code"><span class="cvsign">' + sign[r.op] + '</span>' + (esc(r.text) || '&nbsp;') + '</td>'
      + '<td class="cvtag"></td></tr>';
  }).join('');
  cvscroll.innerHTML = '<table class="cvcode cvdiff"><tbody>' + body + '</tbody></table>';
  cvTable = cvscroll.querySelector('table.cvcode');
  cvLineCount = rows.length;
  cvminimap.textContent = '';   // no overview ruler in diff mode
  applyPendingScroll(cvPath);   // honor a history restore's saved scroll (keyed to the REQUESTED path,
  //                               not the server's data.path — they differ for a renamed file in diff mode)
}
// Re-run the search when a new file finishes rendering, but only while the sidebar is showing a "@"
// file-scoped outline — so the outline follows whatever file the code viewer now shows.
function sbOnFileChanged() {
  if (!searchbar.hidden && sbInput.value.trim()[0] === '@') sbRun();
}
// Load `path` (repo-relative) into the code viewer, scrolled to `line`. Same file + new line just moves
// the highlight (no refetch). Only meaningful in FULL mode; a no-op otherwise.
async function loadCode(path, line) {
  if (!SERVED || !path) return;
  // A real file is being shown -> leave browsing so the code viewer is visible. For a FOLDER element this
  // runs first (loading its first file) and updateFolderPeek re-opens browsing right after; for a leaf,
  // an edge, or a Happy-Path step it stays off, so their source isn't hidden behind the browser.
  setBrowsing(false);
  cvLine = line || null;
  const asDiff = wantDiffFor(path);
  const diffKey = diffKeyFor(asDiff);
  // same file AND same mode AND same range -> just move the line + refresh header (no refetch). A mode
  // flip (diff armed/cleared) OR a range change (a new diff armed) falls through to reload.
  if (path === cvPath && asDiff === cvDiffMode && diffKey === cvDiffKey) { renderCvHeader(); markLine(cvLine); paintCodeTags(); return; }
  const token = ++cvReq;
  cvPath = path; cvTable = null; cvminimap.textContent = '';  // clear the old file's ruler while the new one loads
  cvDiffMode = asDiff; cvDiffKey = diffKey;
  renderCvHeader();  // set the header (dropdown marks the new file) AFTER cvPath is updated
  cvscroll.innerHTML = '<p class="cvempty">Loading…</p>';
  const url = asDiff
    ? (API_BASE + (LIVE_DIFF && LIVE_DIFF.impact ? 'impactsrcdiff' : 'srcdiff')
       + '?path=' + encodeURIComponent(path) + diffRangeQS())
    : (API_BASE + 'src?path=' + encodeURIComponent(path));
  let r = null;
  try {
    r = await fetch(url, { cache: 'no-store' });
    if (token !== cvReq) return;
    if (!r.ok) {
      // A 404 with a healthy repo means this ONE file is not in the commit; with a broken one it means
      // the map has no readable code at all, which is a different sentence (see noCodeMessage).
      cvscroll.innerHTML = r.status !== 404 ? '<p class="cverr">Could not load this file.</p>'
        : (REPO_STATE !== 'ok' ? '<p class="cvempty">' + noCodeMessage() + '</p>'
                               : '<p class="cverr">Not tracked in this commit.</p>');
      cvPath = null; cvPinned = null; clearPendingScroll(path); return;  // nothing shown -> drop any pin + pending scroll
    }
  } catch (_) {
    if (token === cvReq) { cvscroll.innerHTML = '<p class="cverr">Could not load this file.</p>'; cvPath = null; cvPinned = null; clearPendingScroll(path); }
    return;
  }
  if (asDiff) {
    let data = null;
    try { data = await r.json(); } catch (_) { data = null; }
    if (token !== cvReq) return;
    renderCodeDiff(data, token);
    return;
  }
  let text = null;
  try { text = await r.text(); } catch (_) { text = null; }
  if (token !== cvReq || text === null) return;
  renderCode(path, text, token);
}
// Mirror a selection's source ref into the code viewer — from a node/edge with a local file anchor.
// `files` (the element's whole file list, source first) drives the header switcher. Skips directory
// anchors (a subsystem's folder) and off-repo URLs — but if the element still has member/owned files,
// the first is opened so the switcher has something to show.
function syncCodeView(file, line, files) {
  if (Array.isArray(files)) cvFiles = files;
  const anchor = (file && localRef(file) && !isDirRef(file, line)) ? cleanPath(file, line) : null;
  // Keep a file the reader opened DIRECTLY from the browser (cvPinned) even though this element (its
  // container) doesn't list it in `files` — an unmapped-file click must not override to the container's
  // own source. The file belongs to no element, so its switcher lists only itself: drop the container's
  // `files` the line above just copied in. Consume the pin so a later selection updates normally.
  if (cvPinned && cvPath === cvPinned && anchor !== cvPath) { cvFiles = []; cvPinned = null; renderCvHeader(); return; }
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
// pane). Not tied to a graph selection, so it just moves the tree highlight to this file's row.
function openInCodeViewer(file, line) {
  if (!file) return;
  if (SERVED && localRef(file)) {
    cvElement = null;  // a standalone / glossary open isn't tied to one element -> no header pill
    highlightTreePath(refTreePath(file, line));  // highlights the file's row (or its folder, for a dir home)
    syncCodeView(file, line, []);                // shows the file; a no-op for a directory ref
    return;
  }
  openSource({ file: file, line: line });        // degraded / off-repo: the external editor is the only option
}

// --- startup --------------------------------------------------------------------
stage.addEventListener('mousedown', (e) => { downX = e.clientX; downY = e.clientY; }, true);
document.addEventListener('keydown', (e) => {
  // While typing in a field, arrows (bare or with ⌘/⌥) are the native text-cursor moves — ⌘←/→ line
  // start/end, ⌥←/→ by word — so we never hijack them for history/flow navigation.
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || '') || (e.target && e.target.isContentEditable);
  // ⌘/⌥ + ←/→ navigate history (preventDefault so ⌘+arrows don't trigger the browser's back/forward)
  if (!typing && (e.metaKey || e.altKey) && e.key === 'ArrowLeft') { e.preventDefault(); back(); return; }
  if (!typing && (e.metaKey || e.altKey) && e.key === 'ArrowRight') { e.preventDefault(); fwd(); return; }
  // Bare ←/→ walk the use-case flow step by step (only on a flow view, and not while typing in a field).
  if (flowPlay && !typing && !e.metaKey && !e.altKey && !e.ctrlKey) {
    if (e.key === 'ArrowLeft') { e.preventDefault(); flowStepBy(-1); return; }
    if (e.key === 'ArrowRight') { e.preventDefault(); flowStepBy(1); return; }
  }
  if (e.key === 'Escape' && mainScene) resetScene(mainScene);
});
// While ⌥ (Option / Alt) is held, flag the body so drillable subsystems/arrows show the drill-in cursor
// (see .drill in the CSS) and the hover tip previews the drill/open action. (⌘/⌃ is now the multi-select
// modifier — see isMultiSelectClick — so the drill affordance moved to ⌥.) Clear on key-up and on blur so
// a released key never sticks.
const setDrillMod = (on) => { document.body.classList.toggle('altmod', on); renderHoverTip(); };
document.addEventListener('keydown', (e) => { if (e.key === 'Alt') setDrillMod(true); });
document.addEventListener('keyup', (e) => { if (e.key === 'Alt') setDrillMod(false); });
window.addEventListener('blur', () => setDrillMod(false));
window.addEventListener('resize', refitStage);  // keep the diagram fitted when the window itself resizes
window.addEventListener('resize', updateAllPillFades);  // and re-evaluate the pill-box edge fades

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
const LS = { editor: 'coyodex.editor', custom: 'coyodex.customUri', root: 'coyodex.srcRoot', ok: 'coyodex.rootOk', repo: 'coyodex.ghRepo', coach: 'coyodex.coachSeen', dimSeen: 'coyodex.dimSeen', legend: 'coyodex.legend', leftW: 'coyodex.leftW', panelH: 'coyodex.panelH', treeW: 'coyodex.treeW', treePinned: 'coyodex.treePinned',
  searchOpen: 'coyodex.searchOpen', searchW: 'coyodex.searchW' };
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

// --- navigation guide -----------------------------------------------------------
// An overlay teaching the map's gestures. It auto-shows once on the first visit (remembered in
// localStorage), and the header "?" button reopens it any time. Esc / backdrop / "Got it" dismiss it.
const coach = document.getElementById('coach');
const dismissCoach = () => { coach.hidden = true; lsSet(LS.coach, '1'); };
document.getElementById('coachok').addEventListener('click', dismissCoach);
document.getElementById('helpbtn').addEventListener('click', () => { coach.hidden = false; });
legendbtn.addEventListener('click', () => setLegendOpen(!legendOpen()));
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
document.addEventListener('mousemove', (e) => { if (resizing) { leftcol.style.width = clampLeftW(e.clientX - leftcol.getBoundingClientRect().left) + 'px'; resizeStagePreserve(); } });
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
// Restore the persisted pinned state, then wire the two controls. The code viewer's Files button toggles
// browsing (the browser filling the code slot); the browser's pin button pins it to its own pane, or
// unpins it away. Both re-fit the diagram since the stage width changes when a pane appears/disappears.
treePinned = lsGet(LS.treePinned) === '1';
applyTreeState();
if (cvFilesBtn) cvFilesBtn.addEventListener('click', () => { if (!treePinned) { setBrowsing(!treeBrowsing); } });
if (treeCodeBtn) treeCodeBtn.addEventListener('click', () => { if (!treePinned) { setBrowsing(false); } });
if (treePinBtn) treePinBtn.addEventListener('click', () => { setPinned(!treePinned); refitStage(); });
let treeResizing = false;
treeResizer.addEventListener('mousedown', (e) => { e.preventDefault(); treeResizing = true; document.body.classList.add('resizing'); });
document.addEventListener('mousemove', (e) => { if (treeResizing) { tree.style.width = clampTreeW(e.clientX - tree.getBoundingClientRect().left) + 'px'; resizeStagePreserve(); updateAllPillFades(); } });
document.addEventListener('mouseup', () => {
  if (!treeResizing) return;
  treeResizing = false; document.body.classList.remove('resizing');
  lsSet(LS.treeW, String(parseInt(tree.style.width, 10) || ''));
});
// --- search sidebar: incremental "jump to anything" ------------------------------
// One in-memory index over the whole map — element names, entity fields, glossary terms, and (in FULL
// mode) every file + folder — fuzzy-matched incrementally as you type. A hit reuses the viewer's own
// navigation: an element selects in its home view, a file opens in the code viewer, a folder opens in
// the browser, a term flashes on the Glossary. Collapsed by default; the header magnifier, "/" or ⌘K
// toggles it (open/closed state persisted). No server round-trips — the graph is already in memory and
// SEARCH_FILES is filled from the loaded tree.
let SEARCH_STATIC = null;     // elements + fields + glossary (by NAME) — built once (the graph is fixed at boot)
let SEARCH_PROSE = null;      // description bodies (purpose / meaning / …) for full-text — built once
let SEARCH_FILES = [];        // {path,dir} for every tree entry — (re)filled by renderFileTree
let SEARCH_SYMBOLS = null;    // code symbols (class/fn) as search rows — null = not fetched, [] = fetched
let SYMBOLS_BY_FILE = null;   // treeKey(file) -> [{name,line,kind}] — for the code-viewer outline (Phase 2b)
let symbolsPending = null;    // in-flight fetch guard, so /api/symbols is requested at most once
const searchbar = document.getElementById('searchbar');
const searchBtn = document.getElementById('searchbtn');
const sbInput = document.getElementById('sbinput');
const sbClose = document.getElementById('sbclose');
const sbResults = document.getElementById('sbresults');
const sbMeta = document.getElementById('sbmeta');

const SB_KIND_LABEL = { usecase: 'use case', subsystem: 'subsystem', component: 'component',
                        subdomain: 'subdomain', entity: 'entity', process: 'process',
                        block: 'decision area', rule: 'business rule' };
const sbElemLabel = (n) => (n.kind === 'dep' ? ((n.fields && n.fields.Kind) || 'dependency') : (SB_KIND_LABEL[n.kind] || n.kind));
// A per-kind nudge so a same-quality name match on a behaviour/structure element outranks a raw path hit.
const SB_TYPE_BONUS = { usecase: 45, subsystem: 40, component: 35, entity: 35, subdomain: 30, dep: 30,
                        process: 28, gloss: 25, sys: 12, field: 10, file: 5, dir: -5, symbol: -2 };

// The fixed half of the index: every named node, each entity's fields, every glossary term. Built once.
function sbBuildStatic() {
  const items = [];
  const nodes = GRAPH.nodes || {};
  for (const id in nodes) {
    const n = nodes[id];
    if (!n || !n.name) continue;
    const parent = n.parent && nodes[n.parent] ? nodes[n.parent].name : '';
    items.push({ text: n.name, sub: parent, cls: n.kind, badge: sbElemLabel(n),
      run: ((nid) => () => selectFromTree(nid))(id) });
    for (const a of (n.attrs || [])) {
      if (!a || !a.name) continue;
      items.push({ text: a.name, sub: n.name, cls: 'field', badge: 'field',
        run: ((nid) => () => selectFromTree(nid))(id) });
    }
  }
  for (const g of (GRAPH.glossary || [])) {
    if (!g || !g.term) continue;
    items.push({ text: g.term, sub: (g.meaning || '').replace(/\s+/g, ' ').slice(0, 90),
      cls: 'gloss', badge: 'term', run: ((t, s) => () => sbGotoGlossary(t, s))(g.term, g.source) });
  }
  // System-tab reference rows. An entry point navigates to its owning component (a real node); every
  // other reference row jumps to the System tab and flashes the matching row (sbGotoSystem).
  const sysRow = (text, sub, badge) => ({ text, sub, cls: 'sys', badge,
    run: ((t) => () => sbGotoSystem(t))(text) });
  for (const e of (GRAPH.entry_points || [])) {
    if (!e || !e.trigger) continue;
    const cid = e.component;
    // A hit navigates to the owning component AND selects this exact entry point in its pane; an entry
    // point with no component falls back to flashing the System-tab row.
    items.push({ text: e.trigger, sub: (e.kind || 'entry point'), cls: 'sys', badge: 'entry point',
      run: (cid && (GRAPH.nodes || {})[cid]) ? ((c, i) => () => selectEntryPoint(c, i))(cid, e.index || 0)
                                             : ((t) => () => sbGotoSystem(t))(e.trigger) });
  }
  for (const c of (GRAPH.config || [])) { if (c && c.key) items.push(sysRow(c.key, 'config', 'config')); }
  for (const s of (GRAPH.security || [])) { if (s && s.surface) items.push(sysRow(s.surface, 'security surface', 'security')); }
  // Every deployment unit is now a real NODE, so none needs a System-tab fallback row (the tab no
  // longer tables `deployment[]`, so such a row would land nowhere): a unit that hosts code, or an
  // untraced one, is its own `process` node; an INFRASTRUCTURE unit is the dependency node standing in
  // for it, carrying its facts (annotate_unit_dep_facts). That dep is indexed under the DEP's name, so
  // index the unit name too whenever the two differ — else searching `mongo` would miss `MongoDB`.
  for (const id in (GRAPH.nodes || {})) {
    const n = GRAPH.nodes[id];
    if (n && n.kind === 'dep' && n.unit && n.unit !== n.name) {
      items.push({ text: n.unit, sub: n.name, cls: 'dep', badge: 'deployment unit',
        run: ((nid) => () => selectFromTree(nid))(id) });
    }
  }
  for (const o of (GRAPH.observability || [])) { if (o && o.signal) items.push(sysRow(o.signal, 'observability', 'signal')); }
  for (const r of (GRAPH.run_commands || [])) { if (r && r.action) items.push(sysRow(r.action, 'run command', 'run')); }
  for (const t of (GRAPH.non_entity_types || [])) { if (t && t.name) items.push(sysRow(t.name, 'not modelled', 'type')); }
  return items;
}
// The full-text (description) index: the PROSE fields — a purpose, a "used for", a trigger→outcome, an
// entity meaning, a glossary meaning — as searchable bodies. Structural fields (name, kind, parent,
// entry-point path, …) are excluded: they just echo the name/paths the name index already covers. A hit
// renders as "[field] ElementName — …snippet…" and navigates to the element (or glossary term).
const SB_PROSE_SKIP = new Set(['Subsystem', 'Component', 'Entry point', 'Name', 'Kind', 'Type',
                               'Parent', 'Subdomain', 'Actor', 'Use case']);
function sbBuildProse() {
  const items = [];
  const nodes = GRAPH.nodes || {};
  for (const id in nodes) {
    const n = nodes[id];
    if (!n || !n.name) continue;
    for (const key in (n.fields || {})) {
      const val = n.fields[key];
      if (SB_PROSE_SKIP.has(key) || typeof val !== 'string' || val.trim().length < 4) continue;
      items.push({ text: n.name, body: val, prose: true, cls: 'prose', badge: key.toLowerCase(),
        run: ((nid) => () => selectFromTree(nid))(id) });
    }
  }
  for (const g of (GRAPH.glossary || [])) {
    if (!g || !g.term || !g.meaning) continue;
    items.push({ text: g.term, body: g.meaning, prose: true, cls: 'prose', badge: 'meaning',
      run: ((t, s) => () => sbGotoGlossary(t, s))(g.term, g.source) });
  }
  // Full-text over the System tab's descriptive cells (config purpose, security risk, unmodelled-type why).
  const sysProse = (text, body, badge) => { if (text && body) items.push({ text, body, prose: true,
    cls: 'prose', badge, run: ((t) => () => sbGotoSystem(t))(text) }); };
  for (const c of (GRAPH.config || [])) { if (c) sysProse(c.key, c.purpose, 'config'); }
  for (const s of (GRAPH.security || [])) { if (s) sysProse(s.surface, s.risk, 'risk'); }
  for (const t of (GRAPH.non_entity_types || [])) { if (t) sysProse(t.name, t.why, 'type'); }
  return items;
}
function sbEnsureIndex() {
  if (!SEARCH_STATIC) SEARCH_STATIC = sbBuildStatic();
  if (!SEARCH_PROSE) SEARCH_PROSE = sbBuildProse();
}
// A one-line excerpt of a prose body centred on the match, matched chars in <mark>, elided with "…".
function sbSnippet(body, pos) {
  if (!pos.length) return esc(body.slice(0, 90));
  const first = pos[0], last = pos[pos.length - 1];
  const start = Math.max(0, first - 24), end = Math.min(body.length, Math.max(last + 40, start + 80));
  const set = new Set(pos);
  let out = start > 0 ? '…' : '';
  for (let i = start; i < end; i++) out += set.has(i) ? '<mark>' + esc(body[i]) + '</mark>' : esc(body[i]);
  return out + (end < body.length ? '…' : '');
}

// Code symbols (real class/function definitions) from the build-time pre-index, fetched lazily from the
// server the first time search is opened. They round out the index beyond the map's curated elements —
// so a class the map doesn't call out (e.g. a UI badge component) is still findable. One row per SITE:
// a name that lives at several sites gets one row per site, each labelled with its own file:line and
// opening exactly that location (no collapsed "N places" row that could only reach the first). A symbol
// whose name is already a map element is dropped (the element row represents it). By-file index kept for
// the code outline (Phase 2b). No server -> no fetch; missing pre-index -> an empty, harmless result.
function sbEnsureSymbols() {
  if (SEARCH_SYMBOLS !== null || symbolsPending || !API_BASE) return;
  symbolsPending = fetch(API_BASE + 'symbols', { cache: 'no-store' })
    .then((r) => (r.ok ? r.json() : { symbols: [] }))
    .then((j) => { sbBuildSymbols(j.symbols || []); if (!searchbar.hidden && sbInput.value.trim()) sbRun(); })
    .catch(() => { SEARCH_SYMBOLS = []; })
    .finally(() => { symbolsPending = null; });
}
function sbBuildSymbols(list) {
  const elemNames = new Set();
  const nodes = GRAPH.nodes || {};
  for (const id in nodes) { if (nodes[id] && nodes[id].name) elemNames.add(nodes[id].name.toLowerCase()); }
  const byFile = {};            // treeKey(file) -> [{name,line,kind}]
  const items = [];
  for (const s of list) {
    if (!s || !s.name || !s.file) continue;
    const key = treeKey(s.file);
    (byFile[key] || (byFile[key] = [])).push({ name: s.name, line: s.line, kind: s.kind });
    if (elemNames.has(s.name.toLowerCase())) continue;   // the map element already represents this name
    const isClass = s.kind === 'class';
    const sub = s.file.split('/').pop() + (s.line ? ':' + s.line : '');
    items.push({ text: s.name, sub, cls: 'symbol', badge: isClass ? 'class' : 'function',
      bonus: isClass ? 8 : -10, run: ((f, l) => () => openInCodeViewer(f, l))(s.file, s.line) });
  }
  SEARCH_SYMBOLS = items;
  SYMBOLS_BY_FILE = byFile;
}
// The file/folder half, rebuilt each search from SEARCH_FILES so it tracks whatever tree is loaded.
function sbFileItems() {
  return SEARCH_FILES.map((f) => ({ text: f.path, sub: '', cls: f.dir ? 'dir' : 'file',
    badge: f.dir ? 'folder' : 'file',
    run: f.dir ? ((p) => () => sbGotoDir(p))(f.path) : ((p) => () => openInCodeViewer(p, null))(f.path) }));
}

const sbBoundary = (s, i) => { if (i === 0) return true; const c = s.charCodeAt(i - 1); return c === 47 || c === 95 || c === 45 || c === 32 || c === 46 || c === 58; };  // / _ - space . :
// Score `q` (already lowercased) against `s`. Higher = better; null = no match. A contiguous substring is
// the strong case (prefix / word-boundary bonuses); otherwise a subsequence match, rewarding runs and
// boundary landings and penalising gaps. Returns the matched positions too, for highlighting.
function sbScore(q, s, substringOnly) {
  const sl = s.toLowerCase();
  const idx = sl.indexOf(q);
  if (idx >= 0) {
    const pos = []; for (let i = 0; i < q.length; i++) pos.push(idx + i);
    let sc = 1000 - idx - Math.max(0, s.length - q.length) * 0.4;
    if (idx === 0) sc += 600; else if (sbBoundary(sl, idx)) sc += 300;
    return { score: sc, pos };
  }
  // Prose (full-text) matches the query as a literal phrase only — a fuzzy subsequence over a long
  // description would match almost anything and scatter the highlight. Identifiers/names keep the
  // subsequence fallback below (good for "IUAS" -> InMemoryUserAccountStore).
  if (substringOnly) return null;
  let si = 0, run = 0, sc = 0; const pos = [];
  for (let i = 0; i < q.length; i++) {
    let found = -1;
    for (let j = si; j < sl.length; j++) { if (sl[j] === q[i]) { found = j; break; } }
    if (found < 0) return null;
    pos.push(found);
    let add = 12;
    if (sbBoundary(sl, found)) add += 18;
    if (found === si) { run += 1; add += run * 6; } else { run = 0; add -= Math.min(found - si, 8); }
    sc += add; si = found + 1;
  }
  return { score: sc - s.length * 0.2, pos };
}

// The outline of the file currently open in the code viewer: its map items (elements / use-case steps
// anchored here) plus its real code symbols, as search rows, in source-line order. Feeds the "@" scope.
// null = no file open. This is the "go to symbol in this file" list.
function sbFileScopedItems() {
  const path = cvPath;
  if (!path) return null;
  const items = [];
  for (const it of codeItemsForPath(path)) {
    // A line walked by several use cases is ONE codeItem (its name lists them all, select opens the
    // first) so the code-tag pill can collapse them behind a picker. Search has no picker, so expand
    // it back into one row per use case — each opens exactly its own, none left unreachable.
    if (it.choices && it.choices.length > 1) {
      for (const c of it.choices) items.push({ text: c.name, sub: 'line ' + it.line, line: it.line,
        cls: 'usecase', badge: it.label, run: c.select });
      continue;
    }
    items.push({ text: it.name, sub: 'line ' + it.line, line: it.line,
      cls: it.kind === 'usecase' ? 'usecase' : 'component', badge: it.label, run: it.select });
  }
  for (const s of ((SYMBOLS_BY_FILE && SYMBOLS_BY_FILE[treeKey(path)]) || [])) {
    items.push({ text: s.name, sub: 'line ' + s.line, line: s.line,
      cls: 'symbol', badge: s.kind === 'class' ? 'class' : 'function',
      run: ((l) => () => scrollCodeToLine(l))(s.line) });
  }
  items.sort((a, b) => (a.line || 0) - (b.line || 0));
  return items;
}
function sbShowMessage(msg) {
  sbRows = []; sbRowEls = []; sbActive = -1; sbMeta.textContent = '';
  sbResults.innerHTML = '<div class="sb-empty">' + msg + '</div>';
}

let sbRows = [];    // current results in display order: [{ it, score, pos, group? }]
let sbRowEls = [];  // the .sb-row elements, parallel to sbRows (section headers excluded) — active tracking
let sbActive = -1;
function sbRun() {
  const raw = sbInput.value.trim();
  sbEnsureIndex();
  // "@" scopes to the file open in the code viewer: "@" alone lists its symbols in source order (the
  // outline); "@foo" fuzzy-matches within them. This is symbol navigation for the current file.
  if (raw[0] === '@') {
    const scoped = sbFileScopedItems();
    if (scoped === null) { sbShowMessage('Open a file in the code viewer, then use <kbd>@</kbd> to jump to a symbol in it.'); return; }
    if (!scoped.length) { sbShowMessage('No symbols found in this file.'); return; }
    const q = raw.slice(1).trim().toLowerCase();
    const scored = [];
    for (const it of scoped) {
      if (!q) { scored.push({ it, score: 0, pos: [] }); continue; }  // no query -> keep source-line order
      const m = sbScore(q, it.text);
      if (m) scored.push({ it, score: m.score, pos: m.pos });
    }
    if (q) scored.sort((a, b) => b.score - a.score || a.it.text.length - b.it.text.length);
    sbRender(scored, raw, scored.length);
    return;
  }
  if (!raw) { sbRender([], '', 0); return; }
  const q = raw.toLowerCase();
  // Names first: elements, entity fields, glossary terms, files/folders, and code symbols, ranked.
  const nameItems = SEARCH_STATIC.concat(sbFileItems(), SEARCH_SYMBOLS || []);
  const names = [];
  for (const it of nameItems) {
    const m = sbScore(q, it.text);
    if (m) names.push({ it, score: m.score + (SB_TYPE_BONUS[it.cls] || 0) + (it.bonus || 0), pos: m.pos });
  }
  names.sort((a, b) => b.score - a.score || a.it.text.length - b.it.text.length);
  const top = names.slice(0, 50);
  // Then a separate "In descriptions" section: full-text over the prose bodies. Gated at 3+ chars (a
  // 1–2 char query would match nearly every description) and kept below the name results, since a name
  // hit is a stronger signal than a word buried in prose.
  let prose = [];
  if (q.length >= 3) {
    for (const it of SEARCH_PROSE) {
      const m = sbScore(q, it.body, true);   // substring-only: a literal phrase match, clean highlight
      if (m) prose.push({ it, score: m.score, pos: m.pos, group: 'In descriptions' });
    }
    prose.sort((a, b) => b.score - a.score);
    prose = prose.slice(0, 12);
  }
  sbRender(top.concat(prose), raw, names.length + prose.length);
}
// Char-by-char build with matched positions wrapped in <mark>; a path dims its directory portion.
function sbHighlight(it, pos) {
  const set = new Set(pos), s = it.text;
  const build = (from, to) => { let out = ''; for (let i = from; i < to; i++) out += set.has(i) ? '<mark>' + esc(s[i]) + '</mark>' : esc(s[i]); return out; };
  if (it.cls === 'file' || it.cls === 'dir') {
    const cut = s.lastIndexOf('/') + 1;
    return (cut ? '<span class="sb-dir">' + build(0, cut) + '</span>' : '') + build(cut, s.length);
  }
  return build(0, s.length);
}
function sbRender(scored, raw, total) {
  sbRows = scored;
  sbRowEls = [];
  sbActive = scored.length ? 0 : -1;
  if (!raw) { sbMeta.textContent = ''; sbResults.innerHTML = '<div class="sb-empty">Type to search elements, files, symbols, glossary terms and fields. <kbd>@</kbd> jumps to a symbol in the open file. <kbd>↑</kbd><kbd>↓</kbd> to move, <kbd>↵</kbd> to jump.</div>'; return; }
  if (!scored.length) { sbMeta.textContent = ''; sbResults.innerHTML = '<div class="sb-empty">No matches for “' + esc(raw) + '”.</div>'; return; }
  sbMeta.textContent = (total > scored.length ? scored.length + ' of ' + total : String(total)) + ' result' + (total === 1 ? '' : 's');
  const frag = document.createDocumentFragment();
  let lastGroup = null;
  scored.forEach((r, i) => {
    const group = r.group || null;                 // a section header appears when the group changes
    if (group !== lastGroup) {
      lastGroup = group;
      if (group) { const h = document.createElement('div'); h.className = 'sb-group'; h.textContent = group; frag.appendChild(h); }
    }
    const row = document.createElement('div');
    row.className = 'sb-row' + (r.it.prose ? ' prose' : '') + (i === sbActive ? ' active' : '');
    // A prose (full-text) row shows the element name plain + the matched snippet; a name row highlights
    // the name itself and shows its context sub, exactly as before.
    const textHtml = r.it.prose ? esc(r.it.text) : sbHighlight(r.it, r.pos);
    const subHtml = r.it.prose ? sbSnippet(r.it.body, r.pos) : (r.it.sub ? esc(r.it.sub) : '');
    row.innerHTML = '<span class="sb-badge ' + r.it.cls + '">' + esc(r.it.badge) + '</span>'
      + '<span class="sb-text">' + textHtml + '</span>'
      + (subHtml ? '<span class="sb-sub">' + subHtml + '</span>' : '');
    row.addEventListener('mousemove', () => sbSetActive(i));
    row.addEventListener('click', () => { const rr = sbRows[i]; if (rr) rr.it.run(); });
    sbRowEls.push(row);                             // parallel to sbRows[i]; group headers are NOT included
    frag.appendChild(row);
  });
  sbResults.innerHTML = '';
  sbResults.appendChild(frag);
}
// Active-row tracking keys off sbRowEls (the .sb-row elements only), not sbResults.children, so the
// interspersed section headers don't throw off the indexing.
function sbSetActive(i) {
  if (i === sbActive) return;
  if (sbActive >= 0 && sbRowEls[sbActive]) sbRowEls[sbActive].classList.remove('active');
  sbActive = i;
  if (sbRowEls[i]) { sbRowEls[i].classList.add('active'); sbRowEls[i].scrollIntoView({ block: 'nearest' }); }
}

// A folder result: reveal it in the file browser (open it in the code slot when it isn't pinned).
function sbGotoDir(path) {
  if (!treePinned) setBrowsing(true);
  const key = treeKey(path);
  highlightTreePath(key);   // expands ancestors, highlights the row, scrolls it into view
  expandDir(key);           // then open the folder itself
}
// A glossary result: switch to the Glossary view, flash the term's row, and open its source if it has one.
// go() may animate a view change, so poll for the freshly rendered row before flashing.
function sbGotoGlossary(term, source) {
  go({ kind: 'glossary' });
  const flash = (tries) => {
    let hit = null;
    diagram.querySelectorAll('.glossary tbody tr').forEach((r) => { if (r.dataset.term === term) hit = r; });
    if (hit) {
      hit.scrollIntoView({ block: 'center' });
      hit.classList.add('sb-flash');
      setTimeout(() => hit.classList.remove('sb-flash'), 1200);
      if (source && localRef(source)) { const wn = whereNode(source); openInCodeViewer(wn.file, wn.line); }
      return;
    }
    if (tries > 0) requestAnimationFrame(() => flash(tries - 1));
  };
  requestAnimationFrame(() => flash(60));
}
// Jump to the System tab and flash the first table row whose text contains `text` (a config key, a
// security surface, a run action, …). The System tab has no per-row id, so we match on cell text —
// good enough to land the eye on the right row after navigating.
function sbGotoSystem(text) {
  go({ kind: 'system' });
  const needle = (text || '').trim().toLowerCase();
  const flash = (tries) => {
    let hit = null;
    diagram.querySelectorAll('.system-wrap tbody tr').forEach((r) => {
      if (!hit && r.textContent.toLowerCase().includes(needle)) hit = r;
    });
    if (hit) {
      hit.scrollIntoView({ block: 'center' });
      hit.classList.add('sb-flash');
      setTimeout(() => hit.classList.remove('sb-flash'), 1200);
      return;
    }
    if (tries > 0) requestAnimationFrame(() => flash(tries - 1));
  };
  requestAnimationFrame(() => flash(60));
}

const sbResizer = document.getElementById('sbresizer');
const clampSearchW = (w) => Math.min(Math.max(w, 220), Math.round(window.innerWidth * 0.45));
const savedSearchW = parseInt(lsGet(LS.searchW) || '', 10);
if (savedSearchW) searchbar.style.width = clampSearchW(savedSearchW) + 'px';

// A diagram snapshot for stageScaleWithColumn: the svg-pan-zoom sizes + pan, plus the diagram column's DOM
// width — all captured BEFORE a column resize.
function stageBaseline() { return mainPz ? { ...mainPz.getSizes(), pan: mainPz.getPan(), leftW: leftcol.getBoundingClientRect().width } : null; }
// Scale the diagram in step with its column's WIDTH: as the column narrows / widens by ratio r, scale the
// diagram by r too — even when the diagram is height-constrained and a plain re-fit would leave it unchanged
// — so the whole diagram shrinks / grows proportionally with the pane (the info pane already does). Keeps the
// same point under the viewport centre. The ratio is measured from the column's DOM width (exactly linear),
// NOT svg-pan-zoom's internal width (which carries a padding offset) — so scaling composes exactly: a drag
// from an opened state lands on the same scale as opening straight to that width. `before` = stageBaseline().
function stageScaleWithColumn(before) {
  if (!mainPz || !before) return;
  scheduleStage(() => {
    const cx = (before.width / 2 - before.pan.x) / before.realZoom;   // SVG point at the old viewport centre
    const cy = (before.height / 2 - before.pan.y) / before.realZoom;
    mainPz.resize();
    const ratio = before.leftW ? leftcol.getBoundingClientRect().width / before.leftW : 1;  // column width change
    const a = mainPz.getSizes();
    if (a.realZoom) mainPz.zoom(mainPz.getZoom() * (before.realZoom * ratio) / a.realZoom);  // apply that scale
    const s = mainPz.getSizes();
    mainPz.pan({ x: s.width / 2 - s.realZoom * cx, y: s.height / 2 - s.realZoom * cy });  // re-centre same point
  });
}

function setSearchOpen(on) {
  const wasOpen = !searchbar.hidden;
  if (on === wasOpen) { if (on) { sbInput.focus(); sbInput.select(); } return; }
  const served = document.body.classList.contains('served');
  const before = stageBaseline();  // diagram state BEFORE the column resizes
  const anchorRight = served ? resizer.getBoundingClientRect().left : null;
  searchbar.hidden = !on;
  document.body.classList.toggle('search-open', on);
  lsSet(LS.searchOpen, on ? '1' : '0');
  // In-flow: the sidebar takes real width out of the diagram column (the info pane shrinks with it), and
  // we take that width from the middle column so the file browser + code viewer on the right stay put.
  if (anchorRight !== null) {
    const shift = resizer.getBoundingClientRect().left - anchorRight;  // how far the right group moved
    if (shift) leftcol.style.width = clampLeftW(leftcol.getBoundingClientRect().width - shift) + 'px';
  }
  if (before) stageScaleWithColumn(before); else if (served) refitStage();  // shrink / grow the diagram with the column
  if (on) { sbEnsureIndex(); sbEnsureSymbols(); sbRun(); sbInput.focus(); sbInput.select(); }
}
// Resizable width (persisted + clamped). The sidebar's width change is taken OUT OF the middle pane (the
// diagram + info column), not the code viewer: as the sidebar grows by Δ the middle column shrinks by Δ,
// so the file browser and code pane on the right stay put. The diagram scales by the column's width ratio —
// the exact same proportional shrink/grow as opening the sidebar (stageScaleWithColumn, off the drag-start
// baseline), so a drag and an open resize the diagram identically.
let sbResizing = false, sbDragX = 0, sbDragSbW = 0, sbDragLeftW = 0, sbDragBefore = null;
sbResizer.addEventListener('mousedown', (e) => {
  e.preventDefault(); sbResizing = true; document.body.classList.add('resizing');
  sbDragX = e.clientX;
  sbDragSbW = searchbar.getBoundingClientRect().width;
  sbDragLeftW = leftcol.getBoundingClientRect().width;  // px snapshot so the middle pane can give the space back
  sbDragBefore = stageBaseline();  // diagram baseline; scaling off it composes exactly with an open resize
});
document.addEventListener('mousemove', (e) => {
  if (!sbResizing) return;
  const newSbW = clampSearchW(sbDragSbW + (e.clientX - sbDragX));
  const applied = newSbW - sbDragSbW;                 // real sidebar delta after clamping
  searchbar.style.width = newSbW + 'px';
  leftcol.style.width = clampLeftW(sbDragLeftW - applied) + 'px';  // middle pane absorbs it; right panes unchanged
  if (sbDragBefore) stageScaleWithColumn(sbDragBefore); else resizeStagePreserve();
});
document.addEventListener('mouseup', () => {
  if (!sbResizing) return;
  sbResizing = false; document.body.classList.remove('resizing');
  lsSet(LS.searchW, String(parseInt(searchbar.style.width, 10) || ''));
  // Don't persist the shrunken column into leftW — that's the search reservation, restored on close.
});

const toggleSearch = () => setSearchOpen(searchbar.hidden);
searchBtn.addEventListener('click', toggleSearch);
sbClose.addEventListener('click', () => setSearchOpen(false));
sbInput.addEventListener('input', sbRun);
sbInput.addEventListener('keydown', (e) => {
  if (e.key === 'ArrowDown') { e.preventDefault(); if (sbRows.length) sbSetActive((sbActive + 1) % sbRows.length); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); if (sbRows.length) sbSetActive((sbActive - 1 + sbRows.length) % sbRows.length); }
  else if (e.key === 'Enter') { e.preventDefault(); const r = sbRows[sbActive]; if (r) r.it.run(); }
  else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); setSearchOpen(false); }
});
// Global shortcuts: ⌘/Ctrl-K toggles; bare "/" opens + focuses (unless already typing in a field).
document.addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); toggleSearch(); return; }
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target && e.target.tagName) || '') || (e.target && e.target.isContentEditable);
  if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); setSearchOpen(true); }
});
if (lsGet(LS.searchOpen) === '1') setSearchOpen(true);  // collapsed by default; reopen only if left open

buildFileTree();
initServerMode();  // probe for `coyodex serve`; on success reveal + wire the file browser and code viewer

// The intro's title IS the tab's label — read it off the button so the two can never disagree. Read
// BEFORE the legend is built: its section headings name views from the same map.
viewsw.querySelectorAll('button[data-view]').forEach((b) => { VIEW_LABEL[b.dataset.view] = b.textContent.trim(); });
buildLegend();  // one legend, built once; syncLegend decides where it shows
viewsw.querySelectorAll('button').forEach((b) => {
  if (b.dataset.view === 'container' && !HAS_GROUPING) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'domain' && !HAS_DOMAIN) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'hp' && !HAS_HP) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'usecases' && !HAS_USECASES) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'deployment' && !HAS_DEPLOYMENT) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'glossary' && !HAS_GLOSSARY) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'system' && !HAS_SYSTEM) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'data' && !HAS_DATA) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'tests' && !HAS_TESTS) { b.style.display = 'none'; return; }
  if (b.dataset.view === 'rules' && !HAS_RULES) { b.style.display = 'none'; return; }
  b.addEventListener('click', () => goTab(b.dataset.view));
});
navback.addEventListener('click', back);
navfwd.addEventListener('click', fwd);
zoomin.addEventListener('click', () => { if (mainPz) { mainPz.zoomIn(); updateZoomLevel(); } });
zoomout.addEventListener('click', () => { if (mainPz) { mainPz.zoomOut(); updateZoomLevel(); } });
zoomlevel.addEventListener('click', () => { if (mainPz) { mainPz.reset(); updateZoomLevel(); } });  // fit to screen
diagram.addEventListener('wheel', wheelNavigate, { passive: false });  // scroll=pan, Ctrl/Cmd/pinch=zoom
flowprev.addEventListener('click', () => flowStepBy(-1));  // step player: previous / next flow action
flownext.addEventListener('click', () => flowStepBy(1));
// Same view, different overlay — capture the live pan/zoom + selection first so the toggle keeps them
// (render() restores from the state) instead of resetting to a fresh, unselected fit. Registered
// unconditionally: renderChrome hides #toggle unless a diff (baked or live) is active.
toggle.addEventListener('click', () => { captureViewState(); mode = mode === 'diff' ? 'base' : 'diff'; render(); });

// Drop the active impact overlay and restore the baked baseline (if any). This is the ONLY
// interactive overlay teardown left — the old mechanical diff picker was removed in favor of the
// impact explorer (a strict superset: any range, resolution rungs, typed ripple, provenance).
function clearLiveDiff() {
  IMPACT = null;
  document.getElementById('impactbtn').classList.remove('armed');
  LIVE_DIFF = null;
  DIFF_STATE = BAKED_DIFF_STATE || {};
  mode = HAS_DIFF ? 'diff' : 'base';
  syncTreeDiff();                                       // clear the file-browser badges + hide the filter
  if (cvPath && cvDiffMode) loadCode(cvPath, cvLine);   // revert an open diff back to the plain file
  captureViewState();
  render();
}
const treeDiffOnlyBtn = document.getElementById('treediffonly');
if (treeDiffOnlyBtn) treeDiffOnlyBtn.addEventListener('click', () => {
  diffOnly = !diffOnly;
  treeDiffOnlyBtn.classList.toggle('on', diffOnly);
  applyDiffFilterAll();
});

// --- impact explorer ---------------------------------------------------------------
// Projects an ARBITRARY diff (any base/target, incl. ranges that don't touch the map's commit) onto
// the map: direct hits carry their change + resolution rung; typed ripple carries provenance. Rides
// the live-diff overlay rails (badges, tree, code diff) via a synthesized LIVE_DIFF — the mutex with
// the plain diff picker is therefore structural: arming either one disarms the other.
function impactShown(imp) { return imp.cause === 'direct' || imp.strength <= impactTh; }
function impactProjection() {
  const out = {};
  if (!IMPACT) return out;
  for (const id in IMPACT.impacts) {
    const imp = IMPACT.impacts[id];
    if (!impactShown(imp)) continue;
    out[id] = imp.cause === 'direct' ? (BADGE[imp.change] ? imp.change : 'modified') : 'rippled';
  }
  return out;
}
// The impact summary iterates THIS, so a bucket `impact_ripple.type_of` can produce and this cannot
// name is a row that silently vanishes while `counts.direct`/`counts.ripple` still count it.
// `capabilities` and `subflows` were reachable and missing before the decision layer existed; the
// order is the reading order, not the emission order.
const IMP_TYPE_LABEL = { subsystems: 'Subsystems', components: 'Components', deps: 'Dependencies',
  entities: 'Entities', subdomains: 'Subdomains', use_cases: 'Use cases', capabilities: 'Capabilities',
  happy_path: 'Happy Path', flow_steps: 'Flow steps', subflows: 'Sub-flows',
  edges: 'Call sites (edges)', entry_points: 'Entry points',
  blocks: 'Decision areas', rules: 'Business rules', rule_sites: 'Rule enforcement sites',
  glossary: 'Glossary', security: 'Security surfaces', run_commands: 'Run commands',
  non_entity_types: 'Other types', other: 'Other' };
// A flow-step synthetic id 'step:<uc>:<n>' → its parts, or null. Shared by impName / gotoImpactEid.
function parseStepEid(id) {
  const m = id.match(/^step:([^:]+):(.+)$/);
  return m ? { uc: m[1], n: m[2] } : null;
}
// A rule-site synthetic id 'rule:<BRn>:<i>' → its rule id, or null.
function parseRuleSiteEid(id) {
  const m = id.match(/^rule:(BR\d+):\d+$/);
  return m ? m[1] : null;
}
function impName(id) {
  if (GRAPH.nodes[id]) return GRAPH.nodes[id].name;
  // A rule SITE is not a node — name it by the decision it enforces, not by `BR1:0`.
  const rid = parseRuleSiteEid(id);
  if (rid && GRAPH.nodes[rid]) return GRAPH.nodes[rid].name;
  const st = parseStepEid(id);
  if (st) {  // a hit flow step reads as "<use case / sub-flow> · step n", not the raw synthetic id
    const uc = GRAPH.nodes[st.uc];
    if (uc) return uc.name + ' · step ' + st.n;
    const sf = (GRAPH.subflows || []).find((s) => s.id === st.uc);  // step:SF…: no node — the SF list
    return (sf ? sf.name : st.uc) + ' · step ' + st.n;
  }
  const i = id.indexOf(':');
  return i > 0 ? id.slice(i + 1) : id;   // synthetic ids (edge:…, ep:…) show their payload
}
function impResLabel(imp) {
  if (imp.cause === 'direct') return imp.resolution || 'file';
  return 'ripple' + (imp.distance > 1 ? ' ·' + imp.distance : '');
}
function gotoImpactEid(id) {
  if (id.startsWith('UC')) { go({ kind: 'usecase', uc: id }); return; }
  if (id.startsWith('HP')) { go({ kind: 'hp' }); return; }
  if (id.startsWith('edge:')) { selectFromTree(id.slice(5).split('>')[0]); return; }
  // A rule SITE is not a node — route the row to the rule it enforces, which is one.
  const rid = parseRuleSiteEid(id);
  if (rid) { selectFromTree(rid); return; }
  const st = parseStepEid(id);
  if (st) {
    // The synthetic id carries the authored `n` WITHIN its container (a flow, or a sub-flow whose
    // steps are expanded inline into every referencing flow). Host `n`s and sub-flow `n`s can
    // collide in one expanded narrative, so the mapping matches on the (sf, n) PAIR, never n alone.
    if (st.uc.startsWith('SF')) {  // step:SF…: land on the FIRST referencing flow's expanded run
      for (const uc in FLOWS_NARR) {
        const i = FLOWS_NARR[uc].findIndex((s) => s.sf === st.uc && String(s.n) === st.n);
        if (i >= 0) { selectFlowStep(uc, i); return; }
      }
      return;  // referenced by no flow (validate warns) — nowhere to land
    }
    const i = (FLOWS_NARR[st.uc] || []).findIndex((s) => !s.sf && String(s.n) === st.n);
    if (i >= 0) selectFlowStep(st.uc, i);
    else go({ kind: 'usecase', uc: st.uc });  // step missing from the narrative — open its flow
    return;
  }
  if (GRAPH.nodes[id]) selectFromTree(id);
}
// The forward panel: "what does this diff impact?" — grouped by element type, strongest first,
// every row clickable. Takes over the Subsystems-overview default panel while impact is armed.
function showImpactSummary() {
  if (!IMPACT) return;
  const short = (r) => (r === DIFF_WORKTREE ? 'working tree' : (r || '').slice(0, 8));
  const c = IMPACT.counts || {};
  let html = '<h2>Impact</h2>'
    + '<p class="muted" style="margin:0 0 8px">' + esc(short(IMPACT.spec.base)) + ' → '
    + esc(short(IMPACT.spec.target)) + ' · ' + (IMPACT.files || []).length + ' file'
    + ((IMPACT.files || []).length === 1 ? '' : 's') + ' changed</p>'
    + '<div class="badges"><span class="badge kind">' + (c.direct || 0) + ' direct</span>'
    + '<span class="badge kind">' + (c.ripple || 0) + ' rippled</span></div>';
  for (const w of (IMPACT.warnings || []))
    html += '<p class="impwarn">' + esc(w) + '</p>';
  const byType = IMPACT.byType || {};
  for (const t in IMP_TYPE_LABEL) {
    const ids = (byType[t] || []).filter((id) => impactShown(IMPACT.impacts[id]));
    if (!ids.length) continue;
    html += '<dl><dt>' + esc(IMP_TYPE_LABEL[t]) + ' <span class="muted">' + ids.length + '</span></dt>'
      + ids.map((id) => {
          const imp = IMPACT.impacts[id];
          const st = imp.cause === 'direct' ? (BADGE[imp.change] ? imp.change : 'modified') : 'rippled';
          const click = (GRAPH.nodes[id] || id.startsWith('UC') || id.startsWith('HP')
            || id.startsWith('edge:') || id.startsWith('step:'));
          const name = click
            ? '<a href="#" class="impref" data-id="' + esc(id) + '">' + esc(impName(id)) + '</a>'
            : esc(impName(id));
          return '<dd>' + name + ' <span class="badge ' + st + '">' + esc(impResLabel(imp)) + '</span></dd>';
        }).join('') + '</dl>';
  }
  panel.innerHTML = html;
  panel.querySelectorAll('a.impref').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault(); gotoImpactEid(a.getAttribute('data-id'));
  }));
}
// The backward panel section on a selected element: "why is THIS impacted?" — the change + rung for
// a direct hit, the provenance chain for a ripple, and the changed files (each opens its diff).
function impactSectionHtml(id) {
  if (!IMPACT) return '';
  const imp = IMPACT.impacts && IMPACT.impacts[id];
  if (!imp || !impactShown(imp)) return '';
  let html = '<div class="impsec"><h3>Impact of the active diff</h3>';
  if (imp.cause === 'direct') {
    const st = BADGE[imp.change] ? imp.change : 'modified';
    html += '<p><span class="badge ' + st + '">' + esc(imp.change) + '</span> '
      + '<span class="muted">directly hit at ' + esc(imp.resolution || 'file') + ' resolution</span></p>';
  } else {
    const hops = (imp.via || []).map((h) =>
      '<a href="#" class="impvia" data-id="' + esc(h.from) + '">' + esc(impName(h.from)) + '</a>'
      + ' <span class="muted">(' + esc(h.relation) + ')</span>').join(' → ');
    html += '<p><span class="badge rippled">affected</span> <span class="muted">via</span> ' + hops + '</p>';
  }
  const files = imp.files || [];
  if (files.length) {
    html += '<dl><dt>Changed files</dt>' + files.map((f) =>
      '<dd><a href="#" class="impfile" data-path="' + esc(f) + '">' + esc(f) + '</a></dd>').join('') + '</dl>';
  }
  return html + '</div>';
}
function bindImpactSection(root) {
  root.querySelectorAll('a.impfile').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault(); loadCode(a.getAttribute('data-path'), null);
  }));
  root.querySelectorAll('a.impvia').forEach((a) => a.addEventListener('click', (ev) => {
    ev.preventDefault(); gotoImpactEid(a.getAttribute('data-id'));
  }));
}
async function loadImpact(base, target) {
  const msg = document.getElementById('impactpopmsg');
  if (msg) msg.textContent = '';
  const qs = new URLSearchParams();
  if (base) qs.set('base', base);
  if (target) qs.set('target', target);
  if (impactTh >= 7) qs.set('callgraph', '1');
  let data;
  try {
    const res = await fetch(API_BASE + 'impact?' + qs.toString(), { cache: 'no-store' });
    const body = await res.text();
    if (!res.ok) { if (msg) msg.textContent = body || ('impact failed (' + res.status + ')'); return; }
    data = JSON.parse(body);
  } catch (_) { if (msg) msg.textContent = 'Could not reach the server for the impact.'; return; }
  IMPACT = data;
  LIVE_DIFF = { impact: true, base: data.spec.base, target: data.spec.target,
                changes: (data.files || []).map((f) => ({ status: f.status, path: f.path,
                  oldPath: (f.p_path && f.p_path !== f.path) ? f.p_path : null })),
                counts: { files: (data.files || []).length }, elements: {} };
  DIFF_STATE = impactProjection();
  mode = 'diff';
  document.getElementById('impactbtn').classList.add('armed');
  closeImpactPop();
  syncTreeDiff();
  if (cvPath) loadCode(cvPath, cvLine);
  if (HAS_GROUPING) go({ kind: 'container' });
  else { captureViewState(); render(); }
}
const impactctl = document.getElementById('impactctl');
const impactbtn = document.getElementById('impactbtn');
const impactpop = document.getElementById('impactpop');
function closeImpactPop() { if (impactpop) impactpop.hidden = true; }
function openImpactPop() {
  if (!impactpop) return;
  impactpop.hidden = false;
  document.getElementById('impactpopmsg').textContent = '';
  loadImpactCommits();
}
// The impact picker's commit list: DESCENDANTS of the pin first (code newer than the map — the common
// case after a fetch), then ancestors. Clicking a row fills the BASE input.
let impactCommitsLoaded = false;
async function loadImpactCommits() {
  const host = document.getElementById('impcommits');
  if (!host || impactCommitsLoaded) return;
  host.innerHTML = '<div class="diffpop-loading">Loading commits…</div>';
  let data;
  try {
    const r = await fetch(API_BASE + 'impactcommits', { cache: 'no-store' });
    if (!r.ok) throw new Error('impactcommits ' + r.status);
    data = await r.json();
  } catch (_) { host.innerHTML = ''; return; }
  impactCommitsLoaded = true;
  const row = (c, tag) =>
    '<button type="button" class="diffcommit" data-sha="' + esc(c.sha) + '" title="' + esc(c.subject) + '">'
    + '<span class="dc-sha">' + esc(c.sha) + '</span>'
    + (tag ? '<span class="dc-tag">' + tag + '</span>' : '')
    + '<span class="dc-subj">' + esc(c.subject) + '</span></button>';
  const desc = (data.descendants || []).map((c) => row(c, 'newer'));
  const anc = (data.ancestors || []).map((c) => row(c, ''));
  host.innerHTML = desc.join('') + anc.join('');
  host.querySelectorAll('.diffcommit').forEach((b) =>
    b.addEventListener('click', () => { document.getElementById('impBase').value = b.getAttribute('data-sha'); }));
}
if (impactbtn) {
  impactbtn.addEventListener('click', (e) => { e.stopPropagation(); impactpop.hidden ? openImpactPop() : closeImpactPop(); });
  document.addEventListener('click', (e) => { if (!impactpop.hidden && !impactctl.contains(e.target)) closeImpactPop(); });
  document.getElementById('impSinceMap').addEventListener('click', () => loadImpact('', DIFF_WORKTREE));
  function impGoNow() {
    const base = document.getElementById('impBase').value.trim();
    const target = document.getElementById('impTarget').value.trim();
    if (!base && !target) { document.getElementById('impactpopmsg').textContent = 'Pick a base commit (or use the one-click option above).'; return; }
    loadImpact(base, target || DIFF_WORKTREE);
  }
  document.getElementById('impGo').addEventListener('click', impGoNow);
  ['impBase', 'impTarget'].forEach((iid) =>
    document.getElementById(iid).addEventListener('keydown', (e) => { if (e.key === 'Enter') impGoNow(); }));
  document.getElementById('impClear').addEventListener('click', clearLiveDiff);
  impactpop.querySelectorAll('.imp-depth').forEach((b) => b.addEventListener('click', () => {
    impactpop.querySelectorAll('.imp-depth').forEach((x) => x.classList.toggle('on', x === b));
    impactTh = Number(b.getAttribute('data-th'));
    if (!IMPACT) return;
    // +Calls needs call-graph data the default fetch skips — refetch once with it on.
    if (impactTh >= 7 && !(IMPACT.spec.options && IMPACT.spec.options.callgraph)) {
      loadImpact(IMPACT.spec.base, IMPACT.spec.target);
      return;
    }
    DIFF_STATE = impactProjection();
    captureViewState(); render();
    if (mainScene && !mainScene.selection.length) showImpactSummary();
  }));
}

// Land on the Subsystems view for a diff render (the change-impact overlay lives there); otherwise the
// Happy Path — the behavioural spine, lead-with-behaviour — falling back to Subsystems, then the
// Dependencies (context) view, when a map has no Happy Path.
go({ kind: (HAS_DIFF && HAS_GROUPING) ? 'container' : (HAS_HP ? 'hp' : (HAS_GROUPING ? 'container' : 'context')) });
