# The gate block counts one claim surface, and says which unvoted claims were pinned

Change (2026-09-08): `anchor-drift` takes `--with-behavioural`; `finalize` passes it to its
verdict-based drift leg at the record's tier, and `ship` passes it at step 2 when the pinned
worklist is behavioural, so `challenged N of M` and `N L2 claims on the grounding worklist` count
ONE surface. And the three sentences that explained a shipped claim with no verdict (the gate block,
`grounding write`'s NOTE, `ship`'s coverage line) share `grounding.unvoted_reason`, which splits
the count into claims pinned and never challenged and claims minted or reworded after the pin.
The 2026-09-08 mcpolis gate block read `challenged 817 of 833` under `1782 L2 claims`, and called
all 965 unvoted claims "minted after the worklist was pinned" when 949 had been pinned from the
start and left unchallenged by a partial pass.

Escalation: none on its own.

## Checks

1. expect: in the gate block of a build that pinned a behavioural worklist, the drift leg's
   `challenged N of M` has the same M as the audit leg's `M L2 claims on the grounding worklist`.
   regression sign: two different M in one gate block.

2. expect: on a partial pass, the shipped-map line reads `<u> do not. <n> were pinned and never
   challenged; <a> were minted or reworded after the worklist was pinned`, with `n + a = u` and
   `a` equal to the record's `claims_added_since`.
   regression sign: every unvoted claim called "minted after the pin" on a pass whose grounding
   note says a theme was left unchallenged.

3. expect: `grounding write`'s NOTE and `ship`'s COVERAGE line in the transcript carry the same
   split as the gate block.
   regression sign: one of the three sentences saying something the other two do not.

verified in reminderrepo build of 2026-09-13 23:03
