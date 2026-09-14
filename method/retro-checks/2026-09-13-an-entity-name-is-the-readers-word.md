# An entity's NAME is the reader's word, not the class's spelling

Change: the T5 naming rule, from the 2026-09-13 reminderrepo retrospective · `method.md` (T5 domain
model), `method/templates/t5-addendum.md`. Both said what to MODEL — a real named type whose
`source` anchors its definition — and were silent on what to CALL it, so the domain agent named
each entity after its class. On that build **52 of 59 entity names were raw class names**
(`WeeklyMultipleRequestTypeWithIntervalEndWithOccurence`, `NotificationSecurityData`,
`DateGeneratorDaily`) while **0 of 126 component names** were, and every one of those entities
carried a good plain-language `meaning` beside it — so the agent knew what the thing was and named
it after the class anyway. Both files now say the name is the reader's word and that the class name
lives in `source`.

Escalation: if check 1 comes back above 20%, the prose fix did not take and the Data section is
still unreadable to a non-coder. Propose the tool half — a `validate` advisory counting code-shaped
entity NAMES, the way the readability check already counts code inside a sentence — before
accepting the map.

## Checks

1. expect: fewer than 10% of the map's entity names are code-shaped — CamelCase with no space,
   snake_case, or a bolted-on type word (`Data`, `Dto`, `Entity`, `Type`, `Config`). State the
   fraction with its noun ("7 of 59 entity names"). The number to beat is 52 of 59 (88%) on the
   reminderrepo map of 2026-09-13.
   regression sign: still above 50%; OR the count falls while `source` anchors go missing — the
   agent renamed by DELETING the class reference instead of moving it to the anchor. Every entity
   must still carry a `source` that `validate --check-sources` accepts.

2. expect: the renamed entities' `meaning` sentences still say what they said before — the name was
   the defect, the sentence beside it was already good.
   regression sign: a `meaning` that now restates its own name ("A weekly reminder request is a
   weekly reminder request"). That is what happens when the plain-language sentence gets copied up
   into the name and nothing is left to explain it.

3. expect: the readability advisory count over the entity fields does not RISE. A reader's word is
   a plain short label, so moving off the class name should hold that count flat or lower it.
   regression sign: it rises, because the new names are prose phrases rather than labels — a
   leading article, or a name long enough to read as a sentence.

4. expect: the T5 fragment still delivers its LAST fields at their previous size: `non_entity_types`
   populated, and a `relations` item wherever two entities relate.
   regression sign: either comes back empty or thin. The naming rule was inserted mid-paragraph in
   the addendum, and a slice that stops delivering what follows the insertion is the sign the agent
   stopped reading there.
