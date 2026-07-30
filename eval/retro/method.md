# coyodex-retro — a retrospective on one finished build

A build just ran. Two artifacts survive it: the **map** it produced and the **transcript** that
produced it. This method reads both and reports what the run says about the tools and the method.

**Report only.** Change nothing — no map edit, no tool fix, no method edit. Every finding is a
proposal the user decides on. Saying "I would change X" is the deliverable; changing X is not.

**Why it is not `/coyodex-eval`.** That one REBUILDS the map blind and judges it against a
baseline: *did quality regress?* This one never builds anything. It asks a different question —
*what did this run reveal?* — and its answer is a list of bugs, friction and gaps. The two are
complementary; neither replaces the other.

## Paths — keep them straight

- **`COYODEX_HOME`** — the coyodex clone (the skill substitutes the real path). The CLI is
  `COYODEX_HOME/.venv/bin/coyodex` and `COYODEX_HOME/.venv/bin/coyodex-eval`; the method under
  audit is `COYODEX_HOME/method.md` + `COYODEX_HOME/method/`.
- **The reviewed project** — your cwd. Map in `.coyodex/`, previous map in `.coyodex/.old-ignore*/`,
  output in `.coyodex-eval/retro/<timestamp>/`.

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

Read `provenance.json`. Its last `sessions[]` entry carries the `session_id` and `built_at` of the
build. The transcript is:

```
~/.claude/projects/<slug>/<session_id>.jsonl
```

where `<slug>` is the project's absolute path with every `/` replaced by `-`. **Derive it; do not
guess and do not pick "the newest file"** — several sessions can share a directory, and the newest
one is often the retro itself.

Also locate, for comparison (all optional — say so when absent):

- **the previous map** — the highest-numbered `.coyodex/.old-ignore*/project-map.json`. That is
  where `archive_map.py` puts the map a from-scratch rebuild replaced.
- **the previous transcript** — the `session_id` in that archive's own `provenance.json`.

Stop and say what is missing if the map or the provenance is absent. A retro with no transcript can
still do Steps 1 and 5, and must say that Steps 2–4 were skipped.

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
(`claims_grounded / claims_total`, refutations), and every count that moved against the previous
map.

**Read `compare`'s verdict as information, not judgement.** A DRIFT on a rebuild is expected — two
LLM builds of one repo never match.

---

## Step 2 — Process signals (deterministic, free, no model)

What the RUN did, as opposed to what it produced.

```
coyodex-eval process <transcript> --out .coyodex-eval/retro/<ts>/process.json
coyodex-eval transcript <transcript> --stats
```

If the previous transcript exists:

```
coyodex-eval process <prev-transcript> --out .../prev-process.json
coyodex-eval process --diff .../prev-process.json .../process.json
```

The ten assertions and what each audits are in
`COYODEX_HOME/eval/fixtures/trapdoor/L3-DESIGN.md`. **Read the scores with their notes** — several
carry a caveat that changes their meaning (assertion 9 says so when the final validate view was
narrowed by a grep), and `n/a` means the run held no opportunity of that kind, which is not the
same as a miss.

---

## Step 3 — The friction read (this is the part no tool does)

Steps 1 and 2 count ten known failures. This step looks for the ones nobody has named yet, and it
is the reason this skill exists.

**Slice first, then delegate.** The transcript is 300–500 turns and cannot be read whole. Get the
index and the fan-out map:

```
coyodex-eval transcript <transcript> --stats
coyodex-eval transcript <transcript>                    # one line per tool call, with turn numbers
```

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
   barrier. Compare timestamps within one fan-out.
10. **Anything surprising.** The classes above are what was found LAST time. The valuable finding
    is the one not on this list — say so explicitly when you see it.

### What a finding must carry

- **turn number(s)** — so the user can go and look;
- **what happened**, in one or two sentences;
- **the class** (one of the above, or "new");
- **where the fix belongs**: `tool` / `method` / `both` / `neither — agent judgement`;
- **confidence**: certain (the transcript shows it plainly) vs likely (inferred).

A finding without a turn number is not a finding. Drop it.

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

---

## Step 5 — Report

Write `.coyodex-eval/retro/<ts>/report.md` and summarise it in chat. Structure:

```
# Retrospective — <project> build of <built_at> (session <id>)

## What this covers
the map, the transcript, and what could NOT be assessed

## Product signals
blocking problems · advisories surviving · components vs E · grounding coverage
· deltas vs the previous map

## Process signals
the ten L3 assertions, with the diff against the previous build

## Findings
ranked; each with turn number, class, where the fix belongs, confidence

## Proposals
tool changes · method changes · new L3 assertions worth adding

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

### Feed it back

Any finding that is a REPEATABLE process defect is a candidate eleventh L3 assertion — the
scorecard exists to turn a one-off discovery into a number that gets watched. Name those
explicitly in the proposals section; that loop is how the retro stops being a one-off read.
