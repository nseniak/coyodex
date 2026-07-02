#!/usr/bin/env python3
"""Tests for the md→model converter and the generated views — including the GOLDEN case: the
committed real-world mcpolis map (tests/fixtures/mcpolis-project-map.md, the 2026-07-01 backup
with its historical letter-suffixed subsystem ids corrected to numeric ones so it validates)
must come through the JSON pipeline losslessly:

  - converter → model → canonical JSON → model is the identity;
  - model → markdown view → converter is the identity (the view loses nothing the model holds);
  - model → graph carries every defined element (the HTML view is a pure function of that dict);
  - the model audit + L2 worklist behave deterministically on the real map.

(The md-vs-json PIPELINE PARITY tests retired with the v1 parser in Phase 3 — parity was proven
at the Phase-2 boundary and the markdown pipeline no longer exists to compare against.)

Run either way (needs an editable install: `make deps`):
    python3 tests/test_convert_and_views.py
    pytest tests/test_convert_and_views.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex import audit_model, schema_v1
from coyodex.convert_md import convert_text
from coyodex.model import all_elements, load_model, to_canonical_json
from coyodex.validate_analysis import validate_map
from coyodex.views import model_to_graph, model_to_markdown

FIXTURE = Path(__file__).parent / "fixtures" / "mcpolis-project-map.md"
CONVERT = [sys.executable, "-m", "coyodex.convert_md"]
RENDER = [sys.executable, "-m", "coyodex.viewer.render"]


def make_fixture_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def make_small_map(extra_section: bool = False) -> str:
    """A minimal valid map exercising one of everything the converter must capture."""
    extra = ("## Custom notes\n\nSome authored prose the view must keep.\n\n---\n\n"
             if extra_section else "")
    return (
        "# Tiny — Codebase Analysis\n\n"
        "> **Commit:** `abc1234` · **Committed:** `2026-07-01` · **Built:** `2026-07-02 10:00`\n\n"
        "## T0 — Goal (the anchor)\n\nA tiny demo.\n\n---\n\n"
        "## Roles (actors)\n\n"
        "| Role | Kind | What they want | Use cases they drive |\n|---|---|---|---|\n"
        "| **Andy** | human | see orders | UC1 |\n\n"
        "## Use cases\n\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n|---|---|---|---|\n"
        "| **UC1** | View order | Andy | opens → sees |\n\n"
        "## Golden Path — the spine\n\n"
        "**GP1 — Andy views the order** *(UC1)*\n\n---\n\n"
        "## T1 — Components\n\n"
        "| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | Viewer | shows orders | [v.py](src/v.py#L1) |  |\n\n"
        "## T2 — External dependencies\n\n"
        "| ID | Name | Kind | Type | Used for | Where configured | Conf. |\n"
        "|---|---|---|---|---|---|---|\n"
        "| **D1** | Postgres | datastore | SQL database | orders | [cfg](cfg.py#L1) | verified |\n\n"
        + extra +
        "## T5 — Domain model (domain cards)\n\n"
        "**E1 — Order** *(orders)*\n"
        "MEANING: a customer order\n"
        "FIELDS: id:str PK\n"
        "SOURCE: [order.py](src/order.py#L1)\n\n---\n\n"
        "## T6 — Use-case flows\n\n"
        "**UC1 — View order**\n"
        "1. Andy → C1 : opens the list\n"
        "2. C1 → E1\n\n---\n\n"
        "## Relationships — backbone edge list\n\n"
        "| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | reads | E1 | show it | [v.py](src/v.py#L5) |\n"
        "| C1 | uses | D1 | query | [v.py](src/v.py#L7) |\n"
    )


# --- converter basics ------------------------------------------------------------

def test_convert_small_map_captures_everything():
    m = convert_text(make_small_map()).model
    assert m.title == "Tiny" and m.commit == "abc1234" and m.built == "2026-07-02 10:00"
    assert [r.name for r in m.roles] == ["Andy"]
    assert [u.id for u in m.use_cases] == ["UC1"] and m.use_cases[0].actor == "Andy"
    assert m.golden_path[0].uc == "UC1"
    assert m.components[0].entry_point == "[v.py](src/v.py#L1)"
    assert m.deps[0].kind == "datastore" and m.deps[0].confidence == "verified"
    assert m.entities[0].fields[0].markers == ["PK"]
    assert len(m.edges) == 2 and m.edges[0].verb == "reads"
    assert m.flows[0].steps[0].phrase == "opens the list"


def test_convert_preserves_unrecognized_section_in_extras():
    m = convert_text(make_small_map(extra_section=True)).model
    assert [e.heading for e in m.extras] == ["Custom notes"]
    assert "authored prose" in m.extras[0].body
    # …and the generated view carries it, so re-converting keeps it.
    view = model_to_markdown(m)
    assert "## Custom notes" in view
    m2 = convert_text(view).model
    assert [e.heading for e in m2.extras] == ["Custom notes"]


def test_convert_cli_refuses_invalid_v1_map():
    bad = make_small_map().replace("| **C1** |", "| **C1a** |")  # a malformed suffixed id
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "project-map.md"
        p.write_text(bad, encoding="utf-8")
        proc = subprocess.run(CONVERT + [str(p)], capture_output=True, text=True)
        assert proc.returncode == 1
        assert "does not validate" in proc.stderr


def test_convert_cli_writes_json_and_views():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "map.md"
        p.write_text(make_small_map(), encoding="utf-8")
        proc = subprocess.run(CONVERT + [str(p), "--out", td], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert (Path(td) / "project-map.json").exists()
        assert (Path(td) / "project-map.md").exists()
        assert (Path(td) / "project-map.html").exists()


def test_render_cli_json_to_md_and_html():
    m = convert_text(make_small_map()).model
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "project-map.json"
        src.write_text(to_canonical_json(m), encoding="utf-8")
        assert subprocess.run(RENDER + [str(src), str(Path(td) / "out.md")],
                              capture_output=True).returncode == 0
        assert (Path(td) / "out.md").read_text(encoding="utf-8") == model_to_markdown(m)
        assert subprocess.run(RENDER + [str(src), str(Path(td) / "out.html")],
                              capture_output=True).returncode == 0
        assert (Path(td) / "out.html").stat().st_size > 0


# --- golden equivalence on the real mcpolis map ----------------------------------

def test_golden_convert_has_no_warnings():
    assert convert_text(make_fixture_text()).warnings == []


def test_golden_json_round_trip_is_identity():
    m = convert_text(make_fixture_text()).model
    j = to_canonical_json(m)
    assert to_canonical_json(load_model(j)) == j


def test_golden_view_reconvert_is_identity():
    m = convert_text(make_fixture_text()).model
    view = model_to_markdown(m)
    assert to_canonical_json(convert_text(view).model) == to_canonical_json(m)


def test_golden_generated_view_validates_under_v1():
    m = convert_text(make_fixture_text()).model
    problems, _warnings = validate_map(schema_v1.strip_fences(model_to_markdown(m)))
    assert problems == []


def test_golden_graph_carries_every_defined_element():
    """model→graph must expose every defined element as a node (the HTML view is a pure function
    of this dict), with the map's header metadata intact."""
    m = convert_text(make_fixture_text()).model
    g = model_to_graph(m)
    assert g["title"] and g["commit"] == m.commit and g["goal"]
    node_ids = set(g["nodes"])
    for eid in all_elements(m):
        if not eid.startswith("GP"):  # GP steps ride the `gp` list, not the node dict
            assert eid in node_ids, f"{eid} missing from the graph"
    assert len(g["gp"]) == len(m.golden_path)
    assert len(g["roles"]) == len(m.roles)
    assert g["edges"], "the fixture's backbone must survive into the graph"


def test_golden_model_audit_is_deterministic_and_deduped():
    """The model audit on the real map: stable across runs, worklist deduped by claim, every edge
    claim self-describing enough to carry an anchor or a detail."""
    m = convert_text(make_fixture_text()).model
    f1 = [(f.check, f.severity, f.location) for f in audit_model.audit_model(m)]
    f2 = [(f.check, f.severity, f.location) for f in audit_model.audit_model(m)]
    assert f1 == f2
    wl = audit_model.l2_worklist_model(m)
    claims = [w.claim for w in wl]
    assert wl and len(claims) == len(set(claims)), "worklist must be deduped by claim"


def test_golden_v2_detail_describes_components_by_entry_points():
    """The F2 fix: an edge claim's detail lists the FROM component's member entry points, and a dep
    endpoint reads as an external system, never a code file."""
    m = convert_text(make_fixture_text()).model
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
