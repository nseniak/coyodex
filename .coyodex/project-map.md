# coyodex — Codebase Analysis

<!-- GENERATED VIEW — do not edit. The source of truth is project-map.json; regenerate this
     file with `coyodex render project-map.json project-map.md`. -->

> Built with the **coyodex** method. Behavioral layer first (Goal → Glossary → Roles →
> Use cases → Happy Path), then the structural machine (Components → Entry points /
> Model / Deps → Flows + Edges), joined at **use case ↔ flow**.
> The committed source of truth is `project-map.json` (JSON); this file is a generated
> view. IDs, cross-references, and confidence tags are validated by
> `coyodex validate project-map.json`.
> **Commit:** `025e6a4` · **Committed:** `2026-07-28` · **Built:** `2026-07-28 21:40`

---

## T0 — Goal (the anchor)

coyodex is for a developer whose AI coding agent has generated more code than they can hold in their head — the point where the project still runs but nobody knows what is under it (the "Coyote Effect"). It gives that developer a top-down, drillable map of their own repo: a behavioral layer (goal, roles, use cases, one ordered Happy Path) over a structural layer (subsystems, components, dependencies, a domain model, and per-use-case flows), where every box and arrow is written in plain language and anchored to a real file:line. The map is not a drawing: it is a JSON model committed next to the code and pinned to a commit, produced by a coding agent following a written method, checked by deterministic tools (schema + semantics, self-contradiction, diagram balance, anchor grounding), rendered as a committed markdown view, and served live as an interactive C4 viewer. When the code changes, the same tools project the diff onto the map, show what it ripples to, and fold the result back into the baseline — so the map stays in step with the code instead of rotting.

---

## Glossary — the ubiquitous language

| Term | Meaning | Defined / used in |
|---|---|---|
| **Map (project map)** | the whole deliverable: one JSON model of a codebase, pinned to a commit and committed next to the code | [model.py](tools/coyodex/model.py:398) |
| **Baseline pin** | the commit (+ date) the map describes exactly; every anchor in the map is a location at that commit | [model.py](tools/coyodex/model.py:403) |
| **Fragment** | a partial map model one build agent returns — a subset of the top-level arrays, merged by `assemble` | [assemble.py](tools/coyodex/assemble.py:118) |
| **Component (C)** | one module-/folder-sized unit of code with a single purpose — the leaf box of the structural layer | [model.py](tools/coyodex/model.py:99) |
| **Subsystem (S)** | a group of components and/or nested subsystems; membership is a single parent pointer carried on the child | [model.py](tools/coyodex/model.py:73) |
| **Dependency (D)** | something outside the project the code talks to — an external system drawn at Context, or an in-process library that folds away | [model.py](tools/coyodex/model.py:124) |
| **Entity (E) / domain card** | a real named type in the domain, carrying its fields, its relations to other entities, and where it is stored | [model.py](tools/coyodex/model.py:244) |
| **Subdomain (SD)** | a bounded context grouping entities — the domain-model analog of a subsystem | [model.py](tools/coyodex/model.py:73) |
| **Backbone edge** | one project-wide relationship between components, dependencies and entities, carrying a verb, a why and a witness call site | [model.py](tools/coyodex/model.py:313) |
| **Flow (T6)** | the inside view of one use case: ordered from → to steps, each with its own action phrase and its own call site | [model.py](tools/coyodex/model.py:293) |
| **Sub-flow (SF)** | a step sequence shared by two or more flows, defined once and referenced by a single step | [model.py](tools/coyodex/model.py:300) |
| **Happy Path** | one ordered walk through the use cases that tells the product's story end to end; each step is a use case | [model.py](tools/coyodex/model.py:65) |
| **Anchor** | a bare repo-relative source location — a file with an optional line, or a directory ref ending in / | [anchors.py](tools/coyodex/anchors.py:21) |
| **Witness (`where`)** | the call site that grounds a backbone edge — an example location, not the only one; a step's `where` is THE location | [model.py](tools/coyodex/model.py:318) |
| **Grounding worklist (L2)** | the ranked list of 'what this actually does' claims that no deterministic check can settle, handed to fresh-context skeptics to disprove | [audit_model.py](tools/coyodex/audit_model.py:358) |
| **Anchor drift** | a stored anchor that no longer points at the line where the operation actually happens | [anchors.py](tools/coyodex/anchors.py:85) |
| **Pre-index** | the code-derived sizing input: per-directory weight, a symbol index, and the component expectation E | [preindex.py](tools/coyodex/preindex.py:260) |
| **E (expected components)** | how many components the code tree alone says a repo (or a slice) should have — an advisory zoom anchor for the leaf decision | [preindex_lib.py](tools/coyodex/preindex_lib.py:461) |
| **Fan-out** | how many boxes one rendered diagram shows — its node's immediate children; the readable target is 5±2 | [balance_lib.py](tools/coyodex/balance_lib.py:250) |
| **Activation** | who starts an entry point — `self` (a job, loop, consumer or boot hook) or `external` (something outside asks) | [grammar.py](tools/coyodex/grammar.py:223) |
| **Bucket** | a dependency's purpose group, used to cluster deps inside the Context view or the folded Libraries drill | [grammar.py](tools/coyodex/grammar.py:111) |
| **Store mode** | how an entity relates to its physical store — its own collection, embedded in a parent, transient, cached, in-code, or an enum | [grammar.py](tools/coyodex/grammar.py:243) |
| **Ripple** | the map elements a change reaches indirectly — through structure, behavior, or the domain model — beyond the lines it hit directly | [impact_ripple.py](tools/coyodex/impact_ripple.py:160) |
| **Map profile** | the deterministic quality signals of one built map, reduced to numbers two runs can be compared on | [profile.py](eval/tools/coyodex_eval/profile.py:35) |
| **Reconcile file** | declarative build-time directives applied on every assemble — bulk group assignments and refuted-edge drops | [reconcile.py](tools/coyodex/reconcile.py:78) |
| **View bundle** | everything the viewer frontend needs for one project — the graph plus every pre-rendered diagram, flow and config flag | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2434) |
| **Coyote Effect** | running fine on generated code you no longer understand — the moment you look down and find nothing under your feet | [README.md](README.md:26) |

---

## Roles (actors)

| Role | Kind | What they want | Use cases they drive |
|---|---|---|---|
| **Developer** | human | to understand and oversee a codebase their coding agent generated — see what it does top-down, drill to the code only where needed, and keep that picture true as the code moves | UC1, UC10, UC11, UC12, UC13, UC15, UC17 |
| **Coding agent** | service | to follow the coyodex method and produce a map that is well-formed, self-consistent and grounded in the code — and to be told, mechanically, wherever it is not | UC2, UC3, UC4, UC5, UC6, UC7, UC8, UC9, UC14, UC16 |
| **Method maintainer** | human | to know whether a change to the method or the tools makes the maps they produce better or worse, before shipping it | UC18 |

---

## Use cases

| ID | Use case | Actor | Trigger → Outcome |
|---|---|---|---|
| **UC1** | Install the coyodex skill | Developer | Runs `make install` in the coyodex clone → a repo-local virtualenv holds the `coyodex` CLI, and each agent's skills home holds a SKILL.md with this clone's absolute path baked in, so `/coyodex` works from any project. |
| **UC2** | Pre-index the repo | Coding agent | Runs `coyodex preindex` before the structural harvest → `.coyodex/preindex.json` holds the directory weight tree, the symbol index, the component expectation E per slice, and an honest list of what could not be parsed; a one-line summary lands on stderr. |
| **UC3** | Self-check a build fragment | Coding agent | A harvest or trace agent runs `coyodex lint-fragment` on its own fragment before returning → every schema, anchor-format, unknown-key and missing-file error is reported in that agent's own turn, so nothing bounces back from the lead's assemble. |
| **UC4** | Assemble the map from fragments | Coding agent | Runs `coyodex assemble <fragments> --out .coyodex --reconcile …` → the fragments merge into one canonical `project-map.json` plus its markdown view, with duplicate deps/components collapsed, actor edges stripped, missing C→E edges derived, and the reconcile assignments applied. |
| **UC5** | Validate the map | Coding agent | Runs `coyodex validate --check-sources --check-coverage` → blocking problems (dangling references, malformed anchors, unwitnessed edges, a stale committed view) and advisory nudges are printed, and the exit code says whether the map is well-formed. |
| **UC6** | Audit the map for self-contradiction | Coding agent | Runs `coyodex audit` → the narrative Happy Path and the mechanism (flows + edges) are made to refute each other, blocking only on a hard `why:` contradiction, and the ranked L2 grounding worklist is printed for fresh-context skeptics. |
| **UC7** | Correct drifted anchors | Coding agent | Feeds the skeptics' verdicts to `coyodex anchor-drift`, then `coyodex fix apply-drift` → every confirmed claim whose stored anchor sits far from the line the skeptics actually found is rewritten to that line, matched on the full edge triple. |
| **UC8** | Re-balance the map's grouping | Coding agent | Runs `coyodex balance` after the trace → every diagram's fan-out, the inter-subsystem edge matrix, and a deterministic split proposal for each over-dense screen, printed as Direct-map-change blocks to accept or justify. |
| **UC9** | Render the committed markdown view | Coding agent | Runs `coyodex render project-map.json project-map.md` → the readable markdown view is regenerated from the model in canonical order, and the project is registered so it appears on the map server's landing page. |
| **UC10** | Serve the maps | Developer | Runs `make start` once → a local server listens on 127.0.0.1:8765 and its landing page lists every project already opened, each openable, removable and reorderable; new folders are added by browsing to them. |
| **UC11** | Explore a map in the viewer | Developer | Opens `/p/<project>/` → the frontend fetches the whole view bundle and draws the Context, Subsystems, Domain, Deployment, Happy-Path and flow diagrams, each box drillable into the level below and selectable for its plain-language explanation. |
| **UC12** | Read a mapped element's source | Developer | Clicks an element's source link in the viewer → the file is shown at the map's own commit in the built-in code viewer, positioned at the anchored line, with a hand-off to the local editor or GitHub when a local file is wanted. |
| **UC13** | Explore the impact of a code change | Developer | Picks a base and a target in the viewer's impact explorer → the diff is projected onto the map's anchors, each hit labelled with how precisely it resolved (line, symbol or file), and the elements it ripples to are badged on the diagrams. |
| **UC14** | Accept a change into the baseline | Coding agent | Patches the model for the reviewed change → the map's fields are edited surgically, the pin is bumped to the new commit, provenance is re-stamped with this conversation, and the gates re-run before the map is committed with the code. |
| **UC15** | Ask for a direct map change | Developer | Asks in plain language to move, rename, split or group something → the agent edits the model surgically, stays inside what the code actually backs, re-runs validate → audit → render, and commits the result. |
| **UC16** | Look up an element in the model | Coding agent | Runs `coyodex dump --id/--record/--edges/--members` → that element's kind, name, canonical source, full stored record, incident backbone edges or group members come back as JSON, without opening the whole map. |
| **UC17** | Back up a map with its conversation | Developer | Runs `map_backup.py backup <repo>` → the stamped provenance is read and the map files are bundled with the exact conversation transcripts that produced them, under a dated folder in the coyodex clone. |
| **UC18** | Run the method-quality eval | Method maintainer | Runs `coyodex-eval run` on a freshly built map → its deterministic profile and judge report are compared against the blessed baseline, and the verdict is PASS, DRIFT or REGRESSED with the tripped gate named. |

---

## Happy Path — the spine (an ordered walk through the use cases)

The happy-path ordering of use cases. Each step IS a use case (its `*(UCn)*` tag
names it); the step's detail lives in that use case's T6 flow. An optional `why:`
line records the prerequisite that fixes the step's position.

**HP1 — Developer installs the coyodex skill into their agent** *(UC1)*
**HP2 — Agent pre-indexes the repo to size and locate the code** *(UC2)*
why: needs the CLI installed in HP1
**HP3 — Each harvest agent self-checks its fragment before returning it** *(UC3)*
why: the slices are sized from HP2's expectation E
**HP4 — Lead assembles the clean fragments into the canonical model** *(UC4)*
why: only fragments that passed HP3 assemble without bouncing
**HP5 — Agent validates the assembled map** *(UC5)*
why: needs the model written in HP4
**HP6 — Agent audits the map and takes its grounding worklist** *(UC6)*
why: runs on a map that already validates (HP5)
**HP7 — Agent corrects the anchors the skeptics refuted** *(UC7)*
why: the skeptics work HP6's worklist
**HP8 — Agent re-balances the grouping against the traced edges** *(UC8)*
why: the grouping was cut before any edge existed
**HP9 — Agent renders the committed markdown view** *(UC9)*
why: renders the map only after HP5–HP8 have settled it
**HP10 — Developer starts the local map server** *(UC10)*
why: HP9 registered the project, so it shows on the landing page
**HP11 — Developer drills the map from Context down to a component** *(UC11)*
why: needs the server from HP10
**HP12 — Developer opens the source behind a box they drilled into** *(UC12)*
why: opens the box reached by drilling in HP11
**HP13 — Developer explores what their new commit touches on the map** *(UC13)*
why: compares the working tree against the pin recorded in HP4
**HP14 — Agent accepts the reviewed change into the baseline** *(UC14)*
why: folds in what HP13 reported
**HP15 — Developer asks for the grouping to be renamed and moved** *(UC15)*
why: edits the map HP14 has just re-pinned
**HP16 — Maintainer evals the method against the blessed baseline** *(UC18)*
why: compares against a baseline blessed from an earlier build

---

## Subsystems (S) — the container altitude

| ID | Subsystem | Purpose | Parent | Tech | Source | Conf. |
|---|---|---|---|---|---|---|
| **S1** | Map model | The committed JSON model every other part reads and writes, plus the vocabulary it is written in — element ids, dependency kinds and purpose buckets, entry-point kinds, edge-verb families, domain-relation verbs, and the one canonical source-anchor format. |  | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/model.py:398 | verified |
| **S2** | Map authoring | Turning a codebase into a map: sizing and locating the code before the harvest, letting each build agent self-check its own fragment, merging the fragments into the canonical model, and recording which conversation produced it. |  | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/assemble.py:339 | verified |
| **S3** | Map verification | The gates a written map must pass: is it well-formed, does it contradict itself, are its diagrams readable, and do its claims still point at the lines where the work actually happens. |  | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/validate_model.py:2025 | verified |
| **S4** | Map viewer | Showing a map: a local server that pins every file read to the map's own commit, the builder that turns the model into every diagram the frontend draws, the generated markdown view, and the browser page the developer drills. |  | Python + browser JavaScript ([pyproject.toml](pyproject.toml:52)) | tools/coyodex/viewer/serve.py:502 | verified |
| **S5** | Change impact | Answering "what did my commit touch on the map": projecting an arbitrary git diff onto the map's anchors in the pin's line frame, then spreading from the elements it hit directly to the ones they reach. |  | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/impact_git.py:207 | verified |
| **S6** | Method-quality eval | Guarding the method itself: reducing a built map to comparable numbers, adding the semantic scores no deterministic check can see, and gating a rebuild against the blessed baseline so a method change that made maps worse is caught. |  | Python ([pyproject.toml](pyproject.toml:32)) | eval/tools/coyodex_eval/profile.py:35 | verified |
| **S7** | Method & command entry | How coyodex reaches its users: the written method a coding agent follows, the skill manifests installed into each agent's skills home, and the single command that routes every tool verb. |  | Markdown + Python ([pyproject.toml](pyproject.toml:30)) | method.md:1 | verified |

---

## T1 — Components

| ID | Component | Subsystem | Purpose | Entry point | Depends on | Conf. | Files | Evidence | Runs in |
|---|---|---|---|---|---|---|---|---|---|
| **C1** | Map model & serializer | S1 | Defines the map as typed dataclasses, loads a JSON document into them while reporting the exact JSON path of any shape violation, and writes it back through one deterministic serializer so the committed file always diffs cleanly. Also generates the documentation-only JSON Schema straight from the same dataclasses, so the two cannot drift. | [json_schema.py](tools/coyodex/json_schema.py:286) | the shared grammar for id tokens and verb families | verified | tools/coyodex/model.py · tools/coyodex/json_schema.py | [model.py](tools/coyodex/model.py:729) — load_model is the structural half of `coyodex validate` — parse, then field-by-field type check · [model.py](tools/coyodex/model.py:588) — to_canonical_json is the one serialization: fixed key order, indent 2, so the same model is byte-identical · [model.py](tools/coyodex/model.py:511) — remap_element_ids rewrites every reference when a merge collapses one element id into another | coyodex CLI, coyodex serve, coyodex-eval CLI |
| **C2** | Shared grammar & anchors | S1 | The single place every reader agrees on meaning: which id shapes exist, how a dependency's kind and purpose bucket are classified, how an entry-point kind folds to its seed and what activation it implies, what each backbone verb reveals about a dependency's role, which domain-relation verb is canonical, and what a source anchor may look like. |  | nothing inside coyodex — anchors deliberately imports no coyodex module | verified | tools/coyodex/grammar.py · tools/coyodex/anchors.py | [grammar.py](tools/coyodex/grammar.py:431) — edge_role maps a backbone verb to the role it reveals — the derivation behind a dependency's shown role · [grammar.py](tools/coyodex/grammar.py:288) — canonical_entry_kind is the one normalizer every consumer routes an entry-point kind through · [anchors.py](tools/coyodex/anchors.py:85) — anchor_drift is the deterministic judge of whether a stored anchor drifted from the reported line | coyodex CLI, coyodex serve, coyodex-eval CLI |
| **C3** | Model reader | S1 | Read-only lookups over a written map, for orchestration glue and change-impact spelunking: the whole model as JSON, or one of a deliberately tiny fixed set of slices — an id resolved to its kind, name and source; an element's full stored record; the backbone edges into and out of a node; a group's members. | [dump.py](tools/coyodex/dump.py:122) | the map model loader | verified | tools/coyodex/dump.py | [dump.py](tools/coyodex/dump.py:14) — the slice surface is fixed on purpose — this is a reader, not a query language | coyodex CLI |
| **C4** | Structural pre-index | S2 | Sizes and locates a codebase before anyone names a component: a directory tree weighted by lines, file count and git churn; a symbol index resolving names to definitions with their extents; a lower-bound import-edge advisory between components the agent already named; the code-derived component expectation E per directory; and an honest record of every file it could not parse. | [preindex.py](tools/coyodex/preindex.py:260) | tree-sitter for non-Python symbols, git for churn | verified | tools/coyodex/preindex.py · tools/coyodex/preindex_lib.py · tools/coyodex/pysrc.py | [preindex_lib.py](tools/coyodex/preindex_lib.py:477) — expected_components computes E deterministically from the code tree — the leaf-decision anchor · [preindex_lib.py](tools/coyodex/preindex_lib.py:301) — tree-sitter is imported lazily and its absence is reported as uncovered, never as empty | coyodex CLI |
| **C5** | Fragment linter | S2 | The self-check a harvest or trace agent runs on its own fragment before returning it. It reuses the validator's checks at fragment scope — schema shape, anchor format, unknown-key conventions, entry-point kinds, edge rules — and, given the repo, confirms every anchored file really exists, so a wrong repo-root prefix dies in the agent's own turn instead of at the lead's assemble. | [lint_fragment.py](tools/coyodex/lint_fragment.py:182) | the fragment loader and the validator's check functions | verified | tools/coyodex/lint_fragment.py | [lint_fragment.py](tools/coyodex/lint_fragment.py:1) — the whole point is moving the fix into the agent's own context, in parallel, instead of the lead patching serially | coyodex CLI |
| **C6** | Fragment assembler | S2 | Merges the build agents' fragments into the one canonical model. It validates each fragment alone so a bad one fails by name, refuses a duplicate id across fragments, collapses the same dependency or module found by two slices, strips backbone edges that wrongly name an actor, derives the component-to-entity edge an entity flow-step implies but nobody wrote, applies the declarative reconcile directives, and writes the model plus its markdown view. | [assemble.py](tools/coyodex/assemble.py:339) | the model serializer, the reconcile loader, the markdown view generator | verified | tools/coyodex/assemble.py · tools/coyodex/reconcile.py | [assemble.py](tools/coyodex/assemble.py:91) — _derive_entity_edges heals the missing C→E edge from the flow step, idempotently, on every assemble · [reconcile.py](tools/coyodex/reconcile.py:238) — apply_reconcile is what makes group assignments and refuted-edge drops survive a re-assemble | coyodex CLI |
| **C7** | Provenance & backup | S2 | Records which conversation produced a map — session id, build minute, mode and the code commit — into a committed provenance file, and later bundles the map files together with those exact conversation transcripts into a dated backup folder. Deliberately standalone and stdlib-only so it keeps working when the project virtualenv is broken. | [map_backup.py](tools/map_backup.py:625) | the coding agent's local transcript store and git | verified | tools/map_backup.py | [map_backup.py](tools/map_backup.py:300) — un-stamped maps are recovered by finding transcripts that actually wrote a project-map file · [map_backup.py](tools/map_backup.py:340) — transcripts are always copied, never moved — they live in the agent's live store | map backup script |
| **C8** | Model validator | S3 | Answers "is this map well-formed?". Past the structural load it checks the semantics: every referenced id resolves, groups nest without cycles under the right kind of parent, Happy-Path steps name their use case, flow steps carry a phrase and a call site, edges carry a witness, domain cards are complete, and — against the repo — that every anchor exists and no entity was synthesized. It also re-measures the tree for coverage and granularity advisories, and flags a committed markdown view that has gone stale. | [validate_model.py](tools/coyodex/validate_model.py:2217) | the model loader, the grammar, the balance advisories | verified | tools/coyodex/validate_model.py · tools/coyodex/validate_analysis.py | [validate_analysis.py](tools/coyodex/validate_analysis.py:37) — check_hierarchy is the grouping check: right-kind parent, defined, no cycles · [validate_model.py](tools/coyodex/validate_model.py:2025) — validate_model returns problems and warnings — the split between blocking and advisory | coyodex CLI, coyodex-eval CLI |
| **C9** | Model auditor | S3 | Answers "does this map contradict itself?" with no code at all, by making the map's two layers refute each other: the narrative Happy Path against the mechanism of flows and backbone edges. It blocks only on a hard prerequisite contradiction and keeps its ordering and actor checks advisory, then prints the ranked worklist of "what this actually does" claims that only a fresh-context skeptic reading the code can settle. | [audit_model.py](tools/coyodex/audit_model.py:511) | the model, expanded flows, the grammar's verb families | verified | tools/coyodex/audit_model.py | [audit_model.py](tools/coyodex/audit_model.py:358) — l2_worklist_model builds the ranked grounding worklist, most dangerous first · [audit_model.py](tools/coyodex/audit_model.py:83) — each work item carries self-describing detail so a skeptic needs no map file | coyodex CLI, coyodex-eval CLI |
| **C10** | Diagram balance | S3 | Answers "is each screen readable?". It computes every rendered diagram's immediate-children count against the 5±2 target, honours recorded exceptions, and for an over-dense screen proposes a deterministic split — a greedy modularity partition of the component graph, or of the quotient graph one level up — while refusing to propose noise on list-shaped or star-shaped screens. It only ever re-groups; it may never merge or split a component to hit a number. | [balance.py](tools/coyodex/balance.py:170) | the model's grouping and backbone edges | verified | tools/coyodex/balance.py · tools/coyodex/balance_lib.py | [balance_lib.py](tools/coyodex/balance_lib.py:448) — propose_split is the deterministic greedy proposer behind the report's suggestions · [balance_lib.py](tools/coyodex/balance_lib.py:250) — balance_warnings are the always-on advisories the validator appends | coyodex CLI, coyodex-eval CLI |
| **C11** | Grounding reconcile | S3 | Closes the grounding loop after the skeptics have read the code. It compares each confirmed claim's stored anchor against the line the skeptics reported and reports the drift deterministically, then applies the corrections to the model in place — rewriting a drifted edge or security anchor matched on the full triple, dropping a refuted edge while healing or reporting the flow steps that rode it, and resolving a duplicate domain relation by an explicit human choice. | [anchor_drift.py](tools/coyodex/anchor_drift.py:99) | the audit worklist, the anchor drift math, the model serializer | verified | tools/coyodex/anchor_drift.py · tools/coyodex/fix.py | [fix.py](tools/coyodex/fix.py:61) — apply_drift writes the corrected line, matching on the full (src, verb, dst) triple so paired edges never swap · [anchor_drift.py](tools/coyodex/anchor_drift.py:24) — consensus_evidence takes the median reported line, so one stray skeptic cannot move an anchor | coyodex CLI |
| **C12** | Map server | S4 | The viewer's whole backend, on loopback only: it serves the generic shell and shared frontend assets, each project's view data, and a file browser plus code viewer whose reads are pinned to that map's own commit — so what you read always matches what the map describes. It scans no disk: the served set is exactly the folders the developer has opened, remembered in a small recents file that concurrent writers merge rather than clobber. | [serve.py](tools/coyodex/viewer/serve.py:763) | git for every file read, the view bundle builder, the file tree builder | verified | tools/coyodex/viewer/serve.py · tools/coyodex/viewer/recents.py | [serve.py](tools/coyodex/viewer/serve.py:136) — ensure_fresh drops the per-map caches when the model file changes, so an edited map shows on the next request · [serve.py](tools/coyodex/viewer/serve.py:219) — git_show is how every file the viewer displays is read — from the commit, not the working tree · [recents.py](tools/coyodex/viewer/recents.py:92) — register_project lets a build add itself to the landing page without importing the server | coyodex serve |
| **C13** | View bundle builder | S4 | Turns the map's graph into everything the frontend draws: the Context, Subsystems, per-subsystem, edge-card, Domain, subdomain, bridge and Deployment diagrams, the Happy-Path sequence, one sequence diagram plus a readable narrative per use-case flow, the crossing-edge lists behind each aggregated arrow, and the source-link configuration. It also holds the graph data model and the parser for a change-impact report. | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2582) | the graph produced from the model, git for the origin remote | verified | tools/coyodex/viewer/gen_viewer.py · tools/coyodex/viewer/build_graph.py | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2434) — ViewBundle is the contract between this builder and the frontend · [build_graph.py](tools/coyodex/viewer/build_graph.py:111) — GraphDict is the graph shape the model is converted into | coyodex serve, coyodex-eval CLI |
| **C14** | Generated views | S4 | The pure model-to-view conversions: the committed markdown rendering in canonical section order that is never hand-edited, the graph the viewer's diagram builder consumes, and the repo's file tree tagged by how the map covers each path — so the file browser doubles as a coverage view showing what the map describes and what it misses. | [render.py](tools/coyodex/viewer/render.py:22) | the model and the shared grammar only | verified | tools/coyodex/views.py · tools/coyodex/viewer/render.py · tools/coyodex/viewer/filetree.py | [views.py](tools/coyodex/views.py:676) — model_to_graph builds the viewer's graph straight from the model, with no second grammar · [filetree.py](tools/coyodex/viewer/filetree.py:186) — build_tree tags each path self/under/has/none — the coverage overlay | coyodex CLI, coyodex serve |
| **C15** | Viewer frontend | S4 | The browser page the developer actually uses: one generic bundle for every map that fetches its project's view data at boot, renders each diagram with pan, zoom and a click-to-side-panel bridge, drills box by box down the altitudes as a back/forward history, shows the file tree and the code at the map's commit, runs the impact explorer, and hands off to the local editor or GitHub when a real file is wanted. | [viewer.html](tools/coyodex/viewer/viewer.html:1) | the map server's project API, Mermaid and svg-pan-zoom from a CDN | verified | tools/coyodex/viewer/viewer.js · tools/coyodex/viewer/viewer.css · tools/coyodex/viewer/viewer.html | [viewer.js](tools/coyodex/viewer/viewer.js:5) — all per-project data arrives from the server at boot and is assigned by applyBundle · [viewer.html](tools/coyodex/viewer/viewer.html:16) — Mermaid and svg-pan-zoom load from a pinned CDN with subresource integrity | viewer page |
| **C16** | Impact projection | S5 | Projects an arbitrary git diff onto the map's anchors. Because every anchor is a line at the pin, it re-expresses each changed file in the pin's frame across renames and compares the two sides' hunks to decide which of the pin's lines the change really affects, then resolves each anchor at the finest rung it can honestly claim — the line, the enclosing definition, or just the file — never faking precision. | [impact_git.py](tools/coyodex/impact_git.py:207) | read-only git, the pre-index's symbol extents | verified | tools/coyodex/impact_lib.py · tools/coyodex/impact_git.py | [impact_lib.py](tools/coyodex/impact_lib.py:94) — FileFrame is the pin-frame effect of a change on one file — which of the pin's lines it affects · [impact_git.py](tools/coyodex/impact_git.py:101) — rename maps come from full-tree passes, never a single-path pathspec, which would fabricate deletes | coyodex serve |
| **C17** | Impact ripple | S5 | Spreads from the elements a change hit directly to the ones they reach — the subsystem that contains them, the use cases whose flows step through them, the entities they persist — under pinned semantics: the rules apply once from the direct hits, a rippled element never re-fires, and only an opt-in call-graph walk goes further than one hop. Each reached element keeps the strongest signal that found it. Also parses a unified diff into the rows the code view paints. | [impact_ripple.py](tools/coyodex/impact_ripple.py:160) | the direct hits from the projection layer, the model's grouping, flows and edges | verified | tools/coyodex/impact_ripple.py · tools/coyodex/viewer/diffmap.py | [impact_ripple.py](tools/coyodex/impact_ripple.py:15) — the strength lattice orders every cause from direct-line down to territory · [impact_ripple.py](tools/coyodex/impact_ripple.py:56) — RippleOptions keeps the noisy links (reads-only, entity graph, call graph) off by default | coyodex serve |
| **C18** | Eval harness | S6 | The eval's deterministic orchestration: it profiles a freshly built map, attaches a judge report, compares the pair against the blessed baseline under hard gates and softer drift bands, archives the run, and promotes a run to become the new baseline. It never builds a map and never calls a model itself, so the whole pipeline is testable without an LLM. | [cli.py](eval/tools/coyodex_eval/cli.py:26) | the map profile, the judge report, the coyodex core | verified | eval/tools/coyodex_eval/cli.py · eval/tools/coyodex_eval/run.py · eval/tools/coyodex_eval/compare.py | [compare.py](eval/tools/coyodex_eval/compare.py:227) — compare applies the hard gates then the bands, and the verdict precedence is REGRESSED > DRIFT > PASS · [run.py](eval/tools/coyodex_eval/run.py:170) — bless promotes a run directory to the baseline | coyodex-eval CLI |
| **C19** | Eval profile & judge | S6 | The two measurements a comparison needs. The profile reduces a map to signals that survive an LLM rewriting it — element counts, validator and audit outcomes, coverage flags, density, balance, and the name sets a gate can watch. The judge layer holds the seam to the model: the prompt builders and aggregation math for skeptics grounding the riskiest claims and judges scoring the rubric, with the model call itself injected. | [profile.py](eval/tools/coyodex_eval/profile.py:237) | the validator and auditor for the shared parse; an injected judge for the semantic half | verified | eval/tools/coyodex_eval/profile.py · eval/tools/coyodex_eval/judge.py | [judge.py](eval/tools/coyodex_eval/judge.py:139) — Judge is the dependency-injection boundary to the model — a fake in tests, a sub-agent in the orchestrator · [judge.py](eval/tools/coyodex_eval/judge.py:208) — majority_verdict decides a claim from N skeptics, and a failed skeptic is never counted as refuted | coyodex-eval CLI |
| **C20** | Method docs | S7 | The method itself — the prompts a coding agent follows to build and maintain a map. It fixes the deliverable sections and their order, the behavioral-before-structural rule, how to pick altitude, the harvest and trace prompts, the invariant every write must pass, and the field-by-field contract of the stored model, the domain cards and the change-impact report. | [dispatch.md](method/dispatch.md:1) | the coyodex CLI verbs it prescribes | verified | method.md · method/dispatch.md · method/model.md · method/domain-cards.md · method/change-impact.md · method/diagrams.md · method/templates/project-map.template.md · method/project-map.schema.json | [dispatch.md](method/dispatch.md:3) — dispatch is the entry doc: it picks build, analyze or accept and points at every other doc · [method.md](method.md:1159) — the invariant after every write is validate --check-sources, then audit, then render |  |
| **C21** | Skill manifest & installer | S7 | The install path and the two manifests it writes. `make install` builds the repo-local virtualenv, installs both packages editable into it, and copies a SKILL.md into each agent's global skills home with this clone's absolute path substituted for the placeholder. The manifests carry no method of their own on purpose: they name the trigger phrases, separate the coyodex clone from the repo being mapped, and send the agent straight to the dispatch doc — so the method can evolve in the clone without ever reinstalling. | [Makefile](Makefile:52) | the method docs it points at | verified | skill/coyodex/SKILL.md · eval/SKILL.md · Makefile | [Makefile](Makefile:56) — the manifest is copied with __COYODEX_HOME__ replaced by this clone's absolute path · [SKILL.md](skill/coyodex/SKILL.md:12) — the manifest states that the repo is the source of truth and the skill only points at it · [Makefile](Makefile:38) — the CLI is installed editable, so the repo stays the source of truth |  |
| **C22** | CLI dispatcher | S7 | The single `coyodex` command. It parses nothing but the verb, defaults a missing map argument to the conventional path, and imports each verb's implementation lazily inside its own branch — a deliberate dependency firewall that keeps validate and render free of any third-party import, so only the pre-index path may ever touch tree-sitter. | [cli.py](tools/coyodex/cli.py:66) | every verb module, imported lazily | verified | tools/coyodex/cli.py | [cli.py](tools/coyodex/cli.py:4) — the dependency firewall: only stdlib at top level, each subcommand imported inside its branch · [cli.py](tools/coyodex/cli.py:52) — _default_map supplies the conventional map path when no positional argument is given | coyodex CLI |

---

## T2 — External dependencies

| ID | Name | Kind | Bucket | Type | Used for | Where configured | Conf. | Deployment-linked | Package | Alternative | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **D1** | git | platform | Infrastructure & runtime | version-control system, invoked read-only as a subprocess | every file the viewer shows is read from the map's own commit; the pre-index reads churn; the impact engine reads diffs, rename maps and blobs on both sides of a range | [serve.py](tools/coyodex/viewer/serve.py:176) | verified |  | git (any recent version; a system binary, not a Python package) |  | [serve.py](tools/coyodex/viewer/serve.py:176) — the server's git envelope: no shell, timeouts, ref and path safety · [impact_git.py](tools/coyodex/impact_git.py:46) — the impact engine's own read-only git runner |
| **D2** | tree-sitter | library | Source parsing | incremental parser runtime | parsing non-Python sources for the pre-index's symbol index; a deliberate, scoped exception to the stdlib-only rule, confined to the pre-index path | [pyproject.toml](pyproject.toml:19) | verified |  | tree-sitter>=0.21 (pyproject.toml optional-dependencies.preindex) | absent → the affected files are reported as uncovered, never silently counted as empty | [preindex_lib.py](tools/coyodex/preindex_lib.py:316) — imported lazily inside the pre-index, so no other command loads it |
| **D3** | tree-sitter language pack | library | Source parsing | bundled tree-sitter grammars | supplying the per-language grammar the pre-index needs to extract symbols outside Python | [pyproject.toml](pyproject.toml:20) | verified |  | tree-sitter-language-pack>=0.2 (pyproject.toml optional-dependencies.preindex) | a missing grammar makes those files uncovered rather than empty | [preindex_lib.py](tools/coyodex/preindex_lib.py:317) — get_language is how the pack supplies a grammar to the parser |
| **D4** | Mermaid | library | Frontend / UI | browser diagram renderer | drawing every diagram the view bundle emits as Mermaid source — flowcharts, class diagrams and sequence diagrams | [viewer.html](tools/coyodex/viewer/viewer.html:19) | verified |  | mermaid 11.15.0 (pinned in viewer.html with subresource integrity) |  | [viewer.js](tools/coyodex/viewer/viewer.js:1) — mermaid is the global the frontend renders through |
| **D5** | svg-pan-zoom | library | Frontend / UI | browser SVG pan/zoom control | wrapping each rendered diagram so a large map can be panned and zoomed instead of being shrunk to fit | [viewer.html](tools/coyodex/viewer/viewer.html:16) | verified |  | svg-pan-zoom 3.6.1 (pinned in viewer.html with subresource integrity) |  | [viewer.html](tools/coyodex/viewer/viewer.html:16) — loaded from the pinned CDN URL with an integrity hash |
| **D6** | jsDelivr CDN | service | Infrastructure & runtime | third-party public asset CDN | delivering the two pinned frontend bundles to the viewer page at load time; the page has no local fallback, so an outage breaks the diagrams | [viewer.html](tools/coyodex/viewer/viewer.html:16) | verified |  |  |  | [viewer.html](tools/coyodex/viewer/viewer.html:17) — each script tag carries an SRI hash, so a substituted bundle is rejected by the browser |
| **D7** | GitHub | service | Integrations | code hosting web service | the portable way to open a mapped source location when no local editor is configured — a blob URL pinned to the map's commit, derived from the repo's origin remote | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:81) | verified |  |  |  | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:74) — the GitHub repo URL is derived from the origin remote and shipped in the view bundle |
| **D8** | Local code editor | platform | Integrations | desktop editor reached through its URL scheme (VS Code, Cursor, IntelliJ, or a custom scheme) | opening a mapped file at its anchored line in the developer's own editor, from any box in the viewer | [viewer.js](tools/coyodex/viewer/viewer.js:5850) | verified |  |  | no editor chosen or no local root confirmed → the GitHub blob URL is used instead | [viewer.js](tools/coyodex/viewer/viewer.js:5913) — editorUri builds the scheme URL, or returns null when no editor or root is set |
| **D9** | Browser local storage | datastore | Data & storage | per-origin key/value store in the browser | remembering the viewer's per-machine preferences — the chosen editor, the confirmed local repo root, the GitHub repo, and the panel and pane sizes | [viewer.js](tools/coyodex/viewer/viewer.js:5868) | verified |  |  |  | [viewer.js](tools/coyodex/viewer/viewer.js:5874) — the editor choice and custom scheme are global per machine, shared across every map |
| **D10** | Local filesystem | datastore | Data & storage | plain JSON and markdown files on disk | everything coyodex persists: the map model and its markdown view, the pre-index and provenance under the mapped repo's .coyodex/, the build fragments and reconcile file, and the server's recents list under the home directory | [assemble.py](tools/coyodex/assemble.py:470) | verified |  |  |  | [recents.py](tools/coyodex/viewer/recents.py:18) — the served project list is one small JSON file in the user's home directory |
| **D11** | Claude Code transcript store | datastore | Data & storage | the coding agent's local conversation store (JSONL files per session) | locating and copying the exact conversation transcripts that produced a map, so a backup bundles the map with the reasoning behind it | [map_backup.py](tools/map_backup.py:41) | verified |  |  |  | [map_backup.py](tools/map_backup.py:208) — a session's transcript file and its sidechain folder are located by session UUID |
| **D12** | pytest | library | Build & test tooling | Python test runner | running the repo's own regression suite over the tools and the eval package | [pyproject.toml](pyproject.toml:25) | verified | yes | pytest>=8 (pyproject.toml optional-dependencies.dev) |  | [pyproject.toml](pyproject.toml:35) — testpaths pins both suites, so a bare pytest run covers tools and eval |
| **D13** | pyright | library | Build & test tooling | Python static type checker | type-checking the packages in the repo-local virtualenv as a contributor gate | [pyproject.toml](pyproject.toml:26) | verified | yes | pyright>=1.1 (pyproject.toml optional-dependencies.dev) |  | [pyrightconfig.json](pyrightconfig.json:2) — extraPaths points the checker at both source roots |
| **D14** | setuptools | library | Build & test tooling | Python build backend | building and editable-installing the two packages from the src-layout source root, and wheeling the frontend assets in as package data | [pyproject.toml](pyproject.toml:2) | verified |  | setuptools>=64 (pyproject.toml build-system.requires) |  | [pyproject.toml](pyproject.toml:44) — package-dir maps the tools/ source root and the separate eval package |

---

## T3 — How to run / build / test

| Action | Command | Source |
|---|---|---|
| Install the skill + CLI (one time) | make install | Makefile:52 |
| Install the opt-in eval skill | make install-eval | Makefile:64 |
| Contributor setup (CLI + pytest + pyright in the venv) | make dev | Makefile:42 |
| Refresh dependencies after editing pyproject | make deps | Makefile:37 |
| Start the local map server | make start   # or: make start PORT=9000 | Makefile:87 |
| Run the test suite | .venv/bin/pytest tests eval/tests | pyproject.toml:35 |
| Type-check the packages | .venv/bin/pyright coyodex | Makefile:44 |
| Regenerate the documentation JSON Schema | .venv/bin/python -m coyodex.json_schema > method/project-map.schema.json | tools/coyodex/json_schema.py:286 |
| Uninstall the skill | make uninstall | Makefile:72 |
| Remove the repo-local virtualenv | make clean | Makefile:91 |

---

## T4 — Entry points

| Kind | Trigger | Code entity | Component |
|---|---|---|---|
| agent-skill | the developer types /coyodex (or asks to map a repo) in Claude Code, Codex or Cursor | [SKILL.md](skill/coyodex/SKILL.md:1) | C21 |
| agent-skill | the maintainer types /coyodex-eval to regression-test the method | [SKILL.md](eval/SKILL.md:1) | C21 |
| cli | `coyodex <verb>` — the root dispatcher | [cli.py](tools/coyodex/cli.py:66) | C22 |
| cli | `coyodex preindex --root <repo>` | [preindex.py](tools/coyodex/preindex.py:260) | C4 |
| cli | `coyodex lint-fragment --repo <repo> <fragment.json>` | [lint_fragment.py](tools/coyodex/lint_fragment.py:182) | C5 |
| cli | `coyodex assemble <fragments> --out <dir> [--reconcile <file>]` | [assemble.py](tools/coyodex/assemble.py:339) | C6 |
| cli | `coyodex validate [map] [--check-sources] [--check-coverage]` | [validate_model.py](tools/coyodex/validate_model.py:2217) | C8 |
| cli | `coyodex audit [map] [--json]` | [audit_model.py](tools/coyodex/audit_model.py:511) | C9 |
| cli | `coyodex balance [map]` | [balance.py](tools/coyodex/balance.py:170) | C10 |
| cli | `coyodex anchor-drift --map <map> --verdicts <file>` | [anchor_drift.py](tools/coyodex/anchor_drift.py:99) | C11 |
| cli | `coyodex fix apply-drift \| drop-edge \| dedup-relation` | [fix.py](tools/coyodex/fix.py:303) | C11 |
| cli | `coyodex dump [--id \| --record \| --edges \| --members]` | [dump.py](tools/coyodex/dump.py:122) | C3 |
| cli | `coyodex render <project-map.json> <out.md>` | [render.py](tools/coyodex/viewer/render.py:22) | C14 |
| cli | `coyodex serve [FOLDER ...] [--port N] [--open]` | [serve.py](tools/coyodex/viewer/serve.py:763) | C12 |
| cli | `python -m coyodex.json_schema` — regenerate the documentation schema | [json_schema.py](tools/coyodex/json_schema.py:286) | C1 |
| cli | `python -m coyodex.viewer.gen_viewer` — dump a view bundle for two-stage debugging | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2582) | C13 |
| cli | `python tools/map_backup.py stamp <repo> --mode build --built-at <time>` | [map_backup.py](tools/map_backup.py:568) | C7 |
| cli | `python tools/map_backup.py backup <repo> [--keep] [--search]` | [map_backup.py](tools/map_backup.py:594) | C7 |
| cli | `coyodex-eval <verb>` — the eval dispatcher | [cli.py](eval/tools/coyodex_eval/cli.py:26) | C18 |
| cli | `coyodex-eval score <map> [--repo <repo>]` | [profile.py](eval/tools/coyodex_eval/profile.py:237) | C19 |
| cli | `coyodex-eval run <map>` | [run.py](eval/tools/coyodex_eval/run.py:186) | C18 |
| cli | `coyodex-eval claims <map>` | [run.py](eval/tools/coyodex_eval/run.py:259) | C18 |
| cli | `coyodex-eval hash <artifact>` | [run.py](eval/tools/coyodex_eval/run.py:318) | C18 |
| cli | `coyodex-eval judge` | [run.py](eval/tools/coyodex_eval/run.py:333) | C18 |
| cli | `coyodex-eval protocol [--against <judge.json>]` | [run.py](eval/tools/coyodex_eval/run.py:381) | C18 |
| cli | `coyodex-eval bless <run-dir>` | [run.py](eval/tools/coyodex_eval/run.py:430) | C18 |
| cli | `coyodex-eval compare <baseline> <candidate>` | [compare.py](eval/tools/coyodex_eval/compare.py:377) | C18 |
| http-route | GET / — the landing page listing every opened project | [serve.py](tools/coyodex/viewer/serve.py:517) | C12 |
| http-route | GET /api/recents — the served project cards | [serve.py](tools/coyodex/viewer/serve.py:548) | C12 |
| http-route | GET /api/browse?path= — the folder browser for adding a project | [serve.py](tools/coyodex/viewer/serve.py:555) | C12 |
| http-route | POST /api/open — add a project folder to the served set | [serve.py](tools/coyodex/viewer/serve.py:568) | C12 |
| http-route | POST /api/forget — remove a project from the served set | [serve.py](tools/coyodex/viewer/serve.py:581) | C12 |
| http-route | POST /api/reorder — reorder the landing-page cards | [serve.py](tools/coyodex/viewer/serve.py:589) | C12 |
| http-route | GET /static/<asset> — the shared frontend bundle | [serve.py](tools/coyodex/viewer/serve.py:521) | C12 |
| http-route | GET /p/<project>/ — the generic viewer shell | [serve.py](tools/coyodex/viewer/serve.py:602) | C12 |
| http-route | GET /p/<project>/api/health | [serve.py](tools/coyodex/viewer/serve.py:609) | C12 |
| http-route | GET /p/<project>/api/view — the whole view bundle the frontend renders | [serve.py](tools/coyodex/viewer/serve.py:611) | C12 |
| http-route | GET /p/<project>/api/tree — the file browser tree with map coverage | [serve.py](tools/coyodex/viewer/serve.py:620) | C12 |
| http-route | GET /p/<project>/api/symbols — the pre-index symbol search index | [serve.py](tools/coyodex/viewer/serve.py:625) | C12 |
| http-route | GET /p/<project>/api/src?path=&at= — one file, at the pin or another commit or the working tree | [serve.py](tools/coyodex/viewer/serve.py:629) | C12 |
| http-route | GET /p/<project>/api/impact?base=&target= — the projected diff and its ripple | [serve.py](tools/coyodex/viewer/serve.py:655) | C12 |
| http-route | GET /p/<project>/api/impactcommits — the pin's ancestors and descendants for the picker | [serve.py](tools/coyodex/viewer/serve.py:666) | C12 |
| http-route | GET /p/<project>/api/impactsrcdiff?path=&base=&target= — one file's inline diff | [serve.py](tools/coyodex/viewer/serve.py:669) | C12 |

---

## Subdomains (SD) — bounded contexts of the domain model

| ID | Subdomain | Purpose | Parent | Source | Conf. |
|---|---|---|---|---|---|
| **SD1** | Map model | The committed map itself, element by element: the behavioral layer (roles, use cases, the Happy Path), the structural layer (subsystems, components, dependencies, entry points), the domain cards, the flows and backbone edges, and the operational tables. Everything here is serialized into one JSON document. |  | tools/coyodex/model.py:398 | verified |
| **SD2** | Verification findings | What the gates produce about a map: a source location parsed into a comparable shape, the drift verdict on a stored anchor, an audit finding, a grounding claim handed to a skeptic, and a proposed regrouping of an over-dense diagram. |  | tools/coyodex/audit_model.py:75 | verified |
| **SD3** | Structural pre-index | What the code tree says about itself before anyone names a component: where each symbol is defined, which module a file imports, and how many components a directory subtree is expected to hold. |  | tools/coyodex/preindex_lib.py:240 | verified |
| **SD4** | Viewer graph & bundle | The shapes the viewer renders rather than stores: the map flattened into nodes and edges, the per-project bundle of pre-rendered diagrams, the file tree with its coverage tags, one served project, and a parsed change report. |  | tools/coyodex/viewer/build_graph.py:111 | verified |
| **SD5** | Change impact | How a git diff is expressed against a map: one diff hunk in the pin's coordinate frame, a file's affected line ranges, the anchors a change hits, and the options controlling how far the effect spreads. |  | tools/coyodex/impact_lib.py:169 | verified |
| **SD6** | Method-quality eval | How two builds of the same map are compared: the deterministic profile of one map, the semantic judge report over it, the thresholds and the gate, band and granularity results they produce, and the archived run. |  | eval/tools/coyodex_eval/profile.py:35 | verified |
| **SD7** | Build reconcile & provenance | The two records that survive a rebuild: the declarative directives re-applied on every assemble, and the stamped history of which conversations produced a map. |  | tools/coyodex/reconcile.py:78 | verified |
| **SD8** | Behavioral layer | Who the system is for and what they achieve with it: the roles, the ubiquitous language, the use cases and the ordered walk through them. | SD1 | tools/coyodex/model.py:38 | verified |
| **SD9** | Structural layer | The machine: the grouped components, the external dependencies, the ways in, how to run it, and the citations that ground each claim. | SD1 | tools/coyodex/model.py:99 | verified |
| **SD10** | Domain cards | The mapped project's own domain model as coyodex records it — an entity with its fields, its relations, where it is stored, and the types deliberately left out. | SD1 | tools/coyodex/model.py:244 | verified |
| **SD11** | Flows & edges | How the parts interact: the per-use-case flows and their steps, the shared sub-flows, the one backbone edge list, and the async channel catalog. | SD1 | tools/coyodex/model.py:313 | verified |
| **SD12** | Operational & lifecycle tables | The facts no diagram holds: processes and their environments, signals, security surfaces, configuration keys, the test gap table, lifecycles, and the recorded adjudications. | SD1 | tools/coyodex/model.py:338 | verified |

---

## T5 — Domain model (domain cards)

**E1 — ProjectModel** *(D10..coyodex/project-map.json — collection; one document per mapped repo, committed with the code; field order is the canonical key order so the file diffs cleanly)*
SUBDOMAIN: SD1
MEANING: the whole map of one codebase — its title and goal, the commit it is pinned to, and every element array
FIELDS: format:string · title:string · goal:string · commit:string ? · committed:string ? · built:string ? · roles:E2 [] · glossary:E3 [] · use_cases:E4 [] · happy_path:E5 [] · subsystems:E6 [] · components:E7 [] · deps:E8 [] · run_commands:E9 [] · entry_points:E10 [] · subdomains:E6 [] · entities:E11 [] · non_entity_types:E15 [] · flows:E16 [] · subflows:E18 [] · edges:E19 [] · messaging:E20 [] · deployment:E23 [] · environments:string [] · observability:E25 [] · security:E26 [] · config:E27 [] · tests_note:string · tests:E28 [] · extras:E29 []
RELATIONS: contains 1→* E2 Role · contains 1→* E3 GlossaryRow · contains 1→* E4 UseCase · contains 1→* E5 HappyStep · contains 1→* E6 Group · contains 1→* E7 Component · contains 1→* E8 Dep · contains 1→* E9 RunRow · contains 1→* E10 EntryPoint · contains 1→* E11 Entity · contains 1→* E15 NonEntityType · contains 1→* E16 Flow · contains 1→* E18 SubFlow · contains 1→* E19 Edge · contains 1→* E20 MessagingRow · contains 1→* E23 DeploymentRow · contains 1→* E25 ObservabilityRow · contains 1→* E26 SecurityRow · contains 1→* E27 ConfigRow · contains 1→* E28 TestRow · contains 1→* E29 ExtraSection
SOURCE: [model.py](tools/coyodex/model.py:398)

**E2 — Role** *(D10 — embedded; one row of the map document's roles array)*
SUBDOMAIN: SD8
MEANING: a party the system is for — a first-class element other elements reference by id, never by name
FIELDS: id:string PK · name:string · kind:string · wants:string · drives:string
RELATIONS: drives 1→* E4 UseCase {the use case names the role ids in its actors list, and the role restates them in its drives cell}
SOURCE: [model.py](tools/coyodex/model.py:38)

**E3 — GlossaryRow** *(D10 — embedded; one row of the map document's glossary array)*
SUBDOMAIN: SD8
MEANING: one term of the project's ubiquitous language, with the code home it is defined in — or none, for a pure product-level word
FIELDS: term:string PK · meaning:string · source:string ?
SOURCE: [model.py](tools/coyodex/model.py:47)

**E4 — UseCase** *(D10 — embedded; one row of the map document's use_cases array)*
SUBDOMAIN: SD8
MEANING: one goal an actor achieves in a single run — its outside view, stated as what triggers it and what the actor ends up with
FIELDS: id:string PK · name:string · actors:E2 [] FK→E2 · trigger_outcome:string
SOURCE: [model.py](tools/coyodex/model.py:56)

**E5 — HappyStep** *(D10 — embedded; one row of the map document's happy_path array; order in the array is the walk)*
SUBDOMAIN: SD8
MEANING: one position in the ordered walk through the use cases, naming the use case it realizes and, optionally, the prerequisite that fixes it there
FIELDS: id:string PK · title:string · uc:E4 ? FK→E4 · why:string ?
RELATIONS: realizes *→1 E4 UseCase
SOURCE: [model.py](tools/coyodex/model.py:65)

**E6 — Group** *(D10 — embedded; one shape, two forests — the subsystems array and the subdomains array)*
SUBDOMAIN: SD9
MEANING: a subsystem or a subdomain: a named group whose membership is a single parent pointer carried on the child, so member lists are always derived
FIELDS: id:string PK · name:string · purpose:string · parent:E6 ? · source:string ? · confidence:string · tech:string · tech_source:string
RELATIONS: contains 1→* E6 child Group
SOURCE: [model.py](tools/coyodex/model.py:73)

**E7 — Component** *(D10 — embedded; one row of the map document's components array)*
SUBDOMAIN: SD9
MEANING: one module-sized unit of code: what it is for, where it lives, which files it owns, which process runs it, and the citations that ground the claims made about it
FIELDS: id:string PK · name:string · subsystem:E6 ? FK→E6 · purpose:string · entry_point:string ? · depends_on:string · source:string ? · confidence:string · files:string [] · runs_in:string [] FK→E23 · evidence:E30 [] · states:E21 ? · extra:json
RELATIONS: has 1→* E30 EvidenceItem · has 1→0..1 E21 StateMachine · runsIn *→* E23 DeploymentRow
SOURCE: [model.py](tools/coyodex/model.py:99)

**E8 — Dep** *(D10 — embedded; one row of the map document's deps array)*
SUBDOMAIN: SD9
MEANING: something outside the project the code talks to, described by two independent axes: where it lives (its kind, which decides whether it is drawn or folded away) and what it is for (its purpose bucket)
FIELDS: id:string PK · name:string · kind:string ? · type:string · used_for:string · bucket:string · where_configured:string · confidence:string · deployment_linked:bool · package:string · alternative:string · evidence:E30 [] · extra:json
RELATIONS: has 1→* E30 EvidenceItem
SOURCE: [model.py](tools/coyodex/model.py:124)

**E9 — RunRow** *(D10 — embedded; one row of the map document's run_commands array)*
SUBDOMAIN: SD9
MEANING: one way to run, build or test the mapped project, anchored at the line that defines the command rather than a doc that mentions it
FIELDS: action:string PK · command:string · source:string
SOURCE: [model.py](tools/coyodex/model.py:142)

**E10 — EntryPoint** *(D10 — embedded; one row of the map document's entry_points array)*
SUBDOMAIN: SD9
MEANING: one way into the system — a route, a command, a tool surface, or something that starts itself; carries who activates it and, when nobody outside does, when it runs
FIELDS: kind:string · trigger:string · source:string · component:E7 FK→E7 · activation:string · runs_in:string [] · cadence:string · cadence_source:string
RELATIONS: triggers *→1 E7 Component
SOURCE: [model.py](tools/coyodex/model.py:150)

**E11 — Entity** *(D10 — embedded; one row of the map document's entities array — a domain card)*
SUBDOMAIN: SD10
MEANING: one real named type in the mapped project's domain, read whole: what it means, where it is defined, its fields, its relations to other entities, where it is physically stored, and any lifecycle it implements
FIELDS: id:string PK · name:string · store:E14 ? · meaning:string · subdomain:E6 ? FK→E6 · source:string ? · fields:E12 [] · relations:E13 [] · states:E21 ?
RELATIONS: contains 1→* E12 EntityField · contains 1→* E13 EntityRelation · has 1→0..1 E14 Store · has 1→0..1 E21 StateMachine
SOURCE: [model.py](tools/coyodex/model.py:244)

**E12 — EntityField** *(D10 — embedded; embedded in its entity's card)*
SUBDOMAIN: SD10
MEANING: one attribute of a domain entity: its name, its type — a scalar or another entity — and the small controlled markers that say whether it is a key, nullable or a collection
FIELDS: name:string · type:string · markers:string []
SOURCE: [model.py](tools/coyodex/model.py:171)

**E13 — EntityRelation** *(D10 — embedded; embedded in the source entity's card; authored on one side only)*
SUBDOMAIN: SD10
MEANING: one typed link from this entity to another, with its cardinality pair and either the storage key or the note that explains how a field-less link is actually wired
FIELDS: verb:string · target:E11 FK→E11 · src_card:string ? · dst_card:string ? · display:string · how:string ? · keyed_by:string []
SOURCE: [model.py](tools/coyodex/model.py:178)

**E14 — Store** *(D10 — embedded; embedded in its entity's card)*
SUBDOMAIN: SD10
MEANING: where an entity physically lives, structured rather than described: which dependency holds it, which compartment inside that dependency, how it relates to it, and what the shape cannot say
FIELDS: dep:E8 ? FK→E8 · container:string · mode:string · notes:string
RELATIONS: lives-in *→1 E8 Dep
SOURCE: [model.py](tools/coyodex/model.py:230)

**E15 — NonEntityType** *(D10 — embedded; one row of the map document's non_entity_types array)*
SUBDOMAIN: SD10
MEANING: a named type in the domain directories that is deliberately not modelled as an entity — a repository, a provider, an error — recorded so the coverage check does not count it as missed
FIELDS: name:string PK · source:string ? · why:string
SOURCE: [model.py](tools/coyodex/model.py:259)

**E16 — Flow** *(D10 — embedded; one row of the map document's flows array; one flow per use case)*
SUBDOMAIN: SD11
MEANING: the inside view of one use case: the ordered interactions between the components, dependencies and entities it touches
FIELDS: uc:E4 PK FK→E4 · title:string · steps:E17 []
RELATIONS: contains 1→* E17 FlowStep · detailsOf 1→1 E4 UseCase
SOURCE: [model.py](tools/coyodex/model.py:293)

**E17 — FlowStep** *(D10 — embedded; embedded in its flow or sub-flow)*
SUBDOMAIN: SD11
MEANING: one interaction in a scenario — from one element to another, with its own action phrase and its own call site, or a reference that runs a shared sub-flow at this position
FIELDS: n:int PK · src:string · dst:string · phrase:string · note:string · where:string ? · no_call_site:bool · subflow:E18 ? FK→E18
SOURCE: [model.py](tools/coyodex/model.py:269)

**E18 — SubFlow** *(D10 — embedded; one row of the map document's subflows array)*
SUBDOMAIN: SD11
MEANING: a step sequence shared by two or more flows, defined once so every flow that rides it tells the same story at the same depth; it may not itself reference another sub-flow
FIELDS: id:string PK · name:string · steps:E17 []
RELATIONS: contains 1→* E17 FlowStep
SOURCE: [model.py](tools/coyodex/model.py:300)

**E19 — Edge** *(D10 — embedded; one row of the map document's edges array — the single project-wide backbone list)*
SUBDOMAIN: SD11
MEANING: one relationship between components, dependencies and entities: a verb, the purpose the verb cannot carry, and a witness call site — or an explicit admission that there is no single call site
FIELDS: src:string · verb:string · dst:string · why:string ? · where:string ? · no_call_site:bool
SOURCE: [model.py](tools/coyodex/model.py:313)

**E20 — MessagingRow** *(D10 — embedded; one row of the map document's messaging array, keyed by channel name rather than an id)*
SUBDOMAIN: SD11
MEANING: one named channel, queue or topic — the async sibling of a backbone edge: which broker carries it, which components put messages on it and take them off, and what a message holds
FIELDS: name:string PK · kind:string · broker:E8 FK→E8 · publishers:E7 [] FK→E7 · consumers:E7 [] FK→E7 · payload:E11 FK→E11 · source:string
RELATIONS: carriedBy *→1 E8 Dep · carries *→0..1 E11 Entity
SOURCE: [model.py](tools/coyodex/model.py:194)

**E21 — StateMachine** *(D10 — embedded; embedded on the entity or component whose lifecycle it is)*
SUBDOMAIN: SD12
MEANING: a lifecycle the code actually implements — the declared state names, the transitions between them, and the line that declares them; never synthesized when the code has no named states
FIELDS: states:string [] · transitions:E22 [] · source:string
RELATIONS: contains 1→* E22 StateTransition
SOURCE: [model.py](tools/coyodex/model.py:217)

**E22 — StateTransition** *(D10 — embedded; embedded in its state machine)*
SUBDOMAIN: SD12
MEANING: one move between two declared states, and the trigger that causes it
FIELDS: src:string · dst:string · on:string
SOURCE: [model.py](tools/coyodex/model.py:210)

**E23 — DeploymentRow** *(D10 — embedded; one row of the map document's deployment array)*
SUBDOMAIN: SD12
MEANING: one process the mapped system runs as: where it runs, how it is exposed, where its configuration comes from, and which environments it belongs to
FIELDS: unit:string PK · runs_on:string · exposed_as:string · config_source:string · variants:E24 []
RELATIONS: contains 1→* E24 VariantTag
SOURCE: [model.py](tools/coyodex/model.py:338)

**E24 — VariantTag** *(D10 — embedded; embedded in its deployment row)*
SUBDOMAIN: SD12
MEANING: one environment placement of a process, together with the manifest line that grounds it — an empty source means the placement is inferred rather than proven
FIELDS: env:string · source:string
SOURCE: [model.py](tools/coyodex/model.py:325)

**E25 — ObservabilityRow** *(D10 — embedded; one row of the map document's observability array)*
SUBDOMAIN: SD12
MEANING: one signal the system emits: where it comes from, where it is looked at, and what alerts on it
FIELDS: signal:string PK · where_emitted:string · where_viewed:string · alerts:string
SOURCE: [model.py](tools/coyodex/model.py:353)

**E26 — SecurityRow** *(D10 — embedded; one row of the map document's security array)*
SUBDOMAIN: SD12
MEANING: one surface someone can reach, who can reach it, the line that actually enforces the check, and what the residual risk is
FIELDS: surface:string PK · who:string · source:string · risk:string
SOURCE: [model.py](tools/coyodex/model.py:361)

**E27 — ConfigRow** *(D10 — embedded; one row of the map document's config array)*
SUBDOMAIN: SD12
MEANING: one configuration key: what it is for, what it defaults to, and how it varies per environment — secrets by location, never by value
FIELDS: key:string PK · purpose:string · default:string · per_env:string
SOURCE: [model.py](tools/coyodex/model.py:370)

**E28 — TestRow** *(D10 — embedded; one row of the map document's tests array)*
SUBDOMAIN: SD12
MEANING: one row of the test-completeness gap table: which map elements it assesses, whether they are covered, which suites exercise them, and what the remaining risk is
FIELDS: targets:string [] · tested:string · label:string · tests:E30 [] · gap:string · confidence:string
RELATIONS: cites 1→* E30 EvidenceItem
SOURCE: [model.py](tools/coyodex/model.py:378)

**E29 — ExtraSection** *(D10 — embedded; one row of the map document's extras array)*
SUBDOMAIN: SD12
MEANING: a freeform authored section kept verbatim — and the place recorded adjudications live, where six specific headings are machine-read so a justified advisory goes quiet instead of re-firing forever
FIELDS: heading:string PK · body:string
SOURCE: [model.py](tools/coyodex/model.py:391)

**E30 — EvidenceItem** *(D10 — embedded; embedded on the component, dependency or test row that carries it)*
SUBDOMAIN: SD9
MEANING: one citation grounding a claim the map makes — the file and line a skeptic re-reads, and what it is supposed to show
FIELDS: file:string · why:string
SOURCE: [model.py](tools/coyodex/model.py:91)

**E31 — AnchorLoc** *(transient; parsed on demand from an anchor string; never stored)*
SUBDOMAIN: SD2
MEANING: a source anchor parsed into comparable parts — the path and, when the anchor carries them, the first and last line
FIELDS: path:string · lo:int ? · hi:int ?
SOURCE: [anchors.py](tools/coyodex/anchors.py:58)

**E32 — DriftResult** *(transient; computed per confirmed claim during the grounding reconcile)*
SUBDOMAIN: SD2
MEANING: the verdict on one stored anchor: whether it drifted, what it says today, the consensus line the skeptics actually found, and how far apart the two are
FIELDS: drifted:bool · stored:string · reported:int · same_file:bool · distance:int ?
RELATIONS: measures *→1 E31 AnchorLoc {both sides are parsed to anchor locations before the median line is compared}
SOURCE: [anchors.py](tools/coyodex/anchors.py:65)

**E33 — Finding** *(transient; printed by the auditor; only the exit code persists)*
SUBDOMAIN: SD2
MEANING: one thing the audit noticed about a map — which check saw it, how serious it is, where in the map it sits, and what it says
FIELDS: check:string · severity:string · location:string · message:string
SOURCE: [audit_model.py](tools/coyodex/audit_model.py:75)

**E34 — WorkItem** *(transient; emitted as the audit's L2 worklist, consumed by the grounding skeptics)*
SUBDOMAIN: SD2
MEANING: one 'what this actually does' claim a fresh-context skeptic must try to disprove, with the anchor to start from, why it is risky, and enough self-describing detail to find the code without the map
FIELDS: claim:string PK · anchor:string ? · why_risky:string · detail:string ?
SOURCE: [audit_model.py](tools/coyodex/audit_model.py:83)

**E35 — HPStep** *(transient; the auditor's own reading of a Happy-Path step, built per run)*
SUBDOMAIN: SD2
MEANING: a Happy-Path step as the auditor sees it: its position in the walk plus the step ids its prerequisite refers to, which is what makes a forward reference detectable
FIELDS: pos:int · hp_id:string PK · uc:string ? · title:string · why:string ? · why_refs:int []
RELATIONS: readingOf 1→1 E5 HappyStep {built one-for-one from the map's happy_path array at audit time}
SOURCE: [audit_model.py](tools/coyodex/audit_model.py:97)

**E36 — Proposal** *(transient; printed by the balance report as a Direct-map-change block)*
SUBDOMAIN: SD2
MEANING: one suggested child group for an over-dense diagram — its name, whether that name came from a shared directory or from purpose, and the members that would move into it
FIELDS: name:string · name_basis:string · members:string []
SOURCE: [balance_lib.py](tools/coyodex/balance_lib.py:382)

**E37 — Symbol** *(D10..coyodex/preindex.json — collection; serialized into the pre-index's symbols index, by name; the extents feed the impact engine's symbol rung)*
SUBDOMAIN: SD3
MEANING: one class or function definition found in the code — its name and kind, the file and line it starts at, and the last line of its body
FIELDS: name:string · kind:string · file:string · line:int · end:int ?
SOURCE: [preindex_lib.py](tools/coyodex/preindex_lib.py:240)

**E38 — ImportRef** *(transient; used only to compute the lower-bound import advisory between named components)*
SUBDOMAIN: SD3
MEANING: one import statement seen in a file — used as lower-bound evidence that one named component reaches another; absence is never evidence of no dependency
FIELDS: file:string · line:int · module:string
SOURCE: [preindex_lib.py](tools/coyodex/preindex_lib.py:249)

**E39 — DirExpectation** *(D10..coyodex/preindex.json — collection; serialized as the granularity block, whole-repo and per directory)*
SUBDOMAIN: SD3
MEANING: how many components one directory subtree is expected to hold, derived from the code alone; it has children only where the stop rule decided the directory was subsystem-shaped and recursed
FIELDS: path:string PK · files:int · loc:int · expected:int · children:E39 []
RELATIONS: contains 1→* E39 child DirExpectation
SOURCE: [preindex_lib.py](tools/coyodex/preindex_lib.py:461)

**E40 — Node** *(transient; built from the model per request and cached with the served project)*
SUBDOMAIN: SD4
MEANING: one drawable box in the viewer — a component, dependency, entity or group flattened into a name, a source location, display fields, and the derived extras each diagram needs
FIELDS: id:string PK · kind:string · name:string · file:string ? · line:int ? · fields:json · parent:string ? · attrs:json [] · dep_kind:string ? · files:string [] · entry_points:json [] · runs_in:string [] · roles:string [] · store:json ? · states_count:int · states_lines:string []
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:28)

**E41 — Edge (viewer)** *(transient; built from the model per request)*
SUBDOMAIN: SD4
MEANING: one drawable arrow — a backbone edge or a domain relation, carrying the cardinality, the resolved backing field and the note the info pane shows
FIELDS: src:string · verb:string · dst:string · why:string ? · where:string ? · kind:string ? · src_card:string ? · dst_card:string ? · how:string ? · fk_fields:string [] · fk_side:string ? · keyed_by:string []
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:67)

**E42 — GraphDict** *(transient; the viewer's input, rebuilt from the model whenever the map file changes)*
SUBDOMAIN: SD4
MEANING: the whole map flattened for drawing: the header, every node and arrow, the Happy Path and flows, and the reference tables the diagram itself cannot hold
FIELDS: commit:string ? · title:string ? · goal:string ? · nodes:E40 [] · edges:E41 [] · happy_path:E44 [] · flows:json [] · data_view:json · tests:E43 []
RELATIONS: contains 1→* E40 Node · contains 1→* E41 Edge (viewer) · contains 1→* E44 HappyStep (viewer) · contains 1→* E43 TestRowView
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:111)

**E43 — TestRowView** *(transient; resolved server-side so the frontend needs no id parsing)*
SUBDOMAIN: SD4
MEANING: one row of the Tests tab with its targets already resolved to names and to whether each is a box the reader can be taken to
FIELDS: targets:json [] · label:string · tested:string · tests:json [] · gap:string · confidence:string
RELATIONS: viewOf 1→1 E28 TestRow {one view row per stored test row, with element ids resolved to names and node-locatability}
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:102)

**E44 — HappyStep (viewer)** *(transient; the drawable form of a Happy-Path step)*
SUBDOMAIN: SD4
MEANING: one position in the drawn walk: it carries no story of its own, because drilling it opens the use case's flow
FIELDS: id:string PK · title:string · uc:string ? · why:string
RELATIONS: viewOf 1→1 E5 HappyStep {built one-for-one from the map's happy_path array when the graph is assembled}
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:86)

**E45 — ViewBundle** *(cache; built once per map version and cached on the served project; also archived by the eval for inspection)*
SUBDOMAIN: SD4
MEANING: everything one project's frontend needs in a single payload — the merged graph plus every pre-rendered diagram, the crossing-edge lists behind each aggregated arrow, the flows as diagrams and as narratives, and the source-link configuration
FIELDS: repoRoot:string · ghRepo:string ? · ghCommit:string ? · graph:E42 · mermaidContext:string · mermaidContainer:string · mermaidBySub:json · mermaidDomain:string · mermaidDeployment:string · mermaidHp:string · flowsMm:json · flowsNarr:json · deploymentEnvironments:string [] · hasDeployment:bool
RELATIONS: wraps 1→1 E42 GraphDict
SOURCE: [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2434)

**E46 — FileTreeNode** *(cache; built once per map version from git and cached on the served project)*
SUBDOMAIN: SD4
MEANING: one folder or file in the mapped repo, tagged by how the map covers it — so the browser doubles as a coverage view showing at a glance what the map describes and what it misses
FIELDS: name:string · path:string PK · dir:bool · node:string ? · others:string [] · sel:string ? · cov:string · mapped:int · ref:int · children:E46 []
RELATIONS: contains 1→* E46 child FileTreeNode
SOURCE: [filetree.py](tools/coyodex/viewer/filetree.py:38)

**E47 — Project** *(transient; held in the running server's memory; the folder list behind it is what persists)*
SUBDOMAIN: SD4
MEANING: one served map: its URL slug, the repo it describes, the commit every git read is pinned to, and the lazily built artifacts dropped whenever the map file changes
FIELDS: slug:string PK · repo_root:string · map_json:string · commit:string · title:string · goal:string · map_mtime:int ? · tree:E46 ? · view:E45 ?
RELATIONS: caches 1→0..1 E45 ViewBundle · caches 1→0..1 E46 FileTreeNode · serves 1→1 E1 ProjectModel {the project points at one project-map.json path and reloads it when its mtime changes}
SOURCE: [serve.py](tools/coyodex/viewer/serve.py:65)

**E48 — DiffRow** *(transient; produced per request for the code view's inline diff)*
SUBDOMAIN: SD4
MEANING: one line of a rendered file diff — whether it is a separator, unchanged, added or removed, and its line number on each side
FIELDS: op:string · old_ln:int ? · new_ln:int ? · text:string
SOURCE: [diffmap.py](tools/coyodex/viewer/diffmap.py:15)

**E49 — Hunk** *(transient; parsed from git diff output per request)*
SUBDOMAIN: SD5
MEANING: one change block expressed in the pin's coordinate frame: which of the pin's lines it replaces, and what replaces them — its identity is what lets two diffs' fates be compared
FIELDS: p_lo:int · p_len:int · plus:string [] · minus:string []
SOURCE: [impact_lib.py](tools/coyodex/impact_lib.py:36)

**E50 — ParsedDiff** *(transient; one per file pair, per side)*
SUBDOMAIN: SD5
MEANING: one file pair's diff reduced to its hunks, or the fact that the file is binary
FIELDS: hunks:E49 [] · binary:bool
RELATIONS: contains 1→* E49 Hunk
SOURCE: [impact_lib.py](tools/coyodex/impact_lib.py:51)

**E51 — FileFrame** *(transient; computed per changed file from the two side diffs)*
SUBDOMAIN: SD5
MEANING: what a change does to one file in the pin's frame: which of the pin's line ranges it affects, where content was inserted, and the honest special cases — no frame at all, binary, whitespace-only, or fully deleted
FIELDS: affected:json [] · insertions:int [] · p_absent:bool · binary:bool · whitespace_only:bool · fully_deleted:bool
SOURCE: [impact_lib.py](tools/coyodex/impact_lib.py:94)

**E52 — AnchorRef** *(transient; the seed set, indexed from the model on every impact request)*
SUBDOMAIN: SD5
MEANING: one code anchor carried by a map element — which element and which of its fields, the path and lines, whether it claims a whole directory, and the component that owns it
FIELDS: eid:string · kind:string · path:string · lo:int ? · hi:int ? · field:string · is_dir:bool · owner:string ?
SOURCE: [impact_lib.py](tools/coyodex/impact_lib.py:170)

**E53 — DirectHit** *(transient; one per anchor the change reached; the ripple seeds from exactly this set)*
SUBDOMAIN: SD5
MEANING: one map element a change reached directly, recording how it changed and — crucially — at which rung the match resolved, so the interface never shows more precision than it has
FIELDS: eid:string · kind:string · path:string · change:string · resolution:string · field:string · owner:string ? · drift_to:int ? · territory:bool
RELATIONS: resolves *→1 E52 AnchorRef {each hit is one anchor matched against its file's frame at the finest rung that holds}
SOURCE: [impact_lib.py](tools/coyodex/impact_lib.py:278)

**E54 — Change** *(transient; parsed from git name-status output)*
SUBDOMAIN: SD5
MEANING: one file's fate across a range — added, modified, deleted, renamed or copied — with both sides' paths when the file moved
FIELDS: status:string · path:string · old_path:string ?
SOURCE: [impact_git.py](tools/coyodex/impact_git.py:68)

**E55 — ImpactFile** *(transient; one per changed file in an impact run)*
SUBDOMAIN: SD5
MEANING: one changed file as the impact engine sees it: its name on the target side, the same file in the pin's frame, its fate, its frame, and the map elements it hit
FIELDS: path:string · p_path:string ? · status:string · frame:E51 ? · hits:E53 []
RELATIONS: has 1→0..1 E51 FileFrame · contains 1→* E53 DirectHit
SOURCE: [impact_git.py](tools/coyodex/impact_git.py:175)

**E56 — ImpactCore** *(transient; the projection layer's whole result, handed to the ripple layer)*
SUBDOMAIN: SD5
MEANING: one impact run before any spreading: the three commits it is expressed between, every changed file, and the warnings about anything it could not do exactly
FIELDS: pin:string · base:string · target:string · files:E55 [] · warnings:string []
RELATIONS: contains 1→* E55 ImpactFile
SOURCE: [impact_git.py](tools/coyodex/impact_git.py:184)

**E57 — RippleOptions** *(transient; read from the request's query string; the noisy links default to off)*
SUBDOMAIN: SD5
MEANING: how far an effect is allowed to spread — whether read-only data links, the entity graph and the transitive call graph are followed, and how deep
FIELDS: reads:bool · entity_graph:bool · callgraph:bool · callgraph_depth:int
SOURCE: [impact_ripple.py](tools/coyodex/impact_ripple.py:56)

**E58 — MapProfile** *(D10.profile.json — collection; written into each eval run directory and into the blessed baseline)*
SUBDOMAIN: SD6
MEANING: the deterministic quality signals of one built map — element counts, validator and audit outcomes, coverage, density, balance, flow granularity and the name sets a gate can watch — chosen so two runs of an LLM-authored map are still comparable
FIELDS: use_cases:int · components:int · deps:int · entities:int · edges:int · validate_ok:bool · validate_problems:int · contradictions:int · l2_claims:int · coverage_flags:int ? · edges_per_component:float ? · granularity_expected:int ? · root_fanout:int ? · auth_surfaces:string [] · use_case_names:string [] · entity_names:string []
RELATIONS: profileOf 1→1 E1 ProjectModel {built by loading one map document and running the shared validate and audit parse over it}
SOURCE: [profile.py](eval/tools/coyodex_eval/profile.py:35)

**E59 — GroundingVerdict** *(transient; one per skeptic vote; only the aggregate survives into the judge report)*
SUBDOMAIN: SD6
MEANING: one skeptic's answer on one claim — held, refuted, or a failure that must never be scored as a refutation — with the evidence behind it
FIELDS: claim:string FK→E34 · grounded:bool ? · evidence:string
RELATIONS: judges *→1 E34 WorkItem
SOURCE: [judge.py](eval/tools/coyodex_eval/judge.py:56)

**E60 — RubricVerdict** *(transient; one per judge per dimension; the median is what is kept)*
SUBDOMAIN: SD6
MEANING: one judge's score for one rubric dimension, with the justification and the line it is grounded in
FIELDS: dimension:string · score:int · justification:string · evidence:string
SOURCE: [judge.py](eval/tools/coyodex_eval/judge.py:66)

**E61 — DimensionScore** *(D10.judge.json — embedded; embedded in the judge report)*
SUBDOMAIN: SD6
MEANING: one rubric dimension's settled score — the median of the judges' answers, plus how many judges answered
FIELDS: dimension:string PK · score:float · n_judges:int
RELATIONS: has 1→* E60 RubricVerdict {the median of the N judges' scores for this dimension}
SOURCE: [judge.py](eval/tools/coyodex_eval/judge.py:74)

**E62 — JudgeProtocol** *(D10.judge.json — embedded; embedded in the judge report as its fingerprint)*
SUBDOMAIN: SD6
MEANING: which judging regime produced a set of scores — the pinned model, how many skeptics voted, how many claims were sampled, and a fingerprint of the rubric text and the prompt version; a mismatch invalidates a cached comparison instead of silently reusing it
FIELDS: model:string · n_skeptics:int · grounding_cap:int · rubric_sha:string · prompt_version:string
SOURCE: [judge.py](eval/tools/coyodex_eval/judge.py:81)

**E63 — JudgeReport** *(D10.judge.json — collection; written beside the profile in each run directory and in the baseline)*
SUBDOMAIN: SD6
MEANING: the semantic half of a map's quality: how many risky claims survived the skeptics, the rubric medians and their overall mean, how many skeptics failed outright, and how many confirmed anchors turned out to have drifted
FIELDS: n_claims:int · n_grounded:int · grounding_passrate:float ? · dimensions:E61 [] · overall:float ? · n_worklist:int · n_failures:int · protocol:E62 ? · n_anchor_checked:int · n_anchor_drifted:int · anchor_drift_rate:float ?
RELATIONS: contains 1→* E61 DimensionScore · has 1→0..1 E62 JudgeProtocol
SOURCE: [judge.py](eval/tools/coyodex_eval/judge.py:101)

**E64 — Thresholds** *(D10.thresholds.json — collection; the committed starter file, merged with any per-project override)*
SUBDOMAIN: SD6
MEANING: the rules a comparison is judged by — the hard gates that block, the drift bands that only ask for a look, and the one band measured against the code rather than the baseline
FIELDS: validate_must_not_regress:bool · no_new_contradictions:bool · coverage_flags_may_increase_by:int · auth_surfaces_must_not_drop:bool · bands:json · judge_bands:json · granularity_band_pct:float
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:91)

**E65 — GateResult** *(D10.delta.json — embedded; embedded in the delta report)*
SUBDOMAIN: SD6
MEANING: one hard gate's outcome — which gate, whether it held, and the numbers behind the answer
FIELDS: name:string PK · passed:bool · detail:string
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:130)

**E66 — BandResult** *(D10.delta.json — embedded; embedded in the delta report)*
SUBDOMAIN: SD6
MEANING: one drift band's outcome — both sides' values, the signed change, what was allowed, and whether only a fall counts as a breach
FIELDS: metric:string PK · baseline:float · candidate:float · delta_pct:float · allowed_pct:float · within:bool · shrink_only:bool
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:137)

**E67 — JudgeBand** *(D10.delta.json — embedded; embedded in the delta report; empty unless both sides carry judge reports)*
SUBDOMAIN: SD6
MEANING: one semantic-quality band — how far the candidate's grounding pass-rate or rubric score fell against the baseline, and whether that fall was allowed
FIELDS: metric:string PK · baseline:float · candidate:float · drop:float · allowed_drop:float · within:bool
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:148)

**E68 — GranularityResult** *(D10.delta.json — embedded; embedded in the delta report; absent when no side was scored with the repo)*
SUBDOMAIN: SD6
MEANING: both maps' distance from the same code-derived component expectation — reported for each, but gating only on the candidate, because the baseline's own zoom may itself be wrong
FIELDS: expected:int · baseline_components:int · candidate_components:int · baseline_delta_pct:float · candidate_delta_pct:float · allowed_pct:float · within:bool
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:158)

**E69 — DeltaReport** *(D10.delta.json — collection; written into each run directory next to the profile and judge report)*
SUBDOMAIN: SD6
MEANING: the whole comparison of a candidate against the baseline — the verdict, every gate and band it applied, and the notes that inform without ever gating
FIELDS: verdict:string · gates:E65 [] · bands:E66 [] · notes:string [] · judge_bands:E67 [] · granularity:E68 ?
RELATIONS: contains 1→* E65 GateResult · contains 1→* E66 BandResult · contains 1→* E67 JudgeBand · has 1→0..1 E68 GranularityResult · appliedUnder *→1 E64 Thresholds {the thresholds are an input to the comparison, not stored in its output}
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:173)

**E70 — RunResult** *(transient; the in-memory result; its three parts are what get archived)*
SUBDOMAIN: SD6
MEANING: one eval run of one project — the map's profile, its judge report, the comparison against the baseline, and the verdict that carries into the exit code
FIELDS: project:string · profile:E58 · judge:E63 ? · delta:E69 ? · verdict:string
RELATIONS: contains 1→1 E58 MapProfile · has 1→0..1 E63 JudgeReport · has 1→0..1 E69 DeltaReport
SOURCE: [run.py](eval/tools/coyodex_eval/run.py:45)

**E71 — SetDirective** *(D10..coyodex/reconcile.json — embedded; embedded in the reconcile file's set array)*
SUBDOMAIN: SD7
MEANING: one bulk assignment applied after every merge — which elements, and which of grouping, runtime placement or purpose bucket to set on them; on the list field it replaces rather than appends, so re-running changes nothing
FIELDS: ids:string [] · subsystem:string ? · subdomain:string ? · runs_in:string [] ? · bucket:string ?
SOURCE: [reconcile.py](tools/coyodex/reconcile.py:55)

**E72 — DropEdgeDirective** *(D10..coyodex/reconcile.json — embedded; embedded in the reconcile file's drop_edges array)*
SUBDOMAIN: SD7
MEANING: one refuted backbone edge to remove on every assemble, and what to do with the flow steps that rode it — report them, drop them, or repoint them somewhere else
FIELDS: src:string · verb:string · dst:string · drop_steps:bool · repoint:string ?
SOURCE: [reconcile.py](tools/coyodex/reconcile.py:67)

**E73 — Reconcile** *(D10..coyodex/reconcile.json — collection; kept outside the fragments folder so the fragment glob never sweeps it)*
SUBDOMAIN: SD7
MEANING: the declarative build-time directives applied after the merge and before the write, so a re-assemble always re-applies them instead of silently reverting a whole synthesis pass
FIELDS: sets:E71 [] · drop_edges:E72 []
RELATIONS: contains 1→* E71 SetDirective · contains 1→* E72 DropEdgeDirective
SOURCE: [reconcile.py](tools/coyodex/reconcile.py:78)

**E74 — SessionEntry** *(D10..coyodex/provenance.json — embedded; embedded in the provenance record's sessions array; re-stamping the same session updates its entry)*
SUBDOMAIN: SD7
MEANING: one conversation that built or accepted a map — its session id, the minute it finished, what it was doing, and the code commit it was working against
FIELDS: session_id:string PK · built_at:string · mode:string · code_commit:string ? · code_committed:string ?
SOURCE: [map_backup.py](tools/map_backup.py:56)

**E75 — Provenance** *(D10..coyodex/provenance.json — collection; committed with the map so a backup can find the transcripts deterministically later)*
SUBDOMAIN: SD7
MEANING: the record of which conversations produced a map, so the map can later be bundled with the exact reasoning behind it
FIELDS: project:string PK · repo_path:string · sessions:E74 [] · schema:string
RELATIONS: contains 1→* E74 SessionEntry
SOURCE: [map_backup.py](tools/map_backup.py:83)

---

## Non-entity types (plumbing, deliberately unmodelled)

| Type | Source | Why |
|---|---|---|
| ModelError | tools/coyodex/model.py:31 | an exception carrying the JSON path of a shape violation — error plumbing, not a domain concept |
| ReconcileError | tools/coyodex/reconcile.py:40 | the reconcile loader's own exception type |
| Judge | eval/tools/coyodex_eval/judge.py:139 | the dependency-injection boundary to the model — a protocol, not data; a fake implements it in tests and a sub-agent-backed one in the orchestrator |
| PrecomputedJudge | eval/tools/coyodex_eval/judge.py:266 | an adapter that replays verdicts an orchestrator already collected |
| RecentsStore | tools/coyodex/viewer/recents.py:24 | the repository over the served-folders file; the data it holds is a bare list of paths with no named type |
| Handler | tools/coyodex/viewer/serve.py:502 | the HTTP request handler — the server's routing plumbing |
| _Maps | tools/coyodex/impact_ripple.py:77 | lookup indexes built once per impact call from the model, not a stored shape |
| _Impact | tools/coyodex/impact_ripple.py:64 | the ripple layer's working accumulator for one element, flattened into the response payload |

---

## T6 — Use-case flows

**UC1 — Install the coyodex skill**
1. Developer → C21 : clones the coyodex repo and runs `make install` from its root @ [Makefile](Makefile:52)
2. C21 → D10 : creates the repo-local virtualenv if it is not there yet @ [Makefile](Makefile:31) · fails fast with a readable message when python3 is missing or too old
3. C21 → D14 : installs both packages editable into that virtualenv, with the pre-index extra @ [Makefile](Makefile:38) · editable, so the clone stays the source of truth and docs evolve without reinstalling
4. C21 → D10 : writes a SKILL.md into each agent's skills home with this clone's absolute path substituted for the placeholder @ [Makefile](Makefile:56)
5. C21 → C20 : the installed manifest points the agent at the method's dispatch doc, which stays in the clone @ [SKILL.md](skill/coyodex/SKILL.md:26)
6. C21 → Developer : reports the home each skill landed under, and the clone it points back at @ [Makefile](Makefile:57)

**UC2 — Pre-index the repo**
1. Coding agent → C22 : runs `coyodex preindex --root <repo>` after drafting the behavioral layer @ [cli.py](tools/coyodex/cli.py:76)
2. C22 → C4 : routes to the pre-index, the one code path allowed to load a third-party parser @ [cli.py](tools/coyodex/cli.py:78)
3. C4 → D1 : asks git for each file's change count, to weight the tree by churn as well as size @ [preindex_lib.py](tools/coyodex/preindex_lib.py:159)
4. C4 → E37 : records every class and function definition it finds with its file, line and extent @ [preindex_lib.py](tools/coyodex/preindex_lib.py:265) · Python through the standard library's own parser; other languages only when the grammar pack is installed
5. C4 → D3 : asks the language pack for the grammar of each non-Python language it meets @ [preindex_lib.py](tools/coyodex/preindex_lib.py:318)
6. C4 → E39 : computes how many components each directory subtree should hold, recursing only where a directory is subsystem-shaped @ [preindex_lib.py](tools/coyodex/preindex_lib.py:511)
7. C4 → D10 : writes the weight tree, symbols, granularity and coverage blocks as one committed JSON file @ [preindex.py](tools/coyodex/preindex.py:306)
8. C4 → Coding agent : prints the heaviest directories, the totals and the expectation on stderr, with the reminder to reconcile rather than copy @ [preindex.py](tools/coyodex/preindex.py:310)

**UC3 — Self-check a build fragment**
1. Coding agent → C22 : runs `coyodex lint-fragment --repo <repo>` on the fragment it is about to return @ [cli.py](tools/coyodex/cli.py:100)
2. C22 → C5 : routes to the fragment linter @ [cli.py](tools/coyodex/cli.py:102)
3. C5 → C6 : loads the fragment as a partial model, so a bad id shape dies here rather than a phase later @ [lint_fragment.py](tools/coyodex/lint_fragment.py:238)
4. C5 → C8 : reuses the validator's own anchor-format check at fragment scope @ [lint_fragment.py](tools/coyodex/lint_fragment.py:117)
5. C5 → C8 : reuses the validator's edge rules, so a witness-less edge is caught in the agent's own turn @ [lint_fragment.py](tools/coyodex/lint_fragment.py:131)
6. C5 → D10 : confirms every anchored file really exists under the given repo root @ [lint_fragment.py](tools/coyodex/lint_fragment.py:243) · this is what catches a wrong repo-root prefix at the source
7. C5 → Coding agent : prints every finding in one pass, and separates advisory warnings from failures @ [lint_fragment.py](tools/coyodex/lint_fragment.py:256)

**UC4 — Assemble the map from fragments**
1. Coding agent → C22 : runs `coyodex assemble` over the clean fragments, with the reconcile file @ [cli.py](tools/coyodex/cli.py:91)
2. C22 → C6 : routes to the assembler @ [cli.py](tools/coyodex/cli.py:93)
3. C6 → D10 : reads each fragment and validates it alone, so a malformed one fails by name instead of poisoning the batch @ [assemble.py](tools/coyodex/assemble.py:396)
4. C6 → E1 : merges the fragments into one model, refusing a duplicate id across two agents rather than silently overwriting @ [assemble.py](tools/coyodex/assemble.py:410)
5. C6 → E19 : strips any backbone edge that names an actor, and collapses edges two agents wrote at the same call site @ [assemble.py](tools/coyodex/assemble.py:185) · an actor edge is a trace-prompt defect, so the count is reported as a warning to fix at the source
6. C6 → C8 : asks which entity flow-steps no backbone edge covers @ [assemble.py](tools/coyodex/assemble.py:99)
7. C6 → E19 : creates the missing component-to-entity edge each of those steps implies, inferring the verb from the step's leading word @ [assemble.py](tools/coyodex/assemble.py:111) · anything not clearly a write becomes a read, so a derived edge never invents ownership
8. C6 → E73 : loads the declarative reconcile directives and applies them after the merge @ [assemble.py](tools/coyodex/assemble.py:440) · run after the edge derivation, so a dropped entity edge is not re-derived in the same pass
9. C6 → E1 : writes the merged model through the one canonical serializer @ [assemble.py](tools/coyodex/assemble.py:470)
10. C6 → C14 : renders the markdown view beside it so the readable copy never lags the model @ [assemble.py](tools/coyodex/assemble.py:471)
11. C6 → C12 : registers the freshly built project so it appears on the map server's landing page @ [assemble.py](tools/coyodex/assemble.py:475)
12. C6 → Coding agent : prints one self-describing digest of the resulting inventory and every mutation this assemble made @ [assemble.py](tools/coyodex/assemble.py:484)

**UC5 — Validate the map**
1. Coding agent → C22 : runs `coyodex validate --check-sources --check-coverage` @ [cli.py](tools/coyodex/cli.py:79)
2. C22 → C8 : routes to the validator @ [cli.py](tools/coyodex/cli.py:81)
3. C8 → C1 : loads the model ⟨runs SF1 — Load the map model into typed form⟩
4. C8 → E1 : checks the semantics the loader cannot: every referenced id resolves, groups nest without cycles, steps carry a phrase and a site, edges carry a witness @ [validate_model.py](tools/coyodex/validate_model.py:2036)
5. C8 → D10 : reads each anchored file to confirm it exists, and each entity's source to reject a name with no real named type behind it @ [validate_model.py](tools/coyodex/validate_model.py:2107)
6. C8 → C4 : re-measures the tree itself for the component-count expectation, never reading the pre-index's own answer @ [validate_model.py](tools/coyodex/validate_model.py:2116) · generation and verification share code but never data
7. C8 → C10 : appends the always-on diagram fan-out advisories @ [validate_model.py](tools/coyodex/validate_model.py:2136)
8. C8 → E29 : reads the recorded adjudications, so a justified advisory goes quiet instead of re-firing forever @ [validate_model.py](tools/coyodex/validate_model.py:2136)
9. C8 → Coding agent : prints the blocking problems and the advisory warnings separately, and fails the exit code only on the former @ [validate_model.py](tools/coyodex/validate_model.py:2271)

**UC6 — Audit the map for self-contradiction**
1. Coding agent → C22 : runs `coyodex audit` on a map that already validates @ [cli.py](tools/coyodex/cli.py:82)
2. C22 → C9 : routes to the auditor @ [cli.py](tools/coyodex/cli.py:84)
3. C9 → C1 : loads the model ⟨runs SF1 — Load the map model into typed form⟩
4. C9 → E35 : reads each Happy-Path step's position and the step ids its prerequisite refers to @ [audit_model.py](tools/coyodex/audit_model.py:110) · this is what makes a forward reference detectable at all
5. C9 → E33 : makes the narrative order and the mechanism refute each other, and records what disagrees @ [audit_model.py](tools/coyodex/audit_model.py:292)
6. C9 → E34 : builds the ranked worklist of claims no deterministic check can settle, most dangerous first @ [audit_model.py](tools/coyodex/audit_model.py:367) · each item carries enough self-describing detail that a skeptic needs no map file
7. C9 → Coding agent : prints the findings and the worklist, blocking only on a hard prerequisite contradiction @ [audit_model.py](tools/coyodex/audit_model.py:533)

**UC7 — Correct drifted anchors**
1. Coding agent → C22 : runs `coyodex anchor-drift` with the skeptics' verdicts file @ [cli.py](tools/coyodex/cli.py:103)
2. C22 → C11 : routes to the grounding reconcile @ [cli.py](tools/coyodex/cli.py:105)
3. C11 → C1 : loads the model ⟨runs SF1 — Load the map model into typed form⟩
4. C11 → C9 : rebuilds the same worklist the skeptics were given, so each verdict pairs back to its claim @ [anchor_drift.py](tools/coyodex/anchor_drift.py:137)
5. C11 → C2 : asks the shared anchor helper whether the reported line drifts from the stored one @ [anchor_drift.py](tools/coyodex/anchor_drift.py:62)
6. C2 → E32 : records the verdict from the median line the skeptics reported, so one stray skeptic cannot move an anchor @ [anchors.py](tools/coyodex/anchors.py:107) · one stray skeptic cannot move an anchor; a different file is always drift
7. C11 → Coding agent : prints the drift worklist — it flags, the reconciler decides @ [anchor_drift.py](tools/coyodex/anchor_drift.py:99)
8. Coding agent → C11 : runs `coyodex fix apply-drift` to write the corrections in @ [fix.py](tools/coyodex/fix.py:303)
9. C11 → E19 : rewrites each drifted edge's witness line, matching on the whole source, verb and target triple so paired edges never swap @ [fix.py](tools/coyodex/fix.py:105)
10. C11 → E1 : writes the edited model back through the one canonical serializer, never by hand @ [fix.py](tools/coyodex/fix.py:42)

**UC8 — Re-balance the map's grouping**
1. Coding agent → C22 : runs `coyodex balance` once the trace has produced real edges @ [cli.py](tools/coyodex/cli.py:97)
2. C22 → C10 : routes to the balance report @ [cli.py](tools/coyodex/cli.py:99)
3. C10 → C1 : loads the model ⟨runs SF1 — Load the map model into typed form⟩
4. C10 → E19 : aggregates the component-to-component edges onto each group, so an over-dense screen can be cut where the graph is already loose @ [balance_lib.py](tools/coyodex/balance_lib.py:354)
5. C10 → E36 : proposes child groups by a deterministic greedy partition, and says so plainly instead of proposing noise on a list-shaped screen @ [balance_lib.py](tools/coyodex/balance_lib.py:499)
6. C10 → Coding agent : prints each proposal as a ready-to-apply map-change block, always exiting zero because balance never gates @ [balance.py](tools/coyodex/balance.py:170)
7. Coding agent → C10 : accepts a proposal as a direct map edit, or records why the screen stays as it is @ [balance.py](tools/coyodex/balance.py:170)

**UC9 — Render the committed markdown view**
1. Coding agent → C22 : runs `coyodex render` as the last step of the invariant @ [cli.py](tools/coyodex/cli.py:85)
2. C22 → C14 : routes to the renderer, which accepts a model input and a markdown output only @ [cli.py](tools/coyodex/cli.py:87)
3. C14 → C1 : loads the model ⟨runs SF1 — Load the map model into typed form⟩
4. C14 → E1 : walks the model in canonical section order and renders it as template-shaped tables @ [views.py](tools/coyodex/views.py:239)
5. C14 → D10 : writes the view beside the model, with a notice saying it is generated and must not be edited @ [render.py](tools/coyodex/viewer/render.py:49)
6. C14 → C12 : registers the project folder, so rendering is also what puts it on the server's landing page @ [render.py](tools/coyodex/viewer/render.py:52) · best-effort — a failure here never fails the render
7. C14 → Coding agent : reports the file it wrote, ready to be committed with the model @ [render.py](tools/coyodex/viewer/render.py:53)

**UC10 — Serve the maps**
1. Developer → C21 : runs `make start` once, from the coyodex clone @ [Makefile](Makefile:87)
2. C21 → C12 : launches the server on the configured port and opens the landing page @ [Makefile](Makefile:88)
3. C12 → D10 : reads the remembered project folders — there is no disk scan, so the served set is exactly what was opened before @ [recents.py](tools/coyodex/viewer/recents.py:34)
4. C12 → C14 : loads each folder's map into the viewer graph to read its commit, title and goal for the landing card @ [serve.py](tools/coyodex/viewer/serve.py:119)
5. C12 → E47 : builds one served project per loadable map, giving each a URL slug and disambiguating a repeated folder name @ [serve.py](tools/coyodex/viewer/serve.py:128) · a folder whose map is missing or broken stays in the list, shown as not yet built
6. C12 → Developer : binds the loopback socket, prints the projects and the URL, and serves until interrupted @ [serve.py](tools/coyodex/viewer/serve.py:734)

**UC11 — Explore a map in the viewer**
1. Developer → C15 : opens the project's page from the landing card @ [serve.py](tools/coyodex/viewer/serve.py:602)
2. C15 → C12 : fetches the whole view bundle at boot, and says plainly when the server is not there @ [viewer.js](tools/coyodex/viewer/viewer.js:104)
3. C12 → E47 : checks the map file's timestamp first and drops the cached artifacts if it changed, so an edited map shows on the next refresh @ [serve.py](tools/coyodex/viewer/serve.py:155)
4. C12 → C14 : flattens the model into the viewer's graph of boxes and arrows @ [serve.py](tools/coyodex/viewer/serve.py:397)
5. C14 → E42 : resolves each element into a drawable node with its derived extras, and each relation into an arrow with its backing field @ [views.py](tools/coyodex/views.py:686)
6. C12 → C13 : asks for every diagram the frontend will draw @ [serve.py](tools/coyodex/viewer/serve.py:399)
7. C13 → E45 : pre-renders the Context, subsystem, domain, deployment, Happy-Path and per-flow diagrams, plus the crossing-edge list behind each aggregated arrow @ [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2540)
8. C12 → C15 : returns the bundle as JSON, or a clean error body if the map cannot be drawn @ [serve.py](tools/coyodex/viewer/serve.py:616)
9. C15 → D4 : renders each diagram's source into SVG @ [viewer.js](tools/coyodex/viewer/viewer.js:4511)
10. C15 → D5 : wraps the SVG so a large map can be panned and zoomed instead of shrunk to fit @ [viewer.js](tools/coyodex/viewer/viewer.js:4575)
11. C15 → Developer : draws the altitude, and on a click shows that box's plain-language explanation beside it

**UC12 — Read a mapped element's source**
1. Developer → C15 : clicks the source link on a selected box
2. C15 → C12 : asks for that file's text, without saying which commit — the map's own pin is the default @ [viewer.js](tools/coyodex/viewer/viewer.js:5755)
3. C12 → E47 : answers from the project's pinned commit, so what the reader sees always matches what the map describes @ [serve.py](tools/coyodex/viewer/serve.py:640)
4. C12 → D1 : checks the blob's size before reading it, then reads the file out of that commit @ [serve.py](tools/coyodex/viewer/serve.py:650) · the size check comes first so a huge blob is never buffered into memory
5. C12 → C15 : returns the file as plain text, or a not-found when it is not tracked in that commit @ [serve.py](tools/coyodex/viewer/serve.py:654)
6. C15 → Developer : shows the file with the anchored line brought into view and highlighted
7. Developer → C15 : asks instead for the real file on their own machine
8. C15 → D8 : hands the path and line to the chosen editor through its URL scheme @ [viewer.js](tools/coyodex/viewer/viewer.js:5970)
9. C15 → D7 : opens the blob URL pinned to the map's commit when no editor is configured @ [viewer.js](tools/coyodex/viewer/viewer.js:5973)

**UC13 — Explore the impact of a code change**
1. Developer → C15 : picks a base and a target in the impact explorer @ [viewer.js](tools/coyodex/viewer/viewer.js:6838)
2. C15 → C12 : asks for the impact of that range, with the noisy ripple links left off by default @ [viewer.js](tools/coyodex/viewer/viewer.js:6800)
3. C12 → C16 : asks the projection layer what the change did to the map's anchors @ [serve.py](tools/coyodex/viewer/serve.py:370)
4. C16 → E52 : indexes every anchor the map carries, remembering which element and which field each came from @ [impact_git.py](tools/coyodex/impact_git.py:221)
5. C16 → D1 : reads both sides' diffs against the pin, and the full-tree rename maps that let a moved file still be found @ [impact_git.py](tools/coyodex/impact_git.py:224) · never a single-path pathspec — that filters before rename detection and fabricates deletes
6. C16 → E51 : compares the two sides' hunks to decide which of the pin's lines the change really affects @ [impact_lib.py](tools/coyodex/impact_lib.py:135)
7. C16 → E53 : resolves each anchor at the finest rung it can honestly claim — the line, the enclosing definition, or just the file @ [impact_lib.py](tools/coyodex/impact_lib.py:353)
8. C12 → C17 : asks the ripple layer to spread from those direct hits @ [serve.py](tools/coyodex/viewer/serve.py:371)
9. C17 → E57 : applies the typed rules once, keeping read-only links, the entity graph and the transitive call graph off unless asked @ [impact_ripple.py](tools/coyodex/impact_ripple.py:276)
10. C17 → C15 : returns each reached element with its cause and the strongest signal that found it @ [impact_ripple.py](tools/coyodex/impact_ripple.py:325)
11. C15 → Developer : badges the changed and rippled boxes on the diagrams, so the blast radius is read on the map rather than in a diff

**UC14 — Accept a change into the baseline**
1. Coding agent → C20 : reads the accept half of the change-impact method after the developer approves the report @ [change-impact.md](method/change-impact.md:1)
2. C20 → C7 : prescribes re-stamping provenance with this conversation as part of accepting @ [method.md](method.md:1186)
3. Coding agent → C11 : patches the model's fields surgically for what the change did — never a rebuild @ [fix.py](tools/coyodex/fix.py:303)
4. C11 → E1 : bumps the map's pin to the new commit and writes the model back through the canonical serializer @ [model.py](tools/coyodex/model.py:591)
5. C7 → D1 : reads the analyzed repo's new short sha and its commit date @ [map_backup.py](tools/map_backup.py:392)
6. C7 → E75 : adds this session to the map's provenance, or updates its entry when the same session stamps twice @ [map_backup.py](tools/map_backup.py:409)
7. Coding agent → C8 : re-runs the validator, because a patch can introduce a fresh contradiction of its own @ [validate_model.py](tools/coyodex/validate_model.py:2271)
8. Coding agent → C14 : re-renders the markdown view so it tracks the patched model @ [render.py](tools/coyodex/viewer/render.py:49)
9. Coding agent → Developer : commits the model, the view, the pre-index and the provenance together with the code @ [method.md](method.md:1193)

**UC15 — Ask for a direct map change**
1. Developer → Coding agent : asks in plain language to move, rename, split or group something on the map
2. Coding agent → C20 : reads the dispatch doc, which names a plain-language request as its own mode — not a code diff to analyze @ [dispatch.md](method/dispatch.md:64)
3. C20 → Coding agent : confines the edit to what the code actually backs — reorganize and rename what exists, never invent @ [dispatch.md](method/dispatch.md:70)
4. Coding agent → E7 : edits the membership pointer on each moved component, since membership is single-sourced on the child @ [model.py](tools/coyodex/model.py:102)
5. Coding agent → C8 : re-runs the validator, which fails on any edge left pointing at a retired element @ [validate_model.py](tools/coyodex/validate_model.py:2217)
6. Coding agent → C9 : re-runs the audit, because a re-ordered walk can now read something a later step creates @ [audit_model.py](tools/coyodex/audit_model.py:511)
7. Coding agent → C14 : re-renders the markdown view and commits both — the gates are not optional for a requested edit @ [render.py](tools/coyodex/viewer/render.py:49)
8. C12 → Developer : picks the edited map up on the next refresh, with no restart @ [serve.py](tools/coyodex/viewer/serve.py:155)

**UC16 — Look up an element in the model**
1. Coding agent → C22 : runs `coyodex dump --id C7` rather than opening the whole map @ [cli.py](tools/coyodex/cli.py:94)
2. C22 → C3 : routes to the model reader, defaulting the map path to the conventional one @ [cli.py](tools/coyodex/cli.py:96)
3. C3 → C1 : loads the model ⟨runs SF1 — Load the map model into typed form⟩
4. C3 → E1 : resolves the id to its kind, display name, canonical source and members, or returns the one requested slice @ [dump.py](tools/coyodex/dump.py:153)
5. C3 → Coding agent : prints it as JSON, deliberately offering a tiny fixed set of slices rather than a query language @ [dump.py](tools/coyodex/dump.py:122)

**UC17 — Back up a map with its conversation**
1. Developer → C7 : runs the backup script against a mapped repo @ [map_backup.py](tools/map_backup.py:625)
2. C7 → E75 : reads the stamped provenance to learn which sessions built this map @ [map_backup.py](tools/map_backup.py:432)
3. C7 → D11 : locates each session's transcript file and its sidechain folder by session id @ [map_backup.py](tools/map_backup.py:352) · an unstamped map can instead be recovered by finding transcripts that actually wrote a map file
4. C7 → D10 : copies the transcripts into the dated backup folder — always copied, never moved, because they live in the agent's live store @ [map_backup.py](tools/map_backup.py:512)
5. C7 → D10 : writes a manifest describing what the bundle holds @ [map_backup.py](tools/map_backup.py:530)
6. C7 → Developer : reports the folder, and which sessions had no transcript left on disk @ [map_backup.py](tools/map_backup.py:512)

**UC18 — Run the method-quality eval**
1. Method maintainer → C18 : runs `coyodex-eval run` on a map just rebuilt with the current method @ [cli.py](eval/tools/coyodex_eval/cli.py:26)
2. C18 → C19 : asks for the candidate map's deterministic profile @ [run.py](eval/tools/coyodex_eval/run.py:60)
3. C19 → C8 : reuses the validator's exact parse, so a map is never scored through a second grammar @ [profile.py](eval/tools/coyodex_eval/profile.py:129)
4. C19 → C9 : counts the audit's findings and the size of its grounding worklist @ [profile.py](eval/tools/coyodex_eval/profile.py:131)
5. C19 → C4 : re-computes the component expectation from the code tree at scoring time @ [profile.py](eval/tools/coyodex_eval/profile.py:143)
6. C19 → E58 : reduces the map to signals that survive an LLM rewording it — counts, gate outcomes, density, balance and the watched name sets @ [profile.py](eval/tools/coyodex_eval/profile.py:162)
7. C19 → E63 : aggregates the skeptics' majority verdicts and the judges' medians, never counting a failed skeptic as a refutation @ [judge.py](eval/tools/coyodex_eval/judge.py:237)
8. C18 → D10 : reads the blessed baseline's profile and judge report @ [run.py](eval/tools/coyodex_eval/run.py:232)
9. C18 → E69 : applies the hard gates first, then the drift bands, then the one band measured against the code rather than the baseline @ [compare.py](eval/tools/coyodex_eval/compare.py:332)
10. C18 → D10 : archives the map, the profile, the judge report and the comparison into a run folder @ [run.py](eval/tools/coyodex_eval/run.py:248)
11. C18 → Method maintainer : reports PASS, DRIFT or REGRESSED with the tripped gate named, and mirrors that in the exit code @ [run.py](eval/tools/coyodex_eval/run.py:186)

---

## T6b — Sub-flows (shared step sequences, referenced by the flows above)

**SF1 — Load the map model into typed form**
1. C1 → D10 : reads the map document off disk @ [model.py](tools/coyodex/model.py:758)
2. C1 → E1 : parses the JSON and builds the typed model field by field, naming the JSON path of any shape violation @ [model.py](tools/coyodex/model.py:744)
3. C1 → E1 : rejects any element id that is not its array's prefix followed by digits @ [model.py](tools/coyodex/model.py:750) · structure only — that ids RESOLVE is the validator's job, not the loader's

---

## Operational dimensions — the standard core four

### Deployment & topology

| Unit | Runs on | Exposed as | Config source |
|---|---|---|---|
| coyodex CLI | the developer's machine, as a short-lived process out of the repo-local virtualenv (.venv/bin/coyodex) | the `coyodex` console script, invoked by the coding agent | pyproject.toml [project.scripts]; the venv is built by `make deps` |
| coyodex serve | the developer's machine, as a long-lived threading HTTP server bound to 127.0.0.1 | http://127.0.0.1:8765/ (port overridable with --port or make start PORT=…) | Makefile PORT; ~/.coyodex/serve-recents.json holds the served project set |
| viewer page | the developer's browser, one tab per map | http://127.0.0.1:8765/p/<project>/ — a generic shell that fetches this map's bundle at boot | browser local storage for editor, repo root and layout preferences |
| coyodex-eval CLI | the developer's machine, as a short-lived process out of the same virtualenv | the `coyodex-eval` console script, driven by the eval skill's orchestration | eval/thresholds.json, plus a per-project .coyodex-eval directory |
| map backup script | the developer's machine, run directly with the venv's python (no console script) | python tools/map_backup.py stamp\|backup | CLAUDE_CODE_SESSION_ID from the environment; ~/.claude/projects for transcripts |

### Observability

| Signal | Where emitted | Where viewed | Alerts |
|---|---|---|---|
| CLI diagnostics and exit codes | each verb's main(): the validator's problems and warnings, the auditor's findings, the assembler's merge errors and auto-clean notes | the coding agent's tool output, in the build transcript | a non-zero exit blocks the build — validate and audit are gates, balance is advisory and always exits 0 |
| Assemble digest line | one self-describing line printed after every assemble: the resulting inventory plus every mutation the auto-clean passes and the reconcile made | the build transcript — so a later audit sees the effects without reverse-engineering a script | none; it is a trail, not an alarm |
| Pre-index summary | a one-line human summary on stderr beside the JSON: heaviest directories, file and line totals, ambiguous symbols, languages without symbol data | the agent's terminal, read before the harvest is planned | none |
| Map server console | startup prints the served projects and the listening URL; the per-request access log is deliberately silenced | the terminal running make start | none; a broken map surfaces as a 500 body in the browser rather than a log alarm |

### Security & auth

| Surface | Who can reach | Auth check | Risk note |
|---|---|---|---|
| The whole map server HTTP API | any process or page that can reach 127.0.0.1 on this machine — there is no authentication of any kind | tools/coyodex/viewer/serve.py:512 | the socket is bound to loopback and every request's Host header is checked against a loopback allow-list to block DNS rebinding, but a local caller still reads every mapped repository's source through the file API. Treat it as a single-user developer tool, never expose the port. |
| State-changing landing-page requests (open / forget / reorder a project) | same-machine callers that also send the custom request header | tools/coyodex/viewer/serve.py:535 | the CSRF guard is a custom header a cross-origin page cannot set without a preflight that would fail; there is no token and no origin check beyond the loopback Host guard |
| Reading a file from the working tree instead of the commit | the impact explorer, which needs both ends of an arbitrary diff | tools/coyodex/viewer/serve.py:275 | the one escape from the frozen-snapshot rule; guarded by realpath containment inside the repo, an exclusion of the .git directory, and a tracked-or-untracked-but-not-ignored test — a defect here would read arbitrary local files |
| Path and ref parameters on the file APIs | any caller of /api/src and the impact endpoints | tools/coyodex/viewer/serve.py:631 | relative paths are rejected if absolute, backslashed or NUL-bearing, and refs must match a conservative shape, so a crafted query cannot escape the repository or smuggle a git option |
| Third-party frontend bundles fetched at page load | the viewer page, from a public CDN | tools/coyodex/viewer/viewer.html:17 | both bundles are version-pinned with subresource integrity, so a substituted file is rejected — but there is no local fallback, so a CDN outage leaves the diagrams unrendered |
| Bundling conversation transcripts into a backup | the developer running the backup script — nothing gates this read | tools/map_backup.py:512 | There is no check here at all, which is the finding: a transcript holds everything that session saw, and the backup copies it verbatim into the coyodex clone, where it is protected only by that folder being git-ignored. The anchor is the copy itself, not a guard. |

### Config & environments

| Key | Purpose | Default | Per-env / secret? |
|---|---|---|---|
| PORT | the port the local map server listens on | 8765 | make start PORT=9000, or coyodex serve --port 9000 |
| SKILLS_DIRS | the agent skills homes `make install` writes the manifest into | ~/.claude/skills and ~/.agents/skills | Makefile variable; Cursor is covered by both, so no third directory is written |
| COYODEX_NO_SERVE_REGISTER | skip auto-registering a freshly built project with the map server | unset (a build does register itself) | set by the regression eval so its throwaway maps never pollute the recents list |
| CLAUDE_CODE_SESSION_ID | the conversation id stamped into a map's provenance | read from the environment inside a Claude Code session | override with --session-id when stamping from elsewhere |
| ~/.coyodex/serve-recents.json | the ordered list of project folders the server serves — there is no disk scan | created on first use; empty until a folder is opened | per machine; every mutation reloads the file first so concurrent writers merge |
| preindex extra | gates the tree-sitter dependencies to the pre-index path only | installed by make install / make deps | pip install -e '.[preindex]'; without it, only Python symbols are extracted |
| eval/thresholds.json | the eval's hard gates, drift bands and pinned judge protocol | the committed starter values | per project via a .coyodex-eval directory or a --thresholds override |

---

## Relationships — backbone edge list

| From | Verb | To | Why | Where (example) |
|---|---|---|---|---|
| C22 | routes-to | C4 | dispatches the pre-index verb, the only branch allowed to load a third-party parser | [cli.py](tools/coyodex/cli.py:78) |
| C22 | routes-to | C8 | dispatches the validate verb, supplying the conventional map path when none is given | [cli.py](tools/coyodex/cli.py:81) |
| C22 | routes-to | C9 | dispatches the audit verb | [cli.py](tools/coyodex/cli.py:84) |
| C22 | routes-to | C14 | dispatches the render verb | [cli.py](tools/coyodex/cli.py:87) |
| C22 | routes-to | C12 | dispatches the serve verb | [cli.py](tools/coyodex/cli.py:90) |
| C22 | routes-to | C6 | dispatches the assemble verb | [cli.py](tools/coyodex/cli.py:93) |
| C22 | routes-to | C3 | dispatches the dump verb | [cli.py](tools/coyodex/cli.py:96) |
| C22 | routes-to | C10 | dispatches the balance verb | [cli.py](tools/coyodex/cli.py:99) |
| C22 | routes-to | C5 | dispatches the fragment-lint verb agents run on themselves | [cli.py](tools/coyodex/cli.py:102) |
| C22 | routes-to | C11 | dispatches both grounding verbs — the drift check and the fix that applies it | [cli.py](tools/coyodex/cli.py:105) |
| C22 | reads | C1 | reads the package version for the --version flag | [cli.py](tools/coyodex/cli.py:73) |
| C6 | uses | C1 | loads each fragment as a partial model and writes the merged result through the one canonical serializer | [assemble.py](tools/coyodex/assemble.py:470) |
| C6 | uses | C2 | reads the shared verb families to infer a derived entity edge's verb | [assemble.py](tools/coyodex/assemble.py:71) |
| C6 | uses | C8 | asks which entity flow-steps carry no backing backbone edge | [assemble.py](tools/coyodex/assemble.py:99) |
| C6 | uses | C14 | renders the markdown view beside every model it writes | [assemble.py](tools/coyodex/assemble.py:471) |
| C6 | uses | C12 | registers a freshly assembled project on the map server's landing page | [assemble.py](tools/coyodex/assemble.py:475) |
| C6 | writes | D10 | writes the canonical model and its markdown view into the output folder | [assemble.py](tools/coyodex/assemble.py:470) |
| C6 | persists | E1 | the assembler is where a built map first becomes a stored document | [assemble.py](tools/coyodex/assemble.py:470) |
| C6 | writes | E19 | strips actor edges, collapses same-site duplicates and derives the entity edge a flow step implies | [assemble.py](tools/coyodex/assemble.py:111) |
| C6 | reads | E73 | applies the declarative reconcile directives after the merge and before the write | [assemble.py](tools/coyodex/assemble.py:440) |
| C5 | uses | C6 | loads a fragment through the same partial-model loader the assembler uses | [lint_fragment.py](tools/coyodex/lint_fragment.py:238) |
| C5 | uses | C8 | reuses the validator's anchor, edge, activation and entry-kind checks at fragment scope | [lint_fragment.py](tools/coyodex/lint_fragment.py:117) |
| C5 | uses | C2 | reads the shared entry-point and dependency vocabularies when checking a fragment's rows | [lint_fragment.py](tools/coyodex/lint_fragment.py:91) |
| C5 | reads | D10 | reads each fragment and confirms every anchored file exists under the repo root | [lint_fragment.py](tools/coyodex/lint_fragment.py:238) |
| C5 | reads | E1 | checks a fragment against the same model shape the whole map obeys | [lint_fragment.py](tools/coyodex/lint_fragment.py:238) |
| C4 | reads | D1 | reads per-file change counts, so the weight tree carries churn as well as size | [preindex_lib.py](tools/coyodex/preindex_lib.py:159) |
| C4 | calls | D2 | parses non-Python sources for the symbol index | [preindex_lib.py](tools/coyodex/preindex_lib.py:318) |
| C4 | calls | D3 | asks the pack for each non-Python language's grammar | [preindex_lib.py](tools/coyodex/preindex_lib.py:318) |
| C4 | writes | D10 | writes the committed pre-index document the viewer's symbol search also reads | [preindex.py](tools/coyodex/preindex.py:306) |
| C4 | writes | E37 | records every definition it finds with its file, line and extent | [preindex_lib.py](tools/coyodex/preindex_lib.py:265) |
| C4 | writes | E38 | records the import statements behind the lower-bound component-edge advisory | [preindex_lib.py](tools/coyodex/preindex_lib.py:281) |
| C4 | writes | E39 | computes each directory subtree's component expectation from the code alone | [preindex_lib.py](tools/coyodex/preindex_lib.py:511) |
| C8 | uses | C1 | loads and structurally validates the map before checking any semantics | [validate_model.py](tools/coyodex/validate_model.py:2253) |
| C8 | uses | C2 | checks dependency kinds, entry-point kinds, activations and store modes against the shared vocabularies | [validate_model.py](tools/coyodex/validate_model.py:32) |
| C8 | uses | C4 | re-measures the code tree for the component expectation instead of trusting the pre-index's own answer | [validate_model.py](tools/coyodex/validate_model.py:2116) |
| C8 | uses | C10 | appends the always-on diagram fan-out advisories to its warnings | [validate_model.py](tools/coyodex/validate_model.py:2136) |
| C8 | uses | C14 | re-renders the markdown view to detect a committed copy that has gone stale | [validate_model.py](tools/coyodex/validate_model.py:2017) |
| C8 | reads | D10 | reads the map, then every anchored file the map claims, to confirm each exists | [validate_model.py](tools/coyodex/validate_model.py:2253) |
| C8 | reads | E1 | checks that every reference resolves and every rule the loader cannot see still holds | [validate_model.py](tools/coyodex/validate_model.py:2036) |
| C8 | reads | E29 | reads the recorded adjudications that silence a justified advisory | [validate_model.py](tools/coyodex/validate_model.py:2136) |
| C9 | uses | C1 | loads the map, and walks flows with their sub-flow references expanded | [audit_model.py](tools/coyodex/audit_model.py:529) |
| C9 | uses | C2 | classifies each backbone verb to decide which claims are dangerous enough to rank first | [audit_model.py](tools/coyodex/audit_model.py:40) |
| C9 | reads | D10 | reads the map document — the audit reaches no code at all | [audit_model.py](tools/coyodex/audit_model.py:529) |
| C9 | writes | E33 | records every contradiction and advisory the two layers surface about each other | [audit_model.py](tools/coyodex/audit_model.py:292) |
| C9 | writes | E34 | builds the ranked grounding worklist for the fresh-context skeptics | [audit_model.py](tools/coyodex/audit_model.py:367) |
| C9 | writes | E35 | reads each Happy-Path step's position and prerequisite references, which is what makes a forward reference detectable | [audit_model.py](tools/coyodex/audit_model.py:110) |
| C10 | uses | C1 | loads the map the balance report measures | [balance.py](tools/coyodex/balance.py:193) |
| C10 | reads | D10 | reads the map document | [balance.py](tools/coyodex/balance.py:193) |
| C10 | reads | E19 | aggregates the component-to-component edges onto each group to find where a dense screen can be cut | [balance_lib.py](tools/coyodex/balance_lib.py:354) |
| C10 | writes | E36 | proposes child groups by a deterministic greedy partition | [balance_lib.py](tools/coyodex/balance_lib.py:499) |
| C11 | uses | C1 | loads the map and writes the corrected model back through the one serializer | [fix.py](tools/coyodex/fix.py:42) |
| C11 | uses | C9 | rebuilds the same worklist the skeptics were given, so each verdict pairs back to its claim | [anchor_drift.py](tools/coyodex/anchor_drift.py:137) |
| C11 | uses | C2 | asks the shared anchor helper whether a reported line drifts from the stored one | [anchor_drift.py](tools/coyodex/anchor_drift.py:62) |
| C11 | writes | D10 | writes the edited model back in place, so a drift fix is never hand-scripted | [fix.py](tools/coyodex/fix.py:42) |
| C11 | writes | E1 | applies the terminal grounding corrections to the assembled map | [fix.py](tools/coyodex/fix.py:42) |
| C11 | writes | E19 | rewrites a drifted witness line, or removes a refuted edge and heals the steps that rode it | [fix.py](tools/coyodex/fix.py:105) |
| C11 | reads | E32 | acts on the drift verdict computed from the skeptics' consensus line | [anchor_drift.py](tools/coyodex/anchor_drift.py:62) |
| C3 | uses | C1 | loads the map before resolving the requested id or slice | [dump.py](tools/coyodex/dump.py:153) |
| C3 | reads | D10 | reads the map document, read-only | [dump.py](tools/coyodex/dump.py:153) |
| C3 | reads | E1 | resolves an id to its kind, name, source and members, or returns one stored record verbatim | [dump.py](tools/coyodex/dump.py:153) |
| C1 | uses | C2 | rewrites id tokens through the shared token pattern when a merge remaps an element | [model.py](tools/coyodex/model.py:508) |
| C1 | reads | D10 | reads a map document from a path for the common command entry | [model.py](tools/coyodex/model.py:758) |
| C1 | persists | E1 | the loader and the deterministic serializer are the map's only reader and writer of record | [model.py](tools/coyodex/model.py:591) |
| C2 | writes | E31 | parses an anchor string into a comparable path and line range | [anchors.py](tools/coyodex/anchors.py:78) |
| C2 | writes | E32 | judges drift from the median reported line, so one stray skeptic cannot move an anchor | [anchors.py](tools/coyodex/anchors.py:107) |
| C12 | uses | C1 | loads each served map, and re-reads it whenever the file changes underneath | [serve.py](tools/coyodex/viewer/serve.py:119) |
| C12 | uses | C14 | flattens the model into the viewer graph and builds the file tree with its coverage tags | [serve.py](tools/coyodex/viewer/serve.py:119) |
| C12 | uses | C13 | asks for the whole per-project view bundle the frontend renders | [serve.py](tools/coyodex/viewer/serve.py:399) |
| C12 | uses | C16 | projects a requested diff range onto the map's anchors | [serve.py](tools/coyodex/viewer/serve.py:370) |
| C12 | uses | C17 | spreads from the direct hits and assembles the impact payload | [serve.py](tools/coyodex/viewer/serve.py:371) |
| C12 | uses | C15 | serves the generic shell and the shared frontend bundle, identical for every map | [serve.py](tools/coyodex/viewer/serve.py:605) |
| C12 | reads | D1 | every file the viewer shows is read out of the map's own commit, and the file list comes from the same place | [serve.py](tools/coyodex/viewer/serve.py:223) |
| C12 | reads | D10 | reads the remembered project folders, and reads a file from the working tree for the impact explorer | [recents.py](tools/coyodex/viewer/recents.py:34) |
| C12 | writes | D10 | records a newly opened project folder, and the reordering of the landing-page cards | [recents.py](tools/coyodex/viewer/recents.py:44) |
| C12 | writes | E47 | builds one served project per loadable map and caches its artifacts against the map's timestamp | [serve.py](tools/coyodex/viewer/serve.py:128) |
| C12 | reads | E1 | reads each map's pin, title and goal to serve its landing card and pin its file reads | [serve.py](tools/coyodex/viewer/serve.py:119) |
| C13 | uses | C2 | classifies each dependency to decide whether it is drawn at Context or folded into the libraries box | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:1167) |
| C13 | reads | D1 | reads the origin remote and the repo root, so a source link can fall back to a GitHub blob URL | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:57) |
| C13 | writes | E45 | pre-renders every diagram, flow and crossing-edge list into one payload | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2540) |
| C13 | reads | E42 | reads the flattened graph the diagrams are drawn from | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2503) |
| C14 | uses | C1 | loads the model, which is the only accepted render input | [render.py](tools/coyodex/viewer/render.py:44) |
| C14 | uses | C2 | reuses the domain-relation vocabulary and the backing-field resolution rather than a second grammar | [views.py](tools/coyodex/views.py:557) |
| C14 | uses | C12 | registers the rendered project folder with the map server, best effort | [render.py](tools/coyodex/viewer/render.py:52) |
| C14 | writes | D10 | writes the committed markdown view of the model | [render.py](tools/coyodex/viewer/render.py:49) |
| C14 | reads | E1 | walks the whole model to render it, both as markdown and as the viewer's graph | [views.py](tools/coyodex/views.py:239) |
| C14 | writes | E42 | flattens the model into drawable nodes and arrows, resolving each relation's backing field once | [views.py](tools/coyodex/views.py:680) |
| C14 | writes | E40 | builds each element's drawable box, resolving the extras each diagram draws from | [views.py](tools/coyodex/views.py:686) |
| C14 | writes | E46 | tags each path in the repo tree by how the map covers it, so the browser doubles as a coverage view | [filetree.py](tools/coyodex/viewer/filetree.py:203) |
| C15 | calls | C12 | fetches the view bundle at boot and, on demand, the file tree, symbols, source text and impact payload | [viewer.js](tools/coyodex/viewer/viewer.js:104) |
| C15 | calls | D4 | renders each pre-built diagram source into SVG | [viewer.js](tools/coyodex/viewer/viewer.js:4511) |
| C15 | calls | D5 | wraps the rendered SVG so a large diagram can be panned and zoomed | [viewer.js](tools/coyodex/viewer/viewer.js:4575) |
| C15 | calls | D6 | loads both frontend bundles from the pinned CDN URLs, checked by subresource integrity | [viewer.html](tools/coyodex/viewer/viewer.html:16) |
| C15 | calls | D7 | opens a mapped file as a blob URL pinned to the map's commit when no editor is configured | [viewer.js](tools/coyodex/viewer/viewer.js:5973) |
| C15 | calls | D8 | hands a path and line to the chosen desktop editor through its URL scheme | [viewer.js](tools/coyodex/viewer/viewer.js:5970) |
| C15 | reads | D9 | reads the per-machine viewer preferences — chosen editor, confirmed root, GitHub repo, pane sizes | [viewer.js](tools/coyodex/viewer/viewer.js:5878) |
| C15 | writes | D9 | stores a preference the moment it is set, tolerating a browser that refuses to persist | [viewer.js](tools/coyodex/viewer/viewer.js:5879) |
| C15 | reads | E45 | assigns the fetched bundle into the module state every view then renders from | [viewer.js](tools/coyodex/viewer/viewer.js:106) |
| C16 | uses | C1 | reads the map's elements to index every anchor a change could hit | [impact_git.py](tools/coyodex/impact_git.py:221) |
| C16 | uses | C2 | parses each stored anchor into a comparable path and line range | [impact_lib.py](tools/coyodex/impact_lib.py:189) |
| C16 | reads | D1 | reads both sides' diffs, the full-tree rename maps, and each side's file text | [impact_git.py](tools/coyodex/impact_git.py:49) |
| C16 | writes | E52 | indexes every anchor the map carries, keeping which element and field each came from | [impact_git.py](tools/coyodex/impact_git.py:221) |
| C16 | writes | E51 | decides which of the pin's lines a change really affects by comparing both sides' hunks | [impact_lib.py](tools/coyodex/impact_lib.py:135) |
| C16 | writes | E53 | records each hit at the finest rung that honestly holds — line, enclosing definition, or file | [impact_lib.py](tools/coyodex/impact_lib.py:353) |
| C16 | writes | E56 | assembles the projection layer's whole result, with a warning for anything it could not do exactly | [impact_git.py](tools/coyodex/impact_git.py:228) |
| C17 | uses | C16 | spreads outward from the direct hits the projection layer produced | [impact_ripple.py](tools/coyodex/impact_ripple.py:184) |
| C17 | reads | E53 | seeds the ripple from the direct hit set only, so a rippled element never re-fires | [impact_ripple.py](tools/coyodex/impact_ripple.py:184) |
| C17 | reads | E57 | keeps read-only links, the entity graph and the transitive call graph off unless the caller asks | [impact_ripple.py](tools/coyodex/impact_ripple.py:276) |
| C17 | reads | E1 | walks the map's grouping, flows and edges to decide what each hit reaches | [impact_ripple.py](tools/coyodex/impact_ripple.py:80) |
| C17 | writes | E48 | turns a unified diff into the rows the code view paints | [diffmap.py](tools/coyodex/viewer/diffmap.py:40) |
| C18 | uses | C19 | asks for the candidate map's profile and, when a judge is injected, its judge report | [run.py](eval/tools/coyodex_eval/run.py:60) |
| C18 | uses | C9 | prints the audit's grounding worklist as the judging orchestration's input | [run.py](eval/tools/coyodex_eval/run.py:303) |
| C18 | uses | C1 | loads a map to list its claims without going through the full profile | [run.py](eval/tools/coyodex_eval/run.py:303) |
| C18 | uses | C13 | archives the run's view bundle so a regressed run can be inspected as the viewer would show it | [run.py](eval/tools/coyodex_eval/run.py:131) |
| C18 | reads | D10 | reads the blessed baseline's profile and judge report, and the thresholds file | [run.py](eval/tools/coyodex_eval/run.py:232) |
| C18 | writes | D10 | archives the map, profile, judge report and comparison into a run folder, and promotes one to the baseline | [run.py](eval/tools/coyodex_eval/run.py:248) |
| C18 | writes | E69 | applies the gates then the bands, with REGRESSED taking precedence over DRIFT over PASS | [compare.py](eval/tools/coyodex_eval/compare.py:332) |
| C18 | writes | E70 | assembles one run's profile, judge report, comparison and verdict | [run.py](eval/tools/coyodex_eval/run.py:69) |
| C18 | reads | E64 | merges the per-project overrides onto the built-in gates and bands, key by key | [compare.py](eval/tools/coyodex_eval/compare.py:118) |
| C19 | uses | C8 | reuses the validator's exact parse, so a map is never scored through a second grammar | [profile.py](eval/tools/coyodex_eval/profile.py:129) |
| C19 | uses | C9 | counts the audit's findings by severity and the size of its grounding worklist | [profile.py](eval/tools/coyodex_eval/profile.py:131) |
| C19 | uses | C10 | reads the diagram fan-out summary into the profile's report-only balance fields | [profile.py](eval/tools/coyodex_eval/profile.py:149) |
| C19 | uses | C4 | re-computes the component expectation from the code tree at scoring time | [profile.py](eval/tools/coyodex_eval/profile.py:143) |
| C19 | uses | C1 | loads the map document into the model the profile is built from | [profile.py](eval/tools/coyodex_eval/profile.py:122) |
| C19 | reads | D10 | reads the map file it is asked to score | [profile.py](eval/tools/coyodex_eval/profile.py:272) |
| C19 | writes | E58 | reduces one map to the signals that survive an LLM rewording it | [profile.py](eval/tools/coyodex_eval/profile.py:162) |
| C19 | writes | E63 | aggregates the skeptics' majority verdicts and the judges' medians into the semantic report | [judge.py](eval/tools/coyodex_eval/judge.py:257) |
| C19 | writes | E59 | collects one verdict per skeptic per claim, never scoring a failure as a refutation | [judge.py](eval/tools/coyodex_eval/judge.py:236) |
| C19 | writes | E61 | takes the median of the judges' scores for each rubric dimension | [judge.py](eval/tools/coyodex_eval/judge.py:223) |
| C7 | reads | D1 | reads the analyzed repo's short sha and commit date to record what the map was built against | [map_backup.py](tools/map_backup.py:392) |
| C7 | reads | D11 | locates each stamped session's transcript file and sidechain folder by session id | [map_backup.py](tools/map_backup.py:352) |
| C7 | writes | D10 | writes the committed provenance record, and bundles the map files and transcripts into a dated backup folder | [map_backup.py](tools/map_backup.py:409) |
| C7 | persists | E75 | the provenance file is the record of which conversations produced this map | [map_backup.py](tools/map_backup.py:409) |
| C7 | writes | E74 | adds this session's entry, or updates it when the same session stamps twice | [map_backup.py](tools/map_backup.py:392) |
| C21 | uses | C20 | the installed manifest sends the agent straight to the method's dispatch doc in the clone | [SKILL.md](skill/coyodex/SKILL.md:26) |
| C21 | uses | D14 | installs both packages editable into the repo-local virtualenv, with the pre-index extra | [Makefile](Makefile:38) |
| C21 | writes | D10 | creates the virtualenv and writes a path-substituted manifest into each agent's skills home | [Makefile](Makefile:56) |
| C21 | uses | C12 | starts the local map server on the configured port and opens the landing page | [Makefile](Makefile:88) |
| C20 | uses | C4 | prescribes the pre-index as the structural input, run after the behavioral draft and never before | [method.md](method.md:573) |
| C20 | uses | C5 | makes every harvest agent lint its own fragment before returning it | [method.md](method.md:988) |
| C20 | uses | C6 | prescribes assembling the fragments rather than hand-authoring the stored file | [method.md](method.md:1107) |
| C20 | uses | C8 | makes validation the first half of the invariant every write must pass | [method.md](method.md:1118) |
| C20 | uses | C9 | makes the adversarial audit the second half of the invariant | [method.md](method.md:1133) |
| C20 | uses | C10 | prescribes re-balancing the grouping against the traced edges before the map is finished | [method.md](method.md:852) |
| C20 | uses | C11 | prescribes checking and applying anchor drift with the tool, never a hand script | [method.md](method.md:886) |
| C20 | uses | C14 | makes rendering the markdown view the third half of the invariant, and forbids hand-editing it | [method.md](method.md:1166) |
| C20 | uses | C7 | prescribes stamping the driving conversation into the map's provenance | [method.md](method.md:1087) |
| C20 | uses | C12 | tells the reader to start the server and open the project to see the interactive map | [method.md](method.md:1177) |
| C16 | writes | E50 | parses one file pair's diff output into the hunks the fate comparison runs on | [impact_lib.py](tools/coyodex/impact_lib.py:58) |
| C16 | writes | E54 | reads each file's fate out of git's name-status output, keeping both paths when a file moved | [impact_git.py](tools/coyodex/impact_git.py:82) |
| C12 | writes | E57 | builds the ripple options from the request's query string, leaving the noisy links off unless asked | [serve.py](tools/coyodex/viewer/serve.py:356) |

---

## Test completeness — gaps against the map

> **Tests run for this table?** Tests run for this table? YES — `.venv/bin/pytest tests eval/tests` was run during this build and all 807 tests passed. Coverage was NOT measured: no coverage tool is installed in the repo's dev extra, so which lines actually ran is unknown. Every row below is therefore judged by READING the suite and confirming it executes, which puts it at INFERRED on the confidence ladder — running with line and branch coverage is what would make a row verified. The gaps are the deliverable: the backup script and the browser frontend are the two large unexercised surfaces.

| Target | Tested? | Test(s) | Gap / risk | Confidence |
|---|---|---|---|---|
| Provenance stamping & map backup (Provenance & backup, Provenance, SessionEntry, Back up a map with its conversation) | no |  | The largest untested surface: 631 lines with no test file anywhere in either suite. Nothing exercises the provenance round-trip, the recovery path that finds a session by searching transcripts that wrote a map, the copy-versus-move rule that must never move a live transcript, or the destructive default of MOVING the .coyodex files out of the source repo. A defect here loses a map or a conversation, and both are irreversible. | verified |
| Viewer frontend behaviour (Viewer frontend, Explore a map in the viewer, Read a mapped element's source, Explore the impact of a code change) | no | [test_viewer_js.py](tests/test_viewer_js.py:1) — a `node --check` syntax gate over the bundle — it parses the file without executing any of it, and skips entirely when node is not installed | 6,886 lines of hand-edited browser JavaScript with no behavioural test at all: the diagram click bridge, the drill history, the code viewer, the impact overlay and the editor hand-off are all unexercised. The one guard catches an unbalanced brace, nothing more — and it is skipped rather than failed on a machine without node, so the gate can be silently absent. Every viewer regression has to be caught by hand in a browser. | verified |
| Install and start (Skill manifest & installer, Install the coyodex skill, Serve the maps) | no |  | Nothing exercises `make install` or `make start`. The path substitution that bakes this clone's absolute path into each installed manifest is the single point of failure for the whole product — a wrong path makes every `/coyodex` invocation read the wrong method — and it is checked only by a maintainer running the install by hand. | verified |
| Map server request surface (Map server) | partial | [test_serve.py](tests/test_serve.py:385) — drives the static and view routes over a real socket · [test_serve_fresh.py](tests/test_serve_fresh.py:41) — an edited map is picked up on the next request, a broken edit keeps serving the old bundle and retries · [test_impact_serve.py](tests/test_impact_serve.py:59) — the working-tree read refuses ignored files, git internals, a relative escape and a symlink out of the repo | The loopback Host guard and the relative-path guard are unit-tested, but two guards on the same surface are not exercised end to end: the CSRF header check on the three state-changing POST routes has no test that a request without the header is refused, and the git ref shape check has no test of its own. Both are security guards on a server that has no authentication behind them. | verified |
| Structural pre-index (Structural pre-index) | partial | [test_preindex.py](tests/test_preindex.py:1) — the weight walk, the Python symbol and import extraction, and the coverage block · [test_granularity.py](tests/test_granularity.py:1) — the component expectation E and the stop rule that decides where to recurse | The Python path is well covered because it uses the standard library's own parser. The tree-sitter path — the whole reason the optional dependency exists — is exercised only where the grammar pack happens to be installed, so a polyglot repo's symbol extraction can break without any test noticing. | verified |
| View bundle & diagram generation (View bundle builder) | partial | [test_gen_deployment.py](tests/test_gen_deployment.py:1) — the Deployment view's process topology, infrastructure lane and environment gating · [test_data_view.py](tests/test_data_view.py:1) — the store-centric Data view derived from the entity stores and the C→E edges · [test_convert_and_views.py](tests/test_convert_and_views.py:1) — model to graph to bundle, end to end | The Deployment and Data views are tested in depth, but the Context, subsystem, domain and per-flow diagram generators are covered mostly through the end-to-end bundle assertions rather than by their own cases. A subtly wrong Mermaid source for one of those altitudes would still assemble and still serve. | verified |
| Map model, loader & serializer (Map model & serializer, ProjectModel) | yes | [test_model.py](tests/test_model.py:1) — the structural loader's field-by-field errors, the id-shape rule, the deterministic serializer and the id remap · [test_json_schema.py](tests/test_json_schema.py:1) — the generated schema stays derived from the dataclasses | The reference remap is guarded by a regression test that fails when a new reference site is added to the reader but not to the writer — the one place where a silent divergence would leave dangling references after a merge. | verified |
| Model validator (Model validator) | yes | [test_validate_model.py](tests/test_validate_model.py:1) — the semantic checks, the advisories, and the recorded-adjudication escapes that silence them · [test_granularity.py](tests/test_granularity.py:1) — the component-count advisory against the re-measured expectation | The largest module in the repo, and the suite tracks it closely. The residual risk is breadth rather than depth: each new advisory needs its own case, and an advisory added without one would simply never fire in anger. | verified |
| Model auditor & grounding worklist (Model auditor, Finding, WorkItem) | yes | [test_audit.py](tests/test_audit.py:1) — the blocking prerequisite contradiction, the advisory ordering and actor checks, and the worklist's ranking and self-describing detail | Well covered for a component whose whole job is judgement. What no test can assert is whether the ranking actually puts the most dangerous claims first — that is settled by the eval's grounding pass-rate, not here. | verified |
| Diagram balance (Diagram balance, Proposal) | yes | [test_balance.py](tests/test_balance.py:1) — the fan-out advisories, the recorded exceptions, and the report · [test_grouping.py](tests/test_grouping.py:1) — the largest test file in the repo: the grouping graph, modularity and the split proposer | The proposal engine is exercised hard. Its stated contract — that balance may only ever re-group and may never merge or split a component to hit a number — is a design rule enforced by review rather than by a test. | verified |
| Fragment assembly & reconcile (Fragment assembler, Reconcile) | yes | [test_assemble.py](tests/test_assemble.py:1) — the merge, the duplicate-id refusal, the dependency and component collapse, the actor-edge strip, the derived entity edges and the reconcile directives | The derived-edge verb inference defaults anything ambiguous to a read so it can never invent ownership; that default is tested, but the phrase vocabulary it reads is open-ended, so a new authoring style could silently land more edges in the default bucket. | verified |
| Anchor drift & the fix verbs (Grounding reconcile, DriftResult) | yes | [test_anchor_drift.py](tests/test_anchor_drift.py:1) — the consensus line, the tolerance and the different-file case · [test_fix.py](tests/test_fix.py:1) — apply-drift matching on the whole triple, drop-edge healing the riding steps, and the duplicate-relation resolution | The triple matching that stops a paired persists/reads edge from being swapped is directly tested — the exact defect a hand-written script once caused. | verified |
| Change-impact projection & ripple (Impact projection, Impact ripple, FileFrame, DirectHit) | yes | [test_impact.py](tests/test_impact.py:1) — the pin-frame fate comparison, renames, and the line/symbol/file resolution ladder · [test_impact_ripple.py](tests/test_impact_ripple.py:1) — the typed rules applying once, the strength lattice, and the opt-in links staying off · [test_diffmap.py](tests/test_diffmap.py:1) — unified-diff row parsing | The engine's soundness claim is that it errs only towards false positives. The suite checks the stated cases; it does not fuzz arbitrary diffs, so an alignment case git handles unusually could still under-report. | verified |
| Generated views & file tree (Generated views, GraphDict, FileTreeNode) | yes | [test_convert_and_views.py](tests/test_convert_and_views.py:1) — the markdown rendering and the model-to-graph conversion · [test_filetree.py](tests/test_filetree.py:1) — the coverage tags, the click-target rule and the path-collision case | The markdown view is also guarded indirectly by the validator's staleness check, which fails whenever the committed copy stops matching a re-render. | verified |
| Fragment linter (Fragment linter) | yes | [test_lint_fragment.py](tests/test_lint_fragment.py:1) — the schema, anchor-format, unknown-key and missing-file findings, and the advisory-versus-failure split | Covered for what it reports. Whether it reports enough is structural: it borrows the validator's checks, so a check the validator gains is only picked up here if it is wired in explicitly. | verified |
| Shared grammar & anchors (Shared grammar & anchors, AnchorLoc) | yes | [test_anchors.py](tests/test_anchors.py:1) — the anchor shapes, including extensionless files carrying a line · [test_grammar_roles.py](tests/test_grammar_roles.py:1) — the verb-to-role derivation and the dual-role dependency case | The entry-point kind folding is tested for the aliases that exist; the rule that an ambiguous spelling must stay minted rather than be silently rerouted is the kind of decision only a case-by-case test protects, and it came from an adversarial review rather than a failure. | verified |
| Model reader (Model reader) | yes | [test_dump.py](tests/test_dump.py:1) — each of the fixed slices and the default map path | A small read-only surface, fully exercised. | verified |
| Method-quality eval (Eval harness, Eval profile & judge, MapProfile, JudgeReport, DeltaReport) | yes | [test_profile.py](eval/tests/test_profile.py:1) — every profile field, including the ones that stay report-only · [test_judge.py](eval/tests/test_judge.py:1) — majority verdicts, the failure that is never a refutation, the medians and the protocol fingerprint · [test_compare.py](eval/tests/test_compare.py:1) — the hard gates, the bands, the granularity band and the verdict precedence · [test_run.py](eval/tests/test_run.py:1) — the orchestration, the archive and blessing a run | The whole pipeline is testable without a model because the judge is injected, and the suite uses that seam. What is untested is the real judge implementation itself, which lives in the orchestration prompts rather than in this package. | verified |
| CLI dispatch (CLI dispatcher) | yes | [test_cli.py](tests/test_cli.py:1) — the verb routing, the default map path and the unknown-command exit | The dependency firewall — that no command other than the pre-index may pull in a third-party import — is a rule the tests do not assert. It holds today by the lazy-import structure alone, so an eager import added at module level would break it silently. | verified |
| Method documents (Method docs) | no |  | Not testable as code, and deliberately so: the method is a prompt corpus, and its regression harness is the eval — a rebuild judged against a blessed baseline. That harness needs a pinned reference repo and a real model, so it does not run in this suite. | verified |

---

## Entry-point coverage

cli: complete — walked the `coyodex` dispatch table (tools/coyodex/cli.py:76-108), the `coyodex-eval` dispatch table (eval/tools/coyodex_eval/cli.py), the two `python -m` debug mains, and map_backup's argparse subcommands.
http-route: complete — walked Handler.do_GET and Handler.do_POST plus both sub-routers (tools/coyodex/viewer/serve.py:511-682); every reachable path is listed.
agent-skill: complete — the two manifests `make install` / `make install-eval` copy into the agents' skills homes.

---

## Self-starting entry points

There are none, asserted rather than assumed. coyodex has no scheduled job, worker, poller, queue consumer, boot hook or signal handler: a search for threads, timers, event loops and exit hooks across both packages finds only the map server's own accept loop, which is started by the `coyodex serve` verb (tools/coyodex/viewer/serve.py:734) and therefore belongs to that external entry point. The server keeps itself in step with an edited map lazily, per request (tools/coyodex/viewer/serve.py:136), rather than by watching the filesystem, so there is no background watcher either.

---

## Balance exceptions

granularity: the map carries 22 components against a code-derived expectation E of 11 (band 6–16). E sizes a directory by mass, so it folds `tools/coyodex/`'s 37 modules into about nine boxes. Here that would hide exactly what the map exists to explain: each module in this repo is one command verb or one pipeline stage, with its own tests and its own place in the build invariant, so validate, audit, balance and the anchor-drift reconcile would collapse into a single "checks" box. The map is deliberately one altitude finer than E, at roughly twice its count, and every component still obeys the leaf rule (each is at most three files and well under the line cap).

---

## Coverage exceptions

tests/: the regression suite is measured in the Tests table, not mapped as components.
eval/tests/: same, for the eval package's suite.
assets/: README images.
.github/: issue and pull-request templates only, no workflows.
build/: setuptools' editable-install scratch output, git-ignored.
map-backups/: local map+transcript archives written by the backup script, git-ignored.

---

## Happy Path coverage

UC16: looking an element up with `coyodex dump` is an orchestration and spelunking convenience the agent reaches for at any point, not a step in the product's story — placing it on the spine would suggest an ordering it does not have.
UC17: backing a map up with its conversation is a deliberate archival action taken long after a map is built, so it sits off the walk rather than inside it.

---

## Persistence exceptions

C12: the map server's only write is the served-project list — a bare array of folder paths in one small JSON file, with no named type behind it. Synthesizing an entity for it would put a box on the domain diagram that no class backs.
C14: the render step writes the markdown view, which is a generated rendering of the map model rather than a stored type of its own; the model it renders is already owned by the assembler.
C15: the viewer's browser-storage writes are loose preference keys — a chosen editor, a confirmed root, pane sizes — set and read individually, with no record type grouping them.
C21: the installer's writes are the virtualenv and a path-substituted copy of a markdown manifest; neither is data the product models.

---

*Generated with coyodex from `project-map.json` — the committed source of truth. Do not edit this file; regenerate it with `coyodex render`.*
