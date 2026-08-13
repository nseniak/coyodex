#!/usr/bin/env python3
"""`coyodex-eval cost` — what one build SPENT: wall time, tokens, and both per unit of map.

The L3 scorecard asks whether the agent behaved as the method says; this asks what that behaviour
cost. It reads the same build transcript plus the sub-agent transcripts beside it, and reports the
handful of numbers that decide whether a tooling change actually paid:

  time    build wall, active time (idle excluded), fan-out batches, straggler waste, lead-only time
  tokens  per role — lead / harvest / trace / verify — output, cache reads, cache writes, cost
  unit    with `--map`: rows produced, and cost + seconds PER ROW

## Why per-row is the headline and absolute minutes are not

Across four mcpolis builds the map grew 1,195 -> 1,564 rows while the method was being changed
under it. Absolute wall time moved 61-71 min and cost $189-$207, so a build that got *cheaper per
unit of work* read as "slower and more expensive". Anything comparing two builds has to divide by
what they produced, or it measures the map's growth and calls it a regression.

## Why idle time is excluded

A transcript spans the whole session, not the build: a lead that asks the operator a question and
waits 40 minutes records a 130-minute session for a 68-minute build. A gap longer than
`--idle-gap` seconds with NO sub-agent running is operator wait, not work, and is subtracted from
`active`. Gaps with agents running are the lead correctly waiting on its fan-out and stay in.

## What this is not

Not a gate. It emits no verdict and fails nothing — a build costs what it costs. The quality
question is `coyodex-eval run` / `compare`; the two are read together, which is why `--map` also
prints the grounding counts (claims challenged / refuted / unverifiable) next to the spend. A
change that halves the bill and doubles refutations is not an improvement, and one report should
make that visible.

Prices are LIST prices, per model, from the table below — a subscription bills differently. They
are here so two builds are comparable in one unit, not to predict an invoice.

Stdlib only, like the rest of `coyodex_eval`.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from coyodex_eval.transcript import ToolCall, Turn, Usage, read_turns

#: $ per million tokens (input, output) at list price. Cache reads bill at 0.1x input and cache
#: writes at 1.25x (5-minute TTL) or 2x (1-hour TTL, `--cache-ttl 1h`).
#: A model absent here is reported by name with its tokens and NO cost, rather than silently
#: priced as something else — a wrong number is worse than a missing one.
MODEL_RATES: dict[str, tuple[float, float]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-mythos-5": (10.0, 50.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-opus-4-5": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}

CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = {"5m": 1.25, "1h": 2.0}

#: Roles are GUESSED from the agent's own description, because nothing in the harness records the
#: phase an agent belonged to. Order matters: "trace" before "harvest" so "Trace the harvest gaps"
#: lands as a trace. A description matching nothing is reported as `other`, never forced into a
#: bucket — a silently mis-bucketed agent moves a whole phase's number.
ROLE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("verify", r"skeptic|refute|verif|adversar"),
    ("trace", r"\btrace\b|flow"),
    ("test/gap", r"\btest|gap|fill\b|complete"),
    ("harvest", r"harvest|structural|dependenc|domain model|surface|owner|ops:|bootstrap|adapter"),
)

ROLE_ORDER = ("lead", "harvest", "trace", "verify", "test/gap", "other")


def classify(description: str) -> str:
    text = description.lower()
    for role, pattern in ROLE_PATTERNS:
        if re.search(pattern, text):
            return role
    return "other"


def _seconds(stamp: str) -> float | None:
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


@dataclass(frozen=True)
class Actor:
    """One participant in the build: the lead, or one sub-agent."""

    name: str
    role: str
    turns: tuple[Turn, ...]

    @property
    def stamps(self) -> tuple[float, ...]:
        return tuple(s for s in (_seconds(t.timestamp) for t in self.turns) if s is not None)

    @property
    def start(self) -> float | None:
        return min(self.stamps, default=None)

    @property
    def end(self) -> float | None:
        return max(self.stamps, default=None)

    @property
    def duration(self) -> float:
        s, e = self.start, self.end
        return (e - s) if (s is not None and e is not None) else 0.0

    @property
    def requests(self) -> tuple[Turn, ...]:
        """Assistant turns that carry a usage block — one per API call."""
        return tuple(t for t in self.turns if t.usage)

    def totals(self) -> Usage:
        out = Usage()
        for t in self.requests:
            u = t.usage
            out = Usage(out.input_tokens + u.input_tokens,
                        out.output_tokens + u.output_tokens,
                        out.cache_read_input_tokens + u.cache_read_input_tokens,
                        out.cache_creation_input_tokens + u.cache_creation_input_tokens)
        return out

    @property
    def base_context(self) -> int:
        """The context of this actor's FIRST request — its fixed per-turn overhead (system prompt,
        tool schemas, connected servers) plus its own brief. Paid again on every later turn, so a
        rise here multiplies across the whole run."""
        first = self.requests
        return first[0].usage.context if first else 0


def cost_of(usage: Usage, model: str, cache_ttl: str) -> float | None:
    rates = MODEL_RATES.get(model)
    if rates is None:
        return None
    price_in, price_out = rates
    write = CACHE_WRITE_MULTIPLIER[cache_ttl]
    return (usage.input_tokens * price_in
            + usage.cache_read_input_tokens * price_in * CACHE_READ_MULTIPLIER
            + usage.cache_creation_input_tokens * price_in * write
            + usage.output_tokens * price_out) / 1e6


def actor_cost(actor: Actor, cache_ttl: str) -> tuple[float, set[str]]:
    """Cost summed PER TURN, because a run can mix models (a cheaper verify agent is exactly the
    experiment this command exists to measure). Returns the total and the models that had no rate."""
    total = 0.0
    unpriced: set[str] = set()
    for turn in actor.requests:
        c = cost_of(turn.usage, turn.model, cache_ttl)
        if c is None:
            unpriced.add(turn.model or "(unknown)")
        else:
            total += c
    return total, unpriced


# --- reading a run ---------------------------------------------------------------------


def subagent_dir(session: Path) -> Path:
    """Sub-agent transcripts live in `<session-dir>/<session-id>/subagents/`, beside the session
    JSONL — NOT inside it. A build's sub-agents are 90% of its spend, so a reader that only opens
    the session file reports the lead's 20% and calls it the build."""
    return session.parent / session.stem / "subagents"


def read_agents(session: Path) -> list[Actor]:
    directory = subagent_dir(session)
    if not directory.is_dir():
        return []
    agents: list[Actor] = []
    for path in sorted(directory.glob("agent-*.jsonl")):
        meta_path = path.with_suffix(".meta.json")
        description = ""
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(meta, dict):
                    value = meta.get("description")
                    description = value if isinstance(value, str) else ""
            except ValueError:
                description = ""
        turns = read_turns(path, include_sidechains=True)
        if not turns:
            continue
        agents.append(Actor(name=description or path.stem,
                            role=classify(description), turns=turns))
    return agents


def read_run(session: Path, *, from_turn: int = 0,
             to_turn: int | None = None) -> tuple[Actor, list[Actor]]:
    """The lead and its sub-agents, bounded to the build.

    A session is not a build: it can archive the previous map first, and it usually keeps
    answering questions after the map lands. `from_turn` / `to_turn` cut those off, so time and
    tokens describe the same stretch. Without them one 68-minute build reads as a 130-minute
    session — the idle exclusion recovers most of that, but only explicit bounds drop the
    post-build conversation, which is real work and real tokens that simply are not the build."""
    upper = to_turn if to_turn is not None else 10 ** 9
    lead_turns = tuple(t for t in read_turns(session) if from_turn <= t.index <= upper)
    return Actor(name="lead", role="lead", turns=lead_turns), read_agents(session)


# --- timeline --------------------------------------------------------------------------


def _union(intervals: Iterable[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[list[float]] = []
    for start, end in sorted(i for i in intervals if i[1] > i[0]):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


@dataclass(frozen=True)
class Batch:
    """One fan-out: the agents spawned close together, and what waiting for the slowest one cost.

    `waste` is the batch's wall MINUS its mean agent duration — the time the fast agents spent
    finished and idle. It is the single number a slice-balancing change has to move."""

    index: int
    start: float
    end: float
    agents: tuple[Actor, ...]

    @property
    def wall(self) -> float:
        return self.end - self.start

    @property
    def durations(self) -> list[float]:
        return sorted((a.duration for a in self.agents), reverse=True)

    @property
    def mean(self) -> float:
        return statistics.fmean(self.durations) if self.agents else 0.0

    @property
    def waste(self) -> float:
        return max(0.0, self.wall - self.mean)


def batches(agents: Sequence[Actor], gap: float = 120.0) -> list[Batch]:
    """Cluster agents into fan-outs: a start more than `gap` after the previous one begins a new
    batch. The lead spawns one agent per message, so a batch's own starts are minutes apart —
    hence a gap this wide."""
    ordered = sorted((a for a in agents if a.start is not None), key=lambda a: a.start or 0.0)
    out: list[Batch] = []
    current: list[Actor] = []
    for agent in ordered:
        if current and (agent.start or 0.0) - (current[-1].start or 0.0) > gap:
            out.append(_batch(len(out), current))
            current = []
        current.append(agent)
    if current:
        out.append(_batch(len(out), current))
    return out


def _batch(index: int, agents: list[Actor]) -> Batch:
    return Batch(index=index, start=min(a.start or 0.0 for a in agents),
                 end=max(a.end or 0.0 for a in agents), agents=tuple(agents))


def _subtract(span: tuple[float, float],
              busy: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """`span` minus every interval in `busy` (which must be sorted and merged)."""
    start, end = span
    free: list[tuple[float, float]] = []
    cursor = start
    for begin, finish in busy:
        if finish <= cursor:
            continue
        if begin >= end:
            break
        if begin > cursor:
            free.append((cursor, min(begin, end)))
        cursor = max(cursor, finish)
        if cursor >= end:
            break
    if cursor < end:
        free.append((cursor, end))
    return free


def idle_gaps(lead: Actor, agents: Sequence[Actor], threshold: float) -> list[tuple[float, float]]:
    """Stretches where the lead was silent for longer than `threshold` AND no agent was running.

    That conjunction is the whole definition. A long silence with agents running is the lead
    waiting on its own fan-out — real build time. A long silence with nothing running is a human
    who walked away, and counting it made one 68-minute build read as 130 minutes.

    The agent windows are SUBTRACTED from each silence rather than used to veto it, so a 40-minute
    silence in which one agent ran for two minutes yields 38 idle minutes, not zero. Vetoing was
    the first cut, and it also managed to call a silence idle when an agent covered it exactly."""
    busy = _union((a.start, a.end) for a in agents if a.start is not None and a.end is not None)
    stamps = lead.stamps
    gaps: list[tuple[float, float]] = []
    for previous, following in zip(stamps, stamps[1:]):
        if following - previous <= threshold:
            continue
        for free in _subtract((previous, following), busy):
            if free[1] - free[0] > threshold:
                gaps.append(free)
    return gaps


# --- the map it produced ---------------------------------------------------------------


@dataclass(frozen=True)
class MapFacts:
    """What the build produced, for the per-unit divisor, and how well it held up.

    Read straight from the JSON rather than through `load_model`: a map that fails validation still
    cost what it cost, and a measurement command that refuses to measure a broken build is useless
    exactly when the question is 'what did that failure cost us'."""

    rows: int
    sections: int
    claims_total: int = 0
    #: How many of `claims_total` a skeptic actually read. Falls back to `claims_total` for a map
    #: written before the field existed.
    claims_challenged: int = 0
    claims_refuted: int = 0
    claims_unverifiable: int = 0


def read_map(path: Path) -> MapFacts | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    lists = {k: v for k, v in data.items() if isinstance(v, list)}
    grounding = data.get("grounding")
    grounding = grounding if isinstance(grounding, dict) else {}

    def n(key: str) -> int:
        value = grounding.get(key)
        return value if isinstance(value, int) else 0

    # `claims_total` is the SIZE OF THE WORKLIST; `claims_challenged` is how many a skeptic actually
    # read. On a complete pass they are equal, which is why reading the wrong one went unnoticed —
    # on a PARTIAL pass they are not, and the refutation rate the method tells you to read was
    # divided by the wrong denominator: one real build printed 6/1385 = 0.4% for a rate that is
    # 6/743 = 0.8%.
    return MapFacts(rows=sum(len(v) for v in lists.values()), sections=len(lists),
                    claims_total=n("claims_total"),
                    claims_challenged=n("claims_challenged") or n("claims_total"),
                    claims_refuted=n("claims_refuted"),
                    claims_unverifiable=n("claims_unverifiable"))


# --- the report ------------------------------------------------------------------------


@dataclass
class Report:
    session: str
    wall_seconds: float
    idle_seconds: float
    agent_busy_seconds: float
    lead_only_seconds: float
    agents: int
    requests: int
    usage: dict[str, int]
    cost: float
    unpriced_models: list[str]
    models: dict[str, int]
    by_role: dict[str, dict[str, float]]
    batches: list[dict[str, float]]
    base_context_median: int
    context_per_turn: dict[str, int]
    tool_seconds: float
    spawn_prompt_tokens: int
    map: dict[str, int] = field(default_factory=dict)
    per_row: dict[str, float] = field(default_factory=dict)


def _tool_seconds(agents: Sequence[Actor]) -> float:
    """Wall time inside sub-agents spent waiting on a tool, as opposed to generating.

    Pairs each call to its result by id and unions the intervals per agent, so parallel calls in
    one message are not counted twice. On these builds it lands at 4-7%: the fan-out is bound by
    token generation, not by grep.

    The call side reads `ToolCall.timestamp` — the block's OWN execution time — never the Turn's.
    A Turn carries the first record's stamp, so timing ten calls of one response from it measures
    the generation between them and reports ~34%."""
    total = 0.0
    for agent in agents:
        started: dict[str, float] = {}
        spans: list[tuple[float, float]] = []
        for turn in agent.turns:
            for call in turn.tool_calls:
                stamp = _seconds(call.timestamp) or _seconds(turn.timestamp)
                if stamp is not None:
                    started[call.id] = stamp
            done = _seconds(turn.timestamp)
            if done is None:
                continue
            for result in turn.tool_results:
                begin = started.pop(result.tool_use_id, None)
                if begin is not None and done > begin:
                    spans.append((begin, done))
        total += sum(e - s for s, e in _union(spans))
    return total


def _spawn_tokens(lead: Actor) -> int:
    """Tokens the lead generated writing agent briefs. Serial, on the critical path, and the thing
    a slice spec on disk replaces."""
    total = 0
    for turn in lead.turns:
        for call in turn.agent_calls:
            total += len(call.text()) // 4
    return total


def build_report(session: Path, *, map_path: Path | None = None, from_turn: int = 0,
                 to_turn: int | None = None, idle_threshold: float = 180.0,
                 cache_ttl: str = "5m") -> Report:
    lead, agents = read_run(session, from_turn=from_turn, to_turn=to_turn)
    everyone: list[Actor] = [lead, *agents]
    stamps = [s for actor in everyone for s in actor.stamps]
    if not stamps:
        raise ValueError(f"no timestamped turns in {session}")
    wall = max(stamps) - min(stamps)
    idle = sum(b - a for a, b in idle_gaps(lead, agents, idle_threshold))
    busy = sum(e - s for s, e in _union((a.start, a.end) for a in agents
                                        if a.start is not None and a.end is not None))

    usage = Usage()
    cost = 0.0
    unpriced: set[str] = set()
    models: Counter[str] = Counter()
    by_role: dict[str, dict[str, float]] = {}
    for actor in everyone:
        totals = actor.totals()
        actor_total, actor_unpriced = actor_cost(actor, cache_ttl)
        unpriced |= actor_unpriced
        cost += actor_total
        usage = Usage(usage.input_tokens + totals.input_tokens,
                      usage.output_tokens + totals.output_tokens,
                      usage.cache_read_input_tokens + totals.cache_read_input_tokens,
                      usage.cache_creation_input_tokens + totals.cache_creation_input_tokens)
        for turn in actor.requests:
            models[turn.model or "(unknown)"] += 1
        bucket = by_role.setdefault(actor.role, {"agents": 0.0, "requests": 0.0, "output": 0.0,
                                                 "cache_read": 0.0, "cache_write": 0.0,
                                                 "cost": 0.0, "seconds": 0.0})
        bucket["agents"] += 1
        bucket["requests"] += len(actor.requests)
        bucket["output"] += totals.output_tokens
        bucket["cache_read"] += totals.cache_read_input_tokens
        bucket["cache_write"] += totals.cache_creation_input_tokens
        bucket["cost"] += actor_total
        bucket["seconds"] += actor.duration

    bases = sorted(a.base_context for a in agents if a.base_context)
    requests = sum(len(a.requests) for a in everyone)
    report = Report(
        session=session.stem,
        wall_seconds=wall,
        idle_seconds=idle,
        agent_busy_seconds=busy,
        lead_only_seconds=max(0.0, wall - idle - busy),
        agents=len(agents),
        requests=requests,
        usage=asdict(usage),
        cost=cost,
        unpriced_models=sorted(unpriced),
        models=dict(models),
        by_role=by_role,
        batches=[{"index": float(b.index), "start": b.start - min(stamps), "wall": b.wall,
                  "agents": float(len(b.agents)), "slowest": b.durations[0] if b.agents else 0.0,
                  "median": statistics.median(b.durations) if b.agents else 0.0,
                  "mean": b.mean, "waste": b.waste} for b in batches(agents)],
        base_context_median=int(statistics.median(bases)) if bases else 0,
        context_per_turn={
            "lead": (lead.totals().cache_read_input_tokens // len(lead.requests)
                     if lead.requests else 0),
            "subagents": (sum(a.totals().cache_read_input_tokens for a in agents)
                          // max(sum(len(a.requests) for a in agents), 1)),
        },
        tool_seconds=_tool_seconds(agents),
        spawn_prompt_tokens=_spawn_tokens(lead),
    )
    if map_path is not None:
        facts = read_map(map_path)
        if facts is not None:
            report.map = asdict(facts)
            active = wall - idle
            report.per_row = {
                "cost": cost / facts.rows if facts.rows else 0.0,
                "seconds": active / facts.rows if facts.rows else 0.0,
            }
    return report


# --- rendering -------------------------------------------------------------------------


def _m(seconds: float) -> str:
    return f"{seconds / 60:.1f}m"


def format_report(report: Report) -> str:
    lines: list[str] = []
    active = report.wall_seconds - report.idle_seconds
    lines.append(f"BUILD {report.session}")
    lines.append(f"  wall {_m(report.wall_seconds)}   active {_m(active)}"
                 f"   (idle excluded: {_m(report.idle_seconds)})")
    lines.append(f"  agents busy {_m(report.agent_busy_seconds)}"
                 f" ({100 * report.agent_busy_seconds / max(active, 1):.0f}% of active)"
                 f"   lead alone {_m(report.lead_only_seconds)}")
    lines.append(f"  {report.agents} sub-agent(s), {report.requests} API call(s)")

    lines.append("")
    lines.append("FAN-OUT")
    lines.append(f"  {'#':>2} {'start':>7} {'wall':>7} {'n':>3} {'slowest':>8} {'median':>7}"
                 f" {'mean':>7} {'waste':>7}")
    for b in report.batches:
        lines.append(f"  {int(b['index']):>2} {_m(b['start']):>7} {_m(b['wall']):>7}"
                     f" {int(b['agents']):>3} {_m(b['slowest']):>8} {_m(b['median']):>7}"
                     f" {_m(b['mean']):>7} {_m(b['waste']):>7}")
    waste = sum(b["waste"] for b in report.batches)
    lines.append(f"  straggler waste {_m(waste)}"
                 f" ({100 * waste / max(active, 1):.0f}% of active time)")

    lines.append("")
    lines.append("TOKENS")
    lines.append(f"  {'role':<10} {'n':>3} {'calls':>6} {'output':>11} {'cache read':>13}"
                 f" {'cache write':>12} {'$':>8}")
    for role in ROLE_ORDER:
        b = report.by_role.get(role)
        if not b:
            continue
        lines.append(f"  {role:<10} {int(b['agents']):>3} {int(b['requests']):>6}"
                     f" {int(b['output']):>11,} {int(b['cache_read']):>13,}"
                     f" {int(b['cache_write']):>12,} {b['cost']:>8.2f}")
    u = report.usage
    lines.append(f"  {'TOTAL':<10} {'':>3} {report.requests:>6} {u['output_tokens']:>11,}"
                 f" {u['cache_read_input_tokens']:>13,}"
                 f" {u['cache_creation_input_tokens']:>12,} {report.cost:>8.2f}")
    if report.unpriced_models:
        lines.append(f"  ! no list price for {', '.join(report.unpriced_models)} —"
                     f" their tokens are counted, their cost is NOT in the total")
    if len(report.models) > 1:
        lines.append("  models: " + ", ".join(f"{m} x{n}" for m, n in
                                              sorted(report.models.items(), key=lambda kv: -kv[1])))

    lines.append("")
    lines.append("STRUCTURE")
    lines.append(f"  fixed base context per agent turn   {report.base_context_median:>12,}")
    lines.append(f"  avg cache read per turn — lead      {report.context_per_turn['lead']:>12,}")
    lines.append(f"  avg cache read per turn — agents    {report.context_per_turn['subagents']:>12,}")
    lines.append(f"  tool execution inside agents        {_m(report.tool_seconds):>12}"
                 f"  ({100 * report.tool_seconds / max(sum(b['seconds'] for r, b in report.by_role.items() if r != 'lead'), 1):.0f}% of agent time)")
    lines.append(f"  lead tokens spent writing briefs    {report.spawn_prompt_tokens:>12,}")

    if report.map:
        lines.append("")
        lines.append("PER UNIT OF MAP")
        m = report.map
        lines.append(f"  rows produced                       {m['rows']:>12,}"
                     f"  (in {m['sections']} sections)")
        lines.append(f"  cost per row                        {report.per_row['cost']:>12.4f}")
        lines.append(f"  seconds per row                     {report.per_row['seconds']:>12.2f}")
        challenged = m.get("claims_challenged") or m["claims_total"]
        if challenged:
            rate = 100 * m["claims_refuted"] / challenged
            partial = ("" if challenged == m["claims_total"]
                       else f" of {m['claims_total']:,} on the worklist")
            lines.append(f"  claims challenged / refuted         "
                         f"{challenged:>7,} / {m['claims_refuted']:<4}"
                         f"  ({rate:.1f}% refuted, {m['claims_unverifiable']} unverifiable"
                         f"{partial})")
    return "\n".join(lines)


# --- CLI -------------------------------------------------------------------------------

USAGE = """usage: coyodex-eval cost <transcript.jsonl> [--map project-map.json] [--json]
                             [--from-turn N] [--to-turn N] [--idle-gap SECONDS]
                             [--cache-ttl 5m|1h]

What a build SPENT: wall time, tokens, and both per row of map produced. Reads the session
transcript AND the sub-agent transcripts beside it (`<session>/subagents/`), which are ~80% of
the spend — a reader that opens only the session file measures the lead and misses the build.

  --map PATH     the map the build produced; adds rows, cost-per-row, seconds-per-row, and the
                 grounding counts. WITHOUT it the report cannot be compared against another
                 build: absolute minutes and dollars track how big the map got, not how well
                 the tooling did.
  --from-turn N  ignore the lead's turns before N, for a session that did something else first
                 (an archive step, an unrelated question) before the build began.
  --to-turn N    and after N — a session usually keeps answering questions once the map has
                 landed. Turn numbers come from `coyodex-eval transcript`.
  --idle-gap S   a lead silence longer than S seconds with NO agent running is operator wait and
                 is excluded from `active` (default 180).
  --cache-ttl    cache-write price multiplier: 1.25x at 5m (default), 2x at 1h.
  --json         the whole report as JSON, for tracking builds over time.

Not a gate: it emits no verdict. Read it beside `coyodex-eval compare` — a change that halves
the bill and doubles the refutation rate is not an improvement."""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0

    def opt(flag: str) -> str | None:
        if flag not in args:
            return None
        i = args.index(flag) + 1
        return args[i] if i < len(args) else None

    consumed = {opt(f) for f in ("--map", "--from-turn", "--to-turn", "--idle-gap", "--cache-ttl")}
    positional = [a for a in args if not a.startswith("--") and a not in consumed]
    if not positional:
        print("ERROR: give a transcript path\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    session = Path(positional[0])
    if not session.is_file():
        print(f"ERROR: no transcript at {session}", file=sys.stderr)
        return 2

    map_arg = opt("--map")
    map_path = Path(map_arg) if map_arg else None
    if map_path is not None and not map_path.is_file():
        print(f"ERROR: no map at {map_path}", file=sys.stderr)
        return 2
    cache_ttl = opt("--cache-ttl") or "5m"
    if cache_ttl not in CACHE_WRITE_MULTIPLIER:
        print("ERROR: --cache-ttl takes 5m or 1h", file=sys.stderr)
        return 2
    try:
        from_turn = int(opt("--from-turn") or 0)
        to_raw = opt("--to-turn")
        to_turn = int(to_raw) if to_raw is not None else None
        idle_gap = float(opt("--idle-gap") or 180.0)
    except ValueError:
        print("ERROR: --from-turn/--to-turn take an integer and --idle-gap a number",
              file=sys.stderr)
        return 2

    try:
        report = build_report(session, map_path=map_path, from_turn=from_turn, to_turn=to_turn,
                              idle_threshold=idle_gap, cache_ttl=cache_ttl)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if "--json" in args:
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
        return 0
    print(format_report(report))
    if not subagent_dir(session).is_dir():
        print("\nNOTE: no sub-agent transcripts beside this session — the numbers above are the"
              "\n      LEAD ONLY. On a fan-out build that is about a fifth of the real spend.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
