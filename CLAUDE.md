# coyodex

## Glossary

The words we use when talking about this project. Use these; don't drift back to
the code's names.

**The product**

- **map** — the whole picture coyodex produces for a project: the diagrams, the
  plain-language text on every box, and the code links. Lives in `.coyodex/`.
- **baseline** — the map as currently accepted, pinned to a commit. What a
  change is compared against.
- **build** — analyzing a project from scratch and producing a new map. Throws
  away hand edits.
- **viewer** — the browser page that shows a map. Served live, never committed.
- **view** (a tab in the viewer) — one diagram answering one question: Happy
  Path, Use Cases, Business logic, Entities, Subsystems, Dependencies, Data,
  Deployment, System, Glossary, Tests.
- **box** — one thing drawn on a view. **arrow** — a relation between two boxes.
- **code link** — the `file:line` a box points at. A box without one is
  ungrounded, which is a defect.
- **change impact** — the report saying what a code change does to the map.
- **accept** — folding a change-impact report into the baseline.
- **Coyote Effect** — the situation coyodex exists for: your agent wrote a lot
  of code, it runs, and you have lost track of what is under your feet.

**How coyodex is delivered**

- **the method** — `method.md` and the files under `method/`: the instructions
  the coding agent follows to build a map. The product's real logic lives here,
  not in code.
- **the skill** — what `make install` puts into the agent so `/coyodex` works.
- **the tools** — the small programs the agent calls while building (indexing,
  code sizing, validation).

**Working on coyodex**

- **eval** — scoring two maps of the same project to tell whether a change to
  the method made map quality better or worse.
- **retro** — reading a finished build and its chat to find what went wrong in
  the process.
- **gates** — the automatic checks a change must pass before it counts as done:
  the full test run and the type checker. Green gates only prove nothing broke;
  they never prove a change to the method is an improvement.
- **test tier** — which set of tests a change requires; picked from what was
  touched. A path given to the test command silently skips whole tiers.
- **verdict** — how an eval run rates the new map against the baseline:
  **PASS** (as good), **DRIFT** (a measurement moved further than allowed —
  needs a human look, not automatically bad), **REGRESSED** (a hard check got
  worse — blocking).

The word **gate** is also used inside the product, with a different meaning:
there it is a check a *map* must pass. Failing one is a defect in the map, not
in the code.
