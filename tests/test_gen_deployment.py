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


def test_gen_deployment_emits_processes_runs_and_declared_boxes():
    mm = G.gen_deployment_mermaid(model_to_graph(make_deploy_model()))
    # process boxes (bot/worker/shard = U_0/U_1/U_2)
    assert "class U_0 process" in mm and "class U_1 process" in mm and "class U_2 process" in mm
    # a runs edge to a subsystem, and BOTH the shared component's processes point at Plugins (S1)
    assert "U_0 --> S1" in mm and "U_1 --> S1" in mm      # bot AND worker run Plugins (the monolith mesh)
    assert "U_1 --> S2" in mm                             # worker runs Memberships
    # subsystem endpoint boxes are DECLARED (else they'd be bare inert nodes)
    assert "class S1 subsystem" in mm and "class S2 subsystem" in mm


def test_overview_infra_is_an_ambient_band_with_no_process_arrows():
    # AMBIENT INFRA: the brokers/stores are drawn as an Infrastructure band (so their use is implied by
    # adjacency) but the overview draws NO process→infra arrows — those live on the drill cards.
    mm = G.gen_deployment_mermaid(model_to_graph(make_deploy_model()))
    assert 'subgraph L_infra["Infrastructure"]' in mm
    assert "class D1 dep" in mm and "class D2 dep" in mm  # both infra boxes present
    assert "--> D1" not in mm and "--> D2" not in mm      # ...but nothing points an arrow at them


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


def test_unit_card_shows_the_infra_dropped_from_the_overview():
    # The process→infra arrows removed from the overview reappear on the drill card: worker (U_1) runs
    # C1 (emits Redis) and C2 (writes Mongo), so its card points at BOTH deps; bot (U_0) runs only C1.
    cards = G.deployment_cards(model_to_graph(make_deploy_model()))
    assert "U_1 --> D1" in cards["worker"] and "U_1 --> D2" in cards["worker"]
    assert "class D1 dep" in cards["worker"] and "class D2 dep" in cards["worker"]
    assert "U_0 --> D1" in cards["bot"] and "U_0 --> D2" not in cards["bot"]  # bot only touches Redis


# --- all-in-one (superset) fold -------------------------------------------------

def make_allinone_model() -> ProjectModel:
    """backend runs S1, frontend runs S2, and `standalone` packages BOTH — an all-in-one superset."""
    m = ProjectModel(title="Demo", goal="g")
    m.subsystems = [Group(id="S1", name="Backend"), Group(id="S2", name="Frontend")]
    m.components = [
        Component(id="C1", name="Api", subsystem="S1", source="a.py:1", runs_in=["backend", "standalone"]),
        Component(id="C2", name="Web", subsystem="S2", source="b.py:1", runs_in=["frontend", "standalone"]),
    ]
    m.deps = [Dep(id="D1", name="Redis", kind="messaging", type="broker")]
    m.edges = [Edge(src="C1", verb="emits", dst="D1", why="publish", where="y.py:2")]
    m.deployment = [DeploymentRow(unit="backend"), DeploymentRow(unit="frontend"),
                    DeploymentRow(unit="standalone")]                      # U_0 / U_1 / U_2
    return m


def test_superset_unit_is_folded_not_fanned():
    # standalone (U_2) runs everything backend+frontend run between them → an all-in-one packaging.
    # It is folded to a labelled annotation with NO arrows; only the two real processes fan out.
    mm = G.gen_deployment_mermaid(model_to_graph(make_allinone_model()))
    assert 'subgraph L_allinone["All-in-one"]' in mm
    assert "standalone — all-in-one: runs everything below" in mm
    assert "U_2 -->" not in mm                                   # the folded unit draws no arrows
    assert "U_0 --> S1" in mm and "U_1 --> S2" in mm             # backend + frontend still fan out
    # only the two meaningful runs arrows remain (no infra, no standalone fan)
    assert mm.count(" --> ") == 2


def test_folded_unit_still_has_a_drill_card_showing_everything():
    cards = G.deployment_cards(model_to_graph(make_allinone_model()))
    assert "U_2 --> S1" in cards["standalone"] and "U_2 --> S2" in cards["standalone"]
    assert "U_2 --> D1" in cards["standalone"]                   # and its infra, on the card


def test_all_equal_units_are_not_all_folded():
    # Degenerate case: every unit runs the same set. Folding all would leave nothing — so fold none.
    m = make_allinone_model()
    m.components = [
        Component(id="C1", name="Api", subsystem="S1", source="a.py:1", runs_in=["a", "b"]),
        Component(id="C2", name="Web", subsystem="S2", source="b.py:1", runs_in=["a", "b"]),
    ]
    m.deployment = [DeploymentRow(unit="a"), DeploymentRow(unit="b")]
    mm = G.gen_deployment_mermaid(model_to_graph(m))
    assert 'subgraph L_allinone' not in mm                       # neither unit folded
    assert "class U_0 process" in mm and "class U_1 process" in mm


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
