#!/usr/bin/env python3
"""`coyodex eval <subcommand>` — the method-quality regression harness dispatcher.

Subcommands (each imports its implementation lazily, like the top-level CLI):
  compare   Score a candidate map profile against a baseline and apply the regression gates.

Planned: `baseline` (bless a run as the baseline) and `run` (the full orchestrator — build a map per
reference repo, profile + judge + compare). Stdlib-only.
"""
from __future__ import annotations

import sys

USAGE = """usage: coyodex eval <subcommand> [args...]

Subcommands:
  compare   Compare a candidate MapProfile against a baseline; apply the relative regression gates.

Run `coyodex eval <subcommand> --help` for command-specific options."""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    sub, rest = args[0], args[1:]
    if sub == "compare":
        from coyodex.eval import compare
        return compare.main(rest)
    print(f"coyodex eval: unknown subcommand '{sub}'\n", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
