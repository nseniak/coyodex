#!/usr/bin/env python3
"""Tests for `coyodex timings` — the measured answer to "which slice is longest?".

The method tells the lead to dispatch the longest slice first, then hands it folklore to decide
"longest" with. A measured build got the order wrong three times in six fan-outs and paid up to 7.7
minutes of pure barrier delay for it. These tests hold the two properties that make the record worth
keeping: a first build is never blocked by the absence of one, and a corrupt one is never silently
replaced by an empty one.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_timings.py
    pytest tests/test_timings.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from coyodex.timings import PHASES, VERSION, Run, latest_by_slice, load_runs, main, record_path


def make_repo(tmp: str) -> str:
    """An analyzed repo with no timings record — what every first build looks like."""
    Path(tmp, ".coyodex").mkdir(parents=True, exist_ok=True)
    return tmp


def make_record(tmp: str, runs: list[dict]) -> Path:
    path = record_path(make_repo(tmp))
    path.write_text(json.dumps({"version": VERSION, "runs": runs}), encoding="utf-8")
    return path


def read_record(tmp: str) -> list[dict]:
    return json.loads(record_path(tmp).read_text(encoding="utf-8"))["runs"]


def test_a_project_with_no_record_is_told_so_and_not_blocked(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        assert main(["order", "--repo", make_repo(tmp), "--phase", "harvest"]) == 0
        out = capsys.readouterr().out
        assert "no timings recorded" in out
        assert "order by the pre-index" in out


def test_one_call_records_every_slice_of_a_fan_out() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        code = main(["record", "--repo", make_repo(tmp), "--phase", "harvest",
                     "--slice", "T5 model", "--minutes", "12.4",
                     "--slice", "deps", "--minutes", "3.2"])
        assert code == 0
        rows = read_record(tmp)
        assert [(r["slice"], r["minutes"]) for r in rows] == [("T5 model", 12.4), ("deps", 3.2)]


def test_order_prints_the_slices_longest_first(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        make_record(tmp, [{"phase": "harvest", "slice": "deps", "minutes": 3.2},
                          {"phase": "harvest", "slice": "T5 model", "minutes": 12.4}])
        assert main(["order", "--repo", tmp, "--phase", "harvest"]) == 0
        lines = [ln for ln in capsys.readouterr().out.splitlines() if "min" in ln]
        assert lines[0].endswith("T5 model")
        assert lines[1].endswith("deps")


def test_a_slice_with_no_record_is_listed_apart_and_never_assumed_short(capsys) -> None:
    """The whole failure this replaces is an unknown slice dispatched last. Ranking one we have
    never measured BELOW ones we have would re-create it under a measured-looking heading."""
    with tempfile.TemporaryDirectory() as tmp:
        make_record(tmp, [{"phase": "harvest", "slice": "deps", "minutes": 3.2}])
        assert main(["order", "--repo", tmp, "--phase", "harvest",
                     "--slice", "deps", "--slice", "brand new"]) == 0
        out = capsys.readouterr().out
        assert "no record for these" in out
        assert "brand new" in out.split("no record for these", 1)[1]


def test_the_most_recent_recording_of_a_slice_wins() -> None:
    """Not an average: slices are re-cut between builds, so an old shape is not evidence about a
    new one."""
    runs = [Run("harvest", "T5 model", 12.4, None, None),
            Run("harvest", "T5 model", 4.0, None, None)]
    assert [r.minutes for r in latest_by_slice(runs, "harvest")] == [4.0]


def test_a_phase_only_sees_its_own_slices() -> None:
    runs = [Run("harvest", "deps", 3.2, None, None), Run("trace", "deps", 30.0, None, None)]
    assert [r.minutes for r in latest_by_slice(runs, "harvest")] == [3.2]


def test_an_unknown_phase_is_refused_with_the_list(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        code = main(["record", "--repo", make_repo(tmp), "--phase", "harvst",
                     "--slice", "a", "--minutes", "1"])
        assert code == 2
        err = capsys.readouterr().err
        assert "unknown phase" in err
        for phase in PHASES:
            assert phase in err
        assert not record_path(tmp).exists()


def test_a_slice_minutes_count_mismatch_is_refused_rather_than_paired_off(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        code = main(["record", "--repo", make_repo(tmp), "--phase", "harvest",
                     "--slice", "a", "--slice", "b", "--minutes", "1"])
        assert code == 2
        assert "pair by position" in capsys.readouterr().err
        assert not record_path(tmp).exists()


@pytest.mark.parametrize("bad", ["0", "-3", "nope", "nan", "inf"])
def test_a_minutes_value_that_is_not_positive_wall_time_is_refused(bad: str, capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        code = main(["record", "--repo", make_repo(tmp), "--phase", "harvest",
                     "--slice", "a", "--minutes", bad])
        assert code == 2
        assert "ERROR" in capsys.readouterr().err
        assert not record_path(tmp).exists()


def test_one_call_naming_a_slice_twice_is_refused(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        code = main(["record", "--repo", make_repo(tmp), "--phase", "harvest",
                     "--slice", "a", "--minutes", "1", "--slice", "a", "--minutes", "2"])
        assert code == 2
        assert "twice in one call" in capsys.readouterr().err


def test_a_batch_with_one_bad_row_writes_nothing(capsys) -> None:
    """The same guarantee `coyodex record` gives: a bad line in a batch of twenty leaves the file
    untouched rather than holding half a batch."""
    with tempfile.TemporaryDirectory() as tmp:
        make_record(tmp, [{"phase": "harvest", "slice": "deps", "minutes": 3.2}])
        code = main(["record", "--repo", tmp, "--phase", "harvest",
                     "--slice", "good", "--minutes", "5",
                     "--slice", "bad", "--minutes", "-1"])
        assert code == 2
        assert [r["slice"] for r in read_record(tmp)] == ["deps"]


def test_items_must_be_one_per_slice_or_none_at_all(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        code = main(["record", "--repo", make_repo(tmp), "--phase", "harvest",
                     "--slice", "a", "--minutes", "1", "--slice", "b", "--minutes", "2",
                     "--items", "10"])
        assert code == 2
        assert "one per slice or none" in capsys.readouterr().err


def test_a_corrupt_record_is_an_error_not_a_fresh_start() -> None:
    """Silently starting over would throw away the measurements the next dispatch is ordered by,
    and nothing would say so."""
    with tempfile.TemporaryDirectory() as tmp:
        record_path(make_repo(tmp)).write_text("{not json", encoding="utf-8")
        with pytest.raises(ValueError, match="not readable JSON"):
            load_runs(record_path(tmp))


def test_a_record_from_a_newer_version_is_refused() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        record_path(make_repo(tmp)).write_text(
            json.dumps({"version": VERSION + 1, "runs": []}), encoding="utf-8")
        with pytest.raises(ValueError, match="version"):
            load_runs(record_path(tmp))


def test_a_missing_record_is_empty_not_an_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        assert load_runs(record_path(make_repo(tmp))) == []


def test_show_json_round_trips_through_the_loader(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        main(["record", "--repo", make_repo(tmp), "--phase", "trace",
              "--slice", "checkout walk", "--minutes", "8.5", "--items", "12"])
        capsys.readouterr()
        assert main(["show", "--repo", tmp, "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["runs"] == [{"phase": "trace", "slice": "checkout walk",
                                    "minutes": 8.5, "items": 12}]


def test_the_record_lives_beside_the_map_and_never_inside_it() -> None:
    """Build telemetry, not map content. A wrong number here can make a build slower; it must never
    be able to make a map wrong."""
    with tempfile.TemporaryDirectory() as tmp:
        main(["record", "--repo", make_repo(tmp), "--phase", "harvest",
              "--slice", "deps", "--minutes", "3.2"])
        assert record_path(tmp).name == "fanout-timings.json"
        assert not Path(tmp, ".coyodex", "project-map.json").exists()


def test_an_unknown_verb_is_refused_with_the_usage(capsys) -> None:
    assert main(["ordre"]) == 2
    assert "unknown verb" in capsys.readouterr().err


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


# --- one process, one write, and no shell loop ------------------------------------------------
# The flags already repeat and pair by position, and three real builds still wrote
# `for s in "h11 t5-domain 15.6" ...; do set -- $s; timings record --slice "$2" --minutes "$3"; done`.
# The Bash tool runs zsh, where an unquoted `$s` does NOT word-split, so every call received empty
# arguments and exited 2. With `>/dev/null 2>&1` on the call and an unconditional success line after
# the loop, all 35 attempts across three fan-outs failed silently and the timings file was never
# created — so the next build's `timings order` had nothing to order by.

def _record_lines(tmp: Path, text: str, phase: str = "harvest") -> int:
    from coyodex.timings import main
    src = tmp / "t.txt"
    src.write_text(text, encoding="utf-8")
    return main(["record", "--repo", str(tmp), "--phase", phase, "--lines-from", str(src)])


def test_lines_from_records_a_whole_fan_out_in_one_call():
    import tempfile
    from coyodex.timings import latest_by_slice, load_runs, record_path
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        assert _record_lines(tmp, "h11 t5-domain-model 15.6\nh12 deps 11.9\nh4 auth 5.5\n") == 0
        ranked = latest_by_slice(load_runs(record_path(str(tmp))), "harvest")
    assert [r.slice for r in ranked] == ["h11 t5-domain-model", "h12 deps", "h4 auth"], ranked
    assert ranked[0].minutes == 15.6


def test_lines_from_skips_blanks_and_comments():
    import tempfile
    from coyodex.timings import latest_by_slice, load_runs, record_path
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _record_lines(tmp, "# what the barrier took\n\nh1 domain 9.0\n\n")
        ranked = latest_by_slice(load_runs(record_path(str(tmp))), "harvest")
    assert [r.slice for r in ranked] == ["h1 domain"], ranked


def test_lines_from_carries_an_item_count_when_one_is_given():
    import tempfile
    from coyodex.timings import latest_by_slice, load_runs, record_path
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        _record_lines(tmp, "h1 domain 9.0 12\n")
        ranked = latest_by_slice(load_runs(record_path(str(tmp))), "harvest")
    assert ranked[0].items == 12, ranked


def test_a_line_that_is_not_a_pair_is_refused_and_nothing_is_written():
    import tempfile
    from coyodex.timings import record_path
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rc = _record_lines(tmp, "h1 domain 9.0\njustaname\n")
        assert rc != 0, "a malformed line must be refused"
        assert not Path(record_path(str(tmp))).exists(), "a bad line in the batch writes nothing"
