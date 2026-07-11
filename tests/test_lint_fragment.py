"""Tests for `coyodex lint-fragment` — the per-fragment self-check (B1)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyodex import lint_fragment
from coyodex.assemble import load_fragment


def make_fragment(obj: dict) -> object:
    """A partial model built from a fragment dict, exactly as `assemble`/`lint-fragment` load it."""
    return load_fragment(json.dumps(obj), "frag")


def make_fragment_file(tmp: Path, name: str, obj: dict) -> Path:
    p = tmp / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_lint_reports_anchor_and_extra_in_one_pass():
    # A bad anchor AND a forbidden `loc` extra both surface from a single lint (not one-at-a-time).
    m = make_fragment({"components": [{"id": "C1", "name": "X", "source": "[bad](x/)",
                                       "extra": {"loc": 5}}]})
    problems = lint_fragment.lint_fragment_problems(m, None)
    assert any("not a valid anchor" in p for p in problems)
    assert any("loc" in p for p in problems)


def test_lint_clean_fragment_has_no_problems():
    m = make_fragment({"components": [{"id": "C1", "name": "X", "source": "src/x.py:3"}]})
    assert lint_fragment.lint_fragment_problems(m, None) == []


def test_lint_extensionless_anchor_is_accepted():
    # A2: an extensionless ops file with a line is a valid anchor, so lint must not reject it.
    m = make_fragment({"deps": [{"id": "D1", "name": "img", "where_configured": "Dockerfile:1"}]})
    assert lint_fragment.lint_fragment_problems(m, None) == []


def test_lint_repo_flag_flags_missing_file():
    # With --repo, a wrong prefix / stale path is caught at the SOURCE (the anchor's file must exist).
    m = make_fragment({"components": [{"id": "C1", "name": "X", "source": "nope/x.py:3"}]})
    with tempfile.TemporaryDirectory() as td:
        problems = lint_fragment.lint_fragment_problems(m, Path(td))
    assert any("does not resolve" in p or "not" in p.lower() for p in problems)


def test_lint_repo_flag_passes_when_file_exists():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        (root / "src" / "x.py").write_text("x = 1\n", encoding="utf-8")
        m = make_fragment({"components": [{"id": "C1", "name": "X", "source": "src/x.py:1"}]})
        assert lint_fragment.lint_fragment_problems(m, root) == []


def test_lint_cli_exit_codes():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        good = make_fragment_file(tmp, "good.json", {"components": [{"id": "C1", "name": "X",
                                                                     "source": "a/b.py:1"}]})
        bad = make_fragment_file(tmp, "bad.json", {"deps": [{"id": "D1", "name": "r",
                                                             "where_configured": None}]})
        assert lint_fragment.main([str(good)]) == 0
        assert lint_fragment.main([str(bad)]) == 1  # schema error → non-zero
