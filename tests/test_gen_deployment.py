#!/usr/bin/env python3
"""Tests for the Deployment view generator (gen_viewer.gen_deployment_mermaid + node injection).

Run either way (needs an editable install: `make deps`):
    python3 tests/test_gen_deployment.py
    pytest tests/test_gen_deployment.py
"""
from __future__ import annotations

from coyodex.model import (Component, Dep, DeploymentRow, Edge, Group, MessagingRow, ProjectModel,
                           VariantTag)
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


# --- derived dep roles (WS2) — role = union of incoming C→D edge verbs, no stored field -----------

def test_dep_node_roles_derived_from_incoming_cd_verbs():
    m = make_deploy_model()
    # Redis (D1) is used as a bus (emits) AND a store (writes) → dual role, from its two real verbs.
    m.edges.append(Edge(src="C2", verb="writes", dst="D1", why="rate-limit", where="z.py:3"))
    nodes = model_to_graph(m)["nodes"]
    assert nodes["D1"]["roles"] == ["datastore", "messaging"]     # sorted union of {messaging, datastore}
    assert nodes["D2"]["roles"] == ["datastore"]                  # writes → store only


def test_infra_band_dual_role_goes_to_bus_and_roleless_falls_back():
    # A dual-role infra dep (Redis: emits + writes → bus + store) bands under Message bus (messaging
    # wins). A roleless-verb infra dep still bands by its structural dep_kind (fallback).
    m = make_deploy_model()
    m.edges.append(Edge(src="C2", verb="writes", dst="D1", why="rl", where="z.py:1"))  # Redis now bus+store
    m.deps.append(Dep(id="D3", name="Postgres", kind="datastore", type="db"))
    m.edges.append(Edge(src="C1", verb="uses", dst="D3", why="q", where="a.py:9"))       # roleless verb
    # C1 runs in bot AND worker, so both deps are touched by 2 processes — the overview only draws
    # infra that couples processes, and banding is what this test is about.
    mm = G.gen_deployment_mermaid(model_to_graph(m))
    assert "class D1 infraBus" in mm                       # dual role → bus (primary)
    assert "class D3 infraStore" in mm                     # roleless verb → dep_kind fallback (datastore)


def test_dep_with_no_cd_edge_has_no_roles():
    m = make_deploy_model()
    m.deps.append(Dep(id="D3", name="Grafana", kind="service", type="observability",
                      deployment_linked=True))                    # infra, no code call site → no C→D edge
    assert model_to_graph(m)["nodes"]["D3"]["roles"] == []        # empty role set → renders no role tag


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


def test_infra_unit_facts_land_on_the_dependency_box_standing_in_for_it():
    # An infra unit hosts no code, so it gets no process box — it IS the dep box. Its operational facts
    # must ride there, or they would have no home at all once the System tab stops tabling deployment[].
    m = make_deploy_model()
    m.deployment.append(DeploymentRow(unit="mongo", runs_on="docker image mongo:7",
                                      exposed_as="27017", config_source="compose.yml",
                                      variants=[VariantTag(env="prod", source="compose.yml:4")]))
    m.environments = ["dev", "prod"]
    g = model_to_graph(m)
    mg: dict = {"nodes": {k: dict(v) for k, v in g["nodes"].items()}}
    G.add_deployment_nodes(mg, g)
    G.annotate_unit_dep_facts(mg, g)
    assert not any(n.get("unit") == "mongo" and n.get("kind") == "process" for n in mg["nodes"].values())
    d2 = mg["nodes"]["D2"]                                  # the Mongo dep
    assert d2["fields"]["Runs on"] == "docker image mongo:7"
    assert d2["fields"]["Exposed as"] == "27017"
    assert d2["unit"] == "mongo"                            # keeps the unit name findable in search
    assert [v["env"] for v in d2["variants"]] == ["prod"]


def test_an_untraced_unit_gets_a_node_so_its_box_binds():
    # It hosts nothing and matches no dependency, so the overview draws it in the Untraced lane. A drawn
    # box that cannot be selected has no way to show its facts.
    m = make_deploy_model()
    m.deployment.append(DeploymentRow(unit="mystery", runs_on="unknown image"))
    g = model_to_graph(m)
    mg: dict = {"nodes": dict(g["nodes"])}
    G.add_deployment_nodes(mg, g)
    node = next(n for n in mg["nodes"].values() if n.get("unit") == "mystery")
    assert node["kind"] == "process" and node["fields"]["Runs on"] == "unknown image"


def test_an_authored_dep_field_is_not_overwritten_by_a_unit_fact():
    m = make_deploy_model()
    m.deps[1].used_for = "documents"                        # D2 = Mongo
    m.deployment.append(DeploymentRow(unit="mongo", runs_on="mongo:7"))
    g = model_to_graph(m)
    mg: dict = {"nodes": {k: dict(v) for k, v in g["nodes"].items()}}
    mg["nodes"]["D2"]["fields"] = {"Runs on": "authored"}    # a dep that already states this
    G.annotate_unit_dep_facts(mg, g)
    assert mg["nodes"]["D2"]["fields"]["Runs on"] == "authored"
    assert mg["nodes"]["D2"]["unit"] == "mongo"              # the alias is still recorded


# --- overview -------------------------------------------------------------------

def test_process_box_label_is_the_unit_name_not_the_id():
    # regression: process ids (U_n) are not in the clean graph, so the box label must come from the
    # unit name, never fall back to the id.
    mm = G.gen_deployment_mermaid(model_to_graph(make_deploy_model()))
    assert 'U_0["bot"]' in mm and 'U_1["worker"]' in mm and 'U_2["shard"]' in mm


def test_overview_draws_runtime_only_no_subsystems_lane():
    # The overview is RUNTIME: processes + the infrastructure that couples them. Subsystems are code
    # structure — the Subsystems view draws all of them with their real relationships, and placement is
    # answered per element by the pane's "Runs in" row, so a lane here would only restate a subset.
    mm = G.gen_deployment_mermaid(model_to_graph(make_deploy_model()))
    assert 'subgraph L_proc["Processes"]' in mm
    assert 'subgraph L_core["Shared runtime"]' not in mm and 'subgraph L_sat[' not in mm
    assert "L_subs" not in mm and "-->|runs|" not in mm    # no lane, and no tautological aggregate arrow
    assert "class S1 subsystem" not in mm                  # no subsystem boxes at all
    assert 'subgraph L_infra["Shared infrastructure"]' in mm
    # Every arrow a process draws points at shared infra (a `Dn`) or another process (`U_n`).
    targets = [l.split("-->")[1].strip() for l in mm.splitlines() if l.strip().startswith("U_") and "-->" in l]
    assert targets and all(t.startswith("D") or t.startswith("U_") for t in targets)
    ends = sum(1 for l in mm.splitlines() if l.strip() == "end")
    assert mm.count("subgraph ") == ends                  # balanced (incl. nested infra bands)


def test_gen_deployment_emits_a_process_box_per_hosting_unit():
    mm = G.gen_deployment_mermaid(model_to_graph(make_deploy_model()))
    # process boxes (bot/worker/shard = U_0/U_1/U_2)
    assert "class U_0 process" in mm and "class U_1 process" in mm and "class U_2 process" in mm


def test_overview_infra_is_only_the_coupling_points_and_they_get_real_arrows():
    # The lane is COUPLING POINTS, not a catalog. Redis (D1) is emitted to by C1, which runs in BOTH bot
    # and worker → 2 processes → drawn, banded by its derived role, with a real arrow per user. Mongo
    # (D2) is written only by C2 (worker alone) → not a coupling point → not on the overview at all;
    # it stays on worker's card. A catalog here would just restate the Dependencies view.
    mm = G.gen_deployment_mermaid(model_to_graph(make_deploy_model()))
    assert 'subgraph L_infra["Shared infrastructure"]' in mm
    assert 'subgraph L_infra_bus["Message bus"]' in mm and "class D1 infraBus" in mm    # Redis = bus
    assert "U_0 --> D1" in mm and "U_1 --> D1" in mm      # real arrows, one per process that uses it
    assert "class D2" not in mm and "--> D2" not in mm    # single-process infra is not drawn here…
    assert "U_1 --> D2" in G.deployment_cards(model_to_graph(make_deploy_model()))["worker"]  # …only on its card


def test_coupling_point_arrows_carry_their_call_sites():
    # A coupling-point arrow is not mute: it stands for the real component→dep calls made by the code
    # that process runs, so selecting it can answer "why does this process need this".
    edges = G.gen_deployment_infra_edges(model_to_graph(make_deploy_model()))
    assert set(edges) == {"U_0>D1", "U_1>D1", "U_1>D2"}   # bot→Redis, worker→Redis, worker→Mongo
    row = edges["U_0>D1"][0]
    assert row["srcName"] == "PluginA" and row["dstName"] == "Redis"
    assert row["verb"] == "emits" and row["why"] == "publish" and row["where"] == "y.py:2"


def test_infra_arrows_and_their_call_sites_come_from_one_derivation():
    # The arrows drawn and the calls listed must never disagree — the drawn set IS the call-site keys.
    m = make_deploy_model()
    g = model_to_graph(m)
    uid_of = {unit: uid for uid, unit in G._deployment_unit_ids(g)}
    _runs, infra, _boxes = G._deployment_edges(g, uid_of)
    assert infra == set(G._infra_call_sites(g, uid_of))


def test_overview_drops_the_infra_lane_when_nothing_is_shared():
    # A project whose processes share no infrastructure has no coupling points, so the lane disappears
    # rather than degrading back into a catalog of boxes with no arrows.
    m = make_deploy_model()
    m.components[0].runs_in = ["bot"]                     # C1 (→Redis) now runs in bot only
    mm = G.gen_deployment_mermaid(model_to_graph(m))      # C2 (→Mongo) runs in worker only
    assert "subgraph L_infra" not in mm
    assert 'subgraph L_proc["Processes"]' in mm           # the rest of the view is unaffected


def test_ungrouped_component_is_not_drawn_on_the_overview_but_states_its_host():
    # C3 has no subsystem. With no code lane on the overview it is not drawn there at all — the answer
    # to "where does it run" is its own pane row, and shard's card still draws it.
    g = model_to_graph(make_deploy_model())
    mm = G.gen_deployment_mermaid(g)
    assert "class C3 component" not in mm
    mg: dict = {"nodes": {k: dict(v) for k, v in g["nodes"].items()}}
    G.annotate_run_by(mg, g)
    assert mg["nodes"]["C3"]["run_by"] == ["shard"]
    assert "U_2 --> C3" in G.deployment_cards(g)["shard"]


# --- environments (C2) ----------------------------------------------------------

def _env_model() -> ProjectModel:
    m = ProjectModel(title="D", goal="g")
    m.subsystems = [Group(id="S1", name="Core")]
    m.components = [
        Component(id="C1", name="Api", subsystem="S1", source="a.py:1", runs_in=["api"]),      # prod-only
        Component(id="C2", name="Dev", subsystem="S1", source="b.py:1", runs_in=["devbox"]),    # dev-only
        Component(id="C3", name="Shr", subsystem="S1", source="c.py:1", runs_in=["shared"]),    # ungated
    ]
    m.deps = [Dep(id="D1", name="PG", kind="datastore", type="db")]
    m.edges = [Edge(src="C1", verb="reads", dst="D1", why="x", where="a.py:2")]
    m.environments = ["dev", "prod"]
    m.deployment = [DeploymentRow(unit="api", variants=[VariantTag(env="prod", source="docker-compose.yml:5")]),
                    DeploymentRow(unit="devbox", variants=[VariantTag(env="dev")]),  # inferred (no source)
                    DeploymentRow(unit="shared")]                  # empty variants → ungated (every env)
    return m


def test_every_unit_is_drawn_whatever_the_environment_with_its_variants_on_the_node():
    # ONE diagram: the overview always draws every unit, and the viewer dims the ones the selected
    # environment excludes (it reads `variants` off the node). Filtering here made units vanish, which
    # could not be told apart from "not in the map" — and relaid the diagram on every switch.
    g = model_to_graph(_env_model())
    mm = G.gen_deployment_mermaid(g)
    assert all(f'U_{i}["' in mm for i in (0, 1, 2))                 # prod-only, dev-only and ungated
    mg: dict = {"nodes": dict(g["nodes"])}
    G.add_deployment_nodes(mg, g)
    envs = {n["unit"]: [v["env"] for v in n["variants"]] for n in mg["nodes"].values()
            if n.get("kind") == "process"}
    assert envs["api"] == ["prod"] and envs["devbox"] == ["dev"] and envs["shared"] == []


def test_deployment_all_view_shows_every_unit():
    mm_all = G.gen_deployment_mermaid(model_to_graph(_env_model()))   # env=None → All
    assert all(f'U_{i}["' in mm_all for i in (0, 1, 2))              # every unit present


def test_no_environments_degrades_to_single_overview():
    m = _env_model()
    m.environments = []                                             # feature un-adopted
    g = model_to_graph(m)
    assert G.deployment_environments(g) == []                      # no envs → the frontend shows no picker
    assert all(f'U_{i}["' in G.gen_deployment_mermaid(g) for i in (0, 1, 2))  # overview unchanged


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


# --- process topology derived from the async catalog ------------------------------------------

def make_channel_model() -> ProjectModel:
    """Three processes wired by channels: shard publishes `shard.events` that bot consumes, and bot
    publishes two rpc channels that gateway consumes. C4 both publishes and consumes `selfq` inside
    worker — a self-loop, which the topology drops."""
    m = ProjectModel(title="Demo", goal="g")
    m.subsystems = [Group(id="S1", name="Runtime")]
    m.components = [
        Component(id="C1", name="Shard", subsystem="S1", source="s.go:1", runs_in=["shard"]),
        Component(id="C2", name="Bot", subsystem="S1", source="b.py:1", runs_in=["bot"]),
        Component(id="C3", name="Gw", subsystem="S1", source="g.go:1", runs_in=["gateway"]),
        Component(id="C4", name="Worker", subsystem="S1", source="w.py:1", runs_in=["worker"]),
    ]
    m.deps = [Dep(id="D1", name="Redis broker", kind="messaging", type="broker")]
    m.edges = [Edge(src="C2", verb="emits", dst="D1", why="publish", where="y.py:2")]
    m.messaging = [
        MessagingRow(name="shard.events", kind="queue", broker="D1",
                     publishers=["C1"], consumers=["C2"], source="s.go:34"),
        MessagingRow(name="rpc.guild", kind="pubsub", broker="D1",
                     publishers=["C2"], consumers=["C3"], source="rpc.py:45"),
        MessagingRow(name="rpc.broadcast", kind="pubsub", broker="D1",
                     publishers=["C2"], consumers=["C3"], source="rpc.py:37"),
        MessagingRow(name="selfq", kind="queue", broker="D1",
                     publishers=["C4"], consumers=["C4"], source="w.py:9"),
    ]
    m.deployment = [DeploymentRow(unit="shard"), DeploymentRow(unit="bot"),
                    DeploymentRow(unit="gateway"), DeploymentRow(unit="worker")]  # U_0..U_3
    return m


def test_overview_draws_a_process_arrow_per_channel_crossing():
    mm = G.gen_deployment_mermaid(model_to_graph(make_channel_model()))
    assert "U_0 -->|\"shard.events\"| U_1" in mm          # one channel → labelled with its own name
    assert "U_1 -->|\"2 channels\"| U_2" in mm            # two channels on the same pair → counted
    assert "U_3 -->" not in mm                        # a channel a process publishes to ITSELF is no topology


def test_process_arrows_carry_their_channels_for_the_select_panel():
    edges = G.gen_deployment_edges(model_to_graph(make_channel_model()))
    assert [c["name"] for c in edges["U_0>U_1"]] == ["shard.events"]
    assert [c["name"] for c in edges["U_1>U_2"]] == ["rpc.guild", "rpc.broadcast"]
    row = edges["U_0>U_1"][0]
    assert row["kind"] == "queue" and row["brokerName"] == "Redis broker" and row["source"] == "s.go:34"
    assert "U_3>U_3" not in edges                     # the self-loop is dropped here too


def test_synchronous_cross_process_calls_also_draw_a_process_arrow():
    # A client/server app talks over HTTP, not a queue. A backbone component→component edge whose ends
    # run in DIFFERENT units is one process calling another — without this the view is blank for any
    # project with no message bus.
    m = make_channel_model()
    m.messaging = []                                          # no async catalog at all
    m.edges.append(Edge(src="C3", verb="requests", dst="C2", why="dashboard API", where="api.ts:9"))
    mm = G.gen_deployment_mermaid(model_to_graph(m))           # C3=gateway, C2=bot
    assert 'U_2 -->|"requests"| U_1' in mm                     # one call → labelled with its verb
    edges = G.gen_deployment_call_edges(model_to_graph(m))
    assert [r["srcName"] for r in edges["U_2>U_1"]] == ["Gw"]
    assert edges["U_2>U_1"][0]["where"] == "api.ts:9"


def test_an_in_process_call_is_not_topology():
    m = make_channel_model()
    m.messaging = []
    m.edges.append(Edge(src="C2", verb="calls", dst="C2", why="self", where="a.py:1"))  # C2 runs in bot
    assert G.gen_deployment_call_edges(model_to_graph(m)) == {}
    mm = G.gen_deployment_mermaid(model_to_graph(m))
    assert not [l for l in mm.splitlines() if "-->" in l and l.split("-->")[1].strip().startswith("|")]


def test_a_pair_that_talks_both_ways_draws_one_arrow_counting_each_mechanism():
    # Two processes may share a channel AND call each other. One arrow per ordered pair — two arrows
    # would give the same pair two mermaid ids and the second could bind to the wrong bundle.
    m = make_channel_model()
    m.edges.append(Edge(src="C1", verb="calls", dst="C2", why="sync fetch", where="s.go:12"))
    mm = G.gen_deployment_mermaid(model_to_graph(m))            # C1=shard→C2=bot, plus shard.events
    assert 'U_0 -->|"1 channel, 1 call"| U_1' in mm
    assert len([l for l in mm.splitlines() if "U_0 -->" in l and "U_1" in l]) == 1


def test_a_channel_to_a_unit_that_hosts_no_code_is_not_drawn():
    # An arrow may only end on a box the view draws (B1). A consumer whose unit hosts nothing is not a
    # process box, so its channel contributes no arrow rather than one dangling into empty space.
    m = make_channel_model()
    m.components[2].runs_in = []                                     # gateway now hosts no component
    mm = G.gen_deployment_mermaid(model_to_graph(m))
    assert 'subgraph L_untraced' in mm                               # gateway drops to Untraced, not dropped…
    assert "U_2" not in "".join(l for l in mm.splitlines() if "-->" in l)   # …and no arrow reaches it
    assert "U_0 -->" in mm                                           # the unaffected arrow still drawn


def test_a_runs_in_naming_no_deployment_row_is_skipped_not_fatal():
    # `serve` renders without validating, so a map mid-edit can carry a `runs_in` that names no unit.
    # That name has no box, so it must be dropped — never raise and take the whole map down with it.
    m = make_channel_model()
    m.components[0].runs_in = ["ghost-unit"]                         # shard's component: unknown unit
    mm = G.gen_deployment_mermaid(model_to_graph(m))                 # must not raise
    assert "ghost-unit" not in mm
    assert "U_1 -->|\"2 channels\"| U_2" in mm                           # the other topology survives
    assert list(G.gen_deployment_edges(model_to_graph(m))) == ["U_1>U_2"]   # and the bundle agrees


def test_a_channel_name_with_braces_does_not_break_the_diagram():
    # A pipe edge label is stricter than a node label: unquoted `(){}[]@` are PARSE errors that fail the
    # WHOLE diagram. Templated channel names are routine, so the label must be quoted, not mangled.
    m = make_channel_model()
    m.messaging[0].name = "gateway.rpc.{guild_id}"
    mm = G.gen_deployment_mermaid(model_to_graph(m))
    assert 'U_0 -->|\"gateway.rpc.{guild_id}\"| U_1' in mm             # quoted, and the name kept intact


def test_a_gated_units_arrows_are_still_drawn_for_the_viewer_to_dim():
    # The arrow stays in the diagram whatever the environment; the viewer fades it when either end is
    # excluded (applyEnvDim), so a link out of the current environment reads as "not here", not as gone.
    m = make_channel_model()
    m.environments = ["dev", "prod"]
    m.deployment[2].variants = [VariantTag(env="prod", source="compose.yml:9")]   # gateway: prod only
    mm = G.gen_deployment_mermaid(model_to_graph(m))
    assert 'U_1 -->|"2 channels"| U_2' in mm and 'U_0 -->|"shard.events"| U_1' in mm


def test_unit_card_names_the_peers_it_exchanges_channels_with():
    # bot's card gains what it could never show before: who feeds it, and who it feeds.
    cards = G.deployment_cards(model_to_graph(make_channel_model()))
    bot = cards["bot"]
    assert "U_0 -->|\"shard.events\"| U_1" in bot and "U_1 -->|\"2 channels\"| U_2" in bot
    assert 'U_0["shard"]' in bot and 'U_2["gateway"]' in bot        # each peer declared once
    assert bot.count('U_0["shard"]') == 1
    assert "U_0 -->" not in cards["gateway"]                        # shard is not gateway's peer


def test_a_long_channel_name_is_elided_on_the_arrow():
    m = make_channel_model()
    m.messaging[0].name = "imagine-backend.txt2img-requests-v2.queue-fast"
    mm = G.gen_deployment_mermaid(model_to_graph(m))
    assert "U_0 -->|\"imagine-backend.txt2img-reque…\"| U_1" in mm     # 29 chars + the ellipsis


def test_run_by_annotates_subsystems_and_components_with_their_processes():
    # The overview draws one aggregate `runs` arrow, so placement is answered in the info pane instead:
    # a subsystem names the processes that run it, and a component names its own hosts.
    g = model_to_graph(make_deploy_model())
    mg: dict = {"nodes": {k: dict(v) for k, v in g["nodes"].items()}}
    G.annotate_run_by(mg, g)
    assert mg["nodes"]["S1"]["run_by"] == ["bot", "worker"]   # C1 runs in both → its subsystem does too
    assert mg["nodes"]["S2"]["run_by"] == ["worker"]
    assert mg["nodes"]["C1"]["run_by"] == ["bot", "worker"]   # the leaf states its own hosts
    assert mg["nodes"]["C3"]["run_by"] == ["shard"]           # ungrouped component: still answered


def test_run_by_skips_a_unit_that_hosts_no_code():
    # A name with no process box has no card to open, so it must not become a dead link in the pane —
    # the same B2 rule the diagram uses to decide which units get drawn.
    m = make_deploy_model()
    m.components[0].runs_in = ["bot", "ghost-unit"]
    g = model_to_graph(m)
    mg: dict = {"nodes": {k: dict(v) for k, v in g["nodes"].items()}}
    G.annotate_run_by(mg, g)
    assert mg["nodes"]["C1"]["run_by"] == ["bot"]
    assert "ghost-unit" not in mg["nodes"]["S1"]["run_by"]


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


def test_superset_unit_keeps_allinone_label_in_processes_lane():
    # standalone (U_2) runs everything backend+frontend run between them → an all-in-one packaging.
    # With the single aggregate arrow there's no fold lane / core-satellite split: it sits in the one
    # Processes lane, keeping only a label suffix; the overview draws ONE aggregate arrow, no fan.
    mm = G.gen_deployment_mermaid(model_to_graph(make_allinone_model()))
    assert 'subgraph L_proc["Processes"]' in mm and 'subgraph L_allinone' not in mm
    assert "standalone — all-in-one: runs every subsystem" in mm
    # No per-process→subsystem fan: the only arrows are to shared infra (Redis is reached from C1,
    # which runs in both backend and standalone).
    targets = [l.split("-->")[1].strip() for l in mm.splitlines() if l.strip().startswith("U_") and "-->" in l]
    assert targets and all(t == "D1" for t in targets)


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
    assert "all-in-one" not in mm                                # neither unit labelled all-in-one
    assert "class U_0 process" in mm and "class U_1 process" in mm


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")


# --- process topology: co-residency is not a crossing --------------------------------------------

def make_monolith_model() -> ProjectModel:
    """The shape that exploded a live map: shared modules loaded into three processes.

    `Launcher` and `BotRuntime` both run in api, bot AND worker (one `manage.py` starts whichever
    service the sub-command names). Their call is in-process in every one of those units."""
    m = ProjectModel(title="Monolith", goal="g")
    m.components = [
        Component(id="C1", name="Launcher", source="manage.py:1",
                  runs_in=["api", "bot", "worker"]),
        Component(id="C2", name="BotRuntime", source="mee6/bot.py:1",
                  runs_in=["api", "bot", "worker"]),
        Component(id="C3", name="IdService", source="idsvc/main.go:1", runs_in=["ids"]),
    ]
    m.edges = [Edge(src="C1", verb="calls", dst="C2", why="starts the bot", where="manage.py:75"),
               Edge(src="C2", verb="calls", dst="C3", why="mints ids", where="mee6/bot.py:90")]
    m.deployment = [DeploymentRow(unit=u) for u in ("api", "bot", "worker", "ids")]
    return m


def _links(m: ProjectModel) -> dict:
    g = model_to_graph(m)
    uid_of = {unit: uid for uid, unit in G._deployment_unit_ids(g)}
    return {(a, b): rows for (a, b), rows in
            G._call_process_links(g, uid_of, set(uid_of)).items()}


def test_co_resident_components_draw_no_process_arrow():
    # ONE in-process call between two components sharing {api,bot,worker} used to fan out into SIX
    # false network arrows (every ordered pair of the three units), in both directions.
    m = make_monolith_model()
    g = model_to_graph(m)
    uid_of = {unit: uid for uid, unit in G._deployment_unit_ids(g)}
    links = G._call_process_links(g, uid_of, set(uid_of))
    for a in ("api", "bot", "worker"):
        for b in ("api", "bot", "worker"):
            assert (uid_of[a], uid_of[b]) not in links, f"{a}->{b} is an in-process call"


def test_a_genuinely_disjoint_call_still_draws_from_every_host():
    # C2 (api/bot/worker) → C3 (ids) really does leave the process, from each of its three hosts.
    m = make_monolith_model()
    g = model_to_graph(m)
    uid_of = {unit: uid for uid, unit in G._deployment_unit_ids(g)}
    links = G._call_process_links(g, uid_of, set(uid_of))
    assert {a for a, _ in links} == {uid_of[u] for u in ("api", "bot", "worker")}
    assert {b for _, b in links} == {uid_of["ids"]}


def test_partial_overlap_keeps_the_arrow_from_the_non_hosting_unit():
    # The blunt "any shared host → drop it" rule erases REAL traffic. A frontend baked into the
    # backend image AND served by a dev server still crosses the wire from the dev server.
    m = ProjectModel(title="Web", goal="g")
    m.components = [
        Component(id="C1", name="SPA", source="frontend/src/main.tsx:1",
                  runs_in=["backend", "vite-dev"]),
        Component(id="C2", name="API", source="backend/app.py:1", runs_in=["backend"]),
    ]
    m.edges = [Edge(src="C1", verb="calls", dst="C2", why="fetches pages",
                    where="frontend/src/api.ts:20")]
    m.deployment = [DeploymentRow(unit="backend"), DeploymentRow(unit="vite-dev")]
    g = model_to_graph(m)
    uid_of = {unit: uid for uid, unit in G._deployment_unit_ids(g)}
    links = G._call_process_links(g, uid_of, set(uid_of))
    assert list(links) == [(uid_of["vite-dev"], uid_of["backend"])]


# --- capability containers: grouping the overview above the readable cap -------------------------

def make_big_deploy_model(n_connectors: int = 14) -> ProjectModel:
    """A monolith shape: two all-capability processes plus a fleet of single-capability satellites."""
    m = ProjectModel(title="Big", goal="g")
    m.subsystems = [Group(id="S1", name="Connectors"), Group(id="S2", name="Billing"),
                    Group(id="S3", name="Core")]
    m.components, m.deployment = [], []
    for i in range(n_connectors):                       # one capability each -> one container
        m.components.append(Component(id=f"C{i+1}", name=f"conn{i}", subsystem="S1",
                                      source=f"conn/{i}.py:1", runs_in=[f"conn-{i}"]))
        m.deployment.append(DeploymentRow(unit=f"conn-{i}"))
    for j, unit in enumerate(("api", "bot")):           # every capability -> stays its own box
        for k, sub in enumerate(("S1", "S2", "S3")):
            m.components.append(Component(id=f"M{j}{k}", name=f"{unit}-{sub}", subsystem=sub,
                                          source=f"{unit}/{sub}.py:1", runs_in=["api", "bot"]))
        m.deployment.append(DeploymentRow(unit=unit))
    return m


def test_small_maps_are_not_grouped_at_all():
    # Below the cap the flat list IS the clearest drawing; a drill level would buy nothing.
    g = model_to_graph(make_deploy_model())
    assert G.deployment_groups(g, G._process_unit_names(g)) == ({}, {})


def test_same_capability_processes_collapse_into_one_named_container():
    m = make_big_deploy_model()
    g = model_to_graph(m)
    groups, group_of = G.deployment_groups(g, G._process_unit_names(g))
    assert len(groups) == 1
    gid, members = next(iter(groups.items()))
    assert len(members) == 14 and all(u.startswith("conn-") for u in members)
    assert G.deployment_group_label(g, members) == "Connectors (14)"
    assert group_of["conn-3"] == gid


def test_a_multi_capability_process_stays_its_own_box():
    # `api`/`bot` run everything. Folding them into one container produced a box labelled with seven
    # capability names while hiding the two processes a reader most wants to see.
    m = make_big_deploy_model()
    g = model_to_graph(m)
    _, group_of = G.deployment_groups(g, G._process_unit_names(g))
    assert "api" not in group_of and "bot" not in group_of
    mm = G.gen_deployment_mermaid(g)
    assert '["api"]' in mm and '["bot"]' in mm


def test_container_arrows_merge_member_arrows_and_drop_internal_ones():
    m = make_big_deploy_model()
    m.edges = [Edge(src="C1", verb="calls", dst="M00", why="w", where="a.py:1"),   # conn-0 -> api/bot
               Edge(src="C2", verb="calls", dst="M00", why="w", where="b.py:1"),   # conn-1 -> api/bot
               Edge(src="C1", verb="calls", dst="C2", why="w", where="c.py:1")]    # inside the group
    g = model_to_graph(m)
    groups, _ = G.deployment_groups(g, G._process_unit_names(g))
    gid = next(iter(groups))
    mm = G.gen_deployment_mermaid(g)
    out = [l for l in mm.splitlines() if l.strip().startswith(gid) and "-->" in l]
    assert out, mm
    assert not any(f"| {gid}" in l for l in out)       # no self-loop from the internal call
    card = G.gen_deployment_group_card_mermaid(g, gid)
    assert "U_" in card                                 # members are drawn individually on the card


def test_infra_lane_is_capped_and_says_what_it_dropped():
    m = make_big_deploy_model()
    m.deps = [Dep(id=f"D{i}", name=f"store{i}", kind="datastore", type="db") for i in range(1, 12)]
    # every connector touches every store -> 11 shared infra, above the lane cap of 8
    m.edges = [Edge(src=f"C{c}", verb="writes", dst=f"D{i}", why="w", where="x.py:1")
               for i in range(1, 12) for c in (1, 2)]
    mm = G.gen_deployment_mermaid(model_to_graph(m))
    assert mm.count("[(") == G.INFRA_LANE_MAX
    assert "+3 more shared dependencies" in mm         # never a silent truncation
