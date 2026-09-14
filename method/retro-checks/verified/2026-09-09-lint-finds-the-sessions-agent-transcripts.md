# `grounding lint` finds this session's per-agent transcripts without the flag

Change (2026-09-09): `coyomap grounding lint` defaults `--agent-transcripts` to
`~/.claude/projects/<repo slug>/<$CLAUDE_CODE_SESSION_ID>/subagents/` when that directory exists,
and says on stderr which directory it read. The flag was advertised by the tool's own output and
passed 0 times across four builds; on the 2026-09-08 mcpolis build the retro ran the check after
the fact and found 56 of 1,180 verdict rows resting on grep-only evidence. The method now says to
lint after EVERY wave, not only the first.

Escalation: none on its own.

## Checks

1. expect: every `grounding lint` run in the next build's transcript prints
   `agent transcripts: … (this session's, found without --agent-transcripts)` and an
   `evidence check covered N of M row(s)` line.
   regression sign: a lint run that prints the "pass --agent-transcripts" hint inside a build.

2. expect: a lint run after each skeptic wave — the count of `grounding lint` runs equals the
   number of waves (2 on the last mcpolis build), each naming that wave's verdict files.
   regression sign: one lint run on wave 1 and none after, as on 2026-09-08.

3. expect: the share of verdict rows resting on grep-only evidence does not rise:
   56 of 1,180 (4.7 %) on 2026-09-08 is the baseline.
   regression sign: above 6 %, with the check now running during the build and read by nobody.

verified in reminderrepo build of 2026-09-13 23:03
