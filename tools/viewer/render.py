#!/usr/bin/env python3
"""Render a project-map.md to a self-contained HTML viewer in one step (map -> HTML).

Wraps build_graph.py (map -> graph.json) + gen_viewer.py (graph.json -> HTML); the graph.json
parser/renderer interface stays in a temp file, so the only persisted artifacts are the map (the
single source) and the HTML rendering.

Usage:  python3 tools/viewer/render.py <project-map.md> <out.html> [change-report.md]
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: render.py <project-map.md> <out.html> [change-report.md]", file=sys.stderr)
        return 2
    md, out = Path(sys.argv[1]), Path(sys.argv[2])
    report = sys.argv[3:4]  # optional change-impact report for the diff overlay
    if not md.exists():
        print(f"ERROR: {md} not found", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        graph = Path(d) / "graph.json"
        subprocess.run([sys.executable, str(HERE / "build_graph.py"), str(md), str(graph)], check=True)
        subprocess.run(
            [sys.executable, str(HERE / "gen_viewer.py"), str(graph), str(out), *report], check=True
        )
    print(f"Rendered {md} -> {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
