# Design notes — the reasoning behind coyodex

A decision log captured from the session where the method was designed. `method.md` and the
other docs say *what* the method is; this file records *why*, and what was considered and
rejected — so the rationale isn't lost.

## Origin

The method grew from one question: "how would you explore a new codebase top-down, where I
can drill into any line?" Each answer was pressure-tested, which is why most decisions below
come with a rejected alternative.

## The framing — the coyote effect

Vibe coding accumulates un-understood code; you feel fine until you must understand it and
find nothing under your feet (Wile E. Coyote past the cliff edge). coyodex maintains a map
that stays in sync with the code, so you keep your footing without re-reading everything.
**The map's trustworthiness is the whole product** — a stale/confidently-wrong map is a new
cliff. Hence the validator, the accept-cycle, and committing the map with the code are core,
not polish. Best uses: staying oriented while building, and **PR review** (review against a
maintained map, not a raw diff read cold).

## Decisions and why

### Layered, drillable tables
A fixed set of tables at increasing zoom, every row drillable to `file:line`. Rejected:
free-form prose maps (don't compose, can't drill, drift). The layers later turned out to map
onto the C4 model — confirmation the altitude levels were natural.

### Behavioral layer added on top of structural
The structural tables explain the *machine* but not the *intent*. Added Goal → Glossary →
Roles → Use cases on top. Honest limit: intent often isn't in the code (it's in
README/docs/heads), so those are marked inferred and confirmed, not asserted.

### Golden Path as the best top-level view
One concrete, instantiated end-to-end story (named personas, two registers: STORY +
UNDER THE HOOD). Chosen because a single thread proves how the parts connect better than the
parts listed separately. It's a known pattern (worked example / C4 runtime view), not novel.

### Relationships as an edge list (single source)
"X uses Y" lives in a uniform `from — verb — to` edge list, so you can drill from either end.
Bidirectional Golden-Path↔entity traceability is derived from it (forward `Touches:` + a
backward `Used in GP` column). Rejected: storing links twice (they drift).

### Build order ≠ present order
Build bottom-up (nodes before the edges that connect them) but present top-down. Reason:
generating strictly in presentation order makes the top tables guesses. This also doubles as
a completeness checklist (a full harvest catches side doors a top-down pass skips).

### Parallel mode, gated on size
Fan-out (harvest → synthesis → trace) only for large repos; serial is simpler and just as
accurate on small ones. The final reconcile is never delegated — that's the accuracy
safeguard. Delegate the gather, not the reconcile.

### Change-impact: re-walk the diff, NO index (the biggest debate)
The original design grew an elaborate structured **index + call-graph** to map diffs onto the
map. This was challenged and **walked back**:
- *"Why does the baseline need no index but the diff does?"* — it doesn't. Diff impact is the
  same skill as building the baseline (read code → meaning), scoped to the diff.
- *"90% of diffs won't match an exact symbol anchor."* — true. So containment (file →
  component) is the always-available backbone; exact symbol/edge matching is a precision
  *bonus*, concentrated on the spine changes that matter most.
- *"Doesn't that make the index not very useful?"* — for coverage, yes; a file→component map
  suffices. The index's real value (ripple, grounded explanation) is reuse of the map, not a
  new artifact — so it's not worth a separate persisted structure yet.
- **Resolution honesty:** always answer at least at component level; sharpen where reading
  allows; *state the resolution reached*; never fake GP-step precision. A widely-used helper's
  honest answer is "load-bearing, high blast radius — reaches GP-a/b/c."
- **Decision:** no precomputed index/call-graph. Re-walk the diff against the baseline each
  time; the diff drives (catches added code), the baseline guides (anti-drift). Revisit only
  if scale makes re-reading the bottleneck.

### Two artifacts, not three
Clean current-state baseline + one annotated baseline-diff per accepted cycle. The diff is
clean because the new baseline is the *patched* old one (no regeneration → no wording drift).
Deletions need no tombstone — a diff shows removed blocks naturally. Rejected: per-element
"changed" markers in the baseline (they accumulate into a changelog and rot the clean
snapshot). The change *narrative* lives at the top of the diff, never in the baseline.

### Accept = commit the map with the code
Patch the baseline, bump the commit pin, commit it together with the (already-saved) dated
diff. The commit IS the acceptance, and it keeps baseline-commit aligned with code-commit —
the alignment that keeps the map trustworthy over time. The baseline updates **only** here,
never during analysis; until accept it lags the code by exactly the un-accepted diff.

### The change-impact report lives on disk as a draft (reversal)
First designed as an ephemeral overlay shown only in chat. Challenged as fragile — and it is:
a lost session loses it, you can't review it in an editor, and a **PR reviewer needs a file,
not a chat message**. Fix: the report is written to disk at analysis time
(`.coyodex/analysis-changes/<date>.md`), **uncommitted**; accept just commits it. This is
git's own working-tree-vs-commit model, so the draft is not a third artifact — it's the
un-accepted state of the same dated diff. The proliferation worry that motivated "ephemeral"
dissolves once it's the same file in two states.

### Accept is mechanical; the report is patch-complete
All code reasoning happens in the analysis (step 2). Accept must do **no** new inference and
re-read **no** code — otherwise what gets committed could differ from what you reviewed,
breaking the review-then-accept contract and reintroducing wording drift. So the report must
be **patch-complete**: it carries the exact `was → now` text for every element it touches,
including the new text of *rippled* elements (not just "GP4 affected"). If accept finds itself
inferring, the report was incomplete → regenerate it, don't invent at accept time.

### Diagrams are a rendering, and the markdown is the schema
A diagram is another rendering of the same map. Initially this seemed to need a separate
JSON model — but the markdown is *already* structured (tables, IDs, edges). So instead of a
second source, tighten the markdown into a parseable contract (schema v1: IDs, ID-based
refs, no stray pipes, a Golden Path micro-format, a validator). One source, parsed on
demand. Diagram edges come from the verbed component edge list; T1 "Depends on" is derived.

### Domain model as cards (a class diagram), not tables
T5 became **per-entity cards** rendering as a Mermaid `classDiagram` (boxes with attributes +
typed, cardinal relations), specified in [domain-cards.md](../../method/domain-cards.md). A class
view needs three things — entities, attributes, relations. Rejected: **three tables** (entity /
attribute / relation) — splits one entity across three places you can't read together; and a
**single wide table** — a cell with 30 fields is unreadable. The Golden Path already proved the
pattern: an element with rich internal structure is a *block* with a dedicated parser, not a row.
So an entity is a card with the same micro-format. Rejected **Mermaid-as-source** (author a literal
`classDiagram`): code fences are stripped by the parser (invisible as source), and class names
aren't `E` ids, so GP/T6/traceability cross-refs would break — cards keep the global `E` id, so
only T5's internal shape changed, not its id contract. Render target is `classDiagram`, not
`erDiagram` (which forces a lossy crow's-foot cardinality and has no methods). Cost accepted: a
second non-table micro-format, justified exactly as the Golden Path's is. Relations are
single-sourced on the card (one side), never in the backbone edge list.

### The interactive viewer (Tier B) was promoted from spike to `tools/`
Tier B (an interactive HTML viewer) was deferred while Tier A (Mermaid-from-markdown) carried
diagrams. It was then built as a gitignored spike (`internal/viewer/`) and validated on a real map
— it renders the C4 altitudes (Context → Subsystems → Components → code), expand-in-place grouping
with derived inter-subsystem edges, and a diff overlay; the spike even surfaced a real validator
bug (membership read by column position). Having earned it, the viewer was **un-deferred and merged
into `tools/viewer/`**, gated on a promotion punch-list: the schema-v1 grammar extracted to a
single shared module (`tools/schema_v1.py`, imported by validator and parser — no duplicate
grammar); CDN libs pinned + SRI; parser tests added; the membership rule made position-independent.
The Python side stays stdlib-only — the only dependency is client-side JS. Diagram-is-a-rendering
still holds: the viewer parses the committed markdown, never a second source.

### Generated artifacts are standalone w.r.t. the coyodex repo
**Every artifact the tooling generates — today the HTML viewer, and any future rendered output —
must be completely standalone with respect to the coyodex repo.** It is committed *into the mapped
project*, not into coyodex, so it has to open and render on a machine that has never seen coyodex.
The generator therefore **inlines everything** (map data, diagram text, all CSS/JS) into the
artifact — it carries no path back to `tools/` or any coyodex file. Reason: the map travels with the
code it describes (PR review, offline reading), and any reference to the tooling repo would dangle
the moment the artifact leaves this checkout. This is a hard goal for the generators, not a
nice-to-have. Honest limit: "standalone w.r.t. coyodex" is **not** the same as "fully offline" — the
viewer still loads Mermaid + svg-pan-zoom from a CDN (version-pinned + SRI, so no surprise upgrades
and a tampered file is rejected, but it needs network at view time). Vendoring those two libs into
the artifact would close that last gap; deferred, not rejected.

## What was deliberately deferred

- A precomputed index / call-graph (revisit only at scale).
- A cumulative cross-cycle changelog narrative (the dated diffs already are the history).

(The interactive HTML viewer (Tier B) was on this list; it has since been promoted to
`tools/viewer/` — see the decision above.)

## Worked example

The method was first run on a real repo (an MCP gateway), which produced an ID-based
`project-map.md`, a passing validator run, and the first Mermaid diagrams — validating
that the schema is parseable and the diagrams render from it.
