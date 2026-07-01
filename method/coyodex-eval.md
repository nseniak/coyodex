# coyodex-eval — method-quality regression for a coyodex map

Run this **inside a project that already has a coyodex map** (`.coyodex/project-map.md`). It rebuilds a
FRESH map with the current coyodex method, judges it, and compares it to that baseline — answering one
question: **did the method/tooling get better or worse?** All results go in `.coyodex-eval/`
(git-ignored, regenerable). Nothing here overwrites the curated `.coyodex/` map.

**Why the pin guard matters.** The comparison only means "the *method* changed" if the *code* is held
fixed. So the fresh map must be built from the SAME source the baseline was. The baseline map records
its commit; this method REFUSES unless you are checked out at that commit.

## Paths — keep them straight
- **`COYODEX_HOME`** (from the skill) — the coyodex clone: method docs, config, and the CLI
  (`COYODEX_HOME/.venv/bin/coyodex`). Config: `COYODEX_HOME/method/eval/thresholds.json` and
  `COYODEX_HOME/method/eval/rubric.md`.
- **Your cwd** — the project being evaluated. Baseline map: `.coyodex/project-map.md`. Eval data:
  `.coyodex-eval/`.

The invariant after any map write is the usual `validate → audit → render` (on the fresh map's path).

## Step 1 — Guard: baseline + pin (refuse if not aligned)
1. Require `.coyodex/project-map.md`. If missing → tell the user to run `/coyodex` first to build a
   baseline, then stop.
2. Read the pin from its header (`**Commit:**` / `**Committed:**` line) — the bare short sha.
3. `git rev-parse --short HEAD`. Also check the tree is clean, ignoring coyodex's own dirs:
   `git status --porcelain -- . ':(exclude).coyodex' ':(exclude).coyodex-eval'`.
4. If `HEAD` ≠ the pin, **or** the tree is dirty → **REFUSE** and stop:
   > eval needs the source at the baseline's commit so a quality change means the *method* changed, not
   > the code. The baseline map is pinned at `<pin>`. Run `git checkout <pin>` in a clean tree, then
   > re-run `/coyodex-eval`.
5. Make sure `.coyodex-eval/` is git-ignored in this project (add it to `.gitignore` if absent).

## Step 2 — Baseline cache (score + judge the CURRENT `.coyodex/` map, once per version)
The baseline is `.coyodex/project-map.md`; its deterministic profile is cheap but its judge scores are
expensive, so cache both, keyed by the map's hash.
1. Compute a hash of `.coyodex/project-map.md`; compare to `.coyodex-eval/baseline/map-hash`.
2. If missing or different (first run, or the baseline map changed):
   - `COYODEX_HOME/.venv/bin/coyodex score .coyodex/project-map.md --repo . --json` → save as
     `.coyodex-eval/baseline/profile.json`.
   - Judge `.coyodex/project-map.md` with the **Step 4** procedure → `.coyodex-eval/baseline/judge.json`.
   - Write the hash to `.coyodex-eval/baseline/map-hash`.
3. Otherwise reuse the cached `.coyodex-eval/baseline/{profile,judge}.json`.

## Step 3 — Build the FRESH map (at the pin, into the run dir)
1. Pick a run dir: `.coyodex-eval/runs/<YYYY-MM-DD_HHMM>/` (create it).
2. Build a fresh map by following the FULL coyodex build method — read `COYODEX_HOME/method/dispatch.md`
   then `COYODEX_HOME/method.md` (+ `method/schema-v1.md`, `method/domain-cards.md`) — but write the map
   to `.coyodex-eval/runs/<ts>/project-map.md`, **not** `.coyodex/`. (Preindex's `.coyodex/preindex.json`
   is fine to write; it is regenerable scratch, not the baseline map.)
3. Enforce the invariant on the fresh map's path:
   - `COYODEX_HOME/.venv/bin/coyodex validate --check-sources .coyodex-eval/runs/<ts>/project-map.md`
   - `COYODEX_HOME/.venv/bin/coyodex audit .coyodex-eval/runs/<ts>/project-map.md`
   - `COYODEX_HOME/.venv/bin/coyodex render .coyodex-eval/runs/<ts>/project-map.md .coyodex-eval/runs/<ts>/project-map.html`

## Step 4 — Judge a map (used for both the baseline in Step 2 and the fresh map)
This is the real, LLM-backed judge; it runs in sub-agents (the tool never calls a model). For a map M:
1. `COYODEX_HOME/.venv/bin/coyodex eval claims M --json` → the L2 claims `[{claim, anchor}]`. Anchors
   are relative to the map's `.coyodex[-eval/...]` dir (e.g. `../backend/x.py#L70` → `<repo>/backend/x.py`).
2. **Ground** — one fresh-context skeptic sub-agent per claim, told to *disprove* it against the code
   (grounded=true only if the code clearly supports it; default to refuted when unsure). Collect
   `{claim, grounded, evidence}`. A workflow that fans these out is the efficient way.
3. **Rubric** — 3 judge sub-agents, each scoring all 5 dimensions of `COYODEX_HOME/method/eval/rubric.md`
   0–4 against the code, with a `file:line` per score.
4. Write the raw verdicts `{ "grounding": [...], "judges": [...] }` to a JSON file, then aggregate:
   `COYODEX_HOME/.venv/bin/coyodex eval judge --map M --repo . --verdicts <raw.json> --rubric COYODEX_HOME/method/eval/rubric.md --out <judge.json>`.
   Keep the raw JSON as provenance (`judge-verdicts.json` in the run dir).

## Step 5 — Compare + store + report
1. Compare the fresh run against the cached baseline and archive it:
   ```
   COYODEX_HOME/.venv/bin/coyodex eval run \
     --project <repo-name> --map .coyodex-eval/runs/<ts>/project-map.md --repo . \
     --thresholds COYODEX_HOME/method/eval/thresholds.json \
     --baseline-dir .coyodex-eval/baseline --judge <fresh judge.json> \
     --out .coyodex-eval/runs/<ts>
   ```
   Copy the fresh raw verdicts into the run dir as `judge-verdicts.json`.
2. Report to the user: the **verdict** (PASS / DRIFT / REGRESSED), the deltas that moved, and the path
   to the run's `delta.md` and `project-map.html`. On REGRESSED, name the gate that tripped.

## Accepting a better map
The eval never touches `.coyodex/`. If a fresh map is genuinely better and you want it to become the
baseline, accept it into `.coyodex/` through the normal coyodex flow (`/coyodex accept` / replace the
map + re-pin); the next `/coyodex-eval` will re-score the new baseline (Step 2 hash mismatch).
