# Diagrams

A diagram is just another **rendering** of the map the markdown already encodes — not a new
analysis. Because the markdown obeys [schema v1](schema-v1.md), a renderer parses it into a
graph; no separate persisted model is needed.

## Drill-down maps onto C4 + a behavioral view

| Zoom level | Shows | From the map |
|---|---|---|
| **Context** | the system, actors, external deps | T0 Goal · Roles · T2 |
| **Container** | runtime pieces (services, datastores, sandboxes) | Deployment + components |
| **Component** | T1 components + their verbed arrows | T1 + the edge list |
| **Code** | entry points → `file:line`; the **domain model as a `classDiagram`** (entities with attributes + typed, cardinal relations) | T4 anchors · T5 [domain cards](domain-cards.md) |
| **Behavioral overlay** | the Golden Path as a black-box sequence of steps; drill a step into the subgraph of components it touches | GP steps + traceability |

Drill down = zoom one level in; step back = zoom out — the same "name a row to drill"
navigation as the markdown, made visual.

**Context-diagram direction.** Actors (from Roles) point *into* the system — they initiate use
cases. External dependencies (from T2) point *out* — the system calls them. Keeping external
systems in T2 (not Roles) is what makes those arrows render the right way: an IdP, sandbox, or
upstream service is something the system *uses*, never an actor that uses the system.

## Diff as an overlay

Recolor the baseline graph from the annotated baseline-diff: **green = added, amber =
modified, red/ghosted = deleted** (re-draw deleted nodes just for the overlay), with a
show/hide toggle. The element-keyed deltas are the data.

## Edges and source links

- **Edges come from the verbed component edge list**, so every arrow carries its verb. Do
  not derive arrows from T1's coarse "Depends on".
- **Source links pin to the analysis commit SHA** so line drift doesn't break them.

## Realization tiers

- **Tier A — diagram-as-code (Mermaid / D2), generated from the markdown.** One diagram per
  level + a Golden Path sequence diagram, with `click`→source and diff via styled
  regeneration. Cheap, in-repo, version-controlled; "drill-down" is hyperlinked per-level
  diagrams rather than true zoom.
- **Tier B — a small self-contained HTML viewer**, available in [`tools/viewer/`](../tools/viewer/).
  Parses the markdown (via the shared `tools/schema_v1.py` grammar) and renders the C4 altitudes —
  Context → Subsystems (click a box/arrow to drill in place, derived inter-subsystem edges) →
  Components → code — plus the **Golden Path** as its own behavioural overlay (a black-box sequence
  diagram of the steps; clicking a step drills into the induced subgraph of the components it
  touches, with a link back to locate them in the full map). Navigated as a back/forward history
  (header arrows, ⌘/⌥+←/→, breadcrumb) with pan/zoom, click→panel, and a baseline⇄diff overlay.
  Mermaid + svg-pan-zoom load from a pinned CDN with Subresource-Integrity.

Reference frame: the **C4 model**, **Structurizr**, **Sourcetrail** — all standard. The
request to see architecture this way is not unusual.

## Example (Mermaid, Tier A)

A component diagram is the verbed edge list rendered directly:

```mermaid
flowchart TB
  c2[C2 Gateway] -->|enforces| c6[C6 Policy]
  c2 -->|routes-to| c8[C8 Upstream]
  c8 -->|persists| c12[(C12 Persistence)]
  c12 -->|cloud| d1[(D1 Mongo)]
  click c2 "path/to/file.py#L281" "file.py:281"
```
