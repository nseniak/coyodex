# The coyodex method

How an AI coding agent builds and maintains a top-down, drillable map of a codebase.
Deliver this fixed set of sections, rendered as tables in the generated view. Every row is
drillable: name a row and it expands to a lower table or jumps to code with clickable
`file:line` links.

Two linked families:
- **Behavioral** (why/who/what): Goal → Glossary → Roles → Use cases → Golden Path.
- **Structural** (the machine): Components → Entry points / Model / Deps → Flows + Edges.

They join at **use case ↔ flow**.

See also: [dispatch](method/dispatch.md) · [the map model — schema v2](method/model.md) · [schema v1](method/schema-v1.md) · [domain cards](method/domain-cards.md) · [change-impact](method/change-impact.md) · [diagrams](method/diagrams.md).

**The stored map is a structured JSON model** (`.coyodex/project-map.json`, [schema v2](method/model.md));
the markdown map and the HTML diagram are **generated views** committed next to it. Build agents
return structured rows; `coyodex assemble` writes the model — nobody hand-authors the stored file.

The method is `method.md` and the `method/` docs (plus the `tools/coyodex/` package). The coyodex repo's
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
- **Use cases**: `Use case | Actor | Trigger | Outcome`. Rank by importance — the headline
  features and intended workflows in the project's docs are usually the primary use cases (see
  *Read the project's own docs* under Cross-cutting rules).

### Golden Path — the spine (an ordered walk through the use cases)

The Golden Path is one end-to-end happy-path **ordering of use cases** that traverses **all** main
functionality and involves **all** relevant actors; edge cases excluded. A use case on its own has
no fixed position — use cases relate by **preconditions**, a partial order / DAG ("an org must exist
before a user can join it"), and several orderings can satisfy it. The Golden Path is the **one
concrete walk** through that DAG that tells a coherent story. Placed right after Roles/Use cases as
the spine; built after harvest + at least one full trace.

- **Each step IS a use case.** A step is a `**GPn — <title>** *(UCn)*` heading whose `*(UCn)*` tag
  (**required**) names the use case it realizes; `GPn` is just its position in the walk. The step's
  *detail* — the sequence of actions and the components/deps/entities involved — is **not** written
  here; it lives once in that use case's **T6 flow** (below). Drilling a step opens its flow. A use
  case may appear at several positions (each a distinct `GPn`); the use case is still defined once.
- **Order = the chosen walk; an optional `why:` line records the prerequisite** ("needs the org from
  GP1"). That is the only narrative the Golden Path itself carries — the actions and mechanics belong
  to the use case's flow, not restated here.
- **Actor = the use case's actor.** Because a step is exactly one use case, its driving role is that
  use case's `Actor` — there is no separate `Actor:` line. A cross-actor handoff is simply the next
  step being a use case with a different actor.
- **Refer to actors by their role** (the Roles-table names: "the org admin", "an end user") — never
  invented persona nicknames, which anchor to nothing and can read as real data.
- **Coverage rule**: pick the walk hitting all main functionality + all actors; if one linear walk
  can't reach everything, NOTE the use cases left off rather than forcing them in — they still have
  their own T6 flow, just not a spine position.

### Bidirectional traceability (use case ↔ elements) — standard

Connect each use case to the T1/T2/T5 elements its **flow** touches, **and** the converse, so the
reader can drill down (use case → elements) and step back (element → use cases). ONE source — the
**T6 flow steps** — both views derived; don't store links twice (they drift). A flow step's
endpoints (a component, dep, or entity) ARE the touches, and element↔element steps reuse the
backbone edge (its `Verb` + `Why`), so no relationship is restated.

Deliver as:
1. forward view = the use case's **T6 flow**, whose ordered steps name the elements it touches;
2. backward view = **derived, not authored** — the tooling shows, on each element, the use cases
   whose flow steps through it (`Used in UC`); T5 entities included (no extra column on the cards).

Give every use case, every T1/T2 row, and every T5 **card** a stable ID/anchor (the card heading +
its `SOURCE` link) so both link directions are clickable. Each touch inherits its flow's confidence.

One use case has two faces: **outside** — what the actor does and sees, carried by the use case's
`Trigger → Outcome` cell — and **inside = T6 flow** (the ordered interactions among
components/deps/entities), drawn as a sequence diagram and read as a numbered narrative.
(A separate prose "Journey" table existed in earlier method versions; it duplicated the flows at
prose level, the model has no field for it, and builders rightly skipped it — dropped.)

---

## Structural layer

### Level 0 (one screen, whole project)
- **Subsystems (S)** *(optional; recommended above ~15 components)*: `ID | Subsystem | Purpose |
  Parent | Anchor | Conf.` — the Container altitude: components grouped into subsystems, optionally
  nested (a subsystem's `Parent` is another `S`). Membership is carried on the child (a `Subsystem`
  column on T1); the member list and the inter-subsystem edges are *derived*, never authored. Present
  this first on large maps; drill into T1. **Nesting renders as recursive drill**: each subsystem's card
  shows only its *immediate* children (sub-subsystems as drillable boxes), so a large area drills down
  level by level inside the one map — there is no depth limit (deep chains only warn).
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
  `**En — Name**` + `MEANING` / `FIELDS` / `RELATIONS` / `SOURCE` (a block with a defining heading,
  like the Golden Path and T6 flows). Renders as a Mermaid `classDiagram` (boxes with attributes + typed, cardinal relations).
  Each entity is a **real named type** whose `SOURCE` anchors its definition (don't synthesize
  unnamed concepts). Entity↔entity relations are authored on the source card only, never in the
  backbone edge list. Full spec: [domain cards](method/domain-cards.md).
- **Subdomains (SD)** *(optional; recommended above ~15 entities)*: `ID | Subdomain | Purpose | Parent |
  Anchor | Conf.` — the domain analog of Subsystems: T5 entities grouped into bounded contexts,
  optionally nested. Membership is carried on each card (a `SUBDOMAIN:` line holding one `SD`); the
  member list, the inter-subdomain arrows, and the subsystem→subdomain bridge are *derived*. The Domain
  diagram then leads with a Subdomains overview and drills into one subdomain's classDiagram.
- **T6 Use-case flows** *(the inside view of each use case — a block, not a table)*: one block per
  use case, `**UCn — <title>**` + **numbered step lines**. Each step is an ordered interaction
  `from → to`: when both ends are elements (C/D/E) it is a pure reference to the backbone edge, so the
  edge's `Verb` + `Why` render the step from **one source** (never restated); an **actor step**
  (`<Role> → C…`) carries a short authored phrase (the backbone has no actor edges); an optional
  `· <note>` adds flow-specific context. Renders as a Mermaid `sequenceDiagram` — the actor plus the
  touched components/deps/entities as lifelines, the steps as ordered messages — **and** as a numbered
  narrative below it. Drilling a Golden Path step opens its use case's flow here.
  - **Steps can go *backward*, not just forward.** A flow isn't only the request chain — record the
    return-direction interactions where they carry meaning: the **response the actor sees** (the use
    case's outcome), an **error / fallback** path, a **callback or event** the callee fires back. A step
    whose `to` is an earlier participant renders as a **right-to-left** arrow automatically (lifelines
    are placed in first-appearance order). These are **authored steps** (a return is not a backbone
    edge), so write them like an actor step — `C5 → C2 : returns the member list`, `System → Member :
    shows the org`. Don't echo *every* call with a return — only the ones that say something.

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
inventory (use cases, T4 entry points, failure modes, invariants, state
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
- **Verbs may PRIORITIZE, never GATE.** A verb is an authored word — no deterministic check verifies
  it against the code. So a verb may set *attention* (the audit ranks its L2 worklist by verb —
  security verbs like `enforces`/`encrypts` first) but must never decide *truth*: no gate may branch
  pass/fail on a verb, no claim may be dropped from grounding because its verb sounds benign, and a
  rendered fact derived from a verb is presented as **inferred**, never asserted. Two viewer facts are
  verb-derived and labelled `(inferred)` accordingly: the subsystem→subdomain bridge's **owns/reads**
  split (owns = `persists`/`writes`) and the class-diagram **inheritance** arrows (`isA`). If a
  derived fact matters, ground the underlying edge (L2), don't trust the verb.
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
- **`Where` = the call site: the `file:line` in `From`'s code where it invokes `To`** — not `To`'s
  definition. An edge `A — verb → B` is *evidenced* by the line in **A** where A uses B, so `Where`
  points there. This is also the line a flow arrow opens (the drill-to-code link), so it should land on
  the action. When the relationship fires at several sites, pick the **primary / most representative**
  one (the edge is an aggregate — one `Where` per edge). Format it as a clickable `[file](path#Lnnn)`
  link, pinned to the analysis commit (see [schema v1](method/schema-v1.md) source-link pinning).
- Convenience = inline "Uses" column on T6 (the most-used slice of the edge list).

---

## Cross-cutting rules

**Confidence by layer.** Structure (components, entry points, data) reads reliably from
source — mostly **verified**. Goal/Roles/intent often are NOT in the code (they live in
README/docs/the maintainer's head) — infer from naming/structure, mark **inferred**, and
ask rather than assert a confidently-wrong purpose. A use case's `Trigger → Outcome` sits in
between: the trigger traces from code, but the "user sees" register sometimes needs the running
app, not just code.

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

**Pre-index (structural input — run it after the behavioral draft, before the structural
harvest).** On a non-trivial repo, don't choose altitude from a *count* ("65 plugins, too many")
or from maintainer diagrams alone — that is how a heavy area silently collapses into one box.
First draft the behavioral layer (Goal → Glossary → Roles → Use cases → Golden-Path skeleton),
**then** run the pre-index and let it *size and locate* while you keep *naming and judging*:

```
.venv/bin/coyodex preindex --root <repo>       # writes .coyodex/preindex.json (ephemeral, gitignored)
```

It returns, for the whole tree: a **weight map** (LOC + file count + git churn per directory), a
**symbol index** (`class/func → file:line + kind`, with an `ambiguous` list when a name is defined
in several places), and — when you pass `--pairs` a `{component: [paths]}` map — a lower-bound
**import-edge advisory** between components you have *already named*. Use it like this:

- **Weight is a hint to where to look, never a decision.** A directory carrying a large share of
  the tree's mass *and* split into many sibling sub-units (e.g. `plugins/` with dozens of
  subdirs) is a **drill candidate** — promote it to a subsystem and map its units, don't fold it
  into one component. But a heavy *generated* dir still collapses, and a tiny *auth gate* still
  gets promoted — the number sets attention, your judgement sets altitude.
- **Reconcile every item; never paste it in.** The pre-index is input you accept / reject /
  abstract with a reason — it is not rows for the map. The behavioral layer and the subsystem
  names stay yours.
- **Treat what it could not parse as UNKNOWN, not empty.** Its `coverage` block reports the files
  it skipped and the languages without symbol data (symbols are deep for Python; other languages
  need the tree-sitter pack). An unparsed region is a region you still owe a read.

**The hand-off — read the stderr summary first; don't reverse-engineer the JSON.** `preindex` writes
the JSON to `.coyodex/preindex.json` **and** prints a one-line human summary to **stderr** (heaviest
top-level dirs, file/LOC totals, ambiguous-symbol count, languages without symbols, the GR1/GR2
reminders). **Read that stderr summary** — do *not* pipe the run through `tail`/`head` and discard it,
and don't re-derive "the largest files/dirs" by hand: the weight tree already ranks them (children are
sorted by LOC, descending). The JSON shape, so you don't have to guess its keys:

```
{ "tool", "root",                       # provenance
  "weight":   { "path", "loc", "file_count", "churn", "lang", "langs",
                "children": [ …same node shape, sorted by loc desc… ] },   # the nested directory tree
  "symbols":  { "by_name": { "<name>": [ { "file", "line", "kind" } … ] }, "ambiguous": [ … ] },
  "imports":  { "pairs": [ … ] },        # only when --pairs {component:[paths]} was given
  "coverage": { "files_counted", "git_available", "tree_sitter_available",
                "languages_seen_without_extractor", "note", … } }          # what it could/couldn't parse
```

This concretises finding **G1** in
[internal/docs/scaling-to-large-codebases.md](internal/docs/scaling-to-large-codebases.md); the
guardrails above are **GR1/GR2/GR3/GR5** there. The validator's `--check-coverage` (below) is the
verification half — it re-measures the tree independently and never reads this JSON (**GR4**).

**Parallel mode (large repos only — serial is simpler and just as accurate on small
ones).** The build order maps to a fan-out workflow: **parallel harvest → barrier
synthesis → parallel trace.**
- Phase 1 Harvest (fan out, one agent each): T4 entry points, T2 deps, T5 model, T3
  run/build, T0/Roles reader. Parallel harvest also improves completeness. **Launch the whole
  harvest as one concurrent batch** (all agents in a single fan-out), not in waves — the slices are
  disjoint and use pre-allocated ID ranges, so no agent needs another's output first, and they
  return compact rows (not file dumps) so reading them together is cheap.
  - **Exactly one agent owns T5, in every fan-out mode — non-optional.** The T5 model is a single
    whole-domain slice: one dedicated agent reads the domain/model layer across the repo and returns
    **per-entity cards with FIELDS *and* RELATIONS** (the `E↔E` class diagram). This holds even when
    the rest of the harvest is sliced **by directory or by subsystem** for a large repo: the
    directory/subsystem-sliced agents return their **components / entry-points only** (Phase 1 returns
    nodes; edges are Phase 3) and must **not** absorb (or split up) the T5 slice, and no slice may
    silently drop it. Skipping the
    dedicated T5 owner is the thin-domain regression — the entity graph then gets backfilled late as
    an afterthought and comes out sparse. **Anti-pattern:** do **not** collapse T5 into an "entities
    touched" list or a bag of `C→E` edges — those record which component uses an entity, not how the
    entities relate; the `E↔E` RELATIONS are the domain backbone and only the T5 owner authors them.
    (`--check-coverage` independently flags a sparse / under-harvested domain model — see below.)
- Phase 2 Synthesize (barrier, one agent): T1 clusters/dedups all harvest outputs, and (large
  maps) assigns Subsystems — a global graph cut, so it stays at the non-delegated barrier.
- Phase 3 Trace (fan out, one agent per use case; large maps may instead fan out one agent
  per subsystem — bounded context — then a non-delegated reconcile traces the cross-subsystem seams).
  Each trace agent produces its use case's **T6 flow** (the ordered `from → to` steps) and also
  records the **`C→E` edges** for the components in its slice — the entities they persist/write/read by
  **direct** use — so structural entity-usage is captured at component granularity, not only
  behaviorally via the flow steps. This is *additional*: the `C↔C`/`C↔D` edges
  remain the primary output and must stay complete (every dep wired, the component graph not sparse).
- Phase 4 Adversarial verify (fan out, one skeptic per L2 worklist claim — **fresh context**). After
  the map validates and `coyodex audit` runs (fix any blocking `why:`-ref contradiction; reconcile the
  read-before-create / actor advisories), take the audit's
  **L2 grounding worklist** and launch one sub-agent per high-risk claim, each told to *disprove* the
  claim against the code (default to *refuted* on doubt; for the riskiest claims — auth, scoping,
  encryption — use N skeptics + majority vote). This is the *breaking* twin of the parallel *build*:
  the same fan-out shape, aimed at falsification. **Fresh context is the whole point** — a verifier
  that can see the build reasoning inherits its blind spots, so independence comes from an isolated
  sub-agent, not from a separate run. Reconcile every refutation (fix the map, or justify the claim
  and record why); this reconcile is **not delegated**. Re-validate → re-audit → render after fixes.
- Guardrails: all agents share the same schema + edge-verb vocabulary; Phase 1 produces
  the canonical node inventory FIRST (nodes before edges, agents reference nodes and
  never invent them); every agent keeps inferred-vs-verified labels + returns `file:line`;
  agents return rows (structured output), not file dumps. The final reconcile (dedup
  names, verify cross-agent edges against code) is not delegated — and the lead may **not**
  author a `C→D` edge (or any edge into an external dependency) the trace agents did not
  report: every backbone edge must trace to a delegated agent's finding or be grounded
  against the code, never invented at synthesis to satisfy the "every dep needs an incoming
  edge" nudge (the audit→Elastic false-edge class — a benign-verb edge no gate re-checks).

**Harvest-prompt template (Phase 1).** Give every harvest agent the same prompt skeleton —
only the file list and the background blurb change per agent. Reusing one contract is what makes
each agent return the same row shapes with the same verified/inferred discipline, which keeps the
barrier synthesis clean. Fill the «angle-bracket» parts:

> You are harvesting «structural / operational / build» facts for a coyodex codebase map.
> Read these files completely, then produce ONLY the rows below — the only file you may write is
> your own fragment file (see the output rule below).
>
> **Files:** «absolute paths this agent owns; list a directory first, then read each file».
> **Background:** «what the main agent already learned about this slice, handed down so you
> don't re-derive it».
>
> For every row give `file:line` evidence and a confidence tag (**verified** = read in code /
> **inferred** = guessed). Use only the schema IDs and edge verbs; reference nodes, never
> invent them. **Return exactly this fixed set of sections — one per prescribed slice — and if you
> cannot fill one, return its header with `(none found)` and say why; never silently omit a
> section.** Your output is **ONE JSON fragment** — a partial map model per
> [method/model.md](method/model.md): an object holding only the top-level arrays your slice owns
> («e.g. `components`, `entry_points`, `deps`, `deployment`, `observability`, `security`,
> `config`»), each entry using that array's exact field names. **WRITE the fragment to
> `«repo»/.coyodex/build-fragments/«agent-id».json` yourself and return only that path plus a
> one-line inventory (row count per array)** — never inline the fragment in your reply: a large
> fragment (a T5 return routinely exceeds 50 KB) is silently truncated by sub-agent result caps,
> and a truncated fragment fails `assemble`. An empty slice is an empty array plus a one-line note.
> **Anchor formats** (`assemble` normalizes the common drifts, but write them right):
> `components[].anchor` and `entities[].source` are **bare** repo-root-relative refs
> (`path/to/file.py#L120`; a directory anchor keeps its trailing slash, `path/dir/`); group anchors
> (`subsystems[].anchor` / `subdomains[].anchor`) are **markdown links** `[dir](path/dir/)`; an edge
> `where` and an `entry_points[].entity` are markdown links `[file](path#Lnnn)`.
> **If you are the T5 DOMAIN-MODEL owner** (one agent owns T5 — see the harvest plan), your fragment
> also carries the **`entities` array — per-entity objects, never a flat table** (`id`, `name`,
> `store`, `meaning`, `source`, `fields`, `relations` — the semantic spec is
> [domain-cards.md](method/domain-cards.md)), with **a `relations` item wherever two entities
> relate** — the entities + their `E↔E` relations are the whole point of the slice. Each entity is a
> **real named type** (class / dataclass / enum) whose `source` anchors its **definition** — do NOT
> synthesize an entity for an unnamed concept; type embedded fields by their entity (`auth:E7`) so
> relations carry the field name. Mark plumbing types you deliberately did NOT model in
> `non_entity_types` (name + why). A directory- or subsystem-sliced agent that is **not** the T5
> owner returns its components / entry-points only and leaves `entities` to the owner.
> (Edges — including `C→E` — are traced in Phase 3, NOT harvested here; this phase returns nodes.)

**Completeness check before the barrier (lead, not delegated).** Before the Phase 2 synthesis, the
lead confirms **every prescribed slice came back with its sections** — in particular that the T5 owner
returned per-entity cards *with* RELATIONS, and that each agent that wrote `(none found)` is genuinely
empty rather than under-delivered. Re-ping any agent that dropped or thinned its sections; a missing
section caught here is cheap, one discovered after synthesis is a re-trace.

**Expected yield per slice — judge each return against its size (under-delivery guidance).** A
well-formed return can still be an under-delivered one: a slice that comes back with far fewer
components than its size suggests has *abstracted where it should have harvested*. Set the
expectation from the pre-index weight map (LOC + file count per directory — the denominators are
already computed) **before** reading the returns, roughly: **expect at least one component per
top-level sub-unit of the slice** (each subdirectory / module cluster that has its own purpose), and
treat **fewer than ~1 component per 3–5 kLOC** of slice mass as suspicious. The two signals compound:
a 40-file, 12-kLOC slice with 6 subdirs that returns 1–2 components is under-delivered even though
every row validates. Re-ping such a slice **with the expectation stated** ("this dir holds 6 sub-units
and ~12 kLOC; return its real units or say per unit why it folds") — a size-blind re-ping just gets
the same answer back. These are attention thresholds, not gates (a heavy *generated* dir still
legitimately folds — the pre-index guardrail applies); a cheap deterministic backstop exists after the
fact in `validate --check-coverage`, which flags folded sibling subdirs and never-referenced dirs.

**Output files — model + generated views.** Build writes a **new** baseline and overwrites any
existing `.coyodex/` map, so you should only be here for a first map or a user-confirmed rebuild —
[dispatch](method/dispatch.md) routes an existing baseline to Analyze, not Build. The committed
source of truth is `.coyodex/project-map.json` ([the map model — schema v2](method/model.md)),
written by `coyodex assemble` together with its two generated views, `.coyodex/project-map.md`
(readable diffs) and `.coyodex/project-map.html` (the diagram) — all three are committed. Record
the commit the map was built at in the model's `commit`/`committed`/`built` fields (the baseline
pin — see the pin gate below).

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

Write the pin into the model's **`commit`** / **`committed`** / **`built`** fields (sha · commit
date · build time — the header fragment carries them; the generated views render them as the map's
header line). For **Built**, capture the minute once —
`date +'%Y-%m-%d %H:%M'` — and reuse that exact string in both the header cell and the stamp below.

**Stamp the conversation (provenance for backup).** After the map is written and validated, record
which conversation built it — run (paths under the coyodex clone, like `.venv/bin/coyodex`):

```
.venv/bin/python tools/map_backup.py stamp <repo> --mode build --built-at '<YYYY-MM-DD HH:MM>'
```

It reads this session's id from `$CLAUDE_CODE_SESSION_ID` and writes `<repo>/.coyodex/provenance.json`
(committed — session id + build time), so a later `.venv/bin/python tools/map_backup.py backup <repo>`
can bundle the map **and** the exact transcript deterministically. Run it in the **main** build
session, not a delegated sub-agent, so the id recorded is the driver conversation's. **Commit
`provenance.json`** with the map + diagram.

**Assemble the model from the agents' fragments — never hand-author the stored file.** Each agent
wrote its JSON fragment to the scratch dir (`.coyodex/build-fragments/<agent>.json` — the harvest
prompt's output rule); `coyodex assemble` itself writes a `.coyodex/.gitignore` entry ignoring
`build-fragments/`, so the scratch dir never dirties the tree (you may still delete it after a
successful assemble — the model is the record). Write one small `header.json` fragment yourself
(`title`, `goal`, the pin fields), then run:

```
.venv/bin/coyodex assemble .coyodex/build-fragments/*.json --out .coyodex
```

It validates every fragment against the schema (a malformed fragment fails ALONE, with its file and
JSON path named — re-request that one agent's rows), refuses duplicate IDs across fragments, and
writes the canonical `project-map.json` plus the generated md/HTML views. In serial (non-parallel)
mode the same rule holds at smaller scale: author your rows as one or a few fragments and let
`assemble` serialize — the stored JSON is always tool-written, so its validity is guaranteed by the
serializer, not by you. (The old markdown template,
[`method/templates/project-map.template.md`](method/templates/project-map.template.md), now only
documents the generated view's shape — it is no longer filled in by hand.) Run the validator —
`.venv/bin/coyodex validate .coyodex/project-map.json --check-sources --check-coverage` ([tools/coyodex/validate_model.py](tools/coyodex/validate_model.py)) — after
each assemble/patch and fix the model (via fragments / field edits + re-assemble or re-render)
until it passes (`--check-sources` reads each entity's `source` to reject synthesized entities —
names with no real named type; `--check-coverage`
re-walks the repo and WARNS — non-blocking — when many sibling source subdirs are folded into one
box or a significant directory is never referenced, the map-fidelity gaps the ID checks can't see).
**Then run the adversarial pass** — `.venv/bin/coyodex audit .coyodex/project-map.json`
([tools/coyodex/audit_model.py](tools/coyodex/audit_model.py)). Where validate asks *is the map
well-formed*, audit asks *is it self-contradictory*: it makes the map's two layers — the narrative
Golden Path (step order, actors) and the mechanism (T6 flows + the backbone edge list) — refute each
other, deterministically, with no code. The map is **over-determined** (each precondition is encoded
twice — once as narrative order, once as which entity a flow reads vs writes), so the two copies check
each other. Audit **blocks (exit 1) only on a hard contradiction** — a *`why:` reference that points
forward or at a nonexistent step* (unambiguous, no false positives) — which you fix like a validator
error. Its ordering/actor checks are **ADVISORY, not blocking**, on purpose: *read-before-create* (a
Golden-Path step reads an entity a later step first `writes`/`persists`/`creates` — `writes` is
create-or-update ambiguous, so this is a pointer, not a verdict) and *actor-attribution* (the
Use-cases table and the flow disagree on who drives a use case) are derived from lossy
component-granularity attribution, so they have real false positives (a shared component leaks its
reads) and false negatives (a read routed through a `C→C` dependency is invisible — only `C→E` edges
count). Treat them as strong "look here" pointers to reconcile, not facts; *read-never-created* (a read
with no create — often external/config data) is advisory too. The known bug that motivated audit (a
sign-in step ordered before the org it needs) surfaces here as an *advisory* — audit points, you or L2
decide. Audit also prints an **L2 grounding worklist**: the "actually-does" claims no deterministic
check can settle — the **whole backbone edge list**, ranked most-dangerous first so a large list is
worked top-down: security surfaces + `enforces` / `encrypts` edges, then every `C→D` external-dependency
edge (any verb — the audit→Elastic system-boundary class), then every `C→E` ownership edge, then the
remaining element↔element edges (an edge into a dep explicitly tagged `framework`/`library` is skipped —
a false "uses <lib>" is benign). Ground each
by spawning a **fresh-context skeptic** (Phase 4 below) that sees only the finished map + the code —
never your build reasoning — and tries to *disprove* the claim; **reconcile every finding — advisory
or blocking — (fix the map, or justify and note why)** before rendering. So the invariant after every
write is **validate → audit → render**.
**Then render the views** — once the
map validates and the adversarial pass has no blocking contradiction (advisories reconciled),
regenerate both views next to the model (assemble already wrote them; re-run after any patch):

```
.venv/bin/coyodex render .coyodex/project-map.json .coyodex/project-map.md
.venv/bin/coyodex render .coyodex/project-map.json .coyodex/project-map.html
```

Both are *renderings* of the model (no second source; never hand-edit them — `validate` flags a
stale view) — commit them alongside the model so the three stay in step and a reviewer can open
either. **Finish by reporting the artifacts as links** — the model (`.coyodex/project-map.json`),
the markdown view (`.coyodex/project-map.md`), and the diagram HTML (`.coyodex/project-map.html`),
as relative paths so the reader can open any. **In addition, for the HTML give the full clickable `file://`
URL with the absolute path**, so the reader can open the diagram straight in a browser — e.g.
`Open in browser: file:///abs/path/to/repo/.coyodex/project-map.html`. (Paths like `.venv/bin/coyodex`
are relative to the coyodex clone, like the validator above.)

**Maintaining the map.** When code changes after a baseline exists, follow
[change-impact](method/change-impact.md): report the impact against the map (modified /
added / deleted), then accept: patch the MODEL (`.coyodex/project-map.json` — surgical field
edits), bump the baseline pin, re-stamp provenance
(`.venv/bin/python tools/map_backup.py stamp <repo> --mode accept --built-at '<YYYY-MM-DD HH:MM>'`,
which appends this session), **re-run validate → audit** (a patch can introduce a fresh
self-contradiction — e.g. a re-ordered Golden Path step now reads before it creates), **re-render
both views** (`coyodex render` to `.md` and `.html`, so they track the patched model), save the
annotated diff under `.coyodex/analysis-changes/<date>.md`, and commit the model + views +
`provenance.json` with the code.

**Drilling deeper (refine altitude in place — never a second map file).** When a subsystem is too big
to detail at its altitude (e.g. a `plugins` area holding dozens of feature units), go finer **inside the
one map**, two ways:
- **Nest** — add child subsystems (their `Parent` is the bigger `S`) and move the members onto them.
- **Promote a leaf component into a subsystem** — when a component turns out to *be* a group (its
  Purpose enumerates many sub-units; the validator nudges this), retire the component, add a subsystem in
  its place, and add its real units as components under it. **Re-trace its edges**: the old component's
  aggregate edges (`C — verb → X`) must be re-pointed to the specific new components — a subsystem can't
  be an edge endpoint, so the validator's "every reference resolves" check fails on any leftover edge
  to the retired id, which forces (and guards) the re-trace.

Both are ordinary single-map edits; the viewer then drills the new level automatically. **Altitude may
be uneven** — refine only where you need detail; an area you haven't drilled stays a single box. This
**supersedes child maps** (a second `.coyodex/<area>/project-map.md`): a separate file is a separate ID
space, so links can't cross it and Analyze/Accept won't track it — see [dispatch](method/dispatch.md).

**How to apply.** Lead with the behavioral layer (T0 Goal → Glossary → Roles → Use cases →
Golden Path); on a non-trivial repo run the **pre-index** next (never before the behavioral
draft — GR1), then build structural Level 0 (T1–T3) using its weight map to set altitude;
generate the rest on demand as the reader drills. Always attach `file:line` (the pre-index's
symbol index gives correct ones). Label every entry point and every relationship as
verified vs inferred — that is where wrong guesses hide.
