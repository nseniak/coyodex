# A present-tense number about a live map goes in the ledger, not only in a comment

Change (2026-09-07): new `coyomap-eval live-numbers` — a ledger of 9 sentences in `tools/` and
`eval/tools/` that state a number about a LIVE map, each paired with a `measure` that regenerates it
by CALLING THE PRODUCT'S OWN FUNCTION. 31 more sentences of the same class are recorded with the
reason no measure can be written for them. Tool + tests only; no method text, no build behaviour
changes.

Escalation: if check 3 fails — a new sentence of this shape landed with no ledger row — the answer
is a lint, not more words. Say so in the report.

## What this change is answering

**Measured on 2026-09-07** over `tools/coyomap/` and `eval/tools/coyomap_eval/`: 739 prose blocks
carry a number-claim. 665 of them record a PAST build and cannot rot. **35 describe a live map
today, and 23 of the 27 that could be decided were wrong** — 85%. Four of the six defects fixed
that day were exactly this.

The three shapes the 23 came in, because only one of them is harmless:

| shape | rows | what a reader loses |
|---|---|---|
| the map grew; the sentence's reasoning survives | 14 | a stale size |
| **the problem it describes was FIXED; the prose still calls it live** | 6 | told a live defect exists that does not |
| it describes a map that is gone | 3 | the viewer draws FK and optional field markers, and no live map produces one |

**Why this is not a prose-reading check.** The prose never says which computation made its number.
Working that out by inference is what the three advisories of 2026-09-06/07 did, and each missed the
defect it was written for. This reads no prose: a person writes the sentence twice — once in the
code, once in the ledger — and the ledger's `measure` regenerates it from the map. There is nothing
to infer.

**And why the ledger is 9 rows and not 40.** The first cut mechanised 30 of them, by hand-writing a
recount for each sentence. An adversarial review broke 19 of the 30, and every break was the same
shape: the recount had drifted one step from the thing described. Field markers looked up by the
wrong spelling, so a map holding 26 foreign keys reported 0. An advisory's one aggregated line
counted as one instance, so five surfaces read as one. A sub-flow matched by substring onto a
different sub-flow. Two rows survived, and they were the two that called the product's own function. A SECOND review of
the rebuilt 14 broke four more — every one a `max()` or a substring quietly picking which map, or
which object, the sentence "meant" — and caught that one row's quote had been clipped past its own
dating clause, so a RECORD was being watched as a live claim and the report was telling a reader to
falsify it.
**So that is now the rule for admitting a row**, and a sentence with no function to call is recorded
in `NOT_MECHANISED` rather than watched by a guess. The danger the review named is what makes the
rule non-negotiable: a reader repairing a stale row pastes the tool's measured line into the comment,
so a wrong measure does not merely fail to help — it converts a true-but-old sentence into a
permanently false one that then reports as holding.

**Why the sentence and not the number.** Storing the NUMBER alone would repeat the original failure:
three of the six defects were a figure corrected in a markdown file and left wrong in the code
beside it. The ledger stores the SENTENCE and demands the file still contains it, so a comment
edited without the ledger reports `DRIFTED` and a ledger edited without the comment cannot go quiet.

## The habit

**A present-tense number about a live map does not go into a comment on its own.** Either give it a
ledger row in `eval/tools/coyomap_eval/live_numbers.py`, or write it in the past tense naming the
build it came from — "the 2026-09-07 mcpolis map read 4 of 43" — which is a record, and records do
not rot. Two thirds of the number-claims in the tools already do the second thing correctly.

Run it: `coyomap-eval live-numbers --map argus=<path> --map mcpolis=<path>` (coyomap's own map is
found in the repo). NOT in `make gates` — two of the three maps live outside this repo, and a
rebuild legitimately moves these numbers. Three gate-safe tests do run: every ledger sentence is
still in the tree, still pinned to its exact line, and every recorded reason names a file that
exists.

**Exit 1 means a sentence disagrees with its map. Exit 2 means the LEDGER is broken** — a row
crashed, or its sentence is gone from the file. They are not the same news, and one code for both
would let a run where every row errored pass the CLI sweep, which tolerates exit 1.

## Open, and deliberately not done here

**All 9 rows HOLD.** The 9 sentences were rewritten as part of this change, so the ledger's first
committed state is green and its next red row means something moved. A check that ships permanently
failing is a check people learn to skip, which this repo already knows.

Two of the rewrites were not renumbering, and both are worth reading:

* **The record-direction gap is now 0 of 45, on neither map.** The two argus records the sentence
  named have been closed, so its example became a dated record inside the same paragraph and the
  live half stayed live. That is the habit applied to a sentence rather than stated about one.
* **The non-disjoint-files evidence collapsed from 27% of call-site anchors to 2%**, and the
  comment now says so out loud. The rule did not change, because it never rested on the share —
  one file with two owners is enough. Hiding the collapse behind a quiet renumber would have left
  the next reader deciding whether to "design it away" without the fact that nearly all of it is
  already gone.

**Before the rewrite, two of the 9 described a problem that had since been FIXED** and still called
it live — the
record-direction gaps (0 today, the sentence says 2 on argus), the no-reply walk (3, says 4), and
the shared-file overlap, which has collapsed from 27% of call-site anchors to 2% while the comment
around it says the fact "must not be designed away". Those two mislead a reader; the rest are only
out of date.

**31 sentences of this class are recorded but NOT mechanised**, grouped in that module by why:
four name no particular map (so any rule picking one is a guess — that is what broke four rows of
the second cut), eight describe a computation nothing implements, three sit on an advisory that
reports one aggregated line per map rather than per instance, three name a map that can no longer
be opened, four state a number that is not a measurement, four are dated records, and **five were
in neither list until the second review found them** — including the twin of a watched row's own
number, 250 lines away in `views.py`. Those five are rows waiting to be written, not exclusions.

**Two of the maps these sentences count cannot be opened.** MEE6 fails on the renamed
`grounding.claims_grounded`, distown on the split `capabilities[].label`. Every sentence saying
"the four live maps" or "five maps" is unverifiable for that reason, not because it drifted.

## Checks

1. expect: `coyomap-eval live-numbers` against all three maps reports **9 hold and 0 stale**, or a
   stale row for every map rebuilt since — a red row here should be traceable to a rebuild.
   regression sign: a row reading `STALE` with no rebuild in between. That means a measure is
   reading something the sentence does not describe, which is the defect class that took out 19 of
   the first 30 rows and 4 of the next 14.

2. expect: **exit 1, not 2** — `0 drifted` and `0 errored`. A `DRIFTED` row means someone edited a
   comment the ledger mirrors and did not update the ledger, which is the exact half a number-only
   ledger cannot see. An `ERROR` row means a measure calls a product function that has changed
   shape, which is the ledger telling you it can no longer be trusted.
   regression sign: any drifted or errored row surviving a whole retro cycle — the ledger is then a
   file people edit around rather than with.

3. expect: no commit since the previous build added a NEW present-tense live-map number to a
   comment in `tools/` or `eval/tools/` without a ledger row. Re-derive the candidate list the way
   the 2026-09-07 measurement did: prose blocks carrying `\d+\s+\w+`, naming argus / mcpolis /
   coyomap's own map / "live maps", with no past-tense framing (`was`, `were`, `ran`, `on the
   20xx-`, `one build`). Baseline: **40 such rows, 9 of them in the ledger, 31 recorded as not
   mechanised.** The baseline was published as 35 and was itself one of the unmeasured numbers this
   tool exists to stop; the second review found five more.
   regression sign: the count rises and the ledger did not. An instruction has then done what a
   suggestion did, and the answer is a lint over that same filter rather than another paragraph.

4. expect: the shared-file share has not fallen to 0. It went 27% → 2% between the 2026-08 and
   2026-09 maps, and the comment at `validate_model.py` now says so; at 0 the rule's only remaining
   evidence is gone and the API decision it defends is worth re-arguing rather than re-numbering.
   regression sign: a rebuild reporting 0 files claimed by more than one component, quietly
   renumbered instead of raised.

5. expect: no row admitted to `LEDGER` whose measure reimplements a count instead of calling the
   function the sentence describes. Read each measure: it should be a call plus formatting.
   regression sign: a measure with its own loop over `m.entities` / `m.flows` / `m.extras` deciding
   what counts, or a `max()` / substring choosing which map or which object the sentence "meant".
   Those two shapes are all 23 rows the two reviews broke, between them.

6. expect: at most one row carries `data_words`, and the five sentences marked NOT YET WATCHED have
   either become rows or been given a reason they cannot be. They are stale and measurable today,
   so leaving them recorded is a debt, not an answer.
   regression sign: more rows rewording their own sentences, or the five still sitting there
   unexplained after a retro read this file.
