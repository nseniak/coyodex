#!/usr/bin/env python3
"""Tests for the run orchestrator (deterministic half) — run_eval + archive + bless.

No live LLM: the judge is the injected `ScriptedJudge` from test_judge. Stdlib-only.
    python3 tests/test_run.py        # built-in runner
    pytest tests/test_run.py         # if pytest is installed
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex.eval.judge import JudgeReport
from coyodex.eval.profile import MapProfile, build_profile
from coyodex.eval.run import BASELINE, bless, load_baseline, run_eval, write_run
from test_judge import ScriptedJudge, make_l2_map

RUN = [sys.executable, "-m", "coyodex.cli", "eval", "run"]
BLESS = [sys.executable, "-m", "coyodex.cli", "eval", "bless"]


def make_map() -> str:
    """A small well-formed-enough map with the two L2 sources, so profile + judge both have content."""
    return (
        "## Use cases\n| ID | Use case | Actor | Trigger → Outcome |\n|---|---|---|---|\n"
        "| **UC1** | Admin action | Admin | a -> b |\n\n"
        + make_l2_map()
    )


# --- run_eval -------------------------------------------------------------------
def test_first_run_has_no_baseline_verdict() -> None:
    r = run_eval("p", make_map(), None)
    assert r.verdict == BASELINE and r.delta is None, r


def test_run_against_equal_baseline_passes() -> None:
    base = build_profile(make_map())
    r = run_eval("p", make_map(), None, baseline_profile=base)
    assert r.verdict == "PASS", r


def test_run_builds_judge_report_from_injected_judge() -> None:
    r = run_eval("p", make_map(), Path("."), judge=ScriptedJudge(), rubric="R", n_judges=1)
    assert r.judge is not None and r.judge.n_claims >= 1, r


def test_run_flags_a_judge_drop_as_drift() -> None:
    base_profile = build_profile(make_map())
    base_judge = run_eval("p", make_map(), Path("."), judge=ScriptedJudge(), rubric="R", n_judges=1).judge
    # candidate grounds fewer claims (refute the enforces edge) -> pass-rate drops
    r = run_eval("p", make_map(), Path("."), baseline_profile=base_profile, baseline_judge=base_judge,
                 judge=ScriptedJudge(refute_marker="enforces"), rubric="R", n_judges=1)
    assert r.verdict == "DRIFT", r


# --- persistence + bless --------------------------------------------------------
def test_write_run_then_load_and_bless_round_trip() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        run_dir, baseline_dir = root / "runs" / "p" / "ts", root / "baseline" / "p"
        r = run_eval("p", make_map(), Path("."), judge=ScriptedJudge(), rubric="R", n_judges=1)
        write_run(run_dir, r, make_map())
        assert (run_dir / "project-map.md").exists()
        assert (run_dir / "profile.json").exists()
        assert (run_dir / "judge.json").exists()
        assert (run_dir / "delta.md").exists()
        bless(run_dir, baseline_dir)
        bp, bj = load_baseline(baseline_dir)
        assert isinstance(bp, MapProfile) and isinstance(bj, JudgeReport)
        # the blessed baseline is what a next run compares against -> equal map -> PASS
        r2 = run_eval("p", make_map(), None, baseline_profile=bp)
        assert r2.verdict == "PASS", r2


def test_load_baseline_missing_is_none() -> None:
    with tempfile.TemporaryDirectory() as d:
        bp, bj = load_baseline(Path(d))
        assert bp is None and bj is None


# --- CLI ------------------------------------------------------------------------
def test_cli_run_first_then_bless_then_run_again() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        mp = root / "map.md"
        mp.write_text(make_map(), encoding="utf-8")
        run_dir, baseline_dir = root / "run1", root / "baseline"
        # first run: no baseline -> BASELINE, exit 0
        r1 = subprocess.run([*RUN, "--project", "p", "--map", str(mp), "--out", str(run_dir)],
                           capture_output=True, text=True)
        assert r1.returncode == 0 and "BASELINE" in r1.stdout, r1.stdout + r1.stderr
        # bless it
        rb = subprocess.run([*BLESS, str(run_dir), str(baseline_dir)], capture_output=True, text=True)
        assert rb.returncode == 0, rb.stdout + rb.stderr
        # second run vs the baseline (same map) -> PASS, exit 0
        r2 = subprocess.run([*RUN, "--project", "p", "--map", str(mp), "--baseline-dir", str(baseline_dir)],
                           capture_output=True, text=True)
        assert r2.returncode == 0 and "PASS" in r2.stdout, r2.stdout + r2.stderr


def test_cli_run_requires_project_and_map() -> None:
    r = subprocess.run([*RUN, "--project", "p"], capture_output=True, text=True)
    assert r.returncode == 2 and "required" in (r.stdout + r.stderr)


# --- built-in runner ------------------------------------------------------------
def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
