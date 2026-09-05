# Every saved record owes a use case, the same way every interface does

Change (2026-09-05): `validate` gains an advisory — a record this codebase KEEPS (`store.mode` of
`collection` or `embedded`) that no use case walk reaches draws one line, naming the fix (author the
central touch as a `Cn → En` step) and the escape (`<En>: <why>` under a "Balance exceptions" extras
heading). A record INSIDE another one counts as reached when its container is. New derivation
`record_use_cases`. The method and the trace contract say so at the point steps are authored ·
tools/coyodex/validate_model.py, method.md, method/model.md, method/templates/trace-contract.md.
Seven records were storied into the mcpolis map in the same change.

Escalation: if check 1 fails on a rebuild, the instruction is not reaching the worker that authors
T6 — say so rather than hand-adding the steps, which the next build throws away.

## What this change is answering

**The map could keep a record and never say what it is for.** A saved record with no story draws a
box on the Data tab whose owner nothing backs, which is the "owner with no evidence" defect the
glossary already names, arrived at from the other direction.

**It is the same hole the interface rule closed, on the other half of the map's outside.** An
interface says where the product meets the world; a saved record says what it keeps. Neither means
anything until a story says what it is FOR, and until now only one of the two was checked.

**It is also where the removed `interfaces[].carries[]` used to say something.** Its record list
named four of mcpolis's embedded records — `RoleSettings`, `UserDefinition`, `StdioTransportConfig`,
`HttpTransportConfig` — and after the removal nothing did. Those four are now reached through their
containers, which is a better answer than a list beside the walks: it comes with a story.

**SAVED, not every entity, and the filter is one the model already had.** `model.is_saved` is
`collection` or `embedded`. A projection is a read shape over rows something else owns, a transient
is built for the length of one call, an enum is a set of constants. Across the two live maps: 142
entities, 46 saved. Demanding a story for the other 96 would bury every real gap, which is the
mistake the `facing: operator` exemption made in the opposite direction two days earlier.

**THE CONTAINER ARM IS WHAT MAKES THE RULE AFFORDABLE.** An embedded record lives inside its
parent's row, so a story that writes the parent writes the piece. Measured: it takes argus from 9 of
11 saved records reached to **11 of 11**, and mcpolis from 17 of 35 to 28 of 35. What it does not do
is hide a gap — the 7 it leaves in mcpolis are records with no parent and no story, and those are
the finding. The chain is walked with a `seen` set, because `contains` is authored and nothing stops
a cycle.

## Open, and NOT fixed

1. **The rule says a record owes a STORY, not that the story is the right one.** A step drawn at a
   record satisfies it whatever the step says. The audit worklist is what challenges the phrase, and
   the direction now rides in that claim, but nothing checks that the story reaching a record is the
   story that record exists for.
2. **A cache owes nothing.** `cache` is in neither `STORE_MODES_SAVED` nor `STORE_MODES_UNOWNED`:
   something writes it, and it is not a record the product keeps. That is deliberate and untested by
   this change, because neither live map has a `cache` entity.

## Checks

1. expect: on a rebuild, every saved record is reached by a use case walk, directly or through a
   container, and `validate` reports none unstoried.
   regression sign: the advisory names more than a handful. The instruction is not reaching the
   worker that authors T6, and the field-level fix is to make the trace contract louder, not to add
   the steps by hand.

2. expect: the seven mcpolis records storied in this change come back storied — the gateway's own
   sign-in state for AI clients, its stored refresh token and refusal shape, the sandbox pointer,
   and what a mounted server reports about itself.
   regression sign: any of them comes back with no step. The story that does that work exists in
   the map already, so a rebuild dropping the record is the walk being written at too coarse a
   grain, not a missing use case.

3. expect: the advisory stays silent on records the codebase does NOT save.
   regression sign: it names a projection, a transient or an enum. `is_saved` has been widened, or
   the check stopped using it, and the real gaps are now buried under 96 shapes that owe nothing.

4. expect: recorded escapes stay rare and each names one record with a real reason (a migration-only
   write, say).
   regression sign: a run of `<En>: <why>` lines under "Balance exceptions", or one line covering
   several records. The rule is being answered with paperwork instead of stories, which is what a
   waved-through advisory looks like.

5. expect: no entity's `store.mode` moves OUT of `collection`/`embedded` between builds without the
   code changing.
   regression sign: a saved record re-labelled `projection` or `transient`. That silences the
   advisory by making the map less true, and it is the same cheap escape the `facing` swap was for
   the interface rule.
