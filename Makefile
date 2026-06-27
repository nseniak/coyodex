REPO := $(CURDIR)

# Skills homes to install into — one per agent family, chosen to cover Claude
# Code, Codex, and Cursor while keeping duplicate discovery to a minimum:
#   ~/.claude/skills  -> Claude Code (Cursor also reads this for compatibility)
#   ~/.agents/skills  -> the cross-agent standard, read natively by Codex AND Cursor
# Cursor needs no dir of its own (it reads both of the above); we skip
# ~/.codex/skills and ~/.cursor/skills on purpose, since .agents already covers
# Codex and Cursor and extra copies would just show up as duplicate skills.
SKILLS_DIRS := $(HOME)/.claude/skills $(HOME)/.agents/skills

.PHONY: install uninstall

# Install the coyodex skill globally for all agents (macOS/Linux).
# Copies SKILL.md into each skills home with this repo's absolute path baked in
# (replacing __COYODEX_HOME__), so the skill points straight here with no runtime
# lookup. The method docs and tools are still read live from this repo, so they
# keep evolving without reinstalling. Re-run install only if you move the repo or
# edit SKILL.md itself.
install:
	@for dir in $(SKILLS_DIRS); do \
		rm -rf "$$dir/coyodex"; \
		mkdir -p "$$dir/coyodex"; \
		sed 's|__COYODEX_HOME__|$(REPO)|g' skill/coyodex/SKILL.md > "$$dir/coyodex/SKILL.md"; \
		echo "Installed coyodex skill -> $$dir/coyodex (home: $(REPO))"; \
	done

uninstall:
	@for dir in $(SKILLS_DIRS); do \
		rm -rf "$$dir/coyodex"; \
		echo "Uninstalled coyodex skill from $$dir/coyodex"; \
	done
