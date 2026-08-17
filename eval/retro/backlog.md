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


### Landed 2026-08-17 — from the mcpolis build of that morning (session `0b3af67e`)

Uncommitted in the working tree. Gates: `pytest tests eval/tests` **2,125 passed**;
`pyright tools/coyodex eval/tools` **0 errors**. Every one was verified against the real build's
artifacts, not only against a fixture.

**Measurement (`coyodex-eval`)**

| what | evidence |
|---|---|
| Assertion 31 follows a brief that lives in a file | The 15 harvest prompts were one-line pointers (`Read …/prompt-h-domain.md completely`), so the detector scored the pointer and reported 0.00 about a build whose 15 briefs ALL cite use cases. It reads 1.00 now, while the previous build — briefs inline, citing nothing — still reads 0.00. A pointer whose file is gone reads `n/a`, never 0. |
| `_COYODEX_SUBVERBS` holds every dispatched verb, and `--commands` expands a shell function | `row`, `security-row`, `dedup-security`, `lint`, `stamp`, `show` were all missing, and the scan counted a function DEFINITION instead of its calls. On the build's own transcript the table goes `fix 1` → `fix row 6`, `provenance` → `provenance stamp`, `record 8` → `record 40`; 73 invocations → 111. `test_subverbs_cover_every_dispatched_verb` reads the three dispatch tables so the next verb cannot ship missing. |
| Assertion 38 resolves a shell variable in a redirect target | The worklist was written absolutely and read four times as `$CO/verify/worklist.json`. 0/1 → 1/1. |
| Assertion 3 stops counting a lone dispatch as a failed fan-out | `of` is now batched turns plus SERIALISED one-agent turns; an isolated single-agent job is neither. 5/6 → 5/5. The serialised shape the assertion exists for still scores 0. |
| `cost` excludes coordinator round-trip idle from an agent's duration | The two "slowest" agents held 4.7 and 6.9 minutes waiting for a follow-up; the rework after each took about a minute. Slowest in the trace batch 18.9m → 16.9m, in the rules batch 15.6m → 10.6m. `Actor.span` keeps the raw figure. |

**Tools (`coyodex`)**

| what | evidence |
|---|---|
| `grounding lint\|write\|report --verdicts` is variadic, as its usage line always said | `--verdicts a.json b.json` died on `unknown option(s)`. A bare glob works now; the repeated-flag form still does. |
| `grounding lint` says how much of the pass the evidence check could test | It printed the same line with and without `--agent-transcripts`. On the real build it now says `949 verdict row(s); evidence check covered 16 of 949` — the number this retro had to compute by hand. |
| `dump` reads a flow, a sub-flow and an entry point | `--id UC29` returned `members: []` while a contract handed to 11 agents advertised it as "a use case, with its flow steps and their anchors"; `--id SF200` said `kind: unknown`; 0 of 311 entry points were addressable. All three now resolve. |
| `finalize` names a verdict-based leg it was not asked to run | A second `finalize` (for `--emit-gate-block`, without `--verdicts`) overwrote the report and dropped the leg and its `challenged N of M` coverage line. It cannot be INCOMPLETE — that verdict is for a leg that FAILED — so it is a loud advisory naming the files it found beside the map. |
| `lint-fragment` warns on an authored `runs_in` | Two harvest slices guessed unit names; their own lint passed and the lead's `validate` raised 17 blocking lines. ADVISORY, not blocking: the committed corpus has a lead-authored fragment with 35 legitimate `runs_in` rows, and a single-fragment linter cannot tell the two apart. |
| `record --remove <prefix>` | A stale record was deleted with a `python3` splice of `extras.json`. Removing the last line takes the heading with it. |
| `provenance stamp --update-header <fragment>` | Closes the 2026-08-14 proposal 10: the build hand-edited `header.json` with a heredoc because the tool only printed the string. |
| `balance --map <path>` | Exit 2 before, while `record` / `anchor-drift` / every `fix` verb take `--map`. |

**Method and templates**

| what | evidence |
|---|---|
| The ordering block names all 13 steps | It omitted `grounding report`, `provenance stamp`, the header backfill and the combined `finalize`, while calling itself the one sequence — so a compliant build wrote the grounding record twice and ran `finalize` twice. |
| `grounding lint` is named at verdict collection, with its repeated-flag shape | It appeared 0 times in `method.md`, `method/` and the skill; the lead hand-rolled half of it twice. |
| The harvest template carries the `.draft.json` rule, the do-not-author list (`runs_in` first), per-agent scratch names and the zsh quoting rule | `draft.json` appeared 0 times in the template and 0 times in all 15 dispatched prompts, so the crash-resilience rule reached no agent. |
| A `rules-contract.md` template ships | There was none, so a lead composed one from prose and told all 11 rule agents to write a `block` field `lint-fragment` treats as blocking — the failure fired in 13 of 71 agent transcripts. |
| The skeptic contract has a `«CLAIMS»` slot, plus scratch-naming and quoting rules | An N-vote batch forced the generator to append an "## Override — read this, it corrects one path above" block contradicting the body, in 6 of 30 prompts. Ten skeptics wrote to the same `build_verdicts.py` and one process wrote another skeptic's verdicts file. |
| The anchor-drift pre-pass is a GATE before the skeptic dispatch | Stated as prose it was read as advice: one build ran it once, at the end, with `--verdicts`, and paid three skeptics to report drift by hand. |
| The N≥3 vote's scope is named (the whole `security` theme), with the counter-argument | Two different cuts were written; a build guessed and 8 of its 10 refutations came from single-vote batches. |
| Shared fan-out state must live in the contract, never a per-slice option | 12 of 14 slices got the shared-machinery block; of the two that did not, one was repaired and **the other shipped uncorrected**. |
| `record --line` repeats, `--lines-from` exists, `record` seeds the extras fragment | Every example showed one `--line`; the build spawned 40 processes for 40 lines and defended against a non-problem with a truncating `echo … >`. |
| `method/diagrams.md` is in dispatch's Build reading list; `method.md` says read it in windows | It was cited as authority and never opened; two whole-file reads overflowed the result cap into files nobody opened. |
| The barrier text turn should carry what happens next | The tool-less wait turn is MANDATED and is not the defect; the 18-turn gap between naming a refutation and opening the file is. |

**Not done, deliberately**

| what | why |
|---|---|
| Assertion 10 counting tool-less barrier turns as idle | Proposed before a refuter established that `method.md` REQUIRES a tool-less text turn at a barrier. Implementing it as written would penalise compliant behaviour — the exact bug class this batch fixes. What is worth measuring is the gap between naming a refutation and verifying it, which needs a different detector. |
| `audit --batches` balancing within a theme | Real (6 batches of ≤10 claims each cost a whole fresh-context agent), untouched — it changes how every future build is sliced and deserves its own measured change. |
| A recordable heading for the minted-entry-point-kind and single-reference-sub-flow advisories | Real (5 of 11 advisories are "carried (no escape)", so CLEAN is unreachable), but it is a change to the recorded-exception vocabulary, not a bug fix. |
| `reconcile` merge mode | Still open from 2026-08-14 (proposal 6). |
| Splitting `method.md` | The windowed-read note landed instead; the split is a large structural change. |

---

## Open — tools

What is still open. Landed items move to the table above, with the commit. `scope` here means
what the change would have to read.

| # | change | why | scope |
|---|---|---|---|
| 7 | ~~`record`: repeatable `--line` / `--lines-from`, and seed the extras fragment~~ **LANDED** | The seeding half was yours; `--line` now repeats and `--lines-from <file|->` reads a batch, one process and one write. Every line is shape-checked before anything is written, so a bad one in a batch of twenty leaves the fragment untouched. |

---

## Open — build method and templates

These are `method.md` at the repo root and `method/templates/`, not the retro method.

| # | change | why |
|---|---|---|
| 1 | ~~`skeptic-contract.md` needs an explicit falsification mandate~~ **WITHDRAWN — measured, 2026-08-16** | The experiment it was gated on ran: 10 planted falsehoods, four shapes, both contracts, two skeptics each. **10/10 detection either way, zero false positives, identical verdict splits** — the wording made no measurable difference, and the hardest shape (a two-clause rule with only the second clause reversed) was caught every time. The low refutation rate is much better explained by the map being right. Write-up and answer key in `eval/experiments/`. |
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
