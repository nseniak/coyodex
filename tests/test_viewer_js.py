#!/usr/bin/env python3
"""Syntax gate for the hand-maintained viewer frontend bundle.

viewer.js is a large, hand-edited vanilla-JS file and the repo has no JS test harness, so a stray
syntax error (an unbalanced brace, a dangling edit) would ship silently and break the whole viewer.
`node --check` parses the file without executing it — a cheap, deterministic regression guard. Skips
when node isn't installed (e.g. a Python-only CI image), so it never turns into a spurious failure.

Conventions: top-level test functions, no classes/fixtures.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

VIEWER_DIR = Path(__file__).resolve().parent.parent / "tools" / "coyodex" / "viewer"


def _node_check(js_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed — skipping viewer JS syntax gate")
    assert js_path.exists(), f"expected {js_path} to exist"
    result = subprocess.run(
        [node, "--check", str(js_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, f"{js_path.name} failed `node --check`:\n{result.stderr}"


def test_viewer_js_parses() -> None:
    _node_check(VIEWER_DIR / "viewer.js")


def test_flow_step_links_the_pair_without_rendering_rides_rows() -> None:
    """A step's A → B line is the one route to every backbone relation for that pair."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    start = js.index("function showFlowStep(uc, i)")
    end = js.index("\n// One actor's card", start)
    flow_step = js[start:end]

    assert 'class="flowpairref"' in flow_step
    assert "showPairEdges(pairEdges)" in flow_step
    assert "Rides arrow" not in flow_step
    assert "ridesref" not in flow_step
    assert 'class="flowref"' not in flow_step


def test_the_ui_does_not_name_internal_model_fields():
    """The viewer speaks the reader's language, not the model's.

    A panel that says "no `runs_in`" names a JSON field the reader never sees and cannot act on from
    the UI. Naming the field is right in `validate` — that output is FOR editing the map, and the
    codebase already draws this line ("Completeness is validate's job, where it comes with the
    specific ids to fix"). It is wrong on screen.

    Checks the rendered STRINGS only: reading `ep.runs_in` in code is how the data is used, and
    backtick-to-<code> markdown of AUTHORED map text is the map's own words, not ours."""
    js = (Path(__file__).resolve().parents[1] / "tools/coyodex/viewer/viewer.js").read_text()
    fields = ("runs_in", "no_call_site", "non_entity_types", "tests_note", "where_configured",
              "cadence_source", "tech_source", "subflow", "why_refs")
    offenders = []
    for i, line in enumerate(js.splitlines(), 1):
        code = line.split("//", 1)[0] if not line.lstrip().startswith("//") else ""
        if "<code>" not in code:
            continue
        for f in fields:
            if f"<code>{f}</code>" in code:
                offenders.append(f"{i}: {line.strip()[:90]}")
    assert offenders == [], "internal field name rendered in the UI:\n" + "\n".join(offenders)


def test_source_links_are_bound_by_delegation_not_per_render():
    """One listener per container, so a new panel writer cannot ship dead source buttons.

    Source buttons used to be wired by calling `wireSrcLinks(root)` after each render, which works
    only if every panel writer remembers. `showNode` — the pane shown for any selected element — did
    not, so a deployment unit's Environments row rendered its manifest anchors as buttons that did
    nothing when clicked. Delegation makes forgetting impossible rather than merely catchable."""
    js = (VIEWER_DIR / "viewer.js").read_text()
    code = [ln for ln in js.splitlines() if not ln.lstrip().startswith("//")]
    stale = [ln.strip() for ln in code if "wireSrcLinks" in ln]
    assert stale == [], ("per-render source-link wiring is back — it double-binds against the "
                         "delegated listener:\n" + "\n".join(stale))
    assert "closest('.srclink')" in js, "the delegated source-link listener is missing"
    # it must be attached to the STABLE panel host, not the `panel` binding, which is temporarily
    # re-pointed at individual cards while a multi-selection renders.
    assert "[PANEL_HOST, diagram].forEach" in js
