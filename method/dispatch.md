# Dispatch — what to do when coyodex is invoked

The user invoked coyodex on a repo. Decide the mode, then read the listed doc(s) **fully** and
follow them — don't restate them or work from memory. The tooling is the `coyodex` CLI, installed
into this clone's venv (`.venv/bin/coyodex`; source under `tools/coyodex/`).
The clone's `internal/` folder is design rationale, not the method — ignore it.

**Path reminder:** every `method.md` / `method/...` / template / `.venv/bin/coyodex` path below is
under the coyodex clone (`COYODEX_HOME` from the skill), **not** the repo you are mapping (your cwd).
Read/run them with that absolute prefix. Only `.coyodex/...` paths are in the analyzed repo.

## Step 0 — did the user name a mode?

If the invocation explicitly names a mode — **`build`**, **`analyze`**, or **`accept`** (the verbs
the README teaches, e.g. `/coyodex analyze`) — do that mode directly: Build → `method.md`, Analyze /
Accept → `method/change-impact.md`. (Bare `/coyodex` names nothing, so fall through to Step 1.)

## Step 1 — is there already a baseline?

Look for `.coyodex/project-map.json` (the schema-v2 model) in the analyzed repo. A legacy
`.coyodex/project-map.md` with no `project-map.json` next to it is NOT a baseline — schema-v1
markdown is no longer readable by the tools; treat the repo as having no baseline and fall through
to Build below.

### No baseline → Build

Create it. Read `method.md` (+ `method/model.md`, `method/domain-cards.md`): agents return
structured rows and `coyodex assemble` writes the model + views.

### Baseline exists → default to Analyze (never silently rebuild)

A rebuild regenerates the map from scratch and **overwrites the curated, reviewed baseline** — it
loses manual fixes and the pin history. So it is **never** the default. Read the baseline pin from
the model's `commit` / `committed` fields, then:

1. **Is there anything to analyze?** Compare the pin to the **current working tree** (so a later
   commit *and* uncommitted edits both count), ignoring coyodex's own files. The tree matches the pin
   only when there is no diff **and** no untracked file:

   ```
   git -C <repo> diff --quiet <pin> -- . ':(exclude).coyodex' \
     && [ -z "$(git -C <repo> ls-files --others --exclude-standard -- . ':(exclude).coyodex')" ]
   ```

   (Use the pin's bare sha; if the pin ends in `-dirty` it never matched a clean commit, so skip
   straight to Analyze.)

   - **Both true — current source == the pin** → the baseline is current. Tell the user
     `baseline is up to date @ commit <id> from <date>` and stop; do **not** produce an empty diff.
     (If only `.coyodex/project-map.html` is missing or stale, just re-render it with
     `coyodex render` — that is a render, not a rebuild.)
   - **Otherwise — the source differs** (a later commit, uncommitted edits, or new files) →
     **Analyze**: read `method/change-impact.md` and follow it. The diff it computes is
     `git diff <pin>` (pin → working tree) plus any untracked files.

2. **Accept** — when the user says the report looks right, read `method/change-impact.md` (Accept).

3. **Rebuild** — only when the user *explicitly* asks to regenerate from scratch. Warn that it
   **overwrites the existing baseline and discards its curation and pin history**, get confirmation,
   then Build as above.

## Invariant (every mode)

The map is the single source at the analyzed repo's `.coyodex/project-map.json`; the committed
`.coyodex/project-map.md` and `.html` are generated views of it (never hand-edited). After every
write: **validate → audit → render**. Validate (`coyodex validate --check-sources`) checks schema +
semantics (and that the committed views are fresh); audit (`coyodex audit`) is the adversarial
pass — it makes the narrative Golden Path and
the mechanism flows/edges refute each other. It blocks only on a hard contradiction (a forward/dangling
`why:` reference); read-before-create and actor-attribution are ADVISORY (lossy attribution — reconcile,
don't treat as fact), and it prints an L2 grounding worklist to disprove against the code with
fresh-context skeptics (see `method.md`); render (`coyodex render` to `.md` and `.html`) — the views
are renderings, never a second source.

**Going deeper stays in the one map.** When a part of the system needs finer detail than its current
altitude, refine it IN PLACE — nest subsystems/subdomains, or promote a leaf component into a subsystem
(see `method.md` "Drilling deeper"). The viewer drills these nested levels recursively. **Never write a
second map file** (a per-area `.coyodex/<area>/project-map.md` "child map"): a separate file is a
separate ID space, so cross-references can't resolve, bidirectional links and shared elements break, the
viewer can't drill across it, and Analyze/Accept/change-impact only ever track this one baseline. Child
maps are **not supported**.
