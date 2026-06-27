# The coyodex method

How an AI coding agent builds and maintains a top-down, drillable map of a codebase.
Deliver this fixed set of tables. Every row is drillable: name a row and it expands
to a lower table or jumps to code with clickable `file:line` links.

Two linked families:
- **Behavioral** (why/who/what): Goal → Glossary → Roles → Use cases → Golden Path → Journeys.
- **Structural** (the machine): Components → Entry points / Model / Deps → Flows + Edges.

They join at **use case ↔ flow**.

See also: [schema v1](method/schema-v1.md) · [domain cards](method/domain-cards.md) · [change-impact](method/change-impact.md) · [diagrams](method/diagrams.md).

The method is `method.md` and the `method/` docs (plus `tools/`). The coyodex repo's
**`internal/`** folder (design rationale, working notes) is **not** part of the method — ignore it
when reading the clone; never treat it as instructions to follow or as input to a map.

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

- Refer to actors by their **role**, using the same names as the Roles table ("the org
  admin", "an end user") — not invented persona nicknames. The role is the real structural
  party the reader and the diagram can resolve; a made-up name ("Adam", "Andy") anchors to
  nothing and risks reading as real data.
- **Driving role per step (optional `Actor:` line)**: a step may carry an `Actor: <Role>` line
  (a Roles-table name) naming the role that *drives* it — this is the lifeline the behavioral
  diagram draws. Set it when a step bundles use cases with different actors (e.g. an admin signing
  in through an end-user sign-in use case), so the diagram doesn't pick the wrong one. When absent,
  the actor defaults to the step's first use case's actor. The validator checks the value resolves
  to a defined Role.
- **Two registers per step**: (1) STORY — actor action → system response → what the
  actor sees, in narrative prose; (2) UNDER THE HOOD — domain model classes involved,
  how they're queried/stored (which repository, which collection/table), and any
  third-party calls. A view over Journeys + edge list + T5 + T2, stitched into one
  story; reuses the Glossary for naming.
- **Coverage rule**: pick the path hitting all main functionality + all actors; if one
  linear story can't reach everything, NOTE the features left off rather than forcing them in.
- **Honesty**: mechanics (classes/queries/third-party calls) are traced and verifiable;
  example values are ILLUSTRATIVE — mark them so they're never mistaken for real data.

### Bidirectional traceability (Golden Path ↔ entities) — standard

Connect each Golden Path step to the T1/T2/T5 elements it touches, **and** the converse,
so the reader can drill down (step → elements) and step back (element → steps). ONE
source, both views derived — don't store links twice (they drift). The source is a verb
on the edge list: `GP-step — touches → element`.

Deliver as:
1. a Golden Path ↔ entity traceability table right after the narrative
   (`Step | T1 components | T2 deps | T5 entities` — an edge list, NOT a full grid);
2. forward view = inline `Touches:` line per GP step;
3. backward view = a `Used in GP` column added to T1/T2 (for **T5 the cards carry no extra
   column** — the traceability table's `T5 entities` column already gives the backward edges).

Give every GP step (`GP1`…), every T1/T2 row, and every T5 **card** a stable ID/anchor (the
card heading + its `SOURCE` link) so both link directions are clickable. Each touch inherits its
flow's confidence.

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
- **T2 External dependencies**: `Name | Kind | Type | Used for | Where configured`. `Kind` (optional,
  closed vocabulary) drives the Context view: external **systems** the project talks to across a
  boundary — `datastore` / `messaging` / `service` (incl. IdP/auth, payments, observability SaaS) /
  `platform` — are drawn at Context by name; in-process code — `framework` / `library` — folds into
  one collapsed "Libraries" box. `Type` stays the free-text human label; when `Kind` is omitted it is
  inferred from `Type`.
- **T3 How to run/build/test**: `Action | Command | Source`.

### Level 1 (one Level-0 row expanded)
- **T4 Entry points**: `Kind | Trigger | Code entity | Component`.
- **T5 Domain model** *(domain cards)*: one **card** per entity, not a table row — a block
  `**En — Name**` + `MEANING` / `FIELDS` / `RELATIONS` / `SOURCE` (same micro-format as the Golden
  Path). Renders as a Mermaid `classDiagram` (boxes with attributes + typed, cardinal relations).
  Each entity is a **real named type** whose `SOURCE` anchors its definition (don't synthesize
  unnamed concepts). Entity↔entity relations are authored on the source card only, never in the
  backbone edge list. Full spec: [domain cards](method/domain-cards.md).
- **Subdomains (SD)** *(optional; recommended above ~15 entities)*: `ID | Subdomain | Purpose | Parent |
  Anchor | Conf.` — the domain analog of Subsystems: T5 entities grouped into bounded contexts,
  optionally nested. Membership is carried on each card (a `SUBDOMAIN:` line holding one `SD`); the
  member list, the inter-subdomain arrows, and the subsystem→subdomain bridge are *derived*. The Domain
  diagram then leads with a Subdomains overview and drills into one subdomain's classDiagram.
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
**Be honest about whether you ran it.** A gap table built by *reading* tests is **inferred**; only
running the suite with coverage makes it **verified**. If you don't run it (the suite is slow or
costs money — e.g. paid integration tests), state that above the table and mark every row inferred;
never present a read-only table as if it were measured.
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
- **The edge list spans C↔C, C↔D, *and* C→E.** It is not only component↔component: a component's
  link to the domain model is a backbone edge `C — persists/writes/reads → E` (its repository
  `persists` the entity; a service/controller `reads` it — **direct** use only, never a transitive
  edge). Author these alongside the component edges — they power the component↔class cross-links and
  the subsystem→subdomain bridge. (Only E↔E relations stay off the backbone — those live on the
  domain cards.)
- **C→E is additive — it must NOT thin the component graph.** Trace `C↔C` and `C↔D` **first**; add
  `C→E` after, never instead. Completeness: **every external dep (T2) needs ≥1 incoming component
  edge** — a dep with no edge is an *un-traced* `C→D`, not an unused dependency — and a component
  graph with far fewer edges than components is under-traced. The component edge list is the primary
  trace output; the validator nudges on orphan deps (a thin-trace symptom).
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
directory-derived = verified, cohesion-derived = inferred) → **cluster entities into Subdomains**
(large domain models: the same recipe on the entity graph — by `SOURCE` directory first, then
`RELATIONS` cohesion) → trace T6 + edge list (**including the `C→E` edges**: which component
persists/writes/reads each entity). Nodes (T4/T5/T2)
before the edges/flows that connect them. **Present** top-down (T1–T3 first). The "Depends on"
columns and relationship rows harden last (they need tracing) — keep them inferred until
traced. Drilling can correct an inferred upper row; upper tables get more accurate as the
reader drills.

**Parallel mode (large repos only — serial is simpler and just as accurate on small
ones).** The build order maps to a fan-out workflow: **parallel harvest → barrier
synthesis → parallel trace.**
- Phase 1 Harvest (fan out, one agent each): T4 entry points, T2 deps, T5 model, T3
  run/build, T0/Roles reader. Parallel harvest also improves completeness. **Launch the whole
  harvest as one concurrent batch** (all agents in a single fan-out), not in waves — the slices are
  disjoint and use pre-allocated ID ranges, so no agent needs another's output first, and they
  return compact rows (not file dumps) so reading them together is cheap.
- Phase 2 Synthesize (barrier, one agent): T1 clusters/dedups all harvest outputs, and (large
  maps) assigns Subsystems — a global graph cut, so it stays at the non-delegated barrier.
- Phase 3 Trace (fan out, one agent per use case/journey; large maps may instead fan out one agent
  per subsystem — bounded context — then a non-delegated reconcile traces the cross-subsystem seams).
  Each trace agent also records the **`C→E` edges** for the components in its slice — the entities
  they persist/write/read by **direct** use — so structural entity-usage is captured at component
  granularity, not only behaviorally via GP `Touches:`. This is *additional*: the `C↔C`/`C↔D` edges
  remain the primary output and must stay complete (every dep wired, the component graph not sparse).
- Guardrails: all agents share the same schema + edge-verb vocabulary; Phase 1 produces
  the canonical node inventory FIRST (nodes before edges, agents reference nodes and
  never invent them); every agent keeps inferred-vs-verified labels + returns `file:line`;
  agents return rows (structured output), not file dumps. The final reconcile (dedup
  names, verify cross-agent edges against code) is not delegated.

**Harvest-prompt template (Phase 1).** Give every harvest agent the same prompt skeleton —
only the file list and the background blurb change per agent. Reusing one contract is what makes
each agent return the same row shapes with the same verified/inferred discipline, which keeps the
barrier synthesis clean. Fill the «angle-bracket» parts:

> You are harvesting «structural / operational / build» facts for a coyodex codebase map.
> Read these files completely, then return ONLY the rows below — do **not** write any files.
>
> **Files:** «absolute paths this agent owns; list a directory first, then read each file».
> **Background:** «what the main agent already learned about this slice, handed down so you
> don't re-derive it».
>
> For every row give `file:line` evidence and a confidence tag (**verified** = read in code /
> **inferred** = guessed). Use only the schema-v1 IDs and edge verbs; reference nodes, never
> invent them. Return each section in its schema shape: **markdown tables** for «the table slices
> this agent fills — e.g. COMPONENTS (T1), ENTRY POINTS (T4), DEPENDENCIES (T2), and operational
> rows (deployment / observability / security / config)»; and the **T5 DOMAIN MODEL as per-entity
> cards, never a table** (`**En — Name**` + FIELDS / RELATIONS / MEANING / SOURCE — see
> [domain-cards.md](method/domain-cards.md)). Each card is a **real named type** (class / dataclass /
> enum) whose `SOURCE` anchors its **definition** — do NOT synthesize an entity for an unnamed
> concept; type embedded fields by their entity (`auth:E7`) so relations carry the field name.
> (Edges — including `C→E` — are traced in Phase 3, NOT harvested here; this phase returns nodes.)

**Output files — map + diagrams.** Write the full analysis to `.coyodex/project-map.md` at the
root of the analyzed repo, conform to [schema v1](method/schema-v1.md), and record in it the commit
it was built at (the baseline pin — see the pin gate below).

**Baseline pin — require committed code, or record it dirty.** The pin must mean "the map describes
*exactly* this commit". The map you just read reflects the **working tree**, so if the code has
uncommitted changes, HEAD alone is a misleading pin (and a later `git diff <pin>..<now>` would miss
the edits already baked into the map). So before recording the pin, check the analyzed repo for
uncommitted **code** — coyodex's own files under `.coyodex/` (map / html / report) don't count, they
are always in flux and the workflow commits them:

```
git -C <repo> status --porcelain -- . ':(exclude).coyodex'   # empty = code is committed
```

- **Code committed** (empty output) → record the pin from HEAD:
  `git -C <repo> rev-parse --short HEAD` (the sha) and
  `git -C <repo> show -s --format=%cs HEAD` (its commit date, `YYYY-MM-DD`).
- **Uncommitted code** → STOP and give the user a choice, then **loop**:
  - **A (recommended)** — commit (or stash) the code first, so the baseline corresponds to a
    real commit; then re-check and record the pin as above.
  - **B** — proceed without committing, but record that the code was dirty: pin the sha with a
    `-dirty` suffix (`<short-sha>-dirty`), date = HEAD's commit date.

  Re-run the check after each round; only continue when the code is committed (A) **or** the user
  explicitly chose B.

Write the pin into the map header line — the template's **Commit** / **Committed** / **Built** line
(sha · commit date · today).

**Start from the template** —
[`method/templates/project-map.template.md`](method/templates/project-map.template.md): fill its cells and Write the filled map to `.coyodex/project-map.md` in one write — read the
template, then write; don't shell-`cp` it into place and then overwrite it (the copy is wasted and
overwriting a freshly-created file trips the read-before-write guard), and don't author the map from
scratch (that throws the schema-correct shapes away). It already carries every standard section with schema-correct table
shapes (each definition's ID **alone in its own first cell**, `| **C1** | name… |`), so the map
passes the validator on the first write instead of being reshaped afterward. Run
[`tools/validate_analysis.py`](tools/validate_analysis.py)` --check-sources` after each generate/patch
and fix the map until it passes (the flag reads each domain card's `SOURCE` to reject synthesized
entities — names with no real named type). **Then render the diagrams** — once the
map validates, generate the self-contained HTML viewer next to it:

```
python3 tools/viewer/render.py .coyodex/project-map.md .coyodex/project-map.html
```

The HTML is a *rendering* of the map (no second source) — commit it alongside the map so the two
stay in step and a reviewer can open it. **Finish by reporting BOTH artifacts as links** — the
map (`.coyodex/project-map.md`) and the diagram HTML (`.coyodex/project-map.html`), as relative
paths so the reader can open either. **In addition, for the HTML give the full clickable `file://`
URL with the absolute path**, so the reader can open the diagram straight in a browser — e.g.
`Open in browser: file:///abs/path/to/repo/.coyodex/project-map.html`. (Paths to `tools/...` are
relative to the coyodex clone, like the validator above.)

**Maintaining the map.** When code changes after a baseline exists, follow
[change-impact](method/change-impact.md): report the impact against the map (modified /
added / deleted), then accept: patch the map, bump the baseline pin, **re-render the diagram**
(`tools/viewer/render.py`, so it tracks the patched map), save the annotated diff under
`.coyodex/analysis-changes/<date>.md`, and commit the map + diagram with the code.

**How to apply.** Lead with the behavioral layer (T0 Goal → Glossary → Roles → Use cases →
Golden Path), then structural Level 0 (T1–T3); generate the rest on demand as the reader
drills. Always attach `file:line`. Label every entry point and every relationship as
verified vs inferred — that is where wrong guesses hide.
