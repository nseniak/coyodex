# `finalize` checks the grounding digest at the tier the record was written at

Change (2026-09-08): `tools/coyomap/finalize.py` reads which claim tier the map's grounding record
describes off the record's own digest, runs its audit leg at that tier, and compares the digest
with the surface it hashed. Before, `grounding write --map` hashed the live surface at the pinned
worklist's tier while `finalize` re-hashed at the default tier always. The 2026-09-08 mcpolis
build, the first to pin a behavioural worklist, got "the record's `live_claims_digest` does not
match this map's claim surface" on a record that matched its map exactly (1782 claims hashed, 833
compared), and a gate block counting 833 claims beside a record counting 1782.

Escalation: none on its own.

## Checks

1. expect: on a build that pinned a behavioural worklist, the finalize report prints no
   `live_claims_digest` mismatch, and `python3 -c` recomputing the digest at
   `l2_worklist_model(m, behavioural=True)` matches the record's.
   regression sign: the mismatch advisory on a map whose behavioural-tier digest matches.

2. expect: the gate block counts ONE surface: the audit leg's "N L2 claims on the grounding
   worklist" equals the record's live count (`claims_total - claims_superseded +
   claims_added_since`, which is the size of the shipped surface).
   regression sign: two different claim counts in one gate block, as on 2026-09-08 (833 and 1782).

3. expect: a surface that really moved still fires. A claim edited after `grounding write` and
   before the final assemble produces the mismatch, and the advisory says the record matches
   neither tier.
   regression sign: silence on such a build. The tier detection has become a way to pass.
