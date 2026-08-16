# Harvest contract (Phase 1) — the copyable template

**Copy this file; do not retype it from prose.** Which, taken literally, was impossible: the body
below is a `>`-quoted skeleton full of «angle-bracket» slots, so it cannot be handed to an agent
as-is, and every build has "copied" it by rewriting it — a live one produced 9.5 KB of replacement
prose and dropped the AGENT_ID clause in the process, exactly the drift this file warns about. So
the instruction is now mechanical:

1. Take the quoted block below and strip the leading `> ` from every line.
2. Fill ONLY the «angle-bracket» slots — per agent, that is the file list, the background blurb,
   the **use cases the slice serves**, the component budget and the agent id; per build, the repo
   path and `COYODEX_HOME`.
3. Change nothing else. If a rule reads wrong for this repo, fix it HERE, once, so the next build
   inherits the fix instead of re-deriving it.

**The slot that keeps being left empty is «SERVES».** Structural slices exist to serve the
behavioral layer, and on two consecutive measured builds not one harvest brief — 14 of 14, then 13
of 13 — cited a single `UC`/`CAP`/`HP`/`R` id. Every slice boundary was a directory boundary, and
the harvest came back with 260 of 260 components carrying no backbone edge. The behavioral draft
exists before this fan-out precisely so the slices can be cut to it; a brief that names no use case
is a brief cut from the file tree. Assertion 31 counts this and has scored 0 both times.

**Why the wording matters.** This used to live inline in `method.md`, and every build hand-copied
~5.6 KB of it into a scratchpad. That retyping is where wording drifts: one live build's copy
promised that a `.draft.json` suffix "keeps a half-written file out of the assemble glob", which was
not true of the tool at the time and had to be fixed in both places.

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
> Six of fourteen agents on one build wrote a generator script instead; it predicts nothing about
> speed — the fastest agent of all used one — but every lint round then costs patch-generator,
> regenerate, copy, re-lint instead of one edit, and the two slowest agents in that fan-out were
> both paying it. A sub-agent's output is silently dropped: on a live build a harvest
> agent that delegated returned prose instead of writing its fragment, and the whole slice had to be
> re-harvested. You read the files and write the one fragment; no delegation.
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
> [method/model.md](method/model.md): an object holding only the top-level arrays your slice owns
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
> (`notes`, `slice`, `loc`, …) — but `confidence` IS a real field, required above and enumerated in the schema (`verified` / `inferred`); it was listed here as a stray key while the same template demanded it. (c) Every anchor is **repo-root-relative**: the repo root
> is «absolute repo path» — prefix every path with it. Minimal valid fragment:
> `{"components":[{"id":"C1","name":"AuthGate","purpose":"verifies tokens","source":"backend/auth/gate.py:10"}]}`.
> **SELF-CHECK BEFORE RETURNING (required):** run
> `«COYODEX_HOME»/.venv/bin/coyodex lint-fragment --repo «repo» --expect «N» «your-fragment».json` and
> fix every row it reports until it exits clean — this catches schema / anchor-format / extra-key /
> missing-file errors in YOUR context (in parallel), so nothing bounces back from the lead's
> `assemble`. Pass `--expect «N»` with the component budget this slice was dispatched with: it is
> advisory, and it puts the over/undershoot in front of the agent that can explain it. On a live build
> nine slices dispatched with budgets summing to ~55 delivered 86 components, every slice over, and
> nobody noticed until the lead's granularity advisory fired after assembly.
> If the lint prints `warning:` lines (advisory), either FIX them or **repeat them verbatim in your
> reply with one line of justification each** — never silently shrug an advisory off; the lead must
> not rediscover a warning your own lint already showed you.
> **Anchor the operative statement** — the call / write / enforce line itself — **never the enclosing
> `def`/class header** (the most common anchor-drift the adversarial pass finds).
> Your AGENT_ID is your fragment's **filename stem only** — never a field inside the JSON.
> **If you are the T5 DOMAIN-MODEL owner** (one agent owns T5 — see the harvest plan), your fragment
> also carries the **`entities` array — per-entity objects, never a flat table** (`id`, `name`,
> `store`, `meaning`, `source`, `fields`, `relations` — the semantic spec is
> [domain-cards.md](method/domain-cards.md)), with **a `relations` item wherever two entities
> relate** — the entities + their `E↔E` relations are the whole point of the slice. Each entity is a
> **real named type** (class / dataclass / enum) whose `source` anchors its **definition** — do NOT
> synthesize an entity for an unnamed concept; type embedded fields by their entity (`auth:E7`) so
> relations carry the field name. For a **field-less** relation a store realizes by keying (no FK on
> the row — e.g. a per-parent store keyed by `parent_id`), set the relation's **`keyed_by`** so the
> arrow shows the key (`«key» parent_id`) instead of a bare line — see [domain-cards.md](method/domain-cards.md).
> Mark plumbing types you deliberately did NOT model in `non_entity_types` (name + why). A directory- or subsystem-sliced agent that is **not** the T5
> owner returns its components / entry-points only and leaves `entities` to the owner.
> (Edges — including `C→E` — are traced in Phase 3, NOT harvested here; this phase returns nodes.)
