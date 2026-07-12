#!/usr/bin/env python3
"""Local multi-project server for coyodex maps — the whole viewer's backend.

The interactive viewer is served, not baked into a file. For each project this server serves:

  * a generic shell (``viewer.html``) + shared frontend assets (``viewer.js`` / ``viewer.css`` from
    ``/static/``) — identical for every map;
  * the map's own data at ``/p/<project>/api/view`` — the graph + every pre-rendered diagram, flow,
    and config flag (``gen_viewer.build_view_bundle``), which the frontend fetches and renders;
  * the file browser + code viewer, both read from git AT THE MAP'S COMMIT (``/api/tree`` /
    ``/api/src``, never the dirty working tree), so what you see always matches the map.

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
from coyodex.viewer.diffmap import (
    WORKTREE,
    FileChange,
    parse_name_status,
    project_changes,
    untracked_changes,
)
from coyodex.viewer.filetree import FileTreeNode, build_tree, node_path_index, resolved_path_index
from coyodex.viewer.gen_viewer import ViewBundle, build_view_bundle
from coyodex.viewer.recents import RecentsStore
from coyodex.views import model_to_graph

MAP_JSON = "project-map.json"
CHANGE_REPORT = "change-report.md"  # optional change-impact overlay, alongside the model in .coyodex/
PREINDEX_JSON = "preindex.json"  # build-time structural pre-index (symbols/imports), alongside the map
_DEFAULT_PORT = 8765

# The generic frontend assets (shell + viewer.js/css) live next to this module and are served as-is,
# shared by every project — the per-project data arrives separately via /p/<slug>/api/view.
_FRONTEND_DIR = Path(__file__).resolve().parent
_STATIC_FILES = {  # exact-name whitelist (no path traversal possible) -> content type
    "viewer.js": "text/javascript; charset=utf-8",
    "viewer.css": "text/css; charset=utf-8",
}
_STATE_LOCK = threading.Lock()  # guards recents mutation + the derived projects map


@dataclass
class Project:
    """One served map: its slug (URL segment), repo root, the model file, and the map's commit.

    ``commit`` is the SHA every git read is pinned to — ``-dirty`` stripped, since a working-tree
    marker isn't a real ref. ``tree`` caches the built file-browser tree (lazy, on first request);
    ``view`` caches the view bundle (lazy, on first request)."""

    slug: str
    repo_root: Path
    map_json: Path
    commit: str
    title: str = ""   # the map's human title (shown on the landing card) — folder name if the map has none
    goal: str = ""    # the map's one-paragraph goal (shown, clamped, under the title)
    tree: FileTreeNode | None = None  # cached tree (built once, on the first /api/tree)
    view: ViewBundle | None = None    # cached view bundle (built once, on the first /api/view)
    symbols: list[dict[str, object]] | None = None  # cached code symbols (built once, on the first /api/symbols)


def _strip_dirty(commit: str) -> str:
    """Drop a ``-dirty`` suffix so the SHA is a real ref git can resolve (mirrors the viewer)."""
    return commit[:-6] if commit.endswith("-dirty") else commit


_SHA_RE = re.compile(r"[0-9a-fA-F]{7,64}")


def _valid_commit(commit: str) -> bool:
    """True only for a bare hex SHA. Guards the git calls: a commit read from the map JSON that is
    empty, malformed, or (crucially) starts with ``-`` must never reach git's argv, where a leading
    dash would be parsed as a flag rather than a revision (argument injection)."""
    return bool(_SHA_RE.fullmatch(commit))


def _has_coyodex(folder: Path) -> bool:
    """True if `folder` holds a `.coyodex/` directory — the marker of a coyodex project. The map inside
    may be missing or not yet valid; such a folder is still addable (its recents card then shows
    'No valid map yet' and stays disabled until the map is built)."""
    try:
        return (folder / ".coyodex").is_dir()
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
    return Project(slug=root.name or "project", repo_root=root, map_json=map_json, commit=commit,
                   title=str(graph.get("title") or "").strip() or (root.name or "project"),
                   goal=str(graph.get("goal") or "").strip())


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


# --- git diff producers (the git layer of the mechanical diff viewer) ---------------------------
# resolve_ref/diff_changes turn a user-supplied ref pair into a normalized FileChange list; diffmap
# (pure) then projects it onto the map. The map's commit must be exactly one end of the range, so the
# anchors line up with that side (see coyodex.viewer.diffmap for the direction rules).

_REF_RE = re.compile(r"[0-9A-Za-z_./~^@{}+-]{1,200}")


def _safe_ref(ref: str) -> bool:
    """A git revision safe to pass to git's argv: non-empty, no leading dash (which git would read as
    a flag — argument injection), and only revision-ish characters. Not a resolution — just the gate
    before `git rev-parse` peels it to a SHA."""
    return bool(ref) and not ref.startswith("-") and bool(_REF_RE.fullmatch(ref))


def resolve_ref(repo_root: Path, ref: str) -> str | None:
    """A user-supplied ref → the SHA it points at, or None if unsafe/unresolvable. The `WORKTREE`
    sentinel passes through verbatim (the dirty tree isn't a committed object). `--end-of-options`
    plus `_safe_ref` keep a hostile ref from becoming a git flag."""
    if ref == WORKTREE:
        return WORKTREE
    if not _safe_ref(ref):
        return None
    code, out = _git(repo_root, ["rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"])
    if code != 0:
        return None
    sha = out.decode("utf-8", "replace").strip()
    return sha if _valid_commit(sha) else None


def diff_changes(repo_root: Path, base_sha: str, target: str) -> list[FileChange] | None:
    """The normalized changed-file list for `base_sha`..`target`. `target` is a committed SHA or the
    `WORKTREE` sentinel (base → the current working tree, plus untracked files as adds). Both SHAs are
    already hex-validated by the caller, so they cannot be git flags. None on a git failure."""
    if not _valid_commit(base_sha):
        return None
    if target == WORKTREE:
        code, out = _git(repo_root, ["diff", "--name-status", "-M", base_sha])
    else:
        if not _valid_commit(target):
            return None
        code, out = _git(repo_root, ["diff", "--name-status", "-M", base_sha, target])
    if code != 0:
        return None
    changes = parse_name_status(out.decode("utf-8", "replace"))
    if target == WORKTREE:  # `git diff` omits untracked files — add them as target-side adds
        code2, out2 = _git(repo_root, ["ls-files", "--others", "--exclude-standard"])
        if code2 == 0:
            changes = changes + untracked_changes(out2.decode("utf-8", "replace").splitlines())
    return changes


def project_diff(proj: Project, base_ref: str, target_ref: str) -> dict[str, object]:
    """The `/api/diff` payload: resolve the range, enforce that the map's pin is exactly one end
    (which fixes the direction and the anchor side), run the git diff, and project it onto the map.

    Raises ValueError for a range the viewer can't make sense of (no pin, unresolvable ref, or the pin
    not at an end) — the handler turns that into a 400."""
    pin = proj.commit
    if not pin or not _valid_commit(pin):
        raise ValueError("this map has no pinned commit to diff against")
    # The map usually stores a SHORT sha; resolve it (and the range) to full shas so the
    # pin-at-one-end check compares like for like.
    pin_sha = resolve_ref(proj.repo_root, pin)
    if pin_sha is None:
        raise ValueError("the map's pinned commit is not in this repo")
    base_sha = resolve_ref(proj.repo_root, base_ref)
    target_sha = resolve_ref(proj.repo_root, target_ref)
    if base_sha is None or target_sha is None:
        raise ValueError("could not resolve the base or target commit")
    if base_sha == pin_sha and target_sha != pin_sha:      # pin is the OLDER end: changes since the map
        map_side, direction = "base", "A"
    elif target_sha == pin_sha and base_sha != pin_sha:    # pin is the NEWER end: retrospective to the map
        map_side, direction = "target", "B"
    else:
        raise ValueError("the diff range must have the map's commit at exactly one end")
    changes = diff_changes(proj.repo_root, base_sha, target_sha)
    if changes is None:
        raise ValueError("git diff failed for that range")
    model = load_model(proj.map_json.read_text(encoding="utf-8"))
    elements = project_changes(model, changes, map_side)
    kinds = list(elements.values())
    return {
        "base": base_sha,
        "target": target_sha,
        "mapSide": map_side,
        "direction": direction,
        "changes": [{"status": c.status, "path": c.path, "oldPath": c.old_path} for c in changes],
        "elements": elements,
        "counts": {
            "files": len(changes),
            "created": kinds.count("created"),
            "modified": kinds.count("modified"),
            "deleted": kinds.count("deleted"),
        },
    }


def project_tree(proj: Project) -> FileTreeNode:
    """The file-browser tree for a project — git file set at the commit, overlaid with map coverage.

    Reuses the render-path tree builder (build_tree + node_path_index) so the served tree and the
    once-embedded tree are the SAME shape; only the file source differs (git vs a disk walk). Cached
    on the Project after the first build."""
    if proj.tree is not None:
        return proj.tree
    graph = model_to_graph(load_model(proj.map_json.read_text(encoding="utf-8")))
    rels = sorted(git_ls_files(proj.repo_root, proj.commit))
    proj.tree = build_tree(rels, node_path_index(graph), resolved_path_index(graph),
                           root_name=proj.repo_root.name)
    return proj.tree


def project_view(proj: Project) -> ViewBundle:
    """The whole view bundle for a project — the graph plus every pre-rendered diagram, flow, colour,
    and config flag the generic frontend needs (see gen_viewer.build_view_bundle). Computed from the
    committed model, source-links anchored on the map's `.coyodex/` folder, with the optional
    `change-report.md` overlay applied when present. Cached on the Project after the first request.
    The frontend fetches this at boot from /p/<slug>/api/view and renders it."""
    if proj.view is not None:
        return proj.view
    graph = model_to_graph(load_model(proj.map_json.read_text(encoding="utf-8")))
    report = proj.map_json.parent / CHANGE_REPORT
    proj.view = build_view_bundle(graph, report if report.is_file() else None, proj.map_json.parent)
    return proj.view


def project_symbols(proj: Project) -> list[dict[str, object]]:
    """The code symbols (class/function definitions) from the build-time pre-index next to the map, as a
    flat list of ``{name, file, line, kind}`` — one entry per definition site. The pre-index is generated
    at the map's commit, so its file:line anchors match what the code viewer serves from git. Missing or
    unreadable pre-index -> an empty list (the viewer then just has no code-symbol results). Cached on the
    Project after the first request; the frontend fetches it lazily from /p/<slug>/api/symbols."""
    if proj.symbols is not None:
        return proj.symbols
    out: list[dict[str, object]] = []
    path = proj.map_json.parent / PREINDEX_JSON
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = None  # no pre-index, or unreadable/invalid JSON -> degrade to no code symbols
    # isinstance guards at every level: a pre-index whose shape doesn't match (a list where a dict is
    # expected, a hand-edited/older/hostile file) must yield [] here, never an AttributeError that would
    # break the response. Only well-shaped {symbols:{by_name:{name:[{file,line,kind}]}}} contributes rows.
    symbols = doc.get("symbols") if isinstance(doc, dict) else None
    by_name = symbols.get("by_name") if isinstance(symbols, dict) else None
    if isinstance(by_name, dict):
        for name, locs in by_name.items():
            if not isinstance(locs, list):
                continue
            for loc in locs:
                if not isinstance(loc, dict) or not loc.get("file"):
                    continue
                out.append({"name": name, "file": loc.get("file"),
                            "line": loc.get("line"), "kind": loc.get("kind")})
    proj.symbols = out
    return out


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
                    entries.append({"name": child.name, "path": str(child), "hasMap": _has_coyodex(child)})
            except OSError:
                continue
    except (OSError, PermissionError):
        pass
    parent = str(path.parent) if path.parent != path else None
    return {"path": str(path), "parent": parent, "home": str(Path.home()),
            "hasMap": _has_coyodex(path), "entries": entries}


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
    """Every recents folder for the landing page — its served slug (None if the map is gone/broken) and
    commit — so the UI can offer Open / Remove for each. A valid map is directly openable: the viewer is
    served (built on demand), so there is no separate 'render the HTML first' step. `rendered` mirrors
    `ok` for the older landing-page script that still reads it."""
    by_path = {str(p.repo_root): slug for slug, p in projects.items()}
    items: list[dict[str, object]] = []
    for folder in store.list():
        slug = by_path.get(folder)
        proj = projects.get(slug) if slug else None
        items.append({
            "path": folder,
            "name": Path(folder).name,
            "title": proj.title if proj else Path(folder).name,
            "goal": proj.goal if proj else "",
            "slug": slug,
            "ok": proj is not None,
            "commit": proj.commit if proj else "",
            "rendered": proj is not None,   # a valid map is openable; the viewer is served, not baked
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
        if parts[0] == "static" and len(parts) == 2:  # shared generic frontend (viewer.js/css)
            return self._static(parts[1])
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
        if parts[:1] == ["api"] and len(parts) == 2 and parts[1] in ("open", "forget", "reorder"):
            body = self._read_json()
            if parts[1] == "reorder":
                return self._reorder(body)
            path = str(body.get("path") or "") if isinstance(body, dict) else ""
            return self._open(path) if parts[1] == "open" else self._forget(path)
        return self._send(404, "text/plain; charset=utf-8", b"not found")

    # --- landing-page API ---
    def _root_api(self, rest: list[str], query: dict[str, list[str]]) -> None:
        if rest == ["recents"]:
            # Re-read the file (a build may have registered a project since startup) and rebuild the
            # served set, so a just-built project shows up as a card AND is openable, no restart needed.
            with _STATE_LOCK:
                self.store.reload()
                Handler.projects = build_projects(self.store.list())
            return self._json(_recents_payload(self.store, self.projects))
        if rest == ["browse"]:
            raw = (query.get("path") or [""])[0]
            if not raw:
                return self._json(list_dirs(Path.home()))  # no path -> land at Home
            try:
                base = Path(raw).expanduser().resolve()  # accept ~/… and absolute paths
            except OSError:
                base = None
            if base is None or not base.is_dir():
                return self._send(404, "text/plain; charset=utf-8", b"no such folder")  # let the UI flag a typo
            return self._json(list_dirs(base))
        return self._send(404, "text/plain; charset=utf-8", b"unknown api")

    def _open(self, path: str) -> None:
        p = Path(path).expanduser() if path else Path("")  # accept ~/… paths typed in the UI
        if not path or not p.is_absolute():
            return self._send(400, "text/plain; charset=utf-8", b"enter an absolute folder path")
        if not p.is_dir():
            return self._send(400, "text/plain; charset=utf-8", b"no such folder on this machine")
        if not _has_coyodex(p):  # a .coyodex/ dir is enough — the map inside may not be valid/built yet
            return self._send(400, "text/plain; charset=utf-8", b"that folder has no .coyodex/ folder")
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

    def _reorder(self, body: object) -> None:
        folders = body.get("folders") if isinstance(body, dict) else None
        if not isinstance(folders, list):
            return self._send(400, "text/plain; charset=utf-8", b"missing folders")
        with _STATE_LOCK:
            self.store.set_order([f for f in folders if isinstance(f, str)])
            Handler.projects = build_projects(self.store.list())
        return self._json({"ok": True})

    # --- a project's map + file/code API ---
    def _project(self, proj: Project, rest: list[str], query: dict[str, list[str]]) -> None:
        if rest and rest[0] == "api":
            return self._project_api(proj, rest[1:], query)
        if not rest:
            # The generic shell — identical for every project; it fetches this map's data from
            # api/view at boot.
            return self._send_file(_FRONTEND_DIR / "viewer.html", "text/html; charset=utf-8")
        return self._send(404, "text/plain; charset=utf-8", b"not found")

    def _project_api(self, proj: Project, rest: list[str], query: dict[str, list[str]]) -> None:
        if rest == ["health"]:
            return self._json({"ok": True, "project": proj.slug, "commit": proj.commit})
        if rest == ["view"]:
            # Widest of the API catches: build_view_bundle walks the whole model + change-report and
            # assembles every diagram, so an odd-but-loadable map can raise KeyError/IndexError/TypeError
            # too. A bad map must yield a clean 500, never kill the worker thread or leak a traceback.
            try:
                return self._json(project_view(proj))
            except (ModelError, OSError, ValueError, KeyError, IndexError, TypeError) as e:
                return self._send(500, "text/plain; charset=utf-8",
                                  f"could not build the view: {e}".encode("utf-8"))
        if rest == ["tree"]:
            try:
                return self._json(project_tree(proj))
            except (ModelError, OSError, ValueError) as e:
                return self._send(500, "text/plain; charset=utf-8", str(e).encode("utf-8"))
        if rest == ["symbols"]:
            # Never fatal: a missing/broken pre-index yields an empty list, so the search just falls back
            # to map elements + files. No git or model work here, so nothing else to catch.
            return self._json({"symbols": project_symbols(proj), "commit": proj.commit})
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
        if rest == ["diff"]:
            # The mechanical diff overlay. base/target default to "since the map's commit, incl. the
            # dirty tree" (direction A). A range the viewer can't place (no pin, unresolvable ref, pin
            # not at an end) is the user's input problem -> 400; a model/git fault is a 500.
            base = (query.get("base") or [proj.commit])[0]
            target = (query.get("target") or [WORKTREE])[0]
            try:
                return self._json(project_diff(proj, base, target))
            except ValueError as e:
                return self._send(400, "text/plain; charset=utf-8", str(e).encode("utf-8"))
            except (ModelError, OSError, KeyError, IndexError, TypeError) as e:
                return self._send(500, "text/plain; charset=utf-8",
                                  f"could not build the diff: {e}".encode("utf-8"))
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

    def _static(self, name: str) -> None:
        """Serve one shared generic-frontend asset by exact name (whitelist -> no traversal)."""
        ctype = _STATIC_FILES.get(name)
        if ctype is None:
            return self._send(404, "text/plain; charset=utf-8", b"not found")
        return self._send_file(_FRONTEND_DIR / name, ctype)

    def _send_file(self, path: Path, ctype: str) -> None:
        try:
            data = path.read_bytes()
        except OSError:
            return self._send(404, "text/plain; charset=utf-8", b"file not found")
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
        if _has_coyodex(folder):  # a .coyodex/ dir is enough; an unbuilt map just shows as "No valid map yet"
            store.add(str(folder))
        else:
            print(f"coyodex serve: skipping {folder} — no .coyodex/ folder", file=sys.stderr)
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


# --- landing page (recents cards + a folder browser to add a project) ---------------------------
# Self-contained (no external assets). Recents render as cards (map title + goal) from GET
# /api/recents; a project is added by pasting a path or browsing the filesystem via GET /api/browse
# (breadcrumbs, quick locations, filter, inline add). Add/Remove POST to /api/open|forget with the
# X-Coyodex CSRF header. Themed for light + dark via CSS variables + prefers-color-scheme.
INDEX_HTML = r"""<!doctype html><html><head><meta charset="utf-8"><title>coyodex maps</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iNyIgZmlsbD0iIzFlMWI0YiIvPjxsaW5lIHgxPSIxMS41IiB5MT0iMTEuNSIgeDI9IjIwLjUiIHkyPSIyMC41IiBzdHJva2U9IiNjN2QyZmUiIHN0cm9rZS13aWR0aD0iMi4yIiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48Y2lyY2xlIGN4PSIxMCIgY3k9IjEwIiByPSIzLjQiIGZpbGw9IiNhNWI0ZmMiLz48Y2lyY2xlIGN4PSIyMiIgY3k9IjIyIiByPSIzLjQiIGZpbGw9IiNmMGFiZmMiLz48L3N2Zz4=">
<style>
:root{color-scheme:light dark;
  --bg:#fff;--fg:#111827;--muted:#6b7280;--faint:#9ca3af;--line:#e5e7eb;--line2:#f1f2f4;
  --card:#fff;--cardh:#f9fafb;--accent:#4f46e5;--accent2:#6366f1;--hover:#f5f6ff;
  --badge:#059669;--badgebg:#ecfdf5;--badgeln:#a7f3d0;--warn:#b45309;--danger:#dc2626;--ring:#c7d2fe}
@media (prefers-color-scheme:dark){:root{
  --bg:#0f1117;--fg:#e5e7eb;--muted:#9ca3af;--faint:#6b7280;--line:#242836;--line2:#1b1e28;
  --card:#161a23;--cardh:#1b2030;--accent:#a5b4fc;--accent2:#6366f1;--hover:#1a1f2e;
  --badge:#34d399;--badgebg:#0c2a20;--badgeln:#134e3a;--warn:#fbbf24;--danger:#f87171;--ring:#3730a3}}
*{box-sizing:border-box}
body{font:15px/1.55 -apple-system,system-ui,sans-serif;margin:0;background:var(--bg);color:var(--fg)}
.wrap{max-width:820px;margin:0 auto;padding:36px 20px 60px}
h1{font-size:22px;margin:0 0 2px;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:13px;margin:0 0 20px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);margin:26px 0 10px;font-weight:600}
button{font:inherit;font-size:13px;padding:7px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);cursor:pointer}
button:hover{background:var(--hover)}button:disabled{opacity:.5;cursor:default}
button.primary{background:var(--accent2);border-color:var(--accent2);color:#fff}button.primary:hover{background:#818cf8}
input{font:inherit;font-size:14px;padding:8px 11px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg);width:100%}
input:focus{outline:2px solid var(--accent2);outline-offset:-1px;border-color:transparent}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.addbar{display:flex;gap:8px;align-items:center}.addbar input{flex:1}
.err{color:var(--danger);font-size:13px;min-height:1.2em;margin:6px 2px 0}
.browser{border:1px solid var(--line);border-radius:12px;padding:12px;margin-top:6px;background:var(--card)}
.bhead{display:flex;gap:8px;align-items:center;margin-bottom:8px}
.crumbs{display:flex;flex-wrap:wrap;gap:1px;align-items:center;flex:1;min-width:0}
.crumb{padding:3px 7px;border:0;background:none;color:var(--accent);border-radius:6px;font-size:13px}
.crumb:hover{background:var(--hover);text-decoration:underline}.crsep{color:var(--faint);font-size:12px}
.quick{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px}
.chip{font-size:12px;padding:3px 9px;border:1px solid var(--line);border-radius:999px;background:var(--bg);color:var(--muted)}
.chip:hover{background:var(--hover);color:var(--fg)}
.filter{margin-bottom:8px}
.dirs{max-height:300px;overflow:auto;border:1px solid var(--line2);border-radius:8px}
.dir{display:flex;align-items:center;gap:9px;padding:7px 11px;cursor:pointer;border-bottom:1px solid var(--line2)}
.dir:last-child{border-bottom:0}.dir:hover{background:var(--hover)}
.dir.hasmap{background:var(--cardh)}.dir.hasmap:hover{background:var(--hover)}
.dir.ksel{background:var(--hover);box-shadow:inset 2px 0 0 var(--accent2)}
.dir .ic{font-size:14px}.dir .dn{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mapbadge{font-size:10px;color:var(--badge);background:var(--badgebg);border:1px solid var(--badgeln);border-radius:5px;padding:1px 6px;font-family:ui-monospace,monospace}
.mini{padding:3px 9px;font-size:12px}
.dir.empty{color:var(--faint);cursor:default}.dir.empty:hover{background:none}
.cards{display:flex;flex-direction:column;gap:10px}
.card{position:relative;border:1px solid var(--line);border-radius:12px;padding:14px 40px 14px 30px;background:var(--card);transition:border-color .12s,box-shadow .12s}
.card:hover{border-color:var(--ring);box-shadow:0 2px 12px rgba(80,70,229,.08)}
.card.clickable{cursor:pointer}
.card.disabled{opacity:.6}.card.disabled:hover{border-color:var(--line);box-shadow:none}.card.disabled .x{opacity:1}
.card.drag{opacity:.4}
.grip{position:absolute;left:8px;top:0;bottom:0;display:flex;align-items:center;color:var(--faint);opacity:0;cursor:grab;font-size:13px;user-select:none}
.card:hover .grip{opacity:.7}.grip:active{cursor:grabbing}
.card .title{font-size:15px;font-weight:650;color:var(--accent)}
.card.clickable:hover .title{text-decoration:underline}.card .title.dead{color:var(--fg)}
.iconbtn{border:0;background:none;color:var(--faint);font-size:14px;padding:2px 7px;line-height:1}.iconbtn:hover{color:var(--fg)}
.card .goal{color:var(--muted);font-size:13px;margin:3px 0 8px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card .cmeta{display:flex;flex-wrap:wrap;gap:10px;align-items:center;font-size:12px}
.card .cpath{color:var(--faint);font-family:ui-monospace,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}
.card .csha{color:var(--muted);font-family:ui-monospace,monospace}
.card .warn{color:var(--warn)}.card .copy{padding:2px 8px;font-size:11px}
.card .x{position:absolute;top:10px;right:8px;border:0;background:none;color:var(--faint);font-size:15px;padding:2px 6px;opacity:0;transition:opacity .1s}
.card:hover .x{opacity:1}.card .x:hover{color:var(--danger)}
.empty{color:var(--faint);font-size:14px;padding:6px 2px}
.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#111827;color:#fff;padding:8px 14px;border-radius:8px;font-size:13px;opacity:0;transition:opacity .2s;pointer-events:none}
.toast.on{opacity:.95}
</style></head><body>
<div class="wrap">
<h1>coyodex maps</h1>
<p class="sub">Open a project's map, or add one — start typing a folder to browse, or paste a path and press ↵.</p>

<input id="pathbar" class="mono" placeholder="Type or paste a folder — ↵ opens it; type to browse &amp; filter" autocomplete="off" spellcheck="false">
<div id="adderr" class="err"></div>

<div id="browser" class="browser" hidden>
  <div class="bhead">
    <button id="up" title="Parent folder">↑</button>
    <div id="crumbs" class="crumbs"></div>
    <button id="closebrowser" class="iconbtn" title="Close browser">✕</button>
  </div>
  <div id="quick" class="quick"></div>
  <div id="dirs" class="dirs"></div>
</div>

<h2>Recent</h2>
<div id="recents" class="cards"><div class="empty">Loading…</div></div>
</div>
<div id="toast" class="toast"></div>

<script>
const H={'Content-Type':'application/json','X-Coyodex':'serve'};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const $=id=>document.getElementById(id);
async function jget(u){const r=await fetch(u,{cache:'no-store'});if(!r.ok)throw new Error(r.status);return r.json();}
async function jpost(u,body){return fetch(u,{method:'POST',headers:H,body:JSON.stringify(body)});}
// cur = the folder currently DISPLAYED (may be a live preview while typing); curBase = the COMMITTED
// current folder — changed only by an explicit click or Enter, never by typing. Relative paths resolve
// against curBase, and clearing the input snaps the view back to it.
let home=null,recents=[],cur=null,entries=[],curParent=null,typeSeq=0,curBase=null,dirRows=[],selIdx=-1,dragSrc=null,dragging=false;
const shorten=p=>home&&(p===home||p.startsWith(home+'/'))?'~'+p.slice(home.length):p;
function toast(m){const t=$('toast');t.textContent=m;t.classList.add('on');setTimeout(()=>t.classList.remove('on'),1400);}

async function loadRecents(){
  try{recents=await jget('/api/recents');}catch(_){$('recents').innerHTML='<div class="empty">Could not load recents.</div>';return;}
  const box=$('recents');
  if(!recents.length){box.innerHTML='<div class="empty">No projects yet — add one above.</div>';renderQuick();return;}
  box.innerHTML='';
  for(const it of recents){
    const c=document.createElement('div');c.className='card';c.draggable=true;c.dataset.path=it.path;
    const goal=it.goal?'<p class="goal">'+esc(it.goal)+'</p>':'';
    let meta='<span class="cpath" title="'+esc(it.path)+'">'+esc(shorten(it.path))+'</span>';
    if(it.commit)meta+='<span class="csha">'+esc(it.commit.slice(0,10))+'</span>';
    if(!it.ok)meta+='<span class="warn">No valid map yet</span>';
    else if(!it.rendered)meta+='<span class="warn">not rendered</span><button class="copy" data-path="'+esc(it.path)+'">Copy render cmd</button>';
    c.innerHTML='<span class="grip" title="Drag to reorder">⠿</span><span class="title'+(it.ok&&it.rendered?'':' dead')+'">'+esc(it.title)+'</span>'+goal
      +'<div class="cmeta">'+meta+'</div><button class="x" title="Remove from list">✕</button>';
    if(!it.ok)c.classList.add('disabled');                                                                 // .coyodex present but no valid map -> dimmed, not clickable
    if(it.ok&&it.rendered){c.classList.add('clickable');c.onclick=()=>{if(dragging){dragging=false;return;}location.href='/p/'+encodeURIComponent(it.slug)+'/';};}  // whole card opens the map (unless we just dragged)
    // Drag to reorder. mousedown resets the flag so a plain click still opens; a drag sets it so the
    // click that may follow the drop is swallowed. Order is persisted on drop.
    c.addEventListener('mousedown',()=>{dragging=false;});
    c.addEventListener('dragstart',e=>{dragSrc=c;dragging=true;c.classList.add('drag');e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',it.path);});
    c.addEventListener('dragend',()=>{c.classList.remove('drag');dragSrc=null;persistOrder();});
    c.addEventListener('dragover',e=>{e.preventDefault();if(!dragSrc||dragSrc===c)return;const b=c.getBoundingClientRect();const before=(e.clientY-b.top)<b.height/2;c.parentNode.insertBefore(dragSrc,before?c:c.nextSibling);});
    c.querySelector('.x').onclick=async e=>{e.stopPropagation();await jpost('/api/forget',{path:it.path});loadRecents();};
    const cp=c.querySelector('.copy');
    if(cp)cp.onclick=e=>{e.stopPropagation();const cmd='cd "'+cp.dataset.path+'" && coyodex render .coyodex/project-map.json .coyodex/project-map.md';if(navigator.clipboard)navigator.clipboard.writeText(cmd);toast('Render command copied');};
    box.appendChild(c);
  }
  renderQuick();
}
// Persist the current card order (after a drag) to the server, and keep the local recents[] in sync.
async function persistOrder(){
  const order=[...$('recents').querySelectorAll('.card')].map(c=>c.dataset.path);
  jpost('/api/reorder',{folders:order});
  recents.sort((a,b)=>order.indexOf(a.path)-order.indexOf(b.path));
}

async function addPath(path){
  if(!path)return false;
  const r=await jpost('/api/open',{path});
  if(r.ok){$('adderr').textContent='';await loadRecents();if(!$('browser').hidden)renderList();toast('Added');return true;}
  $('adderr').textContent=await r.text();return false;
}

/* --- integrated path bar + folder browser (one control, not two) --- */
function openBrowser(){const b=$('browser');if(b.hidden){b.hidden=false;if(!cur)browse(home||'');}}
function closeBrowser(){$('browser').hidden=true;}
// A typed path: absolute (/…), home (~/…), or RELATIVE to the committed folder curBase (e.g.
// "mee6/repos" at Home). curBase never moves while typing, so relative resolution stays stable.
function resolvePath(v){if(v[0]==='/')return v;if(v[0]==='~')return (home||'')+v.slice(1);return (curBase||cur||home||'')+'/'+v;}
// The filter fragment = the text after the last "/" (or the whole value if none) — so a bare name
// filters the current folder, and while typing a path only the trailing segment filters.
function filterFrag(){const v=$('pathbar').value;const i=v.lastIndexOf('/');return (i===-1?v:v.slice(i+1)).trim().toLowerCase();}
// Enter COMMITS: resolve the typed path and either add it (a project folder) or move into it.
async function goPath(){
  const v=$('pathbar').value.trim();if(!v)return;
  let d;try{d=await fetchBrowse(resolvePath(v));}catch(_){$('adderr').textContent='No such folder.';return;}
  $('adderr').textContent='';
  if(d.hasMap){if(await addPath(d.path))browse(curBase);}  // a project folder -> add it, snap back to the committed folder
  else{$('pathbar').value='';applyBrowse(d);curBase=cur;}  // a parent folder -> move into it (commit)
}
// Typing only PREVIEWS — it never changes the committed folder (curBase). The text up to the last "/"
// is shown ("/" previews the root dir, "mee6/repos" at Home previews that folder), the part after it
// filters. A bare name (no "/") filters the committed folder. Clearing the input snaps back to curBase.
// Only a click (a folder row / breadcrumb / chip / Up) or Enter commits.
async function onType(){
  openBrowser();
  const v=$('pathbar').value;
  if(!v.includes('/')){                       // empty or a bare name -> show the committed folder, filtered
    if(cur!==curBase){const seq=++typeSeq;try{const d=await fetchBrowse(curBase);if(seq!==typeSeq)return;applyBrowse(d);}catch(_){}}
    renderList();return;
  }
  const target=resolvePath(v.slice(0,v.lastIndexOf('/')+1));   // preview the typed folder (no commit)
  const norm=target.replace(/\/+$/,'')||'/';
  if(norm!==cur){
    const seq=++typeSeq;
    try{const d=await fetchBrowse(target);if(seq!==typeSeq)return;applyBrowse(d);return;}catch(_){/* not a folder yet */}
  }
  renderList();
}
// Keyboard: ↑/↓ move a highlight through the folder list, Enter opens the highlighted folder (or, with
// nothing highlighted, commits the typed path via goPath).
function moveSel(d){
  if(!dirRows.length)return;
  selIdx = selIdx<0 ? (d>0?0:dirRows.length-1) : Math.max(0,Math.min(dirRows.length-1,selIdx+d));
  dirRows.forEach((r,i)=>r.classList.toggle('ksel',i===selIdx));
  dirRows[selIdx].scrollIntoView({block:'nearest'});
}
$('pathbar').addEventListener('focus',openBrowser);
$('pathbar').addEventListener('input',onType);
$('pathbar').addEventListener('keydown',e=>{
  if(e.key==='ArrowDown'){e.preventDefault();moveSel(1);}
  else if(e.key==='ArrowUp'){e.preventDefault();moveSel(-1);}
  else if(e.key==='Enter'){if(selIdx>=0&&dirRows[selIdx])dirRows[selIdx].click();else goPath();}
});
$('up').onclick=()=>{if(curParent)browse(curParent);};
$('closebrowser').onclick=closeBrowser;
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('browser').hidden)closeBrowser();});
// Click anywhere outside the browser (and not on the path bar that opens it) closes it — like Esc.
document.addEventListener('mousedown',e=>{const b=$('browser');if(b.hidden)return;if(!b.contains(e.target)&&e.target!==$('pathbar'))closeBrowser();});

async function fetchBrowse(path){return jget('/api/browse'+(path?'?path='+encodeURIComponent(path):''));}
function applyBrowse(d){
  home=d.home;cur=d.path;curParent=d.parent;entries=d.entries;
  $('up').disabled=!d.parent;
  renderCrumbs();renderList();
}
// A COMMITTED navigation (click / Up / crumb / chip): clear the typed text, show the folder, and make
// it the new committed base.
async function browse(path){$('pathbar').value='';let d;try{d=await fetchBrowse(path);}catch(_){return;}applyBrowse(d);curBase=cur;}
function renderCrumbs(){
  const box=$('crumbs');box.innerHTML='';
  const seg=(label,t)=>{const b=document.createElement('button');b.className='crumb';b.textContent=label;b.onclick=()=>browse(t);return b;};
  const sep=()=>{const s=document.createElement('span');s.className='crsep';s.textContent='/';return s;};
  let base,rest;
  if(home&&(cur===home||cur.startsWith(home+'/'))){base=home;rest=cur.slice(home.length);box.appendChild(seg('Home',home));}
  else{base='';rest=cur;box.appendChild(seg('/','/'));}
  let acc=base;
  // The root "/" crumb already shows the leading slash, so skip the separator before the first segment
  // under it (otherwise "/ / Users"). Under Home, every segment gets its separator.
  rest.split('/').filter(Boolean).forEach((p,i)=>{acc+='/'+p;if(!(base===''&&i===0))box.appendChild(sep());box.appendChild(seg(p,acc));});
}
function renderQuick(){
  const box=$('quick');box.innerHTML='';const seen=new Set();const chips=[];
  if(home){chips.push(['Home',home]);seen.add(home);}
  for(const it of recents){const par=it.path.slice(0,it.path.lastIndexOf('/'))||'/';if(!seen.has(par)){seen.add(par);chips.push([shorten(par),par]);}}
  if(chips.length<=1){box.style.display='none';return;}box.style.display='';
  for(const[label,path]of chips){const b=document.createElement('button');b.className='chip';b.textContent=label;b.title=path;b.onclick=()=>browse(path);box.appendChild(b);}
}
function renderList(){
  const q=filterFrag();const box=$('dirs');box.innerHTML='';selIdx=-1;dirRows=[];
  const added=new Set(recents.map(r=>r.path));  // map folders already in the recents list
  const ordered=[...entries.filter(e=>e.hasMap),...entries.filter(e=>!e.hasMap)].filter(e=>e.name.toLowerCase().includes(q));
  if(!ordered.length){box.innerHTML='<div class="dir empty">'+(entries.length?'No matching folders.':'(no subfolders)')+'</div>';return;}
  for(const e of ordered){
    const row=document.createElement('div');row.className='dir'+(e.hasMap?' hasmap':'');
    let tail='';
    if(e.hasMap)tail='<span class="mapbadge">map</span>'
      +(added.has(e.path)?'<button class="mini add" disabled>Added</button>':'<button class="mini primary add">+ Add</button>');
    row.innerHTML='<span class="ic">'+(e.hasMap?'🗺️':'📁')+'</span><span class="dn">'+esc(e.name)+'</span>'+tail;
    row.onclick=()=>browse(e.path);  // a click commits into the folder (browse clears the filter)
    const a=row.querySelector('.add');if(a&&!a.disabled)a.onclick=ev=>{ev.stopPropagation();addPath(e.path);};
    box.appendChild(row);
  }
  dirRows=[...box.querySelectorAll('.dir:not(.empty)')];  // for ↑/↓ keyboard selection
}
(async()=>{try{const d=await jget('/api/browse');home=d.home;}catch(_){}loadRecents();})();
</script>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
