---
name: coyodex
description: >
  Build and maintain a coyodex project map — a top-down, drillable map of a codebase (behavioral
  layer first, then the structural machine), committed next to the code and rendered as an
  interactive C4 diagram. Use this skill whenever the user wants to: generate / build a project
  map or codebase map "with the coyodex method", "map this repo", analyze the change impact of a
  diff against an existing map, or accept a change-impact report into the baseline. Triggers on
  "coyodex", "project map", "codebase map", "change impact", "accept the map".
---

# coyodex

coyodex is a method (prompts) + tools for a drillable map of a codebase. **The repo is the source of
truth — this skill only points at it. Read the method docs and follow them; don't work from memory.**

Read `__COYODEX_HOME__/method/dispatch.md` and follow it. It picks the mode (build / analyze /
accept), handles an existing baseline, and points to every other doc and tool. Every path it
mentions is relative to `__COYODEX_HOME__` — the coyodex clone.
