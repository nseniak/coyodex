# Roles can record relations (becomes / includes), and builds use them only where the code grounds them

Change: role relations — `roles[].relations` ({kind: becomes, role, at} / {kind: includes, role})
in the model + schema, the instruction under the Roles rule in method.md, referential validation,
and the viewer's actor page reading them (hero meta + greyed before-segment) · method.md,
method/model.md, method/project-map.schema.json, tools/coyodex/model.py, validate_model.py,
views.py, viewer.

Escalation: if check 3 or 4 fails (invented relations), run the eval before accepting the map.

## Checks

1. expect: the next MCP Hero build records `R5 (Prospective customer)` with
   `{ "kind": "becomes", "role": <the admin's Rn>, "at": <the "sign in and name the organization"
   UCn> }` — the one transition the code actually maps.
   regression sign: the build carries no relations at all (the instruction was not read), or the
   `becomes` sits on the admin instead of the prospect (the direction reversed).
2. expect: the same build records the admin with `{ "kind": "includes", "role": <the member's Rn> }`,
   in that one direction.
   regression sign: the member also carries `includes` the admin (a symmetric duplicate — A
   includes B AND B includes A), or `includes` links roles whose permission sets the code never
   nests.
3. expect: every `relations[].role` and `relations[].at` in the built map resolves to a defined
   `Rn` / `UCn` (`coyodex validate` reports zero undefined-ID references from relations).
   regression sign: validate reports a relation id that resolves to nothing.
4. expect: zero relations invented where the code gives no ground — every `becomes` names an `at`
   use case that really performs the transition.
   regression sign: a `becomes` with no transition use case behind it (an `at` picked to satisfy
   the field), or relations between roles the code never connects.
