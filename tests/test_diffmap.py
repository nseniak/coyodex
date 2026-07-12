"""Tests for the pure diff-projection core (coyodex.viewer.diffmap).

No git, no I/O — the module projects an already-parsed changed-file list onto a model. Stdlib-only
(runs under pytest or `python tests/test_diffmap.py`); explicit make_* builders, no fixtures/classes.
"""
from __future__ import annotations

from coyodex.model import Component, Entity, Group, ProjectModel
from coyodex.viewer.diffmap import (
    CREATED,
    DELETED,
    FileChange,
    MODIFIED,
    parse_name_status,
    parse_unified_diff,
    project_changes,
    side_map,
    untracked_changes,
)


# --- builders -------------------------------------------------------------------
def make_component(cid: str, source: str | None = None, files: list[str] | None = None) -> Component:
    return Component(id=cid, name=cid, source=source, files=files or [])


def make_model(components: list[Component] | None = None,
               entities: list[Entity] | None = None,
               subsystems: list[Group] | None = None) -> ProjectModel:
    return ProjectModel(components=components or [], entities=entities or [],
                        subsystems=subsystems or [])


# --- parse_name_status ----------------------------------------------------------
def test_parse_name_status_basic() -> None:
    text = "M\tsrc/a.py\nA\tsrc/b.py\nD\tsrc/c.py\n"
    got = parse_name_status(text)
    assert got == [
        FileChange("M", "src/a.py"),
        FileChange("A", "src/b.py"),
        FileChange("D", "src/c.py"),
    ]


def test_parse_name_status_rename_and_copy_and_typechange() -> None:
    text = "R100\told/x.py\tnew/x.py\nC080\tsrc/base.py\tsrc/copy.py\nT\tsrc/link.py\n"
    got = parse_name_status(text)
    assert got == [
        FileChange("R", "new/x.py", old_path="old/x.py"),  # rename keeps the old path
        FileChange("A", "src/copy.py"),                     # copy = add of the new path only
        FileChange("M", "src/link.py"),                     # type change = modify
    ]


def test_parse_name_status_skips_blank_and_malformed() -> None:
    assert parse_name_status("\n  \nM\n") == []             # 'M' with no path is malformed


def test_untracked_changes() -> None:
    assert untracked_changes(["a.py", "", "b.py"]) == [FileChange("A", "a.py"), FileChange("A", "b.py")]


# --- side_map (direction handling) ----------------------------------------------
def test_side_map_target_keeps_adds_drops_deletes() -> None:
    changes = [FileChange("A", "new.py"), FileChange("M", "mod.py"), FileChange("D", "gone.py")]
    assert side_map(changes, "target") == {"new.py": "A", "mod.py": "M"}   # delete dropped


def test_side_map_base_keeps_deletes_drops_adds() -> None:
    changes = [FileChange("A", "new.py"), FileChange("M", "mod.py"), FileChange("D", "gone.py")]
    assert side_map(changes, "base") == {"gone.py": "D", "mod.py": "M"}    # add dropped


def test_side_map_rename_keyed_per_side() -> None:
    changes = [FileChange("R", "new/x.py", old_path="old/x.py")]
    assert side_map(changes, "target") == {"new/x.py": "R"}   # new end sees the new path
    assert side_map(changes, "base") == {"old/x.py": "R"}     # old end sees the old path


def test_side_map_rejects_bad_side() -> None:
    try:
        side_map([], "sideways")
    except ValueError:
        return
    assert False, "expected ValueError for a bad map_side"


# --- project_changes: direction B (map = newer/target end, Y -> X) --------------
def test_project_created_on_target_side() -> None:
    # A component whose source file is brand-new between Y and X reads as CREATED.
    model = make_model([make_component("C1", source="src/new.py:1")])
    changes = [FileChange("A", "src/new.py")]
    assert project_changes(model, changes, "target") == {"C1": CREATED}


def test_project_modified_on_target_side() -> None:
    model = make_model([make_component("C1", source="src/a.py:10")])
    changes = [FileChange("M", "src/a.py")]
    assert project_changes(model, changes, "target") == {"C1": MODIFIED}


def test_project_target_ignores_deletions() -> None:
    # A file deleted before X isn't in the current (newer) map, so nothing is projected.
    model = make_model([make_component("C1", source="src/a.py:10")])
    changes = [FileChange("D", "src/a.py")]
    assert project_changes(model, changes, "target") == {}


# --- project_changes: direction A (map = older/base end, X -> now) --------------
def test_project_deleted_on_base_side() -> None:
    model = make_model([make_component("C1", source="src/a.py:10")])
    changes = [FileChange("D", "src/a.py")]
    assert project_changes(model, changes, "base") == {"C1": DELETED}


def test_project_base_ignores_additions() -> None:
    # New code after X has no element in the (older) map — additions project to nothing.
    model = make_model([make_component("C1", source="src/a.py:10")])
    changes = [FileChange("A", "src/brand_new.py")]
    assert project_changes(model, changes, "base") == {}


def test_project_base_modified() -> None:
    model = make_model([make_component("C1", source="src/a.py:10")])
    changes = [FileChange("M", "src/a.py")]
    assert project_changes(model, changes, "base") == {"C1": MODIFIED}


# --- classification nuances -----------------------------------------------------
def test_owned_file_change_is_modify_not_create() -> None:
    # The canonical home (source) is untouched; an OWNED file was added. Element still exists -> MODIFIED.
    model = make_model([make_component("C1", source="src/main.py:1", files=["src/main.py", "src/helper.py"])])
    changes = [FileChange("A", "src/helper.py")]
    assert project_changes(model, changes, "target") == {"C1": MODIFIED}


def test_source_add_is_create_even_with_other_owned_files() -> None:
    model = make_model([make_component("C1", source="src/main.py:1", files=["src/main.py"])])
    changes = [FileChange("A", "src/main.py")]
    assert project_changes(model, changes, "target") == {"C1": CREATED}


def test_dir_anchor_matches_children() -> None:
    model = make_model(subsystems=[Group(id="S1", name="S1", source="src/pkg/")])
    changes = [FileChange("M", "src/pkg/deep/mod.py")]
    assert project_changes(model, changes, "target") == {"S1": MODIFIED}


def test_dir_anchor_no_match_outside_prefix() -> None:
    model = make_model(subsystems=[Group(id="S1", name="S1", source="src/pkg/")])
    changes = [FileChange("M", "src/other/mod.py")]
    assert project_changes(model, changes, "target") == {}


def test_entity_and_component_projected_together() -> None:
    model = make_model(
        components=[make_component("C1", source="src/a.py:1")],
        entities=[Entity(id="E1", name="E1", source="src/models.py:5")],
    )
    changes = [FileChange("M", "src/a.py"), FileChange("A", "src/models.py")]
    assert project_changes(model, changes, "target") == {"C1": MODIFIED, "E1": CREATED}


def test_untouched_elements_absent() -> None:
    model = make_model([make_component("C1", source="src/a.py:1"), make_component("C2", source="src/b.py:1")])
    changes = [FileChange("M", "src/a.py")]
    assert project_changes(model, changes, "target") == {"C1": MODIFIED}   # C2 untouched -> absent


# --- parse_unified_diff ---------------------------------------------------------
def test_parse_unified_diff_line_numbers_and_ops() -> None:
    text = (
        "diff --git a/f.py b/f.py\n"
        "index 111..222 100644\n"
        "--- a/f.py\n"
        "+++ b/f.py\n"
        "@@ -1,3 +1,3 @@\n"
        " a\n"
        "-b\n"
        "+B\n"
        " c\n"
    )
    rows = parse_unified_diff(text)
    assert [(r.op, r.old_ln, r.new_ln, r.text) for r in rows] == [
        ("hunk", None, None, "@@ -1,3 +1,3 @@"),
        ("ctx", 1, 1, "a"),
        ("del", 2, None, "b"),
        ("add", None, 2, "B"),
        ("ctx", 3, 3, "c"),
    ]


def test_parse_unified_diff_added_file_all_adds() -> None:
    text = "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,2 @@\n+one\n+two\n"
    rows = parse_unified_diff(text)
    assert [(r.op, r.new_ln) for r in rows if r.op == "add"] == [("add", 1), ("add", 2)]


def test_parse_unified_diff_preamble_skipped_and_no_newline_marker() -> None:
    text = "@@ -1,1 +1,1 @@\n-old\n+new\n\\ No newline at end of file\n"
    rows = parse_unified_diff(text)
    assert [r.op for r in rows] == ["hunk", "del", "add"]   # the "\ No newline" marker dropped


def test_parse_unified_diff_empty_before_first_hunk() -> None:
    assert parse_unified_diff("diff --git a/x b/x\nindex 1..2\n") == []


if __name__ == "__main__":
    import sys

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
    sys.exit(0)
