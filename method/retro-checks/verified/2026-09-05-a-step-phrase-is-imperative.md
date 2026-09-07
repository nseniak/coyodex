# A step phrase is imperative, never third person

**Armed** 2026-09-05.

## What this change is answering

The viewer titles a step with its phrase ALONE, with no subject in front of it — because the same line
has to title a step that runs a shared sub-flow, where the text is the walk's NAME. Names are imperative,
for use cases and shared sub-flows alike. A third-person phrase in that slot reads as a sentence whose
beginning is missing.

Before this rule the two forms split cleanly on the two live maps: 1376 of 1379 step phrases were
third person, and 24 of 24 shared sub-flow names and 82 of 82 use case names were imperative. Both maps
were migrated, and `method.md`, `method/model.md` and the trace contract now say imperative.

## Open, and NOT fixed

One other field keeps the third person on purpose, because it is never shown as a title on its own: a
backbone edge's `why` (shown beside its two ends). If a later screen starts titling it alone, it joins
this rule. A Happy Path step's `title` was the other exemption; the field was removed on 2026-09-07
(a step is labelled with its use case's name, which is imperative already), so item 3 below no longer
has a title to keep the rule off.

A step's `note` is also untouched: it is a condition or a qualifier, never an action.

## Checks

1. expect: on a rebuild, every `phrase` on a flow step and on a shared sub-flow's step starts with a bare
   verb — `return the verified email`, not `returns the verified email`.
   regression sign: take the first word of every phrase and flag any ending in `s` that is not a
   plural noun, plus `is`, `has`, `does`, `goes`. A non-empty list means the trace contract's wording
   is not reaching the worker that authors T6, and the fix is in the contract, not in the map.

2. expect: a second verb after `and`, `or`, `then` or a comma is imperative too — `open the screen and
   carry the press to it`, never `and carries`.
   regression sign: any phrase where the first word is imperative and a later coordinated verb is not.
   That is the half-applied rule, and it reads worse than the old form because one sentence carries
   both.

3. expect: the rule stays OFF an edge `why` and a step `note`. (It also stayed off a Happy Path step
   title while that field existed.)
   regression sign: an edge `why` reading `verify service tokens` where it used to read `verifies`.
   The rule has been over-applied.

---

**verified in mcpolis build of 2026-09-07 00:32** (map commit `e430399`, tool stamp
`21de5e3`). All 3 items confirmed by a fresh reader:
**811 of 811 step phrases** start with a bare verb, across 134 distinct first words, 0 flagged ·
37 coordinated `-s` words and 0 third-person verbs among them · **31 of 31** Happy Path titles
and **490 of 490** edge explanations stayed third person, with 63 step notes untouched.

The one `-s` verb the reader paused on, `takes` in UC15.16, coordinates with `is` inside a
content clause rather than with the imperative — correct as written.
