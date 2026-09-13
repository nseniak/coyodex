# `validate --json` carries the sweep worklist as rows

Change (2026-09-09): `coyomap validate --json` emits `sweep_worklist`, one row per anchored flow
step that reads like a decision no rule claims, mirroring `audit --json`'s `worklist`. On the
2026-09-08 mcpolis build the lead hand-parsed the clipped prose advisory (turn 335), searched the
JSON for a key containing `sweep` and got nothing (turn 337), and re-ran it searching string values
(turn 339) — three turns for a list the tool held.

Escalation: none on its own.

## Checks

1. expect: the next build reads the sweep rows from `validate --json` (a `sweep_worklist` read in
   the transcript) and never from the advisory text.
   regression sign: a `python3 -c` over the advisory's prose, or a grep for `DECISION`.

2. expect: the row count in the JSON equals the count in the advisory sentence.
   regression sign: the two disagree, meaning one list is clipped.
