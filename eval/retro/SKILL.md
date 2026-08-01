---
name: coyodex-retro
description: >
  FOR THE COYODEX DEVELOPER, not for users of coyodex: run a retrospective on a coyodex
  build that has ALREADY finished — read the map it produced and
  the chat transcript that produced it, and report what the run says about the tools and the method:
  quality signals, process signals, and the friction, bugs and gaps worth fixing. Report only; it
  changes nothing. Use whenever the user wants to "review the build", "what went wrong in that
  build", "find bugs from the last coyodex run", "retro the map build", or runs /coyodex-retro.
  Triggers on "coyodex-retro", "build retrospective", "review the coyodex run".
---

# coyodex-retro

A retrospective on ONE finished build: what the run reveals about the tools and the method.

**The repo is the source of truth — this skill is only a pointer into it, and is deliberately
thin.** Anything written HERE is a copy baked into `~/.claude/skills/` at `make install-retro` time, and
goes stale the moment the repo moves on: the coyodex skill told agents for weeks to read a method
doc that had been renamed. So this file carries only what is needed to FIND the repo. Everything
else lives there and is read live.

- **`COYODEX_HOME` = `__COYODEX_HOME__`** — the coyodex clone. Every method doc, template and tool
  lives here; read and run them with that absolute prefix.
- **The project whose build you are reviewing** — your current working directory, a *different*
  path. Only `.coyodex/` and `.coyodex-eval/` paths belong to it.

Read `__COYODEX_HOME__/eval/retro/method.md` and follow it end to end. It is the entry point, and it names every
other doc, tool and precondition — work from it, not from memory, and do not expect this file to
list them.
