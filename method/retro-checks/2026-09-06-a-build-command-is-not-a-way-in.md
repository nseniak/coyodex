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

4. expect: three mcpolis commands KEEP an `entry_points` row on the rebuild — the sandbox image
   publisher (`runner/e2b-templates`), the orphan-sandbox lister
   (`backend/tests/integration/run-list-orphan-sandboxes.sh`), and the live-site smoke test
   (`internal/scripts/prod-smoke.sh`).
   regression sign: any of the three missing. The first two prove "acts on a live provider" landed;
   the third is the only test in either repo that acts on production, and it is what
   "being a test exempts nothing" was written for.

5. expect: argus records its service launch as ONE way in, not two. `backend/src/argus/main.py` is
   the row; `make run` is its wrapper and gets a `run_commands` row only.
   regression sign: two rows for one launch (the wrapper cut did not land), or none (the launch
   was read as a local start script).

6. record the number, do not judge it: the "Entry-point coverage" line `coyodex validate` now
   prints. Baselines measured 2026-09-06 — argus **86 external ways in: 73 named by a use case, 13
   reached only through the component a walk touches, 0 unclaimed**; mcpolis **250: 64 named, 144
   component-only, 42 unclaimed**.
   regression sign: the component-only half grows as a SHARE of the total on a rebuild. That would
   mean the cut removed rows a use case had named rather than rows nobody claimed, which is the
   quiet way this change could make coverage look better while making it worse.
