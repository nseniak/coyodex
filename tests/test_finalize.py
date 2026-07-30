#!/usr/bin/env python3
"""`coyodex finalize` — the pre-commit read.

The design point these pin: it is a CONVENIENCE WRAPPER, not an enforcement point. Nothing makes a
build run it, and `finalize | grep …` returns grep's status, so the value is (a) running `compare`
during the build at all — the check that caught a 103→19 security-table collapse every other gate
passed, and that nobody ran — and (b) writing a durable report a `> /dev/null` cannot erase.

Run either way: `python3 tests/test_finalize.py` or `pytest tests/test_finalize.py`.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex import finalize
from coyodex.model import FORMAT

#: A genuinely minimal VALID map — no entities, because a domain card carries its own blocking
#: requirements (meaning, fields, a real named type in its source) that have nothing to do with what
#: these tests are about. Two components and one C→C edge is the smallest thing that validates.
MAP = {
    "format": FORMAT,   # the real constant, so the fixture cannot drift from the loader
    "title": "T", "goal": "G",
    "roles": [{"id": "R1", "name": "A", "kind": "human", "wants": "x", "drives": "UC1"}],
    "use_cases": [{"id": "UC1", "name": "Do it", "actors": ["R1"]}],
    "happy_path": [{"id": "HP1", "title": "Do", "uc": "UC1"}],
    "components": [{"id": "C1", "name": "Front", "purpose": "takes the ask", "entry_point": "src/a.py:1"},
                   {"id": "C2", "name": "Back", "purpose": "answers it", "entry_point": "src/b.py:1"}],
    "edges": [{"src": "C1", "verb": "calls", "dst": "C2", "why": "to answer", "where": "src/a.py:2"}],
    "flows": [{"uc": "UC1", "title": "Do it",
               "steps": [{"n": 1, "src": "R1", "dst": "C1", "phrase": "asks"},
                         {"n": 2, "src": "C1", "dst": "C2", "phrase": "forwards", "where": "src/a.py:2"},
                         {"n": 3, "src": "C1", "dst": "R1", "phrase": "answers"}]}],
}


def make_git_repo_with_baseline() -> tuple[Path, Path]:
    """A repo whose HEAD holds a PREVIOUS map, so the compare leg actually runs. Without this every
    test returned early at the no-baseline branch, leaving the one novel leg untested."""
    root, p = make_repo()
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
    subprocess.run(["git", "add", "-f", str(p.relative_to(root))], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "baseline"],
                   cwd=root, check=True)
    return root, p


def make_repo(broken: bool = False, components: int = 0) -> tuple[Path, Path]:
    root = Path(tempfile.mkdtemp())
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("def front():\n    return back()\n", encoding="utf-8")
    (root / "src" / "b.py").write_text("def back():\n    return 1\n", encoding="utf-8")
    (root / ".coyodex").mkdir()
    doc = json.loads(json.dumps(MAP))
    if components:
        # An edgeless map of N components: the isolated-component advisory lists every id, so a
        # truncation (or its absence) is observable.
        doc["components"] = [{"id": f"C{i}", "name": f"C{i}", "purpose": "p",
                              "entry_point": "src/a.py:1"} for i in range(1, components + 1)]
        doc["edges"] = []
        doc["flows"] = [{"uc": "UC1", "title": "Do it",
                         "steps": [{"n": 1, "src": "R1", "dst": "C1", "phrase": "asks"},
                                   {"n": 2, "src": "C1", "dst": "C2", "phrase": "f",
                                    "where": "src/a.py:2"},
                                   {"n": 3, "src": "C1", "dst": "R1", "phrase": "answers"}]}]
    if broken:
        doc["edges"][0]["dst"] = "C999"        # a dangling reference — a BLOCKING validate problem
    p = root / ".coyodex" / "project-map.json"
    p.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return root, p


def test_a_clean_map_exits_zero_and_writes_both_reports():
    root, p = make_repo()
    code = finalize.main([str(p), "--repo", str(root)])
    assert code == 0
    assert (root / ".coyodex" / "finalize-report.json").is_file()
    assert (root / ".coyodex" / "finalize-report.md").is_file()


def test_a_blocking_problem_exits_one_and_is_recorded_as_blocking():
    """Exit 1 means exactly what validate/audit already block on — nothing more."""
    root, p = make_repo(broken=True)
    code = finalize.main([str(p), "--repo", str(root)])
    assert code == 1
    report = json.loads((root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8"))
    assert report["verdict"] == "BLOCKED"
    assert report["blocking_total"] >= 1
    assert any("C999" in b for leg in report["legs"] for b in leg["blocking"])


def test_a_leg_that_did_not_run_can_never_produce_a_verdict_of_clean():
    """The defect this command shipped in its first cut, and the whole reason `Leg.status` exists.

    A leg that did not run contributed 0 blocking and 0 advisory, so a broken map with a typo'd
    `--repo` reported **Verdict: CLEAN**, exit 0 — a report testifying that a gate passed when the gate
    never ran. Worse than no report at all."""
    root, p = make_repo(broken=True)                 # a dangling reference: validate exits 1 on this
    code = finalize.main([str(p), "--repo", "/nonexistent-dir-for-this-test"])
    r = json.loads((root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8"))
    assert r["verdict"] == "INCOMPLETE", r["verdict"]
    assert code != 0, "a run that does not know whether the map is clean must not exit 0"
    assert any(l["status"] == "failed" for l in r["legs"])
    md = (root / ".coyodex" / "finalize-report.md").read_text(encoding="utf-8")
    verdict_line = next(ln for ln in md.splitlines() if ln.startswith("**Verdict:"))
    assert "CLEAN" not in verdict_line, verdict_line
    assert "their silence is not a pass" in md


def test_an_unavailable_leg_is_benign_and_still_permits_exit_zero():
    """The other side of the same rule: no baseline on a first build is expected, not a failure. If
    `unavailable` were treated like `failed`, every first build would exit non-zero."""
    root, p = make_repo()                            # tmpdir: no git history, no archive
    code = finalize.main([str(p), "--repo", str(root)])
    r = json.loads((root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8"))
    leg = next(l for l in r["legs"] if l["name"].startswith("compare"))
    assert leg["status"] == "unavailable"
    assert r["verdict"] != "INCOMPLETE" and code == 0


def test_the_report_is_byte_identical_across_identical_runs():
    """Non-determinism in a pre-commit report is a defect: a build cannot tell a real change from
    noise, and a diff of the committed report becomes unreadable."""
    root, p = make_repo()
    finalize.main([str(p), "--repo", str(root)])
    first = (root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8")
    finalize.main([str(p), "--repo", str(root)])
    assert (root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8") == first


def test_no_baseline_is_a_named_skip_not_a_silent_pass():
    """The failure this command exists for was a check nobody ran. A baseline that cannot be found
    must say so in the report, because 'no comparison happened' and 'the comparison was clean' are
    the two states a build must never confuse."""
    root, p = make_repo()                       # a temp dir: no git history, no .old-ignore archive
    finalize.main([str(p), "--repo", str(root)])
    r = json.loads((root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8"))
    leg = next(l for l in r["legs"] if l["name"].startswith("compare"))
    assert leg["status"] == "unavailable"
    assert leg["note"] and "no baseline" in leg["note"]
    assert r["baseline"] is None


def test_it_leaves_no_scratch_files_even_when_a_baseline_was_materialised():
    """The first version of this test used a tmpdir with no git, so `find_baseline` returned None and
    the cleanup it claimed to pin never ran. With a real baseline the temp copy IS created — and it is
    ~800 KB of the previous map, so leaking it beside the real one is not cosmetic."""
    root, p = make_git_repo_with_baseline()
    finalize.main([str(p), "--repo", str(root)])
    strays = [f.name for f in (root / ".coyodex").iterdir()
              if f.name.startswith(f".{finalize.REPORT_STEM}")]
    assert strays == [], strays


def test_a_crash_mid_run_still_cleans_up_the_baseline_copy():
    """`build_report` materialises the baseline BEFORE the legs, so only a `finally` can hold this."""
    root, p = make_git_repo_with_baseline()
    boom = root / ".coyodex" / "not-json.json"
    boom.write_text("{{{ not json", encoding="utf-8")
    try:
        finalize.main([str(p), "--repo", str(root), "--verdicts", str(boom)])
    except Exception:
        pass
    strays = [f.name for f in (root / ".coyodex").iterdir()
              if f.name.startswith(f".{finalize.REPORT_STEM}")]
    assert strays == [], strays


def test_a_missing_map_and_a_missing_verdicts_file_fail_before_any_leg_runs():
    root, p = make_repo()
    assert finalize.main([str(root / ".coyodex" / "nope.json")]) == 1
    assert finalize.main([str(p), "--repo", str(root), "--verdicts", str(root / "nope.json")]) == 1


def test_the_report_carries_whole_lists_on_a_map_big_enough_to_truncate():
    """The previous version asserted `"more" not in … or "+" not in …` on a 2-component map — both
    disjuncts trivially true, and it passed with whole-list mode removed. This builds a map with 30
    isolated components, well past the 8-id inline limit, and asserts the ids are all present."""
    root, p = make_repo(components=30)
    finalize.main([str(p), "--repo", str(root)])
    text = (root / ".coyodex" / "finalize-report.md").read_text(encoding="utf-8")
    isolated = [ln for ln in text.splitlines() if "carry no backbone edge" in ln]
    assert isolated, "expected the isolated-component advisory on a 30-component edgeless map"
    assert "more" not in isolated[0], isolated[0]
    assert "C30" in isolated[0], "the last id must be present, not elided"


def test_the_help_says_it_is_not_an_enforcement_point():
    """If the docs ever start promising enforcement, the promise is false — the exit status is lost to
    any pipeline. Pinned so the claim cannot drift back."""
    r = subprocess.run([sys.executable, "-m", "coyodex.cli", "finalize", "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "not an enforcement point" in r.stdout
    assert "never gating" in r.stdout


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all finalize tests passed")


def test_the_compare_leg_runs_against_a_committed_baseline():
    """The only genuinely new signal this command adds, and it had zero coverage: every earlier test
    hit the no-baseline branch, so `_find_eval`, the score/compare subprocesses, the JSON parse and the
    temp-file cleanup never executed once."""
    root, p = make_git_repo_with_baseline()
    finalize.main([str(p), "--repo", str(root)])
    r = json.loads((root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8"))
    leg = next(l for l in r["legs"] if l["name"].startswith("compare"))
    assert leg["status"] == "ran", leg
    assert r["baseline_source"] and r["baseline_source"].startswith("git HEAD:")
    assert any(row.startswith("Comparison verdict: ") for row in leg["advisory"])
    assert r["compare_verdict"] in ("PASS", "DRIFT", "REGRESSED")


def test_a_crashed_compare_is_a_failure_not_nothing_found():
    """It scraped stdout and returned `ran=True` regardless of the exit code, so a crashed `compare`
    read as a comparison that ran and found nothing — for the one check the command exists to run."""
    root, p = make_git_repo_with_baseline()
    fake = Path(tempfile.mkdtemp()) / "coyodex-eval"
    fake.write_text("#!/bin/sh\n"
                    'case "$1" in\n'
                    '  score) shift; exec "$@" ;;\n'   # never reached; replaced below
                    "esac\n", encoding="utf-8")
    # A stub whose `score` works (emits a real profile) and whose `compare` crashes.
    real = Path(finalize.__file__).parent.parent.parent / ".venv" / "bin" / "coyodex-eval"
    fake.write_text(f'#!/bin/sh\nif [ "$1" = "compare" ]; then echo boom >&2; exit 7; fi\n'
                    f'exec "{real}" "$@"\n', encoding="utf-8")
    fake.chmod(0o755)
    orig = finalize._find_eval
    finalize._find_eval = lambda: str(fake)          # type: ignore[assignment]
    try:
        code = finalize.main([str(p), "--repo", str(root)])
    finally:
        finalize._find_eval = orig                    # type: ignore[assignment]
    r = json.loads((root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8"))
    leg = next(l for l in r["legs"] if l["name"].startswith("compare"))
    assert leg["status"] == "failed", leg
    assert "crashed" in (leg["note"] or "")
    assert r["verdict"] == "INCOMPLETE" and code != 0


def test_the_archive_fallback_picks_the_NEWEST_archive():
    """Sorting on the directory NAME LENGTH picked the wrong archive in 28 of 40 measured trials, and
    `Path.glob` is unordered so same-length names resolved in filesystem order. A wrong baseline does
    not fail loudly — it produces a confident verdict about the wrong comparison."""
    root, p = make_repo()
    for n in ("", "-2", "-9", "-10", "-11", "-12"):
        d = root / ".coyodex" / f".old-ignore{n}"
        d.mkdir()
        (d / "project-map.json").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    chosen, source, note = finalize.find_baseline(p, root)
    assert chosen is not None and chosen.parent.name == ".old-ignore-12", source


def test_the_report_records_the_maps_hash_so_a_stale_one_is_detectable():
    """A crash writes no report, so the PREVIOUS run's file survives — and the method tells the build to
    read the file. The hash is how a reader tells this map's result from another's."""
    import hashlib
    root, p = make_repo()
    finalize.main([str(p), "--repo", str(root)])
    r = json.loads((root / ".coyodex" / "finalize-report.json").read_text(encoding="utf-8"))
    assert r["map_sha256"] == hashlib.sha256(p.read_bytes()).hexdigest()
    assert r["map_sha256"] in (root / ".coyodex" / "finalize-report.md").read_text(encoding="utf-8")
