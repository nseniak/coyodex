# L3 — process assertions over a build transcript

**Status: assertions 1–10, 12–18, 21 and 22 are IMPLEMENTED; 11, 19 and 20 are not.** The reader is
[eval/tools/coyodex_eval/transcript.py](../../tools/coyodex_eval/transcript.py), the assertions and
the scorecard/diff CLI are
[eval/tools/coyodex_eval/process_scorecard.py](../../tools/coyodex_eval/process_scorecard.py)
(`coyodex-eval process`), the logic tests are
[eval/tests/test_process_scorecard.py](../../tests/test_process_scorecard.py) and the opt-in corpus
run is [eval/tests/test_process_corpus.py](../../tests/test_process_corpus.py). **Assertion 11 is
still design only** — it compares a built map against the trapdoor golden map, and that golden map
was assembled from an authored fragment rather than produced by a live agent build.

L1 asks *does the method name the tool*. L2 asks *does the tool say the right thing*. Neither
can see the third defect class: **the agent does not behave as the method says**. Nothing in a
static check or a tool test can observe that — only the transcript can.

> ## Correction: the "26 of 26" measurement was wrong
>
> This design opened by saying method.md requires a fan-out to be emitted as ONE message and that
> 26 of 26 measured fan-outs launched exactly one agent per turn — the rule rewritten, the
> behaviour unmoved. **Running the implemented checker over the same eight transcripts says the
> opposite.** Seven of the eight builds contain at least one assistant message carrying two or more
> `Agent` calls; the eighth launched no agents at all.
>
> The earlier measurement counted JSONL **records** as turns. This harness writes one content block
> per record and stamps each with the time the tool *executed*, so a message that emitted ten
> `Agent` calls appears as ten records minutes apart with the tool results interleaved — which reads
> exactly like one agent per turn. What settles it: those records share one `message.id`, one
> `requestId` and one byte-identical `usage` block, and there is exactly **one** `thinking` block
> among all ten. A model does not emit ten tool-calling responses of which nine contain no
> reasoning.
>
> The lesson generalises past this number: **the reader is the measurement.** Any future assertion
> over a transcript is only as true as its turn reconstruction, which is why
> `transcript.grouping_is_consistent()` exists and why the corpus test asserts it first.

## Say this first: L3 is a scorecard, not a gate

An L3 run costs a real model, real minutes, and a real API budget, and it is **not
deterministic**: the same fixture, the same method and the same model produce different turn
counts, different batching and sometimes a different set of commands. So L3 must never block a
commit and must never be part of `make test`. **L1 and L2 are the hard gates.** L3 is a
periodic scorecard you run when the method changes, read as a trend across runs, and act on
when a number moves — the same relationship `eval/` already has with map quality, applied to
process instead of product.

Every assertion below is therefore reported as a **score with the evidence attached**, never as
a pass/fail line. A single run proves nothing; three runs that all show zero multi-agent turns
prove the rule is not landing.

## How a run works, unattended

```sh
cd eval/fixtures/trapdoor
claude -p "/coyodex from scratch"                       # ~10 minutes on this fixture, by design
cd -
.venv/bin/coyodex-eval process "$(ls -t ~/.claude/projects/*trapdoor*/*.jsonl | head -1)"
.venv/bin/coyodex-eval process --diff <previous>.l3-scorecard.json <new>.l3-scorecard.json
```

No live build is needed to exercise the checker itself — any existing build transcript scores:

```sh
COYODEX_L3_CORPUS=1 .venv/bin/python -m pytest eval/tests/test_process_corpus.py -q -s
```

Three things make that possible and each is already true:

- the fixture is small enough that a full build is ~10 minutes rather than an hour;
- `.coyodex/.ignore` keeps the fixture's own build artifacts out of coyodex's self-map, so a run
  leaves the parent repo clean apart from `eval/fixtures/trapdoor/.coyodex/`;
- the transcript is a plain JSONL of turns under `~/.claude/projects/<slug>/`, so the assertions
  are ordinary parsing over `{role, content[], tool_use{name, input}}` records — no new
  infrastructure, no LLM in the checking loop.

The checker needs one new piece: a small reader that turns the JSONL into a typed
`Turn(index, role, tool_calls: list[ToolCall])` sequence, with `ToolCall(name, input)`. Frozen
dataclasses, stdlib `json`, same house style as `tests/trapdoor.py`. Everything else is
counting.

## The assertions, each tied to a fix that failed

| # | assertion | the fix it audits |
|---|---|---|
| 1 | `coyodex preindex --report` appears in a Bash call | the read command exists *because* all four measured builds hand-wrote `python3 -c "json.load(open('.coyodex/preindex.json'))…"`. Does adding it change behaviour? |
| 2 | **no** turn parses `preindex.json` by hand — no `json.load`, `jq`, `grep`, `head` or `sed` over that path | the negative half of #1. A build that runs `--report` *and* still hand-parses has not adopted it |
| 3 | at least one fan-out turn contains **≥2 agent tool calls in ONE assistant turn** | the one-message fan-out rule: 26 of 26 measured fan-outs were one agent per turn. This is the single highest-value number on the scorecard |
| 4 | `coyodex anchor-drift` runs with **no** `--verdicts` (the shape-only pass) | the serial-build grounding floor. It was added so a build with no skeptics still gets deterministic drift findings; nothing yet shows it is reached |
| 5 | Phase-4 skeptics are launched at all, and in ≥1 batched fan-out | a live small-repo build finished and told the user it had no fresh-context skeptics — the exact blind spot Phase 4 exists to break |
| 6 | the assembled model carries a non-empty `grounding` object | a monorepo build grounded 319 of 1,608 claims and reported it only in chat, where it evaporated |
| 7 | `coyodex reconcile` is used, or `reconcile.json` is written some other way — record which | the headline class-2 defect: a working, tested command that ran zero times in four builds while every one hand-wrote its output (one was 24 KB, 139 rules, 882 id assignments) |
| 8 | `coyodex audit --json` is used; `audit` output is **not** paged through `head`/`sed`/`grep` | the machine-readable payload was built for the Phase-4 batching step and the doc forbids regex-parsing the human report |
| 9 | no advisory is left both unfixed and unrecorded — cross-check the final `validate` warnings against the model's extras headings | "advisory waved through" is the failure the method names in its own words |
| 10 | `ls`/`find` polling of `build-fragments/` stays under a threshold (propose **3** per fan-out) | the method says wait on completion notifications, never poll; a not-ready file reads as an error and burns turns |
| 11 | *(fixture-specific, free)* the run's own `traps.yaml` outcomes: did the build fall for A1/O1/O2/G2/G5? | the fixture's whole reason to exist — compare the built map against the golden one |

Assertions 1–10 are project-agnostic and run against any build transcript — that is why they could
be validated against eight real builds of four different repos instead of waiting for a fixture run.
11 is what makes the trapdoor fixture worth building a map of rather than just testing tools
against, and it is the one still unimplemented.

### 12–17, added after later builds

These shipped without an entry here, and the omission had a cost: a retrospective met three of them
scoring zero (13, 14, 17), found nothing in this table, and had to read the detector source to learn
what they even measured. There is no assertion 11 in the runner — the number stays reserved for the
fixture row above.

| # | assertion | the fix it audits |
|---|---|---|
| 12 | the commit message's gate claim matches what `finalize` actually returned | a build wrote "gates clean" over a report that said ADVISORIES. The durable record is the commit; if it disagrees with the gate, the gate may as well not have run |
| 13 | `grounding write` is the LAST write — no map or fragment write follows it | the record describes a worklist that no longer exists. A live build wrote it and then made 21 further writes, four of which ADDED claims no skeptic ever saw |
| 14 | the record's pinned `claims_total` matches the map's live audit worklist | the same failure seen from the other side. A build shipped `446 of 446 challenged` against a live worklist of 444 and quoted the 446 in its commit message |
| 15 | no advisory is re-checked with a filter narrower than the run that surfaced it | narrowing the view is what a waved-through advisory looks like from the inside. Distinct from 9, which compares the final view to the model's records; this one watches the *re-check* |
| 16 | in every fan-out, the known-longest slice is dispatched first | launch order is the only lever on when a barrier closes. A straggler dispatched twelfth of thirteen held one ~4 minutes longer than it had to |
| 17 | a recorded drift exception cites a file the build actually opened | a record is a judgement about code; written without reading the code it is a dismissal. **Read this score with care** — it has been observed reporting 0 for reasons other than the behaviour, when records were written through `coyodex record --line` with shell-escaped backticks, or when the anchor-drift output was captured as `--json` so the text form it pairs on never landed |

### What building them taught

Four detectors were wrong on first writing, and every one was found by the corpus rather than by a
synthetic test — the author of a synthetic test is the author of its blind spot:

| the bug | what it did |
|---|---|
| substring matching for `coyodex <cmd>` | a `python3 - <<'PY'` body that merely *printed* the command name counted as running it — three shape-only `anchor-drift` runs reported where one had happened |
| requiring the literal token `coyodex` | every build aliases the binary (`C=…/coyodex; $C audit …`); requiring the literal hid every `audit` invocation one build made |
| "names `preindex.json` + contains a parsing tool" | `git add …/preindex.json` counted as hand-parsing an artifact it never opened |
| "written by a `>` redirect or `Write`" | the largest `reconcile.json` in the corpus (24 KB, 139 rules, 882 id assignments) came out of a generator script, so the detector reported it was never produced at all |

Assertion 9 has a limit no transcript can remove: "the final validate output" is only a complete
view when the build did not narrow it, and every measured build pipes validate through `grep`. The
scorecard therefore reports the run sizes and says plainly when the last view was a fraction of the
widest one. An unlabelled optimistic number would be the worse failure.

## What each assertion emits

```
{ "id": 3, "name": "fan-out emitted as one message",
  "observed": 0, "of": 4, "score": 0.0,
  "evidence": [{"turn": 41, "agents": 1}, {"turn": 42, "agents": 1}, …] }
```

`observed / of` rather than `true / false`, and always with turn indices, so a regression is a
number that moved and a reader can go look at the turn. The run writes one JSON scorecard next
to the transcript; a second script diffs two scorecards. That is deliberately the same shape as
`coyodex-eval`'s relative gates — **compare to the last run, do not demand perfection** — so the
two layers read alike and could share `compare.py`'s banding later. (Sharing it is a real
option, not a plan: it would need agreement first, and the L3 scorecard has no baseline
memoisation to reuse.)

## Cost, and what it buys

One run: ~10 minutes wall clock and one build's worth of tokens on the fixture. Assertions 1, 2,
4, 7, 8 and 10 are pure counting and would each have caught a shipped-but-unreached fix. Assertion
3 is the one that already has a measured answer (0 for 26) and would tell you, on the next
method edit, whether the rewrite landed — which is exactly what nobody could tell last time.

## Open follow-up this design depends on

The golden map in `golden/` was written by `coyodex assemble` from an authored fragment: a real
tool output over a real tree, but not the product of a live agent build. Assertion 11 wants a
map produced by an actual `/coyodex` run over this fixture, reviewed and blessed. That first
blessed build is the natural moment to implement L3, because it produces the first transcript
worth asserting over.

### 18–22, from the 2026-08-01 retrospective

Each is a repeatable process defect a real build showed and no existing number watched.

| # | assertion | the fix it audits |
|---|---|---|
| 18 | a commit's shape numbers match the map it describes | a commit claimed "416 backbone edges … 33 flows/sub-flows" for a map holding 365 and 36. Both had been true earlier in the build; `fix dedup-edge` then dropped 49 duplicate occurrences. Scored against the `Shape:` line `finalize --emit-gate-block` now generates |
| 19 | *(WITHDRAWN — do not re-add without reading below)* no gate's output is filtered with an inverting `grep` | the defect is real: a build hid 38 duplicate-edge warnings behind `grep -v` and they stayed invisible across two assembles and a whole grounding pass. The MEASUREMENT was not. See the note under this table |
| 20 | *(reserved, NOT implemented)* the lead re-verified every refutation before applying it | three of one batch's eight adverse skeptic findings were false, including a 2-1 majority on the highest-risk claim in the map, and the lead caught all three on its own initiative. But a refutation is reconciled by an ordinary map write and justified by an ordinary file read, so there is no reliable transcript signature. Reserved rather than filled with a guess |
| 21 | `assemble`'s digest is clean at the FINAL assemble | a build was told `UNHEALED riding steps 4` at four successive assembles and addressed it at none. Only the last assemble counts: a mid-build unhealed count is expected and drains as the trace lands. This measures whether the digest was READ, not whether the shipped map is broken |
| 22 | the behavioral draft precedes `preindex` | `preindex` prints GR1 on every run. A build read it, harvested 14 structural slices, and wrote its behavioral fragment 79 turns later. The structural slices exist to serve the behavioral layer, so the order is not decoration |

11 and 20 are both absent from the runner, for different reasons: 11 needs the fixture's golden map,
20 needs a signature the transcript does not carry.

### Why 19 was withdrawn

It shipped, was measured against the corpus, and removed in the same session. The defect it aimed at
is real and stays on the record above; the detector could not be made precise.

The problem is that the real shape is not a pipeline. The motivating build ran
`coyodex validate … > /tmp/v5.txt 2>&1; …; grep -v '<pattern>' /tmp/v5.txt`, so a `gate | grep -v`
pattern matched nothing. Widening it to "an inverting grep anywhere in a shell block that also
mentions a gate" did catch the two real cases — and produced 5 false flags out of 7 on the corpus:
`git status --porcelain | grep -v '^ M …'`, a source grep filtered with `grep -v "^.*#"`, and
repo-wide sweeps excluding `./.venv`, all in commands that happened to mention `validate` or `audit`
somewhere. **71 % noise in a scorecard line is worse than an absent line**, because the next
retrospective reads it as signal — which is the exact failure this whole assertion family exists to
prevent.

Making it precise needs something shell text does not carry: which output a later `grep -v` was
reading. A file path can be tracked from the redirect to the grep, but a build that pipes, or that
greps a path it built by variable, defeats it — and a detector that works on the tidy half of the
corpus is how the first version got here.

Assertion 15 already catches the narrower, well-signalled case (a re-check with a pattern narrower
than the run that surfaced it). **If you re-add 19, first measure it on the whole corpus and count
the false positives — the number that got it withdrawn is 5 of 7, and any replacement has to beat
that before it is worth a line.**

The number 19 stays retired, like 11 and 20. Re-using it would make two different measurements share
an id across archived scorecards.
