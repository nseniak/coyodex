# A skeptic brief's batch slots hold ids, never paths

Change (2026-09-08): `coyomap contract --fill` refuses a `«BATCH»` or `«CLAIMS»` value that
contains a `/` or ends in `.json`. The skeptic contract composes `.coyomap/verify/claims-«CLAIMS».json`
and `verdicts-«BATCH».json` itself, so a path in either slot builds a file name that exists nowhere:
38 of 38 briefs on the 2026-09-08 mcpolis build named
`claims-/Users/…/.coyomap/verify/claims-backbone-1.json.json`.

Escalation: none on its own.

## Checks

1. expect: 0 skeptic briefs whose "Claims file" line names a path containing `claims-/` or ending
   in `.json.json` (grep over the build's `contracts/` or scratch briefs).
   regression sign: 1 or more.

2. expect: the refusal, when it fires, costs the lead one turn — the message names the slot and
   the shape wanted (`backbone-1`).
   regression sign: two or more fill attempts on the same brief.

verified in reminderrepo build of 2026-09-13 23:03
