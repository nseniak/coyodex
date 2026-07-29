# trapdoor — the trap fixture

A synthetic codebase that plants, on purpose, every defect class four real coyodex builds
produced. It exists so the regression suite can assert things unit tests structurally cannot:
not only *does the code do the right thing when called*, but *does the method reach for the
tool at all*, and *does the tool say the right thing about a real tree*.

**This tree is not part of coyodex.** `.coyodex/.ignore` at the repo root excludes
`eval/fixtures/trapdoor/`, so coyodex's own self-map never ingests it. That ignore file is
precisely why deliberately-broken code can live inside this repo.

## Layout

| path | what it is | traps |
|---|---|---|
| `traps.yaml` | **the single source of truth** — every layer reads it | — |
| `src/auth/`, `src/lifecycle/` | anchor traps: far-from-header enforcement, prose lifecycle | A1 A2 |
| `src/domain/`, `src/store/` | the domain model + its repository | A3 P1 P2 P3 |
| `src/api/`, `src/services/`, `src/clients/` | the three overclaim shapes | O1 O2 O3 O4 |
| `src/messaging/` | publishers, one consumer, two spellings | M1 M2 M3 M4 |
| `src/base/`, `docker-compose.yml`, `Dockerfile.*` | deployment topology | D1–D6 |
| `src/plugins/`, `src/flatpack/`, `src/generated/`, `web/` | altitude | G1–G5 |
| `config.default.env`, `docs/runbook.md` | environment | E1 E2 |
| `golden/project-map.json` | a frozen map OF this fixture, used by L2 | — |

## Size

Hand-written trap code is ~1.5 kLOC — that is what a build agent has to read and judge, and it
is what keeps a full build over this fixture near ten minutes rather than an hour.
`src/flatpack/`, `src/generated/` and `web/src/components/` add mechanical filler on top,
because traps G1–G3 are *about size*: the leaf caps only bind if the tree actually exceeds
them. The filler is deliberately repetitive so it skims in seconds.

## Gotchas that cost time

- **The walk prefers `git ls-files`.** A fixture file that is not committed is invisible to
  `coyodex preindex`. Commit before you measure.
- **Building a map here writes `eval/fixtures/trapdoor/.coyodex/`** — nested inside the coyodex
  repo's own tree. `.coyodex` is a built-in exclusion *and* the ignore entry covers the whole
  subtree, so it stays out of the self-map either way.
- **`git -C eval/fixtures/trapdoor ls-files` DOES return fixture-relative paths** (`src/auth/gate.py`,
  not `eval/fixtures/trapdoor/src/auth/gate.py`) even though the fixture is not its own git repo —
  `ls-files` is cwd-relative. That is what lets `coyodex preindex --root eval/fixtures/trapdoor`
  take the git path and see the fixture as a repo root. Verified, not assumed: it is the one
  thing that would silently break every measurement here if it were the other way round.

## The golden map

`golden/project-map.json` is a real `coyodex assemble` output — fragments in, canonical model
out, exactly the way any map is written; nothing in it is hand-serialized. It is **not** the
product of a live agent build; producing one of those and blessing it as the golden map is the
open follow-up recorded in the L3 design. What L2 needs from it today is a real, schema-valid,
validator-exercised map of a real tree, and it is that.
