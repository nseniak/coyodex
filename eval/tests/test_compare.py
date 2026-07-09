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

from coyodex_eval.compare import (DEFAULT_BANDS, DRIFT, PASS, REGRESSED, Thresholds, compare,
                                  format_report, load_thresholds)
from coyodex_eval.judge import DimensionScore, JudgeReport
from coyodex_eval.profile import MapProfile

COMPARE = [sys.executable, "-m", "coyodex_eval.cli", "compare"]


# --- builders -------------------------------------------------------------------
def make_profile(**over: object) -> MapProfile:
    """A representative baseline profile; override any field to build a candidate that drifts."""
    base: dict[str, object] = dict(
        use_cases=10, subsystems=4, subdomains=3, components=20, deps=5, entities=15,
        edges=40, hp_steps=8, flows=10, security_surfaces=5,
        validate_ok=True, validate_problems=2, validate_warnings=1,
        contradictions=0, advisories=1, audit_warnings=0, l2_claims=6,
        coverage_flags=0, edges_per_component=2.0,
        auth_surfaces=["a", "b", "c", "d", "e"], use_case_names=[], entity_names=[],
    )
    base.update(over)
    return MapProfile(**base)  # type: ignore[arg-type]


def make_judge(passrate: float = 1.0, overall: float = 3.0,
               dims: list[DimensionScore] | None = None, n_failures: int = 0) -> JudgeReport:
    """A representative JudgeReport; override pass-rate / overall / dimensions / failures to build a
    drifting one. The pass-rate is over the surviving denominator (n_claims - n_failures)."""
    if dims is None:
        dims = [DimensionScore("faithfulness", 3.0, 3), DimensionScore("completeness", 3.0, 3)]
    denom = 10 - n_failures
    return JudgeReport(n_claims=10, n_grounded=int(round(passrate * denom)),
                       grounding_passrate=passrate if denom else None,
                       dimensions=dims, overall=overall, n_worklist=10, n_failures=n_failures)


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


# --- judge bands (drop-only, soft DRIFT) ----------------------------------------
def test_judge_passrate_drop_beyond_allowance_drifts() -> None:
    r = compare(make_profile(), make_profile(), None, make_judge(passrate=0.9), make_judge(passrate=0.7))
    assert r.verdict == DRIFT, r
    assert any(j.metric == "grounding_passrate" and not j.within for j in r.judge_bands)


def test_judge_passrate_small_drop_is_within() -> None:
    r = compare(make_profile(), make_profile(), None, make_judge(passrate=0.9), make_judge(passrate=0.85))
    assert r.verdict == PASS, r


def test_judge_score_rise_is_never_a_drift() -> None:
    """Judge bands are drop-only — a higher score is good, not drift."""
    r = compare(make_profile(), make_profile(), None, make_judge(overall=3.0), make_judge(overall=3.9))
    assert r.verdict == PASS, r


def test_dimension_score_drop_drifts() -> None:
    base = make_judge(dims=[DimensionScore("faithfulness", 4.0, 3)])
    cand = make_judge(dims=[DimensionScore("faithfulness", 3.0, 3)])
    r = compare(make_profile(), make_profile(), None, base, cand)
    assert r.verdict == DRIFT, r
    assert any(j.metric == "dim:faithfulness" and not j.within for j in r.judge_bands)


def test_missing_candidate_judge_is_a_drift_not_a_skip() -> None:
    """Review-2 Finding 3: a judged baseline vs an UNJUDGED candidate must not PASS — skipping the
    semantic gates is the escape hatch an unjudged (or judge-crashed) run would take."""
    r = compare(make_profile(), make_profile(), None, make_judge(), None)
    assert r.verdict == DRIFT, r
    assert any(j.metric == "judge_report_missing" and not j.within for j in r.judge_bands), r.judge_bands
    assert any("NO judge report" in n for n in r.notes), r.notes


def test_missing_baseline_judge_is_noted_and_skipped() -> None:
    """The reverse one-sided case is harmless: there is nothing to compare the candidate's judge
    against, so it is a note, not a penalty."""
    r = compare(make_profile(), make_profile(), None, None, make_judge())
    assert r.verdict == PASS, r
    assert not r.judge_bands
    assert any("only one side" in n for n in r.notes), r.notes


def test_grounding_failure_flood_is_a_drift() -> None:
    """Review-2 Finding 2: a candidate whose grounding mostly FAILED (no usable verdicts) must not
    PASS just because the pass-rate over the surviving denominator looks fine."""
    r = compare(make_profile(), make_profile(), None,
                make_judge(passrate=1.0), make_judge(passrate=1.0, n_failures=5))  # 50% failure rate
    assert r.verdict == DRIFT, r
    assert any(j.metric == "grounding_failure_rate" and not j.within for j in r.judge_bands), r.judge_bands


def test_small_grounding_failure_rate_is_within() -> None:
    r = compare(make_profile(), make_profile(), None,
                make_judge(passrate=1.0), make_judge(passrate=1.0, n_failures=2))  # 20% <= 25% cap
    assert r.verdict == PASS, r


def test_hard_fail_dominates_a_judge_drift() -> None:
    r = compare(make_profile(contradictions=0), make_profile(contradictions=1),
                None, make_judge(passrate=0.9), make_judge(passrate=0.4))
    assert r.verdict == REGRESSED, r


def test_report_leads_with_the_judge_deltas() -> None:
    """P1: the formatted report puts judge/quality deltas first; raw structural bands come last."""
    r = compare(make_profile(), make_profile(entities=9), None, make_judge(), make_judge())
    text = format_report(r)
    assert text.index("Judge bands") < text.index("Hard gates") < text.index("Bands"), text


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
    assert proj.bands["entities_pct"] == 0.30       # global band value carried to the project
    assert "components_shrink_pct" in proj.bands    # a default band NOT dropped by the partial override


def test_partial_bands_override_keeps_defaults() -> None:
    """Review Finding 2: tightening ONE band must not disable the others (bands merge, not replace)."""
    t = Thresholds.from_config({"global": {"bands": {"components_pct": 0.05}}})
    assert t.bands["components_pct"] == 0.05
    assert t.bands["entities_shrink_pct"] == DEFAULT_BANDS["entities_shrink_pct"]  # still at its default
    assert set(t.bands) >= set(DEFAULT_BANDS)


def test_every_structural_count_has_a_band() -> None:
    """Review Finding 3: every count-like metric keeps a (shrink-only, collapse-detector) band, so a
    collapse can't pass silently. `l2_claims` is the deliberate exception (P1): the worklist derives
    from edges + auth rows, so banding it double-jeopardizes movement those signals already catch."""
    for metric in ("use_cases", "subsystems", "subdomains", "components", "deps", "entities",
                   "edges", "hp_steps", "flows"):
        assert f"{metric}_shrink_pct" in DEFAULT_BANDS, metric
    assert "l2_claims_pct" not in DEFAULT_BANDS and "l2_claims_shrink_pct" not in DEFAULT_BANDS
    assert "edges_per_component_pct" in DEFAULT_BANDS


def test_deps_collapse_drifts_under_default_thresholds() -> None:
    """A previously-ungated metric (deps) now drifts when it collapses (review Finding 3)."""
    r = compare(make_profile(deps=10), make_profile(deps=1))  # default Thresholds now band deps
    assert r.verdict == DRIFT, r
    assert any(b.metric == "deps" and not b.within for b in r.bands)


# --- density bands (P1): scale-invariant drift, counts as collapse detectors -----
def test_finer_but_better_map_with_steady_density_passes() -> None:
    """The motivating P1 case: a rebuild that maps FINER (more components, proportionally more edges)
    keeps edges-per-component steady and must NOT trip DRIFT under the default thresholds."""
    base = make_profile(components=20, edges=40, edges_per_component=2.0)
    cand = make_profile(components=28, edges=56, edges_per_component=2.0)
    r = compare(base, cand)
    assert r.verdict == PASS, r


def test_density_collapse_drifts_even_when_raw_counts_hold() -> None:
    """Same component count but a thinner backbone: the edge shrink (-27.5%) stays inside the 30%
    shrink band, and the tight density band is what catches it."""
    base = make_profile(components=20, edges=40, edges_per_component=2.0)
    cand = make_profile(components=20, edges=29, edges_per_component=1.45)  # -27.5% density
    r = compare(base, cand)
    assert r.verdict == DRIFT, r
    assert any(b.metric == "edges_per_component" and not b.within for b in r.bands)
    assert any(b.metric == "edges" and b.within for b in r.bands), r.bands


def test_exactly_halved_map_with_steady_density_drifts() -> None:
    """Review-2 Finding 1: a proportionally HALVED map keeps density steady — the shrink-only count
    bands are what refuse it (a symmetric ±50% band waved exactly this through)."""
    base = make_profile(components=20, edges=40, edges_per_component=2.0)
    cand = make_profile(components=10, edges=20, edges_per_component=2.0)
    r = compare(base, cand)
    assert r.verdict == DRIFT, r
    assert any(b.metric == "components" and not b.within for b in r.bands)


def test_count_growth_never_trips_a_shrink_band() -> None:
    """Counts are shrink-only: tripling the components with steady density is a (much) finer map, and
    whether that fineness is right is the altitude rubric's call — not a count band's."""
    base = make_profile(components=20, edges=40, edges_per_component=2.0)
    cand = make_profile(components=60, edges=120, edges_per_component=2.0)
    assert compare(base, cand).verdict == PASS


def test_baseline_without_the_density_field_is_skipped_not_crashed() -> None:
    """A baseline profile.json written before edges_per_component existed loads as None — the band is
    skipped with a note, never crashed on or treated as 0."""
    r = compare(make_profile(edges_per_component=None), make_profile())
    assert r.verdict == PASS, r
    assert any("edges_per_component" in n and "skipped" in n for n in r.notes), r.notes


# --- granularity (candidate vs the code-derived expectation E — the leaf anchor) --
def test_granularity_candidate_below_band_drifts() -> None:
    """The mcpolis failure mode: an honest rebuild lands far COARSER than the code-derived E."""
    base = make_profile(components=20, granularity_expected=20)
    cand = make_profile(components=10, granularity_expected=20)  # -50% vs E, band is ±40%
    r = compare(base, cand, _tight())
    assert r.verdict == DRIFT, r
    assert r.granularity is not None and not r.granularity.within, r.granularity


def test_granularity_candidate_above_band_drifts() -> None:
    base = make_profile(components=20, granularity_expected=20)
    cand = make_profile(components=30, granularity_expected=20)  # +50% vs E
    r = compare(base, cand, _tight())
    assert r.verdict == DRIFT, r


def test_granularity_within_band_passes() -> None:
    base = make_profile(components=20, granularity_expected=20)
    cand = make_profile(components=25, granularity_expected=20)  # +25%, inside ±40%
    r = compare(base, cand, _tight())
    assert r.verdict == PASS, r
    assert r.granularity is not None and r.granularity.within


def test_granularity_gates_the_candidate_never_the_baseline() -> None:
    """Both maps' distance to the same E is reported, but a baseline whose own zoom is off must not
    trip the verdict — E-relative is fairer than baseline-relative exactly because of this case.
    (Count bands are off here: the point is the E-band's own behavior.)"""
    base = make_profile(components=45, granularity_expected=20)   # baseline way off (+125%)
    cand = make_profile(components=22, granularity_expected=20)   # candidate in band
    r = compare(base, cand, _tight())
    assert r.verdict == PASS, r
    assert r.granularity is not None
    assert r.granularity.baseline_delta_pct > 1.0 and r.granularity.within, r.granularity


def test_granularity_skipped_with_a_note_when_no_profile_carries_e() -> None:
    r = compare(make_profile(), make_profile(), _tight())  # granularity_expected defaults to None
    assert r.verdict == PASS, r
    assert r.granularity is None
    assert any("granularity band skipped" in n for n in r.notes), r.notes


def test_granularity_prefers_the_candidate_e_and_notes_a_mismatch() -> None:
    """Both sides score the same pinned tree, so their E should agree; if they don't (the tree
    changed between scorings), the candidate's fresher E gates and the mismatch is surfaced."""
    base = make_profile(components=20, granularity_expected=15)
    cand = make_profile(components=20, granularity_expected=20)
    r = compare(base, cand, _tight())
    assert r.granularity is not None and r.granularity.expected == 20, r.granularity
    assert any("expectation differs" in n for n in r.notes), r.notes


def test_granularity_band_pct_merges_from_config() -> None:
    cfg = {
        "global": {"granularity_band_pct": 0.10},
        "per_project": {"mcpolis": {"granularity_band_pct": 0.60}},
    }
    glob = Thresholds.from_config(cfg)
    proj = Thresholds.from_config(cfg, "mcpolis")
    assert glob.granularity_band_pct == 0.10
    assert proj.granularity_band_pct == 0.60
    assert Thresholds.from_config({}).granularity_band_pct == 0.40  # the built-in default


def test_report_shows_both_maps_distance_to_e_and_leads_the_counts() -> None:
    """The formatted report carries a Granularity section with BOTH distances, placed before the
    baseline-relative count bands (the E-comparison leads for counts)."""
    base = make_profile(components=45, granularity_expected=20)
    cand = make_profile(components=10, granularity_expected=20)
    text = format_report(compare(base, cand, _tight()))
    assert "Granularity" in text and "candidate: 10 vs E 20" in text \
        and "baseline : 45 vs E 20" in text, text
    r = compare(base, cand)  # default bands on → a Bands section exists to order against
    text = format_report(r)
    assert text.index("Granularity") < text.index("Bands (drift vs baseline)"), text


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
    # entities -67%: past even the wide collapse-detector band (±50%)
    r = subprocess.run([*COMPARE, _write(make_profile(entities=15)),
                        _write(make_profile(entities=5))], capture_output=True, text=True)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "DRIFT" in r.stdout


def _write_judge(j: JudgeReport) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(j.to_json())
        return f.name


def test_cli_applies_judge_reports() -> None:
    r = subprocess.run([*COMPARE, _write(make_profile()), _write(make_profile()),
                        "--baseline-judge", _write_judge(make_judge(passrate=0.9)),
                        "--candidate-judge", _write_judge(make_judge(passrate=0.5))],
                       capture_output=True, text=True)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "Judge bands" in r.stdout and "DRIFT" in r.stdout


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
