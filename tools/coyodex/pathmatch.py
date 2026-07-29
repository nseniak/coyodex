#!/usr/bin/env python3
"""Segment-wise path globbing — the ONE matcher shared by every path-rule surface.

Two features match repo-relative paths against author-written globs: `coyodex reconcile`
(`source_glob` rules) and the analysis ignore file (`.coyodex/.ignore`). They want the same
semantics, so they share this implementation rather than growing two subtly different ones — a
second matcher would have to re-learn the four bugs already fixed here (see `match_segments`).

Stdlib-only (the `cli.py` dependency firewall): `fnmatch` per segment, never a translated regex.
"""
from __future__ import annotations

import fnmatch


def match_segments(pat: list[str], path: list[str]) -> bool:
    """Segment-wise glob match. `**` consumes zero or more whole segments; every other segment is
    matched by `fnmatch` against ONE path segment (a segment contains no `/`, so `*` cannot cross a
    directory boundary — the shell/.gitignore distinction).

    Written as an explicit walk rather than a translated pattern because the string-surgery version
    of this was wrong in four separate ways at once: `a/*/b` never matched (the tail was measured
    from the FIRST star, so any later segment read as "crossing a boundary"), `a/**/nope` matched
    everything under `a/` (everything after `**` was discarded), a leading `**` matched every path
    in the map, and a trailing `/` matched nothing."""
    if not pat:
        return not path
    head, rest = pat[0], pat[1:]
    if head == "**":
        if not rest:
            return True                                   # trailing ** — everything at/below here
        return any(match_segments(rest, path[k:]) for k in range(len(path) + 1))
    if not path or not fnmatch.fnmatchcase(path[0], head):
        return False
    return match_segments(rest, path[1:])


def matches(pattern: str, path: str) -> bool:
    """Does this repo-relative path satisfy the glob?

    A wildcard-free pattern additionally matches everything BENEATH it, so `mee6/plugins` and
    `mee6/plugins/` both behave like the directory the author obviously meant."""
    if not path:
        return False
    pat = [s for s in pattern.strip().strip("/").split("/") if s]
    parts = [s for s in path.strip("/").split("/") if s]
    if not pat:
        return False
    if match_segments(pat, parts):
        return True
    if not any(ch in pattern for ch in "*?"):             # a plain directory prefix
        return len(parts) > len(pat) and parts[:len(pat)] == pat
    return False
