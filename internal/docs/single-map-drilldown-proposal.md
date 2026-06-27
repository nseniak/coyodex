# Design proposal — single-map nested drill-down

A design extension for coyodex: make **drilling deeper happen inside the one map**, by rendering the
**nested subsystems / subdomains the schema already allows** as real, recursive drill levels — and by
**refining altitude in place** (promote a leaf component into a subsystem on demand) instead of
spawning a second map file.

This file follows the [design-notes](design-notes.md) style: every decision is pressure-tested with a
rejected alternative, and every claim carries `file:line` evidence. It is the companion to
[grouping-proposal.md](grouping-proposal.md) (which *designed* multi-level subsystems) and
[scaling-to-large-codebases.md](scaling-to-large-codebases.md) (which motivated drilling huge
subsystems). It is an **internal rationale doc — a proposal for the maintainer, not yet the method.**

---

## Provenance

Surfaced from a real session: a coyodex run on a very large repo (mee6, `~/mee6/repos/MEE6`, ~54
top-level components) drilled the **Plugins** subsystem by generating a **separate child map** at
`.coyodex/plugins/project-map.md` (+ its own HTML), cross-linked to the parent only by a prose
markdown up-link. Investigating "is that a good idea?" exposed a structural problem and led to the
decision below. An A4 promote-on-drill demo (promoting `C22 Social Content plugins` → a top-level
subsystem `S12` with its 10 plugins as components) was built on a scratch copy, validated clean, and
rendered correctly before this proposal was written.

---

## The problem child maps create

A second map file is a **second, disconnected graph**. coyodex's bidirectional links work because
edges live in **one ID space**, stored once, with both directions derived (`method.md` relationships;
"ONE source, both views derived"). Across two files that breaks:

- **IDs don't cross files.** In the mee6 maps, `C20` = "Engagement & Leveling plugins" (parent) but
  `C20` = "verify" (child); `C22` = "Social Content plugins" vs "bot_data_collection". The same token
  means different things, and there are **zero cross-map ID references** in either file.
- **No edge can connect a parent element to a child element** — the validator (per-file) would reject
  an unresolved reference. Parent `C22` and the child's `twitch` component are *not* linked; they only
  both happen to point at `mee6/plugins/twitch`.
- **Shared elements duplicate** (MongoDB / Guild appear as unrelated nodes per file). "What uses
  MongoDB?" can't span maps.
- **The viewer can't drill across files** (parent HTML has 0 references to the child) and
  **analyze/accept/change-impact only track `.coyodex/project-map.md`** (`method/dispatch.md`
  invariant), so the child map silently drifts.

Restoring bidirectional links across files would require a whole new machinery: a qualified-ID
namespace (`plugins:C20`), a whole-forest load in validator + viewer, and cross-file navigation.

## The key finding — the gap is the viewer, not the model

The data model **already supports arbitrary nesting**, and the docs already say so:

- Schema: `Subsystem`/`Parent` membership, "optionally nested" (`method/schema-v1.md`); same for
  subdomains via the card `SUBDOMAIN:` line + Subdomains `Parent`.
- Validator: `check_hierarchy` validates parent **kind**, **cycles**, and **depth ≤ MAX_DEPTH**
  ([validate_analysis.py:282](../../tools/validate_analysis.py#L282)); `MAX_DEPTH = 3`
  ([schema_v1.py:43](../../tools/schema_v1.py#L43)).
- `grouping-proposal.md` explicitly designed "several levels of nesting."

Only the **viewer flattens**: every grouping generator buckets endpoints with `_top_subsystem` /
`_top_subdomain` ("walk to the *top* ancestor"), and the container view draws only
`_parent_of(...) is None` ([gen_viewer.py:541](../../tools/viewer/gen_viewer.py#L541),
[:577](../../tools/viewer/gen_viewer.py#L577)). The JS view-state is a flat
`container → subsystem → components` stack with no deeper drill
([viewer.js:1197](../../tools/viewer/viewer.js#L1197)).

So a nested `S4 → category → plugin` map exists fine on disk; the viewer just collapses it (a
subsystem card dumps **all** descendant components flat).

---

## Decision

**Implement nested drill-down in the single map; deprecate child maps.**

Locked decisions:
1. **Arbitrary depth** — recursive drill, any number of nested levels (not a fixed 2-tier).
2. **Symmetric** — subsystems **and** subdomains (they share the code paths).
3. **Validator warns, never blocks** on altitude — keeps the existing "problems fail, warnings are
   advisory" philosophy ([validate_analysis.py:407](../../tools/validate_analysis.py#L407)).
4. **Child maps deprecated** — single-map nested drill is the only supported way to go deeper.

Sub-decisions:
- **MAX_DEPTH**: demote the depth cap from a **blocking error** to a **non-blocking warning**, and
  raise the threshold (warn only at depth > 5). The depth cap is *not* a safety guard — the separate
  **cycle check** ([validate_analysis.py:305](../../tools/validate_analysis.py#L305)) already
  guarantees the walk terminates on any acyclic chain. The cap only flags "suspiciously deep"
  modeling. With arbitrary depth allowed, a hard error is inconsistent; a warning matches decision 3.
- **Flat "Components" view** at scale: leave as-is (the Subsystems drill is the intended entry for
  large maps).

### Rejected alternatives

- **A1 — federated child maps + cross-map linking** (qualified IDs, whole-forest load, cross-file
  nav). Rejected: it builds a large new machinery *only to re-simulate what one graph gives for
  free*. Bidirectional links, single baseline, and change-impact all come automatically from one
  graph.
- **A2 — one physical map, viewer filters altitude.** Rejected: a drilled subsystem is often a
  *different decomposition* (categories→subsystems, plugins→components), not a zoom of the same
  nodes, so a filter can't reproduce it. And it doesn't address building a big map.
- **A4-without-A3 — promote-on-drill but keep the viewer's one-level limit.** Workable today (the
  demo proved it) but the promoted subsystem must sit at the **top level** (the viewer flattens
  nesting), so you can't keep a tidy parent box around drilled children. A3 (recursive render) is the
  polish that lets promotions nest cleanly. We do both: **A4 is the authoring behavior, A3 is the
  viewer that renders it.**

---

## The core idea (drives all viewer work)

Replace the always-to-top bucket (`_top_subsystem`) with a **level-relative resolver**: when
rendering the card for group `G`, bucket each endpoint into **the immediate child of `G`** that
contains it (a child-subsystem box, or the node itself if it's a direct member), and collapse
anything outside `G`'s subtree to a sibling box **at `G`'s level**.

Property that makes arbitrary depth safe: **each card draws only its immediate children**, so any
single diagram stays small no matter how deep the tree.

The container overview and a subsystem card become the **same function at a different root** → unify
them (DRY): `gen_group_view(graph, root_or_None)` and a domain twin
`gen_domain_group_view(graph, root_or_None)`.

New helpers: `_members_of(sid_or_None)` (immediate child subsystems + components), `_child_under(nid,
ancestor)`, `_descends_from(nid, sid)`. Keep `_top_*` only where the root overview genuinely wants
top level.

---

## Workstreams

### A. Viewer rendering — `tools/viewer/gen_viewer.py`

Structural functions to convert from flatten-to-top → level-relative:
`_components_of`→`_members_of`, `_component_subgraph` (child subsystems as collapsed **drillable**
boxes), `gen_subsystem_card_mermaid`, `subsystem_component_mermaids` (emit a card for **every**
subsystem — drop the `parent is None` filter), `gen_container_mermaid` + `gen_container_edges` (unify
as `gen_group_view`; per-level crossing edges + tooltips), `gen_edge_card_mermaid` /
`edge_card_mermaids` (sibling pairs at any depth).

Domain twin (same edits): `_entities_of`→`_domain_members_of`, `gen_domain_container_mermaid` +
`gen_domain_subdomain_card`→`gen_domain_group_view`, `domain_subdomain_mermaids` (all SDs),
`gen_domain_container_edges`, `gen_domain_edge_card` / `domain_edge_card_mermaids`,
`_subdomain_namespace`.

Bridges (S↔SD): `_subsystem_bridge_lines`, `gen_bridge_card_mermaid`, `bridge_card_mermaids` — resolve
each side at its own altitude.

Plumbing: the baked dicts (`MERMAID_BY_SUB`, `MERMAID_EDGE_CARD`, `CONTAINER_EDGES`, domain
equivalents) gain entries for every level; keys unchanged so JS lookups keep working. HTML grows
somewhat.

### B. Viewer UI — `tools/viewer/viewer.js` (+ `viewer.css`)

- `ancestors(s)` ([viewer.js:1197](../../tools/viewer/viewer.js#L1197)): walk `GRAPH.nodes[sid].parent`
  for the **full** breadcrumb (`Subsystems › Plugins › Social Content`); same for `domsub`.
- `bindSubsystem` / `bindDomainSub`: make child-group boxes **inside** the frame ⌘-drillable
  (`go({kind:'subsystem', sid: child})`) by tagging them `class subsystem`.
- side panel (`showNode` / `subsystemBlock` [viewer.js:232](../../tools/viewer/viewer.js#L232)): list
  **immediate** children + a "N deeper" count, not all descendants.
- tooltips / `drillhint` / `viewer.css`: a "has children" affordance distinguishing a drillable
  sub-group from a leaf component.
- No JS test harness exists; verify via gen_viewer output assertions + one manual viewer check.

### C. The `.md` check — `tools/validate_analysis.py` (warn-only)

Nesting integrity is already enforced. Add advisory warnings: **altitude hint** (a `component` that
reads as a group — enumerates many sub-items / high edge fan-out — "consider promoting to a
subsystem"); **single-child subsystem** (a level with no grouping value); **demote MAX_DEPTH** to a
warning at depth > 5. Promotion integrity (a stale edge to a removed component) is already a blocking
error via "references resolve" — add a test, no new code.

### D. Method correction (docs) + deprecate child maps

`method.md` (recursive nesting + new **"Drill deeper = promote-on-drill"** subsection: promote on
demand, **re-trace the old aggregate edges to the new children**, validator guards, uneven altitude is
OK); `method/schema-v1.md` (nesting now renders as recursive drill; promote-on-drill; MAX_DEPTH);
`method/dispatch.md` (deeper detail = refine the one map; **child maps deprecated — never a second
file**); `method/change-impact.md` (the **promotion** change shape: retire C + add S + add child Cs +
re-trace edges; ripple/accept handling); `method/diagrams.md` (drill = arbitrary nested levels);
`method/domain-cards.md` (subdomain nesting symmetry); `method/templates/project-map.template.md` (add
commented nested-subsystem + nested-subdomain examples); `tools/viewer/README.md` (multi-level drill +
deeper breadcrumb).

### E. Tests — `tools/tests/test_grouping.py`

112 tests cover flat grouping well but have **zero nested-rendering coverage**. Add (top-level funcs,
`make_*` builders, DI — per the repo's test rules): `make_nested_subsystem_map` /
`make_nested_subdomain_map`; card exists for a non-top subsystem; parent card draws a child as a
drillable box (not flattened grandchildren); container overview shows only top-level; level-relative
crossing (grandchild→sibling renders as a crossing to the sibling box); edge card between nested
subsystems; bridge card with nested S+SD picks correct altitude; full domain symmetry; validator
warnings (coarse component, single-child subsystem, depth>5); promotion dangling-edge errors; template
nested example validates + renders. **Regression guard:** flat maps (depth 1) must render identically
— all existing tests stay green.

### F. Migration & cleanup

Document (not auto-run) the **child-map → single-map conversion recipe** (the A4 demo *is* the
recipe). The existing mee6 `.coyodex/plugins/` child map is left for the user to convert when they
choose. `VERSION` bump + changelog line. The shipped per-repo `srcRoot` namespacing (one HTML/root per
map) is unaffected — one map, one root.

---

## Sequencing

1. A (structural recursive resolver + unify), tests green throughout →
2. A (domain + bridges) →
3. B (JS navigation / breadcrumb / panel) →
4. C (validator warnings) →
5. D (docs + template + deprecate child maps) →
6. E (tests alongside each phase, TDD) →
7. F (cleanup + VERSION) →
8. Independent adversarial review (complex, viewer-wide blast radius).

## Risks

- **Regression on flat maps** from the resolver refactor → mitigated by keeping all existing tests
  green (flat = depth 1, must be identical).
- **Diagram density**: avoided by the "immediate children only" property — depth doesn't enlarge any
  single card.
- **HTML size** grows (cards for every group) — acceptable.

## Implementation log

- **Phase 1a (done)** — subsystem cards render nested levels. `_child_under` / `_sibling_level_box`
  replace flatten-to-top; `_components_of` = direct members; `_component_subgraph` draws child
  subsystems as drillable boxes; `gen_subsystem_card_mermaid` buckets every endpoint at the card's
  level; `subsystem_component_mermaids` emits a card for every subsystem. Flat byte-identical.
- **Phase 1b (done)** — domain/subdomain symmetry (`_entities_of` direct, `_child_subdomains`,
  `_descendant_entity_count`, `_sibling_subdomain_box`, `gen_domain_subdomain_card` level-relative,
  `domain_subdomain_mermaids` all levels). Plus the **"immediate children only" rule**: a parent card
  shows only its DIRECT members' deps/bridges; a child's deps/bridges live on the child's card (avoids
  clutter and the cross-arrow-to-dep mis-binding).
- **Re-sequenced** — **per-level edge cards** (`edge_card_mermaids` / `gen_container_edges` and the
  domain twins for nested sibling pairs) move from A into **Phase B**: which edge-card keys must exist
  is determined by the JS cross-arrow drill binding (`pa>pb` substitution,
  [viewer.js:889](../../tools/viewer/viewer.js#L889)), so generating them is only correct alongside
  that binding. Today nested **box** drill is fully data-backed (a card per level); nested cross-**arrow**
  click + deep breadcrumb are Phase B. No flat map is affected.
- **Phase B (done)** — the nested drill is now usable in the viewer.
  - **B1 breadcrumb** — `ancestors()` walks the parent chain via `groupChain()`, so a deep drill shows
    every level (Subsystems › Plugins › Social Content), each crumb clickable; subsystems + subdomains.
  - **B2 panel** — `showNode()` lists a group's immediate children (child groups first, each tagged with
    its descendant-leaf count, then direct leaves). Child-box ⌘-drill already worked (`bindNodes`).
  - **B3 edge cards** — one `_edge_card_pairs` source (and `_domain_edge_card_pairs` twin) enumerates
    every DISJOINT subsystem/subdomain pair an edge crosses (over the endpoints' ancestors), so edge
    cards + crossing lists exist at every drill level. `gen_edge_card_mermaid` / `gen_domain_edge_card`
    are level-relative (frame immediate children; a direct-member crossing stays labelled, a crossing
    into a child group is an aggregated box arrow). The JS binding routes an OVERLAPPING pair (a child
    of, or ancestor of, the current card) to **navigation** (descend / zoom out via `bindNavEdge`) and a
    DISJOINT pair to its edge card (guarded by existence) — for both `bindSubsystem` and `bindDomainSub`.
  - Flat maps render byte-identical throughout. End-to-end: a nested map bakes `S2>S3` + `S1>S3`, omits
    the overlapping `S1>S2`.
- **Phase C (done)** — validator warnings (all non-blocking): `MAX_DEPTH(3)` → `DEEP_NEST_WARN(5)` and
  the depth check demoted from a hard error to a warning (`check_hierarchy` now returns
  `(problems, warnings)`); `check_altitude_hints` (a component whose row lists ≥6 bare sub-unit names);
  redundant-nesting-level nudge (a group whose only child is another group of the same kind).
- **Phase D (done)** — docs: `dispatch.md` (deeper = refine in place; child maps unsupported),
  `method.md` ("Drilling deeper" rule + recursive-drill note), `schema-v1.md` (recursive render + depth
  advisory, both altitudes), `diagrams.md`, `change-impact.md` (Promotion change shape), the template
  (nested S3 + SD2 examples), `viewer/README.md`.
- **Phase E (done)** — tests: validator warnings (×3), nested subsystem/subdomain cards + edge cards,
  per-level container edges, and a render-level end-to-end nested assertion. 128 tests; pyright +
  `node --check` clean.
- **Phase F (done)** — `VERSION` 0.1.0 → 0.2.0; the scratch `_a4_demo` was removed; the existing mee6
  `plugins/` child map is left for the user to convert via the documented recipe.
- **Remaining** — independent adversarial review of the whole change (viewer-wide blast radius).
