#!/usr/bin/env python3
"""L3 — the process scorecard: did the BUILD AGENT behave as `method.md` says?

L1 (`tests/test_method_contract.py`) asks whether the method names the tool. L2
(`tests/test_trapdoor_tools.py`) asks whether the tool says the right thing about a real tree.
Neither can see the third defect class: a fix that ships, passes its tests, is documented — and
never gets reached, because the agent does not do the thing. Only a build transcript shows that.

## THIS IS A SCORECARD, NOT A GATE

It never blocks a commit, never joins `make test`, and never returns a pass/fail verdict. L1 and L2
are the hard gates. Every assertion emits `observed / of` with turn indices attached, because a
single run proves nothing and a trend across runs proves a great deal: three runs all showing zero
batched fan-outs mean the rule is not landing. `main()` therefore exits 0 whatever the numbers say —
the only non-zero exits are for a missing file or an unreadable scorecard.

A `score` of `None` means NOT APPLICABLE: the run contained nothing of that kind (no fan-out at all,
no `reconcile.json` to write). That is deliberately distinct from `0.0`, which means the opportunity
existed and was missed. Averaging the two together would hide the difference.

## Reading the transcript

See `transcript.py`. The one trap worth repeating: a JSONL record is not a turn. This harness writes
each content block of one API response as its own record, stamped with the time that block
*executed*, so a message that emitted ten `Agent` calls at once looks like ten one-call turns spread
over minutes. Assertion 3 — the highest-value number here — is exactly the one that measurement
would get backwards.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from coyodex_eval.transcript import (ToolCall, Turn, bash_commands, grouping_is_consistent,
                                     read_turns, results_by_tool_use_id)

EvidenceValue = str | int | float | bool

#: The artifact every measurement here is about.
PREINDEX_JSON = "preindex.json"
RECONCILE_JSON = "reconcile.json"
FRAGMENT_DIR = "build-fragments"

#: Assertion 10's proposed ceiling: how many idle turns a single fan-out may spend before it counts
#: as polling. The method says wait on completion notifications.
POLL_THRESHOLD = 3

#: A command that does nothing but yield the turn. `echo .`, `sleep 120`, `true`, `:` — and any
#: `;`-chain of only those.
#:
#: Assertion 10 used to count ONLY `ls`/`find`/`stat`/`wc` naming the fragment dir. A live build
#: then spent 42 of its 195 tool calls on `echo .` keep-alives and scored a PERFECT 38/38, up from
#: 0.60 — the scorecard reported an improvement while the waste roughly tripled. The behaviour the
#: assertion is about is "turns burned waiting", so it has to see any shape of it, not the one shape
#: the first build happened to use.
_NOOP_SEGMENT = re.compile(r"^\s*(?:echo\b[^|<>]*|sleep\s+[\d.]+|true|:)\s*$")


def _is_noop_wait(command: str) -> bool:
    """True when every `;`-separated segment of `command` does nothing observable."""
    segments = [s for s in command.split(";") if s.strip()]
    return bool(segments) and all(_NOOP_SEGMENT.match(s) for s in segments)

#: Reading `preindex.json` YOURSELF, as opposed to letting `preindex --report` read it.
#: These target the file rather than merely co-occurring with it, because a `git add …
#: .coyodex/preindex.json` or a `git check-ignore … preindex.json` names the artifact without
#: parsing a byte of it — counting those was a real false positive in this module's first draft.
_HAND_PARSE = tuple(re.compile(p) for p in (
    r"json\.loads?\s*\(\s*open\s*\([^)]*preindex\.json",          # json.load(open('…/preindex.json'))
    r"open\s*\(\s*['\"][^'\"]*preindex\.json",                    # open('…/preindex.json')
    r"\b(?:cat|jq|grep|egrep|rg|head|tail|sed|awk|cut|less)\b[^\n;|&]*preindex\.json",
    r"preindex\.json[^\n;&]*\|\s*(?:jq|grep|egrep|rg|head|tail|sed|awk|cut|python3?)\b",
    r"<\s*[^\n;|&]*preindex\.json",                               # redirect the file into a reader
))

#: Pipes that page a command's human output instead of reading its machine-readable form.
_PAGERS = re.compile(r"\|\s*(head|tail|sed|grep|egrep|rg|awk|cut|less|more)\b")

#: An advisory that names a way to record the decision — the escape tokens L1 audits.
_ESCAPE_HEADING = re.compile(r"['\"]([A-Z][A-Za-z -]{3,30})['\"]\s+extras heading")
_ESCAPE_LITERAL = re.compile(r"record the literal ['`]([a-z-]+)['`]")

#: Words that mark an Agent launch as a Phase-4 skeptic rather than a harvest or trace agent.
_SKEPTIC_WORDS = ("skeptic", "sceptic", "disprove", "refute", "falsif")


# --- result shapes ---------------------------------------------------------------------

@dataclass(frozen=True)
class Evidence:
    """One place in the transcript a reader can go and look. `turn` is the Turn index; `detail`
    carries whatever that assertion needs to make the number legible."""

    turn: int
    detail: Mapping[str, EvidenceValue] = field(default_factory=dict)

    def as_json(self) -> dict[str, EvidenceValue]:
        return {"turn": self.turn, **dict(self.detail)}


@dataclass(frozen=True)
class Assertion:
    """One scorecard line. `observed / of`, never true/false.

    `observed` is always the GOOD count, so every score reads higher-is-better and the diff can
    treat them uniformly. `of` is the number of opportunities; `of == 0` means the run contained no
    opportunity, and `score` is then `None` rather than `0.0`."""

    id: int
    name: str
    observed: int
    of: int
    evidence: tuple[Evidence, ...] = ()
    note: str = ""

    @property
    def score(self) -> float | None:
        if self.of <= 0:
            return None
        return round(min(1.0, self.observed / self.of), 4)

    def as_json(self) -> dict[str, object]:
        return {"id": self.id, "name": self.name, "observed": self.observed, "of": self.of,
                "score": self.score, "note": self.note,
                "evidence": [e.as_json() for e in self.evidence]}


@dataclass(frozen=True)
class Scorecard:
    """Every assertion for one transcript, plus enough provenance to trust the numbers."""

    transcript: str
    turns: int
    assertions: tuple[Assertion, ...]
    grouping_consistent: bool = True
    label: str = ""

    def as_json(self) -> dict[str, object]:
        return {"kind": "coyodex-l3-scorecard", "version": 1, "transcript": self.transcript,
                "label": self.label, "turns": self.turns,
                "grouping_consistent": self.grouping_consistent,
                "assertions": [a.as_json() for a in self.assertions]}

    def by_id(self) -> dict[int, Assertion]:
        return {a.id: a for a in self.assertions}


# --- shared helpers --------------------------------------------------------------------

#: A heredoc body — `<<'EOF' … EOF` or `<<EOF … EOF`. Its contents are DATA, not shell.
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?^\s*\2\s*$", re.S | re.M)
#: A quoted span that crosses a newline: the body of `python3 -c "…"`. Also data, not shell.
_MULTILINE_QUOTE = re.compile(r"(['\"])(?:(?!\1).)*?\n(?:(?!\1).)*?\1", re.S)


def _shell_only(command: str) -> str:
    """The command with embedded PROGRAM TEXT removed — heredoc bodies and multi-line quoted
    strings.

    Without this, a `python3 - <<'PY' … PY` block whose body merely MENTIONS `coyodex anchor-drift`
    (in a comment, or in a string it is about to print) reads as an invocation. That was a real
    over-count in this module's first draft: three shape-only anchor-drift runs reported across the
    post-change corpus where one had happened. The bodies are still available to callers that want
    them — `ToolCall.text()` returns the whole input — but nothing that asks 'was this command RUN'
    may look inside them."""
    without_heredoc = _HEREDOC.sub(" ", command)
    return _MULTILINE_QUOTE.sub(" ", without_heredoc)


def _segments(command: str) -> list[str]:
    """A shell command split into the pieces that could each be an invocation. Crude on purpose:
    the question is only 'was `coyodex X` RUN here', and splitting on the operators that start a new
    command answers it without pretending to be a shell parser. Embedded program text is stripped
    first — see `_shell_only`."""
    return [s.strip() for s in re.split(r"&&|\|\||[;\n|]", _shell_only(command)) if s.strip()]


#: Subcommands that belong to `coyodex` alone. Only these may be recognised behind a shell
#: variable (`$CX audit`), where the binary's identity cannot be read off the command itself.
_COYODEX_SUBCOMMANDS = frozenset({
    "preindex", "validate", "audit", "render", "serve", "assemble", "lint-fragment",
    "anchor-drift", "fix", "dump", "reconcile", "balance",
})


def _invokes(command: str, subcommand: str) -> bool:
    """Did this command actually RUN `coyodex <subcommand>`?

    Two failure modes, both found against the real corpus and both fixed here:

    * **Substring matching over-counts.** `grep -n 'coyodex anchor-drift' method.md` mentions the
      command without running it, and a `python3 - <<'PY'` body that prints the string does too.
      So the match must sit at the START of a command segment, and `_segments` strips embedded
      program text first.
    * **A path prefix is not the only spelling.** Every measured build assigns the binary to a
      variable and calls `$CX anchor-drift …` / `$C audit …`. Requiring the literal token `coyodex`
      missed all of those — in the baseline corpus it hid every `audit` invocation mee6 made. A
      `$VAR` prefix is therefore accepted, but ONLY for a subcommand that is coyodex's alone
      (`_COYODEX_SUBCOMMANDS`), so `$PY dump` cannot be mistaken for `coyodex dump`."""
    sub = re.escape(subcommand)
    named = re.compile(r"^(?:[\w./~-]*/)?(?:\.?venv/bin/)?coyodex(?:-eval)?\s+" + sub + r"\b")
    aliased = re.compile(r"^\"?\$\{?\w+\}?\"?\s+" + sub + r"\b")
    allow_alias = subcommand in _COYODEX_SUBCOMMANDS
    for seg in _segments(command):
        seg = re.sub(r"^(?:sudo|time|nohup|env(?:\s+\w+=\S+)*)\s+", "", seg)
        if named.search(seg):
            return True
        if allow_alias and aliased.search(seg):
            return True
    return False


#: Producing a file from a program rather than by redirect: `open('…/reconcile.json', 'w')`,
#: `json.dump(x, open('…reconcile.json','w'))`, `Path(…).write_text(…)`. The measured builds all
#: went this way — mee6's `reconcile.json` came out of a 24 KB generator script, so a detector that
#: only understood `>` redirects reported that mee6 produced no reconcile file at all.
def _python_write(blob: str, needle: str) -> bool:
    esc = re.escape(needle)
    return bool(re.search(r"open\s*\(\s*[^)]*" + esc + r"[^)]*['\"][wa]", blob)
                or re.search(r"json\.dump\s*\([^)]*" + esc, blob)
                or re.search(esc + r"[^)\n]*\)\s*\.write_text", blob))


def _writes_path(call: ToolCall, needle: str) -> bool:
    """Did this tool call PRODUCE the named file — however it did it?

    Three shapes, all seen in the corpus: a direct `Write`/`Edit`; a shell redirect or `tee`; and a
    program that opens the file for writing, which may be a heredoc OR the body of a helper script
    written to the scratchpad and run later. The last one is why the whole tool input is searched
    and not just the command line."""
    if call.name in ("Write", "Edit", "NotebookEdit"):
        target = call.input.get("file_path")
        if isinstance(target, str) and target.endswith(needle):
            return True
    blob = call.text()
    if needle not in blob:
        return False
    if call.name == "Bash" and re.search(r"(>|>>|tee\s+|--out\s+\S*)\s*\S*" + re.escape(needle),
                                         call.command):
        return True
    return _python_write(blob, needle)


def _is_skeptic(call: ToolCall) -> bool:
    blob = call.text().lower()
    return any(word in blob for word in _SKEPTIC_WORDS)


def _at_least_once(count: int) -> tuple[int, int]:
    """`observed / of` for a 'did this happen at all' assertion: the target is one."""
    return count, 1


def _escape_tokens(warning: str) -> tuple[str, ...]:
    """The recordable escapes an advisory names, if any. An advisory naming none cannot be
    'recorded' at all, so assertion 9 must not count it as a missed reconciliation."""
    found = [m.group(1).strip().lower() for m in _ESCAPE_HEADING.finditer(warning)]
    found += [m.group(1).strip().lower() for m in _ESCAPE_LITERAL.finditer(warning)]
    return tuple(dict.fromkeys(found))


def _validate_warnings(turns: Sequence[Turn]) -> list[tuple[int, tuple[str, ...]]]:
    """(turn index, warning lines) for every `coyodex validate` run whose OUTPUT the transcript
    captured, in call order.

    Each validate call is paired with its OWN result by `tool_use_id`. Pairing by order was wrong:
    results arrive out of order when sub-agents are in flight, so one command's warnings could be
    attributed to another run entirely — and assertion 9 turns on which run was LAST.

    Because the pairing is by id, the result is KNOWN to belong to a validate call, so no header
    sniffing is needed — and requiring the `VALIDATION WARNINGS` banner was actively wrong: the
    measured builds routinely pipe validate through `grep -E "^  - …"`, which strips the banner and
    keeps the advisory lines. That requirement reported "no validate output captured" for a build
    that ran validate nineteen times.

    Two deliberate exclusions and one deliberate bias:
      * `--emit-unclaimed` prints a ready-to-paste extras block, not advisories — skipped;
      * a run whose captured output holds NO advisory line (a `grep -c` count, a redirect to a
        file) is skipped rather than treated as a clean sheet. That biases the measure toward
        reporting advisories as unresolved, which is the safe direction for a check about
        advisories being waved through: it can under-credit a build, never over-credit one."""
    results = results_by_tool_use_id(turns)
    outputs: list[tuple[int, tuple[str, ...]]] = []
    for turn in turns:
        for call in turn.calls_named("Bash"):
            if not _invokes(call.command, "validate") or "--emit-unclaimed" in call.command:
                continue
            text = results.get(call.id, "")
            if not text:
                continue
            body = text.split("VALIDATION WARNINGS", 1)[-1]
            lines = tuple(ln.strip()[2:].strip() for ln in body.splitlines()
                          if ln.strip().startswith("- "))
            if lines:
                outputs.append((turn.index, lines))
    return outputs


# --- the ten assertions ----------------------------------------------------------------

def assert_1_preindex_report_used(turns: Sequence[Turn]) -> Assertion:
    """1 — `coyodex preindex --report` appears in a Bash call.

    The read command exists BECAUSE all four measured builds hand-wrote
    `python3 -c "json.load(open('.coyodex/preindex.json'))…"` to get the weight tree and per-slice
    E. Does adding it change behaviour?"""
    hits = [Evidence(idx, {"command": cmd[:120]}) for idx, cmd in bash_commands(turns)
            if _invokes(cmd, "preindex") and "--report" in cmd]
    observed, of = _at_least_once(len(hits))
    return Assertion(1, "preindex --report used", observed, of, tuple(hits))


def assert_2_preindex_not_hand_parsed(turns: Sequence[Turn]) -> Assertion:
    """2 — no turn parses `preindex.json` by hand.

    The negative half of #1: a build that runs `--report` AND still hand-parses has not adopted it.
    `of` counts every shell touch of the artifact; `observed` counts the ones that went through the
    tool. Two things are deliberately NOT hand-parses: `preindex --report --in <path>`, which names
    the file because that is the flag's job, and housekeeping (`git add …/preindex.json`) that moves
    the artifact without reading it. The hand-parse patterns therefore require the file to be an
    OPERAND of a reader — see `_HAND_PARSE`.

    The heredoc body IS searched here, unlike in `_invokes`: `python3 - <<'PY' … json.load(open(
    '.coyodex/preindex.json')) … PY` is precisely the behaviour this assertion exists to catch, and
    it lives inside the heredoc."""
    good: list[Evidence] = []
    bad: list[Evidence] = []
    for idx, cmd in bash_commands(turns):
        touches = PREINDEX_JSON in cmd
        reports = _invokes(cmd, "preindex") and "--report" in cmd
        if not (touches or reports):
            continue
        hand = touches and any(p.search(cmd) for p in _HAND_PARSE)
        (bad if hand else good).append(Evidence(idx, {"command": cmd[:120],
                                                      "hand_parsed": hand}))
    return Assertion(2, "preindex.json never hand-parsed", len(good), len(good) + len(bad),
                     tuple(bad or good))


def assert_3_fanout_is_one_message(turns: Sequence[Turn]) -> Assertion:
    """3 — at least one fan-out turn contains >=2 agent calls in ONE assistant turn.

    THE HEADLINE. `method.md` requires a fan-out to be emitted as one message; the study that
    motivated L3 measured 26 of 26 fan-outs launching exactly one agent per turn.

    `of` is the number of fan-out turns (any turn launching at least one agent); `observed` is how
    many of those launched two or more. Every fan-out turn is carried in the evidence with its agent
    count, so the shape of the distribution is visible and not just its summary."""
    fanouts = [(t.index, len(t.agent_calls)) for t in turns if t.agent_calls]
    batched = [n for _idx, n in fanouts if n >= 2]
    evidence = tuple(Evidence(idx, {"agents": n}) for idx, n in fanouts)
    return Assertion(3, "fan-out emitted as one message", len(batched), len(fanouts), evidence)


def assert_4_shape_only_anchor_drift(turns: Sequence[Turn]) -> Assertion:
    """4 — `coyodex anchor-drift` runs with NO `--verdicts` (the shape-only pass).

    The serial-build grounding floor: it needs no skeptics, so a build with none still gets
    deterministic drift findings. Nothing yet showed it was reached."""
    hits: list[Evidence] = []
    for idx, cmd in bash_commands(turns):
        if not _invokes(cmd, "anchor-drift"):
            continue
        if "--verdicts" in cmd:
            continue
        hits.append(Evidence(idx, {"command": cmd[:120]}))
    observed, of = _at_least_once(len(hits))
    return Assertion(4, "shape-only anchor-drift run", observed, of, tuple(hits))


def assert_5_skeptics_fanned_out(turns: Sequence[Turn]) -> Assertion:
    """5 — Phase-4 skeptics are launched at all, and in >=1 batched fan-out.

    A live small-repo build finished and told the user it had no fresh-context skeptics — the exact
    blind spot Phase 4 exists to break. `of` is 1 (the target is one batched skeptic fan-out), so a
    build that launches no skeptics scores 0.0 rather than falling into 'not applicable'."""
    total = 0
    batched: list[Evidence] = []
    launched: list[Evidence] = []
    for turn in turns:
        skeptics = [c for c in turn.agent_calls if _is_skeptic(c)]
        if not skeptics:
            continue
        total += len(skeptics)
        launched.append(Evidence(turn.index, {"skeptics": len(skeptics)}))
        if len(skeptics) >= 2:
            batched.append(Evidence(turn.index, {"skeptics": len(skeptics)}))
    observed, of = _at_least_once(len(batched))
    note = f"{total} skeptic agent(s) across {len(launched)} turn(s)"
    return Assertion(5, "Phase-4 skeptics fanned out", observed, of, tuple(launched), note)


def assert_6_grounding_recorded(turns: Sequence[Turn],
                                ctx: "ScoreContext | None" = None) -> Assertion:
    """6 — the assembled model carries a non-empty `grounding` object.

    A monorepo build grounded 319 of 1,608 claims and reported it only in chat, where it evaporated.

    READ THE MAP when one is given: that is what the assertion actually claims to measure, and
    grepping the transcript for it got the answer exactly backwards. The old rule looked for
    `claims_total` in a tool call's own text, which is present when a build HAND-WRITES the record
    in a python heredoc and absent when it runs `coyodex grounding write` (the string appears only
    in that command's output). So the correct path scored 0.0 and the defect scored 1.0 — a live
    build used the command, scored 0, and read as a regression against the previous build that had
    hand-tallied it.

    Without a map, fall back to the transcript and count BOTH paths — the command counts as
    evidence, not just the hand-written text."""
    grounding = ctx.grounding if ctx else None
    if grounding is not None:
        non_empty = bool(grounding) and any(
            v for k, v in grounding.items() if k != "note")
        ev = (Evidence(0, {"source": "map", "claims_total": grounding.get("claims_total", 0)}),)
        return Assertion(6, "grounding recorded in the model", 1 if non_empty else 0, 1,
                         ev if non_empty else (), "read from the map")
    hits: list[Evidence] = []
    for turn in turns:
        for call in turn.tool_calls:
            if call.name not in ("Write", "Edit", "NotebookEdit", "Bash"):
                continue
            blob = call.text()
            wrote_by_hand = ("claims_total" in blob or "claims_challenged" in blob
                             or "claims_grounded" in blob)
            by_command = call.name == "Bash" and _invokes(call.command, "grounding")
            if wrote_by_hand or by_command:
                hits.append(Evidence(turn.index, {
                    "tool": call.name,
                    "how": "coyodex grounding write" if by_command else "hand-written"}))
                break
    observed, of = _at_least_once(len(hits))
    return Assertion(6, "grounding recorded in the model", observed, of, tuple(hits),
                     "inferred from the transcript — no map given")


def assert_7_reconcile_command_used(turns: Sequence[Turn]) -> Assertion:
    """7 — `coyodex reconcile` is used, or `reconcile.json` is written some other way.

    The headline class-2 defect: a working, tested command that ran zero times in four builds while
    every one hand-wrote its output (one was 24 KB, 139 rules, 882 id assignments).

    `of` counts every time the build produced a `reconcile.json`; `observed` counts the ones the
    command produced. A build with no assignments to make produces none, and scores `None`."""
    by_tool: list[Evidence] = []
    by_hand: list[Evidence] = []
    for turn in turns:
        for call in turn.tool_calls:
            if call.name == "Bash" and _invokes(call.command, "reconcile"):
                by_tool.append(Evidence(turn.index, {"how": "coyodex reconcile"}))
            elif _writes_path(call, RECONCILE_JSON):
                size = len(str(call.input.get("content", "")))
                by_hand.append(Evidence(turn.index, {"how": f"hand-written via {call.name}",
                                                     "bytes": size}))
    return Assertion(7, "reconcile.json produced by the command", len(by_tool),
                     len(by_tool) + len(by_hand), tuple(by_tool + by_hand))


def assert_8_audit_read_as_json(turns: Sequence[Turn]) -> Assertion:
    """8 — `coyodex audit --json` is used, and audit output is not paged through head/sed/grep.

    The machine-readable payload was built for the Phase-4 batching step, and the method forbids
    regex-parsing the human report. `of` is every audit invocation; `observed` is those that asked
    for JSON and did not page the result."""
    good: list[Evidence] = []
    bad: list[Evidence] = []
    for idx, cmd in bash_commands(turns):
        if not _invokes(cmd, "audit"):
            continue
        as_json = "--json" in cmd
        paged = bool(_PAGERS.search(cmd))
        target = good if (as_json and not paged) else bad
        target.append(Evidence(idx, {"json": as_json, "paged": paged, "command": cmd[:120]}))
    return Assertion(8, "audit read as JSON, not paged", len(good), len(good) + len(bad),
                     tuple(bad or good))


def assert_9_no_advisory_waved_through(turns: Sequence[Turn]) -> Assertion:
    """9 — no advisory is left both unfixed and unrecorded.

    'Advisory waved through' is the failure the method names in its own words. Measured against the
    transcript alone: collect every RECORDABLE advisory that any `coyodex validate` run printed
    during the build (one that names an extras heading or a literal token — an advisory naming no
    escape cannot be recorded, so counting it would be unfair), then check whether it is still
    present in the FINAL validate output. Gone means fixed or recorded; still there means waved
    through.

    `of` is 0 when the build never ran validate with captured output, or printed no recordable
    advisory — both genuinely 'nothing to measure'.

    **Read this number with its note.** 'The final run' is only a complete view of the map when the
    build did not narrow it. Every measured build pipes validate through `grep`, and one of them
    ended on a grep that returned a single line — against which almost anything looks resolved. So
    the note carries the run sizes, and says plainly when the last view was a fraction of the widest
    one. A transcript cannot do better than that: the full final state lives in the map file, not in
    the transcript, and inventing precision here would be worse than reporting the limit."""
    runs = _validate_warnings(turns)
    if not runs:
        return Assertion(9, "no advisory left unfixed and unrecorded", 0, 0, (),
                         "no validate output captured in this transcript")
    seen: dict[str, int] = {}
    for at, lines in runs:
        for line in lines:
            if _escape_tokens(line):
                seen.setdefault(line, at)
    final_at, final_lines = runs[-1]
    still = {line for line in final_lines if line in seen}
    resolved = [line for line in seen if line not in still]
    widest = max(len(lines) for _at, lines in runs)
    note = (f"{len(runs)} validate run(s) captured; final view {len(final_lines)} line(s), "
            f"widest {widest}")
    if len(final_lines) * 2 < widest:
        note += " — FINAL VIEW WAS NARROWED (grepped), so this score is optimistic"
    evidence = tuple(Evidence(final_at, {"unresolved": line[:120]}) for line in sorted(still))
    return Assertion(9, "no advisory left unfixed and unrecorded", len(resolved), len(seen),
                     evidence, note)


def assert_10_idle_turns_at_a_barrier(turns: Sequence[Turn]) -> Assertion:
    """10 — turns burned waiting at a fan-out barrier stay under a threshold.

    The method says wait on completion notifications, never poll: a not-ready file reads as an error
    and burns turns. Each idle turn is attributed to the most recent preceding fan-out, so the
    threshold is per fan-out as the design proposes. `of` is the number of fan-outs; `observed` is
    how many stayed under the ceiling.

    TWO shapes count, because scoring only the first one made this assertion lie. It used to match
    `ls`/`find`/`stat`/`wc` naming the fragment dir and nothing else; a live build waited with
    `echo .` instead, burned 42 of its 195 tool calls, and scored 38/38 — reported as an improvement
    from 0.60 while the waste roughly tripled. What the assertion is about is turns spent waiting,
    so it counts a no-op command too (see `_is_noop_wait`)."""
    fanouts = [t.index for t in turns if t.agent_calls]
    if not fanouts:
        return Assertion(10, "idle turns at a barrier under threshold", 0, 0, (),
                         "no fan-out in this transcript")
    idle: dict[int, int] = {idx: 0 for idx in fanouts}
    evidence: list[Evidence] = []
    for idx, cmd in bash_commands(turns):
        polls_dir = FRAGMENT_DIR in cmd and bool(re.search(r"\b(ls|find|stat|wc)\b", cmd))
        noop = _is_noop_wait(cmd)
        if not (polls_dir or noop):
            continue
        owner = max((f for f in fanouts if f <= idx), default=fanouts[0])
        idle[owner] += 1
        evidence.append(Evidence(idx, {"after_fanout": owner,
                                       "kind": "fragment-dir poll" if polls_dir else "no-op turn",
                                       "command": cmd[:120]}))
    under = [idx for idx, n in idle.items() if n <= POLL_THRESHOLD]
    return Assertion(10, "idle turns at a barrier under threshold", len(under), len(fanouts),
                     tuple(evidence), f"threshold {POLL_THRESHOLD} idle turn(s) per fan-out")


#: Every assertion, in scorecard order. 11 is deliberately absent: it compares a built map against
#: the trapdoor golden map, and that golden map was assembled from an authored fragment rather than
#: produced by a live agent build — the blocker the design already names. 1-10 need a transcript and
#: nothing else, so they run against any build of any repo.
_FINALIZE_VERDICT = re.compile(r"finalize:\s+(CLEAN|ADVISORIES|BLOCKED|BLOCKING|INCOMPLETE)\s+—\s+"
                               r"(\d+)\s+blocking,\s+(\d+)\s+advisory")
#: Words a commit message uses to claim a gate passed. `clean` is the one a live build actually used.
_CLEAN_CLAIM = re.compile(r"\b(clean|no findings|all clear|passed)\b", re.I)
#: A line that REPORTS the gates, not one that merely mentions a tool. The distinction is the whole
#: measurement: `anchor-drift: clean up the drift regex` is an honest conventional-commit subject
#: about editing that module, and scoring it as a false gate claim would make this assertion a liar
#: about liars — the "the reader is the measurement" failure L3-DESIGN.md opens with. So the line
#: must read like a gate REPORT: it leads with `Gates:`/`finalize`, or pairs a gate name with a
#: verdict word or a finding count.
_GATE_REPORT = re.compile(
    r"^\s*(gates?\b|finalize\b)"                                   # `Gates: …` / `finalize: …`
    r"|\b(validate|audit|anchor-drift|finalize)\b[^:]{0,60}?"       # or a gate named alongside
    r"\b(\d+\s+(blocking|advisor|finding|warning)|advisories|blocking|contradiction)", re.I)


def _false_gate_claim(commit_text: str) -> str | None:
    """The gate-claiming phrase in a commit message, if any — one line at a time.

    Deliberately conservative: it under-reports rather than accuse an honest commit. A miss costs a
    number; a false accusation costs the assertion its credibility."""
    for line in commit_text.splitlines():
        if _GATE_REPORT.search(line):
            hit = _CLEAN_CLAIM.search(line)
            if hit:
                return hit.group(0)
    return None


def assert_12_commit_matches_the_finalize_verdict(turns: Sequence[Turn]) -> Assertion:
    """The commit message's gate claims must match what `finalize` actually said, in the same run.

    Assertion 9 cannot see this: it reads `validate` warnings against the model's extras, and a build
    can satisfy it while writing something else entirely into git. A live build quoted its verdict
    honestly in chat ("that is not a clean pass") and then committed
    `validate … clean (1166 anchors resolved) … anchor-drift clean … each reconciled or recorded` —
    three false clauses against its own report, with an anchor count copied from a run 2.5 hours
    earlier. Chat is ephemeral; the commit is the record a future reader gets.

    Transcript-only BY DESIGN: it pairs the `finalize:` verdict line the transcript captured with the
    `git commit` text in the same transcript. Reading `.coyodex/finalize-report.json` instead would
    break the "1-10 need a transcript and nothing else" invariant and make an archived scorecard
    depend on repo state at scoring time.

    `of == 0` (n/a) when the run never both ran finalize and committed — no opportunity, not a miss."""
    results = results_by_tool_use_id(turns)
    verdict: str | None = None
    at: int | None = None
    text = ""
    for turn in turns:
        for call in turn.calls_named("Bash"):
            if _invokes(call.command, "finalize"):
                # Only the RESULT, never the command text: `finalize | grep "finalize: CLEAN …"`
                # would otherwise launder a grep PATTERN into a verdict.
                hit = _FINALIZE_VERDICT.search(results.get(call.id, ""))
                if hit:
                    verdict = hit.group(1)
            elif re.search(r"\bgit\s+commit\b", call.command):
                # The verdict in force AT THIS COMMIT. Pairing the last commit with the last verdict
                # overall let a later CLEAN run whitewash an earlier dishonest commit, and failed an
                # honest one whose CLEAN was superseded afterwards.
                at, text = turn.index, call.command
                if verdict is not None:
                    break
    if verdict is None or at is None:
        return Assertion(12, "commit message matches the finalize verdict", 0, 0, (),
                         "no finalize verdict and/or no git commit captured in this transcript")
    # Only an ADVISORIES/BLOCKING verdict can be contradicted: a CLEAN verdict makes "clean" true.
    claim = _false_gate_claim(text)
    honest = verdict == "CLEAN" or claim is None
    ev = () if honest else (Evidence(at, {"verdict": verdict, "commit_claims": claim or ""}),)
    return Assertion(12, "commit message matches the finalize verdict", 1 if honest else 0, 1, ev,
                     f"finalize said {verdict}")


# --- helpers for assertions 13-17 ---------------------------------------------------------------

#: A shell command that writes a file — the shapes a build actually uses to patch a fragment.
_WRITES_A_FILE = re.compile(r"(>>?\s*\S|\btee\b|json\.dump\b|\.write_text\b|\bcp\b|\bmv\b)")

#: A content filter on a gate's output, as opposed to merely paging it.
_GREP_FILTER = re.compile(r"\|\s*(?:grep|egrep|rg|ag)\b")

#: A shell command that READS a file's contents, as opposed to merely naming it. The distinction is
#: load-bearing: a fragment-patching heredoc mentions the very path whose drift is being recorded,
#: and counting that as "the agent looked" turned assertion 17 from 0/2 into a false 1.00 on the
#: build that motivated it.
_READER_CMD = re.compile(r"\b(?:cat|sed|grep|egrep|rg|ag|head|tail|awk|less|bat|open)\b")

#: A source path inside such a command.
_SOURCE_PATH = re.compile(r"[\w./-]+\.(?:py|ts|tsx|js|jsx|go|rs|rb|java|kt|json|yaml|yml|toml)")


def _paths_read(call: ToolCall) -> set[str]:
    """The source files this call actually opened — `Read`, or a shell READER command."""
    if call.name == "Read":
        return {str(call.input.get("file_path", ""))}
    if call.name == "Bash" and _READER_CMD.search(call.command):
        return set(_SOURCE_PATH.findall(call.command))
    return set()

#: A recorded drift-exception key as it appears in a COMMAND: ``anchor-drift `<key>`: <why>``.
#:
#: The delimiter may carry ANY run of backslashes. `coyodex record --line "anchor-drift \\`…"` is
#: the documented way to write a record, which escapes the backtick once, and a live build's nested
#: quoting doubled it again — the real bytes were `anchor-drift \\\\``. Requiring a bare backtick
#: made three well-formed records invisible, so the assertion scored 0/2 for a behaviour the build
#: had actually performed, and the retrospective reading that score had to go and find out why.
#: Quote characters are accepted alongside backticks for the same reason `anchor_drift` accepts
#: them: every cadence claim is phrased with them.
_DRIFT_KEY_IN_TEXT = re.compile(r"anchor-drift\s+\\*([`'\"])(.+?)\\*\1")

#: One drift FINDING as `anchor-drift` prints it: the claim, then `stored [path:line]`. The claim
#: and the file arrive on the same line, which is what lets a recorded exception be paired with the
#: file it should have been checked against — the exception KEY is the claim text and carries no
#: path of its own.
_DRIFT_FINDING_LINE = re.compile(r"([^\n]+?):\s*stored \[([\w./-]+\.\w+):\d+\]")

#: One drift finding in the `--json` shape `{"claim": "...", "stored": "path:line", ...}`. Read as
#: text rather than parsed, because the payload arrives inside a tool RESULT that may be truncated
#: mid-object; a regex recovers the pairs that did land, where `json.loads` would recover none.
_DRIFT_FINDING_JSON = re.compile(
    r'"claim"\s*:\s*"((?:[^"\\]|\\.)*)"[^}]*?"stored"\s*:\s*"([\w./-]+\.\w+):\d+"')

#: Launches more than this far apart belong to different fan-outs. A real batch dispatches ~10-20 s
#: apart even when serialised one message at a time; separate phases sit minutes apart.
_FANOUT_GAP_SECONDS = 300.0


def _seconds(stamp: str) -> float | None:
    from datetime import datetime
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _fanout_groups(turns: Sequence[Turn]) -> list[list[tuple[int, float | None]]]:
    """Agent launches grouped into fan-outs, each entry `(launch turn, duration in seconds)`.

    Duration is the gap between the launch turn and the turn carrying that call's tool_result, so a
    background launch measures the AGENT's runtime rather than the launch acknowledgement."""
    ended: dict[str, float | None] = {}
    for turn in turns:
        for res in turn.tool_results:
            ended.setdefault(res.tool_use_id, _seconds(turn.timestamp))
    launches: list[tuple[int, float | None, float | None]] = []
    for turn in turns:
        for call in turn.agent_calls:
            started = _seconds(turn.timestamp)
            finished = ended.get(call.id)
            launches.append((turn.index, started, finished))
    groups: list[list[tuple[int, float | None]]] = []
    prev_start: float | None = None
    for idx, started, finished in launches:
        duration = (finished - started) if (started is not None and finished is not None) else None
        new_group = (not groups or started is None or prev_start is None
                     or started - prev_start > _FANOUT_GAP_SECONDS)
        if new_group:
            groups.append([])
        groups[-1].append((idx, duration))
        prev_start = started
    return groups


# --- assertions 13-17: added from the 2026-08-01 retro ------------------------------------------
#
# Each is a repeatable process defect a real build committed and no existing assertion could see.
# The scorecard exists to turn a one-off discovery into a number that gets watched.


def assert_13_grounding_write_is_the_last_write(turns: Sequence[Turn]) -> Assertion:
    """13 — `grounding write` runs AFTER the last reconcile edit, not before it.

    `grounding write` pins `claims_total` to the worklist as it stands. Reconciling a refutation
    rewrites the claim, which orphans its verdict — so a record written first describes a map that
    no longer exists. A live build wrote it at turn 394 and reconciled nine refutations at 400-428;
    the map shipped `418 of 418 challenged` while the live worklist held 415 and only 403 could be
    matched. `validate` cannot catch it: it blocks only `challenged > total`, and 418 = 418 passes.

    `of` is 1 when the run wrote a grounding record at all; `observed` is 1 when nothing edited a
    fragment or the map after it."""
    wrote_at: int | None = None
    edited_after: list[Evidence] = []
    for turn in turns:
        for call in turn.tool_calls:
            if call.name == "Bash" and _invokes(call.command, "grounding"):
                wrote_at = turn.index
                continue
            if wrote_at is None or turn.index <= wrote_at:
                continue
            touches = call.text()
            # An `assemble` after `grounding write` is now PRESCRIBED, not a violation: the record
            # lives in a fragment, so a final assemble is the only way it reaches the map, and
            # `grounding write --map` needs the assembled map to measure the live claim surface.
            # Assemble is idempotent on claims (verified over the real fragments: 444, 444, 444), so
            # it cannot invalidate what the record just measured. Before this carve-out the
            # assertion scored 0 for every build that followed the method — the redirection in
            # `assemble … 2>&1 | tail -3` alone matched `_WRITES_A_FILE`.
            if call.name == "Bash" and _invokes(call.command, "assemble"):
                continue
            if (FRAGMENT_DIR in touches or "project-map.json" in touches) and (
                    call.name in ("Write", "Edit", "NotebookEdit")
                    or (call.name == "Bash" and _WRITES_A_FILE.search(call.command))):
                edited_after.append(Evidence(turn.index, {"tool": call.name}))
    if wrote_at is None:
        return Assertion(13, "grounding write is the last write", 0, 0, (),
                         "no grounding record written in this transcript")
    return Assertion(13, "grounding write is the last write", 0 if edited_after else 1, 1,
                     tuple(edited_after),
                     f"written at turn {wrote_at}; {len(edited_after)} later map/fragment write(s)")


def assert_14_grounding_total_matches_the_worklist(turns: Sequence[Turn]) -> Assertion:
    """14 — the grounding record accounts for the map's live claim surface.

    It used to require `claims_total == live worklist`. That is now the WRONG rule: reconciling a
    refutation rewrites its claim, so the pinned surface and the shipped one legitimately differ,
    and the pin cannot simply be recomputed — the claims a reconcile deletes are exactly the refuted
    ones, so re-pinning records `refuted 0`. A build following the current method deliberately
    ships `total != live` and states the delta instead, via `grounding write --map`, which records
    `claims_superseded`, `claims_added_since` and a digest of the live claim set.

    So this now asks: when the totals differ, does the record SAY why? A bare mismatch with no
    delta recorded is the original failure — a live build shipped `418 of 418 challenged` against a
    worklist of 415 and quoted the 418 in its commit message as fact."""
    pinned: int | None = None
    live: int | None = None
    explained = False
    at: int | None = None
    results = results_by_tool_use_id(turns)
    for turn in turns:
        for call in turn.tool_calls:
            blob = call.text() + "\n" + results.get(call.id, "")
            m = re.search(r"(\d+)\s+of\s+(\d+)\s+claim\(s\)\s+challenged", blob)
            if m:
                pinned, at = int(m.group(2)), turn.index
                explained = ("live_claims_digest" in blob or "superseded" in blob
                             or (call.name == "Bash" and "--map" in call.text()
                                 and _invokes(call.command, "grounding")))
            # Two shapes carry the live size: `audit`/`finalize` say "N L2 claims on the grounding
            # worklist", `anchor-drift` says "challenged N of M worklist claim(s)".
            w = (re.search(r"(\d+)\s+L2 claims on the grounding worklist", blob)
                 or re.search(r"challenged\s+\d+\s+of\s+(\d+)\s+worklist claim\(s\)", blob))
            if w:
                live = int(w.group(1))
    if pinned is None or live is None:
        return Assertion(14, "grounding accounts for the live worklist", 0, 0, (),
                         "no grounding record and audit worklist seen together")
    ok = pinned == live or explained
    ev = () if ok else (Evidence(at or 0, {"pinned": str(pinned), "live worklist": str(live),
                                           "delta recorded": "no"}),)
    return Assertion(14, "grounding accounts for the live worklist", 1 if ok else 0, 1, ev,
                     f"record pinned {pinned}; worklist held {live}"
                     + ("; delta recorded" if explained else "; no delta recorded"))

def assert_15_no_advisory_rechecked_with_a_narrower_filter(turns: Sequence[Turn]) -> Assertion:
    """15 — a gate re-run is not filtered more narrowly than the run that surfaced the finding.

    A live build surfaced a messaging advisory with a wide `validate`, then re-checked with a grep
    whose pattern no longer matched that wording. The finding vanished from view and shipped
    unrecorded and unfixed. Narrowing the view is how a waved-through advisory looks handled.

    `of` counts consecutive same-gate re-runs; `observed` counts those not narrowed."""
    runs: list[tuple[int, str, int]] = []          # (turn, gate, filter width; lower = narrower)
    for idx, cmd in bash_commands(turns):
        for gate in ("validate", "audit", "balance", "anchor-drift", "finalize"):
            if not _invokes(cmd, gate):
                continue
            if _GREP_FILTER.search(cmd):
                width = 0                          # a content filter — the narrowest view
            elif _PAGERS.search(cmd):
                width = 1                          # paged, but not content-filtered
            else:
                width = 2                          # read whole
            runs.append((idx, gate, width))
            break
    narrowed: list[Evidence] = []
    pairs = 0
    for gate in {g for _, g, _ in runs}:
        seq = [(i, w) for i, g, w in runs if g == gate]
        for (_, prev), (idx, cur) in zip(seq, seq[1:]):
            pairs += 1
            if cur < prev:
                narrowed.append(Evidence(idx, {"gate": gate, "was": prev, "now": cur}))
    if not pairs:
        return Assertion(15, "no advisory re-checked with a narrower filter", 0, 0, (),
                         "no gate was run twice in this transcript")
    return Assertion(15, "no advisory re-checked with a narrower filter",
                     pairs - len(narrowed), pairs, tuple(narrowed))


def assert_16_longest_slice_dispatched_first(turns: Sequence[Turn]) -> Assertion:
    """16 — the slowest agent in a fan-out is not the one dispatched last.

    A straggler dispatched last holds the barrier for its whole runtime. In a live build the T5
    domain-model slice ran 10.2 min against siblings' 5.0-6.9 and was dispatched twelfth, closing
    the barrier ~4 min later than it had to. The method warns about stragglers but never says
    "dispatch the known-longest slice first".

    `of` counts fan-outs whose agents can be timed; `observed` counts those where the slowest agent
    was not in the last third of the dispatch order."""
    ok, bad = 0, []
    for group in _fanout_groups(turns):
        timed = [(idx, dur) for idx, dur in group if dur is not None]
        if len(timed) < 3:
            continue
        slowest_at = max(timed, key=lambda p: p[1])[0]
        order = [idx for idx, _ in timed]
        rank = order.index(slowest_at)
        if rank >= (len(order) * 2) // 3:
            bad.append(Evidence(slowest_at, {"dispatched": rank + 1, "of": len(order)}))
        else:
            ok += 1
    total = ok + len(bad)
    if not total:
        return Assertion(16, "longest slice dispatched first", 0, 0, (),
                         "no fan-out with timeable agents in this transcript")
    return Assertion(16, "longest slice dispatched first", ok, total, tuple(bad))


def assert_17_a_drift_exception_cites_a_file_that_was_read(turns: Sequence[Turn]) -> Assertion:
    """17 — a recorded drift exception is preceded by actually opening the file it is about.

    A live build recorded two drift findings as false alarms without a single Read or grep of either
    cited file between the finding and the record, on asserted reasoning about what a cadence anchor
    "is defined to point at". The two SECURITY anchors in the same run were properly checked against
    source first, which is the standard the drift ones fell short of.

    The file cannot come from the exception KEY — the key is the claim text ("… runs on cadence
    'continuous'"), which carries no path. It comes from the FINDING the record answers, which
    `anchor-drift` prints as `stored [path:line]`. So: collect the files the open drift findings
    cite, then ask whether the run opened any of them before writing the record.

    `of` counts recorded drift exceptions; `observed` counts those preceded by such a read."""
    cited: dict[str, str] = {}         # drift claim → the file its stored anchor names
    opened: set[str] = set()           # files read since the finding that named them
    checked, unchecked = 0, []
    for turn in turns:
        for result in turn.tool_results:
            for claim, path in _DRIFT_FINDING_LINE.findall(result.content):
                cited[claim.strip()] = path
            # The same findings in their `--json` shape. A build that captured `anchor-drift --json`
            # (or paged the text through `head`) produced no `stored [path:line]` line at all, so
            # every record scored "(no matching drift finding)" — the assertion reporting 0 for a
            # reason other than the behaviour it audits.
            for claim, path in _DRIFT_FINDING_JSON.findall(result.content):
                cited.setdefault(claim.strip(), path)
        for call in turn.tool_calls:
            # Only reads AFTER the finding count — a file opened earlier for unrelated reasons is
            # not evidence that anyone re-checked this drift.
            for got in _paths_read(call):
                opened |= {p for p in cited.values() if p == got or got.endswith(p)}
            blob = call.text()
            # NOT `"anchor-drift `" in blob`: the documented way to write a record is
            # `coyodex record --line "anchor-drift \\`…"`, where the backtick is shell-escaped, so
            # the bare-backtick guard skipped exactly the records the tool tells you to write.
            if (call.name not in ("Write", "Edit", "NotebookEdit", "Bash")
                    or "anchor-drift" not in blob):
                continue
            for _delim, key in _DRIFT_KEY_IN_TEXT.findall(blob):
                # pair the record with its own finding — exact claim, else the one it contains
                path = cited.get(key.strip()) or next(
                    (p for c, p in cited.items() if key.strip() in c or c in key.strip()), "")
                if path and path in opened:
                    checked += 1
                else:
                    unchecked.append(Evidence(turn.index, {
                        "should_have_read": path or "(no matching drift finding)"}))
    total = checked + len(unchecked)
    if not total:
        return Assertion(17, "a drift exception cites a file that was read", 0, 0, (),
                         "no drift exception recorded in this transcript")
    return Assertion(17, "a drift exception cites a file that was read", checked, total,
                     tuple(unchecked))


@dataclass(frozen=True)
class ScoreContext:
    """What an assertion can know BEYOND the transcript.

    Only assertion 6 needs it today, and only because its subject is the assembled map rather than
    the run. Everything else is transcript-only by design: the scorecard must work on a corpus
    transcript whose repo has moved on. `grounding` is None when no map was given."""
    map_path: Path | None = None
    grounding: dict[str, EvidenceValue] | None = None


def read_score_context(map_path: str | Path | None) -> ScoreContext:
    """Build a context from a map path, tolerating a missing or unreadable map (the scorecard is
    never a gate, so a bad --map degrades to transcript-only rather than failing the run)."""
    if not map_path:
        return ScoreContext()
    p = Path(map_path)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ScoreContext(map_path=p)
    g = doc.get("grounding") if isinstance(doc, dict) else None
    return ScoreContext(map_path=p, grounding=g if isinstance(g, dict) else {})



# ── 18-22: added after the 2026-08-01 retrospective, each pinning a defect no number watched ─────

#: `git commit` prose claiming a shape: "416 backbone edges", "33 flows/sub-flows", "66 components".
_COMMIT_SHAPE = re.compile(
    r"(\d+)\s+(?:backbone\s+)?(components?|edges?|entities|use cases?|flows?/sub-flows?|"
    r"subsystems?|entry points?|security rows?)")

#: The same counts as `coyodex finalize --emit-gate-block` now generates them.
_GATE_SHAPE = re.compile(
    r"Shape:\s*(\d+) components in (\d+) subsystems, (\d+) entities in (\d+) subdomains, "
    r"(\d+) deps, (\d+) use cases, (\d+) edges, (\d+) flows/sub-flows")


def assert_18_commit_shape_matches_the_map(turns: Sequence[Turn]) -> Assertion:
    """A commit's shape numbers must match the map it describes.

    A live commit claimed "416 backbone edges … 33 flows/sub-flows" for a map holding 365 and 36.
    Neither was invented: both were true earlier in the build, and `fix dedup-edge` dropped 49
    duplicate occurrences after they were written down. The commit is the artifact a future reader
    trusts most, and nothing compared it against the file it names.

    Scored against the generated `Shape:` line when one is present in the run (that is what
    `finalize --emit-gate-block` emits). `of == 0` when the run has no commit carrying shape prose,
    or no generated line to check it against — an opportunity that did not arise, not a miss."""
    truth: dict[str, int] | None = None
    hits: list[Evidence] = []
    good = 0
    results = results_by_tool_use_id(turns)
    for turn in turns:
        for call in turn.calls_named("Bash"):
            blob = call.command + "\n" + results.get(call.id, "")
            g = _GATE_SHAPE.search(blob)
            if g:
                truth = {"components": int(g.group(1)), "entities": int(g.group(3)),
                         "use cases": int(g.group(6)), "edges": int(g.group(7)),
                         "flows/sub-flows": int(g.group(8))}
            if truth is None or not re.search(r"\bgit\s+commit\b", call.command):
                continue
            for n, word in _COMMIT_SHAPE.findall(call.command):
                key = word.rstrip("s") + "s" if not word.endswith("s") else word
                key = {"components": "components", "edges": "edges", "entities": "entities",
                       "use cases": "use cases", "flows/sub-flows": "flows/sub-flows"}.get(
                    word if word in truth else key, "")
                if not key or key not in truth:
                    continue
                if int(n) == truth[key]:
                    good += 1
                else:
                    hits.append(Evidence(turn.index, {"claimed": f"{n} {key}",
                                                      "map holds": str(truth[key])}))
    total = good + len(hits)
    return Assertion(18, "commit shape numbers match the map", good, total, evidence=tuple(hits))


#: An inverting grep anywhere in a shell block that also runs a gate. Deliberately NOT a pipeline
#: pattern: the real shape on a live build was `coyodex validate … > /tmp/v5.txt 2>&1; echo …;
#: grep -v 'declared .* times with differing' /tmp/v5.txt`, so a `gate | grep -v` regex saw nothing.
#: The full output being on disk does not help when the VIEW the agent reads is the inverted one.
#: Broad on purpose — a scorecard may under-credit, never over-credit.
_INVERTING_GREP = re.compile(r"\bgrep\s+(?:-\w+\s+)*-\w*v\w*\b")


def assert_19_no_gate_output_inverted_grep(turns: Sequence[Turn]) -> Assertion:
    """No gate's output is piped through `grep -v`.

    Assertion 15 catches a re-check narrowed by a pattern; it does not catch a family deleted from
    the view. A live build ran `validate … | grep -v 'declared .* times with differing'`, hiding 38
    duplicate-edge warnings that then stayed invisible across two assembles and a whole grounding
    pass — the same 38 `fix dedup-edge` listed when it was finally run.

    `observed` counts gate runs NOT inverted, so higher is better like every other line."""
    clean = 0
    hits: list[Evidence] = []
    for turn in turns:
        for call in turn.calls_named("Bash"):
            if not re.search(r"\b(validate|audit|balance|finalize|anchor-drift)\b", call.command):
                continue
            if _INVERTING_GREP.search(call.command):
                hits.append(Evidence(turn.index, {"command": call.command[:160]}))
            else:
                clean += 1
    return Assertion(19, "no gate output filtered with `grep -v`", clean, clean + len(hits),
                     evidence=tuple(hits))


def assert_21_final_assemble_digest_is_clean(turns: Sequence[Turn]) -> Assertion:
    """`assemble`'s digest lines are zero at the LAST assemble.

    The digest reports what the auto-clean passes changed and what it could not heal. A live build
    was told `UNHEALED riding steps 4` at four successive assembles and shipped without addressing
    it; the digest was printed four times and read zero times.

    Only the FINAL assemble counts: an unhealed count mid-build is expected and drains as the trace
    lands. `of == 0` when the run never assembled."""
    last: tuple[int, str] | None = None
    results = results_by_tool_use_id(turns)
    for turn in turns:
        for call in turn.calls_named("Bash"):
            if _invokes(call.command, "assemble"):
                last = (turn.index, results.get(call.id, ""))
    if last is None:
        return Assertion(21, "final assemble digest is clean", 0, 0)
    idx, out = last
    unhealed = re.search(r"UNHEALED[^\n]*?(\d+)", out)
    n = int(unhealed.group(1)) if unhealed else 0
    ev = [] if not n else [Evidence(idx, {"unhealed_at_final_assemble": str(n)})]
    return Assertion(21, "final assemble digest is clean", 0 if n else 1, 1, evidence=tuple(ev))


def assert_22_behavioral_draft_precedes_preindex(turns: Sequence[Turn]) -> Assertion:
    """GR1: the behavioral layer is drafted BEFORE the structural pre-index is used.

    `preindex` prints this rule on every run. A live build read it and went straight into a
    14-agent structural harvest; its behavioral fragment was written 79 turns later. The structural
    slices exist to serve the behavioral layer, so the order is not decoration.

    `of == 0` when the run never ran `preindex` — no opportunity."""
    first_preindex: int | None = None
    first_behavioral: int | None = None
    for turn in turns:
        for call in turn.tool_calls:
            if first_behavioral is None and call.name in ("Write", "Edit", "Bash"):
                blob = call.text()
                # `\\?"` because a tool call's text is JSON-serialised, so the fragment's own keys
                # arrive escaped (`\\"use_cases\\"`) rather than bare.
                if "build-fragments" in blob and re.search(
                        r'\\?"(use_cases|happy_path|roles|glossary)\\?"', blob):
                    first_behavioral = turn.index
            if (first_preindex is None and call.name == "Bash"
                    and _invokes(call.command, "preindex")):
                first_preindex = turn.index
    if first_preindex is None:
        return Assertion(22, "behavioral draft precedes preindex", 0, 0)
    ok = first_behavioral is not None and first_behavioral < first_preindex
    ev = [] if ok else [Evidence(first_preindex, {
        "preindex_at": str(first_preindex),
        "behavioral_draft_at": str(first_behavioral) if first_behavioral else "(never in this run)"})]
    return Assertion(22, "behavioral draft precedes preindex", 1 if ok else 0, 1, evidence=tuple(ev))


ASSERTIONS = (
    assert_1_preindex_report_used,
    assert_2_preindex_not_hand_parsed,
    assert_3_fanout_is_one_message,
    assert_4_shape_only_anchor_drift,
    assert_5_skeptics_fanned_out,
    assert_6_grounding_recorded,
    assert_7_reconcile_command_used,
    assert_8_audit_read_as_json,
    assert_9_no_advisory_waved_through,
    assert_10_idle_turns_at_a_barrier,
    assert_12_commit_matches_the_finalize_verdict,
    assert_13_grounding_write_is_the_last_write,
    assert_14_grounding_total_matches_the_worklist,
    assert_15_no_advisory_rechecked_with_a_narrower_filter,
    assert_16_longest_slice_dispatched_first,
    assert_17_a_drift_exception_cites_a_file_that_was_read,
    assert_18_commit_shape_matches_the_map,
    assert_19_no_gate_output_inverted_grep,
    assert_21_final_assemble_digest_is_clean,
    assert_22_behavioral_draft_precedes_preindex,
)


def score_turns(turns: Sequence[Turn], *, transcript: str = "", label: str = "",
                grouping_consistent: bool = True,
                ctx: ScoreContext | None = None) -> Scorecard:
    """Every assertion over an already-read turn sequence. The seam the unit tests drive with
    synthetic turns — no file, no corpus, fully deterministic."""
    ctx = ctx or ScoreContext()
    # Assertion 6 is the one whose subject is the MAP rather than the run, so it alone is handed the
    # context. Passing it to every assertion would invite the rest to reach for the repo, and a
    # scorecard that needs the repo cannot score an archived corpus transcript.
    assertions = tuple(assert_6_grounding_recorded(turns, ctx)
                       if fn is assert_6_grounding_recorded else fn(turns)
                       for fn in ASSERTIONS)
    return Scorecard(transcript=transcript, turns=len(turns), assertions=assertions,
                     grouping_consistent=grouping_consistent, label=label)


def score_transcript(path: Path | str, *, label: str = "",
                     map_path: str | Path | None = None) -> Scorecard:
    """Read a transcript and score it."""
    p = Path(path)
    turns = read_turns(p)
    return score_turns(turns, transcript=str(p), label=label or p.stem,
                       grouping_consistent=grouping_is_consistent(p),
                       ctx=read_score_context(map_path))


# --- the diff --------------------------------------------------------------------------

@dataclass(frozen=True)
class ScoreDelta:
    """One assertion, before and after. `direction` is the plain-words reading."""

    id: int
    name: str
    before: float | None
    after: float | None
    before_counts: str
    after_counts: str

    @property
    def direction(self) -> str:
        if self.before is None and self.after is None:
            return "n/a"
        if self.before is None:
            return "new"
        if self.after is None:
            return "gone"
        if self.after > self.before:
            return "up"
        if self.after < self.before:
            return "down"
        return "flat"

    def as_json(self) -> dict[str, object]:
        return {"id": self.id, "name": self.name, "before": self.before, "after": self.after,
                "before_counts": self.before_counts, "after_counts": self.after_counts,
                "direction": self.direction}


def diff(before: Scorecard, after: Scorecard) -> tuple[ScoreDelta, ...]:
    """Compare two scorecards. RELATIVE, like `coyodex-eval`'s gates: this reports which way each
    number moved, and never asserts that any of them should have been 1.0."""
    b, a = before.by_id(), after.by_id()
    out: list[ScoreDelta] = []
    for aid in sorted(set(b) | set(a)):
        ba, aa = b.get(aid), a.get(aid)
        named = aa if aa is not None else ba
        out.append(ScoreDelta(
            id=aid, name=named.name if named is not None else str(aid),
            before=ba.score if ba else None, after=aa.score if aa else None,
            before_counts=f"{ba.observed}/{ba.of}" if ba else "-",
            after_counts=f"{aa.observed}/{aa.of}" if aa else "-"))
    return tuple(out)


def load_scorecard(path: Path | str) -> Scorecard:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("kind") != "coyodex-l3-scorecard":
        raise ValueError(f"{path}: not a coyodex L3 scorecard")
    rows = doc.get("assertions")
    assertions: list[Assertion] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        ev = row.get("evidence")
        evidence = tuple(
            Evidence(turn=int(e.get("turn", -1)),
                     detail={k: v for k, v in e.items() if k != "turn"})
            for e in (ev if isinstance(ev, list) else []) if isinstance(e, dict))
        assertions.append(Assertion(id=int(row.get("id", 0)), name=str(row.get("name", "")),
                                    observed=int(row.get("observed", 0)),
                                    of=int(row.get("of", 0)), evidence=evidence,
                                    note=str(row.get("note", ""))))
    return Scorecard(transcript=str(doc.get("transcript", "")), turns=int(doc.get("turns", 0)),
                     assertions=tuple(assertions),
                     grouping_consistent=bool(doc.get("grouping_consistent", True)),
                     label=str(doc.get("label", "")))


# --- formatting ------------------------------------------------------------------------

def _fmt_score(score: float | None) -> str:
    return " n/a " if score is None else f"{score:5.2f}"


def format_scorecard(card: Scorecard) -> str:
    lines = [f"L3 process scorecard — {card.label or card.transcript}",
             f"  {card.turns} turns"
             + ("" if card.grouping_consistent else "   WARNING: message-id grouping inconsistent"),
             "",
             f"  {'#':>2}  {'score':>5}  {'counts':>8}  assertion"]
    for a in card.assertions:
        lines.append(f"  {a.id:>2}  {_fmt_score(a.score)}  {a.observed:>3}/{a.of:<4}  {a.name}"
                     + (f"   ({a.note})" if a.note else ""))
    lines += ["",
              "A scorecard, not a gate: `score` is observed/of, `n/a` means the run held no",
              "opportunity of that kind. Read it against the last run, not against 1.00."]
    return "\n".join(lines)


def format_diff(before: Scorecard, after: Scorecard) -> str:
    rows = diff(before, after)
    lines = [f"L3 scorecard diff — {before.label or before.transcript}"
             f"  ->  {after.label or after.transcript}", "",
             f"  {'#':>2}  {'before':>6}  {'after':>6}  {'move':<5}  assertion"]
    for r in rows:
        lines.append(f"  {r.id:>2}  {_fmt_score(r.before)}  {_fmt_score(r.after)}  "
                     f"{r.direction:<5}  {r.name}   [{r.before_counts} -> {r.after_counts}]")
    lines += ["", "Relative by design — which way each number moved. No threshold, no verdict."]
    return "\n".join(lines)


# --- CLI -------------------------------------------------------------------------------

USAGE = """usage: coyodex-eval process <transcript.jsonl> [--map <project-map.json>]
                                  [--out <scorecard.json>] [--json] [--label L]
       coyodex-eval process --diff <before.json> <after.json> [--json]

Score a build TRANSCRIPT against the L3 process assertions, or diff two scorecards.

--map lets assertion 6 read the built map's `grounding` record instead of inferring it from the
transcript. Without it that assertion falls back to transcript evidence and says so in its note.

Without --out, the scorecard is written next to the transcript as <name>.l3-scorecard.json.
This is a SCORECARD, not a gate: it always exits 0 unless a file is missing or unreadable, and
it never emits a pass/fail verdict. L1 (tests/test_method_contract.py) and L2
(tests/test_trapdoor_tools.py) are the hard gates."""


def _arg(argv: Sequence[str], flag: str, default: str | None = None) -> str | None:
    if flag in argv:
        i = list(argv).index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def main(argv: list[str] | None = None) -> int:
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0

    if "--diff" in args:
        rest = [a for a in args if a != "--diff" and not a.startswith("--")]
        if len(rest) != 2:
            print("ERROR: --diff needs exactly two scorecard paths\n", file=sys.stderr)
            print(USAGE, file=sys.stderr)
            return 2
        try:
            before, after = load_scorecard(rest[0]), load_scorecard(rest[1])
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        if "--json" in args:
            print(json.dumps({"kind": "coyodex-l3-diff", "version": 1,
                              "before": before.label, "after": after.label,
                              "deltas": [d.as_json() for d in diff(before, after)]}, indent=2))
        else:
            print(format_diff(before, after))
        return 0

    positional = [a for a in args if not a.startswith("--")]
    skip = {_arg(args, "--out"), _arg(args, "--label")}
    positional = [a for a in positional if a not in skip]
    if not positional:
        print("ERROR: give a transcript path\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    src = Path(positional[0])
    if not src.is_file():
        print(f"ERROR: no transcript at {src}", file=sys.stderr)
        return 2
    card = score_transcript(src, label=_arg(args, "--label") or "",
                            map_path=_arg(args, "--map"))
    out = Path(_arg(args, "--out") or src.with_suffix(".l3-scorecard.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(card.as_json(), indent=2), encoding="utf-8")
    if "--json" in args:
        print(json.dumps(card.as_json(), indent=2))
    else:
        print(format_scorecard(card))
        print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
