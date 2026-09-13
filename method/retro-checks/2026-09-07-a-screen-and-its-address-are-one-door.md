# A screen and the address it calls are one door, not two

Change (2026-09-07): `method.md` gains a clause under the front-door rule saying a screen and the
address that screen calls are ONE door, and that a split needs two places a person can ARRIVE from.
`tools/coyomap/validate_model.py` gains a per-kind naming advisory, with an "Entry-point coverage"
line as its escape.

Escalation: if check 1 fails on a rebuild, the wording is not the lever and the advisory is the
whole fix — say so in the report rather than re-wording again.

## What this change is answering

**A rule meant to produce MORE use cases produced fewer, and cost the map 40 of its named doors.**

The front-door sentence widened between the two builds:

- before: *"Two PARTIES who reach the same goal through DIFFERENT front doors are TWO use cases."*
- after: *"One goal reached through DIFFERENT front doors is TWO use cases — whether that is two
  parties or ONE party arriving two ways."*

Under the first, an admin naming both their screen and the address behind it was one use case with
two doors, and 24 of 50 use cases did exactly that. Under the second, that same pairing reads as one
party arriving two ways. The next build did not split it. **It kept the screen and dropped the
address**, and said so in its own words: *"It caught that I gave one use case two front doors on two
different surfaces — the second is traversal, not a trigger, so I'll drop it."*

**Measured per kind, and only the action-level kinds moved:**

| kind | 2026-09-02 named | 2026-09-07 named |
|---|---|---|
| `http-route` | 38 of 114 (33%) | **2 of 118 (2%)** |
| `mcp-tool` | 6 of 43 (14%) | **1 of 43 (2%)** |
| `ui-route` | 20 of 39 (51%) | 21 of 36 (58%) |

Use cases went 50 → 43, the opposite direction a splitting rule produces. Ways in named by a use
case went 64 → 24, and 40 of the 46 lost namings sit on rows that still exist at the same anchor.

**Nothing counted it.** `validate` prints the coverage split on its second line, and it is a report
line with no advisory. The build's lead saw it once, before any naming existed, reading 0/0/0; every
later run filtered it out with `tail -60` or a `grep` for advisory bullets. The advisory that does
exist is binary — "No use case names ANY entry point" — and goes quiet at the first link, so 45
links silenced it exactly as 73 would have.

**The new advisory separates the two builds** and, run on the older map, independently rediscovers a
defect found by hand the same week: `cli`, 0 of 36 named, which was that map's build-and-test
pipeline sitting on a product surface.

## Open, found while doing this and NOT fixed

1. **Neither build ever did the per-row walk the method asks for** over the 118 addresses. The older
   build's pairing covered 38 of them as a side effect of how it wrote use cases.
2. **Whether naming the screen alone is WRONG is arguable.** The person does open the screen. What
   is unarguably lost is that no use case now says which address its action fires.
3. **The coverage split still does not reach `finalize`**, so it stays out of the committed report
   where a grep cannot hide it.

## Checks

1. expect: on a rebuild of mcpolis, `http-route` naming is back above 25% — 30 or more of ~118 rows
   named by a use case — and the advisory is silent for that kind.
   regression sign: still under 10%. The wording is not the lever; the advisory is the whole fix.

2. expect: the use-case count does not fall again. Baseline 43, and the two builds before it were
   50 and 50.
   regression sign: another drop, meaning the splitting rule is still being read as a merging rule.

3. expect: use cases that name a screen name the address behind it as well, on the same row. Spot
   check the upstream-admin stories: several sharing one `App.tsx` row is the shape this fixes.
   regression sign: one screen row named by five or more use cases. On the 2026-09-07 map one row
   was named by seven.

4. expect: the advisory stays rare — at most one kind per map.
   regression sign: it fires on three or more kinds at once, which would mean the floor is drawn in
   the wrong place rather than that the map collapsed.

5. expect: no build silences it with a recorded line instead of naming the doors.
   regression sign: an "Entry-point coverage" line reading `http-route naming: <why>`. That is the
   cheap fix, and it makes the map permanently unable to say who opens its addresses.
