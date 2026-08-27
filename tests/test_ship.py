#!/usr/bin/env python3
"""Tests for `coyodex ship` — the closing sequence as one command.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_ship.py
    pytest tests/test_ship.py

The runner is INJECTED (a callable recording each step's argv), so these tests assert the plan and
the stop-on-failure contract without executing the underlying subcommands — those have their own
suites, and `tests/test_cli_sweep.py` drives `ship` end-to-end against the committed fixture.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from coyodex import ship


# --- builders -------------------------------------------------------------------

def make_repo(tmp: str, *, fragments: bool = True, worklist: bool = True,
              verdicts: bool = True, reconcile: bool = True) -> Path:
    """A repo skeleton holding exactly the closing sequence's inputs."""
    repo = Path(tmp) / "repo"
    out = repo / ".coyodex"
    (out / "build-fragments").mkdir(parents=True)
    (out / "verify").mkdir(parents=True)
    if fragments:
        (out / "build-fragments" / "b-slice.json").write_text("{}")
        (out / "build-fragments" / "a-slice.json").write_text("{}")
        (out / "build-fragments" / "half.draft.json").write_text("{}")  # must never assemble
    if worklist:
        (out / "verify" / "worklist.json").write_text("[]")
    if verdicts:
        (out / "verify" / "verdicts-security-1.json").write_text("{}")
        (out / "verify" / "verdicts-backbone-1.json").write_text("{}")
    if reconcile:
        (out / "reconcile.json").write_text("{}")
    return repo


def make_inputs(repo: Path, **kw) -> ship.ShipInputs:
    got = ship.derive_inputs(repo, **kw)
    assert not isinstance(got, str), got
    return got


def make_recording_runner(fail_on: str | None = None, code: int = 1):
    """A runner that records each step's argv and optionally fails the step whose argv[0]
    matches `fail_on` — dependency injection instead of patching the real subcommands."""
    calls: list[list[str]] = []

    def runner(argv: list[str]) -> int:
        calls.append(argv)
        return code if fail_on is not None and argv[0] == fail_on else 0

    return calls, runner


# --- deriving the inputs --------------------------------------------------------

def test_fragments_are_sorted_and_drafts_are_excluded():
    with tempfile.TemporaryDirectory() as td:
        s = make_inputs(make_repo(td))
        names = [p.name for p in s.fragments]
        assert names == ["a-slice.json", "b-slice.json"], (
            "fragment argument order decides dedup survivors, so it must be the shell's sorted "
            f"glob, drafts excluded — got {names}")


def test_derive_refuses_each_missing_input_by_name():
    with tempfile.TemporaryDirectory() as td:
        for kw, expect in ((dict(fragments=False), "no fragments"),
                           (dict(worklist=False), "worklist"),
                           (dict(verdicts=False), "verdicts")):
            repo = make_repo(tempfile.mkdtemp(dir=td), **kw)
            got = ship.derive_inputs(repo)
            assert isinstance(got, str) and expect in got, f"{kw}: {got}"


def test_a_missing_reconcile_file_is_none_not_an_error():
    with tempfile.TemporaryDirectory() as td:
        s = make_inputs(make_repo(td, reconcile=False))
        assert s.reconcile is None


# --- the plan -------------------------------------------------------------------

def test_prepare_plan_is_the_four_steps_ending_in_the_report():
    with tempfile.TemporaryDirectory() as td:
        steps = ship.build_plan(make_inputs(make_repo(td)))
        assert [st.argv[0] for st in steps] == ["anchor-drift", "fix", "assemble", "grounding"]
        assert steps[-1].argv[1] == "report", "the prepare phase must END on the report the note is written from"
        # every step that reads verdicts repeats the flag once per file
        assert steps[0].argv.count("--verdicts") == 2
        assert "--to-reconcile" in steps[1].argv
        assert "--reconcile" in steps[2].argv


def test_full_plan_runs_the_method_sequence_in_order():
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        note = repo / "note.txt"
        note.write_text("319 of 1608 challenged")
        steps = ship.build_plan(make_inputs(repo, note_file=note, partial=True))
        heads = [(st.argv[0], st.argv[1] if len(st.argv) > 1 else "") for st in steps]
        assert [h[0] for h in heads] == [
            "anchor-drift", "fix", "assemble",          # the idempotent prepare prefix
            "grounding", "assemble", "provenance",       # write → carry in → stamp
            "assemble", "lint-fragment", "validate",     # header in → lint → gates
            "audit", "render", "finalize"], heads
        write = steps[3].argv
        assert write[1] == "write" and "--note-file" in write and "--partial" in write
        assert "--keep-note" not in write
        stamp = steps[5].argv
        assert "--update-header" in stamp and "--mode" in stamp
        fin = steps[-1].argv
        assert "--emit-gate-block" in fin and "--access-baseline" not in fin


def test_access_baseline_reaches_finalize_and_only_finalize():
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        note = repo / "note.txt"
        note.write_text("n")
        base = repo / "old-map.json"
        base.write_text("{}")
        steps = ship.build_plan(make_inputs(repo, note_file=note, access_baseline=base))
        carriers = [st.argv[0] for st in steps if "--access-baseline" in st.argv]
        assert carriers == ["finalize"]


def test_without_a_reconcile_file_no_assemble_carries_the_flag():
    with tempfile.TemporaryDirectory() as td:
        steps = ship.build_plan(make_inputs(make_repo(td, reconcile=False)))
        for st in steps:
            if st.argv[0] == "assemble":
                assert "--reconcile" not in st.argv


# --- running --------------------------------------------------------------------

def test_run_stops_at_the_first_failing_step_and_names_the_rest(capsys):
    with tempfile.TemporaryDirectory() as td:
        steps = ship.build_plan(make_inputs(make_repo(td)))
        calls, runner = make_recording_runner(fail_on="fix", code=3)
        rc = ship.run_plan(steps, runner)
        assert rc == 3, "the failing step's own exit code must propagate"
        assert [c[0] for c in calls] == ["anchor-drift", "fix"], (
            "a step after the failure ran — a skipped step must never happen silently, and a run "
            "one must never happen at all")
        err = capsys.readouterr().err
        assert "SHIP STOPPED" in err and "NOT RUN" in err and "assemble" in err


def test_a_clean_run_calls_every_step_once():
    with tempfile.TemporaryDirectory() as td:
        steps = ship.build_plan(make_inputs(make_repo(td)))
        calls, runner = make_recording_runner()
        assert ship.run_plan(steps, runner) == 0
        assert len(calls) == len(steps)


# --- the command shell ----------------------------------------------------------

def test_main_refuses_an_unknown_option():
    assert ship.main(["--definitely-not-a-real-flag"]) == 2


def test_main_requires_a_repo():
    assert ship.main(["--partial"]) == 2


def test_main_refuses_a_note_file_that_does_not_exist():
    with tempfile.TemporaryDirectory() as td:
        repo = make_repo(td)
        assert ship.main([str(repo), "--note-file", str(repo / "missing-note.txt")]) == 2


def test_main_names_whats_missing_on_an_empty_repo(capsys):
    with tempfile.TemporaryDirectory() as td:
        assert ship.main([td]) == 2
        assert "fragments" in capsys.readouterr().err


if __name__ == "__main__":
    import inspect

    for _name, _fn in sorted(list(globals().items())):
        if _name.startswith("test_") and callable(_fn):
            if "capsys" in inspect.signature(_fn).parameters:
                continue  # pytest-only: needs capture
            _fn()
            print(f"ok  {_name}")
    print("ship tests passed (capsys ones under pytest)")
