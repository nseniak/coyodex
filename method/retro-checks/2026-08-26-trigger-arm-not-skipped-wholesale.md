# The authored trigger arm is never skipped wholesale, and the customer-facing surfaces get a per-surface pass

Change: the mcpolis rebuild shipped 0 trigger links across 319 entry points (the old map linked 41
of 188), and six behaviours silently lost their use case (a sandbox-file upload route and an hourly
health-check job among them, both still live in the code). Fix: `validate` warns on the degenerate
all-empty trigger arm (escape: `trigger-arm: <why>` under 'Entry-point coverage'), and method.md
now requires a per-surface pass at synthesis for the customer-facing kinds (http-route, ui-route,
mcp-tool): each surface is named by a use case's `entry_points`, recorded unclaimed, or becomes a
use case — blanket per-kind prose is a harvest statement, not an adjudication · method.md,
tools/coyodex/validate_model.py. Ledger: mcpolis-2026-08-26-22.

Escalation: if check 3 fails (the lost behaviours stay lost on a rebuild), run the eval before
accepting the map.

## Checks

1. expect: the next build of any project ships a non-zero number of use cases naming entry points
   (`use_cases[].entry_points`), and `coyodex validate` fires no "No use case names any entry
   point" warning — or the map carries a recorded `trigger-arm: <why>` line an operator wrote.
   regression sign: 0 trigger links again with no record, or a `trigger-arm:` record authored by
   the BUILD to silence the warning it just caused (the escape is the operator's, not the build's).
2. expect: every customer-facing surface (http-route, ui-route, mcp-tool) is either named by a use
   case, listed under 'Unclaimed surfaces', or has a use case created for it — spot-check 10
   random such surfaces in the finished map.
   regression sign: a customer-facing surface reachable in the running product with none of the
   three dispositions.
3. expect: the next MCP Hero build recovers the behaviours the 2026-08-26 build lost as use cases
   where the code still has them: adding a sandbox file to a hosted stdio MCP, editing an upstream
   MCP's configuration, and the hourly upstream health check (as a use case or a recorded
   unclaimed line, not silence).
   regression sign: the same behaviours absent again with no record naming them.
