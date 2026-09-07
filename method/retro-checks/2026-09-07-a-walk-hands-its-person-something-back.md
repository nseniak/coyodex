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

Eight other flow reports landed in the four minutes after that one.

**Measured, and CORRECTED after an adversarial review.** Person-facing walks whose person is left
acting with nothing handed back: **0 of 50 on the 2026-09-02 map and 4 of 43 on the 2026-09-07 map**,
one of them UC3. Also 3 of argus's 18 person-facing walks and 3 of coyodex's own 18. **Every
denominator here is person-facing walks, not flows** — an earlier draft of this line said "3 of 40"
for a map that has 38 flows, having borrowed the 40 from the sibling check's own denominator.

The first shipped version was wrong in both directions and a reviewer reproduced each on a live map:

- it took the last step touching ANY actor and then asked whether that one was a person, so **one
  machine step after a person's dead end hid it** — silent on argus UC3 and coyodex UC38, the exact
  defect it exists for;
- it read a walk's OWN steps, so a reply handed back inside a shared sub-flow read as no
  reply. **This one has no live instance**: expanded and own steps give identical rows on all four
  maps today. It is a defect in reasoning, fixed before it could bite, and not something a reviewer
  reproduced on a map;
- it demanded a reply when the person walked out to somebody ELSE'S console, which the product
  stands at neither end of. That was 1 of the 5 it first reported.

It now tracks the last contact PER PERSON over the expanded steps, and exempts a third party's
surface only when the walk ENDS there. Across four live maps that exemption suppresses exactly one
row. The advisory counts PEOPLE only: a service role opening its own scheduled work fires 2 more
times on the 2026-09-07 map (UC40-43) and 2 on the earlier one (UC46-47), and is owed no reply.
Both of those numbers were stated wrong twice before being measured.

## Checks

1. expect: on the next mcpolis build, UC3 "Ask the team a question" either ends at a surface that
   hands the visitor to their mail program, or carries a `UC3: <why>` line under a "Missing
   surfaces" heading.
   regression sign: the advisory fires on UC3 again with neither. A build is reading its warnings
   and skipping this one.

2. expect: the count stays small — at most 4 or 5 person-facing walks per map. (An earlier draft
   said "2 or 3" while the same file measured 4, so the check contradicted its own evidence.)
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
