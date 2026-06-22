# Schema v1 — making the map a clean machine source

`project-map.md` is semi-structured markdown, but to drive diagrams and tooling
reliably it must obey a contract. Schema v1 is that contract: treat the table/ID/edge
format as a real schema, not just a nice layout. A diagram is just another rendering of
this same model — so the markdown stays the **single source**; any `model.json` is an
ephemeral parse result, never a second hand-maintained document.

## The ID scheme

Every element has a stable, unique ID by prefix:

| Prefix | Element |
|---|---|
| `UC` | Use case |
| `R` | Role / actor (optional; reference roles by name if unprefixed) |
| `GP` | Golden Path step |
| `C` | Component (T1) |
| `S` | Subsystem — a group of components and/or nested subsystems (optional) |
| `D` | External dependency (T2) |
| `E` | Domain-model entity (T5) |

Definitions live in the **first cell of a table row** (`| **C1** | ... |`) or, for Golden
Path steps, in the step heading (`**GP1 — ...**`). An ID written anywhere else is a
*reference*, not a definition.

## The 5 conventions

1. **Stable column headers per table** — the headers are the schema; don't rename them.
2. **ID-based cross-references** — every reference (T1 "Depends on", T1 `Subsystem`, the
   Subsystems `Parent`, edge endpoints, GP `Touches:`, traceability tables, "Used in GP")
   resolves to a defined ID, not a bare display name. Display text may accompany the ID
   (`C8 Upstream connectivity`) but the ID must be present.
3. **No raw `|` inside table cells** — escape or avoid it; it silently breaks table parsing.
4. **Golden Path micro-format** — each step is an `**GPn — title**` heading followed by
   labeled lines: STORY, UNDER THE HOOD, and a `Touches:` line listing the IDs it touches.
5. **A validator** — checks ID uniqueness, that every reference resolves, and that every GP
   step has a `Touches:` line. Run it after each generate/patch.

## Derived, not duplicated

- **Diagram edges come from the verbed component edge list** (`From | Verb | To | Why | Where`,
  IDs in From/To). T1's "Depends on" is a coarse *derived* summary of that edge list — the
  edge list is the source of truth for arrows, their verbs, and **why each dependency exists**.
- The edge **`Why`** is the **canonical relationship rationale** — distinct from a node's Purpose
  (about the node) and from the Golden Path (the sequenced story). Narrative layers reference
  edges instead of re-explaining them, so the `Why` lives in exactly one place.
- The Golden Path `Touches:` lines and the traceability table are two views of the same
  `GP-step — touches → element` edges.

### Grouping is single-source (optional, additive)

Components may be grouped into **subsystems** (prefix `S`) — the C4 "Container" altitude — defined
in their own table (`ID | Subsystem | Purpose | Parent | Anchor | Conf.`), optionally nested.

- **Membership lives on the child, once.** A component's `Subsystem` cell and a subsystem's
  `Parent` cell each hold **one** `S` ID (or empty = top-level). No table stores a member/child
  list — the member view is *derived*.
- **Inter-subsystem edges are derived** from the component edge list + membership: `S_a → S_b`
  exists iff a component edge crosses from `S_a` to `S_b`. Never authored.
- **Grouped "Depends on" / grouped touches are derived** the same way; `S` is *not* written into
  `Touches:` lines.
- Grouping is **optional and additive**: a map with no Subsystems table and no `Subsystem` column
  is fully valid (its components are simply ungrouped).

## The validator

[`scripts/validate_analysis.py`](../scripts/validate_analysis.py) is stdlib-only:

```
python3 scripts/validate_analysis.py .coyodex/project-map.md
```

It prints an element inventory and exits non-zero on: duplicate definitions, references to
undefined IDs, a Golden Path step missing its `Touches:` line, a Roles table missing the required
`Kind` column, or — when grouping is present — a `Subsystem`/`Parent` that doesn't resolve to a
defined `S`, an element with more than one parent, a nesting cycle, or a membership chain more than
`MAX_DEPTH` subsystem levels deep (default 3). It does **not** yet check table-cell pipe escaping,
anchor existence, or that edge tables carry the `Why` column — those are candidate additions.

## Source-link pinning

Each element carries a `file:line` (or `file#Lnnn`) anchor. Symbols drift by line, so when
generating clickable diagram links, **pin to the analysis commit SHA** (e.g. a GitHub blob
URL at that SHA) rather than a bare line that a later edit invalidates.
