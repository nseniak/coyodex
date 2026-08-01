"""`coyodex-eval retro-precheck` — the guard `/coyodex-retro` never had.

The failure it exists for is silent: provenance is stamped near the END of a build, so while a build
is running it still names the PREVIOUS one. The retro's same-session guard sees two different ids and
passes, and the whole retrospective reports on the wrong run.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "eval" / "tools"))

from coyodex_eval.retro_precheck import check, transcript_dir  # noqa: E402

PREV = "aaaaaaaa-1111-2222-3333-444444444444"
LIVE = "bbbbbbbb-5555-6666-7777-888888888888"
MINE = "cccccccc-9999-0000-1111-222222222222"


def make_project(root: Path, *, built_session: str = PREV, valid_map: bool = True) -> Path:
    """A project tree with a committed map and a provenance naming `built_session`."""
    coy = root / ".coyodex"
    coy.mkdir(parents=True)
    (coy / "project-map.json").write_text(
        json.dumps({"format": "coyodex-map", "components": []}) if valid_map else "{half-writ",
        encoding="utf-8")
    (coy / "provenance.json").write_text(json.dumps({
        "schema": "coyodex-provenance/v1",
        "sessions": [{"session_id": built_session, "built_at": "2026-07-30 16:23", "mode": "build"}],
    }), encoding="utf-8")
    return root


def make_transcripts(root: Path, *sessions: str) -> Path:
    """Transcript files for `root`, written NOW, in the real `~/.claude/projects/<slug>` location."""
    d = transcript_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    for s in sessions:
        (d / f"{s}.jsonl").write_text("{}\n", encoding="utf-8")
    return d


def test_it_refuses_while_another_session_is_still_writing():
    """The headline case. Provenance names the PREVIOUS build, a different session is mid-run, and
    the retro's own same-session guard cannot see it — two different ids look fine."""
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj")
        d = make_transcripts(root, PREV, LIVE)
        try:
            ok, message, detail = check(root, idle_seconds=180, this_session=MINE)
            assert not ok, "a live build must stop the retro"
            assert LIVE in message
            assert "still names the PREVIOUS one" in message
            assert detail["provenance_session"] == PREV
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_it_proceeds_once_that_session_has_gone_quiet():
    """Same tree, only the clock moved: the guard must not be a permanent veto."""
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj")
        d = make_transcripts(root, PREV, LIVE)
        try:
            old = time.time() - 3600
            os.utime(d / f"{LIVE}.jsonl", (old, old))
            ok, message, _detail = check(root, idle_seconds=180, this_session=MINE)
            assert ok, message
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_the_retros_own_transcript_never_counts_as_a_live_build():
    """The retro is itself a session writing a transcript in this project. Counting it would make
    the guard refuse every run, forever."""
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj")
        d = make_transcripts(root, PREV, MINE)
        try:
            ok, message, _detail = check(root, idle_seconds=180, this_session=MINE)
            assert ok, message
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_it_refuses_when_provenance_names_this_session():
    """The retro reading the file it is writing — Step 0a's rule, enforced instead of described."""
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj", built_session=MINE)
        ok, message, _detail = check(root, idle_seconds=180, this_session=MINE)
        assert not ok and "THIS session" in message


def test_it_refuses_a_half_written_map():
    """What a build mid-assemble leaves on disk."""
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj", valid_map=False)
        ok, message, _detail = check(root, idle_seconds=180, this_session=MINE)
        assert not ok and "may be writing it right now" in message


def test_it_refuses_when_there_is_no_build_at_all():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td) / "empty"
        (root / ".coyodex").mkdir(parents=True)
        ok, message, _detail = check(root, idle_seconds=180, this_session=MINE)
        assert not ok and "no finished build" in message
