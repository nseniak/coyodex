#!/usr/bin/env python3
"""The single `coyodex` command — dispatches to the pre-index, validator, and viewer.

DEPENDENCY FIREWALL: this module imports only stdlib at top level. Each subcommand
imports its implementation lazily, inside its own branch, so `coyodex validate` and
`coyodex render` never load the pre-index code path and stay free of any third-party
import (tree-sitter). See internal/docs/design-notes.md.
"""
from __future__ import annotations

import sys

from coyodex import __version__

USAGE = """usage: coyodex <command> [args...]

Commands:
  preindex   Build the structural pre-index (.coyodex/preindex.json). Needs the
             `preindex` extra (tree-sitter); install with: pip install -e '.[preindex]'
  validate   Validate a project-map.md (schema-v1 checks).
  render     Render a project-map.md to a standalone HTML viewer.

Global:
  --version  Print the coyodex version and exit.
  -h/--help  Show this help and exit.

Run `coyodex <command> --help` for command-specific options."""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if args[0] in ("--version", "-V"):
        print(__version__)
        return 0

    cmd, rest = args[0], args[1:]
    if cmd == "preindex":
        from coyodex import preindex  # lazy: only this path may touch tree-sitter
        return preindex.main(rest)
    if cmd == "validate":
        from coyodex import validate_analysis  # stdlib-only
        return validate_analysis.main(rest)
    if cmd == "render":
        from coyodex.viewer import render  # stdlib-only
        return render.main(rest)

    print(f"coyodex: unknown command '{cmd}'\n", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
