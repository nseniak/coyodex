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

#: Assertion 10's proposed ceiling: how many `ls`/`find` sweeps of the fragment dir a single
#: fan-out may make before it counts as polling. The method says wait on completion notifications.
POLL_THRESHOLD = 3

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


def assert_6_grounding_recorded(turns: Sequence[Turn]) -> Assertion:
    """6 — the assembled model carries a non-empty `grounding` object.

    A monorepo build grounded 319 of 1,608 claims and reported it only in chat, where it evaporated.
    Only WRITING tools count: a skeptic prompt that discusses grounding is not a record."""
    hits: list[Evidence] = []
    for turn in turns:
        for call in turn.tool_calls:
            if call.name not in ("Write", "Edit", "NotebookEdit", "Bash"):
                continue
            blob = call.text()
            if "claims_total" in blob or "claims_challenged" in blob or "claims_grounded" in blob:
                hits.append(Evidence(turn.index, {"tool": call.name}))
                break
    observed, of = _at_least_once(len(hits))
    return Assertion(6, "grounding recorded in the model", observed, of, tuple(hits))


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


def assert_10_fragment_polling(turns: Sequence[Turn]) -> Assertion:
    """10 — `ls`/`find` polling of `build-fragments/` stays under a threshold.

    The method says wait on completion notifications, never poll: a not-ready file reads as an error
    and burns turns. Each poll is attributed to the most recent preceding fan-out, so the threshold
    is per fan-out as the design proposes. `of` is the number of fan-outs; `observed` is how many
    stayed under the ceiling."""
    fanouts = [t.index for t in turns if t.agent_calls]
    if not fanouts:
        return Assertion(10, "fragment-dir polling under threshold", 0, 0, (),
                         "no fan-out in this transcript")
    polls: dict[int, int] = {idx: 0 for idx in fanouts}
    evidence: list[Evidence] = []
    for idx, cmd in bash_commands(turns):
        if FRAGMENT_DIR not in cmd:
            continue
        if not re.search(r"\b(ls|find|stat|wc)\b", cmd):
            continue
        owner = max((f for f in fanouts if f <= idx), default=fanouts[0])
        polls[owner] += 1
        evidence.append(Evidence(idx, {"after_fanout": owner, "command": cmd[:120]}))
    under = [idx for idx, n in polls.items() if n <= POLL_THRESHOLD]
    return Assertion(10, "fragment-dir polling under threshold", len(under), len(fanouts),
                     tuple(evidence), f"threshold {POLL_THRESHOLD} poll(s) per fan-out")


#: Every assertion, in scorecard order. 11 is deliberately absent: it compares a built map against
#: the trapdoor golden map, and that golden map was assembled from an authored fragment rather than
#: produced by a live agent build — the blocker the design already names. 1-10 need a transcript and
#: nothing else, so they run against any build of any repo.
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
    assert_10_fragment_polling,
)


def score_turns(turns: Sequence[Turn], *, transcript: str = "", label: str = "",
                grouping_consistent: bool = True) -> Scorecard:
    """Every assertion over an already-read turn sequence. The seam the unit tests drive with
    synthetic turns — no file, no corpus, fully deterministic."""
    return Scorecard(transcript=transcript, turns=len(turns),
                     assertions=tuple(fn(turns) for fn in ASSERTIONS),
                     grouping_consistent=grouping_consistent, label=label)


def score_transcript(path: Path | str, *, label: str = "") -> Scorecard:
    """Read a transcript and score it."""
    p = Path(path)
    turns = read_turns(p)
    return score_turns(turns, transcript=str(p), label=label or p.stem,
                       grouping_consistent=grouping_is_consistent(p))


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

USAGE = """usage: coyodex-eval process <transcript.jsonl> [--out <scorecard.json>] [--json] [--label L]
       coyodex-eval process --diff <before.json> <after.json> [--json]

Score a build TRANSCRIPT against the L3 process assertions (1-10), or diff two scorecards.

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
    card = score_transcript(src, label=_arg(args, "--label") or "")
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
