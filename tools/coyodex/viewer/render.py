#!/usr/bin/env python3
"""Render a map to a generated view in one step.

Schema v2 (`project-map.json`) renders to EITHER view — the output extension picks it:
    coyodex render .coyodex/project-map.json .coyodex/project-map.html   # interactive viewer
    coyodex render .coyodex/project-map.json .coyodex/project-map.md    # committed markdown view
Schema-v1 markdown input still renders to HTML (the legacy path, alive until Phase 3).

The persisted artifacts are the model (the single source) and its generated views. The stages stay
importable on their own (`coyodex.views`, `coyodex.viewer.gen_viewer`) for debugging.

Driven by `coyodex render <map> <out> [change-report.md]`.
"""
from __future__ import annotations

import sys
from pathlib import Path

from coyodex.viewer.gen_viewer import write_html


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print("usage: coyodex render <project-map.json|md> <out.html|out.md> [change-report.md]",
              file=sys.stderr)
        return 2
    src, out = Path(argv[0]), Path(argv[1])
    report = Path(argv[2]) if len(argv) > 2 else None  # optional change-impact diff overlay
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix == ".json":
        from coyodex.model import ModelError, load_model
        from coyodex.views import model_to_graph, model_to_markdown
        try:
            model = load_model(src.read_text(encoding="utf-8"))
        except ModelError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        if out.suffix == ".md":
            out.write_text(model_to_markdown(model), encoding="utf-8")
        else:
            write_html(model_to_graph(model), out, report)
    else:
        if out.suffix == ".md":
            print("ERROR: the markdown view is generated from a schema-v2 model "
                  "(convert the map first: `coyodex convert`)", file=sys.stderr)
            return 2
        from coyodex.viewer.build_graph import build
        write_html(build(src), out, report)
    print(f"Rendered {src} -> {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
