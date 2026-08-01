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

A **plain-language request to change the map itself** ("move component X into subsystem Y", "rename
this subsystem", "split this component", "add a use case for…") is also a recognized input, even
without a verb — it is a **Direct map change** (Step 1, "Baseline exists", item 3), not Analyze. Do
not treat such a request as "nothing to analyze / baseline up to date".

## Step 1 — is there already a baseline?

Look **only at the working tree** of the analyzed repo for `.coyodex/project-map.json`. If the file
is not on disk, **there is no baseline — even if git history still has a committed copy.** A deleted
working-tree file is a deliberate signal to start from scratch. **Never restore, `git checkout`,
`git show`, or otherwise recover a deleted `.coyodex/` file from git; never treat a git-committed
copy as the baseline when the working-tree file is gone.** Fall through to Build below.

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
     (If only the committed `.coyodex/project-map.md` view is stale, just re-render it with
     `coyodex render … project-map.md` — that is a render, not a rebuild.)
   - **Otherwise — the source differs** (a later commit, uncommitted edits, or new files) →
     **Analyze**: read `method/change-impact.md` and follow it. The diff it computes is
     `git diff <pin>` (pin → working tree) plus any untracked files.

2. **Accept** — when the user says the report looks right, read `method/change-impact.md` (Accept).

3. **Direct map change** — the user asks, in plain language, to change the *map itself* (not driven
   by a code diff): "move component X into subsystem Y", "rename the API subsystem", "split this
   component in two", "create a subsystem for the reporting components", "add a use case for an admin
   resetting a password". This is **not** Analyze (there may be no code change to diff) — do it
   directly:
   - **Make the edit surgically to the model** (`.coyodex/project-map.json`) — the same field/array
     edits Accept applies (`method/change-impact.md`), never a rebuild.
   - **Stay grounded in the code** (the same rule as Build): a map describes what the code does, so
     reorganize / rename / re-drill what exists, but do not invent elements the code doesn't back — an
     "add a use case" only stands if there is real code and a traced flow behind it; otherwise say so
     and don't add it.
   - **Run the gates and commit**: the invariant below — **validate --check-sources → audit → render** — then commit
     the model + regenerated markdown view (a direct map change is a write like any other; the gates
     are not optional).

4. **Rebuild** — only when the user *explicitly* asks to regenerate from scratch. Warn that it
   **overwrites the existing baseline and discards its curation and pin history**, get confirmation,
   then Build as above.

## Invariant (every mode)

The map is the single source at the analyzed repo's `.coyodex/project-map.json`; the committed
`.coyodex/project-map.md` is a generated view of it (never hand-edited), and the interactive C4
diagram is served live by `coyodex serve` (not a committed file). After every write — **including a
Direct map change made at the user's request**, not only Build / Accept — the invariant is
**validate → audit → render**. Validate (`coyodex validate --check-sources`) checks schema +
semantics (and that the committed markdown view is fresh); audit (`coyodex audit`) is the adversarial
pass — it makes the narrative Happy Path and
the mechanism flows/edges refute each other. It blocks only on a hard contradiction (a forward/dangling
`why:` reference); read-before-create and actor-attribution are ADVISORY (lossy attribution — reconcile,
don't treat as fact), and it prints an L2 grounding worklist to disprove against the code with
fresh-context skeptics (see `method.md`); render (`coyodex render … project-map.md`) — the markdown
view is a rendering, never a second source, and the diagram is served on demand from the model.

**Going deeper stays in the one map.** When a part of the system needs finer detail than its current
altitude, refine it IN PLACE — nest subsystems/subdomains, or promote a leaf component into a subsystem
(see `method.md` "Drilling deeper"). The viewer drills these nested levels recursively. **Never write a
second map file** (a per-area `.coyodex/<area>/project-map.md` "child map"): a separate file is a
separate ID space, so cross-references can't resolve, bidirectional links and shared elements break, the
viewer can't drill across it, and Analyze/Accept/change-impact only ever track this one baseline. Child
maps are **not supported**.

## Waiting at a barrier (every fan-out, every phase)

This is here, in the file the skill points at, because the rule lived only in `method.md` — inside a
block introduced by "**Parallel mode covers HARVESTING ONLY … Verification is NOT part of it**", and
this file did not contain the words *poll*, *sleep*, *Monitor*, *notification*, *wait* or *barrier*
anywhere. Every build reads this file. It applies to **every** fan-out: harvest, trace, and the
Phase-4 skeptics.

**The wait is a TEXT turn. Emit no tool call at all.**

- **Never** `sleep`, `until … sleep …`, or a keep-alive like `echo ok` — foreground or backgrounded.
  A no-op turn costs a full model round trip and yields the turn no better than ending on text.
- **Never** `ls` the fragment or verdicts directory. A not-ready file reads as an error and burns
  the turn. It is also unsafe: on a live build a verdicts file was tallied 22 seconds before the
  agent writing it finished, and only luck kept the read from being truncated JSON.
- **The agents' completion notifications ARE the barrier signal.** They arrive named and carrying
  the agent's result. A live build had all fifteen and counted files anyway.
- If you genuinely must block on a condition, use the **`Monitor` tool with an until-condition** —
  and `Monitor`'s command must not itself be an `ls`/`sleep` poll. (`Monitor` is deferred: run
  `ToolSearch select:Monitor` once before the first call.) **One barrier means ONE `Monitor`.**

The measured cost of ignoring this: one build spent **88 of its 278 tool calls (32 %)** on
`sleep 1; echo ok`, 77 of them inside a single 9-minute barrier — one poll every 7 seconds — and
never called `Monitor` or `ToolSearch` once in 560 turns. The prose in `method.md` had already been
escalated twice, citing an earlier build that wasted 22 %. **L3 assertion 10 is the enforcement;
this paragraph is the courtesy.**

**Dispatch the known-longest slice FIRST** — launch order is the only lever on when a barrier
closes. Where the slices are deliberately uniform (the Phase-4 skeptic batches are capped at the
same claim count) that lever does not exist: identical 40-claim batches have run 4m54s to 10m31s,
a 2.1× spread with nothing to sort on. There, **probe the straggler** with `SendMessage` after a
couple of minutes of silence — not with a late `ls` sweep, and not by waiting out the tail.
