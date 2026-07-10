# Change-impact analysis

After you change code, coyodex reports the impact on the existing baseline map — what is
**modified / added / deleted** — so you understand the new code grounded in the model you
already learned. No special machinery: the same skill as building the baseline (read code →
meaning), scoped to the diff.

## Lifecycle — three steps, two documents

| Step | Action | Writes | Committed? |
|---|---|---|---|
| **1 Build** | map the repo | `.coyodex/project-map.json` (+ generated md/html views + `preindex.json`) | yes — pinned to the code commit it describes |
| **2 Analyze** | diff the code against the baseline | `.coyodex/analysis-changes/<date>.md` (the report) | **no** — written to disk, uncommitted |
| **3 Accept** | fold the report into the baseline | patches `project-map.json`, regenerates the views + pre-index | yes — all committed |

The change-impact report is a **file from the moment it's generated** (step 2) — just
uncommitted. This mirrors git's own model: the report is a *working-tree change*, accept is
the *commit*. So it survives a lost session, you can open / review / share it (essential for
PR review), and you can accept later.

- report (step 2) = working-tree change → on disk, **uncommitted**
- accepted baseline-diff (step 3) = commit → on disk, **committed**

There is no third artifact: the draft report and the accepted baseline-diff are the **same
file in two states**.

## When does the baseline update?

Only at **accept** — never during analysis. The baseline always describes one past commit:
its **pin**. A diff is always measured from the pin to the current code.

```
baseline pinned @ C0  ───────────────────────────▶ (unchanged)
   edit code → C1
   step 2: git diff C0..C1 → report               baseline STILL @ C0
   step 3 accept: patch baseline → C1, bump pin    baseline NOW @ C1
   edit code → C2
   step 2: git diff C1..C2 ...
```

- The **pin = the last accepted point.** Diff left endpoint = pin, right endpoint = **now = the
  current working tree** (includes uncommitted edits and new files, so analysis runs on a dirty tree).
- Between edits and accept the baseline lags the code on purpose; that lag is exactly what
  the diff describes. Accept zeroes it.
- **Cadence is yours:** several code commits then one accept → a cumulative `pin..now` diff;
  accept after each change → small diffs. Either works.

## Principles

- **Driven by BOTH.** The **diff drives** (bottom-up — what changed, what it reaches; this
  catches ADDED code that maps to no existing element). The **baseline guides** (anti-drift
  + consistent names; catches MODIFIED/DELETED). Walking only the baseline's elements would
  miss purely-additive changes, so the diff must be a driver, not just the guide.
- **Cheaper direction.** Start from the change set and trace OUTWARD to the elements it
  reaches. Do NOT walk every baseline element asking "is it affected?" (that's O(all
  elements) and forces proving a negative for each).
- **Baseline pin.** The diff is `git diff <baseline-commit>` — pin **to the current working tree**,
  not commit-to-commit, so it captures committed changes *and* uncommitted edits (use `-M` so renames
  are renames). A plain `git diff` omits **untracked** new files, so also list them
  (`git ls-files --others --exclude-standard`) and treat them as added. git is ground truth for
  added/deleted/renamed. (Analysis runs fine on a dirty tree; *accepting* still needs committed code
  — the pin gate in `method.md`.)
- **Per change.** Classify modified / added / deleted; **ripple** by following the changed
  element's relationships (edge list) to downstream elements and Happy Path steps. Verify by
  reading the changed code; a pure refactor/move with no behavior change = "no analysis
  impact" (keep noise down).
- **Resolution honesty.** Always place a change at least at **component** level (which file →
  which component — always available). Sharpen to entity / HP step where reading allows.
  **State the resolution reached per change**; don't fake HP-step precision. For a
  widely-used helper, the honest answer is often "load-bearing, high blast radius — reaches
  HP-a/b/c", which is itself useful.
- **Seam caveat.** Tracing callers statically breaks at interface / dependency-injection
  boundaries (callers hit a port, not the impl). Resolve the binding by reading the wiring
  (a `Dependencies` / storage-factory), and note where reachability is incomplete rather than
  claim a clean closure.

## The report is patch-complete; accept is mechanical

All the code reasoning happens in **step 2**. **Accept does no new inference and re-reads no
code** — it transcribes the report into the baseline, bumps the pin, and commits. What you
reviewed is exactly what lands; that's the whole point of review-then-accept.

For that to hold, the report must be **patch-complete**: for every element it touches it
carries the exact **was → now** text, not just a description of impact.

| Change | The report must already contain | Accept does |
|---|---|---|
| Modified | the new row/step text | replace the old text |
| Added | the new row + which table/section + where | insert |
| Deleted | which row to remove + every reference to scrub | delete + clean refs |
| Ripple | the **new text** of each rippled element (e.g. UC4's new flow steps, a HP step's new `why`), not just "UC4 affected" | apply it |
| Promotion (drill deeper) | the retired component id, the new subsystem + its child components, and every old `C — verb → X` edge **re-pointed** to a specific new component | retire the component, insert the subsystem + children, re-point the edges, scrub refs to the old id (a subsystem can't be an edge endpoint, so any leftover edge to it fails validation) |

**If accept finds itself inferring or re-reading code, the report was incomplete** —
regenerate the report, don't invent at accept time. The draft `analysis-changes/<date>.md`
*is* the patch; its `was → now` blocks are the edits. (The agent still performs the
find-and-replace edits — markdown isn't a `git apply`-able patch — but adds no new
understanding.)

## Structure of the report / annotated baseline-diff

1. **Header** — baseline-commit → new-commit, files changed.
2. **Narrative summary** — functional (delta to the Happy Path / use cases) + technical
   (architectural shape). Lives here, at the top, never in the baseline.
3. **Happy Path / flow impact** — which use cases entered/left the walk, and whose T6 flow changed.
4. **Per-element annotated diff** — `was → now`, classification (modified/added/deleted), why,
   code link, confidence. *This section is also the patch applied at accept* (see above).
5. **New / removed elements.**
6. **Honesty footer** — resolution reached, gaps, DI seams.

## Why the diff is clean

The new baseline is the **patched** old one (surgical edits), not a fresh regeneration. So
`prev → new` shows only real semantic deltas — `git diff` of the baseline plus an annotation
layer, with no wording-drift noise.

**Deletions need no tombstone/marker:** a diff naturally shows added/changed/removed blocks;
the removed block IS the deletion record. Do not add per-element "changed" markers to the
clean baseline.

## Accept — the four actions

1. Apply the report's `was → now` blocks to the MODEL, `.coyodex/project-map.json` (mechanical —
   surgical field/array edits; the report's `was → now` text names the fields).
2. Bump its commit pin (the model's `commit` and `committed` fields) to the code commit it now
   describes — the same
   **pin gate** as Build applies (`method.md`): the *code* must be committed (the `.coyodex/` report
   and map you are accepting are expected to be dirty — that's what this step commits), else give the
   user the A/B choice and record the pin `-dirty` only if they pick B.
3. Regenerate the committed derived artifacts at the new pin — deterministic, no new inference:
   (a) re-render the markdown view (`.venv/bin/coyodex render .coyodex/project-map.json
   .coyodex/project-map.md`); (b) **if the map has a pre-index** (`.coyodex/preindex.json` exists),
   rebuild it at the now-current commit (`.venv/bin/coyodex preindex --root <repo>`) so its
   `file:line` anchors match the re-pinned map — the viewer's symbol search reads it, so a pin bump
   without this leaves the committed index stale (wrong lines for the files the change touched). (The
   interactive diagram is served live from the model; there is no `.html` file to re-render.)
4. The draft `.coyodex/analysis-changes/<date>.md` becomes the committed record (no rewrite).
5. git-commit all (map + markdown view + pre-index + report) — so baseline-commit stays aligned with
   code-commit. The commit IS the acceptance.
6. **Finish by reporting the URL to open the diagram** in the coyodex map server (where the file
   browser + code viewer work): if the server isn't already running, start it from the coyodex clone
   with `make start` (or `.venv/bin/coyodex serve`), then open
   `http://127.0.0.1:8765/p/<repo-folder-name>/` — or the landing page `http://127.0.0.1:8765/` and
   click this project.

## Deliberately out of scope (for now)

No precomputed index / call-graph artifact — re-walk the diff against the baseline each time.
Revisit only if scale/frequency makes re-reading the bottleneck. When that day comes, the
structured source already exists (`project-map.json`), so a viewer/tool reads it directly rather
than introducing a second maintained model.
