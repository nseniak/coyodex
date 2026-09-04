# coyodex — Codebase Analysis

<!-- GENERATED VIEW — do not edit. The source of truth is project-map.json; regenerate this
     file with `coyodex render project-map.json project-map.md`. -->

> Built with the **coyodex** method. Behavioral layer first (Goal → Glossary → Roles →
> Use cases → Happy Path), then the structural machine (Components → Entry points /
> Model / Deps → Flows + Edges), joined at **use case ↔ flow**.
> The committed source of truth is `project-map.json` (JSON); this file is a generated
> view. IDs, cross-references, and confidence tags are validated by
> `coyodex validate project-map.json`.
> **Commit:** `037db30` · **Committed:** `2026-08-25`

---

## T0 — Goal (the anchor)

coyodex builds a map of a codebase that a person can read top down, without reading the code. An AI coding agent follows a written method to read the project and produce that map: diagrams, one plain sentence on every box, and a link to a real file and line under every claim. The map is committed next to the code and served as an interactive browser page. The product exists for one situation: your coding agent wrote a lot of code, the code runs, and you have lost track of what is under your feet. It is for the developer who owns such a project, for the agent that has to keep the map honest, and for whoever maintains the method itself.

---

## Glossary — the ubiquitous language

| Term | Meaning | Defined / used in |
|---|---|---|
| **map** | The whole picture coyodex produces for a project: diagrams, plain-language text on every box, and code links. | [model.md](method/model.md:1) |
| **baseline** | The map as currently accepted, pinned to one commit. A code change is compared against it. | [change-impact.md](method/change-impact.md:1) |
| **build** | Analysing a project from scratch and producing a new map. Hand edits are thrown away. | [method.md](method.md:2008) |
| **viewer** | The browser page that shows a map. Served live from the map, never committed as a file. | [tools/coyodex/viewer/](tools/coyodex/viewer/) |
| **view** | One screen in the viewer answering one question. Happy Path, Features, Entities and Deployment are views. | [views.py](tools/coyodex/views.py:1) |
| **box** | One thing drawn on a view. A component, an entity, a feature or a dependency each draw as one. | [build_graph.py](tools/coyodex/viewer/build_graph.py:1) |
| **code link** | The file and line a box points at. A box without one is an ungrounded claim. | [anchors.py](tools/coyodex/anchors.py:1) |
| **change impact** | The report saying what a code change does to the map: what is added, changed or gone. | [impact_lib.py](tools/coyodex/impact_lib.py:1) |
| **accept** | Folding a change-impact report into the baseline and re-pinning it to the new commit. | [change-impact.md](method/change-impact.md:1) |
| **Coyote Effect** | Your agent wrote a lot of code, and the code still runs. Nobody knows any more what is under your feet. | [README.md](README.md:20) |
| **the method** | The written instructions a coding agent follows to build a map. This product's real logic lives there. | [method.md](method.md:1) |
| **the skill** | The small pointer file installed into each coding agent so a person can invoke coyodex by name. | [SKILL.md](skill/coyodex/SKILL.md:1) |
| **fragment** | One worker's slice of a map, written as its own file. Every fragment is merged into the map. | [assemble.py](tools/coyodex/assemble.py:1) |
| **contract** | The briefing a fan-out worker is handed, printed by a command so the wording never drifts. | [contract.py](tools/coyodex/contract.py:1) |
| **fan-out** | Splitting one phase of a build across many workers who run at the same time and never share context. | [method.md](method.md:1045) |
| **skeptic** | A fresh worker handed a batch of the map's claims and told to disprove each one against the code. | [skeptic-contract.md](method/templates/skeptic-contract.md:1) |
| **claim** | One statement the map makes about what the code actually does, carrying the line that witnesses it. | [audit_model.py](tools/coyodex/audit_model.py:1) |
| **worklist** | The ranked list of claims the audit says need code evidence. The skeptics work it top down. | [audit_model.py](tools/coyodex/audit_model.py:1) |
| **grounding** | The record of how many claims were challenged and how the skeptics voted on each. | [grounding.py](tools/coyodex/grounding.py:1) |
| **anchor drift** | A code link pointing at a line that cannot be acting, such as a definition header or a comment. | [anchor_drift.py](tools/coyodex/anchor_drift.py:1) |
| **advisory** | A finding that never blocks. Fix it, or write one line saying why it is acceptable. | [validate_model.py](tools/coyodex/validate_model.py:1) |
| **recorded exception** | One written line that stops a named advisory firing forever, because a person judged it acceptable. | [record.py](tools/coyodex/record.py:1) |
| **gate** | An automatic check a map must pass. Failing one is a defect in the map, not in the code. | [finalize.py](tools/coyodex/finalize.py:1) |
| **pre-index** | A measurement of the code tree made before the map is drawn: folder weight, symbols, and an expected size. | [preindex_lib.py](tools/coyodex/preindex_lib.py:1) |
| **expected component count** | How many components a tree of this size should produce, derived from the code alone with a band around it. | [preindex_lib.py](tools/coyodex/preindex_lib.py:1) |
| **component** | One module-sized unit of the code, roughly a folder with one purpose. The map's main structural box. | [model.py](tools/coyodex/model.py:1) |
| **subsystem** | A group of components, and of smaller subsystems. What the first screen of a large map shows. | [model.py](tools/coyodex/model.py:1) |
| **entity** | A real named type in the code that the product stores or reasons about. Drawn with its fields and relations. | [domain-cards.md](method/domain-cards.md:1) |
| **subdomain** | A group of entities that belong together. The domain-model twin of a subsystem. | [model.py](tools/coyodex/model.py:1) |
| **use case** | One goal one actor has, with one trigger and one outcome. The unit the product's story is told in. | [model.py](tools/coyodex/model.py:1) |
| **flow** | The inside view of one use case: the ordered steps among components, dependencies and entities. | [model.py](tools/coyodex/model.py:1) |
| **sub-flow** | A named step sequence shared by two or more flows, so shared machinery is written down once. | [model.py](tools/coyodex/model.py:1) |
| **Happy Path** | One end-to-end walk through the use cases that tells the product's story and reaches every actor. | [method.md](method.md:226) |
| **feature** | A group of use cases serving one goal of the product. What a product person would call an area. | [features.py](tools/coyodex/features.py:1) |
| **business rule** | One decision the product makes, in product words, plus every place the code enforces it. | [method.md](method.md:600) |
| **block** | A group of business rules covering one area a product person would argue about. | [model.py](tools/coyodex/model.py:1) |
| **entry point** | A surface the outside world reaches the product through, or a job the product starts on its own. | [model.py](tools/coyodex/model.py:1) |
| **pin** | The commit a map says it describes. Every code link is read at that commit. | [provenance.py](tools/coyodex/provenance.py:1) |
| **eval** | Scoring two maps of one project to say whether a change to the method made map quality better or worse. | [README.md](eval/README.md:1) |
| **retro** | Reading a finished build and its transcript to find what went wrong in the process. | [method.md](eval/retro/method.md:1) |
| **verdict** | How an eval rates a new map, in one of three words. Pass means as good as before. Drift means a measurement moved too far. Regressed means a hard check got worse. | [thresholds.json](eval/thresholds.json:1) |

---

## Roles (actors)

`Audience` says WHICH SIDE this actor is on: `internal` = the side of the company that ships the product,
`user` = everyone else. On a program it is whose machine it is, so a bought service is `internal`.
Every capability's audience is derived from it.

| Role | Kind | Audience | What they want | Use cases they drive |
|---|---|---|---|---|
| **Map reader** | human | user | To understand a codebase top down, and to drop into the code only where it matters. | Installs the skill, starts the map server, reads the map, and asks for map changes in plain words. |
| **Coding agent** | ai-agent | user | To follow the written method end to end and produce a map every gate accepts. | Runs the briefing, the tree sizing, the fan-out, the merge, every gate, and the change-impact report. |
| **coyodex developer** | human | internal | To know whether a change to the method made the maps better or worse. | Archives a map, scores a rebuild against the accepted one, and reviews what a finished build did. |

---

## Capabilities — what this product does

The use-case grouping. `Audience` is DERIVED from the roles driving its use cases, so nothing on a capability can contradict its own actors.

| ID | Capability | Audience | Purpose | Parent |
|---|---|---|---|---|
| **CAP1** | Getting set up | user | Putting coyodex on a machine and getting the map server running, once. |  |
| **CAP2** | Building a map | user | Reading a project from scratch and turning what many workers found into one map. |  |
| **CAP3** | Proving the map | user | Deciding whether a finished map is well formed, self-consistent, and true about the code. |  |
| **CAP4** | Reading the map | user | Letting a person understand a project top down, and reach the code only where it matters. |  |
| **CAP5** | Keeping the map current | user | Telling what a later code change did to the map, and folding the answer back in. |  |
| **CAP6** | Judging map quality | internal | Answering whether a change to the method made the maps it produces better or worse. |  |
| **CAP7** | Reviewing a finished build | internal | Reading a build that already ran to find what the method and the tools got wrong. |  |

---

## Use cases

### Getting set up *(CAP1)*

| ID | Use case | Actor | Trigger → Outcome |
|---|---|---|---|
| **UC1** | Install the coyodex skill into the coding agents | Map reader | The reader runs the install target in a fresh clone. Every coding agent on that machine can now answer to coyodex. |
| **UC2** | Start the local map server | Map reader | The reader starts the server once. A landing page lists every project that has a map. |

### Building a map *(CAP2)*

| ID | Use case | Actor | Trigger → Outcome |
|---|---|---|---|
| **UC3** | Brief the reader on what will be analysed | Coding agent | The agent begins a run. The reader sees the file count, what each exclusion removed, and the commit the map will name. |
| **UC4** | Declare code the map should not describe | Map reader | The reader lists a fixture or vendored tree in the ignore file. Every measurement afterwards drops those files. |
| **UC5** | Size the code tree before choosing altitude | Coding agent | The agent asks for the weight of every folder. The answer gives line counts, churn, a symbol index and an expected size. |
| **UC6** | Hand a fan-out worker its contract | Coding agent | The agent is about to dispatch workers. One command prints the worker's half of the briefing, ready to fill in. |
| **UC7** | Self-check one harvested fragment | Coding agent | A worker finishes its rows. The check reports schema, code-link and drift problems while the worker can still fix them. |
| **UC8** | Merge the workers' fragments into one map | Coding agent | Every fragment is on disk. Merging them writes the map and its readable view, refusing any duplicate identifier. |
| **UC9** | Turn path rules into explicit assignments | Coding agent | The agent knows folder paths, not identifiers. Path rules expand into an assignment file, naming every rule that matched nothing. |
| **UC10** | Look up one part of the map | Coding agent | The agent needs one element's stored record. A read-only lookup returns it, from a finished map or a build fragment. |

### Proving the map *(CAP3)*

| ID | Use case | Actor | Trigger → Outcome |
|---|---|---|---|
| **UC11** | Check the map is well formed | Coding agent | The agent finishes a write. The check reports broken references, bad code links, and every balance and coverage advisory. |
| **UC12** | Make the map's two layers refute each other | Coding agent | The agent has a map that is well formed. The walk and the flows are compared, and the claims needing code evidence are ranked. |
| **UC13** | Disprove a claim against the code | Coding agent | A fresh worker is handed a batch of claims and told to break them. Each comes back confirmed, refuted, or impossible to settle. |
| **UC14** | Record what the skeptics proved | Coding agent | Every verdict file is in. The counts are derived and written into the map, refusing a verdict for a claim nobody pinned. |
| **UC15** | Correct a code link that points at the wrong line | Coding agent | The skeptics report a truer line than the map holds. The correction is written so the next merge keeps it. |
| **UC16** | Drop a claim the code refutes | Coding agent | A relation turns out not to exist. Removing it also heals the walk steps that rode on it. |
| **UC17** | Record an advisory the reader accepts | Coding agent | An advisory is a judgement, not a defect. One line written under the heading it names stops it firing again. |
| **UC18** | Re-balance the diagrams against the traced graph | Coding agent | Grouping was cut before any relation existed. The report shows each screen's box count and where a split would fall. |
| **UC19** | Run the pre-commit read | Coding agent | The agent believes the map is done. One run does every gate, writes the whole finding list to a file, and says which gates ran. |
| **UC20** | Stamp which conversation built the map | Coding agent | The map is written and checked. The session and the minute are recorded, so the transcript can be found again later. |

### Reading the map *(CAP4)*

| ID | Use case | Actor | Trigger → Outcome |
|---|---|---|---|
| **UC21** | Open a project's map in a browser | Map reader | The reader clicks a project on the landing page. Every view is built from the map on demand and drawn. |
| **UC22** | Follow the product's story end to end | Map reader | The reader wants to know what the product does. One column shows every feature in the order the story runs. |
| **UC23** | Read the code under a box | Map reader | The reader wants the evidence behind a claim. The file opens at that line, read from the commit the map names. |
| **UC24** | Open an element's source in the editor | Map reader | The reader wants to change what a box describes. One click opens that line in the editor or on the hosting site. |

### Keeping the map current *(CAP5)*

| ID | Use case | Actor | Trigger → Outcome |
|---|---|---|---|
| **UC25** | Report what a code change did to the map | Coding agent | The code has moved past the commit the map names. The report says which parts of the map are added, changed or gone. |
| **UC26** | Fold a change report into the map | Coding agent | The reader says the report is right. The map is patched element by element and re-pinned to the new commit. |
| **UC27** | Change the map by asking in plain words | Map reader | The reader asks to split, rename, move or drill deeper into a part. The map is edited directly, then put through every gate. |
| **UC28** | See what an edit changed, row by row | Coding agent | The agent has the map from before and after an edit. Every added, dropped and changed row is listed with the fields that moved. |
| **UC38** | See the change overlaid on the map | Map reader | The reader picks two commits in the viewer. Every box the change reaches is marked, including the ones it reaches indirectly. |

### Judging map quality *(CAP6)*

| ID | Use case | Actor | Trigger → Outcome |
|---|---|---|---|
| **UC29** | Score a rebuilt map against the accepted one | coyodex developer | The developer changed the method and rebuilt. The two maps are measured and the run says pass, drift or regressed. |
| **UC30** | Have judges read both maps | coyodex developer | Counting cannot say whether the words are true. Judges read both maps for grounding and against a rubric, and their verdicts are gathered. |
| **UC31** | Accept a run as the new baseline | coyodex developer | The developer decides the new map is the standard. Its map, view, profile and judgement all become the baseline. |
| **UC32** | Measure how many planted falsehoods the skeptics catch | coyodex developer | Refutation rates cannot say whether skeptics are weak. Planting known-false claims gives an answer key to score against. |

### Reviewing a finished build *(CAP7)*

| ID | Use case | Actor | Trigger → Outcome |
|---|---|---|---|
| **UC33** | Refuse to review a build that has not finished | coyodex developer | A build stamps its session near the end. Reviewing early would read the previous run, so the check stops it. |
| **UC34** | Read a build transcript in slices | coyodex developer | A build transcript is far too large to read whole. An index comes first, then one range at a time. |
| **UC35** | Score a build's behaviour against the method | coyodex developer | The gates say a map is well formed, never that the agent followed the method. The transcript is scored rule by rule. |
| **UC36** | Measure what a build spent | coyodex developer | The developer wants the price of a map. Time and tokens are totalled across every worker, then divided by the rows produced. |
| **UC37** | Archive a map so the next run builds from scratch | coyodex developer | A rebuild must never read the map it replaces. Filing the old map away leaves the folder empty and keeps the baseline. |


---

## Happy Path — the spine (an ordered walk through the use cases)

The happy-path ordering of use cases. Each step IS a use case (its `*(UCn)*` tag
names it); the step's detail lives in that use case's T6 flow. An optional `why:`
line records the prerequisite that fixes the step's position.

**HP1 — Reader installs the skill into their coding agents** *(UC1)*
**HP2 — Agent briefs the reader on what it is about to analyse** *(UC3)*
why: needs the skill installed at HP1, so the agent knows what coyodex means
**HP3 — Agent measures the weight of every folder** *(UC5)*
why: needs the file set agreed at HP2
**HP4 — Agent hands each worker its briefing** *(UC6)*
why: needs the slice sizes from HP3
**HP5 — A worker self-checks its fragment before returning it** *(UC7)*
why: needs the briefing handed over at HP4
**HP6 — Agent merges every fragment into one map** *(UC8)*
why: needs every worker's fragment on disk from HP5
**HP7 — Agent assigns grouping and links across the whole build** *(UC9)*
why: needs the merged identifiers from HP6
**HP8 — Agent checks the map is well formed** *(UC11)*
why: needs a written map from HP6
**HP9 — Agent makes the walk and the flows refute each other** *(UC12)*
why: needs the map to be well formed, from HP8
**HP10 — A fresh worker tries to disprove a batch of claims** *(UC13)*
why: needs the ranked claim list from HP9
**HP11 — Agent corrects a code link the skeptics moved** *(UC15)*
why: needs the skeptics' verdicts from HP10
**HP12 — Agent records what the skeptics proved** *(UC14)*
why: needs every verdict file from HP10
**HP13 — Agent runs the pre-commit read** *(UC19)*
why: needs the grounding record from HP12
**HP14 — Agent stamps the conversation that built the map** *(UC20)*
why: needs a map that passed the gates at HP13
**HP15 — Reader starts the local map server** *(UC2)*
**HP16 — Reader opens the new project's map** *(UC21)*
why: needs the server running from HP15 and a committed map from HP14
**HP17 — Reader follows the product's story end to end** *(UC22)*
why: needs the map open from HP16
**HP18 — Reader reads the code under a box that surprised them** *(UC23)*
why: needs a box on screen from HP17
**HP19 — Agent reports what later code changes did to the map** *(UC25)*
why: needs the pinned baseline from HP14
**HP20 — Agent folds the change report into the map** *(UC26)*
why: needs the report from HP19 and the reader's agreement
**HP21 — Developer archives the map before rebuilding it** *(UC37)*
why: needs a baseline worth comparing against, from HP20
**HP22 — Developer scores the rebuilt map against the archived one** *(UC29)*
why: needs the archived baseline from HP21
**HP23 — Judges read both maps for grounding and against the rubric** *(UC30)*
why: needs both maps profiled at HP22
**HP24 — Developer accepts the rebuilt map as the new baseline** *(UC31)*
why: needs the verdict and the judgements from HP22 and HP23
**HP25 — Developer scores the build's behaviour against the method** *(UC35)*
why: needs the finished build's transcript, found through the stamp from HP14

---

## Subsystems (S) — the container altitude

| ID | Subsystem | Purpose | Parent | Tech | Source | Conf. |
|---|---|---|---|---|---|---|
| **S1** | Building and updating the map | Turns a project into a map, and works out what a later code change did to that map. |  | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/ | verified |
| **S2** | Proving the map | Decides whether a finished map is well formed, self-consistent and true about the code. |  | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/ | verified |
| **S3** | Reading the map | Shows a person the map in a browser, and the code behind any box they ask about. |  |  | tools/coyodex/viewer/ | verified |
| **S4** | Map server | Serves the map's screens from one local process, and reads source out of the commit the map names. | S3 | Python ([pyproject.toml](pyproject.toml:9)) | tools/coyodex/viewer/serve.py:800 | verified |
| **S5** | Browser page | Draws every view, remembers where the reader is, and puts the code beside the picture. | S3 | JavaScript ([pyproject.toml](pyproject.toml:51)) | tools/coyodex/viewer/viewer.html:362 | verified |
| **S6** | Written method | The instructions a coding agent follows to build a map. This product's real logic lives here. |  |  | method/ | verified |
| **S7** | Judging and reviewing builds | Answers whether a method change made the maps worse, and what a finished run got wrong. |  | Python ([pyproject.toml](pyproject.toml:9)) | eval/tools/coyodex_eval/ | verified |

---

## T1 — Components

| ID | Component | Subsystem | Purpose | Entry point | Depends on | Conf. | Files | Evidence | Runs in |
|---|---|---|---|---|---|---|---|---|---|
| **C78** | Eval recipe | S6 | Written instructions for scoring two maps of the same code. The scoring says whether a change to the coyodex method made maps better or worse. The same instructions fix the quality rubric a reviewer scores against, and the pass marks a map must clear. A run ends in one word: as good, drifted, or worse. |  |  | verified | eval/method.md · eval/rubric.md · eval/thresholds.json · eval/README.md · eval/blind-build.md · eval/experiments/2026-08-16-skeptic-recall.md · eval/experiments/2026-08-16-skeptic-recall.key.json | [method.md](eval/method.md:8) — The recipe states its job, which is to compare the current map against an archived one. · [method.md](eval/method.md:41) — The recipe forbids editing either map to improve a number, and voids a run where that happened. · [thresholds.json](eval/thresholds.json:6) — The pass marks hold the hard check that a map must not gain new validation problems. · [rubric.md](eval/rubric.md:10) — The rubric names its first quality dimension, asking whether the map's claims match the code. · [method.md](eval/method.md:33) — The recipe hands a caller off to the separate recipe for a provably blind rebuild. |  |
| **C79** | Build retrospective recipe | S6 | Written instructions for reviewing one finished build. The review reads the map the build made and the chat that made it. The review reports the friction, bugs and gaps the build revealed. A review changes nothing on disk, so every finding is a proposal for the developer. Each past finding is re-checked with a command that returns a number. |  |  | verified | eval/retro/method.md · eval/retro/backlog.md | [method.md](eval/retro/method.md:4) — The recipe states its job, which is to read the map and the chat and report what the run shows. · [method.md](eval/retro/method.md:6) — The recipe forbids changing anything on disk, so every finding stays a proposal. · [method.md](eval/retro/method.md:62) — The recipe orders the reviewer to refuse while the build is still writing. · [method.md](eval/retro/method.md:264) — The recipe collects every promise a method change made since the previous build. · [backlog.md](eval/retro/backlog.md:7) — The durable record of past proposals says the recipe must read it before a review starts. |  |
| **C1** | Map document | S1 | Holds the shape of a map: what a box, an arrow and a code link may each contain. Writes the map file the same way every time, so a rebuild shows only real changes. Also holds the word lists the whole tool shares. |  |  | verified | tools/coyodex/model.py · tools/coyodex/grammar.py · tools/coyodex/anchors.py · tools/coyodex/json_schema.py | [model.py](tools/coyodex/model.py:892) — The one serializer: fixed key order, indent 2, trailing newline, so the same map always writes identical bytes. · [model.py](tools/coyodex/model.py:1084) — Load rejects an element whose id does not match its array's required prefix, which is the shape half of validation. · [grammar.py](tools/coyodex/grammar.py:369) — One shared decision for an entry point's activation, reused by the viewer, the coverage advisory and the eval. · [anchors.py](tools/coyodex/anchors.py:36) — The single definition of a well-formed code link: a file reference with an optional line, or a directory reference. | coyodex command |
| **C2** | Fragment merge | S1 | Merges every worker's part of the map into one document. A box claimed by two workers stops the build, instead of one part quietly winning. Gives a worker the self-check it runs before handing its part back. |  |  | verified | tools/coyodex/assemble.py · tools/coyodex/lint_fragment.py | [assemble.py](tools/coyodex/assemble.py:394) — A duplicate id across two fragments is reported as a merge conflict naming both files, never silently overwritten. · [assemble.py](tools/coyodex/assemble.py:688) — Entry-point ids are minted here from content order, which is why a fragment must not author one. · [assemble.py](tools/coyodex/assemble.py:963) — The merged model is written to the canonical map file, plus its generated markdown view. · [lint_fragment.py](tools/coyodex/lint_fragment.py:452) — The per-fragment self-check runs the same row-local rules the whole-map validator does, in the authoring worker's own turn. | coyodex command |
| **C3** | Map lookups | S1 | Reads one part of a map, so nobody opens the file and picks it apart by hand. Compares two versions of a map row by row, saying what was added, dropped or changed. Writes the note an operator leaves when accepting an advisory. |  |  | verified | tools/coyodex/dump.py · tools/coyodex/mapdiff.py · tools/coyodex/record.py · tools/coyodex/records.py | [dump.py](tools/coyodex/dump.py:297) — With no slice flag the whole parsed model is emitted, which is the read-only whole-map lookup. · [mapdiff.py](tools/coyodex/mapdiff.py:159) — For a row present on both sides, the fields whose values moved are recorded as the change. · [record.py](tools/coyodex/record.py:318) — One write for a whole batch of recorded lines, after every line has passed its shape check. · [records.py](tools/coyodex/records.py:183) — The single reader for a recorded line, so every advisory family parses the same key-and-reason shape. | coyodex command |
| **C4** | Command shell and build setup | S1 | The single command every coyodex action runs through. Before a build starts, the command says which files will be read and which commit the map will name. The same command prints the brief one worker receives, and reads the list of code the map should skip. |  |  | verified | tools/coyodex/cli.py · tools/coyodex/scope.py · tools/coyodex/ignorefile.py · tools/coyodex/pathmatch.py · tools/coyodex/contract.py · tools/coyodex/reporting.py · tools/coyodex/subverb_help.py · tools/coyodex/pysrc.py · tools/coyodex/__init__.py | [cli.py](tools/coyodex/cli.py:114) — Standard output is switched to line buffering at startup, so notes and failures interleave in program order under a pipe. · [scope.py](tools/coyodex/scope.py:172) — The up-front briefing is printed as plain text, with no exit-code signalling, for a person to read before the build. · [ignorefile.py](tools/coyodex/ignorefile.py:178) — Each accepted line of the analysis ignore file becomes an ordered rule, where a later rule overrides an earlier one. · [contract.py](tools/coyodex/contract.py:118) — Only the agent half of a contract template is printed, so the lead's own instructions cannot reach a worker. | coyodex command |
| **C13** | Map validator | S2 | Checks a finished map is well formed before anyone trusts it. Every reference must resolve and every code link must point at a real file. Softer findings are advice, and an operator can silence one by writing down a reason. |  |  | verified | tools/coyodex/validate_model.py · tools/coyodex/validate_analysis.py · tools/coyodex/prose.py | [validate_model.py](tools/coyodex/validate_model.py:4444) — A code link pointing at a file that is not there fails the map, rather than only nudging. · [validate_analysis.py](tools/coyodex/validate_analysis.py:181) — Warns when many sibling folders of code were folded into about one box on a diagram. · [prose.py](tools/coyodex/prose.py:172) — Counts what makes one sentence hard to read alone, and reports each count as advice. · [validate_model.py](tools/coyodex/validate_model.py:4810) — Names the command that writes down a reason, once, where the operator reads the warnings. | coyodex command |
| **C14** | Map auditor | S2 | Reads a map against itself and reports where the story and the mechanism disagree. Also ranks every claim the map makes about the code. Fresh readers then try to disprove the riskiest claims first. |  |  | verified | tools/coyodex/audit_model.py | [audit_model.py](tools/coyodex/audit_model.py:1432) — Only a hard contradiction stops the build; every softer finding is advice to reconcile. · [audit_model.py](tools/coyodex/audit_model.py:1017) — Access claims are ranked first, so the first batch of readers gets the riskiest claims. · [audit_model.py](tools/coyodex/audit_model.py:831) — A written reason silences exactly one finding, and the report still says what it silenced. · [audit_model.py](tools/coyodex/audit_model.py:1250) — Clears its own earlier claim files, so a stale batch is never handed out a second time. | coyodex command |
| **C15** | Diagram balance report | S2 | Counts the boxes on every diagram and says which screens are too crowded to read. Proposes a regrouping for each crowded screen, as a starting point for judgment. Never fails a build, because grouping is a view choice. |  |  | verified | tools/coyodex/balance.py · tools/coyodex/balance_lib.py | [balance_lib.py](tools/coyodex/balance_lib.py:313) — Warns when one screen shows more boxes than a reader can hold at once. · [balance.py](tools/coyodex/balance.py:201) — Writes a concrete regrouping suggestion for each crowded screen, ready to apply by hand. · [balance.py](tools/coyodex/balance.py:284) — Always reports success, because a crowded diagram is a judgement call and not a failure. · [balance_lib.py](tools/coyodex/balance_lib.py:238) — Reads the reasons an operator wrote down and skips the screens those reasons name. | coyodex command |
| **C16** | Pre-commit gate run | S2 | Runs the other gates in one command and writes every finding to a report file. Says for each gate whether it really ran, so silence never reads as a pass. Can also name files that held an access check in an earlier map and hold none now. |  |  | verified | tools/coyodex/finalize.py · tools/coyodex/access_surface.py | [finalize.py](tools/coyodex/finalize.py:490) — A gate that should have run and did not makes the whole read incomplete, never a pass. · [finalize.py](tools/coyodex/finalize.py:877) — Writes every finding to a file, which trimming the screen output cannot hide. · [finalize.py](tools/coyodex/finalize.py:719) — Checks each piece of advice against what the map recorded, and names a missing record. · [access_surface.py](tools/coyodex/access_surface.py:84) — Names files that held an access check in an earlier map and hold none in this one. | coyodex command |
| **C17** | Feature index | S4 | Joins every part of the map onto the feature it belongs to, and stores nothing. Also derives the one story order every feature screen draws. Counts what fails to join, so a partial list is never shown as a whole one. |  |  | verified | tools/coyodex/features.py | [features.py](tools/coyodex/features.py:331) — Reuses the reader the Rules view uses, so the two screens cannot disagree about a rule. · [features.py](tools/coyodex/features.py:382) — Counts the decisions that reach no feature, so a floor is never read as an answer. · [features.py](tools/coyodex/features.py:246) — Derives one story order here, instead of letting the browser compute a layout. | coyodex command |
| **C23** | Grounding record | S2 | Turns the fresh readers' verdicts into the four counts a map must carry before anyone trusts it. Those counts refuse a verdict for a claim nobody pinned, and a pinned claim nobody voted on. A second check compares a proven claim's code link against the line the fresh readers actually found. |  |  | verified | tools/coyodex/grounding.py · tools/coyodex/anchor_drift.py | [grounding.py](tools/coyodex/grounding.py:201) — One claim's votes are folded into one of three buckets, and the bucket totals become the counts the map ships. · [grounding.py](tools/coyodex/grounding.py:162) — A verdict about a claim the pinned worklist never held is refused, because the two sides came from different snapshots. · [grounding.py](tools/coyodex/grounding.py:180) — A pinned claim with no verdict is refused, unless the operator declares the pass deliberately partial. · [anchor_drift.py](tools/coyodex/anchor_drift.py:93) — The stored code link of a proven claim is compared against the lines the fresh readers reported. | coyodex command |
| **C24** | Map repairs | S2 | Applies the mechanical corrections a map needs after a fresh reader reports, so none of them is hand-typed. A moved code link is rewritten, and a disproved relation is dropped. The happy-path steps that rode the dropped relation are healed too. |  |  | verified | tools/coyodex/fix.py | [fix.py](tools/coyodex/fix.py:227) — The corrected line the fresh readers agreed on is written into every drifted code link. · [fix.py](tools/coyodex/fix.py:447) — Dropping a disproved relation also removes the happy-path steps that rode it, so a rebuild cannot bring it back. · [fix.py](tools/coyodex/fix.py:926) — A relation declared at several different lines is reduced to the one occurrence the operator chose. · [fix.py](tools/coyodex/fix.py:1586) — A text correction is written into the fragment that authored the row, so every later rebuild keeps it. | coyodex command |
| **C25** | Assignment pass | S1 | Turns path rules into an explicit assignment file, so nobody lists hundreds of elements by hand. Every rule that matched nothing is named, and so is an assignment aimed at a group nobody declared. The build stamp is also written here, naming which conversation built the map and the code commit. |  |  | verified | tools/coyodex/reconcile_build.py · tools/coyodex/reconcile.py · tools/coyodex/provenance.py | [reconcile_build.py](tools/coyodex/reconcile_build.py:168) — A rule whose path pattern reached no element is reported instead of quietly producing an empty assignment. · [reconcile_build.py](tools/coyodex/reconcile_build.py:439) — The expanded assignment file is written, keeping the repair decisions an earlier run had already recorded in it. · [reconcile.py](tools/coyodex/reconcile.py:539) — An assignment is applied to the merged map after the fragments are joined and before the map is written. · [provenance.py](tools/coyodex/provenance.py:217) — The session, the build minute and the code commit are written into the stamp file a commit is gated on. | coyodex command |
| **C33** | Pre-index | S1 | Sizes a codebase before the map is drawn. The result gives the size and change rate of every folder. A symbol list says where every class and function is defined. The result also says how many parts a map of this size should hold. | [preindex.py](tools/coyodex/preindex.py:557) |  | verified | tools/coyodex/preindex.py · tools/coyodex/preindex_lib.py | [preindex.py](tools/coyodex/preindex.py:604) — Writes the sizing result, holding the folder weights, the symbol list, the import advisory and the part count. · [preindex_lib.py](tools/coyodex/preindex_lib.py:600) — The stop rule that turns one folder into one part of the map, which is how the advised count is reached. · [preindex_lib.py](tools/coyodex/preindex_lib.py:492) — Reads Python deeply through the standard parser, and every other language through an optional parser pack. · [preindex.py](tools/coyodex/preindex.py:143) — Records every file the tool could not read, so unread code is reported as unknown rather than as empty. | coyodex command |
| **C34** | Change impact | S1 | Tells what a code change did to a finished map. The map is pinned to one commit, so the code has moved on. Two comparisons against that commit say which map boxes the changed lines belong to. The answer then spreads along the map's own arrows, so a reader sees everything the change touches. |  |  | verified | tools/coyodex/impact_lib.py · tools/coyodex/impact_git.py · tools/coyodex/impact_ripple.py | [impact_git.py](tools/coyodex/impact_git.py:94) — Lists the files a change added, edited, deleted or renamed, including edits not yet committed. · [impact_lib.py](tools/coyodex/impact_lib.py:146) — Compares the two sides against the pinned commit, so a change already present at both ends counts as nothing. · [impact_lib.py](tools/coyodex/impact_lib.py:353) — Says how precisely a box was reached, from an exact line down to only the file, so the viewer never overstates precision. · [impact_ripple.py](tools/coyodex/impact_ripple.py:236) — Carries a hit outward along the map's own relations, so a reader sees everything the change touches. | coyodex command |
| **C43** | Map server | S4 | Serves every remembered map to a browser on this machine. Each file shown comes from the project's history at the commit the map names. | [serve.py](tools/coyodex/viewer/serve.py:852) | The diagram builder, the graph builder and the file browser tree. | verified | tools/coyodex/viewer/serve.py · tools/coyodex/viewer/recents.py · tools/coyodex/viewer/__init__.py | [serve.py](tools/coyodex/viewer/serve.py:594) — sends a request for one project to that project's own handler · [serve.py](tools/coyodex/viewer/serve.py:279) — reads a file out of the project's history at the commit the map names · [serve.py](tools/coyodex/viewer/serve.py:577) — refuses any request that did not come from this machine · [recents.py](tools/coyodex/viewer/recents.py:67) — saves the list of project folders the landing page offers | map server |
| **C44** | Diagram builder | S4 | Builds every diagram a map's screens draw, straight from the map. The work happens on each request, so no diagram file is ever saved. |  | The graph builder, and the map's own folder for the code links. | verified | tools/coyodex/viewer/gen_viewer.py | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:3264) — draws the whole map as boxes and arrows · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2364) — draws one arrow for each pair of running processes that talk · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:2900) — draws one numbered message per step of a use case · [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:1552) — folds the in-process libraries into one box on the top view | coyodex command, map server |
| **C45** | Graph builder | S4 | Turns the stored map into the boxes and arrows every screen draws. The same code writes the committed text version of the map. | [render.py](tools/coyodex/viewer/render.py:53) | The stored map, plus the change-impact report when one sits beside it. | verified | tools/coyodex/views.py · tools/coyodex/viewer/build_graph.py · tools/coyodex/viewer/render.py | [views.py](tools/coyodex/views.py:299) — starts the committed text version with the map's title · [views.py](tools/coyodex/views.py:1128) — turns one component of the map into a box a screen can draw · [build_graph.py](tools/coyodex/viewer/build_graph.py:271) — reads a change-impact report so the screens can badge what moved · [render.py](tools/coyodex/viewer/render.py:53) — writes the committed text version to disk | coyodex command, map server |
| **C46** | File browser tree | S4 | Builds the folder tree the file browser shows, marking which files the map covers. Also turns one file's change into the rows the code viewer paints. |  | The graph builder, for the map's file anchors. | verified | tools/coyodex/viewer/filetree.py · tools/coyodex/viewer/diffmap.py | [filetree.py](tools/coyodex/viewer/filetree.py:210) — marks a file as covered by the map, or not covered at all · [filetree.py](tools/coyodex/viewer/filetree.py:115) — indexes every path the map points at, so a click finds its box · [filetree.py](tools/coyodex/viewer/filetree.py:261) — states on the tree what the ignore file hid from it · [diffmap.py](tools/coyodex/viewer/diffmap.py:51) — marks a line as added, for the side-by-side code view | map server |
| **C55** | Map canvas | S5 | Draws a map view as a diagram the reader can pan, zoom and click. Selecting a box or an arrow opens the card describing that box or arrow. |  |  | verified | tools/coyodex/viewer/viewer.js · tools/coyodex/viewer/viewer.css · tools/coyodex/viewer/viewer.html | [viewer.js](tools/coyodex/viewer/viewer.js:8953) — Turns the map's own diagram text into the drawing on screen. · [viewer.js](tools/coyodex/viewer/viewer.js:9025) — Adds pan and zoom to the drawing, and keeps the reader's camera. · [viewer.js](tools/coyodex/viewer/viewer.js:6389) — Gives each kind of view its own click behaviour on boxes and arrows. · [viewer.js](tools/coyodex/viewer/viewer.js:940) — Lights every selected element and dims the rest, so a selection reads as a focus. | viewer page |
| **C56** | Map reading pages | S5 | Draws the map screens that are pages of cards instead of drawings. The features, the rules, the storage, the tests and the glossary all live here. |  |  | verified | tools/coyodex/viewer/viewer.js · tools/coyodex/viewer/viewer.css | [viewer.js](tools/coyodex/viewer/viewer.js:7961) — The Features page leads with the story of every feature beside the cast of actors. · [viewer.js](tools/coyodex/viewer/viewer.js:8738) — The Rules page groups the product's decisions into decision areas. · [viewer.js](tools/coyodex/viewer/viewer.js:8375) — The Storage page is built from the stores the map records. · [viewer.js](tools/coyodex/viewer/viewer.js:6861) — The Glossary page is a table of terms, not a drawing. | viewer page |
| **C57** | Trail and history | S5 | Decides which map screen is open, and names it in the tabs and the breadcrumb. Back and forward reopen a screen exactly as the reader left it. |  |  | verified | tools/coyodex/viewer/viewer.js · tools/coyodex/viewer/viewer.css · tools/coyodex/viewer/viewer.html | [viewer.js](tools/coyodex/viewer/viewer.js:11386) — Clicking a view tab opens that view. · [viewer.js](tools/coyodex/viewer/viewer.js:11401) — Clicking a group tab opens the view that group was last left on. · [viewer.js](tools/coyodex/viewer/viewer.js:4302) — Remembers where each tab was left, so returning to a tab lands back there. · [viewer.js](tools/coyodex/viewer/viewer.js:11694) — Picks the first screen a reader sees when the map opens. | viewer page |
| **C58** | Source column | S5 | Shows the mapped project's files and their code, read at the commit the map names. A file can also be opened in the reader's own editor. |  |  | verified | tools/coyodex/viewer/viewer.js · tools/coyodex/viewer/viewer.css · tools/coyodex/viewer/viewer.html | [viewer.js](tools/coyodex/viewer/viewer.js:9712) — Asks the server for the project's file tree and draws it as a browser. · [viewer.js](tools/coyodex/viewer/viewer.js:10683) — Builds the address that opens a file in the reader's chosen editor. · [viewer.js](tools/coyodex/viewer/viewer.js:10707) — Builds the GitHub address for a file, pinned to the commit the map names. | viewer page |
| **C63** | Map quality score and verdict | S7 | Reduces a finished map to numbers that two runs can be compared on. Says whether the new map is as good as the accepted one, giving pass, drift or regressed. Also plants false claims about the map and counts how many a reviewer catches. | [cli.py](eval/tools/coyodex_eval/cli.py:56) |  | verified | eval/tools/coyodex_eval/cli.py · eval/tools/coyodex_eval/profile.py · eval/tools/coyodex_eval/compare.py · eval/tools/coyodex_eval/run.py · eval/tools/coyodex_eval/judge.py · eval/tools/coyodex_eval/legacy_map.py · eval/tools/coyodex_eval/mutate.py · eval/tools/coyodex_eval/__init__.py | [profile.py](eval/tools/coyodex_eval/profile.py:263) — Counts the risky claims a reviewer is asked to check against the code. · [compare.py](eval/tools/coyodex_eval/compare.py:503) — One failed hard check makes the whole comparison read as regressed. · [judge.py](eval/tools/coyodex_eval/judge.py:242) — Turns the reviewers' votes into one pass rate, ignoring votes that failed. · [mutate.py](eval/tools/coyodex_eval/mutate.py:228) — A reviewer that confirms a claim false by construction is scored as a miss. | coyodex command |
| **C64** | Build transcript reader and spend report | S7 | Reads a finished build's chat log in slices, because the whole log is too big to open. Also reports the time and the money that build spent, per row of map produced. | [transcript.py](eval/tools/coyodex_eval/transcript.py:1067) |  | verified | eval/tools/coyodex_eval/transcript.py · eval/tools/coyodex_eval/cost.py | [transcript.py](eval/tools/coyodex_eval/transcript.py:374) — Every record of one reply is folded into one turn, so ten tool calls at once count as one turn. · [transcript.py](eval/tools/coyodex_eval/transcript.py:874) — Lists every coyodex command the build ran, with the turn number that ran it. · [cost.py](eval/tools/coyodex_eval/cost.py:492) — Subtracts the stretches where nobody was working, so the clock measures the build. · [cost.py](eval/tools/coyodex_eval/cost.py:557) — Divides the spend by the rows of map produced, so two builds of different size compare. | coyodex command |
| **C65** | Build behaviour scorecard | S7 | Scores what a build agent actually did against the rules the method sets. Reports a share of the chances the build had, never a pass or a fail. Also compares two scorecards to show which way each number moved. | [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:3130) |  | verified | eval/tools/coyodex_eval/process_scorecard.py | [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:124) — A line with no chance to obey the rule scores as not applicable, never as zero. · [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:2987) — Warns when a score rose only because the chances to break the rule vanished. · [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:3180) — Refuses a map it cannot read, instead of quietly scoring less of the build. | coyodex command |
| **C66** | Map archive and build guard | S7 | Moves a project's current map aside so the next run builds from scratch, keeping it as the baseline. Refuses a review while a build is still writing. Also stamps which chat built a map and bundles the two together. | [archive.py](eval/tools/coyodex_eval/archive.py:159) |  | verified | eval/tools/coyodex_eval/archive.py · eval/tools/coyodex_eval/retro_precheck.py · tools/map_backup.py | [archive.py](eval/tools/coyodex_eval/archive.py:83) — Each archive takes the next number up, so the number always means how recent. · [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:201) — A recent write inside the map folder means something is still changing the map. · [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:226) — A chat file whose date moved counts as live only when a real message was added. · [map_backup.py](tools/map_backup.py:361) — Refuses to move a map out of a repo when no chat could be bundled with it. | coyodex command |
| **C75** | Build method | S6 | The written instructions a coding agent follows to build a map. The same instructions specify every field a map holds. |  |  | verified | method.md · method/dispatch.md · method/model.md · method/domain-cards.md · method/diagrams.md · method/change-impact.md · method/project-map.schema.json | [dispatch.md](method/dispatch.md:83) — the line that sends an agent into a fresh build when no map is on disk · [method.md](method.md:1047) — the build order the whole method runs, from harvest through synthesis to trace · [model.md](method/model.md:50) — the first line of the map document's field-by-field specification · [method.md](method.md:2100) — the command that turns the workers' returns into the stored map |  |
| **C76** | Worker briefings | S6 | The briefings a build hands to each worker agent it fans out to. A briefing states what that worker must return. |  |  | verified | method/templates/harvest-contract.md · method/templates/trace-contract.md · method/templates/rules-contract.md · method/templates/skeptic-contract.md · method/templates/gapfill-contract.md · method/templates/writing-rules.md · method/templates/project-map.template.md | [harvest-contract.md](method/templates/harvest-contract.md:26) — the opening line of the briefing every harvest worker reads · [trace-contract.md](method/templates/trace-contract.md:51) — tells a trace worker to write one file and return only its path · [rules-contract.md](method/templates/rules-contract.md:95) — names the one field a rule worker must never fill, which cost eleven repairs · [method.md](method.md:1960) — the command that prints a briefing, so nobody retypes one |  |
| **C77** | Installed skill and project writing | S6 | The pointer a person installs into their coding agent, so the coyodex command reaches the method. The project's own writing for readers and contributors lives beside that pointer. |  |  | verified | skill/coyodex/SKILL.md · eval/SKILL.md · eval/retro/SKILL.md · README.md · CONTRIBUTING.md · CLAUDE.md · SECURITY.md · CODE_OF_CONDUCT.md · docs/how-coyodex-works.html · internal/docs/method-rationale.md · method/retro-checks/README.md · method/retro-checks/2026-08-25-feature-stakes.md · method/retro-checks/2026-08-25-role-relations.md · method/retro-checks/2026-08-25-story-anchors.md · method/retro-checks/2026-08-25-term-linking-and-indirect-references.md · .github/PULL_REQUEST_TEMPLATE.md · .github/ISSUE_TEMPLATE/bug_report.yml · .github/ISSUE_TEMPLATE/idea.yml · .github/ISSUE_TEMPLATE/config.yml | [SKILL.md](skill/coyodex/SKILL.md:27) — the one line that sends an agent from the installed pointer into the method · [SKILL.md](skill/coyodex/SKILL.md:22) — the clone path baked in at install time, so everything else is read live · [CONTRIBUTING.md](CONTRIBUTING.md:99) — the install step that copies the pointer into each agent's skills home · [README.md](README.md:74) — tells a reader where installing puts the skill for each agent |  |

---

## T2 — External dependencies

| ID | Name | Kind | Bucket | Type | Used for | Where configured | Conf. | Deployment-linked | Package | Alternative | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **D1** | git | platform | Infrastructure & runtime | version-control program, run as a separate process | Reads project files at a pinned commit. The map server shows each file as it was when the map was built. | [serve.py](tools/coyodex/viewer/serve.py:236) | verified |  |  |  | [serve.py](tools/coyodex/viewer/serve.py:236) — the map server runs a read-only git command inside the project folder · [preindex_lib.py](tools/coyodex/preindex_lib.py:189) — the file survey asks git for the tracked file list · [provenance.py](tools/coyodex/provenance.py:120) — the build stamp reads the current commit from git |
| **D2** | Python | platform | Infrastructure & runtime | language runtime, version 3.10 or newer | Runs every coyodex command. Setup builds a private environment inside the coyodex folder, so no package lands in the machine's own Python. | [pyproject.toml](pyproject.toml:9) | verified |  |  |  | [pyproject.toml](pyproject.toml:9) — the package declares the minimum Python version · [Makefile](Makefile:31) — setup refuses to continue on an older Python, with a plain message |
| **D3** | tree-sitter | library | Code parsing | optional Python package, source-code parser | Parses code in many languages. The file survey uses tree-sitter to count symbols and imports before an altitude is chosen. | [pyproject.toml](pyproject.toml:19) | verified |  | tree-sitter >=0.21 (pyproject.toml, the `preindex` extra) | Python's own built-in parser, which still handles Python files when tree-sitter is missing. | [pyproject.toml](pyproject.toml:19) — the pin lives in an optional extra, so the checking path stays free of it · [preindex_lib.py](tools/coyodex/preindex_lib.py:390) — the survey builds one parser per language from tree-sitter |
| **D4** | tree-sitter-language-pack | library | Code parsing | optional Python package, bundled grammars | Supplies the grammar for each language the survey parses. Without the pack no non-Python file can be surveyed. | [pyproject.toml](pyproject.toml:20) | verified |  | tree-sitter-language-pack >=0.2 (pyproject.toml, the `preindex` extra) | The survey falls back to Python-only parsing and records that the pack was absent. | [pyproject.toml](pyproject.toml:20) — the pin lives in the same optional extra as the parser · [preindex.py](tools/coyodex/preindex.py:587) — the survey records whether the grammars were available for this run |
| **D5** | pytest | library | Testing & type checking | developer-only Python package, test runner | Runs the coyodex test suite. Only a coyodex developer installs pytest. | [pyproject.toml](pyproject.toml:25) | verified | yes | pytest >=8 (pyproject.toml, the `dev` extra) |  | [pyproject.toml](pyproject.toml:25) — the pin sits in the developer-only extra · [pyproject.toml](pyproject.toml:35) — the two test folders the runner reads by default |
| **D6** | pyright | library | Testing & type checking | developer-only Python package, type checker | Checks types across the coyodex code. Only a coyodex developer installs pyright. | [pyproject.toml](pyproject.toml:26) | verified | yes | pyright >=1.1 (pyproject.toml, the `dev` extra) |  | [pyproject.toml](pyproject.toml:26) — the pin sits in the developer-only extra · [pyrightconfig.json](pyrightconfig.json:2) — the two source roots the type checker is pointed at |
| **D7** | setuptools | library | Build & packaging | Python build backend | Builds and installs coyodex into its private environment. The install is editable, so an edit takes effect with no reinstall. | [pyproject.toml](pyproject.toml:2) | verified |  | setuptools >=64 (pyproject.toml, the build requirement) |  | [pyproject.toml](pyproject.toml:2) — the build backend and its minimum version · [Makefile](Makefile:40) — setup installs the package editable into the private environment |
| **D8** | Mermaid | library | Frontend / UI | browser JavaScript library, fetched from a content delivery network | Draws every diagram in the viewer. The browser fetches Mermaid from a pinned web address and rejects a tampered copy. | [viewer.html](tools/coyodex/viewer/viewer.html:19) | verified |  | mermaid 11.15.0 (viewer.html, pinned with an integrity hash) |  | [viewer.html](tools/coyodex/viewer/viewer.html:19) — the exact version and the integrity hash the browser checks |
| **D9** | svg-pan-zoom | library | Frontend / UI | browser JavaScript library, fetched from a content delivery network | Lets a reader pan and zoom a diagram. The browser fetches svg-pan-zoom from a pinned web address with an integrity hash. | [viewer.html](tools/coyodex/viewer/viewer.html:16) | verified |  | svg-pan-zoom 3.6.1 (viewer.html, pinned with an integrity hash) |  | [viewer.html](tools/coyodex/viewer/viewer.html:16) — the exact version and the integrity hash the browser checks |
| **D10** | highlight.js | library | Frontend / UI | browser JavaScript library, fetched on demand from a content delivery network | Colours the code shown in the source column. The fetch happens only the first time a file is opened. | [viewer.js](tools/coyodex/viewer/viewer.js:9902) | verified |  | highlight.js 11.9.0 (viewer.js, pinned with an integrity hash) | Plain uncoloured code, whenever the library cannot be fetched. | [viewer.js](tools/coyodex/viewer/viewer.js:9902) — the pinned address, version and integrity hash · [viewer.js](tools/coyodex/viewer/viewer.js:9918) — a failed fetch degrades to uncoloured text instead of breaking the page |
| **D11** | web browser | platform | Code viewing | desktop application the reader already has | Shows the viewer. Starting the map server opens the landing page in the reader's default browser. | [serve.py](tools/coyodex/viewer/serve.py:806) | verified |  |  |  | [serve.py](tools/coyodex/viewer/serve.py:806) — the server hands the landing page address to the default browser · [Makefile](Makefile:119) — the start command asks for the browser to be opened |
| **D12** | Claude Code | platform |  | AI coding agent that hosts the coyodex skill | Runs the coyodex method. Installing copies the skill into the Claude Code skills folder, with this clone's path baked in. | [Makefile](Makefile:17) | verified |  |  |  | [Makefile](Makefile:17) — the first skills folder written is the Claude Code one · [Makefile](Makefile:58) — the skill file is copied in with the clone's path substituted |
| **D13** | Codex | platform | Coding agents | AI coding agent that hosts the coyodex skill | Runs the coyodex method. Installing copies the skill into the shared cross-agent skills folder Codex reads. | [Makefile](Makefile:17) | verified |  |  |  | [Makefile](Makefile:17) — the second skills folder written is the cross-agent one Codex reads · [Makefile](Makefile:58) — the skill file is copied in with the clone's path substituted |
| **D14** | Cursor | platform | Coding agents | AI coding agent, and a code editor | Runs the coyodex method. Cursor reads both skills folders the installer writes, so it needs no folder of its own. | [Makefile](Makefile:17) | verified |  |  |  | [Makefile](Makefile:17) — both folders written are read by Cursor, so no third folder is created · [viewer.js](tools/coyodex/viewer/viewer.js:10610) — Cursor is also one of the editors a source link can open |
| **D15** | GitHub | service | Code viewing | code-hosting website, reached as a plain link | Opens a box's source file in a browser. The link is pinned to the commit the map was built from. | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:125) | verified |  |  |  | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:125) — the repository address is derived from the project's `origin` remote · [viewer.js](tools/coyodex/viewer/viewer.js:10707) — the file link is built from that address plus the map's commit |
| **D16** | code editor | platform | Code viewing | desktop editor, opened by a link scheme | Opens a box's source file at its line. The reader picks one editor once, from a list of eleven. | [viewer.js](tools/coyodex/viewer/viewer.js:10606) | verified |  |  |  | [viewer.js](tools/coyodex/viewer/viewer.js:10609) — one row of the editor table, holding the link that opens a file at a line · [viewer.js](tools/coyodex/viewer/viewer.js:10622) — only known editor link schemes are allowed through |

---

## T2b — Interfaces (the product's outside edge)

| ID | Name | Side | Kind | Facing | Crosses | What it is | Actors | Ways in | Deps | Source | Conf. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **I1** | Map commands | ours | command-line | user |  | How a person builds a map, checks it, serves it and accepts a change into it. | R1, R2 | 32 |  | [cli.py](tools/coyodex/cli.py:105) | verified |
| **I2** | Developer commands | ours | command-line | operator |  | How a coyodex developer scores a map's quality and reviews a finished build. | R3 | 21 |  | [cli.py](eval/tools/coyodex_eval/cli.py:47) | verified |
| **I3** | Map viewer | ours | screen | user |  | The browser page where a reader looks at a map and the code behind any box. | R1 | 28 |  | [serve.py](tools/coyodex/viewer/serve.py:633) | verified |
| **I4** | Agent skill | ours | agent-tools | user |  | How a coding agent is asked, in plain words, to build or update a map. | R1, R2 | 5 | D12, D13, D14 | [dispatch.md](method/dispatch.md:62) | verified |
| **I5** | Developer skills | ours | agent-tools | operator |  | How a coyodex developer asks an agent to score a map or review a build. | R3 | 2 |  | [SKILL.md](eval/SKILL.md:28) | verified |
| **I6** | Map files in your repo | ours | file | user |  | The map coyodex writes next to the code, which a person opens and git shows. |  |  |  | [assemble.py](tools/coyodex/assemble.py:963) | verified |
| **I7** | Settings | ours | settings | user |  | The values the person running coyodex sets: which clone, which port, what to leave out. |  |  |  |  | verified |
| **I8** | Project source files | theirs | content | user |  | The code being mapped. coyodex did not write it, and reading it is the whole job. |  |  |  |  | verified |
| **I9** | Coding agent's build transcript | theirs | content | operator |  | The records an agent wrote while building a map, read back to review the run. |  |  | D12 |  | verified |
| **I10** | GitHub | theirs | handoff | user |  | Where a reader continues, when they follow a code link out of the viewer. | R1 |  | D15 |  | verified |
| **I11** | Code editor | theirs | handoff | user |  | The editor coyodex opens on the reader's own machine, at the line they clicked. | R1 |  | D16 |  | verified |

---

## T3 — How to run / build / test

| Action | Command | Source |
|---|---|---|
| Install the coyodex skill into the coding agents | make install | Makefile:54 |
| Install the coyodex command and the parser pack, without the skill | make deps | Makefile:39 |
| Install the developer test and type-check tools | make dev | Makefile:44 |
| Install the two developer skills, for evaluating and reviewing builds | make install-dev | Makefile:91 |
| Start the local map server and open the landing page | make start | Makefile:118 |
| Run the tests | .venv/bin/pytest tests eval/tests | pyproject.toml:35 |
| Run the type checker | .venv/bin/pyright coyodex | pyrightconfig.json:2 |
| Remove the coyodex skill from the coding agents | make uninstall | Makefile:97 |
| Remove the two developer skills | make uninstall-dev | Makefile:94 |
| Delete the private environment, so the next install rebuilds it | make clean | Makefile:122 |

---

## T4 — Entry points

| Kind | Trigger | Code entity | Component | Cadence |
|---|---|---|---|---|
| agent-skill | A coyodex developer runs the retro skill to review a build that has already finished. | [SKILL.md](eval/retro/SKILL.md:28) | C77 |  |
| agent-skill | A coyodex developer runs the eval skill to score one project's map against an earlier map of the same code. | [SKILL.md](eval/SKILL.md:28) | C77 |  |
| cli | coyodex-eval archive | [archive.py](eval/tools/coyodex_eval/archive.py:159) | C66 |  |
| cli | coyodex-eval | [cli.py](eval/tools/coyodex_eval/cli.py:56) | C63 |  |
| cli | coyodex-eval compare | [compare.py](eval/tools/coyodex_eval/compare.py:606) | C63 |  |
| cli | coyodex-eval cost | [cost.py](eval/tools/coyodex_eval/cost.py:674) | C64 |  |
| cli | coyodex-eval mutate plant | [mutate.py](eval/tools/coyodex_eval/mutate.py:244) | C63 |  |
| cli | coyodex-eval mutate score | [mutate.py](eval/tools/coyodex_eval/mutate.py:249) | C63 |  |
| cli | coyodex-eval process | [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:3130) | C65 |  |
| cli | coyodex-eval process --diff | [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:3134) | C65 |  |
| cli | coyodex-eval score | [profile.py](eval/tools/coyodex_eval/profile.py:443) | C63 |  |
| cli | coyodex-eval retro-precheck | [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:249) | C66 |  |
| cli | coyodex-eval run | [run.py](eval/tools/coyodex_eval/run.py:192) | C63 |  |
| cli | coyodex-eval claims | [run.py](eval/tools/coyodex_eval/run.py:279) | C63 |  |
| cli | coyodex-eval hash | [run.py](eval/tools/coyodex_eval/run.py:338) | C63 |  |
| cli | coyodex-eval judge | [run.py](eval/tools/coyodex_eval/run.py:353) | C63 |  |
| cli | coyodex-eval protocol | [run.py](eval/tools/coyodex_eval/run.py:418) | C63 |  |
| cli | coyodex-eval bless | [run.py](eval/tools/coyodex_eval/run.py:463) | C63 |  |
| cli | coyodex-eval transcript | [transcript.py](eval/tools/coyodex_eval/transcript.py:1067) | C64 |  |
| agent-skill | A person asks coyodex to analyze, when a map exists and the code has moved on since it was pinned. | [dispatch.md](method/dispatch.md:151) | C75 |  |
| agent-skill | A person says the change report looks right, so coyodex folds the report into the map. | [dispatch.md](method/dispatch.md:154) | C75 |  |
| agent-skill | A person asks in plain words to move, rename, split or drill deeper into a part of the map. | [dispatch.md](method/dispatch.md:156) | C75 |  |
| agent-skill | A person explicitly asks to regenerate the whole map from scratch, and confirms the warning. | [dispatch.md](method/dispatch.md:171) | C75 |  |
| agent-skill | A person types the coyodex command in a project that has no map yet, so a first map is built. | [dispatch.md](method/dispatch.md:83) | C75 |  |
| cli | Running `coyodex anchor-drift` lists every code link pointing at a line that cannot be doing the work. | [anchor_drift.py](tools/coyodex/anchor_drift.py:378) | C23 |  |
| cli | `coyodex assemble` merges the build's fragments into one map and writes it. | [assemble.py](tools/coyodex/assemble.py:812) | C2 |  |
| cli | coyodex audit | [audit_model.py](tools/coyodex/audit_model.py:1307) | C14 |  |
| cli | coyodex balance | [balance.py](tools/coyodex/balance.py:231) | C15 |  |
| cli | Running `coyodex` with no command, or asking for help or the version, prints a summary. | [cli.py](tools/coyodex/cli.py:115) | C4 |  |
| cli | `coyodex contract` prints the brief one fan-out worker should receive. | [contract.py](tools/coyodex/contract.py:109) | C4 |  |
| cli | `coyodex dump` prints the whole map, or one named part of it, as data. | [dump.py](tools/coyodex/dump.py:246) | C3 |  |
| cli | coyodex finalize | [finalize.py](tools/coyodex/finalize.py:778) | C16 |  |
| cli | Running `coyodex fix dedup-security` drops an access surface that two harvest fragments both recorded. | [fix.py](tools/coyodex/fix.py:1128) | C24 |  |
| cli | Running `coyodex fix row` rewrites one row's own text inside the fragment that authored the row. | [fix.py](tools/coyodex/fix.py:1416) | C24 |  |
| cli | Running `coyodex fix apply-drift` writes the corrected line into every code link a fresh reader found had moved. | [fix.py](tools/coyodex/fix.py:149) | C24 |  |
| cli | Running `coyodex fix drop-edge` removes a disproved relation and heals the happy-path steps that rode it. | [fix.py](tools/coyodex/fix.py:399) | C24 |  |
| cli | Running `coyodex fix dedup-relation` removes one chosen copy of a relation two data cards both declare. | [fix.py](tools/coyodex/fix.py:508) | C24 |  |
| cli | Running `coyodex fix dedup-edge` keeps one code link for a relation declared at several different lines. | [fix.py](tools/coyodex/fix.py:739) | C24 |  |
| cli | Running `coyodex fix security-row` rewrites one access surface's text, and refuses when the selector matches more than one row. | [fix.py](tools/coyodex/fix.py:976) | C24 |  |
| cli | Running `coyodex grounding write` derives the four counts and writes them into a build fragment. | [grounding.py](tools/coyodex/grounding.py:1003) | C23 |  |
| cli | Running `coyodex grounding by-element` shows, per map element, what a fresh reader proved against the label its author typed. | [grounding.py](tools/coyodex/grounding.py:1049) | C23 |  |
| cli | Running `coyodex grounding report` lists which claims were disproved, tied, unsettled, or never voted on. | [grounding.py](tools/coyodex/grounding.py:1073) | C23 |  |
| cli | Running `coyodex grounding lint` checks the verdict files for shape while the reader that wrote them is still reachable. | [grounding.py](tools/coyodex/grounding.py:924) | C23 |  |
| cli | Running `coyodex grounding refutations` fails the build when the map still carries a claim a fresh reader disproved. | [grounding.py](tools/coyodex/grounding.py:974) | C23 |  |
| cli | `python -m coyodex.json_schema` prints the published schema for the map file. | [json_schema.py](tools/coyodex/json_schema.py:432) | C1 |  |
| cli | `coyodex lint-fragment` checks one worker's fragment before the worker returns it. | [lint_fragment.py](tools/coyodex/lint_fragment.py:353) | C2 |  |
| cli | `coyodex diff` reports what changed between two versions of a map, row by row. | [mapdiff.py](tools/coyodex/mapdiff.py:198) | C3 |  |
| cli | A coding agent reads an already measured codebase back as a readable summary. | [preindex.py](tools/coyodex/preindex.py:518) | C33 |  |
| cli | A coding agent sizes a codebase before choosing how coarse the map should be. | [preindex.py](tools/coyodex/preindex.py:557) | C33 |  |
| cli | Running `coyodex provenance show` prints the conversations that built this map, newest last. | [provenance.py](tools/coyodex/provenance.py:293) | C25 |  |
| cli | Running `coyodex provenance stamp` records this conversation's id, the build minute and the code commit. | [provenance.py](tools/coyodex/provenance.py:308) | C25 |  |
| cli | Running `coyodex reconcile` expands path rules into an assignment file and names every rule that matched nothing. | [reconcile_build.py](tools/coyodex/reconcile_build.py:329) | C25 |  |
| cli | `coyodex record` writes one accepted-advisory line under a named heading. | [record.py](tools/coyodex/record.py:194) | C3 |  |
| cli | `coyodex scope` says which files will be analysed and which commit the map will name. | [scope.py](tools/coyodex/scope.py:167) | C4 |  |
| cli | coyodex validate | [validate_model.py](tools/coyodex/validate_model.py:4663) | C13 |  |
| cli | python -m coyodex.viewer.gen_viewer <graph file> <output file> | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:3298) | C44 |  |
| cli | coyodex render <map file> <output text file> | [render.py](tools/coyodex/viewer/render.py:53) | C45 |  |
| poller | The server checks whether its own code changed since it started, and warns once | [serve.py](tools/coyodex/viewer/serve.py:180) | C43 | every 2s ([serve.py](tools/coyodex/viewer/serve.py:145)) |
| poller | The server checks whether a map changed on disk, and drops what it cached | [serve.py](tools/coyodex/viewer/serve.py:210) | C43 | on every project request ([serve.py](tools/coyodex/viewer/serve.py:592)) |
| http-route | GET / | [serve.py](tools/coyodex/viewer/serve.py:583) | C43 |  |
| http-route | GET /static/<file> | [serve.py](tools/coyodex/viewer/serve.py:586) | C43 |  |
| http-route | GET /api/recents | [serve.py](tools/coyodex/viewer/serve.py:614) | C43 |  |
| http-route | GET /api/browse?path= | [serve.py](tools/coyodex/viewer/serve.py:621) | C43 |  |
| http-route | POST /api/open | [serve.py](tools/coyodex/viewer/serve.py:643) | C43 |  |
| http-route | POST /api/forget | [serve.py](tools/coyodex/viewer/serve.py:650) | C43 |  |
| http-route | POST /api/reorder | [serve.py](tools/coyodex/viewer/serve.py:660) | C43 |  |
| http-route | GET /p/<project>/ | [serve.py](tools/coyodex/viewer/serve.py:671) | C43 |  |
| http-route | GET /p/<project>/api/health | [serve.py](tools/coyodex/viewer/serve.py:675) | C43 |  |
| http-route | GET /p/<project>/api/view | [serve.py](tools/coyodex/viewer/serve.py:677) | C43 |  |
| http-route | GET /p/<project>/api/tree | [serve.py](tools/coyodex/viewer/serve.py:686) | C43 |  |
| http-route | GET /p/<project>/api/symbols | [serve.py](tools/coyodex/viewer/serve.py:691) | C43 |  |
| http-route | GET /p/<project>/api/src?path=&at= | [serve.py](tools/coyodex/viewer/serve.py:695) | C43 |  |
| http-route | GET /p/<project>/api/impact?base=&target= | [serve.py](tools/coyodex/viewer/serve.py:721) | C43 |  |
| http-route | GET /p/<project>/api/impactcommits | [serve.py](tools/coyodex/viewer/serve.py:732) | C43 |  |
| http-route | GET /p/<project>/api/impactsrcdiff?path=&base=&target= | [serve.py](tools/coyodex/viewer/serve.py:735) | C43 |  |
| worker-thread | Each browser request gets its own worker thread | [serve.py](tools/coyodex/viewer/serve.py:800) | C43 | one per request ([serve.py](tools/coyodex/viewer/serve.py:800)) |
| startup-hook | Starting with the open option pops the landing page up in a browser | [serve.py](tools/coyodex/viewer/serve.py:806) | C43 | on-boot ([serve.py](tools/coyodex/viewer/serve.py:805)) |
| server-loop | The server takes requests until someone stops it | [serve.py](tools/coyodex/viewer/serve.py:808) | C43 | continuous ([serve.py](tools/coyodex/viewer/serve.py:808)) |
| signal-handler | Pressing the stop key closes the listening port | [serve.py](tools/coyodex/viewer/serve.py:812) | C43 | on stop ([serve.py](tools/coyodex/viewer/serve.py:810)) |
| cli | coyodex serve [folder] [--port N] [--open] | [serve.py](tools/coyodex/viewer/serve.py:852) | C43 |  |
| ui-route | Opens the Features tab, under Product | [viewer.html](tools/coyodex/viewer/viewer.html:120) | C56 |  |
| ui-route | Opens the Happy Path tab, under Product | [viewer.html](tools/coyodex/viewer/viewer.html:121) | C55 |  |
| ui-route | Opens the Rules tab, under Product | [viewer.html](tools/coyodex/viewer/viewer.html:127) | C56 |  |
| ui-route | Opens the Entities tab, under Data | [viewer.html](tools/coyodex/viewer/viewer.html:130) | C55 |  |
| ui-route | Opens the Storage tab, under Data | [viewer.html](tools/coyodex/viewer/viewer.html:131) | C56 |  |
| ui-route | Opens the Subsystems tab, under Under the hood | [viewer.html](tools/coyodex/viewer/viewer.html:136) | C55 |  |
| ui-route | Opens the Dependencies tab, under Under the hood | [viewer.html](tools/coyodex/viewer/viewer.html:137) | C55 |  |
| ui-route | Opens the Tests tab, under Under the hood | [viewer.html](tools/coyodex/viewer/viewer.html:138) | C56 |  |
| ui-route | Opens the Deployment tab, under Under the hood | [viewer.html](tools/coyodex/viewer/viewer.html:140) | C55 |  |
| ui-route | Opens the System tab, under Under the hood | [viewer.html](tools/coyodex/viewer/viewer.html:141) | C56 |  |
| ui-route | Opens the Glossary tab, its own group | [viewer.html](tools/coyodex/viewer/viewer.html:145) | C56 |  |
| event-consumer | The browser window changes size, so the drawing refits itself to the new space | [viewer.js](tools/coyodex/viewer/viewer.js:10593) | C55 | continuous ([viewer.js](tools/coyodex/viewer/viewer.js:10593)) |
| startup-hook | A reader opens a map for the first time in this browser, so the guide to getting around opens by itself | [viewer.js](tools/coyodex/viewer/viewer.js:10853) | C57 | on-boot ([viewer.js](tools/coyodex/viewer/viewer.js:10853)) |
| startup-hook | The map's page loads, so the viewer checks the server is alive and loads the project's file tree | [viewer.js](tools/coyodex/viewer/viewer.js:11366) | C58 | on-boot ([viewer.js](tools/coyodex/viewer/viewer.js:11366)) |
| ui-route | Opens a project's map in a browser, landing on the first view the map offers | [viewer.js](tools/coyodex/viewer/viewer.js:11694) | C57 |  |
| startup-hook | The map's page loads, so the viewer fetches the whole map from the server before drawing anything | [viewer.js](tools/coyodex/viewer/viewer.js:154) | C57 | on-boot ([viewer.js](tools/coyodex/viewer/viewer.js:154)) |
| event-consumer | Any screen writes new text, so every glossary word inside that text becomes a link with no reader action | [viewer.js](tools/coyodex/viewer/viewer.js:479) | C56 | continuous ([viewer.js](tools/coyodex/viewer/viewer.js:479)) |
| cli | python tools/map_backup.py stamp | [map_backup.py](tools/map_backup.py:452) | C66 |  |
| cli | python tools/map_backup.py backup | [map_backup.py](tools/map_backup.py:478) | C66 |  |

---

## Subdomains (SD) — bounded contexts of the domain model

| ID | Subdomain | Purpose | Parent | Source | Conf. |
|---|---|---|---|---|---|
| **SD1** | What a map holds | Every kind of thing a finished map can say about a project. |  | tools/coyodex/model.py:646 | verified |
| **SD2** | Product story | Who uses the product, what they come to do, and the one walk that tells it end to end. | SD1 | tools/coyodex/model.py:92 | verified |
| **SD3** | Machine | The parts the product is built from, what it pulls in from outside, and how the parts reach each other. | SD1 | tools/coyodex/model.py:187 | verified |
| **SD4** | Domain model | The named types a project stores, their fields, how they relate, and the states they move through. | SD1 | tools/coyodex/model.py:343 | verified |
| **SD5** | Running and deciding | What runs where, what is watched, what is configured, and every decision the product makes. | SD1 | tools/coyodex/model.py:437 | verified |
| **SD6** | Document and its record | The whole map as one file, plus the citations and judgements that say how far it can be trusted. | SD1 | tools/coyodex/model.py:646 | verified |
| **SD7** | Building a map | What a build measures, merges, assigns and stamps on the way to a finished map. |  | tools/coyodex/preindex_lib.py:312 | verified |
| **SD8** | Proving a map | The claims a map must defend, the verdicts on each, and the report saying which checks ran. |  | tools/coyodex/audit_model.py:421 | verified |
| **SD9** | What the viewer holds | What the server keeps about each map it serves, and the shapes a view is drawn from. |  | tools/coyodex/viewer/build_graph.py:28 | verified |
| **SD10** | Judging a map | How one map measures against another, and what the judges said about both. |  | eval/tools/coyodex_eval/profile.py:39 | verified |

---

## T5 — Domain model (domain cards)

**E1 — ProjectModel** *(project-map.json — collection; one file per project, written byte-identically so a rebuild diffs cleanly)*
SUBDOMAIN: SD6
MEANING: The whole map as one document, holding every element the analysis produced.
FIELDS: format:string · title:string · goal:string · commit:string ? · built:string ? · roles:E2 [] · glossary:E4 [] · capabilities:E5 [] · use_cases:E6 [] · happy_path:E9 [] · subsystems:E5 [] · components:E13 [] · deps:E14 [] · run_commands:E17 [] · entry_points:E16 [] · subdomains:E5 [] · entities:E18 [] · non_entity_types:E22 [] · flows:E10 [] · subflows:E12 [] · edges:E15 [] · messaging:E25 [] · deployment:E26 [] · environments:string [] · observability:E28 [] · security:E29 [] · config:E30 [] · tests:E31 [] · grounding:E35 ? · blocks:E5 [] · rules:E33 [] · extras:E36 []
RELATIONS: contains 1→* E2 · contains 1→* E4 · contains 1→* E5 · contains 1→* E6 · contains 1→* E9 · contains 1→* E10 · contains 1→* E12 · contains 1→* E13 · contains 1→* E14 · contains 1→* E15 · contains 1→* E16 · contains 1→* E17 · contains 1→* E18 · contains 1→* E22 · contains 1→* E25 · contains 1→* E26 · contains 1→* E28 · contains 1→* E29 · contains 1→* E30 · contains 1→* E31 · contains 1→* E33 · contains 1→0..1 E35 · contains 1→* E36
SOURCE: [model.py](tools/coyodex/model.py:646)

**E2 — Role** *(project-map.json — embedded)*
SUBDOMAIN: SD2
MEANING: One kind of actor the code recognises, either a person or a program.
FIELDS: id:string PK · name:string · kind:string · audience:string · wants:string · drives:string · relations:E3 []
RELATIONS: contains 1→* E3
SOURCE: [model.py](tools/coyodex/model.py:56)

**E3 — RoleRelation** *(project-map.json — embedded)*
SUBDOMAIN: SD2
MEANING: A link saying one actor turns into another, or may do everything another may do.
FIELDS: kind:string · role:string FK→E2 · at:string ?
SOURCE: [model.py](tools/coyodex/model.py:40)

**E4 — GlossaryRow** *(project-map.json — embedded)*
SUBDOMAIN: SD2
MEANING: One product word, its plain meaning, and the place in code the word belongs to.
FIELDS: term:string PK · meaning:string · source:string ? · aliases:string [] · no_autolink:bool
SOURCE: [model.py](tools/coyodex/model.py:75)

**E5 — Group** *(project-map.json — embedded; four separate forests share this one shape)*
SUBDOMAIN: SD3
MEANING: A named box gathering members: a feature, a subsystem, a subdomain, or a decision area.
FIELDS: id:string PK · name:string · purpose:string · parent:string ? FK→E5 · happy_path:string · stakes:E7 [] · story:E8 ? · source:string ? · confidence:string · tech:string · tech_source:string
RELATIONS: contains 1→* E5 · contains 1→* E7 · contains 1→0..1 E8
SOURCE: [model.py](tools/coyodex/model.py:145)

**E6 — UseCase** *(project-map.json — embedded)*
SUBDOMAIN: SD2
MEANING: One job an actor comes to the product to get done.
FIELDS: id:string PK · name:string · actors:string [] FK→E2 · trigger_outcome:string · capability:string ? FK→E5 · entry_points:string [] FK→E16
RELATIONS: drivenBy *→* E2 · belongsTo *→1 E5 · startsAt *→* E16
SOURCE: [model.py](tools/coyodex/model.py:92)

**E7 — Stake** *(project-map.json — embedded)*
SUBDOMAIN: SD2
MEANING: What one actor comes to a feature to do, said in a short verb phrase.
FIELDS: actor:string FK→E2 · stake:string
RELATIONS: heldBy *→1 E2
SOURCE: [model.py](tools/coyodex/model.py:121)

**E8 — StoryAnchor** *(project-map.json — embedded)*
SUBDOMAIN: SD2
MEANING: Where a feature the main walk never reaches sits in the one product story.
FIELDS: place:string · feature:string FK→E5
SOURCE: [model.py](tools/coyodex/model.py:131)

**E9 — HappyStep** *(project-map.json — embedded)*
SUBDOMAIN: SD2
MEANING: One position in the ordered walk through the product's main story.
FIELDS: id:string PK · title:string · uc:string ? FK→E6 · why:string ?
RELATIONS: realizes *→1 E6
SOURCE: [model.py](tools/coyodex/model.py:113)

**E10 — Flow** *(project-map.json — embedded)*
SUBDOMAIN: SD2
MEANING: The inside view of one job, as an ordered run of interactions.
FIELDS: uc:string FK→E6 · title:string · steps:E11 []
RELATIONS: realizes 1→1 E6 · contains 1→* E11
SOURCE: [model.py](tools/coyodex/model.py:392)

**E11 — FlowStep** *(project-map.json — embedded)*
SUBDOMAIN: SD2
MEANING: One interaction inside a job, from a starting box to a receiving box.
FIELDS: n:int · src:string · dst:string · phrase:string · note:string · where:string ? · no_call_site:bool · subflow:string ? FK→E12
SOURCE: [model.py](tools/coyodex/model.py:368)

**E12 — SubFlow** *(project-map.json — embedded)*
SUBDOMAIN: SD2
MEANING: A named run of steps that several jobs share, written down once.
FIELDS: id:string PK · name:string · steps:E11 []
RELATIONS: contains 1→* E11
SOURCE: [model.py](tools/coyodex/model.py:399)

**E13 — Component** *(project-map.json — embedded)*
SUBDOMAIN: SD3
MEANING: One module-sized piece of the code, named and described in plain words.
FIELDS: id:string PK · name:string · subsystem:string ? FK→E5 · purpose:string · entry_point:string ? · depends_on:string · source:string ? · confidence:string · files:string [] · runs_in:string [] FK→E26 · evidence:E32 [] · states:E23 ? · extra:json
RELATIONS: belongsTo *→1 E5 · contains 1→* E32 · has 1→0..1 E23 · runsIn *→* E26
SOURCE: [model.py](tools/coyodex/model.py:187)

**E14 — Dep** *(project-map.json — embedded)*
SUBDOMAIN: SD3
MEANING: One outside thing the product leans on, such as a database or a library.
FIELDS: id:string PK · name:string · kind:string ? · type:string · used_for:string · bucket:string · where_configured:string · confidence:string · deployment_linked:bool · package:string · alternative:string · evidence:E32 [] · extra:json
RELATIONS: contains 1→* E32
SOURCE: [model.py](tools/coyodex/model.py:212)

**E15 — Edge** *(project-map.json — embedded)*
SUBDOMAIN: SD3
MEANING: One backbone arrow: a piece of code reaching another, plus the calling line.
FIELDS: src:string · verb:string · dst:string · why:string ? · where:string ? · no_call_site:bool
SOURCE: [model.py](tools/coyodex/model.py:412)

**E16 — EntryPoint** *(project-map.json — embedded)*
SUBDOMAIN: SD3
MEANING: One front door into the product, such as a route, a command, or a timed job.
FIELDS: id:string PK · kind:string · trigger:string · source:string · component:string FK→E13 · activation:string · runs_in:string [] FK→E26 · cadence:string · cadence_source:string
RELATIONS: livesIn *→1 E13 · runsIn *→* E26
SOURCE: [model.py](tools/coyodex/model.py:238)

**E17 — RunRow** *(project-map.json — embedded)*
SUBDOMAIN: SD5
MEANING: One command a person runs on the project, and the file defining that command.
FIELDS: action:string PK · command:string · source:string
SOURCE: [model.py](tools/coyodex/model.py:230)

**E18 — Entity** *(project-map.json — embedded)*
SUBDOMAIN: SD4
MEANING: One real named type the product works with, drawn as a box with its attributes.
FIELDS: id:string PK · name:string · store:E21 ? · meaning:string · subdomain:string ? FK→E5 · source:string ? · fields:E19 [] · relations:E20 [] · states:E23 ?
RELATIONS: belongsTo *→1 E5 · has 1→0..1 E21 · contains 1→* E19 · contains 1→* E20 · has 1→0..1 E23
SOURCE: [model.py](tools/coyodex/model.py:343)

**E19 — EntityField** *(project-map.json — embedded)*
SUBDOMAIN: SD4
MEANING: One attribute on a type: its name, the kind of value it holds, and its markers.
FIELDS: name:string · type:string · markers:string []
SOURCE: [model.py](tools/coyodex/model.py:268)

**E20 — EntityRelation** *(project-map.json — embedded; authored on the source type only, never on both)*
SUBDOMAIN: SD4
MEANING: One arrow between two types, with its verb and how many sit at each end.
FIELDS: verb:string · target:string FK→E18 · src_card:string ? · dst_card:string ? · display:string · how:string ? · keyed_by:string []
SOURCE: [model.py](tools/coyodex/model.py:275)

**E21 — Store** *(project-map.json — embedded)*
SUBDOMAIN: SD4
MEANING: Where a type physically lives: which outside store, which compartment, in what shape.
FIELDS: dep:string ? FK→E14 · container:string · mode:string · notes:string
RELATIONS: livesIn *→1 E14
SOURCE: [model.py](tools/coyodex/model.py:327)

**E22 — NonEntityType** *(project-map.json — embedded)*
SUBDOMAIN: SD4
MEANING: A named type left out of the domain model on purpose, carrying the reason why.
FIELDS: name:string PK · source:string ? · why:string
SOURCE: [model.py](tools/coyodex/model.py:358)

**E23 — StateMachine** *(project-map.json — embedded)*
SUBDOMAIN: SD4
MEANING: A lifecycle the code really implements: its states, its moves, and the declaring line.
FIELDS: states:string [] · transitions:E24 [] · source:string
RELATIONS: contains 1→* E24
SOURCE: [model.py](tools/coyodex/model.py:314)

**E24 — StateTransition** *(project-map.json — embedded)*
SUBDOMAIN: SD4
MEANING: One move from one state to another, plus the trigger that causes the move.
FIELDS: src:string · dst:string · on:string
SOURCE: [model.py](tools/coyodex/model.py:307)

**E25 — MessagingRow** *(project-map.json — embedded)*
SUBDOMAIN: SD5
MEANING: One channel messages travel on, with who puts messages in and who takes them out.
FIELDS: name:string PK · kind:string · broker:string FK→E14 · publishers:string [] FK→E13 · consumers:string [] FK→E13 · payload:string FK→E18 · source:string
RELATIONS: carriedBy *→1 E14 · movedBy *→* E13 · carries *→0..1 E18
SOURCE: [model.py](tools/coyodex/model.py:291)

**E26 — DeploymentRow** *(project-map.json — embedded)*
SUBDOMAIN: SD5
MEANING: One running process the product ships, where it runs and how it is reached.
FIELDS: unit:string PK · runs_on:string · exposed_as:string · config_source:string · variants:E27 []
RELATIONS: contains 1→* E27
SOURCE: [model.py](tools/coyodex/model.py:437)

**E27 — VariantTag** *(project-map.json — embedded)*
SUBDOMAIN: SD5
MEANING: One environment a process belongs to, plus the setup line proving that placement.
FIELDS: env:string · source:string
SOURCE: [model.py](tools/coyodex/model.py:424)

**E28 — ObservabilityRow** *(project-map.json — embedded)*
SUBDOMAIN: SD5
MEANING: One signal the product emits, where it comes out, and where a person reads it.
FIELDS: signal:string PK · where_emitted:string · where_viewed:string · alerts:string
SOURCE: [model.py](tools/coyodex/model.py:452)

**E29 — SecurityRow** *(project-map.json — embedded; older storage for access facts; a new map states them as business rules)*
SUBDOMAIN: SD5
MEANING: One guarded surface, who may pass it, and what the guard's limit costs.
FIELDS: surface:string PK · who:string · source:string · risk:string
SOURCE: [model.py](tools/coyodex/model.py:460)

**E30 — ConfigRow** *(project-map.json — embedded)*
SUBDOMAIN: SD5
MEANING: One setting the product reads, what the setting is for, and its default.
FIELDS: key:string PK · purpose:string · default:string · per_env:string
SOURCE: [model.py](tools/coyodex/model.py:469)

**E31 — TestRow** *(project-map.json — embedded)*
SUBDOMAIN: SD5
MEANING: One line of the test gap table: what is covered, by which suites, and what is missing.
FIELDS: targets:string [] · tested:string · label:string · tests:E32 [] · gap:string · confidence:string
RELATIONS: contains 1→* E32
SOURCE: [model.py](tools/coyodex/model.py:477)

**E32 — EvidenceItem** *(project-map.json — embedded)*
SUBDOMAIN: SD6
MEANING: One citation: a line in the code, and why that line backs the claim beside it.
FIELDS: file:string · why:string
SOURCE: [model.py](tools/coyodex/model.py:179)

**E33 — BusinessRule** *(project-map.json — embedded)*
SUBDOMAIN: SD5
MEANING: One decision the product makes, written in product words and naming no code.
FIELDS: id:string PK · statement:string · name:string · block:string ? FK→E5 · sites:E34 [] · access:bool · risk:string · confidence:string
RELATIONS: belongsTo *→1 E5 · contains 1→* E34
SOURCE: [model.py](tools/coyodex/model.py:508)

**E34 — RuleSite** *(project-map.json — embedded)*
SUBDOMAIN: SD5
MEANING: One line that actually enforces a decision, and what that line does for it.
FIELDS: where:string ? · why:string · no_call_site:bool
SOURCE: [model.py](tools/coyodex/model.py:490)

**E35 — Grounding** *(project-map.json — embedded)*
SUBDOMAIN: SD6
MEANING: How much of the map the skeptics challenged, and how those challenges came out.
FIELDS: claims_total:int · claims_challenged:int · claims_confirmed:int · claims_refuted:int · claims_unverifiable:int · claims_superseded:int · claims_added_since:int · live_claims_digest:string · claims_live_challenged:int · note:string
RELATIONS: counts 1→* E41 {the record keeps totals only, so it names no single claim}
SOURCE: [model.py](tools/coyodex/model.py:565)

**E36 — ExtraSection** *(project-map.json — embedded)*
SUBDOMAIN: SD6
MEANING: An authored section the schema does not know, kept word for word.
FIELDS: heading:string PK · body:string
SOURCE: [model.py](tools/coyodex/model.py:558)

**E37 — Symbol** *(preindex.json — embedded)*
SUBDOMAIN: SD7
MEANING: One definition found in the code: its name, its kind, its file, and its line span.
FIELDS: name:string · kind:string · file:string · line:int · end:int ?
SOURCE: [preindex_lib.py](tools/coyodex/preindex_lib.py:312)

**E38 — DirExpectation** *(preindex.json — embedded)*
SUBDOMAIN: SD7
MEANING: How many components one folder should yield, worked out from its file count and size.
FIELDS: path:string PK · files:int · loc:int · expected:int · children:E38 []
RELATIONS: contains 1→* E38
SOURCE: [preindex_lib.py](tools/coyodex/preindex_lib.py:533)

**E39 — FragmentLoad** *(transient)*
SUBDOMAIN: SD7
MEANING: The result of reading the workers' map pieces: what loaded, what was skipped, what failed.
FIELDS: parts:E1 [] · notes:string [] · errors:string []
RELATIONS: contains 1→* E1
SOURCE: [assemble.py](tools/coyodex/assemble.py:222)

**E40 — Reconcile** *(reconcile.json — collection)*
SUBDOMAIN: SD7
MEANING: The lead's after-the-fact assignments, re-applied every time the map is rebuilt.
FIELDS: sets:json [] · drop_edges:json [] · keep_edges:json [] · set_anchors:json [] · drop_relations:json []
RELATIONS: assignsInto *→1 E1 {the file names map elements by id, and the merge applies it while building}
SOURCE: [reconcile.py](tools/coyodex/reconcile.py:159)

**E41 — WorkItem** *(worklist.json — collection)*
SUBDOMAIN: SD8
MEANING: One claim the map makes, handed to a fresh reader with the job of disproving it.
FIELDS: claim:string PK · anchor:string ? · why_risky:string · detail:string ? · drift_eligible:bool · theme:string
RELATIONS: challenges *→1 E1 {the wording is copied in as plain text, and the map holds no pointer back}
SOURCE: [audit_model.py](tools/coyodex/audit_model.py:421)

**E42 — Audit finding** *(transient)*
SUBDOMAIN: SD8
MEANING: One place the map contradicts itself, with how bad the contradiction is.
FIELDS: check:string · severity:string · location:string · message:string
RELATIONS: reports *→1 E1 {the place is written as plain prose, so nothing joins the two automatically}
SOURCE: [audit_model.py](tools/coyodex/audit_model.py:413)

**E43 — ElementCheck** *(projection; recomputed from the pinned claim list and the votes, never stored)*
SUBDOMAIN: SD8
MEANING: One map element beside what the skeptics actually did to the claims it makes.
FIELDS: element_id:string · kind:string · label:string · stated:string · confirmed:int · refuted:int · unverifiable:int · unvoted:int
RELATIONS: summarizes 1→* E41 {the row is counted afresh from the votes each time somebody asks}
SOURCE: [grounding.py](tools/coyodex/grounding.py:412)

**E44 — SurvivingRefutation** *(projection)*
SUBDOMAIN: SD8
MEANING: A claim the skeptics disproved that the shipped map still makes, word for word.
FIELDS: claim:string FK→E41 · element_id:string · kind:string · label:string · refuted_by:int · note:string
RELATIONS: refutes *→1 E41
SOURCE: [grounding.py](tools/coyodex/grounding.py:631)

**E45 — Leg** *(finalize-report.json — embedded)*
SUBDOMAIN: SD8
MEANING: One check inside the end-of-build report, its findings, and whether the check ran.
FIELDS: name:string PK · status:string · blocking:string [] · advisory:string [] · note:string ?
STATES: ran · failed — [finalize.py](tools/coyodex/finalize.py:65)
SOURCE: [finalize.py](tools/coyodex/finalize.py:70)

**E46 — FinalizeReport** *(finalize-report.json — collection)*
SUBDOMAIN: SD8
MEANING: The end-of-build verdict: every check, its findings, and a fingerprint of the map judged.
FIELDS: map_path:string · map_sha256:string · legs:E45 [] · verdict:string · advisory_total:int · blocking_total:int
RELATIONS: contains 1→* E45
STATES: BLOCKED · INCOMPLETE · ADVISORIES · CLEAN — [finalize.py](tools/coyodex/finalize.py:488)
SOURCE: [finalize.py](tools/coyodex/finalize.py:86)

**E47 — Provenance** *(provenance.json — collection)*
SUBDOMAIN: SD7
MEANING: The record of every build of one project's map, in the order the builds happened.
FIELDS: project:string PK · repo_path:string · sessions:E48 [] · schema:string
RELATIONS: contains 1→* E48
SOURCE: [provenance.py](tools/coyodex/provenance.py:60)

**E48 — SessionEntry** *(provenance.json — embedded)*
SUBDOMAIN: SD7
MEANING: One build: when it ran, in which mode, and the code commit it read.
FIELDS: session_id:string PK · built_at:string · mode:string · code_commit:string ? · code_committed:string ?
SOURCE: [provenance.py](tools/coyodex/provenance.py:33)

**E49 — AnchorRef** *(projection; gathered from the map's own anchors whenever a change is analysed)*
SUBDOMAIN: SD7
MEANING: One code link a map element carries, split into a file and a line span.
FIELDS: eid:string · kind:string · path:string · lo:int ? · hi:int ? · field:string · is_dir:bool · owner:string ?
RELATIONS: landsIn *→0..1 E37 {the definition whose line span holds the anchor line is looked up at check time}
SOURCE: [impact_lib.py](tools/coyodex/impact_lib.py:170)

**E50 — DirectHit** *(transient)*
SUBDOMAIN: SD7
MEANING: One code link a change really touched, and how tightly the touch was pinned down.
FIELDS: eid:string FK→E49 · kind:string · path:string · change:string · resolution:string · field:string · owner:string ? · drift_to:int ? · territory:bool
RELATIONS: resolves *→1 E49
SOURCE: [impact_lib.py](tools/coyodex/impact_lib.py:289)

**E51 — Graph node** *(projection; built from the map each time a screen is served, never saved)*
SUBDOMAIN: SD9
MEANING: One box the browser draws, with its name, its code link, and its shown fields.
FIELDS: id:string PK · kind:string · name:string · file:string ? · line:int ? · fields:json · parent:string ? · attrs:json [] · dep_kind:string ? · files:string [] · entry_points:json [] · runs_in:string [] · actors:string [] · roles:string [] · store:json ? · states_count:int · states_lines:string []
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:28)

**E52 — Graph edge** *(projection)*
SUBDOMAIN: SD9
MEANING: One arrow the browser draws, carrying its verb, its counts at each end, and its label.
FIELDS: src:string FK→E51 · verb:string · dst:string FK→E51 · why:string ? · where:string ? · kind:string ? · src_card:string ? · dst_card:string ? · how:string ? · fk_fields:string [] · fk_side:string ? · keyed_by:string []
RELATIONS: joins *→1 E51
SOURCE: [build_graph.py](tools/coyodex/viewer/build_graph.py:72)

**E53 — MapProfile** *(profile.json — collection)*
SUBDOMAIN: SD10
MEANING: The countable quality signals of one built map, kept so two maps can be compared.
FIELDS: use_cases:int · subsystems:int · subdomains:int · components:int · deps:int · entities:int · edges:int · hp_steps:int · flows:int · security_surfaces:int · validate_ok:bool · validate_problems:int · validate_warnings:int · contradictions:int · audit_advisories:int · audit_warnings:int · l2_claims:int · coverage_flags:int ? · granularity_expected:int ?
RELATIONS: measures 1→1 E1 {every number is counted off the finished map, which stores none of them}
SOURCE: [profile.py](eval/tools/coyodex_eval/profile.py:39)

**E54 — JudgeReport** *(judge.json — collection)*
SUBDOMAIN: SD10
MEANING: The judged quality of one map: how many claims held up, and the rubric scores.
FIELDS: n_claims:int · n_grounded:int · grounding_passrate:float ? · dimensions:json [] · overall:float ? · n_worklist:int · n_failures:int · protocol:json ? · n_anchor_checked:int · n_anchor_drifted:int · anchor_drift_rate:float ?
RELATIONS: scores 1→1 E1 {fresh readers vote on a sample of claims, and the map records nothing of the vote}
SOURCE: [judge.py](eval/tools/coyodex_eval/judge.py:101)

**E55 — DeltaReport** *(transient; rendered to a readable report at the end of a scoring run)*
SUBDOMAIN: SD10
MEANING: The verdict comparing a new map against the accepted one, check by check.
FIELDS: verdict:string · gates:json [] · bands:json [] · notes:string [] · judge_bands:json [] · granularity:json ? · tool_delta:string ?
RELATIONS: compares *→1 E53 {the report holds the two runs' numbers side by side, not the profiles themselves} · compares *→1 E54 {the judged scores are copied in as allowed drops, not linked}
STATES: PASS · DRIFT · REGRESSED — [compare.py](eval/tools/coyodex_eval/compare.py:38)
SOURCE: [compare.py](eval/tools/coyodex_eval/compare.py:176)

**E56 — RecentsStore** *(serve-recents.json — collection; kept in the reader's home folder; every change reloads it first, so two writers merge instead of overwriting)*
SUBDOMAIN: SD9
MEANING: The project folders the reader has opened, kept in order with the newest first.
FIELDS: path:string · folders:string []
RELATIONS: resolvesTo *→* E57 {the list keeps directory names as text, and the server turns each one into a served map}
SOURCE: [recents.py](tools/coyodex/viewer/recents.py:22)

**E57 — Project** *(transient; the cached tree, screen parcel and symbol list are keyed to one map version and dropped when the map file changes)*
SUBDOMAIN: SD9
MEANING: One map the server is serving, pinned to the commit every code read uses.
FIELDS: slug:string PK · repo_root:string · map_json:string · commit:string · title:string · goal:string · map_mtime:int ? · tree:E58 ? · view:json ? · symbols:json ?
RELATIONS: has 1→0..1 E58 · loads *→1 E1 {the server reads the named file from disk on each change, and keeps no link to the loaded document}
SOURCE: [serve.py](tools/coyodex/viewer/serve.py:67)

**E58 — FileTreeNode** *(projection; built once per map version from the repository listing and the map)*
SUBDOMAIN: SD9
MEANING: One entry in the file browser's tree, saying whether the map covers that path.
FIELDS: name:string · path:string PK · dir:bool · node:string ? · others:string [] · sel:string ? · cov:string · mapped:int · ref:int · children:E58 [] · ignored:E59 ?
RELATIONS: contains 1→* E58 · has 1→0..1 E59
SOURCE: [filetree.py](tools/coyodex/viewer/filetree.py:66)

**E59 — IgnoreNote** *(embedded; carried on the tree's root entry only)*
SUBDOMAIN: SD9
MEANING: What the skip list removed from this tree, so a narrowed tree cannot pass as the whole repository.
FIELDS: files:int · patterns:string [] · unused:string []
SOURCE: [filetree.py](tools/coyodex/viewer/filetree.py:48)

---

## Non-entity types (plumbing, deliberately unmodelled)

| Type | Source | Why |
|---|---|---|
| ModelError | tools/coyodex/model.py:33 | An error raised when a map file has the wrong shape, so it carries no map data. |
| ReconcileError | tools/coyodex/reconcile.py:50 | An error raised when the lead's assignment file is malformed. |
| ImpactError | tools/coyodex/impact_git.py:43 | An error raised when a change cannot be compared against the map's pinned commit. |
| WalkResult | tools/coyodex/preindex_lib.py:156 | The file list one scan produced, used immediately and then dropped. |
| ImportRef | tools/coyodex/preindex_lib.py:321 | One import line the pre-index notes as a hint; the map stores no such row. |
| IgnoreSpec | tools/coyodex/ignorefile.py:63 | A parsed settings file saying which code the map is not meant to describe. |
| IgnoreReport | tools/coyodex/ignorefile.py:99 | A tally of what the skip list did on one scan, printed and forgotten. |
| Pin | tools/coyodex/scope.py:38 | The commit and the uncommitted files, read fresh from version control each run. |
| FlowStep (parsed) | tools/coyodex/grammar.py:577 | A step shape for the retired text reader; the map's own step replaced it. |
| Flow (parsed) | tools/coyodex/grammar.py:591 | A job shape for the retired text reader, kept beside the parsed step. |
| Hunk | tools/coyodex/impact_lib.py:36 | One block of changed lines inside a file comparison. |
| ParsedDiff | tools/coyodex/impact_lib.py:51 | The blocks of one file comparison, held only while the comparison runs. |
| FileFrame | tools/coyodex/impact_lib.py:94 | Which lines of one file a change reaches, computed and discarded. |
| Change | tools/coyodex/impact_git.py:69 | One changed file with its status, read straight from version control. |
| ImpactFile | tools/coyodex/impact_git.py:176 | A wrapper holding one changed file beside the code links it touched. |
| ImpactCore | tools/coyodex/impact_git.py:185 | A wrapper holding every changed file of one comparison. |
| ClaimTarget | tools/coyodex/audit_model.py:170 | Which map element a claim is about, worked out in order to correct it. |
| ClaimMatch | tools/coyodex/audit_model.py:185 | Whether a claim resolved to exactly one element, or to none, or to several. |
| HPStep | tools/coyodex/audit_model.py:477 | A walk step with its citations pulled out, used only while checking order. |
| RuleStepLink | tools/coyodex/validate_model.py:785 | A computed link from a decision to a job step, derived on every read. |
| VerdictLint | tools/coyodex/grounding.py:733 | The answer of a shape check over the skeptics' files, printed and dropped. |
| SetDirective | tools/coyodex/reconcile.py:75 | One line of the lead's assignment file, already covered by the file itself. |
| KeepEdgeDirective | tools/coyodex/reconcile.py:110 | One recorded choice about which duplicate arrow survives a rebuild. |
| AnchorDirective | tools/coyodex/reconcile.py:126 | One recorded correction of a code link, replayed on every rebuild. |
| Proposal | tools/coyodex/balance_lib.py:451 | A suggested split for a crowded diagram, offered to the author and dropped. |
| HeadingSpec | tools/coyodex/records.py:73 | The reading rule for one authored heading, a setting rather than map data. |
| Finding (prose) | tools/coyodex/prose.py:143 | One readability observation about one sentence of the map. |
| ArrayDiff | tools/coyodex/mapdiff.py:63 | One list's changes between two maps, shown once and not kept. |
| DiffRow | tools/coyodex/viewer/diffmap.py:15 | One line of a file comparison as the browser shows it. |
| FeatureIndex | tools/coyodex/features.py:117 | Everything the Features screen needs, worked out from the map on each request. |
| GraphDict | tools/coyodex/viewer/build_graph.py:116 | The whole parcel of data one screen receives, an envelope around the boxes. |
| ViewBundle | tools/coyodex/viewer/gen_viewer.py:3163 | The pre-drawn diagrams and data one served map hands the browser, all of it derived. |
| Handler | tools/coyodex/viewer/serve.py:567 | The web server's request handling, which is behaviour rather than recorded data. |
| _FileTreeOptional | tools/coyodex/viewer/filetree.py:59 | A typing workaround splitting out the one key only the tree's root entry carries. |
| _Dir | tools/coyodex/viewer/filetree.py:159 | A changeable folder used only while the file tree is being assembled. |
| Turn | eval/tools/coyodex_eval/transcript.py:162 | One message of a build conversation, read only to score how the build went. |
| Usage | eval/tools/coyodex_eval/transcript.py:105 | The token counts one reply was billed for, part of the cost report. |
| Actor | eval/tools/coyodex_eval/cost.py:105 | One participant in a build, counted for cost rather than mapped. |
| MapFacts | eval/tools/coyodex_eval/cost.py:373 | A rough size of the map, read for cost per row rather than for meaning. |
| Scorecard | eval/tools/coyodex_eval/process_scorecard.py:133 | Every score for one build conversation, about the process and not the product. |
| Assertion | eval/tools/coyodex_eval/process_scorecard.py:106 | One scored line of a build conversation, a good count over an opportunity count. |
| Planted | eval/tools/coyodex_eval/mutate.py:59 | One deliberate mistake planted to test whether the skeptics catch it. |
| Thresholds | eval/tools/coyodex_eval/compare.py:91 | The settings deciding how much a map may move before it counts as worse. |
| GranularityResult | eval/tools/coyodex_eval/compare.py:161 | One check inside the comparison verdict, already carried by that verdict. |
| GroundingVerdict | eval/tools/coyodex_eval/judge.py:56 | One skeptic's vote on one claim, folded into the judged report. |
| DimensionScore | eval/tools/coyodex_eval/judge.py:74 | One rubric score inside the judged report, carried by that report. |
| RunResult | eval/tools/coyodex_eval/run.py:45 | A wrapper holding one scoring run's three results together. |

---

## T6 — Use-case flows

**UC1 — Install the coyodex skill into the coding agents**
1. Map reader → C4 : runs the install command in a fresh clone
2. C4 → D2 : checks the machine has Python 3.10 or newer @ [Makefile](Makefile:31) · stops with a plain message when Python is missing or older
3. C4 → D2 : creates a private Python environment inside the clone, so nothing lands in the machine's own Python @ [Makefile](Makefile:33)
4. C4 → D7 : installs coyodex into that private environment as an editable copy @ [Makefile](Makefile:40) · editable, so later edits need no reinstall
5. C4 → C77 : reads the shipped skill file and replaces its placeholder with this clone's absolute path @ [Makefile](Makefile:58)
6. C4 → D12 : writes the finished skill into the Claude Code skills folder @ [Makefile](Makefile:58)
7. C4 → D13 : writes the same skill into the shared cross-agent skills folder Codex reads @ [Makefile](Makefile:58)
8. C4 → Map reader : prints one line per skills folder, naming the clone the installed skill now points at @ [Makefile](Makefile:59)

**UC2 — Start the local map server**
1. Map reader → C4 : runs the start command, which serves the maps on the chosen port and opens the page @ [Makefile](Makefile:119)
2. C4 → C43 : ⟨runs SF1 — Run a coyodex subcommand⟩
3. C43 → C43 : reads the port and the open-a-browser choice off the command line @ [serve.py](tools/coyodex/viewer/serve.py:838)
4. C43 → C43 : reads the remembered project folders from the small file in the reader's home folder @ [recents.py](tools/coyodex/viewer/recents.py:34) · no disk scan — the served set is exactly this list
5. C43 → E1 : loads each remembered project's map for its title, its goal and the commit it is pinned to @ [serve.py](tools/coyodex/viewer/serve.py:123)
6. C43 → C43 : binds the server to the loopback address on that port, so only this machine can reach it @ [serve.py](tools/coyodex/viewer/serve.py:800)
7. C43 → D11 : opens the landing page in the reader's default browser @ [serve.py](tools/coyodex/viewer/serve.py:806) · only when the start command asked for it
8. C43 → D11 : sends the landing page, one self-contained document that pulls in no outside file @ [serve.py](tools/coyodex/viewer/serve.py:583)
9. C43 → Map reader : answers the page's request with one card per remembered project: its title, its pin, and whether its code can be read @ [serve.py](tools/coyodex/viewer/serve.py:620)
10. C43 → C43 : writes the folder the reader adds back to that file, merging with what is on disk so a parallel writer is never lost @ [recents.py](tools/coyodex/viewer/recents.py:44)
11. C43 → C43 : keeps answering requests until Ctrl-C, then says it stopped and closes the socket @ [serve.py](tools/coyodex/viewer/serve.py:808)

**UC21 — Open a project's map in a browser**
1. Map reader → C43 : clicks a project card, which opens that project's own map address @ [serve.py](tools/coyodex/viewer/serve.py:978)
2. C43 → D11 : sends the viewer shell, the same document for every project @ [serve.py](tools/coyodex/viewer/serve.py:671)
3. C55 → C43 : fetches this map's whole view bundle before anything else on the page runs @ [viewer.js](tools/coyodex/viewer/viewer.js:154)
4. C43 → C1 : ⟨runs SF2 — Load the map into memory⟩
5. C45 → E51 : turns every map element into a graph box carrying its name, its kind, its source line and its parent @ [views.py](tools/coyodex/views.py:730)
6. C45 → E52 : turns every recorded relation into a graph arrow carrying its verb and its call site @ [views.py](tools/coyodex/views.py:1183)
7. C44 → C44 : renders that graph into one bundle holding every diagram, flow and colour @ [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:3264)
8. C43 → C55 : answers the fetch with the finished bundle, and keeps it for the next reader of the same map @ [serve.py](tools/coyodex/viewer/serve.py:682)
9. C55 → C55 : copies the bundle into the page's own data, which every view below reads @ [viewer.js](tools/coyodex/viewer/viewer.js:156)
10. C55 → C57 : opens the first view and records it as the first place in the trail @ [viewer.js](tools/coyodex/viewer/viewer.js:11694)
11. C55 → D8 : draws that view's diagram @ [viewer.js](tools/coyodex/viewer/viewer.js:8953)
12. C55 → D9 : wraps the drawing so the reader can pan it and zoom it @ [viewer.js](tools/coyodex/viewer/viewer.js:9025)
13. C55 → Map reader : puts the drawn view on screen, ready to click into @ [viewer.js](tools/coyodex/viewer/viewer.js:8961)

**UC25 — Report what a code change did to the map**
1. Coding agent → C75 : opens the dispatch rules to decide which mode this invocation is
2. C75 → C4 : runs the up-front briefing, before any mode is chosen @ [dispatch.md](method/dispatch.md:19)
3. C4 → C25 : asks for the code paths that are changed but not committed @ [scope.py](tools/coyodex/scope.py:68)
4. C25 → D1 : runs the version-control status command and returns the uncommitted paths @ [provenance.py](tools/coyodex/provenance.py:159) · coyodex's own folders are excluded, so its churn never makes the tree read as dirty
5. C4 → Coding agent : prints the briefing: the file counts, the ignore patterns and what the pin will mean @ [scope.py](tools/coyodex/scope.py:172)
6. C75 → E1 : reads the baseline map's pin, the commit the comparison starts from @ [dispatch.md](method/dispatch.md:132)
7. C75 → D1 : compares the pin against the working tree and finds the code has moved on @ [dispatch.md](method/dispatch.md:139) · uncommitted edits count as moved on, and a dirty tree is the normal case here
8. C75 → D1 : diffs the pin against the working tree, then adds the untracked files as added @ [change-impact.md](method/change-impact.md:57) · a plain diff omits untracked files, so they are listed separately
9. C75 → C3 : asks the read-only reader which map element claims each changed file @ [change-impact.md](method/change-impact.md:67) · every change is placed at component level at least, and sharpened only where reading allows
10. C3 → C1 : ⟨runs SF2 — Load the map into memory⟩
11. C3 → E1 : reads the element records and the edges into and out of each claiming element @ [dump.py](tools/coyodex/dump.py:139)
12. C75 → C3 : follows those edges outward to the downstream elements and happy-path steps the change reaches @ [change-impact.md](method/change-impact.md:64) · the walk is redone from the diff every run; nothing precomputed is consulted
13. C75 → Coding agent : hands back each touched element's exact was-to-now text, classified added, modified or deleted @ [change-impact.md](method/change-impact.md:83) · the report is written to disk and left uncommitted; the baseline itself changes only at accept

**UC22 — Follow the product's story end to end**
1. Map reader → C55 : opens this project's map page in the browser
2. C55 → C43 : ⟨runs SF11 — Build one view and send it to the browser⟩
3. C17 → E6 : joins every use case onto the feature it belongs to @ [features.py](tools/coyodex/features.py:295)
4. C17 → E9 : walks the happy path to fix where each feature sits in the story @ [features.py](tools/coyodex/features.py:230)
5. C17 → E5 : orders every feature into the one story column @ [features.py](tools/coyodex/features.py:222)
6. Map reader → C57 : clicks the Features tab @ [viewer.js](tools/coyodex/viewer/viewer.js:4342)
7. C57 → C55 : re-renders the page for the state the trail now points at @ [viewer.js](tools/coyodex/viewer/viewer.js:4331)
8. C55 → C56 : draws the Features page @ [viewer.js](tools/coyodex/viewer/viewer.js:8897)
9. C56 → Map reader : shows one column holding every feature in story order, with the actors beside it @ [viewer.js](tools/coyodex/viewer/viewer.js:7766)
10. Map reader → C56 : clicks the use-case pill on one feature's card
11. C56 → C57 : pushes that feature's own page onto the trail @ [viewer.js](tools/coyodex/viewer/viewer.js:7660)
12. C55 → C56 : lists that feature's use cases @ [viewer.js](tools/coyodex/viewer/viewer.js:8907)

**UC23 — Read the code under a box**
1. Map reader → C56 : clicks the code link a box shows
2. C45 → E13 : reads the component's source anchor, the line that code link names @ [views.py](tools/coyodex/views.py:1122) · derived once, when the view bundle is built
3. C56 → C58 : hands that file and line to the source column @ [viewer.js](tools/coyodex/viewer/viewer.js:202)
4. C58 → C43 : ⟨runs SF10 — Read a file out of git at the map's commit⟩
5. C58 → D10 : colours the file's text with highlight.js @ [viewer.js](tools/coyodex/viewer/viewer.js:10186)
6. C58 → Map reader : shows the file scrolled to the line the box named @ [viewer.js](tools/coyodex/viewer/viewer.js:10204)
7. Map reader → C58 : opens the file browser to pick another file
8. C58 → C43 : asks for the repository's file tree at the map's commit @ [viewer.js](tools/coyodex/viewer/viewer.js:9712)
9. C43 → C46 : nests the commit's files into folders and marks the ones the map covers @ [serve.py](tools/coyodex/viewer/serve.py:436)

**UC24 — Open an element's source in the editor**
1. Map reader → C58 : clicks the open-outside arrow beside the file the source column shows
2. C45 → E13 : reads the component's own files, the paths a source link points at @ [views.py](tools/coyodex/views.py:1124) · derived once, when the view bundle is built
3. C44 → D1 : derives the project's GitHub address from the repository's origin remote @ [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:121)
4. C58 → Map reader : asks the reader to pick an editor and confirm the repository root @ [viewer.js](tools/coyodex/viewer/viewer.js:10722) · only the first time, before any source is opened outside
5. C58 → D16 : opens the file at that line in the chosen editor through its URL scheme @ [viewer.js](tools/coyodex/viewer/viewer.js:10729)
6. C58 → D15 : opens the file on GitHub at the map's commit @ [viewer.js](tools/coyodex/viewer/viewer.js:10732) · the fallback when no editor is chosen or its scheme is not allowed

**UC3 — Brief the reader on what will be analysed**
1. Coding agent → C4 : runs the scope briefing on the repo before any other work
2. C4 → C33 : ⟨runs SF20 — Walk the repo for the files that may be analysed⟩
3. C4 → C4 : names each ignore pattern with the number of files it removed @ [scope.py](tools/coyodex/scope.py:131) · only when the ignore file holds at least one usable pattern
4. C4 → C4 : warns when a folder inside the analysed set holds a previous map @ [scope.py](tools/coyodex/scope.py:115) · keyed on a folder that contains project-map.json or project-map.md, not on its name
5. C4 → C25 : asks for the code paths that are changed but not committed @ [scope.py](tools/coyodex/scope.py:68)
6. C25 → C4 : returns those paths, with coyodex's own output folders left out @ [provenance.py](tools/coyodex/provenance.py:160)
7. C4 → D1 : reads HEAD's short sha and its date, for the commit the map will name @ [scope.py](tools/coyodex/scope.py:62)
8. C4 → Coding agent : prints the file count, what each exclusion removed, and what the pin will mean @ [scope.py](tools/coyodex/scope.py:172) · the agent must show this text to the reader unchanged

**UC4 — Declare code the map should not describe**
1. Map reader → C4 : lists a fixture or vendored tree in the ignore file, one pattern per line
2. C4 → C4 : reads a leading exclamation mark as a negation, and skips blank and comment lines @ [ignorefile.py](tools/coyodex/ignorefile.py:159)
3. C4 → C4 : drops a line that carries a trailing comment and reports it as unusable @ [ignorefile.py](tools/coyodex/ignorefile.py:169) · a hash opens a comment only at the start of a line, so `pattern  # why` is one literal pattern
4. C4 → C4 : matches a wildcard-free pattern against that folder and everything beneath it @ [pathmatch.py](tools/coyodex/pathmatch.py:52)
5. C4 → C4 : keeps the last rule that matched, so a later negation puts a file back @ [ignorefile.py](tools/coyodex/ignorefile.py:88)
6. C33 → C33 : ⟨runs SF20 — Walk the repo for the files that may be analysed⟩
7. C33 → E38 : works out each folder's expected component count over the narrowed tree @ [preindex_lib.py](tools/coyodex/preindex_lib.py:625)
8. C33 → Map reader : says on every pre-index run how many files the patterns removed, and which pattern removed nothing @ [preindex.py](tools/coyodex/preindex.py:610)
9. C13 → Map reader : discloses the same per-pattern narrowing on every validate run @ [validate_analysis.py](tools/coyodex/validate_analysis.py:328) · unconditional, so the cheap check a lead runs most still carries the disclosure

**UC5 — Size the code tree before choosing altitude**
1. Coding agent → C33 : runs the pre-index to weigh every folder before choosing the map's altitude
2. C33 → C33 : ⟨runs SF20 — Walk the repo for the files that may be analysed⟩
3. C33 → D1 : launches one git log pass and counts the commits that touched each file @ [preindex_lib.py](tools/coyodex/preindex_lib.py:289)
4. C33 → C33 : adds each file's lines, its count and its churn into every folder above it @ [preindex.py](tools/coyodex/preindex.py:96) · the folders are then ordered heaviest first
5. C33 → D4 : builds the parser for the file's language from the language pack @ [preindex_lib.py](tools/coyodex/preindex_lib.py:391) · Python is read with the standard library instead, so it needs no pack
6. C33 → D3 : parses the file and collects every class and function definition with its line span @ [preindex_lib.py](tools/coyodex/preindex_lib.py:440)
7. C33 → E37 : records each Symbol under its name, with its file, its kind and its line @ [preindex.py](tools/coyodex/preindex.py:148)
8. C33 → E38 : works out how many components each folder should yield from its file count and size @ [preindex_lib.py](tools/coyodex/preindex_lib.py:625)
9. C33 → C33 : turns the whole-tree expectation into a band, and says which cap decided it @ [preindex.py](tools/coyodex/preindex.py:240)
10. C33 → C33 : writes the pre-index file with the weight tree, the symbols, the expectation and the coverage block @ [preindex.py](tools/coyodex/preindex.py:604)
11. C33 → Coding agent : prints the counts, whether git and the parser pack were available, and the expected size @ [preindex.py](tools/coyodex/preindex.py:608)
12. Coding agent → C33 : asks for the readable report of the pre-index it just wrote
13. C33 → Coding agent : prints the weight tree, the per-folder expectation and what the pre-index could not see @ [preindex.py](tools/coyodex/preindex.py:441)

**UC6 — Hand a fan-out worker its contract**
1. Coding agent → C4 : asks for the briefing one fan-out worker should receive, by name
2. C4 → C4 : resolves where the method and its briefings live, preferring the environment setting @ [contract.py](tools/coyodex/contract.py:51)
3. C4 → C76 : reads the briefing file that name stands for @ [contract.py](tools/coyodex/contract.py:90)
4. C4 → C4 : takes the quoted block as the worker's half, stripping the quote marker @ [contract.py](tools/coyodex/contract.py:65)
5. C4 → C4 : otherwise takes everything after the single divider line @ [contract.py](tools/coyodex/contract.py:68)
6. C4 → C4 : refuses a briefing with no boundary, rather than handing the lead's half to a worker @ [contract.py](tools/coyodex/contract.py:70)
7. C4 → C76 : appends the writing rules for the briefings whose workers author map prose @ [contract.py](tools/coyodex/contract.py:93)
8. C4 → Coding agent : prints only the worker's half, ready for the angle-bracket slots to be filled @ [contract.py](tools/coyodex/contract.py:118)

**UC7 — Self-check one harvested fragment**
1. Coding agent → C4 : runs the fragment self-check on the rows it has just written
2. C4 → C2 : ⟨runs SF1 — Run a coyodex subcommand⟩
3. C2 → C1 : builds a typed map document out of the fragment's JSON text @ [assemble.py](tools/coyodex/assemble.py:155)
4. C2 → E1 : reads every row of the parsed map document @ [lint_fragment.py](tools/coyodex/lint_fragment.py:452)
5. C2 → C13 : runs the shared row checks over code-link format, arrows, flow steps and business rules @ [lint_fragment.py](tools/coyodex/lint_fragment.py:125)
6. C2 → C13 : checks that every code link names a file that exists in the project @ [lint_fragment.py](tools/coyodex/lint_fragment.py:188)
7. C2 → C25 : asks which files are changed and not committed @ [lint_fragment.py](tools/coyodex/lint_fragment.py:209) · only when the fragment carries a commit pin with no dirty marker
8. C2 → C13 : counts the code links pointing at a line that cannot be acting @ [lint_fragment.py](tools/coyodex/lint_fragment.py:478)
9. C2 → Coding agent : reports the verdict line first, with the problem, warning and drift counts @ [lint_fragment.py](tools/coyodex/lint_fragment.py:500)
10. C2 → Coding agent : prints each problem and each advisory row under the verdict @ [lint_fragment.py](tools/coyodex/lint_fragment.py:505)

**UC8 — Merge the workers' fragments into one map**
1. Coding agent → C4 : runs the merge, naming every fragment and the assignment file
2. C4 → C2 : ⟨runs SF1 — Run a coyodex subcommand⟩
3. C2 → C1 : ⟨runs SF30 — Merge the fragments into one map⟩
4. C2 → C13 : asks which entity steps carry no backing arrow @ [assemble.py](tools/coyodex/assemble.py:119)
5. C2 → E15 : adds the backbone arrow each of those steps implies, reading the verb off the step's own words @ [assemble.py](tools/coyodex/assemble.py:131)
6. C2 → C1 : ⟨runs SF31 — Write the map and its readable view⟩
7. C2 → Coding agent : says it added the scratch folder to the ignore file, so the build never dirties the project @ [assemble.py](tools/coyodex/assemble.py:970)
8. C2 → Coding agent : warns about a fragment left in the scratch folder that this run did not merge @ [assemble.py](tools/coyodex/assemble.py:972)
9. C2 → Coding agent : prints the one-line digest of everything the merge changed @ [assemble.py](tools/coyodex/assemble.py:977)

**UC9 — Turn path rules into explicit assignments**
1. Coding agent → C4 : runs the assignment pass with a rules file and the folder of fragments
2. C4 → C25 : ⟨runs SF1 — Run a coyodex subcommand⟩
3. C25 → Coding agent : refuses a rules file holding a rule that assigns nothing @ [reconcile_build.py](tools/coyodex/reconcile_build.py:128)
4. C25 → C2 : ⟨runs SF30 — Merge the fragments into one map⟩
5. C25 → C1 : strips the line number off an element's code link, leaving the folder path a rule can match @ [reconcile_build.py](tools/coyodex/reconcile_build.py:105)
6. C25 → C4 : matches one element's folder path against the rule's pattern @ [reconcile_build.py](tools/coyodex/reconcile_build.py:150)
7. C25 → E16 : reads each front door's identifier together with its code link @ [reconcile_build.py](tools/coyodex/reconcile_build.py:213) · the code link is stored beside the identifier so a later renumber is caught
8. C25 → Coding agent : names every rule that matched nothing and every rule pointing at a group nobody declared @ [reconcile_build.py](tools/coyodex/reconcile_build.py:373)
9. C25 → Coding agent : prints how many rules were clean, matched nothing, or point at an undeclared group @ [reconcile_build.py](tools/coyodex/reconcile_build.py:377)
10. C25 → E40 : writes the assignment file, carrying forward the directives it does not author @ [reconcile_build.py](tools/coyodex/reconcile_build.py:439)

**UC10 — Look up one part of the map**
1. Coding agent → C4 : runs the lookup, naming one file, one selector and one identifier
2. C4 → C3 : ⟨runs SF1 — Run a coyodex subcommand⟩
3. C3 → C2 : loads the named file, accepting a finished map or a half-written build fragment @ [dump.py](tools/coyodex/dump.py:292)
4. C3 → C1 : asks the map document which element carries that identifier @ [dump.py](tools/coyodex/dump.py:103)
5. C3 → E1 : reads that element's full stored record out of the map document @ [dump.py](tools/coyodex/dump.py:132)
6. C3 → E16 : reads a front door's record, whose identifier is minted only when the map is merged @ [dump.py](tools/coyodex/dump.py:99)
7. C3 → C1 : asks the serializer for the whole document when no selector is given @ [dump.py](tools/coyodex/dump.py:297)
8. C3 → Coding agent : refuses, saying the identifier is not defined in the map @ [dump.py](tools/coyodex/dump.py:318)
9. C3 → Coding agent : prints the answer as JSON @ [dump.py](tools/coyodex/dump.py:320)

**UC11 — Check the map is well formed**
1. Coding agent → C4 : asks for the check over the map it just wrote, with the repo-reading flags on
2. C4 → C13 : ⟨runs SF1 — Run a coyodex subcommand⟩
3. C13 → C1 : ⟨runs SF2 — Load the map into memory⟩
4. C13 → E1 : reads every element the map document declares, as the set a reference may name @ [validate_model.py](tools/coyodex/validate_model.py:4359)
5. C13 → C13 : reports every reference that names an element the map never defines @ [validate_model.py](tools/coyodex/validate_model.py:4362)
6. C13 → C3 : ⟨runs SF40 — Read the recorded exceptions⟩
7. C13 → C13 : counts the long sentences and the missing link words in the map's plain text @ [validate_model.py](tools/coyodex/validate_model.py:4431)
8. C13 → C13 : fails the check when a code link names a file, or a line, the repo does not have @ [validate_model.py](tools/coyodex/validate_model.py:4444) · only under the check-sources flag
9. C13 → C13 : warns when a code link resolves to a line that cannot be the acting statement @ [validate_model.py](tools/coyodex/validate_model.py:4448) · advisory, because the relation is usually real and only its line drifted
10. C13 → C13 : walks the repo tree and names the folders no box on the map covers @ [validate_model.py](tools/coyodex/validate_model.py:4472) · only under the check-coverage flag
11. C13 → C15 : asks which screens hold more boxes than a reader can hold at once @ [validate_model.py](tools/coyodex/validate_model.py:4501)
12. C13 → Coding agent : prints the advisories, then the blocking problems, and exits non-zero when one stands @ [validate_model.py](tools/coyodex/validate_model.py:4818)

**UC12 — Make the map's two layers refute each other**
1. Coding agent → C4 : asks for the two-layer comparison and for the ranked claims to be cut into batches
2. C4 → C14 : ⟨runs SF1 — Run a coyodex subcommand⟩
3. C14 → C1 : ⟨runs SF2 — Load the map into memory⟩
4. C14 → C14 : builds the walk's ordered steps and each step's entity reads and writes @ [audit_model.py](tools/coyodex/audit_model.py:548)
5. C14 → E42 : records a finding when a walk step reads something the walk only writes later @ [audit_model.py](tools/coyodex/audit_model.py:575)
6. C14 → C14 : blocks the run when a walk step explains itself by a step that comes after it @ [audit_model.py](tools/coyodex/audit_model.py:615)
7. C14 → C14 : reports a flow whose opening actor is not one the use case declares @ [audit_model.py](tools/coyodex/audit_model.py:692)
8. C14 → C3 : ⟨runs SF40 — Read the recorded exceptions⟩
9. C14 → C14 : drops the advisories an operator recorded and names every one it dropped @ [audit_model.py](tools/coyodex/audit_model.py:836) · a contradiction is never dropped
10. C14 → E41 : ranks each access decision and the line enforcing it at the top of the worklist @ [audit_model.py](tools/coyodex/audit_model.py:969)
11. C14 → C14 : cuts the ranked claims into even batches, one file per theme, riskiest first @ [audit_model.py](tools/coyodex/audit_model.py:1395)
12. C14 → Coding agent : prints the findings and the ranked claims, exiting non-zero only on a contradiction @ [audit_model.py](tools/coyodex/audit_model.py:1432)

**UC17 — Record an advisory the reader accepts**
1. Coding agent → C4 : asks to write down the reason one advisory was accepted, naming the heading and the line
2. C4 → C3 : ⟨runs SF1 — Run a coyodex subcommand⟩
3. C3 → C3 : refuses a line that names a key and states no reason @ [record.py](tools/coyodex/record.py:262)
4. C3 → C3 : refuses a heading no check reads, and names the headings that are read @ [record.py](tools/coyodex/record.py:267)
5. C3 → C2 : loads the fragment, remembering which sections it already held @ [record.py](tools/coyodex/record.py:277)
6. C3 → E36 : appends the recorded line under the named heading, adding the section when it is missing @ [record.py](tools/coyodex/record.py:116)
7. C3 → E36 : deletes one recorded line, and drops the whole heading when that was its last line @ [record.py](tools/coyodex/record.py:144) · the remove mode
8. C3 → C3 : re-reads the lines it just added and refuses the whole batch when one adjudicates nothing @ [record.py](tools/coyodex/record.py:308)
9. C3 → C2 : serializes the fragment once, with every line of the batch in it @ [record.py](tools/coyodex/record.py:318)
10. C3 → Coding agent : says what was recorded, or that the fragment was left untouched @ [record.py](tools/coyodex/record.py:312)

**UC18 — Re-balance the diagrams against the traced graph**
1. Coding agent → C4 : asks how crowded each screen of the map is
2. C4 → C15 : ⟨runs SF1 — Run a coyodex subcommand⟩
3. C15 → C1 : ⟨runs SF2 — Load the map into memory⟩
4. C15 → E5 : reads every group and its parent, to build the child list of each screen @ [balance_lib.py](tools/coyodex/balance_lib.py:107)
5. C15 → E13 : puts every component on the screen of the group it belongs to @ [balance_lib.py](tools/coyodex/balance_lib.py:110)
6. C15 → C15 : counts the boxes on each screen and flags the crowded, the thin and the one-child ones @ [balance.py](tools/coyodex/balance.py:51)
7. C15 → C15 : says how many screens sit inside the readable band @ [balance.py](tools/coyodex/balance.py:122)
8. C15 → C15 : counts the arrows between components that cross from one group to another @ [balance.py](tools/coyodex/balance.py:176)
9. C15 → C15 : proposes where a split of a crowded screen would fall, with the exact map change @ [balance.py](tools/coyodex/balance.py:87)
10. C15 → Coding agent : prints the counts, the busiest seams and the proposals, and always exits clean @ [balance.py](tools/coyodex/balance.py:283) · grouping is a view choice, so the report never fails a build

**UC13 — Disprove a claim against the code**
1. Coding agent → C4 : runs the audit and asks it to cut one claims file per theme
2. C4 → C14 : hands the auditor the batch directory and the per-batch cap @ [cli.py](tools/coyodex/cli.py:132)
3. C14 → E41 : ranks every risky claim in the map into a work item carrying its anchor @ [audit_model.py](tools/coyodex/audit_model.py:1366)
4. C14 → Coding agent : refuses to cut any batch while the audit still holds a blocking contradiction @ [audit_model.py](tools/coyodex/audit_model.py:1391)
5. C14 → E41 : writes each theme's claims, anchors and details into their own batch file @ [audit_model.py](tools/coyodex/audit_model.py:1269) · most dangerous theme first, split at the cap
6. C75 → Coding agent : tells the lead to give each batch a fresh worker and to copy the briefing with a command @ [method.md](method.md:1600)
7. Coding agent → C76 : fills the briefing's four slots with the map, the repo, the batch id and its claims file @ [skeptic-contract.md](method/templates/skeptic-contract.md:7)
8. Coding agent → C1 : opens each claim's own anchor and reads the file the map points at @ [skeptic-contract.md](method/templates/skeptic-contract.md:58)
9. Coding agent → C23 : writes one answer per claim — confirmed, refuted or impossible to settle — with the true line @ [skeptic-contract.md](method/templates/skeptic-contract.md:97)
10. Coding agent → C4 : runs the answer-file check at the barrier, naming every batch it sent out @ [method.md](method.md:1723)
11. C4 → C23 : hands the check every answer file and the expected batch names @ [cli.py](tools/coyodex/cli.py:171)
12. C23 → Coding agent : stops the barrier when an expected batch left no answer file behind @ [grounding.py](tools/coyodex/grounding.py:937)
13. C23 → Coding agent : reports the files well formed and how many notes the evidence check could test @ [grounding.py](tools/coyodex/grounding.py:962)

**UC14 — Record what the skeptics proved**
1. Coding agent → C4 : runs the grounding write with the pinned claim list, every answer file and the built map
2. C4 → C23 : hands over the pinned claim list, the answer files and the map @ [cli.py](tools/coyodex/cli.py:171)
3. C23 → C14 : re-derives the built map's live claim surface from the auditor's ranking @ [grounding.py](tools/coyodex/grounding.py:1062)
4. C23 → Coding agent : refuses the record when an answer names a claim the pinned list never held @ [grounding.py](tools/coyodex/grounding.py:164)
5. C23 → Coding agent : refuses a pinned claim nobody voted on @ [grounding.py](tools/coyodex/grounding.py:182) · unless the run declares itself a partial pass with a note saying what was prioritized
6. C23 → E35 : writes the four counts, the live claim digest and the note into the record @ [grounding.py](tools/coyodex/grounding.py:1086)
7. C23 → Coding agent : prints the counts the build's note must quote instead of retyping one @ [grounding.py](tools/coyodex/grounding.py:1109)
8. C23 → Coding agent : warns when the shipped map carries claims minted after the list was pinned @ [grounding.py](tools/coyodex/grounding.py:1121)
9. C23 → E43 : recomputes, per element, what the pass did to the claims that element makes @ [grounding.py](tools/coyodex/grounding.py:1068)
10. Coding agent → C13 : re-runs the validator over the map that now carries the record
11. C13 → E35 : blocks the map when confirmed, refuted and unsettled do not add up to challenged @ [validate_model.py](tools/coyodex/validate_model.py:2549)

**UC15 — Correct a code link that points at the wrong line**
1. Coding agent → C4 : runs the drift check over the map with every answer file
2. C4 → C23 : hands the drift check the map and the answer files @ [cli.py](tools/coyodex/cli.py:165)
3. C23 → C14 : re-derives the ranked claim list so every claim keeps the line the map stores @ [anchor_drift.py](tools/coyodex/anchor_drift.py:419)
4. C23 → Coding agent : reports each confirmed claim whose stored line differs from the line the skeptics found @ [anchor_drift.py](tools/coyodex/anchor_drift.py:434)
5. Coding agent → C4 : runs the repair, asking for the correction to be recorded rather than written into the map
6. C4 → C24 : hands the repair the map, the answer files and the reconcile file @ [cli.py](tools/coyodex/cli.py:174)
7. C24 → C23 : asks for one truer line per drifted claim, at the line the skeptics settled on @ [fix.py](tools/coyodex/fix.py:192)
8. C24 → E40 : records each claim and its corrected line in the reconcile file @ [fix.py](tools/coyodex/fix.py:331) · editing the built map instead would be undone by the next merge
9. C2 → C25 : ⟨runs SF50 — Apply the recorded reconcile at the next merge⟩
10. C25 → C14 : hands the corrected lines to the one writer both repair paths share @ [reconcile.py](tools/coyodex/reconcile.py:526)
11. C14 → E15 : writes the corrected line onto the relation whose claim names it @ [audit_model.py](tools/coyodex/audit_model.py:382)

**UC16 — Drop a claim the code refutes**
1. Coding agent → C4 : runs the repair, asking to drop the refuted relation and record the drop for the next merge
2. C4 → C24 : hands the repair the map, the three parts of the relation and the reconcile file @ [cli.py](tools/coyodex/cli.py:174)
3. C24 → C1 : refuses the drop when no relation in the map matches those three parts @ [fix.py](tools/coyodex/fix.py:352)
4. C24 → E40 : records the drop, and how the riding walk steps should be healed, in the reconcile file @ [fix.py](tools/coyodex/fix.py:384)
5. C24 → Coding agent : warns when walk steps ride the relation and the record says nothing about healing them @ [fix.py](tools/coyodex/fix.py:389)
6. C2 → C25 : ⟨runs SF50 — Apply the recorded reconcile at the next merge⟩
7. C25 → E15 : removes every relation matching the three parts @ [reconcile.py](tools/coyodex/reconcile.py:576)
8. C25 → E11 : re-points or removes the walk steps that rode the dropped relation @ [reconcile.py](tools/coyodex/reconcile.py:584)
9. C25 → Coding agent : names each walk step left with no backing relation when the record healed nothing @ [reconcile.py](tools/coyodex/reconcile.py:588)

**UC19 — Run the pre-commit read**
1. Coding agent → C4 : runs the pre-commit read over the map with every answer file
2. C4 → C16 : hands the gate run the map, the repo root and the answer files @ [cli.py](tools/coyodex/cli.py:168)
3. C16 → C1 : refuses to start when the map cannot be loaded at all @ [finalize.py](tools/coyodex/finalize.py:863)
4. C16 → C13 : runs the validator inside this same process, capturing both its streams @ [finalize.py](tools/coyodex/finalize.py:108)
5. C16 → C14 : runs the auditor the same way and splits its findings into blocking and advisory @ [finalize.py](tools/coyodex/finalize.py:111)
6. C16 → C23 : runs the drift check and the surviving-refutation check against the answer files @ [finalize.py](tools/coyodex/finalize.py:114)
7. C16 → E45 : records one leg per gate, saying whether it ran and what it found @ [finalize.py](tools/coyodex/finalize.py:472)
8. C16 → Coding agent : reports a leg it could have run but was not asked to, rather than staying silent @ [finalize.py](tools/coyodex/finalize.py:393)
9. C16 → E46 : settles one verdict from the legs and hashes the map into the report @ [finalize.py](tools/coyodex/finalize.py:495) · a leg that failed forbids a clean verdict
10. C16 → Coding agent : writes the whole finding list to a file beside the map, where a pipe cannot eat it @ [finalize.py](tools/coyodex/finalize.py:877)
11. C16 → Coding agent : names the files that must be committed with the map, and the ones still missing @ [finalize.py](tools/coyodex/finalize.py:894)
12. C16 → Coding agent : prints the verdict, the two counts, and which gates did not run @ [finalize.py](tools/coyodex/finalize.py:920)

**UC20 — Stamp which conversation built the map**
1. Coding agent → C4 : runs the stamp, pointing it at the build's header fragment
2. C4 → C25 : hands the stamp the repo, the mode and the header fragment @ [cli.py](tools/coyodex/cli.py:180)
3. C25 → Coding agent : refuses when no session id is in the environment and none was passed @ [provenance.py](tools/coyodex/provenance.py:197)
4. C25 → D1 : launches git for the short commit, its date and whether the tree holds uncommitted code @ [provenance.py](tools/coyodex/provenance.py:120)
5. C25 → E48 : builds this session's entry — the id, the minute, the mode and the pinned commit @ [provenance.py](tools/coyodex/provenance.py:199)
6. C25 → E47 : writes the record, replacing this session's own entry rather than adding a second @ [provenance.py](tools/coyodex/provenance.py:217)
7. C25 → C1 : writes the same minute and the same pin into the header fragment @ [provenance.py](tools/coyodex/provenance.py:362)
8. C25 → Coding agent : prints the minute on its own line so nothing has to be retyped @ [provenance.py](tools/coyodex/provenance.py:324)
9. C16 → Coding agent : names the stamp command when the pre-commit read finds no record file @ [finalize.py](tools/coyodex/finalize.py:918)

**UC38 — See the change overlaid on the map**
1. Map reader → C43 : asks what a code change did to the map, naming where the change starts and where it ends @ [serve.py](tools/coyodex/viewer/serve.py:721) · the request reaches the map server over the loopback address; the working tree is the default end point
2. C43 → C1 : ⟨runs SF2 — Load the map into memory⟩
3. C43 → C34 : reads the symbol table saved beside the map, so an anchor can resolve to a whole definition @ [serve.py](tools/coyodex/viewer/serve.py:419) · an older map with no symbol table resolves every anchor at file level instead
4. C43 → C34 : hands the map, its pinned commit and the two ends of the change to the impact engine @ [serve.py](tools/coyodex/viewer/serve.py:420)
5. C34 → E49 : builds one anchor reference for every code link the map carries @ [impact_lib.py](tools/coyodex/impact_lib.py:196)
6. C34 → D1 : launches git to list every file the change touched and to diff each one against the pinned commit @ [impact_git.py](tools/coyodex/impact_git.py:50)
7. C34 → E50 : records one hit per anchor, saying whether the change reached its line, its definition or only its file @ [impact_lib.py](tools/coyodex/impact_lib.py:367)
8. C43 → C34 : asks for every hit to be spread along the map's own relations, one hop only @ [serve.py](tools/coyodex/viewer/serve.py:423)
9. C43 → Coding agent : answers with every part of the map the change reaches, what happened to it and how strongly it is reached @ [serve.py](tools/coyodex/viewer/serve.py:726)

**UC26 — Fold a change report into the map**
1. Coding agent → C75 : reads the accept instructions once the reader says the report is right @ [dispatch.md](method/dispatch.md:154)
2. C75 → E1 : rewrites the map's rows from the report's was-to-now text, element by element @ [change-impact.md](method/change-impact.md:123) · accept re-reads no code: the report already carries the exact new text
3. C75 → E1 : re-pins the map to the code commit it now describes @ [change-impact.md](method/change-impact.md:124)
4. C75 → C25 : re-stamps who folded the report in and when, as an accept entry @ [method.md](method.md:2286)
5. C25 → E47 : writes this session's entry into the provenance file @ [provenance.py](tools/coyodex/provenance.py:217)
6. C75 → C13 : ⟨runs SF70 — Put a changed map through the gates⟩
7. C75 → C33 : rebuilds the pre-index at the new pin, so its file and line numbers match the re-pinned map @ [change-impact.md](method/change-impact.md:133)
8. C75 → Coding agent : commits the map, its readable view, the pre-index and the report together @ [change-impact.md](method/change-impact.md:138)

**UC27 — Change the map by asking in plain words**
1. Map reader → C75 : asks in plain words to split, rename, move or drill deeper into a part of the map @ [dispatch.md](method/dispatch.md:68) · a plain-words request is a direct map change, never a re-analysis of the code
2. C75 → E1 : edits the named part of the map field by field, never by rebuilding it @ [dispatch.md](method/dispatch.md:161)
3. C75 → C24 : rewrites a row's own text inside the fragment that authored it, so the edit survives the next merge @ [method.md](method.md:794)
4. C24 → C2 : re-merges the edited fragments in a temporary copy first, refusing an edit that makes a row appear or vanish @ [fix.py](tools/coyodex/fix.py:1399)
5. C24 → Map reader : names the field it rewrote and the fragment it wrote it in @ [fix.py](tools/coyodex/fix.py:1589)
6. C75 → E1 : drills deeper by retiring a leaf part, putting a group in its place and re-pointing every relation that named it @ [method.md](method.md:2305)
7. C75 → C13 : ⟨runs SF70 — Put a changed map through the gates⟩
8. C75 → Map reader : commits the edited map together with its regenerated readable view @ [dispatch.md](method/dispatch.md:168)

**UC28 — See what an edit changed, row by row**
1. Coding agent → C4 : asks what changed between the map before an edit and the map after it @ [cli.py](tools/coyodex/cli.py:147) · the two maps must be two writes of the same work, never two independent builds
2. C4 → C3 : ⟨runs SF1 — Run a coyodex subcommand⟩
3. C3 → E1 : loads each of the two map files as a map document, refusing one that is malformed @ [mapdiff.py](tools/coyodex/mapdiff.py:193)
4. C3 → C1 : asks which arrays carry an authored identifier, so those rows are matched by identifier @ [mapdiff.py](tools/coyodex/mapdiff.py:123) · relations and entry points are matched on their own text instead, because their identifiers are minted afresh on every write
5. C3 → Coding agent : lists the rows dropped and the rows added in each array @ [mapdiff.py](tools/coyodex/mapdiff.py:175)
6. C3 → Coding agent : names each surviving row that changed, with the exact fields that moved @ [mapdiff.py](tools/coyodex/mapdiff.py:179)
7. C3 → Coding agent : flags an identity held by more than one row and reports it by count instead of pairing the rows @ [mapdiff.py](tools/coyodex/mapdiff.py:181)
8. C3 → Coding agent : prints the same answer as data when asked for it @ [mapdiff.py](tools/coyodex/mapdiff.py:256)

**UC29 — Score a rebuilt map against the accepted one**
1. coyodex developer → C63 : runs the scoring command with the new map and the accepted baseline @ [cli.py](eval/tools/coyodex_eval/cli.py:62)
2. C63 → E53 : reads the accepted map's stored quality signals out of the baseline folder @ [run.py](eval/tools/coyodex_eval/run.py:78) · a baseline folder that is missing or holds no signals stops the run instead of reporting nothing got worse
3. C63 → C1 : turns the frozen map file into the typed document @ [profile.py](eval/tools/coyodex_eval/profile.py:250)
4. C63 → C13 : counts the map's well-formedness problems and warnings @ [profile.py](eval/tools/coyodex_eval/profile.py:257)
5. C63 → C14 : counts the map's contradictions, advisories and risky claims @ [profile.py](eval/tools/coyodex_eval/profile.py:259)
6. C63 → E53 : records the counted quality signals of the new map @ [profile.py](eval/tools/coyodex_eval/profile.py:337)
7. C63 → E55 : settles on pass, drift or regressed from every hard check and band @ [compare.py](eval/tools/coyodex_eval/compare.py:510)
8. C63 → coyodex developer : prints the verdict with the checks and the bands that moved @ [run.py](eval/tools/coyodex_eval/run.py:274)

**UC30 — Have judges read both maps**
1. coyodex developer → C63 : asks for the riskiest claims one map makes @ [cli.py](eval/tools/coyodex_eval/cli.py:68) · run once for the new map and once for the accepted one
2. C63 → C14 : ⟨runs SF80 — List the riskiest claims a map makes⟩
3. coyodex developer → C63 : checks whether a stored judgement was made under the current judging protocol @ [cli.py](eval/tools/coyodex_eval/cli.py:74)
4. C63 → E54 : reads the fingerprint recorded with the stored judgement @ [run.py](eval/tools/coyodex_eval/run.py:450) · a different model, skeptic count, sample cap or rubric makes the stored judgement unusable
5. coyodex developer → C63 : hands back one row per skeptic vote plus each judge's rubric scores @ [cli.py](eval/tools/coyodex_eval/cli.py:71)
6. C63 → C1 : re-reads the frozen map so every vote is matched against the same document @ [judge.py](eval/tools/coyodex_eval/judge.py:234)
7. C63 → E54 : records the pass rate, the excluded failures and the median rubric scores @ [judge.py](eval/tools/coyodex_eval/judge.py:257)
8. C63 → coyodex developer : prints how many claims held up and the overall score @ [run.py](eval/tools/coyodex_eval/run.py:408)

**UC31 — Accept a run as the new baseline**
1. coyodex developer → C63 : takes the map's freeze hash before anything scores it @ [cli.py](eval/tools/coyodex_eval/cli.py:65)
2. coyodex developer → C63 : scores the older accepted map so it can serve as the baseline @ [cli.py](eval/tools/coyodex_eval/cli.py:59)
3. C63 → C1 : reads a map an older coyodex wrote, after dropping the block that no longer exists @ [legacy_map.py](eval/tools/coyodex_eval/legacy_map.py:63) · only for reading; every writing path still refuses an out-of-date map
4. coyodex developer → C63 : archives the finished run, handing back the freeze hash @ [cli.py](eval/tools/coyodex_eval/cli.py:62)
5. C63 → coyodex developer : refuses the whole run when the map no longer matches its freeze hash @ [run.py](eval/tools/coyodex_eval/run.py:220) · only when the map was edited after the hash was taken
6. C63 → C45 : renders the map's readable view into the run folder @ [run.py](eval/tools/coyodex_eval/run.py:163)
7. C63 → E53 : writes the run's counted quality signals into the run folder @ [run.py](eval/tools/coyodex_eval/run.py:166)
8. C63 → E54 : writes the judged pass rate and rubric scores beside them @ [run.py](eval/tools/coyodex_eval/run.py:168)
9. coyodex developer → C63 : promotes that run folder to the baseline @ [cli.py](eval/tools/coyodex_eval/cli.py:77)
10. C63 → coyodex developer : reports the baseline now holds the map, its view, its signals and its judgement @ [run.py](eval/tools/coyodex_eval/run.py:472)

**UC32 — Measure how many planted falsehoods the skeptics catch**
1. coyodex developer → C63 : asks for the riskiest claims, to use as the batch to corrupt @ [cli.py](eval/tools/coyodex_eval/cli.py:68)
2. C63 → C14 : ⟨runs SF80 — List the riskiest claims a map makes⟩
3. coyodex developer → C63 : asks for ten planted falsehoods, spread evenly across the four shapes @ [cli.py](eval/tools/coyodex_eval/cli.py:98)
4. C63 → coyodex developer : writes the corrupted batch and, beside it, the answer key naming every planted claim @ [mutate.py](eval/tools/coyodex_eval/mutate.py:258)
5. coyodex developer → C63 : hands back the skeptics' verdicts on the corrupted batch @ [mutate.py](eval/tools/coyodex_eval/mutate.py:273)
6. C63 → coyodex developer : reports how many planted falsehoods were caught, shape by shape @ [mutate.py](eval/tools/coyodex_eval/mutate.py:278) · a moved anchor counts as caught on the evidence line the skeptic found, never on the verdict

**UC33 — Refuse to review a build that has not finished**
1. coyodex developer → C66 : runs the pre-check before reviewing a finished build @ [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:278)
2. C66 → E47 : reads the recorded build stamp and takes its session list @ [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:179)
3. C66 → E48 : takes the newest recorded session as the build being reviewed @ [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:180)
4. C66 → coyodex developer : refuses the review and tells the developer to open a new chat @ [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:192) · when the newest recorded session is this very chat, so the review would read the file it is writing
5. C66 → coyodex developer : refuses the review and names the file that just changed @ [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:202) · when anything under .coyodex/ was written in the last three minutes; the stamp is written near the end of a build and the build keeps going after it
6. C66 → coyodex developer : refuses the review and names the other chat that is still writing @ [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:237) · only a chat whose newest real message is recent counts as live; a file merely touched does not
7. C66 → coyodex developer : clears the review, naming the build's chat and the minute it was built @ [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:243)

**UC34 — Read a build transcript in slices**
1. coyodex developer → C25 : asks which chat built this map
2. C25 → E47 : loads the recorded build stamp @ [provenance.py](tools/coyodex/provenance.py:296)
3. C25 → E48 : walks every recorded session, reading its build minute, its mode and its chat id @ [provenance.py](tools/coyodex/provenance.py:304)
4. C25 → coyodex developer : prints the recorded sessions, newest last, so the build's chat id can be turned into a log path @ [provenance.py](tools/coyodex/provenance.py:305)
5. coyodex developer → C64 : runs the transcript reader on that chat's log with no range asked for @ [transcript.py](eval/tools/coyodex_eval/transcript.py:1085)
6. C64 → coyodex developer : prints one line per tool call with its turn number, counting every record of one reply as one turn @ [transcript.py](eval/tools/coyodex_eval/transcript.py:1174)
7. coyodex developer → C64 : asks for one turn range, because the whole log is far too big to open @ [transcript.py](eval/tools/coyodex_eval/transcript.py:1097)
8. C64 → coyodex developer : lists every coyodex command the build ran inside that range, with the turn that ran it @ [transcript.py](eval/tools/coyodex_eval/transcript.py:1123)
9. C64 → coyodex developer : counts the tools used and the size of each fan-out inside that range @ [transcript.py](eval/tools/coyodex_eval/transcript.py:1140)

**UC35 — Score a build's behaviour against the method**
1. coyodex developer → C77 : opens the retrospective on a build that has already finished
2. C77 → coyodex developer : sends the developer into the retrospective recipe, which names the scorecard command @ [SKILL.md](eval/retro/SKILL.md:28)
3. coyodex developer → C65 : runs the scorecard on the build's chat log, naming the map that build produced
4. C65 → coyodex developer : refuses before scoring anything, saying which rules would have stopped measuring @ [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:3182) · only when a map was named and cannot be read
5. C65 → C64 : asks the reader for the build's turns, every record of one reply folded into one turn @ [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:2941)
6. C65 → E1 : loads the built map, so the rules whose subject is the map can be checked against it @ [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:1615)
7. C65 → coyodex developer : saves the scorecard beside the chat log, so a later build can be compared against this one @ [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:3198)
8. C65 → coyodex developer : prints one line per rule: how many chances the build had, and how many it took @ [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:3202) · a rule the run gave no chance to reads as not applicable, never as zero
9. coyodex developer → C65 : later asks it to compare two saved scorecards @ [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:3151)
10. C65 → coyodex developer : prints each rule before and after, which way it moved, and a warning when a score rose only because the chances vanished @ [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:3160)

**UC36 — Measure what a build spent**
1. coyodex developer → C64 : runs the spend report on the build's chat log, naming the map that build produced @ [cost.py](eval/tools/coyodex_eval/cost.py:715)
2. coyodex developer → C64 : bounds the report to the build's own turns @ [cost.py](eval/tools/coyodex_eval/cost.py:705) · a chat keeps answering questions after the map lands, and those turns are not the build
3. C64 → E1 : counts every row of the produced map, the divisor the whole report is stated against @ [cost.py](eval/tools/coyodex_eval/cost.py:392)
4. C64 → coyodex developer : reports the wall clock of the run and the active time, with the stretches nobody was working cut out @ [cost.py](eval/tools/coyodex_eval/cost.py:575)
5. C64 → coyodex developer : reports the tokens and the money, one row per kind of worker and a total across the lead chat and every worker chat @ [cost.py](eval/tools/coyodex_eval/cost.py:606)
6. C64 → coyodex developer : reports the money and the seconds per row of map, so two builds of different size compare @ [cost.py](eval/tools/coyodex_eval/cost.py:631)
7. C64 → coyodex developer : warns that the numbers cover the lead chat alone @ [cost.py](eval/tools/coyodex_eval/cost.py:726) · when no worker chat logs sit beside the session, which is about four fifths of a fan-out build's spend

**UC37 — Archive a map so the next run builds from scratch**
1. coyodex developer → C66 : runs the archive command on the mapped repo before starting a rebuild @ [archive.py](eval/tools/coyodex_eval/archive.py:185)
2. C66 → E1 : moves the map document, with the rest of the build output, into the next numbered archive folder @ [archive.py](eval/tools/coyodex_eval/archive.py:107) · moved rather than deleted, because the old map is the baseline the new one is compared against
3. C66 → coyodex developer : names the archive folder and lists every entry that moved into it @ [archive.py](eval/tools/coyodex_eval/archive.py:196)
4. C66 → coyodex developer : says the working tree now holds no map, so the next run will build, and tells the developer to keep the archived one @ [archive.py](eval/tools/coyodex_eval/archive.py:202)
5. C75 → E1 : looks for the map document in the working tree, finds none, and sends the next run down the build-from-scratch branch @ [dispatch.md](method/dispatch.md:75) · the working tree alone decides; a copy still in git history is never treated as the baseline

---

## T6b — Sub-flows (shared step sequences, referenced by the flows above)

**SF1 — Run a coyodex subcommand**
1. C4 → C4 : switches the normal output to line buffering, so notes and errors stay in the order they happened @ [cli.py](tools/coyodex/cli.py:114)
2. C4 → C4 : takes the first argument as the command word and keeps the rest for the command @ [cli.py](tools/coyodex/cli.py:123)
3. C4 → C4 : matches the command word against every command it knows @ [cli.py](tools/coyodex/cli.py:139)
4. C4 → C4 : loads the matching command's code only inside that branch, then runs it and returns its exit code @ [cli.py](tools/coyodex/cli.py:141) · the late load is what keeps a stdlib-only command free of the pre-index's parser packages
5. C4 → C4 : prints the command list on the error stream and returns code 2 when the word matches nothing @ [cli.py](tools/coyodex/cli.py:182)

**SF2 — Load the map into memory**
1. C1 → C1 : turns the map file's text into plain values, naming the exact spot a broken file goes wrong @ [model.py](tools/coyodex/model.py:1069)
2. C1 → C1 : refuses a document whose format word is not the coyodex map format @ [model.py](tools/coyodex/model.py:1075)
3. C1 → C1 : rewrites the older shapes it still accepts, before any type is checked @ [model.py](tools/coyodex/model.py:1077)
4. C1 → E1 : builds the typed map document field by field, naming the exact path of a wrong type @ [model.py](tools/coyodex/model.py:1080)
5. C1 → C1 : refuses an element whose identifier does not carry its own list's letter @ [model.py](tools/coyodex/model.py:1084)

**SF10 — Read a file out of git at the map's commit**
1. C58 → C43 : asks for one file's text at the map's commit @ [viewer.js](tools/coyodex/viewer/viewer.js:10343)
2. C43 → D1 : asks git for the blob's type and size at that commit @ [serve.py](tools/coyodex/viewer/serve.py:261) · a directory or an oversized file is refused before the bytes are read
3. C43 → D1 : runs git show to read the file's bytes at that commit @ [serve.py](tools/coyodex/viewer/serve.py:279)
4. C43 → C58 : returns the file's bytes as plain text @ [serve.py](tools/coyodex/viewer/serve.py:720)

**SF11 — Build one view and send it to the browser**
1. C55 → C43 : fetches this map's view bundle @ [viewer.js](tools/coyodex/viewer/viewer.js:154)
2. C43 → C45 : turns the map document into the graph the browser page draws @ [serve.py](tools/coyodex/viewer/serve.py:455)
3. C45 → E1 : reads the map document's use cases, components and edges @ [views.py](tools/coyodex/views.py:1030)
4. C43 → C44 : asks for every derived view artifact for this map @ [serve.py](tools/coyodex/viewer/serve.py:460)
5. C44 → C17 : derives the feature index and the one story order @ [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:3262)
6. C43 → C55 : returns the whole view bundle as JSON @ [serve.py](tools/coyodex/viewer/serve.py:682)

**SF20 — Walk the repo for the files that may be analysed**
1. C33 → D1 : lists the files git tracks, plus the files created but never added @ [preindex_lib.py](tools/coyodex/preindex_lib.py:190) · when the folder is not a git repo the files are read off disk instead, and .gitignore cannot apply
2. C33 → C4 : loads the repo's ignore file, or an empty one when there is none @ [preindex_lib.py](tools/coyodex/preindex_lib.py:227)
3. C33 → C33 : drops the files under the built-in excluded folders, names and suffixes @ [preindex_lib.py](tools/coyodex/preindex_lib.py:236)
4. C33 → C4 : asks which rule decides each remaining path @ [preindex_lib.py](tools/coyodex/preindex_lib.py:242)
5. C4 → C33 : returns the last rule that matched the path, or nothing @ [ignorefile.py](tools/coyodex/ignorefile.py:89)
6. C33 → C33 : counts the hit against that rule, and leaves the file out when the rule is a positive one @ [preindex_lib.py](tools/coyodex/preindex_lib.py:246)
7. C33 → C33 : returns the file set with both skip counts and the per-rule tally @ [preindex_lib.py](tools/coyodex/preindex_lib.py:249)

**SF30 — Merge the fragments into one map**
1. C2 → C1 : builds a typed map document out of one fragment's JSON text @ [assemble.py](tools/coyodex/assemble.py:155)
2. C2 → E39 : records which fragments loaded, which were skipped and which failed @ [assemble.py](tools/coyodex/assemble.py:294)
3. C2 → Coding agent : refuses the merge and names both fragments that defined the same identifier @ [assemble.py](tools/coyodex/assemble.py:394)
4. C2 → C13 : asks whether two business rules state the same decision at the same lines @ [assemble.py](tools/coyodex/assemble.py:475)
5. C2 → C1 : re-points every reference at the identifier that survived a merge @ [assemble.py](tools/coyodex/assemble.py:497)
6. C2 → C3 : folds two authored headings that differ only in case or spacing into one @ [assemble.py](tools/coyodex/assemble.py:440)
7. C2 → E16 : mints one identifier per front door, ordered by the front door's own content @ [assemble.py](tools/coyodex/assemble.py:688)

**SF31 — Write the map and its readable view**
1. C2 → E40 : reads the assignment file the lead recorded beside the map @ [assemble.py](tools/coyodex/assemble.py:916)
2. C2 → C25 : refuses a directive that names an element the merged map does not hold @ [assemble.py](tools/coyodex/assemble.py:921)
3. C2 → C25 : applies the assignments and heals the steps that rode a dropped arrow @ [assemble.py](tools/coyodex/assemble.py:928)
4. C2 → C25 : stamps which build of coyodex produced this map @ [assemble.py](tools/coyodex/assemble.py:1075)
5. C2 → C1 : asks the serializer for the document text and writes it to the map file @ [assemble.py](tools/coyodex/assemble.py:963)
6. C1 → E1 : writes the whole map document in one fixed key order @ [model.py](tools/coyodex/model.py:892)
7. C2 → C45 : renders the readable markdown view beside the map @ [assemble.py](tools/coyodex/assemble.py:964)
8. C2 → C43 : registers the map's folder so the local viewer can offer this project @ [assemble.py](tools/coyodex/assemble.py:968)

**SF40 — Read the recorded exceptions**
1. C3 → E36 : keeps every extra section whose heading is the one being asked about @ [records.py](tools/coyodex/records.py:165)
2. C3 → C3 : splits each matching section into its non-empty lines, stripping the list bullets @ [records.py](tools/coyodex/records.py:170)
3. C3 → C3 : matches the comma list at the start of each line against this heading's key pattern @ [records.py](tools/coyodex/records.py:183)
4. C3 → C3 : reads nothing from a list where one token is not a key @ [records.py](tools/coyodex/records.py:190) · a half-read line would silence part of a finding while the reader believes it is answered
5. C3 → C3 : collects the keys of every line into the set the calling check honours @ [records.py](tools/coyodex/records.py:251)
6. C3 → C3 : lists the lines that open like a record and silence nothing, so a dropped one is visible @ [records.py](tools/coyodex/records.py:233)

**SF50 — Apply the recorded reconcile at the next merge**
1. Coding agent → C2 : re-runs the merge over the fragments with the reconcile file
2. C2 → C25 : loads the recorded directives, refusing one whose shape is wrong @ [assemble.py](tools/coyodex/assemble.py:916)
3. C2 → C25 : checks each directive still names something the merged map holds @ [assemble.py](tools/coyodex/assemble.py:921)
4. C2 → C25 : applies every directive against the whole merged map @ [assemble.py](tools/coyodex/assemble.py:928)

**SF70 — Put a changed map through the gates**
1. C75 → C13 : checks the changed map against the schema, the semantic rules and the freshness of its readable view @ [dispatch.md](method/dispatch.md:181)
2. C75 → C14 : re-runs the adversarial pass, so the story and the traced flows can refute each other @ [dispatch.md](method/dispatch.md:182)
3. C75 → C45 : re-renders the committed readable view from the changed map @ [dispatch.md](method/dispatch.md:187)

**SF80 — List the riskiest claims a map makes**
1. C63 → C1 : turns the map file into the typed document @ [run.py](eval/tools/coyodex_eval/run.py:322)
2. C63 → C14 : asks the auditor to rank every risky claim, most dangerous first @ [run.py](eval/tools/coyodex_eval/run.py:322)
3. C63 → E41 : keeps the top forty work items as the sample @ [run.py](eval/tools/coyodex_eval/run.py:324)
4. C63 → E41 : reads each work item's claim, anchor and context into a plain row @ [run.py](eval/tools/coyodex_eval/run.py:328)

---

## T7 — Business logic (the decisions this product makes)

One decision per rule, with every place it is enforced. The component on each site line and the
use-case steps under it are DERIVED from the site anchors — no field carries them.

### What counts as source *(BLK1)*

Which of a project's files the map is allowed to describe, and which are deliberately outside it.

**BR1 — Version control owns the file set** — Version control decides which files a map may describe. A project with no version control falls back to a walk of the disk.  *(verified)*
- [tools/coyodex/preindex_lib.py:198](tools/coyodex/preindex_lib.py:198) — Pre-index (C33) · asks version control for the files it tracks, instead of walking the disk
- [tools/coyodex/preindex_lib.py:201](tools/coyodex/preindex_lib.py:201) — Pre-index (C33) · adds files a person created but never added, and drops everything version control is told to ignore
- [tools/coyodex/preindex_lib.py:224](tools/coyodex/preindex_lib.py:224) — Pre-index (C33) · falls back to reading the disk when the folder is not under version control

**BR2 — Generated code is not authored code** — Installed packages, build output, lock files and images are never analysed, so the map measures code people wrote.  *(verified)*
- [tools/coyodex/preindex_lib.py:148](tools/coyodex/preindex_lib.py:148) — Pre-index (C33) · drops any file sitting under a folder on the built-in list of generated and vendored trees
- [tools/coyodex/preindex_lib.py:236](tools/coyodex/preindex_lib.py:236) — Pre-index (C33) · applies that built-in list before anything the project itself declares
- [tools/coyodex/preindex_lib.py:257](tools/coyodex/preindex_lib.py:257) — Pre-index (C33) · prunes the same folders in the disk walk, so both ways of listing files give the same shape
- enforced at: Brief the reader on what will be analysed (UC3) → SF20 step 3 · Declare code the map should not describe (UC4) → SF20 step 3 · Size the code tree before choosing altitude (UC5) → SF20 step 3

**BR3 — Committed code can be declared out of the map** — A project can name committed folders and files that the map is not meant to describe.  *(verified)*
- [tools/coyodex/preindex_lib.py:242](tools/coyodex/preindex_lib.py:242) — Pre-index (C33) · tests each surviving file against the project's own exclusion list, kept separate from the built-in list
- [tools/coyodex/preindex_lib.py:245](tools/coyodex/preindex_lib.py:245) — Pre-index (C33) · takes the file out of the analysed tree when the deciding pattern is an exclusion
- [tools/coyodex/pathmatch.py:52](tools/coyodex/pathmatch.py:52) — Command shell and build setup (C4) · a pattern naming a folder and no wildcard also covers everything beneath that folder
- enforced at: Brief the reader on what will be analysed (UC3) → SF20 step 4 · Declare code the map should not describe (UC4) step 4 · Declare code the map should not describe (UC4) → SF20 step 4 · Size the code tree before choosing altitude (UC5) → SF20 step 4

**BR4 — The last pattern written decides** — When several exclusion patterns match one file, the last pattern written decides. So a later line can put one file back.  *(verified)*
- [tools/coyodex/ignorefile.py:88](tools/coyodex/ignorefile.py:88) — Command shell and build setup (C4) · keeps scanning after a match, so the answer is the last matching pattern and not the first
- [tools/coyodex/ignorefile.py:95](tools/coyodex/ignorefile.py:95) — Command shell and build setup (C4) · reads the file as excluded only when that deciding pattern is an exclusion, not a put-back
- [tools/coyodex/preindex_lib.py:245](tools/coyodex/preindex_lib.py:245) — Pre-index (C33) · keeps the file when the deciding pattern is a put-back line
- enforced at: Declare code the map should not describe (UC4) step 5

**BR5 — A narrowed tree always says so** — Every check and every screen reading a narrowed tree reports which patterns narrowed it and how many files went.  *(verified)*
- [tools/coyodex/validate_model.py:4464](tools/coyodex/validate_model.py:4464) — Map validator (C13) · the disclosure runs on every validate, before the coverage checks, not only in the expensive pass
- [tools/coyodex/scope.py:132](tools/coyodex/scope.py:132) — Command shell and build setup (C4) · the briefing shown before a build states how many files the project's own list removed
- [tools/coyodex/preindex.py:431](tools/coyodex/preindex.py:431) — Pre-index (C33) · the pre-index report names the removed count and every pattern behind it
- [tools/coyodex/viewer/filetree.py:261](tools/coyodex/viewer/filetree.py:261) — File browser tree (C46) · puts the note on the root of the file browser, so a narrowed tree is never shown as the whole project

**BR6 — A pattern that removed nothing is named** — A pattern that removed no file is named on its own, including a line whose spelling can never match anything.  *(verified)*
- [tools/coyodex/ignorefile.py:133](tools/coyodex/ignorefile.py:133) — Command shell and build setup (C4) · collects the patterns that decided nothing, so no report can offer only a total
- [tools/coyodex/validate_analysis.py:336](tools/coyodex/validate_analysis.py:336) — Map validator (C13) · validate names those patterns in a warning of their own
- [tools/coyodex/scope.py:135](tools/coyodex/scope.py:135) — Command shell and build setup (C4) · the briefing before a build warns about them too
- [tools/coyodex/ignorefile.py:170](tools/coyodex/ignorefile.py:170) — Command shell and build setup (C4) · a line carrying a comment after the pattern is dropped and reported, because a comment only opens at the start of a line
- [tools/coyodex/ignorefile.py:176](tools/coyodex/ignorefile.py:176) — Command shell and build setup (C4) · a line made only of slashes is dropped and reported instead of being stored as a pattern that can never fire

### What a code link must point at *(BLK2)*

The one shape every code link takes, and which line inside a file it is allowed to name.

**BR20 — No line, no claim** — A relationship, a step or a decision must name the code line that proves it, or the map is refused.  *(verified)*
- [tools/coyodex/validate_model.py:3540](tools/coyodex/validate_model.py:3540) — Map validator (C13) · refuses a relationship that gives no line and does not declare that none exists
- [tools/coyodex/validate_model.py:1133](tools/coyodex/validate_model.py:1133) — Map validator (C13) · refuses a decision that lists no place where it is enforced
- [tools/coyodex/validate_model.py:1140](tools/coyodex/validate_model.py:1140) — Map validator (C13) · refuses one enforcement place carrying neither a line nor a declared absence
- [tools/coyodex/validate_model.py:401](tools/coyodex/validate_model.py:401) — Map validator (C13) · refuses a step between two parts of the product that gives no line of its own

**BR21 — A missing line is said out loud** — A claim may declare that no single line enforces it. Declaring no line and naming a line at once is refused.  *(verified)*
- [tools/coyodex/validate_model.py:1143](tools/coyodex/validate_model.py:1143) — Map validator (C13) · refuses an enforcement place that both declares no line and gives a line
- [tools/coyodex/validate_model.py:3546](tools/coyodex/validate_model.py:3546) — Map validator (C13) · warns when a relationship declares no line and still carries one
- [tools/coyodex/validate_model.py:407](tools/coyodex/validate_model.py:407) — Map validator (C13) · warns when a step declares no line and still carries one
- [tools/coyodex/audit_model.py:966](tools/coyodex/audit_model.py:966) — Map auditor (C14) · leaves a declared absence out of the claim list a checker is asked to read

**BR22 — One real line that can act** — A code link must name one line, never a whole file. The line must exist in the file. A comment, a blank line or the opening line of a function cannot be the line that acts.  *(verified)*
- [tools/coyodex/validate_model.py:3840](tools/coyodex/validate_model.py:3840) — Map validator (C13) · refuses an enforcement place that names a file without a line
- [tools/coyodex/validate_model.py:1146](tools/coyodex/validate_model.py:1146) — Map validator (C13) · refuses the same file-only place while a worker is still writing its own rows
- [tools/coyodex/validate_model.py:4060](tools/coyodex/validate_model.py:4060) — Map validator (C13) · blocks a link whose file is not in the project
- [tools/coyodex/validate_model.py:4078](tools/coyodex/validate_model.py:4078) — Map validator (C13) · blocks a link naming a line past the end of the file
- [tools/coyodex/anchors.py:128](tools/coyodex/anchors.py:128) — Map document (C1) · counts a blank line as a line that cannot act
- [tools/coyodex/anchors.py:131](tools/coyodex/anchors.py:131) — Map document (C1) · matches the named line against shapes that never act, such as a comment or a function opening
- [tools/coyodex/validate_model.py:4148](tools/coyodex/validate_model.py:4148) — Map validator (C13) · runs that shape test over every link claiming an action fires there

**BR23 — An example, or the exact place** — A relationship shows one example line where it happens. A step shows the exact line, which the reader can open. A change to that line hits the step it belongs to.  *(verified)*
- [tools/coyodex/views.py:649](tools/coyodex/views.py:649) — Graph builder (C45) · shows exactly one line for each relationship, as a witness rather than a list of every call
- [tools/coyodex/views.py:490](tools/coyodex/views.py:490) — Graph builder (C45) · renders a step's own line as a link the reader can open
- [tools/coyodex/impact_lib.py:236](tools/coyodex/impact_lib.py:236) — Change impact (C34) · registers a step's line, so a code change on it points back at that step

**BR24 — Same line, one claim** — Two workers reporting the same relationship at the same line are folded into one claim. Two different lines are both kept, so a person decides which one is right.  *(verified)*
- [tools/coyodex/assemble.py:713](tools/coyodex/assemble.py:713) — Fragment merge (C2) · makes the line part of what identifies a relationship, so only an exact match folds
- [tools/coyodex/assemble.py:710](tools/coyodex/assemble.py:710) — Fragment merge (C2) · keeps a relationship that names no line, because nothing tells two of them apart
- [tools/coyodex/validate_model.py:3570](tools/coyodex/validate_model.py:3570) — Map validator (C13) · flags one relationship declared twice at two different lines, for a person to settle

**BR25 — A moved link is a question, not a verdict** — A link found at the wrong line is reported, never taken as proof the claim is false. A reader may silence one report by writing down why the stored line is right.  *(verified)*
- [tools/coyodex/lint_fragment.py:479](tools/coyodex/lint_fragment.py:479) — Fragment merge (C2) · sends every moved link out on the advisory channel, beside the other nudges
- [tools/coyodex/lint_fragment.py:491](tools/coyodex/lint_fragment.py:491) — Fragment merge (C2) · prints the moved-link count on a passing verdict, so a clean check still says how many moved
- [tools/coyodex/anchor_drift.py:229](tools/coyodex/anchor_drift.py:229) — Grounding record (C23) · drops one report the reader has recorded as a false alarm
- [tools/coyodex/anchor_drift.py:169](tools/coyodex/anchor_drift.py:169) — Grounding record (C23) · requires the whole claim and a non-empty reason, so one record answers one report
- [tools/coyodex/anchor_drift.py:246](tools/coyodex/anchor_drift.py:246) — Grounding record (C23) · reports back a record that silences nothing, because the claim changed or the line was fixed

**BR26 — A place in the running system is not a link** — Where a unit runs, how it is reached, and where a signal is emitted stay plain words. No single code line is that place.  *(verified)*
- [tools/coyodex/views.py:619](tools/coyodex/views.py:619) — Graph builder (C45) · writes what a unit runs on and how it is reached as plain cells, with no link
- [tools/coyodex/views.py:623](tools/coyodex/views.py:623) — Graph builder (C45) · writes where a signal is emitted and where it is watched as plain cells, with no link
- [tools/coyodex/viewer/viewer.js:8178](tools/coyodex/viewer/viewer.js:8178) — Map canvas (C55), Map reading pages (C56), Trail and history (C57), Source column (C58) · shows the emit place in the browser as text, unlike the fields the viewer turns into links

### What blocks a map, and how a finding is closed *(BLK3)*

Which findings stop a build, which only advise, and what it takes to close one for good.

**BR40 — Blocking only where a fix exists** — A finding stops the work only when whoever receives it can still fix it. A judgement call only advises.  *(verified)*
- [tools/coyodex/finalize.py:345](tools/coyodex/finalize.py:345) — Pre-commit gate run (C16) · A disproved claim still standing in the map stops the run, because correcting or dropping it is always possible.
- [tools/coyodex/finalize.py:316](tools/coyodex/finalize.py:316) — Pre-commit gate run (C16) · A code link pointing at the wrong line is only advice, because the repair tool cannot apply every one.
- [tools/coyodex/finalize.py:420](tools/coyodex/finalize.py:420) — Pre-commit gate run (C16) · How boxes are grouped on a screen is recorded as information, and never allowed to move the verdict.
- [tools/coyodex/lint_fragment.py:174](tools/coyodex/lint_fragment.py:174) — Fragment merge (C2) · An access rule that names no stake stops the worker writing it, the one person able to answer.
- [tools/coyodex/lint_fragment.py:480](tools/coyodex/lint_fragment.py:480) — Fragment merge (C2) · A judgement-shaped nudge is printed for the worker and never fails the worker's own check.

**BR41 — Silence is not a pass** — A check that did not run never counts as a check that passed. The run names each check that was missing.  *(verified)*
- [tools/coyodex/finalize.py:490](tools/coyodex/finalize.py:490) — Pre-commit gate run (C16) · One check that should have run and did not makes the whole verdict incomplete.
- [tools/coyodex/finalize.py:934](tools/coyodex/finalize.py:934) — Pre-commit gate run (C16) · An incomplete read exits as a failure, exactly like a finding that blocks.
- [tools/coyodex/lint_fragment.py:487](tools/coyodex/lint_fragment.py:487) — Fragment merge (C2) · A fragment that could not be read gives a did-not-run verdict instead of a clean one.
- [tools/coyodex/finalize.py:393](tools/coyodex/finalize.py:393) — Pre-commit gate run (C16) · A check this run could have done, and was not asked to do, is reported as its own line.
- [tools/coyodex/finalize.py:511](tools/coyodex/finalize.py:511) — Pre-commit gate run (C16) · The written report lists every check that did not run, and says their silence is not a pass.
- enforced at: Run the pre-commit read (UC19) step 8

**BR42 — A reason, or nothing is recorded** — Closing a finding for good takes a written line that names the finding and gives the reason. A line that misses the name, or misses the reason, is refused.  *(verified)*
- [tools/coyodex/record.py:264](tools/coyodex/record.py:264) — Map lookups (C3) · A line that names a finding and gives no reason is refused as a dismissal.
- [tools/coyodex/records.py:151](tools/coyodex/records.py:151) — Map lookups (C3) · The one reader of these lines needs text after the separator before it reads a line as a record.
- [tools/coyodex/record.py:269](tools/coyodex/record.py:269) — Map lookups (C3) · A heading no check reads is refused, because a line under it would silence nothing.
- [tools/coyodex/record.py:309](tools/coyodex/record.py:309) — Map lookups (C3) · The batch is re-read after writing, and refused whole when one line answers no finding.
- [tools/coyodex/validate_model.py:3489](tools/coyodex/validate_model.py:3489) — Map validator (C13) · A stored line that tries to be a record and answers nothing is reported on every run.

**BR43 — One line answers one finding** — A written reason answers only the findings it names. A line that would silence a whole family of findings silences none of them.  *(verified)*
- [tools/coyodex/validate_model.py:3439](tools/coyodex/validate_model.py:3439) — Map validator (C13) · An unscoped deployment exception is reported as silencing nothing, because it once switched off every deployment finding at once.
- [tools/coyodex/records.py:271](tools/coyodex/records.py:271) — Map lookups (C3) · A free-text key answers a line only when the line starts with that key, never when it merely contains it.
- [tools/coyodex/validate_model.py:1487](tools/coyodex/validate_model.py:1487) — Map validator (C13) · A recorded folder covers itself and what sits under it, never a neighbour whose name starts the same.
- [tools/coyodex/records.py:191](tools/coyodex/records.py:191) — Map lookups (C3) · A key list holding one token that is not a key records nothing, rather than the part it could read.

**BR44 — Every silence is reported** — A run always says what each written reason did. The count of findings that reason silenced is shown, or the fact that it silenced none.  *(verified)*
- [tools/coyodex/validate_model.py:3395](tools/coyodex/validate_model.py:3395) — Map validator (C13) · Names how many deployment findings the written reasons swallowed, and which groups they covered.
- [tools/coyodex/validate_model.py:1262](tools/coyodex/validate_model.py:1262) — Map validator (C13) · Names the decision-sounding steps a written reason silenced, and says they were counted as done because of it.
- [tools/coyodex/validate_model.py:3418](tools/coyodex/validate_model.py:3418) — Map validator (C13) · Names a written reason silencing nothing today, so an inert line and a mistyped one are told apart.
- [tools/coyodex/validate_model.py:4744](tools/coyodex/validate_model.py:4744) — Map validator (C13) · Drops every written reason for one read, so a person sees the findings they hide without editing the map.

**BR45 — Advice open is not clean** — A map with open advice is never reported as clean. A run marks one piece of advice answered only where it can name the written line that answers it.  *(verified)*
- [tools/coyodex/finalize.py:492](tools/coyodex/finalize.py:492) — Pre-commit gate run (C16) · Open advice gives the run its own verdict, which is not the clean one.
- [tools/coyodex/finalize.py:929](tools/coyodex/finalize.py:929) — Pre-commit gate run (C16) · Says on screen that advice is not a pass, and that each piece is fixed or recorded.
- [tools/coyodex/finalize.py:719](tools/coyodex/finalize.py:719) — Pre-commit gate run (C16) · Marks a piece of advice unanswered when the finding it names carries no recorded line.
- [tools/coyodex/finalize.py:715](tools/coyodex/finalize.py:715) — Pre-commit gate run (C16) · Says the pairing cannot be decided, rather than guessing that a piece of advice was answered.

**BR46 — The merge refuses to pick a winner** — When two workers state the same thing differently, the merge stops and writes nothing. Neither version is quietly chosen over the other.  *(verified)*
- [tools/coyodex/assemble.py:394](tools/coyodex/assemble.py:394) — Fragment merge (C2) · Two workers claiming one identifier is a conflict, never one silently overwriting the other.
- [tools/coyodex/assemble.py:382](tools/coyodex/assemble.py:382) — Fragment merge (C2) · One fact stated twice with different values stops the merge, and both workers are named.
- [tools/coyodex/assemble.py:558](tools/coyodex/assemble.py:558) — Fragment merge (C2) · Two rows for one channel disagreeing on a value is reported, because the merge will not choose between them.
- [tools/coyodex/assemble.py:891](tools/coyodex/assemble.py:891) — Fragment merge (C2) · A merge conflict leaves no map written at all.
- enforced at: Merge the workers' fragments into one map (UC8) → SF30 step 3 · Turn path rules into explicit assignments (UC9) → SF30 step 3

### How coarse the map may be *(BLK4)*

How big one box may get, how many may share a screen, and when a box should become a group.

**BR60 — Where one box stops** — A folder of at most ten code files and three thousand lines counts as one box. A bigger folder is expected to hold several boxes instead.  *(verified)*
- [tools/coyodex/preindex_lib.py:599](tools/coyodex/preindex_lib.py:599) — Pre-index (C33) · stops at a folder that fits both size limits and counts it as exactly one box
- [tools/coyodex/preindex_lib.py:616](tools/coyodex/preindex_lib.py:616) — Pre-index (C33) · goes inside a folder that is over the limits, so its parts are counted one by one
- [tools/coyodex/preindex_lib.py:615](tools/coyodex/preindex_lib.py:615) — Pre-index (C33) · counts an oversized folder with no sub-folders as several boxes, never as one

**BR61 — Only product code raises the expected count** — The expected number of boxes counts product code only. Documentation, configuration, tests, asset folders and nearly empty folders add no box to that number.  *(verified)*
- [tools/coyodex/preindex_lib.py:577](tools/coyodex/preindex_lib.py:577) — Pre-index (C33) · drops documentation, settings and other text files before counting anything
- [tools/coyodex/preindex_lib.py:579](tools/coyodex/preindex_lib.py:579) — Pre-index (C33) · drops test folders, internal folders and asset folders such as icons, images and translations
- [tools/coyodex/preindex_lib.py:609](tools/coyodex/preindex_lib.py:609) — Pre-index (C33) · folds a nearly empty sub-folder into its parent rather than counting a box for it
- [tools/coyodex/preindex_lib.py:619](tools/coyodex/preindex_lib.py:619) — Pre-index (C33) · counts the loose files of a folder as a box only when they hold real code

**BR62 — Coarseness advises, it never blocks** — How coarse a map is can never fail a build, because every coarseness check only leaves a note. The note also stays quiet while the map sits within forty percent of the expected number of boxes.  *(verified)*
- [tools/coyodex/validate_model.py:4481](tools/coyodex/validate_model.py:4481) — Map validator (C13) · files the box-count comparison under notes, never under failures
- [tools/coyodex/validate_model.py:4501](tools/coyodex/validate_model.py:4501) — Map validator (C13) · files the crowded-screen and thin-screen findings under notes, never under failures
- [tools/coyodex/validate_analysis.py:382](tools/coyodex/validate_analysis.py:382) — Map validator (C13) · says nothing at all while the number of boxes stays inside the forty percent margin
- enforced at: Check the map is well formed (UC11) step 11

**BR63 — About five boxes to a screen** — One screen reads well with three to nine boxes. Once a screen passes twelve boxes the map is told to group them.  *(verified)*
- [tools/coyodex/balance_lib.py:613](tools/coyodex/balance_lib.py:613) — Diagram balance report (C15) · counts a screen as reading well while it carries three to nine boxes
- [tools/coyodex/balance_lib.py:294](tools/coyodex/balance_lib.py:294) — Diagram balance report (C15) · raises the crowding note when the first screen carries more than twelve boxes
- [tools/coyodex/balance_lib.py:307](tools/coyodex/balance_lib.py:307) — Diagram balance report (C15) · raises the same crowding note when a group carries more than twelve boxes

**BR64 — A family of look-alike boxes may be crowded** — A screen may stay crowded when its boxes are same-kind siblings sharing one folder or one name ending. Such a family is only called crowded above fifteen boxes.  *(verified)*
- [tools/coyodex/balance_lib.py:194](tools/coyodex/balance_lib.py:194) — Diagram balance report (C15) · reads the children as one family when two thirds of them sit in the same folder
- [tools/coyodex/balance_lib.py:198](tools/coyodex/balance_lib.py:198) — Diagram balance report (C15) · reads the children as one family when two thirds of their names end in the same word
- [tools/coyodex/balance_lib.py:309](tools/coyodex/balance_lib.py:309) — Diagram balance report (C15) · leaves such a family alone until it passes fifteen boxes

**BR65 — Where a thin screen is a fault** — A thin screen is a fault on the first screen of a large map. Deeper in the map only a group holding exactly one box is called out.  *(verified)*
- [tools/coyodex/balance_lib.py:290](tools/coyodex/balance_lib.py:290) — Diagram balance report (C15) · raises the thin note when the first screen shows under three boxes and the map holds many
- [tools/coyodex/balance_lib.py:303](tools/coyodex/balance_lib.py:303) — Diagram balance report (C15) · raises a note when a group holds exactly one box, so the level earns nothing
- [tools/coyodex/balance.py:147](tools/coyodex/balance.py:147) — Diagram balance report (C15) · names the thin screens deeper in the map and states plainly that none of them is a fault

**BR66 — Re-grouping moves boxes, never changes them** — A re-grouping suggestion may only move a box into another group. Merging two boxes into one, or cutting one box in two, is never suggested.  *(verified)*
- [tools/coyodex/balance_lib.py:524](tools/coyodex/balance_lib.py:524) — Diagram balance report (C15) · starts from exactly the boxes already on the screen, so none is created and none is dropped
- [tools/coyodex/balance.py:103](tools/coyodex/balance.py:103) — Diagram balance report (C15) · the only thing a suggestion adds to the map is a group row
- [tools/coyodex/balance.py:107](tools/coyodex/balance.py:107) — Diagram balance report (C15) · the only change asked of an existing box is which group it belongs to

### What the story must reach *(BLK5)*

Which features the walk has to visit, who counts as an actor, and who a feature is for.

**BR80 — A claimed place in the story** — Each feature states by hand whether the product story must reach it. The map reports every feature whose claim the story contradicts. A feature that states nothing is reported too.  *(verified)*
- [tools/coyodex/validate_model.py:1693](tools/coyodex/validate_model.py:1693) — Map validator (C13) · reports a feature claiming the story must reach it, when no story step does
- [tools/coyodex/validate_model.py:1726](tools/coyodex/validate_model.py:1726) — Map validator (C13) · reports a story step whose work sits in a feature claiming the story skips it
- [tools/coyodex/validate_model.py:1701](tools/coyodex/validate_model.py:1701) — Map validator (C13) · separates a feature that answered nothing from a feature claiming the story skips it
- [tools/coyodex/validate_model.py:2883](tools/coyodex/validate_model.py:2883) — Map validator (C13) · rejects any answer outside the two allowed words, so an unanswered feature stays visible

**BR81 — The driver is the one with the goal** — The party driving a use case is the one whose goal it serves. Machinery that only carries somebody's action inward is not a driver.  *(verified)*
- [tools/coyodex/validate_model.py:1803](tools/coyodex/validate_model.py:1803) — Map validator (C13) · blocks a use case that names no driving party at all
- [tools/coyodex/validate_model.py:1820](tools/coyodex/validate_model.py:1820) — Map validator (C13) · reports a use case naming a person and a program together, because the program is usually delivery machinery
- [tools/coyodex/audit_model.py:692](tools/coyodex/audit_model.py:692) — Map auditor (C14) · reports a traced scenario whose opening party is not one of the declared drivers
- enforced at: Make the map's two layers refute each other (UC12) step 7

**BR82 — Who a feature is for, decided by its people** — Who a feature is for is never written on the feature itself. The people who drive it decide, and a program votes only when no person does. A feature that customers and the company's own staff both drive is flagged for a re-read.  *(verified)*
- [tools/coyodex/validate_model.py:725](tools/coyodex/validate_model.py:725) — Map validator (C13) · sorts each driving party's vote by whether that party is a person or a program
- [tools/coyodex/validate_model.py:726](tools/coyodex/validate_model.py:726) — Map validator (C13) · counts the people's votes, and falls back to the programs only when no person voted
- [tools/coyodex/features.py:353](tools/coyodex/features.py:353) — Feature index (C17) · the feature's record takes the derived answer, so nothing on the feature can contradict its parties
- [tools/coyodex/validate_model.py:3057](tools/coyodex/validate_model.py:3057) — Map validator (C13) · reports a feature whose people pull to opposite sides, unless the map records why

**BR83 — Off the walk is not off the story** — A feature the walk never reaches still holds a place in the one story column. Its author names the feature it reads beside. Without that name the map guesses from the feature's own parties, and otherwise puts it last.  *(verified)*
- [tools/coyodex/features.py:193](tools/coyodex/features.py:193) — Feature index (C17) · uses the author's named neighbour when the feature carries one
- [tools/coyodex/features.py:203](tools/coyodex/features.py:203) — Feature index (C17) · falls back to the last walk step the feature's own parties drive
- [tools/coyodex/features.py:207](tools/coyodex/features.py:207) — Feature index (C17) · puts a feature with nothing to hang on at the end of the column
- [tools/coyodex/validate_model.py:2915](tools/coyodex/validate_model.py:2915) — Map validator (C13) · rejects a named neighbour that is not a defined feature
- [tools/coyodex/validate_model.py:2899](tools/coyodex/validate_model.py:2899) — Map validator (C13) · blocks a story place on a code area or a data area, because only a feature sits in the column

**BR84 — Every front door answers to somebody** — A front door is accounted for when a traced scenario reaches it, or a use case names it. A door nothing claims is reported, including one that starts itself with no caller. Writing a door off silences the report, and the map still counts it as a gap.  *(verified)*
- [tools/coyodex/validate_model.py:1313](tools/coyodex/validate_model.py:1313) — Map validator (C13) · lists every outside-facing door that neither a traced scenario nor a use case reaches
- [tools/coyodex/validate_model.py:1335](tools/coyodex/validate_model.py:1335) — Map validator (C13) · keeps a self-starting job in the same test, so having no caller is not an excuse
- [tools/coyodex/validate_model.py:1365](tools/coyodex/validate_model.py:1365) — Map validator (C13) · drops a door the map has written off, so the report stays quiet about it
- [tools/coyodex/validate_model.py:1530](tools/coyodex/validate_model.py:1530) — Map validator (C13) · counts the written-off doors out loud, so a silenced gap is still visible

**BR85 — Each party says why it comes** — Every party that drives a feature states in its own words what it comes there to do. A blank line does not count as an answer. A line written for a party that drives nothing is reported too.  *(verified)*
- [tools/coyodex/validate_model.py:2971](tools/coyodex/validate_model.py:2971) — Map validator (C13) · reports a driving party that has no line of its own
- [tools/coyodex/validate_model.py:2944](tools/coyodex/validate_model.py:2944) — Map validator (C13) · blocks an empty line, which would count the party as covered while the arrow still falls back
- [tools/coyodex/validate_model.py:2981](tools/coyodex/validate_model.py:2981) — Map validator (C13) · reports a line written for a party that drives none of this feature's work
- [tools/coyodex/validate_model.py:2930](tools/coyodex/validate_model.py:2930) — Map validator (C13) · blocks these lines on a code area or a data area, because only a feature has parties coming to it

**BR86 — One person, several hats** — When one person wears several roles, the map records the link between those roles. A role that turns into another names the action where the change happens.  *(verified)*
- [tools/coyodex/validate_model.py:3017](tools/coyodex/validate_model.py:3017) — Map validator (C13) · blocks a role change that names no action where the change happens
- [tools/coyodex/validate_model.py:3014](tools/coyodex/validate_model.py:3014) — Map validator (C13) · allows only two kinds of link, so a misspelled one cannot pass unseen

### Who owns a piece of data *(BLK6)*

Which part of a project is the system of record for a type, and where that type actually lives.

**BR100 — No card without a real type** — The map draws a kind of data only when the code defines it as a named type.  *(verified)*
- [tools/coyodex/validate_model.py:3754](tools/coyodex/validate_model.py:3754) — Map validator (C13) · rejects a data card that points at no definition in the code
- [tools/coyodex/validate_model.py:3832](tools/coyodex/validate_model.py:3832) — Map validator (C13) · requires that pointer to be a real file location, so a reader can open the type

**BR101 — Only the writer owns the data** — The map credits a part of the project with owning data only when that part's own code writes it.  *(verified)*
- [tools/coyodex/validate_model.py:4533](tools/coyodex/validate_model.py:4533) — Map validator (C13) · counts only save and write links when deciding which part owns a kind of data
- [tools/coyodex/assemble.py:89](tools/coyodex/assemble.py:89) — Fragment merge (C2) · turns an unclear touch into a read, so a filled-in link never grants ownership
- [tools/coyodex/assemble.py:128](tools/coyodex/assemble.py:128) — Fragment merge (C2) · raises a filled-in link to ownership only when some step shows a real write

**BR102 — Data nothing writes needs no owner** — Data that lives inside another record, in the source, or only during a call needs no owner.  *(verified)*
- [tools/coyodex/grammar.py:295](tools/coyodex/grammar.py:295) — Map document (C1) · names the five ways of being stored that mean nothing in the project writes the data
- [tools/coyodex/validate_model.py:4551](tools/coyodex/validate_model.py:4551) — Map validator (C13) · excuses data stored in one of those ways from the missing-owner report

**BR103 — Every save must name what it stores** — A save into a store must be explained by a named type that records the same store.  *(verified)*
- [tools/coyodex/validate_model.py:2747](tools/coyodex/validate_model.py:2747) — Map validator (C13) · accepts the save when the saving part writes a named type kept in that store
- [tools/coyodex/validate_model.py:2748](tools/coyodex/validate_model.py:2748) — Map validator (C13) · also accepts it when the part saves on behalf of the type's owner, one step away

**BR104 — Name the store, do not describe it** — Where data lives must be recorded exactly enough for a reader to find it in the running system.  *(verified)*
- [tools/coyodex/validate_model.py:2795](tools/coyodex/validate_model.py:2795) — Map validator (C13) · flags a compartment named with no store linked to it
- [tools/coyodex/validate_model.py:2817](tools/coyodex/validate_model.py:2817) — Map validator (C13) · flags a compartment name that reads as a description, spotted by the space inside it

**BR105 — Each link between two types is written once** — A relation between two kinds of data is recorded on one side only, never twice.  *(verified)*
- [tools/coyodex/validate_model.py:3780](tools/coyodex/validate_model.py:3780) — Map validator (C13) · rejects a pair where both kinds of data declare the same link
- [tools/coyodex/validate_model.py:3680](tools/coyodex/validate_model.py:3680) — Map validator (C13) · rejects the same link written twice on one card

**BR106 — A lifecycle may be a guess** — A lifecycle whose states no line declares is kept as a guess rather than thrown away.  *(verified)*
- [tools/coyodex/validate_model.py:2658](tools/coyodex/validate_model.py:2658) — Map validator (C13) · marks a lifecycle citing no declaring line as guessed instead of rejecting it
- [tools/coyodex/model.py:322](tools/coyodex/model.py:322) — Map document (C1) · makes the declaring line optional, with nothing written meaning guessed

### What the grounding record may say *(BLK7)*

What a map may claim about how hard its own statements were tested, and what it may not.

**BR120 — Contradiction blocks, thin testing only warns** — A map is blocked when the numbers in its testing record contradict each other. Having tested very little only raises a warning.  *(verified)*
- [tools/coyodex/validate_model.py:2548](tools/coyodex/validate_model.py:2548) — Map validator (C13) · Blocks a record whose held-up, disproved and unsettled tallies do not sum to the number of statements checked.
- [tools/coyodex/validate_model.py:2555](tools/coyodex/validate_model.py:2555) — Map validator (C13) · Blocks a record claiming more statements were checked than the list ever held.
- [tools/coyodex/validate_model.py:2530](tools/coyodex/validate_model.py:2530) — Map validator (C13) · Blocks negative tallies, which can make a wrong record add up.
- [tools/coyodex/validate_model.py:4427](tools/coyodex/validate_model.py:4427) — Map validator (C13) · Sends those arithmetic failures to the blocking list, so a map cannot ship carrying them.
- [tools/coyodex/validate_model.py:4423](tools/coyodex/validate_model.py:4423) — Map validator (C13) · Sends every judgement about how much was checked to the warning list instead, so effort never blocks a map.
- [tools/coyodex/validate_model.py:2413](tools/coyodex/validate_model.py:2413) — Map validator (C13) · Warns when a map carries no testing record at all, so silence cannot read as a clean pass.
- [tools/coyodex/validate_model.py:2435](tools/coyodex/validate_model.py:2435) — Map validator (C13) · Warns when under three statements in five held up, and asks which statements were checked first.

**BR121 — Only three answers** — A check on one statement comes back held up, disproved, or impossible to settle from the code. A fourth answer is refused, never rounded into one of the three.  *(verified)*
- [tools/coyodex/grounding.py:157](tools/coyodex/grounding.py:157) — Grounding record (C23) · Refuses to write the record when any check carries a word outside the three answers.
- [tools/coyodex/grounding.py:767](tools/coyodex/grounding.py:767) — Grounding record (C23) · Runs the same refusal the moment a checker returns, where the fix is still cheap.
- [tools/coyodex/grounding.py:103](tools/coyodex/grounding.py:103) — Grounding record (C23) · Reaches the third answer only when a checker actually said the code cannot settle the statement.

**BR122 — A split vote settles nothing** — A statement counts as held up only when more than half of its checks agree. An even split is filed as unsettled and credited to neither side.  *(verified)*
- [tools/coyodex/grounding.py:99](tools/coyodex/grounding.py:99) — Grounding record (C23) · Requires a strict majority of the checks before a statement counts as held up.
- [tools/coyodex/grounding.py:107](tools/coyodex/grounding.py:107) — Grounding record (C23) · Files an even split as unsettled rather than giving it to the larger-looking side.
- [tools/coyodex/anchor_drift.py:90](tools/coyodex/anchor_drift.py:90) — Grounding record (C23) · Applies the same majority before the code-link check will touch a statement at all.
- [tools/coyodex/grounding.py:281](tools/coyodex/grounding.py:281) — Grounding record (C23) · Lists a split apart from a checker's own cannot-settle answer, so a person adjudicates it.

**BR123 — Stopping early must be declared** — A pass that left statements unchecked is refused until the operator declares that stopping early was deliberate. The declaration must name what was checked first.  *(verified)*
- [tools/coyodex/grounding.py:181](tools/coyodex/grounding.py:181) — Grounding record (C23) · Refuses the record while any statement has no verdict, unless the pass is declared partial.
- [tools/coyodex/grounding.py:187](tools/coyodex/grounding.py:187) — Grounding record (C23) · Refuses the partial declaration when every statement did get a verdict, so a finished pass cannot understate itself.
- [tools/coyodex/grounding.py:192](tools/coyodex/grounding.py:192) — Grounding record (C23) · Refuses a partial pass that carries no note saying which statements were checked first.

**BR124 — Scored against the list as it was pinned** — How much of a map was checked is counted against the statement list as it stood before any fixes. Statements nobody voted on stay in that list.  *(verified)*
- [tools/coyodex/grounding.py:163](tools/coyodex/grounding.py:163) — Grounding record (C23) · Refuses a verdict for a statement missing from the pinned list, which proves the wrong snapshot was used.
- [tools/coyodex/grounding.py:203](tools/coyodex/grounding.py:203) — Grounding record (C23) · Keeps the whole pinned list as the total, so a short pass cannot shrink what it is measured against.
- [tools/coyodex/grounding.py:204](tools/coyodex/grounding.py:204) — Grounding record (C23) · Subtracts an unvoted statement from the number checked, never from the total.
- [tools/coyodex/grounding.py:225](tools/coyodex/grounding.py:225) — Grounding record (C23) · Counts separately how many statements the shipped map carries that a checker actually saw.

**BR125 — A disproved statement may not stay** — A statement the checkers disproved may not remain in the map word for word. A run that finds one fails.  *(verified)*
- [tools/coyodex/grounding.py:992](tools/coyodex/grounding.py:992) — Grounding record (C23) · Fails the run when any disproved statement still matches the shipped map.
- [tools/coyodex/grounding.py:298](tools/coyodex/grounding.py:298) — Grounding record (C23) · Names each disproved statement the map still carries word for word, which the counts alone cannot show.

**BR126 — A moved code link is a correction, not a disproof** — Correcting the code link under a statement never counts against the statement itself. The check that finds a moved link reports it and never fails a run.  *(verified)*
- [tools/coyodex/anchor_drift.py:435](tools/coyodex/anchor_drift.py:435) — Grounding record (C23) · Ends the code-link check as a report, so a moved link cannot block a map.
- [tools/coyodex/anchor_drift.py:86](tools/coyodex/anchor_drift.py:86) — Grounding record (C23) · Skips statements whose link deliberately points at a definition rather than the acting line, so a different line is not a move.
- [tools/coyodex/anchor_drift.py:229](tools/coyodex/anchor_drift.py:229) — Grounding record (C23) · Lets a person record for good that the stored link is the right one, so the finding stops repeating.

### Whether a build may proceed, and in which mode *(BLK8)*

What coyodex does when asked to work on a project, and what it refuses to do without being told.

**BR140 — The working tree decides the mode** — What coyodex does next is decided by the working tree, never by what the project's history still holds.  *(verified)*
- [method/dispatch.md:75](method/dispatch.md:75) — Build method (C75) · looks for an existing map only in the working tree, not in the project's history
- [method/dispatch.md:77](method/dispatch.md:77) — Build method (C75) · refuses to restore a deleted map from history, so deleting it is how a person asks for a fresh build
- [method/dispatch.md:147](method/dispatch.md:147) — Build method (C75) · stops and says the baseline is up to date when the code matches the pin, instead of writing an empty report
- [method/dispatch.md:150](method/dispatch.md:150) — Build method (C75) · routes to change analysis when the code differs from the pin, uncommitted edits included
- enforced at: Archive a map so the next run builds from scratch (UC37) step 5

**BR141 — Briefing before any work** — Before any work starts, the person is told which files will be read and what the pin means.  *(verified)*
- [method/dispatch.md:22](method/dispatch.md:22) — Build method (C75) · requires the briefing to be the first message, shown word for word
- [tools/coyodex/scope.py:172](tools/coyodex/scope.py:172) — Command shell and build setup (C4) · prints the briefing: how many files will be read and what the map's commit will claim
- [tools/coyodex/scope.py:135](tools/coyodex/scope.py:135) — Command shell and build setup (C4) · names every ignore pattern that removed nothing, so a narrowing of the file set cannot pass unseen
- enforced at: Brief the reader on what will be analysed (UC3) step 8 · Report what a code change did to the map (UC25) step 5

**BR142 — A rebuild never reads the old map** — A rebuild never opens the map it is replacing, so the new map cannot copy the old one.  *(verified)*
- [method/dispatch.md:119](method/dispatch.md:119) — Build method (C75) · forbids opening any earlier map during a build, filed archives included
- [tools/coyodex/scope.py:116](tools/coyodex/scope.py:116) — Command shell and build setup (C4) · warns when a map sits inside the set of files to be read, so a hand-made copy is not analyzed as source

**BR143 — Uncommitted code is pinned as uncommitted** — A map built on uncommitted code records a commit marked as not containing that code.  *(verified)*
- [method.md:2043](method.md:2043) — Build method (C75) · requires the marked pin whenever the person chooses to go on without committing
- [method/dispatch.md:49](method/dispatch.md:49) — Build method (C75) · states, at the moment of the choice, that the marked pin means the code is in no commit
- [tools/coyodex/provenance.py:177](tools/coyodex/provenance.py:177) — Assignment pass (C25) · computes the pin and marks it whenever the tree holds uncommitted code
- [tools/coyodex/provenance.py:360](tools/coyodex/provenance.py:360) — Assignment pass (C25) · writes that same pin into the map's header, so the header cannot claim a clean commit

**BR144 — Nothing of the user's is changed unasked** — Nothing the user owns is committed, stashed or overwritten unless the user asks for it.  *(access)*  *(verified)*
- [method/dispatch.md:46](method/dispatch.md:46) — Build method (C75) · forbids committing or stashing the person's code, even to make the pin clean
- [method.md:2040](method.md:2040) — Build method (C75) · repeats the same ban at the moment the pin is recorded
- [method/dispatch.md:171](method/dispatch.md:171) — Build method (C75) · regenerates a map from scratch only on an explicit request, after a warning and a confirmation

**BR145 — The old map is filed, never deleted** — Clearing the way for a rebuild files the old map away instead of deleting it.  *(verified)*
- [eval/tools/coyodex_eval/archive.py:107](eval/tools/coyodex_eval/archive.py:107) — Map archive and build guard (C66) · moves each part of the map into the archive folder rather than removing it
- [eval/tools/coyodex_eval/archive.py:113](eval/tools/coyodex_eval/archive.py:113) — Map archive and build guard (C66) · puts back everything already moved when a move fails, so no half-filed map is left behind
- enforced at: Archive a map so the next run builds from scratch (UC37) step 2

**BR146 — No review of a running build** — A review of a build is refused while anything is still writing that build's map.  *(verified)*
- [eval/tools/coyodex_eval/retro_precheck.py:201](eval/tools/coyodex_eval/retro_precheck.py:201) — Map archive and build guard (C66) · refuses when any map file was written moments ago
- [eval/tools/coyodex_eval/retro_precheck.py:235](eval/tools/coyodex_eval/retro_precheck.py:235) — Map archive and build guard (C66) · refuses when another session has been active moments ago
- [eval/tools/coyodex_eval/retro_precheck.py:191](eval/tools/coyodex_eval/retro_precheck.py:191) — Map archive and build guard (C66) · refuses when the review would be reading the map its own session just wrote

### What the viewer may show and read *(BLK9)*

Who may reach the map server, which files it will open, and which version of each it shows.

**BR160 — Local machine only** — The map server answers only the person sitting at this machine. It listens on the loopback address and nowhere else. A request that names any other site is refused. A request that changes the remembered project list must carry a private marker header.  *(access)*  *(verified)*
- [tools/coyodex/viewer/serve.py:800](tools/coyodex/viewer/serve.py:800) — Map server (C43) · The server binds to the loopback address, so nothing off this machine can connect.
- [tools/coyodex/viewer/serve.py:577](tools/coyodex/viewer/serve.py:577) — Map server (C43) · Every read request whose claimed site is not loopback is refused.
- [tools/coyodex/viewer/serve.py:599](tools/coyodex/viewer/serve.py:599) — Map server (C43) · The same site check refuses a write request.
- [tools/coyodex/viewer/serve.py:601](tools/coyodex/viewer/serve.py:601) — Map server (C43) · A write request without the private marker header is refused.
- enforced at: Start the local map server (UC2) step 6

**BR161 — Only folders you opened** — The server shows only project folders the user has opened before. It never searches the disk for maps. An address naming any other project is refused. A folder can be added only when it already holds a coyodex folder.  *(access)*  *(verified)*
- [tools/coyodex/viewer/serve.py:799](tools/coyodex/viewer/serve.py:799) — Map server (C43) · The served set is built from the remembered list alone, with no disk search.
- [tools/coyodex/viewer/serve.py:590](tools/coyodex/viewer/serve.py:590) — Map server (C43) · An address that does not name a served project is refused.
- [tools/coyodex/viewer/serve.py:640](tools/coyodex/viewer/serve.py:640) — Map server (C43) · Adding a folder is refused unless it holds a coyodex folder.
- [tools/coyodex/viewer/serve.py:794](tools/coyodex/viewer/serve.py:794) — Map server (C43) · A folder named at startup is skipped under the same condition.

**BR162 — Only in-project, tracked files** — The code viewer opens a file only when it sits inside the project being shown. A path that climbs out of the project is refused. A link that points outside the project is refused too. From the working tree only files version control accounts for are served.  *(access)*  *(verified)*
- [tools/coyodex/viewer/serve.py:285](tools/coyodex/viewer/serve.py:285) — Map server (C43) · An absolute or otherwise malformed path is rejected before any read.
- [tools/coyodex/viewer/serve.py:287](tools/coyodex/viewer/serve.py:287) — Map server (C43) · A path containing a step up to the parent folder is rejected.
- [tools/coyodex/viewer/serve.py:697](tools/coyodex/viewer/serve.py:697) — Map server (C43) · The code request refuses a bad path before touching disk or version control.
- [tools/coyodex/viewer/serve.py:324](tools/coyodex/viewer/serve.py:324) — Map server (C43) · A working-tree read refuses anything inside the version-control folder.
- [tools/coyodex/viewer/serve.py:331](tools/coyodex/viewer/serve.py:331) — Map server (C43) · The real resolved location must still sit inside the project, so a link cannot escape.
- [tools/coyodex/viewer/serve.py:338](tools/coyodex/viewer/serve.py:338) — Map server (C43) · A file version control ignores is refused, so an ignored secrets file never leaks.

**BR163 — Always the map's own version** — What a reader sees always matches the map. Each file is read from version control at the commit the map was pinned to, not from the working copy. A map edited while the server runs is picked up on the next page load.  *(verified)*
- [tools/coyodex/viewer/serve.py:701](tools/coyodex/viewer/serve.py:701) — Map server (C43) · A code request defaults to the map's pinned commit; another version is asked for explicitly.
- [tools/coyodex/viewer/serve.py:435](tools/coyodex/viewer/serve.py:435) — Map server (C43) · The file browser lists the files present at the map's pinned commit.
- [tools/coyodex/viewer/serve.py:592](tools/coyodex/viewer/serve.py:592) — Map server (C43) · Every project request first checks whether the map changed on disk.
- [tools/coyodex/viewer/serve.py:210](tools/coyodex/viewer/serve.py:210) — Map server (C43) · A changed map drops the stored copies of the browser tree, the views and the code symbols.

**BR164 — A narrowed tree says so** — The file browser never presents a shortened tree as the whole project. When the skip list hid files, the tree carries a note. The note says how many files went, which pattern removed each one, and which pattern removed nothing.  *(verified)*
- [tools/coyodex/viewer/filetree.py:261](tools/coyodex/viewer/filetree.py:261) — File browser tree (C46) · The note about what the skip list removed is attached to the top of the tree.

**BR165 — Editor links only** — A link that leaves the page may open only a known code editor. The address must start with one of a fixed list of editor schemes. A hand-typed link template using any other scheme is refused.  *(access)*  *(verified)*
- [tools/coyodex/viewer/viewer.js:10684](tools/coyodex/viewer/viewer.js:10684) — Map canvas (C55), Map reading pages (C56), Trail and history (C57), Source column (C58) · An address outside the allowed editor list never becomes a clickable link.
- [tools/coyodex/viewer/viewer.js:10815](tools/coyodex/viewer/viewer.js:10815) — Map canvas (C55), Map reading pages (C56), Trail and history (C57), Source column (C58) · Saving a custom link template is refused when its scheme is not on the list.

**BR166 — Pinned outside libraries** — The viewer page loads its two diagram libraries from the internet at exact pinned versions. Each one carries a fingerprint of the expected file. The browser refuses to run a file whose content does not match that fingerprint.  *(access)*  *(verified)*
- [tools/coyodex/viewer/viewer.html:17](tools/coyodex/viewer/viewer.html:17) — Map canvas (C55), Trail and history (C57), Source column (C58) · The pan and zoom library is pinned by fingerprint.
- [tools/coyodex/viewer/viewer.html:20](tools/coyodex/viewer/viewer.html:20) — Map canvas (C55), Trail and history (C57), Source column (C58) · The diagram drawing library is pinned by fingerprint.

### When a rebuilt map counts as worse *(BLK10)*

What has to move, and by how much, before a new map is called a regression rather than a change.

**BR180 — Drift asks, a failure stops** — A measurement that moved too far asks for a human look, while a failed check stops the work.  *(verified)*
- [eval/tools/coyodex_eval/compare.py:503](eval/tools/coyodex_eval/compare.py:503) — Map quality score and verdict (C63) · any failed hard check makes the answer the blocking one, before anything else is considered
- [eval/tools/coyodex_eval/compare.py:505](eval/tools/coyodex_eval/compare.py:505) — Map quality score and verdict (C63) · a breached allowance only reaches the softer answer, which asks for a person rather than blocking
- [eval/tools/coyodex_eval/compare.py:670](eval/tools/coyodex_eval/compare.py:670) — Map quality score and verdict (C63) · the three answers leave three different exit codes, so an unattended run can tell them apart
- [eval/tools/coyodex_eval/run.py:275](eval/tools/coyodex_eval/run.py:275) — Map quality score and verdict (C63) · the full run returns the same three codes, keeping the meaning identical wherever the comparison is invoked

**BR181 — A finer map is never worse** — A count that grew is never called worse, while a count that fell by thirty percent is.  *(verified)*
- [eval/tools/coyodex_eval/compare.py:195](eval/tools/coyodex_eval/compare.py:195) — Map quality score and verdict (C63) · a shrink-only limit passes any growth and only breaches on a fall past the allowance
- [eval/tools/coyodex_eval/compare.py:454](eval/tools/coyodex_eval/compare.py:454) — Map quality score and verdict (C63) · the name of each limit decides whether it is shrink-only or reacts to movement in both directions
- [eval/tools/coyodex_eval/compare.py:57](eval/tools/coyodex_eval/compare.py:57) — Map quality score and verdict (C63) · sets the allowed fall for a raw count at thirty percent of the accepted map's count

**BR182 — Zoom is judged against the code** — The number of boxes is measured against a count derived from the code, not against the accepted map.  *(verified)*
- [eval/tools/coyodex_eval/profile.py:271](eval/tools/coyodex_eval/profile.py:271) — Map quality score and verdict (C63) · the expected number of boxes is computed fresh from the source tree at scoring time
- [eval/tools/coyodex_eval/compare.py:444](eval/tools/coyodex_eval/compare.py:444) — Map quality score and verdict (C63) · the new map's distance is measured from that code-derived expectation, not from the accepted map
- [eval/tools/coyodex_eval/compare.py:450](eval/tools/coyodex_eval/compare.py:450) — Map quality score and verdict (C63) · only the new map's distance decides the check; the accepted map's distance is shown but never decides

**BR183 — No score from judging that failed** — Judging that did not happen never becomes a score, for the map or against it.  *(verified)*
- [eval/tools/coyodex_eval/judge.py:241](eval/tools/coyodex_eval/judge.py:241) — Map quality score and verdict (C63) · claims nobody could read are removed from the divisor, so they never lower the pass rate
- [eval/tools/coyodex_eval/judge.py:303](eval/tools/coyodex_eval/judge.py:303) — Map quality score and verdict (C63) · a reader who says it could not reach the code is recorded as a failure, never as a disproof
- [eval/tools/coyodex_eval/judge.py:336](eval/tools/coyodex_eval/judge.py:336) — Map quality score and verdict (C63) · a scoring stage that produced nothing yields no dimension scores instead of zeros
- [eval/tools/coyodex_eval/compare.py:212](eval/tools/coyodex_eval/compare.py:212) — Map quality score and verdict (C63) · caps how much of the reading may fail before the whole reading is called untrustworthy
- [eval/tools/coyodex_eval/compare.py:493](eval/tools/coyodex_eval/compare.py:493) — Map quality score and verdict (C63) · either side missing its reading breaches, so a skipped reading can never end in a clean pass

**BR184 — A skipped check says so** — A check that cannot run is reported as skipped, because silence would read as a check that passed.  *(verified)*
- [eval/tools/coyodex_eval/compare.py:282](eval/tools/coyodex_eval/compare.py:282) — Map quality score and verdict (C63) · the source-coverage check names itself as skipped when a map was scored without the code
- [eval/tools/coyodex_eval/compare.py:385](eval/tools/coyodex_eval/compare.py:385) — Map quality score and verdict (C63) · a check that is always true against an older accepted map is announced as empty rather than reported as passing
- [eval/tools/coyodex_eval/compare.py:437](eval/tools/coyodex_eval/compare.py:437) — Map quality score and verdict (C63) · the zoom check says it was skipped when the new map carries no code-derived expectation
- [eval/tools/coyodex_eval/compare.py:534](eval/tools/coyodex_eval/compare.py:534) — Map quality score and verdict (C63) · the comparison of enforcement locations says it was skipped rather than reading absence as agreement
- [eval/tools/coyodex_eval/process_scorecard.py:3182](eval/tools/coyodex_eval/process_scorecard.py:3182) — Build behaviour scorecard (C65) · the scorecard refuses to score at all when the map cannot be read, rather than letting three map-reading rules score zero while the run still reports success
- enforced at: Score a build's behaviour against the method (UC35) step 4

**BR185 — No verdict without the frozen map** — The run refuses a verdict when the map changed after freezing, or when the accepted map is missing.  *(verified)*
- [eval/tools/coyodex_eval/run.py:212](eval/tools/coyodex_eval/run.py:212) — Map quality score and verdict (C63) · an empty freeze value is refused, so the guard is never switched off by an unnoticed typing mistake
- [eval/tools/coyodex_eval/run.py:219](eval/tools/coyodex_eval/run.py:219) — Map quality score and verdict (C63) · refuses to score a map whose bytes no longer match the ones frozen when the run was picked
- [eval/tools/coyodex_eval/run.py:242](eval/tools/coyodex_eval/run.py:242) — Map quality score and verdict (C63) · a named accepted map that is not there stops the run instead of quietly comparing nothing
- [eval/tools/coyodex_eval/run.py:247](eval/tools/coyodex_eval/run.py:247) — Map quality score and verdict (C63) · an accepted map holding no scores stops the run, because an empty standard cannot produce a verdict

**BR186 — Stored judgements die with the method** — Judgements kept from an earlier run are thrown away when the judging method has changed since.  *(verified)*
- [eval/tools/coyodex_eval/run.py:451](eval/tools/coyodex_eval/run.py:451) — Map quality score and verdict (C63) · a stored reading that does not record which judging method made it is treated as unusable
- [eval/tools/coyodex_eval/run.py:455](eval/tools/coyodex_eval/run.py:455) — Map quality score and verdict (C63) · a stored reading made under a different judging method is refused, and the map must be judged again
- [eval/tools/coyodex_eval/compare.py:477](eval/tools/coyodex_eval/compare.py:477) — Map quality score and verdict (C63) · two sides judged under different methods breach, so the comparison cannot end in a clean pass

**BR187 — The checkers are graded on planted lies** — The checkers are scored on how many deliberately false claims they refuse to confirm.  *(verified)*
- [eval/tools/coyodex_eval/mutate.py:228](eval/tools/coyodex_eval/mutate.py:228) — Map quality score and verdict (C63) · confirming a claim that was made false on purpose is the only outcome scored as a miss
- [eval/tools/coyodex_eval/mutate.py:216](eval/tools/coyodex_eval/mutate.py:216) — Map quality score and verdict (C63) · a moved code link counts as caught only when the checker reports a different line than the planted one
- [eval/tools/coyodex_eval/mutate.py:161](eval/tools/coyodex_eval/mutate.py:161) — Map quality score and verdict (C63) · the four kinds of falsehood are planted in turn, so no single easy kind can dominate the score
- [eval/tools/coyodex_eval/mutate.py:113](eval/tools/coyodex_eval/mutate.py:113) — Map quality score and verdict (C63) · a planted moved link must land on a real line of code, so the hard case is not quietly replaced by the easy one

---

## Operational dimensions — the standard core four

### Deployment & topology

| Unit | Runs on | Exposed as | Config source |
|---|---|---|---|
| coyodex command | the user's own machine, in a private Python environment inside the coyodex folder | a terminal command, started by hand or by the coding agent following the method | The package file declares the command name. The setup target builds the environment and installs the package editable, so the clone stays the live source. |
| map server | the same machine, as a long-running Python process bound to the loopback address only | a web address on port 8765, reachable from that machine and no other | The port comes from the start option, defaulting to 8765. The projects served come from the recents file in the user's home folder; there is no disk scan. |
| viewer page | the reader's web browser | the landing page the map server serves, showing one card per project | Per-machine choices kept by the browser itself: the chosen editor, the project's folder on disk, and the code-hosting address. Defaults for the last two are delivered with the map. |

### Observability

| Signal | Where emitted | Where viewed | Alerts |
|---|---|---|---|
| Map check findings | The check command prints an inventory line, then the warnings, then the blocking failures. A machine-readable flag prints the same findings as data, with no list shortened. | The terminal of whoever ran the check, usually the coding agent building the map. | None. A blocking failure is reported as a non-zero exit, which stops the build step that ran the check. |
| Map server start and stop lines | On start the server prints how many projects it has and the address it listens on. On stop it prints one line. | The terminal the map server runs in. | None. |
| Per-request access log | Nothing. The map server deliberately silences the request log it would otherwise print. | Nowhere. There is no request history to read. | None. |
| Stale-server warning | The map server checks its own Python files while it runs. When one is newer than the start time it prints a warning saying to restart. | The terminal the map server runs in. The warning appears once per change, not once per request. | None. |
| Build stamp | Each build records its session id and its build time in a provenance file inside the project's map folder. | That file. The finalize step refuses to bless a commit whose provenance file is missing. | None. |
| Change-impact report | A change-impact run writes a markdown report next to the map in the project's map folder. | The file itself, and the viewer, which lays the report over the map when the file is present. | None. |

### Security & auth

Derived from the business rules marked `access` (T7) — the decision IS the surface.

| Decision | Enforced at | Risk note |
|---|---|---|
| **BR144** — Nothing of the user's is changed unasked | [method/dispatch.md:46](method/dispatch.md:46) · [method.md:2040](method.md:2040) · [method/dispatch.md:171](method/dispatch.md:171) | A reviewed map, or a commit the person never intended, is lost, and coyodex cannot undo either. |
| **BR160** — Local machine only | [tools/coyodex/viewer/serve.py:800](tools/coyodex/viewer/serve.py:800) · [tools/coyodex/viewer/serve.py:577](tools/coyodex/viewer/serve.py:577) · [tools/coyodex/viewer/serve.py:599](tools/coyodex/viewer/serve.py:599) · [tools/coyodex/viewer/serve.py:601](tools/coyodex/viewer/serve.py:601) | Without this limit, a web page open in the reader's browser could read the whole project's source code. |
| **BR161** — Only folders you opened | [tools/coyodex/viewer/serve.py:799](tools/coyodex/viewer/serve.py:799) · [tools/coyodex/viewer/serve.py:590](tools/coyodex/viewer/serve.py:590) · [tools/coyodex/viewer/serve.py:640](tools/coyodex/viewer/serve.py:640) · [tools/coyodex/viewer/serve.py:794](tools/coyodex/viewer/serve.py:794) | Without this limit, a page could name any folder on the machine and read the code inside it. |
| **BR162** — Only in-project, tracked files | [tools/coyodex/viewer/serve.py:285](tools/coyodex/viewer/serve.py:285) · [tools/coyodex/viewer/serve.py:287](tools/coyodex/viewer/serve.py:287) · [tools/coyodex/viewer/serve.py:697](tools/coyodex/viewer/serve.py:697) · [tools/coyodex/viewer/serve.py:324](tools/coyodex/viewer/serve.py:324) · [tools/coyodex/viewer/serve.py:331](tools/coyodex/viewer/serve.py:331) · [tools/coyodex/viewer/serve.py:338](tools/coyodex/viewer/serve.py:338) | Without this limit, a reader could pull any file on the machine, including secrets kept out of version control. |
| **BR165** — Editor links only | [tools/coyodex/viewer/viewer.js:10684](tools/coyodex/viewer/viewer.js:10684) · [tools/coyodex/viewer/viewer.js:10815](tools/coyodex/viewer/viewer.js:10815) | Without this limit a typed link template could run script inside the viewer. A reader could also be sent to an attacker's site. |
| **BR166** — Pinned outside libraries | [tools/coyodex/viewer/viewer.html:17](tools/coyodex/viewer/viewer.html:17) · [tools/coyodex/viewer/viewer.html:20](tools/coyodex/viewer/viewer.html:20) | Without this check, a changed library file could run any code inside the viewer and read the project it shows. |

### Config & environments

| Key | Purpose | Default | Per-env / secret? |
|---|---|---|---|
| map server port | Which port the local map server listens on. | 8765, overridable with the start option or the make variable |  |
| COYODEX_HOME | Which clone the method files and templates are read from. | the folder of the installed package, when the variable is unset |  |
| CLAUDE_CODE_SESSION_ID | Names the agent session that built a map, so the build stamp can record it. | unset, and the stamp command then refuses to run rather than guess |  |
| COYODEX_NO_SERVE_REGISTER | Stops a finished build from adding its project to the map server's landing page. | unset, so every build registers its own project |  |
| recents file | The list of project folders the map server offers as cards. | `~/.coyodex/serve-recents.json`, treated as empty until it is first written |  |
| analysis ignore file | Extra file patterns to leave out of the analysis, on top of what git already ignores. | absent, so nothing beyond the git rules is left out |  |
| GIT_TERMINAL_PROMPT | Keeps a git read from stopping to ask for a password. | `0`, set by coyodex on every git call it makes |  |
| GIT_OPTIONAL_LOCKS | Keeps a git read from taking a lock in the project being mapped. | `0`, set by coyodex on every git call it makes |  |
| chosen code editor | Which editor a source link opens in, remembered per machine by the browser. | unset, so the reader is asked once on the first source link |  |
| project folder on disk | The absolute folder a source link is resolved against before the editor opens it. | the project's git top level, as found when the map was built |  |
| code-hosting address | The website a source link opens on when no editor is chosen. | derived from the project's `origin` remote, when that remote points at GitHub |  |

---

## Relationships — backbone edge list

| From | Verb | To | Why | Where (example) |
|---|---|---|---|---|
| C77 | routes-to | C78 | The eval skill file carries only how to find the coyodex clone, then sends the reader to the scoring recipe. | [SKILL.md](eval/SKILL.md:28) |
| C77 | routes-to | C79 | sends the reader on to the review recipe, which names every other document and tool | [SKILL.md](eval/retro/SKILL.md:28) |
| C63 | reads | C78 | The comparison step opens the pass marks file to learn which gates and bands a map must clear. | [compare.py](eval/tools/coyodex_eval/compare.py:601) |
| C78 | prescribes | C63 | The scoring recipe tells the reviewer to compare the new map against the accepted one. | [method.md](eval/method.md:352) |
| C79 | prescribes | C63 | The review recipe tells the reviewer to reduce the map to numbers before reading the chat. | [method.md](eval/retro/method.md:298) |
| C79 | prescribes | C64 | The review recipe tells the reviewer to report the time and the money the build spent. | [method.md](eval/retro/method.md:384) |
| C79 | prescribes | C65 | The review recipe tells the reviewer to score what the build did against the method's rules. | [method.md](eval/retro/method.md:359) |
| C79 | prescribes | C66 | The review recipe tells the reviewer to refuse a review while a build is still writing. | [method.md](eval/retro/method.md:62) |
| C1 | loads | E1 | turns the map file's text into the typed map document every command works on | [model.py](tools/coyodex/model.py:1080) |
| C4 | invokes | D2 | builds a private Python environment inside the clone and runs every coyodex command from it | [Makefile](Makefile:33) |
| C4 | installs with | D7 | installs the coyodex commands into that private environment through the declared build backend | [Makefile](Makefile:40) |
| C4 | reads | C77 | reads the shipped skill file and substitutes this clone's absolute path into the copy it installs | [Makefile](Makefile:58) |
| C4 | writes | D12 | writes the finished skill into Claude Code's skills folder | [Makefile](Makefile:58) |
| C4 | writes | D13 | writes the finished skill into the cross-agent skills folder Codex reads | [Makefile](Makefile:58) |
| C4 | writes | D14 | writes the finished skill into the two folders Cursor already reads | [Makefile](Makefile:17) |
| C4 | starts | C43 | loads the map server's code late and hands it the rest of the command line | [cli.py](tools/coyodex/cli.py:141) |
| C43 | reads | E1 | reads every served project's map document for its title, its goal and its pinned commit | [serve.py](tools/coyodex/viewer/serve.py:123) |
| C43 | calls | D11 | opens the landing page in the reader's default browser when the start command asks for it | [serve.py](tools/coyodex/viewer/serve.py:806) |
| C43 | calls | C45 | turns each loaded map document into the graph the viewer draws from | [serve.py](tools/coyodex/viewer/serve.py:455) |
| C43 | calls | C44 | asks for the whole view bundle in one call, diagrams, flows and colours together | [serve.py](tools/coyodex/viewer/serve.py:460) |
| C45 | creates | E51 | builds one graph box per map element, carrying its name, kind, source line and parent | [views.py](tools/coyodex/views.py:730) |
| C45 | creates | E52 | builds one graph arrow per recorded relation, carrying its verb and its call site | [views.py](tools/coyodex/views.py:1183) |
| C55 | fetches | C43 | fetches this map's whole view bundle from the server at page load | [viewer.js](tools/coyodex/viewer/viewer.js:154) |
| C55 | calls | C57 | hands every new place to the trail, which records it and drives the change of view | [viewer.js](tools/coyodex/viewer/viewer.js:11694) |
| C55 | draws with | D8 | draws every diagram on the page | [viewer.js](tools/coyodex/viewer/viewer.js:8953) |
| C55 | pans and zooms with | D9 | wraps each drawn diagram so the reader can pan it and zoom it | [viewer.js](tools/coyodex/viewer/viewer.js:9025) |
| C43 | persists | E56 | writes the remembered project list back to the reader's home folder | [recents.py](tools/coyodex/viewer/recents.py:44) |
| C77 | routes-to | C75 | sends the coding agent from the installed pointer into the method's dispatch document, which names every other doc and tool | [SKILL.md](skill/coyodex/SKILL.md:27) |
| C75 | routes-to | C76 | names each worker briefing and tells the agent to fetch it with the contract verb instead of copying the file | [method.md](method.md:1960) |
| C4 | reads | C76 | opens the briefing template and the writing rules and prints the agent's half of them | [contract.py](tools/coyodex/contract.py:90) |
| C75 | prescribes | C33 | prescribes the pre-index run that surveys the repo before any altitude is chosen | [method.md](method.md:860) |
| C75 | prescribes | C2 | prescribes the assemble run that merges the workers' fragments into the stored map | [method.md](method.md:2100) |
| C75 | prescribes | C25 | prescribes the reconcile run that expands the path rules into an explicit assignment file | [method.md](method.md:1298) |
| C75 | prescribes | C13 | prescribes the validate run that checks the assembled map is well-formed | [method.md](method.md:2112) |
| C75 | prescribes | C14 | prescribes the audit run that hunts contradictions and emits the grounding worklist | [method.md](method.md:2127) |
| C75 | prescribes | C23 | prescribes the grounding run that derives the map's verification record from the skeptics' verdicts | [method.md](method.md:1655) |
| C75 | prescribes | C24 | prescribes the mechanical repairs, so a drifted anchor or a duplicate relation is never hand-scripted | [method.md](method.md:1943) |
| C75 | prescribes | C15 | prescribes the balance run whose per-diagram findings the synthesis phase must reconcile | [method.md](method.md:1421) |
| C75 | prescribes | C3 | prescribes looking an id up with the dump verb rather than reading the stored map by hand | [method.md](method.md:1580) |
| C75 | prescribes | C16 | prescribes the finalize run as the pre-commit read over the finished map | [method.md](method.md:2164) |
| C75 | prescribes | C43 | prescribes starting the map server so a reader can look at the change in the viewer | [change-impact.md](method/change-impact.md:142) |
| C16 | reads | C1 | parses the map file into the typed document before running the gate legs over it | [finalize.py](tools/coyodex/finalize.py:570) |
| C17 | reads | C1 | walks the document's flows, expanding each sub-flow reference, to build the feature index | [features.py](tools/coyodex/features.py:312) |
| C23 | reads | C1 | parses the live map into the typed document to measure the verification record against it | [grounding.py](tools/coyodex/grounding.py:979) |
| C24 | reads | C1 | reads the document's access rules and its id arrays to decide what a repair must touch | [fix.py](tools/coyodex/fix.py:1007) |
| C34 | reads | C1 | walks the document's group forests to index every anchor a changed line could hit | [impact_lib.py](tools/coyodex/impact_lib.py:251) |
| C44 | reads | C1 | parses the map file into the typed document before generating the viewer bundle | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:3257) |
| C45 | reads | C1 | reads every element of the typed document to turn it into graph nodes and markdown | [views.py](tools/coyodex/views.py:661) |
| C65 | reads | C1 | parses the built map into the typed document to check the build's behaviour against it | [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:2851) |
| C64 | reads | D12 | streams the Claude Code build transcript file, one JSON record per line, to report the turns and the spend | [transcript.py](eval/tools/coyodex_eval/transcript.py:305) |
| C66 | reads | D12 | scans the Claude Code transcript folder for a session still writing, before it moves a map | [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:216) |
| C75 | reads | E1 | reads the baseline map's pin and its element rows, the model every code diff is measured against | [dispatch.md](method/dispatch.md:132) |
| C3 | reads | E1 | reads element records, member lists and the backbone edges out of the loaded map | [dump.py](tools/coyodex/dump.py:139) |
| C75 | queries | D1 | diffs the pinned commit against the working tree and lists the untracked files as added | [change-impact.md](method/change-impact.md:57) |
| C25 | queries | D1 | asks the version-control program for the paths changed but not committed | [provenance.py](tools/coyodex/provenance.py:159) |
| C43 | calls | D1 | launches git as a separate process to list and read files at the map's commit | [serve.py](tools/coyodex/viewer/serve.py:236) |
| C44 | calls | D1 | runs git for the commit's date, the repository root and the origin remote | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:60) |
| C58 | calls | D10 | loads highlight.js from the content-delivery network and colours the file it shows | [viewer.js](tools/coyodex/viewer/viewer.js:9916) |
| C55 | calls | D8 | asks Mermaid to draw the open view's diagram in the page | [viewer.js](tools/coyodex/viewer/viewer.js:8953) |
| C58 | calls | D16 | opens the shown file at its line in the reader's editor by URL scheme | [viewer.js](tools/coyodex/viewer/viewer.js:10729) |
| C58 | calls | D15 | opens the shown file on GitHub, pinned to the map's commit | [viewer.js](tools/coyodex/viewer/viewer.js:10732) |
| C45 | reads | E1 | reads the whole map document to project it into the browser's graph | [views.py](tools/coyodex/views.py:1030) |
| C45 | reads | E13 | reads each component's source anchor and files to make its code links | [views.py](tools/coyodex/views.py:1122) |
| C17 | reads | E5 | reads every feature to order the story column and count what it holds | [features.py](tools/coyodex/features.py:222) |
| C17 | reads | E6 | reads every use case to join it onto its feature and its actors | [features.py](tools/coyodex/features.py:295) |
| C17 | reads | E9 | reads the happy path to place each feature and each actor in the story | [features.py](tools/coyodex/features.py:230) |
| C43 | calls | C46 | builds the file browser tree from the commit's file list | [serve.py](tools/coyodex/viewer/serve.py:436) |
| C44 | calls | C17 | derives the feature index and the story order for the bundle | [gen_viewer.py](tools/coyodex/viewer/gen_viewer.py:3262) |
| C56 | calls | C58 | opens a box's code link in the source column | [viewer.js](tools/coyodex/viewer/viewer.js:202) |
| C33 | calls | D1 | launches git as a separate process to list the analysable files and to count each file's commits | [preindex_lib.py](tools/coyodex/preindex_lib.py:289) |
| C33 | calls | D4 | builds a parser for each non-Python language it must read symbols and imports from | [preindex_lib.py](tools/coyodex/preindex_lib.py:391) |
| C33 | calls | D3 | parses a source file and walks its syntax tree for definitions and imports | [preindex_lib.py](tools/coyodex/preindex_lib.py:440) |
| C4 | calls | D1 | launches git to read HEAD and its date for the briefing's commit pin | [scope.py](tools/coyodex/scope.py:48) |
| C33 | writes | E37 | records every class and function definition it finds, with its file, kind and line span | [preindex.py](tools/coyodex/preindex.py:148) |
| C33 | writes | E38 | works out how many components each folder of the tree should yield | [preindex_lib.py](tools/coyodex/preindex_lib.py:625) |
| C2 | reads | E1 | reads every row of a fragment's map document to check it | [lint_fragment.py](tools/coyodex/lint_fragment.py:452) |
| C1 | writes | E1 | serializes the whole map document in one fixed key order | [model.py](tools/coyodex/model.py:892) |
| C2 | writes | E39 | records which fragments loaded, which were skipped and which failed | [assemble.py](tools/coyodex/assemble.py:294) |
| C2 | writes | E16 | mints each front door's identifier from the front door's own content | [assemble.py](tools/coyodex/assemble.py:688) |
| C2 | writes | E15 | adds the backbone arrow an entity step implies but no fragment authored | [assemble.py](tools/coyodex/assemble.py:131) |
| C2 | reads | E40 | reads the lead's assignment file before the map is written | [assemble.py](tools/coyodex/assemble.py:916) |
| C25 | writes | E40 | writes the assignment file that the next merge applies | [reconcile_build.py](tools/coyodex/reconcile_build.py:439) |
| C25 | reads | E16 | reads each front door's identifier and code link to witness it in the assignment file | [reconcile_build.py](tools/coyodex/reconcile_build.py:213) |
| C3 | reads | E16 | reads a front door's record, whose identifier exists only in the merged map | [dump.py](tools/coyodex/dump.py:99) |
| C2 | calls | C1 | builds the typed document from a fragment's JSON, re-points merged identifiers, and asks it to serialize the map | [assemble.py](tools/coyodex/assemble.py:155) |
| C2 | calls | C13 | runs the shared row checks over a fragment and over the merged map | [lint_fragment.py](tools/coyodex/lint_fragment.py:125) |
| C2 | calls | C25 | loads, validates and applies the lead's assignment file, and stamps which build produced the map | [assemble.py](tools/coyodex/assemble.py:928) |
| C2 | calls | C3 | matches two authored headings that differ only in case or spacing | [assemble.py](tools/coyodex/assemble.py:440) |
| C2 | calls | C45 | renders the readable markdown view of the merged map | [assemble.py](tools/coyodex/assemble.py:964) |
| C2 | calls | C43 | registers the map's folder so the local viewer can offer this project | [assemble.py](tools/coyodex/assemble.py:968) |
| C25 | calls | C2 | reads and merges the build fragments the path rules resolve against | [reconcile_build.py](tools/coyodex/reconcile_build.py:302) |
| C25 | calls | C1 | strips the line number off a code link, leaving the folder path a rule can match | [reconcile_build.py](tools/coyodex/reconcile_build.py:105) |
| C25 | calls | C4 | matches an element's folder path against a rule's pattern | [reconcile_build.py](tools/coyodex/reconcile_build.py:150) |
| C3 | calls | C2 | loads the named file, accepting a finished map or a half-written build fragment | [dump.py](tools/coyodex/dump.py:292) |
| C3 | calls | C1 | resolves an identifier against the map document and serializes the whole document | [dump.py](tools/coyodex/dump.py:103) |
| C13 | reads | E1 | reads the whole map document to check its references, code links and coverage | [validate_model.py](tools/coyodex/validate_model.py:4359) |
| C13 | calls | C1 | parses the map file into the typed document, and reuses its code-link and word rules | [validate_model.py](tools/coyodex/validate_model.py:4727) |
| C13 | calls | C3 | reads the recorded lines that silence an advisory, and reports the ones that silence nothing | [validate_model.py](tools/coyodex/validate_model.py:3468) |
| C13 | calls | C15 | asks for the per-screen box-count advisories on every validate run | [validate_model.py](tools/coyodex/validate_model.py:4501) |
| C14 | writes | E42 | creates one finding for every contradiction and advisory it raises | [audit_model.py](tools/coyodex/audit_model.py:575) |
| C14 | calls | C1 | parses the map file into the typed document before comparing its two layers | [audit_model.py](tools/coyodex/audit_model.py:1361) |
| C14 | calls | C3 | reads the recorded lines that judge one advisory acceptable | [audit_model.py](tools/coyodex/audit_model.py:782) |
| C14 | calls | C13 | reuses the file-to-component owner table when detailing a business rule's site | [audit_model.py](tools/coyodex/audit_model.py:962) |
| C3 | reads | E36 | reads the recorded lines under every heading a check honours | [records.py](tools/coyodex/records.py:165) |
| C3 | writes | E36 | appends, replaces and removes the recorded lines under a named heading | [record.py](tools/coyodex/record.py:116) |
| C15 | reads | E5 | reads every group and its parent to build the child list of each screen | [balance_lib.py](tools/coyodex/balance_lib.py:107) |
| C15 | reads | E13 | counts the components each screen draws and which group each one sits in | [balance_lib.py](tools/coyodex/balance_lib.py:110) |
| C15 | calls | C1 | parses the map file into the typed document before counting its screens | [balance.py](tools/coyodex/balance.py:271) |
| C4 | calls | C14 | dispatches the audit subcommand and its batch options | [cli.py](tools/coyodex/cli.py:132) |
| C4 | calls | C23 | dispatches the grounding record and drift-check subcommands | [cli.py](tools/coyodex/cli.py:171) |
| C4 | calls | C24 | dispatches the map-repair subcommand and its verbs | [cli.py](tools/coyodex/cli.py:174) |
| C4 | calls | C16 | dispatches the pre-commit gate run | [cli.py](tools/coyodex/cli.py:168) |
| C4 | calls | C25 | dispatches the provenance stamp | [cli.py](tools/coyodex/cli.py:180) |
| C14 | writes | E41 | ranks the map's riskiest claims into work items and cuts them into themed batch files | [audit_model.py](tools/coyodex/audit_model.py:1269) |
| C14 | writes | E15 | writes each skeptic-corrected line onto the relation whose claim names it | [audit_model.py](tools/coyodex/audit_model.py:382) |
| C23 | calls | C14 | re-derives the live claim surface from the auditor's ranked worklist | [grounding.py](tools/coyodex/grounding.py:1062) |
| C23 | writes | E35 | derives the map's grounding record from the pinned worklist and the verdict files | [grounding.py](tools/coyodex/grounding.py:1086) |
| C23 | derives | E43 | recomputes, per element, what the verdicts did to the claims that element makes | [grounding.py](tools/coyodex/grounding.py:1068) |
| C13 | reads | E35 | reads the grounding record and blocks a verdict split that does not add up | [validate_model.py](tools/coyodex/validate_model.py:2549) |
| C24 | calls | C23 | reads the confirmed drift records the verdict comparison produced | [fix.py](tools/coyodex/fix.py:192) |
| C24 | writes | E40 | records corrected anchors and refuted-edge drops as durable reconcile directives | [fix.py](tools/coyodex/fix.py:331) |
| C25 | calls | C14 | reuses the auditor's anchor writer so both repair paths agree on the target | [reconcile.py](tools/coyodex/reconcile.py:526) |
| C25 | removes | E15 | removes the relations a reconcile directive drops from the merged map | [reconcile.py](tools/coyodex/reconcile.py:576) |
| C25 | writes | E11 | re-points or removes the flow steps that rode a dropped relation | [reconcile.py](tools/coyodex/reconcile.py:584) |
| C16 | calls | C13 | runs the validator in-process with its streams captured | [finalize.py](tools/coyodex/finalize.py:108) |
| C16 | calls | C14 | runs the auditor in-process and splits its findings into blocking and advisory | [finalize.py](tools/coyodex/finalize.py:111) |
| C16 | calls | C23 | runs the anchor-drift and surviving-refutation legs against the verdict files | [finalize.py](tools/coyodex/finalize.py:114) |
| C16 | writes | E45 | records one leg per gate, saying whether it ran and what it found | [finalize.py](tools/coyodex/finalize.py:472) |
| C16 | writes | E46 | assembles the verdict, the two counts and the map's hash into the pre-commit report | [finalize.py](tools/coyodex/finalize.py:495) |
| C25 | persists | E47 | writes the session-stamp record beside the map | [provenance.py](tools/coyodex/provenance.py:217) |
| C25 | writes | E48 | builds one entry per build session with its id, minute, mode and pinned commit | [provenance.py](tools/coyodex/provenance.py:199) |
| C25 | calls | D1 | launches git as a separate process for the head commit, its date and whether the tree is dirty | [provenance.py](tools/coyodex/provenance.py:120) |
| C43 | calls | C34 | asks the impact engine which parts of the map a code change reaches | [serve.py](tools/coyodex/viewer/serve.py:420) |
| C34 | queries | D1 | queries git for the changed-file list and for each file diffed against the map pinned commit | [impact_git.py](tools/coyodex/impact_git.py:50) |
| C34 | writes | E49 | builds one anchor reference for every code link the map carries | [impact_lib.py](tools/coyodex/impact_lib.py:196) |
| C34 | writes | E50 | records one hit per anchor, with the precision it reached | [impact_lib.py](tools/coyodex/impact_lib.py:367) |
| C75 | writes | E1 | the accept and direct-change instructions rewrite the map's rows and its commit pin in place | [change-impact.md](method/change-impact.md:123) |
| C25 | writes | E47 | writes this session's entry into the provenance file | [provenance.py](tools/coyodex/provenance.py:217) |
| C24 | calls | C2 | re-merges the edited fragments to check that no row appears or disappears | [fix.py](tools/coyodex/fix.py:1399) |
| C75 | prescribes | C45 | re-renders the readable view from the changed map | [dispatch.md](method/dispatch.md:187) |
| C63 | calls | C1 | parses every map it scores or judges through the shared map reader | [profile.py](eval/tools/coyodex_eval/profile.py:250) |
| C63 | calls | C13 | runs the validator over a map to count its well-formedness problems and warnings | [profile.py](eval/tools/coyodex_eval/profile.py:257) |
| C63 | calls | C14 | runs the auditor and its risk-ranked claim list over every map it scores | [profile.py](eval/tools/coyodex_eval/profile.py:259) |
| C63 | calls | C44 | builds each run's diagram data so an archived run stays viewable after a rebuild | [run.py](eval/tools/coyodex_eval/run.py:136) |
| C63 | calls | C45 | renders the readable view archived beside every run's map | [run.py](eval/tools/coyodex_eval/run.py:163) |
| C63 | persists | E53 | writes each map's counted quality signals to profile.json and reads the accepted map's back | [run.py](eval/tools/coyodex_eval/run.py:166) |
| C63 | persists | E54 | writes the judged pass rate and rubric scores to judge.json and reads a cached one back | [run.py](eval/tools/coyodex_eval/run.py:403) |
| C63 | writes | E55 | builds the pass, drift or regressed verdict and renders it into the run's report | [compare.py](eval/tools/coyodex_eval/compare.py:510) |
| C63 | reads | E41 | reads the auditor's work items to build the claim sample a skeptic is given | [run.py](eval/tools/coyodex_eval/run.py:328) |
| C66 | reads | E47 | reads the recorded build stamp to name the build a review would be about | [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:179) |
| C66 | reads | E48 | takes the newest recorded session's chat id and build minute | [retro_precheck.py](eval/tools/coyodex_eval/retro_precheck.py:180) |
| C66 | persists | E1 | moves the previous map document into a numbered archive folder and keeps it there as the baseline | [archive.py](eval/tools/coyodex_eval/archive.py:107) |
| C25 | reads | E47 | loads the recorded build stamp so the sessions that built this map can be listed | [provenance.py](tools/coyodex/provenance.py:296) |
| C25 | reads | E48 | reads each recorded session's build minute, mode, chat id and code commit for the listing | [provenance.py](tools/coyodex/provenance.py:304) |
| C65 | reads | E1 | loads the built map, so the rules whose subject is the map are scored against it rather than against the chat log | [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:1615) |
| C65 | calls | C64 | reads the build's chat log through the transcript reader, one turn per reply | [process_scorecard.py](eval/tools/coyodex_eval/process_scorecard.py:2941) |
| C64 | reads | E1 | counts the rows of the produced map, the divisor the spend report is stated against | [cost.py](eval/tools/coyodex_eval/cost.py:392) |

---

## Test completeness — gaps against the map

> **Tests run for this table?** The suite was never run for this table. Every row comes from reading the test files, so every row is a reading and not a measurement. Confidence is inferred on all 35 rows.

| Target | Tested? | Test(s) | Gap / risk | Confidence |
|---|---|---|---|---|
| Adding, removing and reordering projects on the map server's landing page (EP64, EP65, EP66) | no | [test_serve.py](tests/test_serve.py:385) — The only test that sends real requests to the server, and only for page assets and one project's view. | No test sends an add, a remove or a reorder request. The header check that blocks other websites is never exercised. A break there lets any page you visit rewrite your project list. | inferred |
| The helper script that stamps a build and moves a map out of a project (EP98, EP99) | no |  | Nothing runs the script. Moving is the default rather than copying. A wrong folder sends the only copy of a map somewhere unexpected. Recovery means hunting for the files by hand. | inferred |
| The recent-projects list and the folder browser on the landing page (EP62, EP63) | no | [test_serve.py](tests/test_serve.py:255) — Checks the folder listing helper marks which folders hold a map, but never through a request. | No test sends either request. The folder browser answers for any directory on the machine, including folders far outside every served project. A widened answer there stays invisible until a person notices. | inferred |
| The landing page, a project's own page and the server's health answer (EP60, EP67, EP68) | no | [test_serve.py](tests/test_serve.py:385) — Sends real requests for the shared page assets and for one project's view, and for nothing else. | No test asks for those three addresses. A break leaves the server running while no page ever loads. Only a person opening a browser would find out. | inferred |
| Opening an element's line in the editor or on the code hosting site (Open an element's source in the editor, Source column) | no |  | Nothing exercises how the link is built or which editor schemes are allowed. A wrong link opens the wrong file, or a scheme the reader never wanted. The reader would trust a line the map does not name. | inferred |
| Starting the map server, popping the browser open, and stopping on the stop key (Start the local map server, EP77, EP78, EP79, EP80) | no | [test_cli_contract.py](tests/test_cli_contract.py:57) — Records the server as the one command no test may call, because starting it takes a port. | The start command is deliberately never called by any test. A bad option or a failed start ships unnoticed. Every reading path begins here, so a break blocks the whole browser page. | inferred |
| Folding a change report back into the map and re-pinning it to the new commit (Fold a change report into the map) | no | [test_method_contract.py](tests/test_method_contract.py:1) — Checks the written instructions still name commands that exist, without ever performing the fold. | No test performs the fold. The step is written instructions an agent follows by hand. A wrong fold quietly loses map rows, or pins the map to the wrong commit. | inferred |
| The three browser libraries that draw the diagrams, pan them and colour the code (Mermaid, svg-pan-zoom, highlight.js) | partial | [test_grouping.py](tests/test_grouping.py:1823) — Checks the served page text asks for the drawing library and hands it the diagram to build. | No test draws a diagram in a real browser. A library upgrade that changes drawing rules passes every check here. The reader meets the broken picture first. | inferred |
| How the browser page behaves when a reader clicks a box, drills in and goes back (Map canvas, Map reading pages, Trail and history, Open a project's map in a browser) | partial | [test_viewer_js.py](tests/test_viewer_js.py:44) — Parses the page's script so a broken edit cannot ship silently. · [test_viewer_js.py](tests/test_viewer_js.py:70) — Reads the script's own text to check well over a hundred screen rules, without running the page. · [test_grouping.py](tests/test_grouping.py:1851) — Checks the served page and its script agree on what each view draws. | Nothing loads the page and clicks it. Almost every check reads the script as text, so a rule can be present and still not work. A reader meets the break before any test does. | inferred |
| The one story column that lists every feature in the order the product runs (Follow the product's story end to end, Feature index) | partial | [test_features.py](tests/test_features.py:1) — Pins which use cases, rules and components each feature reaches, read from the stored map. · [test_viewer_js.py](tests/test_viewer_js.py:3125) — Checks the script text draws the story diagram on the features landing screen. | The join behind the column is well pinned. The drawing itself is only checked as script text. A layout break in the story column fails nothing. | inferred |
| The written method, the worker briefings, and the skill copied into the coding agents (Build method, Worker briefings, Installed skill and project writing, Install the coyodex skill into the coding agents) | partial | [test_method_contract.py](tests/test_method_contract.py:1) — Checks every command the written method names still exists and still takes the options named. · [test_method_rationale.py](tests/test_method_rationale.py:1) — Checks the reason for each rule stays attached to the rule. · [test_skill_pointers.py](tests/test_skill_pointers.py:1) — Checks the installed copies do not point at files that were renamed or deleted. · [test_retro_checks.py](tests/test_retro_checks.py:1) — Checks a promised outcome and the review that reads it still point at each other. | The install step itself never runs in a test. Only the words inside the files are checked. A broken install leaves a coding agent that cannot answer to the product at all. | inferred |
| Judges reading both maps and returning grounding and rubric verdicts (Have judges read both maps) | partial | [test_judge.py](eval/tests/test_judge.py:1) — Feeds a scripted stand-in judge, so gathering the verdicts and taking the middle score are pinned. | No real reader is ever asked to judge. A change to what the judges are asked, or to how their answers are read, is invisible here. A judge that quietly reads worse makes every later comparison wrong. | inferred |
| The harness that plants false claims to measure how many the skeptics catch (Measure how many planted falsehoods the skeptics catch) | partial | [test_mutate.py](eval/tests/test_mutate.py:1) — Eight checks over the planting step and the answer key it writes. | Eight checks cover a harness whose own correctness decides a published score. A planted claim that turns out to be true makes a correct skeptic look wrong. The resulting number would still be believed. | inferred |
| Changing the map by asking for a split, a rename, a move or a deeper drill (Change the map by asking in plain words) | partial | [test_method_contract.py](tests/test_method_contract.py:1) — Checks the written instructions for the edit still name real commands. · [test_finalize.py](tests/test_finalize.py:1) — Pins the gate run the edited map has to pass afterwards. | The edit is agent work, so no test performs one. Only the gates that follow are covered. An edit that drops rows passes whenever the gates do not look for those rows. | inferred |
| Finding names in files written in languages other than Python (tree-sitter, tree-sitter-language-pack) | partial | [test_preindex.py](tests/test_preindex.py:1) — Runs the sizing pass; the checks for other languages only run when the grammar pack is installed. · [test_granularity.py](tests/test_granularity.py:1) — Pins the leaf rule that decides how coarse the map may be. | The checks for other languages skip themselves when the grammar pack is missing. A machine without the pack reports a green suite that proved less. A grammar upgrade that changes what counts as a name would not fail here. | inferred |
| Picking up a map edited while the server runs, and warning when the tool's own code changed (Map server, EP58, EP59) | partial | [test_serve_fresh.py](tests/test_serve_fresh.py:46) — An edited map is served on the next request instead of the cached one. · [test_serve_fresh.py](tests/test_serve_fresh.py:71) — A broken edit keeps the last good drawings and retries later. | The map freshness check is well pinned. The warning about the tool's own code changing has no test. A stale server would keep serving old drawings with no notice to the reader. | inferred |
| The gate that checks a finished map is well formed before anyone trusts it (Check the map is well formed, Map validator) | yes | [test_validate_model.py](tests/test_validate_model.py:1) — Around three hundred checks over unresolved references, missing code links and softer advice. · [test_cli_sweep.py](tests/test_cli_sweep.py:218) — Drives the gate through the real command against a committed map. | Nothing proves the list of checks is complete. A map defect nobody has thought of still passes. The list grows only after a defect is found in a real build. | inferred |
| The gate that makes the map's two layers refute each other (Make the map's two layers refute each other, Map auditor) | yes | [test_audit.py](tests/test_audit.py:1) — Scenario maps written in the same format the gate reads, so the live path is exercised. · [test_trapdoor_tools.py](tests/test_trapdoor_tools.py:1) — Runs the gate against a small planted project and its expected map. | The scenarios are hand written, so a contradiction nobody imagined goes unjudged. A real map is far larger than any scenario here. | inferred |
| Merging the workers' fragments into one map (Merge the workers' fragments into one map, Fragment merge, FragmentLoad) | yes | [test_assemble.py](tests/test_assemble.py:1) — Sixty-six checks over clashing ids, dropped rows and the order rows come out in. · [test_assembly_fixture.py](tests/test_assembly_fixture.py:1) — Merges a committed set of real fragments end to end and compares against the expected map. · [test_fragment_io.py](tests/test_fragment_io.py:1) — Reading and writing one fragment on its own, before the merge. | Cover is strong for dropped rows and clashing ids, which is the risk that matters. The end to end corpus is one committed project, so an unusual fragment shape stays untried. | inferred |
| Handing a worker its brief, and the worker's own check before it hands work back (Hand a fan-out worker its contract, Self-check one harvested fragment) | yes | [test_contract.py](tests/test_contract.py:1) — Pins that each worker gets its own half of the brief, not the whole file. · [test_lint_fragment.py](tests/test_lint_fragment.py:1) — Forty-three checks over the per-fragment self-check, including invented ids. | The brief and the self-check are pinned as text and as exit codes. Nothing proves a worker actually reads the brief it is handed. | inferred |
| The record of what the skeptics proved, and the counts the gate reads (Record what the skeptics proved, Grounding record, ElementCheck, SurvivingRefutation) | yes | [test_grounding.py](tests/test_grounding.py:1) — Fifty checks that the four counts are worked out from the verdicts, never typed by hand. · [test_element_checks.py](tests/test_element_checks.py:1) — Shows, per element, what was proved beside what the author claimed. · [test_cli_sweep.py](tests/test_cli_sweep.py:190) — Drives every grounding verb through the real command against a realistic map. | The counts are worked out rather than typed, and the working is pinned. Nothing checks that the verdict files a real skeptic writes are honest in the first place. | inferred |
| Correcting a code link, dropping a refuted claim, and writing down an accepted advisory (Correct a code link that points at the wrong line, Drop a claim the code refutes, Record an advisory the reader accepts, Map repairs) | yes | [test_fix.py](tests/test_fix.py:1) — Over a hundred checks across the repair verbs that edit a map in place. · [test_records.py](tests/test_records.py:1) — One reader for accepted advisories, after four separate readers each silenced more than named. · [test_anchor_drift.py](tests/test_anchor_drift.py:1) — Lists every code link that has slid off the line it should point at. · [test_operative_lines.py](tests/test_operative_lines.py:1) — Checks a code link points at a line that could really be doing the work. | Silencing more than was named is directly tested, which is the risk that matters most here. A repair still rewrites a committed map in place with no way back. | inferred |
| The pre-commit run that puts a map through every gate at once (Run the pre-commit read, Pre-commit gate run) | yes | [test_finalize.py](tests/test_finalize.py:1) — Forty-six checks, and they state plainly that the run is a convenience, not an enforcement point. · [test_access_surface.py](tests/test_access_surface.py:1) — Catches a security claim that vanished between two maps of unchanged code. | Nothing forces a build to make the run at all. A map can reach a commit with no gate ever having read it. The tests say so rather than fixing it. | inferred |
| Reporting what a code change did to the map (Report what a code change did to the map, Change impact, AnchorRef, DirectHit) | yes | [test_impact.py](tests/test_impact.py:1) — Named code changes replayed in real temporary projects, not imitations. · [test_impact_ripple.py](tests/test_impact_ripple.py:1) — Pins how far a change spreads through the map's own relations. · [test_impact_serve.py](tests/test_impact_serve.py:1) — Pins the reading guards, so a file outside the served project is refused. | Real temporary projects back the checks, which is the right shape. The code changes replayed are a fixed set, so an unusual change stays unmeasured. | inferred |
| Seeing what an edit changed in the map, row by row (See what an edit changed, row by row) | yes | [test_mapdiff.py](tests/test_mapdiff.py:1) — Twenty-five checks, written after a count-only report cost an hour of hand reading. | The row by row comparison is pinned on small hand built maps. A very large map's report has never been checked for readability or for speed. | inferred |
| The briefing, the ignore list, and the sizing pass that runs before any map is built (Brief the reader on what will be analysed, Declare code the map should not describe, Size the code tree before choosing altitude, Pre-index, Symbol, DirExpectation) | yes | [test_scope.py](tests/test_scope.py:1) — Checks the briefing says which files will be read and what the commit pin means. · [test_ignorefile.py](tests/test_ignorefile.py:1) — Twenty-six checks over the file that declares code the map should not describe. · [test_preindex.py](tests/test_preindex.py:1) — Thirty checks over the sizing pass and the summary a coding agent reads back. · [test_source_walk_git.py](tests/test_source_walk_git.py:1) — Pins which files the walk enumerates, since a missed file is invisible to everything after. | The file walk is pinned to what the project tracks, which decides everything downstream. A file the walk misses stays invisible to every later check, including the coverage ones. | inferred |
| Turning path rules into an explicit list of assignments (Turn path rules into explicit assignments, Assignment pass, Reconcile) | yes | [test_reconcile_build.py](tests/test_reconcile_build.py:1) — Fifty-two checks, written after a build reported no components while assigning four hundred. | The failure that prompted the command, a rule matching nothing, is pinned. Very large assignment files are covered by one committed example only. | inferred |
| The map document itself, and looking up one part of it (Look up one part of the map, Map document, Map lookups, ProjectModel) | yes | [test_model.py](tests/test_model.py:1) — Saving and loading a map gives back exactly what went in, in a fixed order. · [test_dump.py](tests/test_dump.py:1) — Twenty-seven checks over the fixed slices a reader can ask for. · [test_json_schema.py](tests/test_json_schema.py:1) — Checks the published description of the map file still matches the map. · [test_retired_parser.py](tests/test_retired_parser.py:1) — Guards that the deleted text format stays deleted everywhere. | Saving and loading round trips exactly, and the old text format stays gone. A map written by a much older release is tolerated only on the scoring side, never here. | inferred |
| Reading the code under a box, at the commit the map names (Read the code under a box, EP72) | yes | [test_serve.py](tests/test_serve.py:101) — Refuses absolute paths, paths that climb out, backslashes and hidden characters. · [test_impact_serve.py](tests/test_impact_serve.py:61) — Refuses ignored files, project internals, and a link that points outside the project. · [test_serve.py](tests/test_serve.py:113) — Reads real files out of a real project at a named commit. | Reading outside the served project is refused several ways, which is the risk that matters. Nothing checks the coloured code the reader actually sees on screen. | inferred |
| Scoring a rebuilt map against the accepted one, and accepting a run as the new baseline (Score a rebuilt map against the accepted one, Accept a run as the new baseline, Map quality score and verdict, MapProfile, DeltaReport) | yes | [test_profile.py](eval/tests/test_profile.py:1) — Thirty-four checks over the score, the reusable heart of the whole comparison. · [test_compare.py](eval/tests/test_compare.py:1) — Sixty-eight checks over the bands that decide the pass, drift and blocking verdicts. · [test_run.py](eval/tests/test_run.py:1) — The whole run end to end, with a scripted stand-in judge. · [test_legacy_map.py](eval/tests/test_legacy_map.py:1) — Reads a map an older release wrote, so a comparison against an archive can still run. | Scoring and the three verdicts are heavily pinned. The thresholds themselves are a judgement call no test can defend. A threshold set too loose passes a map that got worse. | inferred |
| Reading a build transcript, scoring the build's behaviour, and reporting what it spent (Read a build transcript in slices, Score a build's behaviour against the method, Measure what a build spent, Build transcript reader and spend report, Build behaviour scorecard) | yes | [test_transcript.py](eval/tests/test_transcript.py:1) — Thirty checks over reading a build transcript in slices. · [test_process_scorecard.py](eval/tests/test_process_scorecard.py:1) — Over two hundred checks over the ten behaviour assertions, on made-up turn sequences. · [test_cost.py](eval/tests/test_cost.py:1) — Twenty-four checks over what a build spent. · [test_process_corpus.py](eval/tests/test_process_corpus.py:1) — Runs the scorecard against eight real build transcripts, but only when switched on. | The run against eight real transcripts is opt in, so an ordinary run skips it. Only made-up turn sequences are checked by default, and a real build looks nothing like them. | inferred |
| Refusing to review an unfinished build, and archiving a map for a fresh rebuild (Refuse to review a build that has not finished, Archive a map so the next run builds from scratch, Map archive and build guard) | yes | [test_archive.py](eval/tests/test_archive.py:1) — Eighteen checks aimed at not losing the map while moving it aside. · [test_retro_precheck.py](eval/tests/test_retro_precheck.py:1) — Pins the guard that spots a build still running, since the stamp is written near the end. | Not losing the map during an archive is directly tested. Recovering from an archive that stopped halfway is not covered anywhere. | inferred |
| Building the diagrams, the graph behind them, and the file browser tree (Diagram builder, Graph builder, File browser tree) | yes | [test_grouping.py](tests/test_grouping.py:1) — Over a hundred checks across the graph, the views and the diagram text. · [test_convert_and_views.py](tests/test_convert_and_views.py:1) — A committed real world map is the golden case every view is measured against. · [test_gen_deployment.py](tests/test_gen_deployment.py:1) — Fifty-four checks over the deployment drawing alone. · [test_data_view.py](tests/test_data_view.py:1) — Pins how stores group, who writes them and who reads them. · [test_filetree.py](tests/test_filetree.py:1) — Pins the file tree and the overlay showing which files the map covers. | A committed real world map as the golden case catches drift well. What is checked is diagram text, never a drawn picture. A diagram that describes correctly and draws badly passes. | inferred |
| Re-balancing the diagrams so no box has too many or too few children (Re-balance the diagrams against the traced graph, Diagram balance report) | yes | [test_balance.py](tests/test_balance.py:1) — Forty-six checks over the fan-out bands, the exemptions and the escape hatch. | The bands and the escape hatch are pinned. Whether those bands match what a reader finds readable is never measured. Only a person can say a diagram is too busy. | inferred |
| Stamping which conversation built the map (Stamp which conversation built the map, Provenance, SessionEntry) | yes | [test_provenance.py](tests/test_provenance.py:1) — Thirteen checks, written after the stamp existed only in a script the product does not install. | Writing and reading the stamp are covered by the shipped command. The older helper script that also writes the same stamp has no test at all. | inferred |

---

## Entry-point coverage

cli: complete — every subcommand and verb in both command dispatch tables, checked against each implementing module
http-route: complete — walked both request handlers end to end, through every branch of the path dispatch
ui-route: complete — every view button in the page's view tab row, plus the route the page lands on at boot
agent-skill: complete — every skill pointer file in the repo, and every mode branch of the dispatch document
startup-hook: complete — swept the server and the page for every boot-time side effect
poller: complete — the two timed checks the server makes; no other interval exists anywhere
event-consumer: sampled — the two page listeners that act with no reader action; every other listener needs a click or a key
server-loop: complete — the one accept loop the server runs
worker-thread: complete — the one thread the server starts per request
signal-handler: complete — the one interrupt path that closes the listening port

---

## Bucket vocabulary

Code parsing: the tree sizing needs a source parser, and no library seed names parsing
Testing & type checking: the test runner and the type checker are neither a framework nor a driver, and no seed names them
Build & packaging: the build backend is neither a framework nor a driver, and no seed names packaging
Coding agents: the skill installs into three AI agents, which share one real purpose no seed names
Code viewing: the browser, the hosting site and the editor share one purpose, which is showing the reader a file

---

## Map maintenance records — the build's own adjudication log

These sections answer this tool's own checks: each line records an element and why a finding about it was judged correct as it stands. They say nothing about the system being mapped.

### Balance exceptions

store: coyodex writes plain files and depends on no datastore, so no entity can name one; each container is a file name
granularity: 31 components against a code-derived 19, because five of them are the written method and its two developer recipes, which are markdown and outside the count entirely; the remaining 26 follow real module seams
SF11, SF31: the lead prescribed both names in the shared sub-flow catalogue before running them past the naming check, and eight agents then referenced them; renaming mid-fan-out would have broken the contract, so the names stand and the mistake is recorded rather than tidied away
security-granularity: family — one rule per surface family, so a decision enforced at several endpoints is one rule with several sites; the loopback rule alone carries four sites across the bind, the host refusal and the write-path marker

### Sweep debt

eval/tools/coyodex_eval/process_scorecard.py:3160: prints each rule's before and after value and which way it moved; reporting a comparison is not a decision the product makes

### Audit exceptions

read-before-create HP2: the briefing does not read an entry point; the command shell owns both the briefing and the whole command surface, so another flow's entry-point read leaks onto this step through one shared box
read-before-create HP5: a worker's self-check does read a testing record, because a testing record is an ordinary fragment; the record it reads belongs to an earlier build, not to the one the walk is describing
read-never-created HP17: a use case is written into the map by the fan-out workers at HP5, inside their own fragments, which the walk narrates as writing the whole map rather than each element type
read-never-created HP6: a component is written by the fan-out workers at HP5, inside their own fragments; the walk names the whole map at that step, never each element type it contains
read-never-created HP8: a group is assigned at HP7, which the walk narrates as writing the assignment file rather than as writing each group it names
why-less-step HP15: starting the map server is a second way into the story and needs nothing earlier; a reader may start it before any map exists and see an empty landing page


---

*Generated with coyodex from `project-map.json` — the committed source of truth. Do not edit this file; regenerate it with `coyodex render`.*
