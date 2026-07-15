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
from typing import cast

from coyodex import audit_model, grammar
from coyodex.model import (
    Component,
    Entity,
    EntityField,
    EntryPoint,
    Flow,
    FlowStep,
    GlossaryRow,
    ProjectModel,
    SubFlow,
    UseCase,
    all_elements,
    load_model,
    to_canonical_json,
)
from coyodex.viewer.gen_viewer import flow_actors, flow_narrative, gen_flow_mermaid
from coyodex.views import model_to_graph, model_to_markdown

FIXTURE = Path(__file__).parent / "fixtures" / "mcpolis-project-map.json"
RENDER = [sys.executable, "-m", "coyodex.viewer.render"]


def make_fixture_model() -> ProjectModel:
    return load_model(FIXTURE.read_text(encoding="utf-8"))


def make_small_model() -> ProjectModel:
    """A minimal model exercising one field of each kind, for the render-CLI smoke test."""
    m = ProjectModel(title="Tiny", goal="A tiny demo.")
    m.components = [Component(id="C1", name="Viewer", subsystem=None, purpose="shows orders",
                              entry_point="src/v.py:1", depends_on="", source=None,
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
        # The interactive viewer is served by `coyodex serve` now — the only rendered file is the .md
        # view. A non-.md target is a clean error (exit 2), not a silent no-op, and writes nothing.
        r = subprocess.run(RENDER + [str(src), str(Path(td) / "out.html")], capture_output=True, text=True)
        assert r.returncode == 2 and "coyodex serve" in r.stderr
        assert not (Path(td) / "out.html").exists()


def test_golden_graph_carries_every_defined_element():
    """model→graph must expose every defined element as a node (the HTML view is a pure function
    of this dict), with the map's header metadata intact."""
    m = make_fixture_model()
    g = model_to_graph(m)
    assert g["title"] and g["commit"] == m.commit and g["goal"]
    node_ids = set(g["nodes"])
    for eid in all_elements(m):
        # HP steps ride the `happy_path` list; roles ride the `roles` list (actors resolve to names,
        # they are not backbone nodes) — neither is a node in the graph dict.
        if not eid.startswith("HP") and not eid.startswith("R"):
            assert eid in node_ids, f"{eid} missing from the graph"
    assert len(g["happy_path"]) == len(m.happy_path)
    assert len(g["roles"]) == len(m.roles)
    assert len(g["glossary"]) == len(m.glossary)
    assert g["edges"], "the fixture's backbone must survive into the graph"


def test_golden_graph_carries_reference_collections_and_metadata():
    """The operational/reference collections the viewer's System & Tests tabs read (and the header
    metadata) must ride into the graph, one graph row per model row — nothing dropped at model→graph."""
    m = make_fixture_model()
    g = model_to_graph(m)
    assert g["built"] == m.built and g["format"] == m.format
    for key, coll in [("run_commands", m.run_commands), ("entry_points", m.entry_points),
                      ("non_entity_types", m.non_entity_types), ("deployment", m.deployment),
                      ("observability", m.observability), ("security", m.security),
                      ("config", m.config), ("tests", m.tests), ("extras", m.extras)]:
        assert len(g[key]) == len(coll), f"{key} lost rows at model→graph"
    assert g["tests_note"] == m.tests_note


def test_golden_graph_attaches_entry_points_and_resolves_test_targets():
    """Entry points that name a component surface on that component's node (the 'Triggered by' list),
    and each tests[] row resolves its target ids to `{id, name, node}` for the Tests tab."""
    m = make_fixture_model()
    g = model_to_graph(m)
    # every node carrying entry points is a component, and each entry point has the expected shape
    carriers = [nid for nid, n in g["nodes"].items() if n.get("entry_points")]
    assert carriers, "the fixture has entry points that name components"
    for nid in carriers:
        assert g["nodes"][nid]["kind"] == "component"
        eps = g["nodes"][nid]["entry_points"]
        assert isinstance(eps, list)
        for ep in eps:
            assert set(ep) == {"kind", "trigger", "source", "activation"}
            assert ep["activation"] in ("self", "external")
    # each flat entry point that names a component carries its 0-based position within that component's
    # list (the viewer uses it to select the exact entry point from a search hit / System link)
    counts: dict[str, int] = {}
    for e in g["entry_points"]:
        comp = str(e.get("component") or "")
        if comp:
            assert e["index"] == counts.get(comp, 0)
            counts[comp] = counts.get(comp, 0) + 1
    # each tests[] row carries its targets resolved to real nodes (or id-as-name when unresolved),
    # and cites suites as {file, why} bare anchors
    assert g["tests"], "the fixture has a test-completeness table"
    for row in g["tests"]:
        assert row["targets"], "a tests row names at least one target element"
        for tgt in row["targets"]:
            assert set(tgt) == {"id", "name", "node"}
            assert tgt["node"] is None or tgt["node"] in g["nodes"]
        for ev in row["tests"]:
            assert set(ev) == {"file", "why"}


def test_classify_activation_reads_kind_signatures():
    """Self-starting kinds (timer/loop/boot/signal/queue consumer) -> 'self'; caller-driven kinds
    (route/CLI/callback/webhook) -> 'external'; unknown -> 'external' (safe default)."""
    for kind in ("Background loop", "Cron job", "Boot task", "Signal", "Queue consumer",
                 "Startup hook", "Scheduled sweep", "SIGTERM handler"):
        assert grammar.classify_activation(kind) == "self", kind
    for kind in ("HTTP route", "CLI command", "OAuth callback", "Webhook", "Exported fn", ""):
        assert grammar.classify_activation(kind) == "external", kind


def test_entry_point_activation_authored_wins_else_derived():
    """The authored `activation` overrides the heuristic; a blank value falls back to classify_activation
    over `kind` — so old maps (no field) still classify without a rebuild."""
    m = ProjectModel(title="Acts", goal="demo")
    m.components = [Component(id="C1", name="Svc", subsystem=None, purpose="p",
                             entry_point="src/s.py:1", depends_on="", source=None, confidence="")]
    m.entry_points = [
        EntryPoint(kind="Background loop", trigger="every 60s", source="src/s.py:1", component="C1"),
        EntryPoint(kind="HTTP route", trigger="GET /x", source="src/s.py:2", component="C1"),
        # authored value overrides what the kind text would imply (both directions):
        EntryPoint(kind="Reconcile pass", trigger="on boot", source="src/s.py:3", component="C1",
                   activation="self"),
        EntryPoint(kind="Background sync", trigger="manual", source="src/s.py:4", component="C1",
                   activation="external"),
    ]
    g = model_to_graph(m)
    acts = [e["activation"] for e in g["entry_points"]]
    assert acts == ["self", "external", "self", "external"]
    # the per-component "Triggered by" list carries the same resolved value
    comp_eps = g["nodes"]["C1"]["entry_points"]
    assert isinstance(comp_eps, list)
    assert [e["activation"] for e in comp_eps] == acts


def test_tests_rows_resolve_targets_to_names_and_nodes():
    """Each tests[] row carries its `targets` resolved SERVER-SIDE to `{id, name, node}`: a defined
    element gets its name + a node id (the Tests tab makes it clickable to locate); an undefined id
    keeps its id as the name and `node=None` — no client-side id parsing, no guessed link."""
    from coyodex.model import EvidenceItem, TestRow, UseCase
    m = ProjectModel(title="Tiny")
    m.use_cases = [UseCase(id="UC1", name="Login"), UseCase(id="UC2", name="Browse")]
    m.tests = [TestRow(targets=["UC1", "UC9"], label="auth", tested="no",
                       tests=[EvidenceItem(file="tests/unit/", why="login suite")]),
               TestRow(targets=["UC2"], tested="yes")]
    g = model_to_graph(m)
    r0 = g["tests"][0]
    assert r0["label"] == "auth" and r0["tested"] == "no"
    assert r0["targets"][0] == {"id": "UC1", "name": "Login", "node": "UC1"}
    assert r0["targets"][1] == {"id": "UC9", "name": "UC9", "node": None}  # undefined → id as name, no node
    assert r0["tests"] == [{"file": "tests/unit/", "why": "login suite"}]  # bare anchor → clickable code link
    assert g["tests"][1]["targets"][0] == {"id": "UC2", "name": "Browse", "node": "UC2"}


def test_glossary_where_renders_as_link_and_reaches_graph():
    """The bare `source` anchor becomes a clickable basename link in the md view, and the glossary
    (with `source` preserved, "" for a null home) rides into the graph the Glossary tab reads."""
    m = ProjectModel(title="Tiny", goal="A tiny demo.")
    m.glossary = [GlossaryRow(term="Order", meaning="a customer order", source="src/order.py:12"),
                  GlossaryRow(term="Brand", meaning="the product itself", source=None)]
    md = model_to_markdown(m)
    assert "| **Order** | a customer order | [order.py](src/order.py:12) |" in md
    assert "| **Brand** | the product itself |  |" in md  # null home -> empty cell, no broken link
    g = model_to_graph(m)
    assert g["glossary"] == [{"term": "Order", "meaning": "a customer order", "source": "src/order.py:12"},
                             {"term": "Brand", "meaning": "the product itself", "source": ""}]


def test_step_where_renders_in_md_and_reaches_graph():
    """A flow step's own `where` (THE location) renders as an inline ` @ ` code link in the T6 md
    view — between the phrase and the note — and rides into the graph's flow steps for the viewer."""
    m = ProjectModel(title="Tiny", goal="A tiny demo.")
    m.use_cases = [UseCase(id="UC1", name="View")]
    m.components = [Component(id="C1", name="Viewer", purpose="shows")]
    m.entities = [Entity(id="E1", name="Order", source="src/e.py:1",
                         fields=[EntityField(name="id", type="str")])]
    m.flows = [Flow(uc="UC1", title="View",
                    steps=[FlowStep(n=1, src="C1", dst="E1", phrase="reads the order",
                                    where="src/v.py:5", note="cached")])]
    md = model_to_markdown(m)
    assert "1. C1 → E1 : reads the order @ [v.py](src/v.py:5) · cached" in md
    g = model_to_graph(m)
    steps = cast("list[dict[str, object]]", g["flows"][0]["steps"])
    assert steps[0]["where"] == "src/v.py:5"


def make_subflow_model() -> ProjectModel:
    """Two flows sharing one sub-flow: UC1 = actor step + reference; UC2 = reference only."""
    m = ProjectModel(title="Tiny", goal="A tiny demo.")
    m.use_cases = [UseCase(id="UC1", name="View"), UseCase(id="UC2", name="Audit")]
    m.components = [Component(id="C1", name="Viewer", purpose="shows"),
                    Component(id="C2", name="Store", purpose="keeps")]
    m.subflows = [SubFlow(id="SF1", name="Persist the thing",
                          steps=[FlowStep(n=1, src="C1", dst="C2", phrase="hands off",
                                          where="src/a.py:3"),
                                 FlowStep(n=2, src="C2", dst="C1", phrase="confirms",
                                          where="src/b.py:7")])]
    m.flows = [Flow(uc="UC1", title="View",
                    steps=[FlowStep(n=1, src="Andy", dst="C1", phrase="opens"),
                           FlowStep(n=2, src="C1", dst="C2", subflow="SF1"),
                           FlowStep(n=3, src="C1", dst="C2", phrase="renders the result",
                                    where="src/c.py:9")]),
               Flow(uc="UC2", title="Audit",
                    steps=[FlowStep(n=1, src="C1", dst="C2", subflow="SF1")])]
    return m


def test_subflow_renders_in_md_and_reaches_graph():
    m = make_subflow_model()
    md = model_to_markdown(m)
    assert "## T6b — Sub-flows" in md and "**SF1 — Persist the thing**" in md
    assert "2. C1 → C2 : ⟨runs SF1 — Persist the thing⟩" in md  # the reference step, named inline
    g = model_to_graph(m)
    sf = cast("list[dict[str, object]]", g["subflows"])[0]
    assert sf["id"] == "SF1"
    assert cast("list[dict[str, object]]", sf["steps"])[0]["where"] == "src/a.py:3"


def test_flow_narrative_expands_subflow_in_place():
    """The reference step is REPLACED inline by the sub-flow's steps, carrying sf/sfName/sfFirst —
    no header entries, so narrative indexes stay 1:1 with mermaid messages."""
    g = model_to_graph(make_subflow_model())
    narr = flow_narrative(g, cast("dict", g["flows"][0]))
    assert [(s["sf"], s["n"]) for s in narr] == [(None, 1), ("SF1", 1), ("SF1", 2), (None, 3)]
    assert narr[1]["sfFirst"] is True and narr[2]["sfFirst"] is False
    assert narr[1]["sfName"] == "Persist the thing" and narr[1]["where"] == "src/a.py:3"
    mm = gen_flow_mermaid(g, cast("dict", g["flows"][0]))
    msgs = [ln for ln in mm.splitlines() if "->>" in ln]
    assert len(msgs) == len(narr)                       # message[i] <-> narrative[i], notes excluded
    assert "rect rgb" in mm and "Note over" in mm and "Persist the thing" in mm
    assert mm.count("  end") == 1                       # one run -> one closed rect


def test_flow_actors_index_the_expanded_list():
    g = model_to_graph(make_subflow_model())
    actors = flow_actors(g, cast("dict", g["flows"][0]))
    assert len(actors) == 1 and actors[0]["name"] == "Andy"
    assert actors[0]["stepIdx"] == [0]                  # indexes the same 4-entry expanded list


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
