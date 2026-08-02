# coyodex-eval — method-quality regression for a coyodex map

**For the coyodex DEVELOPER, not for users of coyodex.** It answers "did my change to the
method or the tooling make the maps worse?", which is a question only someone changing
coyodex asks. A user's map evolves incrementally alongside their code; the repeated rebuilding
this depends on is a developer habit.

It compares **two maps of the same code** — the project's current `.coyodex/project-map.json`
against one of its archived predecessors in `.coyodex/dev-rebuilds/NNNN/` — and reports whether the
method got better or worse. All results go in `.coyodex-eval/` (git-ignored, regenerable). Nothing
here writes `.coyodex/`.

**It never builds a map.** `/coyodex` is the builder; this scores what is already on disk. The loop:

```
COYODEX_HOME/.venv/bin/coyodex-eval archive .   # move the current map to .coyodex/dev-rebuilds/NNNN/
/coyodex                                        # rebuild from scratch with the current method
/coyodex-eval                                   # compare the new map against that archive
```

Why the build is not part of the eval: `/coyodex` **is** the thing being measured, so a second build
path here would be a copy that drifts from it; and driving a build from inside the eval required a
blind isolated-worktree orchestration whose background fan-out silently stalled unattended runs.
The archive already holds every previous map, so there is nothing left for the eval to build.

## What this takes on trust
The eval scores maps. It cannot see how they were made, and two preconditions are yours to hold:

- **The rebuild must not read `.coyodex/dev-rebuilds/`.** The archived map is the answer key. A
  rebuild in a fresh session is blind in practice — `archive` moves the map out of the working tree,
  `dev-rebuilds/` is git-ignored, and no build path reads it — but nothing stops an agent that goes
  looking. When a build must be **provably** blind (a phase-boundary validation), build it with
  `COYODEX_HOME/eval/blind-build.md` and pass its map to Step 1 as an explicit path.
- **Both maps must describe the same code.** That one the eval does enforce — Step 1.

## Rules that keep a run honest
1. **Both maps are READ-ONLY.** Never edit a map to improve a number; a map edited mid-run voids the
   run. Know what is actually enforced, though: `run --expect-map-hash` guards **only the candidate**,
   and only at the comparison. The baseline map file is never re-opened there — only its cached
   scores are read — so the baseline's freeze is yours to hold, via the cache check in Step 3.1.
2. **A validity failure is a FINDING, never a fixup.** If a map fails `validate` or `audit`, that IS
   a result — "the method produced an invalid map". Report it; never repair the map, and never
   rebuild to get a cleaner one.
3. **Same code both sides** (Step 1) and **same judge model both sides** (Step 4). A comparison where
   either differs is not a method comparison.

## Paths — keep them straight
- **`COYODEX_HOME`** (from the skill) — the coyodex clone: method docs, config, and the CLIs
  (`COYODEX_HOME/.venv/bin/coyodex`, `COYODEX_HOME/.venv/bin/coyodex-eval`). Config:
  `COYODEX_HOME/eval/thresholds.json` and `COYODEX_HOME/eval/rubric.md`.
- **Your cwd** — the project being evaluated. Current map: `.coyodex/project-map.json`. Archived
  maps: `.coyodex/dev-rebuilds/NNNN/project-map.json`. Eval data: `.coyodex-eval/`.

## Step 1 — Pick the two maps, then guard
**Candidate** = the current map, **baseline** = the archived one. That direction matters: the gates
are relative to the baseline, so "the new map lost something the old one had" is what trips
REGRESSED.

1. **Candidate.** `.coyodex/project-map.json`. Missing → tell the user to run `/coyodex` first, then
   stop. Markdown maps are not supported.
2. **Baseline.** By default the newest archive — the highest-numbered directory:
   ```
   ls -d .coyodex/dev-rebuilds/*/ | sort | tail -1
   ```
   The numbers are zero-padded and monotonic, so a lexical sort is a recency sort. The user may name
   another (`0002`, "the first one"). No `dev-rebuilds/` at all → there is nothing to compare
   against: show the user the loop at the top of this doc and stop.
   **Either side may be overridden with an explicit map path** — that is how a map built by
   `blind-build.md`, or any two archives, get compared.
3. **Distinctness.** `coyodex-eval hash` both. Identical hashes → the same map twice; say so and stop.
4. **Same-code guard.** Read each map's pin from its `commit` / `committed` header field — call them
   `P_base` and `P_cand`.

   **First, refuse a `-dirty` pin outright.** A build over uncommitted code records its pin as
   `<short-sha>-dirty` (`method.md`, the scope step), and that suffix is the ONLY record that the map
   describes code no commit contains. Do **not** strip it to compare bare shas: stripping turns
   "describes code that exists nowhere" into "describes `abc123`", which then matches a clean
   checkout of `abc123` and sails through every check below. The map's anchors would point at code
   that is not there, inflating its validate problems and coverage flags — and because every hard
   gate reads "the candidate must not be *worse* than the baseline", an artificially bad **baseline**
   is a free pass for the candidate. This one is **not overridable**; the code it describes is gone.

   Then all four must hold:
   - **zero code delta between the two pins** — `git diff <P_base>..<P_cand> -- . ':(exclude).coyodex'`
     empty. Note this is a delta test, NOT `P_base == P_cand`: once `.coyodex/` is tracked, committing
     a map moves HEAD past the commit that map describes, so consecutive maps normally carry
     *different* pins with identical code between them. Requiring equality would refuse the ordinary
     archive → rebuild → compare loop, and a guard that cries wolf on the happy path just teaches
     everyone to override it;
   - the tree is **clean**, ignoring coyodex's own dirs:
     `git status --porcelain -- . ':(exclude).coyodex' ':(exclude).coyodex-eval'`.
     **Housekeeping exception:** if the ONLY dirty path is `.gitignore`, inspect
     `git diff -- .gitignore`; when every added/removed line does nothing but add coyodex paths
     (`.coyodex-eval/`, `.coyodex/` entries — step 5 below), treat the tree as clean. Any other
     `.gitignore` change still counts as dirty;
   - **zero code delta between `P_cand` and `HEAD`**:
     ```
     git diff <P_cand>..HEAD -- . ':(exclude).coyodex'
     ```
     empty. `.gitignore` is deliberately **not** excluded here. The analysed file set comes from
     `git ls-files --exclude-standard`, so a committed `.gitignore` change silently rescopes the tree
     the maps are measured against — verified: adding one directory to a `.gitignore` moved the walk
     from 24 files to 13 and E from 3 to 2, with every other clause green. If the only difference is
     coyodex housekeeping, apply the same content test as the clause above rather than excluding the
     file;
   - **the analysis scope is unchanged** — `git diff <P_base>..HEAD -- .coyodex/.ignore` empty.
     `.coyodex/.ignore` declares which committed code the map is not meant to describe;
     `iter_source_files` honours it, so it sets the coverage denominator AND the code-derived
     component expectation E. On this repo, removing it took E from 14 to 37 (+164%) and flipped the
     current map's granularity band from DRIFT to PASS with no change to map or code. The other
     clauses all exclude `.coyodex/` wholesale, so this file needs its own check.

   **Why any of this.** Both maps are scored against the **working tree**: `validate --check-sources`
   resolves anchors there, coverage reads it, and the grounding skeptics read it. If the checkout is
   not the code both maps describe, the older map's anchors miss, coverage flags spike, and skeptics
   refute claims that were true when the map was written. The numbers then move because the CODE
   moved — the one thing a method eval must never confuse with a method change.

   Any clause failing → **REFUSE** and stop:
   > eval compares two maps of the SAME code, so a quality change means the *method* changed, not the
   > code. `<what failed — code differs between the two maps' pins / the tree is dirty / HEAD carries
   > code changes on top of the candidate's pin / .coyodex/.ignore changed>`. Get to a clean tree
   > with zero code delta, then re-run `/coyodex-eval`.

   **Override** (never available for a `-dirty` pin). If the user insists on running anyway ("run it
   anyway", "I know the code differs"), run it — under three conditions, all of them required:
   - **the report leads with the stamp**:
     > INFORMATIONAL — the two maps describe different code (`<P_base>` vs `<P_cand>`, N files
     > differ). Counts, coverage and grounding mix code change with method change; this is not a
     > method verdict.
   - **nothing is written to the Step-3 cache.** Score and judge into the run directory instead
     (`.coyodex-eval/runs/<ts>/informational/`). The cache is keyed by map hash alone, so an entry
     written from a rejected tree is indistinguishable from a good one and would be reused, unnoticed,
     by the next honest run — which would then report a clean PASS built on numbers that were never
     valid. The cache must only ever hold scores computed under a guard that PASSED;
   - **the run directory records it**: write `.coyodex-eval/runs/<ts>/INFORMATIONAL` containing both
     pins and the reason. `delta.md` says `Verdict: PASS` in the same words either way, so without
     this file an overridden run is indistinguishable from an honest one to anyone reading it later
     — including you, next month.

   An overridden run is never reported as a clean PASS or REGRESSED, and is never blessed into a
   cache or quoted as a method result.
5. Make sure `.coyodex-eval/` is git-ignored in this project (add it to `.gitignore` if absent).

## Step 2 — Freeze both maps, then check them
No build happens here, but the maps still get frozen: everything downstream must be scoring the exact
bytes that were picked in Step 1.

1. Hash each map and keep both digests for the rest of the run:
   ```
   COYODEX_HOME/.venv/bin/coyodex-eval hash <map>
   COYODEX_HOME/.venv/bin/coyodex-eval hash .coyodex/project-map.json \
     > .coyodex-eval/runs/<YYYY-MM-DD_HHMM>/map-hash        # the candidate's, kept on disk
   ```
   From here both maps are **read-only**. The Step-5 `coyodex-eval run` re-verifies the candidate via
   `--expect-map-hash` and a mismatch voids the run — but that is the LAST step, and `claims` /
   `judge` have no hash guard of their own. So **re-check both hashes yourself immediately before
   judging** (Step 4) and abort if either moved: judging an edited map wastes the entire skeptic
   fan-out, which is the expensive part of the run.
2. Run the checks on **each** map. An archived map sits three levels below the repo root, so
   `validate` needs `--repo .` to resolve its repo-root-relative anchors — without it every anchor
   "fails" as noise (~300 spurious warnings on a real map) and a genuinely broken one is invisible.
   Pass `--repo .` on both sides so the two are measured identically:
   ```
   COYODEX_HOME/.venv/bin/coyodex validate --check-sources --repo . <map>
   COYODEX_HOME/.venv/bin/coyodex audit <map>
   COYODEX_HOME/.venv/bin/coyodex render <map> <run-dir>/<name>.md
   ```
   A `validate` problem or an `audit` contradiction is a **reported finding** that flows into the
   final report — see rule 2. (The interactive diagram is served live from the model by
   `coyodex serve`; there is no `.html` file to render. The run archives `project-map.view.json` —
   the served viewer's data snapshot.)

## Step 3 — Score and judge each map, cached by map hash
The deterministic profile is cheap; the judge scores are expensive. Both are cached per map, keyed by
the map's own hash, so the **same** mechanism serves both sides — and the map you score as the
candidate today is already scored when it becomes the baseline of the next round.

Cache layout, one directory per map:
```
.coyodex-eval/cache/<first 12 chars of the map hash>/
    map-hash · profile.json · judge.json · judge-verdicts.json
```

For each of the two maps, in this order:
0. **Verify the cache entry belongs to this map.** Recompute the map's hash and check it against the
   `map-hash` file in the cache directory; on a mismatch, treat the entry as absent and rebuild it.
   No tool reads that file — the directory NAME is the only link between an entry and its map, and a
   name is not a checksum. Without this, a cache directory whose contents came from a different map
   is undetectable, and it is the baseline's only freeze check (rule 1).
1. If the cache directory exists, **guard the cached judge** — reusable only if produced under the
   CURRENT judge protocol:
   ```
   COYODEX_HOME/.venv/bin/coyodex-eval protocol \
     --thresholds COYODEX_HOME/eval/thresholds.json --rubric COYODEX_HOME/eval/rubric.md \
     --against .coyodex-eval/cache/<sha12>/judge.json
   ```
   Exit 1 (the protocol changed, or the cached report records no fingerprint) → delete that
   `judge.json`; the map must be re-judged. A protocol change must invalidate the cache, never
   silently reuse stale scores.
2. Missing `profile.json` → `COYODEX_HOME/.venv/bin/coyodex-eval score <map> --repo . --json` and
   save it there.
3. Missing `judge.json` → judge the map with **Step 4** and save it there.
4. Write the digest to `map-hash`.

A cache hit on both maps means the run costs nothing but the comparison — the normal state when you
re-run an eval without rebuilding.

## Step 4 — Judge a map (used for both maps in Step 3)
This is the real, LLM-backed judge; it runs in sub-agents (the tool never calls a model).

**The pinned judge model.** All grounding skeptics and rubric judges run on the model named in
`COYODEX_HOME/eval/thresholds.json` → `judge.grounding_model`. A comparison is only meaningful when
both maps were judged by the SAME model; if that pin ever changes, the Step-3 protocol guard
invalidates the cached scores and both maps are re-judged on the new model.

For a map M:
1. **The claims sample.** `COYODEX_HOME/.venv/bin/coyodex-eval claims M --json --top 40` → the top-K
   (K = 40, `judge.grounding_cap`) of the risk-ranked L2 worklist as `[{claim, anchor, detail?}]`. The
   worklist is ranked most-dangerous-first, so the cap grounds the riskiest claims and keeps cost
   bounded on a large map. Anchors are **repo-root-relative** file refs (e.g. `backend/x.py#L70` →
   `<repo>/backend/x.py`); `detail` carries each endpoint's name + source file taken from the claim
   itself. The worklist is "actually-does" behavioral claims (auth surfaces, C→E writes/reads) — it
   does **not** include E↔E domain-relation notes, so a relation's `{how}` note and its `keyed_by`
   storage key are **not** sent to the skeptic (a correct `keyed_by` may be rewarded by the domain
   rubric, but it is never grounded here — same stance as `{how}`).
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
     project-map file**;
   - the **evidence** is the ONE `file:line` where the operation the claim describes **actually
     happens** (the true call site), so it is directly comparable to the map's stored anchor. Reporting
     the true line does NOT change the grounded verdict — it feeds the deterministic drift check below.
   Collect one row per VOTE: `{claim, grounded, evidence}`, with `grounded` true, false, or the
   string `"unverifiable"`. **After grounding, run `coyodex anchor-drift --map <map> --verdicts <the
   {claim,grounded,evidence} rows>`** — a deterministic Layer-2 check that flags any CONFIRMED claim
   whose stored `where` drifts from the line the skeptics found; the eval records `anchor_drift_rate` in
   `judge.json` (informational). The LLM only observed the line; the drift judgment is deterministic. If a skeptic returns "unverifiable" or no usable verdict (malformed
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
   Keep the raw JSON as provenance — `judge-verdicts.json` beside the map's cached scores, and copied
   into the run dir for the candidate. The report states the denominator explicitly: pass-rate over
   the top-K sample minus failures, with the full worklist size alongside.

## Step 5 — Compare + store + report
1. Compare the candidate against the baseline's cached scores and archive the run — under the freeze
   guard:
   Derive both cache paths with command substitution rather than transcribing them — they are named
   by 12 hex characters, and a hand-copied one is a transposition away from pointing nowhere:
   ```
   BASE=$(COYODEX_HOME/.venv/bin/coyodex-eval hash <baseline map> | cut -c1-12)
   CAND=$(COYODEX_HOME/.venv/bin/coyodex-eval hash .coyodex/project-map.json | cut -c1-12)
   COYODEX_HOME/.venv/bin/coyodex-eval run \
     --project "<repo-name> — current vs dev-rebuilds/<NNNN>" --project-key <repo-name> \
     --map .coyodex/project-map.json --repo . \
     --expect-map-hash "$(cat .coyodex-eval/runs/<ts>/map-hash)" \
     --thresholds COYODEX_HOME/eval/thresholds.json \
     --baseline-dir ".coyodex-eval/cache/$BASE" \
     --judge ".coyodex-eval/cache/$CAND/judge.json" \
     --out .coyodex-eval/runs/<ts>
   ```
   `--project` is the human label in the report (it names both sides); `--project-key` is what the
   thresholds file is looked up by, so per-project gates keep working. A hash-mismatch refusal means
   the candidate map was modified during the run — the run is void; restart from Step 1.
   Copy the candidate's raw verdicts into the run dir as `judge-verdicts.json`.

   **A verdict of `BASELINE` is a VOID run, never a result.** It means no baseline profile was
   loaded, so nothing was compared — and its exit code is 0, the same as PASS. `run` now refuses a
   `--baseline-dir` that is missing or empty, but if `BASELINE` ever reaches you, report it as a
   broken run and fix the path; never pass it on as "nothing got worse".
2. Report to the user. Lead with **what was compared** — both map paths, both commits, and the
   INFORMATIONAL banner if the Step-1 guard was overridden. Then **judge/quality deltas first**
   (grounding pass-rate with its denominator and failure count, rubric scores), then the verdict
   (PASS / DRIFT / REGRESSED) with the gates/bands that moved — for the component count, lead with
   the **granularity line** (both maps' distance to the code-derived expectation E; only the
   candidate gates); mention the use-case-granularity fields (max_flow_len / flows_over_band_pct /
   subflows) when they moved notably — then the raw structural counts last, and the path to the run's
   `delta.md` and `project-map.view.json`. On REGRESSED, name the gate that tripped. Any
   validate/audit finding from Step 2 is part of this report — a finding about the method, not
   something to have fixed.

## After the run
The eval never writes `.coyodex/`, so there is nothing to accept: the map it judged as the candidate
IS the project's current map already.

- **Better** — keep going. Nothing to do.
- **Worse** — the previous map is intact in `.coyodex/dev-rebuilds/<NNNN>/`; restore it by hand if
  you want it back, and fix the method before the next rebuild.
- **Next round** — `coyodex-eval archive .`, `/coyodex`, `/coyodex-eval` again. The map you just
  judged becomes the next baseline, with its scores already in the cache.
