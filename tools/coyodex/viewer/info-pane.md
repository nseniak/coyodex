# The info pane — what each element shows

The **info pane** is the side panel that fills in when you select something in the diagram.
Its content depends on what you selected. There are three families: **box elements** (the
nested boxes in the Context / Subsystems / Entities views), **use cases** (the steps of the
Happy Path), and **arrows** (the edges between boxes).

Every value below is text in the map source. The **display** column says how the pane renders
it: *heading*, *badge* (a small coloured tag), *prose* (the one free description line),
*text* (a label → value row), *path* (a code location), or *list* (several links/items).

The **Action** column is empty on purpose — it's where we note what to do with each property
(keep, remove, move, rename, …).

---

## Box elements

Every box element renders the same way: a **title** (its name), a **kind badge**, one
**description line** as prose, then **label → value rows**, a derived **"Used in"** row, and a
**source path** at the bottom. What changes per type is which fields fill those slots. Empty
fields, fields that just repeat the name, and fields the diagram already shows (like which box a
box nests in) are dropped.

### Subsystem
| Property | Display | Action |
|---|---|---|
| Purpose | prose | |
| Confidence | text | |
| Used in | list of use-case links | |
| source | path | |
| *(kind)* | badge: "subsystem" | |

### Component
| Property | Display | Action |
|---|---|---|
| Purpose | prose | |
| Entry point | text | |
| Depends on | text | |
| Confidence | text | |
| Files | list of paths | |
| Evidence | list (path + why) | |
| *(extra authored fields)* | text | |
| Used in | list | |
| source | path | |
| *(kind)* | badge: "component" | |

### Dependency
| Property | Display | Action |
|---|---|---|
| Used for | prose | |
| Type | text | |
| Where configured | text | |
| Confidence | text | |
| Package | text | |
| Alternative | text | |
| Evidence | list | |
| *(extra authored fields)* | text | |
| Used in | list | |
| source | path | |
| *(kind)* | badge: the dependency's sub-type (datastore / service / messaging / …) | |

### Subdomain
| Property | Display | Action |
|---|---|---|
| Purpose | prose | |
| Confidence | text | |
| Used in | list | |
| source | path | |
| *(kind)* | badge: "subdomain" | |

### Entity
| Property | Display | Action |
|---|---|---|
| Meaning | prose | |
| Stored | text | |
| Used in | list | |
| source | path | |
| *(kind)* | badge: "entity" | |
| *(the entity's own fields)* | **not** in the info pane — shown as columns inside the diagram box instead | |

---

## Use case

A use case is not a box. In the UI it appears as a **step in the Happy Path**. Its info pane
shows up when you **select a Happy Path step**, **drill into a step**, or **follow a "Used in"
link** on some other element.

The use-case pane is a **flow panel**, not the box layout above:

| Property | Display | Action |
|---|---|---|
| Step title, or the use case name | heading | |
| Use case name | badge | |
| Driving actor | badge | |
| Why this step comes here | prose (only when reached as a Happy Path step that has a "why") | |
| The flow — the numbered inside steps | list; each step is "A → *verb* → B", with its why and any note inline, each endpoint a link to that element | |

> A use case also carries an **Actor** and a **Trigger → Outcome** in the map source. In normal
> navigation the use case is only ever reached through the flow panel above (where the actor is a
> badge and Trigger → Outcome is not shown), so the generic box layout is never used for a use
> case.

---

## Arrows (edges)

### Backbone edge (A → B)
| Property | Display | Action |
|---|---|---|
| Why | prose | |
| Cardinality | text | |
| Implemented by (the backing field, or a note) | text | |
| verb | badge | |
| source | path | |

### Domain relation (entity → entity)
Same as a backbone edge, plus the relation **kind** (composition / aggregation / inheritance /
association) as a badge.

| Property | Display | Action |
|---|---|---|
| Why | prose | |
| Cardinality | text | |
| Implemented by | text | |
| verb | badge | |
| kind | badge | |
| source | path | |

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
Each shows the two boxes being framed — their name + Purpose — as two prose blocks.

| Property | Display | Action |
|---|---|---|
| Both boxes' name + Purpose (Subsystem ↔ Subsystem, Subdomain ↔ Subdomain, or the structure ↔ domain bridge) | two prose blocks | |

---

## The change badge

On a change-impact map, any box or edge can carry one extra **change badge**
(added / modified / deleted / rippled) next to its kind badge.

| Property | Display | Action |
|---|---|---|
| change | badge | |
