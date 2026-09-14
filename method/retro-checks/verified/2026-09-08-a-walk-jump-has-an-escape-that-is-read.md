# A walk jump's escape heading is one the tools read

Change (2026-09-08): `tools/coyomap/records.py` registers **"Walk jumps"** (keyed on the use case),
and `walk_jumps` in `tools/coyomap/validate_model.py` skips a use case recorded there. The advisory
had named that heading since the day it was written and nothing read it: on the 2026-09-08 mcpolis
build, `coyomap record --heading "Walk jumps"` answered "not a heading any check reads", and the
advisory (UC33 step 15) shipped in the finalize report as "carried (no escape)". A test now reads
every escape heading named under `tools/coyomap/` off the source and refuses one the registry lacks.

Escalation: none on its own.

## Checks

1. expect: 0 `record` refusals naming 'Walk jumps' in the build transcript
   (`coyomap-eval transcript <t> --from 1 --to <last> --full | grep -c "'Walk jumps' is not a heading"`).
   regression sign: 1 or more. The registry and the advisory drifted apart again.

2. expect: every walk-jump advisory the gate printed is either gone (the missing step was written)
   or recorded: 0 finalize rows read "carried (no escape)" for a walk jump.
   regression sign: a walk-jump row still "carried (no escape)" while the heading exists. The build
   read the message and skipped it.

3. expect: the escape stays the exception. Recorded 'Walk jumps' use cases are fewer than the
   walk-jump advisories the first validate printed, and each recorded reason says which thread
   that story opens (one reason may name several use cases, which is the registry's own form).
   regression sign: every jump recorded and no step written, which is the cheap way out; or a
   reason that could sit under any use case ("a second thread") and names no thread.

verified in reminderrepo build of 2026-09-13 23:03
