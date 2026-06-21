# Change-impact analysis

After the code changes, report the impact on the existing baseline map — what is
**modified / added / deleted** — so you understand the new code grounded in the model you
already learned. No special machinery: the same skill as building the baseline (read code →
meaning), scoped to the diff.

## Principles

- **Driven by BOTH.** The **diff drives** (bottom-up — what changed, what it reaches; this
  catches ADDED code that maps to no existing element). The **baseline guides** (anti-drift
  + consistent names; catches MODIFIED/DELETED). Walking only the baseline's elements would
  miss purely-additive changes, so the diff must be a driver, not just the guide.
- **Cheaper direction.** Start from the change set and trace OUTWARD to the elements it
  reaches. Do NOT walk every baseline element asking "is it affected?" (that's O(all
  elements) and forces proving a negative for each).
- **Baseline pin.** The map records the commit it was built at; the diff is
  `git diff <baseline-commit>..<now>` (use `-M` so renames are renames). git is ground
  truth for added/deleted/renamed.
- **Per change.** Classify modified / added / deleted; **ripple** by following the changed
  element's relationships (edge list) to downstream elements and Golden Path steps. Verify
  by reading the changed code; a pure refactor/move with no behavior change = "no analysis
  impact" (keep noise down).
- **Resolution honesty.** Always place a change at least at **component** level (which file
  → which component — always available). Sharpen to entity / GP step where reading allows.
  **State the resolution reached per change**; don't fake GP-step precision. For a
  widely-used helper, the honest answer is often "load-bearing, high blast radius — reaches
  GP-a/b/c", which is itself useful.
- **Seam caveat.** Tracing callers statically breaks at interface / dependency-injection
  boundaries (callers hit a port, not the impl). Resolve the binding by reading the wiring
  (a `Dependencies` / storage-factory), and note where reachability is incomplete rather
  than claim a clean closure.

## Two artifact types only (do not proliferate documents)

1. **`CODEBASE_ANALYSIS.md`** — the clean current-state baseline (committed, commit-pinned).
   Always reads as "how it is now"; never carries change history. Its narrative (Goal +
   Golden Path) gets PATCHED to the new reality.
2. **`analysis-changes/<date>.md`** — the **annotated baseline-diff**, one per accepted
   cycle. This single file IS the change report + the history + the deletion record.

### Structure of an annotated baseline-diff
1. **Header** — baseline-commit → new-commit, files changed.
2. **Narrative summary** — functional (delta to the Golden Path / use cases) + technical
   (architectural shape). Lives here, at the top, never in the baseline.
3. **Golden Path impact** — which steps' story changed.
4. **Per-element annotated diff** — was → now, classification (modified/added/deleted), why,
   code link, confidence.
5. **New / removed elements.**
6. **Honesty footer** — resolution reached, gaps, DI seams.

## Why the diff is clean

The new baseline is the **patched** old one (surgical edits), not a fresh regeneration. So
`prev → new` shows only real semantic deltas — it's `git diff CODEBASE_ANALYSIS.md` plus an
annotation layer, with no wording-drift noise.

**Deletions need no tombstone/marker:** a diff naturally shows added/changed/removed blocks;
the removed block IS the deletion record. Do not add per-element "changed" markers to the
clean baseline.

The live pre-acceptance report is code-first ("I changed X → it ripples to GP3/4/6/8"); on
accept it's finalized analysis-first as the annotated baseline-diff. Same delta, two
orderings, one persisted file per cycle.

## Accept (after the change is validated)

Four steps:
1. Overwrite `CODEBASE_ANALYSIS.md` with the patched version.
2. Bump its commit pin to the code commit it now describes.
3. Save the annotated baseline-diff as `analysis-changes/<date>.md`.
4. git-commit both — so baseline-commit stays aligned with code-commit. The commit IS the
   acceptance.

## Deliberately out of scope (for now)

No precomputed index / call-graph artifact — re-walk the diff against the baseline each
time. Revisit only if scale/frequency makes re-reading the bottleneck. When that day comes,
the structured source already exists (schema v1), so a viewer/tool parses the markdown
rather than introducing a second maintained model.
