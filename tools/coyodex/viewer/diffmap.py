"""Project a git diff onto the map's elements — the pure core of the mechanical diff viewer.

Phase 1 of the diff viewer (see internal/docs/plan/50-diff-viewer.md). Given a list of changed
files (already produced from `git diff` by the caller — this module runs NO git and does NO I/O) and
a loaded `ProjectModel`, decide which map elements *contain changes* and classify each as
**created / modified / deleted**. The projection walks the map's existing `path:line` /
`dir/` anchors, so it needs no new metadata.

Direction handling is the subtle part. The map is pinned to one commit, so its anchors correspond
to exactly ONE end of the diff:

- **`map_side="base"`** — the map is the OLDER end (direction A: pin X → now). Anchors match the
  base side; a file added after X has no element (skip it), a deleted file marks its element gone.
- **`map_side="target"`** — the map is the NEWER end (direction B: older Y → pin X). Anchors match
  the target side; a file added between Y and X marks its element *created*, a file deleted before X
  isn't in the current map (skip it).

Stdlib-only, importing only `model` + `anchors` (no git, no serve) so the diff endpoints can import
it without a cycle.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from coyodex.anchors import DIR_ANCHOR, strip_anchor
from coyodex.model import Component, Entity, Group, ProjectModel

# A target endpoint sentinel meaning "the current working tree" rather than a committed ref. The git
# producer (serve.py) special-cases it; this module only ever sees the resulting FileChange list.
WORKTREE = "WORKTREE"

# The change kinds a projected element can carry (mirrors the viewer's BADGE table: added/modified/
# deleted; "rippled" is a downstream-adjacency state computed elsewhere, not a direct file change).
CREATED = "created"
MODIFIED = "modified"
DELETED = "deleted"


@dataclass(frozen=True)
class FileChange:
    """One changed path from a git diff, normalized. `path` is the TARGET-side path for A/M/R and the
    BASE-side path for D (the file only exists on that side). `old_path` carries the base-side path
    of a rename (R); it is None otherwise."""
    status: str               # 'A' | 'M' | 'D' | 'R' (single letter; rename similarity stripped)
    path: str
    old_path: str | None = None


# ── parsing `git diff --name-status -M` output (pure text → FileChange) ────────────────────────────

def parse_name_status(text: str) -> list[FileChange]:
    """Parse the tab-separated output of `git diff --name-status -M <base> <target>`.

    Lines look like `M\\tpath`, `A\\tpath`, `D\\tpath`, or `R100\\told\\tnew` (rename, with a
    similarity score glued to the R). Copy (`C`) is treated as an add of the new path; type-change
    (`T`) as a modify. Blank / malformed lines are skipped."""
    out: list[FileChange] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        code = parts[0].strip()
        letter = code[:1]
        if letter in ("R", "C") and len(parts) >= 3:
            old, new = parts[1], parts[2]
            # a copy leaves the original in place, so only the NEW path is a change; a rename moves it
            out.append(FileChange(status="R" if letter == "R" else "A", path=new,
                                  old_path=old if letter == "R" else None))
        elif letter in ("A", "M", "D", "T") and len(parts) >= 2:
            out.append(FileChange(status="M" if letter == "T" else letter, path=parts[1]))
    return out


def untracked_changes(paths: list[str]) -> list[FileChange]:
    """New files git doesn't track yet (from `git ls-files --others --exclude-standard`) — each is an
    add on the target side. Only meaningful when the target is the working tree."""
    return [FileChange(status="A", path=p) for p in paths if p]


# ── parsing a single-file unified diff into renderable rows (pure text → DiffRow) ─────────────────

@dataclass(frozen=True)
class DiffRow:
    """One line of a rendered file diff. `op` is 'hunk' (a `@@` separator), 'ctx' (unchanged), 'add',
    or 'del'. `old_ln`/`new_ln` are 1-based line numbers on each side (None where the line doesn't
    exist on that side, and on a 'hunk' row). `text` is the line content (no +/-/space prefix)."""
    op: str
    old_ln: int | None
    new_ln: int | None
    text: str


_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$")


def parse_unified_diff(text: str) -> list[DiffRow]:
    """Parse `git diff`'s unified output for ONE file into display rows. Header lines (`diff --git`,
    `index`, `---`, `+++`) are skipped; `@@` starts a hunk and resets the line counters; the `\\ No
    newline at end of file` marker is dropped. Text before the first `@@` (an empty/binary/pure-mode
    diff) yields no rows."""
    rows: list[DiffRow] = []
    old_ln = new_ln = 0
    in_hunk = False
    for line in text.split("\n"):
        m = _HUNK_RE.match(line)
        if m:
            old_ln, new_ln = int(m.group(1)), int(m.group(2))
            rows.append(DiffRow("hunk", None, None, line))
            in_hunk = True
            continue
        if not in_hunk:
            continue                              # skip the diff/index/---/+++ preamble
        if line == "":
            continue                              # trailing split artifact of the final newline (a real
            #                                       blank context line is " ", never bare "")
        if line.startswith("\\"):
            continue                              # "\ No newline at end of file"
        if line.startswith("+"):
            rows.append(DiffRow("add", None, new_ln, line[1:]))
            new_ln += 1
        elif line.startswith("-"):
            rows.append(DiffRow("del", old_ln, None, line[1:]))
            old_ln += 1
        else:                                     # ' ' context (leading space stripped)
            rows.append(DiffRow("ctx", old_ln, new_ln, line[1:] if line.startswith(" ") else line))
            old_ln += 1
            new_ln += 1
    return rows


# ── the side map: changed paths as the map's anchors see them ─────────────────────────────────────

def side_map(changes: list[FileChange], map_side: str) -> dict[str, str]:
    """Changed paths keyed the way the map's anchors reference them, with a per-path status.

    `map_side="target"` keys by the new/target path (A, M, R-new) and DROPS deletions — a file gone
    before the map's commit is not in the current map. `map_side="base"` keys by the old/base path
    (D, M, R-old) and DROPS additions — a file added after the map's commit has no element yet."""
    if map_side not in ("base", "target"):
        raise ValueError(f"map_side must be 'base' or 'target', got {map_side!r}")
    out: dict[str, str] = {}
    for c in changes:
        if map_side == "target":
            if c.status in ("A", "M"):
                out[c.path] = c.status
            elif c.status == "R":               # element now lives at the new path
                out[c.path] = "R"
            # c.status == "D": no target path -> not in the current (newer) map
        else:  # base
            if c.status in ("D", "M"):
                out[c.path] = c.status
            elif c.status == "R":               # element lived at the old path
                out[c.old_path or c.path] = "R"
            # c.status == "A": no base path -> not in the current (older) map
    return out


# ── element homes (which files/dirs each element is anchored to) ──────────────────────────────────

@dataclass(frozen=True)
class _Home:
    id: str
    kind: str                 # 'component' | 'subsystem' | 'subdomain' | 'entity'
    files: frozenset[str]     # exact file paths (line suffix stripped)
    dirs: frozenset[str]      # directory prefixes (anchors ending in '/')
    primary: str | None       # the canonical home file (source), if any — decides created/deleted


def _split(anchor: str | None) -> tuple[set[str], set[str]]:
    """One anchor string → (file-paths, dir-prefixes). A `dir/` anchor is a prefix; anything else is
    a file whose `:line` suffix is stripped. Empty / None yields nothing."""
    if not anchor:
        return set(), set()
    if DIR_ANCHOR.match(anchor):
        return set(), {anchor}
    return {strip_anchor(anchor)}, set()


def _homes(model: ProjectModel) -> list[_Home]:
    """Every node-level element that carries source anchors, with its file/dir footprint. Behavioral
    elements (use cases, happy path) and edges are derived elsewhere, not here."""
    homes: list[_Home] = []
    for c in model.components:
        files, dirs = _split(c.source)
        primary_files = set(files)
        for f in c.files:                       # a component also owns a plain file list
            fset, dset = _split(f)
            files |= fset
            dirs |= dset
        primary = next(iter(primary_files), None)  # the `source` file is the canonical home
        homes.append(_Home(c.id, "component", frozenset(files), frozenset(dirs), primary))
    for g in model.subsystems:
        files, dirs = _split(g.source)
        homes.append(_Home(g.id, "subsystem", frozenset(files), frozenset(dirs),
                           next(iter(files), None)))
    for g in model.subdomains:
        files, dirs = _split(g.source)
        homes.append(_Home(g.id, "subdomain", frozenset(files), frozenset(dirs),
                           next(iter(files), None)))
    for e in model.entities:
        files, dirs = _split(e.source)
        homes.append(_Home(e.id, "entity", frozenset(files), frozenset(dirs),
                           next(iter(files), None)))
    return homes


def _classify(home: _Home, sm: dict[str, str], map_side: str) -> str | None:
    """The change kind for one element given the side map, or None if it is untouched.

    Created/deleted hinge on the element's *canonical home* (its `source` file): the element is
    born/gone only when that home file is added/removed. Any other touched file (an owned file, a
    file under a dir anchor) is a MODIFY — the element still exists, its code changed."""
    touched = {sm[f] for f in home.files if f in sm}
    for d in home.dirs:                          # a dir anchor matches any changed path beneath it
        for p, st in sm.items():
            if p.startswith(d):
                touched.add(st)
    if not touched:
        return None
    home_st = sm.get(home.primary) if home.primary else None
    if map_side == "target" and home_st == "A":
        return CREATED
    if map_side == "base" and home_st == "D":
        return DELETED
    return MODIFIED


def project_changes(model: ProjectModel, changes: list[FileChange], map_side: str) -> dict[str, str]:
    """Map element id → change kind (created/modified/deleted) for every touched node element.

    The single entry point: build the side map for the direction, then classify each element's file
    footprint against it. Untouched elements are absent from the result."""
    sm = side_map(changes, map_side)
    out: dict[str, str] = {}
    for home in _homes(model):
        kind = _classify(home, sm, map_side)
        if kind is not None:
            out[home.id] = kind
    return out
