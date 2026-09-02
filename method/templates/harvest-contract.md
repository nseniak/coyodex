# Harvest contract (Phase 1) — the copyable template

**Copy this file; do not retype it from prose.** Taken literally that was impossible — the body
below is a `>`-quoted skeleton full of «angle-bracket» slots, so it cannot be handed to an agent
as-is, and every build "copied" it by rewriting it. So the instruction is mechanical:

1. Take the quoted block below and strip the leading `> ` from every line.
2. Fill ONLY the «angle-bracket» slots — per agent, that is the file list, the background blurb,
   the **use cases the slice serves**, the component budget and the agent id; per build, the repo
   path and `COYODEX_HOME`.
3. Change nothing else. If a rule reads wrong for this repo, fix it HERE, once, so the next build
   inherits the fix instead of re-deriving it.

**Two slots need a word about what goes IN them**, since the agent half no longer explains itself:

- **«SERVES»** — the UC / CAP / HP / R ids whose behavior runs through these files, one line each
  on what they need from this slice.
- **«EXPECTED_COMPONENTS»** — the slice's E from the pre-index `granularity.per_dir`.

**The slot that keeps being left empty is «SERVES».** Structural slices exist to serve the
behavioral layer. The behavioral draft exists before this fan-out precisely so the slices can be cut
to it; a brief that names no use case is a brief cut from the file tree, and the harvest then comes
back with components carrying no backbone edge at all. Assertion 31 counts this.

Give every harvest agent the same skeleton — only the file list and the background blurb change per
agent. Reusing one contract is what makes each agent return the same row shapes with the same
verified/inferred discipline, which keeps the barrier synthesis clean.

**The template starts at the quoted block below.** Everything above it is instructions to you, the
lead; nothing above this line goes into an agent prompt.

> You are harvesting «SLICE_KIND» facts for a coyodex codebase map.
>
> **NEVER `cd` into the coyodex clone.** Address both repos by ABSOLUTE path, always. A `cd`
> persists for the rest of your session, so a later relative `.coyodex/...` path silently reads
> the TOOL's own map instead of this project's — a wrong answer that looks like a right one. On the
> 2026-09-02 build 8 of 75 agents did this 33 times, because the rule lived only in the lead's guide
> and no agent had read it.
>
> **This slice serves: «SERVES».** They are why the slice is cut this way. Where a
> file matters to one of them, that is the fact worth returning; where it matters to none, say so
> rather than padding the slice.
> Read these files completely, then produce ONLY the rows below — the only file you may write is
> your own fragment file (see the output rule below).
> **Do this work yourself — do NOT spawn your own sub-agents / delegate, and do NOT write a program
> that GENERATES your fragment.** Author the rows. Speed is not the argument — the fastest agent on
> a measured build used one. The cost is every lint round: patch-generator, regenerate, copy,
> re-lint instead of one edit. A sub-agent's output is silently dropped: an agent that delegates
> returns prose instead of a fragment, and the whole slice has to be re-harvested.
> **What the ban is and is not.** Banned: a script that PRODUCES rows — reading the code, deciding
> what a component is, emitting the JSON. Allowed: a small edit to a fragment you already authored
> by hand — a `sed`, a two-anchor `.replace()`, a `json.dump` that reformats. The line is whether
> the PROGRAM made the judgement or you did. The wording said "writes your fragment", which reads
> as banning both: 9 of 30 agents on one build used a program, and most were patching an authored
> draft rather than generating one. That is not the defect this rule names.
> You read the files and write the one fragment; no delegation.
>
> **Files:** «FILES». **List a directory first, then read each file** — a slice read from the
> file names alone returns components nobody opened.
> **Background:** «BACKGROUND» — what the main agent already learned about this slice, handed
> down so you don't re-derive it.
>
> **Expect roughly «EXPECTED_COMPONENTS» components for your
> slice** (one component ≈ one module-/folder-sized unit, ≤ ~10 source files / ~3 kLOC). If you come
> out far under, you are folding subsystem-shaped dirs into single components — make those
> subsystems and recurse into their units; far over, you are splitting module-sized units.
> For every row give `file:line` evidence and a confidence tag. **`verified`** = you read the code
> and traced it; **`inferred`** = you took it from a name, a path or a convention. Nothing writes
> this field, so it is the one fact only you have — it is NOT a statement about the grounding
> skeptics, whose verdicts are worked out separately and never stored here. **Use both values**: one
> shipped map carried `verified` on all 301 element rows, which tells a reader nothing about which
> rows were read, and `lint-fragment` warns when a fragment's labels are all one value. Use only the schema IDs and edge verbs; reference nodes, never
> invent them.
>
> **THE ARRAYS THIS SLICE OWNS — the full list, not an example.** Author every one of these, and
> nothing else:
>
> | array | yours when |
> |---|---|
> | `components` | always |
> | `entry_points` | a file here is a trigger surface (a route, a command, a job) |
> | `deps` | a third-party system is reached from a file here |
> | `observability` | a logging / crash / analytics adapter lives here |
> | `config` | a settings key is read literally in a file here |
> | `deployment`, `run_commands` | a manifest, compose file or command declaration lives here |
>
> **`entities` is NOT yours** unless your brief carries the T5 addendum. Neither is any array not
> listed above.
>
> **AUTHORING A `deps` ROW: one rule lives in `model.md` and blocks you if you do not know it.**
> Every dep in the EXTERNAL group (`datastore` / `messaging` / `service` / `platform`) must either
> name the surface(s) it belongs to in `interfaces`, or carry `not_an_interface: <why it is none>`.
> Surface ids (`In`) are minted at synthesis by a slice you do not own, so from here the answer is
> almost always `not_an_interface` — write the reason, do not invent an id, and do not leave both
> empty. Frameworks and libraries are exempt: they become the product. Without this sentence one
> agent read `model.md` itself to find the rule, and another would simply have returned no `deps`
> at all and said nothing.
>
> **If an array is empty, return it as an empty array AND say why in your reply** — never silently
> omit one. The lead cannot tell "nothing here" from "the agent forgot" otherwise. (This paragraph
> used to read "return exactly this fixed set of sections — one per prescribed slice", which an
> agent owning one slice could not parse at all: it reads as "return one section".)
>
> Your output is **ONE JSON fragment** — a partial map model per
> [model.md](«COYODEX_HOME»/method/model.md), each entry using that array's exact field names. **WRITE the fragment to
> `«repo»/.coyodex/build-fragments/«agent-id».json` yourself and return only that path plus a
> one-line inventory (row count per array)** — never inline the fragment in your reply: a large
> fragment (a T5 return routinely exceeds 50 KB) is silently truncated by sub-agent result caps,
> and a truncated fragment fails `assemble`. An empty slice is an empty array plus a one-line note.
> **Anchor formats** (`assemble` does not fix these up — write them right, or `coyodex validate`
> rejects them): `components[].source`, `entities[].source`, `components[].entry_point`,
> `deps[].where_configured`, `edges[].where`, `entry_points[].source`, `evidence[].file`,
> `run_commands[].source`, `non_entity_types[].source`,
> **`rules[].sites[].where`** (the OPERATIVE line — its `:line` is REQUIRED, never a bare file),
> **and the group `source`
> fields** (`subsystems[].source` / `subdomains[].source` / `capabilities[].source` /
> `blocks[].source`) are all **bare** repo-root-relative refs
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
> `(none)` (fails the anchor gate). **"Nothing is configured" is a VALUE, not a missing field.** If
> the true answer is that this thing has no alerts, no schedule, no retention — say so in the field,
> in words. Omitting the key means "I did not find out"; the two are different facts and the reader
> cannot tell them apart afterwards. Omit only when you really did not find out. (b) Use **only** each array's exact field names — no stray keys
> (`notes`, `slice`, `loc`, …) — but `confidence` IS a real field, required above and enumerated in the schema (`verified` / `inferred`). (c) Every anchor is **repo-root-relative**: the repo root
> is «REPO_ABS» — prefix every path with it. Minimal valid fragment:
> `{"components":[{"id":"C1","name":"AuthGate","purpose":"verifies tokens","source":"backend/auth/gate.py:10"}]}`.
> **WRITE A DRAFT AS YOU GO (required).** Do not hold the fragment in your head until the end: an
> agent that dies mid-run (API outage, machine sleep) loses ALL its reading. Write incremental
> progress to `«repo»/.coyodex/build-fragments/«agent-id».draft.json` and RENAME it to
> `«agent-id».json` only when complete. Spell it `«agent-id».draft.json`, never
> `«agent-id».json.draft` and never a doubled suffix: `assemble` SKIPS any path ending
> `.draft.json`, which is what keeps a half-written fragment out of the glob — and what makes a
> fragment left with that name never assemble at all. The RENAME is what makes your work land.
> **Fields you must NOT author** (the lead assigns them after the fan-out, through `coyodex
> reconcile`; a fragment carrying one is either rejected or silently wrong): `runs_in` — the
> deployment-unit names are minted by a DIFFERENT slice running beside you, so a plausible guess
> like `["backend"]` passes your own lint and hard-fails the lead's `validate`; `subsystem`;
> `subdomain`; `bucket`; `block`; an `id` key on `entry_points` (`assemble` mints `EP` ids from
> content); and a `security` array, ever — an auth surface is a BUSINESS RULE (`access: true`),
> written after the trace by the rules fan-out, and the Security & auth table is derived from those
> rules. `security[]` is legacy storage on old maps; `lint-fragment` warns on any fragment that
> authors it. Note the auth-relevant facts you see (the guard, its file:line) in your REPLY so the
> lead can seed the rules fan-out; do not author rows for them.
> **Scratch files: put your AGENT_ID in the name.** Every agent in this fan-out shares one
> scratchpad directory. A helper script called `build.py` or `notes.py` WILL be overwritten by a
> sibling mid-run — it has happened, and one agent's script then wrote another agent's output file.
> Name it `«agent-id»-<what>.py` and use absolute paths.
> **Quote your shell separators.** The Bash tool runs zsh, where a bare `=word` is EQUALS expansion:
> `echo ====` aborts the command line THERE, so everything after it on that line silently does not
> run and you get a partial read you believe is complete. Write `echo "===="`. Measured on one
> build: 61 truncated command lines across 18 of 71 agents.
> **SELF-CHECK BEFORE RETURNING (required):** run
> `«COYODEX_HOME»/.venv/bin/coyodex lint-fragment --repo «repo» --expect «N» «your-fragment».json` and
> fix every row it reports until it exits clean — this catches schema / anchor-format / extra-key /
> missing-file errors in YOUR context (in parallel), so nothing bounces back from the lead's
> `assemble`. Pass `--expect «N»` with the component budget this slice was dispatched with: it is
> advisory, and it puts the over/undershoot in front of the agent that can explain it — otherwise
> nobody sees it until the lead's granularity advisory fires after assembly.
> **The verdict line carries the two counts worth acting on, so a reader who takes only the first
> line still sees them.** With `--repo` it ends with an anchor-drift count when any of your anchors
> point at a line that cannot be acting — an import, a comment, a `def`, a blank line. With
> `--expect` it also carries how far past its budget the slice landed. Read the FIRST line:
> `LINT OK — 0 problems, 4 advisory warning(s) (3 anchor drift) (3.7x the slice budget)`. Those rows are advisory and
> never fail the lint, and they are the defect this self-check was blind to until now: six
> fragments once passed clean and produced 86 drifted anchors at the lead's `validate`, costing
> fifty turns of repair after their authors were gone. Anchor the operative statement — the call,
> the write, the enforce line itself — or set `no_call_site`.
> If the lint prints `warning:` lines (advisory), either FIX them or **repeat them verbatim in your
> reply with one line of justification each** — never silently shrug an advisory off; the lead must
> not rediscover a warning your own lint already showed you.
> **Anchor the operative statement** — the call / write / enforce line itself — **never the enclosing
> `def`/class header** (the most common anchor-drift the adversarial pass finds).
> Your AGENT_ID is your fragment's **filename stem only** — never a field inside the JSON.
> **Entities are the T5 owner's alone.** Exactly one agent in this fan-out owns T5; its brief says
> so and continues in an appended addendum. If yours does not, return your components /
> entry-points only and leave `entities` (and every `E↔E` relation) to the owner — do not author
> them, however clearly the domain layer shows in your files.
> (Edges — including `C→E` — are traced in Phase 3, NOT harvested here; this phase returns nodes.)

> **Read the output whole — do not pipe it through `head` or `tail`.** The verdict leads
> the output and the PROBLEM LIST is the middle; a narrow window shows you `LINT FAILED — 6
> problem(s)` and two of the six, and you fix two. Measured across two builds: 0 of 101 sub-agent
> invocations were narrowed on one, 71 of 101 on the next.
>
> **Do not open a previous map.** Not one under `.coyodex/dev-rebuilds/`, not a
> `map-backups/` copy, not one `git show` can produce. This build is deliberately independent of
> its predecessor: a map that reads the one it replaces may still be right, but nobody can tell any
> more, and an eval comparing two maps of one repo reads the agreement as convergence when it is
> copying. If you need an element's record, it is in THIS map — `coyodex dump` reads it.
