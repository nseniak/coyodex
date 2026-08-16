# Retro backlog — what past retrospectives proposed, and where it stands

A retrospective's report lives in the reviewed project's `.coyodex-eval/`, which is scratch: it is
git-ignored, regenerated per run, and one `git clean` from gone. The proposals in it are the durable
part. They live here.

**Step 0 of `method.md` (this directory) tells a retro to read this file before it starts.** That is
the whole point: it stops the next run re-finding what is already fixed, and it stops a proposal
quietly dying because nobody wrote it down.

**Status is dated, never trusted.** Tools move — on one occasion within hours of the report that
prompted the change. Re-check every OPEN item against the tool as it stands before you act on it or
report it, and correct the line here when you do.

Each item carries the finding it came from and what it would have to read to be implemented.

---

## Landed

Verified against the working tree on **2026-08-16**.

| what | evidence |
|---|---|
| `audit` routes an `access: true` rule site to the `security` theme | `audit_model.py` — `theme="security" if br.access else "rule"`. This was the top-ranked finding of the 2026-08-13 coworker retro: the theme the audit orders first was permanently empty after auth surfaces moved into rules, so 200 access claims triaged as ordinary ones. |
| `process_scorecard` sees a subcommand called through a shell alias, and its quote scanner no longer eats invocations | `_COYODEX_SUBCOMMANDS` now carries `grounding`/`finalize`/`record`; one quote scanner. Between them these two bugs mis-measured nine of the twenty-two scored lines on two consecutive builds. |
| `reconcile` can express the assignment the method prescribes | `reconcile_build.py` `_FIELD_OWNER` now carries `capability` and `entry_points`, matching the consumer it claims to mirror. |
| `cost --map` divides refutations by what was challenged, not by the worklist total | `cost.py` — falls back to `claims_total` only when `claims_challenged` is absent, and prints the partial denominator. The old form understated the rate by about half on both measured builds. |
| The retro method reads the per-agent transcripts, refutes its own findings, and checks the map | `method.md` in this directory (commit `6c2fb24`). |

---

## Open — tools

Ranked as the source retro ranked them. `scope` here means what the change would have to read.

| # | change | why | scope |
|---|---|---|---|
| 1 | Rank inside a theme before chunking into batches | Work items are emitted in map-rule order and cut at the cap, so which claims get three skeptics rather than one is an accident of id order. The three-vote batch held 6 access claims; two batches that were 40-of-40 access got one each. Half of this landed (the theme routing); the ranking did not. | `audit_model.py` |
| 2 | A verdict lint — reject a malformed `grounded` value, and flag machine-generated evidence | A malformed value was caught only at `grounding write`, ~100 turns after the skeptic that produced it. Separately, one skeptic generated 40 confirmations from a grep table with `note` lines citing 16 files it never opened. Both are mechanically detectable. | verdict files + per-agent transcripts |
| 3 | `finalize`: emit an advisory-disposition table — each advisory as fixed / recorded / carried | `finalize` states the rule in its own output and does not check it. Nine advisories shipped waved through, and no transcript could show it because every read of the list had been filtered. Needs no transcript: `finalize` already holds both the advisory list and the map. | `finalize.py` + map extras |
| 4 | `dump`: accept `--map` as well as positional; make an empty result distinguishable from a failure | `dump --map` exits 2 with the error on stderr. That spelling was written into the contract handed to 13 sub-agents, so the prescribed "read the map's anchors first" step could not run as written for any of them; one later read the empty output as "no record". Sibling commands are inconsistent — some take the map positionally, some take `--map`. | `dump.py`; consider normalising all subcommands |
| 5 | `lint-fragment`: add validate's reciprocal-relation (domain-card) check, and print its verdict line FIRST | The check is not imported, so 33 blocking errors could only surface after assemble. And one agent's own `head -40` cut the verdict off a run that had already passed, so it iterated twice more — a verdict-first line makes that impossible. | `lint_fragment.py` |
| 6 | `reconcile --dry-run`: validate that assignment targets exist; end with a summary; add `--only-unmatched` | Three clean dry-runs over rules naming subdomains no fragment declared; `assemble` then failed. Separately, "which rules matched nothing" cost four executions because the output is one line per rule with no summary. | `reconcile_build.py` |
| 7 | `record`: repeatable `--line` / `--lines-from -`, and create the extras fragment when absent | It reads only the first `--line`, so 51 separate process spawns in one build; and it cannot bootstrap the file, so 20 calls failed and 20 long prose lines were re-typed after an `echo '{}' >`. | `record.py` |
| 8 | `fix`: `--drop-all` / `--drop-file` for `dedup-relation`; verbs for a messaging consumers list, a rule site's `why`, an entity `states` block, and a lifecycle `states.source` | `dedup-relation` prints 33 drop tokens and demands all 33 back as separate flags — five turns went to shell word-splitting. The missing verbs are where builds hand-edit fragments, which is the failure `fix` exists to prevent. | `fix.py` |
| 9 | `preindex --report --dirs a,b,c`; `validate --json` full lists without the `+N more` truncation | `--report` ranks the top N, so the small slices a lead actually needs are never in it and it hand-parses the JSON instead. And a truncated readable list is why builds re-derive worklists by hand — one such re-derivation produced ten recorded exceptions the gate never flagged. | `preindex_lib.py`, `reporting.py` |
| 10 | `balance`: subdomain analysis, and each diagram's verdict beside the fan-out table | `validate`'s subdomain message points the reader at `coyodex balance`, which has no subdomain analysis. And the per-diagram verdicts sit ~55 lines below the table, so a `head -60` reader hand-authored 12 subsystems without seeing them. | `balance_lib.py` |
| 11 | `validate`: cross-check a use case's declared `actors` against the actor of its own flow's first step, and its name against its flow's title | A late rewrite left two use cases declaring one actor while their flows start with another, one still carrying its pre-rename flow title, and one first step belonging to a different flow. `validate` exited 0. | `validate_model.py` |
| 12 | An extras debt token that keeps counting, the way `Sweep debt` does | Recording an honest "REAL GAP" silences the coverage gate — `unclaimed: 0` — so acknowledged debt is indistinguishable from justified non-coverage. | `validate_model.py` |
| 13 | `compare`: refuse or flag a cross-schema comparison; drop the name-level note when overlap is zero | It reported REGRESSED across the breaking `security[]` → `access: true` change, on a count delta of 2 between two lists sharing no names, then printed all 46 baseline names as "dropped". | `compare.py` |
| 14 | `scope`: warn on or exclude `.coyodex*` siblings | A hand-made archive directory was counted as source — 2731 files against 2672 — so ~59 files of the previous map sat inside the harvest scope with no warning. | `scope.py` |

---

## Open — build method and templates

These are `method.md` at the repo root and `method/templates/`, not the retro method.

| # | change | why |
|---|---|---|
| 1 | `skeptic-contract.md` needs an explicit falsification mandate outweighing its WARNING block, plus a per-theme overclaim hint including a `rule` entry | The template contains no instance of *disprove*, *falsify* or "try to refute", while `method.md` says each skeptic is told to disprove the claim. Its largest block argues against refuting. Outcome: 823 verdict rows, 0 unverifiable, 6 refuted. **Run an experiment first** — inject known-false claims into a batch, or re-run an already-verdicted batch under a falsification-framed prompt. The wording is a hypothesis about the cause; changing it blind means never learning whether it was. |
| 2 | The skeptic contract must require the claim's own anchor line to be opened per row, and forbid machine-generated `evidence`/`note` | See the fabricated-evidence case above. "Read the file" is not the same instruction as "read this claim's anchor". |
| 3 | Make the harvest contract fillable — complete it with the row shapes, or generate it | The dispatched contract is a hand-merge of the template and `method.md` every build. It contradicts the schema on one field, and the fill stripped the two links to the document explaining the rule an agent then reverse-engineered from the validator's source. |
| 4 | Harvest and trace briefs must cite the UC/CAP/HP ids their slice serves | Assertion 31 scored 0 on two consecutive builds: zero of 14 harvest and zero of 13 trace briefs cite one. Every slice boundary was a directory boundary, and the structural harvest came back with no attachment to the behavioral layer. |
| 5 | Order a fan-out by expected minutes, not item count; size it to the harness's 20-agent cap | Three of 23 dispatches were rejected by the cap and re-sent late; one became the straggler. Claim count is a poor predictor of duration — but note the evidence for a per-theme cost factor is one build, so build it from more data before encoding it. |
| 6 | State the gate-reading rule for `balance` and `audit` explicitly | Both were narrowed. The `audit` case is already recorded in `method.md` and the build did it anyway, so restating may not be the fix — consider whether the tools should resist narrowing instead. |
| 7 | Resolve the grounding-write ordering tension; put `--keep-note` / `--note-file` in the worked example | Recording an advisory is a fragment change, but advisories only surface at the gate step after `grounding write` — so the prescribed order forces a redo loop. A 1,300-character note was re-pasted three times and mutated between pastes. |
| 8 | Say where the 3-vote majority goes — the access batches — once the tool can identify them | Blocked on tools item 1. |
| 9 | Name `coyodex-eval archive` at the front door of the skill, not parenthetically | Four turns went to discovering it; before that the map was archived by hand into a directory `scope` then counted as source. |
| 10 | Distinguish *launching* the pre-index from *reading* it | Backgrounding it before the behavioral draft is strictly better, and GR1's wording reads as banning it. |
| 11 | Say plainly whether a harvest agent may author a fragment-generating program | Six of 14 did. It predicts nothing about speed, but it changes what every lint round costs, and nothing sanctions or bans it. |
| 12 | Name `ListAgents` in the anti-polling rule, or bless it as a cheap one-shot | A third variant of the banned wait shape that the current wording does not name. |
| 13 | When a build request includes a retro, say up front that the retro needs a fresh chat | One build reached turn 537 before finding out. |
| 14 | The build must commit | `.coyodex/` was left untracked. Assertions 12 and 18 have never had an opportunity to score on that project, and the durable record the method relies on does not exist. |

---

## Open — candidate L3 assertions

Each is a repeatable process defect a real run showed that no current number watches. **Tagged by
what the detector must read**, because the scorecard is a lead-transcript instrument and most of
these are not — an assertion nobody can implement is a proposal that quietly dies.

| assertion | reads |
|---|---|
| A gate's exit code is not read through a pipe | lead transcript |
| A gate's output filter GREW between consecutive runs of the same gate (the measurable form of withdrawn assertion 19) | lead transcript |
| A `--json` output that was written is read | lead transcript |
| `reconcile`'s output is not read as a bare count — extend assertion 26's gate list | lead transcript |
| Every recorded exception's `(check, id)` pair appears in the gate's live output — the inverse of 24, which catches records that silence nothing | map + gate output |
| The `security` theme is non-empty when the map carries `access: true` rules | map |
| A budget deviation that leaves the granularity band carries a `granularity` balance exception at the time | map + fan-out prompts + pre-index |
| No sub-agent narrowed its own `lint-fragment` output | per-agent transcripts |
| A verdict's `evidence`/`note` does not assert a read the agent's transcript contradicts | per-agent transcripts + verdict files |

---

## Sources

- 2026-08-13, coworker (`3ee6dd61`) — the retro these came from. Report was at
  `.coyodex-eval/retro/2026-08-13_0754/` in that project; git-ignored, so treat this file as the
  surviving record.
