# The blinded-builder recipe — build a fresh map that cannot see the old one

**For the coyodex DEVELOPER.** Build a map of a repo at a chosen commit in an environment where the
builder can see **only the code** — no previous map, no eval state, no thresholds. The output is a
map you can hand to `/coyodex-eval` as an explicit candidate path.

**When you need this.** The everyday loop (`coyodex-eval archive .` → `/coyodex` → `/coyodex-eval`)
is blind *in practice*: `archive` moves the map out of the working tree, `dev-rebuilds/` is
git-ignored, and no build path reads it. Use this recipe when blindness must be **provable** rather
than incidental:

- **phase-boundary validation** of the master plan (`internal/docs/plan/00-MASTER-PLAN.md`, "the
  per-phase validation recipe") — the result gates a phase, so the builder must be isolated by
  construction, not by convention;
- any comparison where the builder's session might already have seen the baseline map (for example
  rebuilding inside the same chat that just read it).

A builder that can peek at the baseline can — even unintentionally — steer toward its numbers, and
the eval is the validation instrument for every change to the method, so its integrity holes are the
worst bugs it can have.

## The recipe

1. **Create an isolated checkout at the pin** (a scratch dir outside the project, e.g. under
   `$TMPDIR`):
   ```
   git -C <project> worktree add <scratch>/coyodex-blind-build <pin>
   ```
   (A `git clone <project> <scratch>/... && git checkout <pin>` works the same when worktrees are
   inconvenient.)
2. **Blind it** — remove everything the builder must not see, **keeping `.coyodex/.ignore`**:
   ```
   cd <scratch>/coyodex-blind-build
   find .coyodex -mindepth 1 -maxdepth 1 ! -name .ignore -exec rm -rf {} +
   rm -rf .coyodex-eval
   ```
   **Why `.ignore` survives the blinding.** It is not a previous answer — it is the repo's
   analysis-SCOPE declaration, tracked in git, saying which committed code the map is not meant to
   describe. `iter_source_files` honours it, so deleting it silently widens the tree the blind build
   maps and the scores are computed over: on this repo it takes the component expectation E from 14
   to 37 and pulls in `eval/fixtures/trapdoor/`, a fixture built deliberately to TRIP coyodex's
   advisories (broken anchors, overclaimed edges, an oversized flat folder). The resulting map
   carries inflated validate problems, contradictions and coverage flags by construction — and since
   every hard gate reads "the candidate must not be *worse* than the baseline", a blind map used as
   the BASELINE is then a free pass for whatever it is compared against. Nothing downstream can
   detect this: the worktree is deleted before the eval ever runs. Same reasoning as
   `archive.py`'s `KEEP` set — scope is not output.
   Note the map usually lives at HEAD, not at the pin: when the pin PREDATES the map commit (the
   normal state — the map is committed on top of the code it describes), the worktree at the pin
   contains no `.coyodex/` at all and blinding holds by construction; the `rm -rf` stays as
   defense-in-depth for the older layout where the map commit IS the pin. `.coyodex-eval/` is
   git-ignored and normally absent from a fresh worktree; remove it defensively anyway.
   **Dogfooding case:** if the built project is the coyodex clone itself, the worktree also contains
   committed copies of the eval bundle (its own `eval/thresholds.json`, `eval/rubric.md`) — remove
   those too (`rm -rf <scratch>/coyodex-blind-build/eval`); the never-read rule below is
   path-independent, but the blinding should be filesystem-deep, not instruction-deep.
3. **Run the build in a FRESH-context sub-agent** (never in an orchestrating context that has read
   eval state) whose working directory is the isolated checkout, instructed to:
   - follow the FULL coyodex build method — read `COYODEX_HOME/method/dispatch.md` then
     `COYODEX_HOME/method.md` (+ `method/model.md`, `method/domain-cards.md`) — agents return
     structured rows, `coyodex assemble` writes the model to its normal path
     `.coyodex/project-map.json` (+ generated views) **inside the isolated checkout**;
   - run the usual invariant there (`validate --check-sources`, `audit`, `render` via
     `COYODEX_HOME/.venv/bin/coyodex`); export `COYODEX_NO_SERVE_REGISTER=1` first so this throwaway
     build in a temporary checkout is NOT registered with `coyodex serve`;
   - **never read**: any path under the original project checkout; any coyodex eval bundle under ANY
     root — in particular any file named `thresholds.json` or `rubric.md` belonging to one (the
     `COYODEX_HOME/eval/` originals AND any committed copy inside the worktree); any `.coyodex/`,
     `.coyodex-eval/`, or `dev-rebuilds/` directory anywhere. The builder sees ONLY the code at the
     pin plus the build-method docs;
   - **run every fan-out synchronously** (wait for each batch of harvest / trace / skeptic
     sub-agents within its own turn): a builder that spawns BACKGROUND children stops at each
     barrier, which silently stalls an unattended run — the first boundary validation needed three
     manual resumes for exactly this. If background fan-out is unavoidable, the orchestrator must
     watch the build agent for stops and nudge it to continue (a stalled builder looks identical to
     a long-running one from outside).
4. **Copy the result out and clean up:**
   ```
   mkdir -p <somewhere outside .coyodex/>
   cp <scratch>/coyodex-blind-build/.coyodex/project-map.json <dest>/project-map.json
   git -C <project> worktree remove --force <scratch>/coyodex-blind-build
   ```

## Handing the map to the eval
The map is now an ordinary file. Give its path to `/coyodex-eval` as the explicit candidate
(`eval/method.md` Step 1.2), with the baseline being the project's committed map or a
`dev-rebuilds/NNNN/` archive. The eval's same-code guard still applies in full: zero code delta
between the two maps' pins (not pin equality), a clean tree, no code delta against HEAD, and an
unchanged `.coyodex/.ignore`. Note the guard verifies each pin with `git rev-parse` — so run the eval
in a checkout where the blind build's pin actually resolves, or the clause is comparing nothing.

The map is **read-only** from the moment it lands: `eval/method.md` freezes and hashes it, and a
validate/audit failure on it is a reported finding about the method, never something to repair. The
build sub-agent fixing its OWN map before it hands it over is part of the method being measured;
touching the map after it leaves the worktree is tampering.
