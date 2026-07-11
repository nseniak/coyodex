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
  validate   Validate a map (schema + semantic checks — is it WELL-FORMED?).
  audit      Adversarial pass over a built map (is it SELF-CONTRADICTORY?): L1
             deterministic contradiction checks + an L2 grounding worklist.
  render     Render a map's committed markdown view (model → project-map.md). The
             interactive diagram is served by `serve`, not written to a file.
  serve      Serve the interactive viewer + file browser + code viewer over a local
             HTTP server, building each map's diagram on demand from its model (files
             read from git at the map's commit). One server covers every project.
  assemble   Merge build agents' structured-row fragments into the canonical
             project-map.json (+ generated views).
  lint-fragment  Self-check ONE build fragment before returning it (schema + anchor
             format + extra-key conventions, and with --repo that anchors exist).
  dump       Emit the parsed model as JSON — whole, or a fixed slice (--id /
             --record / --edges / --members). Read-only lookups over the model.

The method-quality regression eval is a separate command: `coyodex-eval` (see eval/).

Global:
  --version  Print the coyodex version and exit.
  -h/--help  Show this help and exit.

Run `coyodex <command> --help` for command-specific options."""


def _default_map(argv: list[str]) -> list[str]:
    """When no positional map is given, default to `.coyodex/project-map.json`."""
    flags_with_value = {"--repo"}
    expect_value = False
    for a in argv:
        if expect_value:
            expect_value = False
        elif a in flags_with_value:
            expect_value = True
        elif not a.startswith("-"):
            return argv  # an explicit map was given
    return argv + [".coyodex/project-map.json"]


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
        from coyodex import validate_model  # stdlib-only
        return validate_model.main(_default_map(rest))
    if cmd == "audit":
        from coyodex import audit_model  # stdlib-only
        return audit_model.main(_default_map(rest))
    if cmd == "render":
        from coyodex.viewer import render  # stdlib-only
        return render.main(rest)
    if cmd == "serve":
        from coyodex.viewer import serve  # stdlib-only (http.server + git subprocess)
        return serve.main(rest)
    if cmd == "assemble":
        from coyodex import assemble  # stdlib-only
        return assemble.main(rest)
    if cmd == "dump":
        from coyodex import dump  # stdlib-only; defaults to .coyodex/project-map.json
        return dump.main(rest)
    if cmd == "lint-fragment":
        from coyodex import lint_fragment  # stdlib-only
        return lint_fragment.main(rest)

    print(f"coyodex: unknown command '{cmd}'\n", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
