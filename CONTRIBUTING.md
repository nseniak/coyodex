# Contributing to coyodex

Thanks for taking a look. coyodex is **alpha (v0.1.0)** — experimental, early,
and moving fast. That means feedback is worth a lot right now, and the bar to
contribute is low: a clear bug report or a sharp idea is a real contribution.

By participating you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to help

- **Report a bug.** Something the skill, the method, or the viewer got wrong.
  Open a [bug report](../../issues/new?template=bug_report.yml).
- **Share an idea or feedback.** Missing capability, confusing output, an awkward
  step in the build → analyze → accept loop. Open an
  [idea / feedback issue](../../issues/new?template=idea.yml).
- **Comment on map quality.** Because map quality depends on the coding agent and
  model, concrete before/after examples ("the map said X, the code does Y") are
  especially useful.
- **Send a pull request.** For docs, the method, or the Python tooling. For
  anything non-trivial, please open an issue first so we can agree on the shape
  before you spend time on it.

## How the repo is laid out

- **`method.md`** — the single source of truth for the method. The skill follows
  it; it is not a mirror of the code. Changes to behavior usually start here.
- **`method/`** — the supporting method docs (`model.md`, `domain-cards.md`,
  `change-impact.md`, `diagrams.md`) and templates.
- **`skill/coyodex/`** — the agent skill (`SKILL.md`) that drives the method; works on
  Claude Code, Codex, and Cursor.
- **`tools/coyodex/`** — the Python package behind the `coyodex` CLI: the pre-index, schema
  validation, the analysis validator, and the **`viewer/`** (builds the map's view data and
  serves the interactive viewer via `coyodex serve`). `cli.py` is the subcommand dispatcher.
- **`tests/`** — the tool tests (stdlib runners; also run under `pytest`).
- **`README.md`** — user-facing overview and the install / usage steps.

> `internal/` (design notes, working drafts) is **not** part of the method and is
> git-ignored. Don't treat it as instructions or as input to a map.

## Local setup

The skill itself needs no build — install it once from the repo root (macOS/Linux).
`make install` copies `SKILL.md` (with the repo path baked in) into each agent's
skills home — `~/.claude/skills` (Claude Code) and `~/.agents/skills` (the cross-agent
standard read by Codex and Cursor):

```
make install      # copies skill/coyodex -> ~/.claude/skills + ~/.agents/skills
make uninstall     # removes it from both
```

The `coyodex` package is tested with `pytest` and type-checked with `pyright` (see
`pyrightconfig.json`). `make dev` builds the repo-local venv and installs both into it
(alongside the editable package), so the gates run against the installed CLI:

```
make dev                     # venv + editable install + pytest/pyright
.venv/bin/pytest tests       # run the tool tests
.venv/bin/pyright tools      # type-check (please keep it clean)
```

## Pull request guidelines

- **Keep the diff scoped** to one change. The project itself is built around
  small, reviewable diffs — please mirror that.
- **Match the surrounding style.** Plain prose in the docs; typed Python in the
  tools (type annotations, no unnecessary `Any`).
- **Update the method and the docs together with the code.** If behavior changes,
  `method.md` / `method/` should change in the same PR, since the method is the
  source of truth.
- **Run the gates** (`.venv/bin/pytest tests`, `.venv/bin/pyright tools`) before pushing, and say in
  the PR what you ran.
- **Fill in the PR template** so a reviewer can see what changed, why, and how you
  checked it.

## A note on stability

The on-disk map format and the method are still moving — there are **no
backward-compatibility guarantees yet**. Treat generated maps as disposable, and
don't be surprised if a change touches the format. If a change *does* break the
format, please call that out explicitly in the PR.

## Licensing of contributions

coyodex is licensed under the [Apache License 2.0](LICENSE). By contributing, you
agree that your contributions are licensed under the same terms, including the
patent grant in section 3 of that license.
