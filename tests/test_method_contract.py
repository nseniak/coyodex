#!/usr/bin/env python3
"""L1 — the prose<->tool contract, checked statically.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_method_contract.py
    pytest tests/test_method_contract.py

**Why this layer exists.** The 894 tests that came before it all assert what the code does WHEN
CALLED. A build agent reads only `method.md` and the `method/` docs, so a command the method
never names is unreachable no matter how well it is tested — `coyodex reconcile` shipped fully
working, fully tested, and ran ZERO times across four measured builds while every one of them
hand-wrote the file it generates (one was 24 KB, 139 rules, 882 id assignments). That is a
defect no unit test can see, because nothing is wrong with the unit.

So this file checks the SEAM, not the behaviour:

  (a) every command (and `fix` verb) the CLI offers is named somewhere in the method docs
  (b) every CLI flag the method tells a build to pass is accepted by that command
  (b2) …and is actually READ — not merely parsed and thrown away — by the code path that runs
       for that command form
  (c) every advisory the validator prints names a way to record the decision, or is allowlisted,
      and every escape a message NAMES is actually read by the check that prints it
  (d) every extras heading the method tells a lead to write is read by some tool

Pure text + AST. No fixture, no LLM, ~1 second. This is the cheapest layer and it would have
caught the worst defect in the study.

**What a static layer can and cannot prove.** Every assertion here is about the SHAPE of the
code — a literal in a parser, a call in a check, a name in a doc. That is enough to catch a
seam that was never wired, and it is NOT enough to catch a seam that is wired to the wrong
thing. Where the difference matters the claim is stated narrowly in the test's own docstring
and the behavioural half is named: `tests/test_trapdoor_tools.py` runs the real tools against a
real tree and is the layer that proves the wiring WORKS. A static test that oversold itself is
the same prose-vs-reality gap this layer exists to close, so the docstrings below say only what
they check.

**History.** Three of these tests failed when the layer landed; the failures were the
deliverable. All three findings have since been fixed in the CLI, the method docs and the
validator (`coyodex dump` / `reconcile` / `fix dedup-relation` are named in the method,
`preindex --report` honours `--root`, and the unowned-entity advisory carries a real escape),
so the suite is green and each test is now a standing regression gate on the fix.
"""
from __future__ import annotations

import ast
import tempfile
import json
import re
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from coyodex import balance_lib

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS = REPO_ROOT / "tools" / "coyodex"

#: Every doc a build agent actually reads. `internal/` is explicitly NOT the method.
METHOD_DOCS: tuple[Path, ...] = (
    (REPO_ROOT / "method.md"),
    *sorted((REPO_ROOT / "method").glob("*.md")),
    (REPO_ROOT / "skill" / "coyodex" / "SKILL.md"),
)

#: command name -> the module implementing it, as `cli.py` dispatches.
COMMAND_MODULE: dict[str, str] = {
    "preindex": "preindex", "validate": "validate_model", "audit": "audit_model",
    "render": "viewer/render", "serve": "viewer/serve", "assemble": "assemble",
    "lint-fragment": "lint_fragment", "anchor-drift": "anchor_drift", "fix": "fix",
    "dump": "dump", "diff": "mapdiff", "reconcile": "reconcile_build",
    "balance": "balance",
    "finalize": "finalize", "grounding": "grounding", "record": "record",
    "scope": "scope",
}

#: The extras headings some tool actually READS (the escape tokens that silence an advisory).
#: Derived below from the source, never hard-coded into an assertion.
MACHINE_READ_HEADINGS: tuple[str, ...] = (
    "audit exceptions", "balance exceptions", "coverage exceptions",
    "accepted duplications", "entry-point coverage", "happy path coverage",
    "persistence exceptions", "unclaimed surfaces", "drift exceptions",
    "bucket vocabulary", "sweep debt",
)


# --- builders -------------------------------------------------------------------------

def make_method_text() -> str:
    """Every method doc concatenated — the whole surface a build agent can read."""
    return "\n".join(p.read_text(encoding="utf-8") for p in METHOD_DOCS if p.is_file())


def make_cli_commands() -> tuple[str, ...]:
    """The command names `coyodex --help` advertises, read from the USAGE text itself so a new
    command joins this test automatically."""
    from coyodex.cli import USAGE
    body = USAGE.split("Commands:", 1)[1].split("\nGlobal:", 1)[0]
    names: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^  ([a-z][a-z-]+)\s{2,}\S", line)
        if m:
            names.append(m.group(1))
    return tuple(names)


def make_fix_verbs() -> tuple[str, ...]:
    """The second-level verbs `coyodex fix` dispatches, read from its own verb table."""
    from coyodex.fix import _VERBS
    return tuple(sorted(_VERBS))


def make_doc_flag_pairs() -> tuple[tuple[str, str, str], ...]:
    """(command, flag, "doc:line") for every flag the method tells a build to PASS.

    Attribution is span-scoped, never proximity-scoped: a flag counts for a command only when
    both appear inside the SAME code span (a fenced block or one inline-code run). Proximity
    attribution mis-assigns `git status --porcelain` to whatever coyodex command was mentioned
    last, which is how a contract test starts reporting noise and stops being read."""
    cmd_pat = re.compile(r"coyodex\s+(" + "|".join(map(re.escape, COMMAND_MODULE)) + r")\b")
    span_pat = re.compile(r"```[a-z]*\n(.*?)```|`([^`]+)`", re.S)
    pairs: list[tuple[str, str, str]] = []
    for doc in METHOD_DOCS:
        if not doc.is_file():
            continue
        text = doc.read_text(encoding="utf-8")
        rel = doc.relative_to(REPO_ROOT).as_posix()
        for span in span_pat.finditer(text):
            body = (span.group(1) or span.group(2) or "").replace("\n", " ")
            line = text.count("\n", 0, span.start()) + 1
            hits = list(cmd_pat.finditer(body))
            for i, hit in enumerate(hits):
                tail = body[hit.end():hits[i + 1].start() if i + 1 < len(hits) else len(body)]
                for flag in re.findall(r"--[a-z][a-z0-9-]*", tail):
                    pairs.append((hit.group(1), flag, f"{rel}:{line}"))
    return tuple(sorted(set(pairs)))


def make_module_source(command: str) -> str:
    return (TOOLS / f"{COMMAND_MODULE[command]}.py").read_text(encoding="utf-8")


def make_code_flag_literals(command: str) -> frozenset[str]:
    """Every `--flag` literal that appears in EXECUTABLE code in a command's module.

    Deliberately not a text search over the file: every command module carries a `USAGE` string
    that spells out its whole flag vocabulary, so "the flag appears in the source" is satisfied by
    the help text alone — a flag that was documented and then never wired would pass. Counting
    only literals inside a function body is what makes the check about the parser."""
    src = make_module_source(command)
    found: set[str] = set()
    for fn in ast.walk(ast.parse(src)):
        if not isinstance(fn, ast.FunctionDef):
            continue
        found.update(n.value for n in ast.walk(fn)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)
                     and n.value.startswith("--"))
    return frozenset(found)


# --- the tools' own shape, shared by the flag audit and the escape audit ----------------

_BLOCKS = (ast.If, ast.For, ast.While, ast.With, ast.Try)

#: The one function that is a 200-line ORCHESTRATOR rather than a focused check. Escape wiring
#: found anywhere inside it belongs to some other rule, so an advisory it prints is credited only
#: with the wiring in its own enclosing block. Without this, deleting the escape a message
#: advertises would still "pass" against an unrelated escape 200 lines away.
ORCHESTRATOR = "validate_model"


@dataclass(frozen=True)
class ToolFunction:
    """One function defined in the tools: its source and the names it calls."""

    name: str
    src: str
    calls: frozenset[str]


def _src_of(node: ast.AST, src_lines: list[str]) -> str:
    start = getattr(node, "lineno", 0)
    end = getattr(node, "end_lineno", None) or start
    return "\n".join(src_lines[start - 1:end])


def _called_names(node: ast.AST) -> frozenset[str]:
    """Every name invoked under `node` — `f(...)` as `f`, `x.f(...)` as `f`."""
    names: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                names.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                names.add(n.func.attr)
    return frozenset(names)


def make_tool_functions(*files: str) -> dict[str, ToolFunction]:
    """name -> the function's source and call targets, across the named tool modules.

    Keyed by bare name because the checks below follow calls the way a reader does (`_exceptions(m)`
    reads the same whether it was imported or defined here). The tools define no two functions
    under one name; a collision keeps the first and is a fixture bug, not a silent merge."""
    out: dict[str, ToolFunction] = {}
    for f in files:
        src = (TOOLS / f).read_text(encoding="utf-8")
        lines = src.splitlines()
        for fn in ast.walk(ast.parse(src)):
            if isinstance(fn, ast.FunctionDef) and fn.name not in out:
                out[fn.name] = ToolFunction(name=fn.name, src=_src_of(fn, lines),
                                            calls=_called_names(fn))
    return out


def make_dispatch_tables(src: str) -> dict[str, frozenset[str]]:
    """table name -> the tool functions it names as values.

    A producer reached through a module-level DISPATCH TABLE is not an `ast.Call` anywhere, so the
    call graph alone cannot see it. `_RUNS_IN_FAMILY` is the live case: it pairs each `runs-in`
    producer with a label, and one wrapper walks the table and applies the escape once — which is
    precisely the fix that made the suppression countable. Without this, every producer in such a
    table reads as "advertises a heading nothing reads"."""
    out: dict[str, set[str]] = {}
    for node in ast.parse(src).body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if not names:
            continue
        referenced = {n.id for n in ast.walk(node.value) if isinstance(n, ast.Name)}
        for name in names:
            out.setdefault(name, set()).update(referenced)
    return {k: frozenset(v) for k, v in out.items() if v}


def make_tool_callers(fns: dict[str, ToolFunction], tables: dict[str, frozenset[str]] | None = None
                      ) -> dict[str, frozenset[str]]:
    """callee name -> the functions that call it. The inverse of the call table above.

    A function that walks a dispatch table counts as a caller of every tool function that table
    names — otherwise table-driven wiring reads as no wiring at all."""
    out: dict[str, set[str]] = {}
    for fn in fns.values():
        for callee in fn.calls:
            out.setdefault(callee, set()).add(fn.name)
        for table, members in (tables or {}).items():
            if re.search(rf"\b{re.escape(table)}\b", fn.src):
                for member in members & fns.keys():
                    out.setdefault(member, set()).add(fn.name)
    return {k: frozenset(v) for k, v in out.items()}


def _render_str(node: ast.AST) -> str:
    """The literal skeleton of a message expression — f-string holes become `{}`."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(_render_str(v) for v in node.values)
    if isinstance(node, ast.FormattedValue):
        return "{}"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _render_str(node.left) + _render_str(node.right)
    return ""


#: Names whose presence in a check's own source means SOME escape mechanism is wired to it,
#: even when the message text never mentions one.
_ESCAPE_MACHINERY = ("_exceptions(", "_recorded_ids(", "cov_dirs", "deployment_linked",
                     "_deployment_quality_warnings")


@dataclass(frozen=True)
class AdvisorySite:
    """One advisory the validator can PRINT, with everything the audits below need."""

    line: int
    function: str
    message: str
    #: some escape machinery is present in the check's own source (see `_ESCAPE_MACHINERY`).
    wired: bool
    #: The region that must hold the wiring for an escape this message NAMES. For a focused check
    #: that is the whole function; inside the ORCHESTRATOR it is the advisory's own enclosing
    #: block, so an unrelated escape elsewhere in the orchestrator cannot stand in for it.
    scope_src: str
    #: The names called inside `scope_src` — the roots of the transitive "does this read the
    #: heading?" walk.
    scope_calls: frozenset[str]


def make_advisory_sites() -> tuple[AdvisorySite, ...]:
    """Every advisory the validator can PRINT.

    An advisory is a string appended to a warnings list, or returned as the first element of a
    warning function's literal list. Read by AST rather than by regex so a reformatted call
    still counts. `wired` separates two different failures: a check with NO escape at all, and a
    check that HAS one whose message never tells the reader about it."""
    src = (TOOLS / "validate_model.py").read_text(encoding="utf-8")
    src_lines = src.splitlines()
    sites: list[AdvisorySite] = []
    for fn in ast.walk(ast.parse(src)):
        if not isinstance(fn, ast.FunctionDef):
            continue
        fn_src = _src_of(fn, src_lines)
        # `validate_model` is the 200-line ORCHESTRATOR, not a check: escape machinery anywhere
        # inside it belongs to some other rule, so crediting its warnings with it would label a
        # real gap as a wording problem. Every focused check is its own function.
        wired = fn.name != ORCHESTRATOR and any(tok in fn_src for tok in _ESCAPE_MACHINERY)
        for node in ast.walk(fn):
            msg = ""
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in ("append", "extend")
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in ("warnings", "warns", "out") and node.args):
                arg = node.args[0]
                msg = _render_str(arg)
                if not msg and isinstance(arg, ast.List) and arg.elts:
                    msg = _render_str(arg.elts[0])
            elif (isinstance(node, ast.Return) and fn.name.endswith("_warnings")
                  and isinstance(node.value, ast.List) and node.value.elts):
                msg = _render_str(node.value.elts[0])
            if len(msg) > 25:
                scope = _escape_scope(fn, node, src_lines)
                sites.append(AdvisorySite(line=getattr(node, "lineno", fn.lineno),
                                          function=fn.name, message=msg, wired=wired,
                                          scope_src=scope[0], scope_calls=scope[1]))
    return tuple(sorted(set(sites), key=lambda s: (s.line, s.function, s.message)))


def _escape_scope(fn: ast.FunctionDef, node: ast.AST,
                  src_lines: list[str]) -> tuple[str, frozenset[str]]:
    """The region an escape named by `node`'s message has to be wired in.

    A focused check is small enough that the whole function is the honest scope. The ORCHESTRATOR
    is not: it prints a handful of advisories of its own and also reads escapes on behalf of other
    rules, so an advisory inside it is scoped to its own top-level block. That is the difference
    between "this heading is read SOMEWHERE in a 200-line function" (which deleting the wiring
    would survive) and "this heading is read by the code that decides THIS advisory"."""
    if fn.name != ORCHESTRATOR:
        return _src_of(fn, src_lines), _called_names(fn)
    line = getattr(node, "lineno", 0)
    for stmt in fn.body:
        if isinstance(stmt, _BLOCKS) and stmt.lineno <= line <= (stmt.end_lineno or stmt.lineno):
            return _src_of(stmt, src_lines), _called_names(stmt)
    return _src_of(fn, src_lines), _called_names(fn)


def _function_node(module: str, function: str) -> ast.FunctionDef:
    src = (TOOLS / f"{module}.py").read_text(encoding="utf-8")
    for fn in ast.walk(ast.parse(src)):
        if isinstance(fn, ast.FunctionDef) and fn.name == function:
            return fn
    raise AssertionError(f"{module}.py has no function {function}()")


def _loaded_names(fn: ast.FunctionDef) -> frozenset[str]:
    """Every name READ inside `fn` — assignment targets do not count."""
    return frozenset(n.id for n in ast.walk(fn)
                     if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load))


def _flag_sites(fn: ast.FunctionDef) -> tuple[tuple[str, bool], ...]:
    """(flag, the value this occurrence produces is consumed) for every `--flag` literal in `fn`.

    coyodex parses argv by hand (no argparse anywhere — see `cli.py`'s dependency firewall), so
    "the parser accepts it" is "the flag literal is in the code that runs". The literal alone is
    not enough: `_ignored_root = _arg(argv, "--root")` mentions the flag and throws the answer
    away, which is EXACTLY the measured defect. So an occurrence sitting in an assignment whose
    targets are plain names that the function never reads back is marked discarded."""
    live = _loaded_names(fn)
    dead_lines: set[int] = set()
    for stmt in ast.walk(fn):
        targets: list[ast.expr] = []
        if isinstance(stmt, ast.Assign):
            targets = list(stmt.targets)
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            targets = [stmt.target]
        else:
            continue
        if targets and all(isinstance(t, ast.Name) and t.id not in live for t in targets):
            value = stmt.value
            if value is not None:
                dead_lines.update(range(value.lineno, (value.end_lineno or value.lineno) + 1))
    sites: list[tuple[str, bool]] = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith("--"):
            sites.append((n.value, n.lineno not in dead_lines))
    return tuple(sites)


def make_flags_read_by(module: str, function: str) -> frozenset[str]:
    """Every `--flag` one function both names AND consumes.

    Scoping to ONE function is what makes the difference between accepted-and-used and
    accepted-and-ignored visible; scoping to a CONSUMED occurrence is what stops the original
    defect from passing its own regression test."""
    sites = _flag_sites(_function_node(module, function))
    return frozenset(flag for flag, used in sites if used)


def make_flags_discarded_by(module: str, function: str) -> frozenset[str]:
    """Flags this function parses and then throws away — named nowhere else in it. A strictly
    worse state than not accepting the flag: the code LOOKS like it honours it."""
    sites = _flag_sites(_function_node(module, function))
    return frozenset(flag for flag, _ in sites) - make_flags_read_by(module, function)


# --- (a) every command the CLI offers is reachable from the method --------------------

def test_every_cli_command_is_named_in_the_method():
    """A command the method never names cannot be reached: the build agent reads the method,
    not `--help`. Failed when this layer landed, on `dump` and `reconcile`; both are named in the
    method now, so this is the standing gate on the next command that forgets to be."""
    text = make_method_text()
    missing = [c for c in make_cli_commands() if f"coyodex {c}" not in text]
    assert not missing, (
        "CLI commands named nowhere in the method docs, so no build can reach them: "
        + ", ".join(missing)
        + " — every one of these is a working, tested command that a build agent has no way to "
          "learn about. `coyodex reconcile` is the measured case: four builds hand-wrote the "
          "file it generates instead of running it.")


def test_every_fix_verb_is_named_in_the_method():
    """`coyodex fix` dispatches three verbs and the method must name every one. Failed when this
    layer landed, on `dedup-relation` — which resolves a BLOCKING validate error, so a lead who
    hit that error had no documented way out and hand-edited the model instead. Now documented."""
    text = make_method_text()
    missing = [v for v in make_fix_verbs() if v not in text]
    assert not missing, (
        "`coyodex fix` verbs named nowhere in the method docs: " + ", ".join(missing))


# --- (b) every flag the method tells a build to pass is accepted ----------------------

def test_every_flag_the_method_prescribes_is_accepted_by_that_command():
    """The doc must not tell a build to pass a flag the command rejects. Passes today: the flag
    vocabulary in the method is in sync with the parsers. Kept as a standing gate — it is the
    cheap half of the contract, and it is the half that silently rots when a flag is renamed.

    The flag must appear in EXECUTABLE code, not merely somewhere in the file. This used to be a
    text search for the quoted literal anywhere in the module, which a comment or a docstring
    quoting the flag would have answered just as well as a parser. No module does that today, so
    this is a tightening with no finding behind it — taken because it is the same weakness as the
    mode-flag test below (a string standing in for behaviour), one step earlier in the chain."""
    bad: list[str] = []
    for cmd, flag, loc in make_doc_flag_pairs():
        if flag not in make_code_flag_literals(cmd):
            bad.append(f"{loc}: `coyodex {cmd} {flag}` — no executable code in "
                       f"{COMMAND_MODULE[cmd]}.py names it (a comment, a docstring or the USAGE "
                       "text does not count)")
    assert not bad, "Flags the method prescribes that the command does not accept:\n  " + "\n  ".join(bad)


def test_a_mode_flag_does_not_silently_swallow_the_flags_its_mode_ignores():
    """The other half of (b), and the one that bites: a flag can be *accepted* by the command
    and *ignored* by the mode.

    `coyodex preindex --report --root <other-repo>` is the measured case. `preindex.py` reads
    `--root` in `main()`, so the flag-existence check above passes — but `--report` branched into
    `report()`, which read only `--in`, so `--root` was silently dropped and the CWD's pre-index
    was reported instead of the named repo's. Silently using the wrong repo is worse than
    erroring: the output looks exactly right.

    FIXED, and this pins the fix. Two shapes are caught, and both are the original defect:
      ABSENT    — the mode's function never names the flag at all.
      DISCARDED — it parses the flag and throws the value away (`_ignored = _arg(argv, "--root")`).
                  The first version of this test looked only for the literal, so re-introducing
                  the measured bug in exactly this shape passed it. It does not any more.

    WHAT THIS DOES NOT PROVE. It is a static check: it proves the value is consumed, never that it
    is consumed CORRECTLY. `root_arg` read and then used to build the wrong path would pass here.
    The behavioural half is
    `tests/test_trapdoor_tools.py::test_preindex_report_honours_root_over_the_cwd_repo`, which
    runs the command against two real repos and reads the output."""
    main_flags = make_flags_read_by("preindex", "main")
    report_flags = make_flags_read_by("preindex", "report")
    discarded = make_flags_discarded_by("preindex", "report")
    # `--report` itself and the help flags are the mode switch, not mode input.
    switches = {"--report", "--help", "--in", "--depth", "--top"}
    ignored = sorted((main_flags - report_flags) - switches)
    assert not ignored, (
        "`coyodex preindex --report` accepts these flags and silently ignores them: "
        + ", ".join(f"{f} (parsed, then discarded)" if f in discarded else f"{f} (never read)"
                    for f in ignored)
        + " — `--root` is the one that matters: if --report reads only `--in` (a CWD-relative "
          "path), `preindex --report --root <other-repo>` reports the CURRENT repo's pre-index "
          "under the other repo's name. Either make report() honour --root, or reject the flag; "
          "accepting-and-ignoring is the failure mode with no visible symptom.")


# --- (c) every advisory offers a way to record the decision ---------------------------

#: Advisory message prefixes that legitimately need NO recordable escape, each with the reason.
#: An entry here is a claim: "this is always fixable at the point it fires, so an operator never
#: has to live with it." Adding a line to this list is a design decision, not a formality.
KNOWN_NO_ESCAPE: dict[str, str] = {
    # A META-advisory: its subject is a recorded exception that silences nothing, so "record an
    # exception to silence it" is circular — the remedy is to delete the dead line or fix the key.
    # Unsilenceable for the same reason the suppression-COUNT line is: a silence you cannot see is
    # indistinguishable from having no findings.
    "recorded `runs_in` exception(s) currently suppressing nothing":
        "the finding IS a dead record; recording another one cannot answer it",
    # The same META shape: both of these have a RECORD as their subject. Recording an exception to
    # silence a complaint about the shape of your records is circular; the remedy is to rewrite the
    # lines the finding names (collapse the repeats onto one line / fix the malformed key list).
    "'{}' repeats one reason across several records":
        "the finding IS the record's shape; the fix is to write the reason once with every id on it",
    "'{}' has a line that tries to be a record and adjudicates NOTHING":
        "a line that records nothing cannot be answered by recording another one; fix the key list",
    # Row-local well-formedness: the fix is mechanical and local, there is no judgement to record.
    "{}: `no_call_site` is set but a `where` is present":
        "contradictory row; drop one field",
    "{} → {}: `no_call_site` is set but a `Where` is present":
        "contradictory row; drop one field",
    "{} → {}: the '{}' edge is declared {} times":
        "one edge, one primary call site; merge them",
    "{}: '{}' does not resolve to a":
        "a nonexistent path is never a judgement call",
    "{}: '{}' cites a line the file does not have":
        "the file is shorter than the citation, so the citation cannot be true of it at this commit "
        "— arithmetic, not judgement. Its sibling above ('does not resolve') is unrecordable for the "
        "same reason: both are BLOCKING problems from the existence gate, not advisories to live with",
    "{}: '{}' points at {} — anchor the operative statement":
        "the anchor moves to the acting line; nothing to record",
    "{} states: {} of {} state name(s) do not appear in the cited source":
        "either the names or the citation is wrong; both are fixable",
    "{}: state(s) with no transition in or out":
        "a typo'd state name or a missing transition; both fixable",
    "{} state machine(s) cite no `source`":
        "cite the declaring line, or drop the machine — the method forbids an uncited one",
    "{} ({}) is {}ed by {} ({}), which runs in {}":
        "a hard invariant of the code: a base cannot be absent from a process loading its subclass. "
        "Re-examined when the check grew its wholly-untagged-base arm: still no judgement. The rule "
        "only fires once the SUBCLASS is already placed, so the map itself determines the base's "
        "correct tag — the remedy is to copy it, not to decide anything. Escaping it via `runs-in` "
        "would let a map hide the exact defect it exists for (a missing base tag drew eight false "
        "process arrows on a live map)",
    # Row-completeness on a T4 row: an entry point runs INSIDE some component the map already
    # traces, so the owning C id exists to be named. Until it is, the row is invisible to the
    # entry-surface coverage check — an unrecordable state, not a recordable decision.
    "entry_points[{}] [{}] {}: externally activated but owned by no component":
        "name the owning C id; the row is incomplete, not adjudicable",
    # An element with nothing behind it — the same class as 'Subsystems with no members' below:
    # back it or delete it, and DELETING IT is the record.
    "{} ({}) has no T6 flow":
        "trace it or drop it — an untraced use case is a claim with nothing behind it",
    "{} ({}) drives no use case and appears in no flow":
        "trace it or drop it — a role nothing exercises is a claim with nothing behind it",
    # The messaging twin of the allowlisted `unbacked_entity_steps` rule below: the component IS a
    # publisher/consumer, so the C→broker edge is a fact of the code, always authorable.
    "{}: {}(s) {} carry no backbone edge to {}":
        "author the C→broker edge; a recorded participant provably talks to the broker",
    # The honesty record. Both are FACTS about how much of the claim surface was challenged, and an
    # escape would be a switch for making an unverified map look verified — the one thing the
    # grounding feature exists to prevent. Authoring the `grounding` block is the only answer, and
    # it is a structured one (like `deployment_linked`), not an extras token.
    "No `grounding` record":
        "record `grounding` (the block itself IS the escape); an extras token would defeat the feature",
    "Grounding is partial":
        "a measured share of the claim surface — ground more claims; nothing else can honestly quiet it",
    # Closed two-word vocabulary: the fix is to write `verified` or `inferred`, never a judgement.
    "{} row(s) carry a `confidence` outside the vocabulary":
        "use one of the two words the template asks for; there is nothing to adjudicate",
    # Vocabulary nudges: reuse the seed spelling or mint deliberately; the map records the choice.
    "{} bucket '{}' is long (>40 chars)": "shorten the label",
    "Library bucket '{}' is minted (not a seed)": "the minted name IS the record",
    "External bucket '{}' is minted (not a seed)": "the minted name IS the record",
    "The '{}' catch-all among {} holds {} deps": "splitting the bucket is the fix",
    "Many purpose buckets among {}": "merging near-duplicates is the fix",
    "entry-point kind '{}' ({} row(s)) is a drift spelling": "write the canonical spelling",
    "entry-point kind(s) minted (not a seed)": "the minted kind IS the record",
    "{} C→D edge(s) name no role (generic verb)": "a role-revealing verb is always available",
    # Cadence / actor / flow shape: each names the concrete edit that clears it.
    "entry_points[{} {}] records cadence '{}' but is externally activated": "drop the cadence",
    "entry_points[{} {}] cites a `cadence_source` but records no `cadence`": "record the cadence",
    "{} entry-point cadence value(s) cite no `cadence_source`": "anchor the declaring line",
    "{} ({}) mixes a human actor [{}] with a service actor [{}]": "the service is the delivery mechanism; drop it",
    "{} ({}) is referenced {} time(s)": "advisory on the fragment channel by design; inline or leave",
    "{}: broker {} ({}) classifies as '{}'": "re-classify the dep or re-point the channel",
    "Domain card {}: relation '{} … {}' is not backed by a field": "mark the FK marker",
    "Domain card {}: relation '{} … {}' is field-less but its note": "mark the FK marker",
    "{} extra.{}: looks like deployment/config info": "move the row to its real array",
    # Grouping hygiene: pure regrouping, free and view-only by the method's own contract.
    "Groups whose only child is another group of the same kind": "inline the wrapper level",
    "Subsystems with no members": "delete the empty group or give it members",
    "Subdomains with no entities": "delete the empty group or give it members",
    "Entities with no SUBDOMAIN (ungrouped / top-level)": "assign the subdomain",
    # These carry a STRUCTURED escape instead of an extras token — a field on the row, which is
    # a better record than a heading because it travels with the thing it describes.
    "External deps with no incoming edge": "`deployment_linked: true` on the dep is the escape",
    "Deps marked `deployment_linked` but which are a code call target": "drop the marker",
    "{} deployment advisory/advisories suppressed by recorded scoped exception(s)":
        "this IS the escape being reported; it must never be silenceable itself",
    "recorded `runs_in` exception key(s) no check reads":
        "the opposite of an advisory needing an escape — it reports that the escape the operator "
        "wrote is a typo, and names the five that work",
    "a bare `runs-in` exception is recorded and silences NOTHING":
        "the opposite of an advisory needing an escape — it exists to say the escape the operator "
        "wrote does not work, and names the five scoped lines that do",
    "{} store-hygiene advisory/advisories suppressed by the recorded `store` exception":
        "same shape as the `runs-in` count above — a suppression report that can itself be "
        "suppressed reports nothing",
    # Deliberately un-escapable: the whole point is that a suppressed count stays visible.
    "{} {}: {} → {} claims entity use the backbone doesn't": "author the edge; the safety net derives it",
}


def _has_escape(message: str) -> bool:
    low = message.lower()
    return (any(h in low for h in MACHINE_READ_HEADINGS)
            or "record the literal" in low or "extras heading" in low)


def _allowlisted(message: str) -> bool:
    return any(message.startswith(prefix) for prefix in KNOWN_NO_ESCAPE)


def test_every_validator_advisory_names_a_way_to_record_the_decision():
    """An advisory an operator decides to LIVE WITH must be recordable, or it re-fires at every
    validate forever and gets waved through — the "advisory waved through" failure the method
    names in its own words.

    Failed when this layer landed. The headline was trap P1 — "Entities with no owning component"
    — where three separate live leads independently invented a `Persistence exceptions` heading
    that existed but was read only by the persistence-COVERAGE rule (which filters `Cn` ids) and
    silenced nothing here. Every residue has since been answered or allowlisted.

    SCOPE. This reads the MESSAGE TEXT only: it proves an operator is TOLD where to record the
    decision. Whether the escape the message names is wired to anything is the next test's job,
    and whether recording it actually silences the advisory is proven at runtime by
    `tests/test_trapdoor_tools.py` (traps P1 and P2) against the real fixture map.

    The report separates two failure shapes, because they need different fixes:
      NO-ESCAPE   — nothing anywhere can silence it; the fix is to add an escape token.
      UNNAMED     — an escape IS wired to the check, but its message never says so; the fix is
                    one sentence in the message. Cheap, and the difference between an operator
                    recording a decision and an operator ignoring a line forever."""
    orphans = [s for s in make_advisory_sites()
               if not _has_escape(s.message) and not _allowlisted(s.message)]
    detail = "\n  ".join(
        f"{'UNNAMED  ' if s.wired else 'NO-ESCAPE'} validate_model.py:{s.line} ({s.function}): "
        f"{s.message[:105]}" for s in orphans)
    assert not orphans, (
        f"{len(orphans)} validator advisory/advisories offer no recordable escape in their text "
        "and are not allowlisted — an operator who decides the finding is acceptable has nowhere "
        "to say so:\n  " + detail)


def _reads_heading(src: str, heading: str) -> bool:
    """Does this source READ the extras heading — not merely mention it in a message?

    A read is a call into the readers the tools own (`_recorded_ids` / `extras_bodies` /
    `_recorded_line_keys`, and the shared `records` module they now all delegate to) with the
    heading as its literal argument. 'Balance exceptions' is also reachable through `balance_lib`'s
    own `_exceptions()`, which carries the heading in a module constant.

    `_recorded_line_keys` joined the list when the duplicate-security and bucket-vocabulary escapes
    moved to exact prefix-and-colon keying: it wraps `extras_bodies` and takes the heading as a
    PARAMETER, so neither the direct pattern nor the transitive walk could see the literal, which
    sits at the call site. `records.recorded_keys` / `records.lines` joined it when the four
    per-family line parsers were folded into one shared reader."""
    reader = re.compile(r"(?:_recorded_ids|extras_bodies|_recorded_line_keys"
                        r"|records\.recorded_keys|records\.lines)\(\s*\w+\s*,\s*[\"']"
                        + re.escape(heading) + r"[\"']", re.I)
    if reader.search(src):
        return True
    return heading == "balance exceptions" and "_exceptions(" in src


def _reads_heading_via_calls(names: frozenset[str], heading: str,
                             fns: dict[str, ToolFunction], seen: set[str]) -> bool:
    """The same question, followed through the tools' own calls — a check that delegates its
    filtering to a helper (`unexplained_persistence_pairs`) is wired just as truly as one that
    inlines it."""
    for name in sorted(names):
        fn = fns.get(name)
        if fn is None or name in seen:
            continue
        seen.add(name)
        if _reads_heading(fn.src, heading) or _reads_heading_via_calls(fn.calls, heading, fns, seen):
            return True
    return False


def _passes_a_reader_result_into(caller: ToolFunction, callee: str, heading: str,
                                 fns: dict[str, ToolFunction]) -> bool:
    """Does `caller` read the heading and hand the RESULT to `callee` as an argument?

    The escape for a check that takes its exceptions as a parameter lives at the call site, not
    inside the check — `validate_model` reads the recorded 'Coverage exceptions' dirs and passes
    them into `check_domain_coverage_model`. Matching on the argument NAME (bound from a reader)
    keeps that legitimate shape from reading as a gap."""
    tree = ast.parse(textwrap.dedent(caller.src))
    passed: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == callee:
            passed.update(a.id for a in node.args if isinstance(a, ast.Name))
            passed.update(k.value.id for k in node.keywords if isinstance(k.value, ast.Name))
    if not passed:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or node.value is None:
            continue
        if not any(isinstance(t, ast.Name) and t.id in passed for t in node.targets):
            continue
        if (_reads_heading(ast.unparse(node.value), heading)
                or _reads_heading_via_calls(_called_names(node.value), heading, fns, set())):
            return True
    return False


def _escape_is_wired(site: AdvisorySite, heading: str, fns: dict[str, ToolFunction],
                     callers: dict[str, frozenset[str]]) -> bool:
    if _reads_heading(site.scope_src, heading):
        return True
    if _reads_heading_via_calls(site.scope_calls, heading, fns, set()):
        return True
    # A wrapper that applies the escape to this check's OUTPUT, or a caller that supplies it as
    # input. `_deployment_quality_warnings` is the first shape (it collapses its `_raw` twin's
    # findings once `runs-in` is recorded); the orchestrator passing `cov_dirs` is the second.
    for name in sorted(callers.get(site.function, frozenset())):
        caller = fns.get(name)
        if caller is None:
            continue
        if name != ORCHESTRATOR and _reads_heading(caller.src, heading):
            return True
        if _passes_a_reader_result_into(caller, site.function, heading, fns):
            return True
    return False


def test_every_advertised_escape_is_wired_to_the_check_that_prints_it():
    """An advisory whose message NAMES an extras heading is making a promise: record this and I
    will go quiet. Nothing generic used to hold that promise to the code — the message text and
    the wiring were two independent facts, and the check above only ever read the text. Deleting
    the `_recorded_ids(m, "persistence exceptions", ("E",))` line behind the unowned-entity
    advisory, while leaving the sentence that advertises it, passed the whole suite.

    This closes it generically: for every advisory that names a heading, the code that DECIDES
    that advisory must actually read it — directly, through a helper it calls, through the
    wrapper that filters its output, or from a caller that hands it the recorded ids. A new
    advisory that advertises an escape it does not have fails here on the day it is written.

    SCOPE. Static: it proves the reader is called, not that the answer changes. The behavioural
    proof for the two measured cases is `tests/test_trapdoor_tools.py` traps P1 and P2, which
    record the heading on a real map and assert the advisory actually goes quiet."""
    fns = make_tool_functions("validate_model.py", "balance_lib.py")
    tables: dict[str, frozenset[str]] = {}
    for mod in ("validate_model.py", "balance_lib.py"):
        tables.update(make_dispatch_tables((TOOLS / mod).read_text(encoding="utf-8")))
    callers = make_tool_callers(fns, tables)
    gaps: list[str] = []
    for site in make_advisory_sites():
        low = site.message.lower()
        for heading in MACHINE_READ_HEADINGS:
            if heading in low and not _escape_is_wired(site, heading, fns, callers):
                gaps.append(f"validate_model.py:{site.line} ({site.function}) tells the operator "
                            f"to record '{heading}' — nothing in the code that decides this "
                            f"advisory reads that heading: {site.message[:90]}")
    assert not gaps, (
        f"{len(gaps)} advisory/advisories advertise an extras heading that does not silence "
        "them — prose promising a tool that is not there, which is the exact class this layer "
        "exists to catch:\n  " + "\n  ".join(gaps))


def test_the_no_escape_allowlist_has_no_dead_entries():
    """An allowlist entry that matches nothing is a claim about code that no longer exists —
    it hides the next advisory that grows into that shape. This one PASSES today and is the
    guard that keeps the list above honest."""
    messages = [s.message for s in make_advisory_sites()]
    dead = [p for p in KNOWN_NO_ESCAPE if not any(m.startswith(p) for m in messages)]
    assert not dead, "KNOWN_NO_ESCAPE entries matching no advisory today:\n  " + "\n  ".join(dead)


# --- (d) every heading the method prescribes is read by a tool ------------------------

def make_documented_headings() -> tuple[str, ...]:
    """Extras headings the method tells a lead to WRITE, read out of the docs' own quoting
    convention (a quoted Title Case phrase followed by the words `extras heading`)."""
    # Collapse ALL whitespace first: the docs wrap mid-phrase, and a heading read as
    # "balance   exceptions" would fail against a tool that reads "balance exceptions" —
    # a false finding, which is the one thing a contract test must never produce.
    text = re.sub(r"\s+", " ", make_method_text())
    pat = re.compile(r"[\"'“]([A-Z][A-Za-z -]{3,30})[\"'”]\*{0,2} extras heading")
    found = {" ".join(m.group(1).split()).lower() for m in pat.finditer(text)}
    return tuple(sorted(found))


def test_every_extras_heading_the_method_prescribes_is_read_by_a_tool():
    """A heading a lead is told to write but nothing reads is prose that silences nothing — the
    same class as an unreachable command, one level down. PASSES today: all seven documented
    headings are read by `validate_model.py`."""
    # Both files: `validate_model` reads five headings by literal, and reaches 'Balance
    # exceptions' through `balance_lib`'s own constant.
    src = "\n".join((TOOLS / f).read_text(encoding="utf-8")
                    for f in ("validate_model.py", "balance_lib.py")).lower()
    unread = [h for h in make_documented_headings() if f'"{h}"' not in src]
    assert not unread, (
        "Extras headings the method tells a lead to write that NO tool reads: "
        + ", ".join(unread))


def test_every_machine_read_heading_is_documented_in_the_method():
    """The converse: a heading the validator honours but the method never names is an escape
    nobody can use. PASSES today."""
    text = make_method_text().lower()
    undocumented = [h for h in MACHINE_READ_HEADINGS if h not in text]
    assert not undocumented, (
        "Extras headings the validator reads but the method never names: " + ", ".join(undocumented))


def test_the_machine_read_heading_list_matches_the_validator():
    """MACHINE_READ_HEADINGS is used by the escape-token audit above, so it must not drift from
    the source. Re-derived here from the tools' own call sites — including `balance_lib`, which
    owns the 'Balance exceptions' constant that `validate_model` reaches through a helper, and
    `audit_model`, which owns 'Audit exceptions', and `anchor_drift`, which owns 'Drift exceptions'.
    `audit` read no extras heading at all until that one landed, so every one of its six advisory
    families was permanently unanswerable; a file missing from this list is a family whose escape
    nothing here audits."""
    src = "\n".join((TOOLS / f).read_text(encoding="utf-8")
                    for f in ("validate_model.py", "balance_lib.py", "audit_model.py",
                              "anchor_drift.py"))
    # Case-folded: `extras_bodies` matches headings case-insensitively, so a constant written in
    # title case ("Audit exceptions") and a call-site literal in lower case name the same heading.
    found = {h.lower() for h in
             re.findall(r'(?:extras_bodies\(m,|_recorded_ids\(m,|_recorded_line_keys\(m,'
                        r'|records\.recorded_keys\(m,|records\.lines\(m,)'
                        r'\s*"([^"]+)"', src)}
    found |= {h.lower() for h in re.findall(r'_EXCEPTIONS_HEADING\s*=\s*"([^"]+)"', src)}
    assert found == set(MACHINE_READ_HEADINGS), (
        f"MACHINE_READ_HEADINGS is stale: the tools read {sorted(found)}")


def _main() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}\n  {exc}\n")
    print(f"{len(fns) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())


def test_every_advertised_command_has_a_module_in_the_flag_audit_table():
    """COMMAND_MODULE parity with `coyodex --help`.

    `finalize` shipped absent from this table, so the flag audit below silently skipped the two flags
    method.md prescribes for it. A missing row does not fail anything — it just stops auditing — which
    is the quietest way for this layer to lose coverage."""
    advertised = set(make_cli_commands())
    missing = sorted(advertised - set(COMMAND_MODULE))
    assert not missing, f"command(s) advertised by --help but absent from COMMAND_MODULE: {missing}"


def make_prescribed_balance_literals() -> tuple[str, ...]:
    """Every literal the method tells a lead to record under a 'Balance exceptions' heading.

    Read out of the prose, so a new instruction joins this audit automatically."""
    text = make_method_text()
    near = re.compile(r"balance exceptions", re.IGNORECASE)
    # Two shapes the method actually uses, and the first version of this test caught only one — so it
    # did not detect `security-granularity`, the literal it was written for. That is the same
    # near-vacuous-test failure this layer keeps finding elsewhere.
    #   (a) "the literal `runs-in`" / "record the literal `store`"  — a silencing escape
    #   (b) "`security-granularity: <value>`"                        — a declaration
    escape_form = re.compile(r"literal\s+\*{0,2}`([a-z][a-z/-]+)`", re.IGNORECASE)
    # The declaration form requires a HYPHEN: every literal in this vocabulary is hyphenated
    # (`security-granularity`, `channel-ends`, `entity-flows`, `runs-in`), while the un-hyphenated
    # backtick-plus-colon hits nearby are field names and prose (`dep:`, `path:`, `why:`, `step:`).
    declare_form = re.compile(r"`([a-z]+(?:[-/][a-z]+)+)\s*:")
    found: set[str] = set()
    for para in re.split(r"\n\s*\n", text):
        if not near.search(para):
            continue
        found |= set(escape_form.findall(para))
        found |= set(declare_form.findall(para))
    return tuple(sorted(found))


def test_every_balance_exceptions_literal_the_method_prescribes_is_read_by_a_tool():
    """The heading-level twin of this already exists; this is the LITERAL level, and it was missing.

    `security-granularity` shipped as the first literal the method told a build to record under a
    machine-read heading that no tool read — so a build would have written a line nothing consumed,
    and a typo in it would have been undetectable. That is the `coyodex reconcile` failure class (a
    working, tested, unreachable thing) one rung down, and the heading-level test could not see it
    because the HEADING was read; only this literal was not.

    A literal counts as read if `balance_lib._LITERAL_ESCAPES` silences an advisory with it, or some
    tool reads it by name for another purpose (the granularity DECLARATION silences nothing — it is
    echoed beside the security-row count it explains)."""
    src = "\n".join((TOOLS / f).read_text(encoding="utf-8")
                    for f in ("validate_model.py", "balance_lib.py", "audit_model.py",
                              "assemble.py", "balance.py"))
    escapes = set(balance_lib._LITERAL_ESCAPES)
    unread = [lit for lit in make_prescribed_balance_literals()
              if lit not in escapes and lit not in src]
    assert not unread, (
        "literal(s) the method tells a build to record under 'Balance exceptions' that no tool reads: "
        + ", ".join(unread) + " — a record nothing consumes is a decision the build cannot act on, "
        "and a typo in it is undetectable")


def make_documented_json_blocks() -> list[tuple[str, str, str]]:
    """(source, kind, RAW TEXT) for every ```json block in the method docs that a build copies.

    The raw text, not a re-serialized parse: an earlier version parsed each block and handed
    `json.dumps(obj)` to the loader, which normalized away every purely textual defect — a trailing
    comma, a smart quote, an inline `//`. It read the real file and then threw the file's text away.

    Kind comes from the surrounding PROSE (which loader the doc names), never from the loader's own
    key allowlist. Classifying by allowlist meant a misspelled top-level key — exactly the defect worth
    catching — silently reclassified the block as "other" and removed it from scope."""
    out: list[tuple[str, str, str]] = []
    for doc in METHOD_DOCS:
        if not doc.is_file():
            continue
        text = doc.read_text(encoding="utf-8")
        for hit in re.finditer(r"```json\n(.*?)```", text, re.S):
            before = text[max(0, hit.start() - 800):hit.start()].lower()
            if "--rules" in before or "coyodex reconcile" in before:
                kind = "reconcile-rules"
            elif "reconcile" in before or "drop_edges" in before:
                kind = "reconcile"
            else:
                kind = "other"
            out.append((f"{doc.name}:{text[:hit.start()].count(chr(10)) + 1}", kind, hit.group(1)))
    return out


def test_every_documented_json_block_is_valid_json():
    """The most basic doc defect, and the one the loader tests used to EXEMPT: a fenced ```json block
    a build copies that is not JSON at all. The earlier `except ValueError: continue` was justified as
    skipping "elided sketches"; there are none, so its only live effect was to hide real syntax
    errors."""
    bad: list[str] = []
    for src, _kind, raw in make_documented_json_blocks():
        try:
            json.loads(raw)
        except ValueError as e:
            bad.append(f"{src}: {e}")
    assert not bad, "```json block(s) a build copies that are not valid JSON:\n  " + "\n  ".join(bad)


def test_every_reconcile_example_in_the_method_loads_through_the_real_loader():
    """A build copies these blocks verbatim, so a shape the loader rejects is a doc-shaped bug.

    This is the class the `.coyodex/.ignore` example proved: the method showed `pattern  # comment`,
    the parser treated the whole line as one pattern, three live patterns matched nothing, and the
    build deleted the file instead of fixing the syntax. The fix was worth little until a test read the
    example out of the REAL doc — so the same discipline applies to the JSON the method teaches, and
    `drop_edges`'s shape was undocumented until a build read `reconcile.py`'s source to find it."""
    from coyodex.reconcile import ReconcileError, load_reconcile

    examples = [(src, raw) for src, kind, raw in make_documented_json_blocks()
                if kind == "reconcile"]
    assert len(examples) >= 2, f"expected the `set` and `drop_edges` examples, found {examples}"
    for src, raw in examples:
        try:
            rec = load_reconcile(raw, src)          # the RAW text a build copies
        except ReconcileError as e:
            raise AssertionError(f"{src} is not loadable by `assemble --reconcile`: {e}") from e
        assert not rec.is_empty(), f"{src} parsed to an EMPTY reconcile — the example teaches nothing"


def test_every_reconcile_rules_example_in_the_method_is_accepted_by_the_generator():
    """The `coyodex reconcile --rules` input shape, same reasoning. It ran 0 times in 3 measured
    builds, so its documented example is the only thing a build has to go on."""
    from coyodex.reconcile_build import RuleError, load_rules

    examples = [(src, raw) for src, kind, raw in make_documented_json_blocks()
                if kind == "reconcile-rules"]
    assert examples, "expected the --rules example the method documents"
    for src, raw in examples:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "rules.json"
            p.write_text(raw, encoding="utf-8")     # the RAW text a build copies
            try:
                rules = load_rules(p)
            except RuleError as e:
                raise AssertionError(f"{src} is not loadable by `coyodex reconcile --rules`: {e}") from e
        assert rules, f"{src} parsed to zero rules — the example teaches nothing"


def test_every_scoped_runs_in_literal_appears_in_the_method_prose():
    """The REVERSE direction of the audit above, and the gap that let a contract change ship half
    done: the tool stopped honouring a bare `runs-in`, and `method.md` / `method/model.md` went on
    teaching it for another commit. Build agents read those files on every run, so a lead following
    the method would have written the dead literal, silenced nothing, and gained an advisory.

    The existing test only checks method-literal -> tool. `runs-in` is still a recognised literal
    (it is what the "silences nothing" complaint keys off), so that direction stayed green."""
    from coyodex.balance_lib import RUNS_IN_SCOPES
    prose = "\n".join((REPO_ROOT / rel).read_text(encoding="utf-8")
                      for rel in ("method.md", "method/model.md"))
    missing = [scope for scope in RUNS_IN_SCOPES if f"`{scope}`" not in prose]
    assert not missing, (
        f"scoped `runs_in` literal(s) the tool honours but the method never names: {missing} — a "
        f"build cannot record an escape it has never been told about")


def test_every_worklist_theme_is_named_in_the_method():
    """The method tells a build to batch Phase 4 on `theme`, so the closed set it prints must be the
    set the tool emits. It was not: `rule` was added to `_THEMES` by the T7 fold and `method.md` went
    on listing eight themes for two releases, so a lead batching by the method's list had no bucket
    for the decision layer. Nothing caught it — the flag audit checks commands and flags, not the
    vocabulary the payload carries."""
    from coyodex.audit_model import _THEMES
    prose = (REPO_ROOT / "method.md").read_text(encoding="utf-8")
    marker = "closed, most-dangerous-first set ("
    at = prose.find(marker)
    assert at != -1, f"method.md no longer introduces the theme set with {marker!r}"
    # Read the PARENTHESISED LIST ONLY. Two weaker versions of this test both passed while the list
    # was missing `rule`: a document-wide substring check (every theme name is also an ordinary word
    # somewhere in method.md) and a whole-paragraph check (the prose right after the list explains
    # what `rule` means, which is enough to satisfy the search). The list is the thing under
    # contract, so the list is what gets read.
    open_at = at + len(marker) - 1
    close_at = prose.find(")", open_at)
    assert close_at != -1, "the theme set's parenthesis is never closed"
    listing = prose[open_at:close_at + 1]
    missing = [t for t in _THEMES if f"`{t}`" not in listing]
    assert not missing, (
        f"worklist theme(s) the tool emits but the method's printed set omits: {missing} — a build "
        f"told to batch on `theme` cannot bucket a value it has never been shown")


def test_the_method_no_longer_teaches_the_bare_runs_in_escape():
    """It silences nothing now, and a doc that still prescribes it costs a build an advisory plus
    the turns spent working out why the record did not take."""
    prose = "\n".join((REPO_ROOT / rel).read_text(encoding="utf-8")
                      for rel in ("method.md", "method/model.md"))
    for dead in ("the literal **`runs-in`** silences", "the literal `runs-in` silences"):
        assert dead not in prose, dead
