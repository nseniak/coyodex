# `mcp` is the twelfth interface kind, and the only protocol name in the list

Change (2026-09-03): `mcp` joins `grammar.INTERFACE_KIND_SEEDS` as an `either`-side seed, drawn with
the wrench and printed "MCP" · tools/coyodex/grammar.py, the viewer, method.md, method/model.md,
method/project-map.schema.json. Five live rows move from `agent-tools` to `mcp`: mcpolis I3, I4, I6,
I11 and argus I4.

Escalation: if check 2 fails — a second protocol name appears as a kind — the guard did not hold and
the vocabulary is drifting off its own axis. Say so in the report; do not fold the new word in.

## What this change is answering

**The word "MCP" could not be put on screen any other way.** Three routes were tried and measured:

1. *Rename the shape.* Display every `agent-tools` interface as MCP. WRONG on 2 of 6 across the
   three maps: coyodex's "Agent skill" and "Developer skills" are skill FILES an agent reads, whose
   ways in say `agent-skill`, not `mcp-tool`.
2. *Derive it from the ways in.* Label an interface MCP when any way in is an `mcp-tool`. Right on
   the four we publish and SILENT on the one we call: a `theirs` surface has no ways in by
   definition, so mcpolis's "Upstream MCP servers" got nothing. That reopens the exact seam this
   work had just closed by correcting that row's kind.
3. *A seed.* Works on both sides, because a person can author it.

**Why the objection was overruled.** Every other seed says what a surface IS; this one says which
protocol it speaks, and protocol normally belongs to the ways in, where `mcp-tool` already lives.
Two facts beat that: route 2 above cannot reach a `theirs` surface at all, and `mcp-tool` is the
FOURTH-BIGGEST way-in kind across the live maps (63, behind only `http-route` 169, `cli` 90 and
`ui-route` 71). A word that common in the code earns one on screen.

**The guard is the tie-break, not good intentions.** "The most specific seed that fits wins" already
orders `mcp` above `agent-tools` above `api`. `agent-tools` keeps a real job: agent-facing tools
carried some other way, which is what coyodex's own skill files are.

## Checks

1. expect: a rebuild of mcpolis authors `mcp` on the Gateway, the Administration MCP, the Operator
   MCP and the Upstream MCP servers, and `agent-tools` on nothing; a rebuild of coyodex authors
   `agent-skill`-backed surfaces as `agent-tools`, NOT `mcp`.
   regression sign: coyodex's "Agent skill" comes back as `mcp`. The seed was read as "anything an
   agent talks to", which is the mistake route 1 above was rejected for.

2. expect: NO second protocol name appears as an interface kind — not `a2a`, `graphql`, `grpc`,
   `openapi`, `rest`, `websocket`, `soap`.
   regression sign: any of them, minted or seeded. Both the method and `grammar.py` carry an
   explicit "do not mint a second protocol seed by pointing at this one"; if one appears, that
   sentence is not doing its work and the vocabulary has changed axis.

3. expect: `api` does NOT grow. Across the three live maps it stood at 10 rows before this change and
   9 after (mcpolis I11 left it). A rebuild should land near that, with the observability rows
   (crash reporting, analytics, log stores) still `api`.
   regression sign: `api` climbing back while `mcp` and `agent-tools` shrink — the tie-break is being
   read as optional.

4. expect: on the Interfaces screen, every MCP surface carries one word and one glyph, on both
   shores. Verified by eye on mcpolis: Gateway, Administration MCP, Operator MCP and Upstream MCP
   servers all read "MCP".
   regression sign: two words for one protocol on one screen, which is the defect that started this.
