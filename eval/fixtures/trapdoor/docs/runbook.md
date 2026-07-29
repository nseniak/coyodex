# Trapdoor runbook

Operational notes for the fixture service. Read this the way a build agent reads a repo's own
docs: as intent, not ground truth.

## Environments

Three deploy shapes, declared as compose profiles in `docker-compose.yml`:

| profile | what runs | notes |
|---|---|---|
| `dev` | api, worker, web-dev, primary, broker | the frontend is a live Vite process here |
| `cloud` | api, worker, primary, broker, search | the frontend is a static bundle inside the api image |
| `standalone` | standalone | one container; the frontend is baked in by `Dockerfile.standalone` |

## Configuration

Defaults ship in `config.default.env` — committed, non-secret, and the source of truth for the
key list. Tokens are injected by the platform at deploy time.

> **TRAP E2.** The next paragraph MENTIONS a dotenv filename in prose. Nothing here reads it,
> writes it, or asks anyone to open it — the sentence is documentation about naming policy. A
> secrets guard that matches the TEXT of a command rather than an actual file access trips on
> this line, which is how a grep pattern containing the same filename tripped the guard during
> the study that motivated this fixture.

Naming policy: per-environment overrides are conventionally called `.env.production` and are
never committed; only `config.default.env` is in git. If you find a file with that override
name in a checkout, it is local and untracked.

## Channels

| channel | published by | consumed by |
|---|---|---|
| `ticket.state.changed` | `EventPublisher.publish_state_change` | nobody (trap M1) |
| `ticket.comment.added` | `EventPublisher.publish_comment` | `CommentConsumer` |
| `escalation.paged` | `EventPublisher.publish_page` | nobody (trap M1) |

Note the plugin in `src/plugins/p03/` writes the same first channel with a hyphenated spelling.
It is ONE channel; two catalog rows for it is the duplicated-row defect (trap M2).

## Directories the map should judge, not copy

- `src/generated/` — machine-emitted, ~900 LOC, collapses to one box and is RECORDED as folded.
- `src/flatpack/` — 12 files, no subdirectories, over the LOC cap: it SPLITS into cohesive
  groups, it does not become one box.
- `src/plugins/p01..p08` — eight identically-shaped dirs: the homogeneous-family exemption.
- `web/src/components/` — file-per-component frontend; the FILE cap binds here and E lands far
  above the honest altitude.
