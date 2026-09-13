"""`coyomap-eval ledger` — does a row's hand-set `landed` flag agree with the commit it names?"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from coyomap_eval import ledger


# --- builders -------------------------------------------------------------------
def make_repo(tmp: Path) -> tuple[Path, str, str]:
    """A git repo with two commits on HEAD and one on an abandoned branch.

    Returns `(repo, merged sha, abandoned sha)`. The abandoned one matters: a commit can exist in
    the object store and not be a fix that shipped."""
    repo = tmp / "repo"
    repo.mkdir()
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True,
                                    check=True)
    run("init", "-q", "-b", "main")
    run("config", "user.email", "t@t")
    run("config", "user.name", "t")
    (repo / "a.txt").write_text("one", encoding="utf-8")
    run("add", "-A")
    run("commit", "-qm", "one")
    merged = run("rev-parse", "--short", "HEAD").stdout.strip()
    run("checkout", "-q", "-b", "side")
    (repo / "b.txt").write_text("two", encoding="utf-8")
    run("add", "-A")
    run("commit", "-qm", "abandoned")
    abandoned = run("rev-parse", "--short", "HEAD").stdout.strip()
    run("checkout", "-q", "main")
    return repo, merged, abandoned


def make_ledger(tmp: Path, rows: list[dict]) -> Path:
    p = tmp / "findings.json"
    p.write_text(json.dumps({"schema": "coyomap-retro-ledger/v1", "findings": rows}),
                 encoding="utf-8")
    return p


def row(rid: str, landed: bool, landed_in: str = "", title: str = "t") -> dict:
    r: dict = {"id": rid, "title": title, "severity": "MED", "landed": landed}
    if landed_in:
        r["landed_in"] = landed_in
    return r


# --- the failure this exists to catch -------------------------------------------
def test_a_row_claiming_OPEN_whose_fix_is_merged_is_reported_and_exits_1():
    """The measured failure. One session answered 40 rows of a real ledger and, in the same
    session, fixed seven of them — all seven kept `landed: false`. Each would have been
    re-proposed by the next retrospective with its `retros_open` count going up, which is the
    shape that ledger already had 24 instances of. Setting forty flags by hand and getting seven
    wrong is what hand-maintained state does; nothing had ever checked it."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo, merged, _ = make_repo(tmp)
        p = make_ledger(tmp, [row("f-1", False, f"{merged} (the fix)", "prose check missing")])
        assert ledger.main([str(p), "--repo", str(repo), "--json"]) == 1
        rep = ledger.check(json.loads(p.read_text())["findings"], repo)
        assert [i for i, _s, _t in rep.stale_open] == ["f-1"]


def test_a_row_claiming_LANDED_in_a_commit_this_branch_does_not_have():
    """The other direction. Either the fix is unmerged or the sha is wrong, and both mean the row's
    claim cannot be trusted — but it is not the expensive case, so it reports without failing."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo, _merged, abandoned = make_repo(tmp)
        p = make_ledger(tmp, [row("f-2", True, f"{abandoned} (never merged)")])
        assert ledger.main([str(p), "--repo", str(repo)]) == 0
        rep = ledger.check(json.loads(p.read_text())["findings"], repo)
        assert [i for i, _s, _t in rep.unverifiable] == ["f-2"]


def test_a_commit_on_an_abandoned_branch_is_not_a_fix_that_shipped():
    """`cat-file -e` would call the abandoned commit present, and a row citing it would read as
    landed. Reachability from HEAD is the question — the same failure this command catches, in the
    other direction."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo, merged, abandoned = make_repo(tmp)
        assert ledger._commit_exists(repo, merged)
        assert not ledger._commit_exists(repo, abandoned)


def test_rows_that_agree_with_the_branch_are_silent():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo, merged, abandoned = make_repo(tmp)
        p = make_ledger(tmp, [row("ok-1", True, f"{merged} (landed)"),
                              row("ok-2", False, "")])
        assert ledger.main([str(p), "--repo", str(repo)]) == 0
        rep = ledger.check(json.loads(p.read_text())["findings"], repo)
        assert not rep.stale_open and not rep.unverifiable


def test_the_count_it_could_NOT_check_is_printed(capsys):
    """A ledger where nothing is checkable reports zero problems, and zero problems is exactly what
    a clean one reports. On the real ledger 52 of 77 rows name no commit, so the limit is most of
    the file and saying it is the difference between a result and a false all-clear."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo, merged, _ = make_repo(tmp)
        p = make_ledger(tmp, [row("a", True, f"{merged} (landed)"),
                              row("b", False), row("c", False), row("d", False)])
        assert ledger.main([str(p), "--repo", str(repo)]) == 0
        out = capsys.readouterr().out
        assert "3 row(s) name no commit" in out
        assert "not a clean ledger" in out


def test_a_landed_in_that_names_no_sha_is_uncheckable_not_a_finding():
    """Older rows carry prose there (`accepted — fixed in the method …`). Reading that as a missing
    commit would report every one of them as unverifiable and bury the two real cases."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo, _m, _a = make_repo(tmp)
        p = make_ledger(tmp, [row("p-1", True, "accepted — fixed in the method (method.md …)")])
        rep = ledger.check(json.loads(p.read_text())["findings"], repo)
        assert not rep.unverifiable and rep.uncheckable == 1


def test_a_file_that_is_not_a_ledger_is_refused_rather_than_read_as_empty():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p = tmp / "x.json"
        p.write_text(json.dumps({"not": "a ledger"}), encoding="utf-8")
        assert ledger.main([str(p), "--repo", str(tmp)]) == 2
        assert ledger.main([str(tmp / "absent.json")]) == 2


def test_a_bare_list_is_refused_with_the_ledger_message_not_a_traceback():
    """One retro wrote its rows as a bare list; the tool crashed with an `AttributeError` two lines
    short of the diagnosis it already carries."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        p = tmp / "rows.json"
        p.write_text(json.dumps([{"id": "x-1", "landed": False}]), encoding="utf-8")
        assert ledger.main([str(p), "--repo", str(tmp)]) == 2
