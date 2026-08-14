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


# --- the index names the subcommands it truncates away (retro 2026-08-14) -------------------------
# A retrospective read the one-line index, concluded `grounding write` never ran, and published that
# about a build which ran it at turn 489 chained behind an `assemble`. The finding was withdrawn.
# `--commands` was the answer and nothing in the index pointed at it.

def make_bash_call(command: str) -> "transcript.ToolCall":
    return transcript.ToolCall(id="x", name="Bash", input={"command": command})


def test_a_subcommand_hidden_past_the_cut_is_named():
    long_prefix = "cd /a/very/long/path/that/eats/the/width " + "-" * 70
    call = make_bash_call(f"{long_prefix} && coyodex grounding write --map m.json")
    line = transcript.summarise_call(call)
    assert "grounding write" in line, line
    assert "--commands" in line, line


def test_several_hidden_subcommands_are_all_named_once_each():
    long_prefix = "x" * 120
    call = make_bash_call(f"{long_prefix}; coyodex assemble a.json; coyodex validate m.json; "
                          f"coyodex assemble b.json")
    line = transcript.summarise_call(call)
    assert "assemble" in line and "validate" in line
    assert line.count("assemble") == 1, line


def test_a_short_command_is_returned_untouched():
    call = make_bash_call("coyodex validate m.json")
    assert transcript.summarise_call(call) == "coyodex validate m.json"


def test_a_long_command_hiding_no_subcommand_is_truncated_silently():
    call = make_bash_call("echo " + "y" * 200)
    line = transcript.summarise_call(call)
    assert len(line) == 100, line
    assert "--commands" not in line


def test_the_visible_head_is_still_exactly_the_width():
    long_prefix = "z" * 150
    call = make_bash_call(f"{long_prefix} && coyodex render m.json")
    line = transcript.summarise_call(call)
    assert line.startswith("z" * 100)
    assert not line.startswith("z" * 101)


# --- assistant prose is part of a --full read ------------------------------------
# `method.md` and `dispatch.md` prescribe several steps that produce no tool call at all: show
# `scope`'s output verbatim as the first message, announce the build mode, warn before overwriting a
# baseline, and "the wait at a barrier is a TEXT turn". None of it was readable here, so a
# retrospective auditing those rules fell back to hand-parsing the raw JSONL — the exact fallback
# `--full-output` was added to prevent for sub-agent returns.


def make_transcript_with_prose(tmp: Path) -> Path:
    lines = [
        json.dumps({"type": "assistant", "message": {"id": "m0", "content": [
            {"type": "text", "text": "I'll archive the current map and rebuild from scratch."}]}}),
        json.dumps({"type": "assistant", "message": {"id": "m1", "content": [
            {"type": "text", "text": "Running the pre-index now."},
            {"type": "tool_use", "id": "t1", "name": "Bash",
             "input": {"command": "coyodex preindex ."}}]}}),
    ]
    p = tmp / "prose.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_a_text_only_turn_is_invisible_in_the_index():
    """The index is one line per tool CALL, and stays that way — it is how a lead sees a 450-turn
    run at a glance."""
    with tempfile.TemporaryDirectory() as td:
        turns = transcript.read_turns(make_transcript_with_prose(Path(td)))
        assert transcript.format_turns(turns).count("preindex") == 1
        assert "archive the current map" not in transcript.format_turns(turns)


def test_full_shows_assistant_prose_including_a_text_only_turn():
    with tempfile.TemporaryDirectory() as td:
        p = make_transcript_with_prose(Path(td))
        turns = transcript.read_turns(p)
        out = transcript.format_turns(turns, full=True)
        assert "archive the current map" in out, out
        assert "Running the pre-index now." in out, out
        assert "(said)" in out


def test_the_reader_carries_prose_on_the_turn(tmp_path=None):
    with tempfile.TemporaryDirectory() as td:
        turns = transcript.read_turns(make_transcript_with_prose(Path(td)))
        assert turns[0].text.startswith("I'll archive")
        assert turns[0].tool_calls == ()
        assert turns[1].text == "Running the pre-index now."


def test_a_tool_filtered_read_leaves_text_only_turns_out(capsys):
    """`--tool`/`--grep` ask a question about tool calls; a text-only turn is not an answer to it."""
    with tempfile.TemporaryDirectory() as td:
        p = make_transcript_with_prose(Path(td))
        assert transcript.main([str(p), "--full", "--tool", "Bash"]) == 0
        out = capsys.readouterr().out
        assert "archive the current map" not in out
        assert "preindex" in out
