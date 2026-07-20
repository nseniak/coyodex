# The coyodex method

How an AI coding agent builds and maintains a top-down, drillable map of a codebase.
Deliver this fixed set of sections, rendered as tables in the generated view. Every row is
drillable: name a row and it expands to a lower table or jumps to code with clickable
`file:line` links.

Two linked families:
- **Behavioral** (why/who/what): Goal → Glossary → Roles → Use cases → Happy Path.
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
    use case mentions (both happened on live maps). So before finalizing the use-case list, the
    lead enumerates the **registered** routes / MCP tools / CLI commands / callbacks (grep the
    registrations; in parallel mode the T4 harvest IS this enumeration — do the cross-check right
    after synthesis, when T4 first exists) and checks **both directions**: (1) a use case whose
    trigger has **no entry point behind it** → drop it or mark it stale-docs; (2) an
    **externally-triggered entry point no use case claims** → a missing use case or a dead
    surface — add the use case, or adjudicate it as ops/debug/infra. The mechanical backstop:
    `validate` warns (advisory) on every externally-activated T4 entry point whose owning
    component appears in **no T6 flow** (sub-flows expanded); a deliberate ops/debug/infra surface
    is recorded as `Cn: <why>` under an **"Unclaimed surfaces"** extras heading, which silences
    that component durably. On a large repo the wall can be dozens of surfaces — `coyodex validate
    --emit-unclaimed` prints a ready-to-paste block of every current one (each as `Cn (name): <why>`
    with its triggers) so you adjudicate them in one pass instead of hand-typing the list (a fresh
    monorepo build left ~125 of these unaddressed because recording them by hand was too costly).
    Self-activated entry points (crons, workers, consumers) are exempt
    automatically — nobody outside asks, so no use case has to claim them. A use case with **no
    T6 flow at all** also warns once tracing has begun — the phantom-capability signal.

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
- **Coverage rule**: pick the walk hitting all main functionality + all actors; if one linear walk
  can't reach everything, NOTE the use cases left off rather than forcing them in — they still have
  their own T6 flow, just not a spine position. **The note is a recorded adjudication, not build
  prose**: each off-spine use case gets a line `UCn: <why>` under a **"Happy Path coverage"**
  extras heading — `validate` warns (advisory) on an off-spine use case with no such record, and on
  a **role none of whose use cases has a spine position** (the "involves all relevant actors" half —
  an ops-only role kept off the walk is legitimate, but it is a decision: record `Rn: <why>` under
  the same heading). Ids are read from **line-leading** tokens only (`UC7: …`, `- R4: …`), so
  explanatory prose naming other ids never silences them by accident.

### Bidirectional traceability (use case ↔ elements) — standard

Connect each use case to the T1/T2/T5 elements its **flow** touches, **and** the converse, so the
reader can drill down (use case → elements) and step back (element → use cases). ONE source — the
**T6 flow steps** — both views derived; don't store links twice (they drift). A flow step's
endpoints (a component, dep, or entity) ARE the touches — **entities included, so a flow AUTHORS
its central entity touches as steps** (the entity-steps rule under T6): an entity's `Used in UC`
view exists only because flow steps name it. Deriving it **transitively** instead (flow touches a
component → tag every entity that component's edges touch) is rejected: an edge is an *aggregate*
of the component's whole behavior while a step is one scenario's interaction, so transitive tags
smear — measured on a live map, a third of the reachable entities would be tagged into more than
half of all use cases. Every step carries its **own** short action
text describing what happens at that point in the scenario — the same pair of elements can be used by
several steps that mean different things, so a shared pair-level edge label can't describe each one;
the step describes itself.

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
  Parent | Source | Conf.` — the Container altitude: components grouped into subsystems, optionally
  nested (a subsystem's `Parent` is another `S`). Membership is carried on the child (a `Subsystem`
  column on T1); the member list and the inter-subsystem edges are *derived*, never authored. Present
  this first on large maps; drill into T1. **Nesting renders as recursive drill**: each subsystem's card
  shows only its *immediate* children (sub-subsystems as drillable boxes), so a large area drills down
  level by level inside the one map — there is no depth limit (deep chains only warn). Group the **top
  levels by capability** (what the system does), not by tech tier, and keep every card's fan-out near
  the **5±2 target** — see *Diagram balance — the fan-out rule* under Cross-cutting rules.
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
  narrative below it. Drilling a Happy Path step opens its use case's flow here.
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
    leaves the whole domain model untraceable (a live rebuild shipped exactly that, all gates
    green — `validate` now warns when NO flow touches any entity; a map whose flows legitimately
    touch none records the literal `entity-flows` under `Balance exceptions`). *Central* means the
    join flow's Membership upsert or the tool-call flow's RoleSettings decision + AuditEntry append
    — NOT every config read along the way (those stay edges; tagging them all is the transitive
    smear again, hand-authored). Each entity step **rides an existing `C→E` backbone edge** (the
    edge is the aggregate claim, the step this scenario's instance). Author that edge in your slice
    with the right verb (`reads` / `writes` / `persists` — the ownership verbs are what the domain
    `persists/writes` view reads). As a safety net, `assemble` now **derives the C→E edge from any
    entity step that has none** (verb inferred from the phrase, ambiguous → `reads`), so at scale a
    forgotten edge self-heals instead of leaving the entity ownerless — but an inferred verb is
    coarser than the one you know, so still trace it. It carries the ordinary element↔element `where` (the operative read/write
    line in the `from` side's code), and obeys the same false-reads rule as `C→E` edges (the
    entity TYPE at the site, not a string extracted from it). A shared sub-flow is the leverage
    point: one entity step there serves every referencing flow. Entity steps are ordinary authored
    steps — they count toward the 3–15 band; a flow already at the band edge extracts a sub-flow
    or records its exception rather than dropping the entity touch.
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
    blocks). A sub-flow referenced by fewer than 2 flows is pointless indirection (`validate`
    warns). The payoff is CONSISTENCY: without it, each flow retells the shared machinery at
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
- **Deployment & topology**: `Unit | Runs on | Exposed as | Config source`. **Link the code to the
  runtime with `runs_in`** — on each component, the deployment `Unit` name(s) whose process executes
  it (a component may run in several: the C4 *instance* relation, one static box → many processes). It
  powers the **Deployment view** (`coyodex serve` → Deployment tab): processes and infra as nodes,
  their self-started threads on drill, and derived `runs` edges to the subsystems each process
  executes. **Derive `runs_in` by READING THE DEPLOY MANIFESTS — never formula-fill by id range.** Open
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
  - **Environments (deployment variants).** Many projects deploy the same code in several **variants** —
    dev / staging / prod, or genuinely different shapes (a single-container `standalone` vs a
    multi-service `cloud` split). This axis is usually declared in the source: docker-compose
    `profiles:`, k8s/Kustomize overlays, Helm values files, Terraform envs/workspaces, `.env.<name>`
    suffixes, serverless/Procfile stages. **Capture it, don't flatten it** (a build once dropped the
    dev/prod/standalone split as "over-modeling" and lost real information). List the variant names in
    the top-level **`environments`** array, and tag each `deployment[].unit` with the **`variants`** it
    belongs to (empty = **ungated / shared**, appears in every environment). Each variant tag is an
    object **`{env, source}`**: `env` names the environment, and `source` is a bare `path:line` anchor to
    the manifest line that places the unit there. Keep the unit name the process identity (`backend`),
    not the env (`backend (cloud/prod)`) — the env lives in `variants`. A component's environment is
    **derived** from the variants of the units it `runs_in`. Two grounding rules keep the tags honest
    (both from a real mis-tag — a Vite dev server tagged into `standalone` + `cloud` where it does not
    run):
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
- **Security & auth**: `Surface | Who can reach | Auth check | Risk note` (trust
  boundaries often inferred — flag). The **`Auth check`** anchor must point at the line that
  ENFORCES — the `if`/`raise`/`require_*`/decorator call — **never its docstring, comment, or `def`
  header** (the same operative-line rule as an edge `Where`, below). It is an L2 grounding claim, so
  `--check-sources` now verifies the linked file/line exists.
- **Config & environments**: `Key | Purpose | Default | Per-env / secret?` (secrets =
  where they live, never values).
- On-demand extras: state machines/lifecycles, event/message catalog, error/failure
  modes, change hotspots (git churn), permissions matrix (Role × use case).

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
- Convenience = inline "Uses" column on T6 (the most-used slice of the edge list).

---

## Cross-cutting rules

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
two axes, one per altitude: the **top 1–2 levels group by capability** — what the system *does*, read
from use-case / Happy-Path affinity, so the first screen describes the product; a tech-tier-only root
(`Backend` / `Frontend`, or by-language) is an anti-pattern — that axis belongs in a group's name or a
lower tier, not the top cut. **Leaf grouping stays directory-first**, then dependency/behavioral
cohesion; minimize inter-group edges *at the leaf/sibling level only* — a capability top level
legitimately has many cross-group edges, so never judge the top cut by edge counts; mark
directory-derived = verified, cohesion-derived = inferred — a cross-directory capability group has no
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

**Pre-index (structural input — run it after the behavioral draft, before the structural
harvest).** On a non-trivial repo, don't choose altitude from a *count* ("65 plugins, too many")
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
`extras` under the heading **"Balance exceptions"** and silences the matching advisory — the
heading accepts four id families, each scoping one advisory: a diagram id (`root`, `S7`, …)
silences its fan-out warning; a `UCn`/`SFn` id silences that flow's step-count band; a `Cn` id
silences its promote-to-subsystem altitude nudge; the literal **`granularity`** silences the
component-count-vs-E advisory (record it with the why when the altitude decision is conscious); the
literal **`entity-flows`** silences the no-entity-in-any-flow canary; the literal **`runs-in`**
silences the deployment-units-enumerated-but-nothing-links advisory (code that truly runs as one
unit). Never reword prose to dodge a heuristic — record the exception instead. The contract that keeps balance safe: **balance never gates and only ever
re-groups** — grouping is a free, view-only choice (membership on the child, member lists derived),
while the **leaf decision is grounded by E and out of bounds for balance tooling**: no balance
finding may merge or split components to hit a number.

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
  "granularity": { "expected_components", "band": [lo, hi],
                   "per_dir": { "<dir>": E … }, "file_cap", "loc_cap" },   # the leaf anchor (rule above)
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
  - **Reconcile your slice expectations with E BEFORE launching.** Hand each agent its slice's E
    from the pre-index `granularity.per_dir` — never your own gut numbers. If you deliberately
    deviate (a file-per-class repo where per-dir E under-counts), SUM your slice expectations first:
    when the total sits outside the whole-repo band, record the decision NOW — one line under a
    `Balance exceptions` extras heading containing the literal `granularity` plus the why — not as a
    post-hoc shrug when validate warns. (That recorded token also silences the E advisory; an
    overridden-but-unrecorded expectation was how a live build drifted to 2× E with the warning
    waved through at every validate.)
  - **Waiting for the batch (every fan-out phase):** after launching, **wait on the agents' completion
    notifications** — do NOT poll the filesystem with `ls` (a not-ready file reads as an error and
    burns turns). If you must block on a condition, use the **`Monitor` tool with an until-condition**
    (or a `run_in_background` waiter) — **not** a foreground `sleep` / `until … sleep …` loop, which the
    harness blocks. (`Monitor` is a deferred tool — run `ToolSearch select:Monitor` once to load its
    schema before the first call, or that first call fails with an `InputValidationError`.) Hand every
    agent an **absolute** fragment output path
    (`<repo-root>/.coyodex/build-fragments/<id>.json`) so it can never land in a subdirectory; `assemble`
    warns about any fragment left in `build-fragments/` that you did not pass in.
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
    - **Large domain models (many entities) — shard the RELATIONS pass, never skip it.** One agent can
      read ~40 entities and author a complete `E↔E` graph; on a 150–200-entity domain it will
      under-author relations and the graph comes out sparse (a fresh large-monorepo build left ~a
      quarter of its entities with no relation at all). When the entity count is high, the single T5
      owner still owns the slice but MAY fan the relations pass out **by subdomain** (each sub-agent
      relates the entities within one subdomain + names cross-subdomain targets), then merges. The
      invariant is coverage, not headcount: every entity gets its relations authored. `validate`'s
      isolated-entity count is the check.
- Phase 2 Synthesize (barrier, one agent): T1 clusters/dedups all harvest outputs, and (large
  maps) assigns Subsystems — a global graph cut, so it stays at the non-delegated barrier. **Synthesis
  is the final-ID authority.** Harvest agents may use per-slice *provisional* ids; synthesis assigns the
  final canonical ids here. This is the safe place to renumber: Phase 1 produced only nodes (no edges
  yet — those are Phase 3), so the only intra-slice references to fix up are `entry_point.component`,
  `entity.subdomain`, and the `E↔E` `relation.target` / `FK→En` markers. Because collisions are resolved
  before any edge is traced, a range overlap between two harvest agents can never reach the backbone;
  `assemble`'s duplicate-id error remains the loud backstop if a stray collision slips through.
  **Right after synthesis, run `coyodex validate --check-coverage`** — its unreferenced-files list is
  the mechanical harvest-completeness sweep (a source file no component claims = a slice-seam gap);
  an improvised spot-script covering one directory is how a live build nearly missed a component.
  **This is also the front-door verification moment** (the cross-check rule under *Use cases*): T4
  now exists, so reconcile the drafted use-case list against the harvested **external** entry
  surface in both directions — a use case with no entry point behind its trigger (stale docs), an
  externally-triggered entry point no drafted use case claims (missing use case or dead surface) —
  BEFORE the trace fan-out, so Phase 3 traces the corrected list, not the draft. (The entry-surface
  advisory itself stays quiet until flows exist; during Phase 3 it fires on every not-yet-traced
  surface and **drains as traces land** — a mid-trace wall of these warnings is expected, not a
  defect. Only what survives the full trace is a finding.)
  **Also assign each component's `subsystem`, each entity's `subdomain`, each component's `runs_in`,
  and any dep `bucket` fixes here — as a `--reconcile` file, NOT a hand-script.** Synthesis owns the
  finalized ids and has just seen the harvested `deployment[]` units, so this is where the grouping and
  the code↔process link the Deployment view needs get wired — no later phase does it, so if synthesis
  skips it the view ships empty. Author these as a declarative **`.coyodex/reconcile.json`** (kept
  OUTSIDE `build-fragments/` so the fragment glob does not sweep it) and re-run the assemble with it:
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
- Phase 3 Trace (fan out, one agent per use case; large maps may instead fan out one agent
  per subsystem — bounded context — then a non-delegated reconcile traces the cross-subsystem seams).
  Each trace agent produces its use case's **T6 flow** (the ordered `from → to` steps —
  **including the flow's central entity touches as `C→E` steps**, the entity-steps rule under T6)
  and also records the **`C→E` edges** for the components in its slice — the entities they
  persist/write/read by **direct** use. Steps and edges carry different halves of entity usage:
  the edges are the structural aggregate (every entity a component touches, in any scenario); the
  steps are the behavioral instance (THE entity this scenario is about, at its exact line) — the
  `Used in UC` view and line-level diff impact derive from the steps, so edges alone leave the
  domain model untraceable. This is *additional*: the `C↔C`/`C↔D` edges
  remain the primary output and must stay complete (every dep wired, the component graph not sparse).
  Trace-prompt discipline (all proven on live builds):
  - **Prescribe likely sub-flows in the prompts.** The lead can usually see from the use-case list
    which machinery is shared ("UC10 and UC13 walk the same tool-call path — EXTRACT it as a
    sub-flow") — say so explicitly; the duplication detector is the safety net, not the plan.
    **Do NOT blanket-ban sub-flows** ("no subflows" in every trace prompt) — that contradicts this
    rule and forgoes the cross-flow consistency sub-flows buy (a live coarse-altitude build shipped
    zero sub-flows that way). Ban them for a genuinely independent flow, never as a global default;
    where machinery repeats across ≥2 flows, prescribe the `SFn`.
  - **Name `En` as a valid step endpoint in the prompts, with a worked example step** — e.g.
    `6a. C5 → E2 : upserts the Membership document @ repo.py:155` — and require each flow's 1–2
    central entity touches (a live rebuild whose prompts channeled ALL entity mentions into the
    edges array shipped a domain model with zero flow traceability, every gate green). The
    callee's operative read/write line is one hop from the call site the agent already read for
    the calling step's `where`.
  - **Assign each trace agent an `SFn` id range** (SF1–9, SF10–19, …), exactly like the per-agent
    component id ranges, so parallel extractions never collide.
  - **A `C→E` `reads` edge — or entity step — requires the entity TYPE at the site** — a function
    operating on a string/field extracted from an entity is not reading the entity (the
    false-reads class the grounding pass keeps refuting).
  - When the lead has assembled a legend or an earlier map, pass `--ids «legend»` to each agent's
    `lint-fragment` self-check, so a plausible-but-invented element id dies in the agent's own turn.
    **Pass the legend as a FILE PATH** (`--ids path/to/legend`), never inline as `--ids "$(cat …)"` —
    a whole-map legend overflows the shell arg limit (a live build hit this on macOS). The legend
    should list the full id universe **including `UC`/`SF`/`HP` ids** (or just pass the assembled
    `project-map.json`), so a trace fragment's flow `uc` values resolve; `lint-fragment` now tolerates a
    legend that omits a whole namespace (it can't adjudicate one it doesn't cover), so a reduced
    element-only legend no longer false-flags `uc` — but a complete legend still catches an invented one.
  - A **return-direction step** usually has no invoking line of its own: set `no_call_site: true`
    (or anchor the callee's `return` statement when that aids drilling) — either is fine; silence is not.
- Phase 3.5 Re-balance reconcile (lead, not delegated — runs ONCE, after the trace). The grouping was
  cut at Phase 2 **before any edge existed**, so re-check it now against the real graph: run
  `coyodex balance` and reconcile each finding — apply a Drilling-deeper operation (nest / promote /
  flatten) via a Direct map change, or record a one-line justification under the model's
  `extras` "Balance exceptions" heading. The **sparse-root fix is judgment-only** (no proposal
  machinery exists for it — the capability-first guidance drives it); the split proposals are
  starting points, not facts. Exit criterion: `coyodex validate` emits no balance warning that is
  neither fixed nor justified. This step is not part of the per-write validate → audit → render
  invariant; maintenance re-surfaces imbalance for free through validate's always-on warnings.
- Test completeness (one agent, after the Phase 3 trace — it needs the finished inventory + flows).
  Walk the assembled map (use cases, T4 entry points, T5 entities, failure modes, critical-path
  branches) and for each ask "is there a test that exercises it?", emitting the risk-ranked gap table
  `tests[]` + `tests_note` (the **Test completeness** section above carries the full recipe — don't
  duplicate it). **Read-only by default:** build the table by *reading* tests, mark every row
  **inferred**, and set `tests_note` to state the suite was not run. Running the suite with coverage
  (upgrading rows to **verified**) is the opt-in upgrade described in that section — never run an
  unknown suite by default. The table is always produced; it must never ship empty.
- Phase 4 Adversarial verify (fan out, **fresh context**). After the map validates and `coyodex audit`
  runs (fix any blocking `why:`-ref contradiction; reconcile the read-before-create / actor advisories),
  take the audit's **L2 grounding worklist** and disprove it against the code (read it with
  `coyodex audit --json` — the machine-readable `{findings, worklist}` payload built for this
  batching step; never regex-parse the human report). **Batch by theme/risk,
  don't spawn one sub-agent per claim** — the worklist routinely has 100+ items; group the claims into a
  handful of themed skeptics (e.g. security/auth, money, core data-flow, inferred dep-usage), one
  fresh-context skeptic per batch, and for the riskiest claims (auth, scoping, encryption) run **N
  skeptics + majority vote**. Each is told to *disprove* the claim (default to *refuted* on doubt). This
  is the *breaking* twin of the parallel *build*, aimed at falsification. **Fresh context is the whole
  point** — a verifier that sees the build reasoning inherits its blind spots. Each skeptic also reports
  the ONE `file:line` where the operation **actually** happens (the true call site); a drifted anchor
  does NOT refute a true relationship (grounding truth is separate). Collect the skeptics' output as
  the **verdicts file** `anchor-drift` consumes: `{"grounding": [{"claim": <the worklist claim
  string>, "grounded": true|false|"unverifiable", "evidence": "path:line"}]}` — one row per claim
  (or per vote when N skeptics run), `claim` matching the worklist text verbatim so the tool can pair
  it, `evidence` the true call site. **Then run
  `coyodex anchor-drift --map … --verdicts …`** — a deterministic check that flags any CONFIRMED claim
  whose stored `where` drifts from the line the skeptics found; reconcile each by **fixing the map's
  `where`** (the check flags, you apply — the LLM only observed the line). **Apply the drift fixes with
  the tool, never a hand script:** `coyodex anchor-drift … --json` emits the corrected anchors and
  `coyodex fix apply-drift --map … --verdicts …` writes them, matching each on the full `(src, verb,
  dst)` triple — a hand script that keyed on endpoints-only once swapped a paired `persists`/`reads`
  edge. `apply-drift` rewrites a drifted **security-surface** anchor (`security[].source`) the same way,
  so a skeptic's corrected auth-check line lands with the tool, not a hand re-serialize. To drop a
  **refuted** edge as a terminal post-assemble fix, `coyodex fix drop-edge` removes it and reports (or,
  with `--repoint`/`--drop-steps`, heals) the flow steps that rode it. Reconcile every refutation and
  every drift (fix the map, or justify and record why); this reconcile is **not delegated**.
  Two **behavioral-consistency items** ride the same fresh-context pass (judgment calls no
  mechanical gate can make): (1) for each Happy Path step, does its **title contradict its use
  case's name or outcome**? (the "signs in; the organization exists" vs "create an organization"
  class — a title states the action, never a post-condition); (2) do two flows **retell the same
  machinery at different depths** (one spells a pipeline out in 13 steps, another compresses the
  same run to 3)? — the mechanical duplication detector only catches *identical* runs, so
  depth-inconsistent retellings are found here; fix by extracting a sub-flow or aligning the depths.
  Re-validate → re-audit → render after fixes.
  - **Ordering — `coyodex fix` is the FINAL write; do NOT `assemble` after it.** The `fix` verbs edit
    the assembled `project-map.json` in place, but the build's source of truth is the fragments, so a
    later `assemble` rebuilds the map from them and silently DISCARDS every `fix` edit. Both fresh
    builds hit exactly this (ran `fix drop-edge`, re-assembled, then hand-scripted the same drop into a
    fragment — pure wasted work). So: finish all structural/fragment changes and run your **last
    `assemble` FIRST**; then do the Phase-4 grounding reconcile (`anchor-drift` → `fix apply-drift` /
    `fix drop-edge`) as the **terminal** writes, and end with re-validate → re-audit → render — no
    re-assemble. If Phase 4 surfaces a change that must live in a fragment, edit the fragment,
    re-assemble, and re-run the grounding reconcile after (never the other way round). Keep the
    **verdicts file OUT of `build-fragments/`** (e.g. under `.coyodex/verify/`) so a `*.json` glob into
    `assemble` can't pick it up — `assemble` now skips a stray verdicts file with a note, but keeping
    it out of the fragment dir is the clean habit.
  - **Where each reconcile lives — reconcile file vs `fix` verbs.** Build-time drop/dedup (a
    cross-agent duplicate edge, a refuted edge you decide during synthesis/trace) belongs in the
    **`--reconcile` file** (`drop_edges`) or the fragments, so a re-assemble re-applies it — do NOT
    reach for `fix drop-edge` there, its edit is discarded by the next assemble. The `fix` verbs are the
    **post-assemble anchor-drift** tool only (`apply-drift` for drifted edge/security anchors,
    `drop-edge` for a refuted edge found in Phase 4 after the final assemble). One rule: assignment and
    drop that must survive a rebuild → reconcile file; a terminal anchor fix after the last assemble →
    `fix`. `--reconcile drop_edges` runs after the entity-edge derivation and heals the riding flow
    steps exactly like `fix drop-edge`, so a dropped `C→E` edge is not silently re-derived.
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
> your own fragment file (see the output rule below). **Do this work yourself — do NOT spawn your
> own sub-agents / delegate.** A sub-agent's output is silently dropped: on a live build a harvest
> agent that delegated returned prose instead of writing its fragment, and the whole slice had to be
> re-harvested. You read the files and write the one fragment; no delegation.
>
> **Files:** «absolute paths this agent owns; list a directory first, then read each file».
> **Background:** «what the main agent already learned about this slice, handed down so you
> don't re-derive it».
>
> **Expect roughly «the slice's E from the pre-index `granularity.per_dir`» components for your
> slice** (one component ≈ one module-/folder-sized unit, ≤ ~10 source files / ~3 kLOC). If you come
> out far under, you are folding subsystem-shaped dirs into single components — make those
> subsystems and recurse into their units; far over, you are splitting module-sized units.
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
> **Anchor formats** (`assemble` does not fix these up — write them right, or `coyodex validate`
> rejects them): `components[].source`, `entities[].source`, `components[].entry_point`,
> `deps[].where_configured`, `edges[].where`, `entry_points[].source`, `evidence[].file`,
> `run_commands[].source`, `security[].source`, `non_entity_types[].source`, **and the group `source`
> fields** (`subsystems[].source` / `subdomains[].source`) are all **bare** repo-root-relative refs
> (`path/to/file.py:120`; a directory anchor keeps its trailing slash, `path/dir/`; an extensionless
> ops file carrying a line is fine — `Dockerfile:1`, `Makefile:6-9`) — a bare file or directory ref,
> never a markdown link and never two refs joined by a separator (put a run command's doc pointer in
> its `command`/prose, not its `source`). `tests[].tests[].file` is also a bare anchor (a `path:line`
> or a `path/` test dir), turned into a code link. The operational free-prose fields
> (`deployment[].config_source`, `observability[].where_emitted`/`where_viewed`) are
> the deliberate exception — they stay prose, not anchors.
> **Field discipline** (what `assemble` / `validate` reject — get it right at the source): (a) every
> **required** field is present and non-null; for an **optional** field with no value **omit the key**
> entirely — do NOT emit `null` (rejected on defaulted-string fields) and do NOT emit a placeholder like
> `(none)` (fails the anchor gate). (b) Use **only** each array's exact field names — no stray keys
> (`confidence`, `notes`, `slice`, `loc`, …). (c) Every anchor is **repo-root-relative**: the repo root
> is «absolute repo path» — prefix every path with it. Minimal valid fragment:
> `{"components":[{"id":"C1","name":"AuthGate","purpose":"verifies tokens","source":"backend/auth/gate.py:10"}]}`.
> **SELF-CHECK BEFORE RETURNING (required):** run
> `«COYODEX_HOME»/.venv/bin/coyodex lint-fragment --repo «repo» «your-fragment».json` and fix every row
> it reports until it exits clean — this catches schema / anchor-format / extra-key / missing-file
> errors in YOUR context (in parallel), so nothing bounces back from the lead's `assemble`.
> If the lint prints `warning:` lines (advisory), either FIX them or **repeat them verbatim in your
> reply with one line of justification each** — never silently shrug an advisory off; the lead must
> not rediscover a warning your own lint already showed you.
> **Anchor the operative statement** — the call / write / enforce line itself — **never the enclosing
> `def`/class header** (the most common anchor-drift the adversarial pass finds).
> Your AGENT_ID is your fragment's **filename stem only** — never a field inside the JSON.
> **If you are the T5 DOMAIN-MODEL owner** (one agent owns T5 — see the harvest plan), your fragment
> also carries the **`entities` array — per-entity objects, never a flat table** (`id`, `name`,
> `store`, `meaning`, `source`, `fields`, `relations` — the semantic spec is
> [domain-cards.md](method/domain-cards.md)), with **a `relations` item wherever two entities
> relate** — the entities + their `E↔E` relations are the whole point of the slice. Each entity is a
> **real named type** (class / dataclass / enum) whose `source` anchors its **definition** — do NOT
> synthesize an entity for an unnamed concept; type embedded fields by their entity (`auth:E7`) so
> relations carry the field name. For a **field-less** relation a store realizes by keying (no FK on
> the row — e.g. a per-parent store keyed by `parent_id`), set the relation's **`keyed_by`** so the
> arrow shows the key (`«key» parent_id`) instead of a bare line — see [domain-cards.md](method/domain-cards.md).
> Mark plumbing types you deliberately did NOT model in `non_entity_types` (name + why). A directory- or subsystem-sliced agent that is **not** the T5
> owner returns its components / entry-points only and leaves `entities` to the owner.
> (Edges — including `C→E` — are traced in Phase 3, NOT harvested here; this phase returns nodes.)

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
- **Uncommitted code** → first LOOK at the diff. When it is **trivial** — comments and/or
  whitespace only, no code lines (`git -C <repo> diff -w --ignore-blank-lines -- . ':(exclude).coyodex'`
  empty, and any untracked files are non-source) — do NOT block: proceed automatically as **B**
  below and note the pin choice + the trivial diff in your report (a build once lost ~2 hours
  blocked on a single stray scratch comment). Otherwise STOP and give the user a choice, then **loop**:
  - **A (recommended)** — commit (or stash) the code first, so the baseline corresponds to a
    real commit; then re-check and record the pin as above.
  - **B** — proceed without committing, but record that the code was dirty: pin the sha with a
    `-dirty` suffix (`<short-sha>-dirty`), date = HEAD's commit date.

  Re-run the check after each round; only continue when the code is committed (A), the user
  explicitly chose B, **or** the auto-B trivial-diff rule above applied.

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
(`title`, `goal`, the pin fields — as **top-level keys**, NOT wrapped in a `header` object), and
**lint it too before assembling** (`coyodex lint-fragment .coyodex/build-fragments/header.json`): the
header is the one hand-authored fragment that otherwise skips the self-check every sub-agent runs, so a
stray key here is the one thing that still fails `assemble`. Then run:

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
**At a deliberately coarse (whole-repo overview) altitude these coverage warnings are expected, and
a recorded exception silences them per-directory:** list the consciously-folded repo-relative dirs,
one per line, under a **"Coverage exceptions"** extras heading (`plugins/: representative at coarse
altitude`). A recorded dir silences the folded-subdir / unreferenced-dir / no-entity-card warnings
**and** the per-component "unclaimed surface" warning for anything at or under it — one `plugins/`
line replaces the 63 per-plugin records a live build hand-wrote. It is **boundary-scoped**: a real
gap in an *unlisted* dir still warns, and `plugins/` never silences a `plugins-legacy/` sibling. (The
component-count-vs-E advisory has its own token — the literal `granularity` under "Balance
exceptions".)
**Then run the adversarial pass** — `.venv/bin/coyodex audit .coyodex/project-map.json`
([tools/coyodex/audit_model.py](tools/coyodex/audit_model.py)). Where validate asks *is the map
well-formed*, audit asks *is it self-contradictory*: it makes the map's two layers — the narrative
Happy Path (step order, actors) and the mechanism (T6 flows + the backbone edge list) — refute each
other, deterministically, with no code. The map is **over-determined** (each precondition is encoded
twice — once as narrative order, once as which entity a flow reads vs writes), so the two copies check
each other. Audit **blocks (exit 1) only on a hard contradiction** — a *`why:` reference that points
forward or at a nonexistent step* (unambiguous, no false positives) — which you fix like a validator
error. Its ordering/actor checks are **ADVISORY, not blocking**, on purpose: *read-before-create* (a
Happy-Path step reads an entity a later step first `writes`/`persists`/`creates` — `writes` is
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
write is **validate --check-sources → audit → render** (`--check-sources` is not optional — it is the
deterministic backstop that a nonexistent-file anchor / wrong repo-root prefix can never slip through).
**Then render the markdown view** — once the
map validates and the adversarial pass has no blocking contradiction (advisories reconciled),
regenerate the committed markdown view next to the model (assemble already wrote it; re-run after any patch):

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
