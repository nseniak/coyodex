# What crosses a surface is a walk step, and the step says which way

Change (2026-09-05): `interfaces[].carries[]` is REMOVED from the model, the method, the tools and
all three maps on disk. Its one underivable fact becomes `flows[].steps[].direction`
(`in` / `out` / `both`), owed by every step where the map's OWN CODE touches a surface or a record;
a DOOR is exempt, being a human action with no product end. `validate` drops the `facing: operator`
exemption, so EVERY interface owes a use case. The method gains the operator-actor rules and the
sweep back from the interfaces table to the use case list. Four operator use cases were written into
the two live maps, and argus's paid page-reading service got the step it always owed ·
method.md, method/model.md, tools/coyodex/, the three maps.

Escalation: if check 1 fails on a rebuild, an agent is not filling `direction` and the advisory is
not enough — say so and propose promoting it to blocking, rather than hand-filling the field, which
the next build throws away.

## What this change is answering

**`carries[]` was one sentence per direction, authored beside the walks and checked against
nothing.** Every part of it was measured on argus and mcpolis before removal:

- **The sentence repeated the steps.** Overlap with the interface's own description plus its step
  phrases: 13% where no step reached the surface, rising to 66% at the surfaces with more than 20
  steps. 4 rows were word-for-word copies of a single step. At the busiest surfaces the words that
  were genuinely new were mostly paraphrase (*wants, supplies, including, deciding, doing, lately*).
- **The records were not the important ones.** 68 references, of which 31 were already named in a
  use case walk that reaches the surface. Of the 37 that were not: 14 transient wire shapes, 12
  pieces of other records, 9 computed views, and **2** real independent stored records.
- **It was where an unbacked claim could live.** mcpolis's dashboard row said a new agent credential
  is "shown exactly once". Nothing in the map backs it, no step says it, and it sat outside every
  arm of the audit worklist. A step has an anchor; that sentence had none.
- **Direction was the one thing a step could not say**, so the step now says it.

**AN EARLIER REMOVAL, WITHOUT THE STEP DIRECTION, WAS BUILT AND REVERTED.** That is the part worth
remembering. Direction was the real objection then, and the other two were closed rather than argued
away: coverage, by making every interface owe a use case; the records, by measuring what they were.

**`direction` answers at a RECORD too, and that is not a bonus.** 83 of the 170 record steps across
the two maps sit on a component/record pair whose arrows say BOTH read and write, so the map could
not say which the step was. One field, one reading, both places.

**The `facing: operator` exemption was hiding real gaps.** It came from 5 unstoried surfaces, 4 of
them operator-facing, read as "operator surfaces do not get stories". The fuller count says the
opposite: 7 of the 11 operator-facing surfaces across the two maps ALREADY have use cases, and each
of the 4 without names a person in its own description ("the log records an operator searches").

## What was done to the live maps, and how

The 648 boundary and record steps were seeded by a ONE-TIME migration reading structure first and
the phrase only where structure could not answer, then CHECKED against the `carries[]` directions
each map had authored by hand. One interface per map disagreed, both the same shape: a marketing
site authored `out` only, whose steps show visitors opening pages. The step-level answer was kept as
the more complete one — the surface-level answer summarised the CONTENT and could not report the
traffic.

**Reading a direction off a phrase is exactly what the method forbids, and it was right to.** The
first pass of that migration called `In → Rn` "shows the page in the browser" INBOUND, because
"shows" sat in the wrong verb list. Structure had to come first. This is a migration, not a rule.

**The seeded record directions were then CROSS-CHECKED against the `C→E` arrow verbs**, on the 82
record steps whose arrows give one unambiguous answer. 8 disagreed, and reading each one settled a
different question:

- 3 were the migration's fault — "picks the pricing wording", "merges the tool's fixed arguments
  into" — read verbs that were in no verb list. Corrected by hand to `in`.
- 5 were the ARROWS being coarse: `C30 → E14` "reads the summary documents for that page" sits on a
  pair whose only arrow says `persists`. THE STEP WAS RIGHT AND THE ARROW WAS NOT, which is the
  clearest evidence that this field had to live on the step. A derivation from the arrows would have
  written `out` on three plain reads.

argus's paid page-reading service got the step it always owed, in the shared page-reading walk,
anchored at the real call site.

## Open, and NOT fixed

1. **The three redaction promises are gone.** "Stripped of credentials before it leaves", "with
   secret-looking values masked twice on the way", "with secret-shaped fields and credential headers
   stripped". Nitsan decided to let them be lost rather than keep a field for three sentences. A
   step phrase CAN carry one, and nothing requires it.
2. **`direction` is advisory, not blocking, when missing.** Deliberate: a gate on a brand-new
   required field walls off every rebuild before one build has shown an agent filling it. Check 1
   is what decides whether it gets promoted.
3. **Coyodex's own map is the real cost, and the headline numbers hide it.** Every measurement
   above is from argus and mcpolis. The third map on disk draws no doors, so all 11 of its surfaces
   had no walk step: it lost 15 authored sentences and every one of its 11 direction answers, and
   states nothing in their place until its walks get doors. It is stale and not rebuilt, which is
   why this was accepted rather than fixed — but "5 of 28 surfaces had no step" is the two-map
   number, not the whole truth, and the next rebuild of coyodex's own map is where the bill lands.
4. **One outside service still wears two names.** argus carries the same company as dependency
   "Scrapfly" and interface "Paid reading service", and no screen joins them. A viewer defect, not
   a map defect. Nitsan chose not to log it.

## Checks

1. expect: on a rebuild, every step touching a surface or a record carries a `direction`, and
   `validate` reports no missing ones.
   regression sign: the advisory names more than a handful. The instruction is not reaching the
   worker that authors T6, and the field should be promoted to blocking instead of re-explained.

2. expect: no surface is authored with a direction of its own — no revived `carries`, no `flow`
   field, no `crosses` column written by hand.
   regression sign: any per-surface direction. An interface's directions are the SET its steps
   carry, and a second copy is a second thing to disagree with.

3. expect: a rebuild of argus reaches the paid page-reading service from the page-reading walk, and
   a rebuild of either map leaves no interface unstoried without a recorded exception line.
   regression sign: the surface comes back unstoried. The sweep back from the interfaces table is
   not being run, and it is the pass that closes the ordering hole this whole change came from.

4. expect: operator use cases appear at all, and mcpolis's command line carries one or two rather
   than none.
   regression sign: zero operator use cases. The operator rules are not landing, and the sweep back
   is being answered with recorded exceptions instead of stories.

5. expect: those operator use cases are about the RUNNING SERVICE, not the build.
   regression sign: use cases covering test runs, icon regeneration, code export or release
   preparation. Test 2 (it acts on the running service) is being skipped, and the map is filling
   with developer work.

6. expect: no surface acquires `facing: operator` where the previous map said `user`, and the count
   of `facing: user` surfaces does not fall while `operator` rises by the same amount.
   regression sign: a straight swap. Carried from the retired 2026-09-04 check, and it matters MORE
   now that the operator exemption is gone: re-labelling a surface no longer silences anything, so
   a swap would be a map made less true for no gain at all.

7. expect: a `direction` of `both` stays rare and is used for a real exchange (a code traded for a
   verified email, an upsert that returns the stored row).
   regression sign: `both` on a large share of steps. It is being used to avoid deciding, and the
   surface then reports both directions on everything, which says nothing.

8. expect: `direction` is read from the PRODUCT, so a PULL (`Cn → In` "fetches…") is `in` even
   though the arrow points outward, and `In → Cn` is `in` too.
   regression sign: directions that track the ARROW instead — argus's "Tracked web pages" flipping
   to `out`. The reading has been taken from the arrow, which is the mistake this field exists
   around.

9. expect: DOORS carry no direction, and the surface's own reported directions therefore describe
   what the PRODUCT sends and receives, not what a person does.
   regression sign: a door carrying one. Forcing an answer there is what put the word "receives" in
   front of a step whose own phrase said "sends each finished record out" — a label contradicting
   its own line, on argus's shipped logs.
