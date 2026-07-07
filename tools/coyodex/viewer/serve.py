#!/usr/bin/env python3
"""Local multi-project server for coyodex maps — the file browser + code viewer's live backend.

A committed map HTML opens two ways, and the SAME file adapts to how it was opened:

  * double-clicked (``file://``) — DEGRADED mode: diagram + info panel only. Self-contained and
    portable: commit it, share it, open it on any machine with nothing installed.
  * served by THIS server (``http://localhost:PORT/<project>/``) — FULL mode: adds the file
    browser and the code viewer, both read from git AT THE MAP'S COMMIT (never the dirty working
    tree), so what you see always matches the map.

One running server serves EVERY discovered project — any folder holding ``.coyodex/project-map.json``
found under the given roots. Files come from ``git ls-tree`` / ``git show <commit>:<path>``, so the
view is a frozen snapshot of the mapped commit and local edits never leak in.

Stdlib only (``http.server`` + ``subprocess``) — no third-party import, so this stays inside the
render dependency firewall (see internal/docs/design-notes.md). ``coyodex serve`` is the entry point.
"""
from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from coyodex.model import ModelError, load_model
from coyodex.viewer.filetree import FileTreeNode, build_tree, node_path_index
from coyodex.views import model_to_graph

MAP_JSON = "project-map.json"
MAP_HTML = "project-map.html"
_DEFAULT_PORT = 8765
_MAX_DEPTH = 4  # how deep under a root to look for a `.coyodex/` project before giving up


@dataclass
class Project:
    """One served map: its slug (URL segment), repo root, the committed HTML, and the map's commit.

    ``commit`` is the SHA every git read is pinned to — ``-dirty`` stripped, since a working-tree
    marker isn't a real ref. ``tree`` caches the built file-browser tree (lazy, on first request)."""

    slug: str
    repo_root: Path
    map_json: Path
    map_html: Path
    commit: str
    tree: FileTreeNode | None = None  # cached tree (built once, on the first /api/tree)


_SHA_RE = re.compile(r"[0-9a-fA-F]{7,64}")


def _strip_dirty(commit: str) -> str:
    """Drop a ``-dirty`` suffix so the SHA is a real ref git can resolve (mirrors the viewer)."""
    return commit[:-6] if commit.endswith("-dirty") else commit


def _valid_commit(commit: str) -> bool:
    """True only for a bare hex SHA. Guards the git calls: a commit read from the map JSON that is
    empty, malformed, or (crucially) starts with ``-`` must never reach git's argv, where a leading
    dash would be parsed as a flag rather than a revision (argument injection)."""
    return bool(_SHA_RE.fullmatch(commit))


def discover_projects(roots: list[Path], max_depth: int = _MAX_DEPTH) -> dict[str, Project]:
    """Find every ``.coyodex/project-map.json`` under ``roots`` (bounded depth) → slug→Project.

    The slug is the project folder's name; on a collision a numeric suffix keeps both reachable.
    A map that won't load (missing / malformed) is skipped with a warning rather than aborting the
    whole server — one bad project shouldn't take the others down."""
    found: dict[str, Project] = {}
    seen_dirs: set[Path] = set()

    def scan(d: Path, depth: int) -> None:
        if depth > max_depth or d.name in {".git", "node_modules", ".venv"}:
            return
        cx = d / ".coyodex"
        mj = cx / MAP_JSON
        if mj.is_file():
            _register(found, seen_dirs, d.resolve(), mj)
            return  # a project root isn't nested inside another — stop descending here
        try:
            for child in sorted(d.iterdir()):
                if child.is_dir() and not child.is_symlink():
                    scan(child, depth + 1)
        except (PermissionError, OSError):
            pass

    for root in roots:
        rp = root.resolve()
        if rp.is_dir():
            scan(rp, 0)
    return found


def _register(found: dict[str, Project], seen: set[Path], repo_root: Path, map_json: Path) -> None:
    """Load a discovered map's commit and add it under a unique slug (or skip + warn on error)."""
    if repo_root in seen:
        return
    seen.add(repo_root)
    try:
        graph = model_to_graph(load_model(map_json.read_text(encoding="utf-8")))
    except (ModelError, OSError, ValueError) as e:
        print(f"coyodex serve: skipping {repo_root} — cannot load map ({e})", file=sys.stderr)
        return
    commit = _strip_dirty(str(graph.get("commit") or "").strip())
    if commit and not _valid_commit(commit):
        # A non-empty commit that isn't a bare SHA is malformed (or hostile) — refuse to register it
        # rather than let it flow into a git argv. An empty commit is fine (git reads no-op; the map
        # still serves in degraded form).
        print(f"coyodex serve: skipping {repo_root} — map commit is not a valid SHA ({commit!r})", file=sys.stderr)
        return
    base = repo_root.name or "project"
    slug, i = base, 2
    while slug in found:
        slug, i = f"{base}-{i}", i + 1
    found[slug] = Project(slug=slug, repo_root=repo_root, map_json=map_json,
                          map_html=map_json.parent / MAP_HTML, commit=commit)


# --- git reads (pinned to the map's commit) -----------------------------------------------------

def _git(repo_root: Path, args: list[str]) -> tuple[int, bytes]:
    """Run a read-only git command in ``repo_root``; return (returncode, stdout-bytes). No shell —
    args are passed as a list, so a path from the query string can't inject a command."""
    try:
        p = subprocess.run(["git", "-C", str(repo_root), *args],
                           capture_output=True, timeout=15)
        return p.returncode, p.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, b""


def git_ls_files(repo_root: Path, commit: str) -> list[str]:
    """Repo-relative posix paths tracked at ``commit`` (the map's frozen file set)."""
    if not _valid_commit(commit):  # empty or non-SHA -> no git call (see _valid_commit)
        return []
    code, out = _git(repo_root, ["ls-tree", "-r", "--name-only", commit])
    if code != 0:
        return []
    return [ln for ln in out.decode("utf-8", "replace").splitlines() if ln]


def git_blob_size(repo_root: Path, commit: str, path: str) -> int | None:
    """Byte size of the blob at ``commit:path`` — or None if it isn't a *file* there (missing, or a
    directory, which resolves to a git tree). One ``cat-file --batch-check`` gives object type + size,
    so the src route can reject an oversized blob BEFORE ``git_show`` buffers it into memory, and reject
    a directory path (whose ``git show`` would otherwise dump a bare filename listing)."""
    if not _valid_commit(commit) or not _safe_rel(path):
        return None
    try:
        p = subprocess.run(["git", "-C", str(repo_root), "cat-file",
                            "--batch-check=%(objecttype) %(objectsize)"],
                           input=f"{commit}:{path}\n".encode(), capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    parts = p.stdout.decode("utf-8", "replace").split()
    if p.returncode != 0 or len(parts) != 2 or parts[0] != "blob":  # 'tree'/'missing'/malformed -> not a file
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def git_show(repo_root: Path, commit: str, path: str) -> bytes | None:
    """Contents of ``path`` at ``commit`` (``git show <commit>:<path>``); None if it doesn't exist."""
    if not _valid_commit(commit) or not _safe_rel(path):
        return None
    code, out = _git(repo_root, ["show", f"{commit}:{path}"])
    return out if code == 0 else None


def _safe_rel(path: str) -> bool:
    """A repo-relative path with no traversal / absolute escape — the only thing we'll read."""
    if not path or path.startswith("/") or "\\" in path or "\x00" in path:
        return False
    return ".." not in Path(path).parts


def project_tree(proj: Project) -> FileTreeNode:
    """The file-browser tree for a project — git file set at the commit, overlaid with map coverage.

    Reuses the render-path tree builder (build_tree + node_path_index) so the served tree and the
    once-embedded tree are the SAME shape; only the file source differs (git vs a disk walk). Cached
    on the Project after the first build."""
    if proj.tree is not None:
        return proj.tree
    graph = model_to_graph(load_model(proj.map_json.read_text(encoding="utf-8")))
    rels = sorted(git_ls_files(proj.repo_root, proj.commit))
    proj.tree = build_tree(rels, node_path_index(graph), root_name=proj.repo_root.name)
    return proj.tree


# --- HTTP -----------------------------------------------------------------------------------------

_TEXT_MAX = 4_000_000  # refuse to stream an absurdly large blob into the browser code viewer
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _loopback_host(host: str) -> bool:
    """True if the request's Host names loopback (or is absent). Rejecting any other Host defeats a
    DNS-rebinding attack: a page on evil.com that re-points its name at 127.0.0.1 to read a victim's
    source code would still send ``Host: evil.com``, which is refused. An absent Host (HTTP/1.0, curl)
    is not a browser-driven rebinding vector, so it is allowed."""
    if not host:
        return True
    if host.startswith("["):                       # bracketed IPv6 literal: [::1] or [::1]:port
        host = host[1:host.index("]")] if "]" in host else host[1:]
    else:
        host = host.split(":", 1)[0]               # strip an optional :port
    return host in _LOOPBACK_HOSTS


def _index_html(projects: dict[str, Project]) -> bytes:
    """A plain landing page listing every served project, newest-looking first (alpha by slug)."""
    rows = "".join(
        f'<li><a href="/{quote(p.slug)}/">{html.escape(p.slug)}</a>'
        f'<span class="c">{html.escape(p.commit[:12]) or "no commit"}</span>'
        f'<span class="r">{html.escape(str(p.repo_root))}</span></li>'
        for p in sorted(projects.values(), key=lambda x: x.slug.lower())
    ) or '<li class="empty">No coyodex projects found under the served roots.</li>'
    doc = (
        "<!doctype html><meta charset=utf-8><title>coyodex maps</title>"
        "<style>body{font:15px/1.5 -apple-system,system-ui,sans-serif;margin:40px auto;max-width:760px;"
        "color:#111}h1{font-size:20px}ul{list-style:none;padding:0}li{padding:10px 12px;border:1px solid #e5e7eb;"
        "border-radius:8px;margin:8px 0;display:flex;gap:12px;align-items:baseline}"
        "a{font-weight:600;color:#4338ca;text-decoration:none}a:hover{text-decoration:underline}"
        ".c{font:12px ui-monospace,monospace;color:#6b7280}.r{margin-left:auto;font-size:12px;color:#9ca3af}"
        ".empty{color:#9ca3af;display:block}</style>"
        f"<h1>coyodex maps</h1><ul>{rows}</ul>"
    )
    return doc.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    projects: dict[str, Project] = {}  # set on the server instance's class before serve_forever

    server_version = "coyodex-serve"

    def log_message(self, format: str, *args: object) -> None:  # quieter than the default access log
        return

    def do_GET(self) -> None:
        if not _loopback_host(self.headers.get("Host", "")):  # DNS-rebinding guard
            return self._send(403, "text/plain; charset=utf-8", b"host not allowed")
        parsed = urlparse(self.path)
        parts = [unquote(p) for p in parsed.path.split("/") if p]
        if not parts:
            return self._send(200, "text/html; charset=utf-8", _index_html(self.projects))
        slug, rest = parts[0], parts[1:]
        proj = self.projects.get(slug)
        if proj is None:
            return self._send(404, "text/plain; charset=utf-8", b"unknown project")
        # /<slug>/                    -> the map HTML
        # /<slug>/project-map.html    -> the map HTML
        # /<slug>/api/health          -> mode probe + commit
        # /<slug>/api/tree            -> file-browser tree (git @ commit + coverage)
        # /<slug>/api/src?path=...    -> file text (git @ commit)
        if rest and rest[0] == "api":
            return self._api(proj, rest[1:], parse_qs(parsed.query))
        if not rest or rest == [MAP_HTML]:
            return self._send_file(proj.map_html, "text/html; charset=utf-8")
        return self._send(404, "text/plain; charset=utf-8", b"not found")

    def _api(self, proj: Project, rest: list[str], query: dict[str, list[str]]) -> None:
        if rest == ["health"]:
            return self._json({"ok": True, "project": proj.slug, "commit": proj.commit})
        if rest == ["tree"]:
            try:
                return self._json(project_tree(proj))
            except (ModelError, OSError, ValueError) as e:
                return self._send(500, "text/plain; charset=utf-8", str(e).encode("utf-8"))
        if rest == ["src"]:
            path = (query.get("path") or [""])[0]
            if not _safe_rel(path):
                return self._send(400, "text/plain; charset=utf-8", b"bad path")
            size = git_blob_size(proj.repo_root, proj.commit, path)  # size + is-it-a-file check first
            if size is None:
                return self._send(404, "text/plain; charset=utf-8", b"file not in commit")
            if size > _TEXT_MAX:  # reject BEFORE git_show buffers a huge blob into memory
                return self._send(413, "text/plain; charset=utf-8", b"file too large")
            blob = git_show(proj.repo_root, proj.commit, path)
            if blob is None:
                return self._send(404, "text/plain; charset=utf-8", b"file not in commit")
            # Served as plain text; the viewer highlights it client-side. charset best-effort utf-8.
            return self._send(200, "text/plain; charset=utf-8", blob)
        return self._send(404, "text/plain; charset=utf-8", b"unknown api")

    # --- response helpers ---
    def _json(self, obj: object) -> None:
        self._send(200, "application/json; charset=utf-8", json.dumps(obj).encode("utf-8"))

    def _send_file(self, path: Path, ctype: str) -> None:
        try:
            data = path.read_bytes()
        except OSError:
            return self._send(404, "text/plain; charset=utf-8",
                              b"map HTML not rendered yet - run: coyodex render")
        self._send(200, ctype, data)

    def _send(self, code: int, ctype: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)  # only reached from do_GET (HEAD/POST get the base handler's 501)


def serve(roots: list[Path], port: int = _DEFAULT_PORT, open_browser: bool = False) -> int:
    """Discover projects under ``roots`` and serve them until interrupted. Returns a process code."""
    projects = discover_projects(roots)
    Handler.projects = projects
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    names = ", ".join(sorted(projects)) or "(none — nothing to serve)"
    print(f"coyodex serve: {len(projects)} project(s): {names}")
    print(f"coyodex serve: listening on {url}  (Ctrl-C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\ncoyodex serve: stopped")
    finally:
        httpd.server_close()
    return 0


_USAGE = """usage: coyodex serve [ROOT ...] [--port N] [--open]

Serve every coyodex map (a folder with .coyodex/project-map.json) found under the given ROOTs
(default: the current directory). One server, all projects; files are read from git at each map's
commit. Open http://127.0.0.1:PORT/ for the project list.

  ROOT        directory to scan for projects (repeatable; default ".")
  --port N    port to listen on (default 8765)
  --open      open the project list in a browser on start
  -h/--help   show this help"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(_USAGE)
        return 0
    port, open_browser, roots = _DEFAULT_PORT, False, []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--port":
            i += 1
            if i >= len(args) or not args[i].isdigit():
                print("coyodex serve: --port needs a number", file=sys.stderr)
                return 2
            port = int(args[i])
        elif a == "--open":
            open_browser = True
        elif a.startswith("-"):
            print(f"coyodex serve: unknown option '{a}'\n\n{_USAGE}", file=sys.stderr)
            return 2
        else:
            roots.append(Path(a))
        i += 1
    return serve(roots or [Path(".")], port=port, open_browser=open_browser)


if __name__ == "__main__":
    raise SystemExit(main())
