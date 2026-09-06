# A step phrase is imperative, never third person

**Armed** 2026-09-05.

## What this change is answering

The viewer titles a step with its phrase ALONE, with no subject in front of it — because the same line
has to title a step that runs a shared sub-use case, where the text is the walk's NAME. Names are imperative,
for use cases and shared sub-use cases alike. A third-person phrase in that slot reads as a sentence whose
beginning is missing.

Before this rule the two forms split cleanly on the two live maps: 1376 of 1379 step phrases were
third person, and 24 of 24 shared sub-use case names and 82 of 82 use case names were imperative. Both maps
were migrated, and `method.md`, `method/model.md` and the trace contract now say imperative.

## Open, and NOT fixed

Two other fields keep the third person on purpose, because neither is ever shown as a title on its own:
a Happy Path step's `title` (it carries its own subject, "Admin invites a team member") and a backbone
edge's `why` (shown beside its two ends). If a later screen starts titling either of them alone, they
join this rule.

A step's `note` is also untouched: it is a condition or a qualifier, never an action.

## Checks

1. expect: on a rebuild, every `phrase` on a flow step and on a shared sub-use case's step starts with a bare
   verb — `return the verified email`, not `returns the verified email`.
   regression sign: take the first word of every phrase and flag any ending in `s` that is not a
   plural noun, plus `is`, `has`, `does`, `goes`. A non-empty list means the trace contract's wording
   is not reaching the worker that authors T6, and the fix is in the contract, not in the map.

2. expect: a second verb after `and`, `or`, `then` or a comma is imperative too — `open the screen and
   carry the press to it`, never `and carries`.
   regression sign: any phrase where the first word is imperative and a later coordinated verb is not.
   That is the half-applied rule, and it reads worse than the old form because one sentence carries
   both.

3. expect: the rule stays OFF a Happy Path step title, an edge `why` and a step `note`.
   regression sign: a build returns `Admin invite a team member`, or an edge `why` reading `verify
   service tokens` where it used to read `verifies`. The rule has been over-applied, and a happy-path
   title with its own subject now reads ungrammatically.
