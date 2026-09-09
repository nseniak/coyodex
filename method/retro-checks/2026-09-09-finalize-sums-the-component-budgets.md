# `finalize` sums the harvest budgets against what shipped

Change (2026-09-09): a harvest fill records its «EXPECTED_COMPONENTS» in
`.coyodex/verify/budgets.json`, and `finalize` carries a `component budget` leg: the sum of the
budgets against the shipped component count, held to the same ±40 % band each slice is held to,
with the code-derived expectation E beside it. Advisory, never blocking. On the 2026-09-08 mcpolis
build 60 components were budgeted and 114 shipped, every slice over and 7 of 10 past their own
band, and the whole-map reading arrived about 450 turns later in a `Balance exceptions` record
(retro row 28). The leg is absent, not clean, when no budgets were recorded.

Escalation: none on its own.

## Checks

1. expect: `finalize-report.md` on the next build carries the `component budget` leg with a
   non-zero brief count.
   regression sign: the leg absent on a build whose harvest briefs were filled with the verb.

2. expect: when the sum is outside its band, the `Balance exceptions` record explains the map's
   size at assemble time, in the same turn window as the finalize run.
   regression sign: the advisory present and the explanation written hundreds of turns later, or
   never.
