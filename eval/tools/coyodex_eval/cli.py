#!/usr/bin/env python3
"""The single `coyodex-eval` command — the method-quality regression harness dispatcher.

Each subcommand imports its implementation lazily. Stdlib-only; depends on the `coyodex` core package
(schema / validate / audit) for the shared parse, and nothing else.
"""
from __future__ import annotations

import sys

USAGE = """usage: coyodex-eval <command> [args...]

Commands:
  score    Emit a map's deterministic quality PROFILE (structure / validate / audit / coverage).
  run      Profile a built map, compare vs its baseline, and archive the run.
  hash     Print a map artifact's sha256 freeze hash (write it at build time; `run` enforces it).
  claims   Print the audit's L2 worklist (the judge's input) — `--json`, `--top K` for the sample.
  judge    Aggregate orchestrated judge verdicts (grounding + rubric) into judge.json.
  protocol Print the current judge-protocol fingerprint; --against guards the baseline cache.
  bless    Promote a run to the baseline (map + rendered view + profile + judge).
  compare  Compare a candidate MapProfile against a baseline; apply the relative regression gates.
  process  L3 PROCESS scorecard over a build TRANSCRIPT (did the agent behave as the method says?)
           — `--diff a.json b.json` compares two scorecards. A scorecard, never a gate.
  transcript  READ a build transcript in slices — an index by default, `--full` for one range.
           The retrospective's eye on what the agent actually did.
  cost     What a build SPENT — wall time, tokens, and both PER ROW of map produced (`--map`).
           Reads the sub-agent transcripts too, which are most of the spend. Never a gate.
  archive  Move a repo's coyodex map into .coyodex/dev-rebuilds/NNNN/ so the next run BUILDS
           from scratch (dispatch reads the WORKING TREE to choose the mode). Moves, never
           deletes — the old map is the baseline the new one is compared against.
  retro-precheck  Refuse to retrospect a build that has not finished. Exit 1 when another
           session is still writing a transcript — provenance is stamped near the END of a
           build, so mid-run it still names the PREVIOUS one and a retro reads the wrong run.

Run `coyodex-eval <command> --help` for command-specific options."""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    cmd, rest = args[0], args[1:]
    if cmd == "score":
        from coyodex_eval import profile
        return profile.main(rest)
    if cmd == "run":
        from coyodex_eval import run
        return run.run_cli(rest)
    if cmd == "hash":
        from coyodex_eval import run
        return run.hash_cli(rest)
    if cmd == "claims":
        from coyodex_eval import run
        return run.claims_cli(rest)
    if cmd == "judge":
        from coyodex_eval import run
        return run.judge_cli(rest)
    if cmd == "protocol":
        from coyodex_eval import run
        return run.protocol_cli(rest)
    if cmd == "bless":
        from coyodex_eval import run
        return run.bless_cli(rest)
    if cmd == "compare":
        from coyodex_eval import compare
        return compare.main(rest)
    if cmd == "process":
        from coyodex_eval import process_scorecard
        return process_scorecard.main(rest)
    if cmd == "archive":
        from coyodex_eval import archive
        return archive.main(rest)
    if cmd == "retro-precheck":
        from coyodex_eval import retro_precheck
        return retro_precheck.main(rest)
    if cmd == "transcript":
        from coyodex_eval import transcript
        return transcript.main(rest)
    if cmd == "cost":
        from coyodex_eval import cost
        return cost.main(rest)
    print(f"coyodex-eval: unknown command '{cmd}'\n", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
