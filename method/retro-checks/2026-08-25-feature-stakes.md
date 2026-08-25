# Capability stakes: one authored line per driving actor, labelling the Features diagram's arrows

Change: `stakes[]` on capabilities (schema + model.md + the stake-writing instruction in
method.md's Capabilities section); `validate` blocks a stake whose actor is not a defined role
and advises when a derived driving actor has no stake; the viewer's Features diagram labels each
actor→feature arrow with the actor's stake, falling back to the pair's first use-case name.

Escalation: if stakes are systematically missing (check 1) or duplicated across actors (check 4
regressing on most multi-role features), run the eval before accepting the map.

## Checks

1. expect: every multi-role feature in the next build carries a stake for each of its driving
   actors — on a map shaped like MCP Hero that is one stake per (actor, feature) pair the
   use cases derive, and validate's "driving actor(s) with no stake entry" advisory count is 0
   in the final map.
   regression sign: stakes authored only for the first-listed actor, or the advisory fired and
   was ignored, leaving the viewer's arrows on fallback use-case names.

2. expect: every stake's `actor` references a role defined in `roles[]` (validate reports zero
   "not a defined Role id" problems in the build transcript).
   regression sign: stakes written against actor NAMES or against roles invented for the stake.

3. expect: every stake reads as a verb phrase after the actor's name — sample 5 stakes, prepend
   the role's name, and each forms a grammatical sentence ("Organization admin mounts,
   configures and runs the servers").
   regression sign: stakes written as noun phrases ("server management") or as full sentences
   with their own subject ("The admin mounts…"), which double the actor's name on the arrow.

4. expect: two actors of one feature get two DIFFERENT stakes, each from that actor's own angle
   — the case that motivated the field: on "Upstream MCPs" the admin's stake is about mounting
   and running servers, the member's about signing into an upstream.
   regression sign: stakes that restate the feature's purpose sentence (all actors of a feature
   carrying near-identical text), which hides the other roles exactly as the purpose alone did.
