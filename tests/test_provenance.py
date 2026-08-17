#!/usr/bin/env python3
"""Tests for `coyodex provenance` — the stamp `finalize` requires before a map is committed.

The defect behind this module: provenance.json was produced ONLY by `tools/map_backup.py`, a script
in the coyodex clone that the shipped CLI does not install. A live build ran `finalize`, was told to
produce provenance, re-ran `finalize` unchanged, got the identical complaint, and only then went
looking for the script.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_provenance.py
    pytest tests/test_provenance.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyodex.provenance import Provenance, main, stamp


def make_repo(td: str) -> Path:
    repo = Path(td) / "proj"
    (repo / ".coyodex").mkdir(parents=True)
    return repo


def test_stamp_writes_the_file_finalize_requires():
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        path, entry, warnings = stamp(repo, session_id="sess-1", built_at="2026-08-02 18:00")
        assert path == repo / ".coyodex" / "provenance.json"
        assert not warnings
        doc = json.loads(path.read_text(encoding="utf-8"))
        assert doc["schema"] == "coyodex-provenance/v1"
        assert doc["project"] == "proj"
        assert doc["sessions"] == [{"session_id": "sess-1", "built_at": "2026-08-02 18:00",
                                    "mode": "build", "code_commit": None, "code_committed": None}]
        assert entry.session_id == "sess-1"


def test_re_stamping_one_session_updates_it_rather_than_appending():
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        stamp(repo, session_id="sess-1", built_at="2026-08-02 18:00")
        stamp(repo, session_id="sess-1", built_at="2026-08-02 18:40")
        sessions = json.loads((repo / ".coyodex" / "provenance.json").read_text())["sessions"]
        assert [s["built_at"] for s in sessions] == ["2026-08-02 18:40"]


def test_a_second_session_is_appended():
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        stamp(repo, session_id="sess-1", built_at="2026-08-02 18:00")
        stamp(repo, session_id="sess-2", built_at="2026-08-03 09:00", mode="accept")
        sessions = json.loads((repo / ".coyodex" / "provenance.json").read_text())["sessions"]
        assert [s["session_id"] for s in sessions] == ["sess-1", "sess-2"]
        assert sessions[-1]["mode"] == "accept"


def test_a_corrupt_file_is_repaired_by_the_stamp_with_a_warning():
    """The stamp IS the repair — refusing would leave the build with no way forward."""
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        (repo / ".coyodex" / "provenance.json").write_text("{not json", encoding="utf-8")
        _path, _entry, warnings = stamp(repo, session_id="sess-1", built_at="2026-08-02 18:00")
        assert warnings and "rewriting from scratch" in warnings[0]
        assert Provenance.load(repo / ".coyodex" / "provenance.json") is not None


def test_stamp_refuses_without_a_session_id():
    import os
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        prior = os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        try:
            try:
                stamp(repo, session_id=None)
                raise AssertionError("expected ValueError")
            except ValueError as e:
                assert "no session id" in str(e)
        finally:
            if prior is not None:
                os.environ["CLAUDE_CODE_SESSION_ID"] = prior


def test_stamp_refuses_a_repo_with_no_coyodex_dir():
    with tempfile.TemporaryDirectory() as td:
        try:
            stamp(Path(td), session_id="sess-1")
            raise AssertionError("expected FileNotFoundError")
        except FileNotFoundError as e:
            assert ".coyodex/ directory" in str(e)


def test_built_at_goes_to_stdout_so_the_header_can_reuse_the_exact_minute(capsys):
    """The build copies this minute into the map header's "Built:" cell, so the human line has to
    stay on stderr — `built_at=$(coyodex provenance stamp)` must be a usable idiom."""
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        assert main(["stamp", str(repo), "--session-id", "s", "--built-at",
                     "2026-08-02 18:00"]) == 0
        out = capsys.readouterr()
        assert out.out.strip() == "built_at=2026-08-02 18:00"
        assert "stamped" in out.err


def test_show_says_so_when_the_map_is_unstamped(capsys):
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        assert main(["show", str(repo)]) == 1
        assert "un-stamped" in capsys.readouterr().out


def test_an_unknown_mode_is_refused(capsys):
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        assert main(["stamp", str(repo), "--session-id", "s", "--mode", "nonsense"]) == 2
        assert "--mode must be one of" in capsys.readouterr().err


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_update_header_writes_the_stamped_minute_into_the_header_fragment():
    """The tool printed `built_at=…` and told the build to copy it by hand, so every build ran a
    `python3` heredoc that json-loaded header.json, set one string and dumped it back — a
    hand-written map write in the middle of the one prescribed sequence, for a value the tool had
    just computed. The failure mode is a header and a provenance file that disagree, and nothing
    downstream compares them."""
    import json as _json
    import tempfile as _tempfile
    from pathlib import Path as _Path

    from coyodex.provenance import main as _main
    with _tempfile.TemporaryDirectory() as td:
        repo = _Path(td)
        frag = repo / ".coyodex" / "build-fragments"
        frag.mkdir(parents=True)
        header = frag / "header.json"
        header.write_text('{"title": "t", "goal": "g", "built": ""}', encoding="utf-8")
        assert _main(["stamp", str(repo), "--session-id", "s1",
                      "--built-at", "2026-08-17 12:16",
                      "--update-header", str(header)]) == 0
        assert _json.loads(header.read_text(encoding="utf-8"))["built"] == "2026-08-17 12:16"
        prov = _json.loads((repo / ".coyodex" / "provenance.json").read_text(encoding="utf-8"))
        assert prov["sessions"][-1]["built_at"] == "2026-08-17 12:16"


def test_update_header_on_a_missing_file_is_an_error_not_a_silent_skip():
    import tempfile as _tempfile
    from pathlib import Path as _Path

    from coyodex.provenance import main as _main
    with _tempfile.TemporaryDirectory() as td:
        repo = _Path(td)
        (repo / ".coyodex").mkdir()
        assert _main(["stamp", str(repo), "--session-id", "s1",
                      "--update-header", str(repo / "nope.json")]) == 2
