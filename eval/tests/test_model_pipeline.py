#!/usr/bin/env python3
"""Eval-side tests for the schema-v2 model pipeline: the GOLDEN EQUIVALENCE (a real map's
markdown-pipeline profile == its JSON-pipeline profile), model-map support in score/claims/run,
and the judge-protocol fingerprint (recorded in judge.json; a mismatch fails the cache guard and
DRIFTs a comparison).

Run either way (needs an editable install: `make deps` + the eval package):
    python3 eval/tests/test_model_pipeline.py
    pytest eval/tests/test_model_pipeline.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex.convert_md import convert_text
from coyodex.model import to_canonical_json
from coyodex_eval.compare import compare
from coyodex_eval.judge import JudgeProtocol, JudgeReport, report_from_verdicts, rubric_fingerprint
from coyodex_eval.profile import build_profile, build_profile_from_model

FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "mcpolis-project-map.md"
EVAL = [sys.executable, "-m", "coyodex_eval.cli"]


# --- builders -------------------------------------------------------------------

def make_fixture_model_json() -> str:
    return to_canonical_json(convert_text(FIXTURE.read_text(encoding="utf-8")).model)


def make_verdicts(claims: list[str], grounded: bool = True) -> list[dict[str, object]]:
    return [{"claim": c, "grounded": grounded, "evidence": "x.py:1"} for c in claims for _ in range(3)]


def make_judge_report(rubric: str = "rubric v1", model: str = "sonnet") -> JudgeReport:
    return report_from_verdicts("# tiny map\n", Path("."), rubric, [], [{"faithfulness": 3}],
                                judge_model=model)


# --- the golden equivalence -------------------------------------------------------

def test_golden_md_profile_equals_json_profile():
    raw = FIXTURE.read_text(encoding="utf-8")
    p_md = build_profile(raw)
    p_json = build_profile(make_fixture_model_json())  # via the model-document sniff
    assert json.loads(p_md.to_json()) == json.loads(p_json.to_json())


def test_build_profile_from_model_matches_direct_path():
    m = convert_text(FIXTURE.read_text(encoding="utf-8")).model
    assert build_profile_from_model(m).to_json() == build_profile(make_fixture_model_json()).to_json()


# --- model maps through the CLI surfaces -------------------------------------------

def test_score_cli_accepts_model_map():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "project-map.json"
        p.write_text(make_fixture_model_json(), encoding="utf-8")
        proc = subprocess.run(EVAL + ["score", str(p), "--json"], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        profile = json.loads(proc.stdout)
        assert profile["components"] == 111 and profile["validate_ok"] is True


def test_claims_cli_accepts_model_map_with_v2_details():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "project-map.json"
        p.write_text(make_fixture_model_json(), encoding="utf-8")
        proc = subprocess.run(EVAL + ["claims", str(p), "--json", "--top", "40"],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        rows = json.loads(proc.stdout)
        assert len(rows) == 40
        assert any("entry points:" in r.get("detail", "") for r in rows)


def test_run_cli_archives_model_map_with_views():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "project-map.json"
        p.write_text(make_fixture_model_json(), encoding="utf-8")
        out = Path(td) / "run"
        proc = subprocess.run(EVAL + ["run", "--project", "demo", "--map", str(p),
                                      "--out", str(out)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert (out / "project-map.json").exists()
        assert (out / "project-map.md").exists()      # the generated view rides along
        assert (out / "profile.json").exists() and (out / "delta.md").exists()


# --- the judge-protocol fingerprint --------------------------------------------------

def test_report_from_verdicts_records_protocol():
    report = make_judge_report(rubric="rubric text v1", model="sonnet")
    assert report.protocol is not None
    assert report.protocol.model == "sonnet"
    assert report.protocol.rubric_sha == rubric_fingerprint("rubric text v1")
    again = JudgeReport.from_json(report.to_json())
    assert again.protocol == report.protocol


def test_protocol_cli_guards_the_baseline_cache():
    with tempfile.TemporaryDirectory() as td:
        rubric = Path(td) / "rubric.md"
        rubric.write_text("rubric text v1", encoding="utf-8")
        thresholds = Path(td) / "thresholds.json"
        thresholds.write_text(json.dumps(
            {"judge": {"grounding_model": "sonnet", "n_skeptics": 1, "grounding_cap": 40}}),
            encoding="utf-8")
        cached = Path(td) / "judge.json"
        report = report_from_verdicts("# tiny map\n", Path("."), "rubric text v1",
                                      [], [{"faithfulness": 3}], judge_model="sonnet")
        cached.write_text(report.to_json(), encoding="utf-8")
        base = EVAL + ["protocol", "--thresholds", str(thresholds), "--rubric", str(rubric),
                       "--against", str(cached)]
        assert subprocess.run(base, capture_output=True).returncode == 0  # same protocol → reusable
        rubric.write_text("rubric text v2 — reworded", encoding="utf-8")
        proc = subprocess.run(base, capture_output=True, text=True)
        assert proc.returncode == 1 and "MISMATCH" in proc.stdout


def test_protocol_cli_rejects_pre_fingerprint_cache():
    with tempfile.TemporaryDirectory() as td:
        rubric = Path(td) / "rubric.md"
        rubric.write_text("rubric", encoding="utf-8")
        thresholds = Path(td) / "thresholds.json"
        thresholds.write_text(json.dumps({"judge": {"grounding_model": "sonnet",
                                                    "n_skeptics": 1, "grounding_cap": 40}}),
                              encoding="utf-8")
        cached = Path(td) / "judge.json"
        old = JudgeReport(n_claims=1, n_grounded=1, grounding_passrate=1.0, dimensions=[],
                          overall=None)  # a pre-fingerprint report: protocol is None
        cached.write_text(old.to_json(), encoding="utf-8")
        proc = subprocess.run(EVAL + ["protocol", "--thresholds", str(thresholds),
                                      "--rubric", str(rubric), "--against", str(cached)],
                              capture_output=True, text=True)
        assert proc.returncode == 1 and "no fingerprint" in proc.stdout


def test_compare_drifts_on_protocol_mismatch():
    baseline = make_judge_report(rubric="rubric v1")
    candidate = make_judge_report(rubric="rubric v2 — reworded")
    profile = build_profile("# empty\n")
    report = compare(profile, profile, None, baseline, candidate)
    assert report.verdict == "DRIFT"
    assert any(j.metric == "judge_protocol_mismatch" and not j.within for j in report.judge_bands)
    same = compare(profile, profile, None, baseline, make_judge_report(rubric="rubric v1"))
    assert not any(j.metric == "judge_protocol_mismatch" for j in same.judge_bands)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    raise SystemExit(1 if failures else 0)
