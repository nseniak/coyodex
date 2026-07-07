#!/usr/bin/env python3
"""Tests for the generated views — including the GOLDEN case: the committed real-world mcpolis
map (tests/fixtures/mcpolis-project-map.json, generated once from the retired md→model converter
at the Phase-2 boundary — see git history for the original markdown) must come through the model
pipeline losslessly:

  - model → canonical JSON → model is the identity;
  - model → graph carries every defined element (the HTML view is a pure function of that dict);
  - the model audit + L2 worklist behave deterministically on the real map.

(The md-vs-json PIPELINE PARITY tests, and the converter's own unit tests, retired with the v1
parser — the md→model converter is gone; only the JSON model pipeline exists now.)

Run either way (needs an editable install: `make deps`):
    python3 tests/test_convert_and_views.py
    pytest tests/test_convert_and_views.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex import audit_model
from coyodex.model import (
    Component,
    Entity,
    EntityField,
    ProjectModel,
    all_elements,
    load_model,
    to_canonical_json,
)
from coyodex.views import model_to_graph, model_to_markdown

FIXTURE = Path(__file__).parent / "fixtures" / "mcpolis-project-map.json"
RENDER = [sys.executable, "-m", "coyodex.viewer.render"]


def make_fixture_model() -> ProjectModel:
    return load_model(FIXTURE.read_text(encoding="utf-8"))


def make_small_model() -> ProjectModel:
    """A minimal model exercising one field of each kind, for the render-CLI smoke test."""
    m = ProjectModel(title="Tiny", goal="A tiny demo.")
    m.components = [Component(id="C1", name="Viewer", subsystem=None, purpose="shows orders",
                              entry_point="src/v.py:1", depends_on="", anchor=None,
                              confidence="")]
    m.entities = [Entity(id="E1", name="Order", store="orders", meaning="a customer order",
                         source="src/order.py:1",
                         fields=[EntityField(name="id", type="str", markers=["PK"])])]
    return m


# --- golden equivalence on the real mcpolis map ----------------------------------

def test_golden_json_round_trip_is_identity():
    m = make_fixture_model()
    j = to_canonical_json(m)
    assert to_canonical_json(load_model(j)) == j


def test_render_cli_json_to_md_and_html():
    m = make_small_model()
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "project-map.json"
        src.write_text(to_canonical_json(m), encoding="utf-8")
        assert subprocess.run(RENDER + [str(src), str(Path(td) / "out.md")],
                              capture_output=True).returncode == 0
        assert (Path(td) / "out.md").read_text(encoding="utf-8") == model_to_markdown(m)
        assert subprocess.run(RENDER + [str(src), str(Path(td) / "out.html")],
                              capture_output=True).returncode == 0
        assert (Path(td) / "out.html").stat().st_size > 0


def test_golden_graph_carries_every_defined_element():
    """model→graph must expose every defined element as a node (the HTML view is a pure function
    of this dict), with the map's header metadata intact."""
    m = make_fixture_model()
    g = model_to_graph(m)
    assert g["title"] and g["commit"] == m.commit and g["goal"]
    node_ids = set(g["nodes"])
    for eid in all_elements(m):
        if not eid.startswith("GP"):  # GP steps ride the `gp` list, not the node dict
            assert eid in node_ids, f"{eid} missing from the graph"
    assert len(g["gp"]) == len(m.golden_path)
    assert len(g["roles"]) == len(m.roles)
    assert g["edges"], "the fixture's backbone must survive into the graph"


def test_graph_line_parses_colon_range_and_legacy_hash_anchors():
    """`model_to_graph`'s node.line (build_graph._line_of) must resolve the START line of every
    anchor form: canonical single-line, canonical range, and the retired `#Lnnn`/`#Lnnn-Lmmm`
    (an un-migrated map's anchors must still open on click, just not be re-emitted)."""
    m = ProjectModel(title="T", goal="G")
    m.entities = [
        Entity(id="E1", name="A", source="src/a.py:12",
              fields=[EntityField(name="id", type="str")]),
        Entity(id="E2", name="B", source="src/b.py:12-18",
              fields=[EntityField(name="id", type="str")]),
        Entity(id="E3", name="C", source="src/c.py#L12-L18",
              fields=[EntityField(name="id", type="str")]),
    ]
    g = model_to_graph(m)
    assert g["nodes"]["E1"]["line"] == 12 and g["nodes"]["E1"]["file"] == "src/a.py:12"
    assert g["nodes"]["E2"]["line"] == 12 and g["nodes"]["E2"]["file"] == "src/b.py:12-18"
    assert g["nodes"]["E3"]["line"] == 12 and g["nodes"]["E3"]["file"] == "src/c.py#L12-L18"


def test_golden_model_audit_is_deterministic_and_deduped():
    """The model audit on the real map: stable across runs, worklist deduped by claim, every edge
    claim self-describing enough to carry an anchor or a detail."""
    m = make_fixture_model()
    f1 = [(f.check, f.severity, f.location) for f in audit_model.audit_model(m)]
    f2 = [(f.check, f.severity, f.location) for f in audit_model.audit_model(m)]
    assert f1 == f2
    wl = audit_model.l2_worklist_model(m)
    claims = [w.claim for w in wl]
    assert wl and len(claims) == len(set(claims)), "worklist must be deduped by claim"


def test_golden_v2_detail_describes_components_by_entry_points():
    """The F2 fix: an edge claim's detail lists the FROM component's member entry points, and a dep
    endpoint reads as an external system, never a code file."""
    m = make_fixture_model()
    wl = audit_model.l2_worklist_model(m)
    assert any("entry points:" in (w.detail or "") for w in wl)
    dep_details = [w.detail for w in wl
                   if w.detail and "To: D" in w.detail]
    assert dep_details and all("external system" in d for d in dep_details if "To: D" in d)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures += 1
                print(f"FAIL {name}: {e}")
    raise SystemExit(1 if failures else 0)
