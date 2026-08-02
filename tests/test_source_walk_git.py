#!/usr/bin/env python3
"""Which files the source walk enumerates in a git repo (`preindex_lib._git_rels`).

The walk decides what the map is measured and covered against, so what it MISSES is invisible
to every check downstream. Two properties are pinned here:

  * the file set is TRACKED + UNTRACKED-not-ignored — the same pair of questions the change
    analysis asks, so a new file that was never `git add`-ed cannot be visible to `analyze` as
    an addition while being absent from the sizing and the coverage checks;
  * ignoring is git's answer, never ours — a nested `.gitignore` and `.git/info/exclude` hold
    here without a line of pattern code in coyodex, which is the reason to shell out at all.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from coyodex.preindex_lib import iter_source_files

# The developer's own git config is NOT part of what these tests assert: a global `core.excludesFile`
# would silently change which files git reports, so every repo here is built in isolation (the same
# envelope `test_impact` uses). `.git/info/exclude` is per-repo and still applies — which is the
# point of the test that pins it.
_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


# --- builders -------------------------------------------------------------------
def make_git_repo(tmp: Path) -> Path:
    """A repo with ONE committed file, `src/tracked.py`. Everything else a test adds on top."""
    root = tmp / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "tracked.py").write_text("def tracked():\n    return 1\n")
    run_git(root, "init", "-q")
    run_git(root, "add", "-A")
    run_git(root, "commit", "-qm", "init")
    # Resolved: macOS temp dirs live under a /var -> /private/var symlink and the walk resolves
    # its root, so an unresolved root here makes `relative_to` raise.
    return root.resolve()


def run_git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=60,
                   env=_ENV)


def write(root: Path, rel: str, text: str = "def f():\n    return 1\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def walked(root: Path) -> set[str]:
    root = root.resolve()
    return {p.relative_to(root).as_posix() for p in iter_source_files(root).files}


# --- the file set ---------------------------------------------------------------
def test_a_file_never_added_to_git_is_still_walked():
    """The hole this rule closes: `git ls-files` alone lists only the index, so a file the author
    just created was measured as if it did not exist — while `analyze` reported it as an addition."""
    with tempfile.TemporaryDirectory() as td:
        root = make_git_repo(Path(td))
        write(root, "src/brand_new.py")
        assert walked(root) == {"src/tracked.py", "src/brand_new.py"}


def test_a_staged_but_uncommitted_file_is_walked():
    with tempfile.TemporaryDirectory() as td:
        root = make_git_repo(Path(td))
        write(root, "src/staged.py")
        run_git(root, "add", "src/staged.py")
        assert "src/staged.py" in walked(root)


def test_a_gitignored_file_is_not_walked():
    with tempfile.TemporaryDirectory() as td:
        root = make_git_repo(Path(td))
        write(root, ".gitignore", "generated/\n")
        write(root, "generated/out.py")
        # `.gitignore` itself is listed: the walk enumerates every authored file, not only code
        # (`validate_analysis` is what decides which of them a component must own).
        assert walked(root) == {"src/tracked.py", ".gitignore"}


def test_a_nested_gitignore_holds():
    """git applies a `.gitignore` at any depth. coyodex parses none of this — the point of asking
    git rather than re-implementing the rules is that every form of them works for free."""
    with tempfile.TemporaryDirectory() as td:
        root = make_git_repo(Path(td))
        write(root, "src/sub/.gitignore", "*.py\n!keep.py\n")
        write(root, "src/sub/hidden.py")
        write(root, "src/sub/keep.py")
        assert walked(root) == {"src/tracked.py", "src/sub/keep.py", "src/sub/.gitignore"}


def test_git_info_exclude_holds():
    """The per-clone exclude file — never committed, so a repo-shaped test is the only way to see it."""
    with tempfile.TemporaryDirectory() as td:
        root = make_git_repo(Path(td))
        write(root, ".git/info/exclude", "scratch/\n")
        write(root, "scratch/notes.py")
        assert walked(root) == {"src/tracked.py"}


def test_a_tracked_file_deleted_from_disk_is_not_returned():
    """`ls-files` lists the INDEX, so an unstaged delete stays listed. Every caller goes on to read
    the file, so a path that no longer exists would be an error or a zero-length measurement."""
    with tempfile.TemporaryDirectory() as td:
        root = make_git_repo(Path(td))
        (root / "src" / "tracked.py").unlink()
        assert walked(root) == set()


def test_a_folder_that_is_not_a_git_repo_still_walks():
    """No git to ask -> the filesystem walk, and `used_git` says so. `.gitignore` cannot apply in
    this mode; the built-in exclude list is the only narrowing."""
    with tempfile.TemporaryDirectory() as td:
        root = (Path(td) / "plain")
        (root / "src").mkdir(parents=True)
        (root / "src" / "a.py").write_text("def a():\n    return 1\n")
        result = iter_source_files(root.resolve())
        assert not result.used_git
        assert walked(root.resolve()) == {"src/a.py"}
