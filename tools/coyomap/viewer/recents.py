#!/usr/bin/env python3
"""The `coyomap serve` recents store — the list of project folders shown as cards on the landing page.

Persisted to ``~/.coyomap/serve-recents.json``. Kept in its own module (not serve.py) so the build
path (``coyomap render`` / ``coyomap assemble``) can register a freshly-built project via
``register_project`` without importing the whole HTTP server. Stdlib-only.

Every mutation reloads the file first, so an external writer (a build registering a project while the
server runs) is merged, never clobbered — the file is the single source of truth.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

RECENTS_PATH = Path.home() / ".coyomap" / "serve-recents.json"
_OPT_OUT_ENV = "COYOMAP_NO_SERVE_REGISTER"  # set to skip auto-registration (e.g. the regression eval)


class RecentsStore:
    """The ordered (most-recent first) list of project folders the user has opened, persisted to a
    small JSON file. No scanning — the list grows only when a folder is opened in the UI or a build
    registers one, and shrinks when the user removes a card or the landing page finds a remembered
    folder gone from disk (`prune_missing`). Mutations reload the file first so concurrent writers
    merge instead of clobber."""

    def __init__(self, path: Path = RECENTS_PATH) -> None:
        self.path = path
        self.folders: list[str] = []
        self.reload()

    def reload(self) -> None:
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
            print(f"coyomap: could not save recents to {self.path} ({e})", file=sys.stderr)

    def add(self, folder: str) -> None:
        """Add (or bump to front) a folder — stored as its resolved absolute path, deduplicated. Dedup
        is by SAME DIRECTORY, not just an equal string: on a case-insensitive filesystem (macOS/Windows)
        ``resolve()`` doesn't normalize case, so the same folder typed two ways would otherwise be added
        twice — ``samefile`` collapses those (and symlinks to the same target)."""
        self.reload()  # merge with any external change (e.g. a concurrent build registering a project)
        resolved = str(Path(folder).resolve())
        target = Path(resolved)
        kept: list[str] = []
        for f in self.folders:
            if f == resolved:
                continue
            try:
                if target.samefile(f):  # same dir via a different spelling / a symlink -> drop the old entry
                    continue
            except OSError:
                pass  # a folder that is gone: not add's call to drop — the landing page prunes those
            kept.append(f)
        self.folders = [resolved] + kept
        self.save()

    def remove(self, folder: str) -> None:
        self.reload()
        resolved = str(Path(folder).resolve())
        kept = [f for f in self.folders if f != resolved]
        if len(kept) != len(self.folders):
            self.folders = kept
            self.save()

    def prune_missing(self) -> list[str]:
        """Drop every entry whose folder is gone from disk, and return what was dropped. The landing
        page calls this on each load, so a deleted worktree or a test's scratch repo does not stay
        behind as a dead card. Reloads first like every mutation, and writes only when something
        went — a no-op must not touch the file. A folder that still EXISTS is never pruned here, even
        with no valid map in it: its card says "No valid map yet", and the map may be about to be
        built."""
        self.reload()
        gone = [f for f in self.folders if not _exists_as_dir(f)]
        if gone:
            dropped = set(gone)
            self.folders = [f for f in self.folders if f not in dropped]
            self.save()
        return gone

    def set_order(self, order: list[str]) -> None:
        """Reorder the recents to match `order` (existing paths, in the new sequence). Unknown paths are
        ignored; any current entry missing from `order` is appended (safety against a concurrent add)."""
        self.reload()
        known = set(self.folders)
        new = [p for p in order if p in known]
        seen = set(new)
        new += [f for f in self.folders if f not in seen]
        self.folders = new
        self.save()

    def list(self) -> list[str]:
        return list(self.folders)


def _exists_as_dir(folder: str) -> bool:
    """True unless the folder is KNOWN to be gone. One that cannot be looked at (a permission error,
    a mount that is not answering) counts as present: pruning on a doubt would drop a real project."""
    try:
        return Path(folder).is_dir()
    except OSError:
        return True


def register_project(coyomap_dir: Path, store: RecentsStore | None = None) -> None:
    """Best-effort: remember the project that owns ``coyomap_dir`` (a ``.coyomap/`` folder) so
    ``coyomap serve`` shows it as a card. No-ops (never raises) when the opt-out env var is set, the
    dir isn't a ``.coyomap/`` folder, or anything goes wrong — a build must never fail because of
    registration. ``store`` is injectable for tests."""
    if os.environ.get(_OPT_OUT_ENV):
        return
    try:
        d = Path(coyomap_dir)
        if d.name != ".coyomap":
            return
        (store or RecentsStore()).add(str(d.parent))
    except Exception:  # registration is a courtesy — swallow everything
        pass
