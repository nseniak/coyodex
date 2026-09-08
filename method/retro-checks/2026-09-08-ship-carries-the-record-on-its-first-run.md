# `ship` carries the grounding record into the map on its first FINISH run

Change (2026-09-08): `tools/coyodex/ship.py` names `build-fragments/grounding.json` in the two
assembles that follow `grounding write` (steps 7 and 9), whether or not the file existed when
`ship` started. Before, the fragment list was one glob taken before any step ran, so the first
FINISH run assembled everything but the record it had just written. The 2026-09-08 mcpolis build
found its map without the record after a clean `ship` and ran the sequence again.

Escalation: none on its own.

## Checks

1. expect: after the first `ship` FINISH run that exits 0, `.coyodex/project-map.json` carries a
   `grounding` record, read right after that run (the build's own check, or one `python3 -c` over
   the map).
   regression sign: the record is absent until a second `ship` run.

2. expect: `ship` FINISH runs per build ≤ 1 + the number of grounding-note rewrites
   (`coyodex-eval transcript <t> --commands` lists each `ship` turn; a rewrite shows as an edit of
   the note file between two runs).
   regression sign: two consecutive `ship` runs with the note untouched between them.
