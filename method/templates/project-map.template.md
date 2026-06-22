# <Project> — Codebase Analysis

> Built with the **coyodex** method. Behavioral layer first (Goal → Glossary → Roles →
> Use cases → Golden Path), then the structural machine (Components → Entry points /
> Model / Deps → Flows + Edges), joined at **use case ↔ flow**.
> Every row is drillable: name a row and it expands to a lower table or a `file:line`.
> **Schema v1** (ID-based): every element has a stable ID (`UC`/`C`/`D`/`E`/`GP`);
> cross-references use IDs; validated by `scripts/validate_analysis.py`.
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
| **<Role>** | human | <goal> | UC1, UC2 |

---

## Use cases

| ID | Use case | Actor | Trigger → Outcome |
|---|---|---|---|
| **UC1** | <use case> | <actor> | <trigger → outcome> |

---

## Golden Path Narrative — the spine

One happy-path story across all main functionality and every actor. STORY = what the actor
does/sees. UNDER THE HOOD = traced mechanics. Cast and example values are ILLUSTRATIVE; the
mechanics are traced. Each step ends with a `Touches:` line.

**Cast** (illustrative): <Name — role> · …

**GP1 — <title>** *(UC1)*
STORY: <…>
UNDER THE HOOD: <… [file](path#L1) …>
`Touches:` C1, C2 · D1 · E1, E2

### Golden Path ↔ entity traceability

| Step | T1 components | T2 deps | T5 entities |
|---|---|---|---|
| GP1 <title> | C1, C2 | D1 | E1, E2 |

---

## T1 — Components

| ID | Component | Purpose | Entry point | Depends on |
|---|---|---|---|---|
| **C1** | <component> | <purpose> | [file](path#L1) | C2, C3 |

### T1 backbone — component dependency edges (the diagram source)

| From | Verb | To | Why | Where |
|---|---|---|---|---|
| C1 | uses | C2 | <why C1 needs C2 — terse> | [file](path#L1) |

---

## T2 — External dependencies

| ID | Name | Type | Used for | Where configured | Conf. |
|---|---|---|---|---|---|
| **D1** | <dep> | <type> | <used for> | <config> | verified |

---

## T3 — How to run / build / test

| Action | Command | Source |
|---|---|---|
| <action> | `<command>` | [file](path) |

---

## T5 — Domain model

| ID | Entity | Meaning | Defined in | Stored where |
|---|---|---|---|---|
| **E1** | <Entity> | <meaning> | [file](path#L1) | <store> |

---

## Relationships — backbone edge list

| From | Verb | To | Why | Where |
|---|---|---|---|---|
| <source> | <verb> | <target> | <why source needs target — terse> | [file](path#L1) |

---

*Generated with coyodex. Run `python3 scripts/validate_analysis.py .coyodex/project-map.md`
after each edit.*
