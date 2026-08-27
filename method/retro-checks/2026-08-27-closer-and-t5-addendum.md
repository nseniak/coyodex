# The refutation re-read is a fresh-context closer, and the T5 spec reaches the owner alone

Change: two Phase-4/Phase-1 wiring changes from the 2026-08-27 method assessment · method.md,
method/templates/harvest-contract.md, method/templates/t5-addendum.md, tools/coyodex/contract.py.

1. The re-verify-every-refutation step is now dispatched to ONE fresh-context "closer" agent
   (refuted claims + repo only; returns uphold/reject with the line it read); the lead applies,
   and overruling the closer takes a recorded read of the lead's own (item S3).
2. The T5 entity-card spec moved out of the shared harvest contract into `coyodex contract
   harvest-t5`, appended to the owner's brief alone; the shared contract keeps one sentence
   forbidding everyone else (item H3).

Escalation: if check 1's regression sign appears (a false refutation applied), run the eval before
accepting the map.

## Checks

1. expect: the next build's Phase-4 reconcile shows one closer agent dispatched with the refuted
   claims, and `grounding.note` records rejected refutations (a nonzero rejection count is normal
   — on the motivating build 3 of one batch's refutations were false).
   regression sign: refutations applied straight from the vote with no re-read anywhere, or the
   lead re-reads everything itself with the closer available and does not say why.
2. expect: zero non-owner harvest fragments carry `entities`, while the T5 owner's fragment is as
   complete as before (entities WITH relations; the isolated-entity count in
   `validate --check-coverage` is in line with previous builds).
   regression sign: a non-owner authors entities anyway, or the owner's brief was assembled
   without the addendum and the domain slice comes back thin (entities without relations, missing
   `keyed_by` / `non_entity_types`).
