#!/usr/bin/env python3
"""Tests for `serve.ensure_fresh` — the map-staleness check: a map edited while the server runs
(a Direct map change, an Accept, a re-balance) must be picked up on the next request instead of
being masked by the per-process view-bundle cache. (Found dogfooding the balance feature: the
viewer kept serving the pre-rebalance mcpolis map until a manual restart.)

Run either way (needs an editable install: `make deps`):
    python3 tests/test_serve_fresh.py
    pytest tests/test_serve_fresh.py
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from coyodex.model import Component, ProjectModel, to_canonical_json
from coyodex.viewer.serve import ensure_fresh, load_project, project_view


# --- builders -------------------------------------------------------------------

def write_map(root: Path, title: str, component_name: str, mtime_ns: int) -> None:
    """Write a minimal map (no git pin needed — the view path never reads git) with a forced
    mtime, so edits are distinguishable regardless of filesystem timestamp granularity."""
    (root / ".coyodex").mkdir(parents=True, exist_ok=True)
    model = ProjectModel(title=title, components=[
        Component(id="C1", name=component_name, purpose="does things")])
    p = root / ".coyodex" / "project-map.json"
    p.write_text(to_canonical_json(model), encoding="utf-8")
    os.utime(p, ns=(mtime_ns, mtime_ns))


def bundle_text(proj) -> str:  # noqa: ANN001 — ViewBundle shape is the viewer's concern, not ours
    return json.dumps(project_view(proj), default=str)


# --- tests ------------------------------------------------------------------------

def test_edited_map_is_served_after_ensure_fresh() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_map(root, title="Old title", component_name="OldBox", mtime_ns=1_000_000_000)
        proj = load_project(str(root))
        assert proj is not None
        assert "OldBox" in bundle_text(proj)           # bundle now cached
        write_map(root, title="New title", component_name="NewBox", mtime_ns=2_000_000_000)
        ensure_fresh(proj)
        assert proj.view is None and proj.tree is None and proj.symbols is None
        assert proj.title == "New title"
        assert "NewBox" in bundle_text(proj) and "OldBox" not in bundle_text(proj)


def test_unchanged_map_keeps_the_cached_bundle() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_map(root, title="T", component_name="Box", mtime_ns=1_000_000_000)
        proj = load_project(str(root))
        assert proj is not None
        first = project_view(proj)
        ensure_fresh(proj)
        assert proj.view is first                      # same object — no rebuild


def test_broken_edit_keeps_serving_the_old_bundle_and_retries() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_map(root, title="T", component_name="Box", mtime_ns=1_000_000_000)
        proj = load_project(str(root))
        assert proj is not None
        first = project_view(proj)
        p = root / ".coyodex" / "project-map.json"
        p.write_text("{ not json", encoding="utf-8")   # caught mid-write / newly invalid
        os.utime(p, ns=(2_000_000_000, 2_000_000_000))
        ensure_fresh(proj)
        assert proj.view is first and proj.title == "T"   # old bundle survives
        write_map(root, title="Fixed", component_name="FixedBox", mtime_ns=3_000_000_000)
        ensure_fresh(proj)                             # mtime stayed stale -> retried and reloaded
        assert proj.title == "Fixed" and "FixedBox" in bundle_text(proj)


def test_missing_file_keeps_the_cached_bundle() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_map(root, title="T", component_name="Box", mtime_ns=1_000_000_000)
        proj = load_project(str(root))
        assert proj is not None
        first = project_view(proj)
        (root / ".coyodex" / "project-map.json").unlink()
        ensure_fresh(proj)
        assert proj.view is first                      # unstat-able -> serve what we have


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"ok — {len(tests)} tests")
