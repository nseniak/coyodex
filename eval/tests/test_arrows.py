"""Tests for `coyomap-eval arrows` — the check that catches a rebuild dropping true relations.

The failure this exists for was silent in every other instrument at once: a rebuild lost 24 arrows,
22 of them real, including all eight `plugin -> analytics` edges the trapdoor fixture plants as trap
O3 — while `validate` passed, `audit` passed, and `coyomap-eval run` said DRIFT because the edge
shrink came in at 27.4% against a 30% band.

So the tests below pin the two things that would make this instrument useless:

  * calling a real loss a correct drop (the silence that shipped the broken map), and
  * refusing to judge, or judging anyway, when the CODE moved under the two maps.
"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
from pathlib import Path

from coyomap_eval import arrows


def make_map(commit: str, boxes: dict[str, str], edges: list[dict[str, str]]) -> dict[str, object]:
    """A map is just its rows. `boxes` is id -> source anchor; `edges` are src/verb/dst/where."""
    return {"format": "coyomap-map", "commit": commit,
            "components": [{"id": i, "source": s} for i, s in boxes.items()],
            "edges": list(edges)}


def make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return tmp_path


def make_git_repo(tmp_path: Path, files: dict[str, str]) -> tuple[Path, str]:
    repo = make_repo(tmp_path, files)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin"}
    for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "one"]):
        subprocess.run(["git", "-C", str(repo), *cmd], check=True, env=env, capture_output=True)
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    return repo, sha


def run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = arrows.main(argv)
    return code, out.getvalue(), err.getvalue()


# --- matching by file, because ids and names never survive a rebuild ------------------------------

def test_an_arrow_is_addressed_by_the_files_its_ends_live_in() -> None:
    m = make_map("abc", {"C1": "a.py:1", "C2": "b.py:1"},
                 [{"src": "C1", "verb": "calls", "dst": "C2", "where": "a.py:3"}])
    assert arrows.arrows(m)[0].pair == ("a.py", "b.py")


def test_the_same_arrow_matches_across_two_builds_that_renumbered_everything() -> None:
    """This is the whole reason the command exists: `coyomap diff` matches by id and says in its
    own docstring that it cannot compare two independent builds."""
    old = make_map("abc", {"C1": "a.py:1", "C2": "b.py:1"},
                   [{"src": "C1", "verb": "calls", "dst": "C2", "where": "a.py:3"}])
    new = make_map("abc", {"C77": "a.py:1", "C99": "b.py:1"},
                   [{"src": "C77", "verb": "uses", "dst": "C99", "where": "a.py:3"}])
    assert arrows.compare(old, new, Path("/nonexistent")) == ()


def test_an_arrow_into_a_dependency_still_matches_by_its_source_file() -> None:
    """The eight plugin edges this was written for all point at a box with no file of its own."""
    m = make_map("abc", {"C1": "p.py:1", "D1": ""},
                 [{"src": "C1", "verb": "queues", "dst": "D1", "where": "p.py:9"}])
    assert arrows.arrows(m)[0].pair == ("p.py", "")


# --- the verdict ----------------------------------------------------------------------------------

def test_a_lost_arrow_whose_call_site_is_still_live_code_is_a_lost_truth(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"a.py": "import os\nx = 1\nservice.fetch(1)\n"})
    old = make_map("abc", {"C1": "a.py:1", "C2": "b.py:1"},
                   [{"src": "C1", "verb": "calls", "dst": "C2", "where": "a.py:3"}])
    new = make_map("abc", {"C1": "a.py:1"}, [])
    verdicts = arrows.compare(old, new, repo)
    assert [v.verdict for v in verdicts] == [arrows.LOST_TRUTH]
    assert "service.fetch(1)" in verdicts[0].reason


def test_a_lost_arrow_whose_file_is_gone_is_a_correct_drop(tmp_path: Path) -> None:
    old = make_map("abc", {"C1": "deleted.py:1", "C2": "b.py:1"},
                   [{"src": "C1", "verb": "calls", "dst": "C2", "where": "deleted.py:3"}])
    new = make_map("abc", {}, [])
    verdicts = arrows.compare(old, new, tmp_path)
    assert [v.verdict for v in verdicts] == [arrows.CORRECT_DROP]


def test_a_lost_arrow_whose_line_no_longer_exists_is_a_correct_drop(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"a.py": "x = 1\n"})
    old = make_map("abc", {"C1": "a.py:1", "C2": "b.py:1"},
                   [{"src": "C1", "verb": "calls", "dst": "C2", "where": "a.py:99"}])
    verdicts = arrows.compare(old, make_map("abc", {}, []), repo)
    assert [v.verdict for v in verdicts] == [arrows.CORRECT_DROP]


def test_an_anchor_that_now_points_at_a_definition_header_is_a_correct_drop(tmp_path: Path) -> None:
    """A `def` line cannot BE the call, so the recorded site no longer supports the claim."""
    repo = make_repo(tmp_path, {"a.py": "x = 1\ndef handler():\n    pass\n"})
    old = make_map("abc", {"C1": "a.py:1", "C2": "b.py:1"},
                   [{"src": "C1", "verb": "calls", "dst": "C2", "where": "a.py:2"}])
    verdicts = arrows.compare(old, make_map("abc", {}, []), repo)
    assert [v.verdict for v in verdicts] == [arrows.CORRECT_DROP]


def test_an_arrow_still_connecting_the_same_two_files_is_regrouped_not_lost(tmp_path: Path) -> None:
    old = make_map("abc", {"C1": "a.py:1", "C2": "b.py:1"},
                   [{"src": "C1", "verb": "calls", "dst": "C2", "where": "a.py:3"}])
    new = make_map("abc", {"C1": "a.py:1", "C2": "b.py:1"},
                   [{"src": "C1", "verb": "reads", "dst": "C2", "where": "a.py:4"}])
    assert arrows.compare(old, new, tmp_path) == ()


def test_an_arrow_with_no_anchor_is_unjudgeable_rather_than_assumed_either_way(tmp_path: Path) -> None:
    old = make_map("abc", {"C1": "a.py:1", "C2": "b.py:1"},
                   [{"src": "C1", "verb": "calls", "dst": "C2", "where": ""}])
    verdicts = arrows.compare(old, make_map("abc", {}, []), tmp_path)
    assert [v.verdict for v in verdicts] == [arrows.UNJUDGEABLE]


# --- the source guard -------------------------------------------------------------------------------

def test_two_maps_on_the_same_pin_are_judged(tmp_path: Path) -> None:
    ok, why = arrows.source_unchanged(make_map("abc", {}, []), make_map("abc", {}, []), tmp_path)
    assert ok and "abc" in why


def test_a_dirty_pin_still_names_the_commit_it_was_at(tmp_path: Path) -> None:
    ok, _ = arrows.source_unchanged(make_map("abc-dirty", {}, []), make_map("abc", {}, []), tmp_path)
    assert ok


def test_a_map_with_no_pin_is_refused_rather_than_assumed_unchanged(tmp_path: Path) -> None:
    ok, why = arrows.source_unchanged(make_map("", {}, []), make_map("abc", {}, []), tmp_path)
    assert not ok and "no commit pin" in why


def test_committing_the_previous_map_does_not_read_as_the_code_changing(tmp_path: Path) -> None:
    """The bug this check shipped with. Comparing the two pin STRINGS refused the first real pair it
    met, because the baseline map had been COMMITTED between the two builds. Seven files moved and
    every one was under `.coyomap/`."""
    repo, first = make_git_repo(tmp_path, {"a.py": "x = 1\n"})
    (repo / ".coyomap").mkdir(exist_ok=True)
    (repo / ".coyomap" / "project-map.json").write_text("{}", encoding="utf-8")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin"}
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=env, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "map"], check=True, env=env,
                   capture_output=True)
    second = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    ok, why = arrows.source_unchanged(make_map(first, {}, []), make_map(second, {}, []), repo)
    assert ok, why
    assert "no source file" in why


def test_a_real_source_change_between_the_pins_is_refused(tmp_path: Path) -> None:
    repo, first = make_git_repo(tmp_path, {"a.py": "x = 1\n"})
    (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/usr/local/bin"}
    subprocess.run(["git", "-C", str(repo), "commit", "-qam", "edit"], check=True, env=env,
                   capture_output=True)
    second = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    ok, why = arrows.source_unchanged(make_map(first, {}, []), make_map(second, {}, []), repo)
    assert not ok and "a.py" in why


# --- the CLI ------------------------------------------------------------------------------------------

def test_the_exit_code_is_one_only_when_a_truth_was_lost(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, {"a.py": "x = 1\nservice.fetch()\n"})
    old_p, new_p = tmp_path / "old.json", tmp_path / "new.json"
    old_p.write_text(json.dumps(make_map("abc", {"C1": "a.py:1", "C2": "b.py:1"},
                                         [{"src": "C1", "verb": "calls", "dst": "C2",
                                           "where": "a.py:2"}])), encoding="utf-8")
    new_p.write_text(json.dumps(make_map("abc", {"C1": "a.py:1"}, [])), encoding="utf-8")
    assert run([str(old_p), str(new_p), "--repo", str(repo)])[0] == 1
    assert run([str(old_p), str(old_p), "--repo", str(repo)])[0] == 0


def test_different_code_is_refused_unless_the_caller_overrides(tmp_path: Path) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(make_map("aaa", {}, [])), encoding="utf-8")
    b.write_text(json.dumps(make_map("", {}, [])), encoding="utf-8")
    code, _, err = run([str(a), str(b), "--repo", str(tmp_path)])
    assert code == 2 and "refuses rather than guessing" in err
    assert run([str(a), str(b), "--repo", str(tmp_path), "--allow-different-commits"])[0] == 0


def test_json_mode_emits_a_machine_contract(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    a.write_text(json.dumps(make_map("abc", {}, [])), encoding="utf-8")
    code, out, _ = run([str(a), str(a), "--repo", str(tmp_path), "--json"])
    assert code == 0 and json.loads(out)["same_source"] is True


def test_no_argument_prints_usage_and_fails_so_a_typo_is_never_silent() -> None:
    assert run([])[0] == 2
