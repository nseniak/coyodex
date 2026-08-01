#!/usr/bin/env python3
"""Tests for `coyodex-eval archive` — moving a map aside for a from-scratch rebuild.

This command moves a repo's only copy of its map, so the tests are about not losing it: the archive
never nests inside itself, `.gitignore` stays where the next assemble expects it, an interrupted run
puts everything back, and nothing is ever deleted.

Run either way (needs an editable install: `make deps`):
    python3 eval/tests/test_archive.py
    pytest eval/tests/test_archive.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "eval" / "tools"))

# A plain import now. This used to be an `importlib.util.spec_from_file_location` dance against an
# absolute path, because the module was a loose script under `eval/scripts/` rather than part of a
# package — the same pathness that made every caller spell the path out by hand.
from coyodex_eval import archive as archive_map  # noqa: E402


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
        (cy / archive_map.ARCHIVE_DIR / a).mkdir(parents=True)
    return root


def test_archives_are_numbered_from_one_inside_the_container():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp)
        dest, _ = archive_map.archive(root)
        assert dest is not None and dest.name == "0001"
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp, archives=("0001", "0002"))
        dest, _ = archive_map.archive(root)
        assert dest is not None and dest.name == "0003"


def test_numbering_is_numeric_and_zero_padding_makes_text_order_match():
    """The trap the unpadded convention carried: `-9` sorted after `-10` as text, and a consumer got it
    wrong for real (a baseline picker sorted on name length and chose the wrong archive in 28 of 40
    trials). Padding removes it — so assert BOTH that the next number is right and that a plain
    lexical sort of the names now agrees with a numeric one."""
    with tempfile.TemporaryDirectory() as tmp:
        names = tuple(f"{n:04d}" for n in range(1, 11))
        root = make_repo(tmp, archives=names)
        dest, _ = archive_map.archive(root)
        assert dest is not None and dest.name == "0011"
        on_disk = [d.name for d in (root / ".coyodex" / archive_map.ARCHIVE_DIR).iterdir()
                   if d.is_dir()]
        assert sorted(on_disk) == sorted(on_disk, key=int)


def test_a_gap_is_left_alone_so_the_number_still_means_recency():
    """Always highest + 1 — filling a gap would make the number lie about age.

    With `0001` and `0003` present, reusing `0002` would file the NEWEST map between two older
    ones. The common cleanup is worse: prune the oldest archives and the next map lands in
    `0001`, the name that reads as "the first one", so the sequence reads backwards."""
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp, archives=("0001", "0003"))
        dest, _ = archive_map.archive(root)
        assert dest is not None and dest.name == "0004"


def test_pruning_the_oldest_archives_never_recycles_their_names():
    # deleting the two oldest must not hand their names to the newest map
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp, archives=("0003", "0004"))
        dest, _ = archive_map.archive(root)
        assert dest is not None and dest.name == "0005"


def test_a_hand_named_sibling_does_not_break_the_numbering():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo(tmp, archives=("0001", "broken"))
        dest, _ = archive_map.archive(root)
        assert dest is not None and dest.name == "0002"


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
        root = make_repo(tmp, archives=("0001",))
        (root / ".coyodex" / archive_map.ARCHIVE_DIR / "0001" / "project-map.json").write_text("old")
        dest, entries = archive_map.archive(root)
        assert dest is not None
        assert not any(p.name == archive_map.ARCHIVE_DIR for p in entries)
        assert (root / ".coyodex" / archive_map.ARCHIVE_DIR / "0001" / "project-map.json").read_text() == "old"


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
        assert not (cy / archive_map.ARCHIVE_DIR).exists()          # the empty archive is cleaned up too


def test_a_missing_coyodex_dir_reports_instead_of_crashing():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(FileNotFoundError):
            archive_map.archive(Path(tmp))
        assert archive_map.main([tmp]) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
