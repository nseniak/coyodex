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
            "anchor-drift", "fix", "assemble",           # the idempotent prepare prefix
            "grounding", "assemble", "provenance",       # write → carry in → stamp
            "assemble", "lint-fragment",                 # header in → lint
            "grounding",                                 # by-element: the list behind the count
            "validate", "audit", "render", "finalize"], heads
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


# --- one verdict list, two commands with opposite contracts -----------------------------------
# `grounding write` refuses a verdict whose claim is not in the pinned worklist; `finalize` needs
# every verdict there is. `ship` spliced ONE `--verdicts` tuple into both. On the 2026-08-29
# mcpolis build it stopped at step 6 with "9 verdict claim(s) are not in the pinned worklist", the
# lead abandoned the verb and hand-ran steps 5-12, and the map still shipped finalize's "the
# record's delta counts contradict the verdict files" as a carried-no-escape advisory — because the
# two commands had been measured against different sets.

def _ship_dirs(tmp: Path, pinned_claims: list[str], files: dict[str, list[str]]) -> Path:
    import json as _json
    out = tmp / ".coyodex"
    (out / "verify").mkdir(parents=True)
    (out / "build-fragments").mkdir(parents=True)
    (out / "verify" / "worklist.json").write_text(
        _json.dumps({"worklist": [{"claim": c} for c in pinned_claims]}), encoding="utf-8")
    for name, claims in files.items():
        (out / "verify" / f"verdicts-{name}.json").write_text(
            _json.dumps({"grounding": [{"claim": c, "grounded": True} for c in claims]}),
            encoding="utf-8")
    return out


def _plan_argvs(out: Path, tmp: Path):
    from coyodex.ship import ShipInputs, build_plan
    s = ShipInputs(map_path=out / "project-map.json", repo=tmp, out=out,
                   header=out / "build-fragments" / "header.json",
                   md=out / "project-map.md", gate_block=out / "verify" / "gate-block.md",
                   reconcile=out / "reconcile.json", worklist=out / "verify" / "worklist.json",
                   verdicts=tuple(sorted((out / "verify").glob("verdicts-*.json"))),
                   note_file=tmp / "note.txt", fragments=(), partial=False, keep_note=False,
                   access_baseline=None)
    return {step.title: step.argv for step in build_plan(s)}


def test_grounding_write_gets_only_the_pinned_verdicts_and_finalize_gets_them_all():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "note.txt").write_text("a note", encoding="utf-8")
        out = _ship_dirs(tmp, ["c1", "c2"],
                         {"pinned": ["c1", "c2"], "recheck": ["c9-minted-after-the-pin"]})
        argvs = _plan_argvs(out, tmp)
    write = next(a for t, a in argvs.items() if t.startswith("grounding write"))
    final = next(a for t, a in argvs.items() if t.startswith("finalize"))
    assert "verdicts-recheck.json" not in " ".join(write), write
    assert "verdicts-pinned.json" in " ".join(write), write
    assert "verdicts-recheck.json" in " ".join(final), final
    assert "verdicts-pinned.json" in " ".join(final), final


def test_a_file_that_STRADDLES_the_pin_is_dropped_too():
    """The case the whole fix exists for, and the one a first version got wrong.

    On the real build the nine off-pin claims sat in three `verdicts-recheck*.json` files that each
    ALSO carried three pinned ones. Keeping straddlers left `grounding write` refusing the set with
    the identical "9 verdict claim(s) are not in the pinned worklist" — the failure the docstring
    quotes. The set the build needed by hand was the files with no post-pin claim at all."""
    import tempfile
    from coyodex.ship import ShipInputs, post_pin_verdicts
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        (tmp / "note.txt").write_text("a note", encoding="utf-8")
        out = _ship_dirs(tmp, ["c1"], {"pinned": ["c1"], "mixed": ["c1", "c-new"]})
        argvs = _plan_argvs(out, tmp)
        s = ShipInputs(map_path=out / "project-map.json", repo=tmp, out=out,
                       header=out / "build-fragments" / "header.json", md=out / "project-map.md",
                       gate_block=out / "verify" / "gate-block.md",
                       reconcile=out / "reconcile.json", worklist=out / "verify" / "worklist.json",
                       verdicts=tuple(sorted((out / "verify").glob("verdicts-*.json"))),
                       note_file=tmp / "note.txt", fragments=(), partial=False, keep_note=False,
                       access_baseline=None)
        dropped = [p.name for p in post_pin_verdicts(s)]
    write = " ".join(next(a for t, a in argvs.items() if t.startswith("grounding write")))
    final = " ".join(next(a for t, a in argvs.items() if t.startswith("finalize")))
    assert "verdicts-mixed.json" not in write, write
    assert "verdicts-pinned.json" in write, write
    assert "verdicts-mixed.json" in final, "finalize still needs every verdict"
    assert dropped == ["verdicts-mixed.json"], dropped


# --- the operator report's coverage line (retro 2026-09-01, argus row 2) -------------------------
# The build's closing message is written from `claims_total`, the size of the worklist the skeptics
# were given. That is not coverage of the SHIPPED map: a claim reworded after the vote stays in the
# map and loses its verdict. Two builds in a row headlined "all N claims challenged" over fewer.

def _grounding(repo: Path, **fields) -> None:
    import json
    record = {"claims_total": 454, "claims_live_challenged": 440,
              "claims_superseded": 0, "claims_added_since": 0}
    record.update(fields)
    # where `ship`'s own plan sends `grounding write --out`: beside the header fragment.
    (repo / ".coyodex" / "build-fragments" / "grounding.json").write_text(
        json.dumps({"grounding": record}), encoding="utf-8")


def test_the_coverage_line_states_the_shipped_map_not_the_pinned_worklist():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        _grounding(repo)
        line = ship._coverage_line(make_inputs(repo))
    assert "454 claims challenged" in line, line          # the sentence it refuses
    assert "454 claim(s), of which 440" in line, line
    assert "14 do NOT" in line, line


def test_the_live_total_is_computed_from_the_record_not_assumed_equal_to_the_pinned_one():
    """The whole defect is that the two differ. 454 pinned, 4 superseded, 10 added -> 460 live."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        _grounding(repo, claims_superseded=4, claims_added_since=10, claims_live_challenged=440)
        line = ship._coverage_line(make_inputs(repo))
    assert "460 claim(s), of which 440" in line, line
    assert "20 do NOT" in line, line


def test_full_coverage_says_so_and_still_names_the_right_number():
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        _grounding(repo, claims_live_challenged=454)
        line = ship._coverage_line(make_inputs(repo))
    assert "every one of the shipped map's 454 claim(s)" in line, line


def test_an_unreadable_grounding_record_makes_ship_silent_not_wrong():
    """finalize reports a broken record; a second voice guessing at it only adds noise."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = make_repo(tmp)
        assert ship._coverage_line(make_inputs(repo)) == ""
        (repo / ".coyodex" / "build-fragments" / "grounding.json").write_text(
            "{not json", encoding="utf-8")
        assert ship._coverage_line(make_inputs(repo)) == ""
