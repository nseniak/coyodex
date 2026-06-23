#!/usr/bin/env python3
"""Validate project-map.md against the schema-v1 conventions.

Stdlib-only. Checks that the analysis file is a clean machine-parseable source
for diagrams/tooling:

  1. Every element ID (UC/C/D/E/S/GP) is defined exactly once.
  2. Every ID *reference* (Touches lines, traceability tables, edge list,
     Depends-on, Used-in-GP, Subsystem/Parent membership) resolves to a defined ID.
  3. Every Golden Path step (GPn heading) has a `Touches:` line.
  4. Grouping, when present (no-op when absent): every Subsystem/Parent value
     resolves to a defined `S`; at most one parent per element; no nesting
     cycles; nesting depth <= MAX_DEPTH.
  5. Table shape: every row of a markdown table (header / separator / data)
     carries the same column count — catches the malformed-separator / dropped-cell
     class that silently breaks parsing and diagram rendering.

When an id reads as undefined because its definition row glued extra text into the
ID cell (`| **UC1** Search… |` instead of `| **UC1** | Search… |`), the report names
that specific cause instead of the generic "undefined ID".

Exit 0 = clean, 1 = problems found.

Usage:  python3 tools/validate_analysis.py [.coyodex/project-map.md]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Grammar (regexes, membership rule) lives in schema_v1, shared with the parser — one grammar.
from schema_v1 import (
    DEF_BOLD,
    DEF_GP,
    GLUED_DEF,
    GLUED_DEF_INNER,
    ID_TOKEN,
    MAX_DEPTH,
    membership_ids,
    strip_fences,
)


def is_separator_row(row: str) -> bool:
    """A markdown table separator like ``|---|:--:|`` — dashes/colons/pipes/space only."""
    return "-" in row and bool(re.fullmatch(r"[\s|:\-]+", row.strip()))


def split_cells(row: str) -> list[str]:
    r"""Stripped cells of a table row. Escaped pipes (``\|`` — the schema's sanctioned way to put a
    literal pipe inside a cell) are neutralised first so they don't read as column separators."""
    return [c.strip() for c in row.replace(r"\|", "").strip().strip("|").split("|")]


def n_columns(row: str) -> int:
    """Cell count of a table row."""
    return len(split_cells(row))


def collect_defined(text: str) -> tuple[dict[str, int], list[str]]:
    """Return {id: count} for defined ids, plus an ordered list of GP headings."""
    counts: dict[str, int] = {}
    gp_order: list[str] = []
    for line in text.splitlines():
        m = DEF_BOLD.match(line)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
        m = DEF_GP.match(line)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
            gp_order.append(m.group(1))
    return counts, gp_order


def collect_referenced(text: str) -> set[str]:
    return set(ID_TOKEN.findall(text))


def check_gp_touches(text: str, gp_order: list[str]) -> list[str]:
    """Each GPn heading must be followed by a `Touches:` line before the next GP."""
    lines = text.splitlines()
    missing: list[str] = []
    # index of each GP heading
    heading_idx = {}
    for i, line in enumerate(lines):
        m = DEF_GP.match(line)
        if m:
            heading_idx[m.group(1)] = i
    for gp in gp_order:
        start = heading_idx[gp]
        found = False
        for line in lines[start + 1 : start + 8]:
            if DEF_GP.match(line):
                break
            if line.strip().startswith("`Touches:`") or line.strip().startswith("Touches:"):
                found = True
                break
        if not found:
            missing.append(gp)
    return missing


def check_roles_kind(text: str) -> list[str]:
    """If a Roles table exists (header's first cell is 'Role'), it must carry a 'Kind' column.
    No-op when there is no Roles table, so the check is additive."""
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.lower() for c in split_cells(s)]
        if cells and cells[0] == "role":  # the Roles table header row
            if "kind" not in cells:
                return ["Roles table is missing the required 'Kind' column (human/service)"]
            return []
    return []


def collect_parents(text: str) -> tuple[dict[str, str], list[str]]:
    """child_id -> parent_id from the membership column (Subsystem/Parent), via the shared
    schema_v1 rule. Returns the mapping plus problems for multi-parent cells. No-op (returns
    ``({}, [])``) when no such column exists, so ungrouped maps are unaffected.
    """
    parents: dict[str, str] = {}
    problems: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        block: list[str] = []
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            block.append(lines[i])
            i += 1
        if len(block) < 2:
            continue
        headers = [c.lower() for c in split_cells(block[0])]
        if "subsystem" not in headers and "parent" not in headers:
            continue
        for row in block[1:]:
            if is_separator_row(row):
                continue  # separator row
            cm = DEF_BOLD.match(row)
            if not cm:
                continue
            child = cm.group(1)
            cells = split_cells(row)
            ids = membership_ids(child, cells, headers)
            if len(ids) > 1:
                problems.append(f"{child} has multiple parents: {', '.join(ids)}")
            elif ids:
                parents[child] = ids[0]
    return parents, problems


def check_hierarchy(parents: dict[str, str], defined: set[str]) -> list[str]:
    """Parent must be a defined `S`; no nesting cycles; depth <= MAX_DEPTH."""
    problems: list[str] = []
    for child, par in parents.items():
        if not par.startswith("S"):
            problems.append(f"{child} parent {par} is not a subsystem (S…)")
        elif par not in defined:
            problems.append(f"{child} parent {par} is undefined")
    # Walk only well-formed (S-valued) pointers, so a wrong-type parent reported above
    # does not also surface as a spurious "cycle" line.
    valid = {c: p for c, p in parents.items() if p.startswith("S")}
    for start in valid:
        chain, cur, depth = [start], start, 0
        while cur in valid:
            cur = valid[cur]
            depth += 1
            if cur in chain:
                problems.append(f"Subsystem nesting cycle: {' -> '.join(chain)} -> {cur}")
                break
            chain.append(cur)
            if depth > MAX_DEPTH:
                problems.append(
                    f"Subsystem nesting exceeds depth {MAX_DEPTH}: {' -> '.join(chain)}"
                )
                break
    return problems


def find_glued_ids(text: str) -> set[str]:
    """IDs whose definition row glued the name into the ID cell — either outside the bold
    (`| **UC1** Search… |`) or inside it (`| **C8 Upstream** |`). Such a row is not a clean
    definition, so the id reads as undefined elsewhere — this lets the report name the real
    cause instead of the generic 'undefined ID'."""
    out: set[str] = set()
    for line in text.splitlines():
        for pat in (GLUED_DEF, GLUED_DEF_INNER):
            m = pat.match(line)
            if m:
                out.add(m.group(1))
    return out


def check_table_shape(text: str) -> list[str]:
    """Every row of a markdown table must have the header's column count. A table = a run of
    `|`-lines whose 2nd line is a separator; non-table pipe content is skipped (no false
    positives). Catches malformed separators and dropped/extra cells that break parsing.
    Note: a block with NO separator row is treated as non-table and skipped — so a *deleted*
    separator is not caught here (markdown wouldn't render it as a table either); the check
    catches a dropped/added cell in an otherwise-well-formed table. Run on fence-free text."""
    problems: list[str] = []
    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        start = i
        block: list[str] = []
        while i < n and lines[i].lstrip().startswith("|"):
            block.append(lines[i])
            i += 1
        if len(block) < 2 or not is_separator_row(block[1]):
            continue  # not a real table (no separator on the 2nd line)
        expected = n_columns(block[0])
        for offset, row in enumerate(block[1:], start=1):
            got = n_columns(row)
            if got != expected:
                what = "separator" if offset == 1 else "row"
                problems.append(
                    f"Table at line {start + 1}: {what} (line {start + offset + 1}) has "
                    f"{got} columns, header has {expected}"
                )
    return problems


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".coyodex/project-map.md")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    # Parse from fence-free text: verbatim examples inside ``` code fences (Mermaid, shell, a
    # teaching example of a malformed table) are not live content — don't read them as tables,
    # definitions, or references.
    text = strip_fences(path.read_text(encoding="utf-8"))

    defined_counts, gp_order = collect_defined(text)
    defined = set(defined_counts)
    referenced = collect_referenced(text)
    parents, parent_problems = collect_parents(text)
    # Grouping is "present" only if an S is defined or a membership column exists. When absent,
    # ignore stray S-tokens (e.g. prose "S3" / AWS S3) so ungrouped maps stay byte-for-byte additive.
    grouping_present = any(i.startswith("S") for i in defined) or bool(parents)

    problems: list[str] = []

    duplicates = sorted(i for i, n in defined_counts.items() if n > 1 and not i.startswith("GP"))
    if duplicates:
        problems.append(f"Duplicate element definitions: {', '.join(duplicates)}")

    ref_to_check = referenced if grouping_present else {r for r in referenced if not r.startswith("S")}
    unresolved = sorted(ref_to_check - defined)
    if unresolved:
        glued = find_glued_ids(text)
        glued_unresolved = [u for u in unresolved if u in glued]
        truly_undefined = [u for u in unresolved if u not in glued]
        if glued_unresolved:
            problems.append(
                "Definition rows with text glued into the ID cell — put the ID alone in the "
                f"first cell (e.g. `| **UC1** | name… |`): {', '.join(glued_unresolved)}"
            )
        if truly_undefined:
            problems.append(f"References to undefined IDs: {', '.join(truly_undefined)}")

    missing_touches = check_gp_touches(text, gp_order)
    if missing_touches:
        problems.append(f"Golden Path steps missing a Touches: line: {', '.join(missing_touches)}")

    problems.extend(check_roles_kind(text))
    problems.extend(check_table_shape(text))

    # Grouping checks — additive, no-op when there is no Subsystem/Parent column.
    problems.extend(parent_problems)
    problems.extend(check_hierarchy(parents, defined))
    # Loud guard against silent grouping failures: a Subsystems table with NO component actually
    # assigned is almost always a missing/unreadable membership column (which renders disconnected
    # subsystem boxes), not an intentional choice. Fail rather than pass green.
    if (any(i.startswith("S") for i in defined) and any(i.startswith("C") for i in defined)
            and not any(c.startswith("C") for c in parents)):
        problems.append(
            "Subsystems (S) defined but no component is assigned to one — the T1 'Subsystem' "
            "membership column is missing or unreadable"
        )

    # Summary of the element inventory, by prefix.
    by_prefix: dict[str, list[str]] = {}
    for i in defined:
        m = re.match(r"[A-Z]+", i)
        pre = m.group(0) if m else i
        by_prefix.setdefault(pre, []).append(i)
    inventory = ", ".join(
        f"{pre}:{len(v)}" for pre, v in sorted(by_prefix.items())
    )
    print(f"Inventory — {inventory}")

    if problems:
        print("\nVALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Schema v1: OK — all IDs defined once, all references resolve, every GP step has Touches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
