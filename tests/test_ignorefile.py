#!/usr/bin/env python3
"""Tests for `.coyodex/.ignore` — the analysis ignore file (coyodex.ignorefile).

Stdlib-only — no pytest required. Run either way (needs an editable install: `make deps`):
    python3 tests/test_ignorefile.py
    pytest tests/test_ignorefile.py

Two things are under test and they matter for different reasons. The MATCHING is ordinary parsing
work. The DISCLOSURE is a safety property: an ignore file is the one input that both the pre-index
and the coverage check read, so an over-broad pattern hides a gap from the check built to find gaps.
Every surface that narrows the tree must say so, and the tests below pin that.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import cast

from coyodex import validate_analysis
from coyodex.ignorefile import IGNORE_REL, ignore_report, load_ignore, parse_ignore
from coyodex.preindex_lib import expected_components, iter_source_files
from coyodex.viewer.build_graph import GraphDict
from coyodex.viewer.filetree import build_file_tree


# --- builders -------------------------------------------------------------------
def make_repo(tmp: Path, *, ignore: str | None = None, n_src: int = 3, n_trap: int = 5) -> Path:
    """A tiny repo: `src/` (real code), `trapdoor/` (code the map should not describe) and a nested
    `trapdoor/deep/`. Optionally writes the ignore file."""
    root = tmp / "repo"
    (root / "src").mkdir(parents=True)
    (root / "trapdoor" / "deep").mkdir(parents=True)
    for i in range(n_src):
        (root / "src" / f"real_{i}.py").write_text(f"def real_{i}():\n    return {i}\n")
    for i in range(n_trap):
        (root / "trapdoor" / f"trap_{i}.py").write_text(f"def trap_{i}():\n    return {i}\n")
    (root / "trapdoor" / "keep_me.py").write_text("def keep():\n    return 1\n")
    (root / "trapdoor" / "deep" / "d.py").write_text("def deep():\n    return 1\n")
    if ignore is not None:
        (root / IGNORE_REL).parent.mkdir(parents=True, exist_ok=True)
        (root / IGNORE_REL).write_text(ignore)
    # Resolved: on macOS the temp dir is /var/... which is a symlink to /private/var/..., and the
    # walk resolves its root — an unresolved root here makes `relative_to` raise.
    return root.resolve()


def rel_names(root: Path) -> set[str]:
    root = root.resolve()
    return {p.relative_to(root).as_posix() for p in iter_source_files(root).files}


def make_empty_graph() -> GraphDict:
    """The smallest graph the file-browser builder accepts: no nodes, so every row is unmapped and
    only the WALK decides what the tree contains."""
    return cast(GraphDict, {
        "commit": None, "committed": None, "title": None, "goal": None,
        "nodes": {}, "edges": [], "happy_path": [], "roles": [],
    })


# --- parsing --------------------------------------------------------------------
def test_comments_and_blank_lines_are_skipped():
    spec = parse_ignore("# a comment\n\n   \ntrapdoor/\n")
    assert spec.patterns == ["trapdoor/"]


def test_a_wildcard_free_pattern_covers_everything_beneath_it():
    # `trapdoor` and `trapdoor/` are the same statement — the directory the author obviously meant.
    for pat in ("trapdoor", "trapdoor/"):
        spec = parse_ignore(pat)
        assert spec.match("trapdoor/a.py")
        assert spec.match("trapdoor/deep/b.py")
        assert not spec.match("src/a.py")
        assert not spec.match("trapdoorish/a.py")   # prefix must land on a segment boundary


def test_star_does_not_cross_a_directory_boundary_but_doublestar_does():
    assert parse_ignore("trapdoor/*.py").match("trapdoor/a.py")
    assert not parse_ignore("trapdoor/*.py").match("trapdoor/deep/a.py")
    assert parse_ignore("trapdoor/**/*.py").match("trapdoor/deep/a.py")


def test_negation_wins_when_it_comes_last():
    spec = parse_ignore("trapdoor/\n!trapdoor/keep_me.py\n")
    assert spec.match("trapdoor/trap_0.py")
    assert not spec.match("trapdoor/keep_me.py")


def test_order_decides_so_a_broad_rule_can_follow_a_narrow_one():
    # The mirror of the test above: last match wins, both directions.
    spec = parse_ignore("!trapdoor/keep_me.py\ntrapdoor/\n")
    assert spec.match("trapdoor/keep_me.py")


def test_a_pattern_that_can_never_fire_is_reported_not_stored():
    # A dead pattern reads as coverage the author never got, so it must not be silently kept.
    spec = parse_ignore("trapdoor/\n/\n")
    assert spec.patterns == ["trapdoor/"]
    assert spec.bad_lines == ("/",)


def test_an_absent_file_ignores_nothing():
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td))
        spec = load_ignore(root)
        assert not spec and spec.patterns == [] and not spec.match("trapdoor/a.py")


# --- the walk -------------------------------------------------------------------
def test_the_walk_drops_ignored_files_and_counts_them_separately():
    # Separate from `skipped_excluded` on purpose: the built-ins are conventions nobody chose, this
    # is the repo's own declaration, and only the second one can hide a real gap.
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td), ignore="trapdoor/\n")
        walk = iter_source_files(root)
        assert rel_names(root) == {"src/real_0.py", "src/real_1.py", "src/real_2.py"}
        assert walk.skipped_ignored == 7          # 5 traps + keep_me + deep/d.py
        assert walk.ignore.patterns == ["trapdoor/"]


def test_a_negated_file_survives_inside_an_ignored_directory():
    # The reason the walk filters per FILE and never prunes directories: pruning `trapdoor/` would
    # make the negation below unreachable, and the bug would look like a matching bug.
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td), ignore="trapdoor/\n!trapdoor/keep_me.py\n")
        assert "trapdoor/keep_me.py" in rel_names(root)
        assert "trapdoor/trap_0.py" not in rel_names(root)


def test_the_walk_is_unchanged_when_no_ignore_file_exists():
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td))
        walk = iter_source_files(root)
        assert walk.skipped_ignored == 0 and not walk.ignore
        assert "trapdoor/trap_0.py" in rel_names(root)


def test_an_edit_to_the_ignore_file_is_picked_up_within_a_session():
    # The parse is cached on (path, mtime, size); a stale cache would silently keep analysing a tree
    # the author just excluded.
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td))
        assert "trapdoor/trap_0.py" in rel_names(root)
        (root / IGNORE_REL).parent.mkdir(parents=True, exist_ok=True)
        (root / IGNORE_REL).write_text("trapdoor/\n")
        assert "trapdoor/trap_0.py" not in rel_names(root)


def test_the_expectation_e_is_computed_over_the_narrowed_tree():
    # E drives the altitude advisory, so an ignored fixture tree must not inflate it.
    with tempfile.TemporaryDirectory() as td:
        plain = expected_components(make_repo(Path(td) / "a"))
    with tempfile.TemporaryDirectory() as td:
        narrowed = expected_components(make_repo(Path(td) / "b", ignore="trapdoor/\n"))
    assert narrowed.files < plain.files          # the ignored tree is gone from the count…
    assert narrowed.expected <= plain.expected   # …so E can only shrink


# --- disclosure (the safety property) -------------------------------------------
def test_validate_discloses_the_ignore_file_and_names_its_patterns():
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td), ignore="trapdoor/\n")
        out = validate_analysis.ignore_disclosure(root)
        assert len(out) == 1
        assert ".coyodex/.ignore" in out[0] and "trapdoor/" in out[0]
        assert "7 file(s)" in out[0]


def test_validate_says_nothing_when_there_is_no_ignore_file():
    with tempfile.TemporaryDirectory() as td:
        assert validate_analysis.ignore_disclosure(make_repo(Path(td))) == []


def test_validate_calls_out_a_line_that_parsed_to_nothing():
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td), ignore="trapdoor/\n/\n")
        out = validate_analysis.ignore_disclosure(root)
        assert len(out) == 2 and "match nothing" in out[1]


# --- per-rule hits: an unused pattern is the one that can lie -------------------
def test_the_walk_counts_hits_per_rule_and_a_negation_counts_as_a_restore():
    # The DECIDING rule (last match wins) is the one credited, so the two counts read as the story
    # they are: the broad rule took files out, the `!` rule put one back.
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td), ignore="trapdoor/\n!trapdoor/keep_me.py\ntypo_dir/\n")
        walk = iter_source_files(root)
        assert walk.ignore_hits == (6, 1, 0)      # 5 traps + deep/d.py | keep_me.py | nothing
        rep = ignore_report(walk.ignore, walk.ignore_hits)
        assert rep.removed == walk.skipped_ignored == 6   # only the POSITIVE rules remove
        assert rep.restored == 1                          # the `!` rule re-included, it did not remove
        assert rep.unused == ("typo_dir/",)


def test_a_typod_but_valid_pattern_is_reported_as_deciding_nothing():
    # The gap the old code had: `bad_lines` only caught a pattern that stripped to nothing, so a
    # syntactically fine typo matched zero files and was counted in the reassuring "3 pattern(s)".
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td), ignore="trapdoor/\n!trapdoor/keep_me.py\ntypo_dir/\n")
        out = validate_analysis.ignore_disclosure(root)
        assert len(out) == 2
        assert "trapdoor/ (removed 6 file(s))" in out[0]
        assert "!trapdoor/keep_me.py (put back 1 file(s))" in out[0]
        assert "decided nothing" in out[1] and "typo_dir/" in out[1]


def test_a_pattern_a_builtin_exclusion_already_covers_is_reported_as_unused():
    # A doc example that does nothing teaches the wrong thing: `vendor/` is already in
    # DEFAULT_EXCLUDE_DIRS, so the walk never offers those paths to the ignore file at all.
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td), ignore="vendor/\n")
        (root / "vendor").mkdir()
        (root / "vendor" / "lib.py").write_text("def lib():\n    return 1\n")
        out = validate_analysis.ignore_disclosure(root)
        assert len(out) == 2 and "decided nothing" in out[1] and "vendor/" in out[1]


def test_every_used_pattern_stays_out_of_the_unused_report():
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td), ignore="trapdoor/\n")
        out = validate_analysis.ignore_disclosure(root)
        assert len(out) == 1 and "trapdoor/ (removed 7 file(s))" in out[0]


def test_the_hit_counts_are_not_shared_between_two_walks_of_the_same_tree():
    # The spec is process-cached; a counter living on it would accumulate and report a number
    # belonging to some earlier walk.
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td), ignore="trapdoor/\n")
        first = iter_source_files(root).ignore_hits
        second = iter_source_files(root).ignore_hits
        assert first == second == (7,)


# --- the viewer's file browser (F4a) --------------------------------------------
def test_the_file_browser_tree_carries_what_the_ignore_file_removed():
    # The browser is where a human eyeballs "what code isn't covered" — a narrowed tree with no note
    # is the excluded evidence hiding exactly where someone went looking for it.
    with tempfile.TemporaryDirectory() as td:
        root = make_repo(Path(td), ignore="trapdoor/\n!trapdoor/keep_me.py\ntypo_dir/\n")
        tree = build_file_tree(make_empty_graph(), str(root))
        assert tree is not None
        note = tree.get("ignored")
        assert note is not None
        assert note["files"] == 6
        assert note["patterns"][0] == "trapdoor/ (removed 6 file(s))"
        assert note["unused"] == ["typo_dir/"]


def test_the_file_browser_tree_says_nothing_when_no_ignore_file_exists():
    with tempfile.TemporaryDirectory() as td:
        tree = build_file_tree(make_empty_graph(), str(make_repo(Path(td))))
        assert tree is not None and "ignored" not in tree


def _main() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"{len(fns)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
