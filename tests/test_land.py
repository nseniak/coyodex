"""Tests for `tools/land.py`, the landing loop for a worktree branch.

Each test builds a throwaway repository: a main checkout with one commit, and a worktree on a branch
off it. The gates are whatever shell command the test passes, so a test can make "the gates" move
main under the script's feet — the case the loop exists for.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

LAND = Path(__file__).resolve().parent.parent / "tools" / "land.py"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)


def make_repo() -> tuple[Path, Path]:
    """(main checkout, worktree) — main holds one commit, the worktree's branch `feature` sits on it."""
    root = Path(tempfile.mkdtemp(prefix="land-"))
    main = root / "main"
    main.mkdir()
    run(["git", "init", "-q", "-b", "main"], main)
    for key, value in (("user.email", "t@example.com"), ("user.name", "t"), ("commit.gpgsign", "false")):
        run(["git", "config", key, value], main)
    make_commit(main, "a.txt", "one\n", "one")
    worktree = root / "wt"
    run(["git", "worktree", "add", "-q", "-b", "feature", str(worktree)], main)
    return main, worktree


def make_commit(checkout: Path, name: str, text: str, message: str) -> None:
    (checkout / name).write_text(text, encoding="utf-8")
    run(["git", "add", name], checkout)
    run(["git", "commit", "-qm", message], checkout)


def head(checkout: Path) -> str:
    return run(["git", "rev-parse", "HEAD"], checkout).stdout.strip()


def land(worktree: Path, *extra: str, gates: str = "true") -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(LAND), "--gates", gates, *extra], cwd=worktree,
                          capture_output=True, text=True)


def test_a_branch_ahead_of_main_lands_and_the_main_checkouts_files_move_with_the_ref() -> None:
    main, worktree = make_repo()
    make_commit(worktree, "b.txt", "two\n", "two")
    done = land(worktree)
    assert done.returncode == 0, done.stderr
    assert head(main) == head(worktree)
    assert (main / "b.txt").read_text() == "two\n"          # the file, not just the ref
    assert run(["git", "status", "--porcelain"], main).stdout == ""


def test_main_that_moved_is_merged_into_the_branch_first_then_landed() -> None:
    main, worktree = make_repo()
    make_commit(worktree, "b.txt", "two\n", "two")
    make_commit(main, "c.txt", "three\n", "three")
    done = land(worktree)
    assert done.returncode == 0, done.stderr
    assert "a new merge commit" in done.stdout
    assert head(main) == head(worktree)
    assert (main / "b.txt").exists() and (main / "c.txt").exists()


def test_a_conflict_stops_with_the_file_named_and_the_merge_left_to_resolve() -> None:
    main, worktree = make_repo()
    make_commit(worktree, "a.txt", "mine\n", "mine")
    make_commit(main, "a.txt", "theirs\n", "theirs")
    before = head(main)
    done = land(worktree)
    assert done.returncode == 2
    assert "a.txt" in done.stderr and "resolve" in done.stderr
    assert head(main) == before
    assert (worktree / ".git").exists()
    assert run(["git", "diff", "--name-only", "--diff-filter=U"], worktree).stdout.strip() == "a.txt"


def test_main_moving_while_the_gates_run_is_merged_in_again_and_then_lands() -> None:
    """The gates command moves main exactly once, the first time it runs."""
    main, worktree = make_repo()
    make_commit(worktree, "b.txt", "two\n", "two")
    marker = worktree / "moved.once"
    gates = f"test -e {marker} || (touch {marker} && git -C {main} commit -q --allow-empty -m moved)"
    done = land(worktree, gates=gates)
    marker.unlink()
    assert done.returncode == 0, done.stderr
    assert "moved while the gates ran" in done.stdout
    assert head(main) == head(worktree)
    assert "moved" in run(["git", "log", "--oneline"], main).stdout


def test_main_that_keeps_moving_gives_up_after_the_attempts() -> None:
    main, worktree = make_repo()
    make_commit(worktree, "b.txt", "two\n", "two")
    done = land(worktree, "--attempts", "2", gates=f"git -C {main} commit -q --allow-empty -m moved")
    assert done.returncode == 5
    assert "kept moving" in done.stderr
    assert not (main / "b.txt").exists()


def test_failing_gates_land_nothing() -> None:
    main, worktree = make_repo()
    before = head(main)
    make_commit(worktree, "b.txt", "two\n", "two")
    done = land(worktree, gates="false")
    assert done.returncode == 3
    assert head(main) == before


def test_a_dirty_worktree_and_the_main_checkout_itself_are_refused() -> None:
    main, worktree = make_repo()
    (worktree / "loose.txt").write_text("x", encoding="utf-8")
    assert land(worktree).returncode == 1
    (worktree / "loose.txt").unlink()
    assert land(main).returncode == 1
