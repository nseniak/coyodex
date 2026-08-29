# LLM-judge rubric — coyodex map quality

Each dimension is scored **0–4**. N judges score independently; the eval takes the **median** per
dimension. A judge is given the produced `project-map.md` and read access to the source repo, and must
justify every score with a `file:line` from the code. A score you cannot back with a `file:line` must
be scored **down**, not guessed.

## Dimensions

1. **Faithfulness** — do the map's "actually-does" claims match the code? Sample the backbone edges,
   the Security & auth rows and the **T7 business rules**; each false claim is a hard hit. Judge the
   RELATIONSHIP a claim states, not its anchor: a true relationship with an off-by-some-lines anchor
   is still faithful (the anchor is scored under Drill accuracy). (Overlaps the L2-grounding
   pass-rate — the judge adds semantic nuance the claim-by-claim check can't.)

   For a business rule the claim is the STATEMENT: does the code really decide this, and is the rule
   reconstructible from the lines its sites point at with no clause added? An unsupported clause
   under a real anchor is the failure mode to hunt — a rule that reads true but says more than its
   sites show. Whether each site lands on the operative LINE is Drill accuracy, not this dimension.
   A rule stating something no product person could have decided otherwise ("if the list is empty,
   return early") is not a business rule at all, and counts against Altitude discipline.

   For an **interface** (T2b) the claim is that data or events really cross there, and that the far
   side is what the row says. Two failures to hunt, because neither is visible at the call site:
   a service the product only reads its OWN data back from, marked as a surface (a search index over
   its own records is not one; the same service over the open web is); and a **pipe named instead of
   the far side** — a reverse proxy, a log shipper, the library that calls a service. Read what the
   service actually holds or returns before scoring the row true. A `theirs` row with no `evidence`
   is a row nobody checked.

2. **Completeness** — does the map cover the system's real surface area, or are whole modules / entry
   points / entities missing? Cross-check against the repo's top-level structure. Two specific gaps
   to look for, because the map now makes both visible: an **untraced use case** (described but with
   no flow — indistinguishable from a feature that no longer exists, so it is a real defect, not a
   stylistic one), and a **capability none of whose use cases is traced**, which means a whole part
   of the product was never walked.

   The outside edge is scored here too, and it has TWO failures, one of which looks like success.
   A map with external-system dependencies and **no interfaces at all** never authored the section —
   score it as a whole missing surface, not a stylistic gap. And a map with interfaces where **no
   flow step names one** authored the rows and never put them into a story: the map can say what its
   outside edge is while no walk goes through a door. Both have shipped. The second is the one that
   reads as done. Also check the other direction: an external-group dependency that names neither a
   surface nor a reason is a decision nobody made.

3. **Drill accuracy** — do the drill anchors (`file:line`, links) resolve to the code they claim to
   explain? Sample anchors and open them. Anchor-line EXACTNESS lives here — a stale or drifted line
   number is a Drill-accuracy hit, never a grounding refutation of the relationship it anchors.

   A business rule's SITE is scored here, and held to the hardest version of the standard: a site
   claims that THIS LINE enforces the decision, so a site pointing at a definition header, an import
   or the component's home — a line that could not act — is a Drill-accuracy hit even when the rule
   itself is true. That is the seam: the rule is Faithfulness, the site is Drill accuracy.

   An **interface's** `source` claims to be the ONE line declaring the whole surface — the router,
   the command table, the file writer. A comment, an import, or the line that parses `argv` is a
   Drill-accuracy hit even when the surface itself is real; four of the first six authored by hand
   failed exactly this way.

4. **Altitude discipline** — is each element at the right zoom (a component is a component, not a whole
   subsystem folded into one box; the domain model is not under-harvested)? And do the diagrams read at
   that zoom: is the tree balanced (each screen near the 5±2 fan-out target), is the top level grouped by
   product area rather than tech tier, and is no level a single-child wrapper?

   An **interface** is one row per SURFACE, never one per address or per command: 57 web addresses
   that serve one dashboard are one row. The one real split is by AUDIENCE — a customer console and
   a staff console behind the same addresses are two surfaces, and collapsing them hides who a
   surface is for. And the name is in product words: "Customer dashboard", never "http-route".

5. **Happy-Path coherence** — does the ordered spine read as a real end-to-end walk, with each step's
   `why:` precondition satisfied by an earlier step?

## Output (per judge)

An integer `score` (0–4) for each of the five dimensions, a one-line `justification`, and at least one
`evidence` `file:line`, plus a short `notes` summary. The judge harness fixes the exact JSON shape.
