REPO := $(CURDIR)
SKILLS_DIR := $(HOME)/.claude/skills

.PHONY: install uninstall

# Install the coyodex skill globally (macOS/Linux).
# - symlinks the skill into ~/.claude/skills so the global skill always
#   reflects this repo's edits
# - writes this repo's absolute path into .coyodex-home so the skill points
#   straight here instead of searching for the clone
install:
	mkdir -p $(SKILLS_DIR)
	ln -sfn $(REPO)/skill/coyodex $(SKILLS_DIR)/coyodex
	echo $(REPO) > $(REPO)/skill/coyodex/.coyodex-home
	@echo "Installed coyodex skill -> $(SKILLS_DIR)/coyodex (home: $(REPO))"

uninstall:
	rm -f $(SKILLS_DIR)/coyodex
	rm -f $(REPO)/skill/coyodex/.coyodex-home
	@echo "Uninstalled coyodex skill from $(SKILLS_DIR)/coyodex"
