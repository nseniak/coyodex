"""Unified-diff row parsing for the code viewer's inline diff display.

What remains of the old mechanical diff viewer: the impact explorer (impact_lib/impact_git/
impact_ripple + the api/impact* endpoints) superseded its projection and git layers, and the
interactive picker was removed from the UI. `parse_unified_diff` turns `git diff` text into
DiffRow rows that `renderCodeDiff` (viewer.js) paints — used today by `impact_file_diff`
(serve.py). Stdlib-only, no git, no I/O.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

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
