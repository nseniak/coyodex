# The gate block carries the finalize report's advisory disposition

Change (2026-09-08): `finalize`'s gate block (`.coyomap/verify/gate-block.md`, the text a build
quotes in its commit message) gains one line, `Advisory disposition: UNANSWERED: n · UNRECORDED: n
· UNSURE: n · carried (no escape): n · disclosure: n · recorded: n`, with the zero counts left
out. The report had this three-way answer all along, in a file the build never quotes; the gate
block's own wording was two-way ("recordable / no escape"), and the 2026-09-08 mcpolis commit filed
its 2 UNANSWERED rows as "carried with no escape heading to record them under".

Escalation: none on its own.

## Checks

1. expect: the next build's commit message, or its gate block, carries the disposition line, and
   its counts add up to the advisory total on the block's first line.
   regression sign: a commit message that describes advisories with a vocabulary the line does not
   use ("recordable / no escape" only), or counts that disagree with the report's own table.

2. expect: an UNANSWERED row (a `grounding.note` that does not state the count its advisory is
   about) is either answered in the note before the commit or named as UNANSWERED in the message.
   regression sign: UNANSWERED rows described as "carried" or "no escape".

verified in reminderrepo build of 2026-09-13 23:03
