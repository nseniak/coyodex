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


# --- round-two adversarial findings: one shared quote/comment mask ----------------
# The first repair used TWO hand-rolled quote scanners that disagreed by construction, applied
# quote-blanking to the `--help` test but not to the match itself, and left the index annotation
# scanning raw text with a bare regex. Each case below is a repro from that review.


def _subs(cmd: str) -> list[str]:
    call = transcript.ToolCall(name="Bash", input={"command": cmd})
    turn = transcript.Turn(index=1, role="assistant", tool_calls=(call,))
    return [n for _i, n in transcript.coyodex_subcommands([turn])]


def test_an_apostrophe_in_a_comment_does_not_swallow_the_command():
    """The regression the first repair introduced: `_segments` tracked quotes over the whole text
    while `_heredoc_tags` reset per line, so one unbalanced quote merged every segment and a later
    program's `-h` again deleted a real invocation. Six real commands in the corpus carry a comment
    apostrophe; each was one `sort -h` away from vanishing."""
    assert _subs("# don't do this\ncoyodex audit m.json\ndu -h /tmp/x") == ["audit"]
    assert _subs("# it's fine\ncoyodex validate m.json\npython build.py --help") == ["validate"]


def test_a_comment_cannot_open_a_phantom_heredoc():
    """`# use << EOF to redirect` opened a heredoc whose terminator never came, blanking every
    invocation below it. The round-one sweep abstracted "`<<` inside a quoted string" and stopped
    there; a comment is the same class."""
    assert _subs("# use << EOF to redirect\ncoyodex audit m.json") == ["audit"]


def test_coyodex_shaped_prose_inside_a_quoted_string_is_not_a_run():
    """Quote-blanking was applied to the `--help` tail but never to the match, so the scan ruled
    that quoted text is not evidence of a help run but IS evidence of an invocation. Across the
    corpus 130 counted invocations sat inside quoted spans — echoed banners, `sed` replacement
    strings, commit messages describing what was run."""
    assert _subs('echo "next step: coyodex reconcile the fragments"') == []
    assert _subs('coyodex record --map x --line "then runs coyodex assemble"') == ["record"]
    # the quote DELIMITER is ordinary syntax, so the careful `"$CY"` spelling still counts —
    # now via the CALL, because a function definition on its own is a template nobody ran
    assert _subs('rec() { "$CY" record --map m --line "$1"; }\nrec "Sweep debt" "a: why"') \
        == ["record"]


def test_a_plain_heredoc_terminator_must_not_be_indented():
    """Real bash requires column 0 for `<<TAG`; only `<<-` strips leading TABS. Accepting an
    indented terminator ended the body early and read the rest of it as shell — inventing an
    invocation, which is what heredoc stripping exists to prevent."""
    assert _subs("cat <<EOF\n  EOF\ncoyodex dump m.json\nEOF\ncoyodex audit m.json") == ["audit"]
    assert _subs("cat <<-EOF\n\tEOF\ncoyodex audit m.json") == ["audit"]


def test_a_heredoc_tag_may_hold_what_a_filename_may():
    """`<<'PY-END'` read as `[A-Za-z0-9_]+` truncated to `PY`, so the terminator was never matched
    and a perfectly valid heredoc blanked every invocation after it."""
    assert _subs("cat > x <<'PY-END'\nnoise\nPY-END\ncoyodex audit m.json") == ["audit"]
    assert _subs("cat > x <<'EOF.1'\nnoise\nEOF.1\ncoyodex audit m.json") == ["audit"]


def test_a_variable_in_front_of_the_literal_binary_does_not_hide_it():
    """`$WRAPPER coyodex audit` matched the alias branch with `coyodex` as the subcommand — not in
    the allowlist — and skipping to the match END stepped over the real binary behind it."""
    assert _subs("$WRAPPER coyodex audit m.json") == ["audit"]
    assert _subs("PATH=$X coyodex audit m.json") == ["audit"]


def test_the_index_names_only_what_the_commands_table_will_confirm():
    """The index annotation scanned the truncated text with a bare regex — no heredoc stripping, no
    `--help` filter — so it named `dump` and `lint-fragment` at turns whose only mention of them was
    a contract-template body, and pointed the reader at a table that denied them. That annotation
    exists BECAUSE a retro trusted the index; naming a run the table will not confirm is the same
    failure pointing the other way."""
    cmd = ("cat > r.md <<'EOF'\n" + "x" * 110 + "\ncoyodex dump --map m.json\n"
           "coyodex lint-fragment f.json\nEOF\ncoyodex record --map x")
    line = transcript.summarise_call(transcript.ToolCall(name="Bash", input={"command": cmd}))
    named = line.split("…+")[1].replace(" (use --commands)", "") if "…+" in line else ""
    assert named == "record", line
    assert _subs(cmd) == ["record"]


def test_shell_grammar_that_must_not_split_a_command():
    """`2>&1` appears in almost every real coyodex call: splitting on its `&` must not orphan the
    invocation or drag a later `-h` into its segment."""
    assert _subs("coyodex validate m.json --check-sources 2>&1 | grep -h err") == ["validate"]
    assert _subs("for b in a b; do coyodex dump $b; done") == ["dump"]
    assert _subs("x=$(echo a; echo b); coyodex audit m.json") == ["audit"]


# --- the subverb allowlist, and the shell-function template ----------------------
# `coyodex fix row` was tabled as a bare `fix` and `provenance stamp` as `provenance`, because six
# of the twelve dispatched verbs were missing from the allowlist. Worse, a build that has six
# near-identical edits writes the invocation once in a shell function and calls it six times, so
# the scan counted the DEFINITION and reported one run. A retrospective read the resulting table
# and published "no `fix row` invocation in the whole build"; the verb had run six times.


def test_subverbs_cover_every_dispatched_verb():
    """The allowlist is checked against the dispatch tables, not against a comment."""
    from coyodex import fix, grounding, provenance  # the tools this reader measures

    dispatched = set(fix._VERBS)
    dispatched |= {"write", "report", "lint"}          # grounding.main's own `verb not in (...)`
    dispatched |= {"stamp", "show"}                    # provenance.main's own guard
    missing = sorted(dispatched - transcript._COYODEX_SUBVERBS)
    assert not missing, (
        f"{missing} are dispatched but absent from _COYODEX_SUBVERBS, so `--commands` will report "
        f"them at bare-subcommand granularity and a reader cannot tell them apart")
    # And the two source lists this test hard-codes must still be what the tools parse.
    assert "lint" in grounding.USAGE
    assert "stamp" in provenance.USAGE


def test_a_verb_called_through_a_shell_function_is_counted_per_call():
    cmd = ("CX=.venv/bin/coyodex\n"
           'run(){ echo "--- $1"; $CX fix row --fragments $FR --id "$1" "${@:2}" 2>&1 | tail -2; }\n'
           'run BR177 --set-statement "a"\n'
           'run BR181 --set-statement "b"\n'
           'run BR158 --set-statement "c"\n')
    names = [i.name for i in transcript._invocations_in(cmd)]
    assert names == ["fix row"] * 3, names
    # The binary is resolved from the alias assigned OUTSIDE the function.
    assert all(i.binary == "coyodex" and i.alias_resolved
               for i in transcript._invocations_in(cmd))


def test_a_defined_but_never_called_function_counts_nothing():
    """The old scan counted the definition. A template nobody ran is not work that happened."""
    cmd = ("CX=.venv/bin/coyodex\n"
           "rec(){ $CX record --map $F --heading \"$1\" --line \"$2\"; }\n"
           "echo 'defined, never called'\n")
    assert transcript._invocations_in(cmd) == []


def test_a_helper_with_no_coyodex_call_expands_to_nothing():
    cmd = ("hunt(){ grep -rn \"$1\" backend/src; }\n"
           "hunt policy_engine\n"
           "coyodex validate map.json\n")
    assert [i.name for i in transcript._invocations_in(cmd)] == ["validate"]


def test_an_unbalanced_brace_leaves_the_text_alone():
    """Guessing at a broken definition would silently drop a real invocation."""
    cmd = "run(){ coyodex validate map.json\ncoyodex audit map.json\n"
    names = [i.name for i in transcript._invocations_in(cmd)]
    assert "audit" in names


# --- the COMMAND cap: it truncated silently, with no marker and no flag to lift it ---------------
# `--full`'s own help says "include the whole command". It printed `body.splitlines()[:40]` with no
# notice, while the RESULT path two lines below printed a truncation line and honoured
# `--full-output`. On one build 9 of 197 tool-call bodies exceeded the cap and the worst lost 333 of
# its 373 lines — invisible to the retrospective whose whole job is reading what a build hand-wrote.

def make_long_command_transcript(tmp: Path, n_lines: int) -> Path:
    body = "python3 - <<'PY'\n" + "\n".join(f"line_{i} = {i}" for i in range(n_lines)) + "\nPY"
    rec = json.dumps({
        "type": "assistant",
        "message": {"id": "m0", "content": [
            {"type": "tool_use", "id": "t0", "name": "Bash", "input": {"command": body}}]}})
    p = tmp / "long_cmd.jsonl"
    p.write_text(rec + "\n", encoding="utf-8")
    return p


def test_a_truncated_command_says_how_much_it_dropped(capsys):
    with tempfile.TemporaryDirectory() as td:
        p = make_long_command_transcript(Path(td), 100)
        assert transcript.main([str(p), "--full"]) == 0
        out = capsys.readouterr().out
        shown = [ln for ln in out.splitlines() if ln.startswith("        | ")]
        assert len(shown) == transcript.COMMAND_LINES + 1, len(shown)
        assert "more line(s)" in shown[-1], shown[-1]
        assert "--full-output" in shown[-1], shown[-1]


def test_full_output_lifts_the_command_cap_too(capsys):
    """It lifted only the RESULT cap, so the flag named in the truncation notice did not help."""
    with tempfile.TemporaryDirectory() as td:
        p = make_long_command_transcript(Path(td), 100)
        assert transcript.main([str(p), "--full-output"]) == 0
        out = capsys.readouterr().out
        shown = [ln for ln in out.splitlines() if ln.startswith("        | ")]
        assert len(shown) == 102, len(shown)          # heredoc opener + 100 lines + PY
        assert not any("more line(s)" in ln for ln in shown), shown[-1]


def test_a_short_command_carries_no_marker(capsys):
    with tempfile.TemporaryDirectory() as td:
        p = make_long_command_transcript(Path(td), 3)
        assert transcript.main([str(p), "--full"]) == 0
        out = capsys.readouterr().out
        assert "more line(s)" not in out


# --- the OPERATOR, and only the operator ------------------------------------------------------
# USER-role records used to reach the reader carrying tool RESULTS and nothing the human said:
# `text_parts` was dropped on that branch and `format_turns` filtered to ASSISTANT. Measured on one
# 642-turn build, 358 USER turns parsed and 0 carried text, so a retro asking "who noticed the
# missing section" had no mode of this reader that could answer.
#
# The other half is that a Claude Code transcript files skill bodies, `<system-reminder>` blocks and
# IDE notices under the same role as the human. Rendering those as `(operator)` is a worse answer
# than none.

def _one_user_turn(tmp: Path, text: str) -> str:
    import json as _json
    from coyodex_eval.transcript import format_turns, read_turns
    p = tmp / "t.jsonl"
    p.write_text("\n".join([
        _json.dumps({"type": "user", "message": {"role": "user",
                                                 "content": [{"type": "text", "text": text}]}}),
        _json.dumps({"type": "assistant", "message": {"id": "m1", "role": "assistant",
                                                      "content": [{"type": "text", "text": "ok"}]}}),
    ]) + "\n", encoding="utf-8")
    return format_turns(read_turns(p), full=True)


def test_an_operator_turn_is_rendered_in_full():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out = _one_user_turn(Path(td), "Because I never wrote it. That is a gap in the map.")
    assert "(operator)" in out, out
    assert "That is a gap in the map." in out, out


def test_a_skill_body_is_not_the_operator():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out = _one_user_turn(Path(td),
                             "Base directory for this skill: /Users/x/.claude/skills/coyodex-retro")
    assert "(operator)" not in out, out


def test_a_system_reminder_is_not_the_operator():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out = _one_user_turn(Path(td), "<system-reminder>\nsome injected note\n</system-reminder>")
    assert "(operator)" not in out, out


# --- the operator's own words, through a slash-command wrapper (retro 2026-09-02, mcpolis 11) -----
# `--full` rendered 0 of 74 operator records on a real transcript: the harness WRAPS a slash command
# rather than replacing it, and the reader dropped the whole record on seeing `<command-name>`.

def test_a_slash_command_record_yields_the_operators_own_words():
    from coyodex_eval.transcript import operator_text
    raw = ("<command-message>coyodex is running…</command-message>\n"
           "<command-name>coyodex</command-name>\n"
           "<command-args>build the map, do not ask me anything</command-args>")
    assert operator_text(raw) == "/coyodex build the map, do not ask me anything"


def test_a_slash_command_with_no_args_is_still_the_operator_speaking():
    from coyodex_eval.transcript import operator_text
    assert operator_text("<command-name>coyodex-retro</command-name>\n"
                         "<command-args></command-args>") == "/coyodex-retro"


def test_plain_words_pass_through():
    from coyodex_eval.transcript import operator_text
    assert operator_text("stop and show me the scope") == "stop and show me the scope"


def test_real_harness_text_is_still_hidden():
    """Rendering machine text as a person is a worse answer than no answer — the question this
    reader exists to answer is "who noticed this"."""
    from coyodex_eval.transcript import operator_text
    for raw in ("<system-reminder>do the thing</system-reminder>",
                "Base directory for this skill: /x/y",
                "<ide_opened_file>a.py</ide_opened_file>"):
        assert operator_text(raw) == "", raw


def test_a_quoted_wrapper_inside_a_real_message_is_not_read_as_the_command():
    """Searching for the wrapper before the harness filter rendered any body that merely MENTIONED
    `<command-name>` as an operator saying that command — and threw the real words away."""
    from coyodex_eval.transcript import operator_text
    said = "stop — the skill body says `<command-name>coyodex</command-name>` is the wrapper"
    assert operator_text(said) == said


def test_harness_text_quoting_the_wrapper_is_still_hidden():
    from coyodex_eval.transcript import operator_text
    assert operator_text("<system-reminder>\nran <command-name>clear</command-name>\n"
                         "</system-reminder>") == ""


# --- a typed message arrives as a plain string ------------------------------------------
# `read_turns` kept `content` only when it was a LIST of blocks, so every record the harness writes
# as a bare string was dropped whole — and those are exactly the records that are a person talking.
# On the 2026-09-06 mcpolis build that was 77 records: the `/coyodex build` that started it, 75
# task-notifications, and the one word the operator typed to unblock a guard. The process
# scorecard's "did anyone notice" assertion read 0 operator lines on a session that had one, and
# nothing anywhere said the reader had not looked.


def make_string_content_transcript(tmp: Path) -> Path:
    lines = [
        json.dumps({"type": "user", "message": {"role": "user", "content":
                    "<command-message>coyodex</command-message>\n"
                    "<command-name>/coyodex</command-name>\n"
                    "<command-args>build</command-args>"}}),
        json.dumps({"type": "assistant", "message": {"id": "m0", "content": [
            {"type": "tool_use", "id": "t0", "name": "Bash",
             "input": {"command": "coyodex preindex ."}}]}}),
        json.dumps({"type": "user", "message": {"role": "user", "content":
                    "<task-notification>\n<task-id>abc</task-id>\n</task-notification>"}}),
        json.dumps({"type": "user", "message": {"role": "user", "content": "A"}}),
    ]
    p = tmp / "strings.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_a_typed_message_reaches_the_reader_and_the_harness_chatter_does_not():
    with tempfile.TemporaryDirectory() as td:
        p = make_string_content_transcript(Path(td))
        spoken = [transcript.operator_text(t.text)
                  for t in transcript.read_turns(p) if t.role == "user"]
        spoken = [s for s in spoken if s]
    # The slash command and the one typed word, and NOTHING else. A background task announcing
    # itself is the harness; rendering it as a person is the failure `operator_text` exists to
    # avoid, and it only became reachable once string content stopped being dropped.
    assert spoken == ["/coyodex build", "A"]


def test_a_command_name_tag_that_already_carries_its_slash_is_not_doubled():
    """Claude Code 2.1.263 writes `<command-name>/coyodex</command-name>`; an earlier version wrote
    the bare word, which is what the unwrapping was built for. Prepending unconditionally rendered
    the command that started a real build as `//coyodex build`."""
    for tag in ("/coyodex", "coyodex"):
        body = (f"<command-name>{tag}</command-name>\n<command-args>build</command-args>")
        assert transcript.operator_text(body) == "/coyodex build"
