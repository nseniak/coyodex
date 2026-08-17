# coyodex-retro — a retrospective on one finished build

A build just ran. Two artifacts survive it: the **map** it produced and the **transcript** that
produced it. This method reads both and reports what the run says about the tools and the method.

**Report only.** Change nothing **on disk** — no map edit, no tool fix, no method edit. Every finding
is a proposal the user decides on. Saying "I would change X" is the deliverable; changing X is not.
In-memory experiments against the tools are the exception and are encouraged: Step 2 prescribes one.

**Why it is not `/coyodex-eval`.** That one REBUILDS the map blind and judges it against a
baseline: *did quality regress?* This one never builds anything. It asks a different question —
*what did this run reveal?* — and its answer is a list of bugs, friction and gaps. The two are
complementary; neither replaces the other.

## Paths — keep them straight

- **`COYODEX_HOME`** — the coyodex clone (the skill substitutes the real path). The CLI is
  `COYODEX_HOME/.venv/bin/coyodex` and `COYODEX_HOME/.venv/bin/coyodex-eval`; the method under
  audit is `COYODEX_HOME/method.md` + `COYODEX_HOME/method/`.
- **The reviewed project** — your cwd. Map in `.coyodex/`, previous maps in
  `.coyodex/dev-rebuilds/NNNN/`, output in `.coyodex-eval/retro/<timestamp>/`.

**`dev-rebuilds/` is a coyodex-DEVELOPER convention and nothing a user of coyodex should have.** A
user's map evolves incrementally with their code, so a from-scratch rebuild is a first-run event and
they never accumulate previous maps. Rebuilding repeatedly is what someone changing coyodex does, and
`coyodex-eval archive` is what files each snapshot. No production code path reads the
directory — a *build* compares against nothing, deliberately. So expect it in the coyodex author's own
repos and expect it to be ABSENT everywhere else; when it is missing, say Step 1's comparison was
skipped rather than treating it as a defect.

---

## Step 0a — Run this in a NEW chat, not the build's own

**If this retro is running in the same session that built the map, STOP and say so.** Check
`$CLAUDE_CODE_SESSION_ID` against the `session_id` in `.coyodex/provenance.json`; if they match, the
retro is invalid and must not proceed.

Three reasons, and the first is mechanical:

1. **It would read the file it is writing.** A transcript is named after its session, and the
   session is the chat. Running here appends the retro's own turns to the `.jsonl` under analysis,
   so the process scorecard counts the retro's commands as part of the build.
2. **Fresh context is the point** — the same reason Phase 4 uses fresh-context skeptics. An agent
   that built the map inherits its own blind spots: it knows why it wrote that workaround, so it
   reads as the obvious thing to do rather than as friction.
3. **Context budget.** A build is 300–500 turns. Reading it in slices AND fanning out sub-agents
   needs headroom a spent context does not have.

Tell the user to open a new chat in the same project and run `/coyodex-retro` there.

## Step 0 — Locate the run, and refuse clearly if you cannot

```
.coyodex/project-map.json        the map to review
.coyodex/provenance.json         names the session that built it
```

**First, refuse if the build has not finished:**

```
COYODEX_HOME/.venv/bin/coyodex-eval retro-precheck        # exit 1 = do not proceed
```

**Run it bare — never pipe it.** `cmd | tail -3; echo $?` reports `tail`'s status, so a REFUSED
precheck reads as exit 0. A live run printed `PRECHECK_EXIT=0` over the words "REFUSED — provenance
names THIS session". Capture to a file if you want the message and the code.

Step 0a's same-session guard does NOT cover this, and the gap is silent. Provenance is stamped near
the END of a build, so while one is running it still names the PREVIOUS build — a different session
id from yours, so the guard passes, the retro proceeds, and every finding is about the wrong run
with nothing saying so. `retro-precheck` refuses a half-written map, refuses while another
session's transcript is still being written, and — the case the transcript scan cannot see — refuses
while anything under `.coyodex/` is still being written.

**That last check is the one that matters most, because provenance being fresh does not mean the
build is over.** A build stamps provenance and then keeps going: recording advisories, `finalize`,
`render`, the commit. On the 2026-08-01 mcpolis build, provenance said 14:57 and the map was still
being rewritten at 15:43. The transcript scan is blind to it by construction — it must skip the
session provenance names, or the retro would refuse forever after every build — so for 46 minutes
the only answer available was "safe to proceed". Watching the build's own output closes it, and
survives the operator carrying on chatting in the build window after the commit.

Do not hand-roll this wait. The one live attempt used `find -newermt '-120 seconds'`, which this
platform's `find` rejects outright — so the idle test silently read as "always idle" — and it waited
on a `dev-rebuilds/NNNN/` directory that **a build never creates** (archiving is
`coyodex-eval archive`, a developer convention; see the note above). Both conditions were
unsatisfiable, and the finished build went unnoticed for ~90 minutes. Poll the command instead, from
a background waiter, and read its exit code.

Read `provenance.json`. Its last `sessions[]` entry carries the `session_id` and `built_at` of the
build. The transcript is:

```
~/.claude/projects/<slug>/<session_id>.jsonl
```

where `<slug>` is the project's absolute path with every `/` replaced by `-`. **Derive it; do not
guess and do not pick "the newest file"** — several sessions can share a directory, and the newest
one is often the retro itself.

**Locate the per-agent transcripts too — that is where most of the evidence is:**

```
~/.claude/projects/<slug>/<session_id>/subagents/agent-<id>.jsonl      one per sub-agent, full internal turns
~/.claude/projects/<slug>/<session_id>/subagents/agent-<id>.meta.json  which agent that id was
```

Every sub-agent a build fans out keeps a full transcript here — the tools it called, the files it
opened, what it wrote. `coyodex-eval cost` has read them all along and says why in its own `--help`:
they are "~80% of the spend — a reader that opens only the session file measures the lead and misses
the build." That holds for a reader looking for friction too.

Everything a slice reader says about what an agent *did* is otherwise an inference from the text that
agent chose to return, and those inferences go wrong. Step 3 says which of these files to open.

**If the directory is absent, say so and carry on** — a different harness, or a build with no
fan-out, leaves nothing here. Then every agent-level finding is an inference, and the report must say
so rather than imply the agents were checked.

Also locate, for comparison (all optional — say so when absent):

- **the previous map** — the highest-numbered `.coyodex/dev-rebuilds/NNNN/project-map.json`. That is
  where `coyodex-eval archive` puts the map a from-scratch rebuild replaced. Names are zero-padded, so a
  plain sort is a numeric sort; take the last one.
- **the previous transcript** — the `session_id` in that archive's own `provenance.json`.

Stop and say what is missing if the map or the provenance is absent. A retro with no transcript can
still do Steps 1 and 6, and must say that Steps 2–5 were skipped — including the
`Verification status` block, which has nothing to report.

**Then read the backlog and the previous retro, before you create your own directory.**

`COYODEX_HOME/eval/retro/backlog.md` is the durable record of what past retros proposed and where
each item stands. Read it first — it is tracked, whereas a report is not: `.coyodex-eval/` is
git-ignored scratch, one `git clean` from gone, which is exactly why the backlog exists.

Then, if the reviewed project still has one, take the highest-numbered directory under
`.coyodex-eval/retro/` — noting that once you create yours, the newest one is yours, the same trap
this step already warns about for transcripts — and read its `Proposals` for anything the backlog
has not absorbed.

Do this FIRST, not at the end. It changes what the rest of the retro looks for, and skipping it
wastes a fan-out re-finding what is already fixed. Two failure modes it catches, both seen:

- **A fix landed and the docs went on describing the gap.** `L3-DESIGN.md` recorded an assertion as
  not yet reached while it had in fact passed on the last two builds. Nothing re-reads a retro's own
  past claims, so the sentence outlived its truth by several runs before anyone re-scored it.
- **A fix landed between the last retro and this one.** Tools move, sometimes within hours of the
  report that prompted them: the two scorecard bugs above were repaired the same evening the retro
  that found them was written. Re-check every proposal against the tool as it stands right now, and
  carry the answer into Step 6's proposals section. Publishing a fixed bug as live burns the
  reader's trust in the rest.

Create the output directory `.coyodex-eval/retro/<YYYY-MM-DD_HHMM>/` and write everything there.

---

## Step 1 — Product signals (deterministic, free, no model)

What the map itself says. Capture each command's output to the run directory.

```
coyodex validate .coyodex/project-map.json --check-sources --check-coverage
coyodex audit .coyodex/project-map.json
coyodex balance .coyodex/project-map.json
coyodex-eval score .coyodex/project-map.json --repo . --json
```

If a previous map exists, score it too and compare:

```
coyodex-eval score <archive>/project-map.json --repo . --json > prev-profile.json
coyodex-eval compare prev-profile.json profile.json
```

Record: blocking problems (should be zero), the advisory count and which advisories survived, the
component count against the code-derived expectation E, the map's own `grounding` record
(`claims_challenged / claims_total` plus the confirmed/refuted/unverifiable split), and
every count that moved against the previous
map.

**And read `compare`'s NOTES, not only its gates and bands.** One of them is not a count and cannot
be: the share of the auth surface's ENFORCEMENT LINES the two maps agree on, plus the files that hold
access enforcement in one map and are named by no access rule in the other. Two rebuilds of ONE
commit have come in at 25 % agreement — 163 lines against 116, 57 shared, 17 files covered by only
the older map and 16 by only the newer — while the statement count moved just 50 → 44 and every other
signal read clean. A count can hold steady through a wholesale change of content, so this is the only
place that churn is visible. Report the number and name the lost files; they are the reading list.

**Read `compare`'s verdict as information, not judgement.** A DRIFT on a rebuild is expected — two
LLM builds of one repo never match.

### Step 1b — The map's own contradictions

Step 1 runs the gates. It does not read the MAP, and the gates cannot see a map that is internally
consistent by their rules and wrong on its face. This is not a minor lane: on the 2026-08-13 coworker
retro the finding ranked most consequential of all came from reading the audit's worklist builder
against the map, and three more came from reading the shipped map directly. Every one of them passed
`validate` and `audit` cleanly.

Four checks, all cheap, all deterministic, each one productive on that run:

1. **Re-derive every number the `grounding.note` states.** It is free prose in a permanent record and
   nothing checks it. One shipped note gave two of its eight per-theme counts wrong and stated a
   superseded total its own fields contradicted, because the prose was written against an earlier
   pass and re-pasted.
2. **Match each `finalize` advisory to a record in the map's extras.** `finalize` says in its own
   output that each advisory is either fixed or recorded; it does not check it. Nine had been waved
   through, and the transcript could not show it because every read of the list had been filtered.
3. **Check each use case's declared `actors` against the actor of its own flow's first step**, and
   its name against its flow's title. A late rewrite left two use cases declaring one actor while
   their flows started with another, and one carrying its pre-rename flow title.
4. **Count the vocabulary the map minted against the seeds it was offered** — entry-point kinds,
   bucket names. One concept shipped under two kinds, 139 rows against 15, because one brief spelled
   out the seeded name and the others did not.

More generally: where a tool writes a number into the map and a *human sentence* beside it, check the
sentence against the number. That pairing is where this class lives.

---

## Step 2 — Process signals (deterministic, free, no model)

What the RUN did, as opposed to what it produced.

```
coyodex-eval process <transcript> --map .coyodex/project-map.json \
    --out .coyodex-eval/retro/<ts>/process.json
coyodex-eval transcript <transcript> --stats
```

**`--map` is not optional here.** Without it, assertion 6 falls back to transcript inference and
assertions 23 and 24 report `n/a` — three of the scorecard's lines quietly stop measuring, and `n/a`
reads as "no opportunity" rather than "you did not pass the map". This command line omitted it, and
the retro that found the omission had to re-run the whole scorecard.

If the previous transcript exists:

```
coyodex-eval process <prev-transcript> --map <archive>/project-map.json \
    --out .../prev-process.json
coyodex-eval process --diff .../prev-process.json .../process.json
```

Pass each transcript the map IT produced — the archived one for the previous run — or the diff
compares a scorecard that could read the map against one that could not, and three assertions move
for that reason alone.

### What it cost

```
coyodex-eval cost <transcript> --map .coyodex/project-map.json
coyodex-eval cost <prev-transcript> --map <archive>/project-map.json
```

Wall time, tokens, and both PER ROW of map produced, plus the straggler waste in each fan-out.

**Compare per row, never per build.** Absolute minutes and dollars track how big the map got: over
four consecutive mcpolis builds the map grew 1,195 → 1,564 rows while the method changed under it,
so the build that was *cheapest per unit of work* read as the slowest and most expensive one. Cost
per row and seconds per row are the comparable numbers; a rise in either is the signal.

`--map` also prints the grounding counts beside the spend, and they are read together — a change
that halves the bill and doubles the refutation rate is not an improvement. If the session did
anything before or after the build (an archive step, questions once the map landed), bound it with
`--from-turn` / `--to-turn`, or time and tokens describe different stretches.

**Bound it even when the session looks finished, because the retro takes an hour and the build
window is still open.** `retro-precheck` clears you when the build session has been idle for 180
seconds; it cannot promise the operator will not come back to that window while you read. On the
2026-08-14 mcpolis retro they did: the transcript went 449 turns / 3.0 MB at the start to 491 turns
/ 3.4 MB by the time the findings were written, and an unbounded `cost` re-run then covered 42 turns
of unrelated scratch work. Turn INDICES are stable — records only ever append — so findings keep
their turn numbers and nothing has to be redone. Note the last build turn once (the `finalize` or
commit turn), pass `--to-turn` on every `cost` and `process` run, and say in the report which
snapshot the numbers describe.

**Note the transcript's turn count now** (`coyodex-eval transcript <t> --stats`) so Step 6 can tell
whether it grew while you read.

The assertions and what each audits are in
`COYODEX_HOME/eval/fixtures/trapdoor/L3-DESIGN.md` — **all of them, so check the doc against
`coyodex-eval process` output rather than against any count written here.** This file said "the ten
assertions" while the scorecard ran fifteen, and the six the doc did not cover were three of the
four a live build scored zero on; the retro had to read the source to learn what they meant. Then it
happened AGAIN, in the same file, two paragraphs later — the report template below still said "the
ten L3 assertions" while twenty-two ran. Never write the count here; say "every assertion the
scorecard prints". (`eval/tests/test_process_scorecard.py` now fails when L3-DESIGN.md is missing
one, which is the half of this that a doc sentence cannot enforce.)

**Read the scores with their notes** — several carry a caveat that changes their meaning
(assertion 9 says so when the final validate view was narrowed by a grep), and `n/a` means the run
held no opportunity of that kind, which is not the same as a miss.

### Then audit the scorecard itself

**Every `n/a` and every zero is a hypothesis until you have settled which of three things it is.**
Work the triage in order; it is cheap and it is where the biggest findings of the last two retros
came from.

1. **Was `--map` passed?** Assertions 6, 23 and 24 go `n/a` without it. That is your own omission,
   not the build's.
2. **Does the assertion measure a COMMAND?** Then cross-check `coyodex-eval transcript --commands`.
   An assertion whose note says a command "never ran" against an index listing four runs of it is a
   detector bug.
3. **Otherwise, read the assertion's source in `process_scorecard.py`.** Several score turn
   structure, Agent-prompt text or the map — 3, 10, 16, 22 and 31 among them, and the map-only ones
   take no turns at all. No command index can settle those, and they are not rare — 3 and 31 were
   both among the headline lines of the last coworker retro.

The scorecard reads shell text with regexes over the lead's transcript. It is the most fragile thing
you will quote and the most trusted, because it prints numbers.

**When a detector looks wrong, patch it in memory and re-score — do not argue from a code read.**
That turns "this regex looks wrong" into an exact list of which lines move, on real data, changing
nothing on disk:

```python
import sys; sys.path.insert(0, "COYODEX_HOME/eval/tools")
from coyodex_eval import process_scorecard as P
P._COYODEX_SUBCOMMANDS = P._COYODEX_SUBCOMMANDS | {"grounding"}     # the suspect override
for t, m in ((cur_transcript, cur_map), (prev_transcript, prev_map)):
    print(P.score_transcript(t, map_path=m, to_turn=LAST_BUILD_TURN))
```

**Pass `map_path` and `to_turn` on both sides**, for the same reasons the CLI runs did — a bare
`score_transcript(t)` re-scores without the map (three lines silently stop measuring) and over the
post-build turns you were told to exclude.

This is worth doing because it has paid twice. On the 2026-08-13 coworker retro it found two detector
bugs — an alias-blind subcommand list and a quoted-string scanner that ate whole invocations —
between them mis-measuring nine of the twenty-two SCORED lines on BOTH the build and its baseline
(eleven of the twenty-eight printed, counting two that printed `n/a`), changing three of the diff's
directions and inverting one outright. **Both are fixed** (`_COYODEX_SUBCOMMANDS`, `_MULTILINE_QUOTE`);
they are cited here as the shape to look for, not as live bugs.


---

## Step 3 — The friction read (this is the part no tool does)

Steps 1 and 2 count the failures somebody already named. This step looks for the ones nobody has,
and it is the reason this skill exists.

**Slice first, then delegate.** The transcript is 300–500 turns and cannot be read whole. Get the
index and the fan-out map:

```
coyodex-eval transcript <transcript> --stats
coyodex-eval transcript <transcript> --commands         # every coyodex subcommand, with turn numbers
coyodex-eval transcript <transcript>                    # one line per tool call, with turn numbers
```

**Use `--commands` before concluding a command "never ran".** The one-line index truncates at 100
characters, so a subcommand chained behind `;` or `&&` is invisible in it. A retrospective read the
index, concluded `grounding write` never ran, and published that about a build which ran it at turn
489 behind an `assemble`; the finding had to be withdrawn. `--commands` reads the full command text.

Cut it into phases at the fan-out boundaries the stats print — typically: **setup + behavioral
draft**, **pre-index + harvest**, **synthesis**, **trace**, **gates (validate/audit/balance)**,
**Phase-4 grounding**, **finalize + commit**. Give each phase to one fresh-context sub-agent with
its exact turn range:

```
coyodex-eval transcript <transcript> --from <lo> --to <hi> --full
```

Hand every sub-agent the same brief: **the evidence classes below**, the requirement that each
finding carry a **turn number**, and the instruction to return findings only — no fixes, no prose
essay. Tell each one it is reading a slice, so "I did not see X" means "not in my range", never
"the build skipped X".

**Tell them not to time a fan-out off the raw JSONL.** A sub-agent that goes looking at the file
directly will find one assistant record per `tool_use` block, each stamped with the time that block
*executed* — so a single message that launched fourteen agents looks like fourteen separate turns
two minutes apart. Three sub-agents on one run independently reported "the fan-out was emitted as N
separate turns, violating the one-message rule", and all three were wrong: the fourteen records
shared one `message.id`. The transcript reader groups by that id on purpose (`transcript.py`, "A
JSONL record is NOT a turn"), and assertion 3 already measures this correctly. Put it in the brief:
**turn boundaries and turn counts come only from `coyodex-eval transcript`; agent wall times come
only from the per-agent files, which slice readers do not have; never mix the two.** A timestamp
spread inside one printed turn is streaming, not round trips.

### The evidence classes to hunt

Each one has been observed in a real build. Name them in the prompt: a vague "find problems"
returns vague findings.

1. **Hand-written what a tool produces.** A `python3 - <<'PY'` block doing something a `coyodex`
   subcommand already does. The headline case: `coyodex reconcile` ran zero times across eight
   builds while every build hand-wrote the file it generates.
2. **A tool that failed, and a workaround instead of a fix.** A command that errored and was never
   retried, or was replaced by a manual approach. Look for the SECOND attempt: what changed
   between the failing call and the working one usually names the bug.
3. **A flag accepted and ignored.** The output does not match what the flags asked for.
4. **Repeated lint / validate rounds on the same thing.** A fragment bouncing three times means a
   rule was not stated clearly enough in the prompt that produced it.
5. **A prescribed step skipped.** The method says do X; the transcript never does X. Check against
   `COYODEX_HOME/method.md`, not memory.
6. **A doc that misled.** The agent read a doc and then did the wrong thing, or had to ask a
   question the doc should have answered.
7. **An advisory neither fixed nor recorded.** The "waved through" failure the method names.
8. **Wasted turns.** Polling a directory, re-deriving something already computed, re-reading a file
   it had already read.
9. **A straggler in a fan-out.** One agent taking far longer than its siblings stalls the whole
   barrier. **Name which agent; do not time it** — you are reading the lead's transcript, where
   asynchronous dispatch makes every agent look like it returned in about two seconds. Timing is the
   lead's job, after the slices.
10. **Anything surprising.** The classes above are what was found LAST time. The valuable finding
    is the one not on this list — say so explicitly when you see it.

### After the slices: read the agents themselves

The slice readers cover the lead's turns and cannot see inside a sub-agent. Send a second, small wave
at the per-agent files from Step 0. You do not need them all.

**Start from the fan-out table `coyodex-eval cost` already printed** in Step 2 — it has slowest,
median and straggler waste per batch. What it does not give you is *which* agent was slowest, because
the batch rows carry no names. That is the only reason to compute a duration by hand: open
`<session>/subagents/` and take first-to-last record of each `agent-*.jsonl` to put a name to the
outlier.

Two things that span does NOT tell you. A dispatch the harness rejected has **no file at all** — one
build sent 68 and 65 ran — so a re-sent agent's lateness is invisible here and must come from the
lead's turn numbers. And a file span measures the agent's WORK, not its contribution to the barrier:
the batch that held one fan-out open for four minutes had only 2.3 of them in its own file, the rest
being the delay before it was re-sent. Use the span to name the agent; use the lead's transcript to
explain the barrier.

Read, at minimum:

- **the slowest one or two agents in each fan-out**, identified as above;
- **every agent the lead's transcript shows being corrected** — a fragment that bounced through
  repeated lint rounds, a malformed output file, a brief a later turn had to rewrite. The slice
  readers hand you this list; do not wait for the analysis to name it;
- **any agent that finished far faster than its share of the work would allow.** One settled 40
  claims in 95 seconds; that was not diligence.

What to look for there that the lead's transcript cannot show: whether the agent opened the files its
output claims it read; whether it wrote a *program* to produce its answer instead of producing the
answer; whether it narrowed its own self-check (class 4 — one agent's `head -40` cut the verdict line
off a `lint-fragment` run that had already passed, so it iterated twice more); and what it did with
the minutes it spent.

### What a finding must carry

- **turn number(s)** — so the user can go and look;
- **what happened**, in one or two sentences;
- **the class** (one of the above, or "new");
- **where the fix belongs**: `tool` / `method` / `both` / `neither — agent judgement`;
- **confidence**: certain (the transcript shows it plainly) vs likely (inferred);
- **verification**: `re-ran it myself` or `slice reader's word`. One word, on every finding, written
  when the finding is recorded — not reconstructed later from memory across a 40-turn
  reconciliation. This field IS the list Step 5 splits on;
- **both halves of every ratio, and where each came from.** "Roughly ten of 67" was exactly ten of
  63 — the 67 mixed two different record types under one heading. One run reported the same
  refutation rate as 0.81% and 0.73% in different places because one used challenged claims as the
  denominator and the other used verdict rows, which differ when a batch is voted on more than once.
  Write `6 of 743 challenged claims` or `6 of 823 verdict rows`, never `0.8%`.

A finding without a turn number is not a finding. Drop it.

**A trend claim needs the whole ordered list, not its two ends.** This is the most common way a wrong
finding gets published, because a clean correlation across two extremes feels exactly like the
"anything surprising" class 10 asks for. Every refuted finding on the 2026-08-13 coworker retro had
the shape *the two X are the two Y*, and each collapsed once the middle rows existed: six of fourteen
agents wrote generator scripts, including the fastest; the "anti-correlation" between dispatch order
and duration was a rank correlation of +0.16. Before writing one: print all N rows — for per-agent
numbers, first-to-last record of each `agent-*.jsonl` — look at the middle, and check the obvious
confound, which for per-unit costs is fixed startup overhead on small units.

---

## Step 4 — Reconcile the findings (lead, not delegated)

The sub-agents return overlapping and sometimes contradictory lists. This step is yours.

- **Dedupe** — the same defect seen from two phases is one finding.
- **Verify the cheap ones against the code.** A claimed tool bug can usually be confirmed in one
  command: run it. A confirmed bug outranks ten plausible ones.
- **Separate a tool bug from a method gap from an agent judgement call.** Only the first two are
  actionable here; the third is worth recording but is not a defect.
- **Drop what a sub-agent could not have known.** "It did not run X" from an agent holding turns
  40–90 is not evidence about the whole build. Check the full index before accepting it.
- **Rank by what it costs.** A defect that silently produces a wrong map outranks one that wastes
  turns.

Keep, as you go, a list of **which findings you personally re-ran** and which you are taking on a
slice reader's word. Step 5 needs it and the report publishes it.

---

## Step 5 — Send skeptics at your own findings

**Do to this report what the method tells a build to do to its map.** Phase 4 of `method.md` exists
because an author cannot audit their own claims; the lead who just accepted a list of findings is the
worst possible reviewer of it. Step 4 above is dedupe plus spot-check by that same lead. It is not
enough, and the evidence is direct: on the 2026-08-13 coworker retro an adversarial pass moved
**eight** claims in a finished report — five refuted outright, one withdrawn, one causal conclusion
demoted to a hypothesis, one arithmetic error. Every one would have shipped.

Take the list Step 4 told you to keep. **Everything you did not re-run yourself goes to a refuter.**

**How to run it:**

- **Two refuters, split by the Step 3 phase list** — one takes the earlier phases, one the later.
  More than two and they start duplicating each other's recomputation.
- **While they run**, write the Step 6 sections that do not depend on findings: `What this covers`,
  `Product signals`, `Process signals`, `Not assessed`.
- **One round only.** A refuter's corrections are yours to reconcile, not to send out again — that
  recursion has no natural floor. If a verdict is still unsettled after your own check, it is
  published as unverifiable, not sent to a third agent.
- **When two refuters disagree**, recompute from disk yourself. If that does not settle it, publish
  it as unverifiable and say what would.
- **Point them at what the second wave already read.** Step 3's per-agent pass covered the stragglers
  and the fast finishers; name those agents so the refuters spend their reads elsewhere.

The brief that works:

- **"Your job is to REFUTE these claims, not confirm them. Assume each is wrong until the evidence
  forces you to accept it. A refuted claim is a more valuable result than a confirmed one."** Say it
  first and say it plainly — a reviewer asked to "check" a list confirms it.
- Give each claim **as stated**, with its turn numbers and where the underlying artifact lives.
- Point at the files, hard: the map, `.coyodex/verify/`, the build scratchpad, and the per-agent
  transcripts. **"Prefer computing from files on disk over trusting the claim."** The refuter that
  recomputed per-batch counts from the claims files confirmed the headline finding to the digit; the
  one that read the agent transcripts broke three.
- Demand a four-way verdict, not a yes/no: **refuted** (wrong — give the correct value) ·
  **overstated** (directionally right, magnitude or wording wrong) · **unverifiable** (the artifacts
  cannot settle it) · **confirmed**. Most real outcomes are the middle two, and a yes/no forces them
  into the wrong bucket.
- For any claim that is *causal* rather than arithmetic, say so and **tell the refuter to attack the
  inference, not the numbers**, and to name what evidence would settle it. That is what turned "the
  low refutation rate means weaker skeptics" into a hypothesis with two cheap experiments attached,
  which is what it always was.
- Tell them to change nothing.

Then reconcile every verdict — fix or reject, each with a reason. **A refuter is not automatically
right.** One reported the previous map absent and a baseline unverifiable; it had searched the
coyodex clone instead of the archive under the project, and the finding stood. Check before you
retract.

Expect this to change the report substantially. If nothing comes back overturned, suspect the brief
asked for confirmation.

---

## Step 6 — Report

Write `.coyodex-eval/retro/<ts>/report.md` and summarise it in chat. Structure:

```
# Retrospective — <project> build of <built_at> (session <id>)

## What this covers
the map, the transcript, and what could NOT be assessed

## Product signals
blocking problems · advisories surviving · components vs E · grounding coverage
· deltas vs the previous map

## Process signals
every L3 assertion the scorecard printed, with the diff against the previous build

## Findings
ranked; each with turn number, class, where the fix belongs, confidence

## Proposals
tool changes · method changes · new L3 assertions worth adding
· whether the LAST retro's proposals landed

## Verification status
what you re-ran yourself · what a refuter confirmed · what it overturned
· what came back unverifiable, and what would settle it
· where a refuter was wrong · what nobody checked

## Not assessed
say it plainly
```

**Rules for the report.**

- **Numbers with evidence, never verdicts.** No PASS/FAIL. `observed / of` and turn numbers.
- **Say what you could not assess.** A retro that only lists what it found reads as complete when
  it is not. Semantic map quality is NOT assessed here — that is `/coyodex-eval`. Say so.
- **A single build proves nothing about a trend.** Where a number moved against the previous build,
  say it moved; do not say the method improved. Two data points are two data points.
- **Propose, do not apply.** End by asking which proposals the user wants implemented.
- **Re-check the turn count before you write.** Compare `coyodex-eval transcript <t> --stats` against
  the count you noted in Step 2. If it grew, the operator came back to the build window while you
  read, and every UNBOUNDED number you quoted has drifted — one run went 250.5m to 799.7m wall for
  the same build. `retro-precheck` will not warn you; it passes correctly, because those writes are
  the operator's and not another session mid-build. Requote from the `--to-turn` bounded runs and
  say which snapshot the numbers describe.
- **Publish how each finding was checked, not just what it says.** That is the `Verification status`
  block, and it is not optional: a report whose re-run findings and whose taken-on-trust findings are
  formatted identically reads as uniformly solid, and its weakest claim gets quoted as confidently as
  its strongest. Name what a refuter overturned — a table of `claim as drafted` → `outcome` is
  enough — and name where a refuter was itself wrong. Say plainly what nobody verified. On the run
  this section was written from, eight claims moved and one was withdrawn; a reader of the first
  draft had no way to tell those eight from the rest.

### Feed it back

Any finding that is a REPEATABLE process defect is a candidate NEW L3 assertion — the
scorecard exists to turn a one-off discovery into a number that gets watched. Name those
explicitly in the proposals section; that loop is how the retro stops being a one-off read.

**Say what each proposed assertion would have to read.** The scorecard is a lead-transcript
instrument, and much of what a retro finds does not live there — an assertion that needs the map or
a per-agent transcript is a different piece of work from one that greps the lead's commands, and one
nobody can implement is a proposal that quietly dies. Tag each with its source.

**Report what the previous proposals did, and update the backlog.** You read
`COYODEX_HOME/eval/retro/backlog.md` in Step 0; say in `Proposals` which items landed, which did not,
and which were overtaken by a fix that arrived in between. Then say what the backlog should become —
new items to add, items to move to Landed, status lines that are now wrong. **Proposing that edit is
the deliverable; making it is not** — the report-only rule covers the backlog too.
