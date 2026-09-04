# The most specific interface kind that fits wins, and `api` is the fallback

Change (2026-09-03): the interface `kind` instruction gains a tie-break — when two seeds both fit,
author the more specific one; reach for `api` only when nothing else describes the surface ·
method.md, method/model.md. The mcpolis map's "Upstream MCP servers" row is corrected from `api` to
`agent-tools` in the same change.

Escalation: if check 1 fails on a rebuild of mcpolis, the instruction did not reach the worker that
authors T2b — say so in the report rather than hand-fixing the row again, because a hand fix is
thrown away by the next build and hides the fact that the rule is not landing.

## What this change is answering

**`api` is a SUPERSET of several other seeds, and nothing said which to pick when both fit.** Its own
definition is "one program calling another over a network, either direction" — which is also true of
every `agent-tools` surface and of much of `content`. So the vaguer word wins by default, because it
is never actually wrong.

**One live row, found while checking something else.** mcpolis I11 "Upstream MCP servers" — the
servers the gateway asks for their tools and forwards each permitted call to — was authored `api`,
while the gateway that calls them is `agent-tools`. On the Interfaces screen that drew a wrench on
three MCP surfaces and a plug on the fourth, for one protocol.

**The evidence is one row in ten, and that is stated plainly rather than dressed up.** Across the
three live maps there are 10 `api` interfaces and only this one is arguably mis-kinded; the other
nine (analytics ×2, crash reporting ×2, log stores ×2, a sandbox host, a paid page fetcher, an
assistant sign-in exchange) are correctly `api`. What earns the rule is not the count but the
direction: the one case is the MCP one, and `mcp-tool` is already the fourth-biggest way-in kind
across these maps (63, behind only `http-route`, `cli` and `ui-route`).

**IT CANNOT BE A GATE, and must not be turned into one.** Deciding that an upstream service speaks
MCP means matching on its name or its `bucket` text, which is guessing from words. This is an
instruction a build follows, and a later build is its only proof.

## Open, found by the partial run and NOT fixed

Three defects the 2b runs surfaced that this change does not close. They are recorded so the next
person meets them as known, not as a discovery.

1. **No seed covers a message the product PUSHES to a person** (email, SMS, push). Two independent
   readers, on two runs, authored mcpolis's "Outgoing email" as `api` where the map says `handoff`,
   and both gave the same reason: `api` names the SMTP pipe, not the surface, and "prefer a seed,
   mint only when none fits" blocks the mint because `api` technically fits. `handoff` versus `api`
   for an outbound message is never contrasted anywhere.

2. **A protocol's non-tool half has no rule.** argus's "Assistant sign-in" is the registration and
   token exchange beside `agent-tools` "Assistant tools". The reader reached `api` correctly but by
   its own reasoning, not from the text: nothing says whether the sign-in half of a machine protocol
   shares the kind of its tools half.

3. **Two sentences in the `carries[]` guidance conflict**, one from this same day. "Distinct meaning
   it names different records" says split a row; "a rich walk is a reason to write FEWER rows" says
   merge it. A reader hit a row that was two by one sentence and one by the other, and said so:
   "the clearest place where I could not obey both sentences at once."

## Checks

1. expect: on a rebuild of mcpolis, "Upstream MCP servers" comes back as `agent-tools`, not `api`,
   without anyone editing the row by hand.
   regression sign: it returns as `api`. The instruction is not reaching the worker that authors
   T2b, and the corrected row in this change was masking that.

2. expect: no NEW row moves the other way — a surface that a previous map authored with a specific
   kind (`content`, `handoff`, `hosted-screen`, `agent-tools`) coming back as `api`.
   regression sign: the count of `api` rows grows while the specific kinds shrink. "Most specific
   wins" was read as licence to reach for the generic one less carefully, or the worker is choosing
   `api` first and only then looking for a better word.

3. expect: `agent-tools` is used on BOTH sides where it fits — its definition is "ours or theirs" and
   the previous map used it only on `ours`. mcpolis should carry at least one `theirs` row with it.
   regression sign: every `agent-tools` row is `ours` again. The `Side` column in the seed table is
   guidance, and it is being read as a rule.

4. expect: no surface acquires a kind naming a PROTOCOL (`mcp`, `a2a`, `graphql`, `grpc`). The
   vocabulary names what a surface IS, and the protocol belongs to the ways in
   (`entry_points[].kind`, where `mcp-tool` already lives) or to the dependency's own purpose word.
   regression sign: a minted kind that is a protocol name. The tie-break was read as an invitation
   to be specific about the wrong axis.
