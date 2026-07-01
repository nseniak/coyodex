#!/usr/bin/env python3
"""Tests for `coyodex eval compare` — the relative regression gates over two MapProfiles.

Stdlib-only — no pytest required. Run either way (needs an editable install: `make deps`):
    python3 tests/test_compare.py        # built-in runner (prints pass/fail)
    pytest tests/test_compare.py         # if pytest is installed
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex.eval.compare import (DEFAULT_BANDS, DRIFT, PASS, REGRESSED, Thresholds, compare,
                                  load_thresholds)
from coyodex.eval.profile import MapProfile

COMPARE = [sys.executable, "-m", "coyodex.cli", "eval", "compare"]


# --- builders -------------------------------------------------------------------
def make_profile(**over: object) -> MapProfile:
    """A representative baseline profile; override any field to build a candidate that drifts."""
    base: dict[str, object] = dict(
        use_cases=10, subsystems=4, subdomains=3, components=20, deps=5, entities=15,
        edges=40, gp_steps=8, flows=10, security_surfaces=5,
        validate_ok=True, validate_problems=2, validate_warnings=1,
        contradictions=0, advisories=1, audit_warnings=0, l2_claims=6,
        coverage_flags=0,
        auth_surfaces=["a", "b", "c", "d", "e"], use_case_names=[], entity_names=[],
    )
    base.update(over)
    return MapProfile(**base)  # type: ignore[arg-type]


def _tight() -> Thresholds:
    """All hard gates on, no structural bands — so the tests isolate one axis at a time."""
    return Thresholds(bands={})


# --- identity -------------------------------------------------------------------
def test_identical_profiles_pass() -> None:
    p = make_profile()
    assert compare(p, p, _tight()).verdict == PASS


# --- hard gates (relative) ------------------------------------------------------
def test_new_validate_problem_regresses() -> None:
    r = compare(make_profile(validate_problems=2), make_profile(validate_problems=3), _tight())
    assert r.verdict == REGRESSED, r
    assert any(g.name == "validate-no-regress" and not g.passed for g in r.gates)


def test_fewer_validate_problems_is_fine() -> None:
    """A baseline that carried problems, improved — the RELATIVE gate must not punish getting better."""
    r = compare(make_profile(validate_problems=2), make_profile(validate_problems=0), _tight())
    assert r.verdict == PASS, r


def test_new_contradiction_regresses() -> None:
    r = compare(make_profile(contradictions=0), make_profile(contradictions=1), _tight())
    assert r.verdict == REGRESSED, r
    assert any(g.name == "no-new-contradictions" and not g.passed for g in r.gates)


def test_coverage_flag_increase_regresses() -> None:
    r = compare(make_profile(coverage_flags=0), make_profile(coverage_flags=1), _tight())
    assert r.verdict == REGRESSED, r


def test_coverage_gate_skipped_when_a_side_has_no_repo() -> None:
    r = compare(make_profile(coverage_flags=None), make_profile(coverage_flags=3), _tight())
    assert r.verdict == PASS, r
    assert any("coverage gate skipped" in n for n in r.notes), r.notes
    assert not any(g.name == "coverage-no-regress" for g in r.gates)


def test_auth_surface_count_drop_regresses() -> None:
    r = compare(make_profile(security_surfaces=5), make_profile(security_surfaces=4), _tight())
    assert r.verdict == REGRESSED, r
    assert any(g.name == "auth-surfaces-no-drop" and not g.passed for g in r.gates)


def test_auth_surface_name_drift_is_a_note_not_a_gate() -> None:
    """Same count, different names — the count gate passes; the renamed surface is only a note."""
    base = make_profile(security_surfaces=2, auth_surfaces=["/mcp gateway", "/admin"])
    cand = make_profile(security_surfaces=2, auth_surfaces=["MCP gateway endpoint", "/admin"])
    r = compare(base, cand, _tight())
    assert r.verdict == PASS, r
    assert any("names drift" in n for n in r.notes), r.notes


def test_disabling_a_gate_is_honored() -> None:
    r = compare(make_profile(contradictions=0), make_profile(contradictions=2),
                Thresholds(no_new_contradictions=False, bands={}))
    assert r.verdict == PASS, r


# --- bands (soft drift) ---------------------------------------------------------
def test_entities_within_band_pass() -> None:
    t = Thresholds(bands={"entities_pct": 0.20})
    r = compare(make_profile(entities=15), make_profile(entities=13), t)  # -13%, within 20%
    assert r.verdict == PASS, r


def test_entities_beyond_band_drift() -> None:
    t = Thresholds(bands={"entities_pct": 0.20})
    r = compare(make_profile(entities=15), make_profile(entities=9), t)   # -40%, beyond 20%
    assert r.verdict == DRIFT, r
    assert any(b.metric == "entities" and not b.within for b in r.bands)


def test_hard_fail_dominates_a_band_breach() -> None:
    """A hard gate trip outranks any band breach — verdict is REGRESSED, not DRIFT."""
    t = Thresholds(bands={"entities_pct": 0.20})
    r = compare(make_profile(entities=15, contradictions=0),
                make_profile(entities=9, contradictions=1), t)
    assert r.verdict == REGRESSED, r


def test_nonexistent_band_metric_is_noted_not_crashed() -> None:
    r = compare(make_profile(), make_profile(), Thresholds(bands={"nonsense_pct": 0.1}))
    assert r.verdict == PASS
    assert any("not a numeric profile metric" in n for n in r.notes), r.notes


# --- thresholds loading ---------------------------------------------------------
def test_per_project_overrides_global() -> None:
    cfg = {
        "global": {"hard_gates": {"no_new_contradictions": True}, "bands": {"entities_pct": 0.30}},
        "per_project": {"mcpolis": {"hard_gates": {"no_new_contradictions": False}}},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(json.dumps(cfg))
        path = Path(f.name)
    glob = load_thresholds(path)
    proj = load_thresholds(path, "mcpolis")
    assert glob.no_new_contradictions is True
    assert proj.no_new_contradictions is False
    assert proj.bands["entities_pct"] == 0.30   # global band value carried to the project
    assert "components_pct" in proj.bands       # a default band NOT dropped by the partial override


def test_partial_bands_override_keeps_defaults() -> None:
    """Review Finding 2: tightening ONE band must not disable the others (bands merge, not replace)."""
    t = Thresholds.from_config({"global": {"bands": {"components_pct": 0.05}}})
    assert t.bands["components_pct"] == 0.05
    assert t.bands["entities_pct"] == DEFAULT_BANDS["entities_pct"]  # still present at its default
    assert set(t.bands) >= set(DEFAULT_BANDS)


def test_every_structural_count_has_a_band() -> None:
    """Review Finding 3: every count-like metric is banded, so a collapse can't pass silently."""
    for metric in ("use_cases", "subsystems", "subdomains", "components", "deps", "entities",
                   "edges", "gp_steps", "flows", "l2_claims"):
        assert f"{metric}_pct" in DEFAULT_BANDS, metric


def test_deps_collapse_drifts_under_default_thresholds() -> None:
    """A previously-ungated metric (deps) now drifts when it collapses (review Finding 3)."""
    r = compare(make_profile(deps=10), make_profile(deps=1))  # default Thresholds now band deps
    assert r.verdict == DRIFT, r
    assert any(b.metric == "deps" and not b.within for b in r.bands)


# --- CLI ------------------------------------------------------------------------
def _write(p: MapProfile) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(p.to_json())
        return f.name


def test_cli_pass_exits_zero() -> None:
    r = subprocess.run([*COMPARE, _write(make_profile()), _write(make_profile())],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


def test_cli_regressed_exits_one() -> None:
    r = subprocess.run([*COMPARE, _write(make_profile(contradictions=0)),
                        _write(make_profile(contradictions=1))], capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REGRESSED" in r.stdout


def test_cli_drift_exits_two() -> None:
    r = subprocess.run([*COMPARE, _write(make_profile(entities=15)),
                        _write(make_profile(entities=9))], capture_output=True, text=True)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "DRIFT" in r.stdout


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
