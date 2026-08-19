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

**The slot that keeps being left empty is «SERVES».** Structural slices exist to serve the
behavioral layer. The behavioral draft exists before this fan-out precisely so the slices can be cut
to it; a brief that names no use case is a brief cut from the file tree, and the harvest then comes
back with components carrying no backbone edge at all. Assertion 31 counts this.

Give every harvest agent the same skeleton — only the file list and the background blurb change per
agent. Reusing one contract is what makes each agent return the same row shapes with the same
verified/inferred discipline, which keeps the barrier synthesis clean.

**The template starts at the quoted block below.** Everything above it is instructions to you, the
lead; nothing above this line goes into an agent prompt.

> You are harvesting «structural / operational / build» facts for a coyodex codebase map.
>
> **This slice serves: «SERVES — the UC / CAP / HP / R ids whose behavior runs through these files,
> with one line each on what they need from you».** They are why the slice is cut this way. Where a
> file matters to one of them, that is the fact worth returning; where it matters to none, say so
> rather than padding the slice.
> Read these files completely, then produce ONLY the rows below — the only file you may write is
> your own fragment file (see the output rule below). **Do this work yourself — do NOT spawn your
> own sub-agents / delegate, and do NOT write a program that writes your fragment.** Author the rows.
> Speed is not the argument — the fastest agent on a measured build used one. The cost is every lint
> round: patch-generator, regenerate, copy, re-lint instead of one edit. A sub-agent's output is
> silently dropped: an agent
> that delegates returns prose instead of a fragment, and the whole slice has to be re-harvested.
> You read the files and write the one fragment; no delegation.
>
> **Files:** «absolute paths this agent owns; list a directory first, then read each file».
> **Background:** «what the main agent already learned about this slice, handed down so you
> don't re-derive it».
>
> **Expect roughly «the slice's E from the pre-index `granularity.per_dir`» components for your
> slice** (one component ≈ one module-/folder-sized unit, ≤ ~10 source files / ~3 kLOC). If you come
> out far under, you are folding subsystem-shaped dirs into single components — make those
> subsystems and recurse into their units; far over, you are splitting module-sized units.
> For every row give `file:line` evidence and a confidence tag (**verified** = read in code /
> **inferred** = guessed). Use only the schema IDs and edge verbs; reference nodes, never
> invent them. **Return exactly this fixed set of sections — one per prescribed slice — and if you
> cannot fill one, return its header with `(none found)` and say why; never silently omit a
> section.** Your output is **ONE JSON fragment** — a partial map model per
> [model.md](«COYODEX_HOME»/method/model.md): an object holding only the top-level arrays your slice owns
> («e.g. `components`, `entry_points`, `deps`, `deployment`, `observability`, `security`,
> `config`»), each entry using that array's exact field names. **WRITE the fragment to
> `«repo»/.coyodex/build-fragments/«agent-id».json` yourself and return only that path plus a
> one-line inventory (row count per array)** — never inline the fragment in your reply: a large
> fragment (a T5 return routinely exceeds 50 KB) is silently truncated by sub-agent result caps,
> and a truncated fragment fails `assemble`. An empty slice is an empty array plus a one-line note.
> **Anchor formats** (`assemble` does not fix these up — write them right, or `coyodex validate`
> rejects them): `components[].source`, `entities[].source`, `components[].entry_point`,
> `deps[].where_configured`, `edges[].where`, `entry_points[].source`, `evidence[].file`,
> `run_commands[].source`, `security[].source`, `non_entity_types[].source`,
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
> `(none)` (fails the anchor gate). (b) Use **only** each array's exact field names — no stray keys
> (`notes`, `slice`, `loc`, …) — but `confidence` IS a real field, required above and enumerated in the schema (`verified` / `inferred`). (c) Every anchor is **repo-root-relative**: the repo root
> is «absolute repo path» — prefix every path with it. Minimal valid fragment:
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
> content); and a `security` array unless your slice was told it owns one.
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
> **With `--repo`, the verdict line ends with an anchor-drift count when any of your anchors point
> at a line that cannot be acting** — an import, a comment, a `def`, a blank line. Read the FIRST
> line: `LINT OK — 0 problems, 3 advisory warning(s) (3 anchor drift)`. Those rows are advisory and
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
> **If you are the T5 DOMAIN-MODEL owner** (one agent owns T5 — see the harvest plan), your fragment
> also carries the **`entities` array — per-entity objects, never a flat table** (`id`, `name`,
> `store`, `meaning`, `source`, `fields`, `relations` — the semantic spec is
> [domain-cards.md](«COYODEX_HOME»/method/domain-cards.md)), with **a `relations` item wherever two entities
> relate** — the entities + their `E↔E` relations are the whole point of the slice. Each entity is a
> **real named type** (class / dataclass / enum) whose `source` anchors its **definition** — do NOT
> synthesize an entity for an unnamed concept; type embedded fields by their entity (`auth:E7`) so
> relations carry the field name. For a **field-less** relation a store realizes by keying (no FK on
> the row — e.g. a per-parent store keyed by `parent_id`), set the relation's **`keyed_by`** so the
> arrow shows the key (`«key» parent_id`) instead of a bare line — see [domain-cards.md](«COYODEX_HOME»/method/domain-cards.md).
> Mark plumbing types you deliberately did NOT model in `non_entity_types` (name + why). A directory- or subsystem-sliced agent that is **not** the T5
> owner returns its components / entry-points only and leaves `entities` to the owner.
> (Edges — including `C→E` — are traced in Phase 3, NOT harvested here; this phase returns nodes.)
