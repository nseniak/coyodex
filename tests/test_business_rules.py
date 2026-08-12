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
from coyodex.anchors import strip_anchor
from coyodex.impact_git import ImpactCore, ImpactFile, load_map_extents
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
    SubFlow,
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
from coyodex.validate_model import (
    _referenced_ids,
    call_site_anchors,
    component_file_owners,
    anchored_flow_steps,
    rule_components,
    rule_entities,
    rule_steps,
    site_components,
    validate_model,
)

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


# ═══ Phase 2 — the one shared derivation primitive ════════════════════════════════
# A rule's components, its use-case steps and the entities it touches are COMPUTED from its sites.
# These tests exist to stop the two measured facts from being designed away: `Component.files` is
# not disjoint, and the step join is weak on byte equality.

OWN_MAP = REPO / ".coyodex" / "project-map.json"


def load_own_map() -> ProjectModel:
    """This repo's own committed map — the one the ambiguity was measured on."""
    return load_model(OWN_MAP.read_text(encoding="utf-8"))


def make_shared_file_model() -> ProjectModel:
    """Four components claiming ONE file, plus a fifth claiming its own — the shape 5 files on this
    repo's map really have, built deterministically so the assertion cannot rot with a rebuild."""
    m = make_base_model()
    m.components = [Component(id=f"C{i}", name=f"Part {i}", purpose="p",
                              files=["src/shared.py"]) for i in range(1, 5)]
    m.components.append(Component(id="C5", name="Alone", purpose="p", files=["src/solo.py"]))
    m.blocks = [Group(id="BLK1", name="Access", purpose="who may act")]
    m.rules = [BusinessRule(id="BR1", statement="Only an owner may cancel.", block="BLK1",
                            sites=[RuleSite(where="src/shared.py:12", why="rejects a non-owner")])]
    return m


def make_extent_model() -> ProjectModel:
    """One flow whose step sits at a DIFFERENT line of the SAME function as the rule's site, plus a
    step in another function of the same file, plus a step in the same file with no symbol at all."""
    m = make_base_model()
    m.components = [Component(id="C1", name="Guard", purpose="p", files=["src/guard.py"])]
    m.blocks = [Group(id="BLK1", name="Access", purpose="who may act")]
    m.rules = [BusinessRule(id="BR1", statement="Only an owner may cancel.", block="BLK1",
                            sites=[RuleSite(where="src/guard.py:22", why="rejects a non-owner")])]
    m.use_cases = [UseCase(id="UC1", name="Cancel", actors=["R1"]),
                   UseCase(id="UC2", name="Refund", actors=["R1"])]
    m.happy_path = [HappyStep(id="HP1", title="Cancel", uc="UC1")]
    m.flows = [
        Flow(uc="UC1", title="Cancel", steps=[
            FlowStep(n=1, src="R1", dst="C1", phrase="asks"),
            FlowStep(n=2, src="C1", dst="E1", phrase="checks owner", where="src/guard.py:30"),
            FlowStep(n=3, src="C1", dst="E1", phrase="elsewhere", where="src/guard.py:60"),
            FlowStep(n=4, src="C1", dst="E1", phrase="unsymbolled", where="src/guard.py:200")]),
        Flow(uc="UC2", title="Refund", steps=[
            FlowStep(n=1, src="R1", dst="C1", phrase="asks"),
            FlowStep(n=2, src="C1", dst="E1", phrase="same line", where="src/guard.py:22")]),
    ]
    m.edges = [Edge(src="C1", verb="reads", dst="E1", why="show", where="src/guard.py:5"),
               Edge(src="C1", verb="uses", dst="D1", why="q", where="src/guard.py:7")]
    return m


#: `cancel_order` spans 20-40, `refund_order` 50-70 — line 200 sits inside neither.
GUARD_EXTENTS = {"src/guard.py": [(20, 40, "cancel_order", "function"),
                                  (50, 70, "refund_order", "function")]}


# --- fact 1: `Component.files` is not disjoint -------------------------------------

def test_a_shared_file_returns_every_owner_never_one() -> None:
    m = make_shared_file_model()
    assert site_components(m, m.rules[0].sites[0]) == ["C1", "C2", "C3", "C4"]
    assert rule_components(m, m.rules[0]) == ["C1", "C2", "C3", "C4"]


def test_the_repos_own_map_still_has_a_four_owner_file_and_all_four_come_back() -> None:
    """The measurement the design is built on, re-taken on every run. If a rebuild ever made
    `files` disjoint this would go quiet, so it asserts the ambiguity is STILL there — the day it
    is not, the multi-owner rendering is dead code and someone should know."""
    m = load_own_map()
    owners = component_file_owners(m)
    # ONLY files a rule site could actually land in: a shared `.css` proves nothing about the
    # decision surface, and picking the overall maximum would let this pass while every real
    # call-site file had collapsed to a single owner.
    anchored = {strip_anchor(a) for _label, a in call_site_anchors(m)}
    shared = {f: o for f, o in owners.items() if len(o) > 1 and f in anchored}
    assert shared, "expected this repo's own map to still claim ANCHORED files from several components"
    path, worst = max(shared.items(), key=lambda kv: len(kv[1]))
    assert len(worst) >= 4, (path, worst)
    got = site_components(m, RuleSite(where=f"{path}:100"))   # rebuilt from the model, not the dict
    assert got == worst, (got, worst)


def test_a_meaningful_share_of_this_maps_call_sites_sit_in_shared_files() -> None:
    """27% when measured. A single-owner UI would be silently wrong on a quarter of the surface."""
    m = load_own_map()
    shared = {f for f, o in component_file_owners(m).items() if len(o) > 1}
    anchors = [a for _label, a in call_site_anchors(m)]
    in_shared = [a for a in anchors if strip_anchor(a) in shared]
    assert anchors and len(in_shared) / len(anchors) > 0.10, (len(in_shared), len(anchors))


def test_a_site_in_an_unclaimed_file_resolves_to_nobody_rather_than_guessing() -> None:
    m = make_shared_file_model()
    assert site_components(m, RuleSite(where="src/nobody.py:3")) == []


def test_a_components_source_directory_never_claims_a_site() -> None:
    """A component's `source` is where it LIVES, often a directory. Letting a directory prefix
    claim a site is the prototype's 'component home passed off as evidence' error."""
    m = make_shared_file_model()
    m.components = [Component(id="C1", name="Whole tree", purpose="p", source="src/", files=[])]
    assert site_components(m, RuleSite(where="src/shared.py:12")) == []


# --- fact 2: the step join has two strengths, and neither is "same file" -----------

def test_a_byte_equal_anchor_is_an_exact_link() -> None:
    m = make_extent_model()
    exact = [l for l in rule_steps(m, m.rules[0], GUARD_EXTENTS) if l.strength == "exact"]
    assert [(l.uc, l.n) for l in exact] == [("UC2", 2)]


def test_the_symbol_join_is_not_silently_byte_equality() -> None:
    """Line 22 and line 30 are DIFFERENT lines inside one function — the link must exist and must
    be reported as the weaker strength, not as the exact step."""
    m = make_extent_model()
    links = {(l.uc, l.n): l.strength for l in rule_steps(m, m.rules[0], GUARD_EXTENTS)}
    assert links[("UC1", 2)] == "symbol"
    assert links[("UC2", 2)] == "exact"


def test_a_step_in_another_function_of_the_same_file_is_not_a_link() -> None:
    m = make_extent_model()
    reached = {(l.uc, l.n) for l in rule_steps(m, m.rules[0], GUARD_EXTENTS)}
    assert ("UC1", 3) not in reached, "line 60 is in refund_order — a different symbol"


def test_sharing_a_file_with_no_enclosing_symbol_is_not_a_link() -> None:
    """57% of anchors merely share a file with some step. A file-level join lights up nearly every
    row and means nothing, so it does not exist."""
    m = make_extent_model()
    reached = {(l.uc, l.n) for l in rule_steps(m, m.rules[0], GUARD_EXTENTS)}
    assert ("UC1", 4) not in reached


def test_without_a_symbol_table_the_join_degrades_to_exact_only() -> None:
    """"The same enclosing function" is not derivable from the map. Absent the pre-index, the weak
    strength is withheld rather than widened to file equality."""
    m = make_extent_model()
    links = rule_steps(m, m.rules[0])
    assert [(l.uc, l.n, l.strength) for l in links] == [("UC2", 2, "exact")]


def test_exact_wins_over_symbol_for_the_same_step() -> None:
    m = make_extent_model()
    m.rules[0].sites.append(RuleSite(where="src/guard.py:30", why="second site"))
    links = {(l.uc, l.n): l.strength for l in rule_steps(m, m.rules[0], GUARD_EXTENTS)}
    assert links[("UC1", 2)] == "exact"          # the second site anchors that step byte-for-byte


def test_a_subflow_step_reaches_every_referencing_use_case() -> None:
    """Content inside shared machinery must not be invisible — the rule `flow_endpoint_ids_by_uc`
    already follows."""
    m = make_extent_model()
    m.subflows = [SubFlow(id="SF1", name="Owner check", steps=[
        FlowStep(n=1, src="C1", dst="E1", phrase="checks", where="src/guard.py:22")])]
    m.flows = [Flow(uc="UC1", title="Cancel",
                    steps=[FlowStep(n=1, src="C1", dst="E1", phrase="", subflow="SF1")]),
               Flow(uc="UC2", title="Refund",
                    steps=[FlowStep(n=1, src="C1", dst="E1", phrase="", subflow="SF1")])]
    assert {l.uc for l in rule_steps(m, m.rules[0], GUARD_EXTENTS)} == {"UC1", "UC2"}


def test_an_unanchored_site_reaches_no_step() -> None:
    m = make_extent_model()
    m.rules[0].sites = [RuleSite(where="", no_call_site=True)]
    assert rule_steps(m, m.rules[0], GUARD_EXTENTS) == []


# --- entities: only through a step that names one ---------------------------------

def test_a_rule_reaches_an_entity_only_through_a_step_that_names_it() -> None:
    m = make_extent_model()
    assert rule_entities(m, m.rules[0], GUARD_EXTENTS) == ["E1"]


def test_a_rule_whose_steps_name_no_entity_claims_none() -> None:
    m = make_extent_model()
    for f in m.flows:
        for st in f.steps:
            if st.dst == "E1":
                st.dst = "C1"
    assert rule_entities(m, m.rules[0], GUARD_EXTENTS) == []


# --- the shared extents reader ----------------------------------------------------

def test_map_extents_reads_the_preindex_beside_the_map_and_tolerates_its_absence() -> None:
    assert load_map_extents(OWN_MAP), "this repo commits a preindex beside its map"
    with tempfile.TemporaryDirectory() as td:
        assert load_map_extents(Path(td) / "project-map.json") == {}


# --- step identity: `n` is unique per CONTAINER, never per use case ----------------

def make_colliding_step_model() -> ProjectModel:
    """One flow whose OWN step 2 and an expanded sub-flow's step 2 both key `(UC1, 2)`.

    `validate` enforces a unique `n` per flow and per sub-flow separately, so this map is legal —
    and on this repo's own map 26 of 86 anchored step keys collide exactly this way. Keying an
    expanded step by `(uc, n)` merges the two: one row disappears and the survivor carries the
    other's phrase, its site, and — through `rule_entities` — its ENTITY."""
    m = make_extent_model()
    m.subflows = [SubFlow(id="SF1", name="Owner check", steps=[
        FlowStep(n=2, src="C1", dst="E1", phrase="from the sub-flow", where="src/guard.py:22")])]
    m.flows = [Flow(uc="UC1", title="Cancel", steps=[
        FlowStep(n=1, src="C1", dst="C1", phrase="runs the check", subflow="SF1"),
        FlowStep(n=2, src="C1", dst="C1", phrase="from the flow", where="src/guard.py:22")])]
    return m


def test_two_steps_sharing_a_number_after_expansion_both_survive() -> None:
    m = make_colliding_step_model()
    links = rule_steps(m, m.rules[0], GUARD_EXTENTS)
    assert {(l.uc, l.container, l.n) for l in links} == {("UC1", "SF1", 2), ("UC1", "UC1", 2)}
    assert {l.phrase for l in links} == {"from the sub-flow", "from the flow"}


def test_a_colliding_step_number_cannot_fabricate_an_entity_claim() -> None:
    """The rule is enforced at BOTH step 2s; only the sub-flow's names an entity. Keying by
    `(uc, n)` made the flow's own step inherit E1 — an unsupported clause under a real anchor,
    which is the prototype's most damaging error class."""
    m = make_colliding_step_model()
    m.subflows[0].steps[0].dst = "C1"            # now NO reached step names an entity
    assert rule_entities(m, m.rules[0], GUARD_EXTENTS) == []


def test_the_repos_own_map_really_collides_on_uc_and_n() -> None:
    """The measurement behind the container id. If this ever goes to zero the extra key is dead
    weight — but it is 26 of 86 today, so a two-part step identity is simply wrong."""
    m = load_own_map()
    steps = anchored_flow_steps(m)
    assert len({(uc, st.n) for uc, _c, st in steps}) < len({(uc, c, st.n) for uc, c, st in steps})


# --- entity resolution is against the DEFINED ids, not a prefix --------------------

def test_an_entry_point_id_does_not_leak_through_as_an_entity() -> None:
    """`ID_SHAPE` accepts `EP1`, so `startswith("E")` is a decorative guard — model.py:583 warns
    about this exact mistake."""
    m = make_extent_model()
    for f in m.flows:
        for st in f.steps:
            if st.where:
                st.dst = "EP1"
    assert rule_entities(m, m.rules[0], GUARD_EXTENTS) == []


def test_a_dangling_entity_reference_is_not_returned_as_an_entity() -> None:
    m = make_extent_model()
    for f in m.flows:
        for st in f.steps:
            if st.where:
                st.dst = "E99"
    assert rule_entities(m, m.rules[0], GUARD_EXTENTS) == []


# --- path normalization, both directions ------------------------------------------

def test_a_files_entry_carrying_a_line_still_owns_every_site_in_that_file() -> None:
    m = make_shared_file_model()
    m.components = [Component(id="C1", name="Guard", purpose="p", files=["src/shared.py:1"])]
    assert site_components(m, RuleSite(where="src/shared.py:12")) == ["C1"]


def test_a_directory_files_entry_can_never_be_matched_by_a_site() -> None:
    """`src/` trimmed to `src` is matched by the shape-legal anchor `src:12` — manufacturing the
    exact owner a directory is forbidden to claim."""
    m = make_shared_file_model()
    m.components = [Component(id="C1", name="Tree", purpose="p", files=["src/"])]
    assert site_components(m, RuleSite(where="src:12")) == []
    assert site_components(m, RuleSite(where="src/shared.py:12")) == []


# --- link strength does not depend on how the anchor was punctuated ---------------

def test_a_range_site_spanning_the_steps_line_is_still_an_exact_link() -> None:
    m = make_extent_model()
    m.rules[0].sites = [RuleSite(where="src/guard.py:22-24", why="the guard block")]
    links = {(l.uc, l.n): l.strength for l in rule_steps(m, m.rules[0], GUARD_EXTENTS)}
    assert links[("UC2", 2)] == "exact"


# --- ordering ---------------------------------------------------------------------

def test_use_cases_sort_numerically_not_lexicographically() -> None:
    m = make_extent_model()
    m.use_cases.append(UseCase(id="UC10", name="Late", actors=["R1"]))
    m.flows.append(Flow(uc="UC10", title="Late", steps=[
        FlowStep(n=1, src="C1", dst="E1", phrase="same line", where="src/guard.py:22")]))
    order = [l.uc for l in rule_steps(m, m.rules[0], GUARD_EXTENTS) if l.strength == "exact"]
    assert order == ["UC2", "UC10"], order


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
