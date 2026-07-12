"""Integration tests for the git-diff producers + /api/diff projection (serve.py + diffmap).

Uses a REAL temp git repo with several commits (no patching), mirroring test_serve.py. Exercises
resolve_ref safety, diff_changes for both a commit range and the working tree, and project_diff for
direction A (map at the older end) and direction B (map at the newer end). Stdlib-only; explicit
make_* builders, no fixtures/classes.
"""
from __future__ import annotations

import http.client
import json
import subprocess
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from coyodex.model import Component, ProjectModel, to_canonical_json
from coyodex.viewer.diffmap import WORKTREE
from coyodex.viewer.recents import RecentsStore
from coyodex.viewer.serve import (
    Handler,
    build_projects,
    diff_changes,
    load_project,
    project_diff,
    resolve_ref,
)

_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


# --- builders -------------------------------------------------------------------
def git_run(root: Path, *a: str) -> None:
    subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True, env=_ENV)


def git_sha(root: Path) -> str:
    out = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True,
                         capture_output=True, env=_ENV)
    return out.stdout.decode().strip()


def write_files(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def commit(root: Path, files: dict[str, str], removed: list[str] | None = None, msg: str = "c") -> str:
    if not (root / ".git").exists():
        git_run(root, "init", "-q")
    write_files(root, files)
    for rel in removed or []:
        (root / rel).unlink()
    git_run(root, "add", "-A")
    git_run(root, "commit", "-q", "-m", msg)
    return git_sha(root)


def write_map(root: Path, sha: str, components: list[Component]) -> None:
    """Write a minimal .coyodex/project-map.json pinned at `sha`."""
    (root / ".coyodex").mkdir(parents=True, exist_ok=True)
    model = ProjectModel(title="t", commit=sha, components=components)
    (root / ".coyodex" / "project-map.json").write_text(to_canonical_json(model), encoding="utf-8")


# --- resolve_ref safety ---------------------------------------------------------
def test_resolve_ref_worktree_passthrough() -> None:
    with tempfile.TemporaryDirectory() as td:
        assert resolve_ref(Path(td), WORKTREE) == WORKTREE


def test_resolve_ref_rejects_leading_dash() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        commit(root, {"a.py": "1\n"})
        assert resolve_ref(root, "--all") is None            # would be a git flag


def test_resolve_ref_resolves_head() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sha = commit(root, {"a.py": "1\n"})
        assert resolve_ref(root, "HEAD") == sha


def test_resolve_ref_unknown_ref_is_none() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        commit(root, {"a.py": "1\n"})
        assert resolve_ref(root, "nope/deadbeef") is None


# --- diff_changes ---------------------------------------------------------------
def test_diff_changes_commit_range() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        y = commit(root, {"src/a.py": "1\n", "src/b.py": "b\n"})
        x = commit(root, {"src/a.py": "1\n2\n", "src/c.py": "c\n"}, removed=["src/b.py"])
        changes = diff_changes(root, y, x)
        assert changes is not None
        by_path = {c.path: c.status for c in changes}
        assert by_path == {"src/a.py": "M", "src/c.py": "A", "src/b.py": "D"}


def test_diff_changes_worktree_includes_untracked() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        x = commit(root, {"src/a.py": "1\n"})
        write_files(root, {"src/a.py": "1\n2\n", "src/untracked.py": "u\n"})  # edit + new, uncommitted
        changes = diff_changes(root, x, WORKTREE)
        assert changes is not None
        by_path = {c.path: c.status for c in changes}
        assert by_path == {"src/a.py": "M", "src/untracked.py": "A"}


# --- project_diff: direction B (older Y -> pin X, map at the newer end) ----------
def test_project_diff_direction_b_retrospective() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        y = commit(root, {"src/a.py": "1\n", "src/b.py": "b\n"})
        x = commit(root, {"src/a.py": "1\n2\n", "src/c.py": "c\n"}, removed=["src/b.py"])
        # Map pinned at X: C1 (a.py, changed since Y), C3 (c.py, new since Y). No element for deleted b.py.
        write_map(root, x, [Component(id="C1", name="C1", source="src/a.py:1"),
                            Component(id="C3", name="C3", source="src/c.py:1")])
        proj = load_project(str(root))
        assert proj is not None
        out = project_diff(proj, y, x)
        assert out["direction"] == "B" and out["mapSide"] == "target"
        assert out["elements"] == {"C1": "modified", "C3": "created"}
        assert out["counts"] == {"files": 3, "created": 1, "modified": 1, "deleted": 0}


# --- project_diff: direction A (pin X -> working tree, map at the older end) -----
def test_project_diff_direction_a_since_map_default() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        x = commit(root, {"src/a.py": "1\n", "src/c.py": "c\n"})
        write_map(root, x, [Component(id="C1", name="C1", source="src/a.py:1"),
                            Component(id="C3", name="C3", source="src/c.py:1")])
        # Dirty tree: edit a.py, delete c.py, add an untracked file with no element.
        write_files(root, {"src/a.py": "1\n2\n"})
        (root / "src/c.py").unlink()
        write_files(root, {"src/new.py": "n\n"})
        proj = load_project(str(root))
        assert proj is not None
        out = project_diff(proj, proj.commit, WORKTREE)   # default range = since the map, incl. dirty
        assert out["direction"] == "A" and out["mapSide"] == "base"
        assert out["elements"] == {"C1": "modified", "C3": "deleted"}   # new.py has no element -> absent
        counts = out["counts"]
        assert isinstance(counts, dict)
        assert counts["deleted"] == 1 and counts["modified"] == 1


# --- project_diff: guard rails --------------------------------------------------
def test_project_diff_rejects_range_without_pin() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        y = commit(root, {"a.py": "1\n"})
        m = commit(root, {"a.py": "2\n"})
        x = commit(root, {"a.py": "3\n"})
        write_map(root, x, [Component(id="C1", name="C1", source="a.py:1")])
        proj = load_project(str(root))
        assert proj is not None
        # y..m has the pin (x) at neither end -> rejected.
        raised = False
        try:
            project_diff(proj, y, m)
        except ValueError:
            raised = True
        assert raised


# --- HTTP dispatch (real server, real git) --------------------------------------
def _http_get(port: int, path: str) -> tuple[int, str, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", path)
        r = conn.getresponse()
        return r.status, r.getheader("Content-Type") or "", r.read()
    finally:
        conn.close()


def test_http_diff_route() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        y = commit(root, {"src/a.py": "1\n", "src/b.py": "b\n"})
        x = commit(root, {"src/a.py": "1\n2\n", "src/c.py": "c\n"}, removed=["src/b.py"])
        write_map(root, x, [Component(id="C1", name="C1", source="src/a.py:1"),
                            Component(id="C3", name="C3", source="src/c.py:1")])
        commit(root, {}, msg="commit the map")   # map lives in git; proj.commit still reads X from JSON
        projects = build_projects([str(root)])
        slug = next(iter(projects))
        Handler.store = RecentsStore()
        Handler.projects = projects
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            port = httpd.server_address[1]
            code, ctype, body = _http_get(port, f"/p/{slug}/api/diff?base={y}&target={x}")
            assert code == 200 and "application/json" in ctype
            data = json.loads(body)
            assert data["direction"] == "B" and data["elements"] == {"C1": "modified", "C3": "created"}
            # a range that doesn't include the map's pin -> 400 (user input problem)
            assert _http_get(port, f"/p/{slug}/api/diff?base={y}&target={y}")[0] == 400
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    import sys

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
    sys.exit(0)
