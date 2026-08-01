#!/usr/bin/env python3
"""`coyodex-eval retro-precheck` — refuse to retrospect a build that has not finished.

`/coyodex-retro` states "a build has finished in this project" as a PRECONDITION IN PROSE and never
checks it. Its two mechanical guards do not cover this case:

  * the same-session guard compares `$CLAUDE_CODE_SESSION_ID` against provenance, which only catches
    running the retro inside the build's OWN chat;
  * Step 0 stops only when the map or provenance is ABSENT.

Provenance is stamped near the END of a build, so mid-run it still names the PREVIOUS build — a
different session id from the retro's own. Both guards pass, the retro proceeds, and every finding
is about the wrong run with nothing saying so. On a live session the operator had to hand-write a
wait procedure into the prompt to cover this, and that procedure carried two defects of its own: it
used `find -newermt '-120 seconds'`, which this platform's `find` (bfs) rejects outright — so the
idle test silently read as "always idle" — and it waited on a `dev-rebuilds/NNNN/` directory that a
BUILD NEVER CREATES (archiving is `coyodex-eval archive`, a developer convention). Both
conditions were unsatisfiable; the finished build went unnoticed for ~90 minutes.

The detection that actually works: the newest transcript in the project's `~/.claude/projects/<slug>/`
that is NOT this session's. If it is not the one provenance names, and it was written recently, a
build (or another agent) is live — refuse. Ages come from `os.path.getmtime`, never a `find`
predicate, because the failure above was the measurement, not the build.

Stdlib-only.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

#: A transcript written within this many seconds is treated as LIVE. Generous on purpose: a build
#: pauses for minutes at a fan-out barrier while its sub-agents work, and a false "finished" is the
#: expensive direction — it produces a whole retrospective about the wrong run.
DEFAULT_IDLE_SECONDS = 180

USAGE = """usage: coyodex-eval retro-precheck [--repo <root>] [--idle-seconds N] [--json]

Refuse to retrospect a build that has not finished. Exits 0 when it is safe to proceed, 1 when a
build looks live or the map/provenance is unusable, 2 on a usage error.

Checks, in order:
  1. .coyodex/project-map.json and .coyodex/provenance.json exist and parse
  2. provenance's newest session is not THIS session ($CLAUDE_CODE_SESSION_ID)
  3. no transcript newer than provenance's own has been written in the last N seconds"""


def project_slug(repo: Path) -> str:
    """`~/.claude/projects/<slug>` — the absolute path with every `/` replaced by `-`."""
    return str(repo.resolve()).replace("/", "-")


def transcript_dir(repo: Path) -> Path:
    return Path.home() / ".claude" / "projects" / project_slug(repo)


def age_seconds(p: Path) -> float | None:
    """Seconds since `p` was last written. `getmtime`, deliberately — see the module docstring."""
    try:
        return time.time() - os.path.getmtime(p)
    except OSError:
        return None


def check(repo: Path, idle_seconds: int = DEFAULT_IDLE_SECONDS,
          this_session: str | None = None) -> tuple[bool, str, dict]:
    """(ok, message, detail). `ok` False means: do not run the retrospective."""
    coy = repo / ".coyodex"
    map_path, prov_path = coy / "project-map.json", coy / "provenance.json"
    detail: dict[str, object] = {"repo": str(repo)}
    for label, p in (("map", map_path), ("provenance", prov_path)):
        if not p.exists():
            return False, f"{p} not found — there is no finished build here to retrospect.", detail
    try:
        sessions = json.loads(prov_path.read_text(encoding="utf-8")).get("sessions", [])
        built = sessions[-1]
        built_sid = str(built.get("session_id", ""))
    except Exception as e:
        return False, f"{prov_path} does not parse ({e}) — cannot identify the build.", detail
    try:
        json.loads(map_path.read_text(encoding="utf-8"))
    except Exception as e:
        # A half-written map is exactly what a mid-run build leaves behind.
        return False, f"{map_path} does not parse ({e}) — a build may be writing it right now.", detail
    detail["provenance_session"] = built_sid
    detail["built_at"] = built.get("built_at", "")
    if this_session and built_sid == this_session:
        return False, ("provenance names THIS session — the retro would read the file it is writing. "
                       "Open a new chat in this project and run it there."), detail

    tdir = transcript_dir(repo)
    live: list[tuple[str, float]] = []
    if tdir.is_dir():
        for f in tdir.glob("*.jsonl"):
            sid = f.stem
            if sid == built_sid or (this_session and sid == this_session):
                continue
            a = age_seconds(f)
            if a is not None and a < idle_seconds:
                live.append((sid, a))
    live.sort(key=lambda t: t[1])
    detail["live_transcripts"] = [{"session_id": s, "idle_seconds": round(a)} for s, a in live]
    if live:
        sid, a = live[0]
        return False, (
            f"a session other than the one provenance names has been active {a:.0f}s ago "
            f"({sid}) — a build is probably still running, and provenance is stamped near the END "
            f"of a build, so it still names the PREVIOUS one ({built_sid[:8]}…, {detail['built_at']}). "
            f"Retrospecting now would report on the wrong run. Wait for that session to go quiet "
            f"(>{idle_seconds}s) and for provenance to name it."), detail
    return True, (f"safe to proceed — provenance names {built_sid[:8]}… ({detail['built_at']}) and no "
                  f"other session has written a transcript in the last {idle_seconds}s."), detail


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print(USAGE)
        return 0
    repo = Path.cwd()
    idle = DEFAULT_IDLE_SECONDS
    as_json = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True
        elif a in ("--repo", "--idle-seconds"):
            i += 1
            if i >= len(argv) or argv[i].startswith("-"):
                print(f"ERROR: {a} needs a value", file=sys.stderr)
                return 2
            if a == "--repo":
                repo = Path(argv[i])
            else:
                try:
                    idle = int(argv[i])
                except ValueError:
                    print(f"ERROR: --idle-seconds must be an integer, got '{argv[i]}'",
                          file=sys.stderr)
                    return 2
        else:
            print(f"ERROR: unknown option(s): {a}", file=sys.stderr)
            return 2
        i += 1
    ok, message, detail = check(repo, idle, os.environ.get("CLAUDE_CODE_SESSION_ID"))
    if as_json:
        print(json.dumps({"ok": ok, "message": message, **detail}, indent=1))
    else:
        print(f"retro-precheck: {'OK' if ok else 'REFUSED'} — {message}",
              file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
