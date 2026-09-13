# The fan-out timings survive `coyomap-eval archive`

Change (2026-09-08): `eval/tools/coyomap_eval/archive.py` keeps `.coyomap/fanout-timings.json` in
place, beside `.ignore` and `.gitignore`. It is cross-build input: `timings order` reads the most
recent recording per slice to order the next build's dispatch, and on the 2026-09-08 mcpolis build
the verb answered "no timings recorded" on a repo with 26 archived maps because every recording
had moved into `dev-rebuilds/` with the map it was made under.

Escalation: none on its own.

## Checks

1. expect: the next build's `coyomap timings order --phase harvest` prints an order derived from
   the previous build's rows (the transcript shows slice names and minutes, not "no timings
   recorded").
   regression sign: "no timings recorded" on a repo whose previous build ran `timings record`.

2. expect: the archived map under `dev-rebuilds/NNNN/` carries no `fanout-timings.json`, and the
   live `.coyomap/` still does after the archive step.
   regression sign: the file in the archive and gone from `.coyomap/`.
