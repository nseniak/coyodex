#!/usr/bin/env python3
"""Tests for the schema-v2 model layer (`coyodex.model`) — round-trip, deterministic
serialization, and structural (schema) validation on load.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_model.py
    pytest tests/test_model.py
"""
from __future__ import annotations

import json

from coyodex.model import (
    Component,
    Dep,
    Edge,
    Entity,
    EntityField,
    EntityRelation,
    Flow,
    FlowStep,
    GoldenStep,
    Group,
    ModelError,
    ProjectModel,
    UseCase,
    all_elements,
    is_model_document,
    load_model,
    to_canonical_json,
)


# --- builders -------------------------------------------------------------------

def make_model(extra_order: tuple[str, ...] = ("Zeta", "Alpha")) -> ProjectModel:
    """A small but full-shaped model. `extra_order` controls the INSERTION order of a component's
    `extra` dict, so determinism tests can prove key order can't wobble the serialization."""
    m = ProjectModel(title="Demo", goal="A demo project.", commit="abc1234",
                     committed="2026-07-01", built="2026-07-02 10:00")
    m.use_cases = [UseCase(id="UC1", name="View order", actor="Andy", trigger_outcome="opens → sees")]
    m.golden_path = [GoldenStep(id="GP1", title="Andy views the order", uc="UC1")]
    m.subsystems = [Group(id="S1", name="Core", purpose="everything")]
    extra = {k: k.lower() for k in extra_order}
    m.components = [
        Component(id="C1", name="Viewer", subsystem="S1", purpose="shows orders",
                  entry_point="[viewer.py](src/viewer.py#L1)", extra=extra),
        Component(id="C2", name="Store", subsystem="S1", purpose="persists orders"),
    ]
    m.deps = [Dep(id="D1", name="Postgres", kind="datastore", type="SQL database",
                  used_for="orders", where_configured="[cfg](cfg.py#L1)")]
    m.entities = [Entity(id="E1", name="Order", store="orders", meaning="a customer order",
                         source="src/order.py#L1",
                         fields=[EntityField(name="id", type="str", markers=["PK"])],
                         relations=[EntityRelation(verb="has", target="E1",
                                                   src_card="1", dst_card="*")])]
    m.flows = [Flow(uc="UC1", title="View order",
                    steps=[FlowStep(n=1, src="Andy", dst="C1", phrase="opens the list"),
                           FlowStep(n=2, src="C1", dst="E1")])]
    m.edges = [Edge(src="C1", verb="reads", dst="E1", why="show it",
                    where="[viewer.py](src/viewer.py#L5)"),
               Edge(src="C2", verb="persists", dst="E1", why="store it",
                    where="[store.py](src/store.py#L9)"),
               Edge(src="C1", verb="uses", dst="D1", why="query", where="src/viewer.py:7")]
    return m


# --- round-trip + determinism ---------------------------------------------------

def test_round_trip_identity():
    m = make_model()
    j = to_canonical_json(m)
    m2 = load_model(j)
    assert to_canonical_json(m2) == j
    assert m2 == m


def test_serializer_deterministic_across_builds():
    assert to_canonical_json(make_model()) == to_canonical_json(make_model())


def test_serializer_sorts_extra_dicts():
    # Same extra content, different insertion order -> byte-identical serialization.
    assert to_canonical_json(make_model(("Zeta", "Alpha"))) == \
        to_canonical_json(make_model(("Alpha", "Zeta")))


def test_canonical_key_order_is_field_order():
    keys = list(json.loads(to_canonical_json(make_model())).keys())
    assert keys[:6] == ["format", "title", "goal", "commit", "committed", "built"]
    assert keys[-1] == "extras"


# --- structural validation on load ----------------------------------------------

def test_load_rejects_non_model_format():
    try:
        load_model(json.dumps({"format": "something-else"}))
        raise AssertionError("expected ModelError")
    except ModelError as e:
        assert "format" in str(e)


def test_load_rejects_wrong_type_with_path():
    doc = json.loads(to_canonical_json(make_model()))
    doc["components"][0]["purpose"] = 42
    try:
        load_model(json.dumps(doc))
        raise AssertionError("expected ModelError")
    except ModelError as e:
        assert "$.components[0].purpose" in str(e)


def test_load_rejects_unknown_field():
    doc = json.loads(to_canonical_json(make_model()))
    doc["components"][0]["colour"] = "red"
    try:
        load_model(json.dumps(doc))
        raise AssertionError("expected ModelError")
    except ModelError as e:
        assert "colour" in str(e) and "unknown field" in str(e)


def test_load_rejects_missing_required_field():
    doc = json.loads(to_canonical_json(make_model()))
    del doc["use_cases"][0]["name"]
    try:
        load_model(json.dumps(doc))
        raise AssertionError("expected ModelError")
    except ModelError as e:
        assert "use_cases[0]" in str(e)


def test_load_rejects_wrong_id_prefix():
    doc = json.loads(to_canonical_json(make_model()))
    doc["deps"][0]["id"] = "C9"  # a component id in the deps array is a SHAPE error
    try:
        load_model(json.dumps(doc))
        raise AssertionError("expected ModelError")
    except ModelError as e:
        assert "deps" in str(e) and "C9" in str(e)


def test_load_rejects_suffixed_id():
    doc = json.loads(to_canonical_json(make_model()))
    doc["subsystems"][0]["id"] = "S12a"  # the historical malformed-id class, now a load error
    try:
        load_model(json.dumps(doc))
        raise AssertionError("expected ModelError")
    except ModelError as e:
        assert "S12a" in str(e)


def test_absent_optional_fields_take_defaults():
    minimal = {"format": "coyodex-map/2", "title": "T",
               "components": [{"id": "C1", "name": "Only"}]}
    m = load_model(json.dumps(minimal))
    assert m.components[0].purpose == ""
    assert m.components[0].subsystem is None
    assert m.deps == [] and m.flows == []


# --- helpers ---------------------------------------------------------------------

def test_is_model_document():
    assert is_model_document(to_canonical_json(make_model()))
    assert not is_model_document("# A markdown map\n| **C1** | x |\n")
    assert not is_model_document('{"format": "not-a-map"}' + " " * 3000)


def test_all_elements_keyed_by_id():
    els = all_elements(make_model())
    assert set(els) == {"UC1", "GP1", "S1", "C1", "C2", "D1", "E1"}


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
