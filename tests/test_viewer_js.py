#!/usr/bin/env python3
"""Syntax gate for the hand-maintained viewer frontend bundle.

viewer.js is a large, hand-edited vanilla-JS file and the repo has no JS test harness, so a stray
syntax error (an unbalanced brace, a dangling edit) would ship silently and break the whole viewer.
`node --check` parses the file without executing it — a cheap, deterministic regression guard. Skips
when node isn't installed (e.g. a Python-only CI image), so it never turns into a spurious failure.

Conventions: top-level test functions, no classes/fixtures.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

VIEWER_DIR = Path(__file__).resolve().parent.parent / "tools" / "coyodex" / "viewer"


def _node_check(js_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed — skipping viewer JS syntax gate")
    assert js_path.exists(), f"expected {js_path} to exist"
    result = subprocess.run(
        [node, "--check", str(js_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"{js_path.name} failed `node --check`:\n{result.stderr}"


def test_viewer_js_parses() -> None:
    _node_check(VIEWER_DIR / "viewer.js")
