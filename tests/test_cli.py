#!/usr/bin/env python3
"""Tests for the `coyodex` CLI dispatcher and the dependency firewall.

Stdlib-only — no pytest required. Run either way (needs an editable install: `make deps`):
    python3 tests/test_cli.py
    pytest tests/test_cli.py

The firewall: the core gate (validate + render) must import ZERO third-party packages.
tree-sitter is confined to the pre-index code path (see internal/docs/design-notes.md).
"""
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex import __version__, cli

# The core gate — none of these may pull in tree-sitter, at import time or any other.
CORE_MODULES = [
    "coyodex.validate_analysis",
    "coyodex.viewer.render",
    "coyodex.viewer.build_graph",
    "coyodex.viewer.gen_viewer",
    "coyodex.viewer.filetree",
    "coyodex.schema_v1",
]
CORE_SOURCES = ["validate_analysis.py", "schema_v1.py",
                "viewer/render.py", "viewer/build_graph.py", "viewer/gen_viewer.py", "viewer/filetree.py"]


# --- firewall -------------------------------------------------------------------
def test_core_path_does_not_import_tree_sitter() -> None:
    """A fresh interpreter importing only the core modules must not load tree-sitter."""
    code = (
        "import importlib, sys\n"
        f"for m in {CORE_MODULES!r}:\n"
        "    importlib.import_module(m)\n"
        "bad = [m for m in sys.modules if m.startswith('tree_sitter')]\n"
        "print(','.join(bad))\n"
        "sys.exit(1 if bad else 0)\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, f"firewall breach — tree-sitter loaded by core path: {r.stdout.strip()}"


def test_core_sources_have_no_tree_sitter_import() -> None:
    """Belt-and-suspenders: core source files name tree-sitter nowhere (not even lazily)."""
    pkg_dir = Path(cli.__file__).resolve().parent
    for rel in CORE_SOURCES:
        for line in (pkg_dir / rel).read_text(encoding="utf-8").splitlines():
            s = line.strip()
            assert not (s.startswith("import tree_sitter") or s.startswith("from tree_sitter")), \
                f"{rel}: core module imports tree-sitter: {line!r}"


# --- dispatch -------------------------------------------------------------------
def test_version_flag_prints_version() -> None:
    r = subprocess.run([sys.executable, "-m", "coyodex.cli", "--version"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == __version__


def test_version_flag_in_process() -> None:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main(["--version"])
    assert rc == 0
    assert buf.getvalue().strip() == __version__


def test_no_args_prints_usage() -> None:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cli.main([])
    assert rc == 0
    assert "usage: coyodex" in buf.getvalue()


def test_unknown_command_returns_2() -> None:
    assert cli.main(["bogus"]) == 2


def test_validate_dispatch_propagates_not_found() -> None:
    """`coyodex validate <missing>` routes to the validator, which returns 1 (file not found)."""
    with tempfile.TemporaryDirectory() as d:
        assert cli.main(["validate", str(Path(d) / "nope.json")]) == 1


def test_validate_md_map_is_refused() -> None:
    """A `.md` map is unsupported input: usage error (2), not a validate/audit run."""
    with tempfile.TemporaryDirectory() as d:
        assert cli.main(["validate", str(Path(d) / "nope.md")]) == 2
        assert cli.main(["audit", str(Path(d) / "nope.md")]) == 2


def test_render_dispatch_propagates_usage_error() -> None:
    """`coyodex render` with too few args routes to the renderer, which returns 2 (usage)."""
    assert cli.main(["render"]) == 2


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"ok   {fn.__name__}")
        except Exception as e:  # noqa: BLE001 — test runner reports every failure
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
