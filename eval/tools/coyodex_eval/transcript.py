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
  * `usage` / `model` — what the response was billed for, and by which model. The grouping is
    what makes these safe to add: the same `usage` block is repeated on every record of one
    message, so a per-record sum inflates output tokens ~8x. `coyodex-eval cost` reads them.

Streaming: the corpus files are 2–3 MB each and a scorecard run reads eight of them. `iter_turns`
never holds more than one message group in memory.

Stdlib only (`json`), frozen dataclasses — `coyodex_eval` carries no runtime dependencies.
"""
from __future__ import annotations

import re
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
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
    #: When this block EXECUTED — not when its message was answered. The harness stamps each
    #: content block separately, and a Turn carries the first one's time, so ten calls in one
    #: response all share the Turn's timestamp while executing minutes apart. Anything timing a
    #: call against its result must read this, or it measures the generation in between: the first
    #: cut of the cost report put tool execution at 34% of agent time when the true figure is 4%.
    timestamp: str = ""

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
class Usage:
    """The token counts one API response was billed for.

    Carried per TURN, never per record, and that is the whole point: the harness writes each
    content block of one response as its own record and repeats the identical `usage` on every one
    of them, so summing over records multiplies a response's tokens by its block count. On the
    build transcripts this reader was written for that inflates output tokens by roughly 8x.

    `context` is what the request actually re-read: cached tokens plus any written fresh. Growth
    in this number turn over turn IS the cost of a long agent — every turn pays for the whole
    conversation so far."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    @property
    def context(self) -> int:
        """Total prompt the model read this turn — cached + written + fresh."""
        return (self.input_tokens + self.cache_read_input_tokens
                + self.cache_creation_input_tokens)

    def __bool__(self) -> bool:
        return bool(self.input_tokens or self.output_tokens
                    or self.cache_read_input_tokens or self.cache_creation_input_tokens)


def _usage_of(message: Mapping[str, object]) -> Usage:
    raw = message.get("usage")
    if not isinstance(raw, dict):
        return Usage()

    def n(key: str) -> int:
        value = raw.get(key)
        return value if isinstance(value, int) else 0

    return Usage(input_tokens=n("input_tokens"), output_tokens=n("output_tokens"),
                 cache_read_input_tokens=n("cache_read_input_tokens"),
                 cache_creation_input_tokens=n("cache_creation_input_tokens"))


def _merge_usage(a: Usage, b: Usage) -> Usage:
    """Field-wise max across the records of one message.

    Max rather than sum: the records repeat one response's counts, so summing double-counts. Max
    rather than first-wins: a streamed response can be written before its final `output_tokens`
    is known, and the later record carries the complete figure."""
    return Usage(input_tokens=max(a.input_tokens, b.input_tokens),
                 output_tokens=max(a.output_tokens, b.output_tokens),
                 cache_read_input_tokens=max(a.cache_read_input_tokens,
                                             b.cache_read_input_tokens),
                 cache_creation_input_tokens=max(a.cache_creation_input_tokens,
                                                 b.cache_creation_input_tokens))


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
    #: Tokens billed for this turn, and the model that billed them. Empty on user turns — only an
    #: assistant response has a usage block. `coyodex-eval cost` sums these; nothing else may sum
    #: usage off raw records (see `Usage`).
    usage: Usage = Usage()
    model: str = ""
    #: (visible characters, signature bytes) summed over this turn's `thinking` blocks. A block can
    #: carry a multi-KB signature and an EMPTY body — the reasoning is redacted at write time. The
    #: reader used to drop those blocks entirely, so a retrospective could not tell "the agent did
    #: not reason here" from "the reasoning is withheld", and three of its findings had to be
    #: downgraded from certain to likely for want of that distinction.
    thinking_chars: int = 0
    thinking_signature_bytes: int = 0
    #: The assistant's VISIBLE prose for this turn, `text` blocks joined. Empty on user turns.
    #:
    #: Earned by a retrospective that could not audit a whole class of method rule. `method.md` and
    #: `dispatch.md` prescribe several steps that produce no tool call at all — show `scope`'s
    #: output verbatim as the first message, announce the build mode, warn before overwriting a
    #: baseline, and "the wait at a barrier is a TEXT turn". None of it was visible here, so the
    #: reviewer went and hand-parsed the raw JSONL — the exact fallback `--full-output` was added
    #: to prevent for sub-agent returns.
    text: str = ""

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
    thinking_chars: int = 0
    thinking_signature_bytes: int = 0
    text_parts: list[str] = field(default_factory=list)
    #: `usage` above is the SIGNATURE (a json string, used to detect a grouping violation);
    #: `tokens` is the parsed count the cost report sums.
    tokens: Usage = Usage()
    model: str = ""


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
                    is_sidechain=g.is_sidechain, timestamp=g.timestamp,
                    thinking_chars=g.thinking_chars,
                    thinking_signature_bytes=g.thinking_signature_bytes,
                    text="\n".join(g.text_parts).strip(),
                    usage=g.tokens, model=g.model)
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

            record_ts = record.get("timestamp")
            record_ts = record_ts if isinstance(record_ts, str) else ""
            calls: list[ToolCall] = []
            results: list[ToolResult] = []
            think_chars = think_sig = 0
            texts: list[str] = []
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
                                          id=uid if isinstance(uid, str) else "",
                                          timestamp=record_ts))
                elif btype == "text":
                    body = block.get("text")
                    if isinstance(body, str) and body.strip():
                        texts.append(body)
                elif btype in ("thinking", "redacted_thinking"):
                    body = block.get("thinking")
                    sig = block.get("signature") or block.get("data")
                    think_chars += len(body) if isinstance(body, str) else 0
                    think_sig += len(sig) if isinstance(sig, str) else 0
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
                                      results=results, thinking_chars=think_chars,
                                      thinking_signature_bytes=think_sig))
                continue

            key = mid if isinstance(mid, str) and mid else f"@{lineno}"
            model = message.get("model")
            model = model if isinstance(model, str) else ""
            if group is not None and group.key == key:
                sig = _usage_signature(message)
                if sig and group.usage and sig != group.usage:
                    group.usage_conflicts += 1
                group.calls.extend(calls)
                group.results.extend(results)
                group.thinking_chars += think_chars
                group.thinking_signature_bytes += think_sig
                group.text_parts.extend(texts)
                # MERGED, never summed — every record of this message repeats the same counts.
                group.tokens = _merge_usage(group.tokens, _usage_of(message))
                group.model = group.model or model
                continue

            yield from flush()
            group = _Group(key=key, role=ASSISTANT, line=lineno, is_sidechain=sidechain,
                           timestamp=timestamp, usage=_usage_signature(message),
                           calls=calls, results=results, thinking_chars=think_chars,
                           thinking_signature_bytes=think_sig, text_parts=texts,
                           tokens=_usage_of(message), model=model)

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


#: The canonical `coyodex` / `coyodex-eval` subcommands. An ALLOWLIST, because builds alias the
#: binary (`CX=…/coyodex; $CX audit …`) and a pattern loose enough to catch `$CX audit` is also
#: loose enough to read `$SP files` or `--map x` as subcommands — the first cut of this reported
#: `files`, `loc`, `map` and `runs`.
_COYODEX_SUBCOMMANDS = frozenset({
    "anchor-drift", "archive", "assemble", "audit", "balance", "bless", "claims", "compare",
    "cost", "diff", "dump", "finalize", "fix", "grounding", "hash", "judge", "lint-fragment", "preindex",
    "process", "protocol", "provenance", "reconcile", "record", "render", "retro-precheck",
    "run", "score", "scope", "serve", "transcript", "validate",
})

#: Sub-verbs worth reporting separately: `grounding write` and `grounding report` are different
#: acts, and so are the four `fix` verbs. Anything else is reported at subcommand granularity.
_COYODEX_SUBVERBS = frozenset({"write", "report", "apply-drift", "dedup-edge", "drop-edge",
                               "dedup-relation"})

#: `coyodex <subcommand>` anywhere in a shell command, including behind `;`, `&&` or a `$CX` alias.
#: The one-line index truncates at 100 characters, so a subcommand chained after another was
#: INVISIBLE there — and a retrospective concluded from the index that `grounding write` "never ran"
#: in a build that ran it at turn 489, chained behind an `assemble`. The finding was published, then
#: withdrawn. Counting from the full command text is the fix; the index stays short on purpose.
#:
#: The alias branch accepts an OPTIONAL pair of quotes around the expansion. `"$CY" record …` is the
#: careful spelling — a build reached for it precisely because the unquoted form had just been
#: word-split by zsh — and it did not match, so 42 successful `record` calls were invisible while
#: the ONE invocation the table did report was the earlier one that FAILED. A retrospective read
#: `record 1` off that table and concluded the command had barely been used.
#:
#: The separator between binary and subcommand is `[ \t]`, NEVER `\s`. With `\s+` the alias branch
#: matched ACROSS A NEWLINE: `echo "$PWD"\ncoyodex validate m.json` read as alias `$PWD` + subcommand
#: `coyodex`, which is not in the allowlist, and `finditer` then resumed PAST the real invocation —
#: so an ordinary two-line command silently lost its coyodex call.
#: Groups are NAMED. They were positional, and `summarise_call` read `group(1)`/`group(2)` as
#: (subcommand, verb) from 60 lines away; adding the binary branch shifted both and the index
#: silently stopped naming the subcommands it truncates — the very regression that annotation was
#: added to prevent. Two tests caught it; a name cannot shift.
_COYODEX_CMD = re.compile(
    r"""(?:(?P<bin>coyodex(?:-eval)?)|["']?(?P<alias>\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)["']?)"""
    r"[ \t]+(?!-)(?P<sub>[a-z][a-z0-9-]*)(?:[ \t]+(?P<verb>[a-z][a-z0-9-]*))?")


def _label(m: "re.Match[str]") -> str | None:
    """`subcommand [verb]` for a match, or None when the subcommand is not one of ours."""
    sub, verb = m.group("sub"), m.group("verb")
    if sub not in _COYODEX_SUBCOMMANDS:
        return None
    return f"{sub} {verb}" if verb in _COYODEX_SUBVERBS else sub

#: `--help` / `-h` as a standalone word. Applied to ONE shell segment (see `_segments`), never to
#: "the rest of the line": scanning forward from the match let ANY later program's flag delete a real
#: invocation — `coyodex dump m.json > f.json && du -h f.json` scored zero `dump` runs, and so did
#: every `&& df -h`, `&& sort -h` and `&& python build.py --help`. That is the same silent
#: under-count this whole scan was rewritten to end, re-created by the fix for it.
_HELP_ONLY = re.compile(r"(?:^|\s)(?:--help|-h)(?:\s|$)")

#: `CY=/path/to/.venv/bin/coyodex` / `CX="…/coyodex-eval"` — a shell alias for one of the two CLIs.
#:
#: The value may end at whitespace OR at any shell metacharacter. Requiring whitespace missed the
#: most natural one-liner, `CY=…/coyodex-eval; $CY score a b`, so a `coyodex-eval` run was booked to
#: the `coyodex` table — the exact mis-attribution the binary split exists to end.
#:
#: This DOES also match `COYODEX_HOME=/p/coyodex`, which names a directory rather than the binary.
#: That is harmless and `test_a_directory_env_var_produces_no_invocation` pins why: a directory is
#: used as `$COYODEX_HOME/method.md`, with no space between the variable and what follows, so it
#: never satisfies `_COYODEX_CMD`.
_ALIAS_ASSIGN = re.compile(
    r"""\b([A-Za-z_][A-Za-z0-9_]*)=["']?\S*?/(coyodex(?:-eval)?)["']?(?=[\s;&|)]|$)""")


def _heredoc_tags(line: str) -> list[str]:
    """Every heredoc terminator this line OPENS, in order.

    Quote-aware and `<<<`-aware, because a blunt `<<` match blanked the rest of the command on two
    ordinary shapes: a here-STRING (`python3 -c 'pass' <<< 'x'`) whose third `<` was skipped so the
    following word became a terminator that never reappeared, and a literal `<<` inside a quoted
    string (`echo 'use << to redirect'`). In both cases every coyodex call BELOW the line vanished
    from the count, silently.

    A list rather than one tag: `cat <<A <<B` queues two bodies, and finding only the first left B's
    body being scanned as commands."""
    tags: list[str] = []
    i, n, quote = 0, len(line), ""
    while i < n:
        c = line[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 2
                continue
            if c == quote:
                quote = ""
            i += 1
            continue
        if c in "'\"":
            quote = c
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if c == "<" and line.startswith("<<", i):
            if line.startswith("<<<", i):        # here-STRING: no body, no terminator
                i += 3
                continue
            j = i + 2
            if j < n and line[j] == "-":         # <<- strips leading tabs; same terminator rules
                j += 1
            while j < n and line[j] in " \t":
                j += 1
            if j < n and line[j] in "'\"":       # <<'EOF' / <<"EOF" — quoted tag
                j += 1
            k = j
            while k < n and (line[k].isalnum() or line[k] == "_"):
                k += 1
            if k > j:
                tags.append(line[j:k])
                i = k
                continue
            i = j
            continue
        i += 1
    return tags


def _strip_heredocs(cmd: str) -> str:
    """`cmd` with every heredoc BODY blanked out, terminators and all else kept.

    Line-based, because that is what a heredoc is: the body runs from the line after the one
    carrying `<<TAG` to the line whose stripped content is exactly `TAG`. A build writes plenty of
    coyodex-shaped text into one — contract templates, notes, generated docs — and a live
    `cat > rules-contract.md <<'EOF'` body made `dump` and `lint-fragment` appear as invocations at
    a turn that ran neither.

    Several heredocs queue in the order they were opened. An UNterminated heredoc (a truncated
    command) blanks to the end — the safe direction: dropping data can only cost a finding, while
    keeping it invents one."""
    out: list[str] = []
    queue: list[str] = []
    for line in cmd.splitlines():
        if queue:
            out.append(line if line.strip() == queue[0] else "")
            if line.strip() == queue[0]:
                queue.pop(0)
            continue
        out.append(line)
        queue.extend(_heredoc_tags(line))
    return "\n".join(out)


#: A shell segment boundary OUTSIDE quotes. `;;` is `case`; `|&` is bash's pipe-with-stderr.
_SEGMENT_SEPARATORS = ("&&", "||", ";;", "|&", ";", "|", "&", "\n")


def _segments(text: str) -> list[str]:
    """`text` split into shell segments — one command each — respecting quotes.

    The unit a `--help` belongs to is the SEGMENT it sits in, not the line and not "up to the next
    coyodex call". Getting that wrong is what let `&& du -h` erase a real invocation."""
    parts: list[str] = []
    buf: list[str] = []
    i, n, quote = 0, len(text), ""
    while i < n:
        c = text[i]
        if quote:
            buf.append(c)
            if c == "\\" and quote == '"' and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = ""
            i += 1
            continue
        if c in "'\"":
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(c)
            buf.append(text[i + 1])
            i += 2
            continue
        hit = next((sep for sep in _SEGMENT_SEPARATORS if text.startswith(sep, i)), "")
        if hit:
            parts.append("".join(buf))
            buf = []
            i += len(hit)
            continue
        buf.append(c)
        i += 1
    parts.append("".join(buf))
    return [p for p in parts if p.strip()]


#: A quoted span, for blanking before a `--help` test: `record --line "see --help for details"` is
#: an argument that happens to mention the flag, not a help run.
_QUOTED_SPAN = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")


def _alias_binaries(cmd: str) -> dict[str, str]:
    """`{VAR: "coyodex" | "coyodex-eval"}` for every alias assigned in this command."""
    return {m.group(1): m.group(2) for m in _ALIAS_ASSIGN.finditer(cmd)}


def _binary_of(token: str, aliases: Mapping[str, str]) -> str:
    """Which CLI `token` invokes — the literal name, the resolved alias, or the `coyodex` fallback."""
    bare = token.strip("\"'")
    if bare.endswith("coyodex-eval"):
        return "coyodex-eval"
    if bare.endswith("coyodex"):
        return "coyodex"
    var = bare.lstrip("$").strip("{}")
    return aliases.get(var, "coyodex")


@dataclass(frozen=True)
class Invocation:
    """One coyodex CLI call found in a Bash command."""

    turn: int
    name: str               #: `subcommand` or `subcommand verb`
    binary: str             #: "coyodex" | "coyodex-eval"
    alias_resolved: bool    #: False when `binary` is the fallback guess rather than a reading


def _iter_invocations(turns: "Sequence[Turn]") -> "Iterator[Invocation]":
    """Every coyodex invocation in these turns, ONE scan.

    Both `coyodex_subcommands` and `unresolved_aliases` read this. They used to scan separately and
    disagree: the alias footer applied no `--help` filter, so it reported a caveat about invocations
    the table had never counted.

    Order matters and is the fix for a whole class of bug. Heredoc bodies go first (they are data,
    not commands), THEN the text is split into segments, and only then is each segment matched. The
    previous cut matched against the stripped text but read the `--help` tail out of the ORIGINAL —
    so every character the stripping removed shifted that read earlier, and the two fixes silently
    mis-composed: a real `audit` was dropped because the `--help` it "saw" was heredoc data, and a
    genuine `reconcile --help` was counted because the read landed before the flag."""
    for idx, cmd in bash_commands(turns):
        aliases = _alias_binaries(cmd)
        # Join line continuations FIRST: `coyodex reconcile \<newline> --help` is one command, and
        # splitting on the newline put the flag in a segment of its own where nothing tested it.
        text = _strip_heredocs(cmd).replace("\\\n", " ")
        for segment in _segments(text):
            for m in _COYODEX_CMD.finditer(segment):
                label = _label(m)
                if label is None:
                    continue
                # `--help` binds to its own segment, and only up to the NEXT invocation inside it.
                nxt = _COYODEX_CMD.search(segment, m.end())
                tail = segment[m.end():nxt.start() if nxt else len(segment)]
                if _HELP_ONLY.search(_QUOTED_SPAN.sub(" ", tail)):
                    continue
                token = m.group("bin") or m.group("alias") or ""
                yield Invocation(
                    turn=idx,
                    name=label,
                    binary=_binary_of(token, aliases),
                    alias_resolved=bool(m.group("bin"))
                    or token.lstrip("$").strip("{}\"'") in aliases)


def unresolved_aliases(turns: "Sequence[Turn]") -> int:
    """How many COUNTED invocations went through an alias this reader could not resolve.

    The fallback in `_binary_of` is a guess, and a guess that is never surfaced is indistinguishable
    from a measurement. The `--commands` footer prints this so a reader knows how much of the
    coyodex table rests on it."""
    return sum(1 for inv in _iter_invocations(turns) if not inv.alias_resolved)


def coyodex_subcommands(turns: "Sequence[Turn]", *,
                        binary: str | None = None) -> "list[tuple[int, str]]":
    """(turn index, `subcommand [verb]`) for every coyodex invocation found ANYWHERE in a Bash
    command — not only at its head. See `_COYODEX_CMD` for why that distinction cost a real
    finding, and `_COYODEX_SUBCOMMANDS` for why it is an allowlist.

    Heredoc bodies are excluded and `--help` runs are not counted: both make the table claim work
    that did not happen. See `_iter_invocations` for the ordering the two together demand.

    `binary` filters by which CLI was invoked — `"coyodex"` or `"coyodex-eval"`. The two share this
    allowlist because they share subcommand names (`score`, `compare`, `archive`, `process`), so a
    table headed "coyodex invocation(s)" was counting `coyodex-eval archive` runs as build work. An
    ALIASED invocation resolves from the `VAR=…` assignment in the SAME command, which is where
    builds put it — each Bash call is a fresh shell. An alias that still cannot be resolved falls to
    `coyodex`: a build runs that binary and rarely the other, and `unresolved_aliases()` reports how
    much of the table rests on the fallback."""
    return [(inv.turn, inv.name) for inv in _iter_invocations(turns)
            if binary is None or inv.binary == binary]


def summarise_call(call: ToolCall, width: int = 100) -> str:
    """One line describing a tool call — the command for Bash, the description for an Agent, the
    path for a file tool, the first field otherwise."""
    if call.name == "Bash":
        text = " ".join(call.command.split())
    elif call.name in ("Agent", "Task"):
        desc = call.input.get("description")
        text = desc if isinstance(desc, str) else ""
    else:
        target = call.input.get("file_path") or call.input.get("path") or call.input.get("pattern")
        text = target if isinstance(target, str) else ""
    if not text:
        text = " ".join(call.text().split())
    if len(text) <= width:
        return text
    # Say WHAT the truncation hid, when what it hid is a coyodex subcommand. The index is short on
    # purpose, but a reader treats it as the list of what ran: a retrospective read this index,
    # concluded `grounding write` never ran, and published that about a build which ran it at turn
    # 489 chained behind an `assemble`. The finding was withdrawn. `--commands` was the answer and
    # nothing in the index pointed at it, so the index now names the subcommands it is cutting off.
    hidden: list[str] = []
    for m in _COYODEX_CMD.finditer(text[width:]):
        label = _label(m)
        if label and label not in hidden:
            hidden.append(label)
    if hidden:
        return f"{text[:width]} …+{', '.join(hidden)} (use --commands)"
    return text[:width]


def format_turns(turns: Sequence[Turn], *, full: bool = False, results: dict[str, str] | None = None,
                 width: int = 100, result_chars: int = 600, result_lines: int = 20) -> str:
    """Render turns as readable text.

    Two densities, for two readers. The compact form is an INDEX — one line per tool call — so a
    lead can see the whole run at a glance and pick the range worth reading. `full` adds the entire
    command and a slice of what it printed, which is what a sub-agent needs to judge one phase.

    This exists because a retrospective has to READ the transcript, and a 3 MB JSONL is not
    readable: opening one whole is both useless and expensive."""
    lines: list[str] = []
    unlimited = result_chars < 0
    for turn in turns:
        if turn.role != ASSISTANT:
            continue
        # A turn with no tool call is invisible in the INDEX by design — the index is one line per
        # call. In `full` it must not be, because a whole class of method rule produces exactly that
        # shape: "show `scope`'s output verbatim as your first message", "announce the mode", warn
        # before overwriting a baseline, "the wait at a barrier is a TEXT turn". A retrospective
        # trying to audit those found nothing and fell back to hand-parsing the raw JSONL.
        if not turn.tool_calls and not (full and turn.text):
            continue
        if full and turn.text:
            said = turn.text.splitlines()
            kept = said if unlimited else said[:result_lines]
            lines.append(f"[{turn.index:>4}] (said) " + "\n        . ".join(kept))
            if len(said) > len(kept):
                lines.append(f"        . … {len(said) - len(kept)} more line(s) "
                             f"(--full-output for all of it)")
            if not turn.tool_calls:
                lines.append("")
                continue
        if full and turn.thinking_signature_bytes and not turn.thinking_chars:
            # SAY that reasoning existed and was withheld. Dropping the block silently made
            # "the agent did not consider X" indistinguishable from "the agent's reasoning is
            # redacted", and a retrospective had to downgrade three findings for want of the
            # difference.
            lines.append(f"[{turn.index:>4}] (thinking redacted — "
                         f"{turn.thinking_signature_bytes} signature byte(s), no visible text)")
        for call in turn.tool_calls:
            head = f"[{turn.index:>4}] {call.name:<14}"
            if full:
                body = call.command if call.name == "Bash" else call.text()
                lines.append(f"{head} {summarise_call(call, width)}")
                if body and body != summarise_call(call, width):
                    lines.append("        | " + "\n        | ".join(body.splitlines()[:40]))
                out = (results or {}).get(call.id, "")
                if out:
                    snippet = out if unlimited else out[:result_chars]
                    body_lines = snippet.splitlines()
                    shown = body_lines if unlimited else body_lines[:result_lines]
                    lines.append("        > " + "\n        > ".join(shown))
                    if not unlimited and len(out) > len(snippet):
                        lines.append(f"        > … {len(out) - len(snippet)} more char(s) "
                                     f"(--result-chars N, or --full-output for all of it)")
                    elif not unlimited and len(body_lines) > len(shown):
                        lines.append(f"        > … {len(body_lines) - len(shown)} more line(s) "
                                     f"(--full-output for all of it)")
                lines.append("")
            else:
                lines.append(f"{head} {summarise_call(call, width)}")
    return "\n".join(lines)


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


# --- CLI -------------------------------------------------------------------------------

USAGE = """usage: coyodex-eval transcript <transcript.jsonl> [--from N] [--to N]
                                 [--tool NAME] [--grep PATTERN] [--stats] [--commands]
                                 [--full] [--full-output] [--result-chars N]

READ a build transcript in slices — the retrospective's eye on what the agent actually did.
A 3 MB JSONL cannot be opened whole, so this prints an INDEX by default (one line per tool
call, with its turn number) and the FULL text of a range with --full.

  --from/--to   turn range (inclusive), as printed in the index
  --tool NAME   only turns using that tool (Bash, Agent, Write, …)
  --grep PAT    only tool calls whose text matches (case-insensitive substring)
  --full        include the whole command and a slice of what it printed
  --full-output --full with NO truncation of tool results (implies --full). Use it when the
                answer lives in the output — sub-agent returns and long listings are clipped at
                600 chars otherwise, which sent one reviewer back to parsing the raw JSONL.
  --result-chars N  raise (or lower) that per-result cap instead of removing it
  --stats       tool counts and fan-out sizes instead of a listing
  --commands    every `coyodex` subcommand run, with turn numbers and a total per subcommand —
                found ANYWHERE in a command, so one chained behind `;` or `&&` is not missed
                (the one-line index truncates, and that once produced a false "never ran")

`--from`/`--to` apply to EVERY mode, including --commands and --stats. They used to be accepted
and silently ignored by those two, so a reviewer reading one slice was handed whole-transcript
numbers with nothing saying so.
A turn whose reasoning is REDACTED (a signature with no visible text) is marked in --full, so
"did not reason here" and "reasoning withheld" stay distinguishable."""


def _stats(turns: Sequence[Turn]) -> str:
    from collections import Counter
    tools: Counter[str] = Counter()
    fanouts: list[tuple[int, int]] = []
    for turn in turns:
        for call in turn.tool_calls:
            tools[call.name] += 1
        if turn.agent_calls:
            fanouts.append((turn.index, len(turn.agent_calls)))
    lines = [f"{len(turns)} turn(s); {sum(tools.values())} tool call(s)", "", "TOOLS"]
    lines += [f"  {n:>5}  {name}" for name, n in tools.most_common()]
    lines += ["", f"FAN-OUTS ({len(fanouts)} turn(s) launching agents)"]
    lines += [f"  turn {idx:>4}: {n} agent(s)" for idx, n in fanouts]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0

    def opt(flag: str) -> str | None:
        return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else None

    consumed = {opt(f) for f in ("--from", "--to", "--tool", "--grep", "--result-chars")}
    positional = [a for a in args if not a.startswith("--") and a not in consumed]
    if not positional:
        print("ERROR: give a transcript path\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    src = Path(positional[0])
    if not src.is_file():
        print(f"ERROR: no transcript at {src}", file=sys.stderr)
        return 2

    turns = read_turns(src)
    # PARSE AND APPLY THE RANGE FIRST. `--commands` and `--stats` used to run on the whole file
    # while accepting `--from`/`--to` and silently discarding them, so a sliced reviewer — told to
    # say "not in my range" rather than "the build skipped it" — was handed whole-transcript data
    # with nothing saying so. That is the exact failure the sliced-review protocol exists to
    # prevent, in the tool the protocol runs on.
    try:
        lo = int(opt("--from") or 0)
        hi = int(opt("--to") or 10**9)
    except ValueError:
        print("ERROR: --from and --to take an integer", file=sys.stderr)
        return 2
    ranged = tuple(t for t in turns if lo <= t.index <= hi)
    scope = "" if (lo == 0 and hi == 10**9) else f" in turns {lo}-{hi}"
    if scope and not ranged:
        print(f"no turns{scope} (the transcript holds {len(turns)} turn(s), indices 0-"
              f"{turns[-1].index if turns else 0})")
        return 0
    if "--commands" in args:
        from collections import Counter

        def table(found: list[tuple[int, str]], heading: str) -> None:
            counts = Counter(name for _i, name in found)
            by_name: dict[str, list[int]] = {}
            for i, name in found:
                by_name.setdefault(name, []).append(i)
            print(f"{heading}: {len(found)} invocation(s) across {len(counts)} subcommand(s)"
                  f"{scope}\n")
            print(f"{'subcommand':28} {'runs':>5}  turns")
            for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
                turns_s = ", ".join(str(t) for t in by_name[name][:12])
                if len(by_name[name]) > 12:
                    turns_s += f", … +{len(by_name[name]) - 12} more"
                print(f"  {name:26} {n:>5}  {turns_s}")

        # SPLIT BY BINARY. The two CLIs share subcommand names (`score`, `compare`, `archive`,
        # `process`), and one table headed "coyodex invocation(s)" reported a build's three
        # `coyodex-eval archive` calls as build work. A retro reading that over-counts the build.
        table(coyodex_subcommands(ranged, binary="coyodex"), "coyodex")
        evals = coyodex_subcommands(ranged, binary="coyodex-eval")
        # Only when present: on a build transcript this section is empty, and an empty table
        # reads as a gap rather than as "the build did not run the eval tool, which is correct".
        if evals:
            print()
            table(evals, "coyodex-eval")
        unresolved = unresolved_aliases(ranged)
        print("\n(`--help` runs are not counted, and heredoc bodies are not scanned — both make "
              "the table\n claim work that did not happen.)")
        if unresolved:
            print(f"({unresolved} invocation(s) went through an alias with no `VAR=…/coyodex` "
                  f"assignment in the\n same command, and are counted as `coyodex`.)")
        return 0
    if "--stats" in args:
        if scope:
            print(f"(turns {lo}-{hi} only)")
        print(_stats(ranged))
        return 0
    tool, pattern = opt("--tool"), (opt("--grep") or "").lower()
    # Filter the CALLS, not just the turns: one turn can carry a dozen calls, and keeping all of
    # them because one matched is not what `--grep` promises. A turn left with no matching call
    # drops out entirely.
    try:
        result_chars = -1 if "--full-output" in args else int(opt("--result-chars") or 600)
    except ValueError:
        print("ERROR: --result-chars takes an integer", file=sys.stderr)
        return 2
    full = "--full" in args or "--full-output" in args
    picked: list[Turn] = []
    for t in ranged:
        calls = t.tool_calls
        if tool:
            calls = tuple(c for c in calls if c.name == tool)
        if pattern:
            calls = tuple(c for c in calls if pattern in c.text().lower())
        if calls:
            picked.append(replace(t, tool_calls=calls))
        elif full and t.text and not tool and not pattern:
            # An UNFILTERED --full read is "everything in this range", and assistant prose is part
            # of it. A --tool/--grep read is a question about tool calls, so a text-only turn is not
            # an answer to it and stays out.
            picked.append(replace(t, tool_calls=()))
    if not picked and (tool or pattern):
        # The empty-RANGE case says so; a filter that matches nothing used to print one blank line,
        # which reads exactly like "the range is empty" and exactly like a crash.
        print(f"no tool call matches {'--tool ' + tool if tool else ''}"
              f"{' and ' if tool and pattern else ''}"
              f"{'--grep ' + repr(pattern) if pattern else ''}"
              f"{scope or ' in this transcript'}")
        return 0
    print(format_turns(picked, full=full, result_chars=result_chars,
                       results=results_by_tool_use_id(turns) if full else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
