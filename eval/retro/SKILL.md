---
name: coyodex-retro
description: >
  Run a retrospective on a coyodex build that has ALREADY finished — read the map it produced and
  the chat transcript that produced it, and report what the run says about the tools and the method:
  quality signals, process signals, and the friction, bugs and gaps worth fixing. Report only; it
  changes nothing. Use whenever the user wants to "review the build", "what went wrong in that
  build", "find bugs from the last coyodex run", "retro the map build", or runs /coyodex-retro.
  Triggers on "coyodex-retro", "build retrospective", "review the coyodex run".
---

# coyodex-retro

A retrospective on ONE finished build. **Read the method doc and follow it; don't work from
memory.**

**Two different directories — keep them straight:**
- **`COYODEX_HOME` = `__COYODEX_HOME__`** — the coyodex clone. The retro method doc, the method it
  audits (`method.md`, `method/`), and the CLI (`.venv/bin/coyodex`, `.venv/bin/coyodex-eval`) are
  all here.
- **The project whose build you are reviewing** — your current working directory, a *different*
  path. Its map is `.coyodex/`, its previous map is `.coyodex/.old-ignore*/`, and the retro's
  output goes in `.coyodex-eval/retro/` (git-ignored).

So whenever the method doc says to read a doc or run `.venv/bin/coyodex ...`, that path is **under
`COYODEX_HOME`**. Only `.coyodex/...` and `.coyodex-eval/...` paths are in the reviewed project.

**Precondition:** a build has finished in this project, so `.coyodex/project-map.json` and
`.coyodex/provenance.json` both exist. Provenance names the session that built the map, which is
how the retro finds the right transcript instead of guessing.

**Run this in a NEW chat, never the build's own.** A transcript is named after its session, so
running here would append the retro's own turns to the file it is analysing — it would be reading
itself. Fresh context is also the point: an agent that built the map cannot see its own workarounds
as friction. The method doc's Step 0a refuses when the session ids match.

**This is REPORT ONLY.** It edits no map, no tool and no method doc. Its findings are proposals for
the user to decide on.

**It is not `/coyodex-eval`.** That one rebuilds the map blind and judges it against a baseline to
answer *did quality regress*. This one reads a build that already happened to answer *what did the
run reveal about the tools and the method*. Run `/coyodex-eval` when you want the semantic quality
verdict; run this when you want the bug list.

Read `__COYODEX_HOME__/eval/retro/method.md` and follow it end to end.
