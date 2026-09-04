# What crosses a surface is a PAIR: the authored rows, and the walk steps beside them

Change (2026-09-03): the viewer shows `interfaces[].carries[]` and the walk steps drawn at the same
surface SIDE BY SIDE on that surface's own page, and an actor's page switches from the authored rows
to that actor's OWN steps. New derivations `interface_walk_steps` and `interface_steps_by_use_case`.
The audit worklist now challenges SUB-FLOW step phrases too. The advisory demanding a `where` on
every crossing is deleted · method.md, method/model.md, tools/coyodex/validate_model.py,
features.py, audit_model.py, the viewer.

**`carries[]` IS NOT REMOVED.** A change deleting it in favour of the derivation was written in full
and then reverted after an adversarial review. Do not propose the merge again without reading the
`interface_walk_steps` docstring first.

Escalation: if check 1 fails — a surface's page shows the two blocks saying the same thing — the
method's "say the thing a step cannot" instruction did not land, and the field is drifting back into
being a summary. If check 4 fails, the audit change cost more than it bought: run the eval before
accepting the map.

## What this change is answering

**The authored rows were accused of being a hand-written summary of the walks, and the accusation
was measured and did not hold.** Measured on the three live maps:

- **16 of the 39 surfaces have no walk step at all**, so the derivation would have turned 22
  authored sentences into silence — including every one of coyodex's own 11 surfaces, whose map
  draws no doors. Three of the 22 are redaction guarantees ("a log record, with secret-shaped fields
  and credential headers stripped before it leaves the host") that no story reaches.
- **Direction is not derivable.** A step records who talks to whom, not which way data goes: a PULL
  points outward while its data comes back, and the map draws that as one step. Reading polarity as
  direction flipped argus's "Tracked web pages" from `in` to `out` — the surface argus exists to
  read — and on every disagreement across the two maps the AUTHORED value was the better one.
- **No step names the records that cross.** `carries[].elements` holds 71 entity references across
  the three maps and answers "are the plan limits exposed?"; a step answers nothing of the kind.

What the walks DO add is grounding: every step is a line in the code a skeptic has already been sent
at. So the two are shown together, and neither is derived from the other.

**Two real defects were fixed on the way.** An actor's page fell back to EVERY step at a surface when
the walks named no step of that actor's own, so argus told a reader that the software "Assistant"
picks a Google account and approves — a step belonging to the human "Visitor". And the audit worklist
read `flows[].steps` only, so 195 sub-flow step phrases across the three maps (coyodex 59, argus 65,
mcpolis 71) reached readers with no skeptic on them.

## What the partial run changed, and one thing it found in a LIVE map

The `carries[]` guidance was rewritten after a tier-2b run, on both live maps, measured against the
rows those maps actually ship:

| | rows | words/row | over the 20-word rule | guarantee-shaped claims with nothing behind them |
|---|---|---|---|---|
| mcpolis, shipped | 7 | 13 | 0 | 1 |
| mcpolis, first wording | 20 | 29 | 18 | 3 |
| mcpolis, after the fix | 7 | 13 | 0 | 0 |
| argus, shipped | 4 | 12 | 0 | 0 |
| argus, first wording | 7 | 26 | 5 | 3 |
| argus, after the fix | 6 | 13 | 0 | 0 |

The first wording said "prefer the guarantee over the mechanism" and gave no way to get one honestly.
Both readers filled the gap by inference — "no other account's pages", "no password is typed here",
"nothing outside what the command names is removed" — each a security claim reasoned out of prose
with no code read. That is the failure that shipped a refuted privacy fact on the 2026-09-02 map.
The fix bounds it: a guarantee needs a line you have read, and a row with no guarantee is complete.

**AND IT CAUGHT ONE IN A SHIPPED MAP.** mcpolis's live row "A newly minted agent credential, shown
exactly once" is that shape. Under the new wording the reader refused to write it: *"I have no code
line that proves the value is not readable later."* Either that row earns an anchor or it loses its
"once". It was not touched here, because a hand edit to a built map is thrown away by the next build.

## Checks

1. expect: on a surface with both, the "What crosses" rows and "What the stories show here" say
   DIFFERENT things — the rows name a direction, the records, or a guarantee (what is stripped,
   hashed or masked); the steps name what happens. Open the busiest `ours` surface and read both.
   regression sign: a row that re-tells a step in other words. The field is becoming a summary
   again, which is exactly what it was nearly deleted for.

2. expect: every surface still carries `carries[]` rows, including the ones no walk reaches. On the
   previous mcpolis map that was 16 of 16 surfaces and 35 rows; on argus 12 of 12 and 31.
   regression sign: a surface with walk steps and NO authored rows — the build read the new second
   block as permission to stop authoring the first.

3. expect: no screen states a direction that is not authored. Grep the built viewer payload: an
   interface's `steps[]` entries carry `phrase`, `container`, `n`, `role` and NOTHING named
   `direction`.
   regression sign: a `direction` key on a derived step, or an `in`/`out` mark on an actor's page —
   the underivable claim has come back.

4. expect: `audit` challenges every sub-flow step phrase, once each, under its own `SFn` id. The
   behavioural worklist grows by roughly the sub-flow phrase count (coyodex +59, argus +65,
   mcpolis +71) and no `SFn` step appears twice.
   regression sign: a claim reading `UCn step n` whose phrase lives in a sub-flow — expansion crept
   in and several skeptics are being sent at one line.

5. expect: `validate` raises no crossing-anchor advisory on any map, and an interface grounded ONLY
   by a crossing's `where` still passes. coyodex's Settings and Project source files are that case.
   regression sign: either the advisory returns, or those two surfaces start failing "grounded by
   nothing" — the grounding arm was removed along with the advisory, and it must not be.
