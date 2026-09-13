#!/usr/bin/env python3
"""Dev supervisor for `coyomap serve --dev`: FOR SOMEONE WORKING ON THE VIEWER, not for users.

Run it with `make dev-start`. Together with `--dev` it closes the edit → screen loop, so a change
to the viewer shows up with nothing pressed:

  * `viewer.js` / `viewer.css` / `viewer.html` are read from disk per request and sent `no-store`,
    so an edit is already live — the page's own live reload (`--dev`) puts it on screen. No restart
    is involved, and this supervisor deliberately does NOT watch them: restarting for a frontend
    edit buys nothing and costs something, because a restart landing while the page reloads kills
    the port mid-load and leaves a blank page.
  * A PYTHON edit is different: the view bundle is built in-process, so the running server cannot
    pick it up (see the stale-process guard in `viewer/serve.py` for why re-importing a live module
    graph mid-request is not the answer). This supervisor restarts the process instead. The server
    reports itself stale until that happens, and the page waits for the fresh process before
    reloading — so the reload lands on a server that is up.

Usage: devserve.py <repo-root> [port]
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

POLL_S = 1.0
SETTLE_S = 0.4  # the old listener needs a moment to release the port before the new one binds


def sources_stamp(watch_root: Path) -> int:
    """Newest mtime across the tool's Python — one number that changes on any edit.

    Returns 0 when the tree cannot be read, which reads as "nothing changed" rather than as a
    restart loop on a transient filesystem error."""
    newest = 0
    try:
        for f in watch_root.rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            try:
                newest = max(newest, f.stat().st_mtime_ns)
            except OSError:
                continue
    except OSError:
        return 0
    return newest


def spawn(repo: Path, port: str) -> subprocess.Popen[bytes]:
    """Start the server in its own process group, so `stop` can take down anything it spawned."""
    print(f"devserve: starting coyomap serve --dev on :{port}", flush=True)
    return subprocess.Popen(
        [str(repo / ".venv" / "bin" / "coyomap"), "serve", str(repo), "--port", port, "--dev"],
        cwd=str(repo), start_new_session=True,
    )


def stop(proc: subprocess.Popen[bytes]) -> None:
    """SIGTERM the server's process group, SIGKILL if it will not go. A process that is already
    gone (or was never ours to signal) is not an error — we only want it not running."""
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: devserve.py <repo-root> [port]", file=sys.stderr)
        return 2
    repo = Path(args[0]).resolve()
    port = args[1] if len(args) > 1 else "8765"
    watch_root = repo / "tools" / "coyomap"
    proc = spawn(repo, port)
    last = sources_stamp(watch_root)
    try:
        while True:
            time.sleep(POLL_S)
            if proc.poll() is not None:  # it died on its own (a port clash, a crash) — bring it back
                print("devserve: server exited, restarting", flush=True)
                proc = spawn(repo, port)
                last = sources_stamp(watch_root)
                continue
            now = sources_stamp(watch_root)
            if now != last:
                last = now
                print("devserve: a Python source changed — restarting", flush=True)
                stop(proc)
                time.sleep(SETTLE_S)
                proc = spawn(repo, port)
    except KeyboardInterrupt:
        pass
    finally:
        stop(proc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
