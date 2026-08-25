# Glossary term-linking (viewer + aliases) and the generalized indirect-reference rule

Change: glossary term-linking in the viewer; optional `aliases` / `no_autolink` on glossary
entries (schema + model.md + glossary-writing guidance in method.md's Glossary deliverable);
writing rule 4 generalized from "never OPEN with a pointer" to "every reference resolves
inside the same box"; the prose.py advisory counter extended to the checkable subset. As
shipped, the counter flags "either/both/such/the other" + a category noun (kind/mode/way/
transport/form/variant/shape), plus bare "the latter"/"the former", ANYWHERE in the field
(not only mid-sentence), and lets a phrase through on any of three outs: an or/and
enumeration in an EARLIER SENTENCE of the same field, two glossary terms appearing before
the reference, or a trailing "or" enumeration later in the same sentence. It reports as the
"unresolved reference" advisory kind, beside "bare pointer" (the old rule-4 check, kept).

Escalation: if check 1 or check 5 fails, run the eval before accepting the map.

## Checks

1. expect: the two sentences that motivated the rule come out of the rebuild with both
   alternatives named — the "Upstream MCPs" feature purpose (was: "in either kind") and the
   "Connecting to upstreams" subsystem purpose (was: "in either transport").
   regression sign: the sentences got longer but vaguer — the split is still unnamed, or the
   named alternatives replaced the specific verb ("mounting", "holds the connection") that
   carried the sentence's precision.

2. expect: the "unresolved reference" advisory fired during the build (the validate line
   reads "N prose fields with an unresolved reference"; count it in the build transcript /
   validate output) AND the final map retains fewer than 5 true-positive indirect
   references (sample the fired boxes and classify). For calibration: on the pre-rule MCP
   Hero map the counter fires 3 times, all true positives (CAP2 "in either kind", S8 "in
   either transport", C127 "both kinds of MCP").
   regression sign: advisories fired and were ignored (final-map true positives at or above
   the fired count), or 0 fired with opportunity present — the counter is dead.

3. expect: sampling 5 fired advisories from the build finds at most 1 false positive
   (a reference that DID resolve within its own box).
   regression sign: the agent rewrote good within-box references ("keeps that list fresh")
   to silence an over-firing counter — flattened prose in boxes the counter touched.

4. expect: every alias written into the new map's glossary is a real alternative name, none
   is a bare generic English word (tool, value, file, variable, link, or similar), and no
   alias is a mere plural/possessive/case variant of its term.
   regression sign: alias list padded with variants the viewer's folding already covers, or
   with ambiguous single words.

5. expect: in the served viewer on the new map, glossary terms in card prose carry the
   in-place definition (spot-check 3 feature pages and the Storage view's mode notes), with
   at most 1 wrongly-linked ordinary word across the spot-check. As shipped, only the FIRST
   occurrence per card/row links, and no link appears in: titles/headings/card names, pills
   and chips, route triggers, snake_case identifiers, code spans, file paths, SVG diagrams,
   the source column, or the Glossary view itself.
   regression sign: over-linking — ordinary words linked because a generic term or alias
   matched; or load-bearing terms ("cloud mode", "standalone mode") still bare; or links
   showing up in titles, chips or identifiers (the skip list regressed).

6. expect: glossary terms whose own name is a generic word are handled deliberately —
   `no_autolink` set, or an explicit justification in the build transcript.
   regression sign: "Tool" auto-linking on every card that says "tool".
