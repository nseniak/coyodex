#!/usr/bin/env python3
"""Tests for `coyodex-eval cost` — what a build spent.

Run either way (needs an editable install: `make install-eval`):
    python3 eval/tests/test_cost.py
    pytest eval/tests/test_cost.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyodex_eval import cost
from coyodex_eval.transcript import Usage, read_turns

# The whole report rests on two readings that are easy to get wrong, and both were wrong once:
#   * usage repeats on every record of one message — summing records inflates output ~8x
#   * a tool call executes at its OWN record's time, not its Turn's — timing from the Turn
#     reported tool execution at 34% of agent time when the true figure is 4%
# Those two are pinned first.


def write_jsonl(path: Path, records: list[dict[str, object]]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def make_assistant_records(message_id: str, calls: list[tuple[str, str, str]],
                           usage: dict[str, int], stamp_of: dict[str, str],
                           model: str = "claude-opus-5") -> list[dict[str, object]]:
    """One API response written the way the harness writes it: one record per content block, each
    stamped when THAT block ran, every record repeating the same usage."""
    out: list[dict[str, object]] = []
    for call_id, name, command in calls:
        out.append({
            "type": "assistant",
            "timestamp": stamp_of[call_id],
            "message": {"id": message_id, "model": model, "usage": usage,
                        "content": [{"type": "tool_use", "id": call_id, "name": name,
                                     "input": {"command": command}}]},
        })
    return out


def make_result_record(call_id: str, stamp: str) -> dict[str, object]:
    return {"type": "user", "timestamp": stamp,
            "message": {"content": [{"type": "tool_result", "tool_use_id": call_id,
                                     "content": "ok"}]}}


def make_session(tmp: Path) -> Path:
    """A lead that made one two-call response, each call taking 10s, 60s apart."""
    usage = {"input_tokens": 3, "output_tokens": 1000,
             "cache_read_input_tokens": 100_000, "cache_creation_input_tokens": 2_000}
    records = make_assistant_records(
        "m1", [("c1", "Bash", "rg foo"), ("c2", "Bash", "rg bar")], usage,
        {"c1": "2026-08-02T10:00:00.000Z", "c2": "2026-08-02T10:01:00.000Z"})
    records.insert(1, make_result_record("c1", "2026-08-02T10:00:10.000Z"))
    records.append(make_result_record("c2", "2026-08-02T10:01:10.000Z"))
    return write_jsonl(tmp / "session.jsonl", records)


def make_agent(dir_path: Path, name: str, description: str, minutes: float,
               output_tokens: int = 500) -> None:
    """A sub-agent transcript with two responses `minutes` apart."""
    dir_path.mkdir(parents=True, exist_ok=True)
    usage = {"input_tokens": 1, "output_tokens": output_tokens,
             "cache_read_input_tokens": 44_000, "cache_creation_input_tokens": 500}
    end = 60 * minutes
    records = [
        {"type": "user", "isSidechain": True, "timestamp": "2026-08-02T10:05:00.000Z",
         "message": {"content": "go"}},
        {"type": "assistant", "isSidechain": True, "timestamp": "2026-08-02T10:05:00.000Z",
         "message": {"id": f"{name}-1", "model": "claude-opus-5", "usage": usage,
                     "content": [{"type": "tool_use", "id": f"{name}-t1", "name": "Bash",
                                  "input": {"command": "rg x"}}]}},
        {"type": "assistant", "isSidechain": True,
         "timestamp": f"2026-08-02T10:{5 + int(end // 60):02d}:{int(end % 60):02d}.000Z",
         "message": {"id": f"{name}-2", "model": "claude-opus-5", "usage": usage,
                     "content": [{"type": "text", "text": "done"}]}},
    ]
    write_jsonl(dir_path / f"agent-{name}.jsonl", records)
    (dir_path / f"agent-{name}.meta.json").write_text(
        json.dumps({"description": description}), encoding="utf-8")


# --- usage is per message, never per record ------------------------------------------


def test_usage_is_counted_once_per_message_not_once_per_record():
    with tempfile.TemporaryDirectory() as td:
        session = make_session(Path(td))
        turns = read_turns(session)
        assistant = [t for t in turns if t.usage]
        assert len(assistant) == 1, "two tool_use records are ONE API response"
        assert assistant[0].usage.output_tokens == 1000, "summing the records would give 2000"
        assert assistant[0].model == "claude-opus-5"


def test_context_is_everything_the_request_read():
    u = Usage(input_tokens=3, output_tokens=9, cache_read_input_tokens=100,
              cache_creation_input_tokens=7)
    assert u.context == 110


# --- a tool call is timed from its own record ----------------------------------------


def test_tool_time_uses_the_call_timestamp_not_the_turn():
    with tempfile.TemporaryDirectory() as td:
        session = make_session(Path(td))
        lead, _agents = cost.read_run(session)
        seconds = cost._tool_seconds([lead])
        # Two 10s calls. Timing from the Turn (which carries c1's stamp) would charge the 60s of
        # generation between them and report ~80s.
        assert 15 <= seconds <= 25, seconds


# --- idle is a silence with NOTHING running -------------------------------------------


def test_a_long_silence_with_no_agent_running_is_idle():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        records = [
            {"type": "assistant", "timestamp": "2026-08-02T10:00:00.000Z",
             "message": {"id": "a", "model": "claude-opus-5", "usage": {"output_tokens": 1},
                         "content": [{"type": "text", "text": "?"}]}},
            {"type": "assistant", "timestamp": "2026-08-02T11:00:00.000Z",
             "message": {"id": "b", "model": "claude-opus-5", "usage": {"output_tokens": 1},
                         "content": [{"type": "text", "text": "!"}]}},
        ]
        session = write_jsonl(tmp / "s.jsonl", records)
        report = cost.build_report(session)
        assert round(report.idle_seconds) == 3600
        assert round(report.wall_seconds - report.idle_seconds) == 0


def test_a_long_silence_while_an_agent_runs_is_build_time():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        records = [
            {"type": "assistant", "timestamp": "2026-08-02T10:05:00.000Z",
             "message": {"id": "a", "model": "claude-opus-5", "usage": {"output_tokens": 1},
                         "content": [{"type": "text", "text": "spawning"}]}},
            {"type": "assistant", "timestamp": "2026-08-02T10:25:00.000Z",
             "message": {"id": "b", "model": "claude-opus-5", "usage": {"output_tokens": 1},
                         "content": [{"type": "text", "text": "collected"}]}},
        ]
        session = write_jsonl(tmp / "s.jsonl", records)
        make_agent(tmp / "s" / "subagents", "one", "Harvest the adapters", minutes=20.0)
        report = cost.build_report(session)
        assert report.idle_seconds == 0.0, "the lead was waiting on its own fan-out"


# --- sub-agents are most of the spend -------------------------------------------------


def test_subagent_transcripts_are_read_and_bucketed_by_role():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        session = make_session(tmp)
        agents = tmp / "session" / "subagents"
        make_agent(agents, "h1", "Harvest the repositories", minutes=4.0)
        make_agent(agents, "t1", "Trace the sign-in flow", minutes=9.0)
        make_agent(agents, "s1", "Skeptic security-1a", minutes=3.0)
        make_agent(agents, "g1", "Measure test completeness", minutes=2.0)
        report = cost.build_report(session)
        assert report.agents == 4
        assert set(report.by_role) == {"lead", "harvest", "trace", "verify", "test/gap"}
        assert report.by_role["trace"]["requests"] == 2


def test_an_undescribed_agent_is_other_never_forced_into_a_bucket():
    assert cost.classify("") == "other"
    assert cost.classify("Trace the harvest gaps") == "trace", "trace wins over harvest"
    assert cost.classify("Skeptic backbone-2") == "verify"


# --- the straggler tax ----------------------------------------------------------------


def test_waste_is_the_batch_wall_minus_its_mean_agent():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        session = make_session(tmp)
        agents = tmp / "session" / "subagents"
        make_agent(agents, "a", "Harvest one", minutes=2.0)
        make_agent(agents, "b", "Harvest two", minutes=2.0)
        make_agent(agents, "c", "Harvest three", minutes=14.0)
        report = cost.build_report(session)
        assert len(report.batches) == 1
        batch = report.batches[0]
        assert round(batch["wall"] / 60) == 14
        assert round(batch["mean"] / 60) == 6
        assert round(batch["waste"] / 60) == 8, "the two fast agents idled 8 minutes"


# --- pricing --------------------------------------------------------------------------


def test_cache_reads_and_writes_are_priced_at_their_multipliers():
    usage = Usage(input_tokens=0, output_tokens=0,
                  cache_read_input_tokens=1_000_000, cache_creation_input_tokens=0)
    assert cost.cost_of(usage, "claude-opus-5", "5m") == 0.5  # 0.1x of $5
    write = Usage(cache_creation_input_tokens=1_000_000)
    assert cost.cost_of(write, "claude-opus-5", "5m") == 6.25
    assert cost.cost_of(write, "claude-opus-5", "1h") == 10.0


def test_an_unpriced_model_is_named_not_silently_priced_as_something_else():
    usage = Usage(output_tokens=1_000_000)
    assert cost.cost_of(usage, "some-future-model", "5m") is None
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        records = [{"type": "assistant", "timestamp": "2026-08-02T10:00:00.000Z",
                    "message": {"id": "a", "model": "some-future-model",
                                "usage": {"output_tokens": 1_000_000},
                                "content": [{"type": "text", "text": "hi"}]}}]
        session = write_jsonl(tmp / "s.jsonl", records)
        report = cost.build_report(session)
        assert report.cost == 0.0
        assert report.unpriced_models == ["some-future-model"]
        assert "no list price" in cost.format_report(report)


def test_a_mixed_model_run_prices_each_turn_by_its_own_model():
    """The whole point of the report: swapping the verify agents to a cheaper model has to show
    up as a cheaper run, not as the same run priced at the lead's rate."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        records = [
            {"type": "assistant", "timestamp": "2026-08-02T10:00:00.000Z",
             "message": {"id": "a", "model": "claude-opus-5",
                         "usage": {"output_tokens": 1_000_000},
                         "content": [{"type": "text", "text": "x"}]}},
            {"type": "assistant", "timestamp": "2026-08-02T10:00:30.000Z",
             "message": {"id": "b", "model": "claude-haiku-4-5",
                         "usage": {"output_tokens": 1_000_000},
                         "content": [{"type": "text", "text": "y"}]}},
        ]
        session = write_jsonl(tmp / "s.jsonl", records)
        report = cost.build_report(session)
        assert report.cost == 30.0, "$25 of Opus plus $5 of Haiku, not 2x either rate"


# --- the per-unit divisor -------------------------------------------------------------


def make_map(path: Path, rows: int) -> Path:
    path.write_text(json.dumps({
        "components": [{"id": f"C{i}"} for i in range(rows)],
        "grounding": {"claims_total": 100, "claims_refuted": 2, "claims_unverifiable": 1},
        "goal": "not a list, not counted",
    }), encoding="utf-8")
    return path


def test_per_row_divides_by_what_the_build_produced():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        session = make_session(tmp)
        report = cost.build_report(session, map_path=make_map(tmp / "map.json", 100))
        assert report.map["rows"] == 100
        assert report.map["claims_refuted"] == 2
        assert report.per_row["cost"] == report.cost / 100
        rendered = cost.format_report(report)
        assert "cost per row" in rendered and "refuted" in rendered


def test_a_map_that_fails_to_parse_does_not_lose_the_spend_numbers():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        session = make_session(tmp)
        broken = tmp / "broken.json"
        broken.write_text("{ not json", encoding="utf-8")
        report = cost.build_report(session, map_path=broken)
        assert report.map == {} and report.cost > 0


# --- bounding a build inside a longer session -----------------------------------------


def test_only_a_partly_covered_silence_counts_the_uncovered_part():
    """A 40-minute silence with a 2-minute agent in it is 38 idle minutes, not zero and not 40."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        records = [
            {"type": "assistant", "timestamp": "2026-08-02T10:00:00.000Z",
             "message": {"id": "a", "model": "claude-opus-5", "usage": {"output_tokens": 1},
                         "content": [{"type": "text", "text": "x"}]}},
            {"type": "assistant", "timestamp": "2026-08-02T10:40:00.000Z",
             "message": {"id": "b", "model": "claude-opus-5", "usage": {"output_tokens": 1},
                         "content": [{"type": "text", "text": "y"}]}},
        ]
        session = write_jsonl(tmp / "s.jsonl", records)
        make_agent(tmp / "s" / "subagents", "one", "Harvest one", minutes=2.0)
        report = cost.build_report(session)
        assert round(report.idle_seconds / 60) == 38


def test_turn_bounds_cut_the_session_down_to_the_build():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        records = []
        for i in range(4):
            records.append({
                "type": "assistant", "timestamp": f"2026-08-02T10:0{i}:00.000Z",
                "message": {"id": f"m{i}", "model": "claude-opus-5",
                            "usage": {"output_tokens": 100},
                            "content": [{"type": "text", "text": str(i)}]}})
        session = write_jsonl(tmp / "s.jsonl", records)
        assert cost.build_report(session).requests == 4
        assert cost.build_report(session, from_turn=2).requests == 2
        assert cost.build_report(session, from_turn=1, to_turn=2).requests == 2


def test_a_window_with_nothing_in_it_is_an_error_not_a_zero_report():
    """Silently reporting a $0 build for a mistyped bound is the failure this refuses."""
    with tempfile.TemporaryDirectory() as td:
        session = make_session(Path(td))
        try:
            cost.build_report(session, from_turn=999)
        except ValueError as exc:
            assert "no timestamped turns" in str(exc)
        else:
            raise AssertionError("an empty window must raise")


def test_cli_reports_and_exits_zero(capsys):
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        session = make_session(tmp)
        make_map(tmp / "map.json", 50)
        assert cost.main([str(session), "--map", str(tmp / "map.json")]) == 0
        out = capsys.readouterr().out
        assert "BUILD" in out and "TOKENS" in out and "PER UNIT OF MAP" in out


def test_cli_json_is_machine_readable(capsys):
    with tempfile.TemporaryDirectory() as td:
        session = make_session(Path(td))
        assert cost.main([str(session), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["requests"] == 1 and "by_role" in payload


def test_cli_rejects_a_bad_cache_ttl(capsys):
    with tempfile.TemporaryDirectory() as td:
        session = make_session(Path(td))
        assert cost.main([str(session), "--cache-ttl", "1d"]) == 2
        assert "5m or 1h" in capsys.readouterr().err


def test_a_session_with_no_subagents_says_so(capsys):
    with tempfile.TemporaryDirectory() as td:
        session = make_session(Path(td))
        assert cost.main([str(session)]) == 0
        assert "LEAD ONLY" in capsys.readouterr().err


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))


def test_the_refutation_rate_is_divided_by_what_was_actually_challenged(tmp_path):
    """`claims_total` is the size of the WORKLIST; `claims_challenged` is how many a skeptic read.

    They are equal on a complete pass, which is why reading the wrong one survived: one real build's
    1.26% was right by luck. On a PARTIAL pass they are not — the other real build has 743 challenged
    of 1,385, and the rate the method tells you to read was printed as 0.4% for a true 0.8%."""
    from pathlib import Path
    from dataclasses import asdict
    from coyodex_eval.cost import read_map
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"title": "t", "goal": "g", "grounding": {
        "claims_total": 1385, "claims_challenged": 743,
        "claims_refuted": 6, "claims_unverifiable": 0}}), encoding="utf-8")
    read = read_map(Path(p))
    assert read is not None, "a map with a grounding block must read"
    facts = asdict(read)
    assert facts["claims_challenged"] == 743, facts
    assert 100 * facts["claims_refuted"] / facts["claims_challenged"] > 0.8


def test_a_map_without_the_challenged_field_falls_back_to_the_total(tmp_path):
    """Maps written before the field existed must still report a rate rather than a divide-by-zero."""
    from pathlib import Path
    from dataclasses import asdict
    from coyodex_eval.cost import read_map
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"title": "t", "goal": "g", "grounding": {
        "claims_total": 500, "claims_refuted": 5}}), encoding="utf-8")
    read = read_map(Path(p))
    assert read is not None, "a map with a grounding block must read"
    assert asdict(read)["claims_challenged"] == 500


# --- an agent is not charged for its coordinator's latency -------------------------
# The two "slowest" agents of a measured build held 4.7 and 6.9 minutes of sitting still between
# returning an answer and the follow-up arriving; the rework after each reply took about a minute.
# Ranking stragglers on the raw span measures the LEAD's round trip and calls it the agent's.


def _turn(index: int, role: str, stamp: str, *, tool_results=()):
    from coyodex_eval.transcript import Turn as T
    return T(index=index, role=role, timestamp=stamp, tool_results=tool_results)


def test_duration_excludes_the_wait_for_a_coordinator_follow_up():
    from coyodex_eval.cost import Actor
    from coyodex_eval.transcript import ToolResult
    agent = Actor(name="trace-gateway", role="trace", turns=(
        _turn(0, "assistant", "2026-08-17T09:13:00Z"),
        # an ordinary tool round trip: the user turn CARRIES a result, so it is work, not a block
        _turn(1, "user", "2026-08-17T09:14:00Z",
              tool_results=(ToolResult(tool_use_id="t", content="ok"),)),
        _turn(2, "assistant", "2026-08-17T09:15:00Z"),      # the agent's answer
        _turn(3, "user", "2026-08-17T09:20:00Z"),           # coordinator follow-up, 5 min later
        _turn(4, "assistant", "2026-08-17T09:21:00Z"),      # 1 min of rework
    ))
    assert agent.span == 8 * 60
    assert agent.blocked_seconds == 5 * 60
    assert agent.duration == 3 * 60


def test_an_agent_that_was_never_resumed_is_unchanged():
    from coyodex_eval.cost import Actor
    from coyodex_eval.transcript import ToolResult
    agent = Actor(name="skeptic-rule-1", role="verify", turns=(
        _turn(0, "assistant", "2026-08-17T09:53:00Z"),
        _turn(1, "user", "2026-08-17T09:56:00Z",
              tool_results=(ToolResult(tool_use_id="t", content="ok"),)),
        _turn(2, "assistant", "2026-08-17T09:59:00Z"),
    ))
    assert agent.blocked_seconds == 0.0
    assert agent.duration == agent.span == 6 * 60
