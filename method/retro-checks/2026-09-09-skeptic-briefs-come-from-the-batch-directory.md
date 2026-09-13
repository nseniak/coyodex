# The skeptic briefs are written from the batch directory, never by a hand loop

Change (2026-09-09): `coyomap contract skeptic --from-batches .coyomap/verify --fill <slots>
--out-dir <dir> [--votes security=3]` writes one brief per `claims-*.json`, filling «BATCH» and
«CLAIMS» from the file names, writes N voters (`-a`, `-b`, `-c`) over one claims file for a voted
theme, SKIPS any brief that already exists, and prints the pointer prompts to send. On the
2026-09-08 mcpolis build the lead hand-wrote this loop and passed `--force` on all 38 briefs,
which is the overwrite the refusal exists to stop (retro row 19).

Escalation: none on its own.

## Checks

1. expect: the build transcript shows one `contract skeptic --from-batches` call per fan-out and
   no `--force` on a skeptic brief.
   regression sign: a shell or Python loop over `claims-*.json` calling `contract skeptic --fill
   --out`, or `--force` on any skeptic brief.

2. expect: the voted theme's briefs are named `skeptic-security-a/b/c.md` and their verdict files
   pair with them by name in `grounding lint --expect`.
   regression sign: voters named by hand, or `--expect` listing ids the briefs do not carry.
