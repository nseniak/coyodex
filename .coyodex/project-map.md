# coyodex — Codebase Analysis

<!-- GENERATED VIEW — do not edit. The source of truth is project-map.json; regenerate this
     file with `coyodex render project-map.json project-map.md`. -->

> Built with the **coyodex** method. Behavioral layer first (Goal → Glossary → Roles →
> Use cases → Happy Path), then the structural machine (Components → Entry points /
> Model / Deps → Flows + Edges), joined at **use case ↔ flow**.
> The committed source of truth is `project-map.json` (JSON); this file is a generated
> view. IDs, cross-references, and confidence tags are validated by
> `coyodex validate project-map.json`.
> **Commit:** `b9050ae` · **Committed:** `2026-07-29` · **Built:** `2026-07-29 11:06`

---

## T0 — Goal (the anchor)

coyodex is for a developer whose AI coding agent has written more code than they can hold in their head — code that runs fine until the day they need to understand it. It gives that developer a top-down, drillable map of the codebase: an AI coding agent reads coyodex's method (a set of prose prompts), reads the repo, and produces a structured map — what the project is for, who uses it, the ordered walk through its main use cases, then the machine underneath (components, dependencies, the domain model, the flows and calls that connect them). Every claim in the map is anchored to a real file:line, checked by deterministic gates, and attacked by fresh agents that try to disprove it against the code. The map is committed next to the code and pinned to a commit, so it can be diffed and updated as the code changes, and it is read in an interactive C4 viewer served locally, where each box drills down to the source it describes.

---

## Glossary — the ubiquitous language

| Term | Meaning | Defined / used in |
|---|---|---|
| **Coyote Effect** | the state coyodex exists to cure: an agent has generated so much code that the developer has lost track of it, and — like the cartoon coyote past the cliff edge — nothing is under their feet the day they need to understand it | [README.md](README.md:26) |
| **Map (project map)** | the deliverable: one structured JSON document describing a whole codebase top-down, committed next to the code as .coyodex/project-map.json | [model.md](method/model.md:3) |
| **Method** | the prose instructions an AI coding agent follows to build and maintain a map — the program half of the product, shipped as markdown rather than code | [method.md](method.md:1) |
| **Skill** | the small manifest installed into a coding agent's skills folder that makes /coyodex reach the method docs and the CLI in this clone | [SKILL.md](skill/coyodex/SKILL.md:1) |
| **Behavioral layer** | the why/who/what half of a map — goal, glossary, roles, use cases, Happy Path — authored before any code is read | [method.md](method.md:26) |
| **Structural layer** | the machine half of a map — components, dependencies, entry points, the domain model, flows and edges | [method.md](method.md:161) |
| **Use case** | one actor goal with one trigger and one outcome; the join point between the two layers, since each use case has a flow | [method.md](method.md:50) |
| **Happy Path** | the map's spine: one end-to-end ordering of use cases that walks the whole product as a coherent story | [method.md](method.md:86) |
| **Flow (T6)** | the inside view of one use case — its ordered steps between components, dependencies, entities and the actor, each step anchored at its own call site | [method.md](method.md:234) |
| **Sub-flow** | a named step sequence shared by two or more flows, defined once and referenced, so shared machinery is told at one depth everywhere | [method.md](method.md:292) |
| **Component** | one module-, folder- or deployable-sized unit of the code with a single purpose — the leaf box of the map | [method.md](method.md:176) |
| **Subsystem** | a group of components (or of smaller subsystems) — the altitude above components, grouped by what the system does rather than by tech tier | [method.md](method.md:164) |
| **Entity (domain card)** | a real named type in the code, written as a card with its meaning, fields and relations, and rendered as a class diagram | [domain-cards.md](method/domain-cards.md:1) |
| **Subdomain** | a bounded context grouping entities — the domain-model analog of a subsystem | [method.md](method.md:229) |
| **Backbone edge** | one project-wide list of typed relationships between components, dependencies and entities, each with a verb, a reason and a witnessed call site | [method.md](method.md:444) |
| **Anchor** | a bare path:line reference to the exact source location that grounds a claim; every element and most claims carry one | [model.md](method/model.md:309) |
| **Fragment** | a partial map returned by one build agent as JSON; the tooling merges the fragments into the stored model so no agent ever hand-writes it | [model.md](method/model.md:363) |
| **Pre-index** | a mechanical scan of the code tree that reports where the weight is, where symbols are defined, and how many components the tree implies — sizing input, never rows for the map | [method.md](method.md:566) |
| **E (expected components)** | the component count the pre-index derives from the code tree, with a generous band; landing far outside it means the altitude was misjudged, and a deliberate exception is recorded | [method.md](method.md:593) |
| **Fan-out rule** | the readability budget for one screen — about five boxes per diagram, so a large system is grouped into levels instead of one crowded picture | [method.md](method.md:609) |
| **Baseline pin** | the commit the map describes, recorded in the map itself, so a later diff knows exactly which code the map was true for | [method.md](method.md:1128) |
| **Grounding (adversarial pass)** | the final build phase: fresh agents that never saw the build reasoning try to disprove each claim against the code, and every refutation is reconciled | [method.md](method.md:929) |
| **Change impact** | what a code diff does to an existing map — which elements it modifies, adds or deletes, and what those ripple to through the edges and flows | [change-impact.md](method/change-impact.md:1) |
| **Analyze / Accept** | the two maintenance moves: analyze reports a diff's impact without touching the baseline; accept patches the map, re-pins it and commits it | [dispatch.md](method/dispatch.md:14) |
| **Drilling deeper** | refining altitude inside the one map — nesting a subsystem, promoting a component into one, or flattening a level that pulls no weight; never a second map file | [method.md](method.md:1272) |
| **Verified / inferred** | the confidence label every claim carries: read in the code, or guessed from naming and docs | [method.md](method.md:530) |
| **Viewer** | the interactive C4 page a local server builds from the model on demand — never a committed file, so it always matches the map | [model.md](method/model.md:351) |

---

## Roles (actors)

| Role | Kind | What they want | Use cases they drive |
|---|---|---|---|
| **Developer** | human | to understand and oversee a codebase they have lost track of — top-down, without reading all of it, drilling into the code only where it matters | UC1, UC3, UC4, UC5, UC10, UC11 |
| **Coding agent** | service | to turn a repo it has read into a grounded, gate-passing map, and to keep that map in step with the code as the developer changes it | UC2, UC6, UC7, UC8 |
| **Method maintainer** | human | evidence that a change to coyodex's own method or tooling made the maps it produces better rather than worse | UC9 |

---

## Use cases

| ID | Use case | Actor | Trigger → Outcome |
|---|---|---|---|
| **UC1** | Install the coyodex skill | Developer | A developer clones coyodex and runs `make install` → the skill manifest, with this clone's path baked into it, sits in every coding agent's skills folder, and a repo-local virtualenv holds the `coyodex` command; typing `/coyodex` in any agent now reaches the method. |
| **UC2** | Build a baseline map of a repo | Coding agent | The developer types `/coyodex` in a repo that has no map → the agent reads the method, sizes the code tree, fans out to read the repo, and leaves a validated, commit-pinned map (the JSON model, its markdown view and the pre-index) committed in `.coyodex/`. |
| **UC3** | Start the local map server | Developer | The developer runs `make start` in the coyodex clone → a small local server is listening on 127.0.0.1, offering a landing page that lists every project they have mapped. |
| **UC4** | Explore a map top-down | Developer | The developer opens a project in the viewer → they read the goal, the Happy Path and the diagrams, and drill from one screen of boxes into the level beneath it, seeing each element's plain-language annotation as they go. |
| **UC5** | Open the source behind a mapped element | Developer | The developer clicks the code anchor on a box, arrow or flow step → the exact file and line that grounds the claim appears in the code viewer, read from git at the commit the map is pinned to, with the option to hand it off to their editor or GitHub. |
| **UC6** | Analyze a code change against the map | Coding agent | The developer edits code and types `/coyodex analyze` → the agent diffs the working tree against the map's pinned commit and writes an uncommitted report saying which mapped elements the change modifies, adds and deletes, and what those ripple to. |
| **UC7** | Accept a change into the baseline | Coding agent | The developer is satisfied with the report and types `/coyodex accept` → the agent patches the model in place, re-pins it to the new commit, re-runs the gates, regenerates the markdown view and pre-index, and commits the map beside the code. |
| **UC8** | Change the map on request | Coding agent | The developer asks in plain language for a map change ("split this component", "rename that subsystem") → the agent edits the stored model surgically, refusing anything the code does not back, passes the same gates as any other write, and commits the result. |
| **UC9** | Check the method's quality | Method maintainer | A maintainer runs the eval on a project that already has a map → a fresh map is built with the current method, scored on grounding and a rubric, and compared against the committed baseline, so a method change is reported as an improvement or a regression instead of a hunch. |
| **UC10** | Back up a map with its build transcript | Developer | The developer runs the backup script against a mapped repo → the map is bundled together with the exact conversation that produced it, found through the session id the build stamped into the map's provenance file. |
| **UC11** | See what a change ripples to in the viewer | Developer | The developer opens the impact explorer and picks two commits → the diagrams light up with what the diff touched and what that reaches through the map's edges and flows, and each changed file can be read as a diff in place. |

---

## Happy Path — the spine (an ordered walk through the use cases)

The happy-path ordering of use cases. Each step IS a use case (its `*(UCn)*` tag
names it); the step's detail lives in that use case's T6 flow. An optional `why:`
line records the prerequisite that fixes the step's position.

**HP1 — Developer installs the coyodex skill** *(UC1)*
**HP2 — Coding agent builds the repo's baseline map** *(UC2)*
why: needs the skill and the CLI installed in HP1
**HP3 — Developer starts the local map server** *(UC3)*
why: needs the CLI and virtualenv installed in HP1
**HP4 — Developer explores the new map top-down** *(UC4)*
why: needs the map from HP2 and the server from HP3
**HP5 — Developer opens the source behind a box that surprised them** *(UC5)*
why: the code viewer reads from git at the commit the HP2 map is pinned to
**HP6 — Coding agent analyzes the developer's next code change** *(UC6)*
why: diffs against the baseline pinned in HP2
**HP7 — Developer sees what that change ripples to in the viewer** *(UC11)*
why: needs the server from HP3 and the code change analyzed in HP6
**HP8 — Coding agent accepts the change into the baseline** *(UC7)*
why: acts on the report written in HP6
**HP9 — Developer asks for the map itself to be restructured** *(UC8)*
why: edits the baseline map built in HP2
**HP10 — Developer backs up the map with its build transcript** *(UC10)*
why: pairs the map with the session stamped into its provenance during HP2
**HP11 — Method maintainer checks whether the method improved** *(UC9)*
why: compares a fresh build against the baseline accepted in HP8

---

## Subsystems (S) — the container altitude

| ID | Subsystem | Purpose | Parent | Tech | Source | Conf. |
|---|---|---|---|---|---|---|
| **S1** | Method & skill | The prose program a coding agent executes: the method docs that tell it how to build, check and maintain a map, plus the small manifest that makes /coyodex reach them. This is shipped as markdown rather than code, and it is as much the product as the tools are. |  |  |  | verified |
| **S2** | Map authoring | Everything that turns an agent's reading of a repo into the stored map: sizing the code tree first, then defining what a map IS and merging the agents' fragments into one canonical document. |  | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/ | inferred |
| **S3** | Map model | The definition of a map: the typed document, the vocabularies its fields may use, the anchor format every claim is written in, and the published JSON schema derived from all of it. | S2 | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/ | inferred |
| **S4** | Fragment assembly | The build path from many agents to one file: each agent self-checks its fragment, the assembler merges them by id, and reconcile/fix apply the assignments and corrections that must survive a re-assemble. | S2 | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/ | inferred |
| **S6** | Map checking | The gates a map must pass before anyone trusts it: is it well-formed and do all its references and anchors resolve, do its cited lines really exist in the code, is it self-contradictory, and is it readable at each altitude. |  | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/ | inferred |
| **S7** | Map viewing | How a reader actually consumes a map: the model turned into diagrams and tables, served locally, and explored in the browser down to the source line each box stands for. |  |  | tools/coyodex/viewer/ | inferred |
| **S11** | Diagram generation | Builds, from the stored model, every diagram and side-panel payload the viewer shows — the context and subsystem drills, the domain class diagrams, the deployment and channel views, and the Happy Path and use-case sequences. | S7 | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/viewer/ | inferred |
| **S12** | Browser viewer | The single-page app the reader works in: the diagram canvas and its drill navigation, the info pane for a selected element, the file browser and code viewer, search, and the change-impact overlay. | S7 | JavaScript (browser) ([pyproject.toml](pyproject.toml:51)) | tools/coyodex/viewer/ | inferred |
| **S13** | Map serving | The small local HTTP server that fronts every mapped project — serving each map's diagram data built on demand, and reading the mapped repo's files from git at the commit the map is pinned to. | S7 | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/viewer/ | inferred |
| **S8** | Map lifecycle | Keeping a map true over time: working out what a code diff does to the map and what that ripples to, and preserving a map together with the exact conversation that built it. |  | Python ([pyproject.toml](pyproject.toml:9)) |  | inferred |
| **S9** | Method-quality eval | coyodex measuring itself: rebuild a map with the current method, judge it on grounding and a rubric, and compare it against the project's committed baseline to say whether the method got better or worse. |  | Python ([pyproject.toml](pyproject.toml:43)) | eval/tools/coyodex_eval/ | verified |
| **S10** | Command front door | The single `coyodex` command every other part is reached through, and the read-only lookup that answers questions about a stored map without opening it by hand. |  | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/ | inferred |

---

## T1 — Components

| ID | Component | Subsystem | Purpose | Entry point | Depends on | Conf. | Files | Evidence | Runs in |
|---|---|---|---|---|---|---|---|---|---|
| **C11** | Validate semantic-check helpers | S6 | The shared helper library the map validator calls for its semantic (non-schema) checks: it decides whether a nesting parent is the right kind, defined, and cycle-free (all blocking), and it computes the opt-in map-fidelity advisories — peer-level directory compression, absent/unreferenced modules, uncovered code files grouped by directory, and the component-count-vs-code-derived-expectation granularity band. It also owns anchor/source resolution (stripping a `:line`, resolving a path against the repo root) and the domain-coverage thresholds, and it re-measures the repo tree itself rather than trusting the pre-index's JSON. |  |  | verified | tools/coyodex/validate_analysis.py | [validate_analysis.py](tools/coyodex/validate_analysis.py:50) — The blocking hierarchy problem: a child whose parent is not the expected kind (component/subsystem must sit under an S, entity/subdomain under an SD) is appended to `problems`, not `warnings`. · [validate_analysis.py](tools/coyodex/validate_analysis.py:63) — Nesting-cycle detection appends to `problems` too — the cycle check, not a depth cap, is what makes the parent walk terminate; over-deep nesting only becomes an advisory warning. · [validate_analysis.py](tools/coyodex/validate_analysis.py:149) — The peer-compression advisory fires when the map individually references fewer than about a quarter of a directory's sibling source subdirs — the 'many modules folded into one box' lost-signal test. · [validate_analysis.py](tools/coyodex/validate_analysis.py:228) — The file-level coverage gap: a code source file is skipped when it is covered by an exact ref, by a referenced directory prefix, or by a recorded 'Coverage exceptions' dir; everything left is reported grouped by directory. · [validate_analysis.py](tools/coyodex/validate_analysis.py:270) — The granularity advisory stays silent inside the +/-40% band around the code-derived expected component count, and only outside it emits the fold-vs-split hint — a zoom anchor, never a verdict. | coyodex CLI, coyodex-eval CLI |
| **C12** | Map auditor | S6 | The adversarial pass (`coyodex audit`) that makes the map's two layers refute each other: it reads the narrative Happy Path against the mechanism (flows plus backbone edges) and reports contradictions — a `why:` precondition citing a step that does not exist or comes later in the walk, an entity read before any step writes it, a flow whose opening actor is not among the use case's declared actors, a step with no stated precondition while its siblings have one, and step/edge text written as a static dependency instead of an action. Only hard contradictions block (exit 1); everything else is advisory. It then prints the ranked L2 grounding worklist — self-describing 'actually-does' claims that fresh-context skeptics try to disprove against the code — as text or as `--json`. | [audit_model.py](tools/coyodex/audit_model.py:560) |  | verified | tools/coyodex/audit_model.py | [audit_model.py](tools/coyodex/audit_model.py:593) — The blocking rule in one line: the process exits 1 only when some finding carries CONTRADICTION severity — every ADVISORY / WARNING finding exits 0. · [audit_model.py](tools/coyodex/audit_model.py:234) — A contradiction in practice: a step's `why:` cites a Happy-Path position that comes AFTER it in the walk, so the narrative order refutes its own stated precondition. · [audit_model.py](tools/coyodex/audit_model.py:196) — The narrative-vs-mechanism cross-check that stays ADVISORY on purpose: a step reads an entity the Happy Path only writes later; component-granular attribution is lossy in both directions, so it advises rather than blocks. · [audit_model.py](tools/coyodex/audit_model.py:423) — Worklist tier 1 for edges: an `enforces` / `encrypts` verb is filed as security-critical and appended before the dependency, entity, and generic edge buckets. · [audit_model.py](tools/coyodex/audit_model.py:367) — The self-describing detail that stops false refutations: a component endpoint carries its canonical anchor plus its member entry points, so an umbrella component is never reduced to one arbitrary file. | coyodex CLI, coyodex-eval CLI |
| **C13** | Balance reporter | S6 | Reports how readable each rendered diagram is: per-diagram fan-out against the 5±2 target (flagging sparse, soft 10-12, dense, single-child, and homogeneous-family screens), the inter-subsystem component-to-component edge matrix with its busiest cross-subsystem seams, and, for each over-dense non-exempt diagram, a deterministic greedy-modularity split proposal printed as an exact 'Direct map change' block with the next free subsystem id precomputed. It never gates — the command always exits 0, and the same engine supplies the always-on advisory warnings the validator appends; a 'Balance exceptions' block in the map durably silences named diagrams. | [balance.py](tools/coyodex/balance.py:170) |  | verified | tools/coyodex/balance.py · tools/coyodex/balance_lib.py | [balance.py](tools/coyodex/balance.py:206) — Advisory by construction: the command's normal path prints the report and returns 0 — only a missing or unparsable map file is an error. · [balance.py](tools/coyodex/balance.py:122) — The per-diagram fan-out table, one row per diagram with its child count and flag, printed under the '(target 5±2)' heading. · [balance.py](tools/coyodex/balance.py:138) — The inter-subsystem matrix output: the busiest cross-subsystem seams, ranked by how many component-to-component pairs cross each pair of top-level groups. · [balance_lib.py](tools/coyodex/balance_lib.py:478) — The split engine's stop condition — greedy merging halts as soon as no merge improves modularity, which is what makes the proposal deterministic rather than tuned. · [balance_lib.py](tools/coyodex/balance_lib.py:192) — The durable escape: a line-leading `cadence:` / `store:` / `messaging:` / `isolated:` record (plus plain diagram ids) inside a 'Balance exceptions' extras block adds that token to the skip set, so a justified advisory stops re-firing. | coyodex CLI, coyodex-eval CLI |
| **C30** | CLI dispatcher | S10 | The front door of the single `coyodex` command: it reads the first word on the command line and hands the rest to that subcommand's implementation, printing the command list for no arguments, help, or an unknown command. Each implementation is loaded only inside its own branch, so the everyday commands (validate, render, serve, dump) never pull in the code-parsing path and keep working on a plain Python install with no third-party package present; when a command that reads a map is given no map file, the dispatcher fills in the standard `.coyodex/project-map.json` location itself so callers can stay terse. | [pyproject.toml](pyproject.toml:30) |  | verified | tools/coyodex/cli.py · tools/coyodex/__init__.py | [cli.py](tools/coyodex/cli.py:80) — the pre-index implementation is imported inside its own branch — the only path allowed to touch the third-party parser, so no other command loads it · [cli.py](tools/coyodex/cli.py:84) — a map-reading command is dispatched with the argument list already passed through the default-map filler, so an omitted map file resolves to the standard location · [cli.py](tools/coyodex/cli.py:66) — appends the standard map path when the scan found no positional argument, which is the whole default-map rule · [cli.py](tools/coyodex/cli.py:116) — an unrecognised command prints the error plus the usage to standard error and exits with code 2, so a typo fails loudly instead of doing nothing | coyodex CLI, Map server |
| **C31** | Model dump | S10 | A read-only lookup over a stored map: it parses the map file and prints either the whole model back as canonical JSON, or exactly one of four fixed slices — what an id is (kind, display name, canonical source, and its members), an element's full stored record, the backbone links into and out of a node, or a group's member records. The slice set is deliberately closed rather than a query language, it refuses more than one slice flag, and it falls back to the standard map location when no file is named. | [cli.py](tools/coyodex/cli.py:99) |  | verified | tools/coyodex/dump.py | [dump.py](tools/coyodex/dump.py:158) — with no slice flag the entire parsed model is written back out in the canonical serialization — the whole-map read · [dump.py](tools/coyodex/dump.py:144) — more than one slice flag is rejected outright, which is what keeps the surface to exactly one fixed slice per run · [dump.py](tools/coyodex/dump.py:97) — the links slice scans the map's backbone links by destination and by source, keeping the authored order and duplicates · [dump.py](tools/coyodex/dump.py:85) — the id slice returns the resolved kind, display name, canonical source anchor and members for any element id | coyodex CLI |
| **C3** | Map model & serializer | S3 | Defines the exact shape of a project map — which kinds of elements exist, what fields each one carries, and how their ids must look — and is the only place that turns a map into the committed JSON file and back. It always writes the same bytes for the same map so the file diffs cleanly, and it rejects a malformed map by naming the precise location of the bad value. |  |  | verified | tools/coyodex/model.py | [model.py](tools/coyodex/model.py:612) — the single serialization call — fixed key order, indent 2, trailing newline — so the same map always produces byte-identical JSON · [model.py](tools/coyodex/model.py:676) — loading raises an error naming the exact JSON path of an unknown field, which is how a malformed map is pinpointed · [model.py](tools/coyodex/model.py:771) — loading enforces each element array's required id prefix, so a wrongly-prefixed id fails at load · [model.py](tools/coyodex/model.py:592) — rewrites every reference to a renamed element id across the whole map, so a merge never leaves a dangling pointer | coyodex CLI, Map server, coyodex-eval CLI |
| **C4** | Map grammar & vocabularies | S3 | Holds the shared vocabularies the rest of the toolkit agrees on: what an element id looks like, the kinds and purpose groups a dependency can have, the kinds of entry points and who starts them, the verbs used for data relations and for backbone links. It also fills in a value when the author left one blank, so every reader classifies the same row the same way. |  |  | verified | tools/coyodex/grammar.py | [grammar.py](tools/coyodex/grammar.py:97) — an explicitly authored dependency kind wins; otherwise the keyword fallback below classifies it — the single classification rule · [grammar.py](tools/coyodex/grammar.py:294) — folds a drifted entry-point kind spelling back to its canonical seed, so two consumers cannot split the same kind · [grammar.py](tools/coyodex/grammar.py:317) — the one rule deciding an entry point's effective activation, shared by the viewer, the coverage advisory and the eval · [grammar.py](tools/coyodex/grammar.py:456) — derives a dependency's role purely from the verbs of the links pointing at it, so no stored field can drift from the edges | coyodex CLI, Map server |
| **C5** | Anchor & schema utilities | S3 | Small shared helpers for the code references a map is built on: deciding whether a source pointer is well formed, splitting it into file and line, judging whether a cited line could plausibly be the line where something happens, and measuring how far a stored pointer has drifted from where reviewers found the code. It also parses third-party Python without leaking that code's own warnings, and generates a JSON Schema of the map for documentation and editor autocomplete. | [json_schema.py](tools/coyodex/json_schema.py:286) |  | verified | tools/coyodex/anchors.py · tools/coyodex/pysrc.py · tools/coyodex/json_schema.py | [anchors.py](tools/coyodex/anchors.py:31) — the one test for a well-formed source pointer — a file reference or a directory reference · [anchors.py](tools/coyodex/anchors.py:127) — returns why a cited line cannot be the acting statement (a definition header, an import, a comment) · [anchors.py](tools/coyodex/anchors.py:154) — computes whether the stored pointer drifts from the line reviewers reported, beyond a tolerance · [pysrc.py](tools/coyodex/pysrc.py:19) — suppresses the scanned repo's own syntax warnings so they never surface as coyodex output · [json_schema.py](tools/coyodex/json_schema.py:271) — the schema is generated from the model classes themselves, so it cannot drift from the real shape | coyodex CLI, Map server, coyodex-eval CLI |
| **C6** | Fragment assembler | S4 | Merges the JSON pieces each build agent returns into one canonical map file. It checks every piece against the schema so a bad one fails alone with its name, refuses to silently overwrite when two agents claim the same id, folds away duplicate dependencies, components and links, adds the missing component-to-data links that flow steps imply, applies the reconcile file, and writes the map plus its markdown view. | [assemble.py](tools/coyodex/assemble.py:343) |  | verified | tools/coyodex/assemble.py | [assemble.py](tools/coyodex/assemble.py:181) — the merge itself — every piece's arrays are concatenated into one model, in argument order · [assemble.py](tools/coyodex/assemble.py:185) — the same id claimed by two pieces is reported as a conflict naming both, never silently overwritten · [assemble.py](tools/coyodex/assemble.py:115) — creates the component-to-entity link a flow step implies when no piece supplied one · [assemble.py](tools/coyodex/assemble.py:316) — after collapsing two copies of the same component, re-points every reference to the removed id · [assemble.py](tools/coyodex/assemble.py:474) — writes the canonical map file through the one serializer, so validity is guaranteed by code, not by hand | coyodex CLI |
| **C7** | Fragment linter | S4 | The self-check an authoring agent runs on its own piece of the map before handing it back: shape, source-pointer format, per-row rules for links, flows, data relations and channels, that each cited file really exists in the repo, and that every referenced id is defined here or in a supplied id list. Real errors fail the check; judgment-shaped nudges are printed separately and never fail it. | [lint_fragment.py](tools/coyodex/lint_fragment.py:182) |  | verified | tools/coyodex/lint_fragment.py | [lint_fragment.py](tools/coyodex/lint_fragment.py:150) — with a repo root given, every cited file is checked to actually exist, catching a wrong prefix at the source · [lint_fragment.py](tools/coyodex/lint_fragment.py:80) — reports ids referenced but defined neither in this piece nor in the supplied id universe — an invented id dies here · [lint_fragment.py](tools/coyodex/lint_fragment.py:254) — advisory nudges are printed on a separate channel, so a heuristic never fails the check · [lint_fragment.py](tools/coyodex/lint_fragment.py:258) — exits non-zero on any real finding, which is what makes the check a gate the agent must clear | coyodex CLI |
| **C8** | Reconcile & post-assemble fixes | S4 | The bulk-edit toolkit for a map. Before assembly it turns path rules ("everything under this folder belongs to that subsystem") into an explicit, checked assignment file; during assembly it applies those assignments and removes refuted links, healing the flow steps that rode them. After the map is written it rewrites source pointers that reviewers found in the wrong place, drops a refuted link, and resolves duplicate data relations — replacing the throwaway scripts each build used to write by hand. | [fix.py](tools/coyodex/fix.py:303) |  | verified | tools/coyodex/reconcile_build.py · tools/coyodex/reconcile.py · tools/coyodex/fix.py · tools/coyodex/anchor_drift.py | [reconcile_build.py](tools/coyodex/reconcile_build.py:234) — expands path rules into an explicit assignment file, so a huge map's assignments are generated and checked instead of typed · [reconcile.py](tools/coyodex/reconcile.py:258) — an assignment replaces the stored list rather than appending, which is what makes re-running the build idempotent · [reconcile.py](tools/coyodex/reconcile.py:274) — removes the refuted backbone links named by the reconcile file during assembly · [fix.py](tools/coyodex/fix.py:105) — writes the reviewers' corrected line into the stored link, matching on the full source-verb-target triple so paired links never swap · [anchor_drift.py](tools/coyodex/anchor_drift.py:110) — the no-reviewers pass: flags stored pointers aimed at a line that cannot be the acting statement | coyodex CLI |
| **C9** | Code pre-index | S2 | Walks the repository before the map is built and writes a sizing file: how much code sits in each directory (lines, file counts, how often it changed), where every class and function is defined, import links between parts the agent already named, how many components the code's size suggests, and what the scan could not read. It is advisory input the build agent reconciles, never rows copied into the map. | [preindex.py](tools/coyodex/preindex.py:379) |  | verified | tools/coyodex/preindex.py · tools/coyodex/preindex_lib.py | [preindex.py](tools/coyodex/preindex.py:432) — writes the sizing file holding the weight tree, symbols, imports, expectation and coverage blocks · [preindex.py](tools/coyodex/preindex.py:146) — records every class/function definition by name with its file and line — the symbol index the viewer searches · [preindex_lib.py](tools/coyodex/preindex_lib.py:190) — the file walk that produces the counted set, after generated, vendored and binary files are excluded · [preindex_lib.py](tools/coyodex/preindex_lib.py:541) — the stop rule: a directory small enough to be one component counts as a single expected unit, which is how the expectation is derived · [preindex.py](tools/coyodex/preindex.py:400) — the expectation is computed from the code tree at build time, so it is a code-derived hint rather than anything read back from a map | coyodex CLI, coyodex-eval CLI |
| **C23** | Diagram canvas & drill navigation | S12 | The screen the reader spends their time on: it draws the map as a diagram, lets them pan, zoom and switch between the view tabs (Happy Path, Subsystems, Entities, Dependencies, Data, Deployment, and the text-only Glossary / Use Cases / System / Tests tabs), and lets them drill into a box to replace the diagram with that box's own card. It remembers where they have been, so back and forward return each view to the exact zoom, position and selection it was left at, and it shows the legend, the breadcrumb and the environment filter around the drawing. | [viewer.js](tools/coyodex/viewer/viewer.js:6937) |  | verified | tools/coyodex/viewer/viewer.js · tools/coyodex/viewer/viewer.css · tools/coyodex/viewer/viewer.html | [viewer.js](tools/coyodex/viewer/viewer.js:4562) — turns the diagram source picked for the current view/drill state into an SVG drawing · [viewer.js](tools/coyodex/viewer/viewer.js:4570) — writes that drawing into the page — this single line is what the reader actually sees · [viewer.js](tools/coyodex/viewer/viewer.js:4626) — attaches pan/zoom to the fresh drawing, with wheel-pan and pinch-zoom wired separately at viewer.js:6681 · [viewer.js](tools/coyodex/viewer/viewer.js:3103) — double-click or Option-click on a container box drills in, which pushes a new view instead of opening a popup · [viewer.js](tools/coyodex/viewer/viewer.js:2857) — every diagram-changing move is recorded on a back/forward stack, the basis of the arrows and the Cmd-arrow shortcuts | Browser viewer page |
| **C37** | Element info pane & selection | S12 | Turns a click on the canvas into readable detail: the selected box or arrow lights up, everything unrelated fades, and the pane under the diagram fills with that element's purpose, its type tags, its use cases, its entry points and its links. Hovering an element previews its meaning without selecting it; Cmd-clicking more elements stacks their cards; and on a use-case flow a small player walks the steps one arrow at a time. | [viewer.js](tools/coyodex/viewer/viewer.js:2452) |  | verified | tools/coyodex/viewer/viewer.js · tools/coyodex/viewer/viewer.css | [viewer.js](tools/coyodex/viewer/viewer.js:1121) — writes the clicked element's detail card into the pane — the operative line of the whole info pane · [viewer.js](tools/coyodex/viewer/viewer.js:313) — one atomic step re-glows every selected element, fades the rest, and re-stacks their cards · [viewer.js](tools/coyodex/viewer/viewer.js:454) — a multi-selection appends one card per selected element, so Cmd-clicking a second box adds rather than replaces · [viewer.js](tools/coyodex/viewer/viewer.js:1799) — hovering any box or arrow pops the meaning tooltip, so the map reads without clicking · [viewer.js](tools/coyodex/viewer/viewer.js:1681) — the flow step player replaces the selection with exactly one flow step, driving the arrow keys and the prev/next strip | Browser viewer page |
| **C38** | File browser & code viewer | S12 | The right-hand side of the window: the mapped repository's real folder tree, shaded by how much of it the map covers, next to a read-only source view with line numbers, syntax colouring and an overview ruler. Selecting an element on the diagram reveals and highlights its file here; clicking a file selects the matching element on the diagram and shows the source scrolled to its line. Files come from the server as of the map's commit, and one control re-opens the shown file in an external editor or on GitHub. | [viewer.js](tools/coyodex/viewer/viewer.js:6659) |  | verified | tools/coyodex/viewer/viewer.js · tools/coyodex/viewer/viewer.css | [viewer.js](tools/coyodex/viewer/viewer.js:5242) — draws the repository tree from the server's response — the file browser's whole content · [viewer.js](tools/coyodex/viewer/viewer.js:5806) — fetches the selected file's text (or its inline diff) from the server rather than from disk · [viewer.js](tools/coyodex/viewer/viewer.js:5666) — writes the highlighted source as a numbered-line table, which is what the code pane shows · [viewer.js](tools/coyodex/viewer/viewer.js:4822) — clicking a tree row that anchors an element selects that element, closing the file-to-diagram loop · [viewer.js](tools/coyodex/viewer/viewer.js:6021) — hands the file off to the chosen external editor by URL scheme, with the GitHub blob link as the fallback below it | Browser viewer page |
| **C39** | Map search sidebar | S12 | A single 'jump to anything' box on the far left, opened by the magnifier, the slash key or Cmd-K. Typing filters, as you type, over every element name, entity field, glossary term, operational reference row, file, folder and code symbol, plus the free text of every description. Picking a result reuses the viewer's own navigation: an element is selected in the view that draws it, a file opens in the code viewer, a folder opens in the browser, a term flashes on the Glossary. Typing '@' first scopes the search to the symbols of the file currently open. | [viewer.js](tools/coyodex/viewer/viewer.js:6654) |  | verified | tools/coyodex/viewer/viewer.js · tools/coyodex/viewer/viewer.css · tools/coyodex/viewer/viewer.html | [viewer.js](tools/coyodex/viewer/viewer.js:6224) — every named map element becomes a search row whose action selects it in its home view · [viewer.js](tools/coyodex/viewer/viewer.js:6325) — lazily pulls code symbols from the server, so a class or function the map never names is still findable · [viewer.js](tools/coyodex/viewer/viewer.js:6503) — clicking a result runs that row's navigation — the one place a search hit becomes a move in the viewer · [viewer.js](tools/coyodex/viewer/viewer.js:6647) — Enter jumps to the highlighted result, with the arrow keys moving the highlight just above · [viewer.js](tools/coyodex/viewer/viewer.js:6610) — opening the sidebar builds the index and runs the query, so the first keystroke already has everything to match against | Browser viewer page |
| **C32** | Change-impact overlay | S12 | Lets the reader project a code change onto the map: pick the map's commit against the working tree, or any two commits, choose how far the ripple should spread, and the diagram badges every affected box as added, modified, deleted or rippled. The pane lists everything hit, grouped by kind and clickable; selecting one element explains why it was hit and which files changed; the file browser badges the changed files and can hide the rest; and opening a changed file shows its inline diff instead of the plain source. | [viewer.js](tools/coyodex/viewer/viewer.js:6906) |  | verified | tools/coyodex/viewer/viewer.js · tools/coyodex/viewer/viewer.css · tools/coyodex/viewer/viewer.html | [viewer.js](tools/coyodex/viewer/viewer.js:2132) — stamps the change badge onto each drawn box — the visible result of arming an impact analysis · [viewer.js](tools/coyodex/viewer/viewer.js:6805) — writes the 'what does this diff impact' summary into the info pane, every row clickable · [viewer.js](tools/coyodex/viewer/viewer.js:6928) — changing the ripple depth re-projects which elements count as impacted and redraws in place · [viewer.js](tools/coyodex/viewer/viewer.js:5801) — with an impact armed, opening a changed file requests its inline diff instead of the plain file · [viewer.js](tools/coyodex/viewer/viewer.js:5702) — records which files changed, which is what puts the change dots in the file browser and feeds its 'changed only' filter | Browser viewer page |
| **C1** | Method docs | S1 | The prose program a coding agent executes to build and maintain a map: dispatch picks the mode (build / analyze / accept / direct map change), method.md drives the build, and the sibling docs spell out the JSON model, the domain cards, the diagrams, and the change-impact lifecycle. It is product, not documentation — the agent reads it and follows it instead of working from memory. | [dispatch.md](method/dispatch.md:3) |  | verified | method.md · method/dispatch.md · method/model.md · method/domain-cards.md · method/diagrams.md · method/change-impact.md · method/templates/project-map.template.md | [dispatch.md](method/dispatch.md:14) — the docs are executable instructions with modes, not reference: an invocation naming build / analyze / accept routes straight to the doc that implements it. · [dispatch.md](method/dispatch.md:89) — names the gate sequence every write must pass — validate -> audit -> render — which is what makes the prose enforceable by the CLI. · [method.md](method.md:18) — the division of labour with the tools: build agents return structured rows and `coyodex assemble` writes the model; nobody hand-authors the stored file. · [change-impact.md](method/change-impact.md:12) — the three-step Build / Analyze / Accept lifecycle table that defines what each mode writes and what gets committed. · [project-map.template.md](method/templates/project-map.template.md:7) — the template now only documents the generated view's shape (schema v1, ID-based rows), so it is a spec of the rendering, not an authoring form. |  |
| **C2** | Agent skill manifest | S1 | The one file installed into each agent's skills home so that `/coyodex` (and phrases like 'map this repo' or 'change impact') reaches the method. It carries no method content itself: it pins COYODEX_HOME to this clone's absolute path and sends the agent to method/dispatch.md. | [SKILL.md](skill/coyodex/SKILL.md:9) |  | verified | skill/coyodex/SKILL.md | [SKILL.md](skill/coyodex/SKILL.md:9) — the trigger phrases the agent host matches on — 'coyodex', 'project map', 'codebase map', 'change impact', 'accept the map'. · [SKILL.md](skill/coyodex/SKILL.md:28) — the whole payload of the manifest: read `__COYODEX_HOME__/method/dispatch.md` and follow it. · [SKILL.md](skill/coyodex/SKILL.md:18) — separates the two directories the agent must not confuse — the coyodex clone (docs + tools) versus the repo being mapped (only `.coyodex/`). · [Makefile](Makefile:56) — install substitutes `__COYODEX_HOME__` for this repo's absolute path while copying the manifest into each skills home, so the installed copy points straight back here. |  |
| **C40** | Change-impact engine | S8 | Projects an arbitrary git diff onto an existing map: it re-expresses every changed file in the map's pinned line frame (two `-U0` diffs against the pin), resolves each map anchor hosted in that file to a line / symbol / file rung, then applies one pass of typed ripple rules to report every element the change reaches, ranked by strength. | [serve.py](tools/coyodex/viewer/serve.py:655) |  | verified | tools/coyodex/impact_git.py · tools/coyodex/impact_lib.py · tools/coyodex/impact_ripple.py | [impact_git.py](tools/coyodex/impact_git.py:259) — the line-frame translation: a changed file's fate is computed from diff(pin, base) and diff(pin, target), never from a base->target diff directly. · [impact_lib.py](tools/coyodex/impact_lib.py:142) — the fate comparison itself — hunks present identically on both sides cancel; only unmatched hunks mark pinned lines as affected. · [impact_lib.py](tools/coyodex/impact_lib.py:339) — the resolution ladder in action: an anchor whose lines the frame touches resolves at 'line', else at the enclosing symbol, else at file rung. · [impact_ripple.py](tools/coyodex/impact_ripple.py:188) — consolidates several anchor hits on one element and assigns its strength on the lattice (direct line/symbol/file above ripple, territory last). · [impact_ripple.py](tools/coyodex/impact_ripple.py:212) — the structural ripple walk — a hit component climbs to its subsystem and onward to every ancestor group, once, never re-firing. | Map server |
| **C41** | Map backup & provenance | S8 | Records which conversation produced a map (session id + minute-precise build time in a committed provenance.json) and, later, bundles the map files together with the exact transcript(s) of those conversations into a timestamped backup folder. It refuses to move a map out of a repo when no conversation could be found to bundle with it. | [method.md](method.md:1164) |  | verified | tools/map_backup.py | [map_backup.py](tools/map_backup.py:409) — the stamp writes the session entry into `<repo>/.coyodex/provenance.json`, the committed record a later backup reads. · [map_backup.py](tools/map_backup.py:477) — the safety guard: a MOVE with zero bundled conversations is refused before anything is created, because it would delete the map and defeat the feature. · [map_backup.py](tools/map_backup.py:507) — copy-then-delete ordering — the map files are copied into the backup first, so a mid-run failure loses nothing. · [map_backup.py](tools/map_backup.py:512) — the transcripts are copied (never moved) alongside the map, which is what pairs a map with the conversation that built it. · [map_backup.py](tools/map_backup.py:458) — the recovery path for un-stamped maps: scan the agent's transcripts for the session that actually wrote project-map.md. | Map backup script |
| **C45** | Eval runner | S9 | The `coyodex-eval` command and the deterministic run pipeline behind it: reduce a freshly built map to a comparable quality profile (structure counts, validate/audit findings, coverage, granularity), enforce the build-time freeze hash, compare against the blessed baseline, and archive the whole run (map, views, profile, judge report, delta) so it can later be blessed as the new baseline. | [pyproject.toml](pyproject.toml:32) |  | verified | eval/tools/coyodex_eval/cli.py · eval/tools/coyodex_eval/run.py · eval/tools/coyodex_eval/profile.py | [cli.py](eval/tools/coyodex_eval/cli.py:37) — the single command dispatches each subcommand (score / run / hash / claims / judge / protocol / bless / compare) to its implementation, imported lazily. · [run.py](eval/tools/coyodex_eval/run.py:213) — the freeze guard — the run refuses when the map on disk no longer matches the sha256 written at build time, so a post-build edit can never be scored. · [run.py](eval/tools/coyodex_eval/run.py:67) — the run's verdict comes from comparing the fresh profile against the baseline profile and judge report; with no baseline the verdict is BASELINE. · [run.py](eval/tools/coyodex_eval/run.py:164) — archives the run directory — model, generated md view, view bundle, profile.json, judge.json and delta.md — as the historical record a baseline is blessed from. · [profile.py](eval/tools/coyodex_eval/profile.py:129) — the profile is computed through the same validate/audit model pipeline the product itself uses, so a map is never scored through a second, drifting grammar. | coyodex-eval CLI |
| **C46** | Eval scoring | S9 | Turns two maps into a verdict. The judge half aggregates externally produced LLM verdicts — a majority-of-N skeptic vote per high-risk claim plus median rubric scores — into a judge report with a protocol fingerprint; the compare half applies baseline-relative hard gates and drift bands and returns PASS, DRIFT or REGRESSED. | [cli.py](eval/tools/coyodex_eval/cli.py:55) |  | verified | eval/tools/coyodex_eval/judge.py · eval/tools/coyodex_eval/compare.py | [compare.py](eval/tools/coyodex_eval/compare.py:325) — the verdict precedence that the whole eval reports on — any failed hard gate is REGRESSED, any breached band is DRIFT, otherwise PASS. · [compare.py](eval/tools/coyodex_eval/compare.py:238) — the gates are relative, not absolute: a real baseline map carries validate problems, so the rule is 'no new problems'. · [compare.py](eval/tools/coyodex_eval/compare.py:255) — the security-specific hard gate — the number of auth surfaces must never drop between baseline and candidate. · [judge.py](eval/tools/coyodex_eval/judge.py:215) — the grounding math: a claim's verdict is the majority of usable skeptic votes, so a single dissenter cannot flip it and a tie is refuted. · [judge.py](eval/tools/coyodex_eval/judge.py:250) — anchor drift is measured separately from truth — a confirmed claim whose stored `where` is far from the line the skeptics read counts as drift, not as a refutation. | coyodex-eval CLI |
| **C20** | Map views builder | S7 | Turns the loaded map model into its two generated views: the committed markdown file (canonical section order, sections and columns emitted only when the map has that content, bare anchors re-linked so the text view stays clickable) and the graph payload the viewer consumes (nodes carrying their owned files, entry points, stores and lifecycles, deduped edges with their backing fields resolved, and the store-centric Data view). The `coyodex render` command drives the markdown half, writes it next to the map, and registers the project with the local server. | [render.py](tools/coyodex/viewer/render.py:22) |  | verified | tools/coyodex/views.py · tools/coyodex/viewer/render.py | [views.py](tools/coyodex/views.py:259) — appends one markdown section in the template's fixed order — called only for a non-empty model list, so a small map omits the section entirely · [views.py](tools/coyodex/views.py:736) — registers a component as a graph node carrying its owned file list, its grouped entry points and its lifecycle lines · [views.py](tools/coyodex/views.py:849) — rolls a subsystem's or subdomain's files up from its members, so drilling a group's code viewer spans everything it contains · [render.py](tools/coyodex/viewer/render.py:53) — writes the generated markdown view to the requested .md output · [render.py](tools/coyodex/viewer/render.py:56) — registers the rendered project's folder with the serve recents, so the map shows up as a card without a restart | coyodex CLI, Map server, coyodex-eval CLI |
| **C24** | Map server | S13 | Serves every remembered coyodex project from one local loopback-only HTTP server: the shared viewer shell and static assets, each map's view bundle, file tree and code-symbol list, the change-impact endpoints, and file contents read from git at the map's pinned commit (with a scoped `at=` escape for another commit or a guarded working-tree read). It also serves the landing page for adding, reordering and forgetting project folders, and re-reads a map whose file changed on disk so an edit appears on the next refresh. | [serve.py](tools/coyodex/viewer/serve.py:763) |  | verified | tools/coyodex/viewer/serve.py | [serve.py](tools/coyodex/viewer/serve.py:734) — binds the threading HTTP server to 127.0.0.1 only · [serve.py](tools/coyodex/viewer/serve.py:513) — refuses any request whose Host header is not loopback — the DNS-rebinding guard that stops a remote page reading local source · [serve.py](tools/coyodex/viewer/serve.py:527) — checks the map file's mtime on every project request and drops the cached tree/view/symbols when it changed · [serve.py](tools/coyodex/viewer/serve.py:650) — reads a file's bytes out of git at the requested commit — the pinned-snapshot read behind the code viewer · [serve.py](tools/coyodex/viewer/serve.py:605) — serves the one generic viewer shell for every project; the per-map data arrives separately from the project's own API | Map server |
| **C25** | File browser, recents & diff rows | S13 | Builds the viewer's file-browser tree — repo files nested into folders, each row tagged with how the map covers it and with which element a click should select (the file's own element, its owning component, or the nearest mapped ancestor folder) — keeps the remembered-project list in `~/.coyodex/serve-recents.json` so builds and the running server merge instead of clobbering each other, and parses `git diff` output into the numbered add/delete/context rows the code viewer paints. | [serve.py](tools/coyodex/viewer/serve.py:384) |  | verified | tools/coyodex/viewer/filetree.py · tools/coyodex/viewer/recents.py · tools/coyodex/viewer/diffmap.py | [filetree.py](tools/coyodex/viewer/filetree.py:166) — sets a row's click target: the element defined or owned at that path, else the nearest ancestor folder an element anchors · [filetree.py](tools/coyodex/viewer/filetree.py:177) — rolls a folder up to partial coverage when nothing anchors it but a descendant is mapped — what makes the browser double as a coverage view · [filetree.py](tools/coyodex/viewer/filetree.py:127) — records a component as the owner of each file it lists, so clicking any owned file selects that component · [recents.py](tools/coyodex/viewer/recents.py:66) — puts the opened folder at the front of the recents list after dropping duplicate spellings of the same directory · [diffmap.py](tools/coyodex/viewer/diffmap.py:51) — turns one added diff line into a display row carrying its new-side line number | Map server, coyodex CLI |
| **C10** | Map validator | S6 | Runs the model-only semantic rulebook over a loaded map: every element defined once, every cross-reference resolving, and the shape rules for flows, entry points, deps, stores, state machines, messaging channels, domain cards and anchor formats. Blocking breakages come back as problems; the judgement calls (balance, completeness, cadence, persistence coverage, isolated components) come back as non-blocking advisory warnings. |  |  | verified | tools/coyodex/validate_model.py | [validate_model.py](tools/coyodex/validate_model.py:143) — reports every id defined more than once — the duplicate-definition block · [validate_model.py](tools/coyodex/validate_model.py:271) — the reference check: referenced ids minus defined ids, minus the additivity suppressions, is the dangling-reference list · [validate_model.py](tools/coyodex/validate_model.py:306) — per-step flow rulebook — a step missing an endpoint is a blocking problem · [validate_model.py](tools/coyodex/validate_model.py:1684) — a backbone edge with neither a `where` call site nor `no_call_site` blocks · [validate_model.py](tools/coyodex/validate_model.py:1846) — anchor-format gate: every source-location field must be a bare `path:line` · [validate_model.py](tools/coyodex/validate_model.py:1158) — example advisory — components appearing in no edge and no channel are collected and warned about, never blocked | coyodex CLI, coyodex-eval CLI |
| **C14** | Source & coverage grounding checks | S6 | The repo-reading half of validation, opt-in behind `--check-sources` / `--check-coverage`: it opens the cited files to prove each anchor really resolves, that a call-site anchor points at an acting statement rather than a def header, import or comment, and that entity and state-machine names actually appear in the file they cite. For coverage it collects the repo paths the map references and re-parses the entities' source directories to spot named types with no entity card. |  |  | verified | tools/coyodex/validate_model.py | [validate_model.py](tools/coyodex/validate_model.py:2054) — existence check: each anchor's path must be a real file (or directory) under one of the source roots · [validate_model.py](tools/coyodex/validate_model.py:2119) — reads the anchored line and asks whether it can be the acting statement (advisory drift check) · [validate_model.py](tools/coyodex/validate_model.py:2148) — state names that do not appear in the cited source file are reported as invented or prose-read · [validate_model.py](tools/coyodex/validate_model.py:2175) — anti-synthesized-entity gate: no token of the entity name found in its SOURCE file is a blocking problem · [validate_model.py](tools/coyodex/validate_model.py:2267) — re-measures the domain model — Python classes in the entities' source dirs with no matching entity card · [validate_model.py](tools/coyodex/validate_model.py:2212) — keeps only the repo-relative paths that exist, the reference set the coverage walk compares the tree against | coyodex CLI, coyodex-eval CLI |
| **C15** | Validation run & CLI | S6 | Drives one validation pass — calls every check in a fixed order, folds in the hierarchy, balance and tree-coverage checks from the sibling modules, and flags a committed `project-map.md` that differs from the view regenerated out of the model. The `coyodex validate` command line parses the flags, loads the map, prints the inventory, the advisory warnings and the blocking problems, and exits non-zero on any problem; `--emit-unclaimed` instead prints a ready-to-paste adjudication block. | [validate_model.py](tools/coyodex/validate_model.py:2496) |  | verified | tools/coyodex/validate_model.py | [validate_model.py](tools/coyodex/validate_model.py:2308) — the orchestration: each check's findings are appended to the problems or warnings list in turn · [validate_model.py](tools/coyodex/validate_model.py:2368) — the `--check-sources` branch wires the repo-reading anchor existence check in as BLOCKING · [validate_model.py](tools/coyodex/validate_model.py:2386) — the `--check-coverage` branch re-walks the tree and adds the compression/coverage advisories · [validate_model.py](tools/coyodex/validate_model.py:2483) — compares the committed markdown view with the regenerated one — a stale generated file is surfaced · [validate_model.py](tools/coyodex/validate_model.py:2561) — the gate itself: any blocking problem makes the command exit non-zero | coyodex CLI, coyodex-eval CLI |
| **C16** | Advisory adjudication readers | S6 | Reads the operator's durable decisions out of the map's own `extras` headings so a justified advisory stays quiet on every later run — accepted flow duplications, unclaimed surfaces, persistence and Happy-Path-coverage records, coarse-fold coverage directories, and the per-kind entry-point completeness contract. Each record is parsed only from a line-leading id or path followed by a separator, so prose that merely mentions an id mid-sentence can never silence a check. |  |  | verified | tools/coyodex/validate_model.py | [validate_model.py](tools/coyodex/validate_model.py:422) — collects the flow pairs adjudicated under an 'Accepted duplications' heading · [validate_model.py](tools/coyodex/validate_model.py:559) — records an id only when the line STARTS with it and a separator follows — the strictness that keeps prose from exempting elements · [validate_model.py](tools/coyodex/validate_model.py:581) — collects the repo-relative directories recorded under 'Coverage exceptions' · [validate_model.py](tools/coyodex/validate_model.py:588) — boundary-aware prefix match, so a recorded dir silences its subtree and not a same-prefixed sibling · [validate_model.py](tools/coyodex/validate_model.py:873) — reads the per-entry-point-kind completeness contract (complete/sampled/partial), folded to the canonical kind spelling | coyodex CLI, coyodex-eval CLI |
| **C21** | Viewer graph builder | S11 | Defines the graph shape every viewer diagram reads — nodes (with their files, entry points, deployment hosts, store and lifecycle facts), edges, flows, tests and the store-centric Data view — and injects a default subsystem when a map groups nothing, so a component altitude always exists. It also parses a change-impact report into per-element change labels and new edges for the viewer's diff overlay. | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2775) |  | verified | tools/coyodex/viewer/build_graph.py | [build_graph.py](tools/coyodex/viewer/build_graph.py:219) — injects the synthetic default subsystem and reparents every component under it when the map declares none · [build_graph.py](tools/coyodex/viewer/build_graph.py:254) — classifies one change-impact report row into an added/modified/deleted element entry · [build_graph.py](tools/coyodex/viewer/build_graph.py:269) — collects a report's from\|verb\|to row as a new edge the diff overlay draws · [build_graph.py](tools/coyodex/viewer/build_graph.py:192) — splits the report's markdown tables with the shared grammar helpers, so parser and validator cannot disagree on table boundaries | Map server |
| **C22** | View bundle assembler | S11 | Assembles the single JSON payload the browser app fetches per map: every pre-rendered diagram source, the per-arrow crossing lists, the merged graph with diff annotations, the colour table, the header meta line (repo, commit, build time, schema) and the source-link config (repo root and GitHub URL read from git). Each view is included only when the map actually has that content. | [serve.py](tools/coyodex/viewer/serve.py:399) |  | verified | tools/coyodex/viewer/gen_viewer.py | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2813) — builds the ViewBundle, gating each diagram on has_grouping / has_domain / has_subdomains / has_deployment / has_hp · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2801) — assembles the header meta line from the repo name plus commit/date or the diff summary · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2653) — annotates the merged graph with each element's change status so the panel and badges can show it · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:1145) — marks an unchanged element downstream of a changed one as rippled for the diff badges · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2872) — the debug entry point that dumps the same bundle to a JSON file for two-stage inspection | Map server, coyodex-eval CLI |
| **C26** | Context & subsystem diagram generator | S11 | Draws the structural altitudes: the Context view (the system, its actors and the external systems it uses, grouped by purpose and with in-process libraries folded into one drillable box), the Subsystems overview with count-labelled crossings, each subsystem's neighbourhood card, and the two-subsystem edge card. It also produces the explanation payloads behind the Context arrows and the crossing lists behind every subsystem arrow. | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2778) |  | verified | tools/coyodex/viewer/gen_viewer.py | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:1342) — emits the Context view's collapsed Libraries box holding every in-process dependency · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:1219) — wraps each purpose bucket of dependencies in its own labelled cluster, shared by Context and the Libraries drill · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:877) — emits the Subsystems overview's inter-subsystem arrow, labelled by the number of component edges it bundles · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:1078) — emits a subsystem card's bridge arrow from a component to the subdomain its data touches · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:932) — lists, per subsystem-pair arrow, the concrete component-to-component crossings the panel shows | Map server |
| **C27** | Domain diagram generator | S11 | Draws the domain-model altitudes as class diagrams: the flat Entities view (each entity a box with its fields, key markers, store, retention and lifecycle), the Subdomains overview, each subdomain's neighbourhood card, the two-subdomain edge card, and the bridge card pairing a subsystem with a subdomain. It also draws the reverse link showing which subsystems read or write each entity. | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2821) |  | verified | tools/coyodex/viewer/gen_viewer.py | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:468) — emits one class box per entity, with its fields and its store/retention/lifecycle lines, for the flat Entities view · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:581) — emits the Subdomains overview arrow, labelled by how many entity relations cross that pair · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:744) — emits a subdomain card's crossing arrow to a collapsed neighbour subdomain box · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:678) — emits the reverse bridge arrow from a subsystem box into an entity, counted by the underlying component-to-entity edges · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:841) — emits the bridge card's concrete component-to-entity link so a click resolves to the real edge | Map server |
| **C28** | Deployment & messaging diagram generator | S11 | Draws the runtime picture: the Deployment overview (one box per process, product-area containers on big maps, a shared-infrastructure lane banded by role, and process-to-process arrows derived from async channels and cross-process calls), each process's own card, each container's card, and a per-broker channel diagram for the Data tab. It also injects the process boxes into the graph and lists the calls and channels behind every drawn arrow. | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2828) |  | verified | tools/coyodex/viewer/gen_viewer.py | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2110) — emits the one process-to-process arrow per pair, labelled by the channels and calls that cross it · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2116) — emits a real arrow from each process to the infrastructure it shares with another process · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2224) — emits a process card's arrow to each subsystem or component that unit runs · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:1499) — injects a view-only process node per drawn deployment unit so its box binds and shows its operational facts · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2701) — stores the per-broker publisher-to-channel-to-consumer diagram keyed by broker, for the Data tab | Map server |
| **C29** | Behavioural flow generator | S11 | Draws the behavioural overlay as sequence diagrams: the Happy Path as an ordered walk of numbered messages from each step's actor to the system, and each use case's flow as messages between the actor and the components, dependencies and entities it touches, with shared sub-flows expanded inline in a named block. It emits the matching numbered narrative and actor lists the side panel shows, kept on the same index as the drawn messages. | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2837) |  | verified | tools/coyodex/viewer/gen_viewer.py | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2412) — emits one numbered Happy Path message per step, from the step's actor to the system lifeline · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2553) — emits one numbered flow message per step between the two elements it connects · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2550) — wraps an expanded sub-flow run in a tinted block named by a note, without disturbing the message numbering · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2581) — builds the side panel's narrative row for a step, carrying its own action text, note and call site · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2503) — replaces a sub-flow reference step by the referenced sub-flow's own steps, the single expansion all three per-flow views consume | Map server |

---

## T2 — External dependencies

| ID | Name | Kind | Bucket | Type | Used for | Where configured | Conf. | Deployment-linked | Package | Alternative | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **D1** | git | datastore | Data & storage | version-control system, driven as a local CLI binary via subprocess | Reads the mapped repo's files at the map's pinned commit, so the viewer always shows the code the map describes; also resolves refs, lists tracked files, produces diffs for the impact explorer, and supplies churn/history for the pre-index. There is no database in this product — git IS the content store the viewer reads from. | [serve.py](tools/coyodex/viewer/serve.py:180) | verified |  |  | Every git helper degrades instead of failing: a missing binary or a non-repo folder returns an empty result (the pre-index falls back to an os.walk of the tree; the viewer's GitHub target is simply not offered). | [serve.py](tools/coyodex/viewer/serve.py:180) — The single read-only git call site the whole server funnels through — `subprocess.run(["git", "-C", repo_root, *args])`, no shell, args passed as a list. · [serve.py](tools/coyodex/viewer/serve.py:223) — `git show <commit>:<path>` is how the code viewer gets file contents — pinned to the map's commit, so local edits never leak into the view. · [preindex_lib.py](tools/coyodex/preindex_lib.py:172) — The pre-index prefers `git ls-files -z` to enumerate authored files (honors .gitignore) and falls back to an os.walk when the folder is not a git repo. |
| **D2** | Local filesystem | datastore | Data & storage | the user's disk — plain JSON/markdown files, no database | Stores every artifact this product owns: the committed map under each repo's `.coyodex/`, the build fragments, the pre-index, the server's recents list under the user's home, and the map backups. The product has no database and no cloud storage. | [recents.py](tools/coyodex/viewer/recents.py:18) | verified |  |  |  | [recents.py](tools/coyodex/viewer/recents.py:44) — The recents store writes `~/.coyodex/serve-recents.json` itself — the only state coyodex keeps outside a mapped repo. · [serve.py](tools/coyodex/viewer/serve.py:117) — A served project is just a folder holding `.coyodex/project-map.json`, read straight off disk. · [map_backup.py](tools/map_backup.py:40) — Backups are written to `<coyodex-home>/map-backups/<project>-<build-time>/` on the same local disk. |
| **D3** | Claude Code transcript store | datastore | Data & storage | another tool's live on-disk session log (`~/.claude/projects/*/<session>.jsonl`) | Supplies the conversation transcript that produced a map, so a backup bundles the map together with the exact session that built it. Read-only and always copied, never moved, because the store belongs to the running agent. | [map_backup.py](tools/map_backup.py:41) | verified |  |  | When a map carries no stamped session, `--search` scans the transcripts for a Write/Edit of a project-map file to recover the session ids; if no transcript is on disk the backup still bundles the map files alone. | [map_backup.py](tools/map_backup.py:217) — Locates a session's transcript by globbing `*/<session_id>.jsonl` under `~/.claude/projects` — a direct read of another product's store. · [map_backup.py](tools/map_backup.py:265) — Matches the repo to its transcript directory by comparing the `cwd` field Claude Code stamps into each transcript entry. |
| **D4** | jsDelivr CDN | platform | Frontend asset delivery | public CDN host (cdn.jsdelivr.net) the viewer page loads scripts from | Delivers the two browser libraries the viewer page needs at load time (the diagram renderer and the pan/zoom control). Every tag is version-pinned with Subresource Integrity, so a tampered file is rejected by the browser; the server itself never talks to this host. | [viewer.html](tools/coyodex/viewer/viewer.html:16) | verified |  |  | None — the viewer has no local copy of these bundles, so with no network the diagram surface does not render. | [viewer.html](tools/coyodex/viewer/viewer.html:16) — The svg-pan-zoom script tag points at cdn.jsdelivr.net with an `integrity` hash and `crossorigin=anonymous`. · [viewer.html](tools/coyodex/viewer/viewer.html:19) — The mermaid UMD bundle loads from the same host, deliberately the UMD build so SRI covers the whole library. |
| **D5** | cdnjs | platform | Frontend asset delivery | public CDN host (cdnjs.cloudflare.com) the viewer page lazy-loads from | Delivers the syntax highlighter (script plus stylesheet) the first time the user opens the in-app code viewer. Loaded lazily rather than at boot, version-pinned and SRI-checked like the head tags. | [viewer.js](tools/coyodex/viewer/viewer.js:5390) | verified |  |  | The code viewer still shows the file as plain text if the highlighter never arrives — highlighting is an enhancement, not a requirement. | [viewer.js](tools/coyodex/viewer/viewer.js:5390) — The highlight.js script URL is built against cdnjs.cloudflare.com with a pinned version constant. · [viewer.js](tools/coyodex/viewer/viewer.js:5404) — The injected `<script>` carries `integrity` and `crossOrigin` before it is appended — the lazy load is SRI-checked too. |
| **D6** | Web browser | platform | Infrastructure & runtime | the user's browser — the runtime that hosts the whole viewer UI | Runs the viewer application: fetches each map's bundle from the local server, renders the diagrams, and persists per-user viewer settings in localStorage. The server can also ask the OS to open it on start. | [serve.py](tools/coyodex/viewer/serve.py:740) | verified |  |  |  | [serve.py](tools/coyodex/viewer/serve.py:740) — `webbrowser.open(url)` launches the user's default browser at the landing page when `--open` is passed. · [viewer.js](tools/coyodex/viewer/viewer.js:5919) — Viewer settings (editor target, source root, GitHub URL, panel sizes) live in the browser's localStorage — no server-side settings store exists. |
| **D7** | GitHub | service | Source hand-off | hosted git service — a blob-URL hand-off target for source links | Opens a mapped element's source in a browser as a portable fallback when no local editor is configured. The repo URL is derived at build time from the `origin` remote, and the blob link is pinned to the map's commit so the line numbers still match. | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:77) | verified |  |  | Offered only when `origin` is a github.com remote AND the map records a commit; otherwise the target is not even listed and the user picks a local editor instead. The user can override the URL in Settings. | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:77) — Build time: `git remote get-url origin` is parsed into `https://github.com/<owner>/<repo>` and baked into the view bundle. · [viewer.js](tools/coyodex/viewer/viewer.js:6024) — Runtime: the blob URL is opened in a new tab with `noopener` — the only outbound navigation the viewer performs. |
| **D8** | Local code editor | service | Source hand-off | desktop application invoked through an OS URL scheme (vscode://, cursor://, idea://, zed://, …) | Opens a mapped element's file at its exact line in the user's own editor. The hand-off is pure browser: a hidden anchor fires the scheme URI and the OS scheme handler does the opening — no server involvement. | [viewer.js](tools/coyodex/viewer/viewer.js:5901) | verified |  |  | Ten editors ship as presets plus a custom URI template; if nothing usable is configured the viewer falls back to the GitHub blob link, and failing that reopens Settings. | [viewer.js](tools/coyodex/viewer/viewer.js:5901) — The target table maps each editor to its URI template with `{abspath}`/`{line}`/`{col}` placeholders. · [viewer.js](tools/coyodex/viewer/viewer.js:5976) — Only a URI whose scheme is in the editor allowlist is ever returned for an anchor — the enforcement point of the hand-off. |
| **D9** | CPython | platform | Infrastructure & runtime | language runtime, 3.10 or newer, in a repo-local virtualenv | Runs the CLI, the pre-index, and the map server. The core gate is deliberately stdlib-only, so the interpreter itself is effectively the entire runtime requirement. | [pyproject.toml](pyproject.toml:9) | verified | yes | python >=3.10 (pyproject.toml [project].requires-python) |  | [pyproject.toml](pyproject.toml:9) — `requires-python = ">=3.10"` is the declared floor. · [Makefile](Makefile:29) — The venv target fails fast with a readable message when the discovered python3 is older than 3.10. |
| **D10** | pip | platform | Developer tooling | Python package installer, run as its own process from the Makefile | Installs the CLI editable into the repo-local virtualenv, with the optional extras. Deliberately targets the repo's own `.venv` so nothing is installed into the user's system Python. | [Makefile](Makefile:38) | verified | yes |  |  | [Makefile](Makefile:38) — `$(PY) -m pip install -e '$(REPO)[preindex]'` — the install path, always against the repo-local venv interpreter. · [Makefile](Makefile:43) — The contributor target adds the `dev` extra (pytest + pyright) through the same installer. |
| **D11** | setuptools | library | Developer tooling | Python build backend | Builds the distribution: resolves the src-layout (package root `tools/`, plus the separate eval package), declares the two console scripts, reads the version out of the VERSION file, and wheels the viewer's html/css/js as package data. | [pyproject.toml](pyproject.toml:2) | verified | yes | setuptools >=64 (pyproject.toml build-system.requires) |  | [pyproject.toml](pyproject.toml:2) — `requires = ["setuptools>=64"]` with `build-backend = "setuptools.build_meta"`. · [pyproject.toml](pyproject.toml:43) — The non-obvious package-dir mapping (two source roots) that only this backend resolves. |
| **D12** | tree-sitter | library | Source parsing | Python parsing library — an OPTIONAL extra, imported lazily | Extracts symbols and imports from non-Python source files during the pre-index. It is the one deliberate exception to the stdlib-only rule and is firewalled: only the `preindex` command may import it, so validate/render/serve stay dependency-free. | [pyproject.toml](pyproject.toml:19) | verified |  | tree-sitter >=0.21 (pyproject.toml [project.optional-dependencies].preindex) | Python files always go through the stdlib `ast`; when the extra is absent the pre-index still runs and simply reports its non-Python symbol coverage as unavailable rather than failing. | [pyproject.toml](pyproject.toml:19) — Declared only inside the `preindex` optional extra — the core dependency list is empty on purpose. · [cli.py](tools/coyodex/cli.py:80) — The dependency firewall: the import happens inside the `preindex` branch, so no other command can pull it in. · [preindex_lib.py](tools/coyodex/preindex_lib.py:329) — The actual lazy import of `tree_sitter.Parser`, built the documented way for compatibility across 0.21-0.25. |
| **D13** | tree-sitter-language-pack | library | Source parsing | Python package bundling the tree-sitter grammars — same optional extra | Supplies the per-language grammars the pre-index needs (javascript, typescript, go, java, and the rest). Probed behind a try/except so a missing or broken pack degrades the pre-index instead of breaking it. | [pyproject.toml](pyproject.toml:20) | verified |  | tree-sitter-language-pack >=0.2 (pyproject.toml [project.optional-dependencies].preindex) | A grammar that will not load raises a LookupError the caller treats as 'no symbols for this language' — the file is still counted, just not parsed. | [pyproject.toml](pyproject.toml:20) — Declared alongside tree-sitter in the `preindex` extra. · [preindex_lib.py](tools/coyodex/preindex_lib.py:314) — The availability probe imports the pack inside a try/except and reports a boolean, never raising. |
| **D14** | pytest | library | Developer tooling | Python test runner — the `dev` optional extra | Runs the tool test suite (the repo's own tests plus the eval's), installed into the repo-local venv by the contributor setup target so the gates run against the editable package. | [pyproject.toml](pyproject.toml:25) | verified | yes | pytest >=8 (pyproject.toml [project.optional-dependencies].dev) |  | [pyproject.toml](pyproject.toml:25) — Declared in the `dev` extra, kept out of the runtime dependency set. · [pyproject.toml](pyproject.toml:35) — `testpaths = ["tests", "eval/tests"]` — the two suites the runner collects. |
| **D15** | pyright | library | Developer tooling | Python static type checker — the `dev` optional extra | Type-checks the tools package as a contributor gate. Its config only has to add the two source roots, because the package directory name matches the import name. | [pyproject.toml](pyproject.toml:26) | verified | yes | pyright >=1.1 (pyproject.toml [project.optional-dependencies].dev) |  | [pyproject.toml](pyproject.toml:26) — Declared in the `dev` extra. · [pyrightconfig.json](pyrightconfig.json:2) — `extraPaths` points at `tools` and `eval/tools`, the two src-layout roots. |
| **D16** | mermaid | library | Diagram rendering | browser JS library loaded from a CDN with SRI | Renders every diagram in the viewer from the pre-built diagram sources in each map's view bundle — the Context, container, subsystem, domain, deployment, and flow views are all mermaid output. | [viewer.html](tools/coyodex/viewer/viewer.html:19) | verified |  | mermaid 11.15.0 (viewer.html script tag, SRI-pinned) | A parse error or a missing baked diagram degrades to an on-page message rather than a blank stage. | [viewer.html](tools/coyodex/viewer/viewer.html:19) — The pinned UMD bundle plus its integrity hash — the UMD build is chosen specifically so SRI covers the whole library. · [viewer.js](tools/coyodex/viewer/viewer.js:131) — Initialised with `securityLevel: 'loose'` so HTML labels work; the label text is sanitized on the Python side before it ever reaches here. |
| **D17** | svg-pan-zoom | library | Diagram rendering | browser JS library loaded from a CDN with SRI | Adds pan and zoom to the rendered diagram SVG, so a large map stays navigable at any altitude. | [viewer.html](tools/coyodex/viewer/viewer.html:16) | verified |  | svg-pan-zoom 3.6.1 (viewer.html script tag, SRI-pinned) |  | [viewer.html](tools/coyodex/viewer/viewer.html:16) — The pinned script tag with its integrity hash, loaded in the page head before the viewer module. |
| **D18** | highlight.js | library | Frontend / UI | browser JS library lazy-loaded from a CDN with SRI | Syntax-highlights source files in the in-app code viewer. Loaded on first use rather than at boot, with a per-extension language map choosing the grammar. | [viewer.js](tools/coyodex/viewer/viewer.js:5390) | verified |  | highlight.js 11.9.0 (viewer.js HLJS_VER constant, script + stylesheet both SRI-pinned) | An unknown file extension, or a failed load, leaves the file rendered as unhighlighted plain text. | [viewer.js](tools/coyodex/viewer/viewer.js:5389) — The single pinned version constant both the script and stylesheet URLs are built from. · [viewer.js](tools/coyodex/viewer/viewer.js:5401) — The stylesheet is injected with its own integrity hash — the theme is fetched from the CDN too, not bundled. |

---

## T3 — How to run / build / test

| Action | Command | Source |
|---|---|---|
| Install the coyodex skill for all agents (also builds the venv and CLI) | make install | Makefile:52 |
| Install the coyodex-eval skill (opt-in, separate from install) | make install-eval | Makefile:64 |
| Uninstall the coyodex skill from every skills home | make uninstall | Makefile:72 |
| Uninstall the coyodex-eval skill | make uninstall-eval | Makefile:78 |
| Create the repo-local virtualenv (checks Python 3.10+) | make venv | Makefile:26 |
| Install the CLI editable into the venv with the pre-index extra | make deps | Makefile:37 |
| Contributor dev setup — deps plus pytest and pyright in the venv | make dev | Makefile:42 |
| Start the local map server and open the landing page | make start   (PORT=8765 by default; wraps .venv/bin/coyodex serve --port $PORT --open) | Makefile:87 |
| Remove the repo-local virtualenv | make clean | Makefile:91 |
| Run the tests | .venv/bin/pytest            (testpaths cover tests/ and eval/tests/; .venv/bin/pytest tests runs the tool tests only) | pyproject.toml:35 |
| Run the type checker | .venv/bin/pyright tools | pyrightconfig.json:2 |
| Run the coyodex CLI directly | .venv/bin/coyodex <subcommand>   (validate, audit, render, assemble, preindex, serve, lint-fragment, ...) | pyproject.toml:30 |
| Run the method-quality eval CLI directly | .venv/bin/coyodex-eval <subcommand>   (score, run, hash, claims, judge, protocol, bless, compare) | pyproject.toml:32 |
| Stamp a built map with the conversation that produced it | .venv/bin/python tools/map_backup.py stamp <repo> --mode build --built-at '<YYYY-MM-DD HH:MM>' | tools/map_backup.py:568 |
| Back up a map together with its build transcript | .venv/bin/python tools/map_backup.py backup <repo> [--keep] [--search] [--dry-run] | tools/map_backup.py:594 |

---

## T4 — Entry points

| Kind | Trigger | Code entity | Component | Cadence |
|---|---|---|---|---|
| cli | a developer or coding agent runs `coyodex preindex` to build the structural pre-index next to the map | [cli.py](tools/coyodex/cli.py:79) | C30 |  |
| cli | a developer or coding agent runs `coyodex validate` to check a map is well-formed | [cli.py](tools/coyodex/cli.py:82) | C30 |  |
| cli | a developer or coding agent runs `coyodex audit` for the adversarial pass over a built map | [cli.py](tools/coyodex/cli.py:85) | C30 |  |
| cli | a developer or coding agent runs `coyodex render` to write the map's committed markdown view | [cli.py](tools/coyodex/cli.py:88) | C30 |  |
| cli | a developer runs `coyodex serve` to start the local map server | [cli.py](tools/coyodex/cli.py:91) | C30 |  |
| cli | a coding agent runs `coyodex assemble` to merge the build agents' fragments into the canonical map | [cli.py](tools/coyodex/cli.py:94) | C30 |  |
| cli | a developer or coding agent runs `coyodex dump` to read the model back as JSON, whole or sliced | [cli.py](tools/coyodex/cli.py:97) | C30 |  |
| cli | a developer or coding agent runs `coyodex balance` to report per-diagram fan-out and split proposals | [cli.py](tools/coyodex/cli.py:100) | C30 |  |
| cli | a coding agent runs `coyodex reconcile` to expand path rules into an explicit reconcile assignment file | [cli.py](tools/coyodex/cli.py:103) | C30 |  |
| cli | a build agent runs `coyodex lint-fragment` to self-check one fragment before returning it | [cli.py](tools/coyodex/cli.py:106) | C30 |  |
| cli | a coding agent runs `coyodex anchor-drift` to flag claims whose stored line drifted from the line the skeptics found | [cli.py](tools/coyodex/cli.py:109) | C30 |  |
| cli | a coding agent runs `coyodex fix`, which hands the rest of the command line to the fix module's own verb dispatch | [cli.py](tools/coyodex/cli.py:112) | C30 |  |
| cli | a coding agent runs `coyodex fix apply-drift` to move a claim's stored line to the line the drift check found | [fix.py](tools/coyodex/fix.py:281) | C8 |  |
| cli | a coding agent runs `coyodex fix drop-edge` to delete or repoint one relation in the map | [fix.py](tools/coyodex/fix.py:281) | C8 |  |
| cli | a coding agent runs `coyodex fix dedup-relation` to drop duplicated or reciprocal entity relations | [fix.py](tools/coyodex/fix.py:281) | C8 |  |
| cli | a method maintainer runs `coyodex-eval score` to emit a map's deterministic quality profile | [cli.py](eval/tools/coyodex_eval/cli.py:32) | C45 |  |
| cli | a method maintainer runs `coyodex-eval run` to profile a fresh map, compare it against its baseline, and archive the run | [cli.py](eval/tools/coyodex_eval/cli.py:35) | C45 |  |
| cli | a method maintainer runs `coyodex-eval hash` to print a map artifact's freeze hash | [cli.py](eval/tools/coyodex_eval/cli.py:38) | C45 |  |
| cli | a method maintainer runs `coyodex-eval claims` to print the audit worklist the judge scores | [cli.py](eval/tools/coyodex_eval/cli.py:41) | C45 |  |
| cli | a method maintainer runs `coyodex-eval judge` to aggregate the orchestrated judge verdicts into one file | [cli.py](eval/tools/coyodex_eval/cli.py:44) | C45 |  |
| cli | a method maintainer runs `coyodex-eval protocol` to print or guard the judge-protocol fingerprint | [cli.py](eval/tools/coyodex_eval/cli.py:47) | C45 |  |
| cli | a method maintainer runs `coyodex-eval bless` to promote a run to the baseline | [cli.py](eval/tools/coyodex_eval/cli.py:50) | C45 |  |
| cli | a method maintainer runs `coyodex-eval compare` to apply the relative regression gates between a candidate and a baseline | [cli.py](eval/tools/coyodex_eval/cli.py:53) | C45 |  |
| cli | installing the package puts the `coyodex` command on the PATH, pointing at the CLI dispatcher | [pyproject.toml](pyproject.toml:30) | C30 |  |
| cli | installing the package puts the `coyodex-eval` command on the PATH, pointing at the eval dispatcher | [pyproject.toml](pyproject.toml:32) | C45 |  |
| cli | a coding agent runs `python tools/map_backup.py stamp <repo>` to record the session id and build time into the map's provenance | [map_backup.py](tools/map_backup.py:568) | C41 |  |
| cli | a coding agent runs `python tools/map_backup.py backup <repo>` to bundle the map files plus the build conversation into map-backups/ | [map_backup.py](tools/map_backup.py:594) | C41 |  |
| cli | a developer runs `python -m coyodex.json_schema` to print the map's JSON schema (no `coyodex` subcommand exposes it) | [json_schema.py](tools/coyodex/json_schema.py:291) | C5 |  |
| cli | a developer runs `python -m coyodex.viewer.gen_viewer` to dump the view bundle for a graph file — the frontend's data, for debugging | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2877) | C22 |  |
| agent-skill | a coding agent picks up the `/coyodex` skill (or matches its triggers, e.g. "map this repo") and starts reading the method from the manifest | [SKILL.md](skill/coyodex/SKILL.md:2) | C2 |  |
| agent-skill | a coding agent picks up the `/coyodex-eval` skill (or matches "eval this map") and starts the method-quality regression run | [SKILL.md](eval/SKILL.md:2) | C45 |  |
| http-route | a browser requests the server root and gets the landing page listing the recent projects | [serve.py](tools/coyodex/viewer/serve.py:518) | C24 |  |
| http-route | the landing page asks `GET /api/recents` for the recent project folders, re-reading the recents file so a just-built map appears without a restart | [serve.py](tools/coyodex/viewer/serve.py:548) | C24 |  |
| http-route | the landing page's folder picker asks `GET /api/browse?path=` for a directory's subfolders and which of them hold a map | [serve.py](tools/coyodex/viewer/serve.py:556) | C24 |  |
| http-route | the browser requests `GET /static/viewer.js` or `/static/viewer.css` — the shared frontend assets, served from an exact-name whitelist | [serve.py](tools/coyodex/viewer/serve.py:521) | C24 |  |
| http-route | a reader opens a project's map URL `/p/<project>/` and the server returns the generic viewer shell | [serve.py](tools/coyodex/viewer/serve.py:605) | C24 |  |
| http-route | the browser app probes `GET /p/<project>/api/health` at boot to confirm the server is reachable before revealing the file and code panes | [serve.py](tools/coyodex/viewer/serve.py:609) | C24 |  |
| http-route | the browser requests a project's whole view bundle — the graph plus every pre-rendered diagram — at `GET /p/<project>/api/view` | [serve.py](tools/coyodex/viewer/serve.py:611) | C24 |  |
| http-route | the file browser requests `GET /p/<project>/api/tree` for the repo's file tree at the map's commit, overlaid with map coverage | [serve.py](tools/coyodex/viewer/serve.py:620) | C24 |  |
| http-route | the search box lazily requests `GET /p/<project>/api/symbols` for the code symbols taken from the pre-index | [serve.py](tools/coyodex/viewer/serve.py:625) | C24 |  |
| http-route | the code viewer requests one file's text at `GET /p/<project>/api/src?path=&at=` — from git at the map's commit by default, or from the working tree | [serve.py](tools/coyodex/viewer/serve.py:629) | C24 |  |
| http-route | the impact explorer requests `GET /p/<project>/api/impact?base=&target=&…` to project a code diff onto the map | [serve.py](tools/coyodex/viewer/serve.py:655) | C24 |  |
| http-route | the impact picker requests `GET /p/<project>/api/impactcommits` for the commits around the map's pin | [serve.py](tools/coyodex/viewer/serve.py:666) | C24 |  |
| http-route | the impact code view requests `GET /p/<project>/api/impactsrcdiff?path=&base=&target=` for one file's inline diff across any two refs | [serve.py](tools/coyodex/viewer/serve.py:669) | C24 |  |
| http-route | the landing page posts a folder to `POST /api/open` to add a project to the served list | [serve.py](tools/coyodex/viewer/serve.py:543) | C24 |  |
| http-route | the landing page posts a folder to `POST /api/forget` to remove a project from the recents list | [serve.py](tools/coyodex/viewer/serve.py:543) | C24 |  |
| http-route | the landing page posts the dragged card order to `POST /api/reorder` to persist the recents order | [serve.py](tools/coyodex/viewer/serve.py:541) | C24 |  |
| middleware | every GET first passes the loopback-Host check, so a page on another domain that re-points its name at 127.0.0.1 is refused | [serve.py](tools/coyodex/viewer/serve.py:512) | C24 |  |
| middleware | every POST must carry the `X-Coyodex: serve` header, which a cross-origin page cannot set — the CSRF gate before any recents change | [serve.py](tools/coyodex/viewer/serve.py:535) | C24 |  |
| middleware | every request under `/p/<project>/` first re-checks the map file's timestamp and drops the cached diagrams when the map changed on disk | [serve.py](tools/coyodex/viewer/serve.py:527) | C24 |  |
| ui-route | the reader clicks a project card on the landing page, which navigates the browser to that map's URL | [serve.py](tools/coyodex/viewer/serve.py:910) | C24 |  |
| ui-route | the reader clicks a top-bar tab to switch view — Happy Path, Use Cases, Subsystems, Entities, Dependencies, Data, Deployment, System, Glossary, Tests (each hidden when the map has nothing for it) | [viewer.js](tools/coyodex/viewer/viewer.js:6674) | C23 |  |
| ui-route | the reader opens the search overlay (the magnifier button, or the `/` key) to jump to any map element, file, or code symbol | [viewer.js](tools/coyodex/viewer/viewer.js:6641) | C23 |  |
| ui-route | the reader opens the Impact popover to pick two commits and project that diff onto the map | [viewer.js](tools/coyodex/viewer/viewer.js:6906) | C23 |  |
| ui-route | the reader switches the side pane between the file browser and the code viewer | [viewer.js](tools/coyodex/viewer/viewer.js:6178) | C23 |  |
| ui-route | the reader clicks the page title to go back to the server's landing page listing all maps | [viewer.js](tools/coyodex/viewer/viewer.js:5234) | C23 |  |
| startup-hook | the serve command finishes loading the projects and the HTTP server starts accepting connections on 127.0.0.1, handing each one to its own worker thread | [serve.py](tools/coyodex/viewer/serve.py:734) | C24 | continuous ([serve.py](tools/coyodex/viewer/serve.py:742)) |
| startup-hook | with `coyodex serve --open`, the server opens the landing page in the developer's browser by itself as it starts listening | [serve.py](tools/coyodex/viewer/serve.py:740) | C24 | on-boot ([serve.py](tools/coyodex/viewer/serve.py:739)) |
| startup-hook | the landing page's script runs itself as soon as the page loads, fetching the home folder and the recents list | [serve.py](tools/coyodex/viewer/serve.py:1040) | C24 | on-boot ([serve.py](tools/coyodex/viewer/serve.py:1040)) |
| startup-hook | the browser app fetches the map's view bundle at module load, before any other statement runs — nothing in the app can start without it | [viewer.js](tools/coyodex/viewer/viewer.js:107) | C23 | on-boot ([viewer.js](tools/coyodex/viewer/viewer.js:107)) |
| startup-hook | the browser app probes the server once at load and, on success, reveals and wires the file browser and code viewer | [viewer.js](tools/coyodex/viewer/viewer.js:6659) | C23 | on-boot ([viewer.js](tools/coyodex/viewer/viewer.js:6659)) |

---

## Subdomains (SD) — bounded contexts of the domain model

| ID | Subdomain | Purpose | Parent | Source | Conf. |
|---|---|---|---|---|---|
| **SD1** | Map document | The committed map document as a whole — the typed record every other layer reads, plus the declarative directives and proposals that edit it between builds. |  | tools/coyodex/model.py:418 | high |
| **SD2** | Behavioral layer | The part of the map that answers 'what does this system do, for whom, in what order' — roles, glossary, use cases, the Happy Path spine, and the use-case flows. | SD1 | tools/coyodex/model.py:38 | high |
| **SD3** | Structural layer | The machine behind the behavior — components, their groups, external dependencies, entry points, the backbone edge list, the async channel catalog, and the citations grounding them. | SD1 | tools/coyodex/model.py:99 | high |
| **SD4** | Domain-model layer | The map's own picture of the mapped project's data — entity cards with their fields, relations, storage and lifecycles, and the plumbing types deliberately left unmodelled. | SD1 | tools/coyodex/model.py:244 | high |
| **SD5** | Operational & quality layer | How the mapped system is deployed, watched, secured and configured, plus the map's honesty record — test-coverage gaps, grounding coverage, and preserved freeform sections. | SD1 | tools/coyodex/model.py:338 | high |
| **SD6** | Code pre-index | The mechanical reading of the source tree handed to a build — the file walk, the symbols and imports found in each file, and the component-count expectation derived from directory size. |  | tools/coyodex/preindex_lib.py:253 | high |
| **SD7** | Viewer graph & file browser | The shape the map takes on its way to the screen — drawable nodes and arrows, flows, the change-impact report, the coverage-tagged file tree, and the list of recently opened projects. |  | tools/coyodex/viewer/build_graph.py:111 | high |
| **SD8** | Change impact | What a code change does to an existing map — the raw diff pieces, the per-file picture of which pinned lines moved, each anchor it hits, and the ripple out to neighbouring elements. |  | tools/coyodex/impact_lib.py:170 | high |
| **SD9** | Method-quality eval | The measurements that say whether a rebuilt map got better or worse — the deterministic profile, the judged semantic scores, and the gated comparison against the blessed baseline. |  | eval/tools/coyodex_eval/profile.py:37 | high |

---

## T5 — Domain model (domain cards)

**E1 — ProjectModel** *(D2..coyodex/project-map.json — collection; the committed source of truth; the markdown map and the served diagram are generated views of it)*
SUBDOMAIN: SD1
MEANING: The whole map of one codebase — the single committed document holding everything the map knows, in a fixed key order so it diffs cleanly.
FIELDS: format:string · title:string · goal:string · commit:string ? · committed:string ? · built:string ? · roles:E2 [] · glossary:E3 [] · use_cases:E4 [] · happy_path:E5 [] · subsystems:E9 [] · components:E10 [] · deps:E11 [] · run_commands:E14 [] · entry_points:E13 [] · subdomains:E9 [] · entities:E17 [] · non_entity_types:E23 [] · flows:E6 [] · subflows:E8 [] · edges:E12 [] · messaging:E16 [] · deployment:E24 [] · environments:list · observability:E26 [] · security:E27 [] · config:E28 [] · tests_note:string · tests:E29 [] · grounding:E31 ? · extras:E30 []
RELATIONS: contains 1→* E2 roles · contains 1→* E3 glossary · contains 1→* E4 use cases · contains 1→* E5 Happy Path · contains 1→* E9 subsystems & subdomains · contains 1→* E10 components · contains 1→* E11 dependencies · contains 1→* E13 entry points · contains 1→* E14 run commands · contains 1→* E17 entities · contains 1→* E23 non-entity types · contains 1→* E6 flows · contains 1→* E8 sub-flows · contains 1→* E12 backbone edges · contains 1→* E16 channels · contains 1→* E24 deployment units · contains 1→* E26 observability · contains 1→* E27 security · contains 1→* E28 config · contains 1→* E29 test rows · contains 1→0..1 E31 grounding · contains 1→* E30 extras
SOURCE: [model.py](tools/coyodex/model.py:418)

**E2 — Role** *(roles[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD2
MEANING: Someone or something that uses the mapped system — a human user or another service — and what they want out of it.
FIELDS: id:string PK · name:string · kind:string · wants:string · drives:string
SOURCE: [model.py](tools/coyodex/model.py:38)

**E3 — GlossaryRow** *(glossary[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD2
MEANING: One term of the project's shared language, explained in a line and pointed at the code that owns it.
FIELDS: term:string PK · meaning:string · source:path ?
SOURCE: [model.py](tools/coyodex/model.py:47)

**E4 — UseCase** *(use_cases[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD2
MEANING: One thing a role can get done with the system, stated as what starts it and what comes out.
FIELDS: id:string PK · name:string · actors:E2 [] FK→E2 · trigger_outcome:string
RELATIONS: drivenBy *→* E2 actors
SOURCE: [model.py](tools/coyodex/model.py:56)

**E5 — HappyStep** *(happy_path[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD2
MEANING: One position in the ordered walk through the system's main story — a use case shown where it naturally happens.
FIELDS: id:string PK · title:string · uc:E4 ? FK→E4 · why:string ?
RELATIONS: realizes *→1 E4
SOURCE: [model.py](tools/coyodex/model.py:65)

**E6 — Flow** *(flows[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD2
MEANING: The inside story of one use case — the ordered exchanges between the pieces of the system that make it happen.
FIELDS: uc:E4 PK FK→E4 · title:string · steps:E7 []
RELATIONS: contains 1→* E7 steps · detailsUseCase 1→1 E4
SOURCE: [model.py](tools/coyodex/model.py:293)

**E7 — FlowStep** *(flows[].steps[] — embedded; the same shape also fills subflows[].steps[])*
SUBDOMAIN: SD2
MEANING: One interaction inside a flow — who talks to whom, what happens there, and the exact line of code where it happens.
FIELDS: n:int · src:string · dst:string · phrase:string · note:string · where:path ? · no_call_site:bool · subflow:E8 ? FK→E8
SOURCE: [model.py](tools/coyodex/model.py:269)

**E8 — SubFlow** *(subflows[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD2
MEANING: A named run of steps shared by several use cases — written once and referenced, so every flow that rides it stays at the same level of detail.
FIELDS: id:string PK · name:string · steps:E7 []
RELATIONS: contains 1→* E7 steps
SOURCE: [model.py](tools/coyodex/model.py:300)

**E9 — Group** *(subsystems[] — embedded; the same shape also fills subdomains[]; `tech` is subsystem-only)*
SUBDOMAIN: SD3
MEANING: A box that holds other boxes — a subsystem grouping components, or a subdomain grouping entities; both use the same shape and may nest.
FIELDS: id:string PK · name:string · purpose:string · parent:E9 ? FK→E9 · source:path ? · confidence:string · tech:string · tech_source:path
RELATIONS: contains 1→* E9 nested groups
SOURCE: [model.py](tools/coyodex/model.py:73)

**E10 — Component** *(components[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD3
MEANING: One named piece of the mapped system — roughly a module or folder — with what it is for, where it lives, and which files it owns.
FIELDS: id:string PK · name:string · subsystem:E9 ? FK→E9 · purpose:string · entry_point:path ? · depends_on:string · source:path ? · confidence:string · files:list · runs_in:list · evidence:E15 [] · states:E21 ? · extra:dict
RELATIONS: belongsTo *→0..1 E9 its subsystem · contains 1→* E15 evidence · contains 1→0..1 E21 its lifecycle
SOURCE: [model.py](tools/coyodex/model.py:99)

**E11 — Dep** *(deps[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD3
MEANING: Something the mapped project relies on but does not own — a database, a queue, an outside service, a framework or a library.
FIELDS: id:string PK · name:string · kind:string ? · type:string · used_for:string · bucket:string · where_configured:path · confidence:string · deployment_linked:bool · package:string · alternative:string · evidence:E15 [] · extra:dict
RELATIONS: contains 1→* E15 evidence
SOURCE: [model.py](tools/coyodex/model.py:124)

**E12 — Edge** *(edges[] — embedded; one project-wide backbone list; entity-to-entity relations stay on the domain cards)*
SUBDOMAIN: SD3
MEANING: One claimed relationship in the mapped system — this piece uses, writes or calls that one — with a witness line of code proving it.
FIELDS: src:string · verb:string · dst:string · why:string ? · where:path ? · no_call_site:bool
RELATIONS: connects *→* E10 {both endpoints hold an element identifier as plain text — a component, a dependency or an entity — so no typed column can back the arrow}
SOURCE: [model.py](tools/coyodex/model.py:313)

**E13 — EntryPoint** *(entry_points[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD3
MEANING: A way in to the mapped system — a route, a command, a webhook or a background loop — with who or what starts it and how often.
FIELDS: kind:string · trigger:string · source:path · component:E10 FK→E10 · activation:string · runs_in:list · cadence:string · cadence_source:path
RELATIONS: triggers *→1 E10 its owning component
STATES: self · external — [grammar.py](tools/coyodex/grammar.py:223)
SOURCE: [model.py](tools/coyodex/model.py:150)

**E14 — RunRow** *(run_commands[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD3
MEANING: One command a developer actually types to run, build or test the mapped project, pointed at where that command is defined.
FIELDS: action:string PK · command:string · source:path
SOURCE: [model.py](tools/coyodex/model.py:142)

**E15 — EvidenceItem** *(components[].evidence[] — embedded; the same shape also fills deps[].evidence[] and tests[].tests[])*
SUBDOMAIN: SD3
MEANING: One citation backing something the map says — a line of code plus the reason it proves the claim.
FIELDS: file:path · why:string
SOURCE: [model.py](tools/coyodex/model.py:91)

**E16 — MessagingRow** *(messaging[] — embedded; name-keyed: nothing points at a channel, so the row itself is the join)*
SUBDOMAIN: SD3
MEANING: One channel, queue or topic the mapped system passes messages through — who puts messages on it, who takes them off, and what they carry.
FIELDS: name:string PK unique · kind:string · broker:E11 FK→E11 · publishers:E10 [] FK→E10 · consumers:E10 [] FK→E10 · payload:E17 FK→E17 · source:path
RELATIONS: carriedBy *→0..1 E11 its broker · wiredTo *→* E10 publishers & consumers · carries *→0..1 E17 its payload
SOURCE: [model.py](tools/coyodex/model.py:194)

**E17 — Entity** *(entities[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD4
MEANING: One domain card — a real named type in the mapped code, with what it means, what it holds, how it relates to its neighbours and where it is stored.
FIELDS: id:string PK · name:string · store:E20 ? · meaning:string · subdomain:E9 ? FK→E9 · source:path ? · fields:E18 [] · relations:E19 [] · states:E21 ?
RELATIONS: belongsTo *→0..1 E9 its subdomain · contains 1→* E18 fields · contains 1→* E19 relations · contains 1→0..1 E20 where it is stored · contains 1→0..1 E21 its lifecycle
SOURCE: [model.py](tools/coyodex/model.py:244)

**E18 — EntityField** *(entities[].fields[] — embedded; lives only inside its entity card)*
SUBDOMAIN: SD4
MEANING: One attribute on a domain card — its name, its type, and the small markers saying whether it is a key, a list, or may be missing.
FIELDS: name:string · type:string · markers:list
SOURCE: [model.py](tools/coyodex/model.py:171)

**E19 — EntityRelation** *(entities[].relations[] — embedded; authored on the source card only, so a pair is never stated twice)*
SUBDOMAIN: SD4
MEANING: One typed link from a domain card to another — what kind of link it is, how many of each side, and how it is wired when no field carries it.
FIELDS: verb:string · target:E17 FK→E17 · src_card:string ? · dst_card:string ? · display:string · how:string ? · keyed_by:list
SOURCE: [model.py](tools/coyodex/model.py:178)

**E20 — Store** *(entities[].store — embedded; lives only inside its entity card)*
SUBDOMAIN: SD4
MEANING: Where one domain type physically lives — which datastore, which compartment inside it, and in what way it is kept there.
FIELDS: dep:E11 ? FK→E11 · container:string · mode:string · notes:string
RELATIONS: livesIn *→0..1 E11 the physical datastore
STATES: collection · embedded · transient · cache · in-code · enum — [grammar.py](tools/coyodex/grammar.py:243)
SOURCE: [model.py](tools/coyodex/model.py:230)

**E21 — StateMachine** *(entities[].states — embedded; the same shape also fills components[].states)*
SUBDOMAIN: SD4
MEANING: A lifecycle the mapped code really implements — the named states a thing can be in, how it moves between them, and the line that declares them.
FIELDS: states:list · transitions:E22 [] · source:path
RELATIONS: contains 1→* E22 transitions
SOURCE: [model.py](tools/coyodex/model.py:217)

**E22 — StateTransition** *(entities[].states.transitions[] — embedded; lives only inside its state machine)*
SUBDOMAIN: SD4
MEANING: One move from one state to another, and what triggers it.
FIELDS: src:string · dst:string · on:string
SOURCE: [model.py](tools/coyodex/model.py:210)

**E23 — NonEntityType** *(non_entity_types[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD4
MEANING: A named type in the mapped code that is deliberately NOT a domain concept — plumbing, recorded on purpose so the coverage check does not call it missing.
FIELDS: name:string PK · source:path ? · why:string
SOURCE: [model.py](tools/coyodex/model.py:259)

**E24 — DeploymentRow** *(deployment[] — embedded; name-keyed by unit, like a messaging channel)*
SUBDOMAIN: SD5
MEANING: One running process of the mapped system — where it runs, how it is reached, how it is configured, and which environments it belongs to.
FIELDS: unit:string PK unique · runs_on:string · exposed_as:string · config_source:string · variants:E25 []
RELATIONS: contains 1→* E25 environment placements
SOURCE: [model.py](tools/coyodex/model.py:338)

**E25 — VariantTag** *(deployment[].variants[] — embedded; lives only inside its deployment row)*
SUBDOMAIN: SD5
MEANING: One environment a deployment unit runs in, together with the manifest line that proves it belongs there.
FIELDS: env:string · source:path
SOURCE: [model.py](tools/coyodex/model.py:325)

**E26 — ObservabilityRow** *(observability[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD5
MEANING: One signal the mapped system emits — a log, metric or trace — with where it is produced, where it is read, and what alerts on it.
FIELDS: signal:string PK · where_emitted:string · where_viewed:string · alerts:string
SOURCE: [model.py](tools/coyodex/model.py:353)

**E27 — SecurityRow** *(security[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD5
MEANING: One way into the mapped system that needs protecting — who may reach it, the code that checks that, and what is risky about it.
FIELDS: surface:string PK · who:string · source:path · risk:string
SOURCE: [model.py](tools/coyodex/model.py:361)

**E28 — ConfigRow** *(config[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD5
MEANING: One setting that changes how the mapped system behaves — what it is for, its default, and whether it differs per environment.
FIELDS: key:string PK · purpose:string · default:string · per_env:string
SOURCE: [model.py](tools/coyodex/model.py:370)

**E29 — TestRow** *(tests[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD5
MEANING: One honest statement about testing — which parts of the map this covers, whether they are tested, which suites do it, and what the gap is.
FIELDS: targets:list · tested:string · label:string · tests:E15 [] · gap:string · confidence:string
RELATIONS: contains 1→* E15 exercising suites · assesses *→* E10 {the assessed elements are listed as plain-text identifiers and may be of any kind, so no typed column backs the arrow}
SOURCE: [model.py](tools/coyodex/model.py:378)

**E30 — ExtraSection** *(extras[] — embedded; inside .coyodex/project-map.json)*
SUBDOMAIN: SD5
MEANING: A section someone wrote by hand that the map does not otherwise know about, kept word for word so nothing is lost — and the place justified exceptions are recorded.
FIELDS: heading:string PK · body:string
SOURCE: [model.py](tools/coyodex/model.py:391)

**E31 — Grounding** *(grounding — embedded; one object on the map document; absent means no grounding pass ran)*
SUBDOMAIN: SD5
MEANING: How much of the map's risky claims were actually challenged and how many turned out wrong — the map's own confidence, travelling with it.
FIELDS: claims_total:int · claims_challenged:int · claims_confirmed:int · claims_refuted:int · claims_unverifiable:int · note:string
SOURCE: [model.py](tools/coyodex/model.py:398)

**E32 — Reconcile** *(reconcile file — transient; parsed from the JSON file passed to `assemble --reconcile`; the tool never writes it)*
SUBDOMAIN: SD1
MEANING: A re-runnable list of corrections applied to a map every time it is rebuilt, so a hand fix is never quietly lost on the next build.
FIELDS: sets:E33 [] · drop_edges:E34 []
RELATIONS: contains 1→* E33 assignments · contains 1→* E34 edge removals
SOURCE: [reconcile.py](tools/coyodex/reconcile.py:76)

**E33 — SetDirective** *(set[] — embedded; inside the reconcile file)*
SUBDOMAIN: SD1
MEANING: One bulk assignment applied after a build — put these elements in this group, run them in these units, or file this dependency under this purpose.
FIELDS: ids:list · subsystem:string ? · subdomain:string ? · runs_in:list ? · bucket:string ?
RELATIONS: assigns *→* E10 {the directive lists element identifiers as plain text, and whichever property it assigns decides which kind of element is legal}
SOURCE: [reconcile.py](tools/coyodex/reconcile.py:55)

**E34 — DropEdgeDirective** *(drop_edges[] — embedded; inside the reconcile file)*
SUBDOMAIN: SD1
MEANING: One instruction to remove a relationship the map got wrong, and to say what should happen to the flow steps that were riding it.
FIELDS: src:string · verb:string · dst:string · drop_steps:bool · repoint:string ?
RELATIONS: removes *→* E12 {matched against the backbone list by the triple that identifies an edge, rather than by a stored reference}
SOURCE: [reconcile.py](tools/coyodex/reconcile.py:67)

**E35 — Proposal** *(balance report — transient; computed and printed by `coyodex balance`; never stored)*
SUBDOMAIN: SD1
MEANING: One suggested new group for a diagram that shows too many boxes, with a name seed and the members that would move into it.
FIELDS: name:string · name_basis:string · members:list
RELATIONS: groups 1→* E10 {the suggested group lists the elements it would move as identifier and label pairs, not as typed references}
SOURCE: [balance_lib.py](tools/coyodex/balance_lib.py:382)

**E36 — WalkResult** *(walk — transient; computed per run; every consumer re-walks rather than reading a stored copy)*
SUBDOMAIN: SD6
MEANING: The set of real source files found in a repo, and whether git or a plain folder walk found them.
FIELDS: files:list · root:path · used_git:bool · skipped_excluded:int
SOURCE: [preindex_lib.py](tools/coyodex/preindex_lib.py:154)

**E37 — Symbol** *(D2..coyodex/preindex.json — collection; written under `symbols` as name lookups plus line extents)*
SUBDOMAIN: SD6
MEANING: One definition found in the code — a class or function, its file, and the span of lines it covers.
FIELDS: name:string · kind:string · file:path · line:int · end:int ?
SOURCE: [preindex_lib.py](tools/coyodex/preindex_lib.py:253)

**E38 — ImportRef** *(D2..coyodex/preindex.json — collection; written under `imports`; dynamic imports are not captured, so the list is a lower bound)*
SUBDOMAIN: SD6
MEANING: One import found in the code — which file pulls in which module, and on what line.
FIELDS: file:path · line:int · module:string
SOURCE: [preindex_lib.py](tools/coyodex/preindex_lib.py:262)

**E39 — DirExpectation** *(D2..coyodex/preindex.json — collection; written under `granularity`; checkers re-compute it from the tree instead of reading it)*
SUBDOMAIN: SD6
MEANING: How many components one folder should reasonably become, worked out from its size — the anchor that says whether a map is drawn too coarse or too fine.
FIELDS: path:path PK · files:int · loc:int · expected:int · children:E39 []
RELATIONS: contains 1→* E39 sub-folders
SOURCE: [preindex_lib.py](tools/coyodex/preindex_lib.py:474)

**E40 — GraphDict** *(view bundle — transient; built on demand from the map document and served; never committed)*
SUBDOMAIN: SD7
MEANING: The whole map rewritten for the screen — every drawable box, arrow, flow and side table the viewer needs, in one payload.
FIELDS: commit:string ? · committed:string ? · built:string ? · format:string ? · title:string ? · goal:string ? · nodes:E41 [] · edges:E42 [] · happy_path:E43 [] · flows:E44 [] · subflows:E44 [] · roles:list · glossary:list · run_commands:list · entry_points:list · non_entity_types:list · deployment:list · environments:list · messaging:list · observability:list · security:list · config:list · data_view:dict · tests_note:string · tests:E46 [] · extras:list
RELATIONS: contains 1→* E41 nodes · contains 1→* E42 arrows · contains 1→* E43 Happy Path · contains 1→* E44 flows & sub-flows · contains 1→* E46 test rows
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:111)

**E41 — Node** *(view bundle — transient; derived from the map document each time the viewer asks)*
SUBDOMAIN: SD7
MEANING: One box on a diagram — whatever kind of map element it came from — carrying its display fields, the files it covers and the group it sits in.
FIELDS: id:string PK · kind:string · name:string · file:path ? · line:int ? · fields:dict · parent:E41 ? FK→E41 · attrs:list · dep_kind:string ? · files:list · entry_points:list · runs_in:list · roles:list · store:dict ? · states_count:int · states_lines:list
RELATIONS: has 1→* E41 child boxes
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:28)

**E42 — Edge (graph)** *(view bundle — transient; merged from the backbone edge list and the domain cards' relations)*
SUBDOMAIN: SD7
MEANING: One arrow on a diagram, carrying everything the drawing needs — its kind, its cardinality, and the real field name to write on it.
FIELDS: src:string · verb:string · dst:string · why:string ? · where:path ? · kind:string ? · src_card:string ? · dst_card:string ? · how:string ? · fk_fields:list · fk_side:string ? · keyed_by:list
RELATIONS: connects *→* E41 {both endpoints hold a node identifier as plain text, resolved by the viewer at draw time}
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:67)

**E43 — HappyStep (graph)** *(view bundle — transient; carried straight from the map document)*
SUBDOMAIN: SD7
MEANING: One Happy Path position as the viewer shows it — a title, the use case it opens when clicked, and why it sits where it does.
FIELDS: id:string PK · title:string · uc:string ? · why:string
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:86)

**E44 — Flow (view)** *(view bundle — transient; built per request from the map document's flows and sub-flows)*
SUBDOMAIN: SD7
MEANING: One use-case story as the viewer draws it, with its steps already resolved for display.
FIELDS: uc:string PK · title:string · steps:E45 [] · line_no:int
RELATIONS: contains 1→* E45 steps
SOURCE: [grammar.py](tools/coyodex/grammar.py:533)

**E45 — FlowStep (view)** *(view bundle — transient; derived from the map document's flow steps at build time)*
SUBDOMAIN: SD7
MEANING: One step as the viewer draws it — with each end already marked as either a system element or a person, so the arrow reads correctly.
FIELDS: n:int · src:string · dst:string · src_is_id:bool · dst_is_id:bool · phrase:string · note:string · where:path ? · subflow:string ? · ok:bool
SOURCE: [grammar.py](tools/coyodex/grammar.py:519)

**E46 — TestRowView** *(view bundle — transient; resolved on the server so the browser needs no id parsing)*
SUBDOMAIN: SD7
MEANING: One test-coverage row prepared for the screen, with its targets already turned into readable names.
FIELDS: targets:E47 [] · label:string · tested:string · tests:list · gap:string · confidence:string
RELATIONS: contains 1→* E47 resolved targets
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:102)

**E47 — TestTarget** *(view bundle — transient; lives only inside its test row)*
SUBDOMAIN: SD7
MEANING: One thing a test row assesses, shown by name, and clickable when it is a box actually drawn on a diagram.
FIELDS: id:string PK · name:string · node:string ? FK→E41
RELATIONS: locates *→0..1 E41 the drawn box
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:96)

**E48 — DiffDict** *(change-impact report — transient; parsed from the markdown report on demand; the report itself is the artifact)*
SUBDOMAIN: SD7
MEANING: A change-impact report read back in — which map version it compares to which, what changed, and what new relationships appeared.
FIELDS: base:string ? · new:string ? · changes:E49 [] · new_edges:list
RELATIONS: contains 1→* E49 per-element changes
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:161)

**E49 — DiffChange** *(change-impact report — transient; lives only inside a parsed report)*
SUBDOMAIN: SD7
MEANING: What happened to one map element between two versions — added, changed or gone — with a short note.
FIELDS: id:string PK · change:string · name:string ? · kind:string ? · note:string
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:153)

**E50 — FileTreeNode** *(view bundle — transient; rebuilt from the repo at the map's commit each time the browser is opened)*
SUBDOMAIN: SD7
MEANING: One folder or file in the browsable repo tree, tagged with how well the map covers it and which element a click should open.
FIELDS: name:string · path:path PK · dir:bool · node:string ? FK→E41 · others:list · sel:string ? · cov:string · mapped:int · ref:int · children:E50 []
RELATIONS: contains 1→* E50 children · mapsTo *→0..1 E41 the element anchored here
SOURCE: [filetree.py](tools/coyodex/viewer/filetree.py:38)

**E51 — RecentsStore** *(D2.~/.coyodex/serve-recents.json — collection; reloaded before every write so a concurrent build registering a project merges instead of clobbering)*
SUBDOMAIN: SD7
MEANING: The list of projects the user has opened in the map server, most recent first — the cards shown on its landing page.
FIELDS: path:path PK · folders:list
SOURCE: [recents.py](tools/coyodex/viewer/recents.py:22)

**E52 — ImpactCore** *(impact run — transient; computed per run; the published artifact is the change-impact report)*
SUBDOMAIN: SD8
MEANING: One change-impact run — which map version it is measured against, which two code versions are compared, and every changed file it looked at.
FIELDS: pin:string · base:string · target:string · files:E53 [] · warnings:list
RELATIONS: contains 1→* E53 changed files
SOURCE: [impact_git.py](tools/coyodex/impact_git.py:184)

**E53 — ImpactFile** *(impact run — transient; lives only inside an impact run)*
SUBDOMAIN: SD8
MEANING: One changed file seen through the map's eyes — where it used to live, what happened to it, and which map anchors it touches.
FIELDS: path:path PK · p_path:path ? · status:string · frame:E55 ? · hits:E59 []
RELATIONS: contains 1→0..1 E55 its line picture · contains 1→* E59 hits
SOURCE: [impact_git.py](tools/coyodex/impact_git.py:175)

**E54 — Change** *(impact run — transient; read from git per run, never stored)*
SUBDOMAIN: SD8
MEANING: One entry from the raw list of what git says changed — added, modified, deleted or renamed, and under which name.
FIELDS: status:string · path:path · old_path:path ?
SOURCE: [impact_git.py](tools/coyodex/impact_git.py:68)

**E55 — FileFrame** *(impact run — transient; lives only inside an impact file record)*
SUBDOMAIN: SD8
MEANING: Which lines of a file — as the map saw them when it was built — this change actually disturbs, so an old anchor can be judged fairly.
FIELDS: affected:list · insertions:list · p_absent:bool · binary:bool · whitespace_only:bool · fully_deleted:bool
RELATIONS: foldedFrom 1→* E57 {two diffs against the map's pinned version are folded together — a hunk present on both sides cancels, and every remaining one marks the lines it disturbs}
SOURCE: [impact_lib.py](tools/coyodex/impact_lib.py:94)

**E56 — Hunk** *(impact run — transient; parsed from git output per run)*
SUBDOMAIN: SD8
MEANING: One block of a diff — which old lines it replaces and what replaces them.
FIELDS: p_lo:int · p_len:int · plus:list · minus:list
SOURCE: [impact_lib.py](tools/coyodex/impact_lib.py:36)

**E57 — ParsedDiff** *(impact run — transient; parsed from git output per run)*
SUBDOMAIN: SD8
MEANING: One file's diff after parsing — its blocks of change, or a flag saying the file is binary and cannot be read this way.
FIELDS: hunks:E56 [] · binary:bool
RELATIONS: contains 1→* E56 hunks
SOURCE: [impact_lib.py](tools/coyodex/impact_lib.py:51)

**E58 — AnchorRef** *(impact run — transient; collected from the map document at the start of every impact run)*
SUBDOMAIN: SD8
MEANING: One place in the code that the map points at, remembered with which element carries it and which of that element's fields it came from.
FIELDS: eid:string · kind:string · path:path · lo:int ? · hi:int ? · field:string · is_dir:bool · owner:string ?
SOURCE: [impact_lib.py](tools/coyodex/impact_lib.py:170)

**E59 — DirectHit** *(impact run — transient; lives only inside an impact file record)*
SUBDOMAIN: SD8
MEANING: One map anchor the change actually reaches, with how precisely it was reached — the exact line, the surrounding definition, or only the file.
FIELDS: eid:string · kind:string · path:path · change:string · resolution:string · field:string · owner:string ? · drift_to:int ? · territory:bool
RELATIONS: resolves *→1 E58 {one hit is produced per anchor in a changed file, copying that anchor's details rather than keeping a reference to it}
STATES: deleted · added · modified · drifted — [impact_ripple.py](tools/coyodex/impact_ripple.py:42)
SOURCE: [impact_lib.py](tools/coyodex/impact_lib.py:278)

**E60 — RippleOptions** *(impact run — transient; passed in per run; the defaults keep the noisy links switched off)*
SUBDOMAIN: SD8
MEANING: How far a change is allowed to spread beyond what it directly touches — which weaker kinds of link to follow, and how many hops.
FIELDS: reads:bool · entity_graph:bool · callgraph:bool · callgraph_depth:int
SOURCE: [impact_ripple.py](tools/coyodex/impact_ripple.py:56)

**E61 — _Impact** *(impact run — transient; accumulated per run and serialized into the run's result payload)*
SUBDOMAIN: SD8
MEANING: The verdict on one map element in a change-impact run — whether the change hit it directly or reached it indirectly, how strongly, and by which path.
FIELDS: eid:string PK · cause:string · change:string · resolution:string ? · strength:int · distance:int · via:list · files:set
RELATIONS: consolidates 1→* E59 {built from every direct hit on the same element and then strengthened by the ripple rules, keyed by identifier rather than by a stored reference}
SOURCE: [impact_ripple.py](tools/coyodex/impact_ripple.py:64)

**E62 — RunResult** *(run directory — transient; its parts are archived separately as profile.json, judge.json and delta.md)*
SUBDOMAIN: SD9
MEANING: One eval run of a rebuilt map — its measurements, its judged scores, its comparison to the blessed baseline, and the verdict that follows.
FIELDS: project:string PK · profile:E63 · judge:E64 ? · delta:E69 ? · verdict:string
RELATIONS: contains 1→1 E63 the profile · contains 1→0..1 E64 the judge report · contains 1→0..1 E69 the comparison
STATES: PASS · DRIFT · REGRESSED · BASELINE — [run.py](eval/tools/coyodex_eval/run.py:34)
SOURCE: [run.py](eval/tools/coyodex_eval/run.py:45)

**E63 — MapProfile** *(D2.profile.json — collection; written into each run directory and into the blessed baseline, under .coyodex-eval/)*
SUBDOMAIN: SD9
MEANING: Everything measurable about one built map — how big it is, how clean it validates, how well it covers the code — reduced to numbers two runs can be compared on.
FIELDS: use_cases:int · subsystems:int · subdomains:int · components:int · deps:int · entities:int · edges:int · hp_steps:int · flows:int · security_surfaces:int · validate_ok:bool · validate_problems:int · validate_warnings:int · contradictions:int · advisories:int · audit_warnings:int · l2_claims:int · coverage_flags:int ? · edges_per_component:float ? · granularity_expected:int ? · root_fanout:int ? · max_fanout:int ? · fanout_in_band_pct:float ? · nesting_depth:int ? · subflows:int ? · max_flow_len:int ? · flows_over_band_pct:float ? · entry_points:int ? · external_entry_points:int ? · unclaimed_entry_points:int ? · off_spine_ucs:int ? · entities_in_flows:int ? · entities_in_flows_pct:float ? · auth_surfaces:list · use_case_names:list · entity_names:list
RELATIONS: measures 1→1 E1 {every count is computed from a loaded map document at scoring time; only the numbers are kept, not the document}
SOURCE: [profile.py](eval/tools/coyodex_eval/profile.py:37)

**E64 — JudgeReport** *(D2.judge.json — collection; written beside the profile in each run directory and in the blessed baseline)*
SUBDOMAIN: SD9
MEANING: The quality signals only a reader can give — how many of the map's risky claims survived a skeptic, and how it scores on each rubric dimension.
FIELDS: n_claims:int · n_grounded:int · grounding_passrate:float ? · dimensions:E65 [] · overall:float ? · n_worklist:int · n_failures:int · protocol:E68 ? · n_anchor_checked:int · n_anchor_drifted:int · anchor_drift_rate:float ?
RELATIONS: contains 1→* E65 dimension scores · contains 1→0..1 E68 the judging regime · summarizes 1→* E66 {the pass rate is the majority outcome over the skeptic votes on each risky statement, which are counted and then dropped, never kept in the report}
SOURCE: [judge.py](eval/tools/coyodex_eval/judge.py:101)

**E65 — DimensionScore** *(dimensions[] — embedded; inside judge.json)*
SUBDOMAIN: SD9
MEANING: One rubric dimension's settled score for a map — the middle value of several independent readers, so one outlier cannot swing it.
FIELDS: dimension:string PK · score:float · n_judges:int
RELATIONS: medianOf 1→* E67 {the middle value of the individual readers' marks on this rubric axis; their separate judgements are not kept}
SOURCE: [judge.py](eval/tools/coyodex_eval/judge.py:74)

**E66 — GroundingVerdict** *(grounding[] — transient; replayed from the raw verdict file the judging orchestration writes; the aggregated report keeps only the counts)*
SUBDOMAIN: SD9
MEANING: One skeptic's attempt to disprove a claim the map makes — held, refuted, or could not be checked at all — with the line they read.
FIELDS: claim:string · grounded:bool ? · evidence:string
SOURCE: [judge.py](eval/tools/coyodex_eval/judge.py:56)

**E67 — RubricVerdict** *(judges[] — transient; replayed from the raw verdict file; only the median survives into judge.json)*
SUBDOMAIN: SD9
MEANING: One judge's score for one rubric dimension, with the reason and the line of code backing it.
FIELDS: dimension:string · score:int · justification:string · evidence:string
SOURCE: [judge.py](eval/tools/coyodex_eval/judge.py:66)

**E68 — JudgeProtocol** *(protocol — embedded; one object inside judge.json; absent on reports written before fingerprinting existed)*
SUBDOMAIN: SD9
MEANING: The fingerprint of how a map was judged — which model, how many readers, how many claims, which rubric wording — so scores from different regimes are never compared.
FIELDS: model:string · n_skeptics:int · grounding_cap:int · rubric_sha:string · prompt_version:string
SOURCE: [judge.py](eval/tools/coyodex_eval/judge.py:81)

**E69 — DeltaReport** *(delta.md — transient; rendered into the run's delta.md and printable as JSON; the structure itself is not archived)*
SUBDOMAIN: SD9
MEANING: The verdict on whether a rebuilt map got better or worse than the blessed one — which hard checks failed, which numbers drifted, and what could not be compared.
FIELDS: verdict:string · gates:E70 [] · bands:E71 [] · notes:list · judge_bands:E72 [] · granularity:E73 ?
RELATIONS: contains 1→* E70 hard gates · contains 1→* E71 count bands · contains 1→* E72 judge bands · contains 1→0..1 E73 the granularity check
STATES: PASS · DRIFT · REGRESSED — [compare.py](eval/tools/coyodex_eval/compare.py:41)
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:173)

**E70 — GateResult** *(gates[] — embedded; inside the comparison report)*
SUBDOMAIN: SD9
MEANING: One must-not-get-worse check and whether the new map passed it.
FIELDS: name:string PK · passed:bool · detail:string
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:130)

**E71 — BandResult** *(bands[] — embedded; inside the comparison report)*
SUBDOMAIN: SD9
MEANING: One measured number checked against how far it is allowed to move from the baseline before a human should look.
FIELDS: metric:string PK · baseline:float · candidate:float · delta_pct:float · allowed_pct:float · within:bool · shrink_only:bool
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:137)

**E72 — JudgeBand** *(judge_bands[] — embedded; inside the comparison report)*
SUBDOMAIN: SD9
MEANING: One judged quality score checked for a fall against the baseline — a rise is always fine, only a drop counts.
FIELDS: metric:string PK · baseline:float · candidate:float · drop:float · allowed_drop:float · within:bool
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:148)

**E73 — GranularityResult** *(granularity — embedded; one object inside the comparison report)*
SUBDOMAIN: SD9
MEANING: How far each map's component count sits from the count the code itself suggests — the fair check on whether a map is drawn at the right zoom.
FIELDS: expected:int · baseline_components:int · candidate_components:int · baseline_delta_pct:float · candidate_delta_pct:float · allowed_pct:float · within:bool
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:158)

**E74 — Thresholds** *(D2.thresholds.json — collection; read from the eval workspace config; global settings merged with per-project overrides)*
SUBDOMAIN: SD9
MEANING: The tuning for how strict a comparison is — which checks block, how far each number may drift, and how much a judged score may fall.
FIELDS: validate_must_not_regress:bool · no_new_contradictions:bool · coverage_flags_may_increase_by:int · auth_surfaces_must_not_drop:bool · bands:dict · judge_bands:dict · granularity_band_pct:float
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:91)

---

## Non-entity types (plumbing, deliberately unmodelled)

| Type | Source | Why |
|---|---|---|
| ModelError | tools/coyodex/model.py:31 | an error class raised when a map document is malformed, not a concept the map describes |
| ImpactError | tools/coyodex/impact_git.py:42 | an error class for a failed git call or an unsafe revision name, not a domain concept |
| ReconcileError | tools/coyodex/reconcile.py:40 | an error class for a malformed reconcile file, raised at load time so the build fails loudly |
| Extent | tools/coyodex/impact_lib.py:274 | a type alias for the four-part tuple of one symbol's line span, not a class of its own |
| Extents | tools/coyodex/impact_git.py:196 | a type alias for the per-file table of symbol line spans, not a class of its own |
| _Maps | tools/coyodex/impact_ripple.py:77 | a bundle of lookup tables built once per impact run so the ripple rules can be applied quickly — an index, not a concept |
| _Dir | tools/coyodex/viewer/filetree.py:131 | a mutable scratch folder used only while nesting file paths into a tree, frozen into FileTreeNode at the end |
| Judge | eval/tools/coyodex_eval/judge.py:139 | the injection seam standing in for the model that reads the code — an interface, so tests can pass a fake |
| PrecomputedJudge | eval/tools/coyodex_eval/judge.py:266 | an adapter that replays verdicts produced outside the tool through the same aggregation path, not a data concept |

---

## T6 — Use-case flows

**UC2 — Build a baseline map of a repo**
1. Coding agent → C1 : reads the method's dispatch doc and picks the Build mode · no map file on disk means no baseline, even when git history still holds a committed copy
2. C30 → C9 : routes the pre-index command so the code tree is sized and located before any reading starts @ [cli.py](tools/coyodex/cli.py:81)
3. C9 → D1 : lists the repo's tracked files and reads per-file churn from the commit history @ [preindex_lib.py](tools/coyodex/preindex_lib.py:172)
4. C9 → E37 : emits a symbol row for every class and function definition it parses @ [preindex_lib.py](tools/coyodex/preindex_lib.py:277)
5. C9 → D2 : writes the pre-index artifact — weight tree, symbols, expected component count, coverage — beside the map @ [preindex.py](tools/coyodex/preindex.py:432) · advisory input the agent reconciles, never rows copied into the map
6. Coding agent → C7 : self-checks each harvest and trace fragment before returning it · the agents fan out over the sized tree and each returns structured rows, so a bad row dies in its own author's turn instead of at the lead's validate
7. C7 → C10 : runs the model rulebook's anchor, edge and flow checks over the one fragment @ [lint_fragment.py](tools/coyodex/lint_fragment.py:117)
8. C7 → C14 : confirms every anchor in the fragment resolves to a real file in the analyzed repo @ [lint_fragment.py](tools/coyodex/lint_fragment.py:150)
9. C6 → C3 : parses each returned fragment as a partial model, so one malformed fragment fails alone and by name @ [assemble.py](tools/coyodex/assemble.py:139)
10. C6 → C8 : applies the synthesis assignments — subsystem, subdomain, runs_in, dropped edges — after the merge @ [assemble.py](tools/coyodex/assemble.py:456) · a re-assemble re-applies the same file, so the assignments survive a rebuild
11. C6 → E1 : serializes the merged fragments into the canonical map document @ [assemble.py](tools/coyodex/assemble.py:474)
12. C30 → C20 : ⟨runs SF10 — Run the map gates⟩
13. C8 → C12 : re-derives the auditor's grounding worklist so each fresh-context skeptic's verdict pairs with the claim it answers @ [fix.py](tools/coyodex/fix.py:85) · the skeptics read the code themselves and report the true call site; this pass only judges the difference
14. C8 → E1 : rewrites each drifted anchor in the stored map and re-serializes it @ [fix.py](tools/coyodex/fix.py:42)
15. Coding agent → C41 : stamps the session it is running in into the map folder's provenance file, so the map can later be paired with the conversation that produced it
16. Coding agent → D1 : commits the model, its markdown view and the pre-index into the repo's map folder, pinned to the build commit

**UC6 — Analyze a code change against the map**
1. Coding agent → C1 : reads the change-impact doc, which scopes the work to the diff against the pinned baseline instead of a rebuild
2. Coding agent → E1 : reads the baseline's pinned commit off the stored map — the left end of every diff · the baseline is left untouched here; it lags the code on purpose, and that lag is exactly what the report describes
3. Coding agent → D1 : diffs the pin against the working tree with rename detection, and lists the untracked files on their own · the right end is the working tree, so uncommitted edits count; a plain diff omits untracked files, so those are listed separately and treated as added
4. Coding agent → E10 : places every changed file on at least the component that owns it, sharpening to an entity or a flow step only where reading the code allows · the report states the resolution each change reached rather than faking step-level precision
5. Coding agent → E12 : follows each changed element's backbone links and flow steps outward to what they reach, instead of asking of every baseline element whether it was affected · tracing stops honestly at an injection seam, where callers hit a port rather than the implementation
6. Coding agent → D2 : writes the report under `.coyodex/analysis-changes/<date>.md`, carrying the exact was → now text of every element it touches · patch-complete on purpose — accept transcribes this text and reads no code of its own
7. Coding agent → Developer : hands back a report that is on disk but uncommitted, so it survives a lost session and can be reviewed, shared or accepted later

**UC7 — Accept a change into the baseline**
1. Coding agent → C1 : reads the accept half of the change-impact method, which forbids any fresh reading of code at accept time · if accept finds itself inferring, the report was incomplete — regenerate the report rather than invent here
2. Coding agent → E1 : transcribes the report's was → now blocks into the stored map as surgical field edits, never a rebuild · the new baseline is the old one patched in place, so its own diff shows real semantic deltas and no wording drift
3. Coding agent → D1 : reads the new code commit and its date, after checking that the code itself is committed · the pin gate: the map and the report are expected to be dirty — that is what this step commits — and a `-dirty` pin is recorded only if the developer picks that option
4. Coding agent → E1 : re-pins the map to that commit, so the baseline again describes exactly one past commit
5. Coding agent → C41 : re-stamps the map's provenance with this accept session and the repo's current sha
6. Coding agent → C30 : re-runs the map gates over the patched map, because a hand patch can introduce a contradiction the report never had
7. C30 → C20 : ⟨runs SF10 — Run the map gates⟩
8. C30 → C9 : rebuilds the code pre-index at the new pin, so its line anchors match the re-pinned map @ [cli.py](tools/coyodex/cli.py:81) · only when the map already has a pre-index; skipping it leaves the viewer's symbol search on stale lines for exactly the files the change touched
9. Coding agent → D1 : commits the map, the markdown view, the pre-index, the provenance and the report together with the code · the commit IS the acceptance — it is what keeps the baseline pin aligned with the code commit
10. Coding agent → Developer : reports the local URL that opens the re-pinned map in the map server

**UC8 — Change the map on request**
1. Coding agent → C1 : reads the dispatch program's direct-map-change branch, which sends it to edit the stored map surgically instead of rebuilding it
2. C13 → Coding agent : hands over a ready-to-apply split as an exact direct-map-change block — the new group's id and every member to move onto it @ [balance.py](tools/coyodex/balance.py:92) · only when the request came out of the balance report's over-dense-diagram proposal; the block is a starting point, never applied for the agent
3. Coding agent → C30 : runs the read-only lookup for every element the request names, before touching anything
4. C30 → C31 : hands the lookup to the model reader, filling in the standard map location when none was named @ [cli.py](tools/coyodex/cli.py:99)
5. C31 → E1 : reads the stored map document off disk and parses it, then pulls out the named element's record, its links and its members @ [dump.py](tools/coyodex/dump.py:153)
6. C31 → Coding agent : prints the resolved slice as JSON, so the edit is made against what the map actually stores @ [dump.py](tools/coyodex/dump.py:177)
7. Coding agent → E1 : rewrites only the fields and arrays the request names, and refuses any element the code does not back · an added use case stands only when real code and a traced flow back it; otherwise the agent says so and adds nothing
8. Coding agent → C8 : runs the bulk-edit toolkit for the corrections that must not be hand-scripted — dropping a refuted link and healing the flow steps that rode it · the toolkit matches a link on its full source-verb-target triple, so a paired link never swaps
9. C8 → E1 : writes the edited map back through the one canonical serializer, so the file stays byte-stable and valid by construction @ [fix.py](tools/coyodex/fix.py:42)
10. C30 → C20 : ⟨runs SF10 — Run the map gates⟩
11. Coding agent → D1 : commits the edited model together with its regenerated markdown view
12. D1 → Coding agent : hands back the commit that now pins the changed map beside the code it describes

**UC11 — See what a change ripples to in the viewer**
1. Developer → C32 : opens the impact explorer and picks the two commits to compare, or the one-click map-commit-to-working-tree range
2. C32 → C24 : asks the local map server to project that range onto the map, switching the call-graph ripple on when the deepest setting is armed @ [viewer.js](tools/coyodex/viewer/viewer.js:6851)
3. C24 → C40 : hands the pair of refs to the impact engine, which resolves every map anchor the diff touches and ripples once @ [serve.py](tools/coyodex/viewer/serve.py:370)
4. C32 → E61 : reads back each element's verdict — hit directly or reached by ripple, how strongly, at which rung and by which path — and keeps the ones inside the chosen ripple depth @ [viewer.js](tools/coyodex/viewer/viewer.js:6720)
5. C32 → C38 : marks every changed file in the browser and re-opens the file already on screen so it flips into diff mode @ [viewer.js](tools/coyodex/viewer/viewer.js:6866)
6. C32 → C24 : asks for that file's inline diff over the armed range instead of its plain source @ [viewer.js](tools/coyodex/viewer/viewer.js:5801)
7. C24 → C25 : turns git's unified diff for that one file into numbered add, delete and context rows @ [serve.py](tools/coyodex/viewer/serve.py:331)
8. C32 → C37 : takes over the info pane with everything the diff reached, grouped by kind and clickable through to each element @ [viewer.js](tools/coyodex/viewer/viewer.js:6805)
9. C32 → C23 : lands the reader on the view that carries the overlay and redraws it @ [viewer.js](tools/coyodex/viewer/viewer.js:6867)
10. C32 → Developer : lights up every touched box with its change badge, each group box carrying whatever its subtree was hit by @ [viewer.js](tools/coyodex/viewer/viewer.js:2132)

**UC9 — Check the method's quality**
1. Method maintainer → C45 : runs the method-quality eval on a project that already has a committed map
2. Coding agent → C45 : hands over the map it rebuilt at the baseline's pinned commit, with the sha256 taken the moment the build finished · the rebuild happens in an isolated checkout that cannot see the baseline map, earlier eval output or the gate settings, so its numbers cannot steer the build
3. C45 → D2 : re-hashes the fresh map from disk and refuses the whole run when a single byte moved after the build @ [run.py](eval/tools/coyodex_eval/run.py:213) · a flag that lost its value fails closed rather than silently skipping the guard
4. C45 → E63 : reduces the frozen fresh map to the deterministic signals two runs can be compared on ⟨runs SF50 — Measure a map's deterministic quality signals⟩
5. C45 → E63 : measures the project's committed baseline map through exactly the same reduction, so the two sides are never scored differently ⟨runs SF50 — Measure a map's deterministic quality signals⟩ · only when the baseline's cached scoring is missing or was produced under an older judging regime; otherwise the cached profile and judge report are read straight back from the eval folder (eval/tools/coyodex_eval/run.py:77)
6. Coding agent → C45 : hands over the raw votes its judge sub-agents produced — one row per skeptic per claim, plus each judge's rubric scores · the eval itself never calls a model; the judging runs in fresh-context sub-agents on a pinned model
7. C45 → C46 : passes those raw votes to the scoring half to be aggregated by the same tested math a live judge would go through @ [run.py](eval/tools/coyodex_eval/run.py:362)
8. C46 → E64 : settles each risky claim by majority of the usable votes, takes the median of every rubric dimension, and records which judging regime produced the scores @ [judge.py](eval/tools/coyodex_eval/judge.py:257) · a skeptic that could not check the code counts as a failure, excluded from the pass-rate denominator and never counted as a refutation
9. C45 → C46 : hands the fresh profile and judge report to the comparison, alongside the baseline's own @ [run.py](eval/tools/coyodex_eval/run.py:67)
10. C46 → E69 : applies the baseline-relative hard checks and the drift bands and settles on one verdict — a failed check is a regression, a breached band is drift, otherwise it passed @ [compare.py](eval/tools/coyodex_eval/compare.py:332)
11. C45 → D2 : archives the whole run — the frozen map, its generated views, the profile, the judge report and the written-up delta @ [run.py](eval/tools/coyodex_eval/run.py:161) · the historical record a later baseline is blessed from
12. C45 → Method maintainer : reports the verdict with the checks and bands that moved, and exits on a code an unattended run can gate on @ [run.py](eval/tools/coyodex_eval/run.py:255)

**UC10 — Back up a map with its build transcript**
1. Developer → C41 : later, from any session, runs the backup against the mapped repo, choosing whether to move the map out or leave a copy behind
2. C41 → D2 : reads the stamped provenance back for the project name, the build time that names the backup folder, and every session that touched the map @ [map_backup.py](tools/map_backup.py:115) · a corrupt provenance file stops the backup instead of being silently ignored
3. C41 → D3 : locates each stamped session's conversation in the agent's session store by globbing for that id @ [map_backup.py](tools/map_backup.py:217) · an unstamped map can still be recovered on request by scanning the store for the conversation that actually wrote a map file (tools/map_backup.py:458)
4. C41 → D2 : copies the whole map folder — the map document and its generated views — into the bundle, without parsing it @ [map_backup.py](tools/map_backup.py:507) · a move with no conversation to bundle is refused before this point, so the map is never deleted without the conversation that produced it (tools/map_backup.py:477)
5. C41 → D3 : copies each conversation transcript, and any sub-agent folder beside it, into the bundle @ [map_backup.py](tools/map_backup.py:365) · always copied, never moved — the store belongs to the running agent
6. C41 → D2 : writes the bundle manifest — the project, the build time, whether the map was moved or copied, and exactly which sessions were bundled @ [map_backup.py](tools/map_backup.py:530)
7. C41 → D2 : removes the source map folder only now, once its copy is safely in the bundle @ [map_backup.py](tools/map_backup.py:536) · skipped when the developer asked to keep the map in place
8. C41 → Developer : reports the bundle path — the map paired with the exact conversation that produced it @ [map_backup.py](tools/map_backup.py:541)

**UC1 — Install the coyodex skill**
1. Developer → C2 : runs `make install` in the clone, which drops the skill manifest into every coding agent's skills folder with this clone's path baked in
2. Developer → C30 : installs the repo into a repo-local virtualenv that holds the `coyodex` command · the same `make install` run does this first, so one command covers both the skill and the tools
3. Coding agent → C2 : picks up the installed `/coyodex` skill and reads its manifest
4. C2 → Coding agent : hands back the clone's absolute path as the one place the method docs and tools live · install substituted that path for the `__COYODEX_HOME__` placeholder, so nothing has to be looked up at run time
5. C2 → C1 : sends the agent into the method's dispatch doc in the clone, which picks build / analyze / accept @ [SKILL.md](skill/coyodex/SKILL.md:28)
6. C2 → C30 : points every tool run at the clone's virtualenv `coyodex` command @ [SKILL.md](skill/coyodex/SKILL.md:24)

**UC3 — Start the local map server**
1. Developer → C30 : runs `make start`, which launches `coyodex serve --port 8765 --open` from the repo-local virtualenv
2. C30 → C24 : hands the `serve` command line to the map server @ [cli.py](tools/coyodex/cli.py:93)
3. C24 → C25 : asks the recents store for the project folders opened before @ [serve.py](tools/coyodex/viewer/serve.py:726)
4. C25 → E51 : fills the recents store with the remembered project folders @ [recents.py](tools/coyodex/viewer/recents.py:30)
5. C25 → D2 : reads the remembered-projects file out of the user's home folder @ [recents.py](tools/coyodex/viewer/recents.py:34) · a missing or unreadable file yields an empty list, so a first start simply shows no cards
6. C24 → D2 : reads each remembered folder's map file to see which projects can still be served @ [serve.py](tools/coyodex/viewer/serve.py:121) · a folder whose map is gone or unloadable stays in the list but is not served
7. C24 → D6 : opens the landing page in the developer's browser as the server starts listening on 127.0.0.1 @ [serve.py](tools/coyodex/viewer/serve.py:740) · only with `--open`, which `make start` passes
8. C24 → D6 : returns the landing page, one card per remembered project @ [serve.py](tools/coyodex/viewer/serve.py:518)
9. C24 → Developer : shows the developer a landing page listing every project they have mapped

**UC4 — Explore a map top-down**
1. Developer → C23 : opens the project's map in the browser
2. C23 → C22 : ⟨runs SF20 — Open a served map in the browser⟩
3. C23 → Developer : writes the map's title, pinned commit and one-line goal into the page header @ [viewer.js](tools/coyodex/viewer/viewer.js:170)
4. C23 → D16 : turns the pre-rendered diagram source for this altitude into a drawn SVG @ [viewer.js](tools/coyodex/viewer/viewer.js:4562) · a source that fails to draw degrades to a message instead of freezing the view
5. C23 → D17 : makes the drawn diagram pannable and zoomable, fitted to the pane @ [viewer.js](tools/coyodex/viewer/viewer.js:4626)
6. C23 → Developer : shows this level's screen of boxes — the Happy Path, the context or the subsystem map @ [viewer.js](tools/coyodex/viewer/viewer.js:4570)
7. Developer → C23 : drills a box to open the level beneath it
8. C23 → Developer : leaves a trail of the levels descended, each step back up clickable @ [viewer.js](tools/coyodex/viewer/viewer.js:3961)
9. Developer → C23 : clicks a box on the level below to read what it is
10. C23 → C37 : hands the clicked element to the info pane beside the diagram @ [viewer.js](tools/coyodex/viewer/viewer.js:2266)
11. C37 → E41 : reads that element's stored name, type and annotation @ [viewer.js](tools/coyodex/viewer/viewer.js:1072)
12. C37 → Developer : shows the element's plain-language purpose with its type and its related elements @ [viewer.js](tools/coyodex/viewer/viewer.js:1121)

**UC5 — Open the source behind a mapped element**
1. Developer → C23 : opens the project's map in the browser
2. C23 → C22 : ⟨runs SF20 — Open a served map in the browser⟩
3. Developer → C23 : clicks the code anchor carried by a box, an arrow or a flow step
4. C23 → C38 : hands that anchor's file and line to the code viewer @ [viewer.js](tools/coyodex/viewer/viewer.js:152)
5. C38 → C24 : asks the local server for that file's text @ [viewer.js](tools/coyodex/viewer/viewer.js:5806)
6. C24 → D1 : reads the file's contents at the commit the map is pinned to @ [serve.py](tools/coyodex/viewer/serve.py:223) · a file absent from that commit answers 404, so a local edit can never leak into the view
7. C24 → C38 : answers with the file as plain text @ [serve.py](tools/coyodex/viewer/serve.py:654)
8. C38 → D18 : colours the source by language before it is laid out @ [viewer.js](tools/coyodex/viewer/viewer.js:5650) · a blocked or offline CDN falls back to plain, uncoloured text
9. C38 → E41 : reads every element anchored in this file so each is tagged on its own line @ [viewer.js](tools/coyodex/viewer/viewer.js:5496)
10. C38 → Developer : shows the file's numbered source beside the diagram @ [viewer.js](tools/coyodex/viewer/viewer.js:5666)
11. C38 → Developer : scrolls to and flashes the exact line the claim is anchored to @ [viewer.js](tools/coyodex/viewer/viewer.js:5638)
12. Developer → C38 : asks to hand the shown file off to their own editor or to GitHub
13. C38 → D8 : opens the file at that line in the local editor through its URL scheme @ [viewer.js](tools/coyodex/viewer/viewer.js:6021) · only when an editor is the chosen target and the local repo root is set
14. C38 → D7 : opens the file's blob page pinned to the map's commit @ [viewer.js](tools/coyodex/viewer/viewer.js:6024) · the zero-setup default whenever the mapped repo has a GitHub remote

---

## T6b — Sub-flows (shared step sequences, referenced by the flows above)

**SF10 — Run the map gates**
1. C30 → C15 : hands the stored model to the validation run, which blocks on a broken reference or a malformed anchor @ [cli.py](tools/coyodex/cli.py:84)
2. C30 → C12 : hands the same model to the adversarial pass, which makes the narrative and the mechanism refute each other @ [cli.py](tools/coyodex/cli.py:87)
3. C30 → C20 : regenerates the committed markdown view so it never drifts from the model @ [cli.py](tools/coyodex/cli.py:90)

**SF50 — Measure a map's deterministic quality signals**
1. C45 → C3 : loads the map through the product's own model loader, so a scored map is never parsed by a second grammar @ [profile.py](eval/tools/coyodex_eval/profile.py:122)
2. C45 → C10 : counts the well-formedness problems and warnings the shipped validator finds @ [profile.py](eval/tools/coyodex_eval/profile.py:129) · deliberately without the view-freshness check — that is repo hygiene, not map quality
3. C45 → C12 : counts the contradictions and advisories the shipped auditor raises, and sizes its risk-ranked list of actually-does claims @ [profile.py](eval/tools/coyodex_eval/profile.py:131)
4. C45 → C11 : measures how much of the source tree the map's anchors actually reach @ [profile.py](eval/tools/coyodex_eval/profile.py:141) · only when the source repo was given; otherwise the coverage signal is left empty rather than faked
5. C45 → C9 : re-derives from the code tree how many components a map of this repo is expected to have, the anchor the map's zoom is judged against @ [profile.py](eval/tools/coyodex_eval/profile.py:143)
6. C45 → C13 : reads the fan-out and nesting depth the map's diagrams would render at @ [profile.py](eval/tools/coyodex_eval/profile.py:149)
7. C45 → E63 : writes every signal into one profile — the counts, the findings, the coverage, the granularity and the density ratios @ [profile.py](eval/tools/coyodex_eval/profile.py:162)

**SF20 — Open a served map in the browser**
1. C23 → C24 : fetches this project's whole view bundle before anything is drawn @ [viewer.js](tools/coyodex/viewer/viewer.js:107) · no bundle means no map: the page says so and stops rather than rendering half a view
2. C24 → C20 : hands the project's stored map document to the graph builder @ [serve.py](tools/coyodex/viewer/serve.py:397)
3. C20 → E1 : walks the map document element by element @ [views.py](tools/coyodex/views.py:684)
4. C20 → E41 : builds one graph node per mapped element, carrying its name, type and source anchor @ [views.py](tools/coyodex/views.py:472)
5. C20 → E42 : builds one graph edge per authored relationship, so the arrows have something to draw @ [views.py](tools/coyodex/views.py:791)
6. C24 → C22 : asks for the view bundle — the graph plus every pre-rendered diagram and flow @ [serve.py](tools/coyodex/viewer/serve.py:399)
7. C22 → C26 : renders the context and subsystem diagram sources into the bundle @ [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2778)
8. C22 → C29 : renders the Happy Path and each use case's flow diagram into the bundle @ [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2840)
9. C24 → C23 : answers with the whole bundle as one JSON payload @ [serve.py](tools/coyodex/viewer/serve.py:616) · the built bundle is cached per map version and dropped when the map file changes on disk
10. C38 → C24 : asks for the repo's file tree once the server answers a health probe @ [viewer.js](tools/coyodex/viewer/viewer.js:5240)
11. C24 → C25 : builds the tree of the files tracked at the map's commit, shaded by how the map covers them @ [serve.py](tools/coyodex/viewer/serve.py:384)
12. C25 → E50 : builds one tree entry per folder and file, tagged with the element anchored there @ [filetree.py](tools/coyodex/viewer/filetree.py:147)

---

## Operational dimensions — the standard core four

### Deployment & topology

| Unit | Runs on | Exposed as | Config source |
|---|---|---|---|
| coyodex CLI | The developer's own machine, on CPython 3.10+ inside the repo-local virtualenv, installed editable so the clone stays the source of truth. | The `coyodex` console script — one command with sub-commands (preindex, validate, audit, render, assemble, lint-fragment, anchor-drift, fix, dump, reconcile, balance). Invoked by the coding agent following the method, or by hand. | Command-line arguments only, defaulting the map path to `.coyodex/project-map.json`. No config file and no environment variables on this path; the optional extras decide whether the pre-index sub-command has its parser available. |
| Map server | The same developer machine, as a long-lived foreground process (`coyodex serve`, usually via `make start`), stdlib http.server with a thread per request. | HTTP on 127.0.0.1 at the chosen port: a landing page, a shared frontend asset route, and a per-project API (view, tree, symbols, src, impact) under /p/<slug>/. | The `--port` and `--open` flags plus any folders passed on the command line; the served project set comes from `~/.coyodex/serve-recents.json`, re-read on every recents request so a freshly built map appears without a restart. |
| Browser viewer page | The user's web browser, loading the shared frontend from the local server and two libraries from public CDNs. | http://127.0.0.1:<port>/ for the landing page and /p/<slug>/ for a map; opened automatically when the server is started with --open. | The per-map view bundle fetched from the server at boot, overlaid with the user's own settings from browser localStorage (editor target, source root, GitHub URL, panel sizes). |
| coyodex-eval CLI | The developer machine, same virtualenv and interpreter as the main CLI; a separate self-contained package that depends on the core but is never referenced by it. | The `coyodex-eval` console script, run when someone wants a method-quality regression check. | Command-line arguments plus the eval bundle shipped in the repo (thresholds and rubric); all output goes to a git-ignored `.coyodex-eval/` directory in the evaluated project. |
| Map backup script | The developer machine, run directly as a standalone script by the venv interpreter. Deliberately stdlib-only so it still works when the project venv is broken. | Not a console script — invoked as `python tools/map_backup.py stamp\|backup <repo>` by the method's build and accept flows, or by the user later. | Command-line arguments, the `CLAUDE_CODE_SESSION_ID` environment variable for the stamp, and the committed `provenance.json` for the backup; the backup destination is derived from the coyodex clone's own location. |

### Observability

| Signal | Where emitted | Where viewed | Alerts |
|---|---|---|---|
| Command-line progress and summary output | Every CLI sub-command prints a human summary as it works — the pre-index prints its coverage line (git available, tree-sitter available, files walked), the server prints how many projects it is serving and the URL it is listening on, and errors and skip notices go to stderr. | The terminal of whoever ran the command — in practice the coding agent's tool output, since the agent is the usual caller. | None. This is a local developer tool with no alerting of any kind. |
| Process exit codes | Each sub-command returns a status the shell sees: zero on success, non-zero when a gate fails, and a distinct code for a usage error such as an unknown command or a bad --port value. | The calling shell, the Makefile, and the agent driving the method — this is the machine-readable signal the method's gates actually branch on. | None. |
| Map validation findings | The validator reports blocking problems separately from advisory warnings, covering schema shape, semantic checks such as nesting kind and cycles, anchor existence, and map-fidelity advisories like code-coverage and granularity bands. | Read in the terminal by the agent, which is required to clear the blocking findings before the map is considered built. | None — the gate is the exit code, not a notification. |
| Fragment lint findings | The per-fragment self-check each harvest agent runs before returning, reporting schema errors, anchor format and existence problems, unknown id references, and extra-key convention breaches in one pass. | In the sub-agent's own terminal output, deliberately so the agent that has the context fixes its own rows instead of the lead guessing later. | None. |
| Map audit findings | The adversarial pass over an assembled map: deterministic contradiction checks plus a grounding worklist of claims a skeptic should re-verify against the code. | The terminal, during the method's check phase; the worklist then drives further agent work. | None. |
| Balance report | The balance command reports per-diagram fan-out against the target band, the inter-subsystem edge matrix, and advisory split proposals for over-dense diagrams. | The terminal. Its proposals are advisory only — a human decides whether to apply them as a direct map change. | None. |
| Method-quality eval delta report | The eval builds a fresh map with the current method, profiles and judges it, and compares it against the project's committed map, producing a delta report scored against declared thresholds. | The terminal and the files written under the git-ignored `.coyodex-eval/` directory in the evaluated project. | None. There is no CI in this repo — no workflow files exist — so nothing runs these gates automatically; every signal above is produced only when a human or an agent runs the command. |

### Security & auth

| Surface | Who can reach | Auth check | Risk note |
|---|---|---|---|
| Local map server HTTP listener | Any process on the same machine that can reach the loopback interface — there is no authentication, no login, and no token of any kind. | tools/coyodex/viewer/serve.py:734 | The bind address is the only access control: 127.0.0.1 is hardcoded, so the server is unreachable from the network. On a shared or multi-user machine, however, ANY local process or local user can read every served map and every file in every served repo at the pinned commit. Accepted as the trust model of a single-user developer tool, but it is a real surface. |
| DNS-rebinding guard on every request | A web page on an attacker-controlled domain that re-points its hostname at 127.0.0.1 to read the victim's source through the browser. | tools/coyodex/viewer/serve.py:512 | Enforced: a request whose Host header does not name loopback is refused with 403. An ABSENT Host (HTTP/1.0, curl) is allowed on purpose — a deliberate, documented hole, on the reasoning that a header-less request is not a browser-driven rebinding vector. |
| State-changing POST endpoints (add / forget / reorder a project) | A cross-origin page in the user's browser trying to add or remove projects behind their back. | tools/coyodex/viewer/serve.py:535 | Enforced by requiring a custom request header a cross-origin page cannot set without a CORS preflight the server never answers. There is no token and no origin check, so the guard rests entirely on the browser's preflight behaviour; a non-browser local client can set the header freely. |
| Source file read at the pinned commit (/p/<slug>/api/src) | Anyone who can reach the loopback server — the viewer page, or any local process. | tools/coyodex/viewer/serve.py:631 | Path traversal is blocked before anything is read: absolute paths, backslashes, NUL bytes and any `..` segment are rejected with 400, and the read then goes through git rather than the filesystem, so only objects that exist in the named commit can come back. A blob over the size cap is refused before it is buffered. |
| Working-tree file read (/p/<slug>/api/src?at=WORKTREE) | The impact explorer, which must show the uncommitted side of a diff — the one route that touches real disk instead of git objects. | tools/coyodex/viewer/serve.py:275 | Enforced in layers: the resolved real path must stay inside the repo (so a tracked symlink cannot escape), any `.git` component is excluded, and only files git accounts for — tracked, or untracked but not ignored — are served, which keeps a gitignored secrets file from leaking through the viewer. This is the highest-risk read path in the product; the containment depends on all three checks staying together. |
| Git argument injection through a commit value | Whoever writes the map JSON, or a caller passing `at=` on the src route — a value that reaches git's argv. | tools/coyodex/viewer/serve.py:643 | Enforced: only a bare hex SHA is accepted, so a value starting with `-` can never be parsed by git as a flag. Commands are run as an argument list with no shell, which removes shell injection separately. |
| Git argument injection through a user-supplied ref | The impact explorer's base/target parameters, which accept branch names and revision expressions rather than bare SHAs. | tools/coyodex/impact_git.py:59 | Enforced, but NOT where the map first claimed: the guard in the server's own ref resolver never sees a request value (its only caller passes the map's own pin). The user-supplied base/target refs are gated in the impact engine, which rejects a leading dash and requires a revision-shaped character class before `git rev-parse --verify --end-of-options` peels it to a SHA. Verified live: `base=--output=/tmp/pwn` returns 400. |
| Filesystem browser used to pick a project folder (/api/browse) | Anyone who can reach the loopback server; the landing page uses it to walk the disk. | tools/coyodex/viewer/serve.py:512 | NO CONTAINMENT ON THE ROUTE ITSELF — the weakest surface in the product, and the anchor here is the only barrier that actually applies. Any absolute path is expanded, resolved and listed: `/`, `/Users` and `~/.ssh` all return 200 with a real listing (verified live against a throwaway server). Only directory NAMES leak, never file contents, and symlinked directories are skipped. What protects it is not the route but the loopback bind (serve.py:734), this Host guard, and the absence of CORS headers — i.e. it is safe on a single-user machine and not on a shared one. |
| Adding a project folder to the served set (/api/open) | The landing page, or any local caller that can set the CSRF header. | tools/coyodex/viewer/serve.py:574 | The only gate is that the folder must contain a `.coyodex/` directory. That is a low bar: creating such a directory anywhere makes that folder — and, through the src route, its git-tracked contents — servable. Mitigated by the loopback bind and the fact that reads stay inside a single repo at a pinned commit. |
| Shared frontend asset route (/static/<name>) | The browser fetching the viewer's script and stylesheet. | tools/coyodex/viewer/serve.py:702 | Enforced by an exact-name whitelist rather than path joining, so no traversal is possible on this route at all — an unknown name is a flat 404. |
| Editor hand-off URI built from a user-supplied template | The user, who may type a custom URI template into the viewer's Settings dialog. | tools/coyodex/viewer/viewer.js:5976 | Enforced in the browser: only schemes on the editor allowlist may land in an anchor href, which blocks `javascript:`, `data:`, `file:` and `http(s):` templates from running script or hijacking navigation. The dialog re-checks the same allowlist on save, so a rejected template is never stored. Note the URI is fired by the page, so the guard is client-side only — a tampered localStorage value is still filtered at the href, which is the right place. |
| Third-party scripts executed inside the viewer page | The two CDNs the page loads its diagram and highlighting libraries from. | tools/coyodex/viewer/viewer.html:17 | Enforced with Subresource Integrity on every tag, including the lazily injected highlighter and its stylesheet, so a tampered or swapped file is rejected by the browser. Residual risk: the page still depends on reachable third-party hosts, and there is no Content-Security-Policy header, so SRI is the only barrier. |
| Map-supplied text rendered into diagram labels | Whoever authors or edits the map JSON — including an agent writing a fragment. | tools/coyodex/viewer/gen_viewer.py:97 | The diagram renderer runs with HTML labels enabled, so label text is a script-injection path in principle. Enforced by a single sanitizer every diagram label passes through, which neutralises quotes, backticks, brackets, braces, pipes and angle brackets before the label reaches the browser. The risk concentrates in that one function: a caller that builds a label without it would bypass the guard. |
| Request body size on the POST endpoints | Any local caller. | tools/coyodex/viewer/serve.py:689 | Enforced: a missing, zero, or over-64KB Content-Length yields no parsed body, so a large or malformed request cannot exhaust memory. Paired with a 4MB cap on served file contents and a row cap on diff responses. |

### Config & environments

| Key | Purpose | Default | Per-env / secret? |
|---|---|---|---|
| coyodex serve --port | TCP port the local map server listens on. | 8765 | No environment axis — a per-run flag, useful when 8765 is already taken on the machine. |
| PORT (Makefile variable) | Port the `make start` convenience target passes through to the server. | 8765, overridable on the make command line (`PORT ?= 8765`) | No environment axis — a per-invocation override on the developer's own machine. |
| map server listen address | The interface the HTTP server binds to. | 127.0.0.1 — hardcoded, with no flag or variable to change it; the server is loopback-only by design. | Not configurable at all. Reaching it from another machine would require editing the source. |
| coyodex serve --open | Whether to launch the user's default browser at the landing page when the server starts. | off; `make start` passes it explicitly | No environment axis — a per-run flag. |
| ~/.coyodex/serve-recents.json | The ordered list of project folders the server offers as cards. The server does no disk scan, so this file is the entire served set. Holds absolute folder paths only — no secrets. | Absent until the first project is opened or a build registers one; an unreadable file is treated as an empty list. | Per user (under the home directory), shared by every map that user opens. |
| COYODEX_NO_SERVE_REGISTER | Opt out of a build automatically adding the project it just built to the recents list. Set by the regression eval so its throwaway maps do not pollute the user's landing page. | unset (auto-registration on) | Set per process by whoever runs the build; no committed value anywhere. |
| CLAUDE_CODE_SESSION_ID | Identifies the agent conversation that produced a map; written into the committed provenance stamp so a later backup can find the matching transcript. | Provided by the Claude Code runtime inside a session; unset elsewhere, in which case the stamp command refuses to run unless `--session-id` is passed. | Per session, injected by the agent runtime — never stored in the repo except as the recorded id inside provenance.json. |
| preindex optional extra | Pulls in tree-sitter and its grammar pack so `coyodex preindex` can extract symbols from non-Python languages. | Not installed by a plain install; `make deps` and `make install` install it explicitly. | Per install. Its absence is a supported state — the pre-index degrades rather than fails. |
| dev optional extra | Pulls in the test runner and the type checker for contributors. | Not installed; `make dev` installs it into the repo-local venv. | Per install; contributor machines only. |
| map path argument | Which map file a command operates on. | .coyodex/project-map.json, filled in by the CLI when no positional path is given | Per invocation. |
| SKILLS_DIRS (Makefile variable) | Where `make install` copies the agent skill manifest, with this repo's absolute path substituted in so the skill points back at the clone. | $HOME/.claude/skills and $HOME/.agents/skills | Per user home; deliberately two directories to cover the Claude Code and cross-agent families without duplicate discovery. |
| viewer settings in browser localStorage | The user's source hand-off choices: editor target, custom URI template, on-disk repo root, GitHub repo URL, plus panel sizes. The repo root and GitHub URL are namespaced per map so a root saved for one repo cannot open files from another. | Repo root and GitHub URL are seeded from the map's build-time git values; editor target is unset until the user saves the Settings dialog once. | Per browser profile and per map. Never sent to the server — there is no server-side settings endpoint. |
| VERSION file | The single source of the package version, read dynamically by the build backend and printed by `coyodex --version`. | 0.3.0 | One value per release; no per-environment variation. |

---

## Relationships — backbone edge list

| From | Verb | To | Why | Where (example) |
|---|---|---|---|---|
| C1 | uses | C30 | prescribes the exact `coyodex` command lines every build phase runs, so the method drives the tooling instead of restating what it does | [method.md](method.md:573) |
| C3 | persists | E1 | the single loader and serializer for the map document — parses it into the typed model and writes the byte-stable canonical form every writer stores | [model.py](tools/coyodex/model.py:612) |
| C3 | uses | C4 | takes the id-token, verb and dep vocabulary from the one place that decides them, so ids and verbs mean the same thing in every module | [model.py](tools/coyodex/model.py:529) |
| C5 | reads | C3 | walks the model's dataclasses to generate the map's JSON Schema from the types themselves, so the schema can never drift from the stored shape | [json_schema.py](tools/coyodex/json_schema.py:271) |
| C5 | uses | C4 | pulls the closed vocabularies (dep kinds, entry-point kinds, store modes) into the generated schema's enums | [json_schema.py](tools/coyodex/json_schema.py:81) |
| C6 | calls | C3 | builds every fragment and the merged result through the model's own parser and serializer, so the stored map is never hand-authored | [assemble.py](tools/coyodex/assemble.py:139) |
| C6 | calls | C10 | reuses the validator's unbacked-entity-step rule to derive the C→E backbone edge a trace agent authored a step for but forgot | [assemble.py](tools/coyodex/assemble.py:103) |
| C6 | calls | C8 | applies the declarative reconcile file after the merge and before the write, so a re-assemble never loses the synthesis assignments | [assemble.py](tools/coyodex/assemble.py:456) |
| C6 | calls | C20 | regenerates the committed markdown view in the same pass that writes the model, so the view ships fresh | [assemble.py](tools/coyodex/assemble.py:475) |
| C6 | writes | E1 | the build's only writer of the canonical map document — every fragment lands in the map through here | [assemble.py](tools/coyodex/assemble.py:474) |
| C6 | writes | E12 | derives and appends the backbone edge each unbacked entity flow-step implies, so an entity is never left without an owning component | [assemble.py](tools/coyodex/assemble.py:115) |
| C6 | writes | D2 | writes the assembled model, its markdown view and the scratch-dir ignore entry into the analyzed repo's map folder | [assemble.py](tools/coyodex/assemble.py:474) |
| C7 | calls | C6 | loads and schema-checks the fragment through the assembler's own fragment parser, so lint and assemble can never disagree on what is valid | [lint_fragment.py](tools/coyodex/lint_fragment.py:238) |
| C7 | calls | C10 | runs the model rulebook's row-local checks over a single partial fragment, shifting the fix into the authoring agent's own context | [lint_fragment.py](tools/coyodex/lint_fragment.py:117) |
| C7 | calls | C14 | checks each anchor and entity source in the fragment against the real repo, so a wrong path prefix dies at the source | [lint_fragment.py](tools/coyodex/lint_fragment.py:150) |
| C7 | calls | C4 | asks the shared vocabulary whether a step endpoint is a role id or an element id before judging it | [lint_fragment.py](tools/coyodex/lint_fragment.py:91) |
| C8 | calls | C12 | re-derives the auditor's L2 grounding worklist so each skeptic verdict pairs with the exact claim it answers | [fix.py](tools/coyodex/fix.py:85) |
| C8 | calls | C5 | compares a stored anchor with the skeptics' reported lines through the shared anchor parser and drift rule | [anchor_drift.py](tools/coyodex/anchor_drift.py:64) |
| C8 | calls | C14 | falls back to the same deterministic operative-line classifier when no skeptic verdicts exist, so a serial build gets the same grounding floor | [anchor_drift.py](tools/coyodex/anchor_drift.py:110) |
| C8 | calls | C3 | loads the assembled map and re-serializes it after every in-place fix, so the terminal edits keep the canonical form | [fix.py](tools/coyodex/fix.py:42) |
| C8 | calls | C11 | reuses the hierarchy rules to reject a reconcile assignment whose parent is the wrong kind of group | [reconcile.py](tools/coyodex/reconcile.py:227) |
| C8 | writes | E1 | the terminal writer of the stored map after assembly — drifted anchors and refuted edges are corrected here | [fix.py](tools/coyodex/fix.py:42) |
| C8 | persists | E32 | expands the lead's path rules into the explicit reconcile document and writes it beside the map, so the assignments are replayable | [reconcile_build.py](tools/coyodex/reconcile_build.py:234) |
| C8 | writes | D2 | writes the corrected map and the expanded reconcile document back into the analyzed repo's map folder | [fix.py](tools/coyodex/fix.py:42) |
| C9 | reads | D1 | enumerates the repo's tracked files and reads per-file churn from the commit history, so generated output never inflates the weight tree | [preindex_lib.py](tools/coyodex/preindex_lib.py:172) |
| C9 | reads | D2 | walks the source tree when git is unavailable and opens every file it counts, parses or measures | [preindex_lib.py](tools/coyodex/preindex_lib.py:197) |
| C9 | writes | D2 | writes the committed pre-index artifact — weight tree, symbols, imports, granularity, coverage — into the analyzed repo's map folder | [preindex.py](tools/coyodex/preindex.py:432) |
| C9 | uses | D12 | parses non-Python sources with tree-sitter to extract their definitions and import statements | [preindex_lib.py](tools/coyodex/preindex_lib.py:381) |
| C9 | uses | D13 | loads a per-language grammar from the language pack, and records the language unparsed when none exists | [preindex_lib.py](tools/coyodex/preindex_lib.py:331) |
| C9 | calls | C5 | parses Python sources through the shared AST helper rather than its own reader | [preindex_lib.py](tools/coyodex/preindex_lib.py:271) |
| C9 | emits | E36 | returns the enumerated source-file set together with how it was obtained and what was excluded | [preindex_lib.py](tools/coyodex/preindex_lib.py:191) |
| C9 | persists | E37 | produces a symbol row for every class and function definition it parses, the pre-index's file:line lookup | [preindex.py](tools/coyodex/preindex.py:146) |
| C9 | persists | E38 | produces an import reference per import statement, the lower-bound cross-check for named component pairs | [preindex.py](tools/coyodex/preindex.py:219) |
| C9 | writes | E39 | builds the per-directory expected-component record that the pre-index artifact carries as a flattened path-to-count map | [preindex_lib.py](tools/coyodex/preindex_lib.py:541) |
| C10 | calls | C16 | asks the adjudication readers which ids the operator already recorded under an extras heading, so a settled finding stays quiet | [validate_model.py](tools/coyodex/validate_model.py:522) |
| C10 | uses | C4 | decides what a step endpoint, a dep kind or an FK marker means from the shared vocabulary instead of its own patterns | [validate_model.py](tools/coyodex/validate_model.py:208) |
| C11 | calls | C5 | normalizes each stored source anchor through the shared anchor parser before resolving it against the repo | [validate_analysis.py](tools/coyodex/validate_analysis.py:322) |
| C11 | uses | C4 | takes the nesting-depth advisory threshold from the shared vocabulary | [validate_analysis.py](tools/coyodex/validate_analysis.py:66) |
| C12 | calls | C3 | loads the assembled map and expands sub-flow references, so a referencing flow is audited with the shared steps inlined | [audit_model.py](tools/coyodex/audit_model.py:124) |
| C12 | calls | C4 | classifies each dep from the shared vocabulary so a folded framework claim is skipped instead of sent to a skeptic | [audit_model.py](tools/coyodex/audit_model.py:372) |
| C12 | uses | C5 | pulls the file:line out of a stored cell with the shared anchor finder | [audit_model.py](tools/coyodex/audit_model.py:56) |
| C12 | reads | E1 | reads the whole stored map to produce its contradiction findings and the ranked grounding worklist the skeptics work | [audit_model.py](tools/coyodex/audit_model.py:578) |
| C13 | reads | E1 | reads the stored map to measure per-diagram fan-out and the inter-subsystem edge matrix | [balance.py](tools/coyodex/balance.py:193) |
| C13 | calls | C3 | loads and schema-validates the map through the shared loader before measuring anything | [balance.py](tools/coyodex/balance.py:193) |
| C13 | emits | E35 | builds the advisory split proposals for an over-dense diagram, each with a seeded name and its member ids | [balance_lib.py](tools/coyodex/balance_lib.py:499) |
| C14 | reads | D2 | opens every anchored source file in the analyzed repo to confirm it exists and that the cited line can act | [validate_model.py](tools/coyodex/validate_model.py:2113) |
| C14 | calls | C5 | parses each anchor and asks the shared classifier whether the cited line could be the acting statement | [validate_model.py](tools/coyodex/validate_model.py:2119) |
| C14 | calls | C11 | resolves anchors against the repo roots and runs the shared coverage measures over the referenced paths | [validate_model.py](tools/coyodex/validate_model.py:2105) |
| C14 | calls | C20 | regenerates the markdown view and compares it to the committed one, so a stale generated view is visible | [validate_model.py](tools/coyodex/validate_model.py:2288) |
| C15 | calls | C10 | runs the whole model-only rulebook over the loaded map and collects its problems and warnings | [validate_model.py](tools/coyodex/validate_model.py:2307) |
| C15 | calls | C14 | adds the source-grounding and coverage checks when the run asks for them, the opt-in half of the gate | [validate_model.py](tools/coyodex/validate_model.py:2364) |
| C15 | calls | C11 | checks the subsystem and subdomain hierarchy and the code-coverage measures through the shared helpers | [validate_model.py](tools/coyodex/validate_model.py:2376) |
| C15 | calls | C13 | folds the always-on diagram-balance warnings into every validation report | [validate_model.py](tools/coyodex/validate_model.py:2415) |
| C15 | calls | C3 | loads and schema-validates the stored map before any semantic check runs, so a shape violation fails first | [validate_model.py](tools/coyodex/validate_model.py:2532) |
| C15 | reads | E1 | reads the stored map document as the input of every validation run | [validate_model.py](tools/coyodex/validate_model.py:2532) |
| C16 | calls | C13 | reads the map's extras bodies through the shared balance helper, so one place decides what an extras heading holds | [validate_model.py](tools/coyodex/validate_model.py:557) |
| C30 | calls | C9 | routes the preindex command into the pre-index — the only path allowed to load tree-sitter, keeping every other command third-party free | [cli.py](tools/coyodex/cli.py:81) |
| C30 | calls | C15 | routes validate into the validation run, which loads the map and reports its problems and warnings | [cli.py](tools/coyodex/cli.py:84) |
| C30 | calls | C12 | routes audit into the adversarial pass over an assembled map | [cli.py](tools/coyodex/cli.py:87) |
| C30 | calls | C20 | routes render into the markdown view generator — the map's only generated file | [cli.py](tools/coyodex/cli.py:90) |
| C30 | calls | C24 | routes serve into the local viewer server that builds each diagram on demand | [cli.py](tools/coyodex/cli.py:93) |
| C30 | calls | C6 | routes assemble into the fragment merger that writes the canonical map and its view | [cli.py](tools/coyodex/cli.py:96) |
| C30 | calls | C31 | routes dump into the read-only model lookup | [cli.py](tools/coyodex/cli.py:99) |
| C30 | calls | C13 | routes balance into the per-diagram fan-out reporter | [cli.py](tools/coyodex/cli.py:102) |
| C30 | calls | C7 | routes lint-fragment into the per-fragment self-check an authoring agent runs before returning its rows | [cli.py](tools/coyodex/cli.py:108) |
| C40 | reads | D1 | runs read-only git to get the change set with renames, the rename maps and each side's file text | [impact_git.py](tools/coyodex/impact_git.py:49) |
| C40 | reads | D2 | reads a working-tree file straight off disk — the one side of a comparison git cannot serve from a commit | [impact_git.py](tools/coyodex/impact_git.py:128) |
| C40 | reads | C3 | reads the typed map — its pin, every anchor-bearing element, and the grouping, flows and links a hit spreads along — as the graph a diff is projected onto | [impact_lib.py](tools/coyodex/impact_lib.py:212) |
| C40 | calls | C5 | parses every stored anchor into a comparable path and line range, and drops the prose ones that only look like a path | [impact_lib.py](tools/coyodex/impact_lib.py:189) |
| C40 | reads | C9 | reads the symbol-extent table out of the pre-index document, so a hit can name the enclosing definition instead of only the file | [impact_git.py](tools/coyodex/impact_git.py:202) |
| C40 | writes | E54 | records each changed file's fate from git's name-status output, keeping both names when a file moved | [impact_git.py](tools/coyodex/impact_git.py:82) |
| C40 | writes | E57 | collects one file pair's parsed diff, flagged binary when that pair can only ever resolve at file rung | [impact_lib.py](tools/coyodex/impact_lib.py:58) |
| C40 | writes | E56 | turns each diff header and its lines into one hunk expressed in the pin's coordinate frame | [impact_lib.py](tools/coyodex/impact_lib.py:66) |
| C40 | writes | E55 | folds the two diffs against the pin into the pin lines a change really affects, cancelling the hunks both sides share | [impact_lib.py](tools/coyodex/impact_lib.py:135) |
| C40 | writes | E58 | indexes every anchor the map carries into the seed set a change can hit, keeping which element and which field each came from | [impact_lib.py](tools/coyodex/impact_lib.py:196) |
| C40 | writes | E59 | records each hit at the finest rung that honestly holds — the line, the enclosing definition, or just the file — and marks a moved-but-unchanged anchor as drift rather than a change | [impact_lib.py](tools/coyodex/impact_lib.py:353) |
| C40 | writes | E53 | records one changed file as the engine sees it: its target-side name, its name in the pin's frame, its fate, its line frame and the elements it hit | [impact_git.py](tools/coyodex/impact_git.py:244) |
| C40 | writes | E52 | assembles the projection's whole result — the points it is expressed between, every changed file, and a warning for anything it could not do exactly | [impact_git.py](tools/coyodex/impact_git.py:228) |
| C40 | reads | E60 | keeps the noisy links — read-only data links, the entity graph, the transitive call graph — switched off unless the caller asks for them | [impact_ripple.py](tools/coyodex/impact_ripple.py:276) |
| C40 | reads | E12 | walks the map's backbone links to learn which entities a hit component owns and which components it can reach | [impact_ripple.py](tools/coyodex/impact_ripple.py:138) |
| C40 | reads | E6 | expands every flow, inlining its sub-flow references, to learn which use cases each hit element's steps belong to | [impact_ripple.py](tools/coyodex/impact_ripple.py:102) |
| C40 | writes | E61 | accumulates, per reached element, the strongest cause that found it, how far it came, and the path it came by | [impact_ripple.py](tools/coyodex/impact_ripple.py:174) |
| C31 | reads | E1 | reads a stored map straight off disk to answer a lookup — the whole document, one element's record, the links at a node, or a group's members | [dump.py](tools/coyodex/dump.py:153) |
| C31 | calls | C3 | parses every map it reads through the one model loader and re-serializes the whole-map dump through the one canonical writer, so a dump is exactly what the file holds | [dump.py](tools/coyodex/dump.py:158) |
| C32 | calls | C24 | asks the local map server for everything the overlay shows: a base-to-target diff projected onto the map, the pin's neighbouring commits for the picker, and one changed file's diff rows | [viewer.js](tools/coyodex/viewer/viewer.js:6851) |
| C32 | reads | E61 | reads each element's impact verdict out of the returned run — direct or rippled, its strength, its rung and its provenance chain — and turns it into the badge, the summary row and the 'why is this hit' explanation | [viewer.js](tools/coyodex/viewer/viewer.js:6720) |
| C32 | calls | C23 | drives the diagram for an armed diff — lands on the view that carries the overlay, stamps a change badge on every impacted box, and forces the redraw when a new range or ripple depth is picked | [viewer.js](tools/coyodex/viewer/viewer.js:6867) |
| C32 | writes | C37 | takes the element info pane over with the impact summary — every element the diff reached, grouped by kind, each row a link into its home view | [viewer.js](tools/coyodex/viewer/viewer.js:6805) |
| C32 | calls | C38 | puts the change dots on the file browser's rows, offers the changed-files-only filter, and re-opens the shown file so a changed one reads as an inline diff | [viewer.js](tools/coyodex/viewer/viewer.js:6866) |
| C45 | calls | C3 | loads every map it scores through the product's own model loader, so the eval never reads a map with a second grammar | [profile.py](eval/tools/coyodex_eval/profile.py:122) |
| C45 | calls | C10 | measures a map's well-formedness with the shipped validator, and reuses its entry-point and flow-coverage helpers for the completeness counts | [profile.py](eval/tools/coyodex_eval/profile.py:154) |
| C45 | calls | C12 | counts a map's contradictions and advisories with the shipped auditor, and takes its risk-ranked claim worklist as both a profile signal and the judge's input list | [profile.py](eval/tools/coyodex_eval/profile.py:131) |
| C45 | calls | C11 | measures a map's coverage of the source tree with the same helper the validator's coverage check runs | [profile.py](eval/tools/coyodex_eval/profile.py:141) |
| C45 | calls | C9 | re-derives the code's own component expectation from the repo tree at scoring time, so the granularity check is anchored in the code rather than in the baseline map | [profile.py](eval/tools/coyodex_eval/profile.py:143) |
| C45 | calls | C13 | takes the diagram fan-out and nesting depth a map would render at as report-only balance signals in the profile | [profile.py](eval/tools/coyodex_eval/profile.py:149) |
| C45 | calls | C20 | renders each archived run's markdown view and diagram graph from the frozen model, so a past run stays readable after a later rebuild | [run.py](eval/tools/coyodex_eval/run.py:158) |
| C45 | calls | C22 | builds the served viewer's data snapshot for each archived run, so the run keeps its own diagram data | [run.py](eval/tools/coyodex_eval/run.py:131) |
| C45 | calls | C46 | drives the scoring half — aggregating the orchestrator's raw judge votes, then gating the fresh profile against the baseline for the run's verdict | [run.py](eval/tools/coyodex_eval/run.py:67) |
| C45 | persists | D2 | keeps every eval run in the project's ignored eval folder — the frozen map, its generated views, the profile, the judge report and the delta — and reads the blessed baseline back from the same tree | [run.py](eval/tools/coyodex_eval/run.py:161) |
| C45 | writes | E63 | produces the deterministic profile of every map it scores — the counts, findings, coverage, granularity and density two runs are compared on | [profile.py](eval/tools/coyodex_eval/profile.py:162) |
| C45 | writes | E62 | assembles one run's outcome — its profile, its judge report, its comparison against the baseline, and the verdict that follows | [run.py](eval/tools/coyodex_eval/run.py:69) |
| C45 | reads | E64 | loads the judge report the orchestrator produced, and the baseline's cached one, to attach to a run and hand to the comparison | [run.py](eval/tools/coyodex_eval/run.py:228) |
| C46 | calls | C12 | draws the claims it grounds from the auditor's risk-ranked worklist instead of extracting claims a second way | [judge.py](eval/tools/coyodex_eval/judge.py:234) |
| C46 | calls | C3 | loads the map through the product's model loader before selecting which claims to ground | [judge.py](eval/tools/coyodex_eval/judge.py:234) |
| C46 | calls | C5 | compares each confirmed claim's stored anchor against the line the skeptics actually read, turning anchor drift into a measured rate that is kept separate from truth | [judge.py](eval/tools/coyodex_eval/judge.py:250) |
| C46 | writes | E64 | aggregates raw skeptic votes and rubric scores into the judge report — pass-rate, medians, drift rate, and the fingerprint that says two reports were judged the same way | [judge.py](eval/tools/coyodex_eval/judge.py:257) |
| C46 | writes | E69 | produces the comparison outcome — which hard checks failed, which numbers drifted, what could not be compared, and the single verdict | [compare.py](eval/tools/coyodex_eval/compare.py:332) |
| C46 | reads | E63 | diffs the blessed baseline's profile against the fresh candidate's to derive every hard check and drift band | [compare.py](eval/tools/coyodex_eval/compare.py:238) |
| C46 | reads | E74 | reads the gate settings — which checks block, how far each count may drift, how much a judged score may fall — merging per-project overrides onto the built-in defaults | [compare.py](eval/tools/coyodex_eval/compare.py:374) |
| C46 | reads | D2 | reads the gate settings file and, on the direct compare path, the two profile files it is asked to diff, straight off disk | [compare.py](eval/tools/coyodex_eval/compare.py:436) |
| C41 | reads | D3 | finds and reads the conversations that produced a map in the agent's session store — by the stamped session id, or by scanning the store for the session that wrote the map when nothing was stamped | [map_backup.py](tools/map_backup.py:232) |
| C41 | persists | D2 | writes the map's provenance record into the repo, and later the backup bundle — copied map files, transcripts and a manifest — under the coyodex clone's backup folder, removing the source only after the copy is in place | [map_backup.py](tools/map_backup.py:409) |
| C41 | calls | D1 | asks git for the analyzed repo's short HEAD sha and that commit's date, so a provenance stamp records which code state the map describes | [map_backup.py](tools/map_backup.py:145) |
| C2 | routes-to | C1 | sends the agent into the method docs in the clone, which hold the actual instructions | [SKILL.md](skill/coyodex/SKILL.md:28) |
| C2 | uses | C30 | points every tool run at the clone's virtualenv `coyodex` command | [SKILL.md](skill/coyodex/SKILL.md:24) |
| C30 | calls | C8 | routes the reconcile, anchor-drift and fix subcommands to the post-assemble edit tools | [cli.py](tools/coyodex/cli.py:105) |
| C25 | persists | E51 | keeps the remembered project folders, reloading before every change so a concurrent build merges instead of clobbering | [recents.py](tools/coyodex/viewer/recents.py:44) |
| C25 | persists | D2 | writes and re-reads the remembered-projects file in the user's home folder | [recents.py](tools/coyodex/viewer/recents.py:44) |
| C25 | writes | E50 | builds the file-tree nodes the browser pane renders, folders before files, with map coverage overlaid | [filetree.py](tools/coyodex/viewer/filetree.py:147) |
| C25 | calls | C9 | walks the mapped repo's source files through the pre-index's shared file walker | [filetree.py](tools/coyodex/viewer/filetree.py:218) |
| C24 | calls | D6 | opens the landing page in the developer's browser on start and serves the map UI to it from there on | [serve.py](tools/coyodex/viewer/serve.py:740) |
| C24 | reads | D2 | reads each mapped project's map file and the shared frontend assets off the local disk | [serve.py](tools/coyodex/viewer/serve.py:121) |
| C23 | calls | C24 | fetches this map's whole view bundle from the local server at boot, and everything it draws comes from that one payload | [viewer.js](tools/coyodex/viewer/viewer.js:107) |
| C23 | calls | D16 | turns every pre-rendered diagram source into the SVG the canvas shows | [viewer.js](tools/coyodex/viewer/viewer.js:4562) |
| C23 | calls | D17 | wraps each rendered diagram so the reader can pan and zoom it, and restores where they left the camera | [viewer.js](tools/coyodex/viewer/viewer.js:4626) |
| C23 | reads | D4 | loads the pinned diagram and pan-zoom libraries from it, integrity-checked, when the viewer page opens | [viewer.html](tools/coyodex/viewer/viewer.html:16) |
| C23 | calls | C37 | fills the side info pane with whichever element the reader selects on the canvas | [viewer.js](tools/coyodex/viewer/viewer.js:4611) |
| C23 | routes-to | C38 | opens the code viewer on the file and line behind any source anchor clicked on the canvas or in the pane | [viewer.js](tools/coyodex/viewer/viewer.js:152) |
| C24 | reads | D1 | runs read-only git commands so every file and listing it serves comes from the commit the map is pinned to | [serve.py](tools/coyodex/viewer/serve.py:180) |
| C24 | calls | C20 | turns each served project's map document into the viewer's graph | [serve.py](tools/coyodex/viewer/serve.py:397) |
| C24 | calls | C22 | builds the per-project view bundle it answers the view route with, and caches it per map version | [serve.py](tools/coyodex/viewer/serve.py:399) |
| C24 | calls | C25 | builds the file-browser tree of the commit's files, shaded by map coverage | [serve.py](tools/coyodex/viewer/serve.py:384) |
| C24 | reads | E1 | loads each served project's map document from its map folder, and reloads it when the file changes on disk | [serve.py](tools/coyodex/viewer/serve.py:397) |
| C20 | reads | E1 | walks the whole map document — every element, relationship and reference table — to derive the viewer's graph | [views.py](tools/coyodex/views.py:684) |
| C20 | writes | E41 | builds one graph node for every mapped element the diagrams draw | [views.py](tools/coyodex/views.py:472) |
| C20 | writes | E42 | builds one graph edge for every authored relationship and every domain relation | [views.py](tools/coyodex/views.py:791) |
| C20 | writes | E40 | assembles the finished graph payload every diagram generator and the whole frontend read | [views.py](tools/coyodex/views.py:850) |
| C22 | calls | C26 | asks it for the context and subsystem diagram sources the bundle carries | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2778) |
| C22 | calls | C27 | asks it for the domain-model diagram sources the bundle carries | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2821) |
| C22 | calls | C28 | asks it for the deployment and messaging diagram sources the bundle carries | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2828) |
| C22 | calls | C29 | asks it for the Happy Path and per-use-case flow diagrams the bundle carries | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2840) |
| C22 | calls | C21 | parses the optional change-impact report beside the map into the overlay the bundle carries | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2775) |
| C22 | reads | E40 | reads the graph — its commit, title and which layers exist — to decide and assemble what the bundle holds | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2785) |
| C22 | reads | D1 | asks git for the mapped repo's root and its GitHub remote, so the viewer's source links resolve out of the box | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:57) |
| C21 | reads | D2 | reads the change-impact report markdown that sits next to the map | [build_graph.py](tools/coyodex/viewer/build_graph.py:239) |
| C21 | writes | E48 | produces the parsed change-impact overlay the viewer badges the diagram with | [build_graph.py](tools/coyodex/viewer/build_graph.py:277) |
| C21 | writes | E49 | classifies each reported element as added, modified or deleted | [build_graph.py](tools/coyodex/viewer/build_graph.py:254) |
| C29 | reads | E44 | reads each use case's flow to draw it as a sequence diagram | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2597) |
| C37 | reads | E41 | reads the selected element's stored name, type and annotation to fill the info pane | [viewer.js](tools/coyodex/viewer/viewer.js:1072) |
| C38 | calls | C24 | fetches the repo's file tree and every file's text from the server, which serves both at the map's commit | [viewer.js](tools/coyodex/viewer/viewer.js:5806) |
| C38 | calls | D18 | colours the fetched source by language before laying it out line by line | [viewer.js](tools/coyodex/viewer/viewer.js:5650) |
| C38 | reads | D5 | lazily loads the pinned syntax highlighter and its stylesheet from it, the first time a file is shown | [viewer.js](tools/coyodex/viewer/viewer.js:5407) |
| C38 | calls | D7 | opens the shown file's blob page there, pinned to the map's commit and line | [viewer.js](tools/coyodex/viewer/viewer.js:6024) |
| C38 | calls | D8 | hands the shown file and line to the developer's own editor through its URL scheme | [viewer.js](tools/coyodex/viewer/viewer.js:6021) |
| C38 | reads | E41 | reads the elements anchored in the shown file so each is tagged on its own source line | [viewer.js](tools/coyodex/viewer/viewer.js:5496) |
| C39 | calls | C24 | fetches the code-symbol index from the server the first time search opens, so definitions are searchable too | [viewer.js](tools/coyodex/viewer/viewer.js:6325) |
| C39 | calls | C38 | opens a file or code-symbol hit straight in the code viewer at its line | [viewer.js](tools/coyodex/viewer/viewer.js:6345) |

---

## Test completeness — gaps against the map

> **Tests run for this table?** The suite was NOT run to build this table — every row is inferred by reading the test files and the code they exercise, never from a coverage run or an observed pass. That means a cited suite may touch a code path without asserting the behaviour named here, and an untested verdict is a reading of the test corpus rather than a proven absence; only running the suite with coverage would upgrade any row to verified.

| Target | Tested? | Test(s) | Gap / risk | Confidence |
|---|---|---|---|---|
| State-changing POST endpoints: CSRF header, request-body cap, open/forget/reorder handlers (Map server) | no | [test_serve.py](tests/test_serve.py:142) — drives the recents store directly (add / remove / dedupe / persist) — the state the POST handlers mutate, but never through an HTTP POST · [test_serve.py](tests/test_serve.py:194) — reorder semantics asserted on the store object, bypassing the /api/reorder route and its guard | Nothing in the corpus issues an HTTP POST. The custom-header CSRF guard, the 403 it returns when the header is absent, the 64KB Content-Length cap and the malformed-body path, and the /api/open folder gate (must contain a .coyodex/ dir), /api/forget and /api/reorder handlers are all unexercised end to end. This is the product's only write surface reachable from a browser: if the header check regressed to a no-op, every test still passes and any web page the developer visits could add or forget projects — and adding a project makes that folder's git-tracked contents servable. | inferred |
| Filesystem browser (/api/browse) — the unconfined path walk (Map server) | partial | [test_serve.py](tests/test_serve.py:255) — asserts the directory lister flags a .coyodex/ folder and offers a parent entry, called as a plain function on a temp dir | Only the lister function is tested, never the route. Untested: that an arbitrary absolute path or ~-expansion is accepted with no root and no allowlist, that a non-directory yields 404, that symlinked directories are skipped and unreadable entries dropped, and that file NAMES never leak (only subfolders). The map itself calls this the weakest surface in the product; the deliberate absence of a containment check is exactly the property no test pins down, so a future change that started returning file names or file contents here would break nothing. | inferred |
| DNS-rebinding guard actually enforced on every request (Map server) | partial | [test_serve.py](tests/test_serve.py:90) — table-tests the loopback-host predicate itself: absent Host allowed, localhost/127.0.0.1/[::1] allowed, evil.com and a LAN address refused · [test_serve.py](tests/test_serve.py:385) — drives real HTTP GETs against a live server, but only on the happy path — every request carries a loopback Host | The predicate is tested; the WIRING is not. No test sends a request with a foreign Host header and asserts a 403, on either the GET or the POST dispatch. A refactor that dropped the guard call from either entry point would leave the whole suite green while re-opening the rebinding path to every served repo's source. | inferred |
| Editor hand-off URI scheme allowlist in the viewer (File browser & code viewer) | no | [test_viewer_js.py](tests/test_viewer_js.py:33) — runs `node --check` over the frontend bundle — a syntax gate only, it never executes a line | The repo has no JS test harness, so the scheme allowlist that keeps a user-typed editor template from putting javascript:, data:, file: or http(s): into an anchor href is completely unexercised, as is the second check the Settings dialog runs on save. This guard is client-side and its only defence is that one allowlist; a typo that widened or skipped it would ship silently, and the whole viewer's behaviour is likewise unasserted beyond the file parsing. | inferred |
| Diagram label sanitizer — the single chokepoint against map-supplied script injection (View bundle assembler, Context & subsystem diagram generator, Domain diagram generator, Deployment & messaging diagram generator, Behavioural flow generator) | no | [test_grouping.py](tests/test_grouping.py:2012) — asserts relation-label TEXT for foreign keys and keyed-by, i.e. what a label says — not that quotes, backticks, brackets, braces, pipes or angle brackets are neutralised · [test_gen_deployment.py](tests/test_gen_deployment.py:165) — generates deployment and overview diagrams from built maps, so labels pass through the sanitizer incidentally, but no assertion targets the escaping | No test feeds a hostile name (a `<script>` tag, a quote, a pipe) through label generation and asserts the output is neutralised, and no test asserts that every generator routes its labels through the one sanitizer. The diagram renderer runs with HTML labels enabled, so a single generator that builds a label by hand is a script-injection path into the viewer, driven by text an agent wrote into the map. The map names this as the concentrated risk and nothing pins it. | inferred |
| Source read at the pinned commit (/api/src) — traversal rejection and the size cap (Map server) | partial | [test_serve.py](tests/test_serve.py:101) — the path guard: empty, absolute, `..` traversal at head and mid-path, backslash and NUL byte all rejected · [test_serve.py](tests/test_serve.py:113) — real temp git repo — listing and showing a blob at a SHA, with a missing path and an unsafe path both returning nothing · [test_serve.py](tests/test_serve.py:123) — blob size distinguishes file from directory from missing, and refuses an unsafe path before any git call · [test_impact_serve.py](tests/test_impact_serve.py:89) — drives /api/src over HTTP for both the worktree frame and a SHA frame | The guards are well covered as functions and the route is reached over HTTP, but no test asserts the 413 refusal for a blob over the 4MB cap, nor that the size check happens BEFORE the blob is buffered — the ordering that keeps a huge file from being read into memory. Also unasserted: the 400 on a bad path and the 404 on a path absent from the commit, as HTTP status codes rather than helper return values. | inferred |
| Working-tree file read — repo containment, .git exclusion, gitignore respect (Map server) | yes | [test_impact_serve.py](tests/test_impact_serve.py:61) — a tracked file and an untracked-but-not-ignored file are both served from the working tree · [test_impact_serve.py](tests/test_impact_serve.py:70) — the three refusals in one place: a gitignored file, anything under .git, and a path escaping the repo root | The named refusals are asserted, but not the symlink case the design calls out — no test plants a tracked symlink pointing outside the repo and checks the resolved real path still refuses it. That is the specific escape the containment check exists for, and it is the one route in the product that touches real disk instead of git objects. | inferred |
| Git argument injection through commit values and user-supplied refs (Map server) | yes | [test_serve.py](tests/test_serve.py:80) — the commit validator rejects a leading dash, a `--output=` flag smuggle, a ref name and a path-suffixed SHA; accepts short and full SHAs · [test_impact_serve.py](tests/test_impact_serve.py:162) — the ref resolver over the impact base/target parameters, including injection-shaped input | Both validators are asserted, but nothing asserts the second layer — that git is always invoked as an argument list with no shell, and that the `--end-of-options` terminator is present on the rev-parse call. Those are the defences that hold if the character class is ever widened, and a refactor could drop them invisibly. | inferred |
| Validator blocking rules — the gate a wrong map must not pass (Map validator, Source & coverage grounding checks, Validation run & CLI, Advisory adjudication readers) | yes | [test_validate_model.py](tests/test_validate_model.py:521) — roughly 186 tests across referential integrity, anchor syntax, entry-point kind and cadence contracts, structured stores, flow-step call sites, sub-flows, use-case and Happy-Path completeness, deployment and coverage walls · [test_operative_lines.py](tests/test_operative_lines.py:114) — the anchor-quality check: a definition-header anchor is flagged, an operative line accepted, and the check stays advisory rather than blocking · [test_granularity.py](tests/test_granularity.py:174) — the granularity advisory recomputed inside validate, asserted as non-fatal | Every row is built from a synthetic map constructed to trip one rule, so the suite proves each rule fires on its own trigger — it cannot show the absence of a false PASS, which is the failure that matters here (a wrong map shipping as validated). Nothing runs the validator against this repo's own committed map as a fixture, and nothing asserts the process exit-code contract that callers and CI actually branch on. | inferred |
| Fragment assembly — duplicate-id refusal, merge determinism, dedup and edge collapse (Fragment assembler) | yes | [test_assemble.py](tests/test_assemble.py:131) — the same id in two fragments is reported as a conflict rather than silently overwritten · [test_assemble.py](tests/test_assemble.py:365) — the CLI fails on duplicate ids AND writes nothing — the property that keeps a half-assembled map off disk · [test_assemble.py](tests/test_assemble.py:58) — arrays concatenate, singletons are taken, and conflicting singletons are a conflict · [test_assemble.py](tests/test_assemble.py:91) — component dedup merges same-file entries and repoints test targets; edges collapse only when call sites match · [test_assemble.py](tests/test_assemble.py:217) — a malformed fragment fails alone, named by its own path, instead of poisoning the run | The refusal is proven for ids within the fragment set, but not for the crash-mid-write case: no test interrupts the write and checks the previous map survived, and no test asserts the write is atomic. Also unasserted: what happens when a fragment file appears or changes during assembly, and whether the 'writes nothing' guarantee holds for the generated markdown view and pre-index as well as the JSON. | inferred |
| Reconcile and fix — the in-place edits to a stored map (Reconcile & post-assemble fixes) | partial | [test_assemble.py](tests/test_assemble.py:414) — reconcile directives assign fields and survive a reassemble; unknown ids, wrong kinds and bad parents are rejected; zero-match drops warn without failing · [test_assemble.py](tests/test_assemble.py:490) — malformed directives are refused at load · [test_fix.py](tests/test_fix.py:49) — apply-drift rewrites a drifted security anchor, leaves paired persists/reads edges alone, and skips an ambiguous multi-where edge · [test_fix.py](tests/test_fix.py:130) — drop-edge removes the edge, reports riding flow steps, heals them on repoint, and errors on a missing edge · [test_reconcile_build.py](tests/test_reconcile_build.py:49) — the rule language: glob depth, override order, wrong-typed ids reported, rules that match nothing reported, and a leading `**` that cannot sweep the whole map | The transformations are well covered but the WRITE is not. These verbs rewrite the repo's only copy of the map in place: no test asserts the write is atomic, that a failure mid-write leaves the original intact, or that a backup exists. Contrast the archive script, where exactly that rollback property IS tested. A partial write here silently destroys a map that took a full agent fan-out to build. | inferred |
| Change-impact engine and ripple — diff parsing, anchor resolution, and what a hit reaches (Analyze a code change against the map, Change-impact engine) | yes | [test_impact.py](tests/test_impact.py:124) — diff parsing, cancelling identical edits, the anchor-resolution ladder, enclosing-extent innermost-wins, renames with and without edits, deletions, untracked files and cross-commit cancellation · [test_impact_ripple.py](tests/test_impact_ripple.py:96) — a component hit ripples to structure, behaviour and data; data does not chain; entity hits reverse into subdomains; step hits stay inside their use case; sub-flow steps reach every referencing use case · [test_impact_ripple.py](tests/test_impact_ripple.py:236) — the impact API endpoint end to end · [test_diffmap.py](tests/test_diffmap.py:10) — unified-diff line numbering, added files, preamble skipping and the no-newline marker · [test_anchor_drift.py](tests/test_anchor_drift.py:20) — drift detection on confirmed claims, with the corrected anchor recorded | Ripple rules are asserted on hand-built miniature maps of a few elements. Nothing checks the ripple against a real map at real scale, where the risk is not a wrong rule but an overwhelming or misleading result — the map itself frames a wrong ripple as sending a reader to the wrong code. Also unasserted: the callgraph opt-in's decay behaviour beyond one depth case, and any bound on ripple size. | inferred |
| Map backup with its build transcript (Back up a map with its build transcript, Map backup & provenance) | no |  | No test file references the backup tool at all. The whole use case is unexercised: finding the session id in the provenance file, locating the matching transcript, bundling it with the map, and every failure mode (missing provenance, a session id that matches nothing, a partially written bundle). This is the only path that preserves how a map was built; if it silently produces an empty or mismatched bundle, nothing catches it. Note that the archive script, a DIFFERENT tool, is well covered and is easy to mistake for this one. | inferred |
| Installing the skill — manifest path baking and the repo-local environment (Install the coyodex skill, Method docs, Agent skill manifest) | no | [test_granularity.py](tests/test_granularity.py:213) — asserts the method doc still carries the leaf rule — a docs-content check, not an install check | Nothing exercises the install target: that the skill manifest lands in the agent's skills folder, that this clone's path is baked into it correctly, that the virtualenv gets the command, or that reinstalling and uninstalling are clean. A broken install makes the whole product unreachable for a new user, and it is the first thing anyone does. Only the CONTENT of the method docs is checked, never the wiring. | inferred |
| Exploring a map top-down in the browser — drill navigation, info pane, search (Explore a map top-down, Diagram canvas & drill navigation, Element info pane & selection, Map search sidebar) | no | [test_viewer_js.py](tests/test_viewer_js.py:33) — `node --check` parses the bundle so a stray syntax error cannot ship — no execution · [test_viewer_js.py](tests/test_viewer_js.py:37) — a grep-style check that no internal model field name is rendered into the UI · [test_viewer_js.py](tests/test_viewer_js.py:61) — a grep-style check that source links are bound by one delegated listener rather than per render | The repo has no JS test harness by design, so the entire browser viewer — drilling from one diagram level into the next, selecting an element and rendering its pane, the search sidebar — has zero behavioural coverage. The three existing checks are a parser gate and two text greps; they would not notice a drill that navigates to the wrong level or a pane that renders the wrong element. This is the primary way a human consumes a map. | inferred |
| Seeing a change ripple in the viewer — the impact overlay (See what a change ripples to in the viewer, Change-impact overlay) | partial | [test_impact_serve.py](tests/test_impact_serve.py:112) — the commit picker's data: ancestors and descendants of the pin · [test_impact_serve.py](tests/test_impact_serve.py:130) — one file's inline diff across an arbitrary commit range · [test_impact_ripple.py](tests/test_impact_ripple.py:236) — the impact endpoint the overlay consumes, end to end | The server half is covered; the browser half is not. Nothing asserts that the overlay lights the right nodes for a given impact payload, that picking two commits drives the right request, or that the in-place diff view renders. A correct payload rendered onto the wrong boxes is indistinguishable from a correct result to every test here. | inferred |
| Starting the local map server — bind, startup registration, browser launch (Start the local map server) | no | [test_serve.py](tests/test_serve.py:385) — stands up the request handler on an ephemeral port directly, bypassing the runner entirely | No test calls the serve runner. Untested: that the bind address is 127.0.0.1 rather than all interfaces (the map states this hardcoded bind IS the access control), the default port and what happens when it is taken, the folders passed on the command line being registered at startup, and the optional browser launch. A regression that widened the bind to 0.0.0.0 would expose every served repo to the network and no test would fail. | inferred |
| Accepting a change into the baseline (Accept a change into the baseline) | no | [test_assemble.py](tests/test_assemble.py:345) — the assemble CLI writes a canonical map plus its generated views — one step of the accept sequence, run on its own | The accept flow is orchestrated by the agent skill, so no test covers the sequence: patch the model in place, re-pin to the new commit, re-run the gates, regenerate the markdown view and pre-index, commit. Untested in particular is the ordering guarantee — that the gates run BEFORE the commit — and what state the map is left in when a middle step fails. This path rewrites the committed baseline, so a partial accept ships a map that no longer matches its pin. | inferred |
| Building a baseline map end to end, and the per-fragment lint that gates it (Build a baseline map of a repo, Fragment linter) | partial | [test_lint_fragment.py](tests/test_lint_fragment.py:24) — anchor and extra misuse in one pass, malformed ids refused at load, unknown references against the id universe, unknown-prefix targets, and the warning-vs-problem split · [test_lint_fragment.py](tests/test_lint_fragment.py:148) — the completeness family never fires per fragment — the boundary between lint and validate · [test_lint_fragment.py](tests/test_lint_fragment.py:208) — the lint CLI exit codes · [test_assemble.py](tests/test_assemble.py:332) — the assemble CLI writes the fragments gitignore and the canonical map with its views | Every stage is tested alone; the build as a whole is not. No test walks pre-index to fragments to lint to assemble to validate on a fixture repo and asserts a committed, commit-pinned map comes out. That means stage-boundary defects — a fragment shape lint accepts but assemble mishandles, or a map assemble writes that validate then rejects — are invisible, and they are exactly the failures an agent hits mid-build. | inferred |
| Opening the source behind a mapped element — file tree, coverage overlay, code read (Open the source behind a mapped element, File browser, recents & diff rows) | partial | [test_filetree.py](tests/test_filetree.py:54) — the path index strips anchors and skips URLs, resolves collisions leaf-first, and maps owned files to their owner · [test_filetree.py](tests/test_filetree.py:121) — tree nesting and ordering, coverage shading including the partial case, mapped counts summed at each level, and the click target picking the finest ancestor folder · [test_serve.py](tests/test_serve.py:272) — the git-backed tree built from a real commit · [test_serve.py](tests/test_serve.py:294) — symbol flattening from the pre-index, with missing and malformed pre-index both degrading to empty rather than failing | The backend that finds and serves the file is covered; the claim the use case makes is not. Nothing asserts that clicking a given element's anchor lands on the file and LINE that grounds it — the round trip from a map anchor to a scrolled code view lives entirely in the untested frontend. The hand-off to an editor or GitHub is likewise unasserted. | inferred |
| Changing the map on request in plain language (Change the map on request) | partial | [test_reconcile_build.py](tests/test_reconcile_build.py:126) — rule output feeds the reconcile step unchanged, and the coverage report names elements left unassigned · [test_fix.py](tests/test_fix.py:162) — dedup-relation lists both sides then drops the chosen one | The mechanical verbs are covered, but the use case's stated guarantee — that the agent refuses anything the code does not back, and that a requested edit passes the same gates as any other write — has no test. Nothing asserts that a surgical edit is re-validated before it lands, so an edit that satisfies a directive while breaking referential integrity depends on the operator remembering to re-run the gate. | inferred |
| Method-quality eval — profiling, judging, comparison gates and the runner (Check the method's quality, Eval runner, Eval scoring) | yes | [test_compare.py](eval/tests/test_compare.py:57) — the gate matrix: new validate problems and contradictions regress, coverage and auth-surface drops regress, bands and density collapse, granularity gating the candidate only, judge pass-rate and dimension-score drops, and hard-fail precedence · [test_judge.py](eval/tests/test_judge.py:335) — grounding majority vote with dissenters, ties, failed and unverifiable votes; the sampling cap keeping the highest-risk claims; protocol fingerprinting; median and mean score assembly · [test_profile.py](eval/tests/test_profile.py:691) — exact structural counts, completeness and granularity fields, density ratios, and old baselines without newer fields still loading · [test_run.py](eval/tests/test_run.py:107) — first run without a baseline, bless round trip, and the map-hash freeze that refuses a map edited after the run started · [test_model_pipeline.py](eval/tests/test_model_pipeline.py:90) — the model-format path end to end, including the protocol-cache guard and drift on a protocol mismatch | Judges are injected in every test, so the real LLM call, its prompt-to-parse round trip, retries and malformed-response handling are never exercised — the part most likely to break in practice. Nothing asserts the eval's own conclusion is meaningful: a scoring change that makes every map look good would still pass this suite. | inferred |
| Map model, grammar vocabularies, anchors and the JSON schema (Map model & serializer, Map grammar & vocabularies, Anchor & schema utilities, ProjectModel) | yes | [test_model.py](tests/test_model.py:157) — round-trip identity, deterministic serialization across builds, canonical key order, and every element keyed by id · [test_model.py](tests/test_model.py:215) — load refuses a wrong format, wrong types with a path, unknown fields, missing required fields and wrong or suffixed id prefixes · [test_model.py](tests/test_model.py:59) — id remapping reaches every referenced site including the store's dep reference · [test_anchors.py](tests/test_anchors.py:7) — anchor forms (file, file:line, file:range, extensionless, directory) and the drift tolerance rules · [test_json_schema.py](tests/test_json_schema.py:21) — the committed schema is not stale, every ref resolves, id patterns carry their array prefix, and a markdown link or retired hash anchor is rejected · [test_grammar_roles.py](tests/test_grammar_roles.py:15) — edge verbs map to roles per family, dep roles union incoming verbs, and entry-point kind aliases fold without ever folding a minted kind · [test_retired_parser.py](tests/test_retired_parser.py:53) — the retired v1 parser stays deleted and no command dispatches to it | Round-trip identity is proven for maps the suite builds, not for the repo's own large committed map — no fixture asserts it survives a load-and-write byte-identically at real scale. Unicode, very long strings and deeply nested extras are unexercised, and nothing asserts the id-remap covers a field added in future without being updated. | inferred |
| Code pre-index — weighting, symbol extraction, imports and compression advisories (Code pre-index) | yes | [test_preindex.py](tests/test_preindex.py:83) — weights count lines and files, exclude vendored code and lockfiles, and degrade without git · [test_preindex.py](tests/test_preindex.py:124) — symbol extraction reports all matches for an ambiguous name, records kind and line, and records a parse failure instead of swallowing it · [test_preindex.py](tests/test_preindex.py:155) — import edges reported as named pairs, dynamic imports honestly reported as a lower bound, and no false positive on a substring match · [test_preindex.py](tests/test_preindex.py:229) — the compression advisories: collapsed plugins, monorepo layout, small unreferenced folds, and the non-product dirs it skips | Symbol extraction is asserted mostly for Python, with non-Python languages covered by a single present-or-self-reported check — so a silently degraded extractor for another language reads as success. Nothing asserts behaviour on a very large tree, where the pre-index's cost and its truncation choices actually matter. | inferred |
| Map auditor and balance reporter — the advisory checks (Map auditor, Balance reporter) | yes | [test_audit.py](tests/test_audit.py:1320) — read-before-create and actor attribution stay advisory and never block, guarded against known false positives · [test_audit.py](tests/test_audit.py:1468) — the L2 worklist and its tiers: structured stores, messaging, state machines, cadence · [test_balance.py](tests/test_balance.py:72) — the small-map advisory, root and per-subsystem rules, homogeneity, the extras escape hatch, the subdomain forest mirror, graph machinery, naming, and its integration into validate | Both are advisory by design, so the tests prove they do not block — but nothing asserts their output is actionable or that they fire on the real map. An auditor that went quiet on every real defect while staying green here would look identical. | inferred |
| Views builder, graph builder and the diagram generators (Map views builder, Viewer graph builder, Context & subsystem diagram generator, Domain diagram generator, Deployment & messaging diagram generator, Behavioural flow generator) | yes | [test_grouping.py](tests/test_grouping.py:2012) — roughly 95 tests over the grouping and diagram-generation rules across context, subsystem and domain diagrams · [test_gen_deployment.py](tests/test_gen_deployment.py:38) — derived dep roles, injection, overview, environments, cards, process topology from the async catalog, co-residency, the all-in-one fold and the readable-cap container grouping · [test_data_view.py](tests/test_data_view.py:1) — the data view's entity, relation and store rendering · [test_convert_and_views.py](tests/test_convert_and_views.py:71) — golden equivalence over a real committed map fixture — the one place a full real map drives generation | Coverage is on generated STRUCTURE, not on whether a diagram is readable or correct to a human — a layout that renders every box on top of another would pass. The golden fixture pins one real map, so a change that improves that map's output while degrading every other shape reads as a pass, and the fixture must be refreshed by hand or it silently ossifies. | inferred |
| Recents store and served-project discovery (File browser, recents & diff rows) | yes | [test_serve.py](tests/test_serve.py:142) — add, remove, dedupe and persist; a missing file reads as empty; an external change made while the server runs is merged rather than clobbered; the same directory reached via a symlink dedupes · [test_serve.py](tests/test_serve.py:229) — loading a valid and an invalid project, and slug collisions resolved while invalid folders are skipped · [test_serve_fresh.py](tests/test_serve_fresh.py:41) — a map edited while the server runs is picked up; an unchanged map keeps the cached bundle; a broken edit keeps serving the old bundle and retries; a missing file keeps the cache · [test_serve.py](tests/test_serve.py:350) — the served view bundle and its cache, tolerating a malformed change report | The store is mutated from request threads behind a lock, but no test exercises concurrent writes — two simultaneous adds, or a reload racing an add. The dedupe and merge tests all run single-threaded, so a lock removed by refactor would not be caught. | inferred |
| Command front door and the model dump (CLI dispatcher, Model dump) | partial | [test_cli.py](tests/test_cli.py:63) — version flag, no-args usage, unknown command exit code 2, and dispatch propagating not-found and usage errors for validate, audit, balance, fix and render · [test_cli.py](tests/test_cli.py:38) — the core path does not import the heavy parser dependency — an import-cost guard · [test_dump.py](tests/test_dump.py:60) — resolving a component, group, entity and unknown id; edge slices in and out; group members; and the CLI's whole-dump, id-slice, unknown-id and two-slice-flag error paths | Only a subset of the twelve registered commands is dispatch-tested; the rest are reached only through their own module's tests, so a broken registration or a renamed flag on those would surface at runtime rather than in the suite. Argument parsing for the commands that take several flags is largely unasserted. | inferred |

---

## Grounding — how much of this map was challenged

**185 of 185 claim(s) challenged** by fresh-context skeptics — 182 confirmed, 3 refuted, 0 unverifiable.

> No `live_claims_digest`: nothing can confirm this record describes the map as it now stands.

Full Phase-4 coverage: all 185 L2 claims from the audit worklist were challenged by 8 fresh-context skeptics that never saw the build reasoning, batched by theme (security, external dependencies + persistence, domain ownership x2, backbone edges x2) and told to default to refuted on doubt. The 14 security claims were judged three times independently with different lenses — read-the-check, attack-the-surface, and prove-the-call-chain — and decided by majority; one skeptic verified them against a live throwaway server rather than by reading. 3 claims were refuted and reconciled: the /api/browse route has no containment of its own (re-anchored to the loopback Host guard that is its real barrier, with the gap stated), the pre-index builds rather than owns its per-directory expectation record, and the backup script copies the map folder without owning the map document (edge dropped). The ref-injection guard was confirmed real but anchored at a copy that never sees user input; its anchor was repointed. All 5 state machines were checked against their declaring lines and none was invented.

---

## Balance exceptions

- granularity: 36 components against a code-derived expectation of ~11 (band 6–16). The expectation is bound by the LOC ceiling over a 294-LOC median file, which reads a toolkit of single-purpose stdlib modules as far fewer units than it has. Each component here is one module or one clearly separable unit inside an oversized file (the 2.5 kLOC validator is four; the 2.9 kLOC viewer generator is five; the 6.9 kLOC browser app is five), each with its own job, its own command or view, and its own tests. Folding them to reach the band would hide exactly the pipeline this map exists to explain — the altitude is deliberate.
- store: the entities whose store mode is `transient`, `embedded`, `in-code` or `enum` deliberately carry no `dep`. This project has no database: the only physical store is the local filesystem, already linked on the eight entities that really land in a file. Tagging in-memory view, impact and eval structures with a filesystem dep would state a persistence that does not happen.
- UC2: 16 steps against the 3–15 band. This is the product's whole spine — read the method, size the tree, fan out, self-check each fragment, merge, apply the synthesis assignments, run the gates, ground the claims, stamp provenance, commit. The gate run is already extracted as a sub-flow (SF10) and counts as one; the remaining steps each carry a distinct call site, so compressing further would drop a real anchor rather than reduce altitude.

---

## Coverage exceptions

- tests/: the test suite is measured as coverage of the map's targets in the Tests table, not modelled as components of the product.
- eval/tests/: same — the eval's own test suite.
- assets/: two images used by the README.
- .github/: issue and pull-request templates only; there is no CI workflow in this repo.
- method/templates/: a documentation-only template showing the shape of the generated markdown view.

---

## Unclaimed surfaces

- C5: `python -m coyodex.json_schema` prints the generated JSON Schema of the map document. It is a maintainer/tooling surface for regenerating `method/project-map.schema.json` and for IDE autocomplete — no product use case runs it, and the schema it prints is documentation, not a gate (`coyodex validate`'s checks are hand-rolled and semantic). Deliberately off the use-case list rather than a dead surface.

---

## Persistence exceptions

- C41: the backup writes a BUNDLE, not a modelled record — a byte copy of the map folder, the conversation transcripts beside it, and a small manifest naming the project and build time. The bundle has no named type in the code (map_backup.py is stdlib-only and never parses the map), so there is no entity to link. This was confirmed by the grounding pass, which refuted the earlier claim that the backup owns the map document.

---

## Audit checks and the L2 worklist

`coyodex audit` exits 1 only on a CONTRADICTION-severity finding (`audit_model.py:593`). Everything else prints and exits 0.

**Blocking (CONTRADICTION)**
- `dangling-why-ref` — a step's `why:` cites a Happy-Path position that is not a step, or a use case that does not exist in the map (`audit_model.py:230`, `audit_model.py:242`).
- `backward-why-ref` — a step's `why:` cites a Happy-Path position that comes AFTER it in the walk (`audit_model.py:234`).

**Advisory / warning (never blocks)**
- `read-before-create` / `read-never-created` — a step reads an entity the walk writes later, or never (`audit_model.py:196`, `audit_model.py:202`). Advisory because component-granular attribution is lossy in both directions (`audit_model.py:142`).
- `forward-uc-why-ref` / `offspine-why-ref` — a use-case id in a `why:` may be ordinary prose, so blocking would fail a build on a sentence (`audit_model.py:256`, `audit_model.py:247`).
- `actor-attribution` — the flow's opening role id is not in the use case's declared actors (`audit_model.py:281`).
- `why-less-step` (WARNING) — a step states no precondition while its siblings do (`audit_model.py:296`).
- `dependency-phrasing` — step or edge text reads as "A needs B" instead of an action (`audit_model.py:318`, `audit_model.py:324`).

Findings print sorted by severity, then check, then location (`audit_model.py:336`).

**L2 worklist ranking** (highest risk first, then deduplicated by claim string at `audit_model.py:510`)
1. Auth-surface protection claims (`audit_model.py:411`).
2. `enforces` / `encrypts` edges — security-critical verbs (`audit_model.py:423`).
3. Component→external-dependency edges (`audit_model.py:430`), skipping deps explicitly folded as framework/library (`audit_model.py:431`).
4. Component→entity ownership edges (`audit_model.py:435`).
5. All remaining backbone edges (`audit_model.py:441`).
6. Appended after the edge tiers: entity store claims (`audit_model.py:458`), messaging-channel publisher/consumer claims (`audit_model.py:471`), state-machine claims (`audit_model.py:483`), and entry-point cadence claims (`audit_model.py:500`).

---

## Entry-point coverage

Attribution convention: every row is anchored on the line that REGISTERS or DISPATCHES the entry point, and belongs to the component that owns that line. So each `coyodex <cmd>` row sits on its `if cmd == …` line in the CLI dispatcher (C30), not on the implementing module's `main`; the only exceptions are the second-level `coyodex fix <verb>` rows (the verb table lives in the fix module, C8) and the two module-only commands that no dispatcher exposes.

- cli: complete — read the CLI dispatcher's dispatch chain top to bottom (12 `coyodex` subcommands), the fix module's verb table (3 verbs), the eval dispatcher's chain (8 `coyodex-eval` subcommands), `[project.scripts]` in `pyproject.toml` (2 console commands), the backup script's argparse subparsers (2), and then a repo-wide grep for `__main__` blocks to catch modules with a runnable `main` that the dispatchers do NOT expose — exactly two: the schema printer and the view-bundle debug dump. Not counted as rows: the global `--version` / `--help` flags, and the `Makefile` targets (`make dev` / `install` / `start`), which are build wrappers around these same commands and have no owning component.
- agent-skill: complete — a project-specific kind for the two agent-invoked skill manifests (`/coyodex`, `/coyodex-eval`); a coding agent, not a human shell, is the caller. Found by listing every `SKILL.md` in the repo (there are exactly two). The eval manifest is filed under the eval runner (C45) because no canonical component lists `eval/SKILL.md`.
- http-route: complete — walked the request handler's path dispatch in the map server end to end: the GET router (root → landing page; `/api/*` → recents + folder browser; `/static/<name>` → whitelisted assets; `/p/<slug>/…` → the shell and the per-project API branch, whose 8 endpoints are matched one by one), plus the POST router's 3-name whitelist. 16 routes. Any other verb falls through to the base handler's 501.
- middleware: complete — the three per-request hooks that run before any route body: the loopback-Host guard on GET, the CSRF-header guard on POST, and the map-staleness refresh on every project request.
- ui-route: sampled — the browser app is a 6900-line single file and was not read in full. Enumerated by grepping it for navigation and listener registrations (`location.`, `history.`, `addEventListener`, `data-view`) plus the button set in `viewer.html`. The app has NO hash routes and NO query-parameter deep links: one URL per project, and all navigation is in-page. The 6 rows cover the landing-page card click, the 10-way view tab bar (one row on the loop that binds every tab), search, the impact explorer, the file/code pane switch, and the title link home. Not recorded: the in-diagram drill gestures, breadcrumbs, back/forward history, the settings and help modals, and the keyboard shortcuts — all reached from inside an already-open view.
- startup-hook: complete — Pass-2 sweep for self-activation across the whole repo: grepped Python for `threading`, `Thread(`, `atexit`, `signal.`, `webbrowser`, `while True`, `cron`/`schedul`, and the browser app for `setInterval`, `setTimeout`, `EventSource`, and the observer APIs. Findings, asserted either way: the map server is the only long-running service, and it self-starts exactly three things — the accept loop (continuous), the thread-per-connection worker spawned by the threading HTTP server (folded into the accept-loop row; its trigger is an inbound request, not a schedule), and the optional `--open` browser launch. The browser app self-runs two boot steps (the view-bundle fetch that gates the whole module, and the one-shot server probe) and the landing page one. There are NO timers, NO polling loops, NO file watchers, NO signal handlers and NO `atexit` hooks anywhere in the repo: the only `signal`-shaped code is the audit vocabulary's word list, the server stops on a caught `KeyboardInterrupt` rather than an installed handler, freshness is checked per request rather than on a timer, the two `while True` loops outside the server are tree walks, and every `setTimeout` in the browser app is a UI animation or flash. `threading` is used only for a lock guarding the recents state.
- Kinds with nothing to record: `webhook`, `mcp-tool`, `job`, `poller`, `event-consumer`, `signal-handler` — no instance of any of them exists in this repo.
- Deliberately out of scope: `internal/` is git-ignored, so its scripts are not part of the committed repo the map is pinned to; the archive helper that lives there is therefore not recorded as an entry point.

---

## Viewer UI surfaces

What a reader can actually do in the browser viewer (each grounded in the line that implements it):

- **Switch view** — the tab row over the diagram (Happy Path · Use Cases · Subsystems · Entities · Dependencies · Data · Deployment · System · Glossary · Tests); a tab with no content is hidden, and clicking the tab you are already on resets it to its overview (`tools/coyodex/viewer/viewer.js:6674`).
- **Drill a box** — double-click or Option-click a subsystem / subdomain / process box to replace the diagram with that box's own card, at any depth (`tools/coyodex/viewer/viewer.js:3103`).
- **Click a box or arrow** — its detail fills the pane under the diagram, the element glows and everything unrelated fades (`tools/coyodex/viewer/viewer.js:1121`).
- **Cmd-click more elements** — each one stacks its own card in the pane instead of replacing the last (`tools/coyodex/viewer/viewer.js:454`).
- **Hover anything** — a small tooltip previews its meaning without changing the selection (`tools/coyodex/viewer/viewer.js:1799`).
- **Go back / forward** — the header arrows, Cmd+arrow or Option+arrow return each view to the zoom, position and selection it was left at (`tools/coyodex/viewer/viewer.js:5870`).
- **Pan and zoom** — scroll or drag to move, Ctrl/Cmd-scroll or pinch to zoom, and the header percentage button fits the diagram to the screen (`tools/coyodex/viewer/viewer.js:6681`, `tools/coyodex/viewer/viewer.js:6680`).
- **Walk a use-case flow** — on a flow view a small player steps through the actions one arrow at a time, also driven by the left/right arrow keys (`tools/coyodex/viewer/viewer.js:6682`).
- **Search everything** — press `/` or Cmd-K for elements, files, folders, glossary terms, fields and code symbols; `@` scopes to symbols of the open file (`tools/coyodex/viewer/viewer.js:6654`).
- **Browse the repo** — the file tree is shaded by map coverage; clicking a mapped row selects the matching element on the diagram (`tools/coyodex/viewer/viewer.js:4822`).
- **Read the source** — the code pane shows the file at the map's commit, syntax-highlighted, scrolled to the element's line (`tools/coyodex/viewer/viewer.js:5666`).
- **Open source links** — any `path:line` in the pane, the glossary or the System tables opens in the code viewer (`tools/coyodex/viewer/viewer.js:148`).
- **Open externally** — the ↗ control re-opens the shown file in your editor or on GitHub, configured once in the settings dialog (`tools/coyodex/viewer/viewer.js:5258`, `tools/coyodex/viewer/viewer.js:6114`).
- **Switch environment** — on the Deployment overview a floating picker dims what a chosen environment excludes, without redrawing (`tools/coyodex/viewer/viewer.js:3313`).
- **See a change overlay** — the Impact button projects any diff onto the map, with a ripple-depth choice and badged boxes (`tools/coyodex/viewer/viewer.js:6906`, `tools/coyodex/viewer/viewer.js:6928`).
- **Filter to changes** — the file browser can show only the files the active diff touched (`tools/coyodex/viewer/viewer.js:6704`).
- **Show or hide the legend** — the `?` beside the tabs toggles the one key for shapes and colours; the header `?` reopens the first-run gesture guide (`tools/coyodex/viewer/viewer.js:6128`, `tools/coyodex/viewer/viewer.js:6126`).
- **Pin the file browser** — keep it beside the code viewer instead of letting it share the slot (`tools/coyodex/viewer/viewer.js:6180`).
- **Clear the selection** — Escape, or a click on empty canvas (`tools/coyodex/viewer/viewer.js:5877`).


---

## The method as a program

coyodex ships two halves that only work together: prose the agent executes, and a CLI that checks what the agent wrote.

**Entry.** The installed skill manifest carries no method content — it pins this clone's absolute path and says to read `method/dispatch.md` and follow it (`skill/coyodex/SKILL.md:28`). `make install` bakes that path in by substituting `__COYODEX_HOME__` while copying the manifest into each skills home (`Makefile:56`), which is why the docs keep evolving without a reinstall.

**Dispatch decides the mode.** It first looks for an explicitly named verb — build, analyze, accept (`method/dispatch.md:14`). Otherwise it looks *only at the working tree* for `.coyodex/project-map.json`: no file means no baseline, and a deleted one must never be recovered from git (`method/dispatch.md:26`). With a baseline it defaults to Analyze and never silently rebuilds, because a rebuild overwrites curated work and the pin history (`method/dispatch.md:38`). A plain-language request to change the map itself is a fourth path, edited surgically into the model rather than regenerated (`method/dispatch.md:69`).

**The prose never writes the stored file.** Build sub-agents return JSON fragments and `coyodex assemble` serializes the model, so the stored map's validity comes from the tool, not from the agent's typing (`method.md:18`).

**Gates after every write.** The invariant — for Build, Accept *and* a direct map change alike — is validate, then audit, then render (`method/dispatch.md:89`). Validate checks schema and semantics and that the committed markdown view is fresh; audit is the adversarial pass that makes the narrative Happy Path and the mechanism flows refute each other, blocking only on a hard contradiction and printing a grounding worklist to disprove against the code (`method/dispatch.md:90`). Render regenerates the markdown view; the diagram is served live, never committed.

**Beyond the first build.** The same docs cover the lifecycle: Analyze writes an uncommitted report, Accept transcribes it into the model and bumps the pin (`method/change-impact.md:12`), while the impact engine computes the machine half of that picture from an arbitrary diff. The eval closes the loop by rebuilding a map with the current method and scoring it against the committed one — and it scores through the very same validate/audit pipeline the gates use, so there is only ever one grammar (`eval/tools/coyodex_eval/profile.py:129`).

---

## How the viewer reads source

Every element in the map stores a bare `path:line`; the graph view keeps the file and line on the node (`tools/coyodex/views.py:472`) and the component's owned files with anchors stripped (`tools/coyodex/views.py:115`), which is what the code-viewer switcher pages through.

- **The pin.** The map's own commit, `-dirty` stripped (`tools/coyodex/viewer/serve.py:124`), must be a bare hex SHA before any git call (`tools/coyodex/viewer/serve.py:99`) — a leading `-` would otherwise reach git's argv as a flag.
- **Opening a file.** `api/src` size-checks the blob (`tools/coyodex/viewer/serve.py:645`) then reads it with `git show <commit>:<path>` (`tools/coyodex/viewer/serve.py:650`), so the code a reader sees is the code the map was built from — local edits never leak in.
- **Browsing.** The file tree lists exactly what `git ls-tree` reports at that commit (`tools/coyodex/viewer/serve.py:383`, `tools/coyodex/viewer/serve.py:191`), overlaid with map coverage (`tools/coyodex/viewer/filetree.py:203`); a mapped row carries the element to select (`tools/coyodex/viewer/filetree.py:166`).
- **The one exception.** `api/src?at=<sha>|WORKTREE` serves another commit or the working tree for the impact explorer; worktree reads are contained by realpath (`tools/coyodex/viewer/serve.py:275`) and limited to files git accounts for, so an ignored `.env` is never served (`tools/coyodex/viewer/serve.py:281`).
- **Diffs.** One file's inline diff across an arbitrary range comes from `git diff` (`tools/coyodex/viewer/serve.py:325`) parsed into numbered rows (`tools/coyodex/viewer/diffmap.py:51`).
- **Hand-off to an editor / GitHub.** The per-project view bundle is built with the map's own `.coyodex/` folder as the source-link anchor (`tools/coyodex/viewer/serve.py:399`), which is where the repo-root and GitHub-URL link config comes from.
- **Reading the markdown view instead.** There, every stored bare anchor is emitted as a basename-labelled markdown link (`tools/coyodex/views.py:91`), so the committed file is clickable too.

---

## Validator advisory catalogue

Every NON-BLOCKING warning `coyodex validate` can print, with the `extras` heading that silences it durably.

**Silenced by a `Balance exceptions` heading** (the listed id or literal, at line start):

- flow / sub-flow outside the 3-15 step band — its `UC`/`SF` id
- component listing 6+ sub-units in its Purpose (altitude) — its `C` id
- diagram fan-out off the 5±2 target, sparse roots, single-child levels — the diagram id
- no flow step touches any entity — literal `entity-flows`
- self-activated entry points recording no cadence — literal `cadence`
- deployment units enumerated but nothing sets `runs_in`, plus the whole deployment-quality family (non-atomic unit names, formula-filled `runs_in`, unlinked units, ambiguous thread hosts, variant tagging) — literal `runs-in`; the suppressed COUNT is still printed
- emit/listen edges into a bus while the `messaging` catalog is empty — literal `messaging`
- components carrying no backbone edge and no channel role — literal `isolated`
- unstructured, dep-less or prose-named entity stores — literal `store`
- component count outside the ±40% granularity band (`--check-coverage`) — literal `granularity`

**Silenced by another named heading:**

- 4+ identical consecutive steps shared by two flows — `Accepted duplications` (`UC4 & UC9: <why>`)
- externally-activated entry points no use case reaches — `Unclaimed surfaces` (`C7: <why>`; `validate --emit-unclaimed` prints the whole block)
- role driving no on-spine use case / off-spine use case unrecorded — `Happy Path coverage` (`R2: <why>`)
- write edge into a store no entity explains — `Persistence exceptions` (`C3: <why>`)
- entry-point kind with no completeness statement — `Entry-point coverage` (`http-route: complete — <how enumerated>`)
- directory compression, absent dirs, uncovered loose files, under-harvested domain types (`--check-coverage`) — `Coverage exceptions` (`pkg/dir/: <why>`, boundary-aware; also silences unclaimed surfaces under that dir)

**No escape — fix it or accept the nudge:** use case with no flow; entity step with no backing C→E edge; entry point owned by no component; dead role; human+service actor mix; sub-flow referenced fewer than 2 times; use-case/sub-flow name joining two clauses with "and"; duplicate or role-less C→D edges; `where` set together with `no_call_site`; minted or drift-spelled dep buckets and entry-point kinds; oversized catch-all bucket; messaging broker of the wrong kind, edge-less publishers/consumers, one-sided or unplaced channels, no channel naming a payload; missing or partial `grounding` record; base class not tagged where its subclass runs; state machine citing no `source`, isolated states; `tech_source` with no `tech`; deployment-flavoured `extra` keys; empty subsystems/subdomains, ungrouped entities, redundant and deep nesting; entities with no owning component; deps with no incoming edge or a wrong `deployment_linked` marker; drifted call-site anchors and state names missing from the cited file (`--check-sources`); a stale or missing generated `project-map.md`.

---

## Viewer diagrams

Every view the server pre-renders, with the Mermaid diagram type it uses.

| View | What it draws | Diagram |
|---|---|---|
| Context | the system, its actors, and external systems grouped by purpose; in-process libraries folded into one box (`gen_viewer.py:1325`) | flowchart LR |
| Libraries drill | the folded in-process dependencies, grouped by purpose (`gen_viewer.py:1372`) | flowchart LR |
| Bucket drill | one folded purpose bucket's members drawn by name (`gen_viewer.py:1349`) | flowchart LR |
| Subsystems overview | top-level subsystems with count-labelled crossings (`gen_viewer.py:863`) | flowchart TB |
| Subsystem card | one subsystem framed around its direct members, its dependencies and collapsed neighbours (`gen_viewer.py:1003`) | flowchart TB |
| Subsystem edge card | two subsystems framed with the concrete crossings between them (`gen_viewer.py:1096`) | flowchart LR |
| Flat components map | every component and dependency at once — kept dormant, not wired to a tab (`gen_viewer.py:149`) | flowchart TB |
| Entities | the whole domain model: entity boxes with fields, store, retention, lifecycle (`gen_viewer.py:455`) | classDiagram |
| Subdomains overview | one box per subdomain, arrows counted from crossing entity relations (`gen_viewer.py:564`) | flowchart TB |
| Subdomain card | one subdomain framed full, neighbours collapsed, plus the subsystems that touch it (`gen_viewer.py:682`) | classDiagram |
| Domain edge card | two subdomains framed with the entity relations crossing between them (`gen_viewer.py:758`) | classDiagram |
| Bridge card | a subsystem and a subdomain side by side with the component-to-entity links (`gen_viewer.py:799`) | classDiagram |
| Deployment overview | processes, shared infrastructure banded by role, and process-to-process traffic (`gen_viewer.py:1943`) | flowchart TB |
| Process group card | a product-area container's member processes and the real arrows between them (`gen_viewer.py:2128`) | flowchart TB |
| Process card | one process with what it runs, the stores it uses and the peers it talks to (`gen_viewer.py:2200`) | flowchart TB |
| Happy Path | the ordered walk of use cases as messages from each actor to the system (`gen_viewer.py:2392`) | sequenceDiagram |
| Use-case flow | one use case's ordered steps between the actor and the elements it touches (`gen_viewer.py:2507`) | sequenceDiagram |
| Broker channels | per broker: publishing components, the channels, and the consumers (`gen_viewer.py:2669`) | flowchart LR |


---

*Generated with coyodex from `project-map.json` — the committed source of truth. Do not edit this file; regenerate it with `coyodex render`.*
