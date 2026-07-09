# LLM-judge rubric — coyodex map quality

Each dimension is scored **0–4**. N judges score independently; the eval takes the **median** per
dimension. A judge is given the produced `project-map.md` and read access to the source repo, and must
justify every score with a `file:line` from the code. A score you cannot back with a `file:line` must
be scored **down**, not guessed.

## Dimensions

1. **Faithfulness** — do the map's "actually-does" claims match the code? Sample the backbone edges and
   Security & auth rows; each false claim is a hard hit. Judge the RELATIONSHIP a claim states, not its
   anchor: a true relationship with an off-by-some-lines anchor is still faithful (the anchor is scored
   under Drill accuracy). (Overlaps the L2-grounding pass-rate — the judge adds semantic nuance the
   claim-by-claim check can't.)

2. **Completeness** — does the map cover the system's real surface area, or are whole modules / entry
   points / entities missing? Cross-check against the repo's top-level structure.

3. **Drill accuracy** — do the drill anchors (`file:line`, links) resolve to the code they claim to
   explain? Sample anchors and open them. Anchor-line EXACTNESS lives here — a stale or drifted line
   number is a Drill-accuracy hit, never a grounding refutation of the relationship it anchors.

4. **Altitude discipline** — is each element at the right zoom (a component is a component, not a whole
   subsystem folded into one box; the domain model is not under-harvested)?

5. **Happy-Path coherence** — does the ordered spine read as a real end-to-end walk, with each step's
   `why:` precondition satisfied by an earlier step?

## Output (per judge)

An integer `score` (0–4) for each of the five dimensions, a one-line `justification`, and at least one
`evidence` `file:line`, plus a short `notes` summary. The judge harness fixes the exact JSON shape.
