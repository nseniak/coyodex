# A user-facing surface that no use case reaches is a defect

Change (2026-09-04): `validate` gains an advisory — an interface with `facing: user` that no use
case reaches draws one line, naming the two honest fixes (draw the step, or say `facing: operator`)
and one escape (`In: <why>` under an "Interface exceptions" extras heading) · tools/coyodex/
validate_model.py. NO method text changed, and no live map was hand-fixed.

Escalation: if check 1 fails on a rebuild of argus, a build is reading its own `validate` warnings
and doing nothing about this one — say so in the report. Hand-editing the row is worse than useless
here, because the next build throws it away and the silence then reads as the rule landing.

## What this change is answering

**The map can claim a surface exists for a person and never tell a story that goes near it.**
Nothing checked the pair. `facing` is authored and says who a surface serves; use case walks are
authored separately; no gate joined them.

**One live case, and it is the whole evidence.** argus I7 "Paid reading service" — the anti-bot
service the product pays when its own readers get blocked — is `facing: user`, is carried a second
time as dependency D3 "Scrapfly", and is reached by no use case at all. Its shared sub-use case "Read a page
and store its clean text" mentions paid reading twice in PROSE (step 3 "checks the account still has
paid reading allowance", step 7 "charges the account for the credits the paid reading spent") while
step 5, the one that actually leaves the product, is drawn at I8 "Tracked web pages", the open web.

**The root cause is a box with three far sides.** argus C32 "Page readers" holds three readers: a
plain web request, a headless browser, and the paid service. One step was written for all three, and
it named the far side the two free ones reach. Nothing in the method says a step must name the far
side of the reader it is actually about, and this change does not add that rule.

**Measured before shipping: 5 of the 28 surfaces across the two live maps are in no use case.** Four
are operator-facing (argus "Shipped logs"; mcpolis "Command line", "Crash reports", "Log store") and
stay silent. One fires. Zero false alarms.

**The `facing: operator` exemption IS the check.** Crash reporting, log shipping and an ops command
line exist so the team can run the product; no use case is expected to reach them. Firing on those
four would bury the one real case under four false ones, and an advisory that is usually wrong is an
advisory people learn to skip.

**"Reached" takes THREE arms, the same three `interface_walk_order` already used** — a use case
naming one of the surface's `ways_in`, a walk step drawn at the surface, or a walk step drawn at a
dep standing on it. The third arm scores zero on both live maps, and is kept for the day a step
names a `Dn` rather than the surface it is met at.

## Open, found while doing this and NOT fixed

1. **One outside service wears two names and no screen joins them.** argus carries the same company
   as D3 "Scrapfly" on Dependencies and as I7 "Paid reading service" on Interfaces. A reader of
   either screen has no way to learn they are one thing. This is a viewer defect, not a map defect,
   and it is what made the single case look like two.

2. **No rule covers one component with several far sides.** See the root cause above. The advisory
   catches the SYMPTOM on a surface that ends up unreached; it says nothing when a coarse step
   names one real far side and hides another.

3. **`facing` is authored and unverified.** The advisory offers `facing: operator` as a fix, which
   is correct when the surface really does serve the team, and is also the lazy way to silence the
   line. Check 2 below is the only thing watching for that.

## Checks

1. expect: on a rebuild of argus, "Paid reading service" is reached by a use case — a step drawn at
   it in the page-reading walk — or an "Interface exceptions" line says why no story crosses it.
   regression sign: the advisory fires again with neither. A build is reading its warnings and
   skipping this one, or the warning does not say clearly enough what to do.

2. expect: no surface acquires `facing: operator` in a rebuild where the previous map said `user`,
   unless the rebuild also explains it.
   regression sign: the advisory count goes to zero because surfaces were re-labelled rather than
   re-storied. The cheapest fix was taken and the map got less true.

3. expect: the advisory stays rare — at most one or two per map.
   regression sign: it fires on five or more surfaces of one map. Either the `facing: operator`
   exemption is drawn in the wrong place, or that product genuinely reaches most of its surfaces
   outside any story, which would make the whole check the wrong shape.

4. expect: the number of `facing: user` surfaces does not fall on a rebuild while the number of
   `facing: operator` ones rises by the same amount.
   regression sign: a straight swap. Same failure as check 2, visible as a count when the individual
   rows are hard to compare.

---

**RETIRED 2026-09-05, SUPERSEDED AND NOT VERIFIED.** Its premise — "the `facing: operator`
exemption IS the check" — was measured wrong and is gone one day later: 7 of the 11
operator-facing surfaces across the two live maps already had use cases, so the exemption was
hiding the 4 real gaps rather than sparing false ones. Every interface owes a use case now.
Checks 1, 2 and 4 above are still worth watching and were carried into
`2026-09-05-what-crosses-is-a-step-with-a-direction.md`; check 3 ("at most one or two per map")
is void, since removing the exemption is what makes more of them legitimate.
