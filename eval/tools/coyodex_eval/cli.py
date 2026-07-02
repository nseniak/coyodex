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
  bless    Promote a run to the baseline (map + rendered view + profile + judge).
  compare  Compare a candidate MapProfile against a baseline; apply the relative regression gates.

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
    if cmd == "bless":
        from coyodex_eval import run
        return run.bless_cli(rest)
    if cmd == "compare":
        from coyodex_eval import compare
        return compare.main(rest)
    print(f"coyodex-eval: unknown command '{cmd}'\n", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
