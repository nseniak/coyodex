# T5 addendum (Phase 1) — the domain-model owner's half

**Appended to ONE harvest brief only: the T5 owner's.** Get it with
`coyodex contract harvest-t5 >> <that agent's brief>`, AFTER the filled harvest contract. It moved
out of the shared harvest contract on 2026-08-27: 13 of ~14 harvest agents were reading a detailed
spec of a job they must not do, and a described-but-forbidden job is a known confusion source — the
main contract keeps only the one sentence forbidding it. No slots of its own beyond
«COYODEX_HOME».

> You are ALSO the T5 DOMAIN-MODEL owner — exactly one agent in this fan-out owns T5, and it is
> you. Everything in your harvest brief above still applies; this addendum is the domain slice's
> own spec.
>
> Your fragment also carries the **`entities` array — per-entity objects, never a flat table**
> (`id`, `name`, `store`, `meaning`, `source`, `fields`, `relations` — the semantic spec is
> [domain-cards.md](«COYODEX_HOME»/method/domain-cards.md)), with **a `relations` item wherever two
> entities relate** — the entities + their `E↔E` relations are the whole point of the slice. Each
> entity is a **real named type** (class / dataclass / enum) whose `source` anchors its
> **definition** — do NOT synthesize an entity for an unnamed concept; type embedded fields by
> their entity (`auth:E7`) so relations carry the field name. For a **field-less** relation a store
> realizes by keying (no FK on the row — e.g. a per-parent store keyed by `parent_id`), set the
> relation's **`keyed_by`** so the arrow shows the key (`«key» parent_id`) instead of a bare line —
> see [domain-cards.md](«COYODEX_HOME»/method/domain-cards.md). Mark plumbing types you
> deliberately did NOT model in `non_entity_types` (name + why).
