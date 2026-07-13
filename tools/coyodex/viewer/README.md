# coyodex viewer

The interactive, drillable rendering of `project-map.json` — the Tier-B viewer from
[diagrams](../../method/diagrams.md). A diagram is a *rendering* of the map: the model stays the
single source of truth; this tool builds a graph from it and draws it. The viewer is **served**, not
a committed file — `coyodex serve` reads the model and builds every diagram on demand, and a generic
frontend fetches that data and renders it.

## Pipeline

```
.coyodex/project-map.json        the model (single source)
   │  views.model_to_graph       model → GraphDict
   ▼
GraphDict
   │  gen_viewer.build_view_bundle   graph → the view bundle (every diagram source, flow, config)
   ▼
GET /p/<slug>/api/view           served as JSON by `coyodex serve`
   │  viewer.js (fetched by the generic shell viewer.html, from /static/)
   ▼
the rendered map                 render · pan/zoom · click→panel · diff overlay
```

`build_graph.py` additionally hosts the change-impact report parser (`build_diff`), reusing the
same table-splitting grammar (`tools/coyodex/grammar.py`) — a genuinely separate, still-markdown
input (the diff overlay's report), not the map itself.

The frontend lives in **`viewer.html`** (the generic shell), **`viewer.css`**, and **`viewer.js`**
(edited as normal HTML/CSS/JS). `coyodex serve` ships them from `/static/` unchanged for every
project — identical for every map; only the per-project data differs, fetched at boot from `api/view`.
Mermaid + svg-pan-zoom load from a pinned + SRI CDN.

## Run

The viewer is served — there is no HTML file to render. Start the server and open the project:

```bash
make start                       # opens the landing page in a browser
# or directly:
.venv/bin/coyodex serve --port 8765 --open
.venv/bin/coyodex serve ~/code/myrepo   # add + serve a folder right away
```

For each map the server provides: the generic shell + `/static/` assets; the map's data at
`/p/<slug>/api/view`; and a live file browser + syntax-highlighted code viewer, both reading files
from git **at the map's commit** (`git ls-tree` / `git show`), so what you see always matches the map
and edits on disk never leak in.

The server does **not** scan the disk. Open `http://127.0.0.1:8765/` and use **+ Add a project…** to
browse to a folder containing a `.coyodex/project-map.json`; your choices are remembered in
`~/.coyodex/serve-recents.json` and shown as a recents list on the next start (each openable, or
removable with the ✕). highlight.js is lazy-loaded from a pinned + SRI CDN on first use.

## What it shows — the C4 altitudes

**Hover preview** — hovering any node or edge pops a small tooltip with its *meaning* (a node's
Purpose / Used for / Meaning / Wants, an edge's Why), so you can read the map without clicking.
Clicking still opens the fuller side panel; the tooltip never changes the selection.

- **Context** — the system, its actors (Roles, drawn human vs service), and the external **systems**
  it relies on, drawn by name (datastore / messaging / service / platform). In-process deps
  (framework / library) collapse into one **📚 Libraries (N)** box — ⌘-click it to drill into the full
  list (or plain-click to preview the names), so the top altitude stays a clean C4 picture instead of
  a star of every imported library. The split is the T2 `Kind` column (inferred from `Type` when absent).
- **Subsystems** *(whenever the map has components — a map that defines no subsystem of its own gets
  one default subsystem so this altitude always exists)* — the Container altitude: subsystem boxes with
  inter-subsystem edges **derived** from the component edge list (count-labelled). Drilling replaces
  the diagram **in place** (no popups) and is tracked as a back/forward **history** (stepping back
  or forward restores each view's pan/zoom as you left it):
  - Click a **box** → its *neighbourhood* view: the subsystem framed around its **immediate** children
    (its direct components inline, plus any **child subsystems as drillable boxes**), with the deps those
    direct components touch outside the frame, and every other subsystem its members link to/from drawn
    as a collapsed box joined by a count-labelled arrow (like the overview; a subdomain the components
    touch is bridged the same way). Click a child box to drill **deeper** (nesting goes to any depth);
    click a neighbour box to re-center on it; click a cross arrow to open that pair's edge view.
  - Click an `S→S` **arrow** → its edge view: the two subsystems framed with the concrete crossings
    between them. A cross arrow into a box that *contains* (or is contained by) the current one instead
    **navigates** to that box (drill in / zoom out), since one can't frame the other.
  - Component nodes/arrows are clickable for details + `file:line`; the side panel
    shows the group you're on **plus its immediate children** (child groups annotated with how many
    leaves nest under them). **Navigate** with the header **◀ ▶** arrows, **⌘+←/→** or **⌥+←/→**, or by
    clicking any crumb in the breadcrumb — which now shows the **full nesting path**, one crumb per
    level (e.g. Subsystems › Plugins › Social Content). The Entities view nests subdomains the same way.
  - *(No flat whole-repo Components tab: it was too heavy to be a landing view. Components are reached
    by drilling a subsystem; a map that defines no subsystem of its own gets one **default subsystem**
    (named after the project) so there is always a structural altitude. The flat-map generators are kept
    dormant and restorable.)*
- **Happy Path** *(when the map has a Happy Path)* — the behavioural overlay, in two levels:
  - **Level 1** is the path as a black-box **sequence diagram** — an ordered walk through the use
    cases, each step a message from its use case's actor to the System. Plain-click a step to see that
    use case's **outside summary** in the side panel (its actor + trigger → outcome, the same facts as
    the Use Cases list); ⌘-click to drill in.
  - **Level 2** (a step) opens its **use case's T6 flow**: a **sequence diagram** of the actor plus the
    components/deps/entities it touches, each step an ordered message (the verb comes from the backbone
    edge). The side panel keeps the use case's outside summary — it does **not** repeat the steps, since
    the diagram already draws them; clicking one message opens that step's own pane (its action, why, and
    note), each element link locating that element in its home view (its subsystem card, entity card, …).
    Navigate back with the breadcrumb (Happy Path › *this step*) or the **◀ ▶** arrows.
- **Entities** *(when the map has T5 domain cards)* — the C4 Code altitude: the domain model as a
  Mermaid `classDiagram`, each entity a class box holding its attributes, joined by typed, cardinal
  relations (composition/aggregation/inheritance/association). Click a class for its fields +
  `file:line`; click a relation for its kind + cardinality. When the model groups entities into
  **subdomains**, the Entities view drills exactly like Subsystems (in place, back/forward history):
  - It leads with a **Subdomains overview** — one box per subdomain, with `SD→SD` arrows derived from
    the crossing entity relations (count-labelled).
  - Click a subdomain **box** → its *neighbourhood* card: the subdomain framed as a `namespace` holding
    its own entities full (attributes + internal relations), with every other subdomain it relates to
    drawn as a collapsed box joined by cross arrows. Click a neighbour box to re-center on it; click a
    cross arrow to open that pair's edge view.
  - Click an `SD→SD` **arrow** (overview or neighbourhood) → its edge view: the two subdomains both
    framed, showing each one's inner relations plus the concrete entity relations that cross between
    them. Class boxes ⌘-click to open source; relation arrows click for kind + cardinality.
- **Glossary** *(when the map has glossary terms)* — the ubiquitous-language terms as a table, not a
  diagram: each term with its meaning and a link to its code home (the term's bare `where` anchor,
  opened in the editor / on GitHub exactly like a node's source ⌘-click). A term with no single code
  home shows no link.
- **System** *(when the map records any operational fact)* — the reference tables the diagram doesn't
  hold, as a stack of small tables: **entry points** (grouped by kind, each linking to its owning
  component), **run commands**, **deployment**, **observability**, **security**, **config**, the
  deliberately-**unmodelled types**, and any freeform **extras**. Every `path:line` cell opens in the
  code viewer, like a glossary source link.
- **Tests** *(when the map has a test-completeness table)* — the honesty note ("was the suite run, or is
  every row inferred?") above the risk-ranked gap table (`Target · Tested? · Test(s) · Gap/risk ·
  Confidence`).
- **Diff overlay** *(on the Subsystems views)* — pass a change-impact report and the viewer lands on
  the Subsystems overview in **diff** mode: each subsystem box is badged with its subtree's change
  (added/modified/deleted/rippled), drilling a subsystem badges its changed components, and the side
  panel lists every change (added elements included, since they have no box to badge). A
  baseline⇄diff toggle switches the badges off/on. *(The overlay used to live on the flat Components
  map; it moved here when that tab was removed.)*

The header meta line states the map's **commit** + date, its **build time**, and the **schema** tag.

## Tests

```bash
python tests/test_grouping.py     # stdlib runner; or: .venv/bin/pytest tests/test_grouping.py
```

## Scope & current limits

- **Client libs from a pinned CDN with SRI** (Mermaid 11.15.0 UMD + svg-pan-zoom 3.6.1). Viewing
  needs network; the integrity hashes mean a tampered file is rejected. Vendoring the libs locally is
  not done.
- **The viewer requires `coyodex serve`** — there is no offline `file://` fallback; the map data is
  fetched from the server, which also supplies the file browser + code viewer.
- **Subsystem drill-down replaces the diagram in place** (no popups) with a back/forward history,
  rather than expanding boxes in the map. Neighbours are shown collapsed (one box per subsystem,
  aggregated arrows), so a hub subsystem stays readable. The flat whole-repo Components map (which
  showed every component at once) was removed as a tab — its generators are kept dormant. Note:
  **⌘+←/→** is hijacked from the browser's own back/forward via `preventDefault` (⌥+←/→ is the
  conflict-free alternative).
- The Python side (parser + validator) is **stdlib-only**; the only third-party dependency is the
  client-side JS above.
