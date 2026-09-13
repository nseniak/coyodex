#!/usr/bin/env python3
"""Which `coyomap serve` processes are running — a small file beside the recents, so a command
started from a MAPPED project (`coyomap url`) can find a server's port without being told it.

``~/.coyomap/serve-running.json`` holds one row per live server: its port and its process id. The
server writes its row when it binds and removes it when it stops. A row whose process is gone (a
kill, a crash, a closed terminal) is skipped by whoever reads the file next and dropped by the next
writer, because a process id is the one fact about a server that can be checked without talking to
it. The port is recorded nowhere else: the recents file names folders, `serve` takes the port as an
argument, and a real session rarely runs on the default one.

Stdlib-only, like `recents.py`, and for the same reason: a command that only wants the port must not
import the HTTP server to get it.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

RUNNING_PATH = Path.home() / ".coyomap" / "serve-running.json"


@dataclass(frozen=True)
class RunningServer:
    port: int
    pid: int
    started: str  # ISO-8601, UTC — newest first is the order a reader wants

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def _alive(pid: int) -> bool:
    """Whether a process with this id exists. Signal 0 delivers nothing and only checks."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    except OSError:
        return False
    return True


def _read(path: Path) -> list[RunningServer]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = data.get("servers") if isinstance(data, dict) else None
    out: list[RunningServer] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        port, pid = r.get("port"), r.get("pid")
        if isinstance(port, int) and isinstance(pid, int):
            out.append(RunningServer(port=port, pid=pid, started=str(r.get("started") or "")))
    return out


def _write(path: Path, rows: list[RunningServer]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"servers": [asdict(r) for r in rows]}, indent=2),
                        encoding="utf-8")
    except OSError as e:  # a server must never fail to serve because a courtesy file is unwritable
        print(f"coyomap serve: could not record the running server in {path} ({e})", file=sys.stderr)


def running_servers(path: Path = RUNNING_PATH) -> list[RunningServer]:
    """Every recorded server whose process is still alive, newest first. Read-only: a stale row is
    skipped here and dropped by the next writer."""
    live = [r for r in _read(path) if _alive(r.pid)]
    return sorted(live, key=lambda r: r.started, reverse=True)


def note_running(port: int, pid: int, path: Path = RUNNING_PATH) -> None:
    """Record a server that has just bound `port`. Dead rows are dropped on the way."""
    rows = [r for r in _read(path) if r.pid != pid and _alive(r.pid)]
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    _write(path, rows + [RunningServer(port=port, pid=pid, started=started)])


def forget_running(pid: int, path: Path = RUNNING_PATH) -> None:
    """Drop a server's row when it stops, and any dead rows beside it."""
    _write(path, [r for r in _read(path) if r.pid != pid and _alive(r.pid)])
