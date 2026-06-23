#!/usr/bin/env python3
"""Schema v1 grammar — the single source of the project-map token/definition rules.

Imported by the validator (``tools/validate_analysis.py``) and the parser
(``tools/viewer/build_graph.py``) so there is ONE grammar, never two that can drift.
Stdlib-only.
"""
from __future__ import annotations

import re

# IDs by prefix. Multi-letter prefixes (UC, GP) must precede the single-letter ones.
ID_TOKEN = re.compile(r"\b(?:UC\d+|GP\d+|C\d+|D\d+|E\d+|S\d+)\b")

# A definition is the FIRST cell of a table row, bolded: `| **C1** | ... |`
# — not an inline bold reference in prose.
DEF_BOLD = re.compile(r"^\|\s*\*\*(UC\d+|C\d+|D\d+|E\d+|S\d+)\*\*\s*\|")

# A bold id anywhere in a cell — a parser uses this to find a row's defining id.
DEF_ID_CELL = re.compile(r"\*\*(UC\d+|C\d+|D\d+|E\d+|S\d+)\*\*")

# A bold id at the START of a first cell but with extra text glued after it — i.e. NOT a clean
# `| **C1** |` definition. Id and name sharing the cell is the most common reason an id reads as
# "undefined"; the validator uses these to name that exact cause. Two glue forms:
#   GLUED_DEF       — name OUTSIDE the bold:  `| **UC1** Search… |`
#   GLUED_DEF_INNER — name INSIDE the bold:   `| **C8 Upstream** |`
GLUED_DEF = re.compile(r"^\|\s*\*\*(UC\d+|C\d+|D\d+|E\d+|S\d+)\*\*\s+[^|]")
GLUED_DEF_INNER = re.compile(r"^\|\s*\*\*(UC\d+|C\d+|D\d+|E\d+|S\d+)\s+[^*|]+\*\*")

# A Golden Path step heading: `**GP1 — ...`.
DEF_GP = re.compile(r"^\*\*(GP\d+)\s+—")

# Grouping: membership is ONE parent pointer carried on the child.
MAX_DEPTH = 3  # max subsystem levels (parent-pointer hops) in any membership chain


def strip_fences(text: str) -> str:
    """Blank out fenced code blocks (``` or ~~~), keeping the line COUNT so reported line numbers
    stay accurate. Both consumers (validator, parser) read tables/IDs from prose; a verbatim
    example inside a code fence (a Mermaid diagram, a shell snippet, a teaching example of a
    *malformed* table) is not live content and must not be parsed as a table or as ID
    definitions/references. Shared here so the two tools strip fences identically — one grammar."""
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out.append("")  # blank the fence marker line too
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def membership_col(headers_lower: list[str], child_id: str) -> int | None:
    """Index of a row's membership column, chosen by the row's OWN id kind (robust to column
    order): a subsystem row's 'Subsystem' header is its *name* column, so its parent pointer is
    'Parent'; a component (or other) row's membership IS the 'Subsystem' column."""
    sub = headers_lower.index("subsystem") if "subsystem" in headers_lower else None
    par = headers_lower.index("parent") if "parent" in headers_lower else None
    return par if child_id.startswith("S") else (sub if sub is not None else par)


def membership_ids(child_id: str, cells: list[str], headers_lower: list[str]) -> list[str]:
    """All id-tokens in a row's membership column ([] if none / no such column). ``len > 1`` is a
    malformed multi-parent cell; the first id is the parent. Shared by validator and parser so the
    membership rule lives in exactly one place."""
    col = membership_col(headers_lower, child_id)
    if col is None or col >= len(cells):
        return []
    return ID_TOKEN.findall(cells[col])
