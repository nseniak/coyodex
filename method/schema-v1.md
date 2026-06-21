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
| `D` | External dependency (T2) |
| `E` | Domain-model entity (T5) |

Definitions live in the **first cell of a table row** (`| **C1** | ... |`) or, for Golden
Path steps, in the step heading (`**GP1 — ...**`). An ID written anywhere else is a
*reference*, not a definition.

## The 5 conventions

1. **Stable column headers per table** — the headers are the schema; don't rename them.
2. **ID-based cross-references** — every reference (T1 "Depends on", edge endpoints, GP
   `Touches:`, traceability tables, "Used in GP") resolves to a defined ID, not a bare
   display name. Display text may accompany the ID (`C8 Upstream connectivity`) but the ID
   must be present.
3. **No raw `|` inside table cells** — escape or avoid it; it silently breaks table parsing.
4. **Golden Path micro-format** — each step is an `**GPn — title**` heading followed by
   labeled lines: STORY, UNDER THE HOOD, and a `Touches:` line listing the IDs it touches.
5. **A validator** — checks ID uniqueness, that every reference resolves, and that every GP
   step has a `Touches:` line. Run it after each generate/patch.

## Derived, not duplicated

- **Diagram edges come from the verbed component edge list** (`From | Verb | To | Where`,
  IDs in From/To). T1's "Depends on" is a coarse *derived* summary of that edge list — the
  edge list is the source of truth for arrows and their verbs.
- The Golden Path `Touches:` lines and the traceability table are two views of the same
  `GP-step — touches → element` edges.

## The validator

[`scripts/validate_analysis.py`](../scripts/validate_analysis.py) is stdlib-only:

```
python3 scripts/validate_analysis.py .coyodex/project-map.md
```

It prints an element inventory and exits non-zero on: duplicate definitions, references to
undefined IDs, or a Golden Path step missing its `Touches:` line. It does **not** yet check
table-cell pipe escaping or anchor existence — those are candidate additions.

## Source-link pinning

Each element carries a `file:line` (or `file#Lnnn`) anchor. Symbols drift by line, so when
generating clickable diagram links, **pin to the analysis commit SHA** (e.g. a GitHub blob
URL at that SHA) rather than a bare line that a later edit invalidates.
