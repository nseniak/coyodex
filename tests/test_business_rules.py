#!/usr/bin/env python3
"""Tests for the business-rule layer (T7) — the map's decision elements.

Phase 1 covers IDENTITY: a new id prefix is invisible or actively rejected in a dozen places
outside `model.py`, and every one of them fails silently rather than loudly. The `capabilities`
forest shipped with two of those places unpatched (its `source` anchors went unchecked by
`validate` for a release), which is the precedent these tests exist to stop repeating.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_business_rules.py
    pytest tests/test_business_rules.py
"""
from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex import grammar
from coyodex.dump import _group_member_ids, legend_of, resolve_id
from coyodex.impact_git import ImpactCore, ImpactFile
from coyodex.impact_lib import DirectHit, anchor_index
from coyodex.impact_ripple import RippleOptions, build_impact_result, type_of
from coyodex.balance_lib import next_free_group_id
from coyodex.model import (
    ID_ARRAYS,
    ID_SHAPE,
    BusinessRule,
    Component,
    Dep,
    Edge,
    Entity,
    EntityField,
    Flow,
    FlowStep,
    Group,
    HappyStep,
    ProjectModel,
    Role,
    RuleSite,
    Store,
    UseCase,
    all_elements,
    group_forests,
    load_model,
    remap_element_ids,
    to_canonical_json,
)
from coyodex.reconcile import (
    _SET_FIELD_OWNER,
    SetDirective,
    apply_reconcile,
    load_reconcile,
    validate_reconcile,
)
from coyodex.validate_model import _referenced_ids, validate_model

REPO = Path(__file__).resolve().parent.parent


# --- builders -------------------------------------------------------------------

def make_base_model() -> ProjectModel:
    """A minimal map that validates clean, with NO rules — the no-op baseline."""
    m = ProjectModel(title="Demo", goal="A demo.")
    m.roles = [Role(id="R1", name="Andy", kind="human", wants="orders", drives="UC1")]
    m.use_cases = [UseCase(id="UC1", name="View order", actors=["R1"])]
    m.happy_path = [HappyStep(id="HP1", title="View", uc="UC1")]
    m.components = [Component(id="C1", name="Viewer", purpose="shows", entry_point="src/v.py:1",
                              files=["src/v.py"])]
    m.deps = [Dep(id="D1", name="Postgres", kind="datastore", type="SQL database")]
    m.entities = [Entity(id="E1", name="Order", store=Store(notes="orders"), meaning="a thing",
                         source="src/order.py:1",
                         fields=[EntityField(name="id", type="str", markers=["PK"])])]
    m.flows = [Flow(uc="UC1", title="View order",
                    steps=[FlowStep(n=1, src="R1", dst="C1", phrase="opens")])]
    m.edges = [Edge(src="C1", verb="reads", dst="E1", why="show", where="src/v.py:5"),
               Edge(src="C1", verb="uses", dst="D1", why="query", where="src/v.py:7")]
    return m


def make_rule(rid: str = "BR1", block: str | None = "BLK1",
              where: str = "src/v.py:12") -> BusinessRule:
    return BusinessRule(id=rid, statement="Only the order's owner may cancel it.", block=block,
                        sites=[RuleSite(where=where, why="rejects a non-owner caller")])


def make_ruled_model() -> ProjectModel:
    m = make_base_model()
    m.blocks = [Group(id="BLK1", name="Order lifecycle", purpose="who may change an order")]
    m.rules = [make_rule()]
    return m


def problems_of(m: ProjectModel) -> list[str]:
    return validate_model(m)[0]


# --- the id namespace ------------------------------------------------------------

def test_the_two_prefixes_are_registered_shapes() -> None:
    assert ID_SHAPE.match("BLK1") and ID_SHAPE.match("BR7")
    # first-match alternation: neither prefixes the other, and neither swallows the other's digits
    assert not ID_SHAPE.match("BLKA") and not ID_SHAPE.match("B1")


def test_the_two_arrays_are_id_arrays() -> None:
    assert ID_ARRAYS["blocks"] == "BLK" and ID_ARRAYS["rules"] == "BR"


def test_blocks_and_rules_join_all_elements() -> None:
    ids = all_elements(make_ruled_model())
    assert "BLK1" in ids and "BR1" in ids


def test_group_forests_carries_all_four() -> None:
    m = make_ruled_model()
    m.subsystems = [Group(id="S1", name="Core")]
    m.subdomains = [Group(id="SD1", name="Orders")]
    m.capabilities = [Group(id="CAP1", name="Ordering")]
    assert [g.id for g in group_forests(m)] == ["S1", "SD1", "CAP1", "BLK1"]


def test_grammar_id_token_finds_the_new_namespaces() -> None:
    """LOCKSTEP with ID_SHAPE: `remap_element_ids` rewrites `[[ID]]` prose refs through this
    token, so a prefix the model knows and the grammar does not is dropped on every merge."""
    found = grammar.ID_TOKEN.findall("see BLK2 and BR11 beside CAP3 and C5")
    assert set(found) == {"BLK2", "BR11", "CAP3", "C5"}, found


def test_loader_rejects_a_wrong_prefix_in_each_new_array() -> None:
    doc = json.loads(to_canonical_json(make_ruled_model()))
    doc["rules"][0]["id"] = "BLK1"
    assert "not a valid BR-id" in _load_error(doc)
    doc = json.loads(to_canonical_json(make_ruled_model()))
    doc["blocks"][0]["id"] = "BR1"
    assert "not a valid BLK-id" in _load_error(doc)


def _load_error(doc: dict) -> str:
    try:
        load_model(json.dumps(doc))
    except Exception as e:                       # ModelError
        return str(e)
    raise AssertionError("expected the loader to reject this document")


def test_field_order_puts_blocks_and_rules_before_extras() -> None:
    keys = list(json.loads(to_canonical_json(make_base_model())).keys())
    assert keys[-3:] == ["blocks", "rules", "extras"]


# --- references and remap --------------------------------------------------------

def test_a_dangling_block_pointer_is_blocking() -> None:
    m = make_ruled_model()
    m.rules[0].block = "BLK9"
    assert any("BLK9" in p for p in problems_of(m))


def test_a_misshapen_block_pointer_is_blocking() -> None:
    m = make_ruled_model()
    m.rules[0].block = "BLK1a"
    assert any("BR1" in p and "block" in p for p in problems_of(m))


def test_remap_covers_the_block_pointer_and_the_block_parent() -> None:
    """DRIFT GUARD, the `_referenced_ids` twin: a merged-away id must survive nowhere."""
    m = make_ruled_model()
    m.blocks.append(Group(id="BLK9", name="Dup", parent="BLK1"))
    m.rules[0].block = "BLK9"
    assert "BLK9" in _referenced_ids(m)
    remap_element_ids(m, {"BLK9": "BLK1"})
    assert "BLK9" not in _referenced_ids(m)
    assert m.rules[0].block == "BLK1"


def test_a_ruleless_map_is_unchanged_by_the_new_plumbing() -> None:
    """Additivity: every check added here must be a strict no-op while no map carries a rule."""
    m = make_base_model()
    problems, warnings = validate_model(m)
    assert not any("BLK" in t or "BR" in t or "block" in t.lower() for t in problems + warnings)


# --- the four-forest hierarchy ---------------------------------------------------

def test_a_nested_block_is_not_reported_as_a_bad_subsystem() -> None:
    """`_expected_parent_kind` defaulted to "subsystem", so every `BLK2.parent = BLK1` would have
    been a blocking 'is not a subsystem (S…)' — the exact failure capabilities shipped with."""
    m = make_ruled_model()
    m.blocks.append(Group(id="BLK2", name="Refunds", parent="BLK1"))
    assert not any("BLK2" in p for p in problems_of(m))


def test_a_block_parented_to_a_subsystem_is_blocking_and_says_block() -> None:
    m = make_ruled_model()
    m.subsystems = [Group(id="S1", name="Core")]
    m.components[0].subsystem = "S1"
    m.blocks.append(Group(id="BLK2", name="Refunds", parent="S1"))
    assert any("BLK2 parent S1 is not a block (BLK…)" in p for p in problems_of(m))


def test_a_use_case_parented_to_a_subsystem_now_names_the_capability_forest() -> None:
    """Pre-existing mis-report: the hard-coded 'subdomain else subsystem' label called a
    wrong-forest capability pointer 'is not a subsystem (S…)'."""
    m = make_base_model()
    m.subsystems = [Group(id="S1", name="Core")]
    m.components[0].subsystem = "S1"
    m.use_cases[0].capability = "S1"
    assert any("UC1 parent S1 is not a capability (CAP…)" in p for p in problems_of(m))


def test_a_block_nesting_cycle_is_blocking() -> None:
    m = make_ruled_model()
    m.blocks = [Group(id="BLK1", name="A", parent="BLK2"), Group(id="BLK2", name="B", parent="BLK1")]
    assert any("Nesting cycle" in p and "BLK" in p for p in problems_of(m))


# --- per-kind Group field guards -------------------------------------------------

def test_a_block_may_not_carry_a_capability_label() -> None:
    m = make_ruled_model()
    m.blocks[0].label = "core"
    assert any("BLK1 carries `label`" in p and "block" in p for p in problems_of(m))


def test_a_block_may_not_carry_a_subsystem_tech() -> None:
    m = make_ruled_model()
    m.blocks[0].tech = "Python"
    assert any("BLK1 carries `tech`" in p for p in problems_of(m))


def test_a_capability_source_anchor_is_shape_checked() -> None:
    """`_check_anchor_format` enumerated `(*subsystems, *subdomains)` by hand, so a capability's
    anchor was unchecked — a whole forest of anchors nobody validated."""
    m = make_ruled_model()
    m.capabilities = [Group(id="CAP1", name="Ordering", source="[cap](src/cap.py:2)")]
    m.use_cases[0].capability = "CAP1"
    assert any("CAP1 source" in p for p in problems_of(m))


def test_a_block_source_anchor_is_shape_checked() -> None:
    m = make_ruled_model()
    m.blocks[0].source = "[blk](src/blk.py:2)"
    assert any("BLK1 source" in p for p in problems_of(m))


# --- dump ------------------------------------------------------------------------

def test_dump_group_members_of_a_block() -> None:
    m = make_ruled_model()
    m.blocks.append(Group(id="BLK2", name="Refunds", parent="BLK1"))
    assert _group_member_ids(m, "BLK1") == ["BR1", "BLK2"]


def test_dump_resolves_a_block_and_a_rule() -> None:
    m = make_ruled_model()
    blk = resolve_id(m, "BLK1")
    assert blk is not None and blk["kind"] == "block" and blk["members"] == ["BR1"]
    br = resolve_id(m, "BR1")
    assert br is not None and br["kind"] == "business_rule"


def test_dump_legend_lists_blocks_and_rules() -> None:
    rows = {r["id"]: r for r in legend_of(make_ruled_model())}
    assert rows["BLK1"]["kind"] == "block"
    assert rows["BR1"]["kind"] == "business_rule" and rows["BR1"]["parent"] == "BLK1"


def test_dump_members_cli_accepts_a_block() -> None:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "project-map.json"
        path.write_text(to_canonical_json(make_ruled_model()), encoding="utf-8")
        r = subprocess.run([sys.executable, "-m", "coyodex.dump", str(path), "--members", "BLK1"],
                           capture_output=True, text=True, cwd=REPO)
        assert r.returncode == 0, r.stderr
        assert [row["id"] for row in json.loads(r.stdout)] == ["BR1"]


# --- the central claim: derived, never authored -----------------------------------

def test_a_rule_carries_no_authored_component_step_or_sweep_field() -> None:
    """THE design guarantee. A rule's components, its use-case steps and whether it has been swept
    are computed from `sites` against the rest of the map. An authored field for any of them would
    let the layer assert what nobody checked — which is exactly how the prototype lied."""
    names = {f.name for f in dataclasses.fields(BusinessRule)}
    assert names == {"id", "statement", "block", "sites", "access", "confidence"}
    assert not names & {"components", "component", "steps", "use_cases", "swept", "entities"}
    assert {f.name for f in dataclasses.fields(RuleSite)} == {"where", "why", "no_call_site"}


def test_the_loader_refuses_a_smuggled_derived_field() -> None:
    """`_build` rejects ANY unknown field, so a fragment (or a hand-edited map) cannot smuggle one
    in under a plausible name."""
    for smuggled in ("components", "steps", "swept"):
        doc = json.loads(to_canonical_json(make_ruled_model()))
        doc["rules"][0][smuggled] = ["C1"]
        assert "unknown field" in _load_error(doc), smuggled


def test_reconcile_can_set_only_the_block_on_a_rule() -> None:
    """`block` is the ONE reconcile-settable rule field. `_SET_FIELD_OWNER`'s other keys target
    other element types, so no directive can reach a rule's sites or a derived quantity."""
    rule_settable = [f for f, (owner, _label) in _SET_FIELD_OWNER.items() if owner is BusinessRule]
    assert rule_settable == ["block"]


# --- change impact ----------------------------------------------------------------

def test_impact_ripple_knows_the_two_new_kinds() -> None:
    assert type_of("BLK3") == "blocks" and type_of("BR12") == "rules"


def test_anchor_index_seeds_every_group_forest() -> None:
    """`anchor_index` hand-enumerated `subsystems + subdomains`, so a capability's (and now a
    block's) `source` anchor reached neither change-impact nor the drift report."""
    m = make_ruled_model()
    m.subsystems = [Group(id="S1", name="Core", source="src/")]
    m.capabilities = [Group(id="CAP1", name="Ordering", source="src/order.py:1")]
    m.blocks[0].source = "src/v.py:1"
    m.use_cases[0].capability = "CAP1"
    groups = {a.eid for a in anchor_index(m) if a.kind == "group"}
    assert groups == {"S1", "CAP1", "BLK1"}


def test_a_hit_on_a_nested_block_ripples_to_its_parent() -> None:
    """The parent chain is only useful if the arm that WALKS it enumerates the same forests: a
    widened `parent_of` with a two-forest walk is dead code."""
    m = make_ruled_model()
    m.blocks.append(Group(id="BLK2", name="Refunds", parent="BLK1", source="src/v.py:1"))
    reached = _ripple_targets(m, "BLK2")
    assert "BLK1" in reached, reached
    m.capabilities = [Group(id="CAP1", name="Ordering"),
                      Group(id="CAP2", name="Refunding", parent="CAP1", source="src/v.py:1")]
    m.use_cases[0].capability = "CAP1"
    assert "CAP1" in _ripple_targets(m, "CAP2")


def _ripple_targets(m: ProjectModel, eid: str) -> set[str]:
    """Every element reached from ONE direct hit on `eid`."""
    hit = DirectHit(eid, type_of(eid), "src/v.py", "modified", "line", "source")
    core = ImpactCore(pin="p" * 7, base="b" * 7, target="WORKTREE",
                      files=[ImpactFile(path="src/v.py", p_path="src/v.py", status="M",
                                        hits=[hit])])
    return set(build_impact_result(m, core, RippleOptions())["impacts"])


def test_next_free_group_id_covers_every_forest() -> None:
    """The fallback `.get(prefix, m.subsystems)` searched the WRONG array for an unknown prefix and
    minted a colliding id in silence."""
    m = make_ruled_model()
    assert next_free_group_id(m, "BLK") == "BLK2"
    assert next_free_group_id(m, "CAP") == "CAP1"
    try:
        next_free_group_id(m, "XY")
    except ValueError as e:
        assert "unknown group prefix" in str(e)
    else:
        raise AssertionError("an unknown prefix must refuse, not guess")


def test_legend_carries_a_nested_capabilitys_parent_and_source() -> None:
    m = make_ruled_model()
    m.capabilities = [Group(id="CAP1", name="Ordering"),
                      Group(id="CAP2", name="Refunding", parent="CAP1", source="src/order.py:1")]
    m.use_cases[0].capability = "CAP1"
    row = {r["id"]: r for r in legend_of(m)}["CAP2"]
    assert row["parent"] == "CAP1" and row["source"] == "src/order.py:1"


# --- reconcile --------------------------------------------------------------------

def test_set_directive_has_a_block_attribute() -> None:
    """`assigned_fields()` iterates `_SET_FIELD_OWNER` and calls `getattr`, so registering the key
    without the attribute raises AttributeError on EVERY reconcile run, not just this one."""
    assert SetDirective(ids=["BR1"], block="BLK1").assigned_fields() == ["block"]
    assert SetDirective(ids=["BR1"], subsystem="S1").assigned_fields() == ["subsystem"]


def test_reconcile_file_parses_a_block_assignment() -> None:
    rec = load_reconcile(json.dumps({"set": [{"ids": ["BR1", "BR2"], "block": "BLK1"}]}),
                         "reconcile.json")
    assert rec.sets[0].block == "BLK1" and rec.sets[0].ids == ["BR1", "BR2"]


def test_reconcile_assigns_a_block_and_refuses_an_undefined_one() -> None:
    m = make_ruled_model()
    m.rules[0].block = None
    rec = load_reconcile(json.dumps({"set": [{"ids": ["BR1"], "block": "BLK1"}]}), "r.json")
    assert validate_reconcile(m, rec) == []
    stats: dict[str, object] = {}
    apply_reconcile(m, rec, stats)
    assert m.rules[0].block == "BLK1"
    bad = load_reconcile(json.dumps({"set": [{"ids": ["BR1"], "block": "BLK9"}]}), "r.json")
    assert any("BLK9" in p for p in validate_reconcile(m, bad))


def test_reconcile_refuses_a_block_on_a_non_rule() -> None:
    m = make_ruled_model()
    rec = load_reconcile(json.dumps({"set": [{"ids": ["C1"], "block": "BLK1"}]}), "r.json")
    assert any("can only be set on a business rule" in p for p in validate_reconcile(m, rec))


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
