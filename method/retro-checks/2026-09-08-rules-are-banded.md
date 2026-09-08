# `compare` bands the rule count and the rule-site count

Change (2026-09-08): `eval/thresholds.json` gains `rules_shrink_pct` and `rule_sites_shrink_pct`
(0.30, shrink-only, like every other count band). Not the code defaults: the rules layer is
optional, and a default band notes "skipped" on every map without it.
Rules went 102 → 79 → 95 → 88 across four mcpolis builds and nothing banded them; on the 2026-09-08
build all 11 blocks returned exactly 8 rules against a contract asking for about 5, and 57 of the
88 fed the security theme. The band gives the retro the number; the per-block aim stays a method
question (the contract already states 5, and every build fills to 8). A 30 % band would have
fired on none of those four builds (the largest shrink was 102 → 79, 22.5 %): what it catches is a
collapse, and the ceiling behaviour is check 3 below, which the band cannot see.

Escalation: a `rules` DRIFT on a commit where no product file changed means the rule surface is
being re-decided, not re-read — run the eval before accepting the map.

## Checks

1. expect: the next retro's `compare` output carries `rules` and `rule_sites` rows in its band
   table, with the previous build's counts as the baseline.
   regression sign: the rows absent while the profile carries both counts.

2. expect: a rebuild of unchanged code stays within 30 % on both, or the DRIFT is explained in the
   retro by named blocks that lost rules.
   regression sign: a DRIFT waved through as "two LLM builds differ" with no block named.

3. expect: the per-block sizes on the next build vary — not 8 × N — and their mean is under the
   contract's ceiling.
   regression sign: every block at the ceiling again, with the band silent because the total held.
