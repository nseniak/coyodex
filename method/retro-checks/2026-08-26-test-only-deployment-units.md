# A unit only the test suite starts never becomes a deployment row

Change: one method sentence under Deployment & topology — a test-harness-only unit is not a
deployment unit (its code is out of scope, so it is born as a dead empty box and fails the
linkage gate) · method.md.

Escalation: none — the linkage gate itself already blocks the symptom.

## Checks

1. expect: the next MCP Hero build ships zero deployment units whose only manifest is the test
   harness's (no "OAuth test MCP server" row or sibling), and the deployment linkage gate reports
   0 empty units.
   regression sign: an empty unit returns, sourced from a compose/manifest file under tests/.
2. expect: the real deployment units (the product's own processes and infra) are all still
   present — the rule removed a test row, not real topology.
   regression sign: the unit count drops below the product's real process count, or a unit the
   app genuinely runs disappears alongside the test one.
