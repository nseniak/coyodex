# The harvest fan-out no longer invites authoring `security[]` rows

Change: the harvest contract stops listing `security` as an ownable array (three mentions removed
or replaced with "never author it; note auth facts in your reply"), and `method.md`'s Phase-1 slice
guidance says "entry-points harvest" / "entry-points slice" where it said
"entry-points+security harvest" / "the security slice" · method/templates/harvest-contract.md,
method.md. The T7 fold made an auth surface an `access` business rule, written after the trace;
the contract still carried the pre-fold instruction, contradicting it.

Escalation: if check 2 fails (the auth surface shrank), run the eval before accepting the map —
`finalize --access-baseline` is the per-file view of the same risk.

## Checks

1. expect: zero `security[]` rows authored across the next build's harvest fragments, and zero
   `lint-fragment` legacy-security advisories in the agents' transcripts.
   regression sign: any fragment carries a `security` array; the lint advisory fires and is
   shrugged off or justified.
2. expect: the auth surface did not shrink for it — the count of `access: true` rules in the next
   build's map is in line with the repo's real guard surface, and every harvest agent that met an
   auth guard named it (file:line) in its REPLY, so the rules fan-out was seeded.
   regression sign: guards a harvest agent read (middleware, decorators, token checks) reach
   neither a reply note nor any rule's `sites`, and the Security & auth table is thinner than the
   previous map of the same repo with no code change explaining it.
3. expect: the Phase-1 fan-out still splits the entry-points slice by router / surface on a large
   route surface, and dispatches T5 and entry-points first — the wording change removed the word
   "security", not the sizing or ordering advice.
   regression sign: one oversized entry-points slice becomes the Phase-1 straggler, or launch
   order stops putting the heaviest slices first (L3 assertion 16).
