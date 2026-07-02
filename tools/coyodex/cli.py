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
             project-map.json is the schema-v2 source; a .md argument uses the
             legacy schema-v1 validator.
  audit      Adversarial pass over a built map (is it SELF-CONTRADICTORY?): L1
             deterministic contradiction checks + an L2 grounding worklist.
  render     Render a map to a generated view: model → HTML viewer or → the
             committed markdown view (picked by the output extension).
  assemble   Merge build agents' structured-row fragments into the canonical
             project-map.json (+ generated views).
  dump       Emit the parsed model as JSON — whole, or a fixed slice (--id /
             --record / --edges / --members). Read-only lookups over the model.
  convert    One-time migration: a schema-v1 project-map.md → project-map.json.

The method-quality regression eval is a separate command: `coyodex-eval` (see eval/).

Global:
  --version  Print the coyodex version and exit.
  -h/--help  Show this help and exit.

Run `coyodex <command> --help` for command-specific options."""


def _default_map(argv: list[str]) -> list[str]:
    """When no positional map is given, default to the v2 source (`.coyodex/project-map.json`)
    when it exists, else the legacy markdown map — so `coyodex validate` / `audit` keep working
    bare in both migrated and un-migrated repos."""
    from pathlib import Path
    flags_with_value = {"--repo"}
    expect_value = False
    for a in argv:
        if expect_value:
            expect_value = False
        elif a in flags_with_value:
            expect_value = True
        elif not a.startswith("-"):
            return argv  # an explicit map was given
    default = (".coyodex/project-map.json" if Path(".coyodex/project-map.json").exists()
               else ".coyodex/project-map.md")
    return argv + [default]


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
        # validate_model dispatches a `.md` argument to the legacy schema-v1 validator. With no
        # positional map, prefer the v2 source when it exists, else the legacy default.
        from coyodex import validate_model  # stdlib-only
        return validate_model.main(_default_map(rest))
    if cmd == "audit":
        from coyodex import audit_model  # stdlib-only; dispatches .md to the legacy audit
        return audit_model.main(_default_map(rest))
    if cmd == "render":
        from coyodex.viewer import render  # stdlib-only
        return render.main(rest)
    if cmd == "assemble":
        from coyodex import assemble  # stdlib-only
        return assemble.main(rest)
    if cmd == "dump":
        from coyodex import dump  # stdlib-only; v2-only, defaults to .coyodex/project-map.json
        return dump.main(rest)
    if cmd == "convert":
        from coyodex import convert_md  # stdlib-only
        return convert_md.main(rest)

    print(f"coyodex: unknown command '{cmd}'\n", file=sys.stderr)
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
