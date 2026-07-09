# coyodex-eval — method-quality regression for a coyodex map

Run this **inside a project that already has a coyodex map** (`.coyodex/project-map.json`). It rebuilds a
FRESH map with the current coyodex method, judges it, and compares it to that baseline — answering one
question: **did the method/tooling get better or worse?** All results go in `.coyodex-eval/`
(git-ignored, regenerable). Nothing here overwrites the curated `.coyodex/` map.

**Why the pin guard matters.** The comparison only means "the *method* changed" if the *code* is held
fixed. So the fresh map must be built from the SAME source the baseline was. The baseline map records
its commit; this method REFUSES unless you are checked out at that commit.

**Why the eval must not be able to cheat.** The eval is the validation instrument for every change to
the method — so its own integrity holes are the worst bugs it can have. Three rules close them:

1. **The builder is BLIND** (Step 2): the fresh build runs in an isolated environment that cannot see
   the baseline map, any prior eval output, or the gate thresholds. A builder that can peek at the
   baseline can (even unintentionally) steer toward its numbers.
2. **The fresh map is FROZEN before anything reads it** (Step 2): its hash is written at build time and
   every later scoring step verifies it. An edit after the build — however well-meant — invalidates
   the run.
3. **A validity failure is a FINDING, never a fixup** (Steps 2 and 5): if the frozen map fails
   `validate` or `audit`, that IS the eval result ("the method produced an invalid map"). Report it;
   never repair the map to make the run look better.

## Paths — keep them straight
- **`COYODEX_HOME`** (from the skill) — the coyodex clone: method docs, config, and the CLI
  (`COYODEX_HOME/.venv/bin/coyodex`). Config: `COYODEX_HOME/eval/thresholds.json` and
  `COYODEX_HOME/eval/rubric.md`.
- **Your cwd** — the project being evaluated. Baseline map: `.coyodex/project-map.json`. Eval data:
  `.coyodex-eval/`.

## Step 1 — Guard: baseline + pin (refuse if not aligned)
1. Require `.coyodex/project-map.json` — markdown maps are not supported. If missing → tell the
   user to run `/coyodex` first to build a baseline, then stop.
2. Read the pin from the model's `commit` / `committed` fields — the bare short sha.
3. `git rev-parse --short HEAD`. Also check the tree is clean, ignoring coyodex's own dirs:
   `git status --porcelain -- . ':(exclude).coyodex' ':(exclude).coyodex-eval'`.
   **Housekeeping exception:** if the ONLY dirty path is `.gitignore`, inspect `git diff -- .gitignore`;
   when every added/removed line does nothing but add coyodex paths (`.coyodex-eval/`, `.coyodex/`
   entries — the tool's own step-5 housekeeping below), treat the tree as clean. Any other `.gitignore`
   change still counts as dirty.
4. Alignment. `HEAD` equal to the pin is aligned — and so is `HEAD` sitting AHEAD of the pin by
   **map-only commits**: once `.coyodex/` is tracked, committing the map moves HEAD past the commit
   the map describes, so "HEAD == pin" literally never holds again (the normal state, not an error).
   The real invariant is ZERO CODE DELTA between the pin and HEAD:
   ```
   git diff <pin>..HEAD -- . ':(exclude).coyodex' ':(exclude).gitignore'
   ```
   Empty output → aligned. Non-empty output (any code changed since the pin), **or** a dirty tree →
   **REFUSE** and stop:
   > eval needs the source at the baseline's commit so a quality change means the *method* changed, not
   > the code. The baseline map is pinned at `<pin>` and this checkout carries CODE changes on top of
   > it. Check out a state with zero code delta vs the pin, in a clean tree, then re-run
   > `/coyodex-eval`.
5. Make sure `.coyodex-eval/` is git-ignored in this project (add it to `.gitignore` if absent).

## Step 2 — Build the FRESH map BLIND, then freeze it
The build happens FIRST — before the baseline is scored or even read — so no baseline numbers exist
anywhere in context while the fresh map is being written.

### The blinded-builder recipe (reusable — every phase-boundary validation uses exactly this)
This is the canonical **isolated environment** the master plan's validation loop refers to
(`internal/docs/plan/00-MASTER-PLAN.md`, "per-phase validation recipe", step 1). Reuse it verbatim
whenever a fresh map must be built without the builder seeing prior maps or eval state.

1. **Create an isolated checkout at the pin** (a scratch dir outside the project, e.g. under `$TMPDIR`):
   ```
   git -C <project> worktree add <scratch>/coyodex-eval-build <pin>
   ```
   (A `git clone <project> <scratch>/... && git checkout <pin>` works the same when worktrees are
   inconvenient.)
2. **Blind it** — remove everything the builder must not see:
   ```
   rm -rf <scratch>/coyodex-eval-build/.coyodex <scratch>/coyodex-eval-build/.coyodex-eval
   ```
   Note the map lives at HEAD, not at the pin: when the pin PREDATES the map commit (the normal
   state — the map is committed on top of the code it describes), the worktree at the pin contains
   no `.coyodex/` at all and blinding holds by construction; the `rm -rf` stays as defense-in-depth
   for the older layout where the map commit IS the pin. `.coyodex-eval/` is git-ignored and
   normally absent from a fresh worktree; remove it defensively anyway. **Dogfooding case:** if the evaluated project is the coyodex clone itself, the
   worktree also contains committed copies of the eval bundle (its own `eval/thresholds.json`,
   `eval/rubric.md`) — remove those too (`rm -rf <scratch>/coyodex-eval-build/eval`); the never-read
   rule below is path-independent, but the blinding should be filesystem-deep, not instruction-deep.
3. **Run the build in a FRESH-context sub-agent** (never in the orchestrating context, which has read
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
     `COYODEX_HOME/eval/` originals AND any committed copy inside the worktree); any `.coyodex/` or
     `.coyodex-eval/` directory anywhere. The builder sees ONLY the code at the pin plus the
     build-method docs;
   - **run every fan-out synchronously** (wait for each batch of harvest / trace / skeptic
     sub-agents within its own turn): a builder that spawns BACKGROUND children stops at each
     barrier, which silently stalls an unattended run — the first boundary validation needed three
     manual resumes for exactly this. If background fan-out is unavoidable, the orchestrator must
     watch the build agent for stops and nudge it to continue (a stalled builder looks identical to
     a long-running one from outside).
4. **Copy the result out and clean up:**
   ```
   mkdir -p .coyodex-eval/runs/<YYYY-MM-DD_HHMM>
   cp <scratch>/coyodex-eval-build/.coyodex/project-map.json .coyodex-eval/runs/<ts>/project-map.json
   git -C <project> worktree remove --force <scratch>/coyodex-eval-build
   ```

### Freeze the artifact
1. Hash the fresh map the moment it lands in the run dir:
   ```
   COYODEX_HOME/.venv/bin/coyodex-eval hash .coyodex-eval/runs/<ts>/project-map.json \
     > .coyodex-eval/runs/<ts>/map-hash
   ```
2. From this point the fresh map is **read-only**. The tool enforces the freeze at the Step-5
   `coyodex-eval run` via `--expect-map-hash "$(cat .coyodex-eval/runs/<ts>/map-hash)"` — on a
   mismatch it refuses and the run is void; rebuild (Step 2 from the top), never re-hash an edited
   file. Before judging (Step 4), re-check the hash yourself
   (`coyodex-eval hash <map> ` vs the stored `map-hash`) and abort the run if it moved — `claims` and
   `judge` have no built-in guard, and judging an edited map wastes the whole fan-out.
3. Run the checks on the frozen map. The run-dir map sits THREE levels below the repo root, so
   `validate` needs `--repo .` to resolve its repo-root-relative anchors — without it the anchors
   resolve against the run dir, every one "fails" as noise (~300 spurious warnings on a real map),
   and a genuinely broken anchor is invisible:
   ```
   COYODEX_HOME/.venv/bin/coyodex validate --check-sources --repo . .coyodex-eval/runs/<ts>/project-map.json
   COYODEX_HOME/.venv/bin/coyodex audit .coyodex-eval/runs/<ts>/project-map.json
   COYODEX_HOME/.venv/bin/coyodex render .coyodex-eval/runs/<ts>/project-map.json .coyodex-eval/runs/<ts>/project-map.md
   ```
   (The interactive diagram is served live from the model by `coyodex serve`; there is no `.html`
   file to render. The run archives `project-map.view.json` — the served viewer's data snapshot.)
   A `validate` problem or `audit` contradiction here is a **reported finding** — "the method produced
   an invalid map" — that flows into the profile and the final report. Do NOT fix the map, do not
   re-run the builder to get a cleaner one, do not soften the finding. (The build sub-agent fixing its
   OWN map before it hands it over is part of the method being measured; the orchestrator touching the
   map after freeze is tampering.)

## Step 3 — Baseline cache (score + judge the CURRENT `.coyodex/` map, once per version)
The baseline is `.coyodex/project-map.json`; its deterministic profile is cheap but its judge scores are
expensive, so cache both, keyed by the map's hash. Done AFTER the blind build so its numbers can't
leak into the build.
1. `COYODEX_HOME/.venv/bin/coyodex-eval hash .coyodex/project-map.json`; compare to
   `.coyodex-eval/baseline/map-hash`.
2. **Protocol guard (even when the hash matches):** the cached judge scores are reusable only if
   they were produced under the CURRENT judge protocol. Run
   ```
   COYODEX_HOME/.venv/bin/coyodex-eval protocol \
     --thresholds COYODEX_HOME/eval/thresholds.json --rubric COYODEX_HOME/eval/rubric.md \
     --against .coyodex-eval/baseline/judge.json
   ```
   Exit 1 (protocol changed, or the cached report records no fingerprint) → delete
   `.coyodex-eval/baseline/judge.json`; the baseline must be re-judged below. A protocol change
   must invalidate the cache, never silently reuse stale scores.
3. If the map hash is missing/different (first run, or the baseline map changed), or the judge
   cache was invalidated:
   - `COYODEX_HOME/.venv/bin/coyodex-eval score .coyodex/project-map.json --repo . --json` → save as
     `.coyodex-eval/baseline/profile.json` (skip when only the judge cache was invalidated).
   - Judge `.coyodex/project-map.json` with the **Step 4** procedure → `.coyodex-eval/baseline/judge.json`.
   - Write the hash to `.coyodex-eval/baseline/map-hash`.
4. Otherwise reuse the cached `.coyodex-eval/baseline/{profile,judge}.json`.

## Step 4 — Judge a map (used for both the baseline in Step 3 and the fresh map)
This is the real, LLM-backed judge; it runs in sub-agents (the tool never calls a model).

**The pinned judge model.** All grounding skeptics and rubric judges run on the model named in
`COYODEX_HOME/eval/thresholds.json` → `judge.grounding_model`. A comparison is only meaningful when
both sides were judged by the SAME model; if that pin ever changes, delete
`.coyodex-eval/baseline/judge.json` so the baseline is re-judged on the new model.

For a map M:
1. **The claims sample.** `COYODEX_HOME/.venv/bin/coyodex-eval claims M --json --top 40` → the top-K
   (K = 40, `judge.grounding_cap`) of the risk-ranked L2 worklist as `[{claim, anchor, detail?}]`. The
   worklist is ranked most-dangerous-first, so the cap grounds the riskiest claims and keeps cost
   bounded on a large map. Anchors are **repo-root-relative** file refs (e.g. `backend/x.py#L70` →
   `<repo>/backend/x.py`); `detail` carries each endpoint's name + source file taken from the claim
   itself.
2. **Ground — N-skeptic majority vote.** For EACH sampled claim, fan out **3 fresh-context skeptic
   sub-agents** (`judge.n_skeptics`) on the pinned model, each told to *disprove* the claim against
   the code. The claim's verdict is the majority of the usable votes — one dissenting skeptic can't
   flip it. **Every skeptic sub-agent MUST run with its working directory INSIDE the target repo**
   (the project being evaluated) — a skeptic launched elsewhere hunts the disk for the code, fails,
   and its failure masquerades as a refutation (35/240 votes in one boundary run refuted claims
   this way; 3 of them "verified" against stray map fixtures they stumbled on instead). Each
   skeptic prompt must state (this is `build_grounding_prompt`'s wording — reuse it, passing
   `repo_root` as the repo's ABSOLUTE path so the prompt names it):
   - the verdict is one of THREE: grounded=true (the code clearly supports the claim) ·
     grounded=false (you READ the relevant code and it does not support the claim; default here
     when the code leaves you unsure) · grounded="unverifiable" (you could not check against the
     code at all — repo/file not found, read failed). A lookup failure is NOT evidence: never
     refute code you did not read;
   - the repo's absolute root path, and that the skeptic's cwd is inside it;
   - judge ONLY the RELATIONSHIP the claim states — an imprecise/drifted anchor does not refute a true
     relationship (anchor exactness is the `drill_accuracy` rubric dimension, not grounding);
   - resolve names and ids ONLY from the claim text (+ its `detail`) and the code; **do NOT read any
     project-map file**.
   Collect one row per VOTE: `{claim, grounded, evidence}`, with `grounded` true, false, or the
   string `"unverifiable"`. If a skeptic returns "unverifiable" or no usable verdict (malformed
   output, no `grounded` value), retry it once — an environment hiccup is usually transient; if it
   still fails, keep the row as returned (`"unverifiable"`, or without a usable `grounded`) — the
   aggregation counts it as a **judge failure**, surfaced separately and excluded from the
   pass-rate denominator, never scored as refuted.
3. **Rubric** — 3 judge sub-agents on the pinned model, each scoring all 5 dimensions of
   `COYODEX_HOME/eval/rubric.md` 0–4 against the code, with a `file:line` per score. Hand each
   judge the map's generated MARKDOWN VIEW (render it from the frozen model:
   `coyodex render <M.json> <tmp.md>`), not the raw JSON — the view is the readable,
   content-identical rendering.
4. Write the raw verdicts `{ "grounding": [...], "judges": [...] }` to a JSON file, then aggregate:
   `COYODEX_HOME/.venv/bin/coyodex-eval judge --map M --repo . --verdicts <raw.json> --rubric COYODEX_HOME/eval/rubric.md --judge-model <the pinned model> --out <judge.json>`.
   `--judge-model` (the `judge.grounding_model` pin) is recorded in the report's judge-protocol
   fingerprint together with n_skeptics, the cap, the rubric hash, and the grounding-prompt regime
   version — the Step-3 cache guard compares it (so a prompt-rule change, like the unverifiable
   channel, automatically invalidates pre-change cached scores).
   Keep the raw JSON as provenance (`judge-verdicts.json` in the run dir). The report states the
   denominator explicitly: pass-rate over the top-K sample minus failures, with the full worklist size
   alongside.

## Step 5 — Compare + store + report
1. Compare the fresh run against the cached baseline and archive it — under the freeze guard:
   ```
   COYODEX_HOME/.venv/bin/coyodex-eval run \
     --project <repo-name> --map .coyodex-eval/runs/<ts>/project-map.json --repo . \
     --expect-map-hash "$(cat .coyodex-eval/runs/<ts>/map-hash)" \
     --thresholds COYODEX_HOME/eval/thresholds.json \
     --baseline-dir .coyodex-eval/baseline --judge <fresh judge.json> \
     --out .coyodex-eval/runs/<ts>
   ```
   A hash-mismatch refusal means the frozen map was modified — the run is void; restart from Step 2.
   Copy the fresh raw verdicts into the run dir as `judge-verdicts.json`.
2. Report to the user, **judge/quality deltas first** (grounding pass-rate with its denominator and
   failure count, rubric scores), then the verdict (PASS / DRIFT / REGRESSED) with the gates/bands
   that moved — for the component count, lead with the **granularity line** (both maps' distance to
   the code-derived expectation E; only the candidate gates) — then the raw structural counts last,
   and the path to the run's `delta.md` and `project-map.view.json`. On REGRESSED, name the gate that
   tripped. Any post-freeze validate/audit
   finding from Step 2 is part of this report — a finding about the method, not something to have
   fixed.

## Accepting a better map
The eval never touches `.coyodex/`. If a fresh map is genuinely better and you want it to become the
baseline, accept it into `.coyodex/` through the normal coyodex flow (`/coyodex accept` / replace the
map + re-pin); the next `/coyodex-eval` will re-score the new baseline (Step 3 hash mismatch).
