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
    # 19 is WITHDRAWN (unmeasurable — see L3-DESIGN.md) and 20 is RESERVED (no transcript
    # signature). 23 replaces 19 by measuring the OUTCOME instead of the technique.
    # 24 and 25 came from the 2026-08-02 retrospective: an inert recorded exception (a correctly
    # spelled key silencing nothing, indistinguishable from a typo), and a `fix dedup-edge
    # --to-reconcile` run that recorded no directive (the flag used to be a silent no-op).
    assert ids == [*range(1, 11), *range(12, 19), 21, 22, 23, 24, 25], ids
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
    # A real record lives under the `Drift exceptions` extras heading — which is what marks it as a
    # RECORD rather than prose that happens to say "anchor-drift". A bare line is not the shape a
    # fragment carries, and treating any mention as a record made this assertion count
    # documentation text and a Python regex literal as recorded exceptions.
    record = ('{"extras": [{"heading": "Drift exceptions", "body": '
              '"- anchor-drift `E1 runs on cadence \'continuous\'`: the stored anchor is right."}]}')
    turns = (make_turn(0, make_bash("coyodex anchor-drift --map m.json", uid="d"),
                       results=(("d", "E1 runs on cadence 'continuous': stored [src/session.ts:21] "
                                      "— skeptics found a different file"),)),
             make_turn(1, make_write("frag.json", record)))
    a = P.score_turns(turns).by_id()[17]
    assert (a.observed, a.of) == (0, 1)
    assert a.evidence[0].detail["should_have_read"] == "src/session.ts"


def test_17_passes_when_the_cited_file_was_read_after_the_finding():
    # A real record lives under the `Drift exceptions` extras heading — which is what marks it as a
    # RECORD rather than prose that happens to say "anchor-drift". A bare line is not the shape a
    # fragment carries, and treating any mention as a record made this assertion count
    # documentation text and a Python regex literal as recorded exceptions.
    record = ('{"extras": [{"heading": "Drift exceptions", "body": '
              '"- anchor-drift `E1 runs on cadence \'continuous\'`: the stored anchor is right."}]}')
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
    # A real record lives under the `Drift exceptions` extras heading — which is what marks it as a
    # RECORD rather than prose that happens to say "anchor-drift". A bare line is not the shape a
    # fragment carries, and treating any mention as a record made this assertion count
    # documentation text and a Python regex literal as recorded exceptions.
    record = ('{"extras": [{"heading": "Drift exceptions", "body": '
              '"- anchor-drift `E1 runs on cadence \'continuous\'`: the stored anchor is right."}]}')
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

def test_a18_scores_the_flow_the_method_actually_prescribes():
    """`finalize --emit-gate-block` writes the Shape line to a FILE and `method.md` prescribes
    `git commit -F <file>`, so neither number is in a command string. The first cut scanned tool
    results for the Shape line and command text for the claim, and scored 0/0 on all eight real
    build transcripts."""
    gate = ("Shape: 66 components in 14 subsystems, 55 entities in 8 subdomains, 40 deps, "
            "26 use cases, 365 edges, 36 flows/sub-flows, 281 entry points, 26 security rows.")
    turns = [make_turn(1, make_bash("coyodex finalize m.json --emit-gate-block /tmp/g.txt", uid="f"),
                       results=(("f", "finalize: wrote the commit-message gate block to /tmp/g.txt"),)),
             make_turn(2, make_bash("cat /tmp/g.txt", uid="c"), results=(("c", gate),)),
             make_turn(3, make_bash("git commit -F /tmp/msg.txt"))]
    a = P.assert_18_commit_shape_matches_the_map(turns)
    assert a.of == 0 and "no generated" not in (a.note or ""), a


def test_a18_compares_numbers_a_commit_states_alongside_the_generated_line():
    gate = ("Shape: 66 components in 14 subsystems, 55 entities in 8 subdomains, 40 deps, "
            "26 use cases, 365 edges, 36 flows/sub-flows, 281 entry points, 26 security rows.")
    turns = [make_turn(1, make_bash("coyodex finalize m.json", uid="f"), results=(("f", gate),)),
             make_turn(2, make_bash("git commit -F - <<'MSG'\n66 components, 416 edges\nMSG"))]
    a = P.assert_18_commit_shape_matches_the_map(turns)
    assert (a.observed, a.of) == (1, 2), a
    assert any("416" in str(e.detail) for e in a.evidence), a.evidence


def test_a18_says_so_when_a_commit_had_no_generated_line_to_check_against():
    turns = [make_turn(1, make_bash("git commit -m 'map: 416 backbone edges'"))]
    a = P.assert_18_commit_shape_matches_the_map(turns)
    assert a.of == 0 and "no generated" in (a.note or ""), a
def test_a21_reads_only_the_final_assemble():
    """An unhealed count mid-build is expected and drains as the trace lands; only the last one
    means anything. A live build was told UNHEALED 4 at four successive assembles and shipped."""
    turns = [make_turn(1, make_bash("coyodex assemble f/*.json --out .coyodex", uid="a1"),
                       results=(("a1", "model: C:5 | ops: UNHEALED riding steps 4"),)),
             make_turn(2, make_bash("coyodex assemble f/*.json --out .coyodex", uid="a2"),
                       results=(("a2", "model: C:5 | ops: dup-edges collapsed 3"),))]
    assert P.assert_21_final_assemble_digest_is_clean(turns).observed == 1
    turns.append(make_turn(3, make_bash("coyodex assemble f/*.json --out .coyodex", uid="a3"),
                           results=(("a3", "model: C:5 | ops: UNHEALED riding steps 4"),)))
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
    for new in (18, 21, 22):
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


# ── the assertion-17 repair itself, which shipped untested ───────────────────────────────────────

def test_17_sees_a_record_written_through_record_line_with_escaped_backticks():
    """`coyodex record --line "anchor-drift \\`…"` is the DOCUMENTED way to write a record, and
    nested quoting escapes the backtick again. Requiring a bare one made three well-formed records
    invisible on a live build, which then scored 0 for a behaviour it had performed."""
    turns = (make_turn(0, make_bash("coyodex anchor-drift --map m.json", uid="d"),
                       results=(("d", "E1 runs on cadence 'continuous': stored [src/session.ts:21] "
                                      "— skeptics found a different file"),)),
             make_turn(1, make_bash("sed -n '15,30p' src/session.ts")),
             make_turn(2, make_bash(
                 'coyodex record --map m.json --heading "Drift exceptions" --line '
                 '"anchor-drift \\\\`E1 runs on cadence \'continuous\'\\\\`: the stored anchor is right."')))
    a = P.score_turns(turns).by_id()[17]
    assert (a.observed, a.of) == (1, 1), a


def test_17_pairs_a_record_when_the_findings_were_captured_as_json():
    """A build that ran `anchor-drift --json` produced no `stored [path:line]` text at all, so every
    record scored "(no matching drift finding)" — the assertion reporting 0 for a reason other than
    the behaviour it audits."""
    payload = ('{"drift": [{"claim": "E1 runs on cadence \'continuous\'", '
               '"stored": "src/session.ts:21", "corrected": "src/session.ts:33"}]}')
    record = ('{"extras": [{"heading": "Drift exceptions", "body": '
              '"- anchor-drift `E1 runs on cadence \'continuous\'`: the stored anchor is right."}]}')
    turns = (make_turn(0, make_bash("coyodex anchor-drift --map m.json --json", uid="d"),
                       results=(("d", payload),)),
             make_turn(1, make_bash("sed -n '15,30p' src/session.ts")),
             make_turn(2, make_write("frag.json", record)))
    a = P.score_turns(turns).by_id()[17]
    assert (a.observed, a.of) == (1, 1), a


def test_17_does_not_count_prose_or_a_regex_that_merely_says_anchor_drift():
    """Relaxing the scan gate to any occurrence of the word made this count documentation text
    (`{claim}`) and a Python regex literal (`(.+?)`, written while debugging a record) as recorded
    exceptions, inflating the denominator on every transcript measured — one went 0/18 to 0/19."""
    # The quoted text is the REAL claim, so it pairs with the finding — which is what makes this a
    # test of the GATE and not of the unpaired-key handling. It is still not a record: nobody wrote
    # anything under the heading, they printed a diagnostic about one.
    turns = (make_turn(0, make_bash("coyodex anchor-drift --map m.json", uid="d"),
                       results=(("d", "E1 runs on cadence 'continuous': stored [src/session.ts:21] "
                                      "— skeptics found a different file"),)),
             make_turn(1, make_bash(
                 "python3 - <<'PY'\n"
                 "print(\"checking anchor-drift `E1 runs on cadence 'continuous'`: does it parse?\")\nPY")))
    a = P.score_turns(turns).by_id()[17]
    assert a.of == 0, f"a diagnostic ABOUT a record is not a record: {a}"


def test_17_reports_a_key_that_names_no_finding_instead_of_scoring_it():
    """Such a key is not an unread FILE, so it does not belong in the denominator — but a record
    matching nothing is worth knowing about, so it is reported."""
    record = ('{"extras": [{"heading": "Drift exceptions", "body": '
              '"- anchor-drift `a claim this run never reported`: judged fine."}]}')
    turns = (make_turn(0, make_bash("coyodex anchor-drift --map m.json", uid="d"),
                       results=(("d", "E1 runs on cadence 'x': stored [src/session.ts:21] — drift"),)),
             make_turn(1, make_write("frag.json", record)))
    a = P.score_turns(turns).by_id()[17]
    assert a.of == 0 and "matched no drift finding" in (a.note or ""), a


def test_21_cannot_score_when_the_digest_was_not_captured():
    """Treating "no UNHEALED in the captured output" as clean over-credited a build that piped the
    digest through `| tail -2` — and assemble.py records a live build reading this very output with
    `| tail -4`. A scorecard may under-credit, never over-credit."""
    turns = (make_turn(0, make_bash("coyodex assemble f/*.json --out .coyodex | tail -2", uid="a"),
                       results=(("a", "Next: coyodex validate .coyodex/project-map.json"),)),)
    assert P.assert_21_final_assemble_digest_is_clean(turns).of == 0
    turns2 = (make_turn(0, make_bash("coyodex assemble f/*.json --out .coyodex", uid="a"),
                        results=(("a", "model: C:66, D:40 | ops: dup-edges collapsed 38"),)),)
    assert P.assert_21_final_assemble_digest_is_clean(turns2).observed == 1


def test_21_still_flags_an_unhealed_count_in_a_captured_digest():
    turns = (make_turn(0, make_bash("coyodex assemble f/*.json --out .coyodex", uid="a"),
                       results=(("a", "model: C:66 | ops: UNHEALED riding steps 4"),)),)
    a = P.assert_21_final_assemble_digest_is_clean(turns)
    assert (a.observed, a.of) == (0, 1), a


def test_the_subcommand_allowlist_matches_both_clis():
    """A missing name is a SILENT undercount — precisely the failure `--commands` exists to fix.
    The first cut omitted `bless`, `claims`, `hash` and `protocol`, and carried `impact`, which is
    not a coyodex-eval subcommand."""
    import re
    from pathlib import Path
    from coyodex_eval.transcript import _COYODEX_SUBCOMMANDS
    repo = Path(__file__).resolve().parents[2]
    declared: set[str] = set()
    for rel in ("tools/coyodex/cli.py", "eval/tools/coyodex_eval/cli.py"):
        declared |= set(re.findall(r'cmd == "([a-z-]+)"',
                                   (repo / rel).read_text(encoding="utf-8")))
    assert declared, "the CLIs must declare their commands as `cmd == \"...\"`, or this cannot check"
    missing = sorted(declared - set(_COYODEX_SUBCOMMANDS))
    extra = sorted(set(_COYODEX_SUBCOMMANDS) - declared)
    assert not missing, f"subcommand(s) the CLIs have and --commands would never count: {missing}"
    assert not extra, f"names in the allowlist that no CLI declares: {extra}"


def test_14_does_not_pass_on_prose_that_merely_mentions_the_words():
    """It scored 1/1 on a transcript with NO grounding record, because `explained` was set from any
    blob carrying "superseded" — and the trigger was a developer writing the test that asserts the
    pass. Only an actual `grounding write --map` counts."""
    turns = (make_turn(0, make_bash("echo hi", uid="e"),
                       results=(("e", "446 of 446 claim(s) challenged (6 superseded)"),)),
             make_turn(1, make_bash("coyodex audit m.json --json", uid="a"),
                       results=(("a", "444 L2 claims on the grounding worklist"),)))
    a = P.score_turns(turns).by_id()[14]
    assert (a.observed, a.of) == (0, 1), a


def test_14_stays_explained_when_a_later_log_repeats_the_counts():
    """`explained` was reassigned on every match, so an honest run failed if a later `cat` of an old
    log re-matched "N of M claim(s) challenged"."""
    turns = (make_turn(0, make_bash("coyodex grounding write --worklist w.json --map m.json", uid="g"),
                       results=(("g", "wrote g.json: 446 of 446 claim(s) challenged · vs the live "
                                      "map: 6 superseded, 4 added since the pin"),)),
             make_turn(1, make_bash("cat /tmp/old.log", uid="c"),
                       results=(("c", "418 of 418 claim(s) challenged"),)),
             make_turn(2, make_bash("coyodex audit m.json --json", uid="a"),
                       results=(("a", "444 L2 claims on the grounding worklist"),)))
    assert P.score_turns(turns).by_id()[14].observed == 1


def test_13_does_not_let_a_chained_assemble_hide_a_map_rewrite():
    """Skipping the whole call let a rewrite hide by chaining an assemble onto it — and that is the
    exact shape the real transcripts use."""
    turns = (make_turn(0, make_bash("coyodex grounding write --worklist w.json --out g.json")),
             make_turn(1, make_bash(
                 "python3 - <<'EOF'\n"
                 "import json; json.dump(d, open('.coyodex/project-map.json','w'))\nEOF\n"
                 "coyodex assemble .coyodex/build-fragments/*.json --out .coyodex")))
    a = P.score_turns(turns).by_id()[13]
    assert (a.observed, a.of) == (0, 1), a


def test_a22_prefers_preindex_own_gr1_verdict_over_a_transcript_guess():
    """`preindex` computes GR1 from the fragments on disk. The transcript scan cannot see a
    fragment written by a sub-agent, so a build that HAD drafted the layer read as "never"."""
    turns = (make_turn(1, make_bash("coyodex preindex --out .coyodex/preindex.json", uid="p"),
                       results=(("p", "  GR1 met: behavioral draft present (L1-usecases.json).\n"),)),)
    a = P.assert_22_behavioral_draft_precedes_preindex(turns)
    assert (a.observed, a.of) == (1, 1), a
    turns_not = (make_turn(1, make_bash("coyodex preindex --out .coyodex/preindex.json", uid="p"),
                           results=(("p", "  GR1 NOT MET: no fragment carries use_cases.\n"),)),)
    assert P.assert_22_behavioral_draft_precedes_preindex(turns_not).observed == 0


def test_a22_reads_single_quoted_keys_in_a_heredoc():
    """A heredoc quoting its JSON keys with `'` did not match a double-quote-only pattern."""
    turns = (make_turn(1, make_bash(
                 "python3 - <<'PY'\nimport json\n"
                 "json.dump({'use_cases': [{'id': 'UC1'}]}, "
                 "open('.coyodex/build-fragments/beh.json','w'))\nPY")),
             make_turn(2, make_bash("coyodex preindex --out .coyodex/preindex.json")))
    assert P.assert_22_behavioral_draft_precedes_preindex(turns).observed == 1


def test_a22_says_which_signal_it_used():
    """A reader must be able to tell an authoritative verdict from an inferred one."""
    turns = (make_turn(1, make_bash("coyodex preindex --out .coyodex/preindex.json")),)
    a = P.assert_22_behavioral_draft_precedes_preindex(turns)
    assert a.evidence and "transcript scan" in str(a.evidence[0].detail["source"])


def test_a22_takes_the_verdict_from_the_first_preindex_not_the_last():
    """H3 shipped with no test. Reading the LAST run over-credited the exact build the assertion
    exists to catch: `preindex "NOT MET"` -> draft -> `preindex "met"` scored a clean 1/1, and
    re-running preindex after the fragments land is routine."""
    turns = (make_turn(1, make_bash("coyodex preindex --out .coyodex/preindex.json", uid="p1"),
                       results=(("p1", "  GR1 NOT MET: no fragment carries use_cases.\n"),)),
             make_turn(50, make_write(".coyodex/build-fragments/beh.json",
                                      '{"use_cases": [{"id": "UC1"}]}')),
             make_turn(80, make_bash("coyodex preindex --out .coyodex/preindex.json", uid="p2"),
                       results=(("p2", "  GR1 met: behavioral draft present (beh.json).\n"),)))
    a = P.assert_22_behavioral_draft_precedes_preindex(turns)
    assert (a.observed, a.of) == (0, 1), a


def test_a22_does_not_accept_an_echoed_gr1_line():
    """The pattern is anchored to preindex's own output shape."""
    turns = (make_turn(1, make_bash("coyodex preindex --out p.json; echo 'GR1 met'", uid="p"),
                       results=(("p", "some output\nGR1 met\n"),)),)
    a = P.assert_22_behavioral_draft_precedes_preindex(turns)
    assert a.observed == 0, a


# ── 23: the outcome-based replacement for the withdrawn 19 ───────────────────────────────────────

def make_advisory_run(index: int, advisories: int, uid: str = "v"):
    body = "VALIDATION WARNINGS (non-blocking):\n" + "\n".join(
        f"  - advisory number {i}" for i in range(advisories))
    return make_turn(index, make_bash("coyodex validate map.json --check-sources", uid=uid),
                     results=((uid, body),))


def test_23_flags_a_build_that_never_saw_the_whole_gate():
    """The defect the withdrawn assertion 19 aimed at, measured by OUTCOME. 19 tried to detect the
    ACT of hiding and could not be made precise; this asks only whether the build ever looked at the
    advisories the map it committed actually carries — so `grep -v`, `head`, `tail`, `> /dev/null`
    and a summary written from memory are all caught by the same check."""
    turns = (make_advisory_run(1, 3),)
    ctx = P.ScoreContext(map_warnings=12)
    a = P.assert_23_the_build_saw_the_whole_gate(turns, ctx)
    assert (a.observed, a.of) == (0, 1), a
    assert a.evidence[0].detail["never_seen"] == "9", a.evidence


def test_23_passes_when_some_run_showed_the_whole_set():
    """The WIDEST view, not the last: narrowing a re-check is assertion 15's subject, and a build
    that legitimately fixes advisories shows more of them earlier than the final map holds."""
    turns = (make_advisory_run(1, 20, uid="a"), make_advisory_run(9, 2, uid="b"))
    ctx = P.ScoreContext(map_warnings=10)
    assert P.assert_23_the_build_saw_the_whole_gate(turns, ctx).observed == 1


def test_23_is_not_applicable_without_a_map_or_without_output():
    """Both are genuinely nothing to measure — n/a, never a zero."""
    assert P.assert_23_the_build_saw_the_whole_gate((make_advisory_run(1, 3),),
                                                    P.ScoreContext()).of == 0
    assert P.assert_23_the_build_saw_the_whole_gate((), P.ScoreContext(map_warnings=4)).of == 0


# --- from the 2026-08-02 retrospective -------------------------------------------------
# Every case below is a command a real build ran. Three of these assertions had accused an
# honest build; two are new.

def make_read(path: str, uid: str = "") -> ToolCall:
    return ToolCall(name="Read", input={"file_path": path}, id=uid)


def test_10_a_poll_chained_onto_real_work_is_not_an_idle_turn():
    """`ls dir && coyodex assemble …` looks at the directory and then DOES something. Counting it
    made assertion 10 report 0.67 for a build with zero idle turns — its 88-poll predecessor scored
    the same 0.00, so the number could not tell the two apart."""
    assert not P._polls_the_fragment_dir(
        "ls -la .coyodex/build-fragments/ && cd /x && coyodex assemble "
        ".coyodex/build-fragments/*.json --out .coyodex 2>&1 | tail -20")
    assert not P._polls_the_fragment_dir(
        "rm -f .coyodex/build-fragments/*.draft.json && ls .coyodex/build-fragments/")


def test_10_the_english_word_find_in_prose_is_not_a_poll():
    """Two live false positives, both the word `find` inside a quoted sentence — one in an `echo`
    banner, one in an extras body being written into a fragment."""
    assert not P._polls_the_fragment_dir(
        'echo "--- C21 port files, find a real operative line ---"; '
        "grep -n x .coyodex/build-fragments/gap-backend.json")


def test_10_still_catches_the_shapes_a_build_actually_waits_with():
    """A bare listing, a listing piped into a formatter, and an `until` spin loop whose poll hides
    inside a `$(…)`. All three are in the corpus; dropping them was an over-correction the first
    version of this fix shipped."""
    assert P._polls_the_fragment_dir("ls .coyodex/build-fragments/")
    assert P._polls_the_fragment_dir("ls -la .coyodex/build-fragments/ | wc -l")
    assert P._polls_the_fragment_dir(
        "sleep 1; ls /x/.coyodex/build-fragments/ | grep -E 'h10|h9a'")
    assert P._polls_the_fragment_dir(
        'cd /x/.coyodex/build-fragments && until [ "$(ls -1 a.json)" ]; do sleep 2; done')


def test_9_and_23_follow_a_redirect_into_the_later_read():
    """`validate … > v1.txt 2>&1` then `Read v1.txt` is what the method asks for ("read the REPORT
    FILE, not this stdout"). Both assertions scored `n/a — no validate output captured` on a build
    that ran validate five times and read every line of it."""
    body = ("     1\tInventory — C:80\n"
            "     4\tVALIDATION WARNINGS (non-blocking):\n"
            "     5\t  - first advisory, record `granularity` to silence\n"
            "     6\t  - second advisory, record `isolated` to silence\n")
    turns = (make_turn(1, make_bash("coyodex validate m.json > /tmp/v1.txt 2>&1", uid="v"),
                       results=(("v", "exit=0\n"),)),
             make_turn(3, make_read("/tmp/v1.txt", uid="r"), results=(("r", body),)))
    a = P.assert_23_the_build_saw_the_whole_gate(turns, P.ScoreContext(map_warnings=2))
    assert (a.observed, a.of) == (1, 1), a


def test_the_read_tools_line_numbers_do_not_hide_the_advisories():
    """The Read tool returns `cat -n` form. Left in place every advisory line starts with a digit,
    the file reads as zero advisories, and the fix above appears to change nothing."""
    raw = "     5\t  - an advisory\n"
    assert P._advisory_lines(raw) == (), "the prefix must really hide it"
    assert P._advisory_lines(P._strip_line_numbers(raw)) == ("an advisory",)


def test_13_clears_its_evidence_when_the_record_is_written_again():
    """Re-running `grounding write` after further edits is the METHOD-COMPLIANT recovery. A build
    that did exactly that was reported as 'written at turn 343; 14 later map/fragment write(s)' with
    evidence starting at turn 313 — twelve of them predating the turn the note named."""
    turns = (make_turn(1, make_bash("coyodex grounding write --worklist w.json --out g.json")),
             make_turn(3, make_bash("python3 -c \"open('.coyodex/project-map.json','w')\" "
                                    "&& cp a .coyodex/project-map.json")),
             make_turn(5, make_bash("coyodex grounding write --worklist w.json --map m --out g.json")),
             make_turn(7, make_bash("coyodex assemble .coyodex/build-fragments/*.json --out .coyodex")))
    a = P.assert_13_grounding_write_is_the_last_write(turns)
    assert (a.observed, a.of) == (1, 1), a
    assert not a.evidence, a.evidence


def test_13_still_fires_on_a_real_edit_after_the_last_record():
    """The defect itself must survive the repair."""
    turns = (make_turn(1, make_bash("coyodex grounding write --worklist w.json --out g.json")),
             make_turn(3, make_bash("cp fixed.json .coyodex/project-map.json")))
    assert P.assert_13_grounding_write_is_the_last_write(turns).observed == 0


def test_13_does_not_count_a_read_only_gate_or_the_commit_as_a_map_write():
    """`render`+`finalize` matched on `2>&1`; a read-only `python3 -c` matched on the `->` in a
    print; `git add … && git commit` named the map on the command line. None writes the model."""
    turns = (make_turn(1, make_bash("coyodex grounding write --worklist w.json --out g.json")),
             make_turn(3, make_bash("coyodex render .coyodex/project-map.json m.md 2>&1 | tail -2 "
                                    "&& coyodex finalize .coyodex/project-map.json 2>&1 | tail -6")),
             make_turn(5, make_bash("python3 -c \"import json; "
                                    "m=json.load(open('.coyodex/project-map.json')); "
                                    "print('flows', '->', len(m['flows']))\"")),
             make_turn(7, make_bash("git add -f .coyodex/project-map.json && git commit -q -m x")))
    a = P.assert_13_grounding_write_is_the_last_write(turns)
    assert (a.observed, a.of) == (1, 1), a


def test_writes_a_file_ignores_a_stderr_merge_and_a_printed_arrow():
    assert not P._WRITES_A_FILE.search("coyodex finalize m.json 2>&1 | tail -6")
    assert not P._WRITES_A_FILE.search("print(sf['id'], '->', len(sf['steps']))")
    assert P._WRITES_A_FILE.search("coyodex validate m.json > /tmp/v.txt")


def test_22_anchors_on_the_harvest_not_on_preindex():
    """GR1's harm is structural slices written before the behavioral layer exists. A build ran
    preindex at 42, was told GR1 NOT MET, drafted at 58 and fanned out at 76 — it obeyed the rule
    and still scored 0, indistinguishable from the build that harvested first and drafted 79 turns
    later."""
    drafted = make_write(".coyodex/build-fragments/behavioral.json", '{"use_cases": []}')
    obeyed = (make_turn(4, make_bash("coyodex preindex --out .coyodex/preindex.json", uid="p"),
                        results=(("p", "  GR1 NOT MET: no .coyodex/build-fragments/ yet\n"),)),
              make_turn(6, drafted),
              make_turn(8, make_agent(), make_agent()))
    assert P.assert_22_behavioral_draft_precedes_preindex(obeyed).observed == 1
    broke = (make_turn(4, make_bash("coyodex preindex --out .coyodex/preindex.json", uid="p"),
                       results=(("p", "  GR1 NOT MET: no .coyodex/build-fragments/ yet\n"),)),
             make_turn(6, make_agent(), make_agent()),
             make_turn(8, drafted))
    assert P.assert_22_behavioral_draft_precedes_preindex(broke).observed == 0


def test_8_does_not_flag_the_batches_summary():
    """`--batches` writes the claim FILES; its stdout is a summary, so paging it hides nothing and
    `--json` is meaningless for it. A build that ran the JSON form and the batches form in one turn
    scored 1/2 for the second."""
    turns = (make_turn(1, make_bash("coyodex audit m.json --json > worklist.json")),
             make_turn(3, make_bash("coyodex audit m.json --batches .coyodex/verify --cap 40 "
                                    "2>&1 | tail -20")))
    a = P.assert_8_audit_read_as_json(turns)
    assert (a.observed, a.of) == (1, 1), a


def test_24_flags_a_recorded_exception_that_silences_nothing():
    """A correctly spelled key whose advisory is not firing reads exactly like a typo. A live map
    carried three scoped `runs-in/…` records and validate's count line named two."""
    inert = P.ScoreContext(map_warnings=3, map_warning_lines=(
        "recorded `runs_in` exception(s) currently suppressing nothing: `runs-in/unplaced` — …",))
    assert P.assert_24_no_inert_recorded_exception((), inert).observed == 0
    clean = P.ScoreContext(map_warnings=2, map_warning_lines=("some ordinary advisory",))
    assert P.assert_24_no_inert_recorded_exception((), clean).observed == 1
    assert P.assert_24_no_inert_recorded_exception((), P.ScoreContext()).of == 0


def test_25_flags_a_to_reconcile_run_that_recorded_nothing():
    """`--to-reconcile` used to be ignored without `--keep`/`--accept-suggested`: exit 0, a full
    listing, an untouched file. One build escaped only because it read the file back."""
    turns = (make_turn(1, make_bash("coyodex fix dedup-edge --map m.json --to-reconcile r.json",
                                    uid="a"),
                       results=(("a", "46 edge(s) declared more than once…\n"),)),
             make_turn(3, make_bash("coyodex fix dedup-edge --map m.json --accept-suggested "
                                    "--to-reconcile r.json", uid="b"),
                       results=(("b", "dedup-edge: recorded 46 new and updated 0 keep_edges "
                                      "directive(s) in r.json (46 total).\n"),)))
    a = P.assert_25_dedup_to_reconcile_recorded_something(turns)
    assert (a.observed, a.of) == (1, 2), a


# --- regression pins from the adversarial review of the 2026-08-02 repairs ---------------
# Every one of these was a defect the first version of those repairs shipped.

def test_13_is_not_disarmed_by_a_read_only_grounding_command():
    """`edited_after.clear()` keyed on the `grounding` GROUP, so `grounding report` — which
    method.md now PRESCRIBES running straight after `write` — reset the anchor and wiped the
    evidence. Every compliant build would have scored clean whatever it did."""
    turns = (make_turn(1, make_bash("coyodex grounding write --worklist w.json --out g.json")),
             make_turn(3, make_bash("cp fixed.json .coyodex/project-map.json")),
             make_turn(5, make_bash("coyodex grounding report --worklist w.json --map m")))
    a = P.assert_13_grounding_write_is_the_last_write(turns)
    assert (a.observed, a.of) == (0, 1), a
    assert a.evidence[0].turn == 3, a.evidence


def test_13_does_not_invent_a_record_from_a_help_call():
    """A transcript that only ran `grounding --help` and `grounding report` reported "written at
    turn 229" about a record that was never written."""
    turns = (make_turn(1, make_bash("coyodex grounding --help | head -80")),
             make_turn(3, make_bash("coyodex grounding report --worklist w.json")),
             make_turn(5, make_bash("cp fixed.json .coyodex/project-map.json")))
    a = P.assert_13_grounding_write_is_the_last_write(turns)
    assert a.of == 0, a


def test_9_does_not_attribute_an_earlier_dirty_view_to_a_later_clean_run():
    """Keeping the LONGEST text ever read for a path fabricated findings whenever a build reused one
    scratch path: read it dirty, fix everything, re-run to the SAME path and read it clean, and the
    old dirty text was attributed to the clean run too — five unresolved advisories that had all
    been fixed."""
    dirty = ("     1\tVALIDATION WARNINGS (non-blocking):\n"
             "     2\t  - first, record `granularity` to silence\n"
             "     3\t  - second, record `isolated` to silence\n")
    clean = "     1\tSchema OK — structure valid.\n"
    turns = (make_turn(1, make_bash("coyodex validate m.json > /tmp/v.txt 2>&1", uid="v1"),
                       results=(("v1", "exit=0\n"),)),
             make_turn(3, make_read("/tmp/v.txt", uid="r1"), results=(("r1", dirty),)),
             make_turn(5, make_bash("coyodex validate m.json > /tmp/v.txt 2>&1", uid="v2"),
                       results=(("v2", "exit=0\n"),)),
             make_turn(7, make_read("/tmp/v.txt", uid="r2"), results=(("r2", clean),)))
    runs = P._validate_warnings(turns)
    assert [at for at, _ in runs] == [1], runs
    assert P.assert_9_no_advisory_waved_through(turns).of == 0, "the clean re-run resolved them"


def test_22_is_not_flipped_by_how_the_harvest_was_batched():
    """Anchoring on the first turn launching >=2 agents made the score depend on batching: a build
    that dispatched its slices one per turn — the failure assertion 3 measures, not a virtue — had
    no >=2-agent turn during the harvest, so the anchor slid to a later skeptic batch and the same
    build scored 1 instead of 0."""
    drafted = make_write(".coyodex/build-fragments/behavioral.json", '{"use_cases": []}')
    preindex = make_bash("coyodex preindex --out .coyodex/preindex.json", uid="p")
    res = (("p", "  GR1 NOT MET: no .coyodex/build-fragments/ yet\n"),)
    serial = (make_turn(4, preindex, results=res),
              *[make_turn(20 + i, make_agent()) for i in range(14)],   # one slice per turn
              make_turn(100, drafted),
              make_turn(200, make_agent(), make_agent()))              # Phase-4 skeptics
    assert P.assert_22_behavioral_draft_precedes_preindex(serial).observed == 0
    batched = (make_turn(4, preindex, results=res),
               make_turn(20, make_agent(), make_agent()),
               make_turn(100, drafted))
    assert P.assert_22_behavioral_draft_precedes_preindex(batched).observed == 0


def test_10_does_not_score_a_mutating_command_as_a_wait():
    """`sed -i` edits in place, `awk … > out` and `grep -c … > count.txt` redirect, and `xargs` runs
    whatever it is handed — `ls DIR | xargs rm` deleted files and scored as an idle wait."""
    for cmd in ("sed -i s/a/b/ .coyodex/build-fragments/h1.json; ls .coyodex/build-fragments",
                "ls .coyodex/build-fragments/*.json | xargs rm",
                "ls .coyodex/build-fragments; awk 1 x.json > out.json",
                "grep -c x .coyodex/build-fragments/a.json > count.txt; ls .coyodex/build-fragments",
                "ls .coyodex/build-fragments; xargs -I{} cp {} /tmp/backup/"):
        assert not P._polls_the_fragment_dir(cmd), cmd


def test_10_requires_the_poll_itself_to_name_the_directory():
    """Requiring only that the command mention the dir SOMEWHERE let `wc -l /tmp/validate4.txt` —
    counting a gate's output — read as a directory poll."""
    assert not P._polls_the_fragment_dir(
        "sed -n 1,5p .coyodex/build-fragments/h1.json; wc -l /tmp/v.txt")


def test_25_does_not_accuse_the_tools_own_refusal_or_a_clean_map():
    """The same batch made `--to-reconcile` without a decision exit 2 with an ERROR. A build that
    trips that guard, reads it and re-runs correctly is the opposite of the silent no-op. A map with
    no duplicate edges has nothing to record either."""
    refused = (make_turn(1, make_bash("coyodex fix dedup-edge --map m --to-reconcile r.json",
                                      uid="a"),
                         results=(("a", "ERROR: --to-reconcile needs a decision to record\n"),)),)
    assert P.assert_25_dedup_to_reconcile_recorded_something(refused).of == 0
    clean = (make_turn(1, make_bash("coyodex fix dedup-edge --map m --accept-suggested "
                                    "--to-reconcile r.json", uid="b"),
                       results=(("b", "dedup-edge: no (src, verb, dst) edge is declared more than "
                                      "once.\n"),)),)
    assert P.assert_25_dedup_to_reconcile_recorded_something(clean).of == 0


def test_8_batches_skip_does_not_erase_a_paged_read_chained_beside_it():
    """Skipping the whole Bash call let a paged human-report read hide behind a `--batches` run
    chained after it — and two audit forms in one turn is the observed shape."""
    turns = (make_turn(1, make_bash("coyodex audit m.json | head -40; "
                                    "coyodex audit m.json --batches .coyodex/verify --cap 40")),)
    a = P.assert_8_audit_read_as_json(turns)
    assert (a.observed, a.of) == (0, 1), a
