# Trace contract (Phase 3) — the copyable template

**Copy this file; do not compose it from prose.** This template exists because the trace fan-out was
the largest one in a build with no contract of its own — fourteen agents on one build, each prompt
hand-composed from nine separate rules in `method.md`. The rules fan-out was in exactly that state
until it cost eleven repaired fragments and a blocking lint failure in 13 of 71 agent transcripts,
from one wrong sentence the lead wrote from memory. `method.md` states the general form of this
mistake in its own words: shared state belongs in the contract every agent reads, never in a
per-slice option, because a per-slice option gets omitted from one slice — and it records a build
that passed a shared block to 12 of 14 slices, missed two, and shipped one of the omissions.

Fill the «angle-bracket» slots. There are exactly SEVEN — «COYODEX_HOME», «REPO», «AGENT_ID»,
«USE_CASES», «SF_RANGE», «LEGEND», «WHERE_TO_LOOK» — each spelled the same way everywhere.

- **«USE_CASES»** — the `UCn` ids this agent owns, with each one's name and `Trigger → Outcome`
  copied from the map. Always whole use cases: **never split one use case's flow across two agents**,
  because a flow traced by two contexts loses its coherence.
- **«SF_RANGE»** — this agent's sub-flow id range (`SF1–9`, `SF10–19`, …), exactly like the harvest
  id ranges. Two agents minting `SF7` is a hard `assemble` failure.
- **«LEGEND»** — the PATH to the id legend file (the assembled map, or a legend the lead wrote).
  Never the legend's contents inline: a whole-map legend overflows the shell argument limit.
- **«WHERE_TO_LOOK»** — the entry points, components and files this agent's use cases run through,
  and any sub-flow the lead wants extracted (see the sub-flow note below).

**Run every sub-flow name you PRESCRIBE past the naming heuristic first.** A brief that hands agents
`SF20 — Validate and store the token` freezes a fused-goal name into a shared id contract: the agents
hit the lint warning, correctly refuse to rename because renaming breaks the contract, and the same
warnings resurface at your own `validate` to be written up as exceptions. Name a sub-flow the way you
would name a use case — one goal, no "and".

**The template starts at the quoted block below.** Everything above it is instructions to you, the
lead; nothing above this line goes into an agent prompt.

> You are tracing use cases for a coyodex codebase map — the ordered interactions inside each one.
>
> **Your use cases:** «USE_CASES».
> **Where to look:** «WHERE_TO_LOOK».
> **Your sub-flow id range:** «SF_RANGE». Never mint an `SFn` outside it.
>
> Read the code these use cases run through, then produce ONLY the rows below. The one file you may
> write is your own fragment. **Do this work yourself — do NOT spawn sub-agents, and do NOT write a
> program that writes your fragment.** A sub-agent's output is silently dropped, and an agent that
> delegates returns prose instead of a fragment, which means the whole slice is re-run.
>
> ## What you return
>
> **ONE JSON fragment** at `«REPO»/.coyodex/build-fragments/«AGENT_ID».json`, holding only:
>
> ```json
> { "flows":    [ {"uc": "UC7", "title": "<the use case's name>",
>                  "steps": [ {"n": 1, "src": "R1", "dst": "C5",
>                              "phrase": "POSTs the new upstream",
>                              "where": "frontend/src/pages/Upstreams.tsx:212"} ]} ],
>   "subflows": [ {"id": "SF12", "name": "<one goal, no \"and\">", "steps": [ … ]} ],
>   "edges":    [ {"src": "C5", "verb": "persists", "dst": "E2",
>                  "why": "writes the membership document",
>                  "where": "backend/repo.py:155"} ] }
> ```
>
> Return that PATH plus a one-line inventory (flows, sub-flows, steps, edges). **Never inline the
> fragment in your reply** — a large one is silently truncated by the result cap, and a truncated
> fragment fails `assemble`.
>
> A flow's display text is **`title`**; a sub-flow's is **`name`**. They are not the same key.
>
> ## Steps
>
> - **Every step carries a `phrase`** — what happens at that point, present tense, an ACTION
>   ("returns the verified email"). A condition or qualifier belongs in `note`, never in `phrase`.
> - **Every element↔element step carries its own `where`** — the `path:line` in the `src` side's code
>   where THIS step's action fires. Not the callee's definition. A step with genuinely no single site
>   sets `"no_call_site": true` instead; silence is not an option.
> - **Anchor the operative statement** — the call / write / enforce line itself, never the enclosing
>   `def` or class header. That header is the most common drift the adversarial pass finds.
> - **`n` is unique within a flow.** It identifies the step for navigation and for diff impact.
> - **Actor steps** use the role id as `src` (`R1 → C5`). An actor step needs no `where`, though one
>   is welcome when the handler line is clear.
> - **Steps may go BACKWARD.** Record the return-direction interactions that carry meaning: the
>   response the actor sees (the use case's outcome), an error or fallback path, a callback the callee
>   fires back. Write them like any step — `C5 → C2 : returns the member list`. Do not echo every
>   call with a return; only the ones that say something.
> - **3–15 steps per flow.** Over 15 usually means a fused goal, protocol round-trips narrated at
>   wire grain, or shared machinery that should be a sub-flow. Under 3: check the flow reaches its
>   outcome.
>
> ## Entity steps — 1 to 2 per flow, required
>
> The entities whose read or write IS this scenario's outcome or decision appear as their own steps:
>
> ```
> {"n": 6, "src": "C5", "dst": "E2", "phrase": "upserts the Membership document",
>  "where": "backend/repo.py:155"}
> ```
>
> `En` is a valid step endpoint. A flow that narrates only components leaves the whole domain model
> untraceable — the "used in which use case" view and line-level diff impact both derive from STEPS,
> not from edges — and every gate still passes, so nothing will tell you. *Central* means the join
> flow's membership upsert or the tool-call flow's settings decision, NOT every config read along the
> way. Each entity step also needs its `C→E` edge in `edges`, with the real verb (`reads` /
> `writes` / `persists`).
>
> ## Sub-flows
>
> When the same step sequence rides two or more of your flows, extract it once into `subflows` and
> reference it from each flow with a step whose `subflow` names it:
>
> ```
> {"n": 4, "src": "C1", "dst": "C2", "subflow": "SF12"}
> ```
>
> A reference step carries NO `where` of its own and counts as ONE step against the band. One level
> only — a sub-flow's step may not reference another sub-flow. **A step may reference a SIBLING
> agent's sub-flow**: pass `--ids «REPO»/.coyodex/build-fragments/` to your self-check (a directory
> scans every fragment) so the reference resolves at lint time instead of forcing you to duplicate
> the shared trace inline. The refcount nudge ("referenced once — consider inlining") is advisory on
> the fragment channel, because the other reference may live in a sibling's fragment.
>
> ## Edges
>
> - **`C→D` edges name the ROLE with a role-revealing verb**, never a bare `uses`: `publishes` /
>   `emits` for a bus, `reads` / `writes` / `persists` / `queries` for a store, `calls` for a service.
> - **`why` is a short phrase: what `src` does to `dst`** — an action, and a summary of the WHOLE
>   relationship, never one call's story. "writes org, membership and settings documents", not "the
>   page needs the client to POST".
> - **`where` is one representative call site in `src`'s code.** Do not emit the same
>   `(src, verb, dst)` twice with different anchors.
> - **A `reads` edge — or an entity step — requires the entity TYPE at the site.** A function
>   operating on a string or a field extracted from an entity is NOT reading that entity. This is the
>   false-read the grounding pass keeps refuting.
> - **Never author an edge whose endpoint is an actor** (`Rn`). A person or service driving the system
>   is a flow STEP, not an edge.
>
> ## The three overclaim shapes the skeptics keep refuting
>
> Between them these account for most refutations, so avoid them here rather than paying for them
> later. In all three the rule is the same: **attribute the edge to the component whose own code
> contains the operative line**, and if the line you found is a call into another component, the edge
> belongs to that one.
>
> 1. **Transitive attribution** — a component that calls a first-party wrapper credited with the
>    external call the *wrapper's owner* makes.
> 2. **Ownership overclaim** — a controller that calls `.save()` credited as the system of record when
>    the real upsert lives in the repository.
> 3. **Constructs ≠ persists** — a client factory recorded as writing to the stores it only builds
>    clients for.
>
> ## A named channel is a catalog row
>
> When a step or edge passes through a named queue, topic or channel, record the `messaging` row
> alongside the `C→broker` edge: the channel name, the broker dep, its publishers and consumers, the
> payload entity, and the `source` line that DECLARES the channel name — not a line that merely uses
> it. **Only record a channel row if this brief says you own it.** Several agents each recording the
> same channel is how one build produced three spellings of one field and two of another, and
> `assemble` hard-failed twice: every one of those fragments linted clean on its own, because a
> cross-fragment conflict is invisible per fragment by construction.
>
> ## Before you return
>
> ```
> «COYODEX_HOME»/.venv/bin/coyodex lint-fragment --repo «REPO» --ids «LEGEND» «your-fragment».json
> ```
>
> Fix every row it reports until it exits clean — this catches schema, anchor-format, extra-key and
> invented-id errors in YOUR context, in parallel, so nothing bounces back from the lead. `--ids`
> makes a plausible-but-invented element id die in your own turn. If the lint prints `warning:` lines,
> either FIX them or **repeat them verbatim in your reply with one line of justification each**; never
> shrug an advisory off silently.
>
> **Fields you must NOT author** — the lead assigns these after the fan-out, and a fragment carrying
> one is either rejected or silently wrong: `capability`, `entry_points` on a use case, `subsystem`,
> `subdomain`, `bucket`, `block`, and an `id` on an entry point.
>
> **Write a draft as you go.** Write incremental progress to `«AGENT_ID».draft.json` and RENAME it to
> `«AGENT_ID».json` only when complete — an agent that dies mid-run otherwise loses all its reading.
> `assemble` skips any path ending `.draft.json`, so a fragment left with that name never assembles at
> all: the RENAME is what makes your work land.
>
> **Name every scratch file after your agent id.** Every agent in this fan-out shares one scratchpad
> directory and nothing namespaces it. On one build ten agents wrote to the same script name and one
> of them ran a script that was not its own, writing another agent's output file.
>
> **Quote your shell separators.** The Bash tool runs zsh, where a bare `=word` is EQUALS expansion:
> `echo ====` aborts the command line THERE, so every read after it on that line silently does not
> happen and you are left believing you made it. Write `echo "===="`. Measured on one build: 61
> truncated command lines across 18 of 71 agents.
