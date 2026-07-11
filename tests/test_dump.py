#!/usr/bin/env python3
"""Tests for `coyodex dump` — the fixed-slice JSON reader over the model.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_dump.py
    pytest tests/test_dump.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex.dump import edges_of, main, members_of, record_of, resolve_id
from coyodex.model import (
    Component,
    Edge,
    Entity,
    EntryPoint,
    Group,
    ProjectModel,
    UseCase,
    to_canonical_json,
)

CLI = [sys.executable, "-m", "coyodex.cli", "dump"]


# --- builders -------------------------------------------------------------------

def make_model() -> ProjectModel:
    m = ProjectModel(title="Demo", goal="A demo.")
    m.use_cases = [UseCase(id="UC1", name="View", actors=[])]
    m.subsystems = [Group(id="S1", name="Core", source="[core](backend/core/)"),
                    Group(id="S2", name="Edge", parent="S1")]
    m.components = [
        Component(id="C1", name="Viewer", subsystem="S1", source="backend/viewer.py#L1"),
        Component(id="C2", name="Store", subsystem="S1",
                  entry_point="backend/store.py#L5"),
        Component(id="C3", name="Umbrella", subsystem="S2"),
    ]
    m.entry_points = [
        EntryPoint(kind="http", trigger="GET /orders", source="backend/api.py#L10",
                   component="C3"),
        EntryPoint(kind="queue", trigger="orders.created", source="backend/sub.py#L3",
                   component="C3"),
    ]
    m.subdomains = [Group(id="SD1", name="Orders")]
    m.entities = [Entity(id="E1", name="Order", subdomain="SD1", source="backend/order.py#L7")]
    m.edges = [Edge(src="C1", verb="uses", dst="C2", why="reads",
                    where="backend/viewer.py#L20"),
               Edge(src="C2", verb="persists", dst="E1")]
    return m


# --- --id: resolve --------------------------------------------------------------

def test_resolve_component_uses_its_canonical_anchor():
    r = resolve_id(make_model(), "C1")
    assert r == {"id": "C1", "kind": "component", "name": "Viewer",
                 "source": "backend/viewer.py#L1", "members": []}


def test_resolve_component_falls_back_to_the_entry_point_href():
    r = resolve_id(make_model(), "C2")
    assert r is not None and r["source"] == "backend/store.py#L5"


def test_resolve_component_lists_its_member_entry_points():
    r = resolve_id(make_model(), "C3")
    assert r is not None
    assert r["members"] == [{"trigger": "GET /orders", "source": "backend/api.py#L10"},
                            {"trigger": "orders.created", "source": "backend/sub.py#L3"}]


def test_resolve_group_lists_member_ids_and_link_href():
    r = resolve_id(make_model(), "S1")
    assert r is not None
    assert r["source"] == "backend/core/"
    assert r["members"] == ["C1", "C2", "S2"]  # components first, then child subsystems


def test_resolve_entity_anchors_at_its_source():
    r = resolve_id(make_model(), "E1")
    assert r is not None and r["source"] == "backend/order.py#L7" and r["kind"] == "entity"


def test_resolve_unknown_id_is_none():
    assert resolve_id(make_model(), "C99") is None


# --- --record --------------------------------------------------------------------

def test_record_is_the_full_stored_element():
    r = record_of(make_model(), "C2")
    assert r is not None
    assert r["entry_point"] == "backend/store.py#L5" and r["subsystem"] == "S1"


# --- --edges ---------------------------------------------------------------------

def test_edges_slice_splits_in_and_out():
    e = edges_of(make_model(), "C2")
    assert [x["src"] for x in e["in"]] == ["C1"]
    assert [x["dst"] for x in e["out"]] == ["E1"]
    assert e["in"][0]["where"] == "backend/viewer.py#L20"


def test_edges_slice_of_an_unwired_node_is_empty():
    e = edges_of(make_model(), "C3")
    assert e == {"in": [], "out": []}


# --- --members -------------------------------------------------------------------

def test_members_returns_full_records_of_the_groups_children():
    ms = members_of(make_model(), "S1")
    assert [r["id"] for r in ms] == ["C1", "C2", "S2"]
    assert ms[0]["name"] == "Viewer"


def test_subdomain_members_are_its_entities():
    ms = members_of(make_model(), "SD1")
    assert [r["id"] for r in ms] == ["E1"]


# --- CLI -------------------------------------------------------------------------

def run_dump(args: list[str], model: ProjectModel | None = None) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "project-map.json"
        path.write_text(to_canonical_json(model or make_model()), encoding="utf-8")
        proc = subprocess.run(CLI + [str(path)] + args, capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr


def test_cli_whole_dump_is_the_canonical_json():
    code, out, _ = run_dump([])
    assert code == 0 and out == to_canonical_json(make_model())


def test_cli_id_slice_emits_json():
    code, out, _ = run_dump(["--id", "S1"])
    assert code == 0
    assert json.loads(out)["members"] == ["C1", "C2", "S2"]


def test_cli_unknown_id_fails_loudly():
    code, _, err = run_dump(["--id", "C99"])
    assert code == 1 and "C99" in err


def test_cli_members_of_a_non_group_is_a_usage_error():
    code, _, err = run_dump(["--members", "C1"])
    assert code == 2 and "subsystem" in err


def test_cli_rejects_two_slice_flags():
    code, _, err = run_dump(["--id", "C1", "--edges", "C1"])
    assert code == 2 and "ONE slice" in err


def test_main_reports_a_missing_map():
    assert main(["/nonexistent/project-map.json"]) == 1


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
