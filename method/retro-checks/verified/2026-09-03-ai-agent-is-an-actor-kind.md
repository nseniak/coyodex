# `ai-agent` is the third actor kind, and every "is this a program" test reads one predicate

Change (2026-09-03): `Role.kind` gains `ai-agent` beside `human` and `service`
(`grammar.ROLE_KINDS`), with `grammar.is_machine_role` / `isMachineActor` as the ONE predicate every
reader uses. It draws as a bot — antenna, square head, a person's body, no face — on all four
surfaces that draw an actor · grammar.py, model.py, validate_model.py, json_schema.py,
viewer/build_graph.py, viewer/gen_viewer.py, the viewer, method.md, method/model.md, the schema.
Three live roles move: coyomap "Coding agent", argus "Assistant", mcpolis "Headless agent".

Escalation: if check 1 fails — a map's authored `ai-agent` reaching a screen as `human` — a
coercion has come back and the map is being contradicted by its own viewer. Stop and find it before
accepting the map; it is invisible to every gate.

## What this change is answering

**`service` was covering two things that behave differently.** Across the three live maps 4 roles
were `service` and 3 of them were AI agents — a customer's coding agent, an assistant, an unattended
agent holding a token — wearing the same pill and the same hexagon as mcpolis's "Upkeep job", which
is a cron inside the product.

**The distinction that earns the third word: an `ai-agent` is ALWAYS OUTSIDE the product.** Only
`service` with an `internal` audience means the product's own scheduled work, which owes no doors and
stands on no surface. A customer's agent is never that, so it keeps its doors. That is why it is a
third kind rather than a flavour of `service`, and it is why `outside_actor_ids` still tests the
literal word `service` while every other test reads the predicate.

## What this cost, because the estimate was wrong and the next person should know

Estimated "one field plus one shared definition". It was THIRTEEN registration points, and the two
that mattered most were invisible to every gate:

  * `build_graph._role_kind` coerced every explicit kind into two — `startswith("s")` meant service,
    everything else meant human — so the map said `ai-agent` and the browser was told `human`. The
    suite passed, pyright passed, and only opening the page found it.
  * `SEQ_ACTOR_TINT` had no entry for the new kind, and a missing entry there is not a missing
    colour: `styleSeqActor` returns early, so the actor would have rendered as a bare Mermaid stick
    figure whatever the map said.

Nine string comparisons against `"service"` were routed through one predicate as part of the fix,
which reads `!= human` rather than `== service` so a FOURTH kind is a machine by default rather than
silently a person.

**The glyph was measured, not eyeballed.** The card's figure is head 8x5.2, mast 1.3, tip r 0.85 —
width-to-height 1.54, mast 0.25 of the head's height, tip 0.106 of its width. The first Mermaid pass
drew a mast twice that, an aerial rather than a bot. The constants are those three ratios
re-expressed, and the rendered diagram measures 1.53 / 0.24 / 0.106.

**Eyes were drawn and removed.** The person beside it has no face either, so two dots made the pair
inconsistent — one figure detailed, the other bare. The square head and the antenna are the whole
distinction, and neither asks a reader to see something under a pixel across.

## Checks

1. expect: a role authored `ai-agent` reaches every screen as an AI agent. Open the actor's page: the
   pill reads `ACTOR` then `<side> AI AGENT`, and the figure has an antenna and a square head.
   regression sign: the pill says only `ACTOR`, or the figure is a stick person, while the map file
   says `ai-agent`. A coercion is rewriting the kind on the way out — the exact defect above, which
   no gate can see.

2. expect: a rebuild AUTHORS `ai-agent` on the AI actors without being told which they are. On
   mcpolis that is "Headless agent"; on argus "Assistant"; on coyomap "Coding agent".
   regression sign: they come back `service`. The instruction in method.md did not reach the worker
   that authors the roles table, and the three corrected rows in this change were masking that.

3. expect: `service` still means what it meant. The product's own scheduled work — mcpolis's "Upkeep
   job" — stays `service` with an `internal` audience, and still owes no doors.
   regression sign: "Upkeep job" comes back `ai-agent`, or an `ai-agent` is authored `internal` and
   stops owing doors. The kind was read as "any autonomous thing" rather than "a program driven by a
   language model, acting for somebody".

4. expect: the bot figure appears on ALL FOUR drawing surfaces — the card/hero glyph, the Interfaces
   chip, the sequence diagram lifeline, and the flow map / Dependencies node.
   regression sign: a hexagon on any of them. Each surface draws actors by a different mechanism, so
   a new kind that reaches three of four is the normal failure here, not the exception.

5. expect: no NEW actor kind is minted (`bot`, `agent`, `llm`, `assistant`). Three is the vocabulary;
   `validate` never blocks a minted one, so only a reader catches it.
   regression sign: a fourth spelling. It will still draw as a program (the predicate is `!= human`)
   but with no glyph and no reader's word, so it prints the raw code word on a card.

---

**verified in mcpolis build of 2026-09-07 00:32** (map commit `e430399`, tool stamp
`21de5e3`). All 5 items confirmed by a fresh reader with no part in the change:
1 role authored `ai-agent` (`R3 Headless agent`) with nobody editing the row · the rebuild
re-derived it rather than falling back to `service` · the background job stayed `service` +
`internal` with 0 doors against that role's 4 · the bot is drawn in 6 places with 0 hexagons on
it · 3 actor kinds over 6 roles and no fourth spelling anywhere.

One thing the reader found that does NOT reopen the file: the SEQUENCE DIAGRAM this check names
as the third drawing surface no longer exists. `styleSeqActor` and `botHeadActor` are defined
and called by nothing (`tools/coyomap/viewer/viewer.js`); the Happy Path gutter replaced it and
draws the bot. Dead viewer code, filed separately, not a failure of this change.
