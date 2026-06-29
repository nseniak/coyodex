<div align="center">

# coyodex

<img src="assets/running-off-the-cliff.jpg" alt="Wile E. Coyote, having run past the edge of the cliff, hanging in mid-air just before he looks down" width="640">

### Vibe code without running off the cliff

</div>

When your agent generates a lot of code for you, you sometimes end up with code
you have completely lost track of. It runs fine until the day you actually
need to understand it. And then you find there's nothing under your feet.
This is the Coyote Effect.

coyodex helps you get and stay on top of your project without having to read
the code. It consists of a small number of prompts and tools you drive from
your AI coding agent to:

- **build a baseline map**: an AI-annotated view of your whole project,
  both functional and technical, drillable to `file:line`, committed next to the
  code so the two don't drift apart.
- **analyze a code diff** against it and generate a baseline-map overlay:
  what each change adds, touches, and ripples to, in the project's own terms.

## How to use

coyodex runs as an agent skill — it works on Claude Code, Codex, and Cursor. Install it once, then
drive everything with `/coyodex`.

**1. Install the skill (once).** Clone this repo, then from its root run (macOS/Linux):

```
make install
```

This installs the skill into each agent's skills home (`~/.claude/skills` for Claude Code,
`~/.agents/skills` — the cross-agent standard read by Codex and Cursor) with this repo's path baked
in, so `/coyodex` reads the method straight from here on all three. It also installs the Python
dependencies for the structural pre-index (`tools/requirements.txt` — tree-sitter; run `make deps`
alone to refresh them). Re-run only if you move the repo; `make uninstall` removes it.

**2. Build the baseline.** In your project, with no map yet, `/coyodex` builds it:

```
/coyodex
```

Writes `.coyodex/project-map.md` (the map) and `.coyodex/project-map.html` (an interactive, drillable
[C4 viewer](tools/viewer/)), pinned to the current commit. Commit both with your code.

**3. Edit your code.** Work as usual.

**4. Analyze the change.**

```
/coyodex analyze
```

Writes a report to `.coyodex/analysis-changes/<date>.md` — what your change adds, touches, and ripples
to, in the project's own terms. It's left **uncommitted** so you can review it first; the baseline
isn't touched yet.

**5. Accept the change.**

```
/coyodex accept
```

Patches the map, re-renders the viewer, bumps the commit pin, and commits the map together with the
report.

Then keep coding and repeat steps 3–5.

The skill only points at this repo and follows the method docs, which decide Build / Analyze / Accept
— the method stays the single source of truth. `make install` covers Claude Code, Codex, and Cursor;
on any other agent, each step also works by pasting *"Read `method.md` and follow it to …"* to any
agent that can read this repo.

## The workflow

```
/coyodex ────────▶ .coyodex/project-map.md   (committed, commit-pinned)
                   .coyodex/project-map.html (rendered interactive viewer)
   │
   ▼
edit code
   │
   ▼
/coyodex analyze ──▶ .coyodex/analysis-changes/<date>.md (report: modified / added / deleted, uncommitted)
   │
   ▼
/coyodex accept ──▶ patch the map, re-render the html, bump the commit pin, commit the map + the report
```

The map is committed *with* the code, so the baseline commit and the code commit
stay in step.

## Status

**Alpha — v0.1.0. Experimental and incomplete.** Expect breaking changes,
including to the on-disk map format — there are no backward-compatibility
guarantees yet, so a newer version may not read a map produced by an older one.
Good for evaluating and giving feedback; not yet something to depend on.

**What works today**

- Build a baseline map of a repo and render it as an interactive, drillable C4 viewer.
- Analyze a code diff against the map, overlay what changed and what it ripples to,
  and accept the result back into the baseline.
- Open a component's or domain entity's source straight from the viewer — in your
  editor (VS Code, Cursor, IntelliJ, …) or on GitHub.

**Known gaps / rough edges**

- The map format and the method itself are still moving; treat maps as disposable.
- Tested mainly on small and medium repos; behavior on large codebases is unexplored.
- Map quality depends on the coding agent and model — expect to review and correct it.
- The viewer is a browser page. On github.com the committed HTML shows as source, not
  rendered — view it via GitHub Pages or a raw-HTML proxy (e.g. raw.githack.com).

Feedback and bug reports are welcome — please [open an issue](../../issues).
