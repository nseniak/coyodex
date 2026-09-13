# Small themes share one batch, and the prose batches are minted only on request

Change (2026-09-09): `coyomap audit --batches` puts every theme with fewer than 5 claims into one
`claims-small.json` (`theme: mixed`, each claim carrying its own `theme`); `--floor N` moves the
line, and the security theme never merges. The same command writes no `prose-N.json` unless
`--with-prose` is passed, and removes any left from an earlier run. On the 2026-09-08 mcpolis
build the lead dispatched `claims-lifecycle` and `claims-messaging` with 1 claim each as two whole
fresh-context skeptics, and it minted 13 prose batches, dispatched none, and deleted them (retro
rows 20 and 3; the fourth build in a row to mint and drop them). method.md now says what the
verification budget buys on every build: the behaviour theme; the prose surface only when asked.

Escalation: none on its own.

## Checks

1. expect: no dispatched skeptic batch in the build transcript carries fewer than 5 claims, unless
   it is a security batch or the operator passed `--floor`.
   regression sign: a `claims-<theme>.json` under 5 claims dispatched as its own agent.

2. expect: `claims-small.json`, when written, is dispatched as ONE skeptic and its verdict rows
   pair by claim text like any other batch.
   regression sign: the small batch left undispatched, or split back by hand.

3. expect: `prose-*.json` absent from `.coyomap/verify/` unless the transcript shows
   `--with-prose`, and finalize's unread-prose check silent.
   regression sign: prose batches minted and deleted, or the unread-prose advisory firing on a
   build that never asked for them.
