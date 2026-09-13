"""The rename hint: a folder that still holds a `.coyodex/` map is told what changed and what to do,
by the CLI's default-map lookup and by the viewer's project intake alike (one text, in the model)."""
from __future__ import annotations

import contextlib
import io
import tempfile
from pathlib import Path

from coyomap.cli import _default_map
from coyomap.model import old_map_folder_hint


def make_folder(td: str, *, old: bool, new: bool) -> Path:
    root = Path(td)
    if old:
        (root / ".coyodex").mkdir()
        (root / ".coyodex" / "project-map.json").write_text("{}")
    if new:
        (root / ".coyomap").mkdir()
        (root / ".coyomap" / "project-map.json").write_text("{}")
    return root


def test_the_hint_names_the_folder_to_rename_and_the_field_to_set():
    with tempfile.TemporaryDirectory() as td:
        hint = old_map_folder_hint(make_folder(td, old=True, new=False))
    assert hint and ".coyodex/" in hint and ".coyomap/" in hint and '"coyomap-map"' in hint


def test_no_hint_for_a_plain_folder_or_an_already_renamed_one():
    with tempfile.TemporaryDirectory() as td:
        assert old_map_folder_hint(make_folder(td, old=False, new=False)) is None
    with tempfile.TemporaryDirectory() as td:
        assert old_map_folder_hint(make_folder(td, old=True, new=True)) is None


def test_the_default_map_lookup_prints_the_hint_and_still_defaults():
    with tempfile.TemporaryDirectory() as td:
        root = make_folder(td, old=True, new=False)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            argv = _default_map(["--repo", "x"], cwd=root)
    assert argv[-1] == ".coyomap/project-map.json"
    assert "coyodex is now coyomap" in err.getvalue()


def test_an_explicit_map_path_gets_no_hint():
    with tempfile.TemporaryDirectory() as td:
        root = make_folder(td, old=True, new=False)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            _default_map(["some/map.json"], cwd=root)
    assert err.getvalue() == ""
