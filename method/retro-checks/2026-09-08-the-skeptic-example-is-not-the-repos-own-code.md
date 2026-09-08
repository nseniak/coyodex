# The skeptic contract's worked example is not a mapped repo's own code

Change (2026-09-08): the caller-discipline paragraph of `method/templates/skeptic-contract.md`
keeps its rule ("a guard's truth lives at its callers") and its shape, and loses the mcpolis
identifiers it carried since 2026-08-29 (`allow_in_cloud`, `settings.mode == "cloud"`, the
development sign-in). On the 2026-09-08 mcpolis build all 38 briefs carried that example, and the
`claims-security-2` batch returned exactly that refutation 3 of 3 — voters who did open the call
sites, but whose agreement on a claim the brief names is uninterpretable either way.

**Partial run, the same night.** One fresh-context skeptic (Opus) was given only a brief filled from
the new template, over the build's own `claims-cadence` batch (11 claims) on a copy of the map:
`grounding lint` well-formed, 11 of 11 rows covered by the evidence check (1 file cited that the
transcript shows only as grep text), and **11 of 11 verdicts agree with the build's three
skeptics'**, including the same 2 refutations. Where it said it had to guess: what the cadence
word `on-boot` may cover (it judged it against the code); whether `evidence` cites the anchor
or the deciding line (it cited the line and named the anchor in the note); how to reach an
element's record when the claims carry no ids (it wrote a one-off slice script instead of
`dump --id`); whether writing its output inside the repo is "changing nothing"; and which half of
a compound claim decides. The template's shape held without the repo's own code in it.

Escalation: none on its own. The open question it leaves ("is the four-build 0-disagreement record
evidence or priming?") is in the backlog, owner: one wave on the new contract.

## Checks

1. expect: 0 skeptic briefs on the next build name `allow_in_cloud` or another identifier from the
   mapped repo's code inside the contract's own text (the claims list may, the rule text may not).
   regression sign: 1 or more.

2. expect: the dev-stub guard's rule site (`dev_stub_oauth_provider.py`, if the map still carries
   it) gets a verdict from voters whose transcripts show the call-site read, whichever way it goes.
   regression sign: 3-of-3 agreement with no call-site read in any voter's transcript.

3. expect: the refutation rate of the security theme does not collapse because the example is
   gone: at least one refutation among the access rules, as on the last four builds.
   regression sign: 0 refutations on a theme that refuted 3+ on each previous build — the example
   was doing the skeptics' work.
