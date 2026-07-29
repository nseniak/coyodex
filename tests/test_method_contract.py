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
  (b2) …and is actually READ by the code path that runs for that command form
  (c) every advisory the validator prints names a way to record the decision, or is allowlisted
  (d) every extras heading the method tells a lead to write is read by some tool

Pure text + AST. No fixture, no LLM, ~1 second. This is the cheapest layer and it would have
caught the worst defect in the study.

**Three of these FAIL on today's code, and that is the deliverable** — the failures are the
finding, not a bug in the test. Do not "fix" them by editing method.md, the CLI, or the
validator; that is a separate decision for the maintainer.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

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
    "dump": "dump", "reconcile": "reconcile_build", "balance": "balance",
}

#: The extras headings some tool actually READS (the escape tokens that silence an advisory).
#: Derived below from the source, never hard-coded into an assertion.
MACHINE_READ_HEADINGS: tuple[str, ...] = (
    "balance exceptions", "coverage exceptions", "accepted duplications",
    "entry-point coverage", "happy path coverage", "persistence exceptions",
    "unclaimed surfaces",
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


def make_advisory_sites() -> tuple[tuple[int, str, str, bool], ...]:
    """(line, function, message-skeleton, function_has_escape_machinery) for every advisory the
    validator can PRINT.

    An advisory is a string appended to a warnings list, or returned as the first element of a
    warning function's literal list. Read by AST rather than by regex so a reformatted call
    still counts. The fourth field separates two different failures: a check with NO escape at
    all, and a check that HAS one whose message never tells the reader about it."""
    src = (TOOLS / "validate_model.py").read_text(encoding="utf-8")
    src_lines = src.splitlines()
    sites: list[tuple[int, str, str, bool]] = []
    for fn in ast.walk(ast.parse(src)):
        if not isinstance(fn, ast.FunctionDef):
            continue
        fn_src = "\n".join(src_lines[fn.lineno - 1:(fn.end_lineno or fn.lineno)])
        # `validate_model` is the 200-line ORCHESTRATOR, not a check: escape machinery anywhere
        # inside it belongs to some other rule, so crediting its warnings with it would label a
        # real gap as a wording problem. Every focused check is its own function.
        wired = fn.name != "validate_model" and any(tok in fn_src for tok in _ESCAPE_MACHINERY)
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
                sites.append((getattr(node, "lineno", fn.lineno), fn.name, msg, wired))
    return tuple(sorted(set(sites)))


def make_flags_read_by(module: str, function: str) -> frozenset[str]:
    """Every `--flag` literal that appears inside one function of a command module.

    coyodex parses argv by hand (no argparse anywhere — see `cli.py`'s dependency firewall), so
    "the parser accepts it" is "the flag literal is in the code that runs". Scoping to ONE
    function is what makes the difference between accepted-and-used and accepted-and-ignored
    visible."""
    src = (TOOLS / f"{module}.py").read_text(encoding="utf-8")
    for fn in ast.walk(ast.parse(src)):
        if isinstance(fn, ast.FunctionDef) and fn.name == function:
            found = {n.value for n in ast.walk(fn)
                     if isinstance(n, ast.Constant) and isinstance(n.value, str)
                     and n.value.startswith("--")}
            return frozenset(found)
    raise AssertionError(f"{module}.py has no function {function}()")


# --- (a) every command the CLI offers is reachable from the method --------------------

def test_every_cli_command_is_named_in_the_method():
    """A command the method never names cannot be reached: the build agent reads the method,
    not `--help`. FAILS TODAY on `dump` and `reconcile`."""
    text = make_method_text()
    missing = [c for c in make_cli_commands() if f"coyodex {c}" not in text]
    assert not missing, (
        "CLI commands named nowhere in the method docs, so no build can reach them: "
        + ", ".join(missing)
        + " — every one of these is a working, tested command that a build agent has no way to "
          "learn about. `coyodex reconcile` is the measured case: four builds hand-wrote the "
          "file it generates instead of running it.")


def test_every_fix_verb_is_named_in_the_method():
    """`coyodex fix` dispatches three verbs; the method names two. FAILS TODAY on
    `dedup-relation` — which resolves a BLOCKING validate error, so a lead who hits that error
    has no documented way out and hand-edits the model instead."""
    text = make_method_text()
    missing = [v for v in make_fix_verbs() if v not in text]
    assert not missing, (
        "`coyodex fix` verbs named nowhere in the method docs: " + ", ".join(missing))


# --- (b) every flag the method tells a build to pass is accepted ----------------------

def test_every_flag_the_method_prescribes_is_accepted_by_that_command():
    """The doc must not tell a build to pass a flag the command rejects. This one PASSES today:
    the flag vocabulary in the method is in sync with the parsers. Kept as a standing gate —
    it is the cheap half of the contract, and it is the half that silently rots when a flag is
    renamed."""
    bad: list[str] = []
    for cmd, flag, loc in make_doc_flag_pairs():
        src = make_module_source(cmd)
        if f'"{flag}"' not in src and f"'{flag}'" not in src:
            bad.append(f"{loc}: `coyodex {cmd} {flag}` — {COMMAND_MODULE[cmd]}.py never reads it")
    assert not bad, "Flags the method prescribes that the command does not accept:\n  " + "\n  ".join(bad)


def test_a_mode_flag_does_not_silently_swallow_the_flags_its_mode_ignores():
    """The other half of (b), and the one that bites: a flag can be *accepted* by the command
    and *ignored* by the mode.

    `coyodex preindex --report --root <other-repo>` is the measured case. `preindex.py` reads
    `--root` in `main()`, so the flag-existence check above passes — but `--report` branches
    into `report()`, which reads only `--in`, so `--root` is silently dropped and the CWD's
    pre-index is reported instead of the named repo's. Silently using the wrong repo is worse
    than erroring: the output looks exactly right.

    FAILS TODAY. See tools/coyodex/preindex.py:302 (`report()` reads `--in`) against
    tools/coyodex/preindex.py:398 (`main()` reads `--root`), and the dispatch at
    tools/coyodex/preindex.py:396."""
    main_flags = make_flags_read_by("preindex", "main")
    report_flags = make_flags_read_by("preindex", "report")
    # `--report` itself and the help flags are the mode switch, not mode input.
    switches = {"--report", "--help", "--in", "--depth", "--top"}
    ignored = sorted((main_flags - report_flags) - switches)
    assert not ignored, (
        "`coyodex preindex --report` accepts these flags and silently ignores them: "
        + ", ".join(ignored)
        + " — `--root` is the one that matters: --report reads `--in` (a CWD-relative path) and "
          "never looks at --root, so `preindex --report --root <other-repo>` reports the CURRENT "
          "repo's pre-index under the other repo's name. Either make report() honour --root, or "
          "reject the flag; accepting-and-ignoring is the failure mode with no visible symptom.")


# --- (c) every advisory offers a way to record the decision ---------------------------

#: Advisory message prefixes that legitimately need NO recordable escape, each with the reason.
#: An entry here is a claim: "this is always fixable at the point it fires, so an operator never
#: has to live with it." Adding a line to this list is a design decision, not a formality.
KNOWN_NO_ESCAPE: dict[str, str] = {
    # Row-local well-formedness: the fix is mechanical and local, there is no judgement to record.
    "{}: `no_call_site` is set but a `where` is present":
        "contradictory row; drop one field",
    "{} → {}: `no_call_site` is set but a `Where` is present":
        "contradictory row; drop one field",
    "{} → {}: the '{}' edge is declared {} times":
        "one edge, one primary call site; merge them",
    "{}: '{}' does not resolve to a":
        "a nonexistent path is never a judgement call",
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
    "{} deployment advisory/advisories suppressed by the recorded `runs-in` exception":
        "this IS the escape being reported; it must never be silenceable itself",
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

    FAILS TODAY. The residue below is the finding: each one is a judgement an operator can
    legitimately make and has nowhere to write down. The headline is trap P1 — "Entities with no
    owning component" (tools/coyodex/validate_model.py:2459) — where three separate live leads
    independently invented a `Persistence exceptions` heading. That heading now exists, but it
    is read by the persistence-COVERAGE rule (validate_model.py:1331, which filters `Cn` ids)
    and does not silence this advisory at all.

    The report separates two failure shapes, because they need different fixes:
      NO-ESCAPE   — nothing anywhere can silence it; the fix is to add an escape token.
      UNNAMED     — an escape IS wired to the check, but its message never says so; the fix is
                    one sentence in the message. Cheap, and the difference between an operator
                    recording a decision and an operator ignoring a line forever."""
    orphans = [(line, fn, msg, wired) for line, fn, msg, wired in make_advisory_sites()
               if not _has_escape(msg) and not _allowlisted(msg)]
    detail = "\n  ".join(
        f"{'UNNAMED  ' if wired else 'NO-ESCAPE'} validate_model.py:{line} ({fn}): {msg[:105]}"
        for line, fn, msg, wired in sorted(orphans))
    assert not orphans, (
        f"{len(orphans)} validator advisory/advisories offer no recordable escape in their text "
        "and are not allowlisted — an operator who decides the finding is acceptable has nowhere "
        "to say so:\n  " + detail)


def test_the_no_escape_allowlist_has_no_dead_entries():
    """An allowlist entry that matches nothing is a claim about code that no longer exists —
    it hides the next advisory that grows into that shape. This one PASSES today and is the
    guard that keeps the list above honest."""
    messages = [msg for _line, _fn, msg, _wired in make_advisory_sites()]
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
    owns the 'Balance exceptions' constant that `validate_model` reaches through a helper."""
    src = "\n".join((TOOLS / f).read_text(encoding="utf-8")
                    for f in ("validate_model.py", "balance_lib.py"))
    found = set(re.findall(r'(?:extras_bodies\(m,|_recorded_ids\(m,)\s*"([^"]+)"', src))
    found |= set(re.findall(r'_EXCEPTIONS_HEADING\s*=\s*"([^"]+)"', src))
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
