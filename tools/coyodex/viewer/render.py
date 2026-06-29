#!/usr/bin/env python3
"""Render a project-map.md to a self-contained HTML viewer in one step (map -> HTML).

Parses the map into a graph (build_graph) and renders the standalone HTML (gen_viewer) in
process — no subprocess, no temp graph.json. The only persisted artifacts are the map (the
single source) and the HTML rendering. The two stages stay importable on their own (and
runnable via `python -m coyodex.viewer.build_graph` / `... gen_viewer`) for debugging.

Driven by `coyodex render <project-map.md> <out.html> [change-report.md]`.
"""
from __future__ import annotations

import sys
from pathlib import Path

from coyodex.viewer.build_graph import build
from coyodex.viewer.gen_viewer import write_html


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print("usage: coyodex render <project-map.md> <out.html> [change-report.md]", file=sys.stderr)
        return 2
    md, out = Path(argv[0]), Path(argv[1])
    report = Path(argv[2]) if len(argv) > 2 else None  # optional change-impact report for the diff overlay
    if not md.exists():
        print(f"ERROR: {md} not found", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    graph = build(md)
    write_html(graph, out, report)
    print(f"Rendered {md} -> {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
