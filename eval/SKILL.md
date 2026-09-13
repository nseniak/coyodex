---
name: coyomap-eval
description: >
  FOR THE COYOMAP DEVELOPER, not for users of coyomap: run the method-quality regression
  eval on a project whose coyomap map has already been built.
  Scores and judges (grounding + rubric) two maps of the same code and compares them — telling you
  whether the method/tooling got better or worse. It builds nothing itself. Results go in a
  git-ignored .coyomap-eval/. Use whenever the user wants to
  "eval the map", "check the method quality", "regression-test the coyomap map", or runs
  /coyomap-eval. Triggers on "coyomap-eval", "eval this map", "method-quality eval".
---

# coyomap-eval

A method-quality regression check on a codebase map: judge two maps of the same code, compare.

**The repo is the source of truth — this skill is only a pointer into it, and is deliberately
thin.** Anything written HERE is a copy baked into `~/.claude/skills/` at `make install-eval` time, and
goes stale the moment the repo moves on: the coyomap skill told agents for weeks to read a method
doc that had been renamed. So this file carries only what is needed to FIND the repo. Everything
else lives there and is read live.

- **`COYOMAP_HOME` = `__COYOMAP_HOME__`** — the coyomap clone. Every method doc, template and tool
  lives here; read and run them with that absolute prefix.
- **The project you are evaluating** — your current working directory, a *different*
  path. Only `.coyomap/` and `.coyomap-eval/` paths belong to it.

Read `__COYOMAP_HOME__/eval/method.md` and follow it end to end. It is the entry point, and it names every
other doc, tool and precondition — work from it, not from memory, and do not expect this file to
list them.
