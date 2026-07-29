#!/usr/bin/env python3
"""Typed, streaming reader for a Claude Code build transcript (`~/.claude/projects/<slug>/*.jsonl`).

The L3 process scorecard asks whether the BUILD AGENT behaved as `method.md` says. Nothing but the
transcript can answer that, so this module turns the raw JSONL into a small typed sequence and the
assertions become ordinary counting.

## The one thing that is easy to get wrong

**A JSONL record is NOT a turn.** This harness writes each content block of one assistant message as
its own record, and stamps each with the time that block *executed* — so a single API response that
emitted ten `tool_use` blocks appears as ten records, spread over minutes, with the tool results
interleaved between them. Counting records as turns therefore reports "one tool call per turn" for a
message that made ten calls at once, which is exactly the measurement the fan-out rule turns on.

The reliable turn key is the API message identity. Every record of one response repeats:

    message.id            the API's own message id
    requestId             the harness's request id
    message.usage         identical token counts (one response, one usage block)
    message.stop_reason

`message.id` is the primary key here; `_usage_signature` is carried so a caller can assert the
grouping held (across the eight real build transcripts this reader was validated on, zero message
ids ever carried two different usage blocks). The corroborating evidence that settles it: a run of
ten `tool_use` records sharing one message id has exactly ONE `thinking` block among them. A model
does not emit ten tool-calling responses of which nine contain no reasoning.

## What a Turn carries

`Turn(index, role, tool_calls)` is the shape the L3 design specifies. Two additions, both earned:

  * `tool_results` on user turns — assertion 9 has to read what `coyodex validate` PRINTED, which
    lives in the tool result, not in the call.
  * `line` / `message_id` / `is_sidechain` — so evidence can point a reader at the exact record.
    `isSidechain: true` marks a sub-agent's own turns; the lead's fan-out behaviour is what L3
    measures, so callers filter those out by default (`read_turns(..., include_sidechains=False)`).

Streaming: the corpus files are 2–3 MB each and a scorecard run reads eight of them. `iter_turns`
never holds more than one message group in memory.

Stdlib only (`json`), frozen dataclasses — `coyodex_eval` carries no runtime dependencies.
"""
from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

#: Roles a Turn can carry. Records of any other `type` (queue-operation, system, attachment,
#: file-history-*, custom-title …) are harness bookkeeping and never become turns.
ASSISTANT = "assistant"
USER = "user"


@dataclass(frozen=True)
class ToolCall:
    """One `tool_use` block: the tool's name, the arguments the agent passed it, and the id its
    `tool_result` will quote — which is how a caller reads what a command PRINTED (assertion 9
    needs `coyodex validate`'s output, not just the fact that it ran). Pairing by id rather than by
    order matters here: results arrive out of order when sub-agents run asynchronously."""

    name: str
    input: Mapping[str, object] = field(default_factory=dict)
    id: str = ""

    @property
    def command(self) -> str:
        """The shell command, for a Bash call — `""` for every other tool. Most L3 assertions ask
        'did the agent run X', and this is where X lives."""
        value = self.input.get("command")
        return value if isinstance(value, str) else ""

    def text(self) -> str:
        """The whole input serialised, for assertions that must look anywhere in the arguments (a
        `grounding` object written through `Write`, a heredoc inside a Bash command)."""
        try:
            return json.dumps(self.input, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            return str(self.input)


@dataclass(frozen=True)
class ToolResult:
    """One `tool_result` block, flattened to text. The harness stores result content either as a
    plain string or as a list of `{type: text, text: …}` blocks; both arrive here as one string."""

    tool_use_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class Turn:
    """One API message — an assistant response, or the user/tool-result message answering it.

    `index` is the 0-based ordinal among the turns this reader yielded, which is what the L3
    evidence records point at. `line` is the 0-based JSONL line of the turn's FIRST record, for
    when a reader wants to go and look at the file."""

    index: int
    role: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()
    message_id: str = ""
    line: int = -1
    is_sidechain: bool = False
    timestamp: str = ""

    def calls_named(self, *names: str) -> tuple[ToolCall, ...]:
        wanted = frozenset(names)
        return tuple(c for c in self.tool_calls if c.name in wanted)

    @property
    def agent_calls(self) -> tuple[ToolCall, ...]:
        """Sub-agent launches. The tool is `Agent` in this harness; `Task` is the older spelling and
        is accepted so an archived transcript still measures."""
        return self.calls_named("Agent", "Task")


def _flatten_result_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _usage_signature(message: Mapping[str, object]) -> str:
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return ""
    try:
        return json.dumps(usage, sort_keys=True)
    except (TypeError, ValueError):
        return ""


@dataclass
class _Group:
    """Accumulator for the records that make up one API message."""

    key: str
    role: str
    line: int
    is_sidechain: bool
    timestamp: str
    usage: str
    calls: list[ToolCall] = field(default_factory=list)
    results: list[ToolResult] = field(default_factory=list)
    usage_conflicts: int = 0


def iter_turns(path: Path | str, *, include_sidechains: bool = False) -> Iterator[Turn]:
    """Stream the transcript as Turns, grouping every record of one API message into one Turn.

    **The grouping must survive interleaving.** The records of one assistant message are NOT
    consecutive in the file: each `tool_use` block is followed by the `tool_result` that answered
    it, and the next `tool_use` block of the SAME message comes after that. So a group is held open
    across intervening user records and closed only when a NEW assistant `message.id` appears (a new
    API response means the previous one finished) or at EOF.

    Merging only consecutive records was this reader's first bug, and it produced exactly the wrong
    answer for the assertion that matters most: a message with ten `Agent` calls came out as ten
    one-call turns. If you change this function, re-check assertion 3 against a known transcript.

    Order: an assistant Turn is emitted before the user Turns that answered it, which is the logical
    order the assertions reason about (assertion 10 attributes polling to the preceding fan-out;
    assertion 9 pairs validate calls with their results). Only one assistant group and its pending
    user turns are ever held, so the read stays streaming — the corpus files are 2-3 MB each.

    A malformed line is SKIPPED, not fatal. These files are appended to live and a truncated last
    line is ordinary; refusing to read a 3 MB transcript because of it would make the scorecard
    unrunnable exactly when a run was interrupted."""
    index = 0
    group: _Group | None = None
    pending: list[_Group] = []          # user turns that arrived while `group` was open

    def emit(g: _Group) -> Turn:
        nonlocal index
        turn = Turn(index=index, role=g.role, tool_calls=tuple(g.calls),
                    tool_results=tuple(g.results), message_id=g.key, line=g.line,
                    is_sidechain=g.is_sidechain, timestamp=g.timestamp)
        index += 1
        return turn

    def flush() -> Iterator[Turn]:
        nonlocal group, pending
        if group is not None and (include_sidechains or not group.is_sidechain):
            yield emit(group)
        group = None
        for p in pending:
            if include_sidechains or not p.is_sidechain:
                yield emit(p)
        pending = []

    with Path(path).open(encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh):
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            kind = record.get("type")
            if kind not in (ASSISTANT, USER):
                continue
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            blocks: Sequence[object] = content if isinstance(content, list) else []

            calls: list[ToolCall] = []
            results: list[ToolResult] = []
            for block in blocks:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "tool_use":
                    name = block.get("name")
                    args = block.get("input")
                    uid = block.get("id")
                    calls.append(ToolCall(name=name if isinstance(name, str) else "",
                                          input=args if isinstance(args, dict) else {},
                                          id=uid if isinstance(uid, str) else ""))
                elif btype == "tool_result":
                    tid = block.get("tool_use_id")
                    results.append(ToolResult(
                        tool_use_id=tid if isinstance(tid, str) else "",
                        content=_flatten_result_content(block.get("content")),
                        is_error=bool(block.get("is_error"))))

            sidechain = bool(record.get("isSidechain"))
            ts = record.get("timestamp")
            timestamp = ts if isinstance(ts, str) else ""
            mid = message.get("id")

            if kind == USER:
                pending.append(_Group(key=f"@{lineno}", role=USER, line=lineno,
                                      is_sidechain=sidechain, timestamp=timestamp, usage="",
                                      results=results))
                continue

            key = mid if isinstance(mid, str) and mid else f"@{lineno}"
            if group is not None and group.key == key:
                sig = _usage_signature(message)
                if sig and group.usage and sig != group.usage:
                    group.usage_conflicts += 1
                group.calls.extend(calls)
                group.results.extend(results)
                continue

            yield from flush()
            group = _Group(key=key, role=ASSISTANT, line=lineno, is_sidechain=sidechain,
                           timestamp=timestamp, usage=_usage_signature(message),
                           calls=calls, results=results)

    yield from flush()


def read_turns(path: Path | str, *, include_sidechains: bool = False) -> tuple[Turn, ...]:
    """Every Turn, materialised. Convenience for the assertions, which make several passes."""
    return tuple(iter_turns(path, include_sidechains=include_sidechains))


def grouping_is_consistent(path: Path | str) -> bool:
    """Did any `message.id` carry two different `usage` blocks?

    The turn grouping rests on 'one message id == one API response'. This re-reads the file and
    checks that assumption directly, so a harness format change surfaces as a false grouping
    assumption rather than as a silently wrong fan-out number."""
    seen: dict[str, str] = {}
    with Path(path).open(encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                record = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(record, dict) or record.get("type") != ASSISTANT:
                continue
            message = record.get("message")
            if not isinstance(message, dict):
                continue
            mid = message.get("id")
            sig = _usage_signature(message)
            if not isinstance(mid, str) or not sig:
                continue
            if mid in seen and seen[mid] != sig:
                return False
            seen[mid] = sig
    return True


def bash_commands(turns: Sequence[Turn]) -> tuple[tuple[int, str], ...]:
    """(turn index, command) for every Bash call, in order. The workhorse for assertions 1, 2, 4,
    7, 8 and 10, all of which ask 'what did the agent run'."""
    return tuple((t.index, c.command) for t in turns for c in t.calls_named("Bash") if c.command)


def results_by_tool_use_id(turns: Sequence[Turn]) -> dict[str, str]:
    """`tool_use_id -> result text` across the whole transcript.

    Pairing by id, never by order: sub-agents run asynchronously in this harness, so a result can
    arrive several turns after the one that followed its call. Order-pairing silently attributes
    one command's output to another."""
    out: dict[str, str] = {}
    for turn in turns:
        for result in turn.tool_results:
            if result.tool_use_id:
                out[result.tool_use_id] = result.content
    return out
