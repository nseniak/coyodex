---
name: coyodex
description: >
  Build and maintain a coyodex project map — a top-down, drillable map of a codebase (behavioral
  layer first, then the structural machine), committed next to the code as a model and served as an
  interactive C4 diagram by `coyodex serve`. Use this skill whenever the user wants to: generate / build a project
  map or codebase map "with the coyodex method", "map this repo", analyze the change impact of a
  diff against an existing map, or accept a change-impact report into the baseline. Also use it
  when the user wants to SEE one thing in an existing map — "show me the use case about X in the
  map", "link to component Y", "open the map on this rule" — and end the answer with the address
  `coyodex url` prints. Triggers on "coyodex", "project map", "codebase map", "change impact",
  "accept the map", "show me … in the map", "link to … in the map".
---

# coyodex

coyodex is a method (prompts) + tools for a drillable map of a codebase.

**The repo is the source of truth — this skill is only a pointer into it, and is deliberately
thin.** Anything written HERE is a copy baked into `~/.claude/skills/` at `make install` time, and
goes stale the moment the repo moves on: the coyodex skill told agents for weeks to read a method
doc that had been renamed. So this file carries only what is needed to FIND the repo. Everything
else lives there and is read live.

- **`COYODEX_HOME` = `__COYODEX_HOME__`** — the coyodex clone. Every method doc, template and tool
  lives here; read and run them with that absolute prefix.
- **The repo you are mapping** — your current working directory, a *different*
  path. Only `.coyodex/` paths belong to it.

- **A link to any element of the map** — `__COYODEX_HOME__/.venv/bin/coyodex url <ID> --repo <repo>`
  prints the address that opens the running map on that element, already selected (`--context` for
  its home view with the element lit). Find the `<ID>` by grepping `.coyodex/project-map.json` for
  the thing's name. Never compose the address by hand: the words after `#` are the viewer's own.

Read `__COYODEX_HOME__/method/dispatch.md` and follow it end to end. It is the entry point, and it names every
other doc, tool and precondition — work from it, not from memory, and do not expect this file to
list them.
