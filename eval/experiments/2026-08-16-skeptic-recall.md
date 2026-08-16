# Does the skeptic contract need a falsification mandate? — 2026-08-16

**Question.** A Phase-4 pass refuted 6 of 823 rows with 0 unverifiable. A retrospective read that as
"weaker skeptics, not a better map" and proposed adding an explicit *try to disprove this* mandate to
`method/templates/skeptic-contract.md`. That was a hypothesis about a cause, never a measurement, and
it was gated on this experiment rather than shipped.

**Method.** Planted 10 known-false claims across four shapes in `claims-rule-5` (40 access-governing
claims, originally verdicted 40/40 confirmed), kept the answer key, and ran the SAME mutated batch
under two contracts — the current one, and a variant carrying an explicit falsification mandate plus
the four shapes named — with two skeptics each. Recall against a fixed ground truth, not a
comparison of refutation rates, because two rates with no truth behind them cannot say which is
right. Harness: `coyodex-eval mutate`.

## Result

| | current contract | + falsification mandate |
|---|---|---|
| detection | **10/10**, both skeptics | **10/10**, both skeptics |
| false positives | 0 | 0 |
| drifted anchor | 3/3, all pointing at the exact true line | 3/3, same |
| negated second clause | 3/3 | 3/3 |
| swapped actor | 2/2 | 2/2 |
| ghost file | 2/2 | 2/2 |

All four agents returned identical verdict splits (33 true / 7 false / 0 unverifiable) and identical
detection. **The wording made no measurable difference.**

## What this changes

**The proposal is withdrawn.** These skeptics are not weak: they caught every planted falsehood,
including the negated second clause — half the sentence still matching the code, which is the shape
designed to survive a skim — and they invented no refutations. The low refutation rate on the source
build is much better explained by the map being largely correct.

**What it does not settle.** One batch, one theme, one repo, four agents. It measures recall against
*planted* falsehoods, which are cleaner than the ones a real build produces. And 0 unverifiable
across 160 rows is still unexplained — every claim here was decidable, so the experiment gave that
verdict no opportunity.

## The experiment was wrong first, and the record matters more than the result

The first scoring run reported **7/10 with drifted_anchor at 0/3**, which reads as a clear weakness.
It was the harness at fault, twice:

1. Drift was planted by adding 400 to the line number, which put every one PAST end-of-file — a
   ghost LINE, the easy shape wearing the hard shape's name.
2. Drift was scored on the VERDICT. The contract says in as many words that a drifted anchor does not
   refute a true relationship: confirm it, return the line you actually found, and let the drift
   check reconcile. So a refutation is the wrong answer, and scoring it that way marked four
   skeptics 0/3 **for obeying their instructions**. All four had returned the exact original line.

Both are now regression-tested. Had either shipped, this file would have said the skeptics were weak
and the contract change would have followed on the strength of it.
