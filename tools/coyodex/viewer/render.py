#!/usr/bin/env python3
"""Render a map's committed markdown view — and register it for the interactive server.

    coyodex render .coyodex/project-map.json .coyodex/project-map.md   # committed markdown view

The interactive C4 viewer is no longer a file: it is served live by `coyodex serve`, which reads the
model and builds every diagram on demand (the generic frontend fetches its data from the server). So a
`.html` output is accepted for backward compatibility but writes nothing — it only registers the
project with the server and prints how to open it. Markdown INPUT is not supported: only a model
(project-map.json) can be rendered.

The persisted artifacts are the model (the single source) and its committed markdown view. The stages
stay importable on their own (`coyodex.views`, `coyodex.viewer.gen_viewer`) for debugging.

Driven by `coyodex render <map> <out.md> [change-report.md]`.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print("usage: coyodex render <project-map.json> <out.md>  "
              "(the interactive viewer is served by `coyodex serve`)", file=sys.stderr)
        return 2
    src, out = Path(argv[0]), Path(argv[1])
    if not src.exists():
        print(f"ERROR: {src} not found", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix != ".json":
        print("ERROR: views are generated from a model (project-map.json) only — "
              "markdown maps are not supported.", file=sys.stderr)
        return 2
    from coyodex.model import ModelError, load_model
    from coyodex.views import model_to_markdown
    try:
        model = load_model(src.read_text(encoding="utf-8"))
    except ModelError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    # Rendering into a project's .coyodex/ registers it with `coyodex serve` (best-effort; see recents).
    from coyodex.viewer.recents import register_project
    if out.suffix == ".md":
        out.write_text(model_to_markdown(model), encoding="utf-8")
        register_project(out.parent)
        print(f"Rendered {src} -> {out.resolve()}")
    else:
        # The viewer is now served, not baked. Accept the old `.html` target so existing callers keep
        # working, but write nothing — just register the project so `coyodex serve` picks it up.
        register_project(out.parent)
        print(f"The interactive viewer is served by `coyodex serve` — no HTML file is written.\n"
              f"Registered {out.parent} · open it from the coyodex serve landing page.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
