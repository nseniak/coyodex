#!/usr/bin/env python3
"""Tests for `coyodex-eval transcript` — the retrospective's eye on a build transcript.

Run either way (needs an editable install: `make install-eval`):
    python3 eval/tests/test_transcript.py
    pytest eval/tests/test_transcript.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyodex_eval import transcript

# --- the range applies to EVERY mode ---------------------------------------------
# `--commands` and `--stats` accepted --from/--to and silently discarded them, so a reviewer told
# to say "not in my range" rather than "the build skipped it" was handed whole-transcript data with
# nothing saying so — the exact failure the sliced-review protocol exists to prevent, in the tool
# the protocol runs on.


def make_two_phase_transcript(tmp: Path) -> Path:
    lines = []
    for i, cmd in enumerate(["coyodex preindex .", "coyodex assemble a.json",
                             "coyodex validate map.json", "coyodex finalize map.json"]):
        lines.append(json.dumps({
            "type": "assistant",
            "message": {"id": f"m{i}", "content": [
                {"type": "tool_use", "id": f"t{i}", "name": "Bash", "input": {"command": cmd}}]}}))
    p = tmp / "t.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_commands_honours_the_turn_range(capsys):
    with tempfile.TemporaryDirectory() as td:
        p = make_two_phase_transcript(Path(td))
        assert transcript.main([str(p), "--from", "0", "--to", "1", "--commands"]) == 0
        out = capsys.readouterr().out
        assert "preindex" in out and "assemble" in out
        assert "validate" not in out and "finalize" not in out
        assert "in turns 0-1" in out


def test_stats_honours_the_turn_range(capsys):
    with tempfile.TemporaryDirectory() as td:
        p = make_two_phase_transcript(Path(td))
        assert transcript.main([str(p), "--from", "2", "--to", "3", "--stats"]) == 0
        out = capsys.readouterr().out
        assert "(turns 2-3 only)" in out
        assert "2 turn(s)" in out


def test_an_empty_range_says_so_rather_than_printing_the_whole_file(capsys):
    with tempfile.TemporaryDirectory() as td:
        p = make_two_phase_transcript(Path(td))
        assert transcript.main([str(p), "--from", "900", "--to", "999", "--commands"]) == 0
        assert "no turns in turns 900-999" in capsys.readouterr().out


# --- output truncation, and redacted reasoning -----------------------------------


def make_long_result_transcript(tmp: Path, size: int) -> Path:
    lines = [
        json.dumps({"type": "assistant", "message": {"id": "m0", "content": [
            {"type": "tool_use", "id": "t0", "name": "Bash", "input": {"command": "ls"}}]}}),
        json.dumps({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t0", "content": "x" * size}]}}),
    ]
    p = tmp / "long.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_full_output_removes_the_result_cap(capsys):
    with tempfile.TemporaryDirectory() as td:
        p = make_long_result_transcript(Path(td), 2000)
        assert transcript.main([str(p), "--full"]) == 0
        capped = capsys.readouterr().out
        assert "more char(s)" in capped
        assert transcript.main([str(p), "--full-output"]) == 0
        whole = capsys.readouterr().out
        assert "more char(s)" not in whole
        assert len(whole) > len(capped)


def test_a_redacted_thinking_block_is_marked_not_dropped(capsys):
    """A signature with an EMPTY body means the reasoning was withheld at write time. Dropping the
    block made "the agent did not consider X" indistinguishable from "the reasoning is redacted",
    and a retrospective downgraded three findings for want of the difference."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "think.jsonl"
        p.write_text(json.dumps({"type": "assistant", "message": {"id": "m0", "content": [
            {"type": "thinking", "thinking": "", "signature": "s" * 300},
            {"type": "tool_use", "id": "t0", "name": "Bash", "input": {"command": "ls"}}]}}) + "\n",
            encoding="utf-8")
        assert transcript.main([str(p), "--full"]) == 0
        out = capsys.readouterr().out
        assert "thinking redacted" in out and "300 signature byte(s)" in out
