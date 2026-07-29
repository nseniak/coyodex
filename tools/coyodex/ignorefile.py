#!/usr/bin/env python3
"""`.coyodex/.ignore` — the analysis ignore file.

A repo may hold code that is deliberately NOT part of what the map describes: a fixture tree built
to trip the tooling's own advisories, a vendored copy git tracks, a scratch area. Left in, it
inflates the weight tree, skews the component expectation E, and shows up forever as an unreferenced
directory. `.gitignore` cannot express it (the files are meant to be committed), and a "Coverage
exceptions" extras heading is a different statement — that one says *mapped coarsely, stop warning*,
while this one says *not part of the analysed tree at all*.

So the repo declares it once, next to the map:

    .coyodex/.ignore        # gitignore-like patterns, one per line
    trapdoor/               # the trap fixture — deliberately broken code
    generated/**
    !generated/hand_written.py

Semantics (a deliberate SUBSET of gitignore, matched by `coyodex.pathmatch`):
  * blank lines and `#` comments are skipped
  * a wildcard-free pattern matches that path AND everything beneath it (`trapdoor/` == `trapdoor`)
  * `*`/`?` match within one path segment; `**` spans segments
  * a leading `!` negates, and the LAST matching line wins — so a broad ignore can be narrowed
  * patterns are always repo-relative; a trailing `/` is accepted and ignored (only files are
    ever tested, so "the directory" and "everything under it" are the same statement here)

**It is never silent.** Every surface that walks the tree reports how many files it removed, and
`preindex --report` prints the patterns — because an ignore file is the one input that can hide a
real gap from the coverage check that exists to find gaps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from coyodex.pathmatch import matches

# Where the file lives, relative to the repo root. Inside `.coyodex/` so it travels with the map and
# needs no entry in the repo root; `.coyodex` is already in `DEFAULT_EXCLUDE_DIRS`, so the ignore
# file can never be analysed as part of the tree it describes.
IGNORE_REL = Path(".coyodex") / ".ignore"


@dataclass(frozen=True)
class IgnoreSpec:
    """Parsed `.coyodex/.ignore`. `rules` is ordered; later rules override earlier ones."""

    rules: tuple[tuple[bool, str], ...] = ()      # (negated, pattern)
    path: Path | None = None                      # the file it came from, when one existed
    bad_lines: tuple[str, ...] = field(default=())  # lines that parsed to nothing, for reporting

    def __bool__(self) -> bool:
        return bool(self.rules)

    @property
    def patterns(self) -> list[str]:
        """The pattern lines as authored (with `!` restored), for the report."""
        return [("!" if neg else "") + pat for neg, pat in self.rules]

    def match(self, rel: str) -> bool:
        """Is this repo-relative path ignored? LAST matching rule wins, so `!` can carve an
        exception out of a broad ignore. Returns False when the spec is empty."""
        hit = False
        for negated, pattern in self.rules:
            if matches(pattern, rel):
                hit = not negated
        return hit


_EMPTY = IgnoreSpec()
# Cache keyed by (path, mtime_ns, size): a build calls `iter_source_files` several times (the
# pre-index, then validate's independent re-walk), and re-parsing per call is pure waste. Keying on
# the stat means an edit during a session is still picked up.
_CACHE: dict[tuple[str, int, int], IgnoreSpec] = {}


def parse_ignore(text: str, path: Path | None = None) -> IgnoreSpec:
    """Parse ignore-file text. Pure, so the semantics are testable without a filesystem."""
    rules: list[tuple[bool, str]] = []
    bad: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        pattern = line[1:].strip() if negated else line
        # `matches` treats an all-slash pattern as matching nothing; report it rather than storing a
        # rule that can never fire (a silently-dead pattern reads as coverage the author never got).
        if not pattern.strip("/"):
            bad.append(raw)
            continue
        rules.append((negated, pattern))
    return IgnoreSpec(rules=tuple(rules), path=path, bad_lines=tuple(bad))


def load_ignore(root: Path) -> IgnoreSpec:
    """Read `<root>/.coyodex/.ignore`. Absent or unreadable file → an empty spec that ignores
    nothing, so the walk behaves exactly as it did before the file existed."""
    p = (root / IGNORE_REL).resolve()
    try:
        st = p.stat()
    except OSError:
        return _EMPTY
    key = (str(p), st.st_mtime_ns, st.st_size)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    try:
        spec = parse_ignore(p.read_text(encoding="utf-8"), path=p)
    except OSError:
        return _EMPTY
    _CACHE[key] = spec
    return spec
