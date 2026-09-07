# The behavioural tier runs, instead of being available

Change (2026-09-07): `method.md` turns "turn it on when the budget is there" into **RUN IT**, with a
recorded `behavioural: <why not>` line under an "Entry-point coverage" extras heading as the escape.
Method text only. No tool changed; the flag already works.

Escalation: if check 1 fails, an instruction has now produced what a suggestion produced, and the
answer is a `validate` advisory rather than more words. Say so in the report.

## What this change is answering

**The half of the map a reader actually reads is the half nobody has ever checked.** Machinery gets
claims — components, dependencies, rules, storage. The walk does not: use case names, story titles,
step phrases, happy-path steps. **899 rows on the 2026-09-07 mcpolis map carry zero claims.**

The method has said "turn it on when the budget is there" for three consecutive builds. **No build
ever turned it on.** Three retros filed the row as "landed but ineffective" and none found why,
because the cause was not budget: the flag's own NOTE told every build the grounding record could
not hold the result, and went on saying so after that was fixed. A soft suggestion, answering a
message that was wrong, produced nothing three times running.

**The cost, measured.** The worklist goes 933 → 1787 claims on that map, of which 854 are this
theme. The readers that check claims cost $69 of a $341 build, so this adds about a fifth to a
build's bill. Not double, which is what "roughly doubles the worklist" reads as if you do not know
that the worklist is not the bill.

## Open, and deliberately not done here

**No check enforces this.** The escape is a recorded line under a heading a tool already reads, but
nothing verifies that a build either ran the flag or wrote the line. A `validate` advisory — the
grounding record shows zero `behaviour` claims and no `behavioural:` line is recorded — would make
it checkable every build rather than only when a retro runs. It is not written here on purpose:
three advisories shipped the day before this each missed the defect they were written for, and a
fourth written at the same speed is not what this needs. **Propose it after check 1 has run once.**

## Checks

1. expect: the next mcpolis build passes `--with-behavioural`, and its grounding record carries
   `behaviour`-theme claims. Baseline to beat: **0 of 899 behavioural rows claimed**; target on that
   map is ~854 claims added.
   regression sign: zero again, with no `behavioural:` line recorded. An instruction has then done
   what a suggestion did, and the answer is the advisory named above.

2. expect: if a build skips it, `grounding.note` and a recorded line both say so, and the reason is
   about budget rather than about the flag not working.
   regression sign: a note repeating the old limit — "the record cannot hold behaviour claims".
   That message was corrected on 2026-09-07; a build repeating it is reading something stale.

3. expect: `claims_superseded` does not jump by the size of the `behaviour` theme. Measured:
   0 superseded when the record follows the pinned tier, 854 when it does not.
   regression sign: a number near 854, meaning the record path silently returned to the default
   tier while the message says it does not.

4. expect: the added claims find something. A first behavioural pass on a map that has never had one
   should refute or correct at least a handful of step phrases.
   regression sign: 100% confirmed across 854 claims. That is not a clean map, it is a pass nobody
   read — the same shape as a skeptic batch confirmed by grep rather than by opening the anchor.
