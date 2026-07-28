#!/usr/bin/env python3
"""Tests for the store-centric Data view server derivations:

  - `model_to_graph(...)["data_view"]` — store grouping, container/mode rows, the writer/reader
    `access` map (verb-family classification), not-persisted grouping, the coverage-gap strip, and
    unassigned channels;
  - `gen_channel_mermaids` — one per-broker flowchart only when a broker carries ≥2 channels;
  - `unexplained_persistence_pairs` — the shared core the validator and the gap strip both use.

Conventions: top-level test functions, no classes/fixtures; models built via make_XXX helpers.
"""
from __future__ import annotations

from coyodex.model import (
    Component,
    Dep,
    Edge,
    Entity,
    EntityField,
    MessagingRow,
    ProjectModel,
    StateMachine,
    Store,
)
from coyodex.validate_model import unexplained_persistence_pairs
from coyodex.views import model_to_graph
from coyodex.viewer.gen_viewer import (
    ENTITY_STYLE,
    gen_channel_mermaids,
    gen_domain_mermaid,
)


def make_comp(cid: str, name: str) -> Component:
    return Component(id=cid, name=name, source=f"src/{cid.lower()}.py:1")


def make_data_model() -> ProjectModel:
    """A model exercising every Data-view branch: two collections in one datastore, a dual-role
    store (cache + bus), an empty datastore, a broker reached only through a channel, every
    writer/reader verb family, a not-persisted split (embedded / enum / unstated), an unlinked
    collection, a coverage gap, and an unassigned channel."""
    m = ProjectModel(title="Shop", goal="Sell things.")
    m.components = [make_comp(c, c) for c in ("C1", "C2", "C3", "C4", "C7", "C8", "C9")]
    m.deps = [
        Dep(id="D1", name="MongoDB", kind="datastore", type="document db",
            where_configured="src/db.py:3"),
        # Name carries parens on purpose (a live map ships `Redis (cache / main)`): the diagram's
        # store line is a `container(store)` shape, so nested parens would break Mermaid parsing.
        Dep(id="D2", name="Redis (cache / main)", kind="datastore", type="kv cache"),
        Dep(id="D3", name="Elasticsearch", kind="datastore", type="search"),
        Dep(id="D4", name="ExternalBus", kind="service", type="third-party api"),
    ]
    m.entities = [
        Entity(id="E1", name="Order", meaning="a customer order", source="src/order.py:1",
               store=Store(dep="D1", container="orders", mode="collection", notes="30-day TTL"),
               fields=[EntityField(name="id", type="str", markers=["PK"]),
                       EntityField(name="customer_id", type="str", markers=["FK→E2", "?"]),
                       EntityField(name="code", type="str", markers=["unique"]),
                       EntityField(name="tags", type="str", markers=["[]"]),
                       EntityField(name="total", type="int")],
               states=StateMachine(states=["new", "paid", "shipped"], source="src/order.py:9")),
        Entity(id="E2", name="Customer", meaning="a buyer", source="src/cust.py:1",
               store=Store(dep="D1", container="customers", mode="collection")),
        Entity(id="E3", name="Session", meaning="a login session", source="src/sess.py:1",
               store=Store(dep="D2", container="sess", mode="cache")),
        Entity(id="E4", name="Address", meaning="an address", source="src/addr.py:1",
               store=Store(container="embedded", mode="embedded")),
        Entity(id="E5", name="Config", meaning="a config doc", source="src/cfg.py:1",
               store=Store(container="cfg", mode="collection")),  # container, no dep → unlinked
        Entity(id="E6", name="Status", meaning="an enum", source="src/status.py:1",
               store=Store(mode="enum")),
        Entity(id="E7", name="Ghost", meaning="not stated", source="src/ghost.py:1"),  # store=None
    ]
    m.edges = [
        Edge(src="C1", verb="persists", dst="E1", why="owns", where="src/c1.py:2"),   # owner writer
        Edge(src="C2", verb="writes", dst="E1", why="updates", where="src/c2.py:2"),   # writer
        Edge(src="C3", verb="reads", dst="E1", why="shows", where="src/c3.py:2"),      # reader
        Edge(src="C4", verb="consumes", dst="E1", why="pipes", where="src/c4.py:2"),   # other verb
        Edge(src="C1", verb="persists", dst="E2", why="owns", where="src/c1.py:3"),
        Edge(src="C9", verb="writes", dst="D1", why="lock rows", where="src/c9.py:2"),  # gap: unexplained
    ]
    m.messaging = [
        MessagingRow(name="orders.created", kind="topic", broker="D2", publishers=["C1"],
                     consumers=["C3"], payload="E1", source="src/bus.py:1"),
        MessagingRow(name="orders.shipped", kind="topic", broker="D2", publishers=["C2"],
                     consumers=["C3"], source="src/bus.py:2"),
        MessagingRow(name="external.events", kind="queue", broker="D4", publishers=["C7"],
                     consumers=["C8"], source="src/ext.py:1"),
        MessagingRow(name="floating", kind="queue", broker="", publishers=["C7"],
                     consumers=[], source="src/float.py:1"),
    ]
    return m


def _data_view(m: ProjectModel) -> dict:
    return model_to_graph(m)["data_view"]


def _store(dv: dict, dep: str) -> dict:
    return next(s for s in dv["stores"] if s["dep"] == dep)


def test_stores_include_datastores_and_broker_referenced_deps():
    dv = _data_view(make_data_model())
    ids = [s["dep"] for s in dv["stores"]]
    # D1/D2/D3 are datastore-kind; D4 is a service dep pulled in only because a channel brokers on it.
    assert ids == ["D1", "D2", "D3", "D4"]
    assert _store(dv, "D4")["kind"] == "service"


def test_rows_group_by_store_dep_with_container_and_mode():
    dv = _data_view(make_data_model())
    d1 = _store(dv, "D1")
    assert [(r["entity"], r["container"], r["mode"]) for r in d1["rows"]] == [
        ("E1", "orders", "collection"), ("E2", "customers", "collection")]
    assert d1["rows"][0]["notes"] == "30-day TTL"
    assert _store(dv, "D3")["rows"] == [] and _store(dv, "D3")["channels"] == []  # empty store kept


def test_writer_reader_classification_by_verb_family():
    dv = _data_view(make_data_model())
    a = dv["access"]["E1"]
    assert [(w["id"], w.get("owner", False)) for w in a["writers"]] == [("C1", True), ("C2", False)]
    assert [r["id"] for r in a["readers"]] == ["C3"]
    assert [(o["id"], o["verb"]) for o in a["other"]] == [("C4", "consumes")]  # non-family verb kept


def test_dual_role_store_carries_rows_and_channels():
    dv = _data_view(make_data_model())
    d2 = _store(dv, "D2")
    assert [r["entity"] for r in d2["rows"]] == ["E3"]
    assert [c["name"] for c in d2["channels"]] == ["orders.created", "orders.shipped"]
    assert d2["channels"][0]["payload"] == "E1"


def test_not_persisted_groups_and_unlinked_warned_group():
    dv = _data_view(make_data_model())
    by_mode = {g["mode"]: g for g in dv["not_persisted"]}
    assert [e["id"] for e in by_mode["unlinked"]["entities"]] == ["E5"]  # container+collection, no dep
    assert by_mode["unlinked"]["warn"] is True
    assert [e["id"] for e in by_mode["embedded"]["entities"]] == ["E4"]
    assert [e["id"] for e in by_mode["enum"]["entities"]] == ["E6"]
    assert [e["id"] for e in by_mode[""]["entities"]] == ["E7"]  # store is None → "storage not stated"


def test_coverage_gap_strip_reuses_shared_rule():
    dv = _data_view(make_data_model())
    assert len(dv["gaps"]) == 1
    gap = dv["gaps"][0]
    assert gap["dep"] == "D1" and [p["component"] for p in gap["pairs"]] == ["C9"]


def test_unassigned_channels_bucket():
    dv = _data_view(make_data_model())
    assert [c["name"] for c in dv["unassigned_channels"]] == ["floating"]


def test_data_view_is_deterministic():
    m = make_data_model()
    assert model_to_graph(m)["data_view"] == model_to_graph(m)["data_view"]


def test_channel_mermaid_only_for_two_plus_channels():
    g = model_to_graph(make_data_model())
    ch = gen_channel_mermaids(g)
    assert set(ch) == {"D2"}                     # D2 has 2 channels → diagram; D4 has 1 → none
    assert "flowchart LR" in ch["D2"]
    assert "orders.created" in ch["D2"] and "C1" in ch["D2"]


def test_unexplained_pairs_adapter_hop_and_direct():
    m = make_data_model()
    # Direct: C9 writes D1 with no owned entity → unexplained.
    pairs = unexplained_persistence_pairs(m)
    assert [(c, v, d.id) for c, v, d in pairs] == [("C9", "writes", "D1")]
    # Adapter hop: route C9's write through a component C1 already writes → explained, so it clears.
    m.edges.append(Edge(src="C1", verb="persists", dst="C9", why="adapter", where="src/c1.py:9"))
    assert unexplained_persistence_pairs(m) == []


def test_non_persisted_entity_still_gets_access_rows():
    m = make_data_model()
    m.edges.append(Edge(src="C7", verb="reads", dst="E4", why="renders", where="src/c7.py:5"))
    dv = _data_view(m)
    assert [r["id"] for r in dv["access"]["E4"]["readers"]] == ["C7"]  # embedded entity, still tracked


def _box(src: str, decl: str) -> list[str]:
    lines = src.splitlines()
    start = lines.index(decl)
    return [ln.strip() for ln in lines[start + 1:lines.index("  }", start)]]


def test_domain_diagram_box_carries_store_retention_lifecycle_and_markers():
    src = gen_domain_mermaid(model_to_graph(make_data_model()))
    box = _box(src, '  class E1["Order"] {')
    # Fields keep `[]` on the TYPE (it is the shape) and carry their key markers as a ` · ` suffix —
    # the toggleable part the viewer strips back off without re-laying the diagram out.
    assert box[:5] == ["str id · PK", "str customer_id · FK ?", "str code · uniq",
                       "str[] tags", "int total"]
    # The second compartment, in order: where it lives, how long it is kept, its lifecycle. Each is a
    # `name(args)` line — the shape that lands it below the divider, apart from the fields.
    assert box[5:] == ["🛢 orders(MongoDB)", "⏱ retention(30-day)", "⟳ lifecycle(3 states)"]
    assert not any(ln.startswith("<<") for ln in box)   # never above the entity name
    assert f"style E1 {ENTITY_STYLE}" in src
    # A store name carrying its own parens ("Redis (cache / main)") would nest and break parsing.
    assert "🛢 sess(Redis cache / main)" in src
    # A not-persisted entity (E4, embedded) simply carries NO store line — the absence IS the signal,
    # so it keeps the ordinary entity tint (no dimming, which would only restate the same fact).
    assert not any("🛢" in ln for ln in _box(src, '  class E4["Address"] {'))
    assert f"style E4 {ENTITY_STYLE}" in src


def test_detail_extras_are_always_emitted_so_the_toggle_never_relayouts():
    """The Details toggle hides extras in the RENDERED svg, so the generator must emit them
    unconditionally — otherwise the box would be laid out without them and toggling would move it."""
    m = make_data_model()
    src = gen_domain_mermaid(model_to_graph(m))
    assert " · PK" in src and "⏱ retention(" in src and "⟳ lifecycle(" in src
