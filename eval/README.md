# coyodex-eval — method-quality regression harness

This package answers one question: **did a change to the coyodex method or tooling make the maps it
produces better or worse?** You keep the project's committed `.coyodex/project-map.md` as the
**baseline**; the eval rebuilds a **fresh** map with the current method and compares the two. If quality
dropped, it tells you.

Maps are LLM-written, so two builds of the same repo never match byte-for-byte (IDs, wording, ordering
drift). So the harness never diffs map *text* — it compares measurable **quality signals**.

## The two ways in

- **`/coyodex-eval` (the skill)** — the normal way. Run it inside a project and it drives the whole
  thing: guard → build a fresh map BLIND (isolated worktree, no baseline/thresholds visible) + freeze
  its hash → judge it → compare to the baseline → store the run. It's the agent-driven orchestration
  (it builds a map and spawns judge sub-agents, which the tool itself can't do). Install it with
  `make install-eval`; the recipe it follows is `eval/method.md`.
- **The `coyodex-eval` CLI commands below** — the deterministic building blocks the skill calls. You can
  also run them by hand.

## The signals it compares

- **structure** — counts of use cases, subsystems, components, entities, edges, Golden-Path steps…
- **well-formedness** — `coyodex validate` problems / warnings
- **self-consistency** — `coyodex audit` contradictions / advisories
- **coverage** — how much of the source the map actually maps
- **faithfulness (semantic)** — the LLM judge: L2 grounding pass-rate + a 5-dimension rubric (0–4)

The first four are **deterministic** (free, instant, no LLM). The judge needs a real model, so it runs
in the orchestration layer (sub-agents) and is handed in as a `judge.json` (see "The judge" below).

## Two homes — keep them straight

- **The `eval/` bundle** (this self-contained folder in the coyodex repo): the skill (`SKILL.md`), the
  method doc (`method.md`), the config (`thresholds.json`, `rubric.md`), and the code — a standalone
  `coyodex_eval` package under `tools/coyodex_eval/` exposing the `coyodex-eval` command. It depends on
  coyodex's core (schema/validate/audit) but the core has no reference back to it.
- **Data** (`.coyodex-eval/` inside each evaluated project, **git-ignored**): the fresh maps, run
  archives, judge results, and a cached scoring of the baseline. The baseline map itself is the
  project's own committed `.coyodex/project-map.md`.

```
eval/                         # the bundle (in the coyodex repo)
  README.md  SKILL.md  method.md  thresholds.json  rubric.md
  tools/coyodex_eval/         profile.py · compare.py · judge.py · run.py · cli.py
  tests/                      test_profile.py · test_compare.py · test_judge.py · test_run.py
```

```
<project>/
  .coyodex/project-map.md         # the baseline (curated, committed, pinned to a commit)
  .coyodex-eval/                  # git-ignored, regenerable
    baseline/  map-hash · profile.json · judge.json   # memoized scoring of .coyodex/, per version
    runs/<timestamp>/  project-map.md · map-hash · project-map.view.json · profile.json
                       judge.json · judge-verdicts.json · delta.md
```

## The pin guard (why the eval is trustworthy)

The comparison only means "the *method* changed" if the *code* is held fixed. The baseline map records
the commit it was built at; `/coyodex-eval` **refuses** unless your working tree is at that commit. So
before running it: `git checkout <pin>` (the pin is in the map header), then `/coyodex-eval`.

## The commands

Run them with the CLI from the repo venv (`.venv/bin/coyodex-eval …`, or `python -m coyodex_eval.cli …`).

| command | what it does |
|---|---|
| `coyodex-eval score <map.md> [--repo <src>] [--json]` | print a map's deterministic profile (structure / validate / audit / coverage). `--repo` adds coverage. |
| `coyodex-eval run --project <name> --map <map.md> [--repo <src>] [--expect-map-hash <sha256>] [--judge <judge.json>] [--baseline-dir <dir>] [--thresholds <file>] [--out <run-dir>]` | profile a built map, compare it to the baseline, archive the run (map + HTML view + profile + delta). `--expect-map-hash` is the freeze guard: it refuses a map edited after build. |
| `coyodex-eval hash <file>` | print a map artifact's sha256 freeze hash — written to `runs/<ts>/map-hash` at build time, enforced by `run --expect-map-hash`. |
| `coyodex-eval claims <map.md> [--top <K>] [--json]` | print the audit's risk-ranked L2 worklist — the claims the judge grounds. `--top K` keeps the grounding sample; `--json` is the judge orchestration's input. |
| `coyodex-eval judge --map <map.md> --verdicts <raw.json> --out <judge.json> [--repo <src>] [--rubric <file>]` | aggregate raw judge verdicts (from the sub-agents) into a `judge.json`, via the tested math. |
| `coyodex-eval bless <run-dir> <baseline-dir>` | copy a run's artifacts into a baseline dir (used to seed a cache; the real baseline is `.coyodex/`). |
| `coyodex-eval compare <baseline.json> <candidate.json> [--thresholds] [--baseline-judge] [--candidate-judge]` | low-level: compare two profiles directly. `eval run` uses this under the hood. |

**Verdict / exit code** (from `coyodex-eval run` / `coyodex-eval compare`): `0` = **PASS** (or **BASELINE**, first run,
nothing to compare) · `2` = **DRIFT** (a soft band exceeded — worth a look) · `1` = **REGRESSED** (a
hard gate tripped). Gates are **relative** to the baseline ("no *new* validate problems", not "must be
perfect"); tune them in `eval/thresholds.json`.

## Running it (normal path)

```sh
cd <project>
git checkout <pin>        # the commit in .coyodex/project-map.md's header — /coyodex-eval refuses otherwise
/coyodex-eval             # builds a fresh map, judges it, compares to .coyodex/, writes .coyodex-eval/runs/<ts>/
```

It prints the verdict and points you at the run's `delta.md` and `project-map.view.json`. **PASS** → nothing
got worse. **DRIFT** → a count/score moved a lot, look at it. **REGRESSED** → a real regression. If a
fresh map is genuinely better, accept it into `.coyodex/` the normal coyodex way (`/coyodex accept`);
the next eval re-scores the new baseline.

## The judge (the semantic signal)

The tool never calls an LLM (that keeps it dependency-free and testable). So the real judge runs in the
**orchestration layer** — sub-agents on a pinned model (`thresholds.json` → `judge.grounding_model`)
that (1) try to **disprove** the top-K risk-ranked L2 claims against the code, 3 skeptics per claim
with a majority vote → a grounding pass-rate (a skeptic that returns no usable verdict is a *failure*,
excluded from the denominator, never counted as refuted), and (2) **score** the 5 rubric dimensions
(`eval/rubric.md`) 0–4, N judges per dimension. They write a raw verdicts JSON; `coyodex-eval judge`
turns it into `judge.json` via the tested `PrecomputedJudge` path — so the numbers are trustworthy even
though the verdicts came from live models. `/coyodex-eval` does all of this for you (step 4 of
`eval/method.md`).

## The code, briefly

- `profile.py` — `MapProfile` + `build_profile` (the deterministic signals) → `coyodex-eval score`.
- `compare.py` — `Thresholds` + `compare` → the gates/bands and the PASS/DRIFT/REGRESSED verdict.
- `judge.py` — the `Judge` seam, the aggregation, and `PrecomputedJudge` (replays orchestrated verdicts).
- `run.py` — `run_eval` + archive + `bless` + `claims` → `coyodex-eval run` / `claims` / `judge` / `bless`.
- `cli.py` — the `coyodex-eval <subcommand>` dispatcher.

Everything here is stdlib-only and reuses the validator's / audit's exact parse — one grammar, no drift.
Tests: `eval/tests/test_profile.py`, `test_compare.py`, `test_judge.py`, `test_run.py`.
