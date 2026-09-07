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

### Working on the viewer

```bash
make dev-start                   # serves this repo's own map, with live reload
```

An edit reaches the screen with nothing pressed. Two halves, and both are needed:

- **`--dev` gives the map page a live reload.** It polls `/p/<slug>/api/dev-reload` once a second
  for a stamp (the newest mtime across `viewer.html` / `viewer.js` / `viewer.css` **and** this
  tool's Python) and reloads when it moves. `viewer.js` / `viewer.css` / `viewer.html` are read from
  disk per request and sent `no-store`, so an edit to any of them is live at once. Off without the
  flag, and then the endpoint is a 404 like any unknown name: a person reading a map must not get a
  page that reloads under them, nor carry a poll they did not ask for.
- **`tools/devserve.py` restarts the server on a Python edit.** The view bundle is built
  in-process, so the running server cannot pick one up (re-importing a live module graph mid-request
  is how a server starts answering from two versions of itself — see the stale-process guard in
  `serve.py`). It watches only `*.py` under `tools/coyodex/`: restarting for a frontend edit buys
  nothing and costs something, since a restart landing while the page reloads kills the port
  mid-load.

The two halves are joined by one field. `api/dev-reload` also answers `stale` — whether this
process's Python is older than the files on disk, so a restart is owed to it — and the page never
reloads from a stale process. Without that, a Python edit reloads the page from the doomed process
and lands on a dead port: a blank page, and nothing left polling to fix it.

`PORT` works the same as for `make start`: `make dev-start PORT=8792`.

For each map the server provides: the generic shell + `/static/` assets; the map's data at
`/p/<slug>/api/view`; and a live file browser + syntax-highlighted code viewer, both reading files
from git **at the map's commit** (`git ls-tree` / `git show`), so what you see always matches the map
and edits on disk never leak in.

The server does **not** scan the disk. Open `http://127.0.0.1:8765/` and use **+ Add a project…** to
browse to a folder containing a `.coyodex/project-map.json`; your choices are remembered in
`~/.coyodex/serve-recents.json` and shown as a recents list on the next start (each openable, or
removable with the ✕). highlight.js is lazy-loaded from a pinned + SRI CDN on first use.

## Finding your way around

Chrome that orients a first-time reader, so the map is readable without knowing its conventions:

- **View switcher** (two rows, top of the graph pane) — the five **groups** on top (Product · Data ·
  Code · Operations · Glossary), the open group's **views** below. The groups are the old flat row's
  altitude order made visible: what it does · what it knows · what it is made of · what runs · its
  words. Membership is declared on each view button (`data-group`), so there is no second list to keep
  in step; the group row is built at boot and **drops any group whose every view this map gated off**.
  A group holding one view (Glossary) draws no sub tabs, but the strip keeps its height, so switching
  never shunts the diagram up and down. Neither row may shrink its buttons: they wrap to a second line
  instead. Both rows start at the same left edge, with the search and legend buttons pushed to the far
  right, and a view's own **mode switch** (today: the Features axis) rides the RIGHT end of the view
  row rather than a third strip of its own — it is quieter than either row of tabs, because a mode is
  not a destination. (The flat row of eleven tabs did not fit — at a 1280px window the last tab had zero visible
  width and could not be clicked at all.)
- **View caption** — the info pane's top-level state (what it shows when nothing is selected): the
  view's name as the title, and under it the question that view answers.
- **Emptiness note** — a quiet chip under the caption saying why a view looks bare when it does ("no
  infrastructure is used by 2+ processes"). A lane a rule found nothing for looks identical to one
  nobody recorded anything for; the note says which. Deliberately NOT coverage counts — "N of M
  components have no recorded connection" only restates that a map is incomplete, which is a given, and
  never changes how to read the diagram. Completeness belongs to `validate`, with the ids to fix.
- **Environment filter** (bottom-left, Deployment overview only) — picks a deployment variant. Boxes
  and arrows the environment excludes are **dimmed and made unclickable**, never removed: a silent
  absence answers nothing, and the layout stays put while you compare environments. It floats over the canvas because it changes what the canvas draws; the
  per-process cards are environment-independent, so it hides there.
- **Legend** (bottom-right) — ONE key for the whole map: every box kind in its own colour AND its own
  shape, the infrastructure role colours, and the two stroke conventions (dashed border = collapsed,
  dashed arrow = bundled). In diff mode it gains a Changes section, so there is exactly one place to
  look anything up. Colours come from `ELEMENT_TINT`, the same styles the generators paint with, so it
  cannot drift. Close it with the × in its corner; the **?** beside the view tabs brings it back, and
  the choice persists. Shown only on views that actually draw a diagram — never over a text table.
- **First-run guide** (`?` in the header) — the gestures, including drill (double-click or ⌥-click)
  and search (`/`). Shown once, reopenable any time.
- **One-time notes** — e.g. the first time a selection dims the diagram, a line explains that the fade
  is a focus, not a failure.

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
  - **Level 1** is the walk as a stack of **rows**, one per run of steps under one person, named in a
    gutter on the left. Inside a row, a **box** holds a run of consecutive steps in one feature,
    tinted in that feature's own colour (the same `featureTint` the two rails use, so the three
    screens agree); two boxes of one person are joined by one unbroken line, and the row's line ends
    in an arrow head. Each step is a bullet carrying its position in the whole walk — the number both
    rails drop, because this is the view whose subject it is. Three doors: a step opens its use
    case's flow, a feature's name that feature's page, a person's name theirs. Every box on the page
    is one height (`levelHpBoxes`), and each row scrolls sideways on its own, so a row of three
    steps is not dragged off screen to reach the end of a row of thirteen.
    It is HTML (`renderHappyPath`), not a diagram, so it never shrinks: Mermaid scaled the sequence
    diagram this replaced down to 9.5px of step text on a 29-step map, and 44% of another map's
    drawing width was the empty channel between the last actor's lifeline and the System's. The walk
    ran 3.2 and 3.6 screens WIDE as one line; as rows it is about 2 screens DOWN, and only one row on
    two of the four maps is still wider than a window.
  - **Level 2** (a step) opens its **use case's T6 flow**: a **sequence diagram** of the actor plus the
    components/deps/entities it touches, each step an ordered message (the verb comes from the backbone
    edge). The side panel keeps the use case's outside summary — it does **not** repeat the steps, since
    the diagram already draws them; clicking one message opens that step's own pane (its action, why, and
    note), each element link locating that element in its home view (its subsystem card, entity card, …).
    Navigate back with the breadcrumb (Happy Path › *this step*) or the **◀ ▶** arrows.
- **Features** *(when the map records capabilities)* — the product on one screen, in three levels.
  Level 1 is the **story diagram**: ONE column holding every feature in **story order** (the walk's
  first-touch order unbroken, then every feature the walk never reaches in a block after it, each
  placed by its authored `story` anchor — before/after the feature it reads beside — or by a derived
  fallback, its actors' last walk step), beside the actors as a cast in order of first appearance,
  joined by derived actor→feature arrows. A feature the walk skips draws the SAME card as any other
  and spends no word on the walk: walk membership says nothing about importance, and the demoted
  third column this replaces read as a ranking. A `before` anchor is the one placement that keeps
  such a feature among the walk, since the end of a column is not before anything. At rest the arrows are bare; hovering or pinning a
  card lights its arrows and shows each one's **stake label** (the authored `stakes[]` entry, or the
  pair's first use-case name), which links to that edge's first Happy-Path step. Each card's NAME is
  its door one level down, and the only door it has — the counts under the sentence (use cases on
  both columns, rules on a feature) are labels. A spine card's feature NAME is the door to that
  **feature's own page**. A cast card's actor NAME is the door to that **actor's
  own page** — the journey line: the actor's happy-path steps as stations on one rail, zoned by
  feature in the order the actor first enters each (zones tinted per feature), with the actor's
  other use cases as side stops under their zone; the features they never enter on the walk follow
  the rail's arrowhead as normal zones, in the same story order. Its hero states the actor's place
  in the story and, when the map authors role relations, who they were before ("becomes") and whose
  abilities they include.
  There is no Actors tab: the cast column is the actors' home. A map with no walk draws the same
  two columns in map order; only a map with no capabilities
  falls back to the flat card grid, which otherwise survives solely in diff mode for its "changed"
  badges. Search and "show in context" land here with the card pinned. Level 2 is that feature's own
  page, and level 3 a use case's flow — the same flow a Happy Path step drills into, so a use case has
  one home. A map that records no capabilities skips level 1 and keeps the flat catalog it always had.

  A **feature's page** leads with what it is, then a **chip bar** naming every section on it and how
  many things each holds — the page's contents and its summary in one line, so "15 rules, 7 entities"
  is answered before any scrolling. Each count is stated once, on its chip; click to jump, and the
  chip of the section you are in lights as you scroll.

  Its first section is the **feature rail** — the actor page's journey line with the two keys swapped.
  The actor's rail zones by feature; a feature's rail zones by **driver**: the walk's steps that
  belong to this feature, in walk order, as stations, with everything else the feature can do as side
  stops under the dashed cut. The stations are **unnumbered** here — a digit under a dot is that
  step's place in the whole walk, which is the Happy Path's own subject and one click away through
  the station, while the rail already reads as the order it is. The **actor** rail keeps its numbers:
  that page scatters one actor's steps across the whole walk, and the number is the only thing saying
  how far apart two of their stations are. A zone is a run of consecutive steps under one driver, so a
  feature the walk **enters twice** draws two boxes (on this repo's own map, "Getting set up" at steps
  1 and 15) rather than one box claiming they are adjacent. The zone's name opens that actor's page,
  a station opens the Happy Path at that step, a side stop opens that use case's flow. One board, one
  binder and one stylesheet serve both pages. A feature the walk never enters keeps the **card grid**,
  where each card's sentence is the only thing left to read.
- **Rules** *(when the map states any business rule)* — the decisions this product makes, on the same
  cards: one card per **decision area**, with what that area covers and how many rules sit in it.
  Clicking a card opens that area's rules; clicking a rule opens its own page. It was every area
  stacked on one scroll under a chip bar, which put the rules the tab exists to show below the fold.
- **Entities** *(when the map has T5 domain cards)* — the C4 Code altitude: the domain model as a
  Mermaid `classDiagram`, each entity a class box holding its attributes, joined by typed, cardinal
  relations (composition/aggregation/inheritance/association). Click a class for its fields +
  `file:line`; click a relation for its kind + cardinality. Two things a box says are links: a field
  whose **type is another entity** (`Role[] roles`) — click the type to select that entity, wherever
  it is drawn — and the **store line** (`🛢 orders(MongoDB)`), which opens the **Storage** tab on that
  store's pane with this entity's row flashed (the same jump as the info pane's "See in Storage"). When the model groups entities into
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
- **System** *(when the map records any operational fact)* — the reference collections no diagram
  holds, as the same **cards** the Features tab uses: one card per collection, saying what it answers
  and how big it is, drilling to that one collection. The cards sit in three bands, because the tab
  holds three different kinds of thing: **the running system** (entry points, run commands, config,
  security, observability, the deliberately-unmodelled types), **notes about the code** (each authored
  section, previewed by its own opening line), and **about this map** (map completeness, and the
  maintenance records answering this tool's own checks). The entry-point page carries its own pinned
  **Entry points** goes one level deeper for the same reason, with a card per KIND. The collections
  behind the cards are: **entry points** (grouped by kind, each linking to its owning
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
