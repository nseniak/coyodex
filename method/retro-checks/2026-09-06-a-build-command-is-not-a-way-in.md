# A command that builds or tests the product is not an entry point

Change (2026-09-06): T4 gains the cut that decides whether a command is an entry point — what the
command ACTS ON decides, and being a test exempts nothing. Stated in both `method.md` (the lead)
and `method/templates/harvest-contract.md` (the harvesting agent, which never reads method.md).
`tools/coyodex/validate_model.py` gains an "Entry-point coverage" line splitting the two arms of
claiming. NO live map was hand-fixed.

Escalation: if check 1 or check 4 fails, the wording did not survive the trip to the agent. Re-run
the partial run (one fresh agent, the changed text, one repo slice) BEFORE accepting the map; do
not hand-edit the rows, because the next build throws the edit away and the silence then reads as
the rule landing.

## What this change is answering

**A map can put its own build pipeline on a product surface, and every check reads clean.** The
"every way in belongs to a surface" advisory asks whether a row has a home, never whether the row
should exist. mcpolis answered it by grouping the pipeline onto a surface: its "Command line" held
**36 ways in, 32 of them build/test tooling** (test runners, a type checker, icon generators, the
local start/stop scripts, fake servers). **31 of those 32 were reached by no use case**, so the
use-case advisory fired 31 times on rows that were never product behaviour, and **15 already had a
`run_commands` row citing the same `path:line`** — the same command recorded twice.

T2b already said "the pipeline that builds and tests the product is not a product interface". That
rule reaches the agent that GROUPS surfaces and nobody else. The cut now sits where the rows are
MINTED, because a row that is never harvested cannot be grouped onto a surface afterwards.

**The wording was tested before shipping.** Three fresh agents ran it over three repos (mcpolis,
argus, mercatus) with no map and no answers. The first draft's unconditional "a test is never an
entry point" fought its own "what it acts on decides" on a smoke test against production; two
agents named that pair unprompted and both dropped the row. The shipped wording adds the tie-break
("what was there BEFORE the command ran"), three cuts (a caller of an existing address, wrappers,
what a container declares for itself) and the guard that a command a person runs is a command
wherever it is written down. On the third repo the rule produced 1 way in out of 38 commands, and
the row it picked was one the author's own gold answer had missed.

## Open, found while doing this and NOT fixed

1. **`run_commands` is defined as "a way to run, build or test this product", and "move it, never
   drop it" now sends things there that are none of those**: a secrets backup, a `help` target, a
   credential wrapper whose target is whatever the caller passes. The array's own description is
   false for those rows. Widening it touches the schema and was left alone.
2. **A way in is still challenged by no skeptic.** The worklist claims a way in's cadence and
   nothing else, so neither a wrong row nor a missing one can reach a verifier.
3. **The use-case arm is still component-level.** Check 6 below records the size of that looseness
   rather than fixing it.

## Checks

1. expect: on a rebuild of mcpolis, the "Command line" surface holds fewer than 10 ways in (it held
   36, of which 32 were build/test tooling).
   regression sign: still 30 or more — the cut never reached the harvesting agent. OR it falls to
   0 or 1 — the cut ate the real operator commands too, which is the opposite failure and the one
   the tie-break exists to prevent.

2. expect: mcpolis's "unclaimed by any use case" advisories fall from 42 external rows to fewer
   than 15.
   regression sign: unchanged; or the count falls while `run_commands` ALSO shrinks, which means
   the cut was read as "drop it" rather than "move it".

3. expect: the `run_commands` table does not shrink on either map. Baselines: mcpolis 48 rows,
   argus 35.
   regression sign: any drop. A command that loses its `entry_points` row must still be recorded,
   and this is the check that "Move it, never drop it" is answerable at all.

4. expect: three mcpolis ACTIONS keep an `entry_points` row on the rebuild — publishing the sandbox
   images, listing the sandboxes the hosting account holds, and smoke-testing the live site.
   **Match the action, never a path.** The rule itself moves a row off a wrapper and onto the
   command that acts, so naming the wrapper's path is asking the rule to break itself.
   regression sign: any of the three actions has no way-in row anywhere.
   FIRST RUN (2026-09-07): scored FAILED against the path form, wrongly. Two of the three paths
   named were wrappers — `run-list-orphan-sandboxes.sh` execs `list_orphan_sandboxes.py`, and
   `prod-smoke.sh` execs `_prod-smoke.mts` — and the rebuild had put each row on the acting command,
   exactly as the wrapper cut says. All three ACTIONS kept a row. The check was wrong, not the map.

5. expect: on a rebuild of argus, a command that acts on the live product gains a way-in row that
   the pre-change map did not have. The candidates are the deploy path and the account-plan and
   stored-snapshot scripts under `scripts/`.
   regression sign: the argus way-in set is unchanged, meaning the rule reached mcpolis and not
   argus.
   REWRITTEN 2026-09-07. The first wording asked argus to record its launch once rather than twice
   — which the PRE-CHANGE argus map already does. It would have passed whether or not the change
   landed, so it measured nothing. An item that the old world already satisfies is not a check.

6. record the number, do not judge it: the "Entry-point coverage" line `coyodex validate` now
   prints. Baselines measured 2026-09-06 — argus **86 external ways in: 73 named by a use case, 13
   reached only through the component a walk touches, 0 unclaimed**; mcpolis **250: 64 named, 144
   component-only, 42 unclaimed**.
   regression sign: the component-only half grows as a SHARE **and the rows that stopped being named
   are `cli` rows**. Both halves are needed. The share alone cannot tell "the cut removed named
   rows" from "use-case authoring stopped naming doors", and on the first run it was the second.
   FIRST RUN (2026-09-07): the share moved 57.6% -> 82.9% and named rows fell 64 -> 24, but **zero
   of the lost namings are `cli` rows** and 40 of the 46 sit on `http-route` / `ui-route` rows that
   still exist. Fewer use cases (50 -> 43) accounts for only 55 of the expected 64. So the alarm was
   true, its stated cause was false, and the naming collapse is a SEPARATE regression this file must
   not claim credit for. It is filed on its own.
