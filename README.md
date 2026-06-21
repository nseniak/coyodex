# coyodex

> A living, drillable map of a codebase that stays in sync with the code — so you
> never run off the cliff.

## The coyote effect

When you vibe code, you accumulate code you haven't really understood. It feels
fine — until the moment you need to understand it and discover there's nothing
under your feet. Like Wile E. Coyote, you've run past the edge of the cliff and
only now look down.

**coyodex fights the coyote effect.** It keeps a maintained understanding layer
beside the code — a top-down, drillable map — and updates that map as the code
changes, so you keep your footing without having to re-read everything.

It is *not* a replacement for reading code. It shrinks how much you must read and
tells you **where** to look. A trusted map is the whole point; a stale or
confidently-wrong map is a new cliff — which is why the discipline pieces
(the validator, the accept-cycle, committing the map *with* the code) are core,
not optional.

## What it produces

For a project, coyodex maintains two artifact types:

1. **`CODEBASE_ANALYSIS.md`** — a clean, current-state map. Behavioral layer first
   (Goal → Glossary → Roles → Use cases → **Golden Path**), then the structural
   machine (Components → Entry points / Model / Deps → Flows + a relationship edge
   list). Every row is drillable down to `file:line`. ID-based so it's also a clean
   source for diagrams and tooling ([schema v1](docs/schema-v1.md)).
2. **`analysis-changes/<date>.md`** — one annotated baseline-diff per accepted
   change cycle. The change report, the history, and the deletion record in one
   file ([change-impact](docs/change-impact.md)).

Plus optional **diagrams** rendered from the same map ([diagrams](docs/diagrams.md)).

## The workflow

```
analyze ──▶ CODEBASE_ANALYSIS.md (committed, commit-pinned)
   │
   ▼
edit code
   │
   ▼
change-impact ──▶ what's modified / added / deleted, grounded in the map you know
   │
   ▼
accept ──▶ patch the map, bump the commit pin, save the annotated diff, commit
```

The map is committed *with* the code, so "baseline commit" and "code commit" never
drift.

## Two best uses

- **Stay oriented while building.** Keep understanding without stopping to read
  everything; the change-impact report tells you what each edit did to the model.
- **PR review.** Review against a maintained map: "this PR adds Golden-Path step X,
  touches entities Y, ripples to Z" — semantic impact in the project's own terms,
  not a raw diff read cold. Often the sharpest use.

## How to use it (today)

coyodex is a **method + small tooling**, driven by an AI coding agent:

- [`METHOD.md`](METHOD.md) — the full method the agent follows.
- [`docs/`](docs/) — schema, change-impact lifecycle, diagrams.
- [`scripts/validate_analysis.py`](scripts/validate_analysis.py) — stdlib validator
  that checks a `CODEBASE_ANALYSIS.md` against schema v1.
- [`templates/CODEBASE_ANALYSIS.template.md`](templates/CODEBASE_ANALYSIS.template.md)
  — the skeleton to fill.

To analyze a repo, point the agent at `METHOD.md` and ask it to follow the method.

## Status

Early. The method and validator are real and in use; the interactive diagram viewer
is a planned tier (see [diagrams](docs/diagrams.md)).
