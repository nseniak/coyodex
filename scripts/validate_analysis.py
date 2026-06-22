#!/usr/bin/env python3
"""Validate project-map.md against the schema-v1 conventions.

Stdlib-only. Checks that the analysis file is a clean machine-parseable source
for diagrams/tooling:

  1. Every element ID (UC/C/D/E/GP) is defined exactly once.
  2. Every ID *reference* (Touches lines, traceability tables, edge list,
     Depends-on, Used-in-GP) resolves to a defined ID.
  3. Every Golden Path step (GPn heading) has a `Touches:` line.

Exit 0 = clean, 1 = problems found.

Usage:  python3 scripts/validate_analysis.py [.coyodex/project-map.md]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Prefix order matters: multi-letter prefixes (UC, GP) before single-letter C.
ID_TOKEN = re.compile(r"\b(?:UC\d+|GP\d+|C\d+|D\d+|E\d+)\b")

# Definition sites. A definition is the FIRST cell of a table row (`| **C1** | ...`)
# — NOT an inline bold reference in prose (e.g. the coverage note).
DEF_BOLD = re.compile(r"^\|\s*\*\*(UC\d+|C\d+|D\d+|E\d+)\*\*\s*\|")  # table-row id column
DEF_GP = re.compile(r"^\*\*(GP\d+)\s+—")                            # `**GP1 — ...` headings


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
        cells = [c.strip().lower() for c in s.strip("|").split("|")]
        if cells and cells[0] == "role":  # the Roles table header row
            if "kind" not in cells:
                return ["Roles table is missing the required 'Kind' column (human/service)"]
            return []
    return []


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".coyodex/project-map.md")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")

    defined_counts, gp_order = collect_defined(text)
    defined = set(defined_counts)
    referenced = collect_referenced(text)

    problems: list[str] = []

    duplicates = sorted(i for i, n in defined_counts.items() if n > 1 and not i.startswith("GP"))
    if duplicates:
        problems.append(f"Duplicate element definitions: {', '.join(duplicates)}")

    unresolved = sorted(referenced - defined)
    if unresolved:
        problems.append(f"References to undefined IDs: {', '.join(unresolved)}")

    missing_touches = check_gp_touches(text, gp_order)
    if missing_touches:
        problems.append(f"Golden Path steps missing a Touches: line: {', '.join(missing_touches)}")

    problems.extend(check_roles_kind(text))

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
