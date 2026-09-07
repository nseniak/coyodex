# The behavioural note says what the code does

Change (2026-09-07): the NOTE printed by `coyodex audit --with-behavioural` in
`tools/coyodex/audit_model.py` no longer states a limit that was removed. Tools only; no method text
changed and no map was edited.

Escalation: none on its own. But if check 1 fails, the map's whole behavioural half stays
unwarranted for a fourth build, and that row should be raised to the top of the ledger rather than
carried again.

## What this change is answering

**The message told operators the opposite of what the code does, and a build reads the message.**

`--with-behavioural` adds the claims that cover the walk a reader follows: flow titles, step
phrases, use cases. The record path was fixed so a pinned behavioural worklist folds into the
grounding record — the comment two lines above the message says so outright, "THE LIMIT THIS USED TO
STATE IS GONE". The message kept saying the limit stands, and ended with the instruction **"keep the
record on the default worklist until the record path follows this flag"**.

So three consecutive retros filed the same row — *grounding claims naming a use case, flow, happy-
path step or capability: 0 of 935* — as **landed but ineffective**. A fix had landed each time. The
thing that landed was still telling operators not to use it.

**Measured on the mcpolis map of 2026-09-07, the day this was found:**

| | claims |
|---|---|
| default worklist | 933 |
| with the behavioural tier | 1787 |
| of those, `behaviour` theme | 854 |
| superseded if the record follows the pinned tier | **0** |
| superseded if it stayed at the default tier | 854 |

The old message was right only about the second row, and the second row has not been true since the
record path was fixed.

## Open, found while doing this and NOT fixed

1. **The method still frames the tier as a budget choice** — "Turn it on when the budget is there"
   (`method.md`, the batching paragraph). That is a real cost: the worklist roughly doubles, 933 to
   1787 on this map. Whether the behavioural half of every map should be verified by default is an
   operator's decision about money, not a defect, and it is left open deliberately.
2. **899 rows are still unwarranted on the shipped map.** This change makes the next build able to
   cover them; it does not cover them.

## Checks

1. expect: the next build that passes `--with-behavioural` gets its behaviour claims INTO the
   grounding record — `claims_superseded` does not jump by the size of the `behaviour` theme.
   Baseline to beat: 854 behaviour claims, 0 superseded when the record follows the pin.
   regression sign: `claims_superseded` lands near the behaviour count, meaning the record path
   silently went back to the default tier while the message says it does not.

2. expect: no build's transcript quotes the old sentence back as a reason to skip the tier. Search
   the lead's turns for "default worklist".
   regression sign: a build cites it. The message reached the model and the model believed it, which
   is exactly what happened for three builds.

3. expect: if a build does NOT pass the flag, its own note says why in `grounding.note` — a budget
   decision stated, not a silence.
   regression sign: the behavioural half is skipped with nothing recorded, which reads identical to
   nobody having considered it.

4. expect: the message and the comment beside it continue to agree. A test pins this
   (`tests/test_audit.py::test_the_behavioural_note_does_not_repeat_a_limit_that_is_gone`).
   regression sign: the test is deleted or weakened rather than the message being kept true.
