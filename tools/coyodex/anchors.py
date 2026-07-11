"""One home for coyodex source-anchor format + parsing.

Stdlib-only and importing NO coyodex module, so any module (validate, audit, json_schema, the eval)
can depend on it without a cycle. Centralizes what used to be four near-duplicate regexes.

A source anchor is either a repo-relative **file** ref — a path with an OPTIONAL `:line` /
`:line-line` suffix — or a **directory** ref ending in `/`. File-ness is NOT decided by "has a dot":
an extensionless file that carries a line (`Dockerfile:1`, `Makefile:6-9`) is a valid file anchor.
The deterministic judge of whether a path is real is the existence check, not the shape.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# A file anchor: EITHER a dotted filename with an optional line (`a/b.py`, `a/b.py:12`, `a/b.py:12-18`)
# OR anything carrying a `:line` suffix (so extensionless `Dockerfile:1` / `Makefile:6-9` qualify).
# A bare extensionless path with no line (`Dockerfile`) is intentionally NOT a file anchor — without a
# line or a dot it is indistinguishable from a directory that forgot its trailing slash.
FILE_ANCHOR = re.compile(r"^\S+\.\w+(?::\d+(?:-\d+)?)?$|^\S+:\d+(?:-\d+)?$")
DIR_ANCHOR = re.compile(r"^\S+/$")


def is_file_anchor(s: str) -> bool:
    """`s` is a well-formed file anchor (`path`, `path:line`, or `path:line-line`)."""
    return bool(FILE_ANCHOR.match(s))


def is_anchor(s: str) -> bool:
    """`s` is a well-formed anchor — a file ref OR a bare directory ref (`path/`)."""
    return bool(FILE_ANCHOR.match(s) or DIR_ANCHOR.match(s))


# ── anchor parsing (the shared parsing regexes, one home) ─────────────────────────────────────────

# A drill anchor embedded anywhere in a cell: `path:line` or `path#Lnnn` (finder, not a full-string
# match). Was `audit_model._FILEREF`.
FILEREF = re.compile(r"[\w./-]+(?:#L\d+|:\d+)")
# A trailing `:line` / `:line-line` suffix — stripped to recover the bare path. Was
# `validate_analysis._LINE_ANCHOR`.
LINE_ANCHOR = re.compile(r":\d+(?:-\d+)?$")


def strip_anchor(href: str) -> str:
    """The bare path from a `path:line` / `path:line-line` anchor — resolving a source/anchor href
    against the repo needs the path alone."""
    return LINE_ANCHOR.sub("", href)


# ── anchor-drift comparator (Phase G — Layer 2) ───────────────────────────────────────────────────

# A whole-string anchor split into (path, line-lo, line-hi). Accepts `:n`, `:n-m`, `#Ln`, `#Ln-Lm`;
# a bare path yields lo=hi=None; anything with a space (prose) does not match.
_ANCHOR_PARSE = re.compile(r"^(?P<path>\S+?)(?:(?::|#L)(?P<lo>\d+)(?:-L?(?P<hi>\d+))?)?$")


@dataclass(frozen=True)
class AnchorLoc:
    path: str
    lo: int | None
    hi: int | None


@dataclass(frozen=True)
class DriftResult:
    drifted: bool
    stored: str          # the stored anchor, verbatim
    reported: int        # the consensus (median) line the skeptics reported
    same_file: bool      # the reported evidence names the same file as the stored anchor
    distance: int | None  # line distance from the stored anchor/range when same_file, else None


def parse_anchor(s: str) -> AnchorLoc | None:
    """`(path, lo, hi)` for a `path:line` / `path:line-line` / `path#Lnnn` string, `lo=hi=None` for a
    bare path, and `None` for prose (anything that is not a whole-string path[:line])."""
    m = _ANCHOR_PARSE.match(s.strip())
    if not m:
        return None
    lo = int(m.group("lo")) if m.group("lo") else None
    hi = int(m.group("hi")) if m.group("hi") else lo
    return AnchorLoc(path=m.group("path"), lo=lo, hi=hi)


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def anchor_drift(stored: str | None, reported: list[str], tolerance: int) -> DriftResult | None:
    """Whether the skeptics' reported call-site line drifts from the stored anchor, for a CONFIRMED
    claim. `None` (not comparable) when the stored anchor is absent / line-less or no reported string
    carries a parseable `file:line`. Different file → drift; same file → drift when the consensus
    (median) reported line falls more than `tolerance` outside the stored line/range."""
    if not stored:
        return None
    s = parse_anchor(stored)
    if s is None or s.lo is None:
        return None
    locs = [loc for loc in (parse_anchor(r) for r in reported) if loc is not None and loc.lo is not None]
    if not locs:
        return None
    same = [loc for loc in locs if _basename(loc.path) == _basename(s.path)]
    if same:
        lines = sorted(loc.lo for loc in same if loc.lo is not None)
        med = lines[len(lines) // 2]
        lo, hi = s.lo, (s.hi if s.hi is not None else s.lo)
        distance = lo - med if med < lo else (med - hi if med > hi else 0)
        return DriftResult(drifted=distance > tolerance, stored=stored, reported=med,
                           same_file=True, distance=distance)
    lines = sorted(loc.lo for loc in locs if loc.lo is not None)
    med = lines[len(lines) // 2]
    return DriftResult(drifted=True, stored=stored, reported=med, same_file=False, distance=None)
