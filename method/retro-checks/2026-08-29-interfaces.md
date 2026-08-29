# The product's outside edge is authored, and every story goes through a door

Change: a map records `interfaces` (T2b) — one row per surface through which the product exchanges
data or events with the outside world — every external-group dep either names a surface or says why
it is none, and every flow opens at its door (`Rn → In`, then `In → Cn`) with each `Cn → Dn` step on
a surface-standing dep migrated to `Cn → In` · method.md, method/model.md,
method/project-map.schema.json, method/templates/project-map.template.md, tools/coyodex/model.py,
grammar.py, features.py, validate_model.py, audit_model.py, views.py, viewer, eval profile.

Escalation: if check 1 fails as ZERO interfaces on a map with external deps, the section had no step
sending anyone to write it — read the build order in method.md before changing any wording, and do
not accept the map. If check 2 fails as surfaces authored with zero doors, the retrofit step was
skipped, not the authoring.

## Settled twice already — 2026-08-28 test project, 2026-08-29 mcpolis

**The first failure: no step sent anyone.** T2b shipped with its element definition, its checks, its
screens and its model reference, and with NO entry in method.md's build order. The dependency worker
correctly refused (it sees one slice and cannot group a surface) and left a note saying the field was
the lead's; the lead recorded the note and never came back, because nothing sent it. mcpolis: 0
interfaces, 13 external deps, 249 ways in. And `validate` was silent, because every interface check
was gated on there being an interface — a half-authored section was flagged, a wholly missing one was
not. The test project passed the same day on the same method text, because ITS lead happened to
return to its own note. One trial, and it came up heads.

**The second failure: the retrofit was half-specified.** T2b is authored AFTER the trace, so every
flow is written before any surface exists. The rule said an existing `Cn → Dn` step MIGRATES, which
only makes sense post-trace — but nothing told anyone to go back and add the OPENING doors. mcpolis
after authoring: 12 surfaces, 517 flow steps, ZERO doors, 5 migrations owed, 35 flows owing an
opening.

The root mistake under both: **a section was scheduled by its INPUTS and never by its CONSUMERS.**

## Checks

1. expect: the next build of a repo with external dependencies authors interfaces — roughly one
   surface per named group of ways in, plus one per outside service that qualifies — and decides
   every external-group dep one way or the other.
   regression sign: zero interfaces while `validate` reports external deps and ways in (the advisory
   now says so out loud); or every service marked an interface (the read-back rule unread); or a
   library or a pipe (a reverse proxy, a log shipper) marked as one.

2. expect: after authoring, the flows are retrofitted — every use case whose ways in belong to a
   surface opens at that surface, and no step points at a dep that stands on one.
   regression sign: `validate` reports "flow(s) name a way in that belongs to a surface, but no step
   of theirs touches that surface", or "step(s) point at a dependency that stands on a surface".
   Both are aggregated to one line each, so a build cannot lose them in volume.

3. expect: the eval sees the section. `coyodex-eval score` reports `interfaces`, `interface_doors`
   and `interfaces_undecided_deps`, so a build that authors twelve surfaces and one that authors none
   no longer score identically.
   regression sign: a profile in which those three read `None` on a map that has interfaces.
