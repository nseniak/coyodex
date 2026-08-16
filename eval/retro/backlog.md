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

Verified against the working tree on **2026-08-16**. Commits are on `main`, unpushed.

| what | evidence |
|---|---|
| `audit` routes an `access: true` rule site to the `security` theme | `audit_model.py` — `theme="security" if br.access else "rule"`. This was the top-ranked finding of the 2026-08-13 coworker retro: the theme the audit orders first was permanently empty after auth surfaces moved into rules, so 200 access claims triaged as ordinary ones. |
| `process_scorecard` sees a subcommand called through a shell alias, and its quote scanner no longer eats invocations | `_COYODEX_SUBCOMMANDS` now carries `grounding`/`finalize`/`record`; one quote scanner. Between them these two bugs mis-measured nine of the twenty-two scored lines on two consecutive builds. |
| `reconcile` can express the assignment the method prescribes | `reconcile_build.py` `_FIELD_OWNER` now carries `capability` and `entry_points`, matching the consumer it claims to mirror. |
| `cost --map` divides refutations by what was challenged, not by the worklist total | `cost.py` — falls back to `claims_total` only when `claims_challenged` is absent, and prints the partial denominator. The old form understated the rate by about half on both measured builds. |
| The retro method reads the per-agent transcripts, refutes its own findings, and checks the map | `method.md` in this directory (commit `6c2fb24`). |
| The map records WHICH coyodex built it; `compare` leads with the difference | `0a57a81`. Closes the cross-schema guard properly: it records the fact instead of inferring it, so it also catches tool changes that are not schema changes. |
| `balance` is reproducible | `0a57a81`. It was not: five identical runs printed three different seam lists, because equal-weight seams fell back to set iteration order. Found by a before/after harness on its first use. |
| `dump --map <path>` | `0a57a81`. |
| `lint-fragment` leads with its verdict, and runs the reciprocal domain-card check | `4d0ecd9`, `ac59f4f`. The verdict used to print last, so an agent's `head -40` hid a pass twice; the missing check let 33 blocking errors reach assembly. |
| `scope` warns when a previous map is being read as source | `4d0ecd9`. |
| `preindex --report --dirs a,b,c` | `4d0ecd9`. A ranking cannot answer "E for the slices I chose". |
| `reconcile` checks the assignment TARGET exists, and summarises | `f086f0b`. Plus `--only-unmatched`. |
| `scope` keys the stray-map warning on CONTENT, not a name prefix | `b21ef32`. It matched `.coyodex*` and so missed `map-backups/` — where this tool's own backup command writes. |
| `lint-fragment` survives a truncating pipe, and its verdict does not collide with the OK rows | `b21ef32`. |
| `preindex --dirs` normalises the path and distinguishes "exists but scores nothing" from "not a directory" | `b21ef32`. |
| The disposition table only accepts ids the MAP defines | `b21ef32`. It read `S3` out of "artifacts in S3" and `C4` out of "the C4 container view"; a false id can flip a real gap to "recorded". |
| `balance` renders the DOMAIN forest | `e75e89d`. `validate` advised on subdomain fan-out and ended "(`coyodex balance` proposes splits)" — a promise it could not keep. Surfaces four dense diagrams (13/23/22/27) on the coworker map. |
| `grounding lint` — malformed verdicts and fabricated evidence, at the skeptic | `988f51a`. `--agent-transcripts` flags a note claiming a read the agent's own transcript never made. |
| `fix row --set-json-<field>` | `8ad9758`. The four "missing verbs" were one gap: `fix row` could not carry a value that was not a string, which is why all four edits were hand-scripted. |
| Build method: SERVES slot in the harvest contract, fan-out ordering + concurrency cap, the commit step, the archive pointer, no fragment generators | `80e77e3`. |
| L3 assertions 36-39, and 26 widened to `reconcile`/`balance` | `e138a2a`. |
| A committed fragment corpus + assembly regression tests | `f9fbc05`. |
| CLI sweeps for both binaries, with completeness gates read from the dispatch | `760c80a`, `560a471`. Found a live crash in `grounding report` on its first run. |

---

## Open — tools

What is still open. Landed items move to the table above, with the commit. `scope` here means
what the change would have to read.

| # | change | why | scope |
|---|---|---|---|
| 7 | `record`: repeatable `--line` / `--lines-from -`, and create the extras fragment when absent | It reads only the first `--line`, so 51 separate process spawns in one build; and it cannot bootstrap the file, so 20 calls failed and 20 long prose lines were re-typed after an `echo '{}' >`. | `record.py` |

---

## Open — build method and templates

These are `method.md` at the repo root and `method/templates/`, not the retro method.

| # | change | why |
|---|---|---|
| 1 | `skeptic-contract.md` needs an explicit falsification mandate outweighing its WARNING block, plus a per-theme overclaim hint including a `rule` entry | The template contains no instance of *disprove*, *falsify* or "try to refute", while `method.md` says each skeptic is told to disprove the claim. Its largest block argues against refuting. Outcome: 823 verdict rows, 0 unverifiable, 6 refuted. **Run an experiment first** — inject known-false claims into a batch, or re-run an already-verdicted batch under a falsification-framed prompt. The wording is a hypothesis about the cause; changing it blind means never learning whether it was. |
| 2 | ~~The skeptic contract must require the claim's own anchor line to be opened per row, and forbid machine-generated `evidence`/`note`~~ **LANDED** `898233a` |
| 3 | ~~Make the harvest contract fillable — complete it with the row shapes, or generate it~~ **LANDED** `80e77e3` (SERVES slot; the contract is still hand-filled) |
| 4 | ~~Harvest and trace briefs must cite the UC/CAP/HP ids their slice serves~~ **LANDED** `80e77e3` |
| 5 | ~~Order a fan-out by expected minutes, not item count; size it to the harness's 20-agent cap~~ **LANDED** `80e77e3` |
| 6 | State the gate-reading rule for `balance` and `audit` explicitly | Both were narrowed. The `audit` case is already recorded in `method.md` and the build did it anyway, so restating may not be the fix — consider whether the tools should resist narrowing instead. |
| 7 | Resolve the grounding-write ordering tension; put `--keep-note` / `--note-file` in the worked example | Recording an advisory is a fragment change, but advisories only surface at the gate step after `grounding write` — so the prescribed order forces a redo loop. A 1,300-character note was re-pasted three times and mutated between pastes. |
| 8 | Say where the 3-vote majority goes — the access batches — once the tool can identify them | Blocked on tools item 1. |
| 9 | ~~Name `coyodex-eval archive` at the front door of the skill, not parenthetically~~ **LANDED** `80e77e3` |
| 10 | ~~Distinguish *launching* the pre-index from *reading* it~~ **LANDED** `898233a` |
| 11 | ~~Say plainly whether a harvest agent may author a fragment-generating program~~ **LANDED** `80e77e3` |
| 12 | ~~Name `ListAgents` in the anti-polling rule, or bless it as a cheap one-shot~~ **LANDED** `898233a` |
| 13 | When a build request includes a retro, say up front that the retro needs a fresh chat | One build reached turn 537 before finding out. |
| 14 | ~~The build must commit~~ **LANDED** `80e77e3` |

---

## Candidate L3 assertions

**Five landed as 36-39 plus a widening of 26 (`e138a2a`)**: the piped exit code, the growing gate
filter, the unread `--json`, the empty security theme, and `reconcile`/`balance` joining the gates
that may not be read as a count.

The four below are the ones the scorecard cannot yet reach: it reads the LEAD's transcript, and
these need the per-agent files or a second map. That is a change to what it consumes, not another
detector. **Tagged by what the detector must read**, because the scorecard is a lead-transcript instrument and most of
these are not — an assertion nobody can implement is a proposal that quietly dies.

| assertion | reads |
|---|---|
| Every recorded exception's `(check, id)` pair appears in the gate's live output — the inverse of 24, which catches records that silence nothing | map + gate output |
| A budget deviation that leaves the granularity band carries a `granularity` balance exception at the time | map + fan-out prompts + pre-index |
| No sub-agent narrowed its own `lint-fragment` output | per-agent transcripts |
| A verdict's `evidence`/`note` does not assert a read the agent's transcript contradicts | per-agent transcripts + verdict files |

The last one is partly built already: `coyodex grounding lint --agent-transcripts <dir>` performs
exactly that check (`988f51a`). What is missing is the scorecard reading it as a NUMBER, which needs
the same per-agent input as the one above it — so both arrive together or not at all.

---

## Sources

- 2026-08-13, coworker (`3ee6dd61`) — the retro these came from. Report was at
  `.coyodex-eval/retro/2026-08-13_0754/` in that project; git-ignored, so treat this file as the
  surviving record.
