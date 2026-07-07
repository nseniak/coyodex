REPO := $(CURDIR)

# Repo-local virtualenv that coyodex owns. Deps install HERE, never into the user's
# active/system Python — no pollution, no PEP-668 "externally-managed" block. The CLI is
# installed editable, so the repo stays the source of truth (docs/tools evolve without reinstall).
VENV := $(REPO)/.venv
PY := $(VENV)/bin/python
MIN_PY := 3.10

# Skills homes to install into — one per agent family, chosen to cover Claude
# Code, Codex, and Cursor while keeping duplicate discovery to a minimum:
#   ~/.claude/skills  -> Claude Code (Cursor also reads this for compatibility)
#   ~/.agents/skills  -> the cross-agent standard, read natively by Codex AND Cursor
# Cursor needs no dir of its own (it reads both of the above); we skip
# ~/.codex/skills and ~/.cursor/skills on purpose, since .agents already covers
# Codex and Cursor and extra copies would just show up as duplicate skills.
SKILLS_DIRS := $(HOME)/.claude/skills $(HOME)/.agents/skills

.PHONY: install install-eval uninstall uninstall-eval deps dev venv clean start

# Root the map server scans for projects (folders with .coyodex/project-map.json). Defaults to the
# PARENT of this repo, so sibling repos (the common "all my code in one folder" layout) are served
# together. Override for a different layout, e.g.  make start ROOT=~/code  or  make start ROOT=.
ROOT ?= ..
PORT ?= 8765

# Create the repo-local venv. Requires Python $(MIN_PY)+ (the pre-index's tree-sitter deps
# declare requires-python >=3.10); fail fast with a clear message instead of a cryptic error.
venv:
	@command -v python3 >/dev/null 2>&1 || { \
		echo "ERROR: python3 not found. coyodex requires Python $(MIN_PY)+ (see README 'Requirements')."; exit 1; }
	@python3 -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)' || { \
		echo "ERROR: Python $(MIN_PY)+ required; found $$(python3 --version 2>&1). See README 'Requirements'."; exit 1; }
	@test -d "$(VENV)" || python3 -m venv "$(VENV)"

# Install the coyodex CLI editable into the venv, WITH the pre-index extra (tree-sitter for
# polyglot symbol/import extraction). The core gate (validate + render) stays dependency-free;
# tree-sitter is a scoped exception confined to `coyodex preindex` (see internal/docs/design-notes.md).
# Run `make deps` alone to refresh after editing pyproject deps.
deps: venv
	$(PY) -m pip install -e '$(REPO)[preindex]'

# Contributor setup: same as `deps` plus the test/type-check tooling (pytest, pyright) in the venv.
# Run the gates with: .venv/bin/pytest tests   and   .venv/bin/pyright coyodex
dev: venv
	$(PY) -m pip install -e '$(REPO)[preindex,dev]'

# Install the coyodex skill globally for all agents (macOS/Linux). Also builds the venv and
# installs the CLI (via `deps`) so a one-time `make install` covers everything.
# Copies SKILL.md into each skills home with this repo's absolute path baked in
# (replacing __COYODEX_HOME__), so the skill points straight here with no runtime
# lookup. The method docs and tools are still read live from this repo, so they
# keep evolving without reinstalling. Re-run install only if you move the repo or
# edit SKILL.md itself.
install: deps
	@for dir in $(SKILLS_DIRS); do \
		rm -rf "$$dir/coyodex"; \
		mkdir -p "$$dir/coyodex"; \
		sed 's|__COYODEX_HOME__|$(REPO)|g' skill/coyodex/SKILL.md > "$$dir/coyodex/SKILL.md"; \
		echo "Installed coyodex skill -> $$dir/coyodex (home: $(REPO))"; \
	done

# Install the coyodex-eval skill globally — SEPARATE from `install`, since the eval (method-quality
# regression) is opt-in. Same COYODEX_HOME substitution, so the skill points back at this clone for the
# eval bundle under eval/ (method.md, thresholds.json, rubric.md) and the CLI. Depends on `deps`
# so the venv/CLI exist.
install-eval: deps
	@for dir in $(SKILLS_DIRS); do \
		rm -rf "$$dir/coyodex-eval"; \
		mkdir -p "$$dir/coyodex-eval"; \
		sed 's|__COYODEX_HOME__|$(REPO)|g' eval/SKILL.md > "$$dir/coyodex-eval/SKILL.md"; \
		echo "Installed coyodex-eval skill -> $$dir/coyodex-eval (home: $(REPO))"; \
	done

uninstall:
	@for dir in $(SKILLS_DIRS); do \
		rm -rf "$$dir/coyodex"; \
		echo "Uninstalled coyodex skill from $$dir/coyodex"; \
	done

uninstall-eval:
	@for dir in $(SKILLS_DIRS); do \
		rm -rf "$$dir/coyodex-eval"; \
		echo "Uninstalled coyodex-eval skill from $$dir/coyodex-eval"; \
	done

# Start the local map server so the viewer's file browser + code viewer work (files read from git
# at each map's commit). Serves every project found under ROOT; opens the project list in a browser.
# Depends on `deps` so the venv/CLI exist. Ctrl-C to stop.
start: deps
	$(VENV)/bin/coyodex serve "$(ROOT)" --port $(PORT) --open

# Remove the repo-local venv (run `make install` again to rebuild it).
clean:
	rm -rf "$(VENV)"
	@echo "Removed $(VENV)"
