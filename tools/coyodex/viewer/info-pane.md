# The info pane — what each element shows

The **info pane** is the side panel that fills in when you select something in the diagram.
Its content depends on what you selected. There are three families: **box elements** (the
nested boxes in the Context / Subsystems / Entities views), **use cases** (the steps of the
Happy Path), and **arrows** (the edges between boxes).

Every value below is text in the map source. The **display** column says how the pane renders
it: *heading*, *pill* (a small coloured tag), *prose* (the one free description line),
*text* (a label → value row), or *list* (several links/items). A box element's source location
is **not** shown here — selecting it syncs the file browser + code viewer, which carry the path
and the "open externally" control.

**THE location vs A location**: element sources and a flow step's `where` are precise (one thing,
one place) — they sync/link to code. An **arrow's** `where` is only an EXAMPLE call site (a witness
among possibly many), so arrows deliberately never show or open a code location — no source row,
no code-view sync, and the crossings-list rows are inert text.

**Pill convention**: every pane's title carries a **type pill first** (the element type, or — for
an arrow — the relationship). A few elements add **one** secondary pill (a dependency's sub-type,
an actor's human/service, a use case's actor). On a change-impact map a **change pill** is
appended. Everything else lives in the body.

The **Action** column is empty on purpose — it's where we note what to do with each property
(keep, remove, move, rename, …).

---

## Box elements

Every box element renders the same way: a **title** (its name), a **type pill** (two pills for a
dependency), one **description line** as prose, then **label → value rows**, and a derived
**"In use cases"** row grouped by capability. Subsystems and subdomains roll up the use cases that
reach any descendant; leaf elements list the use cases that reach them directly.
What changes per type is which fields fill those slots. Empty fields, fields that just repeat
the name, and fields the diagram already shows (like which box a box nests in) are dropped.

### Subsystem
| Property | Display | Action |
|---|---|---|
| Purpose | prose | |
| Runs in | list of process links (the deployment units running it) | opens that process's card |
| In use cases | use-case links grouped by capability; includes descendant traces | |
| *(kind)* | badge: "subsystem" | |

### Component
| Property | Display | Action |
|---|---|---|
| Purpose | prose | |
| Entry point | text | |
| *(extra authored fields)* | text | |
| Runs in | list of process links (replaces the authored text field, which said the same thing) | opens that process's card |
| In use cases | use-case links grouped by capability | |
| How it decides | the T7 business rules enforced in this component, grouped by block; explicit empty state | opens that rule's page on the Business logic tab |
| Triggered by | list of its T4 entry points (kind · trigger · source) | source link opens the code viewer |
| *(kind)* | badge: "component" | |

### Dependency
| Property | Display | Action |
|---|---|---|
| Used for | prose | |
| Type | text | |
| Package | text | |
| Runs on / Exposed as / Config source | text — present when a `deployment[]` INFRASTRUCTURE unit (one hosting no code) names this dependency; it has no process box, so its facts ride here | |
| Environments | its deployment variants, each with the manifest anchor grounding it | source link opens the code viewer |
| *(extra authored fields)* | text | |
| In use cases | use-case links grouped by capability | |
| *(type)* | two pills: `dependency` + its sub-type (datastore / service / messaging / …) | |

### Subdomain
| Property | Display | Action |
|---|---|---|
| Purpose | prose | |
| In use cases | use-case links grouped by capability; includes descendant traces | |
| *(kind)* | badge: "subdomain" | |

### Entity
| Property | Display | Action |
|---|---|---|
| Meaning | prose | |
| Stored | text | |
| In use cases | use-case links grouped by capability | |
| *(kind)* | badge: "entity" | |
| *(the entity's own fields)* | **not** in the info pane — shown as columns inside the diagram box instead | |

---

## Use case

A use case is not a box. In the UI it appears as a **step in the Happy Path**. Both selecting it
and drilling into it show the **same outside summary** — the facts from its Use Cases row:

| Property | Display | Action |
|---|---|---|
| Use case name | heading | |
| *(type)* | pill: `use case` | |
| Driving actor | pill | |
| Trigger → Outcome | prose | |

The **steps themselves are not listed** in the panel — the sequence diagram already draws every
arrow. Clicking one arrow in the diagram opens that single step's pane:

### Flow step (one arrow of a use case's flow)
Every step shows ITSELF — never the backbone arrow's text (a pair shared by several steps has one
arrow description that can't be right for each). The step's own `where` is THE location: selecting
the step syncs the file browser + code viewer to it (a step without one clears the highlights and
leaves the code viewer alone).

| Property | Display | Action |
|---|---|---|
| The step's action | heading (the step's own authored text — a phrase on every step) | |
| Why (legacy backstop only — empty for a normal step; the backbone edge's why for a phrase-less step) | prose | |
| Note | text | |
| Source (the step's own `where`) | text link — opens the code viewer at the call site | |
| Part of sub-flow | text (only on a step expanded from a named sub-flow: ⟨name⟩ + its SF id) | |
| Decides | the T7 business rules enforced at THIS step, each marked when the rule is enforced inside the same function rather than at this exact line | opens that rule's page on the Business logic tab |

The **Decides** row is keyed by *(use case, authoring container, step number)* — a step's number is
unique per container, never per use case, so a sub-flow's step 2 and the flow's own step 2 are two
different rows. Membership is DERIVED from the rule's site anchors, never authored.

A **sub-flow** (a shared step sequence referenced by several flows) renders **inline**: its steps
appear expanded inside each referencing flow's diagram, wrapped in a tinted block with the
sub-flow's name in a note. Each expanded step selects like any other step; its pane carries the
"Part of sub-flow" row above.

### Flow map arrow (the **Map** rendering)

The flow card (bottom-left of a use-case view) holds both flow controls: the **Flow as
Map / Sequence** switch and the **step player**. Map is the default. It draws the same steps as one box per touched
element — component, dependency, entity, the driving actor — in the structural views' own shapes and
colours, with no subsystem frames (each box names its area on a second line instead). Boxes select
exactly like the boxes of any other diagram, the actor box included. Hovering a model-element box
reveals a **LocateFixed** corner action labelled with its destination tab (for example, **Locate in
Subsystems** or **Locate in Entities**); it opens that element's canonical structural diagram with
the same element selected and centred. Actor boxes have no structural diagram, so they carry no
locate action.

Action icons follow the selection's origin consistently across diagrams. A direct click on a diagram
element selects it and keeps its Drill or Locate icon visible. A selection applied by the UI — stepping,
locating or drilling to a target, following a tree/pane link, switching renderings, or restoring history —
keeps the same highlight and detail pane but leaves its action icon hover-only.

The **step player walks either rendering** — same steps, same panels, same code-viewer sync; on the
Map it glows the arrow carrying the current step and dims to its two boxes. Switching rendering
mid-walk keeps your place. With no selected step it reads **Step – / N**: Previous is disabled and
Next starts at step 1 on a fresh drill. Deselecting during a walk suspends it at that visit's remembered
step; Next restores that step. Back/Forward restores both a selected step and a suspended remembered
step for that history point. Entering the use case again starts fresh at step 1.

Two things the Map deliberately does not carry: an arrow's pane grounds no single code location (its
steps have different call sites — open a step for its own), and a **sub-flow run is not framed** the
way the sequence tints it, since its steps can be spread across several arrows; each step's pane
still names the sub-flow it belongs to.

An arrow is a PAIR, and a pair can carry several steps (its label lists their numbers — the same
numbers the sequence diagram puts on its messages). A one-step arrow displays exactly the same pane
as that message in Sequence. A multi-step arrow displays the complete pane for every carried step,
with a separator between them. Outside an active stepper walk, none of its numbers is emphasized;
during a walk, the current number stays at full opacity and the others dim.

| Property | Display | Action |
|---|---|---|
| Step number + action | one complete section per carried step | |
| Explanation / note / source | same fields as the Sequence message pane | source opens code |

When the pair has a structural relationship, the arrow itself exposes a **Locate** action. It opens
the Subsystems or Entities diagram that draws the relationship and selects every displayed arrow for
that directed pair, including parallel arrows. A response step with no same-direction relationship
locates the reverse pair it is answering; the step pane does not repeat the endpoints.

---

## Actor

An actor (a Role) is selectable on the Happy Path and inside a flow.

| Property | Display | Action |
|---|---|---|
| Actor name | heading | |
| *(type)* | pill: `actor` | |
| Human / service | pill | |
| Wants | prose | |
| Drives | list (the steps this actor drives) | |

---

## Arrows (edges)

The title is `A → B`; the single type pill is the relationship (its verb, or `uses` / `connection`
/ `bridge`).

### Backbone edge (A → B)
An arrow never points at code (see "THE location vs A location" above) — its `where` stays in the
map as a validation/impact witness but is not rendered. A drawn arrow bundling parallel edges
(same pair, different verbs) lists every edge of the pair.

| Property | Display | Action |
|---|---|---|
| verb | pill (the type pill) | |
| Why | prose | |
| Cardinality | text | |
| Implemented by (the backing field, or a note) | text | |

### Domain relation (entity → entity)
Same as a backbone edge; the relation **kind** (composition / aggregation / inheritance /
association) is a body row, not a pill.

| Property | Display | Action |
|---|---|---|
| verb | pill (the type pill) | |
| Why | prose | |
| Kind | text (body row) | |
| Cardinality | text | |
| Implemented by | text | |

### Actor → System
| Property | Display | Action |
|---|---|---|
| Wants | prose | |
| (labelled "uses") | badge | |

### System → Dependency
| Property | Display | Action |
|---|---|---|
| Used for | prose | |
| Realized by | list (the component edges that fulfil it) | |

### Libraries (the folded box)
A roster of the bundled frameworks / libraries, as a list.

| Property | Display | Action |
|---|---|---|
| Bundled | list (name + type) | |

### Group-to-group edges
Title is `A → B` with one relation pill; the body shows the two boxes being framed — each one's
name + Purpose.

| Property | Display | Action |
|---|---|---|
| A → B | heading | |
| *(relation)* | pill: `connection` (subsystems) / `relations` (subdomains) / `bridge` (structure ↔ domain) | |
| Both boxes' name + Purpose | two prose blocks | |

The **group-pair overview** arrow (the bundled crossings between two groups) uses the same title +
`connections` / `relations` pill, then lists each crossing with a count in the body.

---

## Business logic (the T7 tab)

The decisions the product makes, in TWO levels — the same shape the Use Cases catalog has, because
it answers the same kind of question. Not a diagram: a decision is not a box, and drawing it as one
would invent a structure the map does not have.

**Level 1 — the decision areas.** A list of **decision areas** (blocks, nested ones named under their
parent), each holding its rules as one-line rows. A row carries only what it takes to choose: the
decision, its badges, the components it is enforced in (three, then a count), and how many traced
flow steps it governs. Clicking a row opens the rule.

**Level 2 — one rule's page.** Reached by clicking a row, by the "How it decides" / "Decides" links
in the info pane, or by a search hit on the rule. The breadcrumb reads *Business logic › <the rule>*
and walks back to the rule's own area.

| Property | Display | Action |
|---|---|---|
| The rule | heading (its short `name`) with the full decision, in product language, beneath it | |
| sweep debt / unverified | badges — both DERIVED | |
| Decision area | chip, with the area's purpose under it | back to the list, on that area |
| If it is wrong | the rule's risk, where the map states one | |
| Where it is enforced | *line — component(s)*, one row per enforcement site | the line opens the code viewer; a component chip locates it in its structural diagram |
| Enforced at these steps | step chips: *use case* step *position* (with the sub-flow's NAME when the step was authored in one) | selects and frames that step in the use case's flow |
| Touches | entity chips, only where a reached step names the entity | locates the entity's card |

Each of the three lower sections states its empty case ("No traced flow step reaches this rule")
rather than disappearing: that emptiness is a fact about the map, and hiding it reads as a rule with
nothing to say.

The step number on a chip is the step's **position in the rendered flow** — the number the arrow
badge and the step counter show — not the authored `n` the JSON carries. A sub-flow's steps are
spliced into every referencing flow keeping their own numbering, so one flow's narrative can run
1..24 over authored numbers like `1,2,3,1,2,3,4,…`. The markdown view numbers by the authored `n`
instead, and is right to: it does not expand sub-flows, so `UC9 → SF50 step 4` is a lookup its
reader can follow in T6b.

Three site states, and the difference between them is the whole point:

- **verified** — the anchor resolves and at least one component claims the file. Every owner is
  listed; a file several components claim shows all of them, because picking one would be a guess.
- **declared absence** — the rule is enforced by construction (a type, a schema constraint, a
  config-wired guard) and says so. Not a gap.
- **unverified** — the anchor resolves to a file NO component claims, so nothing can check it. Drawn
  dashed and stamped, never blank: a rule that renders bare must not look like a rule nobody wrote.

A rule's components, its steps, its entities and its sweep state are all **derived** from the site
anchors by the same Python implementation the checks and the markdown view use. Nothing on this tab
is a second answer computed in the browser.

**The tab badges only what it derives.** Two authored flags are deliberately **not shown**:

- `confidence` — the authoring agent's own word for its own work, which nothing derives and nothing
  checks, and which comes out constant: every rule in a map carries the same value, because the
  dispatch template's example JSON spells one out and each agent copies it down its whole block. A
  badge on every row that separates no row from another is furniture, and stamping an unfalsifiable
  self-report is what sweep state uses a canary to avoid.
- `access` — a real distinction, but the System tab's **Security & auth** section IS the access
  rules, each with its risk and its enforcement sites. A bare word here was a second, poorer
  rendering of something that already has a home.

Both fields still reach the model, the markdown view and the security surface.

---

## The change badge

On a change-impact map, any box or edge can carry one extra **change pill**
(added / modified / deleted / rippled) after its type pill.

| Property | Display | Action |
|---|---|---|
| change | badge | |
