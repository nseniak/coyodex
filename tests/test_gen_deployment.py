#!/usr/bin/env python3
"""Tests for the Deployment view generator (gen_viewer.gen_deployment_mermaid + node injection).

Run either way (needs an editable install: `make deps`):
    python3 tests/test_gen_deployment.py
    pytest tests/test_gen_deployment.py
"""
from __future__ import annotations

from coyodex.model import Component, Dep, DeploymentRow, Edge, Group, ProjectModel
from coyodex.views import model_to_graph
from coyodex.viewer import gen_viewer as G


# --- builders -------------------------------------------------------------------

def make_deploy_model() -> ProjectModel:
    m = ProjectModel(title="Demo", goal="g")
    m.subsystems = [Group(id="S1", name="Plugins"), Group(id="S2", name="Memberships")]
    m.components = [
        Component(id="C1", name="PluginA", subsystem="S1", source="mee6/plugins/a.py:1",
                  runs_in=["bot", "worker"]),                       # shared: runs in TWO processes
        Component(id="C2", name="MembSvc", subsystem="S2", source="mee6/memberships/svc.py:1",
                  runs_in=["worker"]),
        Component(id="C3", name="Shard", subsystem=None, source="shard/main.go:1",
                  runs_in=["shard"]),                                # ungrouped
    ]
    m.deps = [Dep(id="D1", name="Redis", kind="messaging", type="broker"),
              Dep(id="D2", name="Mongo", kind="datastore", type="db")]
    m.edges = [Edge(src="C2", verb="writes", dst="D2", why="persist", where="x.py:1"),
               Edge(src="C1", verb="emits", dst="D1", why="publish", where="y.py:2")]
    m.deployment = [DeploymentRow(unit="bot"), DeploymentRow(unit="worker"),
                    DeploymentRow(unit="shard")]
    return m


# --- injection ------------------------------------------------------------------

def test_process_nodes_injected_with_distinct_index_ids():
    # Two unit names differing ONLY in punctuation must get distinct ids (index-based, not name slugs
    # — a slug would collide and mermaid silently merges same-id nodes). Both units host a component so
    # they qualify as processes (WS1 injects a process node only for units that host code).
    m = make_deploy_model()
    m.deployment = [DeploymentRow(unit="api worker"), DeploymentRow(unit="api-worker")]
    m.components = [Component(id="C1", name="A", subsystem="S1", source="a.py:1", runs_in=["api worker"]),
                   Component(id="C2", name="B", subsystem="S2", source="b.py:1", runs_in=["api-worker"])]
    g = model_to_graph(m)
    mg: dict = {"nodes": dict(g["nodes"])}
    G.add_deployment_nodes(mg, g)
    procs = {k: v for k, v in mg["nodes"].items() if str(v.get("kind")) == "process"}
    assert set(procs) == {"U_0", "U_1"}                              # distinct ids, no collision
    assert {p["unit"] for p in procs.values()} == {"api worker", "api-worker"}


def test_infra_unit_with_no_runs_in_is_not_a_process_box():
    # WS1: a unit nothing runs in (mongo — the app talks to it, no component/entry point hosts there)
    # must NOT get a process node; it is already the Mongo dep box, so a process box would be dead.
    m = make_deploy_model()
    m.deployment.append(DeploymentRow(unit="mongo"))         # matches the Mongo dep (D2)
    g = model_to_graph(m)
    mg: dict = {"nodes": dict(g["nodes"])}
    G.add_deployment_nodes(mg, g)
    procs = {v.get("unit") for v in mg["nodes"].values() if str(v.get("kind")) == "process"}
    assert procs == {"bot", "worker", "shard"}               # only the real processes; no 'mongo' box
    # ...and the overview draws it nowhere (it name-matches an infra dep) — no U_3 box, no Untraced lane
    mm = G.gen_deployment_mermaid(g)
    assert "U_3" not in mm
    assert 'subgraph L_untraced' not in mm


def test_genuinely_unlinked_unit_goes_to_the_untraced_lane():
    # WS1/S2: a unit hosting no code that matches NO dependency is a real gap — surfaced in its own
    # "Untraced units" lane rather than dropped silently.
    m = make_deploy_model()
    m.deployment.append(DeploymentRow(unit="mystery"))       # hosts nothing, matches no dep name
    mm = G.gen_deployment_mermaid(model_to_graph(m))
    assert 'subgraph L_untraced["Untraced units"]' in mm
    assert '["mystery"]' in mm


def test_has_deployment_gates_on_units():
    assert G.has_deployment(model_to_graph(make_deploy_model())) is True
    m = make_deploy_model()
    m.deployment = []
    assert G.has_deployment(model_to_graph(m)) is False


# --- overview -------------------------------------------------------------------

def test_process_box_label_is_the_unit_name_not_the_id():
    # regression: process ids (U_n) are not in the clean graph, so the box label must come from the
    # unit name, never fall back to the id.
    mm = G.gen_deployment_mermaid(model_to_graph(make_deploy_model()))
    assert 'U_0["bot"]' in mm and 'U_1["worker"]' in mm and 'U_2["shard"]' in mm


def test_layered_lanes_split_shared_runtime_from_standalone():
    # bot+worker share Plugins → "Shared runtime"; shard owns its component alone → "Standalone services".
    mm = G.gen_deployment_mermaid(model_to_graph(make_deploy_model()))
    assert 'subgraph L_core["Shared runtime"]' in mm
    assert 'subgraph L_sat["Standalone services"]' in mm
    assert 'subgraph L_subs["Subsystems"]' in mm
    assert 'subgraph L_infra["Infrastructure"]' in mm
    assert mm.count("subgraph ") == mm.count("\n  end")   # balanced


def test_gen_deployment_emits_processes_runs_infra_and_declared_boxes():
    mm = G.gen_deployment_mermaid(model_to_graph(make_deploy_model()))
    # process boxes (bot/worker/shard = U_0/U_1/U_2)
    assert "class U_0 process" in mm and "class U_1 process" in mm and "class U_2 process" in mm
    # a runs edge to a subsystem, and BOTH the shared component's processes point at Plugins (S1)
    assert "U_0 --> S1" in mm and "U_1 --> S1" in mm      # bot AND worker run Plugins (the monolith mesh)
    assert "U_1 --> S2" in mm                             # worker runs Memberships
    # subsystem endpoint boxes are DECLARED (else they'd be bare inert nodes)
    assert "class S1 subsystem" in mm and "class S2 subsystem" in mm
    # infra hop: a running component's C→D edge rolls up to its process
    assert "U_1 --> D2" in mm and "class D2 dep" in mm    # worker writes Mongo
    assert "U_0 --> D1" in mm                             # bot emits to Redis


def test_ungrouped_component_runs_edge_targets_the_component():
    # C3 has no subsystem, so shard's runs edge targets the component itself (still a real node → binds).
    mm = G.gen_deployment_mermaid(model_to_graph(make_deploy_model()))
    assert "U_2 --> C3" in mm and "class C3 component" in mm


# --- cards ----------------------------------------------------------------------

def test_deployment_cards_keyed_by_unit_name():
    cards = G.deployment_cards(model_to_graph(make_deploy_model()))
    assert set(cards) == {"bot", "worker", "shard"}
    # the worker card frames both subsystems it runs
    assert "U_1 --> S1" in cards["worker"] and "U_1 --> S2" in cards["worker"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
