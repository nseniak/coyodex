# Design notes — the reasoning behind coyodex

A decision log captured from the session where the method was designed. `METHOD.md` and the
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
Overwrite the baseline, bump the commit pin, save the dated diff, git-commit. The commit IS
the acceptance, and it keeps baseline-commit aligned with code-commit. This alignment is what
keeps the map trustworthy over time.

### Diagrams are a rendering, and the markdown is the schema
A diagram is another rendering of the same map. Initially this seemed to need a separate
JSON model — but the markdown is *already* structured (tables, IDs, edges). So instead of a
second source, tighten the markdown into a parseable contract (schema v1: IDs, ID-based
refs, no stray pipes, a Golden Path micro-format, a validator). One source, parsed on
demand. Diagram edges come from the verbed component edge list; T1 "Depends on" is derived.

## What was deliberately deferred

- A precomputed index / call-graph (revisit only at scale).
- The interactive HTML diagram viewer (Tier B). Tier A = Mermaid generated from the markdown.
- A cumulative cross-cycle changelog narrative (the dated diffs already are the history).

## Worked example

The method was first run on a real repo (an MCP gateway), which produced an ID-based
`CODEBASE_ANALYSIS.md`, a passing validator run, and the first Mermaid diagrams — validating
that the schema is parseable and the diagrams render from it.
