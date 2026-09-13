# Skeptics and rule agents dump slices instead of reading the map whole

Change: the skeptic contract gains a "Do NOT read the map file whole" rule with `coyomap dump`
commands (and a «COYOMAP_HOME» slot to reach the CLI, four slots → five); the rules contract gains
the same rule beside its existing dump block · method/templates/skeptic-contract.md,
method/templates/rules-contract.md. Motive: the map is ~35k tokens, and an agent that reads it once
carries it on every later turn — modeled as the largest avoidable spend in the build (the
2026-08-27 method assessment, item C2). The independence argument rides along: a skeptic holding
the whole map is holding the build's own story.

Escalation: if check 2 fails (refutation quality moved), run the eval before accepting the map.

## Checks

1. expect: in the next build's Phase-4 skeptic transcripts and rules-agent transcripts, zero
   whole-map reads (no `cat`/`Read` of `project-map.json` itself) and at least one `coyomap dump`
   call per agent that needed an element's record.
   regression sign: agents still open `project-map.json` directly, or a skeptic pastes map content
   into its notes.
2. expect: the pass's quality numbers hold — the refuted / unverifiable split in `grounding report`
   is in line with previous builds, and no skeptic reports it could not settle a claim because it
   lacked map context it used to have.
   regression sign: `unverifiable` jumps, or verdict `note`s start citing missing context instead
   of code.
3. expect: `coyomap-eval cost` shows the verify role's tokens per claim dropped against the Cost
   log's previous build.
   regression sign: the verify role's spend per claim is flat because agents read the map anyway,
   or rose because dump round-trips replaced one read with many.
