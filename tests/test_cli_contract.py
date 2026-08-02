#!/usr/bin/env python3
"""Package-wide CLI honesty contracts, generalised from defects this project actually shipped.

Every check here is a CLASS, not an instance. Each was written after a specific bug slipped a
per-command test, so the guard is applied to every command at once — the same reason
`tests/test_method_contract.py` audits the prose↔tool seam in bulk rather than one flag at a time.

Run either way: `python3 tests/test_cli_contract.py` or `pytest tests/test_cli_contract.py`.
"""
from __future__ import annotations

import contextlib
import importlib
import io
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: command name -> implementing module, DERIVED from `cli.py`'s own USAGE. The first version of this
#: file hard-coded ten entries while its comment claimed exactly this derivation — and the three it
#: omitted included `preindex`, which was a live instance of the bug these contracts exist to catch.
#: A new command must join automatically or the contract is decoration.
COMMAND_MODULE: dict[str, str] = {
    "preindex": "preindex", "validate": "validate_model", "audit": "audit_model",
    "render": "viewer.render", "serve": "viewer.serve", "assemble": "assemble",
    "lint-fragment": "lint_fragment", "anchor-drift": "anchor_drift", "fix": "fix",
    "dump": "dump", "reconcile": "reconcile_build", "balance": "balance", "finalize": "finalize",
    "grounding": "grounding", "record": "record", "scope": "scope",
}


def make_cli_commands() -> tuple[str, ...]:
    """The command names `coyodex --help` advertises, read from USAGE itself."""
    from coyodex.cli import USAGE
    body = USAGE.split("Commands:", 1)[1].split("\nGlobal:", 1)[0]
    return tuple(ln.split()[0] for ln in body.splitlines()
                 if ln.startswith("  ") and ln.strip() and not ln.startswith("    "))


def test_the_command_table_covers_every_command_the_cli_advertises():
    """The guard on the guard. If this list drifts, every contract below silently stops covering
    whatever fell out — which is precisely how `preindex` was exempt while it was broken."""
    advertised = set(make_cli_commands())
    assert advertised == set(COMMAND_MODULE), (
        f"missing: {sorted(advertised - set(COMMAND_MODULE))}; "
        f"stale: {sorted(set(COMMAND_MODULE) - advertised)}")


#: Commands these probes may not CALL, with the reason. `serve` is a daemon: invoking its `main`
#: binds a port and blocks. Named explicitly and pinned by a test, because "exempt by omission" is the
#: exact failure that left `preindex` uncovered while it was broken.
UNPROBEABLE: dict[str, str] = {"serve": "a long-running HTTP daemon — calling main() binds a port"}


def test_the_unprobeable_list_stays_minimal_and_justified():
    """An exemption is a hole in every contract below it, so it needs a reason and a test."""
    assert set(UNPROBEABLE) <= set(COMMAND_MODULE)
    assert set(UNPROBEABLE) == {"serve"}, (
        "a new exemption was added — every command that can be called must be, or the contracts "
        f"stop covering it: {sorted(UNPROBEABLE)}")


def make_command_mains() -> list[tuple[str, object]]:
    out: list[tuple[str, object]] = []
    for cmd in sorted(set(COMMAND_MODULE) - set(UNPROBEABLE)):
        mod = importlib.import_module(f"coyodex.{COMMAND_MODULE[cmd]}")
        if hasattr(mod, "main"):
            out.append((cmd, mod.main))
    return out


#: An absolute map path, so a probe's exit code reflects FLAG HANDLING and not the process CWD. With a
#: relative default, `audit`/`balance` only reached the offending code path when pytest happened to run
#: from the repo root — both production bugs went green from any other directory.
MAP = REPO_ROOT / ".coyodex" / "project-map.json"


def run_main(main, argv: list[str]) -> tuple[int, str]:
    """Call a command in-process, returning `(exit code, everything it printed)`."""
    out, err = io.StringIO(), io.StringIO()
    code: int = 2
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = int(main(argv) or 0)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 2)
    return code, out.getvalue() + err.getvalue()


def test_every_command_refuses_an_unknown_option():
    """A silently-ignored flag is a request the caller believes was honoured.

    `coyodex audit --jsonn` used to print the HUMAN report and exit 0, so a build asking for JSON got
    prose and had no way to notice the typo. `balance` did the same. Every other command already
    refused, which is exactly why a per-command test never caught these two."""
    assert MAP.is_file(), "coyodex's own map is the fixture for every probe here"
    offenders: list[str] = []
    for name, main in make_command_mains():
        code, _text = run_main(main, [str(MAP), "--definitely-not-a-real-flag"])
        if code == 0:
            offenders.append(name)
    assert not offenders, (
        "command(s) that accept an unknown option and exit 0, so a typo'd flag is undetectable: "
        + ", ".join(offenders))


def test_no_command_prints_an_error_and_then_claims_success():
    """The whole session's recurring failure, as a contract: output that says something went wrong
    while the exit status says nothing did. A caller reads one or the other, never both."""
    # The package reports failure in several vocabularies, not just `ERROR:` — `fix` and `cli` say
    # "unknown verb", `validate` says "VALIDATION FAILED", `assemble` "ASSEMBLY FAILED". Matching only
    # `ERROR` would have missed three of them.
    failed = re.compile(r"\bERROR\b|\bFAILED\b|unknown (?:option|verb|command|argument)",
                        re.IGNORECASE)
    liars: list[str] = []
    for name, main in make_command_mains():
        code, text = run_main(main, ["/nonexistent/path/to/a/map.json"])
        if code == 0 and failed.search(text):
            liars.append(f"{name} (missing file)")
    assert not liars, ("command(s) reporting a failure while exiting 0: " + ", ".join(liars))


#: The commands whose stdout is a MACHINE contract, with the argv that exercises it. An explicit
#: table, not a source-literal heuristic: the first version gated on `'"--json"' in src`, which
#: exempted `dump` — the one command whose entire stdout is JSON and therefore the most important
#: member — and silently dropped three more via a bare `except: continue`.
JSON_COMMANDS: dict[str, list[str]] = {
    "validate": ["--json"],
    "audit": ["--json"],
    "balance": ["--json"],
    "dump": [],                      # no flag: `dump`'s whole stdout IS the machine contract
    "anchor-drift": ["--map", "@MAP", "--repo", "@REPO", "--json"],
}


def test_every_machine_readable_command_emits_only_json_on_stdout():
    """`--json` is a contract with a program. A stray human line breaks `json.load` for the caller, and
    this project has already shipped a `--json` mode that leaked a truncated list into its own payload.

    Failures are COLLECTED, never skipped: an earlier version wrapped each call in
    `except Exception: continue`, so a total crash of `audit --json` — the payload the method tells
    Phase-4 builds to consume — left the test green."""
    assert MAP.is_file()
    broken: list[str] = []
    for cmd, extra in sorted(JSON_COMMANDS.items()):
        mod = importlib.import_module(f"coyodex.{COMMAND_MODULE[cmd]}")
        argv = [a.replace("@MAP", str(MAP)).replace("@REPO", str(REPO_ROOT)) for a in extra]
        if "@MAP" not in " ".join(extra):
            argv = [str(MAP), *argv]
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                mod.main(argv)
        except SystemExit:
            pass
        except Exception as e:                       # a crash is a FINDING, not a skip
            broken.append(f"{cmd}: raised {type(e).__name__}: {e}")
            continue
        text = out.getvalue().strip()
        if not text:
            broken.append(f"{cmd}: wrote nothing to stdout (stderr: {err.getvalue().strip()[:120]})")
            continue
        try:
            json.loads(text)
        except ValueError as e:
            broken.append(f"{cmd}: stdout is not parseable JSON — {e}")
    assert not broken, "machine-readable stdout is broken for:\n  " + "\n  ".join(broken)


if __name__ == "__main__":
    for _name, _fn in sorted(list(globals().items())):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print(f"ok  {_name}")
    print("all CLI contract tests passed")


def _l2(map_path: Path):
    from coyodex.audit_model import l2_worklist_model
    from coyodex.model import load_model
    return l2_worklist_model(load_model(map_path.read_text(encoding='utf-8')))


def test_a_flag_advertised_as_repeatable_reads_every_occurrence():
    """`usage: … [--verdicts <f>]...` is a promise. A scalar rebind silently keeps only the LAST.

    `anchor-drift` bound `verdicts_path = argv[i]`, so a themed Phase-4 fan-out that passed its 13
    per-batch verdict files got a pass computed over the LAST file — 9% of the evidence — while
    `finalize` printed that the verdict-based drift leg had run. "The gate did not run" read exactly
    like "the gate passed", the single thing `finalize` exists to prevent, reintroduced through flag
    arity. `fix apply-drift` carried the identical bug, and fixing only one would have been worse
    than fixing neither: drift reported over the union, corrections written from one file.

    Driven through `main()` on purpose. An earlier version of this test called `load_verdicts`
    directly and stayed green with `main()`'s arity reverted to the scalar — it tested the helper,
    not the flag."""
    import json as _json
    import tempfile

    from coyodex import anchor_drift as ad
    from coyodex import fix as fx

    claims = [w.claim for w in _l2(MAP)]
    assert len(claims) >= 2, "need two claims to split across two files"
    with tempfile.TemporaryDirectory() as td:
        # `fix apply-drift` WRITES the map in place, so it must never be pointed at the repo's own
        # committed one. An earlier version of this test did exactly that and rewrote two security
        # anchors to `nowhere/at/all.py`, which `validate --check-sources` then failed on.
        target = Path(td) / "map.json"
        target.write_text(MAP.read_text(encoding="utf-8"), encoding="utf-8")
        a, b = Path(td) / "a.json", Path(td) / "b.json"
        a.write_text(_json.dumps({"grounding": [
            {"claim": claims[0], "grounded": True, "evidence": "nowhere/at/all.py:1"}]}))
        b.write_text(_json.dumps({"grounding": [
            {"claim": claims[1], "grounded": True, "evidence": "nowhere/at/all.py:2"}]}))
        for name, main, argv in (
            ("anchor-drift", ad.main,
             ["--map", str(target), "--verdicts", str(a), "--verdicts", str(b)]),
            ("fix apply-drift", fx.apply_drift,
             ["--map", str(target), "--verdicts", str(a), "--verdicts", str(b)]),
        ):
            code, text = run_main(main, argv)
            assert code == 0, f"{name} exited {code}"
            if name == "anchor-drift":
                # The coverage line counts BOTH files' claims, so it proves both were read.
                assert "challenged 2 of" in text, (
                    f"{name} read {text.splitlines()[0] if text else '(nothing)'} — a repeatable "
                    f"flag that keeps only the last occurrence")
