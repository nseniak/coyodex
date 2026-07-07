#!/usr/bin/env python3
"""Build the viewer's file-browser tree + map-coverage overlay.

The mapped repo's real folder/file structure, each entry tagged by how the project map covers it.
This is NO LONGER embedded in the HTML — the viewer's file browser is a FULL-mode feature served by
`coyodex serve` (see serve.py), which builds the same tree from git at the map's commit and reuses
the pure pieces here (``build_tree`` + ``node_path_index``). ``build_file_tree`` keeps the disk-walk
variant (via ``iter_source_files`` — shared CODE, never DATA, so the render dependency firewall
holds). Coverage tags:

  cov = 'self'  : a node's source ref points exactly at this path  -> strong "mapped" marker
        'under' : this path sits under a folder a node anchors      -> covered
        'has'   : a folder that merely CONTAINS covered descendants  -> partial
        'none'  : nothing in the map points here                     -> unmapped (dimmed)

So the browser doubles as a coverage view: at a glance you see what the map describes and what it
misses. `sel` is the node a click on the row selects — the exact node, else the nearest ANCESTOR
folder-node (the "finer grain" rule), else None for an unmapped row. `node` is the exact (primary)
node id (set only when cov == 'self'); `others` carries any further node ids that ALSO anchor this
exact path (e.g. a component and an entity sharing one file), so a path collision surfaces every
match instead of only the tie-break winner. The viewer wires this both ways: focusing a graph node
highlights its row; clicking a mapped row navigates to and selects the node (+ its `others`, if any).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

from coyodex.viewer.build_graph import GraphDict

# Group kinds collapse their children into one box; a leaf node (component/entity/dep) is "finer
# grain" and therefore wins a path collision against a group node (subsystem/subdomain).
_GROUP_KINDS = {"subsystem", "subdomain"}
_URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)


class FileTreeNode(TypedDict):
    name: str
    path: str            # repo-relative, posix; "" for the root
    dir: bool
    node: str | None     # exact node id mapping to this path (set iff cov == 'self')
    others: list[str]    # other node ids that ALSO exactly anchor this path (a path collision node_path_index
                          # no longer silently drops) — empty unless `node` is set and collided
    sel: str | None      # node to select on a click (exact, else nearest ancestor folder-node)
    cov: str             # 'self' | 'under' | 'has' | 'none'
    mapped: int          # count of exact-mapped nodes strictly INSIDE (descendants) — the folder's badge
    children: list["FileTreeNode"]


def _clean_node_path(file: str, line: int | None) -> str:
    """Mirror the viewer's ``cleanPath``: drop a ``#Lnn`` / ``:nn`` line anchor and any surrounding
    slashes, so a map href ('src/app.py#L42', 'src/api/') reduces to a bare repo-relative path."""
    p = re.sub(r"#L\d+$", "", file)
    if line is not None:
        p = re.sub(r":" + str(line) + r"$", "", p)
    return p.strip("/")


def _is_local_ref(file: str) -> bool:
    """True for an in-repo path/dir ref; False for an off-repo URL (http(s)://, …) — mirrors the
    viewer's ``localRef`` so only paths that can resolve into the tree are indexed."""
    return not _URL_RE.match(file)


def node_path_index(graph: GraphDict) -> dict[str, list[str]]:
    """Map each in-repo path a node anchors -> ALL node ids that anchor it, primary first. On a
    collision (two+ nodes anchored at the same path — most often two leaves legitimately sharing a
    file) a leaf node (component/entity/dep) is the PRIMARY over a group node (subsystem/subdomain),
    matching the 'finer grain' selection rule, and ties within the same category keep insertion order
    (`graph["nodes"]` iteration order) — same tie-break the old single-id index used. Unlike that old
    index, the rest of the collision is kept (not dropped), so the viewer can surface every node a
    file maps to instead of only the winner."""
    by_path: dict[str, list[str]] = {}
    for nid, node in graph["nodes"].items():
        file = node.get("file")
        if not isinstance(file, str) or not _is_local_ref(file):
            continue
        line = node.get("line")
        path = _clean_node_path(file, line if isinstance(line, int) else None)
        if not path:
            continue
        by_path.setdefault(path, []).append(nid)
    out: dict[str, list[str]] = {}
    for path, ids in by_path.items():
        if len(ids) == 1:
            out[path] = ids
            continue
        leaves = [nid for nid in ids if str(graph["nodes"][nid].get("kind")) not in _GROUP_KINDS]
        groups = [nid for nid in ids if str(graph["nodes"][nid].get("kind")) in _GROUP_KINDS]
        out[path] = leaves + groups
    return out


class _Dir:
    """Mutable folder during the build: child dirs by name, child files (name -> repo-relative path)."""

    def __init__(self, name: str, path: str) -> None:
        self.name = name
        self.path = path
        self.dirs: dict[str, _Dir] = {}
        self.files: dict[str, str] = {}


def _to_node(d: _Dir) -> FileTreeNode:
    """Freeze a `_Dir` into a JSON tree node: child dirs (alpha) before child files (alpha)."""
    children: list[FileTreeNode] = [_to_node(d.dirs[name]) for name in sorted(d.dirs, key=str.lower)]
    for name in sorted(d.files, key=str.lower):
        children.append({"name": name, "path": d.files[name], "dir": False, "node": None, "others": [],
                         "sel": None, "cov": "none", "mapped": 0, "children": []})
    return {"name": d.name, "path": d.path, "dir": True, "node": None, "others": [],
            "sel": None, "cov": "none", "mapped": 0, "children": children}


def _annotate(entry: FileTreeNode, node_paths: dict[str, list[str]], ancestor_node: str | None) -> tuple[str, int]:
    """Tag `entry` (and its subtree) with `node`/`others`/`sel`/`cov`/`mapped`. `ancestor_node` is the
    id of the nearest ANCESTOR folder a node anchors (None if none) — it both flows the 'under'
    coverage down and is the click target for a row no node points at directly. Returns (cov,
    mapped-nodes-in-subtree INCLUDING self) so a parent dir can roll its children up to 'has' and sum
    the badge count."""
    ids = node_paths.get(entry["path"]) if entry["path"] else None
    exact = ids[0] if ids else None
    entry["node"] = exact
    entry["others"] = ids[1:] if ids else []  # the rest of a path collision — kept, not dropped
    entry["sel"] = exact if exact is not None else ancestor_node
    nxt = exact if exact is not None else ancestor_node
    self_mapped = 1 if exact is not None else 0
    if entry["dir"]:
        results = [_annotate(c, node_paths, nxt) for c in entry["children"]]
        entry["mapped"] = sum(m for _, m in results)  # descendants only (the badge count)
        if exact is not None:
            entry["cov"] = "self"
        elif ancestor_node is not None:
            entry["cov"] = "under"
        elif any(cov != "none" for cov, _ in results):
            entry["cov"] = "has"
        else:
            entry["cov"] = "none"
        return entry["cov"], self_mapped + entry["mapped"]
    entry["mapped"] = 0
    entry["cov"] = "self" if exact is not None else ("under" if ancestor_node is not None else "none")
    return entry["cov"], self_mapped


def build_tree(rel_paths: list[str], node_paths: dict[str, list[str]], root_name: str = "") -> FileTreeNode:
    """Pure tree builder (no IO): nest `rel_paths` (repo-relative posix files) into folders, then
    overlay map coverage from `node_paths`. Split out from the git walk so it unit-tests directly."""
    root = _Dir(root_name, "")
    for rp in rel_paths:
        parts = [p for p in rp.split("/") if p]
        if not parts:
            continue
        cur = root
        for i, part in enumerate(parts[:-1]):
            cur = cur.dirs.setdefault(part, _Dir(part, "/".join(parts[: i + 1])))
        cur.files[parts[-1]] = rp
    tree = _to_node(root)
    _annotate(tree, node_paths, None)
    return tree


def build_file_tree(graph: GraphDict, repo_root: str) -> FileTreeNode | None:
    """Walk the mapped repo and overlay map coverage. None when the root has no walkable files
    (not a repo / empty) — the viewer then simply omits the browser pane.

    The git walk is imported lazily here (not at module load), the same way the validator pulls it,
    so importing this module never drags in the pre-index code path."""
    from coyodex.preindex_lib import iter_source_files  # lazy: keep render free of the pre-index path

    root = Path(repo_root)
    if not root.exists():
        return None
    walk = iter_source_files(root)
    rels = sorted(p.relative_to(walk.root).as_posix() for p in walk.files)
    if not rels:
        return None
    return build_tree(rels, node_path_index(graph), root_name=walk.root.name or repo_root)
