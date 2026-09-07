# A walk that leaves its person with nothing handed back is reported

Change (2026-09-07): the interface sweep in `method.md` gains its REVERSE arm — answer every walk
report that says no surface fitted — with a **"Missing surfaces"** extras heading as its escape.
`tools/coyodex/validate_model.py` gains the advisory that makes it checkable, and
`tools/coyodex/records.py` registers the heading.

Escalation: none on its own.

## What this change is answering

**"Every interface owes a use case" can only read DOWN the table.** It finds a surface no story
crosses. It cannot find the opposite — a story that needed a surface nobody wrote — because that row
is not in the table to be read. Only the tracing agent ever sees it, in the moment.

**And on 2026-09-06 one did, and said so, and was not answered.** Its report:

> "UC3 has no final hand-off surface. Its last product action is sending the click to analytics; the
> person then leaves for their own mail client. No authored surface fits that, so I added no door
> there and the story stops at the click."

The lead called it "a second wording correction", rewrote the use case's outcome sentence, and wrote
no row. The map's only `handoff` surface is gone; the code is unchanged
(`frontend/src/components/marketing/EmailLink.tsx` still renders a `mailto:`); and the use case's own
outcome still reads "their own mail program opens" while no box in the map is one.

**The previous build got the same report and answered it.** On 2026-09-02 the lead minted the row 13
minutes later and sent the agent back to close the story through it. The two builds differ only in
the answer, which is why the method text now names the case.

Eight other walk reports landed in the four minutes after that one.

**Measured before shipping**, person-facing walks that end with the person acting and nothing handed
back: **0 of 50 on the 2026-09-02 map, 5 of 43 on the 2026-09-07 map.** One of the five is UC3. The
advisory counts PEOPLE only: a service role opening its own scheduled work fires 3 more times on the
same map and is owed no reply, and burying the five under those three is how an advisory teaches
people to skip it.

## Checks

1. expect: on the next mcpolis build, UC3 "Ask the team a question" either ends at a surface that
   hands the visitor to their mail program, or carries a `UC3: <why>` line under a "Missing
   surfaces" heading.
   regression sign: the advisory fires on UC3 again with neither. A build is reading its warnings
   and skipping this one.

2. expect: the count stays small — at most 2 or 3 person-facing walks per map.
   regression sign: it fires on 8 or more. Either most walks legitimately end on the person acting,
   which would make the whole check the wrong shape, or the person/service cut is drawn wrong.

3. expect: `handoff` is a used kind again on mcpolis — 1 row, not 0.
   regression sign: still 0 while the `mailto:` is still in the code. The surface is being lost the
   same way twice.

4. expect: the escape, when a build uses it, names ONE use case per line with a real reason.
   regression sign: a single line listing four or five use cases at once. That is the shape the
   saved-record check already caught being used to answer four findings with one sentence.

5. expect: no build silences this by DELETING the person from the walk, or by re-typing a human
   role as software.
   regression sign: the map's person-role count falls while this advisory's count falls with it.
   The cheapest fix taken, and the map got less true.
