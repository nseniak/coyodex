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
**"Used in"** row.
What changes per type is which fields fill those slots. Empty fields, fields that just repeat
the name, and fields the diagram already shows (like which box a box nests in) are dropped.

### Subsystem
| Property | Display | Action |
|---|---|---|
| Purpose | prose | |
| Used in | list of use-case links | |
| *(kind)* | badge: "subsystem" | |

### Component
| Property | Display | Action |
|---|---|---|
| Purpose | prose | |
| Entry point | text | |
| *(extra authored fields)* | text | |
| Used in | list of use-case links | |
| Triggered by | list of its T4 entry points (kind · trigger · source) | source link opens the code viewer |
| *(kind)* | badge: "component" | |

### Dependency
| Property | Display | Action |
|---|---|---|
| Used for | prose | |
| Type | text | |
| Package | text | |
| *(extra authored fields)* | text | |
| Used in | list | |
| *(type)* | two pills: `dependency` + its sub-type (datastore / service / messaging / …) | |

### Subdomain
| Property | Display | Action |
|---|---|---|
| Purpose | prose | |
| Used in | list | |
| *(kind)* | badge: "subdomain" | |

### Entity
| Property | Display | Action |
|---|---|---|
| Meaning | prose | |
| Stored | text | |
| Used in | list | |
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
| source → destination | text (each endpoint is a link to that element) | |
| Why (legacy backstop only — empty for a normal step; the backbone edge's why for a phrase-less step) | prose | |
| Note | text | |
| Source (the step's own `where`) | text link — opens the code viewer at the call site | |
| Rides arrow | list — one link per backbone edge of the pair (opens that arrow's pane) | |
| Part of sub-flow | text (only on a step expanded from a named sub-flow: ⟨name⟩ + its SF id) | |

A **sub-flow** (a shared step sequence referenced by several flows) renders **inline**: its steps
appear expanded inside each referencing flow's diagram, wrapped in a tinted block with the
sub-flow's name in a note. Each expanded step selects like any other step; its pane carries the
"Part of sub-flow" row above.

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

## The change badge

On a change-impact map, any box or edge can carry one extra **change pill**
(added / modified / deleted / rippled) after its type pill.

| Property | Display | Action |
|---|---|---|
| change | badge | |
