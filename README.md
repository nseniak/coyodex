<div align="center">

# coyodex

<img src="assets/running-off-the-cliff.jpg" alt="Wile E. Coyote, having run past the edge of the cliff, hanging in mid-air just before he looks down" width="640">

### Vibe code without running off the cliff.

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

You drive coyodex with three prompts.

> The prompts say `method.md`, which lives in this coyodex repo. Make it reachable
> by the agent (e.g. clone coyodex next to your project) before running them.

**1. Build the baseline.** Point the agent at the method and let it map the repo:

```
Read method.md and follow it to analyze this repo.
```

This writes `.coyodex/project-map.md`: a current-state map, behavioral layer
first (Goal → Glossary → Roles → Use cases → **Golden Path**), then the structure
(Components → Entry points / Model / Deps → Flows + a relationship edge list).
Every row drills down to `file:line`, and stable IDs let the same map feed
[diagrams](method/diagrams.md) and tooling ([schema v1](method/schema-v1.md)). It then renders
`.coyodex/project-map.html` — the [interactive viewer](tools/viewer/): drillable C4 diagrams
(Context → Subsystems → Components → code) — and finishes by giving you links to **both** the map
and the diagram.

**2. Analyze a diff.** After you change code, ask for the change-impact report:

```
I've changed code since the last analysis. Read method.md and follow it to
report the change impact against the map.
```

This writes a change-impact report to `.coyodex/analysis-changes/<date>.md` — the
change's adds, touches, and ripples, in the project's own terms. The file is left
**uncommitted** so you can review it (in chat or an editor) first. The baseline
itself isn't touched yet.

**3. Accept the diff.** Once the report looks right, fold it into the baseline:

```
The report looks right. Read method.md and follow it to accept the change.
```

This patches `.coyodex/project-map.md` and commits it together with the report
from step 2 — now the accepted `.coyodex/analysis-changes/<date>.md`: the change
report, the history, and the deletion record in one file
([change-impact](method/change-impact.md)). Accept is mechanical — it applies the
report you reviewed, with no fresh analysis.

### Optional shortcut: the `/coyodex` skill

If you use Claude Code, install the bundled skill once so you can drive all three
steps by intent (e.g. *"generate a project map with the coyodex method"*) instead
of pasting the prompts above. It ships in [`skill/coyodex`](skill/coyodex) — symlink
it into your personal skills directory:

```
ln -s "$(pwd)/skill/coyodex" ~/.claude/skills/coyodex
```

The skill locates this clone, picks Build / Analyze / Accept from what you asked,
and then follows `method.md` — the method stays the single source of truth.

## The workflow

```
analyze ──▶ .coyodex/project-map.md (committed, commit-pinned)
   │
   ▼
edit code
   │
   ▼
change-impact ──▶ .coyodex/analysis-changes/<date>.md (report: modified / added / deleted, uncommitted)
   │
   ▼
accept ──▶ patch the map, bump the commit pin, commit the map + the report
```

The map is committed *with* the code, so the baseline commit and the code commit
stay in step.

## Status

This project is experimental.
