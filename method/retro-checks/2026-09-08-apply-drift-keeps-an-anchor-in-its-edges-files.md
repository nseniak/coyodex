# `apply-drift` refuses a correction into a file neither end of the edge lists

Change (2026-09-08): `tools/coyodex/audit_model.py` gains `cross_file_refusals`, run by
`fix apply-drift` before both of its write paths (in place and `--to-reconcile`). A corrected
anchor whose file is listed in neither endpoint's `files` is not written and is named on stderr.
On the 2026-09-08 mcpolis build `apply-drift` rewrote 22 anchors with no file opened; one put
`C99 tests C41` in a file that a third component lists, and `validate --check-sources` passed
because the path resolves.

Escalation: none on its own.

## Checks

1. expect: 0 edges whose `where` file is listed by neither endpoint's `files` on the next map
   (both endpoints listing files), measured by one loop over `edges` and `components`.
   regression sign: 1 or more, as on the 2026-09-08 map.

2. expect: every refused correction is named in the build transcript with `REFUSED`, and the lead
   either extends the component's `files` after reading the file or re-anchors by hand — never
   by re-running `apply-drift` with `--force`-like edits to the verdicts.
   regression sign: a refused correction that reappears as a hand-typed `set_anchors` row.

3. expect: no legitimate cross-file move is lost: a correction into a file the far end lists is
   still applied, and the `NOTE: … moved to a DIFFERENT FILE` line still prints for it.
   regression sign: the refusal count equals the cross-file move count on a build where the
   moves were correct.
