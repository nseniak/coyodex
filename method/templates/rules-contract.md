# Business-rule contract (Phase 3 / T7) — the copyable template

**Copy this file; do not compose it from prose.** This template exists because one build had to:
`method/templates/` shipped a harvest contract and a skeptic contract and nothing for the rules
fan-out, so the lead wrote one from memory — and told all eleven rule agents to put a `block` field
on every rule. `lint_fragment` makes that a BLOCKING problem (`method.md` and `method/model.md` both
say `block` is assigned by the lead through `coyodex reconcile`, never in a fragment), so the lint
failure fired in **13 of that build's 71 agent transcripts** and every one of the eleven fragments
had to be repaired. One wrong sentence, eleven agents, thirteen failures.

Fill the «angle-bracket» slots. There are exactly SIX — «COYODEX_HOME», «REPO», «MAP», «PROJECT»,
«BLOCK», «AGENT_ID» — each spelled the same way everywhere.

- **«BLOCK»** is this agent's one block id and its BR id range, taken from the lead's block plan.
- **«PROJECT»** is two or three sentences on what the product is, in product language.

Everything below the line is what the agent reads.

---

You are writing the **business-logic layer** of a coyodex map of `«REPO»` — «PROJECT».

Every other layer of this map already exists: what the product stores, what it does in what order,
and how it is built. **None of them says what the product DECIDES.** That is your layer, and it is
the part a reader means by "what is special about this application".

```
CX=«COYODEX_HOME»/.venv/bin/coyodex
MAP=«MAP»
$CX dump --map $MAP --legend           # every id with its name and source
$CX dump --map $MAP --members S3       # the components inside a subsystem
$CX dump --map $MAP --record C50       # one element's full stored record (files, purpose, evidence)
$CX dump --map $MAP --edges C50        # a component's incoming and outgoing backbone edges
$CX dump --map $MAP --id UC31          # a use case: its flow steps and their anchors
```

**Do this work yourself — do NOT spawn sub-agents and do NOT write a program that writes your
fragment.** Author the rows.

## What a rule is

**ONE decision, in product language, naming no component.** Good: *"only the organization's own
admins may mint a service token"*, *"a stored default argument overrides whatever the caller
passed"*, *"an unknown role grants no tools rather than defaulting to open"*. Each carries a short
`name` — the title a reader scans ("Owner-only cancellation") — beside the full `statement`.

**The sharp test: could a product person have decided otherwise?** *"Own connection first, else
oldest shared"* passes. *"If the list is empty, return early"* does not — that is a mechanical
detail, and filling this layer with them is how the decision view stops being worth opening.

**Nothing unsupported.** A rule must be reconstructible from the lines its `sites` point at, with no
clause added. The failure shape is a sentence that reads true sitting under a real anchor that shows
only half of it. If the second half is real, anchor it too; if you cannot find it, cut the clause.

**One rule = one decision.** Several `sites` only when it is the SAME claim enforced in several
places. Two claims joined by "and" are two rules.

**Fusion is preferred to splitting.** A block whose rules are nearly all single-site is the signature
of a flow-step list wearing rule clothing — fuse it. Aim for roughly **5 rules** in your block (3 at
the low end, 8 at the high end). A drift toward one rule per anchor is a FAILURE even when every rule
is verified, because the reader is back to reading the flows.

## The shape you write

```json
{ "rules": [
    { "id": "BR1",
      "name": "<the SHORT title — a few words a reader scans, naming the DECISION>",
      "statement": "<ONE decision, product language, naming no component>",
      "access": true,
      "risk": "<what is AT STAKE if this decision is wrong or absent>",
      "confidence": "verified",
      "sites": [ { "where": "backend/services/policy.py:311",
                   "why": "<what this line does FOR the rule>" } ] } ] }
```

Those seven keys are the whole authored surface. Notes on each:

- **`id`** — from YOUR range only (given above). Two agents minting the same `BRn` is a hard
  assemble failure.
- **`name`** is a TITLE, not the statement cut short. Required.
- **`access`** is `true` when the rule governs **who may do what**. This matters beyond display: it
  is what puts the rule on the product's auth surface and into the Security & auth view.
- **`risk`** is **REQUIRED on an `access` rule** and the lint FAILS without it. It is the one thing a
  statement, a site and a `why` between them cannot say: not what the line does, but what its LIMIT
  costs.
- **`confidence`** is `verified` (you read it in the code) or `inferred` (you deduced it).
- **`sites[].where`** is the **OPERATIVE line** — the `if` / `raise` / `require_*` / decorator call
  that ENFORCES the decision. **Never a docstring, a comment, a `def` header, an import or a blank
  line** (`validate` flags each of those), and never a whole file without a `:line`.
  A decision enforced **by construction** — a type, a schema constraint, a config-wired guard — sets
  `"no_call_site": true` and omits `where`. That is a declared absence, not a gap. Do not invent an
  anchor.

**Do NOT write a `block` field.** Your block id is «BLOCK» and it is how the LEAD will group your
rules, through `coyodex reconcile`, after this fan-out. A `block` key inside a fragment is a
blocking `lint-fragment` failure, not a warning. Say your block id in your REPLY instead — the lead
needs it there, and that is the only place it belongs.

## How to sweep for a rule's sites

**Start from the code your BLOCK is about, not from the rule** — a rule's components are derived FROM
its sites, so "look in the rule's components" is a circle. Take the components your block file names,
then read the anchors **the map already holds** in them: the flow-step `where`s, the edge `where`s.
That is typically a dozen strong candidates per rule, already verified to exist. Read fresh code only
where none of them fit.

**Anchor the TRUE operative line even when a different line would light up a use-case step.** The
step link is a readout, never a target. A site chosen because it makes a flow-step row light up is a
false claim about where the decision is made, and it is invisible on screen — the row looks better,
which is the whole danger.

## What is DERIVED — do not write it, in a field or in prose

Which components enforce a rule, which use-case steps it lands on, which entities it touches, and
whether the sweep finished are all COMPUTED from your `sites`. There is no field for any of them and
none may be added. Do not describe them in prose either: the views compute them, and a prose copy is
a second answer that will disagree.

## Working hygiene

**Name every scratch file after your agent id.** All the agents in this fan-out share one scratchpad
directory and nothing namespaces it. A helper called `notes.py` WILL be overwritten by a sibling
mid-run — it has happened, and one agent's script then wrote another agent's output file. Call yours
`«AGENT_ID»-<what>.py` and use absolute paths.

**Quote your shell separators.** The Bash tool runs zsh, where a bare `=word` is EQUALS expansion:
`echo ====` aborts the command line THERE, so everything after it silently does not run and you are
left with a partial read you believe is complete. Write `echo "===="`. Measured on one build: 61
truncated command lines across 18 of 71 agents.

## Self-check before returning (required)

```
$CX lint-fragment --repo «REPO» --ids $MAP \
   «REPO»/.coyodex/build-fragments/«AGENT_ID».json
```

Fix every problem until it exits clean. If it prints `warning:` lines, either fix them or repeat them
verbatim in your reply with one line of justification each.

Return only: the fragment path, your block id «BLOCK», the rule count, each rule's `name` on one
line, and anything you looked for and could NOT find a decision behind (that absence is itself worth
knowing). **Never inline the fragment in your reply.**
