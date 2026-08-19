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

Verified against the working tree on **2026-08-16**. Pushed to `origin/main` on 2026-08-19.

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

Pushed to `origin/main` on 2026-08-19. Gates at the time: `pytest tests eval/tests` **2,125 passed**;
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

### Landed 2026-08-19 — from the mcpolis build of 2026-08-18 (session `c72a44ce`)

Pushed to `origin/main`, `b267f1e..3068508`. Gates at the last commit: `pytest tests eval/tests`
**2,244 passed**; `pyright tools/coyodex eval/tools` **0 errors**. Every fix has a test that was
checked to FAIL before the change and pass after — one first draft passed with its fix removed,
because its fixture produced nothing for the failure to be re-ordered ahead of, and a test that
passes before the fix holds nothing.

**Tools (`coyodex`)**

| what | evidence |
|---|---|
| Both CLI entry points line-buffer stdout, so `2>&1 \| tail -N` keeps the FAILURE | Piped stdout is block-buffered and stderr is not, so a failure is re-ordered to the HEAD of the pipe. Three consecutive assembles aborted on a `set` directive naming a deleted rule id, the lead read the tail each time, saw a reassuring `note:`, and went on reading a map the tool had refused to write — 16 turns, taking a round of prose rewrites with it, visible only when the next good assemble dropped the long-sentence count 76 → 53. One line fixes every subcommand; `fix.py` alone has 72 stderr call sites. `bd10157` |
| `grounding report` states the still-live refuted count on its FIRST line and its LAST | `\| tail -40` started inside the refuted list and cut the section header off the top; `\| head -30` ended after the third of five bullets. The lead fixed the three it could see and **two refuted claims shipped in the map**. `bd10157` |
| `grounding write` prints a `NOTE FACTS` block | A note said "Eighteen fresh-context skeptics" of a build that dispatched 17 and produced 20 labels, and "Four superseded claims had been CONFIRMED" where the true count was 11 — seven overrides of settled verdicts undisclosed. Both numbers were computable at the moment the note was written. `bd10157` |
| `audit --json` emits `where` beside `location` | The text report prints `where:`; a script read `f.get("where")`, matched nothing, printed nothing, and the next turn redid it by grepping the text. Both keys ship; a rename would break existing readers. `66d2b39` |
| `reconcile` warns when `--out` strands the live directives | The carry-forward is keyed on `--out`, so `--out /tmp/…` silently lost keep_edges (5), drop_edges and set_anchors, and the lead hand-merged them. The tool's `Next:` hint then echoed the temp path into the suggested `assemble`. `66d2b39` |
| The flow-duplication advisory moved to `validate` only | Its escape is an extras heading read from the model being checked — one fragment under `lint-fragment`, while the heading lives in `extras.json`. A build recorded exactly the line it was asked for and got the identical warning back. `--ids` harvests id tokens, never extras. `66d2b39` |
| `finalize` runs `balance` as an INFORMATIONAL leg | A skipped Phase 3.5 and a passed one read the same. One build ran `balance` three times, the next ZERO, and nothing noticed. Never gates: method.md says balance "never gates and only ever re-groups". `66d2b39` |
| `record` refuses a line that keys to nothing | It checked the heading and the presence of a why, then wrote whatever it was given. `read-before-create HP2, read-before-create HP3: …` — the check name repeated inside a comma list — keyed zero ids; unrecorded advisories went 1 → 9 and three extra finalize+render rounds were spent finding the shape by trial. Only the lines THIS call adds are checked. `68f4b06` |
| `grounding lint --expect <batch-ids>` | A missing verdicts file is the one failure nobody spots by eye. One run printed `VERDICTS OK — 18 file(s) well-formed` while a nineteenth was landing, then ran four verdict-consuming commands against the incomplete set. `68f4b06` |
| `grounding report` lists `ADDED SINCE THE PIN` | `write` printed how many and nothing said which, so a build hand-diffed `audit --json` against the worklist in python and then hand-edited the pinned file. `68f4b06` |
| `validate` and `finalize` name `coyodex record` in a footer | Sixty advisory strings end by naming an extras heading and none said what writes one. `record` is named six times in `method.md` and the build used it ZERO times, against forty on the build before. A footer, not sixty rewritten strings, and quiet when every escape is already recorded. `8a36641` |
| `lint-fragment` runs the operative-line check, ADVISORY, with the count in the verdict | The self-check every contract names was blind to the largest defect class it produces: six hand-authored fragments printed `LINT OK — 0 problems` and the next `validate` raised 86 drifted anchors over 366 call-site anchors. Advisory for at least one build — blocking would have failed six fragments on a build that shipped clean. The count rides in the verdict because the agents read this through `head -60`, `head -20`, `head -5` and `tail -20`. `2d325cb` |
| A component's own `purpose` is an L2 claim, themed `description` | Nothing read the map's prose against the code. A map shipped `C36` saying a sign-in guard "refuses to be built at all…" beside its own `BR21` saying that guard "cannot fire" — the true reading. The rule had been challenged and corrected; the sentence next to it was in no worklist. 80 claims on that map, 500 → 580, ~$8 a build. Sorts ABOVE `backbone`: a backbone edge is at least anchor-checked, a description is read by nothing. `3068508` |

**Measurement (`coyodex-eval`)**

| what | evidence |
|---|---|
| `_python_write` sees a path bound to a variable and written through `open(var,'w')` | The dominant hand-edit shape in two measured builds, and neither the literal-path patterns nor `_VAR_BOUND_WRITE` (which covers `Path(…)` + `.write_text()`) matched it. Assertion 27 goes 36/42 → **29/63** and assertion 28's denominator 2 → **11**: the scorecard was reporting about half the hand-scripted edits, in its own favour. `68f4b06` |
| Assertion 21 says when the digest was FILTERED away rather than absent | It printed `n/a — not captured` about an assemble piped through `grep -E "ERROR\|FAILED\|Assembled"`. The digest existed and the build discarded it, which is the class assertion 37 exists to catch, reported as a clean absence. `68f4b06` |
| **Assertion 40** — no sub-agent narrowed its own `lint-fragment` output | The first assertion that reads the per-agent transcripts, because this is invisible anywhere else. 8 of 22 invocations were piped on the measured build. A `grep` FOR the string is not an invocation and is excluded — counting one inflated both halves. `68f4b06` |

**Method and templates**

| what | evidence |
|---|---|
| The retro carries FINDINGS forward and re-verifies them (Step 0b, `findings.json`) | The backlog carries proposals; nothing carried findings, and neither could say whether a landed fix changed anything. `record --line` landed and usage went 40 → 0; the rules contract landed and worker behaviour changed while the churn it targeted did not. `b267f1e` |
| Every finding carries `severity`, `fix_class` and `risk`, and **LOW risk is earned by a test** | Three different questions, collapsed into one impression by a ranked list of prose. The LOW gate moved five rows on a finished report. HIGH severity at LOW risk is the quadrant that sets the order. `e693e46` |
| Step 5b — one reader at the FINISHED report | Step 5 refutes claims mid-draft and overturned six. A separate reader on the finished report then found the most consequential defect of the whole retro (two refuted claims in the shipped map), refuted three of the report's own numbers, and killed its top-ranked proposal by quoting the method line that decided the opposite. `b44d47e` |
| The operator's `decision` is written into the ledger; the per-agent read states its coverage; a hand-rolled number is a draft until a second signal agrees | Three of one report's own figures were wrong: a path set-difference said three files were "never opened" when all had been read, a pipe count said 4 of 23 because a display truncated at 150 characters, and a per-agent read count did not reproduce. `b44d47e` |
| `method.md` names `--expect`, `ADDED SINCE THE PIN`, `REFUTED BUT NOT SUPERSEDED`, `NOTE FACTS` and `--note-file`; all three agent contracts say the lint verdict carries a drift count | Five capabilities existed that no build could reach. This is the `reconcile` class — shipped, tested, and run ZERO times across four builds. A test now checks that direction, which nothing did. `5f5e072` |
| `method.md` says what T7 block bundling costs; `dispatch.md` says the briefing comes before the first tool call | A build gave four of five rule agents two or three blocks each and spent the fresh-context-per-block property without deciding to. Another ran `scope` at turn 6 and emitted two user-facing messages in seventy turns, neither the briefing. `8a36641` |

---

## Open — tools

What is still open. Landed items move to the table above, with the commit. `scope` here means
what the change would have to read.

| # | change | why | scope |
|---|---|---|---|
| 7 | ~~`record`: repeatable `--line` / `--lines-from`, and seed the extras fragment~~ **LANDED** | The seeding half was yours; `--line` now repeats and `--lines-from <file|->` reads a batch, one process and one write. Every line is shape-checked before anything is written, so a bad one in a batch of twenty leaves the fragment untouched. |

---

### Instrumentation lesson from that investigation (2026-08-17)

Three of four hand-rolled measures over the worker logs were WRONG, and each wrong one pointed at a
different conclusion:

| the measure | what it did | how it was caught |
|---|---|---|
| classify rule workers from their prose | found 9 and 8 workers, then 2 and 0 on a second attempt | the two attempts disagreed |
| identify them by the fragment they wrote | matched `r01-…` in one build, silently ZERO in the other | the two builds name fragments differently |
| count `Read`/`Grep`/`Glob` calls | reported **1** read for a worker that read 30 files | these workers read code through `sed -n`/`grep` in Bash |
| count distinct source files named in a log | said the newer workers read MORE (38 vs 36) — the opposite of the truth | a file NAMED in the brief a worker was handed is not a file it read |

Every map-based finding held; every shaky number came from hand-parsing transcripts while
`coyodex-eval transcript` was available and unused — the method's own "reach for the verb before the
heredoc" rule, broken by the retro tooling's own author. A retro reading worker logs should use the
command, and should cross-check any per-worker number against a second signal before reporting it.

## Open — build method and templates

These are `method.md` at the repo root and `method/templates/`, not the retro method.

| # | change | why |
|---|---|---|
| 1 | ~~`skeptic-contract.md` needs an explicit falsification mandate~~ **WITHDRAWN — measured, 2026-08-16** | The experiment it was gated on ran: 10 planted falsehoods, four shapes, both contracts, two skeptics each. **10/10 detection either way, zero false positives, identical verdict splits** — the wording made no measurable difference, and the hardest shape (a two-clause rule with only the second clause reversed) was caught every time. The low refutation rate is much better explained by the map being right. Write-up and answer key in `eval/experiments/`. |
| 2 | ~~The skeptic contract must require the claim's own anchor line to be opened per row, and forbid machine-generated `evidence`/`note`~~ **LANDED** `898233a` |
| 3 | ~~Make the harvest contract fillable — complete it with the row shapes, or generate it~~ **LANDED** `80e77e3` (SERVES slot; the contract is still hand-filled) |
| 4 | ~~Harvest and trace briefs must cite the UC/CAP/HP ids their slice serves~~ **LANDED** `80e77e3` |
| 5 | ~~Order a fan-out by expected minutes, not item count; size it to the harness's 20-agent cap~~ **LANDED** `80e77e3` |
| 6 | ~~State the gate-reading rule for `balance` and `audit` explicitly~~ **ANSWERED THE OTHER WAY, 2026-08-19** | Its own note asked whether the tools should resist narrowing instead. The 2026-08-18 build answered yes: restating did not work (`balance` ran ZERO times against three on the run before), so the tools changed instead — `grounding report` states its critical count at BOTH ends, `lint-fragment` puts the drift count in the verdict, `finalize` runs `balance` itself and records it, and assertion 21 no longer reports a filtered view as `n/a`. What is still open is narrower and belongs to whoever writes a gate next: **a gate's headline number must survive both a `head` and a `tail`.** |
| 7 | Resolve the grounding-write ordering tension (**the `--note-file` half LANDED `5f5e072`**) | Recording an advisory is a fragment change, but advisories only surface at the gate step after `grounding write` — so the prescribed order forces a redo loop. The 2026-08-18 build reproduced it exactly: assertion 13 scored 0/1 with four map/fragment writes after `grounding write`, and the note was retyped inline three times (~1,900 characters). `--note-file` is now in the worked example, which fixes the retyping and not the ordering. The ordering half needs a decision: move a validate+audit read BEFORE `grounding write`, or state the loop-back explicitly. |
| 8 | ~~Say where the 3-vote majority goes — the access batches~~ **LANDED** `method.md:1478` | Verified on the 2026-08-18 build: the 40 highest-risk access claims were three-voted and the three skeptics agreed on all 40 rows, including the single refutation. |
| 9 | ~~Name `coyodex-eval archive` at the front door of the skill, not parenthetically~~ **LANDED** `80e77e3` |
| 10 | ~~Distinguish *launching* the pre-index from *reading* it~~ **LANDED** `898233a` |
| 11 | ~~Say plainly whether a harvest agent may author a fragment-generating program~~ **LANDED** `80e77e3` |
| 12 | ~~Name `ListAgents` in the anti-polling rule, or bless it as a cheap one-shot~~ **LANDED** `898233a` |
| 13 | When a build request includes a retro, say up front that the retro needs a fresh chat | One build reached turn 537 before finding out. Untouched as of 2026-08-19. |
| 14 | ~~The build must commit~~ **LANDED** `80e77e3` |
| 15 | ~~The rules contract must say that a file handed to a worker is a file to OPEN~~ **LANDED, AND IT WORKS — but the churn it targeted did not move** | `method/templates/rules-contract.md` (2026-08-17) got its first fair test on the 2026-08-18 build: **every one of the 63 files named in a rule worker's brief was opened**, against a previous build whose secrets worker opened none of its handed file. The enforcement-line churn did not follow: 116 → 115 lines with **50 in both**, 50 of a 181-line union (28%), against 57 of 222 (26%) for the pair before. So the diagnosis was incomplete, and the obvious replacement does not survive either — of the 17 files that lost coverage, 14 were in NO rule worker's brief, but access SITES did not fall (123 → 124 across 44 → 47 rules), every one of the 14 is in the map as a component `files` entry, and 8 of the 14 were mentioned inside a worker's transcript anyway. **Now question 3 below, with the experiment that would settle it.** |

---

### Open — from the mcpolis retro of 2026-08-18 (decided by the operator 2026-08-19)

Nineteen of that retro's twenty-four findings landed; these are what did not.

| # | item | decision | why it is still here |
|---|---|---|---|
| 16 | A degraded mode for a fan-out that cannot run | **undecided** | An API outage killed 19 of 61 sub-agents (four records each, zero tool calls, all launched 16:39–17:18). The lead improvised: it hand-harvested 4 of 10 harvest slices and hand-traced 6 of 8 trace slices, and lost the contract's self-check discipline with it — which is where that build's 86 drifted anchors came from. The method describes no degraded mode, so the fallback was invented under pressure. It is an ORPHAN: decisions were recorded on findings and this existed only as a proposal, so nothing ever asked about it. **The ledger should carry proposals too, not only findings.** |
| 17 | The wider prose surface | **deferred** | Component `purpose` landed as the `description` theme (80 claims). Uncut: component `evidence[].why` (371) — which carries a SECOND copy of the false sentence that motivated the whole tier — plus rule-site `why` (187), edge `why` (276) and flow step phrases (372). All of it would be 1,286 claims and roughly double a build. **Widen once the refutation rate on real descriptions is known; the next build gives that number for free.** |
| 18 | Assertion 21's sibling: an advisory whose escape is unreachable from the tool that prints it | **open** | The flow-duplication case is fixed by moving the check to `validate`. `test_method_contract` check (c) asserts an escape is read by the check that prints it and did NOT catch this one, so the check has a reach problem of its own. |

**Rejected, 2026-08-19** — recorded so they are not re-proposed: a placeholder-`purpose` warning in
`lint-fragment` (a threshold, and the harm on the measured build was zero); a rule about the grep
that dropped an `assemble` WARNING (the dangerous half is fixed by line-buffering, and what remains
is a filter habit no test can hold); and a method sentence about the post-hoc `granularity` record
(hygiene, and no test reaches a timing habit).

## Open — questions a retro could not answer

A retro's `Not assessed` block names the tool that owns each question it parked. That naming used to
be the end of it, and the report it lives in is git-ignored scratch — so the question died with the
folder. These are the parked ones, with who can answer them.

| # | question | owner | raised |
|---|---|---|---|
| 1 | Do the 44 access rules of the 2026-08-17 mcpolis map SAY what the previous map's 50 said? The deterministic half is answered — the two maps share 25 % of their enforcement lines, 17 files lost their coverage and 16 gained it, so it is neither a clean merge nor a clean loss. What no deterministic check can settle is whether the surviving statements cover the same decisions. | `/coyodex-eval` (judges) | 2026-08-17 |
| 2 | Which of the 17 files that lost access coverage hold enforcement the map should still be claiming? Two were verified by hand as real — a sign-in signature check and a credential encryption call — and one old anchor was a config constant rather than enforcement. The remaining fourteen are unread. | a human, or a targeted skeptic pass | 2026-08-17 |
| 3 | What actually causes the access enforcement-line churn? Item 15 above eliminated the diagnosis it was built on. **The experiment: re-run ONE block's rule worker with a `coyodex dump --members`-derived candidate list instead of the hand-curated one, and compare which files earn sites.** One extra agent on the next build. | the next build | 2026-08-19 |
| 4 | Do the 47 access rules of the 2026-08-18 map say what the previous map's 44 said? Same shape as question 1, for the newer pair: 50 shared enforcement lines of a 181-line union, 17 files lost, 11 gained. | `/coyodex-eval` (judges) | 2026-08-19 |
| 5 | Is one refuted-claim-in-the-map a pattern? `grounding report`'s `REFUTED BUT NOT SUPERSEDED` section found two on the 2026-08-18 map, both from a reconcile that corrected one copy of a row and left another. Nobody has looked at an older map with the same command. | anyone, one command per archived map | 2026-08-19 |

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
| ~~No sub-agent narrowed its own `lint-fragment` output~~ **LANDED as assertion 40** `68f4b06` — 8 of 22 invocations were piped on the 2026-08-18 build. It is the first assertion that reads the per-agent files, so the "change to what it consumes" is now made and the remaining two below are cheaper than they were | per-agent transcripts |
| A verdict's `evidence`/`note` does not assert a read the agent's transcript contradicts | per-agent transcripts + verdict files |

The last one is partly built already: `coyodex grounding lint --agent-transcripts <dir>` performs
exactly that check (`988f51a`). What is missing is the scorecard reading it as a NUMBER, which needs
the same per-agent input as the one above it — so both arrive together or not at all.

---

## Sources

- 2026-08-18, mcpolis (`c72a44ce`) — 24 findings, 19 landed across `b267f1e..3068508`. Report was
  at `.coyodex-eval/retro/2026-08-18_2257/` in that project, with a `findings.json` ledger beside
  it; both are git-ignored, so this file is the surviving record.

- 2026-08-13, coworker (`3ee6dd61`) — the retro these came from. Report was at
  `.coyodex-eval/retro/2026-08-13_0754/` in that project; git-ignored, so treat this file as the
  surviving record.
