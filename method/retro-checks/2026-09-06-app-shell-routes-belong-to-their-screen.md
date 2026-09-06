# The route that serves the built app belongs to the screen it serves

Change (2026-09-06): T2b in `method.md` gains one line — the route that serves the built app, and
the catch-all that serves its shell, belong to the web surface they serve. The note beside
`_PLUMBING_EP_KINDS` in `tools/coyodex/validate_model.py` is corrected: it claimed those two rows
"can never belong to a surface", which is what left the advisory unsatisfiable. NO live map was
hand-fixed and no filter was widened.

Escalation: none on its own. If check 1 fails together with check 1 of
`2026-09-06-a-build-command-is-not-a-way-in.md`, the whole T2b/T4 pass did not reach the build and
the eval is worth running before accepting the map.

## What this change is answering

**An advisory nobody can clear is an advisory people stop reading.** "Every externally activated
way in belongs to exactly one surface" fired on both live maps, on rows the tool's own comment
said could belong to no surface. Neither row carries a `kind` of its own — both are ordinary
`http-route` / `ui-route` rows — so no filter could have excluded them either. The check had no
fix that would satisfy it, in either direction.

The claim in that comment was also wrong. **A browser fetching the app shell is the product meeting
a person**, which is the interface test verbatim. Both maps already carry the screen surface that
person ends up looking at, so the two rows have an obvious home and the map gains a true fact: this
product's whole front end is one page.

Measured before shipping: argus has **4 ways in on no surface** — the built-asset mount
(`mcp_server.py:1473`), the single-page catch-all (`:1480`), the pretend sign-in page and the
service launch. Two of the four are this change. mcpolis has **17**, including its own asset mount
(`app.py:2161`), its catch-all (`:2196`) and the proxy's catch-all (`docker/nginx.conf:42`).

## Open, found while doing this and NOT fixed

1. **The proxy rows are a different defect.** mcpolis records `docker/nginx.conf:22` (the reverse
   proxy forwarding `/api`, `/mcp`, `/oauth` to the backend) as a way in ON the Dashboard surface,
   and `:42` as one belonging to nothing. T2b already says "name the far side, never the pipe" and
   names a reverse proxy as a pipe. Nothing was changed for it here.
2. **The remaining two argus rows still need a decision**: the pretend sign-in page, which settings
   allow in production when Google is not configured, and the service launch, which is covered by
   the sibling check file.

## Checks

1. expect: on a rebuild of either map, the built-asset route and the single-page catch-all each
   appear in some interface's `ways_in`. The "N way(s) in belong to no interface" advisory no
   longer names them.
   regression sign: still unassigned; OR silenced by a recorded `EPn: <why>` line under "Interface
   exceptions" — the cheap escape taken instead of the placement, which reads identical in a clean
   run and is exactly what this change removes the excuse for.

2. expect: they land on the SCREEN surface a person looks at — argus's dashboard or public website,
   mcpolis's Dashboard — beside the addresses that surface's pages already call.
   regression sign: a new surface minted to hold them (a row named something like "Static assets"
   or "Web assets"). That satisfies the letter of the advisory and tells a reader nothing.

3. expect: argus's "belong to no interface" count falls from 4 to at most 2, and the rows that
   remain are the pretend sign-in page and the service launch.
   regression sign: still 4.

4. expect: no map acquires a `facing` of `operator` on the surface these rows land on. The shell a
   customer's browser fetches is user-facing.
   regression sign: the surface flips to `operator`, which would be the same re-labelling dodge a
   retired check already caught once (`verified/2026-09-04-a-user-facing-surface-owes-a-use-case.md`).
