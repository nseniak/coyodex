# An attended AI agent is a pipe, a tool is not a goal, and a message to a person has its own kind

Change (2026-09-03): three method changes that all fall out of one finding, plus the viewer label
that makes the result legible · method.md, method/model.md, tools/coyodex/grammar.py, json_schema.py,
method/project-map.schema.json, viewer/gen_viewer.py, the viewer.

  1. **An attended AI agent is a PIPE, not an actor. The actor is the person.**
  2. **A tool is not a goal**: never mint one use case per tool address.
  3. **`message`** joins the interface kinds — a message we send outward to a person.
  4. The viewer prints `(via AI agent)` on a person who reached an agent-facing surface.

Escalation: if check 1 fails on a rebuild of argus — the assistant still authored as the actor — the
instruction did not reach the worker that writes the roles and use cases, and check 2 cannot be read
at all (the tool-shaped use cases follow from the actor being wrong). Report it and stop; do not
hand-fix the actors, because a build throws hand edits away and the next build repeats it.

## What this change is answering

**THE TWO LIVE MAPS MODEL THE SAME SITUATION IN OPPOSITE WAYS, and neither shows both parties.**

  * argus authored 15 use cases at its MCP interface with `Assistant` as the actor. The page owner —
    the person who wants the page tracked — appears in NONE of them. The same person's DASHBOARD use
    cases name the page owner, so one map gives two answers for one person doing one thing:
    `UC21 Stop tracking a page from the dashboard` (Page owner) beside `UC8 Stop tracking a page`
    (Assistant).
  * mcpolis went the other way. Its Gateway sentence reads "The one MCP address **a member's AI
    client** or an unattended agent connects to" — the AI client is named in PROSE and is not an
    actor, and the use cases name the Team member directly. That sentence is the proof the author
    knew it was there and had nowhere to put it.

**mcpolis is right, and the rules already said so.** Two existing rules point the same way: *name the
far side, never the pipe*, and the advisory that a service beside a human on a use case is usually
the delivery mechanism. argus is the map that departed. What was missing was a sentence saying it
about AI, and the `ai-agent` kind shipped earlier the same day made it worse by listing "the
assistant a member talks to" as an example — telling the next build to do what argus did.

**THE SECOND DEFECT IS BIGGER THAN THE FIRST.** Naming the tool caller as the actor changes what
counts as a use case: when the caller is the actor, every tool looks like an intent. argus put 15 use
cases on 21 MCP tool addresses, roughly one each, and they read like the tool list they are — "Store
page text an assistant supplies", "Plan the next summary", "Check what the account is allowed,
through the assistant". Nobody WANTS to plan the next summary. Written for the page owner the goals
are four or five. So re-actoring the 15 does not fix them; several stop being use cases at all.

**`message` was the only row in the 2026-09-03 partial run where the vocabulary misled a careful
reader.** Two independent agents, on two runs, authored mcpolis's "Outgoing email" as `api`, both
saying `api` names the SMTP pipe and not the surface. The alias table was folding `email`,
`message` and `message-out` INTO `api`, so a map that spelled it plainly was told its surface is one
program calling another. Those spellings now fold to the new seed. Evidence is thin — one row on one
map — and it is recorded as thin: what earns it is that nothing else in the vocabulary fit.

**The label was drawn three ways before it was right.** A bot glyph beside the person was built and
rejected on sight: at that size a figure with an object beside it reads as a second character, and a
pipe is not a party. Then a second label line, which the lifeline picture had nowhere to put — it hit
the figure's legs, and pushed down it hit the first message. It ended as one line in the lifeline
picture (the column widens to fit) and its own line in the map picture (where a long label wraps
mid-phrase), with a non-breaking space so "AI agent" never splits.

## Checks

1. expect: a rebuild of argus authors the PAGE OWNER as the actor of the use cases at its MCP
   interface, not the assistant, and `Assistant` stops being a role at all unless something in the
   product genuinely acts with nobody watching.
   regression sign: `Assistant` is still the actor. The pipe rule did not reach the worker that writes
   roles, and everything below depends on it.

2. expect: that rebuild has ROUGHLY FOUR TO SIX use cases at the MCP interface, not fifteen, and none
   of them names a tool ("store page text", "plan the next summary"). The tools appear as steps.
   regression sign: one use case per tool address again, or a trigger with no subject ("Names a page
   and its address" rather than "a page owner asks their assistant to watch a page").

3. expect: mcpolis keeps `Headless agent` as an `ai-agent` ACTOR. It is unattended — nobody is
   watching, it holds a service token — so it is a party, not a pipe.
   regression sign: it becomes a pipe too, and the map loses the one actor the kind exists for. The
   rule is about ATTENDED agents; an unattended one initiates and keeps its actor row.

4. expect: `message` is authored on a surface that sends outward to a person, and NOT used for a
   message to a system. mcpolis's "Outgoing email" is the live case; "Visitor's mail program" stays
   `handoff`, because there we hand the person to their own app rather than send them anything.
   regression sign: `api` on an outward message again (the old fold coming back through a habit), or
   `message` on a machine-to-machine call.

5. expect: on a use case whose person reached an agent-facing surface, BOTH pictures print
   `(via AI agent)` after their name, the phrase never splits across lines, and the figure clears the
   text. On mcpolis that is 11 (use case, person) pairs.
   regression sign: the text touching the figure, or "AI" and "agent" on different lines. Both
   pictures centre a label block, so anything that changes the number of lines moves everything.
