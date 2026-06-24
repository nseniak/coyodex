# coyodex viewer

An interactive, self-contained HTML rendering of a `project-map.md` — the Tier-B viewer from
[diagrams](../../method/diagrams.md). A diagram is a *rendering* of the map, so this tool parses the
committed markdown (no second source) and draws it; the markdown stays the single source of truth.

## Pipeline

```
.coyodex/project-map.md          schema-v1 map (single source)
   │  build_graph.py             parser — uses the shared grammar in tools/schema_v1.py
   ▼
graph.json                       ephemeral parse result (parser ↔ renderer interface)
   │  gen_viewer.py              inlines viewer.css + viewer.js → one self-contained HTML file
   ▼                             (Mermaid + pan/zoom, pinned + SRI)
project-map.html                 render · pan/zoom · click→panel · diff overlay
```

The viewer's front-end lives in **`viewer.css`** and **`viewer.js`** (edited as normal CSS/JS);
`gen_viewer.py` reads and **inlines** them at build time. The emitted HTML stays standalone — it
carries no path back to this repo, so it can be committed with the mapped project and opened on a
machine that has never seen coyodex (the only external load is the pinned + SRI CDN libs).

## Run

One step (what the method calls) — map straight to HTML; the `graph.json` interface stays in a
temp file:

```bash
python3 tools/viewer/render.py .coyodex/project-map.md .coyodex/project-map.html [analysis-changes/<date>.md]
```

Or the two stages explicitly (e.g. to inspect the parsed graph):

```bash
python3 tools/viewer/build_graph.py .coyodex/project-map.md build/graph.json   # parse → graph.json
python3 tools/viewer/gen_viewer.py  build/graph.json build/project-map.html    # graph.json → HTML
```

To view, serve over http (file:// can't fetch the CDN libs cleanly):

```bash
python3 -m http.server 8753 -d .coyodex   # → http://localhost:8753/project-map.html
```

## What it shows — the C4 altitudes

**Hover preview** — hovering any node or edge pops a small tooltip with its *meaning* (a node's
Purpose / Used for / Meaning / Wants, an edge's Why), so you can read the map without clicking.
Clicking still opens the fuller side panel; the tooltip never changes the selection.

- **Context** — the system, its actors (Roles, drawn human vs service), and external deps.
- **Subsystems** *(when the map groups components)* — the Container altitude: subsystem boxes with
  inter-subsystem edges **derived** from the component edge list (count-labelled). Drilling replaces
  the diagram **in place** (no popups) and is tracked as a back/forward **history**:
  - Click a **box** → its *neighbourhood* view: the subsystem framed around its components (with
    their internal wiring + the deps they touch outside the frame), and every other subsystem its
    components link to/from drawn as a collapsed box, joined by unlabelled component→box arrows.
    Click a neighbour box to re-center on it (walk the graph); click a cross arrow to open that
    pair's edge view.
  - Click an `S→S` **arrow** → its edge view: the two subsystems framed with just the concrete
    component edges that cross between them.
  - Component nodes/arrows behave like the Components view (click for `file:line`); the side panel
    shows the subsystem(s) you're on. **Navigate** with the header **◀ ▶** arrows, **⌘+←/→** or
    **⌥+←/→**, or by clicking an ancestor crumb in the breadcrumb (the structural nesting path,
    e.g. Context › Subsystems › *this subsystem*) below the header.
- **Components** — every component + its verbed edges; click a node/edge for details + `file:line`.
- **Domain** *(when the map has T5 domain cards)* — the C4 Code altitude: the domain model as a
  Mermaid `classDiagram`, each entity a class box holding its attributes, joined by typed, cardinal
  relations (composition/aggregation/inheritance/association). Click a class for its fields +
  `file:line`; click a relation for its kind + cardinality.
- **Diff overlay** — pass a change-impact report to recolor added/modified/deleted nodes and the
  elements they ripple to, with a baseline⇄diff toggle.

## Tests

```bash
python3 tools/tests/test_grouping.py     # stdlib runner; or: pytest tools/tests/test_grouping.py
```

## Scope & current limits

- **Client libs from a pinned CDN with SRI** (Mermaid 11.15.0 UMD + svg-pan-zoom 3.6.1). Viewing
  needs network; the integrity hashes mean a tampered file is rejected. Fully offline use would
  require vendoring the libs locally — not done.
- **Source links** show as `file:line` text in the panel; turning them into clickable blob URLs
  pinned to the map's commit SHA is a follow-up.
- **Subsystem drill-down replaces the diagram in place** (no popups) with a back/forward history,
  rather than expanding boxes in the map. Neighbours are shown collapsed (one box per subsystem,
  aggregated arrows), so a hub subsystem stays readable; full multi-hop tracing still lives in the
  Components view. Note: **⌘+←/→** is hijacked from the browser's own back/forward via
  `preventDefault` (⌥+←/→ is the conflict-free alternative).
- The Python side (parser + validator) is **stdlib-only**; the only third-party dependency is the
  client-side JS above.
