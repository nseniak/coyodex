"""M3 server half — `api/src?at=`, worktree-read safety, impactcommits, impactsrcdiff.

The worktree-read guards are the security-sensitive piece (review finding W6/V8): `_safe_rel` alone
is not a disk-I/O guard, so these tests prove the three additional gates — realpath containment
(a tracked symlink must not escape the repo), `.git/` exclusion, and the tracked-or-untracked-
not-ignored rule (a gitignored `.env` never leaves the machine through the viewer).
Real temp git repos, explicit make_* builders, no fixtures/classes.
"""
from __future__ import annotations

import http.client
import json
import os
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from coyodex.model import to_canonical_json
from coyodex.viewer.recents import RecentsStore
from coyodex.viewer.serve import (
    Handler,
    build_projects,
    impact_commits,
    impact_file_diff,
    worktree_read,
)

from test_impact import GUILD_V1, commit, git_run, make_model


def make_served_repo(td: str) -> tuple[Path, str]:
    root = Path(td)
    pin = commit(root, {"svc/guild.py": GUILD_V1, ".gitignore": ".env\n"}, msg="pin")
    (root / ".coyodex").mkdir()
    (root / ".coyodex" / "project-map.json").write_text(to_canonical_json(make_model(pin)),
                                                        encoding="utf-8")
    return root, pin


def make_server(root: Path) -> tuple[ThreadingHTTPServer, str, int]:
    projects = build_projects([str(root)])
    slug = next(iter(projects))
    Handler.store = RecentsStore()
    Handler.projects = projects
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, slug, httpd.server_address[1]


def get(port: int, url: str) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", url)
    resp = conn.getresponse()
    return resp.status, resp.read()


# --- worktree_read guards -----------------------------------------------------------

def test_worktree_read_serves_tracked_and_untracked() -> None:
    with tempfile.TemporaryDirectory() as td:
        root, _pin = make_served_repo(td)
        (root / "svc/guild.py").write_text("edited\n", encoding="utf-8")
        assert worktree_read(root, "svc/guild.py") == b"edited\n"          # tracked, dirty
        (root / "svc/new.py").write_text("new\n", encoding="utf-8")
        assert worktree_read(root, "svc/new.py") == b"new\n"               # untracked, not ignored


def test_worktree_read_refuses_ignored_git_and_escape() -> None:
    with tempfile.TemporaryDirectory() as td:
        root, _pin = make_served_repo(td)
        (root / ".env").write_text("SECRET=1\n", encoding="utf-8")
        assert worktree_read(root, ".env") is None                          # gitignored secret
        assert worktree_read(root, ".git/config") is None                   # git internals
        assert worktree_read(root, "../outside.txt") is None                # _safe_rel
        outside = Path(td).parent / "outside-coyodex-test.txt"
        outside.write_text("out\n", encoding="utf-8")
        try:
            os.symlink(outside, root / "svc" / "link.txt")
            git_run(root, "add", "svc/link.txt")                            # tracked symlink
            assert worktree_read(root, "svc/link.txt") is None              # realpath escape
        finally:
            outside.unlink()


# --- src?at= over HTTP ---------------------------------------------------------------

def test_src_at_worktree_and_sha_frames() -> None:
    with tempfile.TemporaryDirectory() as td:
        root, pin = make_served_repo(td)
        v2 = commit(root, {"svc/guild.py": GUILD_V1.replace("return 1", "return 2")}, msg="v2")
        (root / "svc/guild.py").write_text("worktree-version\n", encoding="utf-8")
        httpd, slug, port = make_server(root)
        try:
            st, body = get(port, f"/p/{slug}/api/src?path=svc/guild.py")
            assert st == 200 and b"return 1" in body                        # default: the pin
            st, body = get(port, f"/p/{slug}/api/src?path=svc/guild.py&at={v2}")
            assert st == 200 and b"return 2" in body                        # another commit
            st, body = get(port, f"/p/{slug}/api/src?path=svc/guild.py&at=WORKTREE")
            assert st == 200 and body == b"worktree-version\n"              # the dirty tree
            st, _ = get(port, f"/p/{slug}/api/src?path=.env&at=WORKTREE")
            assert st == 404                                                # guard holds over HTTP
            st, _ = get(port, f"/p/{slug}/api/src?path=svc/guild.py&at=--flag")
            assert st == 400                                                # never reaches git argv
        finally:
            httpd.shutdown()


# --- impactcommits + impactsrcdiff ----------------------------------------------------

def test_impact_commits_lists_ancestors_and_descendants() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        commit(root, {"a.txt": "1\n"}, msg="one")
        pin = commit(root, {"a.txt": "2\n"}, msg="two")
        commit(root, {"a.txt": "3\n"}, msg="three")
        (root / ".coyodex").mkdir()
        (root / ".coyodex" / "project-map.json").write_text(
            to_canonical_json(make_model(pin)), encoding="utf-8")
        projects = build_projects([str(root)])
        proj = projects[next(iter(projects))]
        out = impact_commits(proj)
        ancestors, descendants = out["ancestors"], out["descendants"]
        assert isinstance(ancestors, list) and isinstance(descendants, list)
        assert [c["subject"] for c in ancestors][:2] == ["two", "one"]
        assert [c["subject"] for c in descendants] == ["three"]


def test_impact_file_diff_arbitrary_range() -> None:
    """The pin at NEITHER end — the existing srcdiff refuses this; impactsrcdiff serves it."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pin = commit(root, {"svc/guild.py": GUILD_V1, ".gitignore": ".env\n"}, msg="pin")
        git_run(root, "checkout", "-q", "-b", "b1")
        b1 = commit(root, {"svc/guild.py": GUILD_V1.replace("return 1", "return 10")}, msg="b1")
        git_run(root, "checkout", "-q", "-b", "b2", pin)
        b2 = commit(root, {"svc/guild.py": GUILD_V1.replace("return 1", "return 20")}, msg="b2")
        # the map goes in AFTER the branch dance (a checkout would drop a freshly-tracked map file)
        (root / ".coyodex").mkdir()
        (root / ".coyodex" / "project-map.json").write_text(
            to_canonical_json(make_model(pin)), encoding="utf-8")
        projects = build_projects([str(root)])
        proj = projects[next(iter(projects))]
        out = impact_file_diff(proj, "svc/guild.py", b1, b2)
        rows = out["rows"]
        assert isinstance(rows, list)
        texts = [r["text"] for r in rows if r["op"] != " "]
        assert any("return 10" in t for t in texts) and any("return 20" in t for t in texts)
        httpd, slug, port = make_server(root)
        try:
            st, body = get(port, f"/p/{slug}/api/impactsrcdiff?path=svc/guild.py&base={b1}&target={b2}")
            assert st == 200 and json.loads(body)["path"] == "svc/guild.py"
            st, _ = get(port, f"/p/{slug}/api/impactsrcdiff?path=../x&base={b1}&target={b2}")
            assert st == 400
        finally:
            httpd.shutdown()
