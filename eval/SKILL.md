---
name: coyodex-eval
description: >
  FOR THE COYODEX DEVELOPER, not for users of coyodex: run the method-quality regression
  eval on a project that already has a coyodex map.
  Rebuilds a fresh map with the current method, judges it (grounding + rubric), and compares it to
  the project's committed .coyodex/ map as the baseline — telling you whether the method/tooling got
  better or worse. Results go in a git-ignored .coyodex-eval/. Use whenever the user wants to
  "eval the map", "check the method quality", "regression-test the coyodex map", or runs
  /coyodex-eval. Triggers on "coyodex-eval", "eval this map", "method-quality eval".
---

# coyodex-eval

A method-quality regression check on a codebase map: rebuild blind, judge, compare.

**The repo is the source of truth — this skill is only a pointer into it, and is deliberately
thin.** Anything written HERE is a copy baked into `~/.claude/skills/` at `make install-eval` time, and
goes stale the moment the repo moves on: the coyodex skill told agents for weeks to read a method
doc that had been renamed. So this file carries only what is needed to FIND the repo. Everything
else lives there and is read live.

- **`COYODEX_HOME` = `__COYODEX_HOME__`** — the coyodex clone. Every method doc, template and tool
  lives here; read and run them with that absolute prefix.
- **The project you are evaluating** — your current working directory, a *different*
  path. Only `.coyodex/` and `.coyodex-eval/` paths belong to it.

Read `__COYODEX_HOME__/eval/method.md` and follow it end to end. It is the entry point, and it names every
other doc, tool and precondition — work from it, not from memory, and do not expect this file to
list them.
