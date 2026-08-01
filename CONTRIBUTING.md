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
- **`tests/`** — the tool tests, plus the two contract layers: `test_method_contract.py`
  (does the method name tools that exist?) and `test_trapdoor_tools.py` (do the tools say the
  right thing about a real tree?). Stdlib runners; also run under `pytest`.
- **`eval/`** — the two evals and their tests: map quality (`eval/README.md`) and the build-process
  scorecard. `eval/fixtures/trapdoor/` is a synthetic codebase that deliberately plants every
  defect class real builds produced; `traps.yaml` there is the source of truth for what is planted.
- **`README.md`** — user-facing overview and the install / usage steps.

> `internal/` (design notes, working drafts) is **not** part of the method and is
> git-ignored. Don't treat it as instructions or as input to a map.

## Local setup

The skill itself needs no build — install it once from the repo root (macOS/Linux).
`make install` copies `SKILL.md` (with the repo path baked in) into each agent's
skills home — `~/.claude/skills` (Claude Code) and `~/.agents/skills` (the cross-agent
standard read by Codex and Cursor):

```
make install       # the USER skill: skill/coyodex -> ~/.claude/skills + ~/.agents/skills
make install-dev   # both DEVELOPER skills: coyodex-eval + coyodex-retro
make uninstall     # removes the user skill from both homes
make uninstall-dev # removes both developer skills
```

`install-dev` is the one a contributor wants: `coyodex-eval` answers "did my change make the maps
worse?" and `coyodex-retro` answers "what did that run reveal?" — two halves of one feedback loop.
They are deliberately NOT part of `make install`, so installing the developer surface is never a
side effect of setting the tool up. (`make install-eval` / `make install-retro` still install one
at a time.)

**Re-run the relevant target after editing any `SKILL.md`, or after moving the clone.** The install
renders a COPY into the skills homes with the repo path baked in, and nothing re-runs it for you —
which is how the main skill spent weeks telling agents to read a method doc that had been renamed.
`tests/test_skill_pointers.py` keeps the copies thin enough that drift is nearly harmless, but it
cannot see the installed files.

The `coyodex` package is tested with `pytest` and type-checked with `pyright` (see
`pyrightconfig.json`). `make dev` builds the repo-local venv and installs both into it
(alongside the editable package), so the gates run against the installed CLI:

```
make dev                # venv + editable install + pytest/pyright
.venv/bin/pytest        # run the whole suite — see the warning below
.venv/bin/pyright tools # type-check (please keep it clean)
```

> **Run `pytest` with no path.** The suite lives in two places (`tests/` and `eval/tests/`)
> and `pyproject.toml` lists both under `testpaths`. Naming a path on the command line
> **overrides** that setting, so `pytest tests` silently skips every test under `eval/tests`
> and still reports green. Plain `.venv/bin/pytest` runs all of them.

## How to test a change

There is no single command that covers everything, because the layers answer different
questions. What you changed decides how far up you need to go.

| tier | command | answers |
|---|---|---|
| **1. The gates** | `.venv/bin/pytest` · `.venv/bin/pyright tools` | Is anything broken? Do the tools do the right thing, and does the method still name commands and flags that exist? |
| **2. Process corpus** | `COYODEX_L3_CORPUS=1 .venv/bin/pytest eval/tests/test_process_corpus.py -q -s` | Do the transcript detectors still read saved builds the same way? |
| **3. A real build** | `claude -p "/coyodex from scratch"` in a repo, then `coyodex-eval process <transcript>` | Did the agent actually *do* the thing? |
| **4. Map quality** | `/coyodex-eval` in a project with a committed map | Is the map any good — grounding, rubric, coverage? |

**Tier 1 is required for every PR.** It is fast (~20s) and deterministic. It covers three
layers:

- the tool tests — what the code does when it is called;
- **`tests/test_method_contract.py`** — the prose↔tool contract, checked statically: every
  command and flag `method.md` names really exists, and every advisory the validator prints
  can be answered. This layer exists because `coyodex reconcile` once shipped fully working
  and fully tested while appearing nowhere in the method, so no build could reach it;
- **`tests/test_trapdoor_tools.py`** — the tools run against `eval/fixtures/trapdoor/`, a
  synthetic codebase that deliberately plants every defect class real builds produced. Its
  `traps.yaml` is the single source of truth for what is planted and which layer asserts it.

**Tier 2 is opt-in** because it reads build transcripts from `~/.claude/projects/`, which
live outside the repo and will not exist on another machine. Without the flag the tests skip
cleanly. Run it when you touch the process checker itself.

**Tier 3 is the only thing that can test a change to `method.md`.** The method is a prompt.
Tiers 1 and 2 read text and old recordings; neither can tell you whether an agent reading
your new wording behaves differently. That gap is not theoretical — a rule was once rewritten
and the behaviour did not move at all, and nobody could tell. So: make a real build, score its
transcript, and diff it against a build from before your change.

```
.venv/bin/coyodex-eval process <transcript.jsonl>        # writes a scorecard next to it
.venv/bin/coyodex-eval process --diff before.json after.json
```

The scorecard is **never a gate**. It reports `observed / of` with turn numbers attached, not
pass/fail: a single run proves nothing, and these are LLM builds that vary. A number that
moves is something to look at. The design and the ten assertions are in
[`eval/fixtures/trapdoor/L3-DESIGN.md`](eval/fixtures/trapdoor/L3-DESIGN.md).

**Tier 4** costs real model time and money — see [`eval/README.md`](eval/README.md). Reach for
it when your change should alter what a map *contains*, not which commands get run.

### Short version

| you changed | run |
|---|---|
| `tools/coyodex/` | tier 1, plus tier 2 if you touched the transcript detectors |
| `method.md` or `method/` | tier 1, then **tier 3** — nothing else can tell you it landed |
| `eval/` | tier 1 + tier 2 |
| something you expect to improve map quality | tier 1 + tier 4 |

## Pull request guidelines

- **Keep the diff scoped** to one change. The project itself is built around
  small, reviewable diffs — please mirror that.
- **Match the surrounding style.** Plain prose in the docs; typed Python in the
  tools (type annotations, no unnecessary `Any`).
- **Update the method and the docs together with the code.** If behavior changes,
  `method.md` / `method/` should change in the same PR, since the method is the
  source of truth.
- **Run the gates** (`.venv/bin/pytest` with no path, `.venv/bin/pyright tools`) before pushing,
  and say in the PR what you ran. If you changed `method.md` or `method/`, say whether you ran a
  real build (tier 3 above) — a method change the gates pass can still fail to reach the agent.
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
