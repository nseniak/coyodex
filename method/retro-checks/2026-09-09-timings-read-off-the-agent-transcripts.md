# Fan-out timings are read off the agents' transcripts

Change (2026-09-09): `coyodex timings record --phase <p> --from-agents [<dir>] --slice <name>…`
records each named slice at its agent's transcript span (first record to last), with no value
meaning this session's own transcripts directory. Names are the pointer prompt's first word, or the
harness's description. On the 2026-09-08 mcpolis build 11 of 12 hand-read timings were exact and
the twelfth understated the batch straggler by 14 minutes (retro row 23).

Escalation: none on its own.

## Checks

1. expect: every `timings record` in the build transcript carries `--from-agents`, and no
   `--minutes`.
   regression sign: a hand-typed `--minutes`, or a `--lines-from` file written from memory.

2. expect: each recorded slice's minutes equal its agent's first-to-last record span to 0.1.
   regression sign: any row off by more than a minute.
