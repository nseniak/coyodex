# A message the operator types reaches the transcript reader

Change (2026-09-07): `read_turns` in `eval/tools/coyomap_eval/transcript.py` accepts a plain-string
`content` as one text block instead of dropping the record; `<task-notification` joins
`_HARNESS_TEXT` so background chatter stays hidden; and `operator_text` no longer prepends a slash
the `<command-name>` tag already carries. Tools only. No method text changed and no map was edited.

Escalation: none. If this fails, the process scorecard's operator assertions are reading a
transcript with the people removed, and every "nobody noticed" finding it reports is unfounded.

## What this change is answering

**The reader kept `content` only when it was a LIST of blocks.** Every record the harness writes as
a bare string was dropped whole, and those are exactly the records that are a person talking. On the
2026-09-06 mcpolis build that was **77 of 336 user records**: the `/coyomap build` that started the
build, 75 task-notifications, and the one word the operator typed to unblock a safety guard.

The scorecard's own assertion asked whether anyone noticed the guard, read **0 operator lines on a
session that had 2**, and nothing said the reader had not looked. The retro that found it had to
read the raw JSONL to see the turn at all.

Two smaller faults came with it. Accepting string content alone would have rendered 75 background
notifications as an operator speaking, which the reader's own docstring calls a worse answer than no
answer. And the command that started the build rendered as `//coyomap build`, because this harness
version writes the slash inside the tag and the unwrapping added another.

## Checks

1. expect: on the next build's transcript, `operator_text` over the user turns returns at least the
   slash command that started the build. Measured on 2026-09-06: **2 records, `/coyomap build` and
   `A`, against 0 before.**
   regression sign: 0 operator records on a session where a person demonstrably typed something.
   Check the raw JSONL for `"content": "` on a user record before believing the reader.

2. expect: no task-notification is rendered as an operator message. On the same build **75 of them
   stay hidden**.
   regression sign: the operator record count runs into the dozens and the text reads like a
   machine announcing a background task. That is the failure mode the fix's own guard prevents, and
   it looks like success in a count.

3. expect: no rendered operator command starts with `//`.
   regression sign: a doubled slash, meaning the harness changed the tag again and the strip is
   now wrong in the other direction.

4. expect: the process scorecard's operator-facing assertions change verdict on a build where the
   operator spoke, rather than staying at their previous value.
   regression sign: assertion 9 (or its successor) still scores 0 with the reader fixed, which
   would mean the scorecard reads the transcript by some other path that was never fixed.
