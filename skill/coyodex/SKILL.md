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

coyodex is a method (a set of prompts) plus tools that an agent drives to build and maintain a
drillable map of a codebase. This skill is the entry point: it locates the method, then runs the
right one of three modes. **The method docs are the source of truth — read them and follow them;
this skill only sequences the work so you don't start cold.**

## Step 0 — locate the coyodex clone (always first)

The method lives in a separate `coyodex` repo, cloned next to the project. Find `method.md`:

```
for d in ~/Projects/coyodex ../coyodex ../../coyodex ~/coyodex; do
  [ -f "$d/method.md" ] && echo "FOUND $d" && break
done
```

If none match, ask the user for the path to their coyodex clone. Everything below calls tools by
their path **inside that clone** (e.g. `$COYODEX/tools/validate_analysis.py`).

## Pick the mode from what the user asked

| The user wants | Mode | Read first |
|---|---|---|
| a new map / "map this repo" / "build the baseline" | **Build** | `method.md` |
| "I changed code, what's the impact?" | **Analyze** | `method.md` + `method/change-impact.md` |
| "the report looks right, accept it" | **Accept** | `method/change-impact.md` |

## Build (baseline map)

1. Read `method.md` fully (and `method/schema-v1.md` for the table/ID contract, and
   `method/domain-cards.md` for the T5 domain-model card format).
2. **Copy the template** `method/templates/project-map.template.md` to the analyzed repo's
   `.coyodex/project-map.md` and fill cells in place. It already has every standard section with
   schema-correct shapes (each ID alone in its own first cell) — this is what makes the map pass
   validation on the first write.
3. Survey the repo and harvest the inputs, building bottom-up (T3 → T4/T2/T5 → T1 → subsystems →
   T6 + edges), presenting top-down. On a large repo use parallel mode (`method.md` → "Parallel
   mode"): fan out one harvest agent per slice using the **harvest-prompt template** there; a
   small repo is fine serial. Verify every `file:line` anchor against source; label verified vs
   inferred.
4. Record the build commit in the map (the baseline pin).
5. Validate, fixing until clean:
   `python3 $COYODEX/tools/validate_analysis.py /path/to/repo/.coyodex/project-map.md`
6. Render the diagram (deterministic, no new analysis):
   `python3 $COYODEX/tools/viewer/render.py …/.coyodex/project-map.md …/.coyodex/project-map.html`
7. Report the absolute paths of **both** the map and the HTML as links.

## Analyze (change-impact report)

Follow `method/change-impact.md`: diff `git diff <baseline-pin>..HEAD -M`, trace OUTWARD from the
changed code to the elements it reaches, and write a **patch-complete** report (every touched
element carries its `was → now` text) to `.coyodex/analysis-changes/<date>.md`. Leave it
**uncommitted** for review. Do not touch the baseline yet.

## Accept (fold report into baseline)

Mechanical, per `method/change-impact.md` — no new code reading: apply the report's `was → now`
blocks to `.coyodex/project-map.md`, bump the commit pin, re-render the diagram, then commit the
map + diagram + the now-accepted report together.

## Always

- Attach `file:line` to every element; label verified vs inferred.
- After any write or patch of the map, re-validate then re-render — the HTML is a rendering of the
  map, never a second source.
