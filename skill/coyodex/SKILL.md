---
name: coyodex
description: >
  Build and maintain a coyodex project map — a top-down, drillable map of a codebase (behavioral
  layer first, then the structural machine), committed next to the code and rendered as an
  interactive C4 diagram. Use this skill whenever the user wants to: generate / build a project
  map or codebase map "with the coyodex method", "map this repo", analyze the change impact of a
  diff against an existing map, or accept a change-impact report into the baseline. Triggers on
  "coyodex", "project map", "codebase map", "change impact", "accept the map".
---

# coyodex

coyodex is a method (prompts) + tools for building and maintaining a drillable map of a codebase.
**This skill only bootstraps and routes — the method docs are the source of truth. Read the doc for
your mode and follow it; don't restate it or work from memory.**

## Step 0 — locate the coyodex clone (always first)

The method lives in a separate `coyodex` repo, cloned next to the project. Find `method.md`:

```
for d in ~/Projects/coyodex ../coyodex ../../coyodex ~/coyodex; do
  [ -f "$d/method.md" ] && echo "FOUND $d" && break
done
```

If none match, ask the user for the path. Call every tool by its path inside that clone
(`$COYODEX/tools/...`). Ignore the clone's `internal/` folder — design rationale, not the method.

## Pick the mode, read its doc, follow it

| The user wants | Mode | Read fully, then follow |
|---|---|---|
| new map / "map this repo" / "build the baseline" | **Build** | `method.md` (+ `method/schema-v1.md`, `method/domain-cards.md`); start from `method/templates/project-map.template.md` |
| "I changed code, what's the impact?" | **Analyze** | `method/change-impact.md` |
| "the report looks right, accept it" | **Accept** | `method/change-impact.md` |

Invariant: the map is the single source at the analyzed repo's `.coyodex/project-map.md`; after every
write, validate (`$COYODEX/tools/validate_analysis.py`) then render
(`$COYODEX/tools/viewer/render.py`) — the HTML is a rendering, never a second source.
