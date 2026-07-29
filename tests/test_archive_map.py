#!/usr/bin/env python3
"""Tests for `internal/scripts/archive_map.py` — moving a map aside for a from-scratch rebuild.

This script moves a repo's only copy of its map, so the tests are about not losing it: the archive
never nests inside itself, `.gitignore` stays where the next assemble expects it, an interrupted run
puts everything back, and nothing is ever deleted.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_archive_map.py
    pytest tests/test_archive_map.py
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "internal" / "scripts" / "archive_map.py"
_spec = importlib.util.spec_from_file_location("archive_map", _SCRIPT)
assert _spec and _spec.loader
archive_map = importlib.util.module_from_spec(_spec)
sys.modules["archive_map"] = archive_map
_spec.loader.exec_module(archive_map)


def make_repo(tmp: str, *, archives: tuple[str, ...] = ()) -> Path:
    """A repo whose `.coyodex/` holds a full map plus any pre-existing archives."""
    root = Path(tmp)
    cy = root / ".coyodex"
    (cy / "build-fragments").mkdir(parents=True)
    (cy / "build-fragments" / "header.json").write_text("{}")
    for name in ("project-map.json", "project-map.md", "preindex.json", "provenance.json"):
        (cy / name).write_text("x")
    (cy / ".gitignore").write_text("build-fragments/\n")
    for a in archives:
        (cy / a).mkdir()
    return root


def test_the_first_archive_is_unsuffixed_then_numbered():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp)
        dest, _ = archive_map.archive(root)
        assert dest is not None and dest.name == ".old-ignore"
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp, archives=(".old-ignore", ".old-ignore-2"))
        dest, _ = archive_map.archive(root)
        assert dest is not None and dest.name == ".old-ignore-3"


def test_numbering_is_not_lexicographic():
    # ".old-ignore-9" sorts after ".old-ignore-10" as text; the next free NUMBER is 11.
    with tempfile.TemporaryDirectory() as tmp:
        names = (".old-ignore",) + tuple(f".old-ignore-{n}" for n in range(2, 11))
        root = make_repo(tmp, archives=names)
        dest, _ = archive_map.archive(root)
        assert dest is not None and dest.name == ".old-ignore-11"


def test_a_gap_is_left_alone_so_the_number_still_means_recency():
    """Always highest + 1 — filling a gap would make the number lie about age.

    With `.old-ignore` and `-3` present, reusing `-2` would file the NEWEST map between two older
    ones. The common cleanup is worse: prune the oldest archives and the next map lands in
    `.old-ignore`, the name that reads as "the first one", so the sequence reads backwards."""
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp, archives=(".old-ignore", ".old-ignore-3"))
        dest, _ = archive_map.archive(root)
        assert dest is not None and dest.name == ".old-ignore-4"


def test_pruning_the_oldest_archives_never_recycles_their_names():
    # deleting the two oldest must not hand their names to the newest map
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp, archives=(".old-ignore-3", ".old-ignore-4"))
        dest, _ = archive_map.archive(root)
        assert dest is not None and dest.name == ".old-ignore-5"


def test_a_hand_named_sibling_does_not_break_the_numbering():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp, archives=(".old-ignore", ".old-ignore-broken"))
        dest, _ = archive_map.archive(root)
        assert dest is not None and dest.name == ".old-ignore-2"


def test_the_whole_map_moves_and_nothing_is_deleted():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp)
        dest, entries = archive_map.archive(root)
        assert dest is not None
        assert {p.name for p in entries} == {
            "build-fragments", "project-map.json", "project-map.md", "preindex.json",
            "provenance.json"}
        for name in ("project-map.json", "provenance.json"):
            assert (dest / name).is_file()
        assert (dest / "build-fragments" / "header.json").is_file()   # directories move whole
        # …and the working tree now reads as "no baseline", which is what makes the next run BUILD
        assert not (root / ".coyodex" / "project-map.json").exists()


def test_the_gitignore_stays_put():
    # coyodex writes `.coyodex/.gitignore` and the next assemble expects it; archiving it would
    # un-ignore build-fragments/ for the following build.
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp)
        archive_map.archive(root)
        assert (root / ".coyodex" / ".gitignore").read_text() == "build-fragments/\n"


def test_archives_are_never_nested_inside_each_other():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp, archives=(".old-ignore",))
        (root / ".coyodex" / ".old-ignore" / "project-map.json").write_text("old")
        dest, entries = archive_map.archive(root)
        assert dest is not None
        assert not any(p.name.startswith(".old-ignore") for p in entries)
        assert (root / ".coyodex" / ".old-ignore" / "project-map.json").read_text() == "old"


def test_an_already_clear_map_is_not_an_error():
    # the state a from-scratch build wants — running twice must be harmless, not a failure
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp)
        archive_map.archive(root)
        dest, entries = archive_map.archive(root)
        assert dest is None and entries == []
        assert archive_map.main([str(root)]) == 0


def test_dry_run_writes_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp)
        dest, entries = archive_map.archive(root, dry_run=True)
        assert dest is not None and entries
        assert not dest.exists()
        assert (root / ".coyodex" / "project-map.json").is_file()


def test_a_failed_move_puts_everything_back():
    """A half-finished archive is worse than none: the map would be split across two directories."""
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp)
        real_move = archive_map.shutil.move
        calls = {"n": 0}

        def flaky(src: str, dst: str) -> object:
            calls["n"] += 1
            if calls["n"] == 3:
                raise OSError("disk full")
            return real_move(src, dst)

        archive_map.shutil.move = flaky
        try:
            with pytest.raises(OSError):
                archive_map.archive(root)
        finally:
            archive_map.shutil.move = real_move
        cy = root / ".coyodex"
        assert (cy / "project-map.json").is_file() and (cy / "build-fragments").is_dir()
        assert not (cy / ".old-ignore").exists()          # the empty archive is cleaned up too


def test_a_missing_coyodex_dir_reports_instead_of_crashing():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(FileNotFoundError):
            archive_map.archive(Path(tmp))
        assert archive_map.main([tmp]) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
