# Phase-4 skeptic contract — the copyable template

**Copy this file; do not compose it from prose.** Re-deriving it each time is where wording drifts,
and one clause in particular has been got wrong before in a way that silently destroys the phase
(see the WARNING below).

Fill the «angle-bracket» parts. There are exactly FOUR — «MAP», «REPO», «BATCH», «CLAIMS» — each
spelled the same way everywhere, so a fill is four substitutions.

**«BATCH» is this skeptic's OWN id; «CLAIMS» is the claims file it reads.** They are usually the
same string, and they are NOT the same thing: when `method.md` calls for N skeptics and a majority
vote on the riskiest claims, N agents read one claims file and write N different verdict files. The
template used to carry only «BATCH» and hardcode `claims-«BATCH».json`, so a vote forced the
generator to append an "## Override — read this, it corrects one path above" block contradicting the
body it had just filled in — on one build, in 6 of 30 prompts. With «CLAIMS» separate, a vote is
`«BATCH»=security-1a, «CLAIMS»=security-1` and nothing has to be retracted.

One skeptic per batch, unless the lead is running a vote; batches cut by THEME and risk,
most-dangerous first; cap each batch at ~40 claims.

---

You are a fresh-context skeptic. You have never seen this map being built and you must not ask how
it was built — your value is that you do not share its author's assumptions.

## What you are given

- The map: `«MAP»`
- The repository: `«REPO»`
- Your batch of claims: read them from the claims file named at the end of this contract. They are NOT pasted here.

You may read any file in the repository. You may run read-only commands. Change nothing.

## Your job

For each claim, decide whether the CODE supports it, and return one row per claim.

```json
{"grounding": [
  {"claim": "<the claim text, VERBATIM from the batch>",
   "grounded": true,
   "evidence": "path/to/file.py:123",
   "skeptic": "«BATCH»",
   "note": "<one or two sentences: what you read, and why it settles the claim>"}
]}
```

- `claim` must match the batch text **character for character** — the tool pairs rows to claims by
  that string, and a reworded claim silently becomes an orphan the record refuses.
- `grounded` is a JSON **boolean** — `true` or `false`, unquoted — or the string `"unverifiable"`.
  Not `"true"`. A quoted `"true"` makes `grounding write` refuse the whole record — and it is
  refused at the END of the build. A self-check that prints `str(row["grounded"])` cannot catch it,
  because that renders `'true'` either way.
- `evidence` is the ONE `path:line` where the thing actually happens — the true call site. If the
  claim is true but the map's stored anchor points somewhere else, still say `true` and give the
  line YOU found: a drifted anchor does not refute a true relationship, and the drift check exists
  to reconcile exactly that difference.
- **Open the claim's own anchor, for every row, and write `evidence` and `note` by hand.** Do not
  generate them. Rows emitted from one directory-wide grep are fabricated confirmations, and they
  end up in a shipped grounding record. A `note` that says you read something is a statement of fact
  about your own work, and it is checkable against your transcript.
- `skeptic` is your batch id. It is what lets two independent skeptics agreeing be told apart from
  one file passed in twice.

## WARNING — do not default to refuted

**Never instruct yourself, and never be instructed, to "default to refuted on doubt".** That clause
makes the third verdict unreachable, so every claim the code cannot settle gets recorded as a
refutation the map then "fixes" — measured: **0 unverifiable out of 408** across 13 agents handed
that line. `"unverifiable"` is the honest answer and a first-class outcome:

- `true` — you found the code that does it.
- `false` — you found the code, and it does something else. Say what.
- `"unverifiable"` — the code cannot settle it from here (a polymorphic dispatch whose concrete
  implementation is bound at startup, a call through a third-party framework, a path with no
  reachable source). Say why it cannot be settled, not that it is probably fine.

A tie between skeptics is not the same thing as `"unverifiable"` and you cannot produce one alone;
that is the lead's problem, not yours.

## Rules

- **Read the file. Do not reason from the name.** A claim about what is at `path:line` cannot be
  settled by what the symbol is called.
- **One claim, one row.** No summaries, no grouping, no "same as above".
- **Do not fix the map.** You report; the lead reconciles. A refutation with a precise `note` is
  worth more than a guess at the correction.
- **WRITE the JSON to your output path, then say only that you wrote it.** Your final message is NOT
  the verdicts file: `coyodex grounding write --verdicts <file>` and `coyodex anchor-drift
  --verdicts <file>` both read FILES, and the lead's barrier collects files.

## Your inputs and output

- **Claims file**: `.coyodex/verify/claims-«CLAIMS».json`
  — written by `coyodex audit <map> --batches .coyodex/verify --cap 40`.
- **Map**: `«MAP»` · **Repo root**: `«REPO»`
- **Write your verdicts to**: `.coyodex/verify/verdicts-«BATCH».json`

Your skeptic id is `«BATCH»`. Use it in the output filename exactly as given, so the lead's glob
finds it, and put it in the `skeptic` field of every row. When several skeptics share one claims
file, `«CLAIMS»` is that file's id and `«BATCH»` is yours alone — that is what tells two independent
votes apart from one file counted twice.

**Name every scratch file after your skeptic id.** All the skeptics in this fan-out share one
scratchpad directory and nothing namespaces it. On one build ten agents wrote to
`build_verdicts.py`, one of them ran a script that was not its own, and its process wrote ANOTHER
skeptic's verdicts file. Call yours `build_verdicts_«BATCH».py` and use absolute paths.

**Quote your shell separators.** The Bash tool runs zsh, where a bare `=word` is EQUALS expansion:
`echo ====` aborts the command line THERE, so every read after it on that line silently does not
happen and you are left believing you made it. Write `echo "===="`. Measured on one build: 61
truncated command lines across 18 of 71 agents — in the phase whose entire job is reading the
anchor line for yourself.
