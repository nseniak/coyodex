# The coyodex method

How an AI coding agent builds and maintains a top-down, drillable map of a codebase.
Deliver this fixed set of sections, rendered as tables in the generated view. Every row is
drillable: name a row and it expands to a lower table or jumps to code with clickable
`file:line` links.

Two linked families:
- **Behavioral** (why/who/what): Goal → Glossary → Roles → Use cases (grouped into Capabilities) → Happy Path.
- **Structural** (the machine): Components → Entry points / Model / Deps → Flows + Edges.

They join at **use case ↔ flow**.

See also: [dispatch](method/dispatch.md) · [the map model](method/model.md) · [domain cards](method/domain-cards.md) · [change-impact](method/change-impact.md) · [diagrams](method/diagrams.md).

**The stored map is a structured JSON model** (`.coyodex/project-map.json`, [the map model](method/model.md));
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
- **Roles (actors)**: `Role | Kind | What they want | Use cases they drive`. Each role is a first-class
  element with an **id `Rn`** — use cases and flows reference actors BY THAT ID, never by name. List ONLY the
  **primary actors** — the parties who *initiate* a use case and drive the system. Do **not** list
  external systems the project itself calls out to (IdPs, sandboxes, upstream services, third-party
  APIs): they are not actors here. They belong in **T2 external dependencies** + the edge list, and
  the context diagram draws them as *outbound* arrows (the system uses them), never inbound. **Kind**
  (required, every role states one) = `human` or `service`. A `service` actor is an **autonomous
  external initiator with its own goal** — a scheduled job (time as the actor), a worker/poller that
  reaches out on its own, or an external system that calls IN (an inbound webhook sender, an API
  client). It is NOT a system the project depends on (that is a T2 dep, drawn outbound).
  **Crucially, a `service` actor is NOT internal machinery that merely receives or relays a human's
  (or another party's) action inward** — a gateway, a shard / gateway connection, an event
  dispatcher / router, a message consumer that just forwards. That machinery is a **component in the
  flow**, never an actor: the party who *acted* (the member who chatted, the admin who clicked) is the
  actor, and "the event arrives via the shard" is a flow STEP. "It drives event handling" does not
  make something an actor — an actor has the GOAL, not the delivery job. When the docs don't say,
  infer from naming and mark it inferred.
- **Use cases**: `Use case | Actor | Trigger | Outcome`, where **Actor is the party the use case is
  FOR** — the one whose goal it fulfills (`actors: ["Rn", …]`). Rank by importance — the headline
  features and intended workflows in the project's docs are usually the primary use cases (see
  *Read the project's own docs* under Cross-cutting rules). **Prefer exactly ONE actor per use case.**
  List more than one id ONLY when they are *interchangeable initiators of the same goal* (an admin OR
  a moderator can run the same action). **Never pair a human with the machinery that serves them** —
  a member chatting is one actor (the member); the shard that delivers the message, the worker that
  reacts, the dispatcher that routes it are flow components, not co-actors. A human + a `service`
  role on the same use case is the classic tell that the service is really the delivery mechanism.
  - **One use case = ONE actor goal: one trigger, one outcome.** The test: after it runs, the actor
    can say "I did X" with a single X. The **name is a single verb phrase** — a name joining two
    verbs with "and" ("Sign in **and** create an organization") is the split signal (`validate`
    warns, advisory): if the halves have their own triggers and outcomes, they are two use cases;
    the Happy Path expresses their ordering. A fused use case also bloats its T6 flow past the
    step band (below) and forces its Happy Path step titles to compress two outcomes into one line.
  - **Front-door verification — cross-check the list against the REAL entry surface.** The
    behavioral draft comes from README/design docs, and docs lie in both directions: a use case
    authored for a capability that no longer exists (stale docs), and a real user-facing surface no
    use case mentions (both happened on live maps). So before finalizing the use-case list, the lead
    enumerates the **registered** routes / MCP tools / CLI commands / callbacks (grep the
    registrations; in parallel mode the T4 harvest IS this enumeration — do the cross-check right
    after synthesis, when T4 first exists) and checks **both directions**: (1) a use case whose
    trigger has **no entry point behind it** → drop it or mark it stale-docs; (2) an
    **externally-triggered entry point no use case claims** → a missing use case or a dead surface —
    add the use case, or adjudicate it as ops/debug/infra. **Claiming has TWO arms, because one
    cannot carry it.** A use case relates to the entry surface in two different ways: its
    **trigger** is the front door an actor hits to start it (authored as `entry_points` on the use
    case, via the synthesis `reconcile` — see *Build order*), while its **traversal** is every
    surface the scenario merely passes through (derived from the flow's component reach). The
    derived arm stays PRIMARY and the authored one refines it. Making the authored link the only
    test inverts on real maps: on coyodex's own map ~16 of 61 entry points are not triggers of
    anything a person does (fetches the browser makes *after* the reader clicked, plus middleware)
    and every one would report as a missing use case; on a map whose harvest recorded route *groups*
    — one row for a whole SPA — a dozen use cases would have to name zero surfaces, which rule (1)
    reads as "stale docs, drop it". So **a use case naming no surface is legitimate**, never a
    finding. Entry-point granularity is *reported*, not regulated. The mechanical backstop:
    `validate` warns (advisory) on every T4 entry point neither arm reaches; a deliberate
    ops/debug/infra surface is recorded as `Cn: <why>` under an **"Unclaimed surfaces"** extras
    heading, which silences that component durably. On a large repo the wall can be dozens of
    surfaces — `coyodex validate --emit-unclaimed` prints a ready-to-paste block of every current
    one (each as `Cn (name): <why>` with its triggers) so you adjudicate them in one pass instead of
    hand-typing the list (a fresh monorepo build left ~125 of these unaddressed because recording
    them by hand was too costly). **Self-activated entry points (crons, workers, consumers, startup
    hooks) are NOT exempt.** A scheduled job is an actor with a goal by the Roles rule above, so
    exempting them would hide a whole background capability with no signal at all. They are claimed
    like anything else. Be honest about the other half, though: a cron or a boot hook often has **no
    actor to claim it**, and then the answer is the recorded line, not an invented use case. The
    point is that it becomes a decision instead of a silence. A use case with **no T6 flow at all**
    also warns once tracing has begun — the phantom-capability signal.

### Capabilities — the grouping over use cases

Components group into **product areas** (subsystems) and entities into **subdomains**. Use cases
group into **capabilities** — the same shape, a third forest. Without them the use-case list is the
one content family with no structure at all, and no screen answers *"what does this product do?"*.

- **A capability is a group of use cases that serve one goal of the product** — `Organizations &
  teams`, `Upstream MCPs`, `Tool access via gateway`. Aim for the same 5±2 the diagrams use: five
  boxes is a product description, twenty is a list.
- **Each capability carries a `label`: `core` | `supporting` | `platform`.** This is an authored
  judgement about the USE CASES in it, and it is what turns Happy-Path membership into a rule (see
  the Coverage rule below) instead of a written justification per off-spine use case.
- **Nothing derives it, and it says nothing about code.** The tooling can tell you which elements a
  capability's flows reach; it cannot tell you that a component is platform machinery — no threshold
  over that reach separates machinery from product. `validate` therefore BLOCKS `label` on a
  subsystem or a subdomain — an unbacked classification of code is exactly the parallel,
  contradictable axis the `tech`-on-a-subdomain rule already refuses.
- **Assign it once, at synthesis**, as `reconcile` set directives (`{"ids": ["UC1"], "capability":
  "CAP1"}`) — the same pass that assigns `subsystem` / `subdomain` / `runs_in`.
- **Do not confuse a capability with a product area.** A capability groups *use cases* (behavioral);
  a product area groups *components* (structural). A product area usually mirrors a capability —
  that is the point of the top-cut guidance — but neither derives the other.

### Happy Path — the spine (an ordered walk through the use cases)

The Happy Path is one end-to-end happy-path **ordering of use cases** that traverses **all** main
functionality and involves **all** relevant actors; edge cases excluded. A use case on its own has
no fixed position — use cases relate by **preconditions**, a partial order / DAG ("an org must exist
before a user can join it"), and several orderings can satisfy it. The Happy Path is the **one
concrete walk** through that DAG that tells a coherent story. Placed right after Roles/Use cases as
the spine; built after harvest + at least one full trace.

- **Each step IS a use case.** A step is a `**HPn — <title>** *(UCn)*` heading whose `*(UCn)*` tag
  (**required**) names the use case it realizes; `HPn` is just its position in the walk. The step's
  *detail* — the sequence of actions and the components/deps/entities involved — is **not** written
  here; it lives once in that use case's **T6 flow** (below). Drilling a step opens its flow. A use
  case may appear at several positions (each a distinct `HPn`); the use case is still defined once.
- **Order = the chosen walk; an optional `why:` line records the prerequisite** ("needs the org from
  HP1"). That is the only narrative the Happy Path itself carries — the actions and mechanics belong
  to the use case's flow, not restated here.
- **A step's title states the ACTION taken at that position** (present tense: "Admin invites a team
  member"), phrased for this walk moment (it may name the variant/actor: "…adds a *Hosted stdio*
  MCP"). **Never a post-condition**: "Admin signs in; the organization exists" reads as a
  precondition and can contradict its use case's name — the outcome belongs to the use case's
  `Trigger → Outcome`, and state chaining belongs to dependent steps' `why:` lines.
- **Preconditions: implicit vs explicit.** *Implicit* = environment state no walk actor produces by
  using the product (the service is running, the database exists) — never a step, never mentioned.
  *Explicit* = something a walk actor actually does with the product's surfaces (a first-run
  sign-in) — it must live somewhere findable: an on-spine step, an off-spine use case, or the
  depending use case's trigger; when the walk's FIRST step depends on it, say so in that step's
  `why:` so the spine-as-a-list reading isn't left assuming state nobody established.
- **Actor = the use case's actor.** Because a step is exactly one use case, its driving role is that
  use case's `Actor` — there is no separate `Actor:` line. A cross-actor handoff is simply the next
  step being a use case with a different actor.
- **Refer to actors by their role id** (`R2`, resolved to the Roles-table name in the views) — never
  invented persona nicknames, which anchor to nothing and can read as real data.
- **Coverage rule — asked at CAPABILITY altitude.** Pick the walk hitting all main functionality +
  all actors; if one linear walk can't reach everything, the use cases left off still have their own
  T6 flow, just not a spine position. Membership follows the capability's `label`, in **both**
  directions, and `validate` warns (advisory) on each:
  - **forward** — a **core** capability that no spine step reaches. About five checks on a real map,
    each a genuine gap. Fix it, or record `CAPn: <why>`.
  - **converse** — a spine step whose use case sits in a **non-core** capability: either the label is
    wrong or the step does not belong on the main walk. Record `HPn: <why>` to keep it. This is the
    direction a one-way check cannot produce, and it is what catches a walk quietly padded with
    supporting work.
  - a **non-core capability that HOLDS off-spine use cases** needs ONE record — `CAPn: <why>`, not a
    line per use case. Without it, relabelling a capability core→supporting would silence its whole
    membership with no trace anywhere, and the label would have become an unrecorded escape.
  - a **role none of whose use cases has a spine position** (the "involves all relevant actors" half)
    is unchanged: an ops-only role kept off the walk is legitimate, but it is a decision — record
    `Rn: <why>` under the same heading.

  Every record goes under a **"Happy Path coverage"** extras heading, and ids are read from
  **line-leading** tokens only (`UC7: …`, `- R4: …`), so explanatory prose naming other ids never
  silences them by accident.

  **What this deliberately gives up**: an individual core use case falling off the walk no longer
  warns, because its capability still passes. Those use cases are COUNTED instead
  (`off_spine_in_core_capabilities`), so the trade stays visible rather than becoming a silent loss.
  The old rule demanded a written record for each one, and a record that costs more to write than to
  skip is a record that gets skipped. **A map with no capabilities keeps the old per-use-case rule**
  — `UCn: <why>` for each off-spine use case — so the check is additive rather than a cliff.

### Bidirectional traceability (use case ↔ elements) — standard

Connect each use case to the T1/T2/T5 elements its **flow** touches, **and** the converse, so the
reader can drill down (use case → elements) and step back (element → use cases). ONE source — the
**T6 flow steps** — both views derived; don't store links twice (they drift). A flow step's
endpoints (a component, dep, or entity) ARE the touches — **entities included, so a flow AUTHORS its
central entity touches as steps** (the entity-steps rule under T6): an entity's `Used in UC` view
exists only because flow steps name it. Deriving it **transitively** instead (flow touches a
component → tag every entity that component's edges touch) is rejected: an edge is an *aggregate* of
the component's whole behavior while a step is one scenario's interaction, so transitive tags smear.
Every step carries its **own** short action text describing what happens at that point in the
scenario — the same pair of elements can be used by several steps that mean different things, so a
shared pair-level edge label can't describe each one; the step describes itself.

Deliver as:
1. forward view = the use case's **T6 flow**, whose ordered steps name the elements it touches;
2. backward view = **derived, not authored** — the tooling shows, on each element, the use cases
   whose flow steps through it (`Used in UC`); T5 entities included (no extra column on the cards).

Give every use case, every T1/T2 row, and every T5 **card** a stable ID/anchor (the card heading +
its `SOURCE` link) so both link directions are clickable. Each touch inherits its flow's confidence.

One use case has two faces: **outside** — what the actor does and sees, carried by the use case's
`Trigger → Outcome` cell — and **inside = T6 flow** (the ordered interactions among
components/deps/entities), drawn as a sequence diagram and read as a numbered narrative.

---

## Structural layer

### Level 0 (one screen, whole project)
- **Subsystems (S)** *(optional; recommended above ~15 components)*: `ID | Subsystem | Purpose |
  Parent | Source | Conf.` — the Container altitude: components grouped into subsystems, optionally
  nested (a subsystem's `Parent` is another `S`). Membership is carried on the child (a `Subsystem`
  column on T1); the member list and the inter-subsystem edges are *derived*, never authored. Present
  this first on large maps; drill into T1. **Nesting renders as recursive drill**: each subsystem's card
  shows only its *immediate* children (sub-subsystems as drillable boxes), so a large area drills down
  level by level inside the one map — there is no depth limit (deep chains only warn). Group the **top
  levels by product area** (what the system does), not by tech tier, and keep every card's fan-out near
  the **5±2 target** — see *Diagram balance — the fan-out rule* under Cross-cutting rules.
  Give each subsystem a **`tech`** label — ONE honest stack name ("Python/FastAPI", "Go", "Elixir")
  read off the manifests, with `tech_source` anchoring the manifest line (go.mod, package.json) —
  from the manifests, not a stack essay. Subsystem-only (`validate` blocks it on subdomains).
- **T1 Components**: `Component | Subsystem | Purpose | Entry point | Depends on` (the `Subsystem`
  cell is the component's one parent `S`, or empty = ungrouped).
- **T2 External dependencies**: `Name | Kind | Bucket | Type | Used for | Where configured`. Two
  independent axes describe each dep:
  - **Kind** (optional, CLOSED vocabulary) = *where it lives* — decides shown-vs-folded. External
    **systems** the project talks to across a boundary (`datastore` / `messaging` / `service`, incl.
    IdP/auth, payments, observability SaaS / `platform`) are drawn at Context by name; in-process code
    (`framework` / `library`) folds into one collapsed "Libraries" box. Omitted → inferred from `Type`.
  - **Bucket** (SEEDED-OPEN) = *what it's for* — the PURPOSE that GROUPS the dep into a labelled
    cluster. Externals cluster in the Context view; folded libraries cluster inside the Libraries
    drill (two separate diagrams — the cap of ~8 buckets is checked per-diagram). Reuse a seed's exact
    spelling when one fits, and on a rebuild reuse the bucket names already in the committed map. The
    seed list is a **floor, not a ceiling** — mint a bucket whenever a group of services shares a real
    purpose the seeds don't name. Seeds — external:
    `Data & storage` · `Identity & access` · `Observability` · `Messaging & delivery` · `AI & ML` ·
    `Infrastructure & runtime` · `Integrations` (catch-all); libraries: `Web framework / server` ·
    `Frontend / UI` · `Data drivers` · `Service SDKs` · `Validation / models` · `Logging` ·
    `Crypto / security`. Omitted → inferred from `Type` + `Used for`. Name a purpose, not a vendor
    ("Payments", not "Stripe"). **`Integrations` is the catch-all, not a home for everything external**
    — it means "no specific purpose." When several external services DO share a purpose, split them
    into their own bucket (`Payments`, `Social`, `Blockchain`, `Content` …) rather than letting them
    pile into `Integrations`; `validate` flags a bloated catch-all. Minting an external purpose bucket
    is expected and encouraged (external purposes are open-ended); for **libraries** the vocabulary is
    close to closed, so there a minted bucket is more likely a seed synonym worth folding. An
    integration-heavy product legitimately spans more than the ~8-bucket cap — that advisory is soft.
  - `Type` stays the free-text human label; `Used for` doubles as the short caption drawn under each
    box in the diagram (its first clause), so keep its opening words tight.
- **T3 How to run/build/test**: `Action | Command | Source` — `Source` is a bare `path:line` anchor to
  where the command is defined (the script / Makefile target / config line), not a doc pointer.

### Level 1 (one Level-0 row expanded)
- **T4 Entry points**: `Kind | Trigger | Code entity | Component | Activation` (activation = self|external, blank → inferred from kind).
  `Kind` is a **seeded-open vocabulary** — reuse a seed when one fits (external: `http-route`,
  `ui-route`, `cli`, `webhook`, `mcp-tool`, `middleware`; self: `job`, `poller`, `event-consumer`,
  `startup-hook`, `signal-handler`), mint a project-specific kind only when none does, and reuse the
  exact spelling on rebuild (`validate` folds known drift like `http`→`http-route` and nudges the
  rest). **State per-kind completeness honestly**: for each kind you record, say whether the
  inventory is complete or a sample — one line per kind under an **"Entry-point coverage"** extras
  heading, `<kind>: complete|sampled|partial — <how it was enumerated>` (e.g. `http-route: complete
  — walked FastAPI app.routes`). An unstated kind draws one aggregated `validate` advisory.
  For every **self-activated** entry point, also record its `cadence` — WHEN it runs (a cron expr,
  `every 30s`, `on-boot`, `continuous`) — with `cadence_source` anchoring the line that declares
  the schedule (the beat/cron config or the loop's sleep, often not the entry point's own line).
  While harvesting queue consumers, also fill the **`messaging` catalog** — one row per named
  channel/queue/topic (name, broker dep, publisher/consumer components, payload entity, the line
  declaring the channel name); each participant still needs its real `C→broker` edge (the rows
  catalog, the edges claim — see [the map model](method/model.md)).
- **T5 Domain model** *(domain cards)*: one **card** per entity, not a table row — a block
  `**En — Name**` + `MEANING` / `FIELDS` / `RELATIONS` / `SOURCE` (a block with a defining heading,
  like the Happy Path and T6 flows). Renders as a Mermaid `classDiagram` (boxes with attributes + typed, cardinal relations).
  Each entity is a **real named type** whose `SOURCE` anchors its definition (don't synthesize
  unnamed concepts). Entity↔entity relations are authored on the source card only, never in the
  backbone edge list. Full spec: [domain cards](method/domain-cards.md).
- **Subdomains (SD)** *(optional; recommended above ~15 entities)*: `ID | Subdomain | Purpose | Parent |
  Source | Conf.` — the domain analog of Subsystems: T5 entities grouped into bounded contexts,
  optionally nested. Membership is carried on each card (a `SUBDOMAIN:` line holding one `SD`); the
  member list, the inter-subdomain arrows, and the subsystem→subdomain bridge are *derived*. The Domain
  diagram then leads with a Subdomains overview and drills into one subdomain's classDiagram.
- **T6 Use-case flows** *(the inside view of each use case — a block, not a table)*: one block per
  use case, `**UCn — <title>**` + **numbered step lines**. Each step is an ordered interaction
  `from → to`: **every step** — element↔element and actor steps alike — carries a short authored phrase
  saying what happens at that point (an action, present tense: "POSTs the new upstream", "returns the
  verified email"), which is what the arrow shows. Don't lean on the backbone edge for it: the same
  element pair can appear in several steps that do different things, and one shared edge label can't
  describe each; the step describes itself. A phrase is **pure action** — a condition or qualifier
  ("when the baseline needs a paid read…") goes in the `· note`, not the phrase (the
  dependency-phrasing audit trips on condition-shaped phrases). An optional
  `· <note>` adds flow-specific context.
  - **Where auth (or any shared ceremony) belongs**: include it as STEPS only where it is the
    MECHANISM of this use case's outcome (a member joins *by* completing the invite-link OAuth
    callback — remove those steps and the story breaks); where it is merely a prerequisite state
    (an admin must be signed in before creating the org), it is the use case's **trigger**, not
    steps. One machinery, two roles — mechanism in one flow, precondition in another — is correct,
    not an inconsistency. Renders as a Mermaid `sequenceDiagram` — the actor plus the
  touched components/deps/entities as lifelines, the steps as ordered messages — **and** as a numbered
  narrative below it. Drilling a Happy Path step opens its use case's flow here. The viewer also draws
  the same steps as a **leaf-only map** (a box per touched element, no container frames) for the
  "what does this use case touch?" reading — a second *rendering* of the one step list, never a second
  authored thing ([diagrams](method/diagrams.md)).
  - **Every element↔element step carries its own `where` — THE location.** A step is exactly ONE
    interaction, so it anchors its own call site: the `path:line` in the step's `from` code where this
    step's action fires (the same "anchor the operative statement" rule as an edge `Where`). Unlike an
    edge's `Where` (an *example* among possibly many sites — see the edge rules below), a step's
    `where` is precise: the viewer drills the step to exactly this line, and the diff-impact engine
    hits the step (→ its use case → the Happy Path) directly when the line changes. You already read
    this call site to write the step's phrase — record it. **Required** on element↔element steps
    (`validate` blocks; `lint-fragment` catches it in the authoring agent's own turn); a step with
    genuinely no single site (event-driven / config-wired) sets **`no_call_site: true`** instead.
    Actor steps (a Role endpoint — a human action) need none, though a `where` is welcome when the
    handler line is clear. Step numbers `n` must be unique within a flow (`validate` blocks) — they
    identify the step for impact and navigation.
  - **Entity steps — author the flow's CENTRAL entity touches (1–2 per flow).** The entities whose
    read/write IS the scenario's outcome or decision appear as their own steps — `C5 → E2 : upserts
    the Membership document @ repo.py:155` — not only as backbone edges: the entity `Used in UC`
    view and line-level diff impact derive from steps, so a flow that narrates only components
    leaves the whole domain model untraceable while every gate stays green (`validate` warns when NO
    flow touches any entity; a map whose flows legitimately touch none records the literal
    `entity-flows` under `Balance exceptions`). *Central* means the join flow's Membership upsert or
    the tool-call flow's RoleSettings decision + AuditEntry append — NOT every config read along the
    way (those stay edges; tagging them all is the transitive smear again, hand-authored). Each
    entity step **rides an existing `C→E` backbone edge** (the edge is the aggregate claim, the step
    this scenario's instance). Author that edge in your slice with the right verb (`reads` /
    `writes` / `persists` — the ownership verbs are what the domain `persists/writes` view reads).
    As a safety net, `assemble` now **derives the C→E edge from any entity step that has none**
    (verb inferred from the phrase, ambiguous → `reads`), so at scale a forgotten edge self-heals
    instead of leaving the entity ownerless — but an inferred verb is coarser than the one you know,
    so still trace it. It carries the ordinary element↔element `where` (the operative read/write
    line in the `from` side's code), and obeys the same false-reads rule as `C→E` edges (the entity
    TYPE at the site, not a string extracted from it). A shared sub-flow is the leverage point: one
    entity step there serves every referencing flow. Entity steps are ordinary authored steps — they
    count toward the 3–15 band; a flow already at the band edge extracts a sub-flow or records its
    exception rather than dropping the entity touch.
  - **Steps can go *backward*, not just forward.** A flow isn't only the request chain — record the
    return-direction interactions where they carry meaning: the **response the actor sees** (the use
    case's outcome), an **error / fallback** path, a **callback or event** the callee fires back. A step
    whose `to` is an earlier participant renders as a **right-to-left** arrow automatically (lifelines
    are placed in first-appearance order). These are **authored steps** (a return is not a backbone
    edge), so write them like an actor step — `C5 → C2 : returns the member list`, `System → Member :
    shows the org`. Don't echo *every* call with a return — only the ones that say something.
  - **Named sub-flows (`SFn`) — machinery shared by ≥2 flows is defined ONCE.** When the same step
    sequence rides several flows (an event fan-out, a persistence pipeline), extract it into a
    sub-flow — `**SFn — <name>**` + ordinary step lines under all the ordinary rules (phrase,
    `where` anchors, unique `n`) — and reference it from each flow with a step whose `subflow`
    names it: `k. C1 → C2 ⟨runs SF1 — <name>⟩` (src/dst are the run's entry/exit endpoints; the
    phrase may be omitted — it defaults to the sub-flow's name; the reference carries NO `where` of
    its own). One level only — a sub-flow's step may not reference another sub-flow (`validate`
    blocks). A sub-flow with fewer than 2 reference STEPS across the map is pointless indirection
    (`validate` warns — it counts reference steps, so two references inside one flow do not warn). The payoff is CONSISTENCY: without it, each flow retells the shared machinery at
    whatever depth its author picked — the viewer expands the reference inline (a tinted block
    named after the sub-flow) and the diff-impact engine reaches every referencing use case from a
    changed sub-flow line.
  - **The step band: 3–15 steps per flow** (advisory; a sub-flow reference counts as **1** — the
    reward for extracting). Over 15 means one of four things, in the order to try them: **split a
    fused goal** (two use cases were stapled together), **compress step altitude** (protocol
    round-trips narrated at wire grain — fold "401 → metadata → retry" into one meaningful step),
    **extract a sub-flow** (shared machinery inlined), or — when the length is genuinely earned
    (a chatty auth handshake that IS the story) — **record the exception**: the flow's UC/SF id
    under a `Balance exceptions` extras heading, with one line of why. Under 3: check the flow is
    traced to its outcome. `validate` also flags **literal duplication** (a run of ≥4 steps
    identical in endpoints AND grounding appearing in ≥2 flows; runs through an actor step are
    exempt — a sub-flow can't contain them) — extract a sub-flow, or, when investigation shows the
    overlap is deliberate, **record the adjudication**: `UCa & UCb: <why>` under an
    **"Accepted duplications"** extras heading, which silences that pair (a justification that
    lives only in the build transcript re-fires at every future validate). The *same machinery
    retold at different depths* can't be caught mechanically — that is a Phase-4 grounding item
    (below).

### Operational dimensions — standard core four
- **Deployment & topology**: `Unit | Runs on | Exposed as | Config source`. These are NOT tabled on the System tab — that page is for facts no diagram holds. Each row's facts live on the box that represents it in the Deployment view: its **process box** for a unit that hosts code (or an untraced one), and the **dependency box** standing in for it when the unit is infrastructure hosting no code. `variants` shows there too, as an **Environments** row with its grounding anchors. **Link the code to the
  runtime with `runs_in`** — on each component, the deployment `Unit` name(s) whose process executes
  it (a component may run in several: the C4 *instance* relation, one static box → many processes). It
  powers the **Deployment view** (`coyodex serve` → Deployment tab): processes and infra as nodes,
  their self-started threads on drill, and derived `runs` edges to the subsystems each process
  executes. It also carries the view's **process topology**, composed from `runs_in` two ways:
  **asynchronously**, via the async catalog (a channel's `publishers`/`consumers` are components, each
  naming its host unit) → an arrow per channel one unit publishes and another consumes; and
  **synchronously**, via the backbone edges (a component→component edge whose ends run in DIFFERENT
  units is one process calling another) → an arrow per crossing call. Both matter: a message-driven
  system is all channels, an ordinary client/server app is all calls, and deriving only one leaves the
  other kind of project with an empty diagram. One arrow per ordered pair either way, on the overview
  and on both units' cards, selectable to list what it stands for with each declaring line. The overview's
  infrastructure lane is likewise **placement, not a catalog**: it shows only the brokers/stores/services
  used by **2+ processes** — the coupling points — each with a real arrow per user, selectable to list
  the components inside that process that reach it, with their verb, reason and call site. Infra a single
  process touches stays on that process's card; the full inventory is the Dependencies view's job (and
  the Data view's, for stores), so repeating it here would only restate them less completely.
  That lane's sub-bands read **"Used as a message bus / data store / service"** because they group by
  the VERB the code reaches the dependency with, not by what the dependency is. So two deps of the same
  `kind` can sit in different bands — a live map put Mixpanel (`kind: service`, reached by `emits`) in
  the bus band and Sentry (`kind: service`, reached by `calls`) in the service band. That is the useful
  question here ("how does the code talk to this?", which no other view answers), so the grouping stands
  and the LABEL says which question it is answering. Do not re-word an edge verb to move a box between
  bands: the verb records what the call site does, and the band follows it.
  Selecting an **environment** never removes a box: units the environment excludes are **dimmed in
  place and made inert**, so "not deployed there" is visible instead of being a silent absence, and the
  layout does not move when you switch. (One diagram serves every environment; the `variants` tags ride
  on the boxes and the viewer fades the rest.)
  The overview draws **runtime things only** — processes and the infrastructure coupling them. There is
  no subsystems lane: subsystems are code structure, the Subsystems view already draws all of them with
  their real relationships, and a lane here could only restate the subset whose components happen to
  carry `runs_in`. The code→process placement is answered in the **info pane** instead: selecting a
  subsystem or a component shows **Runs in** — the units that run it, each a link opening that
  process's card — and each unit's own card still draws what it runs. The row is absent when nothing
  records running that code, which is the visible sign that its `runs_in` tagging is missing.
  **Derive `runs_in` by READING THE DEPLOY MANIFESTS — never formula-fill by id range.** Open
  the docker-compose services, the Dockerfiles + their `CMD`/`ENTRYPOINT`, k8s/Helm, the `Procfile`, and
  the launch entrypoints (`manage.py`, `main`, the worker bootstraps): for each unit, tag the
  component(s) whose process loads it, and tag each background-loop entry point with its precise host.
  Grounding: **verified** for a satellite that owns its dir/image (obvious from the Dockerfile/dir),
  **inferred** for a shared monolith (which sub-command/loader pulls the component in) — mark it inferred
  where the manifest is ambiguous; empty = untraced. For a background loop whose component runs in >1
  unit, set the loop's own `EntryPoint.runs_in` for a precise host. A deployment `Unit` is **ONE
  process**: keep the name atomic (no `mongo / redis` compound rows) and give each its own row. Infra the
  app merely *talks to* (mongo/redis/nginx) is a **dependency**, not a `deployment[]` process box — the
  Deployment view draws a unit as a process only when a component or entry point `runs_in` it, so an
  infra-only unit renders as a dead empty box. `validate` blocks a `runs_in` that names no real unit (and
  a duplicate unit name), advises on a self-started entry point left with no host (it would be "Unplaced"
  in the view), and now **flags a formula-filled `runs_in`** (one unit blanketing every component while
  other units host nothing and no entry point is placed), a **non-atomic unit name**, an **unlinked unit**
  (hosts nothing, matches no dependency), and an **ambiguous thread host** (a loop whose component runs in
  >1 unit but which sets no `runs_in`). `runs` edges are **derived, never authored** in the edge list.
  - **Environments (deployment variants).** Many projects deploy the same code in several
    **variants** — dev / staging / prod, or genuinely different shapes (a single-container
    `standalone` vs a multi-service `cloud` split). This axis is usually declared in the source:
    docker-compose `profiles:`, k8s/Kustomize overlays, Helm values files, Terraform
    envs/workspaces, `.env.<name>` suffixes, serverless/Procfile stages. **Capture it, don't flatten
    it** — folding the variants away as "over-modeling" loses real information. List the variant
    names in the top-level **`environments`** array, and tag each `deployment[].unit` with the
    **`variants`** it belongs to (empty = **ungated / shared**, appears in every environment). Each
    variant tag is an object **`{env, source}`**: `env` names the environment, and `source` is a
    bare `path:line` anchor to the manifest line that places the unit there. Keep the unit name the
    process identity (`backend`), not the env (`backend (cloud/prod)`) — the env lives in
    `variants`. A component's environment is **derived** from the variants of the units it
    `runs_in`. **The tags GATE the Deployment view's process→process arrows**, so leaving them off
    is not free: two units that share no environment can never be running at the same time, and an
    arrow between them is false however the derivation reached it. An untagged unit stays ungated
    and pairs with everything, which is the right default for a map with no variant axis and the
    wrong one for a map that has one and skipped it. Two grounding rules keep the tags honest:
    1. **Ground each `variants` tag in the explicit profile axis; cite it, never invent one.** The
       compose `profiles:` (or overlays / values files / stages) ARE the authoritative "what runs where"
       list — so put the exact line you read in the tag's **`source`** (e.g. `docker-compose.yml:96`).
       `validate --check-sources` verifies that line exists, so a fabricated anchor is a hard block. A
       tag you genuinely cannot anchor is **inferred**: record it with an empty `source` and `validate`
       surfaces it as an advisory — do NOT dress an inference as a fact. A process that appears in **no**
       profile is an ad-hoc / local-dev launcher (started by a `start.sh`, a Makefile target, a `README`
       step) — tag it **`dev`** (or leave it untagged), never a real deploy variant it has no manifest
       basis for.
    2. **A built / static asset served by another process is NOT its own deployment process there.** A
       Dockerfile that does `npm run build` (or any `build`) then `COPY …/dist …` bakes an artifact
       INTO an existing unit — the artifact is *served by* that unit, not *run as* a separate process.
       So do not give it its own unit/variant in that environment; place it only where it actually runs
       as a live process (e.g. the frontend is a Vite dev server in `dev`, but a static bundle baked
       into `standalone` and `nginx` for `cloud` — so it is a separate unit in `dev` alone).

    `validate` blocks a `variants` tag whose `env` names no declared `environments` entry, blocks a
    cited `source` that doesn't resolve on disk (under `--check-sources`), and advises both when
    `environments` are declared but no unit is tagged and when a tag is inferred (no `source`). **If the
    project has no meaningful variant axis (a single deploy), leave both empty** — the Deployment view
    then behaves exactly as before.
    *(Deferred, not modelled yet: per-environment config/secret differences, env-specific
    scaling/replicas, and a cross-environment comparison view.)*
- **Observability**: `Signal | Where emitted | Where viewed | Alerts`.
- **Security & auth**: **an auth surface IS a business rule** — write it in T7 with `access: true`,
  its enforcement line as a site, and what is at stake as its `risk`. The Security & auth table is a
  DERIVED VIEW of those rules; there is no separate `security[]` to author. **BREAKING, and there is
  no migration tool**: a map built before this carries `security[]` rows, and the table still
  renders them beside the rules so nothing disappears — but a map gains the decision layer only by
  being REBUILT. The site anchor must point at the line that ENFORCES — the
  `if`/`raise`/`require_*`/decorator call — **never its docstring, comment, or `def` header** (the
  same operative-line rule as an edge `Where`, below). It is an L2 grounding claim, so
  `--check-sources` verifies the file/line exists. **STATE THE GRANULARITY, and record it.** One row
  per surface FAMILY ("the dashboard API's session auth") and one row per endpoint-and-condition
  ("`/mcp/{slug}` with a service token for another org", "replay of a logged-out session cookie")
  are both defensible — and they differ by 5x in row count on the same codebase. Pick one, say which
  under a `Security granularity` line in your reply, and record it in the map:
  `security-granularity: <family | endpoint-and-condition> — <why>` under a 'Balance exceptions'
  extras heading. (The T7 rule for "fusion is preferred to splitting" pulls the same way: one
  decision enforced at several endpoints is ONE `access` rule with several sites.) Nothing else in
  the pipeline can see this choice: `--check-sources` only proves each row's anchor resolves, and
  `audit` turns each row into exactly one claim, so no gate can tell a 19-row access surface from a
  103-row one. A large change in what the map says about access control has to be a decision
  somebody wrote down, not a drift nobody noticed.
- **Config & environments**: `Key | Purpose | Default | Per-env / secret?` (secrets =
  where they live, never values).
- On-demand extras: state machines/lifecycles, event/message catalog, error/failure
  modes, change hotspots (git churn), permissions matrix (Role × use case).

### Business logic — what the product DECIDES (T7)
**This is the one genuine content gap the other tiers do not cover.** Entities say what the product
stores, flows say what it does in what order, lifecycles say what states it moves through,
components and edges say how it is built. None of them says what it **decides** — and the decision
is exactly what a reader means by "the interesting, product-specific part". A reader who asks "what
is special about this application?" gets no answer from a well-formed map without it.

A **rule** is ONE decision, in product language, naming no component: *"only the order's owner may
cancel it"*, *"own connection first, else oldest shared"*. It carries a short `name` beside that
sentence ("Owner-only cancellation") — the title every list, breadcrumb and cross-link reads, exactly
as a use case has a name beside its trigger→outcome. A **block** groups rules the way a
capability groups use cases — an area a product person would argue about. Rules are written after
the trace, one agent per block (see *After the trace*), because sweeping a rule's enforcement sites
needs the flows.

Each rule carries `sites`: every place the decision is actually ENFORCED, anchored at the
**operative line** — the one that acts, never a definition header and never a line chosen because
it happens to join a flow step. A decision enforced by construction (a type, a schema constraint, a
config-wired guard) says so with `no_call_site` and no anchor.

**Everything else is derived.** Which components enforce a rule, which use-case steps it lands on,
which entities it touches and whether the sweep that produced it finished are all COMPUTED from the
site anchors — there is no field for any of them, and none may be added. Hand-assigned data rendered
as if it were derived looks correct on screen, which is exactly why it is refused. An authored "I
searched the whole repo" is unfalsifiable, so sweep state comes from a canary instead — anchored
flow steps that read like a decision no rule covers (`validate` lists them; the `Sweep debt` extras
heading records the ones that are not decisions). **The canary is a floor, not a proof**: it reads
the wording of anchored steps with a heuristic vocabulary, so an empty worklist means "nothing
obvious was left", never "the sweep was exhaustive".

**This section is shown in the viewer** (`coyodex serve` → Business logic tab) and in the markdown
view as `## T7 — Business logic`, with each site rendered as *line — component*. A file several
components claim shows EVERY one of them; a site in a file no component claims renders as
**unverified**, which is a real state, not a rendering bug.

### Test completeness — measure against the MAP, not line %
**This table is shown in the viewer**: the `coyodex serve` Tests tab renders the honesty note + the
gap table (`Target · Tested? · Test(s) · Gap/risk · Confidence`) — so an empty table is a visible gap.
**Be honest about whether you ran it.** A gap table built by *reading* tests is **inferred**; only
running the suite with coverage makes it **verified**. If you don't run it (the suite is slow or
costs money — e.g. paid integration tests), state that above the table and mark every row inferred;
never present a read-only table as if it were measured.
Coverage % tells which lines ran, not which behaviors are tested. Start from the
inventory (use cases, T4 entry points, failure modes, invariants, state
transitions, critical-path branches) and ask "is there a test that exercises it?" —
gaps are the deliverable.
- Map tests → targets as `test — covers → element`; gap = element with no incoming
  "covers" edge. Each row names its `targets` as explicit element IDs (e.g. `["UC1","C4"]`, not
  prose) and cites the exercising suites in `tests` as `{file, why}` — `file` a bare `path:line`
  or `path/` anchor the viewer turns into a code link.
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
T8 Component internals · T9 Config/env vars · T10 Data schema. Nothing in the tooling produces these
— they are on-demand drill tiers, not rendered map sections like T7.

### Relationships (always included)
- Backbone = a project-wide edge list: `From | Verb | To | Why | Where`. Uniform
  `source — verb — target` so the reader drills from either end. Verb vocabulary:
  uses, calls, reads, writes, emits, listens-to, routes-to, enforces, persists, encrypts,
  extends, implements.
- **Verbs may PRIORITIZE, never GATE.** A verb is an authored word — no deterministic check verifies
  it against the code. So a verb may set *attention* (the audit ranks its L2 worklist by verb —
  security verbs like `enforces`/`encrypts` first) but must never decide *truth*: no gate may branch
  pass/fail on a verb, no claim may be dropped from grounding because its verb sounds benign, and a
  rendered fact derived from a verb is **inferred**, never asserted. The one verb-derived viewer fact
  is the class-diagram **inheritance** arrow (`isA`): the viewer renders the authored verb plainly, so
  it reads like any asserted edge — if it matters, ground the underlying edge (L2), don't trust the
  verb. (The subsystem→subdomain bridge is **not** verb-derived — it shows a count of underlying C→E
  edges, like the container arrows.)
- **The edge list spans C↔C, C↔D, *and* C→E — components / deps / entities ONLY, never an actor.**
  It is not only component↔component: a component's
  link to the domain model is a backbone edge `C — persists/writes/reads → E` (its repository
  `persists` the entity; a service/controller `reads` it — **direct** use only, never a transitive
  edge). Author these alongside the component edges — they power the component↔class cross-links and
  the subsystem→subdomain bridge. (Only E↔E relations stay off the backbone — those live on the
  domain cards.) **An actor (`Rn`) is NEVER a backbone endpoint** — a person/service driving the
  system is expressed as a T6 flow **step** (`R1 → C5`), not an edge; a trace agent that emits an
  `Rn → C` edge is a prompt defect, and `assemble` strips it and warns (fix the trace prompt, don't
  rely on the strip).
- **A C→D edge names the ROLE with a role-revealing verb — never a bare `uses`.** State HOW the
  component uses the dependency: `publishes`/`emits` for a **message bus**, `reads`/`writes`/`persists`/
  `queries` for a **data store** (a query IS a read), `calls` for a **service**. The dep's role is then
  **derived** from the union of its incoming C→D verbs (a witnessed fact — each verb has a `Where` — not
  a stored field), so a dependency used two ways (Redis as **bus + store**) is captured by having
  **both** edges with their real verbs, and its role reads "bus · store". `validate`/`lint-fragment`
  raise a **non-blocking advisory** on a roleless C→D verb (`uses`/`connects`/…) so you pick a real one;
  it never blocks and never fires off the dep boundary (a C↔C / C→E `uses` is fine).
- **C→E is additive — it must NOT thin the component graph.** Trace `C↔C` and `C↔D` **first**; add
  `C→E` after, never instead. Completeness: **every external dep (T2) needs ≥1 incoming component
  edge** — a dep with no edge is an *un-traced* `C→D`, not an unused dependency — and a component
  graph with far fewer edges than components is under-traced. The component edge list is the primary
  trace output; the validator nudges on orphan deps (a thin-trace symptom).
- **Trace the routing spine (frontend / any router).** A routing or app-shell component MUST emit a
  `routes-to` edge to each page/view component it mounts — the route table is real structure, not
  "wiring" to skip. Page components are **traced destinations, not dead-ends** (they still make their
  own outgoing calls to API clients / hooks). A frontend whose pages have zero incoming edges is
  under-traced, not leaf-clean.
- **`Why` = a short phrase: what `From` does to/with `To`** — an **action**, not a dependency remark
  (e.g. "verify service tokens", "cache refreshed OAuth tokens"). Write "POSTs the new upstream through
  the REST client", never "the page needs the REST client to POST" — a "needs / requires / depends on"
  framing describes a static wiring fact, not the runtime action, and reads wrong on the diagram. The
  edge list is the **canonical home for relationship rationale** — the verb gives the category, `Why`
  gives the purpose the verb can't carry (especially the catch-all `uses`). Prefer a sharper verb first;
  let `Why` say what the verb omits. Keep it a terse phrase, not a sentence, so it stays cheap to
  re-verify. This `Why` powers the **component/architecture diagram** arrows; T6 flow steps carry their
  **own** action text (above) and do not reuse it.
- **`Where` = a verified EXAMPLE call site: one `file:line` in `From`'s code where it invokes `To`**
  — not `To`'s definition. An edge `A — verb → B` is *evidenced* by a line in **A** where A uses B, so
  `Where` points there. The edge is an **aggregate** of possibly many interaction sites, so its
  `Where` is a **witness grounding the claim, not a catalog of the traffic** — and it is therefore
  A location, never THE location: the viewer deliberately does not show or open it (per-step `where`
  in T6 owns drill-to-code), while validation, anchor drift, and diff impact still use it. Write the
  edge's `Why` the same way: a **summary of the whole relationship** ("writes org, membership and
  settings documents"), never one call's story — one example's rationale on a shared arrow reads as
  wrong for every other step riding it. **Anchor the exact operative statement** — the write / call /
  enforce line itself — **not the enclosing `def` or the surrounding assignment**; anchoring at the
  function header instead of the operative line is the common drift the Phase-4 anchor-drift check
  flags. When the relationship fires at several sites, pick the **primary / most representative** one
  (one `Where` per edge; do NOT emit the same `(From, verb, To)` from several trace slices with
  different anchors — `assemble` collapses same-call-site duplicates and `validate` flags
  conflicting-anchor ones). Format it as a bare `path:line` anchor (never a markdown link — see
  [the map model](method/model.md)'s Anchor formats).
  **`Where` is required** — a missing one is a blocking `validate` error, because an unwitnessed edge
  is an ungrounded claim. The one exception: a relationship with **no single call site**
  (event-driven, shared-state, or config/DI-wired coupling, where `From` never directly calls `To`) —
  set **`no_call_site: true`** on the edge to make the absence a conscious choice, not a silent gap.
- Convenience = the T6 flow steps, which retell the most-used slice of the edge list in reading order.

---

## Cross-cutting rules

**Write every reader-facing field to be read ALONE.** The six rules live in ONE file,
[method/templates/writing-rules.md](method/templates/writing-rules.md), because the agents who
author that prose are fan-out workers who never read this document: they get a contract, so the
rules have to travel inside the contract. Every authoring contract is assembled by appending that
one file, never by restating it — a second copy is a second thing to keep in step, and the copy
that drifts is always the one nobody re-read.

`validate` counts four of the six and reports them as advisories. Jargon, metaphor and whether a
sentence actually reads clearly are judgements that stay in the prompt: a regex guessing at them
would be the noisy check nobody leaves switched on.

**A blocked command is a STOP, not a puzzle.** When a shell or safety guard refuses a command, say
so and ask — never rewrite the command so the guard stops matching: not by assembling a blocked
filename out of string literals, not by splitting a blocked path across a `+`. A bypass may well be
harmless and the block a false positive — which is exactly why it is worth stating: the reasoning
that produces a harmless bypass is the same reasoning that produces a harmful one, and the guard
exists because that judgement is not the agent's to make. If a guard is wrong, saying so IS the
deliverable. Reaching for a different TOOL and reporting that you did is fine; disguising the same
command is not.

**Two shell hazards this method's own commands keep hitting.** Both are invisible until the output
is wrong rather than absent.

  * **Never `cd` into the coyodex clone in a command that also touches the mapped repo.** The `cd`
    persists across `;` and `&&`, so a trailing `python3 -c "…open('.coyodex/project-map.json')…"`
    reads *coyodex's own self-map* — a wrong answer that looks like a right one, carrying coyodex's
    vocabulary rather than the mapped project's. Use absolute paths on both sides, or run the CLI by
    its absolute path without `cd` at all.
  * **This environment is zsh, and zsh does not word-split an unquoted expansion.** Building a
    repeated flag as a string — `VD="$VD --verdicts $f"` — arrives as ONE argument and the command
    refuses it. Use a bash array: `VD=(); VD+=(--verdicts "$f")`. This holds for every repeatable
    flag, `--keep` and `--verdicts` included.

**Reach for the verb before the heredoc.** Every row below replaces a `python3 - <<'PY'` block, and
each verb exists because a hand script got the same job wrong once. Measured: 12 of one build's 28
hand-written scripts had a verb already, and the scorecard assertion watching this fell 1.00 → 0.57:

| you are about to hand-write | run instead |
|---|---|
| a walk over `build-fragments/*.json` counting rows | `coyodex dump --counts` (it reads a FRAGMENT too) |
| a listing of ids / names / sources | `coyodex dump --legend`, `--id`, `--record`, `--edges`, `--members` |
| a tally of `true`/`false` across the verdict files | `coyodex grounding report` — the hand tally cannot tell a tie from a stated `unverifiable` |
| an append into an extras heading | `coyodex record --heading … --line …` (`--replace` to correct one) |
| a rewrite of a rule's / entity's own TEXT | `coyodex fix row --fragments .coyodex/build-fragments --id <ID> --set-<field> <text>` — it edits the OWNING FRAGMENT, so the edit survives re-assembly |
| a corrected anchor | `coyodex fix apply-drift --to-reconcile` |
| a duplicate edge or relation resolved | `coyodex fix dedup-edge` / `dedup-relation --to-reconcile` |
| a before/after comparison of two maps | `coyodex diff <old> <new>` |

A hand script over `project-map.json` is also how a build ends up reading a field the schema
renamed, and how it ends up editing the ASSEMBLED map — which the next `assemble` rebuilds from the
fragments, discarding the edit without a word.

**Read the project's own docs.** Before drafting the behavioral layer, read what the project says
about itself — `README`, `docs/`, `CONTRIBUTING`, a `CHANGELOG`, package/manifest descriptions, and
any architecture or design notes. These are the primary source for the parts the code does not spell
out: the **Goal**, the **Roles**, and which **Use cases** matter most — the headline features and
intended workflows a maintainer documents are usually the primary use cases, so rank by them. Treat
docs as **intent, not ground truth**: they go stale and oversell, so anything you take from them
stays **inferred** until the code confirms it, and when docs and code disagree, the code wins (note
the drift). Where the docs are silent, infer from naming/structure and mark inferred — don't assert a
confidently-wrong purpose.

**Confidence by layer.** Structure (components, entry points, data) reads reliably from
source — mostly **verified**. Goal/Roles/intent often are NOT in the code (they live in
README/docs/the maintainer's head) — infer from naming/structure, mark **inferred**, and
ask rather than assert a confidently-wrong purpose. A use case's `Trigger → Outcome` sits in
between: the trigger traces from code, but the "user sees" register sometimes needs the running
app, not just code.

**Build order (internal) ≠ present order.** Build bottom-up so each table's inputs exist
first: T3 → harvest T4, T2, T5 (a full sweep — also the completeness checklist that
catches side doors: after the front-door routes/CLI/callbacks, do a **second pass for
self-starting entry points** — anything that runs with no caller: scheduled/cron jobs,
`while True`/interval loops, `asyncio.create_task`/background workers/threads, queue & stream
**consumers** (`.consume`/`.subscribe`/poll), boot/**startup** hooks (`on_event('startup')`,
lifespan, `atexit`), and OS **signal** handlers. Tag each entry point `activation` (self|external);
a long-running service with **zero** self-starting entry points is a red flag — assert why, don't
leave the list front-doors-only) → synthesize T1 → **cluster components into Subsystems** (large maps —
two axes, one per altitude: the **top 1–2 levels group by product area** — what the system *does*, read
from use-case / Happy-Path affinity, so the first screen describes the product; a tech-tier-only root
(`Backend` / `Frontend`, or by-language) is an anti-pattern — that axis belongs in a group's name or a
lower tier, not the top cut. **Leaf grouping stays directory-first**, then dependency/behavioral
cohesion; minimize inter-group edges *at the leaf/sibling level only* — a product-area top level
legitimately has many cross-group edges, so never judge the top cut by edge counts; mark
directory-derived = verified, cohesion-derived = inferred — a cross-directory product-area group has no
single directory home, so it simply **omits `source`**, never fabricates one) → **cluster entities into Subdomains**
(large domain models: the same recipe on the entity graph — by `SOURCE` directory first, then
`RELATIONS` cohesion) → trace T6 + edge list (**including the `C→E` edges**: which component
persists/writes/reads each entity) → **re-balance the grouping against the traced edges** (the
grouping was cut edge-blind — run `coyodex balance`, fix or justify each finding; Phase 3.5 in
parallel mode) → **measure test completeness against the finished inventory**
(the last structural step — it reads the assembled nodes + flows: use cases, T4 entry points, T5
entities, critical-path branches). Nodes (T4/T5/T2)
before the edges/flows that connect them. **Present** top-down (T1–T3 first). The "Depends on"
columns and relationship rows harden last (they need tracing) — keep them inferred until
traced. Drilling can correct an inferred upper row; upper tables get more accurate as the
reader drills.

**Pre-index (structural input).** LAUNCH it whenever you like — backgrounding it before the
behavioral draft is strictly better use of the wait. What must not happen before the draft exists is
READING it: GR1 guards the judgement, not the subprocess, and a build that read the rule as a ban on
launching serialised itself for no gain.

On a non-trivial repo, don't choose altitude from a *count* ("65 plugins, too many")
or from maintainer diagrams alone — that is how a heavy area silently collapses into one box.
First draft the behavioral layer (Goal → Glossary → Roles → Use cases → Happy-Path skeleton),
**then** run the pre-index and let it *size and locate* while you keep *naming and judging*:

```
.venv/bin/coyodex preindex --root <repo>       # writes .coyodex/preindex.json (committed with the map)
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

**Code the map is not meant to describe — `.coyodex/.ignore`.** A repo may commit code that is
genuinely outside the product: a fixture tree built to exercise the tooling, a vendored copy git
tracks, a scratch area. `.gitignore` cannot say it (the files are meant to be committed), so the repo
declares it once next to the map, in gitignore-like patterns:

Write it to `.coyodex/.ignore`. **A `#` opens a comment only at the START of a line** — the same rule
gitignore uses — so a comment goes on its own line above the pattern it explains. `pattern  # why` is
ONE literal pattern containing spaces; it can never match a real path, and `validate` reports the
line as unusable and drops it (write `\#` if you need a literal `#` in a pattern):

```
# the trap fixture — a wildcard-free pattern covers everything beneath it
trapdoor/
# * stays inside one segment; ** spans segments
generated/**
# ! negates; the LAST matching line wins
!generated/hand_written.py
```

Everything that measures the tree honours it — the weight tree, the component expectation E, and
`validate --check-coverage`. **Do not confuse it with a `Coverage exceptions` heading.** They answer
different questions and are not interchangeable:

| | says | use when |
|---|---|---|
| `Coverage exceptions` (extras) | *mapped, deliberately coarse — stop warning* | a real part of the product folded into one box |
| `.coyodex/.ignore` | *not part of the analysed tree at all* | code the map is not meant to describe |

**Read the disclosure it prints; do not write patterns to quiet a warning.** Every coverage check
here re-measures the repo independently of the pre-index (GR4) precisely so a map cannot look
complete just because generation said so. An ignore file is the ONE input both sides read, so an
over-broad pattern hides a real gap from the very check that exists to find gaps — the
"advisory waved through" failure, one level down. That is why `preindex --report` names the patterns
and `validate` always emits an advisory saying how many files went and on what rules. When you did
not author the file, reconcile that advisory like any other: confirm the patterns still describe code
the map is not meant to cover.

**Component granularity — the leaf rule (what "one component" means).** One component ≈ one
module-/folder-/deployable-sized unit — roughly a directory of **≤ ~10 source files / ≤ ~3 kLOC**
with one purpose. At each source folder decide: **component-shaped → stop** (it is a leaf; its
internal files and subdirs stay abstracted — GR6) vs **subsystem-shaped → recurse** (promote it to a
subsystem and map its units). An oversized *flat* folder (no subdirs) splits into its cohesive file
groups instead of becoming one box. Nesting is the **output** of those decisions — how deep you group
leaves into subsystems is free; what this rule pins is the **leaf decision only**. The pre-index
computes the matching **expected component count E** deterministically from the code tree (same caps;
vendored/generated, docs/config and test trees excluded), whole-repo and per-slice, with a generous
**±40% band** — the `granularity` block in `preindex.json`. E derives from the code alone, so it is
advice you reconcile like any pre-index signal (GR2): landing far **under** the band means you folded
subsystem-shaped dirs into single components — make them subsystems and recurse; far **over** means
you split module-sized units too fine. `validate --check-coverage` and the eval **re-compute E from
the tree independently** (GR4) and nudge when the map's component count leaves the band — the nudge
is advisory; a justified exception stays a judgement call.

**Diagram balance — the fan-out rule (what "one readable screen" means).** The leaf rule sizes the
*boxes*; this rule sizes the *screens*. Every rendered diagram shows a node's **immediate children**
(the root shows the top-level subsystems; a subsystem card shows its child subsystems + member
components), so each screen should carry **5±2 boxes** — advisory band **[3, 9]**. The arithmetic
follows: N leaves at fan-out F need ≈ log_F(N) grouping levels (122 components at F≈5 want ~3
levels, not 2). Two named anti-patterns: the **sparse tech-tier root** (a 2-box `Backend`/`Frontend`
top screen tells the reader the tech stack, not the product — sparseness is an anti-pattern *at the
root only*; a mid-tree 2-child subsystem is normal) and the **single-child subsystem** (a wrapper
level pulling no weight — inline it or grow it). One exemption: a **homogeneous family** — a dense
screen of same-kind siblings (11 repositories, 14 plugins) sharing a directory or a name suffix —
reads fine as a list up to ~15. `coyodex validate` warns (always-on, advisory) outside [3, 12];
`coyodex balance` shows the full per-diagram picture (including the 10–12 soft tier), the
inter-subsystem edge matrix, and deterministic split proposals for over-dense screens — proposals
are **starting points for judgment, not ready-to-apply** (on list-shaped or star-shaped screens it
says so instead of proposing noise). A durably justified exception is recorded in the model's
`extras` under the heading **"Balance exceptions"** and silences the matching advisory — the heading
accepts four id families, each scoping one advisory: a diagram id (`root`, `S7`, …) silences its
fan-out warning; a `UCn`/`SFn` id silences that flow's **granularity family** — both the step-count
band (over AND under) and the fused-goal name smell, which are two readings of one question about
one element; a `Cn` id silences its promote-to-subsystem altitude nudge; the literal
**`granularity`** silences the component-count-vs-E advisory (record it with the why when the
altitude decision is conscious); the literal **`entity-flows`** silences the no-entity-in-any-flow
canary; the `runs_in` placement family has FIVE scoped literals, one per finding group —
**`runs-in/quality`** (unit naming, formula-filled `runs_in`, unlinked units, ambiguous thread
hosts, variant tagging), **`runs-in/unlinked`** (units enumerated but nothing links code to them —
code that truly runs as one unit), **`runs-in/unplaced`** (most components unplaced across the
enumerated units), **`runs-in/entry-hosts`** (self-started entry points left 'Unplaced') and
**`runs-in/messaging`** (a channel no participant's `runs_in` can place). A BARE **`runs-in`**
silences nothing and says so — a family-wide literal switches off five findings on the strength of a
justification about one; the literal **`isolated`** silences the components-wired-to-nothing canary
(see below); the literal **`channel-ends`** silences the one-sided-channel advisory (a channel whose
far end genuinely lives outside the mapped repo); the literal **`channel-payload`** silences the
no-channel-names-a-payload canary (channels that really are untyped); the literal
**`entity-relations`** silences the isolated-entities advisory (a domain whose cards legitimately
relate to nothing — an event log, a settings bag). Never reword prose to dodge a heuristic — record
the exception instead.

Every literal is read **line-leading**, followed by a separator (`:`, `(`, an em/en dash, or a
spaced ` - `) or nothing else on the line — `channel-ends: the consumers are all third-party` — so
a sentence that merely uses the word never silences anything, and a compound that only *starts*
with a literal (`store-front redesign: …`) is not a record either. Element **ids** (`S7`, `UC5`,
`C18`, `root`) are not words, so those still read anywhere in the body: `SF40, SF41: <why>` records
both. And every literal is scoped to its own advisory: recording `isolated` (components) does not quiet `entity-relations`
(entity cards), and `messaging` (no nameable channels at all) does not quiet `channel-payload`
(nameable channels carrying no domain type).

**One escape is still deliberately family-wide, and it reports what it swallowed.** A `UCn`/`SFn` id
covers both granularity signals for its element — one decision, recorded once — so `validate` prints
a line naming the **count** and the **groups** it suppressed: `1 granularity advisory/advisories
suppressed by recorded flow/sub-flow id(s): SF20 (the fused-goal name smell)`. The `runs_in` family
is NOT a second one: its five scoped literals each silence exactly their own group and are reported
the same way (`1 deployment advisory/advisories suppressed by recorded scoped exception(s) …
(`runs-in/quality`)`). Scoping them was the fix for exactly the risk this paragraph describes — the
recorded *why* is usually about a single finding, and a family-wide literal silences the rest. The
line fires on the FIRST suppression, not only on the second — a silence you cannot see is
indistinguishable from having no findings. Neither line can itself be silenced. Read it: if the why
you wrote covered only one of the listed groups, re-read the rest by validating a copy with the
record removed.

**Wire what the prose claims.** `validate` emits one aggregated advisory for components carrying
**no backbone edge and no `messaging` role** — code the model shows connected to nothing. Every view
walks edges and channels (the subsystem arrows, the change-impact ripple, the Deployment view's
process→process topology), so such a component is drawn isolated *however well its `Purpose`
describes what it talks to*: a `Purpose` saying a component "pushes their events to the same broker"
still draws no arrow, because prose is not an edge. Fix it by authoring the edge or adding the
component as a channel publisher/consumer — **never** by having a view infer topology from prose.
Record the literal `isolated` for code that genuinely stands alone. The contract that keeps balance
safe: **balance never gates and only ever re-groups** — grouping is a free, view-only choice
(membership on the child, member lists derived), while the **leaf decision is grounded by E and out
of bounds for balance tooling**: no balance finding may merge or split components to hit a number.

**The hand-off — `coyodex preindex --report`; don't reverse-engineer the JSON.** The build run prints
a one-line summary to **stderr** (heaviest top-level dirs, totals, the GR1/GR2 reminders), but that
summary carries only the top-5 dirs and the whole-repo E — while the harvest plan needs the **weight
tree** and the **per-slice E**, which live only inside the JSON. So there is a read command:

```
.venv/bin/coyodex preindex --report --root <repo> [--depth N] [--top N]   # weight tree + per-dir E + coverage
```

Use it instead of hand-parsing — it reads the file and writes nothing. `preindex --help` is a real
help flag.

**Reconcile E with what it is BOUND BY.** The report says whether the file-count ceiling or the LOC
ceiling produced E, plus the median file size. This matters: on a file-per-UI-component frontend the
FILE cap fires long before the LOC cap, so E counts many tiny files as unit-sized mass and lands
well above the honest altitude. Builds routinely disagree with E by 2–4×, and this report is how you
see why. When you build outside the band deliberately, record the literal `granularity` under a
`Balance exceptions` extras heading with the reason — that is a judgement, and it belongs in the
map, not the transcript.

The JSON shape, so you don't have to guess its keys:

```
{ "tool", "root",                       # provenance
  "weight":   { "path", "loc", "file_count", "churn", "lang", "langs",
                "children": [ …same node shape, sorted by loc desc… ] },   # the nested directory tree
  "symbols":  { "by_name": { "<name>": [ { "file", "line", "kind" } … ] }, "ambiguous": [ … ] },
  "imports":  { "mode", "semantics", "pairs": [ … ] },  # ALWAYS present; `pairs` is filled only
                                         # when --pairs {component:[paths]} was given (else empty,
                                         # with a `note` saying so)
  "granularity": { "expected_components", "band": [lo, hi], "bound_by", "median_file_loc",
                   "per_dir": { "<dir>": E … }, "file_cap", "loc_cap" },   # the leaf anchor (rule above)
  "coverage": { "files_counted", "git_available", "tree_sitter_available",
                "languages_seen_without_extractor", "note", … } }          # what it could/couldn't parse
```

This concretises finding **G1** in
[internal/docs/scaling-to-large-codebases.md](internal/docs/scaling-to-large-codebases.md); the
guardrails above are **GR1/GR2/GR3/GR5** there. The validator's `--check-coverage` (below) is the
verification half — it re-measures the tree independently and never reads this JSON (**GR4**).

**Parallel mode covers HARVESTING ONLY (large repos; serial is simpler and just as accurate on small
ones). Verification is NOT part of it — see "After the trace — every build" below, which a serial
build owes in full.** The build order maps to a fan-out workflow: **parallel harvest → barrier
synthesis → parallel trace.**

> **Scope warning.** Phases 3.5 / test completeness / 4 are NOT part of this section, and a serial
> build owes every one of them. Skip them and the map is built and checked by ONE context — the
> precise blind spot Phase 4 exists to break. Serial mode is exempt from *fanning out the harvest*,
> never from *verifying the result*.

- Phase 1 Harvest (fan out, one agent each): T4 entry points, T2 deps, T5 model, T3
  run/build, T0/Roles reader. Parallel harvest also improves completeness. **Launch the whole
  harvest as one concurrent batch** (all agents in a single fan-out), not in waves — the slices are
  disjoint and use pre-allocated ID ranges, so no agent needs another's output first, and they
  return compact rows (not file dumps) so reading them together is cheap.
  - **"One batch" means one MESSAGE: emit all N agent calls as N tool calls in a SINGLE assistant
    turn.** One message keeps the batch atomic: the slices are dispatched from one decision, so a
    late edit cannot reach half of them. The same rule applies to every fan-out below, not just
    harvest. **What it does NOT buy is speed.** Dispatch latency is the model EMITTING the prompt
    text, at roughly 230-320 bytes/s, so it scales with prompt BYTES and not with agent count. The
    lever is shorter dispatch prompts — put the invariant block in a file the agents read, as the
    skeptic fan-out already does — not turn count.
  - **Pre-size the slices from the pre-index so no slice becomes the critical path.** The whole
    phase ends when the SLOWEST agent does, so one oversized slice stalls the barrier for everybody.
    The pre-index already counts files/symbols per area — aim for roughly EQUAL estimated work per
    slice, and specifically split the entry-points+security harvest **by router / surface** on a
    large route surface (per-kind coverage statements merge cleanly; the coverage sweep catches seam
    misses, so splitting costs no completeness).
  - **Resilience: write a DRAFT fragment early, finalize at the end.** An agent that dies mid-run
    (API outage, machine sleep) loses ALL its reading if the fragment only exists at the end. Write
    incremental progress to `<id>.draft.json` and RENAME to `<id>.json` only when complete — the
    draft suffix keeps a half-written file out of the assemble glob (a partial fragment must never
    assemble). Write it as `<id>.draft.json`, NOT `<your-path>.draft.json` — the fragment path
    already ends in `.json`, and a doubled suffix reads as a draft FOREVER: `assemble` skips any
    path ending `.draft.json`, so a fragment left with that name never assembles at all. The RENAME
    is what makes the work land. The lead probes stalled agents early (a couple of minutes of no
    progress, not a late `ls` sweep) and resumes a dead agent via SendMessage with its draft as the
    continuation point, or relaunches.
  - **Reconcile your slice expectations with E BEFORE launching.** Hand each agent its slice's E
    from the pre-index `granularity.per_dir` — never your own gut numbers. If you deliberately
    deviate (a file-per-class repo where per-dir E under-counts), SUM your slice expectations first:
    when the total sits outside the whole-repo band, record the decision NOW — one line under a
    `Balance exceptions` extras heading containing the literal `granularity` plus the why — not as a
    post-hoc shrug when validate warns. (That recorded token also silences the E advisory, so an
    overridden-but-unrecorded expectation is a drift waved through at every validate.) **Check each
    slice against ITS E, not only the sum.** The recorded-decision rule above fires on the
    whole-repo total, so one slice can run 3× over while the sum stays in band and nothing says a
    word. Where a slice's budget deviates from its E, that is the moment to say why — per slice, not
    per repo.
  - **Never delete draft fragments with a glob while any agent is still running.** `rm -f
    build-fragments/*.draft.json` mid-fan-out destroys the crash-resilience artifact of every agent
    that has not finished. Delete a draft by NAME, after its final fragment exists.
  - **Waiting for the batch (every fan-out phase):** after launching, **wait on the agents'
    completion notifications** — do NOT poll the filesystem with `ls` (a not-ready file reads as an
    error and burns turns). If you must block on a condition, use the **`Monitor` tool with an
    until-condition** — **not** a `sleep` / `until … sleep …` loop, foreground OR backgrounded. A
    backgrounded waiter is no exemption: `until ls …; sleep 45` breaks the `ls` ban whichever way it
    is launched. **`ListAgents` counts too**: polling it to count running agents is cheap, but it is
    the same shape — the barrier already tells you when it closes, and a turn spent asking is a
    turn. (`Monitor` is a deferred tool — run `ToolSearch select:Monitor` once to load its schema
    before the first call, or that first call fails with an `InputValidationError`.) Hand every
    agent an **absolute** fragment output path (`<repo-root>/.coyodex/build-fragments/<id>.json`) so
    it can never land in a subdirectory; `assemble` warns about any fragment left in
    `build-fragments/` that you did not pass in. **The wait itself is a TEXT turn — emit no tool
    call at all.** A keep-alive `echo .` yields the turn no better than ending on text, and it costs
    a full round trip each time; measured waste has run to **22 % of a build's tool calls**. L3
    assertion 10 counts any no-op turn, not just an `ls`. **One barrier means ONE `Monitor`**: stop
    the previous one before starting another, or its events interleave with the new one's and with
    the agents' own completion notifications — three streams for one wait. And the `Monitor`
    **command itself must not be an `ls` poll**: wrapping `for i in $(seq 1 240) … sleep 20` in
    `Monitor` satisfies "use the Monitor tool" in letter while reproducing the exact poll this
    paragraph bans.
    **What the text turn should CARRY.** Emitting no tool call is the rule; saying nothing useful is
    not the point of it. When a returning agent hands you something actionable — a refutation, a
    contradiction between two slices, a lint failure it could not fix — the acknowledgement turn is
    where you write down what you will do with it, and the NEXT turn that has work available is
    where you do it. On one build the lead named a refuted edge at the barrier and did not open the
    file for eighteen turns; every verdict file it needed was already on disk. Verify a refutation
    when it arrives, not when the barrier closes.
  - **Shared state goes in the CONTRACT, never in a per-slice option.** Anything every agent in a
    fan-out must know — the id legend, the sub-flow catalogue, the "do not re-author these edges"
    list — belongs in the copied contract that all of them read. A build whose slice generator made
    the shared-machinery block an opt-in argument passed it to 12 of 14 slices and omitted it from
    two, one of them the slice its own comment called the heaviest in the build. That cost a repair
    round on one slice; **the other was never repaired and its omission shipped into the map.** A
    block that is optional per slice is a block that will be missing from one.
  - **Dispatch the known-longest slice FIRST, in every fan-out.** Launch order is the one lever you
    have over when the barrier closes: a straggler dispatched last holds it for its whole runtime.
    T5 and the security slice are the reliably heaviest in Phase 1; in Phase 3 it is whichever use
    case owns the most sub-flows and the widest "where to look" list. Send those first, the small
    ones last. (L3 assertion 16 watches this.)

    **Order by expected MINUTES, not by item count.** They are not the same number: per-item cost
    varies enough that the batch with the most items is often not the longest. Where a per-item cost
    is known to vary — state-machine and lifecycle work is the reliably expensive kind — weight by
    that, not by rows. Treat it as a tie-breaker rather than a formula.

    **And size the fan-out to the harness's concurrency cap** (~20 agents in one batch, measured).
    Agents over the cap are REJECTED and have to be re-sent, and a bumped slice then closes the
    barrier long after its siblings — a tail that is delay, not work. Merge to fit the cap, or plan
    a deliberate second wave.
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
    - **The T5 owner needs the deps legend to fill `store.dep` — sequence or inject it.** The
      structured store's `dep` is a D-id, and a T5 agent launched in parallel with the deps harvest
      has no D-id universe — it then ships `dep: null` on every entity, silently disabling the
      persistence-coverage rule. Either run the T2 deps slice first and inject its
      datastore/messaging ids into the T5 prompt (`D1=MongoDB, D2=Redis…`), or have synthesis
      BACKFILL `store.dep` from the assembled deps (a `--reconcile` set). The "container but no dep"
      validate advisory is the backstop, not the plan.
    - **Author `states` where the code implements a lifecycle** — an entity with a status
      enum/constants (a subscription's states) gets a `states` machine on its card; a component
      whose purpose lists phases ("5-phase: disabled/deferred/connecting/live/failed") gets one on
      the component. A lifecycle left in purpose prose is unqueryable and rots first. **But author
      it ONLY from a declared state list, and cite THAT line.** A `states` machine is the one claim
      with no per-state anchor, so it is the easiest thing in the map to invent — and the most
      invented, in two recurring shapes: states lifted from docstring PROSE, and a start state
      bolted onto an otherwise-real enum. The `source` must point at the **enum / constants /
      dispatch block that declares the states**, never a docstring or a class header, and every
      state name must be a name that block actually contains. `validate --check-sources` now reports
      state names missing from the cited file — if you cannot cite a declaration, the lifecycle is
      prose, so don't author it.
    - **Large domain models (many entities) — shard the RELATIONS pass, never skip it.** One agent
      can read ~40 entities and author a complete `E↔E` graph; on a 150–200-entity domain it will
      under-author relations and the graph comes out sparse. **The symptom shows up far below that
      threshold, so measure it instead of guessing.** Count the isolated entities after the T5
      fragment lands; if the share is material, shard the relations pass or re-ping the slice, and
      if you carry it, record the count and the why. When the entity count is high, the single T5
      owner still owns the slice but MAY fan the relations pass out **by subdomain** (each sub-agent
      relates the entities within one subdomain + names cross-subdomain targets), then merges. The
      invariant is coverage, not headcount: every entity gets its relations authored. `validate
      --check-coverage`'s isolated-entity count is the check (it is threshold-gated — silent below 5
      entities, below 3 isolated, or at/under 20% isolated — and the plain `validate` never prints
      it).
- Phase 2 Synthesize (barrier, one agent): T1 clusters/dedups all harvest outputs, and (large maps)
  assigns Subsystems — a global graph cut, so it stays at the non-delegated barrier. **Synthesis is
  the final-ID authority.** **Only the dedup/renumber step is the hard barrier — overlap the rest.**
  No trace launches before dedup completes (a trace referencing an id that dedup then renumbers is
  the dangling-ref class this barrier exists to prevent — do not trade that for minutes). But dedup
  itself is fast; the SLOW synthesis work carries no id risk and should run concurrently once dedup
  is done: fan out the **test-completeness agent** and any remaining **deployment/ops backfill**
  WHILE the lead authors the reconcile assignments (subsystem/subdomain/runs_in/bucket). Authoring
  first leaves every agent idle for as long as the authoring takes, and the backfill then runs
  serially after the traces. **Treat this as a launch STEP, not advice** — it is step 1 of
  synthesis, before you author a single rule:

  ```
  1. dispatch the test-completeness + deployment/ops backfill agents      <- FIRST, always
  2. THEN author the reconcile assignments while they run
  ```

  Dispatch those agents before you start authoring.

  **Run every sub-flow name you PRESCRIBE past the naming heuristic before you dispatch it.** A slice
  brief that hands agents `SF20 — Validate and store the token` freezes a fused-goal name into a
  shared id contract: the sub-agents hit the lint warning, correctly refuse to rename (renaming
  breaks the contract), report it in prose, and the same four warnings resurface at the lead's
  `validate` and end up written as exceptions. The lead pays for its own naming twice. Name them the
  way you would name a use case — one goal, no "and" — or expect to record them.

  **Put the gap-fill slice in the SAME batch as the Phase-3 trace fan-out.** Slicing the trace by
  use case structurally guarantees that components off every traced flow get no edges, so the
  gap-fill is predictable, not a surprise: discovering the edgeless set only after the trace agents
  finish costs a serial dispatch, plus rework of anything written too early. Seed that slice from
  the post-synthesis edgeless set. Harvest agents may use per-slice *provisional* ids; synthesis
  assigns the final canonical ids here. This is the safe place to renumber: Phase 1 produced only
  nodes (no edges yet — those are Phase 3), so the only intra-slice references to fix up are
  `entry_point.component`, `entity.subdomain`, and the `E↔E` `relation.target` / `FK→En` markers.
  Because collisions are resolved before any edge is traced, a range overlap between two harvest
  agents can never reach the backbone; `assemble`'s duplicate-id error remains the loud backstop if
  a stray collision slips through. **Right after synthesis, run `coyodex validate
  --check-coverage`** — add **`--json`** whenever you need the FULL finding lists: the human report
  elides long id lists (`C1, C12, … +8 more`) and clips trigger prose, and `--json` emits every list
  whole, so recovering a hidden id never needs a throwaway script. Its unreferenced-files list is
  the mechanical harvest-completeness sweep (a source file no component claims = a slice-seam gap);
  an improvised spot-script covering one directory misses whatever it does not walk. **This is also
  the front-door verification moment** (the cross-check rule under *Use cases*): T4 now exists, so
  reconcile the drafted use-case list against the harvested **external** entry surface in both
  directions — a use case with no entry point behind its trigger (stale docs), an
  externally-triggered entry point no drafted use case claims (missing use case or dead surface) —
  BEFORE the trace fan-out, so Phase 3 traces the corrected list, not the draft. (The entry-surface
  advisory itself stays quiet until flows exist; during Phase 3 it fires on every not-yet-traced
  surface and **drains as traces land** — a mid-trace wall of these warnings is expected, not a
  defect. Only what survives the full trace is a finding.) **Mint the BLOCKS here too** (`blocks[]`,
  the T7 decision grouping) — same moment and same reason as `CAP`: the post-trace rule fan-out is
  one agent per block, so the blocks and their id ranges have to exist before it starts. Cut them
  from what the product DECIDES, not from what the code is shaped like: an area a product person
  would argue about ("who may cancel an order", "how a plan limit is applied"), 8-12 of them on a
  map this size. A block is a `Group` like a capability, so it carries `name` + `purpose` (the "what
  this area decides" line), and `source` only if the area has one honest home directory — a block
  groups DECISIONS, not code, so the viewer never treats that anchor as a file's owner. `label` and
  `tech` are blocked on it, as they are on a subdomain. Leave `rules[]` empty: it is written after
  the trace, when the flows exist to sweep. **Also assign each component's `subsystem`, each
  entity's `subdomain`, each use case's `capability` and its trigger `entry_points`, each
  component's `runs_in`, and any dep `bucket` fixes here — as a `--reconcile` file, NOT a
  hand-script.** Synthesis owns the finalized ids and has just seen the harvested `deployment[]`
  units, so this is where the grouping and the code↔process link the Deployment view needs get wired
  — no later phase does it, so if synthesis skips it the view ships empty. **The two behavioral
  assignments have no other home.** `CAPn` is minted at synthesis, and `EPn` does not exist until
  `assemble` mints it from the harvested T4 rows — so neither can be written in the behavioral
  fragment, which was authored before either existed. Reconcile is the only mechanism, and it is
  also what makes them survive: a re-assemble re-applies them, where a hand-patch of the built map
  is discarded by the next one. These live in a declarative **`.coyodex/reconcile.json`** (kept
  OUTSIDE `build-fragments/` so the fragment glob does not sweep it) — **generate it with `coyodex
  reconcile`, below; hand-author it only on a map small enough to type.** The shape it produces:
  ```json
  { "set": [ {"ids": ["C1","C2"], "subsystem": "S3"},
             {"ids": ["C40","C41"], "runs_in": ["worker"]},
             {"ids": ["E7"], "subdomain": "SD2"},
             {"ids": ["D5"], "bucket": "Data & storage"} ] }
  ```
  `coyodex assemble <fragments…> --out .coyodex --reconcile .coyodex/reconcile.json` applies it AFTER
  the fragment merge, every time — so a re-assemble never loses the assignments (a bespoke Python patch
  edits the assembled map, which the *next* assemble discards). **`--reconcile` is part of the standard
  build assemble from here on**; an assemble without it silently reverts every assignment (assemble
  prints a note if a `reconcile.json` is present but unpassed). Derive `runs_in` by reading the deploy
  manifests, never a component-id-range formula (see *Deployment & topology*); `validate` warns when
  `deployment[]` units exist but no component sets `runs_in`, and flags a formula-filled `runs_in`.
  Keep fragment argument order stable and author the reconcile ids against the assembled ids (dedup
  survivors are first-occurrence-in-argument-order, so reordering fragments can shift surviving ids).
  - **A dedup decision belongs here too.** `coyodex fix dedup-edge --map .coyodex/project-map.json
    --repo . --accept-suggested --to-reconcile .coyodex/reconcile.json` writes its choices as
    `keep_edges` instead of editing the assembled map. **`--to-reconcile` needs a decision** —
    `--accept-suggested`, or explicit `--keep` tokens after reading the listing (run it without
    `--to-reconcile` to see that listing first). On its own it is refused. Editing the map does not
    survive: the next assemble restores every duplicate the fix removed. A map that cannot be
    rebuilt from its fragments has quietly stopped being generated.
  - **Generate the file — `coyodex reconcile`.** Count IDS, not rules: a file of 25 rules can carry
    187 hand-typed ids, and "25 rules" reads as small. There is deliberately NO hand-authoring
    threshold: a size threshold is what a build reads as permission. The file wants explicit id
    LISTS, and on any real map that is hundreds of ids nobody types correctly. Write RULES against
    the fact you actually know — the source path — and let the tool resolve them into ids. **Point
    it at the FRAGMENTS**: you are mid-build, so the map does not exist yet, and it does not need to
    — `reconcile` merges the fragments through the SAME code path `assemble` does, so it sees the same
    ids and the `(id, source)` pairs the rules match are the same either way. **`EPn` is the one id
    family the tooling mints rather than an agent authoring it, and it is order-independent but NOT
    add-stable**: harvesting a new surface that sorts before an existing one shifts every number after
    it, which re-points a use case at a different front door while the id still resolves. You do not
    have to remember this: `reconcile` WITNESSES each entry point with the anchor it had when the file
    was written — `{"id": "EP1", "source": "orders.py:9"}` — and `assemble` refuses a file whose
    witness no longer matches, naming both anchors. A bare `"EP1"` is still legal and buys no
    protection, so let the tool write the file.
    ```
    .venv/bin/coyodex reconcile --rules rules.json --fragments .coyodex/build-fragments/*.json \
                                --out .coyodex/reconcile.json [--dry-run]
    ```
    (`--map .coyodex/project-map.json` instead, when re-assigning on a map that is already built.
    Mid-build, `--map` is a trap: the reconcile file is an INPUT to `assemble`, and `assemble` is
    what writes the map, so demanding a map first is a circle with no way in. If the command says
    the map is not found, you wanted `--fragments`.)
    ```json
    { "rules": [ {"source_glob": "mee6/plugins/*",     "subsystem": "S12"},
                 {"source_glob": "gateway/**",         "runs_in": ["gateway"]},
                 {"ids": ["E7","E8"],                  "subdomain": "SD2"},
                 {"ids": ["UC1"],                      "entry_points": ["EP3"]} ] }
    ```
    It reports **every rule that matched nothing** instead of silently emitting an empty assignment
    — which is the whole point: a hand-rolled generator reports the assignments it *emitted*, and
    nothing checks those ids against the map. Output is an ordinary reconcile file, so `assemble
    --reconcile` stays the one code path that writes. Later rules win on the same (element, field),
    so a broad rule can be followed by a narrow override.
- Phase 3 Trace (fan out, one agent per use case; large maps may instead fan out one agent per
  subsystem — bounded context — then a non-delegated reconcile traces the cross-subsystem seams).
  **Trace EVERY use case. The target is 100 %.** An untraced use case is indistinguishable from a
  phantom one — the map gives you the same silence for "we ran out of time" and "this feature does
  not exist", and those need opposite responses. Do not reach for a coverage rule that redefines the
  shortfall as correct. Closing a large trace gap costs real tokens — on the order of a tenth of a
  build — and it is still cheaper than a map that cannot say which silence it means. Nor are the
  leftovers cheap: they are usually the CRUD variants, but a variant with no traced sibling is new
  ground, and each trace is its own agent context, so nothing is carried over. Where budget
  genuinely runs out, the shortfall is **reported as debt** (`use_cases_untraced`). **There is
  deliberately NO "recorded as deliberately untraced" escape** — the no-T6-flow advisory is one of
  the few with no way to record it away, because an untraced use case is a claim with nothing behind
  it and the two honest remedies are both cheap: trace it, or drop it. Where a trace would truly
  duplicate a sibling, check whether the two are really ONE use case (the one-actor-one-goal test)
  rather than leaving one untraced. Each trace agent produces its use case's **T6 flow** (the
  ordered `from → to` steps — **including the flow's central entity touches as `C→E` steps**, the
  entity-steps rule under T6) and also records the **`C→E` edges** for the components in its slice —
  the entities they persist/write/read by **direct** use. Steps and edges carry different halves of
  entity usage: the edges are the structural aggregate (every entity a component touches, in any
  scenario); the steps are the behavioral instance (THE entity this scenario is about, at its exact
  line) — the `Used in UC` view and line-level diff impact derive from the steps, so edges alone
  leave the domain model untraceable. This is *additional*: the `C↔C`/`C↔D` edges remain the primary
  output and must stay complete (every dep wired, the component graph not sparse). **Size the trace
  fan-out so no agent becomes the straggler**: heaviness is predictable up front (a slice's use-case
  count × its entry-point/component counts), so an agent carrying too many use cases holds the
  barrier for everybody. Split a heavy slice into two agents at LAUNCH, **always at use-case
  boundaries — never split one use case's flow across agents** (a flow traced by two contexts loses
  coherence; per-agent SF ranges + cross-fragment `--ids build-fragments/` handle any shared
  sub-flow between them).
  **The copyable contract is
  [method/templates/trace-contract.md](method/templates/trace-contract.md)** — hand every trace agent
  that file's contents, changing only the «angle-bracket» slots. **Get it with the verb:**
  `coyodex contract trace > <scratch>/trace-contract.md`, then fill them in
  place; a `Read` followed by a `Write` is one keystroke from a rewrite, and the verb prints only
  the agent's half, so the lead-facing header cannot travel with it. This was the largest fan-out
  with no contract of its own, and the rules fan-out shows what that costs: composed from memory, it
  told eleven agents to author a field they must never author, which lint treats as blocking.
  Trace-prompt discipline — what the contract carries, here so you can see what you hand over:
  - **Prescribe likely sub-flows in the prompts.** The lead can usually see from the use-case list
    which machinery is shared ("UC10 and UC13 walk the same tool-call path — EXTRACT it as a
    sub-flow") — say so explicitly; the duplication detector is the safety net, not the plan. **Do
    NOT blanket-ban sub-flows** ("no subflows" in every trace prompt) — that contradicts this rule
    and forgoes the cross-flow consistency sub-flows buy. Ban them for a genuinely independent flow,
    never as a global default; where machinery repeats across ≥2 flows, prescribe the `SFn`.
  - **Name `En` as a valid step endpoint in the prompts, with a worked example step** — e.g. `6a. C5
    → E2 : upserts the Membership document @ repo.py:155` — and require each flow's 1–2 central
    entity touches. Prompts that channel ALL entity mentions into the edges array ship a domain
    model with zero flow traceability, and every gate stays green. The callee's operative read/write
    line is one hop from the call site the agent already read for the calling step's `where`.
  - **Assign each trace agent an `SFn` id range** (SF1–9, SF10–19, …), exactly like the per-agent
    component id ranges, so parallel extractions never collide.
  - **Show the sub-flow SHAPE in the prompt** — `{"id": "SFn", "name": "<display text>", "steps":
    [...]}`. A flow's display text is `title` but a sub-flow's is **`name`** — agents write
    `subflows[].title` by analogy and burn a lint round each (the loader now accepts `title` as an
    alias, but the prompt should still show the canonical shape).
  - **A step MAY reference a sibling agent's sub-flow** (the id ranges make it unambiguous): pass
    `--ids build-fragments/` (a directory scans every fragment) so the reference resolves at
    lint time instead of forcing the agent to duplicate the shared trace inline. The sub-flow
    refcount nudge ("referenced once — consider inlining") is ADVISORY on the fragment channel:
    the other reference may live in a sibling fragment, so never rewrite just to silence it.
  - **A named queue/topic in the trace is a `messaging` row** — when a step or edge goes through a
    named channel (`JOB_QUEUE`, a per-org pub/sub channel), record the catalog row (name, broker
    dep, publishers, consumers, payload) alongside the `C→broker` edge — the edges on their own
    leave the catalog empty.
  - **A `C→E` `reads` edge — or entity step — requires the entity TYPE at the site** — a function
    operating on a string/field extracted from an entity is not reading the entity (the
    false-reads class the grounding pass keeps refuting).
  - When the lead has assembled a legend or an earlier map, pass `--ids «legend»` to each agent's
    `lint-fragment` self-check, so a plausible-but-invented element id dies in the agent's own turn.
    **Pass the legend as a FILE PATH** (`--ids path/to/legend`), never inline as `--ids "$(cat …)"`
    — a whole-map legend overflows the shell arg limit. The legend should list the full id universe
    **including `UC`/`SF`/`HP` ids** (or just pass the assembled `project-map.json`), so a trace
    fragment's flow `uc` values resolve; `lint-fragment` now tolerates a legend that omits a whole
    namespace (it can't adjudicate one it doesn't cover), so a reduced element-only legend no longer
    false-flags `uc` — but a complete legend still catches an invented one.
  - A **return-direction step** usually has no invoking line of its own: set `no_call_site: true`
    (or anchor the callee's `return` statement when that aids drilling) — either is fine; silence is not.
  - **Name the three overclaim shapes the skeptics keep refuting** — they are predictable enough to
    prevent in the prompt instead of paying for later, and between them they account for most
    refutations: (1) **transitive attribution** — a component calling a first-party wrapper credited
    with the external call the *wrapper's owner* makes; (2) **ownership overclaim** — a controller
    that calls `.save()` credited as the system of record when the real upsert lives in the
    repository/model component; (3) **constructs ≠ persists** — a storage/client factory recorded as
    writing to the stores it only *builds clients for*. In all three the rule is the same:
    **attribute the edge to the component whose own code contains the operative line**, and if the
    line you found is a call into another component, the edge belongs to that one.
  - **Fill the `messaging` catalog from the SAME line that proves the edge.** The catalog is the
    weakest-quality area measured — wrong brokers and duplicated rows. A catalog row is a claim like
    any other: its `source` is the line that DECLARES the channel name, its `broker` is the dep that
    line connects to (not the one the component happens to use elsewhere), and a channel already in
    the catalog is never added twice under a second spelling. **NAME THE OWNER in the slice brief.**
    A rule that stays in this doc and never reaches the dispatched contract has no effect: several
    agents each told to record the same channel row will each comply, in their own spelling, and
    `assemble` then hard-fails on the conflict. A fragment that lints CLEAN on its own proves
    nothing here — a cross-fragment conflict is invisible per fragment by construction. One fragment
    owns each catalog row; the others reference it.

### After the trace — EVERY build (serial included)

The four steps below are **not** parallel-mode-only. They run on every build; parallel mode only
changes how many agents do the work (a serial build still FANS OUT for the T7 rules and for Phase 4
— fresh context is the point, not concurrency). See the scope warning at the top of parallel mode.

- Phase 3.5 Re-balance reconcile (lead, not delegated — runs ONCE, after the trace). The grouping was
  cut at Phase 2 **before any edge existed**, so re-check it now against the real graph: run
  `coyodex balance` and reconcile each finding — apply a Drilling-deeper operation (nest / promote /
  flatten) via a Direct map change, or record a one-line justification under the model's
  `extras` "Balance exceptions" heading. The **sparse-root fix is judgment-only** (no proposal
  machinery exists for it — the product-area-first guidance drives it); the split proposals are
  starting points, not facts. Exit criterion: `coyodex validate` emits no balance warning that is
  neither fixed nor justified. This step is not part of the per-write validate → audit → render
  invariant; maintenance re-surfaces imbalance for free through validate's always-on warnings.
  `finalize` now runs `balance` itself as an INFORMATIONAL leg and records what it found, so a
  skipped Phase 3.5 and a passed one no longer read the same in the report. That leg is a trace,
  not a substitute: it never gates, and it does not reconcile a finding for you.
- **T7 Business logic (fan out, one agent per block — after the trace, it needs the flows to sweep
  against).** The map has a home for DATA (entities), SEQUENCE (flows), STATES (lifecycles) and
  STRUCTURE (components, edges) — and none for the DECISION the code makes, which is exactly the
  part a reader calls "product-specific". Each agent gets ONE block (its `name` + `purpose`), the
  map, and its own `BR` id range (BR1–19, BR20–39, … — one contiguous range per agent, exactly like
  the trace fan-out's `SFn` ranges, because two agents minting `BR7` is a hard `assemble` failure).

  **One block per agent is the rule, and bundling is allowed only when you say what it costs.** A
  build gave four of its five rule agents two or three blocks each (R2 got BLK4+BLK5, R4 got
  BLK6+BLK11+BLK10) and its `BR` ranges stayed contiguous, so nothing failed. What it spent is the
  property the fan-out exists for: fresh context PER BLOCK. An agent holding three blocks reads the
  third through whatever the first two left in its window, which is the same reason Phase 4 uses
  fresh-context skeptics rather than one skeptic with a long list. Bundle when the block count
  exceeds the harness's agent cap, or when two blocks are genuinely one decision area; record the
  bundling and its reason under `Balance exceptions` so the next build can tell a deliberate
  bundle from a lost one.
  **Show the rule SHAPE in the prompt** — a nested `sites[]` is more novel than anything the trace
  agents write, and the sub-flow fan-out learned this the expensive way:

  ```json
  { "rules": [ { "id": "BR1",
                 "name": "<the SHORT title — a few words a reader scans>",
                 "statement": "<ONE decision, product language, naming no component>",
                 "access": false,
                 "risk": "<what is AT STAKE if this decision is wrong or absent>",
                 "confidence": "verified",
                 "sites": [ { "where": "path/to/file.py:88",
                              "why": "<what this line does FOR the rule>",
                              "no_call_site": false } ] } ] }
  ```

  **`name` is the rule's TITLE** — a few words ("Owner-only cancellation"), the way a use case has a
  name beside its trigger→outcome sentence. It is REQUIRED and schema-enforced: without it a list of
  rules is a wall of prose with nothing to skim, and every breadcrumb truncates one mid-word. Name
  the DECISION, then state it in full in `statement` — a `name` that is just the statement cut short
  is not a title. `access` is `true` when the rule governs WHO MAY DO WHAT; `confidence` is
  `verified` (read in the code) or `inferred` (deduced). **`risk` is REQUIRED on an `access` rule**
  — it is the one thing a `security[]` row carried that a statement, a site and a `why` between them
  cannot say: not what the line does, but what its LIMIT costs. The Security & auth table renders it
  as its own column, and **`lint-fragment` FAILS on an `access` rule that leaves it empty** — as an
  advisory it changed nothing. Those seven keys are the WHOLE authored surface — the full field
  semantics are in `method/model.md`. **`block` is NOT in the fragment** (see below). The agent
  writes `«repo»/.coyodex/build-fragments/«agent-id».json` itself and returns that path plus a
  one-line inventory, under the same rule as every other fragment (never inline it). **`access`
  matters beyond display**: it is what makes a rule part of the auth surface the eval gates on, and
  what the security table folds onto — a rule about who may do what and `access: false` is a
  silently missing security row.

  **One rule = one decision.** Several sites only when it is the SAME claim enforced in several
  places. Two claims joined by "and" are two rules.

  **The sharp test: could a product person have decided otherwise?** "Own connection first, else
  oldest shared" passes. "If the list is empty, return early" does not — that is a mechanical
  detail, and filling the layer with them is how the decision view stops being worth opening.

  **Nothing unsupported.** A rule must be reconstructible from the lines its sites point at, with no
  clause added. The failure shape is a sentence that reads true, sitting under a real anchor that
  shows only half of it. If the second half is real, anchor it too; if you cannot find it, cut the
  clause.

  **Sweeping a rule's sites.** Start from the code the BLOCK is about, not from the rule (a rule's
  components are derived FROM its sites, so "the anchors in the rule's components" is a circle).
  Take the components that own that area with `coyodex dump` (`--members` for a subsystem's members,
  `--record` for one element's stored record — a component's `files`, a use case's flow steps —
  `--edges` for a node's backbone edges), and read the anchors the map ALREADY holds in them: the
  flow-step `where`s, the edge `where`s, the security sources. That is a median ~11 candidates per
  rule on a real map. Read code only where none of them fit. Anchor the TRUE OPERATIVE LINE
  even when a different line would join a flow step: **the step link is a readout, never a target.**
  A site chosen because it lights up a use-case-step row is a false claim about where the decision
  is made, and it is invisible on screen — the row looks better, which is the whole danger.
  `validate` refuses a site that names a whole file, and flags one that points at a definition
  header, an import, a comment or a blank line.

  **A site with no single line is `no_call_site: true` and no `where`** — enforced by construction
  (a type, a schema constraint, a config-wired guard). It is a declared absence, not a gap, and it
  is the honest answer when there is no line to point at. Do not invent one.

  **Fusion is preferred to splitting. Synthetic, not granular.** Report rules-per-block when you are
  done. A block whose rules are nearly all single-site is the signature of a flow-step list wearing
  rule clothing — fuse it. The shape to hold is roughly 10 blocks and ~55 rules on a map of this
  size: near 5 rules per block. A drift toward one rule per anchor is a FAILURE even when every rule
  is verified, because the reader is back to reading the flows.

  **`block` is assigned via `reconcile`, never in the fragment** — `BLK` ids are minted at synthesis
  and a re-synthesis that renumbers them must not silently re-point every rule (the same reason
  `capability` and `entry_points` go through reconcile).

  **Everything else about a rule is DERIVED and there is no field to write it in:** which components
  enforce it, which use-case steps it lands on, which entities it touches, and whether it has been
  swept. Do not describe them in prose either — the views compute them, and a prose copy is a second
  answer that will disagree. If you find yourself wanting a field for one of them, stop: that is the
  design being wrong, not the map.

  Exit criterion: `coyodex lint-fragment` clean per fragment, then at the lead's `validate` the
  **sweep worklist** — anchored flow steps that read like a decision no rule covers — is empty or
  fully recorded under the `Sweep debt` extras heading (`coyodex record --map
  .coyodex/build-fragments/extras.json --heading "Sweep debt" --line "<the step's anchor>: <why>"`
  — name the FRAGMENT, or the next assemble discards the record). **`--line` REPEATS, and
  `--lines-from <file|->` reads a batch** — one process, one write, and every line shape-checked
  before anything is written. Every `record` example in this file used to show exactly one `--line`
  and `--lines-from` appeared nowhere, so a build spawned **40 processes for 40 lines**. `record`
  also SEEDS the extras fragment when the path does not exist yet and prints a note saying so, so
  never `echo '{"extras": []}' >` it first: that is a truncating redirect one later run away from
  wiping a populated file.

  **A step is covered two ways, and the second one is why you never anchor a decoy.** By ANCHOR: a
  site lands on the step's line, or inside the same function. Or STRUCTURALLY: a rule is enforced in
  a component the step NAMES. The second exists because a step's `where` is the CALLER's line
  (`C1 → C2 : checks the owner` anchors where C1 calls C2) while the decision lives inside C2 — a
  different file, where no anchor link can ever exist. Without it, "the worklist is empty" would be
  unreachable by honest anchoring and the only route to a clean `validate` would be a decoy site on
  the step's own line. Anchor the operative line; the worklist will clear.

  **What the worklist proves, and what it does not.** It catches decision-shaped code nothing
  claims. It does NOT prove the sweep was exhaustive: it reads the wording of ANCHORED steps only,
  its vocabulary is a heuristic with known-incomplete recall, and one rule in a component clears
  every decision-sounding step naming that component. Treat an empty worklist as "nothing obvious
  was left", not as "done".
- Test completeness (one agent, after the Phase 3 trace — it needs the finished inventory + flows).
  Walk the assembled map (use cases, T4 entry points, T5 entities, failure modes, critical-path
  branches) and for each ask "is there a test that exercises it?", emitting the risk-ranked gap table
  `tests[]` + `tests_note` (the **Test completeness** section above carries the full recipe — don't
  duplicate it). **Read-only by default:** build the table by *reading* tests, mark every row
  **inferred**, and set `tests_note` to state the suite was not run. Running the suite with coverage
  (upgrading rows to **verified**) is the opt-in upgrade described in that section — never run an
  unknown suite by default. The table is always produced; it must never ship empty.
- Phase 4 Adversarial verify (fan out, **fresh context**). After the map validates and `coyodex
  audit` runs (fix any blocking `why:`-ref contradiction; reconcile the read-before-create / actor
  advisories — **fix each, or record it under an `Audit exceptions` extras heading** as
  `<check-name> <Id>: <why>`, e.g. `read-never-created HP12: the token is written off-path by the
  OAuth provider; the Happy Path starts after sign-in`. A recorded line silences exactly one
  `(check, id)` pair — never a family — and `audit` REPORTS what it silenced, plus any line that
  matched nothing), take the audit's **L2 grounding worklist** and disprove it against the code.
  **The same command also cuts the READ fan-out.** Beside the claims files it writes `prose-N.json`,
  every reader-facing prose field in the map, each batch carrying the instructions with it. Dispatch
  those to a CHEAP model (Haiku is enough; the whole map is roughly 35k tokens, about eight cents)
  and fold what comes back into the audit report as advice. That fan-out judges exactly two of the
  six writing rules — is there a word the reader will not know, and did a short sentence buy its
  shortness by dropping the specific — because the other four are already counted by `validate` and
  the lead has those numbers. **It never gates anything, and two runs may differ**: a model reading
  prose is not the deterministic check the rest of this step is, and a finding that says "this box
  is hard to read" is worth having without being worth blocking on.

  **Write the per-theme batches with the tool, not a hand script:** `coyodex audit <map> --batches
  .coyodex/verify --cap 40` emits one claims file per theme, most-dangerous-first, each claim
  carrying its `anchor` and `detail`. A hand-rolled batcher drops the anchor, and the claims then
  reach the skeptics as a bare `C140 calls C78` while the prompt promised them a `path:line`. (read
  it with `coyodex audit --json` — the machine-readable `{findings, worklist, themes, theme_counts}`
  payload built for this batching step; never regex-parse the human report; the same rule covers the
  model itself — look an id up with **`coyodex dump`** (`--id` resolves kind/name/source/members,
  `--record` the full stored record, `--edges` a node's in/out backbone edges, `--members` a group's
  members — a subsystem, subdomain, capability or block) rather than hand-parsing
  `project-map.json`, which is how a build ends up with a throwaway script that reads a field the
  schema renamed. **`dump` also reads a build FRAGMENT**, so use it during Phases 1-3 too instead of
  scripting over `build-fragments/*.json`. **To see what an edit actually did, keep the map you are
  about to replace and run `coyodex diff <old-map> <new-map>`** — rows added, dropped and changed,
  with the fields that moved. It is the only row-level before/after signal there is: the assemble
  digest is one line, and a count gate cannot see a row moving between two arrays. Its scope is two
  assembles of the SAME work — before and after a `fix`, or one round of edits — never two
  independent builds, which agree on neither numbering nor wording.) **Batch on the payload's own
  `theme`** — every worklist item carries one from a closed, most-dangerous-first set (`security`,
  `rule`, `dep-usage`, `ownership`, `persistence`, `messaging`, `lifecycle`, `cadence`, `backbone`)
  and **`security` holds every `access: true` rule site** as well as the `enforces`/`encrypts`
  edges, so the batch that sorts first really is the access-control batch — send the multi-skeptic
  majority vote there. (A rule site that is NOT an access rule carries `rule`.) `theme_counts` gives
  you each group's size, so the batches fall out of the data instead of being guessed. **Batch by
  theme/risk, don't spawn one sub-agent per claim** — the worklist routinely has 100+ items; group
  the claims into themed skeptics (e.g. security/auth, money, core data-flow, inferred dep-usage),
  one fresh-context skeptic per batch — hand each one
  [method/templates/skeptic-contract.md](method/templates/skeptic-contract.md), the copyable
  contract, rather than composing one from this section. **Copy it with a command, not by reading
  and retyping** — `coyodex contract skeptic >
  <scratch>/skeptic-contract.md`, then fill the «angle-bracket» slots. The instruction on its own
  does not stop this: a `Read` followed by a `Write` is one keystroke away from a rewrite, and a
  verb is not. The verb also prints only the agent's half: a build once filled this template with
  one text replacement and sent the WHOLE file, so all ten skeptics read the lead's instructions as
  their own and four were told to open a claims file that does not exist. For the riskiest claims run **N skeptics + majority vote — with N ODD, and N ≥ 3.**
  **Where the cut falls: the WHOLE `security` theme, every batch of it.** "the riskiest claims
  (auth, scoping, encryption)" and "the `security` theme" were both written here and they are not
  the same instruction, so a build had to guess: one triple-voted 80 of the security theme's 123
  claims and single-voted the other 43, and 8 of its 10 applied refutations then came from
  single-vote batches. Before spending the budget, weigh what the vote actually bought on that run:
  across 160 redundant rows the three skeptics disagreed on the verdict ZERO times and on the
  evidence anchor once. Unanimity is a real result — it is the only evidence that the
  highest-risk claims are not one agent's blind spot — but it is not discovery, and if the budget
  is tight a second single-vote batch elsewhere finds more. Two skeptics cannot form a majority, and a tie broken by the lead reading
  the code is the build-context blind spot the fresh-context rule exists to break, reintroduced at
  the last step. Give each row a `skeptic` id so two independent agreements are never mistaken for
  one vote counted twice. And note what a tie IS: `grounding write` files it under `unverifiable`,
  which is right for the count and wrong for the reader, so run **`coyodex grounding report`** to
  see ties listed apart from the claims a skeptic actually called unverifiable.
- **Re-verify every REFUTATION against the code before applying it.** A refutation rewrites the map;
  a false one corrupts it silently and no gate can tell the difference. The majority vote is a
  filter, not a verdict: on a live build three of one batch's adverse findings were FALSE, the
  highest-risk claim among them, and all three were caught by the lead's own initiative rather than
  by any step written here. This is that step: open the file, confirm the refutation, THEN
  reconcile. Rejecting a refutation is a normal outcome — say so in `grounding.note`.
- **Cap each batch at ~40 claims** and split an oversized theme into two skeptics rather than one
  long-running one — an oversized batch becomes the phase's critical path, and more, smaller
  skeptics also mean fresher context per claim, so this trades nothing away. **When the worklist
  exceeds what you can ground, TRIAGE ON THE RECORD — never silently.** The worklist is already
  ranked most-dangerous-first, so working it top-down is the right call; what is not optional is
  saying how far you got: at a typical refutation rate an unchallenged remainder of a thousand
  claims plausibly holds a hundred wrong ones, and a number reported only in chat evaporates. Record
  it in the model's **`grounding`** object: `claims_total` (the worklist size), `claims_challenged`
  (how many got a verdict), then the SPLIT of those verdicts — `claims_confirmed` / `claims_refuted`
  / `claims_unverifiable` — plus a `note` saying which claims were prioritized. **How a partial pass
  is recorded: `--partial`.** `grounding write` refuses a worklist claim with no verdict, because
  "we stopped at the top slice" and "a batch of skeptics died on the way home" look identical from
  inside the tool. `--partial` is you saying which one it was — pass it with the FULL pinned
  worklist and the verdicts you have:

  ```
  .venv/bin/coyodex grounding write --worklist .coyodex/verify/worklist.json \
    --verdicts .coyodex/verify/*.json --partial \
    --note '319 of 1,608 challenged: ranked top-down, stopped at the theme budget' --out …
  ```

  **Pass the note with `--note-file <path>`, not inline, on any re-run.** The record is re-measured
  after every late fix, and each re-run had to re-supply the whole note: one build retyped ~1,900
  characters three times through the shell, mutating it between pastes, and a note carrying a quote
  or a backtick would not have survived at all. `--keep-note` reuses the note already in `--out`
  when nothing about it changed.

  **Then quote the `NOTE FACTS` block `write` prints, rather than remembering a number.** It states
  the verdict rows, the distinct skeptic labels, the confirmed / refuted / unverifiable / tied
  split, and how many superseded claims had been CONFIRMED — each one a settled verdict the build
  overrode. A note is free prose in a permanent record and in the commit message, and nothing
  checks it: one said "Eighteen fresh-context skeptics" about a build that dispatched 17 and
  produced 20 labels, and "Four superseded claims had been CONFIRMED" where the true count was 11,
  leaving seven overrides undisclosed. Both numbers were on screen when the note was written.

  **`coyodex grounding report` lists what `write` only counts.** Its `ADDED SINCE THE PIN` section
  names the claims the shipped map carries that the pinned worklist never held, and
  `REFUTED BUT NOT SUPERSEDED` names refuted claims the map still carries verbatim — the count
  appears on the report's first line AND its last, so neither a `head` nor a `tail` can lose it.
  Read both before writing the note: a build that read neither shipped two refuted claims and
  hand-diffed the post-pin set in python to find what the section would have listed.

  `claims_total` keeps the full 1,608 and `claims_challenged` says 319, so the unchallenged
  remainder is visible in the record itself rather than in prose. The `--note` is required (the
  counts say how many, never why those), and passing `--partial` on a pass that turns out to be
  complete is refused too. **Never shrink the `--worklist` file to what you challenged** to get past
  the refusal: that makes `claims_total` the reduced size, and a 319-of-1,608 pass ships looking
  like a complete pass over a small map. Record the split even when it is boring: without it
  "challenged" is the only number, and a reader cannot tell how many claims actually HELD UP —
  `total 399, grounded 399, refuted 3` reads as "399 held up AND 3 were refuted out of 399".
  `validate` BLOCKS on counts that do not add up
  (`confirmed + refuted + unverifiable == challenged`). `claims_unverifiable` is for the honest third
  outcome —
  the code could not settle the claim either way — and folding it into either of the others is what
  makes the record lie. `validate` warns when coverage is thin, and warns when a map with a real
  claim surface carries no `grounding` record at all: an unchallenged map and a fully-verified one
  otherwise look identical in every view and pass every gate the same way. **GATE — run the free pass BEFORE you dispatch a single
  skeptic, not after the barrier:** `coyodex validate --check-sources` (and `coyodex anchor-drift
  --map …` with NO `--verdicts`) flags every call-site anchor pointing at a line that cannot act — a `def` header, an
  import, a comment. That is deterministic, needs no skeptics, and on live maps it reproduced what
  the skeptics found by reading; spend the skeptics on what it cannot decide. Stated as prose in
  this paragraph it was read as advice and skipped: one build ran `anchor-drift` exactly once, at
  the very end and WITH `--verdicts`, and paid three separate skeptics to report drifted anchors by
  hand. It is a gate with an order, not a suggestion. Keep the split WITHIN
  a theme (related claims still travel together). Each is told to *disprove* the claim, and to use
  the THREE-WAY verdict honestly: **refuted when the code contradicts the claim; `unverifiable` when
  the code cannot settle it either way**. Do not tell a skeptic to "default to refuted on doubt" —
  that sentence and the `unverifiable` bucket are the same instruction pulling opposite ways, and
  the bucket is what loses: a third verdict nobody can reach is a record that cannot be honest. This
  is the *breaking* twin of the parallel *build*, aimed at falsification. **Fresh context is the
  whole point** — a verifier that sees the build reasoning inherits its blind spots. Each skeptic
  also reports the ONE `file:line` where the operation **actually** happens (the true call site); a
  drifted anchor does NOT refute a true relationship (grounding truth is separate). Collect the
  skeptics' output as the **verdicts file** `anchor-drift` consumes: `{"grounding": [{"claim": <the
  worklist claim string>, "grounded": true|false|"unverifiable", "evidence": "path:line"}]}` — one
  row per claim (or per vote when N skeptics run), `claim` matching the worklist text verbatim so
  the tool can pair it, `evidence` the true call site.

  **LINT the verdicts as they land, at the barrier — `coyodex grounding lint`.** It is the one
  mechanical check on the pass and it goes unrun because nothing named it: on one build it appeared
  zero times in the transcript, zero times in this file, and zero times in the skill, while the lead
  hand-wrote half of it twice.

  ```
  coyodex grounding lint --verdicts .coyodex/verify/verdicts-a.json \
                         --verdicts .coyodex/verify/verdicts-b.json … \
                         --expect security-1,security-2,rule-1,…      # every batch you dispatched
                         --agent-transcripts <the session's subagents/ dir>
  ```

  **`--expect` NAMES THE BATCHES, and it is the half that makes this a barrier.** Without it the
  command lints the files that HAPPEN TO EXIST and cannot see a batch that produced none, so a
  fan-out with one skeptic still writing lints clean: a build read `VERDICTS OK — 18 file(s)
  well-formed` while a nineteenth was seconds from landing, then ran `anchor-drift`,
  `fix apply-drift`, `assemble` and `grounding report` against the incomplete set and redid all
  four. A missing file is the one failure nobody spots by eye, because nothing is there. List the
  batch ids you dispatched; the command refuses until every one has a file.

  Note the shape: **`--verdicts` REPEATS, one flag per file** — it does not take a list, so a bare
  glob after one flag is an error. Run it the moment the barrier closes, not at `grounding write`:
  `write` refuses the same malformed shapes at the END of the build, where the skeptic that produced
  them is a hundred turns gone. `--agent-transcripts` adds the check no shape test can make — whether
  a note claiming a read is backed by the agent's own transcript. **Write the record with `coyodex
  grounding write`, never a hand tally:**

  ```
  # CAPTURE the worklist BEFORE any refutation is applied, and keep the file — the record is
  # written last, by which point a fresh audit no longer matches the verdicts.
  .venv/bin/coyodex audit .coyodex/project-map.json --json > .coyodex/verify/worklist.json
  # …skeptics run, refutations get applied, THEN:
  .venv/bin/coyodex grounding write --worklist .coyodex/verify/worklist.json \
      $(for f in .coyodex/verify/verdicts-*.json; do printf ' --verdicts %s' "$f"; done) \
      --out .coyodex/build-fragments/grounding.json
  ```

  It derives all four counts and REFUSES two things a hand tally cannot see: a verdict whose claim
  is not in the pinned worklist (the snapshot is wrong), and a worklist claim with no verdict at all
  (the pass did not challenge everything). Pin the worklist — re-deriving it after the refutations
  land makes `claims_challenged` exceed `claims_total`, which `validate` blocks on. **`grounding
  write` runs after the final reconcile edit, and is followed by ONE assemble that carries the
  record into the map.** Write it with `--map`, pointed at the assembled map, so the record states
  how the shipped claim surface differs from the pinned worklist. Both assembles are the SAME
  command, `--reconcile` included — dropping that flag silently discards every subsystem, `runs_in`
  and `drop_edges` assignment and changes the claim count, and `assemble` only prints a note about
  it:

  ```
  # 1. reconcile the refutations INTO THE FRAGMENTS, then:
  .venv/bin/coyodex assemble .coyodex/build-fragments/*.json --out .coyodex \
      --reconcile .coyodex/reconcile.json
  # 2. the record, measured against the map it describes:
  .venv/bin/coyodex grounding write --worklist .coyodex/verify/worklist.json \
      --map .coyodex/project-map.json \
      $(for f in .coyodex/verify/verdicts-*.json; do printf ' --verdicts %s' "$f"; done) \
      --out .coyodex/build-fragments/grounding.json
  # 3. the SAME assemble again, to carry the record in:
  .venv/bin/coyodex assemble .coyodex/build-fragments/*.json --out .coyodex \
      --reconcile .coyodex/reconcile.json
  ```

  Step 3 is safe because `assemble` is idempotent on claims, so it cannot invalidate what step 2
  measured.

  **Then READ what the record only counts — `coyodex grounding report --map`, same arguments.**
  `write` reduces the pass to four numbers plus a digest; `report` prints WHICH claims were
  superseded, refuted, tied, unverifiable or unvoted. Read it before writing `grounding.note`, and
  check two things the counts cannot show:

  - **a SUPERSEDED claim that was CONFIRMED** — the build rewrote something the skeptics had
    settled. That is a decision, not a fix; say so in the note.
  - **a REFUTED claim that is NOT superseded** — the reconcile changed something the claim's text
    does not name, so neither `claims_superseded` nor the digest can witness it (correcting one
    transition of a state machine leaves the claim string identical). Check that one by hand against
    the map, because nothing else will — `report` names it for you.

  The assumption that "superseded" and "refuted" are the same set is false in BOTH directions, and
  the counts alone cannot tell you which way a given build differs.

  **`claims_total` stays PINNED, and the pin is not a bug to fix.** Reconciling a refutation
  REWRITES the claim, which orphans its verdict, so a record written first describes a worklist that
  no longer exists. No gate can catch that by arithmetic: `validate`'s checks (challenged/superseded
  within total, the confirmed+refuted+unverifiable split, no negatives) are all self-consistent
  against a stale pin. `finalize` raises an advisory when the pin and the live worklist disagree,
  and L3 assertions 13 and 14 watch the ordering and the number. `--verdicts` is REPEATABLE: pass
  the per-batch files, do not hand-merge. **Then run `coyodex anchor-drift --map … --verdicts …`** —
  a deterministic check that flags any CONFIRMED claim whose stored `where` drifts from the line the
  skeptics found; reconcile each by **fixing the map's `where`** (the check flags, you apply — the
  LLM only observed the line). **Apply the drift fixes with the tool, never a hand script:**
  `coyodex anchor-drift … --json` emits the corrected anchors and `coyodex fix apply-drift --map …
  --verdicts …` writes them, matching each on the full `(src, verb, dst)` triple — an endpoints-only
  key swaps a paired `persists`/`reads` edge. `apply-drift` rewrites a drifted **rule SITE** anchor
  the same way, so a skeptic's corrected auth-check line lands with the tool, not a hand
  re-serialize. (It also still rewrites a legacy `security[].source`. **`fix security-row` and `fix
  dedup-security` act on `security[]` only**, which the T7 fold leaves empty — on a map built with
  the current method they print "no security rows" and exit 0, so a rule's TEXT is fixed in its
  fragment, not with a verb.) To drop a **refuted** edge as a terminal post-assemble fix, `coyodex
  fix drop-edge` removes it and reports (or, with `--repoint`/`--drop-steps`, heals) the flow steps
  that rode it; **`--to-reconcile <file>` records the drop as a `drop_edges` directive instead of
  editing the map**, which is what makes it survive the next assemble. Reconcile every refutation
  and every drift (fix the map, or justify and record why); this reconcile is **not delegated**.

  **EVERY skeptic outcome has a destination, and the one without a tool is the one that gets lost.**
  A batch comes back with four kinds of answer, not two. Name the destination for each before you
  start reconciling, or the ones with no verb attached evaporate into the notification prose:

  | what came back | where it goes |
  | --- | --- |
  | refuted, an edge | `coyodex fix drop-edge` (or repoint) |
  | refuted, an anchor moved | `coyodex fix apply-drift` |
  | refuted, an ACCESS rule's TEXT is wrong ("that line guards nothing, the real gate is X") | fix the owning T7 fragment's rule (`statement` / `why` / `risk` / `access`) and re-assemble — there is no `fix` verb for a rule's text |
  | refuted, an access rule's SITE is wrong (the enforcement line moved) | `coyodex fix apply-drift` — a rule site is a claim-shaped, drift-eligible anchor like any other |
  | two fragments harvested one auth check | fuse them in the fragment: one decision enforced in several places is ONE `access` rule with several sites |
  | **true, but your note / list / transition is wrong** | fix the fragment, or `coyodex record` the decision — it is NOT a refutation and no counter will miss it |
  | unverifiable | the `unverifiable` verdict, and a line in `grounding.note` |

  The *true, but your note / list / transition is wrong* row is the one that disappears, because
  "confirmed" gets treated as "nothing to do". The verdict counts cannot witness it: the claim stays
  CONFIRMED and the record reads clean.

  **Never hand-script a security-row edit.** `fix security-row` selects EXACTLY (by claim, by
  surface, by anchor) and refuses on 0 or >1 matches. A loose hand-rolled selector overwrites the
  wrong row, and the damage surfaces assembles later, if at all. Two rows sharing an anchor is legal
  and is not duplication — `dedup-security` keys on the surface for exactly that reason.

  **The vote is advisory; your re-read decides.** When N skeptics split and you open the file
  yourself, what you find outranks the majority — a 1-of-3 minority refutation is correct to apply
  when the dissenter turns out to be right. Say so in `grounding.note` (`report` will flag it as a
  CONFIRMED claim you overrode). This is not a licence to overrule a vote you merely dislike: the
  re-read wins because it is evidence, so it only wins when you actually did it. Two
  **behavioral-consistency items** ride the same fresh-context pass (judgment calls no mechanical
  gate can make): (1) for each Happy Path step, does its **title contradict its use case's name or
  outcome**? (the "signs in; the organization exists" vs "create an organization" class — a title
  states the action, never a post-condition); (2) do two flows **retell the same machinery at
  different depths** (one spells a pipeline out in 13 steps, another compresses the same run to 3)?
  — the mechanical duplication detector only catches *identical* runs, so depth-inconsistent
  retellings are found here; fix by extracting a sub-flow or aligning the depths. Re-validate →
  re-audit → render after fixes.
  - **Ordering — ONE sequence, and `grounding write` is second-to-last.** The sequence below is the
    single one; where an older note disagrees, this wins.

    ```
    0. coyodex grounding lint --verdicts <v> … --agent-transcripts <dir>   # at COLLECTION, not here
    1. every structural / fragment change, including the refutation reconcile
    2. coyodex anchor-drift --map … --verdicts …            # what drifted
    3. coyodex fix apply-drift … --to-reconcile <file>      # RECORD it; the map is not edited
    4. coyodex assemble … --reconcile <file>                # last STRUCTURAL assemble; applies set_anchors
    5. coyodex grounding report --worklist … --verdicts …   # WHICH claims were refuted / tied /
                                                            #   unvoted — the reconcile worklist, and
                                                            #   what `grounding.note` is written from
    6. coyodex grounding write … --note …                   # measured against the map it describes
    7. coyodex assemble … --reconcile <file>                # carries the RECORD in; idempotent, and
                                                            #   not optional — skip it and the
                                                            #   grounding record never reaches the map
    8. coyodex provenance stamp <repo> --mode build \
         --update-header .coyodex/build-fragments/header.json   # STAMPS and fills `built` in one
                                                            #   run. Never hand-write that minute
    9. assemble + render again, so the filled header reaches the map
   10. coyodex lint-fragment … header.json                  # the one hand-authored fragment
   11. coyodex validate --check-sources → coyodex audit → coyodex render
   12. coyodex finalize … --verdicts <v> … --emit-gate-block <file>   # ONE run, both flags
   13. commit the map, the .md, the pre-index and provenance
    ```

    **Steps 5, 8, 9 and 12 are here because the list without them cost real builds.** `grounding
    report` used to live only in prose 74 lines above, so a build that followed this block literally
    wrote the record, then read `report`, then wrote the record AGAIN with the note — one wasted
    invocation every time, because `report` reads the worklist, the map and the verdicts and never
    consumes the record. `provenance stamp` and the header backfill were prescribed 160 lines away
    while this block called itself the single sequence, so the third `assemble` they force appeared
    to contradict step 4's "last STRUCTURAL assemble" (it does not: the header carries no claim, and
    `finalize` re-reads the shipped bytes). And `finalize` was run twice on one build — once with
    `--verdicts`, once with `--emit-gate-block` — where the second run overwrote the report and
    dropped its verdict-based anchor-drift leg, including the "challenged N of M" coverage line. The
    flags combine; run it once.

    **Step 8 carries `--update-header` because the step it replaces was an instruction to
    hand-write a map file** — copy the stamped minute across into `header.json` yourself. It read as
    a two-line edit and it is one, which is exactly why no build treated it as a defect: one wrote
    the `built` string with a
    `python3 - <<'PY'` heredoc AFTER `grounding write`, making that heredoc the last fragment write
    of the build and scoring L3 assertion 13 zero. The flag that does it had shipped the day before
    and was named nowhere a build reads — not here, not in `provenance stamp --help`'s prose, only
    in a usage grammar line. Do not hand-write `built`; there is no case left for it.

    Steps 3 and 4 are the change. `fix` edits the ASSEMBLED map, and the source of truth is the
    fragments, so a later `assemble` silently discards every `fix` edit. `--to-reconcile` makes the
    correction durable instead, so the drift fix no longer has to be last and the grounding record
    can be measured against the map that ships. Use bare `fix apply-drift` (no `--to-reconcile`)
    only for a genuinely terminal touch-up after step 6, and re-run `grounding write` if you do. If
    Phase 4 surfaces a change that must live in a fragment, edit the fragment, re-assemble, and
    re-run the grounding reconcile after (never the other way round). Keep the **verdicts file OUT
    of `build-fragments/`** (e.g. under `.coyodex/verify/`) so a `*.json` glob into `assemble` can't
    pick it up — `assemble` now skips a stray verdicts file with a note, but keeping it out of the
    fragment dir is the clean habit.
  - **Where each reconcile lives — reconcile file vs `fix` verbs.** Build-time drop/dedup (a
    cross-agent duplicate edge, a refuted edge you decide during synthesis/trace) belongs in the
    **`--reconcile` file** (`drop_edges`) or the fragments, so a re-assemble re-applies it — do NOT
    reach for a bare `fix drop-edge` there, its edit is discarded by the next assemble ( `fix
    drop-edge --to-reconcile <file>` writes the same drop as a `drop_edges` directive, which is
    not). The `fix` verbs are the **post-assemble anchor-drift** tool only (`apply-drift` for
    drifted edge/security anchors, `drop-edge` for a refuted edge found in Phase 4 after the final
    assemble). One rule: assignment and drop that must survive a rebuild → reconcile file; a
    terminal anchor fix after the last assemble → `fix`. `--reconcile drop_edges` runs after the
    entity-edge derivation and heals the riding flow steps exactly like `fix drop-edge`, so a
    dropped `C→E` edge is not silently re-derived. `set_anchors` is the third directive and the one
    that makes an anchor correction survive a rebuild — `fix apply-drift --to-reconcile` writes it,
    keyed by the claim, and `assemble --reconcile` applies it through the same writer. The directive
    shape (also in `assemble --help`):
    ```json
    { "set_anchors": [ {"claim": "C21 persists E33", "corrected": "backend/store.py:88"} ],
      "drop_edges": [ {"src": "C21", "verb": "persists", "dst": "E33"},
                      {"src": "C7",  "verb": "calls",    "dst": "C9", "drop_steps": true},
                      {"src": "C4",  "verb": "reads",    "dst": "E2", "repoint": "E5"} ] }
    ```
    Each entry defaults to REPORTING the flow steps that rode the edge; `drop_steps` removes them,
    `repoint` re-points them. **A report-only `C→E` drop leaves the step, and the next assemble
    re-derives the edge from it** — so heal it, or the drop does not stick. `assemble` prints the
    unhealed count in its final digest line for exactly this reason. Zero matches warns, never fails,
    so a directive that outlives its edge does not rot the build.
  - **A duplicated domain relation BLOCKS validate — resolve it with `coyodex fix dedup-relation`.**
    The same `E→E` relation declared on both entity cards (or twice on one) is a hard validate error,
    not an advisory, so the build cannot finish until you pick a survivor. Run it with no `--drop` to
    LIST each duplicate with the token that resolves it, then re-run naming the occurrence to remove:
    ```
    .venv/bin/coyodex fix dedup-relation --map .coyodex/project-map.json
    .venv/bin/coyodex fix dedup-relation --map .coyodex/project-map.json --drop <En:verb:Em>
    ```
    Same ordering rule as the other `fix` verbs: it edits the assembled map, so run it AFTER the last
    assemble, or fix the duplicate in the fragment and re-assemble instead.
- Guardrails: all agents share the same schema + edge-verb vocabulary; Phase 1 produces
  the canonical node inventory FIRST (nodes before edges, agents reference nodes and
  never invent them); every agent keeps inferred-vs-verified labels + returns `file:line`;
  agents return rows (structured output), not file dumps. The final reconcile (dedup
  names, verify cross-agent edges against code) is not delegated — and the lead may **not**
  author a `C→D` edge (or any edge into an external dependency) the trace agents did not
  report: every backbone edge must trace to a delegated agent's finding or be grounded
  against the code, never invented at synthesis to satisfy the "every dep needs an incoming
  edge" nudge (the audit→Elastic false-edge class — a benign-verb edge no gate re-checks).

**Harvest-prompt template (Phase 1).** The copyable contract is
[method/templates/harvest-contract.md](method/templates/harvest-contract.md) — hand every harvest
agent that file's contents, changing only the file list and the background blurb. **Get it with the verb, never by copying the file:** `coyodex
contract harvest > <scratch>/harvest-contract.md`, then fill the «angle-bracket» slots in place.
The verb prints the agent's half and appends the writing rules, so you never handle the template
and the lead-facing header at its top cannot reach an agent. A harvest agent authors every
component `purpose` in the map, the largest block of reader-facing prose there is. Do not `Read` it and `Write` your own — that is one
keystroke from a rewrite, and a retyped contract drifts from the tool it describes, silently
dropping rules (the anchor rules for `edges[].where`, `subsystems[].source` and `tests[].file` are
the ones that have gone missing) from the contract every agent is handed.

**Business-rule contract (Phase 3).** The copyable contract is
[method/templates/rules-contract.md](method/templates/rules-contract.md). Get it the same way —
`coyodex contract rules > <scratch>/rules-contract.md` — then fill the «angle-bracket» slots, and
for the same reason. A rule agent authors every `statement` and every `risk`, the two fields a
reader meets when asking what the product decides. This template exists because one build had none:
the lead composed the rules contract from prose and told all eleven rule agents to put a `block`
field on every rule, which `lint-fragment` treats as BLOCKING. The failure fired in 13 of that
build's 71 agent transcripts and every one of the eleven fragments had to be repaired. `block` is
the lead's to assign, through `reconcile`, after the fan-out — an agent states its block id in its
REPLY and never in its fragment.

**Completeness check before the barrier (lead, not delegated).** Before the Phase 2 synthesis, the
lead confirms **every prescribed slice came back with its sections** — in particular that the T5 owner
returned per-entity cards *with* RELATIONS, and that each agent that wrote `(none found)` is genuinely
empty rather than under-delivered. For T4, confirm the **self-starting second pass ran**: a
long-running service whose entry points are all routes/mounts/CLI has likely skipped its background
loops — re-ping with the self-starting checklist stated. Re-ping any agent that dropped or thinned its sections; a missing
section caught here is cheap, one discovered after synthesis is a re-trace. **An agent that returns
prose instead of a written fragment file (it delegated, or answered in its reply) has produced
NOTHING usable — re-launch that slice immediately, do not wait on it or try to salvage the reply;
the written fragment is the only output that counts.** The same "every prescribed
table came back" rule reaches past the barrier to the **test-completeness table**: after the Phase 3
trace's test-completeness step, confirm `tests[]` came back non-empty before finalizing (an empty
`tests[]` is a dropped section — the step always produces a gap table — not a project with zero
targets); re-run that step, exactly as a missing harvest section is re-pinged here.

**Expected yield per slice — judge each return against its E (under-delivery guidance).** A
well-formed return can still be an under-delivered one: a slice that comes back with far fewer
components than its size suggests has *abstracted where it should have harvested*. The expectation is
already computed: the pre-index's `granularity.per_dir` carries each slice's **E** (the leaf rule
above), and the harvest prompt hands it to the agent. **Before** reading the returns, note each
slice's E; a return far under its E's ±40% band is under-delivered even though every row validates.
Re-ping such a slice **with the expectation stated** ("this slice's code-derived expectation is ~E
components; return its real units or say per unit why it folds") — a size-blind re-ping just gets the
same answer back. E is an attention threshold, not a gate (a heavy *generated* dir still legitimately
folds — the pre-index guardrail applies); a cheap deterministic backstop exists after the fact in
`validate --check-coverage`, which re-computes E for the whole map and flags folded sibling subdirs
and never-referenced dirs.

**Output files — model + generated views.** Build writes a **new** baseline and overwrites any
existing `.coyodex/` map, so you should only be here for a first map or a user-confirmed rebuild —
[dispatch](method/dispatch.md) routes an existing baseline to Analyze, not Build. The committed
source of truth is `.coyodex/project-map.json` ([the map model](method/model.md)),
written by `coyodex assemble` together with its generated markdown view, `.coyodex/project-map.md`
(readable diffs). Both are committed — and so is the structural pre-index `.coyodex/preindex.json`
when the build produced one: the viewer's symbol search reads it, pinned to the map's commit, so it
must ship with the map (it is generated at that commit, so its `file:line` anchors match). The
interactive C4 diagram is not a committed file: it is served live by `coyodex serve` (built on
demand from the model). Record the commit the map was built
at in the model's `commit`/`committed`/`built` fields (the baseline pin — see the pin gate below).

**Baseline pin — require committed code, or record it dirty.** The pin must mean "the map describes
*exactly* this commit". The map you just read reflects the **working tree**, so if the code has
uncommitted changes, HEAD alone is a misleading pin (and a later `git diff <pin>..<now>` would miss
the edits already baked into the map). So before recording the pin, check the analyzed repo for
uncommitted **code** — coyodex's own files under `.coyodex/` (map / markdown view / report) don't count, they
are always in flux and the workflow commits them:

```
git -C <repo> status --porcelain -- . ':(exclude).coyodex'   # empty = code is committed
```

- **Code committed** (empty output) → record the pin from HEAD:
  `git -C <repo> rev-parse --short HEAD` (the sha) and
  `git -C <repo> show -s --format=%cs HEAD` (its commit date, `YYYY-MM-DD`).
- **Uncommitted code** → first LOOK at the diff. When it is **trivial** — comments and/or whitespace
  only, no code lines (`git -C <repo> diff -w --ignore-blank-lines -- . ':(exclude).coyodex'` empty,
  and any untracked files are non-source) — do NOT block: proceed automatically as **B** below and
  note the pin choice + the trivial diff in your report. Otherwise STOP and give the user a choice,
  then **loop**:
  - **A (recommended)** — **the user** commits (or stashes) the code first, so the baseline
    corresponds to a real commit; then you re-check and record the pin as above. Never commit or
    stash their working tree yourself — this step is a question, not a mandate.
  - **B** — proceed without committing, but record that the code was dirty: pin the sha with a
    `-dirty` suffix (`<short-sha>-dirty`), date = HEAD's commit date.

  Re-run the check after each round; only continue when the code is committed (A), the user
  explicitly chose B, **or** the auto-B trivial-diff rule above applied.

  **Asked once, not twice.** [dispatch](method/dispatch.md) Step 0 puts this same A/B question to the
  user BEFORE the build starts, off the `coyodex scope` briefing. If it was answered there, honour
  that answer and record the pin — re-asking at the end, after the user already decided and waited
  out a whole build, is the annoyance this gate is supposed to prevent.

Write the pin into the model's **`commit`** / **`committed`** / **`built`** fields (sha · commit
date · build time — the header fragment carries them; the generated views render them as the map's
header line).

**`built` is stamped LAST and copied BACKWARDS — never guessed early and reused.** The header
fragment is authored during Assemble and the stamp belongs after the map is written and validated,
so on a real build they are an HOUR apart. Capture the minute early and reuse it, and both the
header and `provenance.json` carry the wrong minute permanently — and `coyodex-eval retro-precheck`
reads exactly that field to decide whether a build has finished.

So: write `header.json` with `built` **empty**, and fill it from the stamp at the end.

**Stamp the conversation (provenance).** After the map is written and validated, record which
conversation built it — run (paths under the coyodex clone, like `.venv/bin/coyodex`):

```
.venv/bin/coyodex provenance stamp <repo> --mode build \
    --update-header <repo>/.coyodex/build-fragments/header.json   # NO --built-at: real clock
# --update-header writes the stamped minute into `built` for you. Then re-run `assemble` and
# `render` so the filled header reaches the map.
```

**Do not hand-write that minute.** The flag above is the whole step. Without it a build reads
`built_at=…` off stdout and edits `header.json` by hand, which is a map write in the middle of the
closing sequence — one build did it with a `python3` heredoc placed after `grounding write`, so the
last write of the whole build was a hand-script.

Pass `--built-at` only when you are deliberately restating a time you did not just measure (an
`accept` pass re-stamping an earlier build). On a build it is the flag that makes the map lie.

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
(`title`, `goal`, the pin fields — as **top-level keys**, NOT wrapped in a `header` object), and
**lint it too before assembling** (`coyodex lint-fragment .coyodex/build-fragments/header.json`): the
header is the one hand-authored fragment that otherwise skips the self-check every sub-agent runs, so a
stray key here is the one thing that still fails `assemble`. Then run:

```
.venv/bin/coyodex assemble .coyodex/build-fragments/*.json --out .coyodex
```

It validates every fragment against the schema (a malformed fragment fails ALONE, with its file and
JSON path named — re-request that one agent's rows), refuses duplicate IDs across fragments, and
writes the canonical `project-map.json` plus the generated markdown view (no HTML file — the
interactive diagram is served on demand, never written). In serial (non-parallel) mode the same rule
holds at smaller scale: author your rows as one or a few fragments and let `assemble` serialize —
the stored JSON is always tool-written, so its validity is guaranteed by the serializer, not by you.
(The old markdown template,
[`method/templates/project-map.template.md`](method/templates/project-map.template.md), now only
documents the generated view's shape — it is no longer filled in by hand.) Run the validator —
`.venv/bin/coyodex validate .coyodex/project-map.json --check-sources --check-coverage`
([tools/coyodex/validate_model.py](tools/coyodex/validate_model.py)) — after each assemble/patch and
fix the model (via fragments / field edits + re-assemble or re-render) until it passes
(`--check-sources` reads each entity's `source` to reject synthesized entities — names with no real
named type; `--check-coverage` re-walks the repo and WARNS — non-blocking — when many sibling source
subdirs are folded into one box or a significant directory is never referenced, the map-fidelity
gaps the ID checks can't see). **At a deliberately coarse (whole-repo overview) altitude these
coverage warnings are expected, and a recorded exception silences them per-directory:** list the
consciously-folded repo-relative dirs, one per line, under a **"Coverage exceptions"** extras
heading (`plugins/: representative at coarse altitude`). A recorded dir silences the folded-subdir /
unreferenced-dir / no-entity-card warnings **and** the per-component "unclaimed surface" warning for
anything at or under it — one `plugins/` line replaces a per-plugin record for every unit beneath
it. It is **boundary-scoped**: a real gap in an *unlisted* dir still warns, and `plugins/` never
silences a `plugins-legacy/` sibling. (The component-count-vs-E advisory has its own token — the
literal `granularity` under "Balance exceptions".) **Then run the adversarial pass** —
`.venv/bin/coyodex audit .coyodex/project-map.json`
([tools/coyodex/audit_model.py](tools/coyodex/audit_model.py)). Where validate asks *is the map
well-formed*, audit asks *is it self-contradictory*: it makes the map's two layers — the narrative
Happy Path (step order, actors) and the mechanism (T6 flows + the backbone edge list) — refute each
other, deterministically, with no code. The map is **over-determined** (each precondition is encoded
twice — once as narrative order, once as which entity a flow reads vs writes), so the two copies
check each other. Audit **blocks (exit 1) only on a hard contradiction** — a *`why:` reference that
points forward or at a nonexistent step* (unambiguous, no false positives) — which you fix like a
validator error. Its ordering/actor checks are **ADVISORY, not blocking**, on purpose:
*read-before-create* (a Happy-Path step reads an entity a later step first
`writes`/`persists`/`creates` — `writes` is create-or-update ambiguous, so this is a pointer, not a
verdict) and *actor-attribution* (the Use-cases table and the flow disagree on who drives a use
case) are derived from lossy component-granularity attribution, so they have real false positives (a
shared component leaks its reads) and false negatives (a read routed through a `C→C` dependency is
invisible — only `C→E` edges count). Treat them as strong "look here" pointers to reconcile, not
facts; *read-never-created* (a read with no create — often external/config data) is advisory too.
The known bug that motivated audit (a sign-in step ordered before the org it needs) surfaces here as
an *advisory* — audit points, you or L2 decide. Audit also prints an **L2 grounding worklist**: the
"actually-does" claims no deterministic check can settle — the **whole backbone edge list**, ranked
most-dangerous first so a large list is worked top-down: security surfaces + `enforces` / `encrypts`
edges, then every `C→D` external-dependency edge (any verb — the audit→Elastic system-boundary
class), then every `C→E` ownership edge, then the remaining element↔element edges (an edge into a
dep explicitly tagged `framework`/`library` is skipped — a false "uses <lib>" is benign). Ground
each by spawning a **fresh-context skeptic** (Phase 4 below) that sees only the finished map + the
code — never your build reasoning — and tries to *disprove* the claim; **reconcile every finding —
advisory or blocking — (fix the map, or justify and note why)** before rendering. So the invariant
after every write is **validate --check-sources → audit → render** (`--check-sources` is not
optional — it is the deterministic backstop that a nonexistent-file anchor / wrong repo-root prefix
can never slip through).

**Run `coyodex finalize` as the pre-commit read.** It runs that sequence plus the SHAPE-ONLY
anchor-drift pass in one command, and writes every finding to `.coyodex/finalize-report.{json,md}`
with whole lists. The verdict-based drift pass runs only when you hand it `--verdicts`; without
that flag the leg simply does not run and nothing in the report says so, so a run without it is
not the full pre-commit read:

```
.venv/bin/coyodex finalize .coyodex/project-map.json --repo <repo> [--verdicts <file>]...
```

It adds no check of its own. What it adds is a record and an answer:

- **the report is a FILE.** A file survives `> /dev/null`, `| tail -12`, and a summary written from
  memory; a piped gate does not. **This binds the MID-BUILD gate runs too, not only this pre-commit
  one.** Reading each gate through `| tail -40` / `| head -14` costs serial rounds — one `validate`
  run per warning family, each with its own patch turn, where one whole read produces one batch of
  fixes. **And never re-check a warning with a filter narrower than the run that surfaced it**: a
  grep whose pattern no longer matches the wording makes the finding vanish from view, and it then
  ships unrecorded and unfixed. Narrowing the view is what a waved-through advisory looks like from
  the inside. (L3 assertion 15 watches this.) **A COUNT is the narrowest view of all, and it is not
  a read.** A count cannot say WHICH warnings are open, and an identical count before and after a
  change reads as "nothing changed" when checking exactly that was the point. (L3 assertion 26
  watches this, for `validate`, `audit` AND `finalize`.) **`audit` gets the same treatment as
  `validate`.** Printing `len(worklist)` and the theme table out of `audit --json` while never
  reading its `findings` key is the same move: piping a gate into a length is piping it into a grep.
  **`grep -v` on a gate's output is the same move in disguise:** filtering a family out of your own
  view is not reconciling it. If a family is noise, record an exception; never delete it from the
  report you are reading. When a message says a recorded exception silenced more than it names, the
  re-read is **`coyodex validate <map> --ignore-exceptions`** — not a hand-edited copy of the map.
- **it says whether every check actually ran.** Run the three commands by hand and a skipped one
  looks exactly like a clean one. A leg that should have run and did not makes the verdict
  `INCOMPLETE`, which exits non-zero — "the gate did not run" must never read as "the gate passed".

**Read the report file, and quote finalize's verdict line when you report the gates — in the COMMIT
MESSAGE too, not only in chat.** Its stdout can be piped away: in a shell pipeline the exit status
is the last command's, so `finalize | grep …` returns grep's `0` — and so does `finalize | tail -3`.
An honest verdict in chat and a clean-sounding commit message are not the same deliverable, and the
commit is the only record a future reader sees. `finalize --emit-gate-block <file>` writes the block
to paste, so the durable record is generated rather than remembered.

**Then actually commit.** The build is not over at `finalize`. Stopping there leaves `.coyodex/`
untracked, so a map that cost hours and hundreds of dollars exists only in one working tree — and
the whole argument for generating the gate block is that the commit is the durable half. `finalize`
prints the exact `git add -f` line to use; run it, and commit the pre-index and provenance with the
map.

**`finalize` also reads the advisory disposition** — each advisory as fixed / recorded / carried,
against what the map's extras actually record. Read that table rather than the raw list.

**ADVISORIES is not a pass** — fix each one, or record it under the extras heading its message
names. **Where a verb exists, use it.** `validate`'s "the '<verb>' edge is declared N times with
differing call sites" has one: **`coyodex fix dedup-edge --map … --repo …`** lists every conflicting
triple with its competing anchors and suggests the likeliest true site, and `--keep
<src:verb:dst:path:line>` drops the rest. **Some advisories deliberately name no heading.**
`tests/test_method_contract.py`'s `KNOWN_NO_ESCAPE` is that list, each entry with its own reason,
and the reasons are not one kind: some are mechanical and local ("contradictory row; drop one
field"), some say the record already exists ("the minted name IS the record"), and some are
deliberately un-escapable because a suppressed count staying visible IS the feature. So the honest
answer differs per entry — fix it, or carry it and say which. **Never call one "recorded"**: an
advisory whose stock remedy would inject a misattribution (a `C→broker` edge whose publisher's own
source holds zero references to the broker, because it is reached through an event-stream adapter),
or whose remedy is "rename on rebuild", has no home and no correct stock answer. Anchor drift is the
exception that is a judgement call: the skeptics can report a line from a sibling file while the
stored anchor is right, so it has its own escape — record ``anchor-drift `<the claim, verbatim>`:
<why>`` under a **`Drift exceptions`** extras heading. The key is the WHOLE claim in backticks, not
its leading id: keying on the id would let one line silence every drift finding rooted at that
component, which is the family escape the `Audit exceptions` rule above forbids in so many words.
`anchor-drift` prints the exact key to copy; it reports any recorded line that matched nothing, AND
any line that opens with `anchor-drift` but does not parse — an unparsed line yields no key, and a
line that silences nothing looks exactly like no line at all. **A bucket the seed list does not have
has its own escape: `Bucket vocabulary`.** A project whose real vocabulary needs a bucket the
library seeds never named (an MCP gateway genuinely has an "MCP protocol" bucket) would otherwise be
told to rename it on every rebuild, forever — advice that pulls against itself, because reusing the
previous map's spelling for stability is what earns the warning. Record ``coyodex record --map
.coyodex/build-fragments/extras.json --heading "Bucket vocabulary" --line "MCP protocol: <why this
project needs it>"`` — **name the FRAGMENT**, not the assembled map: `--map` defaults to
`.coyodex/project-map.json`, and `record --help` calls that "the edit the next assemble discards". A
record written into the map is a decision that silently un-records itself. and the nudge stops for
that bucket only; a summary line still reports what the record silenced. **A decision-sounding step
that is NOT a business rule has its own escape: `Sweep debt`.** Once a map carries business rules,
`validate` lists every anchored flow step whose wording reads like a decision that no rule claims —
the sweep worklist, and the only thing that says whether the sweep finished. There is deliberately
no `swept` field to set: a boolean asserting "I searched the whole repo" is unfalsifiable, and
hand-assigned data rendered as derived is what makes a screen confidently wrong. So the list shrinks
two ways only — write the rule, or say why the step is not one. Record ``coyodex record --heading
"Sweep debt" --line "<the step's anchor>: <why this is plumbing, not a decision>"`` under the
**"Sweep debt"** extras heading — **name the FRAGMENT** (`--map
.coyodex/build-fragments/extras.json`), not the assembled map, for the reason the bucket paragraph
above gives. The key is whatever the advisory prints: the step's own `path:line` for a
decision-sounding step, and a `BRn` for the other finding this heading answers — a rule whose sites
land in files no component claims, which renders with no component and cannot be verified. Both work
because this heading is read by the generic `key: why` reader, not the id-keyed one (which matches
no `BR` token at all — a `BRn` line under a heading THAT reader serves would silence nothing,
silently). Every suppression is REPORTED, and it moves a derived number: a recorded step counts as
swept. **OPEN THE FILE before recording one.** The escape is for "the skeptics read a sibling file
and the stored anchor is right" — a claim about what is at a `path:line`, which you cannot know
without looking. Reasoning about what an anchor "is defined to point at" is not looking. (L3
assertion 17 watches this.) Write the record with **`coyodex record --heading "Drift exceptions"
--line "…"`** rather than a hand-rolled append: it checks the heading is one a check actually reads,
refuses a key with no why, and `--replace <prefix>` is how you correct a record whose facts moved.
`finalize` exits non-zero for what validate and audit already block on, and for `INCOMPLETE`;
unapplied anchor drift is reported and never gates, because a `lifecycle` claim still has no writer
and a gate with no remedy is a false failure. (`cadence` DID have no writer and now does — `fix
apply-drift` rewrites an entry point's `cadence_source` alongside an edge `where` and a
`security[].source`.) It is a convenience wrapper and a durable record, not a gate that can force
anything. **Then render the markdown view** — once the map validates and the adversarial pass has no
blocking contradiction (advisories reconciled), regenerate the committed markdown view next to the
model (assemble already wrote it; re-run after any patch):

```
.venv/bin/coyodex render .coyodex/project-map.json .coyodex/project-map.md
```

It is a *rendering* of the model (no second source; never hand-edit it — `validate` flags a stale
view) — commit it alongside the model so the two stay in step. The interactive diagram is not a file:
it is served live from the model by `coyodex serve`. **Finish by reporting the artifacts as links** —
the model (`.coyodex/project-map.json`) and the markdown view (`.coyodex/project-map.md`), as relative
paths. **Then give the reader the URL to open the interactive map in a browser through the
coyodex map server** — that is where the diagram, file browser, and code viewer light up (data + source
served from git at the map's commit). Rendering just registered this project with the server, so it shows up there as a
card. Tell the reader: if the server isn't already running, start it once from the coyodex clone —
`make start` (or `.venv/bin/coyodex serve`) — then open `http://127.0.0.1:8765/p/<repo-folder-name>/`
(the `<repo-folder-name>` is the mapped repo's folder name), or the landing page
`http://127.0.0.1:8765/` and click this project. (Paths like `.venv/bin/coyodex` are relative to the
coyodex clone, like the validator above.)

**Maintaining the map.** When code changes after a baseline exists, follow
[change-impact](method/change-impact.md): report the impact against the map (modified /
added / deleted), then accept: patch the MODEL (`.coyodex/project-map.json` — surgical field
edits), bump the baseline pin, re-stamp provenance
(`.venv/bin/python tools/map_backup.py stamp <repo> --mode accept --built-at '<YYYY-MM-DD HH:MM>'`,
which appends this session), **re-run validate → audit** (a patch can introduce a fresh
self-contradiction — e.g. a re-ordered Happy Path step now reads before it creates), **re-render
the markdown view** (`coyodex render … project-map.md`, so it tracks the patched model; the diagram
is served live) and, when the map has a pre-index, **regenerate it at the new pin**
(`coyodex preindex --root <repo>`, so the viewer's symbol search stays aligned with the re-pinned
map), save the annotated diff under `.coyodex/analysis-changes/<date>.md`, and commit the
model + markdown view + pre-index + `provenance.json` with the code.

**Drilling deeper (refine altitude in place — never a second map file).** When a subsystem is too big
to detail at its altitude (e.g. a `plugins` area holding dozens of feature units), go finer **inside the
one map**, three ways:
- **Nest** — add child subsystems (their `Parent` is the bigger `S`) and move the members onto them.
- **Flatten** — dissolve a level that isn't pulling its weight (a single-child wrapper, a group the
  balance check flags as redundant): reparent its children onto its own parent and delete the group
  row. Pure regrouping — no edge moves, since a subsystem is never an edge endpoint.
- **Promote a leaf component into a subsystem** — when a component turns out to *be* a group (its
  Purpose enumerates many sub-units; the validator nudges this), retire the component, add a subsystem in
  its place, and add its real units as components under it. **Re-trace its edges**: the old component's
  aggregate edges (`C — verb → X`) must be re-pointed to the specific new components — a subsystem can't
  be an edge endpoint, so the validator's "every reference resolves" check fails on any leftover edge
  to the retired id, which forces (and guards) the re-trace.

All three are ordinary single-map edits; the viewer then drills the new level automatically. **Altitude may
be uneven** — refine only where you need detail; an area you haven't drilled stays a single box. This
**supersedes child maps** (a second `.coyodex/<area>/project-map.md`): a separate file is a separate ID
space, so links can't cross it and Analyze/Accept won't track it — see [dispatch](method/dispatch.md).

**How to apply.** Lead with the behavioral layer (T0 Goal → Glossary → Roles → Use cases →
Happy Path); on a non-trivial repo run the **pre-index** next (never before the behavioral
draft — GR1), then build structural Level 0 (T1–T3) using its weight map to set altitude;
generate the rest on demand as the reader drills. Always attach `file:line` (the pre-index's
symbol index gives correct ones). Label every entry point and every relationship as
verified vs inferred — that is where wrong guesses hide.
