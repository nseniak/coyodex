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
| `GP` | Golden Path step (a use-case occurrence — a position in the ordered walk) |
| `C` | Component (T1) |
| `S` | Subsystem — a group of components and/or nested subsystems (optional) |
| `D` | External dependency (T2) |
| `E` | Domain-model entity (T5) |
| `SD` | Domain subdomain — a group of T5 entities and/or nested subdomains (optional) |

Definitions live in the **first cell of a table row** (`| **C1** | ... |`) or, for the two
block formats, in a heading: Golden Path steps (`**GP1 — ...**`) and domain entities
(`**E1 — ...**`, the T5 domain cards). An ID written anywhere else is a *reference*, not a
definition — including a **T6 flow block** (`**UC7 — ...**`), which is keyed by an *already-defined*
use case (the canonical `UC` definition is its Use-cases table row), so the flow heading references
that use case rather than redefining it.

## The 5 conventions

1. **Stable column headers per table** — the headers are the schema; don't rename them.
2. **ID-based cross-references** — every reference (T1 "Depends on", T1 `Subsystem`, the
   Subsystems `Parent`, the card `SUBDOMAIN:` / Subdomains `Parent`, edge endpoints, a GP step's
   `*(UCn)*` use-case tag, **T6 flow step endpoints**) resolves to a defined ID, not a bare display
   name. Display text may accompany the ID (`C8 Upstream connectivity`) but the ID must be present.
   (A flow step endpoint may instead be a **Role name** — an actor step — which resolves against the
   Roles table, not the ID space; such a Role must NOT be named like an element ID (`C3`, `E1`, …), or
   it will read as that element.)
3. **No raw `|` inside table cells** — escape or avoid it; it silently breaks table parsing.
4. **Block micro-formats** — three tiers are blocks, not tables, each a heading + labeled/numbered
   lines: the **Golden Path** (`**GPn — title** *(UCn)*` + an optional `why:` line — the step *is* a
   use case, so it carries no STORY/UNDER-THE-HOOD/Touches; those live in the use case's flow); the
   **T6 flows** (`**UCn — title**` + numbered step lines `n. from → to [: phrase] [· note]`); and the
   **T5 domain cards** (`**En — Name**` + FIELDS, RELATIONS, MEANING, SOURCE — see
   [domain-cards.md](domain-cards.md)). The GP and card headings *define* their ID; a flow heading
   *references* a use case. Separators inside list lines are `·`, never raw `|`.
5. **A validator** — checks ID uniqueness, that every reference resolves, that every GP step names a
   use case (`*(UCn)*`) and every T6 flow step's endpoints resolve (to an ID or a Role), and that
   every table row carries its header's column count (catching malformed separators / dropped cells).
   Run it after each generate/patch.

## Derived, not duplicated

- **Diagram edges come from the verbed component edge list** (`From | Verb | To | Why | Where`,
  IDs in From/To). T1's "Depends on" is a coarse *derived* summary of that edge list — the
  edge list is the source of truth for arrows, their verbs, and **why each dependency exists**.
  `Where` is the **call site** — a `[file](path#Lnnn)` link to the line in `From`'s code where it
  invokes `To` (the primary one if several), so the flow arrow's drill-to-code lands on the action.
- The edge **`Why`** is the **canonical relationship rationale** — distinct from a node's Purpose
  (about the node) and from the Golden Path (the sequenced story). Narrative layers reference
  edges instead of re-explaining them, so the `Why` lives in exactly one place.
- A use case's **T6 flow steps** ARE its touches; the `Used in UC` backward view (element → the use
  cases whose flow steps through it) is **derived** from them by the tooling, never authored.
  Element↔element flow steps reuse the backbone edge (`Verb` + `Why`), so a relationship's rationale is
  never restated in the flow.

### Grouping is single-source (optional, additive)

Components may be grouped into **subsystems** (prefix `S`) — the C4 "Container" altitude — defined
in their own table (`ID | Subsystem | Purpose | Parent | Anchor | Conf.`), optionally nested.

- **Membership lives on the child, once.** A component's `Subsystem` cell and a subsystem's
  `Parent` cell each hold **one** `S` ID (or empty = top-level). No table stores a member/child
  list — the member view is *derived*.
- **Inter-subsystem edges are derived** from the component edge list + membership: `S_a → S_b`
  exists iff a component edge crosses from `S_a` to `S_b`. Never authored.
- **Grouped "Depends on" is derived** the same way; an `S` is *not* a flow-step or edge endpoint
  (those reference components/deps/entities, never a subsystem).
- **Nesting renders as recursive drill, to any depth.** A subsystem's card shows only its *immediate*
  children (sub-subsystems as drillable boxes, direct components inline); drilling a child box opens its
  own card. Depth is **not capped** — the validator only *warns* past `DEEP_NEST_WARN` (5). Deeper detail
  is added in place (nest, or promote a leaf component into a subsystem), **never** in a second map file.
- Grouping is **optional and additive**: a map with no Subsystems table and no `Subsystem` column
  is fully valid (its components are simply ungrouped).

### Domain grouping is the same machine, on the entity graph (optional, additive)

T5 entities may be grouped into **subdomains** (prefix `SD`) — bounded contexts / aggregates — defined
in their own table (`ID | Subdomain | Purpose | Parent | Anchor | Conf.`), optionally nested. This is the
*same* single-source/derived machinery as component subsystems, applied to the domain model:

- **Membership lives on the child, once** — but on the **card**, not a table cell: each domain card
  carries a `SUBDOMAIN:` line holding **one** `SD` ID (the analog of a component's `Subsystem` cell). A
  card with no `SUBDOMAIN:` line is ungrouped (top-level). The Subdomains table's own `Parent` cell nests
  one subdomain inside another — and the Entities view **drills these nested subdomains recursively**, each
  card showing one level, exactly like subsystems.
- **Cluster entities like components** — directory first (the card's `SOURCE` location), then relation
  cohesion (the `RELATIONS` graph); minimise crossing relations. Directory-derived = verified,
  cohesion-derived = inferred.
- **Three derived edge kinds, never authored**: `SD → SD` (a subdomain relates to a subdomain) is lifted
  from the E→E `RELATIONS`; `S → SD` — the **bridge** — is lifted from the `C→E` edges (`persists` /
  `writes` = the subsystem *owns* that subdomain's data, `reads` = it *consumes* it).
- **Optional and additive**: a map with no Subdomains table and no `SUBDOMAIN:` line is fully valid (its
  entities are simply ungrouped).

### Dependency Kind drives the Context view (optional, additive)

T2 deps may carry an optional `Kind` — a **closed vocabulary** that decides how the C4 Context view
treats each dep, so the highest altitude stays a clean C4 picture instead of a star of every imported
library:

- **External systems are drawn at Context by name**: `datastore` (DB / cache / object store / search),
  `messaging` (queue / broker / pub-sub / stream), `service` (third-party API / SaaS, incl. IdP/auth,
  payments, observability), `platform` (runtime / cloud / CDN / secrets).
- **In-process code folds into one "Libraries" box**: `framework` and `library`. The box is drillable
  to the full list — nothing is lost, it is just one click below the Context altitude.
- `Type` stays the **free-text** human label; `Kind` is the render-driving enum (same split as a Role's
  free-text name vs its closed `Kind`). When `Kind` is omitted it is **inferred from `Type`**, so a map
  with no `Kind` column is fully valid and still de-cluttered — the column only makes the call exact.

## The validator

The validator ([`tools/coyodex/validate_analysis.py`](../tools/coyodex/validate_analysis.py)) is stdlib-only:

```
.venv/bin/coyodex validate .coyodex/project-map.md
```

It prints an element inventory and exits non-zero on: duplicate definitions, references to
undefined IDs, a Golden Path step missing or with an unresolvable `*(UCn)*` use-case tag, a T6 flow
step whose endpoint resolves to neither a defined ID nor a Role, a Roles table missing the required
`Kind` column, a T2 dependency whose **optional** `Kind` cell is not one of the closed set
`datastore / messaging / service / platform / framework / library` (no-op when the column is absent),
a table row whose column count differs from its header (malformed separator,
dropped/extra cell, or an unescaped raw `|` — an escaped `\|` is fine), an edge row with an empty
`Verb` cell (which would render as `src -->|| dst` and desync the diagram), or — when grouping is
present — a `Subsystem`/`Parent`
that doesn't resolve to a defined `S`, an element with more than one parent, a nesting cycle, or a
membership chain more than `MAX_DEPTH` subsystem levels deep (default 3). The **domain-grouping**
checks mirror these when subdomains are present: a card `SUBDOMAIN:` / Subdomains `Parent` that doesn't
resolve to a defined `SD`, a wrong-kind parent (an entity/subdomain whose parent isn't a `SD`), a
subdomain-nesting cycle or over-deep chain, a loud guard when a Subdomains table is defined but no entity
is assigned, and a non-blocking warning listing ungrouped entities once some are grouped. When an
undefined ID is
actually a definition row that glued the name into the ID cell (`| **UC1** Search… |` or
`| **C8 Upstream** |`), the report names that specific cause. Content inside ```` ``` ```` code
fences is ignored by both the validator and the diagram parser, so verbatim examples (Mermaid,
shell, a sample table) never trip these checks. It does **not** yet check anchor existence or that
edge tables carry the `Why` column — those remain candidate additions. The **T5 domain-card**
checks (card-id uniqueness, `RELATIONS` targets resolve, single-side relations, field/cardinality
well-formedness) are specified in [domain-cards.md](domain-cards.md) and pending implementation.

## Source-link pinning

Each element carries a `file:line` (or `file#Lnnn`) anchor. Symbols drift by line, so when
generating clickable diagram links, **pin to the analysis commit SHA** (e.g. a GitHub blob
URL at that SHA) rather than a bare line that a later edit invalidates.
