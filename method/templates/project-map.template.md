# <Project> — Codebase Analysis

> Built with the **coyodex** method. Behavioral layer first (Goal → Glossary → Roles →
> Use cases → Golden Path), then the structural machine (Components → Entry points /
> Model / Deps → Flows + Edges), joined at **use case ↔ flow**.
> Every row is drillable: name a row and it expands to a lower table or a `file:line`.
> **Schema v1** (ID-based): every element has a stable ID (`UC`/`C`/`D`/`E`/`GP`);
> cross-references use IDs; validated by `tools/validate_analysis.py`.
> Confidence: **verified** (read/traced) vs **inferred** (naming/convention).
> **Commit:** `<sha>` · **Built:** `<date>`

---

## T0 — Goal (the anchor)

<One short paragraph: the problem the project solves and for whom.>

---

## Glossary — the ubiquitous language

| Term | Meaning | Defined / used in |
|---|---|---|
| **<Term>** | <meaning> | [file](path#L1) |

---

## Roles (actors)

<!-- Primary actors only — the parties who INITIATE use cases. External systems the project calls
     out to (IdPs, sandboxes, upstream services, third-party APIs) go in T2, not here. -->

| Role | Kind | What they want | Use cases they drive |
|---|---|---|---|
| **<Role>** | human | <goal> | UC1 |

---

## Use cases

| ID | Use case | Actor | Trigger → Outcome |
|---|---|---|---|
| **UC1** | <use case> | <actor> | <trigger → outcome> |

---

## Golden Path Narrative — the spine

One happy-path story across all main functionality and every actor. STORY = what the actor
does/sees, referring to actors by their **role** (the Roles-table names), not invented persona
nicknames. UNDER THE HOOD = traced mechanics. Example values are ILLUSTRATIVE; the mechanics are
traced. Each step ends with a `Touches:` line. Optional `Actor:` line = the role that *drives* the
step (a Roles-table name) — set it when the step bundles use cases with different actors, so the
diagram draws the right lifeline; otherwise it defaults to the step's first use case's actor.

**GP1 — <title>** *(UC1)*
<!-- optional: the Roles-table name driving this step; omit to default to the first use case's actor -->
Actor: <Role>
STORY: <…>
UNDER THE HOOD: <… [file](path#L1) …>
`Touches:` C1, C2 · D1 · E1

### Golden Path ↔ entity traceability

| Step | T1 components | T2 deps | T5 entities |
|---|---|---|---|
| GP1 <title> | C1, C2 | D1 | E1 |

---

## Subsystems (S) — the container altitude

<!-- Optional; recommended above ~15 components. Components grouped into subsystems, optionally
     nested. Membership is carried on each component (T1 `Subsystem` column); members +
     inter-subsystem edges are derived. Omit this whole section on small maps — ungrouped
     components are valid. -->

| ID | Subsystem | Purpose | Parent | Anchor | Conf. |
|---|---|---|---|---|---|
| **S1** | <subsystem> | <one-line purpose> | <S-id or empty> | [dir/](path/) | inferred |

---

## T1 — Components

| ID | Component | Subsystem | Purpose | Entry point | Depends on |
|---|---|---|---|---|---|
| **C1** | <component> | S1 | <purpose> | [file](path#L1) | C2 |
| **C2** | <component> | S1 | <purpose> | [file](path#L1) |  |

### T1 backbone — component dependency edges (the diagram source)

| From | Verb | To | Why | Where |
|---|---|---|---|---|
| C1 | uses | C2 | <why C1 needs C2 — terse> | [file](path#L1) |

---

## T2 — External dependencies

<!-- `Kind` (optional) is a CLOSED vocabulary that drives the Context view: external SYSTEMS the
     project talks to across a boundary — datastore / messaging / service / platform — are drawn at
     Context by name; in-process code — framework / library — folds into one collapsed "Libraries"
     box. `Type` stays the free-text human label. When `Kind` is omitted it is inferred from `Type`. -->

| ID | Name | Kind | Type | Used for | Where configured | Conf. |
|---|---|---|---|---|---|---|
| **D1** | <dep> | datastore | <type> | <used for> | <config> | verified |

---

## T3 — How to run / build / test

| Action | Command | Source |
|---|---|---|
| <action> | `<command>` | [file](path) |

---

## T4 — Entry points

<!-- Every way the system is entered: HTTP route, CLI, cron, queue consumer, exported fn, boot. -->

| Kind | Trigger | Code entity | Component |
|---|---|---|---|
| <kind> | <trigger> | [entity](path#L1) | C1 |

---

## Contexts (CX) — bounded contexts of the domain model

<!-- Optional; recommended above ~15 entities. T5 entities grouped into contexts (bounded contexts /
     aggregates), optionally nested. Membership is carried on each card (a `CONTEXT:` line); members,
     the inter-context (CX→CX) arrows, and the subsystem→context (S→CX) bridge are all DERIVED. Omit
     this whole section on small models — ungrouped entities are valid. Cluster entities the same way
     components cluster into Subsystems: directory (the card's SOURCE) first, then relation cohesion. -->

| ID | Context | Purpose | Parent | Anchor | Conf. |
|---|---|---|---|---|---|
| **CX1** | <context> | <one-line purpose> | <CX-id or empty> | [dir/](path/) | inferred |

---

## T5 — Domain model (domain cards)

<!-- Each entity is a CARD (a block), not a table row — same micro-format as the Golden Path. The
     heading defines the E id; FIELDS = attributes, RELATIONS = typed E→E edges (authored on the
     source side only, never in the backbone edge list). Renders as a Mermaid classDiagram.
     An optional `CONTEXT:` line assigns the entity to one context (CX) — the domain-model analog of a
     component's `Subsystem` cell. Full spec: method/domain-cards.md. Separators are `·`, never raw `|`. -->

**E1 — <Entity>** *(<stored where>)*
CONTEXT: CX1
MEANING: <one-line meaning>
FIELDS: <name>:<type> PK · <name>:<type> · <name>:<type>
RELATIONS: contains 1→* E2 <display>
SOURCE: [file](path#L1)

**E2 — <Entity>** *(<stored where>)*
CONTEXT: CX1
MEANING: <one-line meaning>
FIELDS: <name>:<type> · <name>:<type>
SOURCE: [file](path#L1)

---

## T6 — Use-case flows

<!-- The inside view of a use case (its outside view is the Journey). `Uses` = the elements +
     role per step; it is the most-used slice of the backbone edge list (don't restate Why here). -->

| Flow | Steps | Uses (element + role) | Key files |
|---|---|---|---|
| UC1 <flow> | <step → step → step> | C1, D1, E1 | [file](path#L1) |

---

## Operational dimensions — the standard core four

### Deployment & topology

| Unit | Runs on | Exposed as | Config source |
|---|---|---|---|
| <unit> | <host/runtime> | <port/route> | [file](path) |

### Observability

| Signal | Where emitted | Where viewed | Alerts |
|---|---|---|---|
| <signal> | [file](path#L1) | <dashboard/log> | <alert or —> |

### Security & auth

<!-- Trust boundaries are often inferred — flag them. -->

| Surface | Who can reach | Auth check | Risk note |
|---|---|---|---|
| <surface> | <caller> | [check](path#L1) | <risk> |

### Config & environments

<!-- Secrets: name where they live, never the value. -->

| Key | Purpose | Default | Per-env / secret? |
|---|---|---|---|
| <KEY> | <purpose> | <default> | <env / secret> |

---

## Relationships — backbone edge list

| From | Verb | To | Why | Where |
|---|---|---|---|---|
| <source> | <verb> | <target> | <why source needs target — terse> | [file](path#L1) |

---

## Test completeness — gaps against the map

> **Tests run for this table?** <yes, with coverage — rows verified / no, read-only — all rows inferred>

<!-- Measure against the MAP, not line %. Walk the inventory (use cases / journeys / T4 entry
     points / failure modes / invariants / state transitions / critical branches) and ask "is
     there a test that exercises it?". Lead with untested critical paths (money / auth / data-loss
     / irreversible). Run the suite with a coverage tool (running beats reading); confidence
     ladder: reading tests = inferred, running with coverage = verified, surviving mutation =
     strongest. Output the risk-ranked gap table, NOT a single percentage. -->

| Target | Tested? | Test(s) | Gap / risk | Confidence |
|---|---|---|---|---|
| UC1 <target> | yes / partial / no | [test](path#L1) | <gap or risk> | inferred / verified |

---

*Generated with coyodex. Run `python3 tools/validate_analysis.py .coyodex/project-map.md`
after each edit.*
