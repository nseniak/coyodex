# L3 — process assertions over a build transcript (DESIGN ONLY, not implemented)

L1 asks *does the method name the tool*. L2 asks *does the tool say the right thing*. Neither
can see the third defect class: **the agent does not behave as the method says**. method.md
requires a fan-out to be emitted as ONE message; measured across 26 fan-outs in 8 builds, 26 of
26 launched exactly one agent per turn. The rule was rewritten and the behaviour did not move at
all. Nothing in a static check or a tool test can observe that — only the transcript can.

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
.venv/bin/python -m pytest eval/tests/test_build_process.py \
    --transcript "$(ls -t ~/.claude/projects/*trapdoor*/*.jsonl | head -1)"
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

Assertions 1–10 are project-agnostic and would run against any build transcript. 11 is what
makes the trapdoor fixture worth building a map of rather than just testing tools against.

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
