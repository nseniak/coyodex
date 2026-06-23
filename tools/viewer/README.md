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
   │  gen_viewer.py              emits one self-contained HTML file (Mermaid + pan/zoom, pinned + SRI)
   ▼
project-map.html                 render · pan/zoom · click→panel · diff overlay
```

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

- **Context** — the system, its actors (Roles, drawn human vs service), and external deps.
- **Subsystems** *(when the map groups components)* — the Container altitude: subsystem boxes with
  inter-subsystem edges **derived** from the component edge list (count-labelled). Click a box to
  **expand it in place** into its components; the cross-edges re-derive at mixed altitude (an
  `S→S` arrow explodes into the concrete `S→component` edges); click the frame to collapse. Click a
  derived edge to see the underlying component edges it aggregates.
- **Components** — every component + its verbed edges; click a node/edge for details + `file:line`.
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
- **Subsystem expand reflows** the whole layout (Mermaid re-lays-out each toggle) rather than
  growing one box in place — that smoothness would need a compound-graph renderer (Cytoscape/ELK).
- The Python side (parser + validator) is **stdlib-only**; the only third-party dependency is the
  client-side JS above.
