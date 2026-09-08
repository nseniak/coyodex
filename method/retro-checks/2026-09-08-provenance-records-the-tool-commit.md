# `provenance stamp` records the tool commit of the build

Change (2026-09-08): each session entry in `.coyodex/provenance.json` carries `tool_commit`, the
coyodex clone's `git describe --always --dirty` at stamp time, and the retro's Step 0c reads the
previous build's `old` boundary from there. The map header's `tool_commit` is re-stamped by any
later repair (`assemble` runs again), which on the 2026-09-08 retro moved the boundary from
`21de5e3` to `55ba550` and dropped 5 of 13 pending check files.

Escalation: none on its own.

## Checks

1. expect: the next build's `provenance.json` last session carries a non-empty `tool_commit`
   equal to the coyodex clone's HEAD at build time.
   regression sign: the field absent or `null` on a build made from a clone.

2. expect: the next retro's Step 0c range starts at the previous build's `provenance` tool
   commit, and the number of pending check files it runs equals the files added in that range.
   regression sign: a range whose `old` differs from the previous provenance entry.
