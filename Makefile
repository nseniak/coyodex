REPO := $(CURDIR)
SKILLS_DIR := $(HOME)/.claude/skills

.PHONY: install uninstall

# Install the coyodex skill globally (macOS/Linux).
# Copies SKILL.md into ~/.claude/skills/coyodex with this repo's absolute path
# baked in (replacing __COYODEX_HOME__), so the skill points straight here with
# no runtime lookup. The method docs and tools are still read live from this
# repo, so they keep evolving without reinstalling. Re-run install only if you
# move the repo or edit SKILL.md itself.
install:
	rm -rf $(SKILLS_DIR)/coyodex
	mkdir -p $(SKILLS_DIR)/coyodex
	sed 's|__COYODEX_HOME__|$(REPO)|g' skill/coyodex/SKILL.md > $(SKILLS_DIR)/coyodex/SKILL.md
	@echo "Installed coyodex skill -> $(SKILLS_DIR)/coyodex (home: $(REPO))"

uninstall:
	rm -rf $(SKILLS_DIR)/coyodex
	@echo "Uninstalled coyodex skill from $(SKILLS_DIR)/coyodex"
