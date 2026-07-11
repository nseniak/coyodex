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
