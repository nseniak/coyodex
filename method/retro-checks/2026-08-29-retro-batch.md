# The 2026-08-29 retro batch: what each fix should change about the next build

Change: 27 fixes from the mcpolis retrospective of 2026-08-29, plus the two rules that were in one
agent contract and needed to be in five · `tools/coyodex/{grounding,validate_model,finalize,
lint_fragment,audit_model,prose,ship,timings,fix,reconcile,contract}.py`,
`eval/tools/coyodex_eval/{transcript,process_scorecard,profile}.py`, `method.md`,
`method/templates/*-contract.md`.

Escalation: if check 2 or check 6 fails, run the eval before accepting the map — both mean a claim
reached the map without the reading the record says it had.

## Checks

1. expect: `coyodex grounding lint --agent-transcripts <the directory a dispatch result names>`
   runs to completion and reports `evidence check covered N of N row(s)` with N the full verdict-row
   count. On the motivating build it died with `AttributeError` and the check covered 0 of 1,085.
   regression sign: any traceback from that flag, or a `grounding.note` that says the pass could not
   run.

2. expect: **no element ships `confidence: verified` with zero verdicts.** `coyodex grounding
   by-element --map <map> --verdicts <each>` (no `--worklist`) reports the same count `finalize`
   prints, and that count is 0. On the motivating build every one of 301 element-level values said
   `verified` and one of them had been refuted by four readers of seven.
   regression sign: the two numbers disagree again, or `finalize`'s advisory names a command whose
   output does not reproduce it.

3. expect: `.coyodex/fanout-timings.json` EXISTS after the build and holds one row per fan-out
   phase, written by `coyodex timings record --lines-from`. `timings order --phase harvest` prints
   an order rather than "no timings recorded".
   regression sign: the file is absent, or the transcript shows a `for … set -- $s` loop again —
   zsh does not word-split, and all 35 such calls on the motivating build exited 2 into `/dev/null`.

4. expect: **zero sub-agents narrow their own `lint-fragment` output** (assertion 40 at 101/101, or
   whatever the denominator is). All five agent contracts now carry the rule; only `gapfill` did.
   regression sign: assertion 40 below 1.00. NOTE — the rule's absence was NOT the cause of the
   0-of-101 → 71-of-101 swing (the distribution was identical on both builds), so a failure here
   means the real cause is still unfound, not that the sentence was ignored.

5. expect: **no sub-agent opens a map under `dev-rebuilds/` or `map-backups/`.** All five contracts
   now carry the independence rule; it lived in `method/dispatch.md`, which only the lead reads.
   regression sign: a grep of the per-agent transcripts' tool-call inputs finds one. One trace agent
   did it nine times on the motivating build and no assertion could see it.

6. expect: `coyodex ship` runs its closing sequence to the end in TWO invocations, and `finalize`
   runs exactly once. `grounding write` no longer refuses the verdict set: `ship` now hands it only
   the files whose claims are all in the pinned worklist, and NAMES the ones it dropped.
   regression sign: three or more `ship` runs, a hand-run tail, or `finalize`'s "the record's delta
   counts contradict the verdict files" surviving into the shipped map.

7. expect: the map's `interfaces` section reaches the rendered `project-map.md`, and
   `lint-fragment` fails an interfaces fragment that `validate` would fail. Both were blind.
   regression sign: `project-map.md` holds none of the surfaces' text while the model holds them.

8. expect: an excused gap is DISCLOSED, never erased — the access-baseline leg, the
   `Interface exceptions` heading and an empty deployment unit all say what they forgave.
   regression sign: "every one of the N file(s) … is still named by an access rule" printed on a map
   that recorded exceptions. That sentence reached a commit message on the motivating build.

9. expect: `coyodex-eval transcript --full` renders the operator's own turns, and renders no skill
   body or `<system-reminder>` as `(operator)`.
   regression sign: zero `(operator)` lines on a session that had a conversation, or a machine-text
   turn labelled as a person.

10. expect: prose batches stay at their previous count (the reading fan-out was NOT widened) while
    `validate`'s long-sentence advisory sees the whole surface. On the motivating map: 13 batches
    either way, and the advisory went 1 → 25.
    regression sign: the batch count jumps ~3×, which is a fan-out cost nobody budgeted.

11. expect: `audit --with-behavioural`, if a build runs it, prints its NOTE and the build keeps the
    grounding record on the DEFAULT worklist. The record path does not follow the flag yet.
    regression sign: a record whose `claims_superseded` is in the hundreds — every behaviour claim
    read as superseded.
