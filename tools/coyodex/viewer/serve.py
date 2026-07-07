#!/usr/bin/env python3
"""Local multi-project server for coyodex maps — the file browser + code viewer's live backend.

A committed map HTML opens two ways, and the SAME file adapts to how it was opened:

  * double-clicked (``file://``) — DEGRADED mode: diagram + info panel only. Self-contained and
    portable: commit it, share it, open it on any machine with nothing installed.
  * served by THIS server (``http://localhost:PORT/p/<project>/``) — FULL mode: adds the file
    browser and the code viewer, both read from git AT THE MAP'S COMMIT (never the dirty working
    tree), so what you see always matches the map.

The server does NOT scan the disk. You pick a project folder (one holding ``.coyodex/project-map.json``)
through the landing page's built-in folder browser; the choice is remembered in a small recents file
(``~/.coyodex/serve-recents.json``). On the next start the recents are shown, each openable or
removable. Files come from ``git ls-tree`` / ``git show <commit>:<path>``, so the view is a frozen
snapshot of the mapped commit and local edits never leak in.

Stdlib only (``http.server`` + ``subprocess``) — no third-party import, so this stays inside the
render dependency firewall (see internal/docs/design-notes.md). ``coyodex serve`` is the entry point.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from coyodex.model import ModelError, load_model
from coyodex.viewer.filetree import FileTreeNode, build_tree, node_path_index
from coyodex.views import model_to_graph

MAP_JSON = "project-map.json"
MAP_HTML = "project-map.html"
_DEFAULT_PORT = 8765
_RECENTS_PATH = Path.home() / ".coyodex" / "serve-recents.json"
_STATE_LOCK = threading.Lock()  # guards recents mutation + the derived projects map


# --- recents store (persisted list of chosen project folders) -----------------------------------

class RecentsStore:
    """The ordered (most-recent first) list of project folders the user has opened, persisted to a
    small JSON file. No scanning — the list only grows when the user opens a folder in the UI."""

    def __init__(self, path: Path = _RECENTS_PATH) -> None:
        self.path = path
        self.folders: list[str] = []
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.folders = []
            return
        folders = data.get("folders") if isinstance(data, dict) else None
        self.folders = [f for f in folders if isinstance(f, str)] if isinstance(folders, list) else []

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"folders": self.folders}, indent=2), encoding="utf-8")
        except OSError as e:
            print(f"coyodex serve: could not save recents to {self.path} ({e})", file=sys.stderr)

    def add(self, folder: str) -> None:
        """Add (or bump to front) a folder — stored as its resolved absolute path, deduplicated."""
        resolved = str(Path(folder).resolve())
        self.folders = [resolved] + [f for f in self.folders if f != resolved]
        self.save()

    def remove(self, folder: str) -> None:
        resolved = str(Path(folder).resolve())
        kept = [f for f in self.folders if f != resolved]
        if len(kept) != len(self.folders):
            self.folders = kept
            self.save()

    def list(self) -> list[str]:
        return list(self.folders)


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


def _strip_dirty(commit: str) -> str:
    """Drop a ``-dirty`` suffix so the SHA is a real ref git can resolve (mirrors the viewer)."""
    return commit[:-6] if commit.endswith("-dirty") else commit


_SHA_RE = re.compile(r"[0-9a-fA-F]{7,64}")


def _valid_commit(commit: str) -> bool:
    """True only for a bare hex SHA. Guards the git calls: a commit read from the map JSON that is
    empty, malformed, or (crucially) starts with ``-`` must never reach git's argv, where a leading
    dash would be parsed as a flag rather than a revision (argument injection)."""
    return bool(_SHA_RE.fullmatch(commit))


def _has_map(folder: Path) -> bool:
    """True if `folder` holds a `.coyodex/project-map.json` (the marker of a mappable project)."""
    try:
        return (folder / ".coyodex" / MAP_JSON).is_file()
    except OSError:
        return False


def load_project(folder: str) -> Project | None:
    """Build a Project from a folder holding a valid map, or None if the map is missing/unloadable.
    A recents entry whose folder went away or broke is simply not served (but stays in the list so the
    user can remove it)."""
    root = Path(folder)
    map_json = root / ".coyodex" / MAP_JSON
    if not map_json.is_file():
        return None
    try:
        graph = model_to_graph(load_model(map_json.read_text(encoding="utf-8")))
    except (ModelError, OSError, ValueError):
        return None
    commit = _strip_dirty(str(graph.get("commit") or "").strip())
    if commit and not _valid_commit(commit):
        return None
    return Project(slug=root.name or "project", repo_root=root, map_json=map_json,
                   map_html=map_json.parent / MAP_HTML, commit=commit)


def build_projects(folders: list[str]) -> dict[str, Project]:
    """slug -> Project for every recents folder that still holds a loadable map. Slug is the folder
    name; a collision (same folder name from two paths) gets a numeric suffix so both stay reachable.
    Recents order (most-recent first) decides who wins the bare name."""
    out: dict[str, Project] = {}
    for folder in folders:
        proj = load_project(folder)
        if proj is None:
            continue
        base, slug, i = proj.slug, proj.slug, 2
        while slug in out:
            slug, i = f"{base}-{i}", i + 1
        proj.slug = slug
        out[slug] = proj
    return out


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


# --- filesystem browser (for the "add a project" picker) ----------------------------------------

def list_dirs(path: Path) -> dict[str, object]:
    """The subdirectories of `path` (names only), each flagged whether it holds a mappable project,
    plus the parent (for up-navigation) and whether `path` itself is mappable. Used by the picker —
    it lists directories on the LOCAL machine for the LOCAL user, so there is no privilege boundary
    to cross here; a permission error on any entry is skipped."""
    entries: list[dict[str, object]] = []
    try:
        for child in sorted(path.iterdir(), key=lambda x: x.name.lower()):
            try:
                if child.is_dir() and not child.is_symlink():
                    entries.append({"name": child.name, "path": str(child), "hasMap": _has_map(child)})
            except OSError:
                continue
    except (OSError, PermissionError):
        pass
    parent = str(path.parent) if path.parent != path else None
    return {"path": str(path), "parent": parent, "hasMap": _has_map(path), "entries": entries}


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


def _recents_payload(store: RecentsStore, projects: dict[str, Project]) -> list[dict[str, object]]:
    """Every recents folder for the landing page — its served slug (None if the map is gone/broken),
    commit, and whether the HTML has been rendered — so the UI can offer Open / a 'render first' hint /
    Remove for each."""
    by_path = {str(p.repo_root): slug for slug, p in projects.items()}
    items: list[dict[str, object]] = []
    for folder in store.list():
        slug = by_path.get(folder)
        proj = projects.get(slug) if slug else None
        items.append({
            "path": folder,
            "name": Path(folder).name,
            "slug": slug,
            "ok": proj is not None,
            "commit": proj.commit if proj else "",
            "rendered": bool(proj and proj.map_html.is_file()),
        })
    return items


class Handler(BaseHTTPRequestHandler):
    store: RecentsStore = RecentsStore.__new__(RecentsStore)  # replaced in serve()
    projects: dict[str, Project] = {}
    server_version = "coyodex-serve"

    def log_message(self, format: str, *args: object) -> None:  # quieter than the default access log
        return

    # --- routing ---
    def do_GET(self) -> None:
        if not _loopback_host(self.headers.get("Host", "")):  # DNS-rebinding guard
            return self._send(403, "text/plain; charset=utf-8", b"host not allowed")
        parsed = urlparse(self.path)
        parts = [unquote(p) for p in parsed.path.split("/") if p]
        query = parse_qs(parsed.query)
        if not parts:
            return self._send(200, "text/html; charset=utf-8", INDEX_HTML.encode("utf-8"))
        if parts[0] == "api":            # landing-page API (recents + folder browser)
            return self._root_api(parts[1:], query)
        if parts[0] == "p" and len(parts) >= 2:  # /p/<slug>/...  -> a project's map + its API
            proj = self.projects.get(parts[1])
            if proj is None:
                return self._send(404, "text/plain; charset=utf-8", b"unknown project")
            return self._project(proj, parts[2:], query)
        return self._send(404, "text/plain; charset=utf-8", b"not found")

    def do_POST(self) -> None:
        if not _loopback_host(self.headers.get("Host", "")):
            return self._send(403, "text/plain; charset=utf-8", b"host not allowed")
        # CSRF guard: a custom header a cross-origin page can't set without a (failing) CORS preflight.
        if self.headers.get("X-Coyodex") != "serve":
            return self._send(403, "text/plain; charset=utf-8", b"missing X-Coyodex header")
        parts = [unquote(p) for p in urlparse(self.path).path.split("/") if p]
        if parts[:1] == ["api"] and len(parts) == 2 and parts[1] in ("open", "forget"):
            body = self._read_json()
            path = str(body.get("path") or "") if isinstance(body, dict) else ""
            return self._open(path) if parts[1] == "open" else self._forget(path)
        return self._send(404, "text/plain; charset=utf-8", b"not found")

    # --- landing-page API ---
    def _root_api(self, rest: list[str], query: dict[str, list[str]]) -> None:
        if rest == ["recents"]:
            return self._json(_recents_payload(self.store, self.projects))
        if rest == ["browse"]:
            raw = (query.get("path") or [""])[0]
            base = Path(raw) if raw else Path.home()
            try:
                base = base.resolve()
            except OSError:
                base = Path.home()
            if not base.is_dir():
                base = Path.home()
            return self._json(list_dirs(base))
        return self._send(404, "text/plain; charset=utf-8", b"unknown api")

    def _open(self, path: str) -> None:
        p = Path(path)
        if not path or not p.is_absolute() or not p.is_dir():
            return self._send(400, "text/plain; charset=utf-8", b"not an absolute directory path")
        if load_project(str(p)) is None:
            return self._send(400, "text/plain; charset=utf-8",
                              b"no valid .coyodex/project-map.json in that folder")
        with _STATE_LOCK:
            self.store.add(str(p))
            Handler.projects = build_projects(self.store.list())
        return self._json({"ok": True})

    def _forget(self, path: str) -> None:
        if not path:
            return self._send(400, "text/plain; charset=utf-8", b"missing path")
        with _STATE_LOCK:
            self.store.remove(path)
            Handler.projects = build_projects(self.store.list())
        return self._json({"ok": True})

    # --- a project's map + file/code API ---
    def _project(self, proj: Project, rest: list[str], query: dict[str, list[str]]) -> None:
        if rest and rest[0] == "api":
            return self._project_api(proj, rest[1:], query)
        if not rest or rest == [MAP_HTML]:
            return self._send_file(proj.map_html, "text/html; charset=utf-8")
        return self._send(404, "text/plain; charset=utf-8", b"not found")

    def _project_api(self, proj: Project, rest: list[str], query: dict[str, list[str]]) -> None:
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
    def _read_json(self) -> object:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if n <= 0 or n > 64_000:
            return None
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, OSError):
            return None

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
        self.wfile.write(body)  # only reached from do_GET/do_POST (other verbs get the base 501)


def serve(add_folders: list[Path], port: int = _DEFAULT_PORT, open_browser: bool = False,
          store: RecentsStore | None = None) -> int:
    """Serve the recents (plus any folders passed on the command line, added + validated) until
    interrupted. No disk scan — the served set is exactly the recents list."""
    store = store or RecentsStore()
    for folder in add_folders:
        if load_project(str(folder)) is not None:
            store.add(str(folder))
        else:
            print(f"coyodex serve: skipping {folder} — no valid .coyodex/project-map.json", file=sys.stderr)
    Handler.store = store
    Handler.projects = build_projects(store.list())
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    names = ", ".join(sorted(Handler.projects)) or "(none yet — add a folder from the landing page)"
    print(f"coyodex serve: {len(Handler.projects)} project(s): {names}")
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


_USAGE = """usage: coyodex serve [FOLDER ...] [--port N] [--open]

Serve coyodex maps over a local HTTP server so the viewer's file browser + code viewer light up
(files read from git at each map's commit). The server does NOT scan the disk: it serves the folders
you have opened before (remembered in ~/.coyodex/serve-recents.json). Open http://127.0.0.1:PORT/ to
add a project by browsing to its folder, or to open / remove a recent one.

  FOLDER      a project folder (with .coyodex/project-map.json) to add + serve now (repeatable)
  --port N    port to listen on (default 8765)
  --open      open the landing page in a browser on start
  -h/--help   show this help"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(_USAGE)
        return 0
    port, open_browser, folders = _DEFAULT_PORT, False, []
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
            folders.append(Path(a))
        i += 1
    return serve(folders, port=port, open_browser=open_browser)


# --- landing page (recents list + folder-picker to add a project) -------------------------------
# Self-contained: recents render from GET /api/recents; the picker walks the filesystem via
# GET /api/browse; Open/Remove POST to /api/open|forget with the X-Coyodex CSRF header.
INDEX_HTML = """<!doctype html><html><head><meta charset="utf-8"><title>coyodex maps</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iNyIgZmlsbD0iIzFlMWI0YiIvPjxsaW5lIHgxPSIxMS41IiB5MT0iMTEuNSIgeDI9IjIwLjUiIHkyPSIyMC41IiBzdHJva2U9IiNjN2QyZmUiIHN0cm9rZS13aWR0aD0iMi4yIiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48Y2lyY2xlIGN4PSIxMCIgY3k9IjEwIiByPSIzLjQiIGZpbGw9IiNhNWI0ZmMiLz48Y2lyY2xlIGN4PSIyMiIgY3k9IjIyIiByPSIzLjQiIGZpbGw9IiNmMGFiZmMiLz48L3N2Zz4=">
<style>
:root{color-scheme:light dark}
body{font:15px/1.5 -apple-system,system-ui,sans-serif;margin:40px auto;max-width:760px;padding:0 16px;color:#111}
h1{font-size:20px;margin:0 0 4px}h2{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:#6b7280;margin:28px 0 8px}
.sub{color:#6b7280;font-size:13px;margin:0 0 8px}
ul{list-style:none;padding:0;margin:0}
li{padding:10px 12px;border:1px solid #e5e7eb;border-radius:8px;margin:8px 0;display:flex;gap:12px;align-items:center}
a.open{font-weight:600;color:#4338ca;text-decoration:none}a.open:hover{text-decoration:underline}
.name{font-weight:600}.meta{font:12px ui-monospace,monospace;color:#6b7280}
.path{font:12px ui-monospace,monospace;color:#9ca3af;margin-left:auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:320px}
.warn{color:#b45309;font-size:12px}
button{font:inherit;font-size:13px;padding:5px 10px;border:1px solid #d1d5db;border-radius:6px;background:#fff;color:#374151;cursor:pointer}
button:hover{background:#f3f4f6}button.primary{background:#6366f1;border-color:#6366f1;color:#fff}button.primary:hover{background:#818cf8}
.x{border:0;background:none;color:#9ca3af;font-size:16px;cursor:pointer;padding:0 4px;line-height:1}.x:hover{color:#cf222e}
.empty{color:#9ca3af}
#picker{border:1px solid #e5e7eb;border-radius:8px;padding:12px;margin-top:10px;display:none}
#picker.on{display:block}
.crumbs{display:flex;gap:6px;align-items:center;margin-bottom:8px}
#curpath{font:12px ui-monospace,monospace;color:#374151;flex:1;padding:5px 8px;border:1px solid #d1d5db;border-radius:6px}
.dirs{max-height:260px;overflow:auto;border:1px solid #f3f4f6;border-radius:6px}
.dir{display:flex;align-items:center;gap:8px;padding:6px 10px;cursor:pointer;border-bottom:1px solid #f6f7f9}
.dir:last-child{border-bottom:0}.dir:hover{background:#f5f7ff}
.dir .ic{color:#9ca3af}.dir .badge{margin-left:auto;font:10px ui-monospace,monospace;color:#059669;border:1px solid #a7f3d0;border-radius:4px;padding:0 5px}
#err{color:#cf222e;font-size:13px;margin-top:8px;min-height:1em}
</style></head><body>
<h1>coyodex maps</h1>
<p class="sub">Open a project's map, or add a new one by browsing to its folder.</p>

<h2>Recent</h2>
<ul id="recents"><li class="empty">Loading…</li></ul>

<button id="addbtn" class="primary">+ Add a project…</button>

<div id="picker">
  <div class="crumbs">
    <button id="up" title="Parent folder">↑</button>
    <input id="curpath" readonly>
    <button id="pick" class="primary" disabled>Open this folder</button>
  </div>
  <div class="dirs" id="dirs"></div>
  <div id="err"></div>
</div>

<script>
const H = { 'Content-Type': 'application/json', 'X-Coyodex': 'serve' };
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function jget(u){ const r = await fetch(u, {cache:'no-store'}); if(!r.ok) throw new Error(r.status); return r.json(); }
async function jpost(u, body){ return fetch(u, {method:'POST', headers:H, body:JSON.stringify(body)}); }

async function loadRecents(){
  const ul = document.getElementById('recents');
  let items; try { items = await jget('/api/recents'); } catch(_) { ul.innerHTML = '<li class="empty">Could not load recents.</li>'; return; }
  if(!items.length){ ul.innerHTML = '<li class="empty">No projects yet — add one below.</li>'; return; }
  ul.innerHTML = '';
  for(const it of items){
    const li = document.createElement('li');
    let left;
    if(it.ok && it.rendered){ left = '<a class="open" href="/p/'+encodeURIComponent(it.slug)+'/">'+esc(it.name)+'</a>'; }
    else if(it.ok){ left = '<span class="name">'+esc(it.name)+'</span> <span class="warn">— run: coyodex render</span>'; }
    else { left = '<span class="name">'+esc(it.name)+'</span> <span class="warn">— map missing or invalid</span>'; }
    const meta = it.commit ? '<span class="meta">'+esc(it.commit.slice(0,12))+'</span>' : '';
    li.innerHTML = left + ' ' + meta + '<span class="path" title="'+esc(it.path)+'">'+esc(it.path)+'</span>'
      + '<button class="x" title="Remove from list">✕</button>';
    li.querySelector('.x').onclick = async () => { await jpost('/api/forget', {path: it.path}); loadRecents(); };
    ul.appendChild(li);
  }
}

let curPath = null, curHasMap = false;
async function browse(path){
  const err = document.getElementById('err'); err.textContent = '';
  let data; try { data = await jget('/api/browse' + (path ? '?path='+encodeURIComponent(path) : '')); }
  catch(_) { err.textContent = 'Could not read that folder.'; return; }
  curPath = data.path; curHasMap = data.hasMap;
  document.getElementById('curpath').value = data.path;
  document.getElementById('up').disabled = !data.parent;
  const pick = document.getElementById('pick');
  pick.disabled = !data.hasMap; pick.textContent = data.hasMap ? 'Open this folder' : 'No .coyodex here';
  const box = document.getElementById('dirs'); box.innerHTML = '';
  if(!data.entries.length){ box.innerHTML = '<div class="dir empty">(no subfolders)</div>'; }
  for(const e of data.entries){
    const row = document.createElement('div'); row.className = 'dir';
    row.innerHTML = '<span class="ic">📁</span><span>'+esc(e.name)+'</span>' + (e.hasMap ? '<span class="badge">map</span>' : '');
    row.onclick = () => browse(e.path);
    box.appendChild(row);
  }
  window._up = data.parent;
}
document.getElementById('addbtn').onclick = () => { const p = document.getElementById('picker'); p.classList.toggle('on'); if(p.classList.contains('on') && !curPath) browse(''); };
document.getElementById('up').onclick = () => { if(window._up) browse(window._up); };
document.getElementById('pick').onclick = async () => {
  const err = document.getElementById('err');
  const r = await jpost('/api/open', {path: curPath});
  if(r.ok){ document.getElementById('picker').classList.remove('on'); loadRecents(); }
  else { err.textContent = await r.text(); }
};
loadRecents();
</script>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
