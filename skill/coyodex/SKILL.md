---
name: coyodex
description: >
  Build and maintain a coyodex project map — a top-down, drillable map of a codebase (behavioral
  layer first, then the structural machine), committed next to the code as a model and served as an
  interactive C4 diagram by `coyodex serve`. Use this skill whenever the user wants to: generate / build a project
  map or codebase map "with the coyodex method", "map this repo", analyze the change impact of a
  diff against an existing map, or accept a change-impact report into the baseline. Triggers on
  "coyodex", "project map", "codebase map", "change impact", "accept the map".
---

# coyodex

coyodex is a method (prompts) + tools for a drillable map of a codebase. **The repo is the source of
truth — this skill only points at it. Read the method docs and follow them; don't work from memory.**

**Two different directories — keep them straight:**
- **`COYODEX_HOME` = `__COYODEX_HOME__`** — the coyodex clone. ALL method docs (`method.md`,
  `method/...`, templates) and the tools (`.venv/bin/coyodex`) live here.
- **The repo you are mapping** — your current working directory, a *different* path. Its only
  coyodex content is `.coyodex/` (the map + report you produce).

So whenever a doc says to read `method.md`, `method/model.md`, a template, or to run
`.venv/bin/coyodex ...`, that path is **under `COYODEX_HOME`** — read/run it with that absolute
prefix (e.g. `__COYODEX_HOME__/method.md`). **Never look for method docs or tools in the repo you
are mapping; they are not there.** Only `.coyodex/...` paths are relative to the analyzed repo.

Read `__COYODEX_HOME__/method/dispatch.md` and follow it. It picks the mode (build / analyze /
accept), handles an existing baseline, and points to every other doc and tool.
