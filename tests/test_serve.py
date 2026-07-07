#!/usr/bin/env python3
"""Tests for the local map server (coyodex.viewer.serve) — the file browser + code viewer backend.

Stdlib-only — no pytest required. Run either way (needs an editable install: `make deps`, and `git`
on PATH for the git-integration tests):
    python3 tests/test_serve.py
    pytest tests/test_serve.py

Covers the pure guards (path safety + the -dirty strip), the git reads against a REAL temp repo (no
patching — an actual `git init` + commit), project discovery over a temp directory tree using the
committed fixture map, and the git-backed file-browser tree.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from coyodex.viewer.filetree import FileTreeNode
from coyodex.viewer.serve import (
    Project,
    _loopback_host,
    _safe_rel,
    _strip_dirty,
    _valid_commit,
    discover_projects,
    git_blob_size,
    git_ls_files,
    git_show,
    project_tree,
)

_FIXTURE_MAP = Path(__file__).parent / "fixtures" / "mcpolis-project-map.json"


# --- builders (no fixtures; explicit make_* helpers) ----------------------------
def make_git_repo(root: Path, files: dict[str, str]) -> str:
    """Init a git repo at `root`, write + commit `files` (path -> text), return the commit SHA."""
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    run = lambda *a: subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True, env=env)
    run("init", "-q")
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "init")
    out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, env=env)
    return out.stdout.decode().strip()


def make_project_dir(parent: Path, name: str) -> Path:
    """Create `parent/name` with a `.coyodex/project-map.json` (the committed fixture) inside."""
    d = parent / name
    (d / ".coyodex").mkdir(parents=True)
    shutil.copy(_FIXTURE_MAP, d / ".coyodex" / "project-map.json")
    return d


# --- pure guards ----------------------------------------------------------------
def test_strip_dirty() -> None:
    assert _strip_dirty("abc123-dirty") == "abc123"
    assert _strip_dirty("abc123") == "abc123"
    assert _strip_dirty("") == ""


def test_valid_commit() -> None:
    assert _valid_commit("e5cec8b")                       # short SHA
    assert _valid_commit("a" * 40)                        # full SHA
    assert not _valid_commit("")                          # empty
    assert not _valid_commit("-x")                        # leading dash -> would be a git flag
    assert not _valid_commit("--output=/tmp/x")           # flag smuggling attempt
    assert not _valid_commit("HEAD")                      # a ref name, not a bare SHA
    assert not _valid_commit("e5cec8b:../evil")           # not a bare SHA


def test_loopback_host() -> None:
    assert _loopback_host("")                             # absent Host (curl / HTTP1.0)
    assert _loopback_host("127.0.0.1:8765")
    assert _loopback_host("localhost:8765")
    assert _loopback_host("[::1]:8765")
    assert _loopback_host("localhost")
    assert not _loopback_host("evil.com")                 # DNS-rebinding target
    assert not _loopback_host("attacker.com:8765")
    assert not _loopback_host("192.168.1.10:8765")


def test_safe_rel_rejects_escapes() -> None:
    assert _safe_rel("src/app.py")
    assert _safe_rel("a/b/c.txt")
    assert not _safe_rel("")                       # empty
    assert not _safe_rel("/etc/passwd")            # absolute
    assert not _safe_rel("../../etc/passwd")       # traversal
    assert not _safe_rel("a/../../b")              # traversal mid-path
    assert not _safe_rel("a\\b")                   # backslash
    assert not _safe_rel("a\x00b")                 # null byte


# --- git reads (real temp repo, no patching) ------------------------------------
def test_git_ls_files_and_show() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sha = make_git_repo(root, {"src/app.py": "print('hi')\n", "README.md": "# hello\n"})
        assert sorted(git_ls_files(root, sha)) == ["README.md", "src/app.py"]
        assert git_show(root, sha, "src/app.py") == b"print('hi')\n"
        assert git_show(root, sha, "does/not/exist.py") is None   # missing -> None
        assert git_show(root, sha, "../escape.py") is None        # unsafe -> None (guard, no git call)


def test_git_blob_size_file_dir_and_missing() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sha = make_git_repo(root, {"src/app.py": "print('hi')\n", "README.md": "# hello\n"})
        assert git_blob_size(root, sha, "src/app.py") == len(b"print('hi')\n")  # blob -> byte size
        assert git_blob_size(root, sha, "src") is None            # a directory is a tree, not a file
        assert git_blob_size(root, sha, "nope.py") is None        # missing -> None
        assert git_blob_size(root, sha, "../escape.py") is None   # unsafe -> None (guard, no git call)


def test_git_reads_empty_commit_is_safe() -> None:
    with tempfile.TemporaryDirectory() as td:
        # No commit given -> both reads return the empty/None result rather than raising.
        assert git_ls_files(Path(td), "") == []
        assert git_show(Path(td), "", "x.py") is None


# --- discovery ------------------------------------------------------------------
def test_discover_projects_finds_maps_and_slugs() -> None:
    with tempfile.TemporaryDirectory() as td:
        parent = Path(td)
        make_project_dir(parent, "alpha")
        make_project_dir(parent, "beta")
        (parent / "empty").mkdir()  # a plain dir with no .coyodex -> ignored
        found = discover_projects([parent])
        assert set(found) == {"alpha", "beta"}
        assert found["alpha"].repo_root == (parent / "alpha").resolve()
        assert found["alpha"].map_html.name == "project-map.html"


def test_discover_projects_does_not_descend_into_project() -> None:
    with tempfile.TemporaryDirectory() as td:
        parent = Path(td)
        proj = make_project_dir(parent, "alpha")
        # A nested .coyodex inside a discovered project must NOT be registered as a second project.
        (proj / "sub").mkdir()
        (proj / "sub" / ".coyodex").mkdir()
        shutil.copy(_FIXTURE_MAP, proj / "sub" / ".coyodex" / "project-map.json")
        found = discover_projects([parent])
        assert set(found) == {"alpha"}  # the nested one is below the stop point


def test_discover_projects_slug_collision() -> None:
    with tempfile.TemporaryDirectory() as td:
        parent = Path(td)
        make_project_dir(parent / "one", "app")   # parent/one/app
        make_project_dir(parent / "two", "app")   # parent/two/app  -> same folder name
        (parent / "one").mkdir(exist_ok=True)
        found = discover_projects([parent])
        assert len(found) == 2
        assert "app" in found and "app-2" in found  # collision disambiguated


# --- git-backed file-browser tree -----------------------------------------------
def test_project_tree_from_git() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sha = make_git_repo(root, {"src/app.py": "x = 1\n", "docs/readme.md": "hi\n"})
        (root / ".coyodex").mkdir()
        shutil.copy(_FIXTURE_MAP, root / ".coyodex" / "project-map.json")
        proj = Project(slug=root.name, repo_root=root, map_json=root / ".coyodex" / "project-map.json",
                       map_html=root / ".coyodex" / "project-map.html", commit=sha)
        tree = project_tree(proj)
        assert tree["name"] == root.name and tree["dir"]
        paths = _all_paths(tree)
        assert "src/app.py" in paths and "docs/readme.md" in paths  # the committed git files
        assert proj.tree is not None  # cached on the Project after the first build


def _all_paths(node: FileTreeNode) -> set[str]:
    out = {node["path"]} if not node["dir"] else set()
    for c in node["children"]:
        out |= _all_paths(c)
    return out


# --- runner ---------------------------------------------------------------------
if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
