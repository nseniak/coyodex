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


def make_project(root: Path, *, built_session: str = PREV, valid_map: bool = True,
                 output_age_seconds: float = 3600) -> Path:
    """A project tree with a committed map and a provenance naming `built_session`.

    `output_age_seconds` ages everything under `.coyodex/`. It defaults to an hour because the
    interesting cases below are about TRANSCRIPTS, and a build whose own output was written one
    second ago is a build that has not finished — which the guard now refuses on its own."""
    coy = root / ".coyodex"
    coy.mkdir(parents=True)
    (coy / "project-map.json").write_text(
        json.dumps({"format": "coyodex-map", "components": []}) if valid_map else "{half-writ",
        encoding="utf-8")
    (coy / "provenance.json").write_text(json.dumps({
        "schema": "coyodex-provenance/v1",
        "sessions": [{"session_id": built_session, "built_at": "2026-07-30 16:23", "mode": "build"}],
    }), encoding="utf-8")
    age_build_output(root, output_age_seconds)
    return root


def age_build_output(root: Path, seconds: float) -> None:
    """Backdate every file under `.coyodex/`, as a finished build's output would be."""
    when = time.time() - seconds
    for f in (root / ".coyodex").rglob("*"):
        if f.is_file():
            os.utime(f, (when, when))


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


# ── the case the transcript scan structurally cannot see ─────────────────────────────────────────

def test_it_refuses_while_the_build_that_stamped_provenance_is_still_writing():
    """The live failure this check was added for, and the one the transcript scan misses BY DESIGN.

    On 2026-08-01 provenance said 14:57 while the build kept rewriting the map until 15:43 —
    recording advisories, `finalize`, `render`, the commit. The transcript scan skips the session
    provenance names (otherwise the retro would refuse forever after a build), so all it saw was
    "no OTHER session is live" and it said "safe to proceed" for 46 minutes. A retro started in that
    window gates a map that is still changing under it."""
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj", output_age_seconds=1)
        d = make_transcripts(root, PREV)
        try:
            old = time.time() - 3600
            os.utime(d / f"{PREV}.jsonl", (old, old))    # even a quiet transcript must not save it
            ok, message, detail = check(root, idle_seconds=180, this_session=MINE)
            assert not ok, "a build still writing its own output must stop the retro"
            assert "still writing under" in message
            # It observes a WRITE; it must not assert a cause it cannot know. The operator running
            # `finalize` or `render` by hand looks identical, and an explanation that is wrong
            # teaches the reader to stop believing the check.
            assert "only you can tell them apart" in message
            assert detail["newest_build_output"].startswith(".coyodex/")
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_it_proceeds_once_the_build_output_has_gone_quiet():
    """The guard must not become a permanent veto — the mirror of the transcript test above."""
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj", output_age_seconds=3600)
        d = make_transcripts(root, PREV)
        try:
            old = time.time() - 3600
            os.utime(d / f"{PREV}.jsonl", (old, old))
            ok, message, _detail = check(root, idle_seconds=180, this_session=MINE)
            assert ok, message
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_a_fresh_archive_is_not_mistaken_for_a_live_build():
    """`coyodex-eval archive` writes under `.coyodex/dev-rebuilds/` AFTER a build, by a developer.
    Counting it would refuse the retro that normally follows it."""
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj", output_age_seconds=3600)
        arch = root / ".coyodex" / "dev-rebuilds" / "0001"
        arch.mkdir(parents=True)
        (arch / "project-map.json").write_text("{}", encoding="utf-8")   # written NOW
        d = make_transcripts(root, PREV)
        try:
            old = time.time() - 3600
            os.utime(d / f"{PREV}.jsonl", (old, old))
            ok, message, _detail = check(root, idle_seconds=180, this_session=MINE)
            assert ok, message
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_the_refusal_reports_the_observation_not_a_diagnosis():
    """A recent write under `.coyodex/` is not the same fact as "a build is running" — running
    `coyodex finalize` by hand looks identical. Refusing is still right; claiming to know why is
    not, and a check that explains wrongly is a check the reader stops believing."""
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj", output_age_seconds=3600)
        (root / ".coyodex" / "finalize-report.md").write_text("# hand-run", encoding="utf-8")
        d = make_transcripts(root, PREV)
        try:
            old = time.time() - 3600
            os.utime(d / f"{PREV}.jsonl", (old, old))
            ok, message, _detail = check(root, idle_seconds=180, this_session=MINE)
            assert not ok
            assert "finalize-report.md" in message, "name the file that moved"
            assert "--idle-seconds" in message, "offer the override"
            assert "the build is still producing output" not in message
        finally:
            shutil.rmtree(d, ignore_errors=True)


# --- a touched transcript is not a live session (retro 2026-08-14) --------------------------------
# A live retrospective refused to start: `retro-precheck` named a session "active 37s ago" whose
# newest conversation record was three weeks old and whose byte count did not move across three
# checks twenty seconds apart. The harness rewrites the trailing sidecar records (`last-prompt`,
# `ai-title`, `mode`) when a session is merely listed or resumed, and those carry no timestamp.

def make_transcript_with_records(root: Path, session: str, *, last_record_age_seconds: float,
                                 trailing_sidecars: bool = True) -> Path:
    """A transcript whose last CONVERSATION record is `last_record_age_seconds` old, written NOW.

    The sidecar tail is the point: it is what the harness appends on a touch, and it carries no
    timestamp — so a reader that stops at the last line finds nothing to date."""
    from datetime import datetime, timezone

    d = transcript_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromtimestamp(time.time() - last_record_age_seconds,
                                   tz=timezone.utc).isoformat().replace("+00:00", "Z")
    lines = [json.dumps({"type": "user", "timestamp": stamp, "message": {"role": "user"}}),
             json.dumps({"type": "assistant", "timestamp": stamp, "message": {"role": "assistant"}})]
    if trailing_sidecars:
        lines += [json.dumps({"type": "last-prompt", "lastPrompt": "/coyodex"}),
                  json.dumps({"type": "ai-title", "aiTitle": "Build a map"}),
                  json.dumps({"type": "mode", "mode": "normal"}),
                  "Shell cwd was reset to /tmp"]
    p = d / f"{session}.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_a_freshly_touched_transcript_with_a_stale_last_record_is_not_live():
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj")
        d = transcript_dir(root)
        try:
            make_transcripts(root, PREV)
            make_transcript_with_records(root, LIVE, last_record_age_seconds=3_000_000)
            ok, message, detail = check(root, this_session=MINE)
            assert ok, message
            assert detail["touched_not_live_transcripts"], detail
            assert detail["touched_not_live_transcripts"][0]["session_id"] == LIVE
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_a_transcript_with_a_fresh_last_record_is_still_live():
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj")
        d = transcript_dir(root)
        try:
            make_transcripts(root, PREV)
            make_transcript_with_records(root, LIVE, last_record_age_seconds=5)
            ok, message, _detail = check(root, this_session=MINE)
            assert not ok, message
            assert LIVE in message
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_a_transcript_with_no_readable_timestamp_falls_back_to_mtime_and_stays_live():
    """Only ever used to DOWNGRADE a recent mtime. With nothing to date, the conservative answer —
    a false 'finished' produces a whole retrospective about the wrong run — must win."""
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj")
        d = transcript_dir(root)
        try:
            make_transcripts(root, PREV, LIVE)      # `{}` — a record with no timestamp
            ok, message, _detail = check(root, this_session=MINE)
            assert not ok, message
            assert LIVE in message
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_a_clock_ahead_of_ours_never_reads_as_idle():
    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj")
        d = transcript_dir(root)
        try:
            make_transcripts(root, PREV)
            make_transcript_with_records(root, LIVE, last_record_age_seconds=-600)
            ok, message, _detail = check(root, this_session=MINE)
            assert not ok, message
        finally:
            shutil.rmtree(d, ignore_errors=True)


def test_the_last_dateable_record_is_found_behind_a_long_sidecar_tail():
    from coyodex_eval.retro_precheck import last_content_age_seconds

    with tempfile.TemporaryDirectory() as td:
        root = make_project(Path(td) / "proj")
        d = transcript_dir(root)
        try:
            p = make_transcript_with_records(root, LIVE, last_record_age_seconds=120)
            age = last_content_age_seconds(p)
            assert age is not None and 100 < age < 200, age
        finally:
            shutil.rmtree(d, ignore_errors=True)
