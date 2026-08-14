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
  3. nothing under .coyodex/ has been written in the last N seconds — the build's own output, which
     is the only signal that sees a build STILL RUNNING AFTER it stamped provenance
  4. no OTHER session's transcript has been written in the last N seconds"""


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


#: How much of a transcript's tail to read when dating its last CONTENT record. A JSONL record is a
#: few KB at most, and the trailing sidecar records (`last-prompt`, `ai-title`, `mode`) that carry no
#: timestamp are short, so this reaches back many records without loading a 2.5 MB file.
_TAIL_BYTES = 64 * 1024


def last_content_age_seconds(p: Path) -> float | None:
    """Seconds since the last record in `p` that carries a `timestamp`. None when none is readable.

    A transcript's mtime is not evidence that a session is writing. The harness rewrites the trailing
    sidecar records (`last-prompt`, `ai-title`, `mode`) when a session is merely listed or resumed,
    and those records carry no timestamp — so the file is touched with no conversation appended.
    A live retrospective refused to start because of exactly that: `retro-precheck` named a session
    as "active 37s ago" whose newest conversation record was from three weeks earlier and whose byte
    count did not move across three checks twenty seconds apart.

    Reading the tail costs one seek. It is used only to DOWNGRADE a recent mtime, never to upgrade an
    old one, so the conservative direction the module argues for is preserved: a file nobody has
    touched stays idle, and a file that is genuinely being appended to has a fresh record to show.
    """
    try:
        size = p.stat().st_size
        with p.open("rb") as fh:
            if size > _TAIL_BYTES:
                fh.seek(size - _TAIL_BYTES)
                fh.readline()                    # drop the partial record the seek landed inside
            tail = fh.read().decode("utf-8", "replace")
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        stamp = rec.get("timestamp") if isinstance(rec, dict) else None
        if not isinstance(stamp, str) or not stamp:
            continue
        try:
            when = _parse_iso_utc(stamp)
        except ValueError:
            continue
        age = time.time() - when
        # A clock ahead of ours reads as a negative age. Treat it as "just now" rather than as a
        # nonsense number, so a skewed clock can never make a live session look idle.
        return max(age, 0.0)
    return None


def _parse_iso_utc(stamp: str) -> float:
    """Epoch seconds for an ISO-8601 UTC timestamp (`2026-08-13T20:21:33.602Z`)."""
    from datetime import datetime, timezone
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc).timestamp()


#: Written by `coyodex-eval archive`, not by a build — a fresh archive must not read as a live build.
_NOT_BUILD_OUTPUT = ("dev-rebuilds",)


def build_output_age(repo: Path) -> tuple[float | None, str | None]:
    """(seconds since the most recent write under `.coyodex/`, the file). (None, None) if empty.

    The transcript scan below cannot see the case that actually happens. Provenance is stamped near
    the end of a build and the build then KEEPS GOING — recording advisories, running `finalize`,
    re-rendering, committing. On the run this was written for, provenance said 14:57 and the map was
    still being rewritten at 15:43: 46 minutes in which the map, the fragments and the verify
    directory all changed while `retro-precheck` said "safe to proceed".

    Watching the build's own OUTPUT closes that window directly, and it is a better signal than the
    build's transcript for two reasons. It does not reset when the operator keeps chatting in the
    build window after the commit (a transcript-only rule would then refuse forever, telling them to
    wait for something that already happened). And it does not depend on provenance being older or
    newer than the map — an ordering that does not survive the final `render`.

    **What it observes is a recent WRITE, which is not the same fact as "a build is running."** The
    operator running `coyodex finalize` or `coyodex render` by hand writes here too. The refusal is
    still right — a map being rewritten by anything is a map the gates should not be read off — but
    the message must report the observation and let the reader supply the cause, because an
    explanation that is wrong teaches the reader to stop believing the check.
    """
    coy = repo / ".coyodex"
    if not coy.is_dir():
        return None, None
    newest: tuple[float, str] | None = None
    for p in coy.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _NOT_BUILD_OUTPUT for part in p.relative_to(coy).parts):
            continue
        a = age_seconds(p)
        if a is None:
            continue
        if newest is None or a < newest[0]:
            newest = (a, str(p.relative_to(repo)))
    return (newest[0], newest[1]) if newest else (None, None)


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

    # The build's own output, checked BEFORE the transcript scan: a build that stamped provenance and
    # is still writing is the case the transcript scan structurally cannot see, because it skips the
    # session provenance names. See `build_output_age`.
    out_age, out_file = build_output_age(repo)
    detail["newest_build_output"] = out_file
    detail["newest_build_output_age_seconds"] = None if out_age is None else round(out_age)
    if out_age is not None and out_age < idle_seconds:
        return False, (
            f"{out_file} was written {out_age:.0f}s ago, so something is still writing under "
            f"`.coyodex/`. Two things look like this and only you can tell them apart: a build that "
            f"has not finished (provenance is stamped near the END and the build keeps going — "
            f"recording advisories, `finalize`, `render`, the commit, so a fresh provenance "
            f"timestamp of {detail['built_at']} does NOT mean the map stopped changing), or you "
            f"having just run a coyodex command by hand. Either way the gates would be read off a "
            f"map that is still moving. Wait for `.coyodex/` to go quiet (>{idle_seconds}s), or "
            f"pass --idle-seconds if you know it is settled."), detail

    tdir = transcript_dir(repo)
    live: list[tuple[str, float]] = []
    touched: list[dict[str, object]] = []      # recent mtime, stale content — not a live session
    if tdir.is_dir():
        for f in tdir.glob("*.jsonl"):
            sid = f.stem
            if sid == built_sid or (this_session and sid == this_session):
                continue
            a = age_seconds(f)
            if a is None or a >= idle_seconds:
                continue
            # A recent mtime is a REASON TO LOOK, not the answer. Confirm with the last conversation
            # record; a touched-but-unwritten transcript is not a live session. See
            # `last_content_age_seconds`.
            content_age = last_content_age_seconds(f)
            if content_age is not None and content_age >= idle_seconds:
                touched.append({"session_id": sid, "mtime_age_seconds": round(a),
                                "last_record_age_seconds": round(content_age)})
                continue
            live.append((sid, content_age if content_age is not None else a))
    live.sort(key=lambda t: t[1])
    detail["live_transcripts"] = [{"session_id": s, "idle_seconds": round(a)} for s, a in live]
    detail["touched_not_live_transcripts"] = touched
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
