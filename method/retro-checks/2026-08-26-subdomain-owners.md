# Every data area says which feature it exists for, and the tools cross-examine the answer

Change: sub-domains holding saved records carry an authored `owners: ["CAPn", …]` (with an
entity-level override for the one record whose owning feature differs from its area's); the derived
touches — which features' flows reach which saved records — ship beside it as evidence, and
`validate` reports grounding / split / dominance / missing / redundant-override disagreements. The
Features page draws a third column of data areas from the same derivation · method.md,
method/model.md, method/project-map.schema.json, tools/coyomap/model.py, grammar.py, areas.py,
features.py, validate_model.py, records.py, viewer.

Escalation: if check 1 fails as "every area single-owned including the shared core", the instruction
is being read as a form to fill in — run the eval before accepting the map, and re-read the WHY
paragraph in method.md before changing any wording.

## Settled once already — 2026-08-26 mcpolis build

Checks 1, 2 and 3 FAILED on that build, and the cause was one thing: the instruction said to decide
ownership at SYNTHESIS, where no walk exists yet, so the author decided blind and `validate` could
not challenge anything (9 owner warnings at that moment, all false). 8 areas took 8 single owners,
one feature took 5, one owner had no evidence at all and was silenced with a recorded exception.

The instruction now says to decide AFTER THE TRACE. Re-deciding the same map with the walks visible
changed exactly the two answers that had failed, and recorded no exception. The checks below stand
unchanged and come due again on the next build — the change is to the method they test, not to them.

## Checks

1. expect: the next mcpolis build authors `owners` on every sub-domain holding saved records
   (8 areas: Organizations and plans, Access rules, Upstream MCP definitions, Discovered catalog,
   Upstream connections and credentials, Gateway credentials, Sandbox runtime and command
   credentials, Activity records). A single owner where one feature clearly runs the lifecycle
   (Access rules → Access control); a deliberate list where the sharing is real (Organizations and
   plans, whose Organization row alone is reached by 7 features, so its records do not partition).
   regression sign: no `owners` anywhere (the instruction was not read); all 8 areas single-owned,
   the shared core included (authored to complete the diagram rather than decided); or `owners`
   authored on a subsystem, a capability or a block, which `validate` blocks.
2. expect: `coyomap validate` reports zero shape errors from `owners`, and any grounding advisory
   it does report ("names owner(s) whose flows touch none of its saved records") points at an area
   the named feature genuinely never reaches.
   regression sign: a dangling owner id or an empty `owners` list reaching the built map; or a
   grounding advisory silenced with a "Data owner exceptions" record instead of fixing the owner or
   writing the missing walk.
3. expect: the rendered Features page matches the authoring — an ownership wire only where exactly
   one owner is authored, a shared area drawing no ownership wire and showing its several inbound
   reference arrows instead, and an area nobody decided drawing reference arrows only.
   regression sign: an owner with no evidence surviving to the screen, or the viewer inventing an owner
   where none was authored (an area with one reference arrow rendered as owned).
4. expect: entity-level `owners` appears only where the record's owning feature genuinely differs
   from its area's — mcpolis's activity/audit record is the candidate, written by the gateway while
   its area exists for the audit trail.
   regression sign: an override on every entity of an area (the area's own `owners` restated
   record by record), which `validate` reports as redundant.
