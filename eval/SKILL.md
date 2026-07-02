---
name: coyodex-eval
description: >
  Run the coyodex method-quality regression eval on a project that already has a coyodex map.
  Rebuilds a fresh map with the current method, judges it (grounding + rubric), and compares it to
  the project's committed .coyodex/ map as the baseline — telling you whether the method/tooling got
  better or worse. Results go in a git-ignored .coyodex-eval/. Use whenever the user wants to
  "eval the map", "check the method quality", "regression-test the coyodex map", or runs
  /coyodex-eval. Triggers on "coyodex-eval", "eval this map", "method-quality eval".
---

# coyodex-eval

coyodex-eval is a method (prompts) + the `coyodex` CLI for a method-quality regression check on a
codebase map. **Read the method doc and follow it; don't work from memory.**

**Two different directories — keep them straight:**
- **`COYODEX_HOME` = `__COYODEX_HOME__`** — the coyodex clone. The eval bundle (this skill, the method
  doc, and the config `eval/thresholds.json`, `eval/rubric.md`) lives under `eval/`,
  and the CLI is `.venv/bin/coyodex` — all here.
- **The project you are evaluating** — your current working directory, a *different* path. Its
  baseline map is `.coyodex/project-map.md`; all eval output goes in `.coyodex-eval/` (git-ignored).

So whenever the method doc says to read a config file or run `.venv/bin/coyodex ...`, that path is
**under `COYODEX_HOME`** — use that absolute prefix (e.g. `__COYODEX_HOME__/eval/rubric.md`).
Only `.coyodex/...` and `.coyodex-eval/...` paths are in the evaluated project.

**Precondition:** this needs an existing `.coyodex/project-map.md`, and the working tree must be at the
commit that map is pinned to (the method refuses otherwise — see Step 1). If there is no map yet, run
`/coyodex` first to build one.

Read `__COYODEX_HOME__/eval/method.md` and follow it end to end (guard → build the fresh map BLIND
in an isolated worktree + freeze its hash → baseline cache → judge → compare + store). The order
matters: the build comes first so no baseline numbers exist in context while the map is written, and
the frozen map is never edited afterwards. It runs the FULL judge every time.
