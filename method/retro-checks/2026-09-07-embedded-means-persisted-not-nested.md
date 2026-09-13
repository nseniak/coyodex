# `embedded` means persisted inside a saved parent, not nested inside anything

Change (2026-09-07): `method/model.md` gives `embedded` the definition `projection` already had;
`tools/coyomap/json_schema.py` says PERSISTED in the store-mode description an agent actually reads,
and `method/project-map.schema.json` is regenerated from it; `tools/coyomap/validate_model.py` gains
an advisory for a record marked `embedded` that nothing saved holds, escaped by a SCOPED token.

Escalation: none on its own.

## What this change is answering

**The word was defined in exactly one file no map-building agent opens** — `tools/coyomap/
grammar.py`, "persisted INSIDE a parent entity's row/document". What the agent read said
"embedded (inside a parent's row)", with PERSISTED missing, so it read the word as **nested**.

Proof from the build's own fragment: of 14 shapes taken from one response-models file, every row it
called `embedded` is a row nested inside another row, and **none is nested inside anything the
product saves**. Their compartments are named "mounted-server detail page" and "my tools page" —
screens, not places. The map's other 22 `embedded` records name real compartments.

Three read shapes the previous map labelled correctly came back marked as kept, with the product's
code unchanged: only one middleware and two unit tests differ between the two build commits.

**It is a wobble, not a one-off.** One record has worn `collection`, `in-code`, `embedded` and
`transient` at an unchanged anchor across 25 builds.

**Nothing caught it.** The shape check inspects only two of the seven modes. The reader worklist
sends a claim only for rows with a database link — 14 of 82 records — so the storage claim on these
was never challenged by anyone. And the saved-record rule DID report all four, whereupon one
recorded line answered all four at once with a reason the map's own data contradicts: it says three
of them live inside a record a story reaches, and none of the three holders is saved.

**Measured before shipping**, records marked `embedded` that nothing saved holds:

| map | fires | of `embedded` rows |
|---|---|---|
| argus | 0 | 2 |
| mcpolis 2026-09-02 | 2 | 23 |
| mcpolis 2026-09-07 | **4** | 25 |

The four are exactly the four the saved-record rule reported.

**The escape is a scoped token, and that is load-bearing.** The first version read the bare id under
"Balance exceptions", and the existing blanket line pre-silenced all four before the check ever ran.
A waiver written for one question must not answer a different one.

## Open, found while doing this and NOT fixed

1. **`method/domain-cards.md` lists the seven modes and defines none**, and it is the entity agent's
   own spec page.
2. **`method/templates/t5-addendum.md` ships `«COYOMAP_HOME»` unsubstituted**, in both builds, so
   the only pointer to that spec page is a dead path.
3. **68 of 82 records go unchallenged on where they live.** The reader worklist could carry one
   claim per `embedded` row.

## Checks

1. expect: on a rebuild, the three response models come back NOT `embedded` — two as `projection`
   and one as `transient` — and the advisory reports at most 1 (a record whose holder relation is
   genuinely missing).
   regression sign: still 4, or a different set of four. The definition is not reaching the agent.

2. expect: no `embedded` row names a SCREEN as its container. Grep the containers for "page",
   "screen", "view".
   regression sign: any. The compartment is where a record lives, not where it is displayed.

3. expect: the 22 genuinely embedded records STAY embedded — role settings, transport configs,
   catalog entries, a subscription.
   regression sign: the `embedded` count collapses. Pushing real kept records out is the opposite
   failure and the more expensive one.

4. expect: if a build uses the escape, it writes `En/embedded: <why>` and not a bare `En`.
   regression sign: a bare id, which would silence the saved-record rule as a side effect.
