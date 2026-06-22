# The coyodex method

How an AI coding agent builds and maintains a top-down, drillable map of a codebase.
Deliver this fixed set of tables. Every row is drillable: name a row and it expands
to a lower table or jumps to code with clickable `file:line` links.

Two linked families:
- **Behavioral** (why/who/what): Goal → Glossary → Roles → Use cases → Golden Path → Journeys.
- **Structural** (the machine): Components → Entry points / Model / Deps → Flows + Edges.

They join at **use case ↔ flow**.

See also: [schema v1](method/schema-v1.md) · [change-impact](method/change-impact.md) · [diagrams](method/diagrams.md).

---

## Behavioral layer — lead with this (what & why, before any code)

- **T0 Goal** — one short paragraph (not a table): the problem the project solves and
  for whom. The anchor.
- **Glossary** (default deliverable): `Term | Meaning | Defined/used in`. The ubiquitous
  language, produced up front and used to name things consistently across all tables
  (prevents the name-drift parallel mode otherwise risks).
- **Roles (actors)**: `Role | Kind | What they want | Use cases they drive`. List ONLY the
  **primary actors** — the parties who *initiate* a use case and drive the system. Do **not** list
  external systems the project itself calls out to (IdPs, sandboxes, upstream services, third-party
  APIs): they are not actors here. They belong in **T2 external dependencies** + the edge list, and
  the context diagram draws them as *outbound* arrows (the system uses them), never inbound. **Kind**
  (required, every role states one) = `human` or `service`, where `service` is a non-human *driver*
  that initiates use cases (a service account, headless agent / bot, scheduled job) — NOT a system
  the project depends on. This lets the context diagram draw people and machine-driven clients
  differently. When the docs don't say, infer from naming and mark it inferred.
- **Use cases**: `Use case | Actor | Trigger | Outcome`.

### Golden Path Narrative (default deliverable — the best top-level view)

One end-to-end happy-path story that traverses **all** main functionality and involves
**all** relevant actors; edge cases excluded. Placed right after Roles/Use cases as the
spine the structural tables hang off. (Built after harvest + at least one full trace;
presented near the top.)

- Use **concrete instantiated names**, not abstract roles: a Cast defined once and
  reused (e.g. "Adam — Acme's admin", "Andy — an end user", "Acme Corp — the customer
  org", plus the third parties). Concrete instances = better anchors.
- **Two registers per step**: (1) STORY — actor action → system response → what the
  actor sees, in narrative prose; (2) UNDER THE HOOD — domain model classes involved,
  how they're queried/stored (which repository, which collection/table), and any
  third-party calls. A view over Journeys + edge list + T5 + T2, stitched into one
  instantiated story; reuses the Glossary for naming.
- **Coverage rule**: pick the path hitting all main functionality + all actors; if one
  linear story can't reach everything, NOTE the features left off rather than forcing them in.
- **Honesty**: mechanics (classes/queries/third-party calls) are traced and verifiable;
  persona names + example values are ILLUSTRATIVE — mark them so they're never mistaken
  for real data.

### Bidirectional traceability (Golden Path ↔ entities) — standard

Connect each Golden Path step to the T1/T2/T5 elements it touches, **and** the converse,
so the reader can drill down (step → elements) and step back (element → steps). ONE
source, both views derived — don't store links twice (they drift). The source is a verb
on the edge list: `GP-step — touches → element`.

Deliver as:
1. a Golden Path ↔ entity traceability table right after the narrative
   (`Step | T1 components | T2 deps | T5 entities` — an edge list, NOT a full grid);
2. forward view = inline `Touches:` line per GP step;
3. backward view = a `Used in GP` column added to T1/T2/T5.

Give every GP step (`GP1`…) and every T1/T2/T5 row a stable ID/anchor so both link
directions are clickable. Each touch inherits its flow's confidence.

### Journeys — the drill-down of a use case (outside view)

`Step | User does | System responds | User sees (feedback) | Code behind (entity + file:line)`.
The "Code behind" column is the bridge into the structural tables. One use case has two
faces: outside = journey, inside = T6 flow + edges.

---

## Structural layer

### Level 0 (one screen, whole project)
- **Subsystems (S)** *(optional; recommended above ~15 components)*: `ID | Subsystem | Purpose |
  Parent | Anchor | Conf.` — the Container altitude: components grouped into subsystems, optionally
  nested. Membership is carried on the child (a `Subsystem` column on T1); the member list and the
  inter-subsystem edges are *derived*, never authored. Present this first on large maps; drill into T1.
- **T1 Components**: `Component | Subsystem | Purpose | Entry point | Depends on` (the `Subsystem`
  cell is the component's one parent `S`, or empty = ungrouped).
- **T2 External dependencies**: `Name | Type | Used for | Where configured`.
- **T3 How to run/build/test**: `Action | Command | Source`.

### Level 1 (one Level-0 row expanded)
- **T4 Entry points**: `Kind | Trigger | Code entity | Component`.
- **T5 Domain model**: `Entity | Meaning | Defined in | Stored where`.
- **T6 Use-case flows**: `Flow | steps | Uses (element + role) | Key files`.

### Operational dimensions — standard core four
- **Deployment & topology**: `Unit | Runs on | Exposed as | Config source`.
- **Observability**: `Signal | Where emitted | Where viewed | Alerts`.
- **Security & auth**: `Surface | Who can reach | Auth check | Risk note` (trust
  boundaries often inferred — flag).
- **Config & environments**: `Key | Purpose | Default | Per-env / secret?` (secrets =
  where they live, never values).
- On-demand extras: state machines/lifecycles, event/message catalog, error/failure
  modes, change hotspots (git churn), permissions matrix (Role × use case).

### Test completeness — measure against the MAP, not line %
Coverage % tells which lines ran, not which behaviors are tested. Start from the
inventory (use cases/journeys, T4 entry points, failure modes, invariants, state
transitions, critical-path branches) and ask "is there a test that exercises it?" —
gaps are the deliverable.
- Map tests → targets as `test — covers → element`; gap = element with no incoming
  "covers" edge.
- Run the suite with a coverage tool for real line+branch data — running beats reading.
- Cross them: coverage says which lines ran, the map says which matter; flag critical
  targets (money/auth/data-loss/irreversible) with low branch coverage first.
- Output: a risk-ranked gap table — `Target | Tested? | Test(s) | Gap/risk | Confidence`
  — NOT a single percentage. Lead with untested critical paths.
- Completeness ≠ test quality (a test can cover a line and assert nothing). Gold
  standard = mutation testing — expensive, offer as an opt-in deep cut on critical paths.
- Confidence ladder: reading tests = inferred; running with coverage = verified;
  surviving mutation = strongest.

### Level 2 (on demand, reached by drilling)
T7 Component internals · T8 Config/env vars · T9 Data schema.

### Relationships (always included)
- Backbone = a project-wide edge list: `From | Verb | To | Why | Where`. Uniform
  `source — verb — target` so the reader drills from either end. Verb vocabulary:
  uses, calls, reads, writes, emits, listens-to, routes-to, enforces, persists, encrypts,
  extends, implements.
- **`Why` = a short phrase: why `From` needs `To`** (e.g. "verify service tokens", "cache
  refreshed OAuth tokens"). The edge list is the **canonical home for relationship rationale** —
  the verb gives the category, `Why` gives the purpose the verb can't carry (especially the
  catch-all `uses`). Prefer a sharper verb first; let `Why` say what the verb omits. Keep it a
  terse phrase, not a sentence, so it stays cheap to re-verify. The Golden Path / T6 flows
  **reference** edges rather than restating their `Why` — one source, derived views.
- Convenience = inline "Uses" column on T6 (the most-used slice of the edge list).

---

## Cross-cutting rules

**Confidence by layer.** Structure (components, entry points, data) reads reliably from
source — mostly **verified**. Goal/Roles/intent often are NOT in the code (they live in
README/docs/the maintainer's head) — infer from naming/structure, mark **inferred**, and
ask rather than assert a confidently-wrong purpose. Journeys are in between: steps can be
traced, but the "user sees" register sometimes needs the running app, not just code.

**Build order (internal) ≠ present order.** Build bottom-up so each table's inputs exist
first: T3 → harvest T4, T2, T5 (a full sweep — also the completeness checklist that
catches side doors) → synthesize T1 → **cluster components into Subsystems** (large maps: by
directory first, then dependency/behavioral cohesion; minimize inter-group edges; mark
directory-derived = verified, cohesion-derived = inferred) → trace T6 + edge list. Nodes (T4/T5/T2)
before the edges/flows that connect them. **Present** top-down (T1–T3 first). The "Depends on"
columns and relationship rows harden last (they need tracing) — keep them inferred until
traced. Drilling can correct an inferred upper row; upper tables get more accurate as the
reader drills.

**Parallel mode (large repos only — serial is simpler and just as accurate on small
ones).** The build order maps to a fan-out workflow: **parallel harvest → barrier
synthesis → parallel trace.**
- Phase 1 Harvest (fan out, one agent each): T4 entry points, T2 deps, T5 model, T3
  run/build, T0/Roles reader. Parallel harvest also improves completeness.
- Phase 2 Synthesize (barrier, one agent): T1 clusters/dedups all harvest outputs, and (large
  maps) assigns Subsystems — a global graph cut, so it stays at the non-delegated barrier.
- Phase 3 Trace (fan out, one agent per use case/journey; large maps may instead fan out one agent
  per subsystem — bounded context — then a non-delegated reconcile traces the cross-subsystem seams).
- Guardrails: all agents share the same schema + edge-verb vocabulary; Phase 1 produces
  the canonical node inventory FIRST (nodes before edges, agents reference nodes and
  never invent them); every agent keeps inferred-vs-verified labels + returns `file:line`;
  agents return rows (structured output), not file dumps. The final reconcile (dedup
  names, verify cross-agent edges against code) is not delegated.

**Output file.** Write the full analysis to `.coyodex/project-map.md` at the root of
the analyzed repo, conform to [schema v1](method/schema-v1.md), and record in it the commit
it was built at (the baseline pin). At the end, report the file's full absolute path. Run
[`scripts/validate_analysis.py`](scripts/validate_analysis.py) after each generate/patch and
fix the map until it passes.

**Maintaining the map.** When code changes after a baseline exists, follow
[change-impact](method/change-impact.md): report the impact against the map (modified /
added / deleted), then accept: patch the map, bump the baseline pin, save the annotated diff
under `.coyodex/analysis-changes/<date>.md`, and commit the map with the code.

**How to apply.** Lead with the behavioral layer (T0 Goal → Glossary → Roles → Use cases →
Golden Path), then structural Level 0 (T1–T3); generate the rest on demand as the reader
drills. Always attach `file:line`. Label every entry point and every relationship as
verified vs inferred — that is where wrong guesses hide.
