#!/usr/bin/env python3
"""`coyodex-eval run` / `coyodex-eval bless` — the run orchestrator (deterministic half).

One eval run of a built map: profile it, optionally attach a judge report, compare against the blessed
baseline, and archive everything to a run directory. `bless` promotes a run to the baseline.

This module is DETERMINISTIC and stdlib-only. It never builds a map and never calls a model: the map
is built by the method (an agent) and handed in; the judge report is either pre-computed (a JSON file
the orchestrator's sub-agents produced) or built here from an INJECTED `Judge` (real one from the
orchestrator, fake one in tests). So the whole pipeline is testable without an LLM.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from coyodex.model import is_model_document
from coyodex_eval.compare import DeltaReport, Thresholds, compare, format_report, load_thresholds
from coyodex_eval.judge import (
    GROUNDING_PROMPT_VERSION,
    Judge,
    JudgeProtocol,
    JudgeReport,
    build_judge_report,
    report_from_verdicts,
    rubric_fingerprint,
)
from coyodex_eval.profile import MapProfile, build_profile

BASELINE = "BASELINE"  # the "verdict" of a run with no baseline yet (it can become one via `bless`)
_EXIT = {"PASS": 0, "REGRESSED": 1, "DRIFT": 2, BASELINE: 0}


def map_sha256(path: Path) -> str:
    """The freeze hash of a map artifact (sha256 of the file bytes). The build step writes it to
    `runs/<ts>/map-hash` via `coyodex-eval hash`; `run --expect-map-hash` recomputes it and hard-fails
    on mismatch — any post-freeze edit invalidates the run."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class RunResult:
    project: str
    profile: MapProfile
    judge: JudgeReport | None
    delta: DeltaReport | None     # None when there is no baseline yet
    verdict: str                  # PASS | DRIFT | REGRESSED | BASELINE


def run_eval(project: str, map_text: str, repo_root: Path | None = None, *,
             thresholds: Thresholds | None = None,
             baseline_profile: MapProfile | None = None, baseline_judge: JudgeReport | None = None,
             judge_report: JudgeReport | None = None, judge: Judge | None = None,
             rubric: str | None = None, n_judges: int = 3) -> RunResult:
    """Profile the map, attach a judge report (pre-computed `judge_report`, else built from an injected
    `judge`+`rubric`), and compare against the baseline if one is given. No baseline → verdict BASELINE."""
    profile = build_profile(map_text, repo_root=repo_root)
    jr = judge_report
    if jr is None and judge is not None and rubric is not None:
        jr = build_judge_report(map_text, repo_root or Path("."), rubric, judge, n_judges)
    delta: DeltaReport | None = None
    verdict = BASELINE
    if baseline_profile is not None:
        delta = compare(baseline_profile, profile, thresholds, baseline_judge, jr)
        verdict = delta.verdict
    return RunResult(project, profile, jr, delta, verdict)


# ── persistence (the coyodex-tests workspace side) ─────────────────────────────────────────────────

def load_baseline(baseline_dir: Path) -> tuple[MapProfile | None, JudgeReport | None]:
    """Read `profile.json` / `judge.json` from a baseline dir; each is None when absent (first run)."""
    prof_p, judge_p = baseline_dir / "profile.json", baseline_dir / "judge.json"
    prof = MapProfile.from_json(prof_p.read_text(encoding="utf-8")) if prof_p.exists() else None
    judge = JudgeReport.from_json(judge_p.read_text(encoding="utf-8")) if judge_p.exists() else None
    return prof, judge


def delta_md(result: RunResult) -> str:
    # The judge (semantic quality) leads; raw structural counts follow — the counts are the noisier,
    # less meaningful signal, so they must not headline the report.
    p = result.profile
    lines = [
        f"# Eval run — {result.project}", "",
        f"Verdict: **{result.verdict}**", "",
    ]
    if result.judge is not None:
        j = result.judge
        denom = j.n_claims - j.n_failures
        pr = "n/a" if j.grounding_passrate is None else f"{j.grounding_passrate:.0%}"
        lines += ["## Judge", "```",
                  f"grounding : {j.n_grounded}/{denom} claims ({pr}) — top {j.n_claims} of "
                  f"{j.n_worklist} risk-ranked claim(s), {j.n_failures} judge failure(s) excluded",
                  f"rubric    : " + " · ".join(f"{d.dimension} {d.score:g}" for d in j.dimensions)
                  + (f"  (overall {j.overall:g})" if j.overall is not None else ""),
                  "```", ""]
    lines += [
        "## Profile", "```",
        f"structure : UC {p.use_cases} · S {p.subsystems} · SD {p.subdomains} · C {p.components} "
        f"· D {p.deps} · E {p.entities} · edges {p.edges} · GP {p.gp_steps} · flows {p.flows} "
        f"· auth {p.security_surfaces}",
        f"validate  : {'OK' if p.validate_ok else f'{p.validate_problems} problem(s)'}, "
        f"{p.validate_warnings} warning(s)",
        f"audit     : {p.contradictions} contradiction(s) · {p.advisories} advisory · {p.l2_claims} L2 claim(s)",
        f"coverage  : {'n/a' if p.coverage_flags is None else p.coverage_flags} flag(s)",
        "```", "",
    ]
    if result.delta is not None:
        lines += ["## Comparison vs baseline", "```", format_report(result.delta), "```"]
    else:
        lines += ["_No baseline yet — `coyodex-eval bless` this run to establish one._"]
    return "\n".join(lines) + "\n"


def render_html(map_path: Path, html_path: Path) -> None:
    """Render the map to a self-contained HTML view next to its source, so each run keeps its OWN
    viewable diagram (the live `.coyodex/project-map.html` in the clone is overwritten every rebuild).
    Best-effort: a render hiccup warns but never loses the already-written source / profile / delta."""
    try:
        from coyodex.model import load_model
        from coyodex.viewer.gen_viewer import write_html
        from coyodex.views import model_to_graph
        write_html(model_to_graph(load_model(map_path.read_text(encoding="utf-8"))),
                   html_path, None)
    except Exception as e:  # archiving must survive a render failure
        print(f"WARNING: could not render {html_path.name}: {e}", file=sys.stderr)


# Everything a run/baseline dir holds, in write order. A run stores project-map.json (the source)
# + its generated md view; project-map.html is rendered (not copied) at write time; bless copies
# whichever of these exist (a pre-migration legacy run dir may still hold project-map.md only).
_RUN_ARTIFACTS = ("project-map.json", "project-map.md", "project-map.html", "profile.json",
                  "judge.json", "delta.md")


def write_run(out_dir: Path, result: RunResult, map_text: str,
              conversation_src: Path | None = None) -> None:
    """Archive a run: the model, its generated md + HTML views, profile.json, judge.json (if any),
    delta.md, and the build conversation (if the orchestrator captured one). The historical record
    a baseline is blessed from — the views are archived so a past run stays viewable after a later
    rebuild. Model documents only (run_eval's profiling already refused anything else)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    map_path = out_dir / "project-map.json"
    map_path.write_text(map_text, encoding="utf-8")
    try:  # the generated md view rides along, like the HTML — best-effort, never blocks archiving
        from coyodex.model import load_model
        from coyodex.views import model_to_markdown
        (out_dir / "project-map.md").write_text(
            model_to_markdown(load_model(map_text)), encoding="utf-8")
    except Exception as e:
        print(f"WARNING: could not write the md view: {e}", file=sys.stderr)
    (out_dir / "profile.json").write_text(result.profile.to_json(), encoding="utf-8")
    if result.judge is not None:
        (out_dir / "judge.json").write_text(result.judge.to_json(), encoding="utf-8")
    (out_dir / "delta.md").write_text(delta_md(result), encoding="utf-8")
    render_html(map_path, out_dir / "project-map.html")
    if conversation_src is not None and conversation_src.exists():
        shutil.copytree(conversation_src, out_dir / "conversation", dirs_exist_ok=True)


def bless(run_dir: Path, baseline_dir: Path) -> None:
    """Promote a run to the baseline: copy its map + rendered view + profile.json + judge.json + delta
    into the baseline dir (whichever exist)."""
    baseline_dir.mkdir(parents=True, exist_ok=True)
    for name in _RUN_ARTIFACTS:
        src = run_dir / name
        if src.exists():
            shutil.copy2(src, baseline_dir / name)


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────────

def _opt(argv: list[str], name: str) -> str | None:
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None


def run_cli(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex-eval run --project <name> --map <project-map.json> [--repo <root>]\n"
              "       [--expect-map-hash <sha256>] [--judge <judge.json>] [--baseline-dir <dir>]\n"
              "       [--thresholds <file>] [--project-key <name>] [--out <run-dir>] [--json]\n\n"
              "Profile a built map, attach a pre-computed judge report, compare vs the baseline, and\n"
              "archive to --out. --expect-map-hash is the freeze guard: the run REFUSES if the map on\n"
              "disk no longer matches the hash written at build time (any post-build edit invalidates\n"
              "the run). Exit: 0 PASS/BASELINE · 2 DRIFT · 1 REGRESSED.")
        return 0
    project = _opt(argv, "--project")
    map_arg = _opt(argv, "--map")
    if not project or not map_arg:
        print("ERROR: --project and --map are required", file=sys.stderr)
        return 2
    map_path = Path(map_arg)
    if not map_path.exists():
        print(f"ERROR: {map_path} not found", file=sys.stderr)
        return 1
    if "--expect-map-hash" in argv:
        expected = _opt(argv, "--expect-map-hash")
        if expected is None or not expected.strip():
            # Fail CLOSED: a flag that lost its value (bad quoting, empty map-hash file) must never
            # silently skip the freeze guard the caller believes is active.
            print("ERROR: --expect-map-hash needs a value (the sha256 from runs/<ts>/map-hash)",
                  file=sys.stderr)
            return 2
        actual = map_sha256(map_path)
        if actual != expected.strip():
            print(f"ERROR: map hash mismatch — {map_path} was modified after freeze.\n"
                  f"  expected {expected.strip()}\n  actual   {actual}\n"
                  "Refusing to score an edited artifact; rebuild and re-freeze the map.",
                  file=sys.stderr)
            return 1
    repo = _opt(argv, "--repo")
    repo_root = Path(repo) if repo else None
    if repo_root is not None and not repo_root.exists():
        print(f"ERROR: --repo {repo_root} not found", file=sys.stderr)
        return 1

    judge_report: JudgeReport | None = None
    if (jp := _opt(argv, "--judge")) is not None:
        judge_report = JudgeReport.from_json(Path(jp).read_text(encoding="utf-8"))

    baseline_profile = baseline_judge = None
    if (bd := _opt(argv, "--baseline-dir")) is not None and Path(bd).exists():
        baseline_profile, baseline_judge = load_baseline(Path(bd))

    thresholds: Thresholds | None = None
    if (tp := _opt(argv, "--thresholds")) is not None:
        thresholds = load_thresholds(Path(tp), _opt(argv, "--project-key") or project)

    from coyodex.model import ModelError
    try:
        result = run_eval(project, map_path.read_text(encoding="utf-8"), repo_root,
                          thresholds=thresholds, baseline_profile=baseline_profile,
                          baseline_judge=baseline_judge, judge_report=judge_report)
    except ModelError as e:
        print(f"ERROR: {map_path}: {e}", file=sys.stderr)
        return 1

    if (out := _opt(argv, "--out")) is not None:
        write_run(Path(out), result, map_path.read_text(encoding="utf-8"))
    if "--json" in argv:
        print(json.dumps({"project": result.project, "verdict": result.verdict,
                          "profile": json.loads(result.profile.to_json()),
                          "delta": json.loads(result.delta.to_json()) if result.delta else None},
                         indent=2, sort_keys=True))
    else:
        print(delta_md(result))
    return _EXIT[result.verdict]


def claims_cli(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex-eval claims [<project-map.json>] [--top <K>] [--json]\n\n"
              "Print the audit's L2 worklist — the high-risk 'actually-does' claims a judge should "
              "ground against the code, risk-ranked most-dangerous first. `--top K` keeps only the "
              "first K (the grounding sample; the eval grounds top-K, not the whole list). `--json` "
              "emits [{claim, anchor, detail?}], the input the judge orchestration fans out over.")
        return 0
    # Consume --top's value by INDEX, never by string equality — a positional map path that happens to
    # equal the K value (a file named `40`) must not be swallowed with it.
    top: int | None = None
    json_out = False
    positional: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--top":
            i += 1
            if i >= len(argv):
                print("ERROR: --top needs a value", file=sys.stderr)
                return 2
            try:
                top = int(argv[i])
            except ValueError:
                print(f"ERROR: --top needs an integer, got '{argv[i]}'", file=sys.stderr)
                return 2
            if top < 0:
                print(f"ERROR: --top needs a non-negative integer, got {top}", file=sys.stderr)
                return 2
        elif a == "--json":
            json_out = True
        elif a.startswith("-"):
            print(f"ERROR: unknown option '{a}'", file=sys.stderr)
            return 2
        else:
            positional.append(a)
        i += 1
    path = Path(positional[0] if positional else ".coyodex/project-map.json")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    if not is_model_document(text):
        print(f"ERROR: {path} is not a schema-v2 model document — markdown maps are not "
              "supported; claims are read from project-map.json", file=sys.stderr)
        return 1
    from coyodex import audit_model
    from coyodex.model import load_model
    items = audit_model.l2_worklist_model(load_model(text))
    if top is not None:
        items = items[:top]
    if json_out:
        # `detail` is the self-describing name+file context Phase-1A adds to WorkItem; emitted when
        # present so grounding never needs to resolve ids against a map file (see method.md Step 4).
        rows = [{"claim": w.claim, "anchor": w.anchor,
                 **({"detail": d} if (d := getattr(w, "detail", None)) else {})} for w in items]
        print(json.dumps(rows, indent=2))
    else:
        for i, w in enumerate(items, 1):
            print(f"{i}. {w.claim}" + (f"  [{w.anchor}]" if w.anchor else ""))
    return 0


def hash_cli(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv or not argv:
        print("usage: coyodex-eval hash <file>\n\n"
              "Print the sha256 freeze hash of an artifact. The build step writes it:\n"
              "  coyodex-eval hash runs/<ts>/project-map.md > runs/<ts>/map-hash\n"
              "and `coyodex-eval run --expect-map-hash \"$(cat .../map-hash)\"` enforces it.")
        return 0 if ("-h" in argv or "--help" in argv) else 2
    path = Path(argv[0])
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    print(map_sha256(path))
    return 0


def judge_cli(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex-eval judge --map <project-map.json> --verdicts <raw.json> --out <judge.json>\n"
              "       [--repo <root>] [--rubric <file>] [--judge-model <name>]\n\n"
              "Aggregate externally-produced judge verdicts — grounding [{claim, grounded, evidence}]\n"
              "with grounded one of true / false / \"unverifiable\" (a could-not-verify vote counts\n"
              "as a judge FAILURE: excluded from the pass-rate denominator, never scored refuted) —\n"
              "and per-judge rubric scores — into a JudgeReport, via the tested PrecomputedJudge path.\n"
              "The orchestration layer (a workflow / sub-agents) does the real judging and writes the\n"
              "raw JSON; this turns it into judge.json with the same pass-rate + median math.\n"
              "--judge-model records the pinned model in the report's judge-protocol fingerprint\n"
              "(model + n_skeptics + grounding_cap + rubric hash) — the Step-3 baseline cache is only\n"
              "reusable when the fingerprint matches (see `coyodex-eval protocol`).")
        return 0
    map_arg, verdicts, out = _opt(argv, "--map"), _opt(argv, "--verdicts"), _opt(argv, "--out")
    if not map_arg or not verdicts or not out:
        print("ERROR: --map, --verdicts and --out are required", file=sys.stderr)
        return 2
    map_path, vpath = Path(map_arg), Path(verdicts)
    for p in (map_path, vpath):
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            return 1
    repo = _opt(argv, "--repo")
    rubric_arg = _opt(argv, "--rubric")
    rubric = Path(rubric_arg).read_text(encoding="utf-8") if rubric_arg and Path(rubric_arg).exists() else ""
    raw = json.loads(vpath.read_text(encoding="utf-8"))
    from coyodex.model import ModelError
    try:
        report = report_from_verdicts(map_path.read_text(encoding="utf-8"),
                                      Path(repo) if repo else Path("."),
                                      rubric, raw.get("grounding", []), raw.get("judges", []),
                                      judge_model=_opt(argv, "--judge-model") or "")
    except ModelError as e:
        print(f"ERROR: {map_path}: {e}", file=sys.stderr)
        return 1
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.to_json(), encoding="utf-8")
    pr = "n/a" if report.grounding_passrate is None else f"{report.grounding_passrate:.0%}"
    ov = "n/a" if report.overall is None else f"{report.overall:g}/4"
    print(f"Wrote {out_path} — grounding {report.n_grounded}/{report.n_claims} ({pr}), overall {ov}")
    return 0


def protocol_cli(argv: list[str]) -> int:
    """`coyodex-eval protocol` — the CURRENT judge-protocol fingerprint, and the Step-3 cache guard:
    with `--against <judge.json>` it exits non-zero when the cached report was produced under a
    DIFFERENT protocol (or records none — a pre-fingerprint cache), telling the orchestrator to
    re-judge instead of silently reusing stale scores."""
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex-eval protocol --thresholds <file> --rubric <file> "
              "[--against <judge.json>]\n\n"
              "Print the current judge-protocol fingerprint {model, n_skeptics, grounding_cap,\n"
              "rubric_sha} from the config. With --against, compare it to the fingerprint recorded\n"
              "in a cached judge.json: exit 0 = same protocol (the cache is reusable), 1 = protocol\n"
              "changed or not recorded (delete the cached judge.json and re-judge).")
        return 0
    tp, rp = _opt(argv, "--thresholds"), _opt(argv, "--rubric")
    if not tp or not rp:
        print("ERROR: --thresholds and --rubric are required", file=sys.stderr)
        return 2
    tpath, rpath = Path(tp), Path(rp)
    for p in (tpath, rpath):
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            return 1
    cfg = json.loads(tpath.read_text(encoding="utf-8")).get("judge", {})
    current = JudgeProtocol(
        model=str(cfg.get("grounding_model", "")),
        n_skeptics=int(cfg.get("n_skeptics", 0)),
        grounding_cap=int(cfg.get("grounding_cap", 0)),
        rubric_sha=rubric_fingerprint(rpath.read_text(encoding="utf-8")),
        prompt_version=GROUNDING_PROMPT_VERSION)
    print(json.dumps(current.__dict__, indent=2, sort_keys=True))
    against = _opt(argv, "--against")
    if against is None:
        return 0
    apath = Path(against)
    if not apath.exists():
        print(f"protocol: no cached report at {apath} — judge fresh (nothing to reuse)")
        return 1
    cached = JudgeReport.from_json(apath.read_text(encoding="utf-8")).protocol
    if cached is None:
        print(f"protocol MISMATCH: {apath} records no fingerprint (pre-fingerprint cache) — "
              "delete it and re-judge")
        return 1
    if cached != current:
        print(f"protocol MISMATCH: cached {cached.__dict__} != current — delete {apath} and re-judge")
        return 1
    print("protocol match — the cached judge report is reusable")
    return 0


def bless_cli(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv or len(argv) < 2:
        print("usage: coyodex-eval bless <run-dir> <baseline-dir>\n\n"
              "Promote a run to the baseline (copy its map + profile.json + judge.json).")
        return 0 if ("-h" in argv or "--help" in argv) else 2
    run_dir, baseline_dir = Path(argv[0]), Path(argv[1])
    if not run_dir.exists():
        print(f"ERROR: {run_dir} not found", file=sys.stderr)
        return 1
    bless(run_dir, baseline_dir)
    print(f"Blessed {run_dir} -> {baseline_dir}")
    return 0
