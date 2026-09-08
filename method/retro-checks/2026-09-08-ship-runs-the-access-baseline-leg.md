# `ship` runs `finalize`'s access-baseline leg against the newest archived map

Change (2026-09-08): `tools/coyodex/ship.py` passes `--access-baseline <newest
.coyodex/dev-rebuilds/NNNN/project-map.json>` to `finalize` when one exists and no baseline was
given; `finalize`'s access-baseline advisory names every lost file instead of 8 and `+N more`.
On the 2026-09-08 mcpolis build the leg ran 0 times in 537 turns while the `auth-surfaces-no-drop`
gate beside it failed (68 → 57); run afterwards it named 19 of 60 files that had held access
enforcement and were claimed by no rule.

Escalation: none on its own.

## Checks

1. expect: on the next build of a repo with an archive, `finalize`'s output carries the
   `access baseline` leg, and the gate block lists it with its count.
   regression sign: the leg absent from a build whose repo has `dev-rebuilds/`.

2. expect: every lost file is named in the report (count in the sentence equals names listed).
   regression sign: `+N more file(s)` in the leg's advisory.

3. expect: the lead answers the list before the commit: each named file either regains an access
   rule, or gets a `<path>: <why>` line under "Access baseline exceptions".
   regression sign: the leg's advisory shipped as carried with no line recorded.
