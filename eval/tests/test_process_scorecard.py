#!/usr/bin/env python3
"""L3 unit tests — the reader and the ten assertions, over SYNTHETIC turn sequences.

Run either way (needs an editable install: `make deps`):
    python3 eval/tests/test_process_scorecard.py
    pytest eval/tests/test_process_scorecard.py

Fast, deterministic, and part of the default suite. The CORPUS run — the eight real build
transcripts these detectors were calibrated against — lives in `test_process_corpus.py` and is
opt-in, because those files live outside the repo.

Note what is under test here: the assertion LOGIC, not any transcript. Every turn below is built by
a `make_*` helper, so a detector that only works on one build's shell style fails loudly.

The reader tests earn their keep on one point in particular. A JSONL record is not a turn: this
harness writes each content block of one API response as its own record, interleaved with the tool
results, so a message that emitted ten `Agent` calls looks like ten one-call turns. That was a real
bug in this module, and it produced exactly the wrong answer for the assertion that matters most.
`test_reader_groups_one_message_across_interleaved_tool_results` is the pin.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from coyodex_eval import process_scorecard as P
from coyodex_eval.transcript import ToolCall, Turn, read_turns


# --- builders -------------------------------------------------------------------------

def make_turn(index: int, *calls: ToolCall, results: tuple[tuple[str, str], ...] = ()) -> Turn:
    """One assistant turn. `results` is (tool_use_id, text) pairs carried on the same Turn for
    brevity — the assertions read them through `results_by_tool_use_id`, which does not care which
    turn a result arrived on."""
    from coyodex_eval.transcript import ToolResult
    return Turn(index=index, role="assistant", tool_calls=calls,
                tool_results=tuple(ToolResult(tool_use_id=i, content=t) for i, t in results))


def make_bash(command: str, uid: str = "") -> ToolCall:
    return ToolCall(name="Bash", input={"command": command}, id=uid)


def make_agent(prompt: str = "harvest the entry points", description: str = "Harvest") -> ToolCall:
    return ToolCall(name="Agent", input={"prompt": prompt, "description": description})


def make_write(path: str, content: str = "") -> ToolCall:
    return ToolCall(name="Write", input={"file_path": path, "content": content})


def make_record(kind: str, *, message_id: str = "", blocks: list[dict[str, object]] | None = None,
                usage: dict[str, int] | None = None) -> str:
    """One raw JSONL record, as the harness writes it: ONE content block per record."""
    message: dict[str, object] = {"content": blocks or []}
    if message_id:
        message["id"] = message_id
    if usage is not None:
        message["usage"] = usage
    return json.dumps({"type": kind, "message": message, "isSidechain": False})


def make_transcript_file(tmp: Path, records: list[str]) -> Path:
    p = tmp / "transcript.jsonl"
    p.write_text("\n".join(records) + "\n", encoding="utf-8")
    return p


def score(*turns: Turn) -> dict[int, P.Assertion]:
    return P.score_turns(turns).by_id()


def _capture_stdout(fn: object) -> str:
    """Run a CLI `main()` and return what it printed. Stdlib only; no pytest fixture (the house
    style forbids them), so the redirect is explicit and local."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()  # type: ignore[operator]
    return buf.getvalue()


# --- the reader -----------------------------------------------------------------------

def test_reader_groups_one_message_across_interleaved_tool_results():
    """THE PIN. Ten `Agent` calls in one API response arrive as ten records with the tool results
    between them. They must come back as ONE turn with ten calls, or assertion 3 reports the exact
    opposite of the truth."""
    usage = {"output_tokens": 22617, "input_tokens": 2}
    records = [make_record("assistant", message_id="m1", usage=usage,
                           blocks=[{"type": "thinking", "thinking": "plan the fan-out"}])]
    for n in range(10):
        records.append(make_record("assistant", message_id="m1", usage=usage, blocks=[
            {"type": "tool_use", "id": f"t{n}", "name": "Agent", "input": {"prompt": "harvest"}}]))
        records.append(make_record("user", blocks=[
            {"type": "tool_result", "tool_use_id": f"t{n}", "content": "launched"}]))
    with tempfile.TemporaryDirectory() as td:
        turns = read_turns(make_transcript_file(Path(td), records))
    assistant = [t for t in turns if t.role == "assistant"]
    assert len(assistant) == 1, f"one API response must be one turn, got {len(assistant)}"
    assert len(assistant[0].agent_calls) == 10


def test_reader_starts_a_new_turn_on_a_new_message_id():
    """The mirror: genuinely separate responses stay separate, so a one-agent-per-turn build is not
    silently merged into a batched one."""
    records = []
    for n in range(3):
        records.append(make_record("assistant", message_id=f"m{n}", usage={"output_tokens": n},
                                   blocks=[{"type": "tool_use", "id": f"t{n}", "name": "Agent",
                                            "input": {}}]))
        records.append(make_record("user", blocks=[{"type": "tool_result", "tool_use_id": f"t{n}",
                                                    "content": "ok"}]))
    with tempfile.TemporaryDirectory() as td:
        turns = read_turns(make_transcript_file(Path(td), records))
    assistant = [t for t in turns if t.role == "assistant"]
    assert len(assistant) == 3 and all(len(t.agent_calls) == 1 for t in assistant)


def test_reader_skips_malformed_lines_instead_of_failing():
    """These files are appended to live; a truncated last line is ordinary. Refusing to read a 3 MB
    transcript because of it would break the scorecard exactly when a run was interrupted."""
    def rec(mid: str) -> str:
        return make_record("assistant", message_id=mid,
                           blocks=[{"type": "tool_use", "id": "t", "name": "Bash",
                                    "input": {"command": "ls"}}])
    with tempfile.TemporaryDirectory() as td:
        p = make_transcript_file(Path(td), [rec("m1"), "{not json", "", rec("m2")])
        turns = read_turns(p)
    assert len([t for t in turns if t.role == "assistant"]) == 2


def test_reader_omits_sidechain_turns_by_default():
    """`isSidechain: true` marks a SUB-AGENT's own turns. L3 measures the LEAD's behaviour, so a
    sub-agent's Bash calls must not count as the lead running a command."""
    lead = make_record("assistant", message_id="m1",
                       blocks=[{"type": "tool_use", "id": "a", "name": "Bash",
                                "input": {"command": "coyodex validate"}}])
    sub = json.dumps({"type": "assistant", "isSidechain": True,
                      "message": {"id": "m2", "content": [
                          {"type": "tool_use", "id": "b", "name": "Bash",
                           "input": {"command": "coyodex validate"}}]}})
    with tempfile.TemporaryDirectory() as td:
        p = make_transcript_file(Path(td), [lead, sub])
        assert len(read_turns(p)) == 1
        assert len(read_turns(p, include_sidechains=True)) == 2


def test_grouping_consistency_flags_a_reused_message_id():
    """The turn grouping rests on 'one message id == one API response'. If a harness change broke
    that, the scorecard must say so rather than quietly reporting wrong fan-out numbers."""
    a = make_record("assistant", message_id="m1", usage={"output_tokens": 1}, blocks=[])
    b = make_record("assistant", message_id="m1", usage={"output_tokens": 999}, blocks=[])
    with tempfile.TemporaryDirectory() as td:
        from coyodex_eval.transcript import grouping_is_consistent
        assert grouping_is_consistent(make_transcript_file(Path(td), [a, a])) is True
        assert grouping_is_consistent(make_transcript_file(Path(td), [a, b])) is False


# --- invocation detection (shared by six assertions) ----------------------------------

def test_invokes_ignores_a_command_that_is_only_mentioned():
    """`grep 'coyodex anchor-drift' method.md` mentions the command; it does not run it. Counting
    mentions over-reported shape-only anchor-drift runs across the real corpus."""
    assert not P._invokes("grep -n 'coyodex anchor-drift' method.md", "anchor-drift")
    assert not P._invokes("echo 'run coyodex validate next'", "validate")
    assert P._invokes(".venv/bin/coyodex anchor-drift --map m.json", "anchor-drift")


def test_invokes_ignores_heredoc_and_multiline_string_bodies():
    """A python heredoc that PRINTS the command name is data, not shell."""
    heredoc = "python3 - <<'PY'\n# coyodex anchor-drift is what we are emulating\nprint(1)\nPY"
    assert not P._invokes(heredoc, "anchor-drift")
    inline = 'python3 -c "\nimport json\n# coyodex validate output\nprint(1)\n"'
    assert not P._invokes(inline, "validate")


def test_invokes_accepts_the_binary_behind_a_shell_variable():
    """Every measured build aliases the binary. Requiring the literal token hid every `audit` call
    one build made."""
    assert P._invokes("C=/path/coyodex; $C audit --json", "audit")
    assert P._invokes('CX=/path/coyodex\n"$CX" validate map.json', "validate")
    assert not P._invokes("$PY somethingelse --json", "audit")


def test_invokes_finds_the_command_after_a_pipe_or_conjunction():
    assert P._invokes("cd /repo && /x/coyodex assemble a.json --out .coyodex", "assemble")
    assert P._invokes("echo hi | /x/coyodex validate m.json", "validate")


# --- assertion 1 / 2: the pre-index hand-off ------------------------------------------

def test_a1_counts_only_a_real_report_invocation():
    good = score(make_turn(0, make_bash(".venv/bin/coyodex preindex --report --depth 3")))[1]
    assert (good.observed, good.of, good.score) == (1, 1, 1.0)
    bad = score(make_turn(0, make_bash("grep -n 'preindex --report' method.md")))[1]
    assert (bad.observed, bad.score) == (0, 0.0)


def test_a2_hand_parsing_the_artifact_is_the_defect_and_report_is_not():
    hand = score(make_turn(0, make_bash(
        "python3 -c \"import json; d=json.load(open('.coyodex/preindex.json')); print(d)\"")))[2]
    assert (hand.observed, hand.of) == (0, 1)
    tool = score(make_turn(0, make_bash("coyodex preindex --report --in .coyodex/preindex.json")))[2]
    assert (tool.observed, tool.of) == (1, 1)


def test_a2_does_not_count_housekeeping_that_merely_names_the_file():
    """`git add …/preindex.json` moves the artifact without parsing a byte of it. Counting it was a
    real false positive against the corpus."""
    a = score(make_turn(0, make_bash("git add .coyodex/project-map.json .coyodex/preindex.json")))[2]
    assert (a.observed, a.of) == (1, 1)


def test_a2_catches_a_hand_parse_inside_a_heredoc():
    """Unlike `_invokes`, this assertion MUST look inside the heredoc — that is where the
    hand-parsing lives."""
    a = score(make_turn(0, make_bash(
        "python3 - <<'PY'\nimport json\nd = json.load(open('.coyodex/preindex.json'))\nPY")))[2]
    assert (a.observed, a.of) == (0, 1)


# --- assertion 3: the headline --------------------------------------------------------

def test_a3_scores_batched_fanouts_against_all_fanouts():
    """`of` is every turn that launched an agent; `observed` is those that launched two or more."""
    turns = (make_turn(0, make_agent(), make_agent(), make_agent()),   # batched
             make_turn(1, make_agent()),                              # one per turn
             make_turn(2, make_bash("ls")))                           # not a fan-out
    a = score(*turns)[3]
    assert (a.observed, a.of, a.score) == (1, 2, 0.5)
    assert [e.detail["agents"] for e in a.evidence] == [3, 1]


def test_a3_is_not_applicable_when_nothing_fanned_out():
    """A serial build launched no agents. That is `n/a`, NOT 0.0 — the opportunity never existed,
    and averaging it in with a build that missed the opportunity would hide the difference."""
    a = score(make_turn(0, make_bash("coyodex validate m.json")))[3]
    assert (a.observed, a.of, a.score) == (0, 0, None)


def test_a3_accepts_the_older_task_tool_spelling():
    a = score(make_turn(0, ToolCall(name="Task", input={}), ToolCall(name="Task", input={})))[3]
    assert (a.observed, a.of) == (1, 1)


# --- assertions 4-8 -------------------------------------------------------------------

def test_a4_wants_the_shape_only_pass_not_the_verdicts_one():
    shape = score(make_turn(0, make_bash("coyodex anchor-drift --map m.json | head -40")))[4]
    assert (shape.observed, shape.score) == (1, 1.0)
    verdicts = score(make_turn(0, make_bash("coyodex anchor-drift --map m.json --verdicts v.json")))[4]
    assert (verdicts.observed, verdicts.score) == (0, 0.0)


def test_a5_scores_a_batched_skeptic_fanout_and_zero_when_none_launched():
    batched = score(make_turn(0, make_agent("You are a fresh-context SKEPTIC. Disprove:", "Skeptic 1"),
                              make_agent("You are a fresh-context SKEPTIC. Disprove:", "Skeptic 2")))[5]
    assert (batched.observed, batched.of, batched.score) == (1, 1, 1.0)
    assert "2 skeptic agent(s)" in batched.note
    none = score(make_turn(0, make_agent("harvest the deps", "Harvest deps")))[5]
    assert (none.observed, none.of, none.score) == (0, 1, 0.0), "no skeptics must score 0, not n/a"


def test_a6_counts_only_a_write_not_a_prompt_that_discusses_grounding():
    written = score(make_turn(0, make_write("/r/.coyodex/build-fragments/header.json",
                                            '{"grounding": {"claims_total": 42, '
                                            '"claims_grounded": 42}}')))[6]
    assert (written.observed, written.score) == (1, 1.0)
    talked = score(make_turn(0, make_agent("report claims_total when you finish grounding")))[6]
    assert (talked.observed, talked.score) == (0, 0.0)


def test_a7_separates_the_command_from_a_hand_written_reconcile_file():
    by_tool = score(make_turn(0, make_bash("coyodex reconcile --rules r.json --out "
                                           ".coyodex/reconcile.json")))[7]
    assert (by_tool.observed, by_tool.of, by_tool.score) == (1, 1, 1.0)
    by_hand = score(make_turn(0, make_write("/r/.coyodex/reconcile.json", '{"set": []}')))[7]
    assert (by_hand.observed, by_hand.of, by_hand.score) == (0, 1, 0.0)
    assert "hand-written" in str(by_hand.evidence[0].detail["how"])


def test_a7_sees_a_reconcile_file_produced_by_a_generator_script():
    """The measured builds did not redirect into the file — they wrote a script that opens it.
    A detector that only understood `>` reported that the largest build produced none at all."""
    a = score(make_turn(0, make_write("/tmp/synth.py",
                                      "import json\n"
                                      "json.dump(out, open('.coyodex/reconcile.json', 'w'))\n")))[7]
    assert (a.observed, a.of) == (0, 1)


def test_a7_is_not_applicable_when_no_reconcile_file_was_produced():
    a = score(make_turn(0, make_bash("coyodex validate m.json")))[7]
    assert (a.observed, a.of, a.score) == (0, 0, None)


def test_a8_wants_json_and_penalises_paging_the_human_report():
    good = score(make_turn(0, make_bash("coyodex audit m.json --json > claims.json")))[8]
    assert (good.observed, good.of, good.score) == (1, 1, 1.0)
    paged = score(make_turn(0, make_bash("coyodex audit m.json --json | head -40")))[8]
    assert (paged.observed, paged.of) == (0, 1)
    human = score(make_turn(0, make_bash("coyodex audit m.json | sed -n '1,50p'")))[8]
    assert (human.observed, human.of) == (0, 1)


# --- assertion 9 ----------------------------------------------------------------------

_ESCAPABLE = ("Entities with no SUBDOMAIN (ungrouped / top-level): E4 — record 'E4: <why>' under a "
              "'Happy Path coverage' extras heading")
_PLAIN = "SF60 step 7: a sub-flow's step may not reference a sub-flow (one level only)"


def make_validate_turn(index: int, uid: str, lines: tuple[str, ...]) -> Turn:
    body = "VALIDATION WARNINGS (non-blocking):\n" + "\n".join(f"  - {ln}" for ln in lines)
    return make_turn(index, make_bash("coyodex validate m.json --check-sources", uid),
                     results=((uid, body),))


def test_a9_counts_only_recordable_advisories():
    """An advisory naming no escape token cannot be 'recorded', so counting it as a missed
    reconciliation would be unfair to the build."""
    a = score(make_validate_turn(0, "v1", (_ESCAPABLE, _PLAIN)),
              make_validate_turn(1, "v2", (_PLAIN,)))[9]
    assert (a.observed, a.of, a.score) == (1, 1, 1.0), "the escapable one went; the plain one is not counted"


def test_a9_reports_an_advisory_still_standing_at_the_end():
    a = score(make_validate_turn(0, "v1", (_ESCAPABLE,)),
              make_validate_turn(1, "v2", (_ESCAPABLE,)))[9]
    assert (a.observed, a.of, a.score) == (0, 1, 0.0)
    assert "Entities with no SUBDOMAIN" in str(a.evidence[0].detail["unresolved"])


def test_a9_says_so_when_the_final_view_was_narrowed():
    """A build that ends on `validate | grep -E 'something narrow'` shows one line, against which
    almost anything looks resolved. The score cannot be fixed from a transcript — but it can be
    labelled, and an unlabelled optimistic number is the worse failure."""
    wide = tuple(f"{n}: use a role-revealing verb — record it under a 'Balance exceptions' "
                 f"extras heading" for n in range(10))
    a = score(make_validate_turn(0, "v1", wide), make_validate_turn(1, "v2", (_PLAIN,)))[9]
    assert "FINAL VIEW WAS NARROWED" in a.note


def test_a9_is_not_applicable_without_captured_validate_output():
    a = score(make_turn(0, make_bash("coyodex validate m.json > /dev/null", "v1")))[9]
    assert (a.observed, a.of, a.score) == (0, 0, None)


# --- assertion 10 ---------------------------------------------------------------------

def test_a10_counts_fanouts_that_stayed_under_the_poll_threshold():
    polls = tuple(make_turn(n, make_bash("ls .coyodex/build-fragments/"))
                  for n in range(1, P.POLL_THRESHOLD + 2))
    a = score(make_turn(0, make_agent(), make_agent()), *polls)[10]
    assert (a.observed, a.of, a.score) == (0, 1, 0.0)
    quiet = score(make_turn(0, make_agent(), make_agent()),
                  make_turn(1, make_bash("ls .coyodex/build-fragments/")))[10]
    assert (quiet.observed, quiet.of, quiet.score) == (1, 1, 1.0)


def test_a10_attributes_each_poll_to_the_fanout_it_followed():
    a = score(make_turn(0, make_agent()),
              make_turn(1, make_bash("ls .coyodex/build-fragments/")),
              make_turn(2, make_agent()),
              make_turn(3, make_bash("find .coyodex/build-fragments -name '*.json'")))[10]
    assert (a.observed, a.of) == (2, 2)
    assert [e.detail["after_fanout"] for e in a.evidence] == [0, 2]


def test_a10_is_not_applicable_without_a_fanout():
    a = score(make_turn(0, make_bash("ls .coyodex/build-fragments/")))[10]
    assert (a.observed, a.of, a.score) == (0, 0, None)


# --- the scorecard and its diff -------------------------------------------------------

def test_a_scorecard_round_trips_through_json():
    card = P.score_turns((make_turn(0, make_agent(), make_agent()),), transcript="t.jsonl",
                         label="demo")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "card.json"
        p.write_text(json.dumps(card.as_json(), indent=2), encoding="utf-8")
        back = P.load_scorecard(p)
    assert back.label == "demo" and len(back.assertions) == len(P.ASSERTIONS)
    assert back.by_id()[3].observed == card.by_id()[3].observed


def test_loading_a_foreign_json_is_refused():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "x.json"
        p.write_text('{"kind": "something-else"}', encoding="utf-8")
        try:
            P.load_scorecard(p)
        except ValueError:
            return
    raise AssertionError("a non-scorecard JSON must be refused, not silently scored")


def test_the_diff_reports_direction_relative_to_the_previous_run():
    """Relative like `coyodex-eval`'s gates: which way each number moved. No threshold, no verdict."""
    before = P.score_turns((make_turn(0, make_agent()),), label="before")
    after = P.score_turns((make_turn(0, make_agent(), make_agent()),), label="after")
    rows = {d.id: d for d in P.diff(before, after)}
    assert rows[3].before == 0.0 and rows[3].after == 1.0 and rows[3].direction == "up"
    assert rows[1].direction == "flat"


def test_the_diff_marks_an_assertion_that_became_not_applicable():
    before = P.score_turns((make_turn(0, make_agent()),), label="before")
    after = P.score_turns((make_turn(0, make_bash("ls")),), label="after")
    rows = {d.id: d for d in P.diff(before, after)}
    assert rows[3].after is None and rows[3].direction == "gone"


def test_the_cli_writes_a_scorecard_next_to_the_transcript_and_never_gates():
    """A scorecard, not a gate: exit 0 whatever the numbers say."""
    records = [make_record("assistant", message_id="m1",
                           blocks=[{"type": "tool_use", "id": "t", "name": "Agent", "input": {}}])]
    with tempfile.TemporaryDirectory() as td:
        src = make_transcript_file(Path(td), records)
        assert P.main([str(src)]) == 0
        out = src.with_suffix(".l3-scorecard.json")
        assert out.is_file()
        card = P.load_scorecard(out)
        assert card.by_id()[3].score == 0.0        # a missed opportunity…
        assert P.main([str(src)]) == 0             # …and still exit 0


def test_the_cli_diff_mode_exits_zero_and_the_missing_file_case_does_not():
    with tempfile.TemporaryDirectory() as td:
        a = Path(td) / "a.json"
        b = Path(td) / "b.json"
        for p, label in ((a, "before"), (b, "after")):
            card = P.score_turns((make_turn(0, make_agent()),), label=label)
            p.write_text(json.dumps(card.as_json()), encoding="utf-8")
        assert P.main(["--diff", str(a), str(b)]) == 0
        assert P.main([str(Path(td) / "nope.jsonl")]) == 2


# --- the transcript slice command (what /coyodex-retro reads with) --------------------

def make_slice_transcript(tmp: Path) -> Path:
    """A transcript with a fan-out, a Bash call and its result — enough to exercise every mode."""
    records = [
        make_record("assistant", message_id="m1", blocks=[
            {"type": "tool_use", "id": "t0", "name": "Bash",
             "input": {"command": "coyodex preindex --report"}}]),
        make_record("user", blocks=[
            {"type": "tool_result", "tool_use_id": "t0", "content": "WEIGHT TREE\n  src loc=10"}]),
        make_record("assistant", message_id="m2", blocks=[
            {"type": "tool_use", "id": "t1", "name": "Agent",
             "input": {"description": "Harvest deps", "prompt": "…"}}]),
        make_record("assistant", message_id="m2", blocks=[
            {"type": "tool_use", "id": "t2", "name": "Agent",
             "input": {"description": "Harvest entry points", "prompt": "…"}}]),
    ]
    return make_transcript_file(tmp, records)


def test_the_transcript_index_gives_one_line_per_tool_call_with_its_turn():
    """The index is what a lead reads to choose a range. One line per call, turn number first —
    a 3 MB JSONL is not readable any other way."""
    from coyodex_eval import transcript as T
    with tempfile.TemporaryDirectory() as td:
        src = make_slice_transcript(Path(td))
        out = _capture_stdout(lambda: T.main([str(src)]))
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) == 3
    assert "Bash" in lines[0] and "coyodex preindex --report" in lines[0]
    assert lines[0].startswith("[   0]")
    assert "Harvest deps" in lines[1] and "Harvest entry points" in lines[2]


def test_the_full_mode_includes_what_the_command_printed():
    """A sub-agent judging a phase needs the OUTPUT, not just the call — that is where a tool bug
    shows itself."""
    from coyodex_eval import transcript as T
    with tempfile.TemporaryDirectory() as td:
        src = make_slice_transcript(Path(td))
        out = _capture_stdout(lambda: T.main([str(src), "--full"]))
    assert "WEIGHT TREE" in out


def test_the_slice_filters_by_range_tool_and_pattern():
    from coyodex_eval import transcript as T
    with tempfile.TemporaryDirectory() as td:
        src = make_slice_transcript(Path(td))
        by_tool = _capture_stdout(lambda: T.main([str(src), "--tool", "Agent"]))
        assert "preindex" not in by_tool and "Harvest deps" in by_tool
        by_grep = _capture_stdout(lambda: T.main([str(src), "--grep", "entry points"]))
        assert "Harvest entry points" in by_grep and "Harvest deps" not in by_grep
        by_range = _capture_stdout(lambda: T.main([str(src), "--from", "0", "--to", "0"]))
        assert "preindex" in by_range and "Harvest" not in by_range


def test_the_stats_mode_lists_tool_counts_and_fanout_sizes():
    """The fan-out map is how the retro cuts the transcript into phases."""
    from coyodex_eval import transcript as T
    with tempfile.TemporaryDirectory() as td:
        src = make_slice_transcript(Path(td))
        out = _capture_stdout(lambda: T.main([str(src), "--stats"]))
    assert "Bash" in out and "Agent" in out
    assert "2 agent(s)" in out, out


def test_the_transcript_command_reports_a_missing_file():
    from coyodex_eval import transcript as T
    with tempfile.TemporaryDirectory() as td:
        assert T.main([str(Path(td) / "nope.jsonl")]) == 2


def test_every_assertion_id_is_unique_and_skips_the_reserved_eleven():
    """11 is RESERVED for the trapdoor golden-map comparison (L3-DESIGN.md: "11 is deliberately
    absent"), so a new transcript-only assertion takes 12 rather than filling the hole."""
    ids = [a.id for a in P.score_turns(()).assertions]
    # 20 is also absent: "the lead re-verified every applied refutation" has no reliable transcript
    # signature (a refutation is reconciled by an ordinary map write, and the read that justifies it
    # is an ordinary file read), so the number is reserved rather than filled with a guess.
    assert ids == [*range(1, 11), *range(12, 20), 21, 22], ids
    assert 11 not in ids, "id 11 is reserved for the fixture-specific golden-map assertion"
    assert len(ids) == len(set(ids))


def _main() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}\n  {str(exc)[:500]}\n")
    print(f"{len(fns) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())


# --- assertions 6 and 10, after the 2026-08-01 retro found both measuring the wrong thing --------


def make_grounded_map(tmp: Path, grounding: dict | None) -> Path:
    p = tmp / "project-map.json"
    doc: dict = {"format": "coyodex-map", "title": "T", "goal": "g"}
    if grounding is not None:
        doc["grounding"] = grounding
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_assertion_6_reads_the_map_when_one_is_given():
    with tempfile.TemporaryDirectory() as td:
        m = make_grounded_map(Path(td), {"claims_total": 418, "claims_challenged": 418})
        ctx = P.read_score_context(m)
        # no transcript evidence at all — the map alone must satisfy it
        a = P.assert_6_grounding_recorded((), ctx)
        assert (a.observed, a.of) == (1, 1) and a.note == "read from the map"


def test_assertion_6_scores_zero_when_the_map_carries_no_grounding():
    with tempfile.TemporaryDirectory() as td:
        ctx = P.read_score_context(make_grounded_map(Path(td), None))
        a = P.assert_6_grounding_recorded((), ctx)
        assert (a.observed, a.of) == (0, 1)


def test_assertion_6_counts_the_command_not_only_a_hand_written_record():
    """The inversion: `coyodex grounding write` never puts `claims_total` in its own command text,
    so the CORRECT path scored 0 while a python heredoc that hand-tallied the record scored 1."""
    by_command = (make_turn(0, make_bash(
        "coyodex grounding write --worklist wl.json --verdicts v.json --out g.json")),)
    a = P.assert_6_grounding_recorded(by_command)
    assert (a.observed, a.of) == (1, 1)
    assert a.evidence[0].detail["how"] == "coyodex grounding write"


def test_assertion_10_counts_a_no_op_turn_not_only_a_fragment_dir_poll():
    """A live build waited with `echo .` 39 times and scored a PERFECT 38/38 on the old rule, which
    only saw ls/find/stat/wc naming the fragment dir."""
    turns = [make_turn(0, make_agent())]
    turns += [make_turn(i, make_bash("echo .")) for i in range(1, 6)]
    a = P.score_turns(tuple(turns)).by_id()[10]
    assert (a.observed, a.of) == (0, 1), "5 no-op turns must break the threshold of 3"
    assert all(e.detail["kind"] == "no-op turn" for e in a.evidence)


def test_assertion_10_still_counts_the_original_fragment_dir_poll():
    turns = [make_turn(0, make_agent())]
    turns += [make_turn(i, make_bash("ls .coyodex/build-fragments/*.json | wc -l"))
              for i in range(1, 6)]
    a = P.score_turns(tuple(turns)).by_id()[10]
    assert (a.observed, a.of) == (0, 1)
    assert all(e.detail["kind"] == "fragment-dir poll" for e in a.evidence)


def test_assertion_10_leaves_real_work_alone():
    turns = (make_turn(0, make_agent()),
             make_turn(1, make_bash("echo hello > out.txt")),      # a redirect is not a no-op
             make_turn(2, make_bash("coyodex validate map.json")))
    a = P.score_turns(turns).by_id()[10]
    assert (a.observed, a.of) == (1, 1) and a.evidence == ()


def test_a_noop_wait_recognises_the_shapes_a_build_actually_used():
    assert P._is_noop_wait("echo .")
    assert P._is_noop_wait("sleep 120")
    assert P._is_noop_wait("sleep 1; echo waiting")
    assert P._is_noop_wait('echo "waiting on agents"')
    assert not P._is_noop_wait("echo x > f")
    assert not P._is_noop_wait("sleep 120; ls *.json | wc -l")
    assert not P._is_noop_wait("")


# --- assertions 13-17, added from the 2026-08-01 retro -------------------------------------------


def test_13_flags_a_grounding_record_written_before_the_reconcile_edits():
    turns = (make_turn(0, make_bash("coyodex grounding write --worklist wl.json --out g.json")),
             make_turn(1, make_bash("python3 - <<'PY'\njson.dump(d, open('.coyodex/build-fragments/x.json','w'))\nPY")))
    a = P.score_turns(turns).by_id()[13]
    assert (a.observed, a.of) == (0, 1)


def test_13_passes_when_nothing_is_written_after_the_record():
    turns = (make_turn(0, make_bash("python3 - <<'PY'\njson.dump(d, open('.coyodex/build-fragments/x.json','w'))\nPY")),
             make_turn(1, make_bash("coyodex grounding write --worklist wl.json --out g.json")))
    a = P.score_turns(turns).by_id()[13]
    assert (a.observed, a.of) == (1, 1)


def test_14_catches_a_pinned_total_that_the_live_worklist_contradicts():
    turns = (make_turn(0, make_bash("coyodex grounding write", uid="g"),
                       results=(("g", "wrote g.json: 418 of 418 claim(s) challenged"),)),
             make_turn(1, make_bash("coyodex anchor-drift --map m.json", uid="d"),
                       results=(("d", "2 drifted anchor(s) · challenged 403 of 415 worklist claim(s)"),)))
    a = P.score_turns(turns).by_id()[14]
    assert (a.observed, a.of) == (0, 1) and "418" in a.note and "415" in a.note


def test_15_catches_a_gate_rerun_narrowed_by_a_grep():
    turns = (make_turn(0, make_bash("coyodex validate map.json --check-sources")),
             make_turn(1, make_bash("coyodex validate map.json --check-sources | grep 'carry no'")))
    a = P.score_turns(turns).by_id()[15]
    assert (a.observed, a.of) == (0, 1)


def test_15_allows_a_rerun_that_widens_the_view():
    turns = (make_turn(0, make_bash("coyodex validate map.json | grep x")),
             make_turn(1, make_bash("coyodex validate map.json")))
    a = P.score_turns(turns).by_id()[15]
    assert (a.observed, a.of) == (1, 1)


def make_timed_turn(index: int, stamp: str, *calls: ToolCall) -> Turn:
    return Turn(index=index, role="assistant", tool_calls=calls, timestamp=stamp)


def make_result_turn(index: int, stamp: str, uid: str) -> Turn:
    from coyodex_eval.transcript import ToolResult
    return Turn(index=index, role="user", timestamp=stamp,
                tool_results=(ToolResult(tool_use_id=uid, content="done"),))


def test_16_flags_the_slowest_slice_dispatched_last():
    def agent(uid: str) -> ToolCall:
        return ToolCall(name="Agent", input={"description": uid}, id=uid)
    turns = (
        make_timed_turn(0, "2026-08-01T08:00:00Z", agent("a")),
        make_timed_turn(1, "2026-08-01T08:00:10Z", agent("b")),
        make_timed_turn(2, "2026-08-01T08:00:20Z", agent("c")),   # dispatched last, runs longest
        make_result_turn(3, "2026-08-01T08:05:00Z", "a"),
        make_result_turn(4, "2026-08-01T08:05:10Z", "b"),
        make_result_turn(5, "2026-08-01T08:20:00Z", "c"),
    )
    a = P.score_turns(turns).by_id()[16]
    assert (a.observed, a.of) == (0, 1)
    assert a.evidence[0].detail["dispatched"] == 3


def test_16_passes_when_the_slowest_goes_first():
    def agent(uid: str) -> ToolCall:
        return ToolCall(name="Agent", input={"description": uid}, id=uid)
    turns = (
        make_timed_turn(0, "2026-08-01T08:00:00Z", agent("a")),   # longest, dispatched first
        make_timed_turn(1, "2026-08-01T08:00:10Z", agent("b")),
        make_timed_turn(2, "2026-08-01T08:00:20Z", agent("c")),
        make_result_turn(3, "2026-08-01T08:20:00Z", "a"),
        make_result_turn(4, "2026-08-01T08:05:10Z", "b"),
        make_result_turn(5, "2026-08-01T08:05:20Z", "c"),
    )
    a = P.score_turns(turns).by_id()[16]
    assert (a.observed, a.of) == (1, 1)


def test_17_flags_a_drift_exception_recorded_without_opening_the_file():
    record = "- anchor-drift `E1 runs on cadence 'continuous'`: the stored anchor is right."
    turns = (make_turn(0, make_bash("coyodex anchor-drift --map m.json", uid="d"),
                       results=(("d", "E1 runs on cadence 'continuous': stored [src/session.ts:21] "
                                      "— skeptics found a different file"),)),
             make_turn(1, make_write("frag.json", record)))
    a = P.score_turns(turns).by_id()[17]
    assert (a.observed, a.of) == (0, 1)
    assert a.evidence[0].detail["should_have_read"] == "src/session.ts"


def test_17_passes_when_the_cited_file_was_read_after_the_finding():
    record = "- anchor-drift `E1 runs on cadence 'continuous'`: the stored anchor is right."
    turns = (make_turn(0, make_bash("coyodex anchor-drift --map m.json", uid="d"),
                       results=(("d", "E1 runs on cadence 'continuous': stored [src/session.ts:21] "
                                      "— skeptics found a different file"),)),
             make_turn(1, make_bash("sed -n '15,30p' src/session.ts")),
             make_turn(2, make_write("frag.json", record)))
    a = P.score_turns(turns).by_id()[17]
    assert (a.observed, a.of) == (1, 1)


def test_17_does_not_count_merely_naming_the_file_in_a_patch_script():
    """A fragment-patching heredoc mentions the very path being recorded; counting that as 'looked'
    turned this assertion into a false 1.00 on the build that motivated it."""
    record = "- anchor-drift `E1 runs on cadence 'continuous'`: the stored anchor is right."
    turns = (make_turn(0, make_bash("coyodex anchor-drift --map m.json", uid="d"),
                       results=(("d", "E1 runs on cadence 'continuous': stored [src/session.ts:21] "
                                      "— skeptics found a different file"),)),
             make_turn(1, make_bash("python3 - <<'PY'\nd['x']='src/session.ts:33'\nPY")),
             make_turn(2, make_write("frag.json", record)))
    a = P.score_turns(turns).by_id()[17]
    assert (a.observed, a.of) == (0, 1)


# ── coyodex_subcommands: the index truncated, and a real finding was published wrong ─────────────

def test_a_subcommand_chained_behind_another_is_still_counted():
    """The one-line index truncates at 100 chars, so a subcommand after a `;` or `&&` was invisible
    there. A retrospective read the index, concluded `grounding write` "never ran", and published
    that about a build which ran it at turn 489 chained behind an `assemble`."""
    from coyodex_eval.transcript import coyodex_subcommands
    turns = [make_turn(489, make_bash(
        "/p/.venv/bin/coyodex assemble .coyodex/build-fragments/*.json --out .coyodex "
        "--reconcile .coyodex/reconcile.json 2>&1 | tail -3; echo '=== grounding write ==='; "
        "/p/.venv/bin/coyodex grounding write --worklist .coyodex/verify/worklist.json "
        "--out .coyodex/build-fragments/grounding.json"))]
    found = coyodex_subcommands(turns)
    assert (489, "assemble") in found
    assert (489, "grounding write") in found, found


def test_an_aliased_binary_is_counted_but_prose_is_not():
    """Builds alias the binary (`CX=…/coyodex; $CX audit …`), so the pattern must follow `$CX` — and
    a pattern loose enough for that reads `$SP files` as a subcommand unless it is allowlisted.
    The first cut reported `files`, `loc`, `map` and `runs` as coyodex subcommands."""
    from coyodex_eval.transcript import coyodex_subcommands
    turns = [make_turn(7, make_bash("CX=/p/.venv/bin/coyodex\n$CX audit map.json --json; "
                                    "ls $SP files; wc -l $OUT map"))]
    found = coyodex_subcommands(turns)
    assert (7, "audit") in found
    assert [n for _i, n in found] == ["audit"], found


def test_the_four_fix_verbs_are_reported_apart():
    """`fix dedup-edge` and `fix apply-drift` are different acts and a retro needs to tell them
    apart; anything not a known sub-verb stays at subcommand granularity."""
    from coyodex_eval.transcript import coyodex_subcommands
    turns = [make_turn(1, make_bash("coyodex fix dedup-edge --map m.json --accept-suggested")),
             make_turn(2, make_bash("coyodex fix apply-drift --map m.json --verdicts v.json")),
             make_turn(3, make_bash("coyodex validate m.json --check-sources"))]
    names = [n for _i, n in coyodex_subcommands(turns)]
    assert names == ["fix dedup-edge", "fix apply-drift", "validate"]


# ── 18-22 ────────────────────────────────────────────────────────────────────────────────────────

def test_a18_catches_a_commit_claiming_a_shape_the_map_does_not_have():
    """A live commit claimed "416 backbone edges … 33 flows/sub-flows" for a map holding 365 and 36.
    Both had been true earlier in the build; `fix dedup-edge` then dropped 49 duplicates."""
    gate = ("Shape: 66 components in 14 subsystems, 55 entities in 8 subdomains, 40 deps, "
            "26 use cases, 365 edges, 36 flows/sub-flows, 281 entry points, 26 security rows.")
    turns = [make_turn(1, make_bash("coyodex finalize map.json --emit-gate-block g.txt", uid="u1"),
                       results=(("u1", gate),)),
             make_turn(2, make_bash("git commit -m 'map: 416 backbone edges, 36 flows/sub-flows'"))]
    a = P.assert_18_commit_shape_matches_the_map(turns)
    assert a.of == 2 and a.observed == 1, a
    assert any("416" in str(e.detail) for e in a.evidence), a.evidence


def test_a19_sees_an_inverting_grep_that_is_not_a_pipeline():
    """The real shape redirects the gate to a file and inverts the grep on the FILE, so a
    `gate | grep -v` pattern saw nothing. The full output being on disk does not help when the view
    the agent reads is the inverted one."""
    turns = [make_turn(1, make_bash(
        "coyodex validate map.json --check-sources > /tmp/v5.txt 2>&1; echo \"exit=$?\"; "
        "grep -v 'declared .* times with differing' /tmp/v5.txt | head -40"))]
    a = P.assert_19_no_gate_output_inverted_grep(turns)
    assert a.observed == 0 and a.of == 1, a


def test_a19_leaves_an_ordinary_gate_run_alone():
    turns = [make_turn(1, make_bash("coyodex validate map.json --check-sources --check-coverage"))]
    a = P.assert_19_no_gate_output_inverted_grep(turns)
    assert a.observed == 1 and a.of == 1


def test_a21_reads_only_the_final_assemble():
    """An unhealed count mid-build is expected and drains as the trace lands; only the last one
    means anything. A live build was told UNHEALED 4 at four successive assembles and shipped."""
    turns = [make_turn(1, make_bash("coyodex assemble f/*.json --out .coyodex", uid="a1"),
                       results=(("a1", "assembled — UNHEALED riding steps 4"),)),
             make_turn(2, make_bash("coyodex assemble f/*.json --out .coyodex", uid="a2"),
                       results=(("a2", "assembled — dup-edges collapsed 3"),))]
    assert P.assert_21_final_assemble_digest_is_clean(turns).observed == 1
    turns.append(make_turn(3, make_bash("coyodex assemble f/*.json --out .coyodex", uid="a3"),
                           results=(("a3", "assembled — UNHEALED riding steps 4"),)))
    a = P.assert_21_final_assemble_digest_is_clean(turns)
    assert a.observed == 0 and a.of == 1, a


def test_a22_catches_a_structural_harvest_before_any_behavioral_draft():
    """`preindex` prints GR1 on every run. A live build read it, harvested 14 structural slices, and
    wrote its behavioral fragment 79 turns later."""
    late = [make_turn(1, make_bash("coyodex preindex --out .coyodex/preindex.json")),
            make_turn(9, make_write(".coyodex/build-fragments/behavioral.json",
                                    '{"use_cases": [{"id": "UC1"}]}'))]
    assert P.assert_22_behavioral_draft_precedes_preindex(late).observed == 0
    early = [make_turn(1, make_write(".coyodex/build-fragments/behavioral.json",
                                     '{"use_cases": [{"id": "UC1"}]}')),
             make_turn(9, make_bash("coyodex preindex --out .coyodex/preindex.json"))]
    assert P.assert_22_behavioral_draft_precedes_preindex(early).observed == 1


def test_the_new_assertions_are_all_registered():
    ids = [a.id for a in P.score_turns(()).assertions]
    for new in (18, 19, 21, 22):
        assert new in ids, (new, ids)


def test_13_allows_the_final_assemble_that_the_method_now_prescribes():
    """The record lives in a FRAGMENT, so a final assemble is the only way it reaches the map — and
    `grounding write --map` needs the assembled map to measure the live claim surface. Before this
    carve-out the assertion scored 0 for every build that followed the method: the redirection in
    `assemble … 2>&1 | tail -3` alone matched the file-write pattern."""
    turns = (make_turn(0, make_bash("coyodex grounding write --worklist wl.json --map m.json "
                                    "--out .coyodex/build-fragments/grounding.json")),
             make_turn(1, make_bash("coyodex assemble .coyodex/build-fragments/*.json "
                                    "--out .coyodex --reconcile .coyodex/reconcile.json 2>&1 | tail -3")))
    a = P.score_turns(turns).by_id()[13]
    assert (a.observed, a.of) == (1, 1), a


def test_13_still_catches_a_hand_edit_after_the_record():
    turns = (make_turn(0, make_bash("coyodex grounding write --worklist wl.json --out g.json")),
             make_turn(1, make_write(".coyodex/build-fragments/sec.json", "{}")))
    assert P.score_turns(turns).by_id()[13].observed == 0


def test_14_accepts_a_differing_total_when_the_record_states_the_delta():
    """`total != live` is now LEGAL and expected: reconciling a refutation rewrites its claim, and
    the pin cannot be recomputed (that records `refuted 0`). What the assertion asks is whether the
    record SAYS why."""
    turns = (make_turn(0, make_bash("coyodex grounding write --worklist wl.json --map m.json", uid="g"),
                       results=(("g", "wrote g.json: 446 of 446 claim(s) challenged · vs the live "
                                      "map: 6 superseded, 4 added since the pin"),)),
             make_turn(1, make_bash("coyodex audit m.json --json", uid="a"),
                       results=(("a", "444 L2 claims on the grounding worklist"),)))
    a = P.score_turns(turns).by_id()[14]
    assert (a.observed, a.of) == (1, 1), a
