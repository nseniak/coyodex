# The test-completeness brief comes from a template, and the verdict lint runs after every wave

Change (2026-09-09): `coyodex contract tests` ships the test-completeness contract (slots
`COYODEX_HOME`, `REPO`, `MAP`, `PROJECT`, `TESTS_ARE`, `AGENT_ID`; the writing rules appended,
because a gap row is read in the viewer), and method.md tells the lead to get the brief with the
verb. The brief was hand-written on every build; on 2026-08-20 it lost the no-delegation block and
on 2026-09-08 it was written last, dispatched last, and was the straggler (retro row 21).
method.md also says `grounding lint` runs after EVERY wave over every verdicts file so far, and
that `--agent-transcripts` defaults to this session's directory: the 2026-09-08 build linted 6 of
38 files, once, on wave 1 (retro row 16).

Escalation: none on its own.

## Checks

1. expect: the test-completeness agent's brief is a `contract tests --fill` output, dispatched
   the moment the traced map is assembled, before the T7 rules and the Phase 4 skeptics.
   regression sign: a hand-written tests brief, or one dispatched after the skeptic fan-out.

2. expect: one `grounding lint` per skeptic wave, each naming every verdicts file so far.
   regression sign: a single lint over wave 1, or a lint naming fewer files than were dispatched.

3. expect: the lint's `agent transcripts:` line names this session's directory on every run.
   regression sign: the citation check reported as skipped.
