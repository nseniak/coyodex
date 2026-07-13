# <Project> — Codebase Analysis

> Built with the **coyodex** method. Behavioral layer first (Goal → Glossary → Roles →
> Use cases → Happy Path), then the structural machine (Components → Entry points /
> Model / Deps → Flows + Edges), joined at **use case ↔ flow**.
> Every row is drillable: name a row and it expands to a lower table or a `file:line`.
> **Schema v1** (ID-based): every element has a stable ID (`UC`/`C`/`D`/`E`/`HP`);
> cross-references use IDs; validated by `coyodex validate`.
> Confidence: **verified** (read/traced) vs **inferred** (naming/convention).
> **Commit:** `<sha>` · **Committed:** `<commit-date>` · **Built:** `<YYYY-MM-DD HH:MM>`

---

## T0 — Goal (the anchor)

<One short paragraph: the problem the project solves and for whom.>

---

## Glossary — the ubiquitous language

| Term | Meaning | Defined / used in |
|---|---|---|
| **<Term>** | <meaning> | [file](path:1) |

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
| **UC2** | <use case> | <actor> | <trigger → outcome> |
| **UC3** | <use case> | <actor> | <trigger → outcome> |

---

## Happy Path — the spine (an ordered walk through the use cases)

The happy-path ORDERING of use cases across all main functionality and every actor. Each step IS a
use case — its `*(UCn)*` tag is required; `HPn` is just its position in the walk. The step carries no
STORY / mechanics / Touches: those live once in the use case's T6 flow below, and drilling a step
opens it. An optional `why:` line records the prerequisite that fixes this step's position. The
driving actor is the use case's own Actor (no separate `Actor:` line). Refer to actors by their
Roles-table names, never invented nicknames.

**HP1 — <title>** *(UC1)*
**HP2 — <title>** *(UC2)*
why: needs the result of HP1
**HP3 — <title>** *(UC3)*

<!-- The use-case↔element traceability and the backward "Used in UC" view are DERIVED from the T6
     flows below (the flow steps name the elements) — not authored here. -->

---

## Subsystems (S) — the container altitude

<!-- Optional; recommended above ~15 components. Components grouped into subsystems, optionally
     NESTED — a subsystem's `Parent` is another `S` (S3/S4 below nest under S2). The viewer drills
     nested levels recursively, so a big area goes finer IN THIS MAP — never a second map file. Go
     deeper by nesting, or by promoting a leaf component into a subsystem (see method.md "Drilling
     deeper"). Membership is carried on each child (T1 `Subsystem` column / this `Parent` cell);
     members + inter-subsystem edges are derived. Omit this whole section on small maps — ungrouped
     are valid.
     To SUBDIVIDE one subsystem into several sub-parts (S2 → S3, S4 below), mint a NEW NUMERIC id for
     each part and set its `Parent` to the big one. NEVER an outline suffix like `S2a` / `S2b`: a
     letter-suffixed id is not a valid schema id (IDs are a prefix + digits only), so it matches
     nothing — its definition and every membership pointing at it are SILENTLY dropped, leaving an
     empty box. Numeric-id + `Parent` also lets you re-parent with a one-cell edit, no rename. -->

| ID | Subsystem | Purpose | Parent | Source | Conf. |
|---|---|---|---|---|---|
| **S1** | <subsystem> | <one-line purpose> |  | path/ | inferred |
| **S2** | <large subsystem, subdivided below> | <one-line purpose> |  | path2/ | inferred |
| **S3** | <sub-part of S2> | <one-line purpose> | S2 | path2/a/ | inferred |
| **S4** | <another sub-part of S2> | <one-line purpose> | S2 | path2/b/ | inferred |

---

## T1 — Components

| ID | Component | Subsystem | Purpose | Entry point | Depends on |
|---|---|---|---|---|---|
| **C1** | <component> | S1 | <purpose> | [file](path:1) | C2 |
| **C2** | <component> | S1 | <purpose> | [file](path:1) |  |
| **C3** | <component in S2's sub-part S3> | S3 | <purpose> | [file](path2/a:1) |  |
| **C4** | <component in S2's sub-part S4> | S4 | <purpose> | [file](path2/b:1) |  |

### T1 backbone — component dependency edges (the diagram source)

<!-- `Why` = why From needs To (terse; carries what the verb omits). `Where` = the CALL SITE: the
     `file:line` in FROM's code where it invokes To (the main one if several), NOT To's definition —
     it's the line a flow arrow opens. -->

| From | Verb | To | Why | Where |
|---|---|---|---|---|
| C1 | uses | C2 | <why C1 needs C2 — terse> | [file](path:1) |

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

<!-- Every way the system is entered, in TWO passes — do BOTH:
     (1) externally triggered — HTTP route, CLI, exported fn, callback, webhook (someone outside asks);
     (2) SELF-STARTING (activation=self, no user) — cron/scheduled job, while-True/interval loop,
         asyncio.create_task / background worker / thread, queue or stream consumer (.consume/.subscribe/
         poll), boot/startup hook (on_event('startup'), lifespan, atexit), OS signal handler.
     Do pass (2) EXPLICITLY: a long-running service with zero self-starting entry points is a red flag —
     assert why none exist rather than leaving the list front-doors-only. Set `activation` on each row
     (self|external); if you leave it blank the viewer infers it from `kind`, so use a kind label like
     "Background loop" / "Boot task" / "Signal" that reads as self-starting. -->

| Kind | Trigger | Code entity | Component | Activation |
|---|---|---|---|---|
| <kind> | <trigger> | [entity](path:1) | C1 | self / external |

---

## Subdomains (SD) — bounded contexts of the domain model

<!-- Optional; recommended above ~15 entities. T5 entities grouped into subdomains (bounded contexts /
     aggregates), optionally nested. Membership is carried on each card (a `SUBDOMAIN:` line); members,
     the inter-subdomain (SD→SD) arrows, and the subsystem→subdomain (S→SD) bridge are all DERIVED. Omit
     this whole section on small models — ungrouped entities are valid. Cluster entities the same way
     components cluster into Subsystems: directory (the card's SOURCE) first, then relation cohesion. -->

| ID | Subdomain | Purpose | Parent | Source | Conf. |
|---|---|---|---|---|---|
| **SD1** | <subdomain> | <one-line purpose> |  | path/ | inferred |
| **SD2** | <nested subdomain> | <one-line purpose> | SD1 | path/sub/ | inferred |

---

## T5 — Domain model (domain cards)

<!-- Each entity is a CARD (a block), not a table row — same micro-format as the Happy Path. The
     heading defines the E id; FIELDS = attributes, RELATIONS = typed E→E edges (authored on the
     source side only, never in the backbone edge list). Renders as a Mermaid classDiagram.
     An optional `SUBDOMAIN:` line assigns the entity to one subdomain (SD) — the domain-model analog of
     a component's `Subsystem` cell. Full spec: method/domain-cards.md. Separators are `·`, never raw `|`.
     Cardinality is always a PAIR `sc→dc` (both sides or neither) — each side `1` / `*` / `0..1` / `1..*`;
     the `has 1→0..1 E3` item below shows an optional side. A lone token (`contains 0..1 E2`) is invalid. -->

**E1 — <Entity>** *(<stored where>)*
SUBDOMAIN: SD1
MEANING: <one-line meaning>
FIELDS: <name>:<type> PK · <name>:<type> · <name>:<type>
RELATIONS: contains 1→* E2 <display> · has 1→0..1 E3 <display>
SOURCE: [file](path:1)

**E2 — <Entity>** *(<stored where>)*
SUBDOMAIN: SD1
MEANING: <one-line meaning>
FIELDS: <name>:<type> · <name>:<type>
SOURCE: [file](path:1)

**E3 — <Entity>** *(<stored where>)*
SUBDOMAIN: SD2
MEANING: <one-line meaning, lives in the nested subdomain SD2>
FIELDS: <name>:<type>
SOURCE: [file](path/sub:1)

---

## T6 — Use-case flows

<!-- The INSIDE view of each use case (its outside view is the use case's Trigger → Outcome). ONE BLOCK PER USE CASE:
     a `**UCn — title**` heading + numbered step lines. A step is `from → to`, where each endpoint is
     an element ID (C/D/E) or a Role name. When BOTH ends are elements it is a pure reference to the
     backbone edge — its Verb + Why render the step (sequence message AND readable line), so DON'T
     restate the why. An ACTOR step (`<Role> → C…`) carries a short authored phrase after `: ` (the
     backbone has no actor edges). Add flow-specific context after `· `. Renders as a Mermaid
     sequenceDiagram + a numbered narrative, and is the drill-down of the matching Happy Path step.
     Separators inside a line are `·`, never raw `|`.
     A step may go BACKWARD too: a `to` that is an earlier participant renders right-to-left. Record
     the meaningful returns — the response the actor sees, an error/fallback, a callback/event — as
     authored steps (step 5 below). Don't echo every call with a return. -->

**UC1 — <flow title>**
1. <Role> → C1 : <what the actor does>
2. C1 → C2
3. C2 → E1 · <optional note>
4. C2 → D1
5. C1 → <Role> : <the response the actor sees — a backward step, drawn right-to-left>

---

## Operational dimensions — the standard core four

### Deployment & topology

| Unit | Runs on | Exposed as | Config source |
|---|---|---|---|
| <unit> | <host/runtime> | <port/route> | [file](path) |

### Observability

| Signal | Where emitted | Where viewed | Alerts |
|---|---|---|---|
| <signal> | [file](path:1) | <dashboard/log> | <alert or —> |

### Security & auth

<!-- Trust boundaries are often inferred — flag them. -->

| Surface | Who can reach | Auth check | Risk note |
|---|---|---|---|
| <surface> | <caller> | [check](path:1) | <risk> |

### Config & environments

<!-- Secrets: name where they live, never the value. -->

| Key | Purpose | Default | Per-env / secret? |
|---|---|---|---|
| <KEY> | <purpose> | <default> | <env / secret> |

---

## Relationships — backbone edge list

| From | Verb | To | Why | Where |
|---|---|---|---|---|
| <source> | <verb> | <target> | <why source needs target — terse> | [file](path:1) |

---

## Test completeness — gaps against the map

> **Tests run for this table?** <yes, with coverage — rows verified / no, read-only — all rows inferred>

<!-- Measure against the MAP, not line %. Walk the inventory (use cases / T4 entry
     points / failure modes / invariants / state transitions / critical branches) and ask "is
     there a test that exercises it?". Lead with untested critical paths (money / auth / data-loss
     / irreversible). Run the suite with a coverage tool (running beats reading); confidence
     ladder: reading tests = inferred, running with coverage = verified, surviving mutation =
     strongest. Output the risk-ranked gap table, NOT a single percentage. -->

| Target | Tested? | Test(s) | Gap / risk | Confidence |
|---|---|---|---|---|
| <label> (<Element name>) | yes / partial / no | [dir/](backend/tests/unit/) — <what it covers> | <gap or risk> | inferred / verified |

<!-- In the JSON source a row is { "targets": ["UC1","C4"], "label", "tested", "tests": [ {file, why} ], "gap", "confidence" }:
     `targets` names element IDs explicitly (the viewer resolves them to names + locate-links, no prose parsing);
     each `tests[].file` is a bare anchor (a `path:line` or a `path/` test dir), rendered as a clickable code link. -->


---

*Generated with coyodex. This file documents the GENERATED markdown view's shape — the committed source is `.coyodex/project-map.json` (see method/model.md); do not fill this template by hand.*
