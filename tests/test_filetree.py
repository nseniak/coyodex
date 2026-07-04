#!/usr/bin/env python3
"""Tests for the viewer's file-browser tree + map-coverage overlay (coyodex.viewer.filetree).

Stdlib-only — no pytest required. Run either way (needs an editable install: `make deps`):
    python3 tests/test_filetree.py
    pytest tests/test_filetree.py

Covers the two pure pieces — node_path_index (map href -> node id, with the 'finer grain' tie-break)
and build_tree (nesting + coverage shading + click target) — plus one end-to-end build_file_tree over a
real temp directory (no git: exercises the os.walk fallback in iter_source_files, no patching).
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, cast

from coyodex.viewer.build_graph import GraphDict
from coyodex.viewer.filetree import (
    FileTreeNode,
    build_file_tree,
    build_tree,
    node_path_index,
)


# --- builders (no fixtures; explicit make_* helpers) ----------------------------
def make_node(nid: str, kind: str, file: str | None = None,
              line: int | None = None, parent: str | None = None) -> dict[str, Any]:
    return {"id": nid, "kind": kind, "name": nid, "file": file, "line": line,
            "fields": {}, "parent": parent}


def make_graph(*nodes: dict[str, Any]) -> GraphDict:
    return cast(GraphDict, {
        "commit": None, "committed": None, "title": None, "goal": None,
        "nodes": {n["id"]: n for n in nodes}, "edges": [], "gp": [], "roles": [],
    })


def find_entry(tree: FileTreeNode, path: str) -> FileTreeNode | None:
    if tree["path"] == path:
        return tree
    for c in tree["children"]:
        hit = find_entry(c, path)
        if hit is not None:
            return hit
    return None


# --- node_path_index ------------------------------------------------------------
def test_node_path_index_strips_anchors_and_skips_urls() -> None:
    graph = make_graph(
        make_node("C1", "component", "src/api.py"),
        make_node("C2", "component", "src/db.py#L10", line=10),
        make_node("C3", "component", "src/q.py:5", line=5),
        make_node("S1", "subsystem", "src/"),
        make_node("D1", "dep", "https://example.com/pkg"),  # off-repo URL -> excluded
    )
    idx = node_path_index(graph)
    assert idx["src/api.py"] == ["C1"]
    assert idx["src/db.py"] == ["C2"]      # #L10 stripped
    assert idx["src/q.py"] == ["C3"]       # :5 stripped
    assert idx["src"] == ["S1"]            # dir anchor, trailing slash stripped
    assert all(not k.startswith("http") for k in idx)  # the URL dep is not indexed


def test_node_path_index_leaf_wins_collision_either_order() -> None:
    # A leaf (component) and a group (subsystem) claim the same path — the leaf is "finer grain"
    # and must be PRIMARY (first) regardless of insertion order, but the group is kept, not dropped.
    g1 = make_graph(make_node("S1", "subsystem", "src/x.py"), make_node("C1", "component", "src/x.py"))
    g2 = make_graph(make_node("C1", "component", "src/x.py"), make_node("S1", "subsystem", "src/x.py"))
    assert node_path_index(g1)["src/x.py"] == ["C1", "S1"]
    assert node_path_index(g2)["src/x.py"] == ["C1", "S1"]


def test_node_path_index_keeps_both_leaves_on_collision() -> None:
    # Two leaves (component + entity) legitimately anchored to the same file: neither is dropped, and
    # the first one inserted (graph["nodes"] iteration order) stays primary — same as before this
    # collision was ever kept, just no longer silently discarding the second one.
    graph = make_graph(make_node("C1", "component", "src/x.py"), make_node("E1", "entity", "src/x.py"))
    assert node_path_index(graph)["src/x.py"] == ["C1", "E1"]


# --- build_tree: structure ------------------------------------------------------
def test_build_tree_nests_and_orders_dirs_before_files() -> None:
    tree = build_tree(["src/api.py", "src/util.py", "README.md", "src/sub/deep.py"], {})
    # top level: the 'src' dir before the 'README.md' file
    top = [(c["name"], c["dir"]) for c in tree["children"]]
    assert top == [("src", True), ("README.md", False)]
    src = find_entry(tree, "src")
    assert src is not None
    # inside src: child dir 'sub' before files 'api.py','util.py' (alpha within each group)
    assert [(c["name"], c["dir"]) for c in src["children"]] == [("sub", True), ("api.py", False), ("util.py", False)]


# --- build_tree: coverage shading + click target --------------------------------
def test_coverage_self_under_has_none() -> None:
    node_paths = {"src": ["S1"], "src/api.py": ["C1"]}
    tree = build_tree(["src/api.py", "src/util.py", "README.md", "docs/guide.md"], node_paths)

    src = find_entry(tree, "src")
    api = find_entry(tree, "src/api.py")
    util = find_entry(tree, "src/util.py")
    readme = find_entry(tree, "README.md")
    docs = find_entry(tree, "docs")
    assert src and api and util and readme and docs

    assert (src["cov"], src["node"], src["sel"]) == ("self", "S1", "S1")     # a node anchors this dir
    assert (api["cov"], api["node"], api["sel"]) == ("self", "C1", "C1")     # exact node wins over the folder
    assert (util["cov"], util["node"], util["sel"]) == ("under", None, "S1") # covered by the src/ folder-node
    assert (readme["cov"], readme["sel"]) == ("none", None)                  # nothing maps here
    assert docs["cov"] == "none"                                            # whole subtree unmapped
    assert src["mapped"] == 1                                               # one exact-mapped node inside (api.py)
    assert api["mapped"] == 0                                               # a file holds nothing


def test_dir_with_only_some_covered_children_is_partial() -> None:
    # 'src' itself isn't a node and isn't under one, but contains a mapped file -> 'has' (partial).
    tree = build_tree(["src/api.py", "src/util.py"], {"src/api.py": ["C1"]})
    src = find_entry(tree, "src")
    util = find_entry(tree, "src/util.py")
    assert src and util
    assert (src["cov"], src["sel"]) == ("has", None)   # partial folder maps to no single node
    assert util["cov"] == "none"
    assert tree["cov"] == "has"                         # root rolls up its partial child
    assert src["mapped"] == 1                           # badge: one mapped item inside the partial folder


def test_mapped_count_sums_descendants_at_each_level() -> None:
    # The badge count is the number of exact-mapped nodes strictly inside, summed at every level.
    tree = build_tree(["a/x.py", "a/b/y.py", "a/b/z.py"], {"a/x.py": ["C1"], "a/b/y.py": ["C2"]})
    a = find_entry(tree, "a")
    ab = find_entry(tree, "a/b")
    x = find_entry(tree, "a/x.py")
    assert a and ab and x
    assert a["mapped"] == 2    # C1 (a/x.py) + C2 (a/b/y.py)
    assert ab["mapped"] == 1   # only C2 lives under a/b
    assert x["mapped"] == 0    # a file never carries a count
    assert tree["mapped"] == 2 # root sees both


def test_sel_picks_finest_ancestor_folder_node() -> None:
    # Nested folder-nodes: a deep file selects the NEAREST (longest-prefix) ancestor node, not the top one.
    tree = build_tree(["a/b/c.py"], {"a": ["S1"], "a/b": ["C1"]})
    leaf = find_entry(tree, "a/b/c.py")
    assert leaf is not None
    assert (leaf["cov"], leaf["sel"]) == ("under", "C1")  # 'a/b' (C1) is finer than 'a' (S1)


def test_others_carries_the_rest_of_a_path_collision() -> None:
    # A file with more than one node anchored to it: `node` is the primary (first in the list), and
    # `others` keeps the rest instead of silently dropping them (the bug this index used to have).
    tree = build_tree(["src/x.py"], {"src/x.py": ["C1", "E1", "S1"]})
    x = find_entry(tree, "src/x.py")
    assert x is not None
    assert (x["node"], x["others"], x["sel"]) == ("C1", ["E1", "S1"], "C1")


def test_others_empty_when_no_collision() -> None:
    tree = build_tree(["src/x.py"], {"src/x.py": ["C1"]})
    x = find_entry(tree, "src/x.py")
    assert x is not None
    assert x["others"] == []


# --- build_file_tree: end-to-end over a real directory --------------------------
def test_build_file_tree_walks_dir_and_overlays_coverage() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        (root / "src" / "api.py").write_text("x = 1\n", encoding="utf-8")
        (root / "src" / "util.py").write_text("y = 2\n", encoding="utf-8")
        (root / "README.md").write_text("# hi\n", encoding="utf-8")
        graph = make_graph(
            make_node("C1", "component", "src/api.py"),
            make_node("S1", "subsystem", "src/"),
        )
        tree = build_file_tree(graph, str(root))
        assert tree is not None
        api = find_entry(tree, "src/api.py")
        util = find_entry(tree, "src/util.py")
        assert api and util
        assert (api["cov"], api["node"]) == ("self", "C1")
        assert (util["cov"], util["sel"]) == ("under", "S1")


def test_build_file_tree_none_for_empty_root() -> None:
    with tempfile.TemporaryDirectory() as td:
        assert build_file_tree(make_graph(), td) is None  # no walkable files -> pane omitted


# --- runner ---------------------------------------------------------------------
if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
