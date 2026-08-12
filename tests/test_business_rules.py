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

from typing import cast

import dataclasses
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex import grammar
from coyodex.dump import _group_member_ids, legend_of, resolve_id
from coyodex.anchors import strip_anchor
from coyodex.assemble import _merge_duplicate_rules
from coyodex.impact_git import ImpactCore, ImpactFile, compute_impact, load_map_extents
from coyodex.audit_model import _THEMES, l2_worklist_model
from coyodex.impact_lib import _CALL_SITE_KINDS, DirectHit, anchor_index
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
    ExtraSection,
    SecurityRow,
    Store,
    SubFlow,
    UseCase,
    all_elements,
    group_forests,
    load_model,
    remap_element_ids,
    to_canonical_json,
)
from coyodex.lint_fragment import lint_fragment_problems
from coyodex.record import KNOWN_HEADINGS
from coyodex.reconcile_build import coverage_report, expand
from coyodex.reconcile import (
    _SET_FIELD_OWNER,
    SetDirective,
    apply_reconcile,
    load_reconcile,
    validate_reconcile,
)
from coyodex.views import model_to_graph, model_to_markdown
from coyodex.validate_model import (
    _referenced_ids,
    call_site_anchors,
    component_file_owners,
    _anchor_pairs,
    _check_anchor_format,
    anchored_flow_steps,
    check_anchor_existence_model,
    check_operative_lines_model,
    check_rules_model,
    rule_components,
    rule_entities,
    rule_steps,
    rules_swept,
    site_components,
    sweep_debt,
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


# ═══ Phase 3 — validation, escapes, the sweep canary ══════════════════════════════
# Every check here is a STRICT NO-OP on a ruleless map: 10+ tests assert on the exact advisory set
# of maps that carry no rules, and the trapdoor golden must stay problem-free.

def make_rule_repo(td: str) -> Path:
    """A tiny repo whose one file has a definition header, a comment and one operative line."""
    root = Path(td)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "guard.py").write_text(
        "def cancel_order(user, order):\n"          # 1 — a definition header
        "    # only the owner may cancel\n"          # 2 — a comment
        "    if order.owner_id != user.id:\n"        # 3 — the operative line
        "        raise Forbidden()\n",               # 4
        encoding="utf-8")
    return root


def make_checkable_model() -> ProjectModel:
    m = make_base_model()
    m.components = [Component(id="C1", name="Guard", purpose="p", source="src/guard.py:1",
                              files=["src/guard.py"])]
    m.entities = [Entity(id="E1", name="Order", store=Store(notes="orders"), meaning="a thing",
                         source="src/guard.py:1",
                         fields=[EntityField(name="id", type="str", markers=["PK"])])]
    m.flows = [Flow(uc="UC1", title="Cancel", steps=[
        FlowStep(n=1, src="R1", dst="C1", phrase="asks to cancel"),
        FlowStep(n=2, src="C1", dst="E1", phrase="rejects a non-owner", where="src/guard.py:3")])]
    m.edges = [Edge(src="C1", verb="reads", dst="E1", why="show", where="src/guard.py:3"),
               Edge(src="C1", verb="uses", dst="D1", why="query", where="src/guard.py:4")]
    m.blocks = [Group(id="BLK1", name="Order lifecycle", purpose="who may change an order")]
    m.rules = [BusinessRule(id="BR1", statement="Only the order's owner may cancel it.",
                            block="BLK1",
                            sites=[RuleSite(where="src/guard.py:3", why="rejects a non-owner")])]
    return m


def rule_problems(m: ProjectModel) -> list[str]:
    return check_rules_model(m)[0]


def rule_warnings(m: ProjectModel) -> list[str]:
    return check_rules_model(m)[1]


# --- the no-op guarantee ----------------------------------------------------------

def test_a_ruleless_map_gets_no_rule_problem_or_warning() -> None:
    assert check_rules_model(make_base_model()) == ([], [])


def test_the_committed_fixtures_stay_exactly_as_they_were() -> None:
    """Both committed fixtures have ZERO component `files` and ZERO flow-step anchors, so any
    always-on rule check would fire on them — and `test_trapdoor_tools.py` requires the golden to
    stay problem-free."""
    for rel in ("tests/fixtures/mcpolis-project-map.json",
                "eval/fixtures/trapdoor/golden/project-map.json"):
        m = load_model((REPO / rel).read_text(encoding="utf-8"))
        assert check_rules_model(m) == ([], []), rel


def test_the_canary_is_silent_until_a_map_carries_rules() -> None:
    """`sweep_debt` answers 'did the sweep miss something?'. On a map nobody swept EVERY decision
    is trivially unclaimed, so firing there would put a permanent advisory on every existing map —
    the 'flag conflating nobody-looked with no-line-exists' the prototype shipped."""
    m = make_checkable_model()
    m.components.append(Component(id="C2", name="Billing", purpose="p", files=["src/bill.py"]))
    m.flows[0].steps[1].phrase = "rejects a non-owner unless the caller is an admin"
    m.rules = []
    assert sweep_debt(m) == []
    # a rule in a component the step does NOT name — neither anchor nor structural coverage
    m.rules = [BusinessRule(id="BR1", statement="Something else.", sites=[
        RuleSite(where="src/bill.py:4", why="elsewhere")])]
    assert sweep_debt(m), "with rules present the unclaimed decision must surface"


def test_a_rule_enforced_in_a_component_the_step_names_covers_that_step() -> None:
    """THE PERVERSE-INCENTIVE FIX. A flow step's `where` is the CALLER's line (`C1 → C2 : checks
    the owner` anchors where C1 calls C2) while the rule's operative line is inside C2 — a different
    file, so no anchor link can ever exist. Requiring one made "the worklist is empty" unreachable
    by honest anchoring, and the only route to a clean `validate` was to add a decoy site on the
    step's own line: the exact corruption the contract forbids, rewarded by the gate."""
    m = make_checkable_model()
    m.components = [Component(id="C1", name="Controller", purpose="p", files=["src/ctl.py"]),
                    Component(id="C2", name="Guard", purpose="p", files=["src/guard.py"])]
    m.flows[0].steps = [
        FlowStep(n=1, src="R1", dst="C1", phrase="asks to cancel"),
        # the step anchors the CALLER's line; the decision lives in C2
        FlowStep(n=2, src="C1", dst="C2", phrase="rejects a non-owner", where="src/ctl.py:40")]
    m.edges = [Edge(src="C1", verb="calls", dst="C2", why="guard", where="src/ctl.py:40")]
    m.rules[0].sites = [RuleSite(where="src/guard.py:12", why="the real guard")]
    assert sweep_debt(m) == [], "an honestly-anchored rule must clear the step it decides"
    # ...and a rule in a component the step names NOTHING of does not
    m.components.append(Component(id="C3", name="Billing", purpose="p", files=["src/bill.py"]))
    m.rules[0].sites = [RuleSite(where="src/bill.py:1", why="unrelated")]
    assert [(c, st.n) for c, st in sweep_debt(m)] == [("UC1", 2)]


# --- a site reaches all three anchor families -------------------------------------

def test_a_misshapen_site_anchor_is_a_shape_problem() -> None:
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(where="[guard](src/guard.py:3)", why="a markdown link")]
    assert any("BR1 site[0] where" in p for p in problems_of(m))


def test_a_dead_site_anchor_is_a_blocking_existence_problem() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = make_rule_repo(td)
        m = make_checkable_model()
        m.rules[0].sites = [RuleSite(where="src/guard.py:900", why="past the end")]
        problems = check_anchor_existence_model(m, [root])
        assert any("BR1 site[0]" in p and "does not have" in p for p in problems), problems


def test_a_definition_header_site_draws_the_operative_line_advisory() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = make_rule_repo(td)
        m = make_checkable_model()
        m.rules[0].sites = [RuleSite(where="src/guard.py:1", why="the def header")]
        warnings = check_operative_lines_model(m, [root])
        assert any("BR1 site[0]" in w for w in warnings), warnings
        m.rules[0].sites = [RuleSite(where="src/guard.py:2", why="a comment")]
        assert any("comment" in w for w in check_operative_lines_model(m, [root]))
        m.rules[0].sites = [RuleSite(where="src/guard.py:3", why="the operative line")]
        assert not any("BR1" in w for w in check_operative_lines_model(m, [root]))


def test_a_site_reaches_all_three_families_from_one_map() -> None:
    """One throwaway map with a bad-shape site, a dead site and a def-header site: each family must
    report its own, and none may swallow another's."""
    with tempfile.TemporaryDirectory() as td:
        root = make_rule_repo(td)
        m = make_checkable_model()
        m.rules = [
            BusinessRule(id="BR1", statement="a", sites=[RuleSite(where="not an anchor at all")]),
            BusinessRule(id="BR2", statement="b", sites=[RuleSite(where="src/guard.py:900")]),
            BusinessRule(id="BR3", statement="c", sites=[RuleSite(where="src/guard.py:1")]),
        ]
        assert any("BR1 site[0] where" in p for p in _check_anchor_format(m))
        assert any("BR2 site[0]" in p for p in check_anchor_existence_model(m, [root]))
        assert any("BR3 site[0]" in w for w in check_operative_lines_model(m, [root]))
        assert {label.split()[0] for label, _a in _anchor_pairs(m) if label.startswith("BR")} \
            == {"BR1", "BR2", "BR3"}


# --- one rule states one decision -------------------------------------------------

def test_a_statementless_rule_is_blocking() -> None:
    m = make_checkable_model()
    m.rules[0].statement = "  "
    assert any("BR1 states no decision" in p for p in rule_problems(m))


def test_a_siteless_rule_is_blocking() -> None:
    m = make_checkable_model()
    m.rules[0].sites = []
    assert any("lists no enforcement site" in p for p in rule_problems(m))


def test_a_site_with_neither_where_nor_no_call_site_is_blocking() -> None:
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(where="", why="nothing")]
    assert any("has no `where`" in p for p in rule_problems(m))


def test_a_site_with_both_where_and_no_call_site_is_blocking() -> None:
    """Mirrors Edge/FlowStep, but BLOCKING rather than advisory: a site is the map's strongest
    'this line acts' claim, and a contradictory one cannot be read either way."""
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(where="src/guard.py:3", no_call_site=True)]
    assert any("sets `no_call_site` but carries a `where`" in p for p in rule_problems(m))


def test_a_declared_absence_site_is_legal() -> None:
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(where="", why="enforced by the type", no_call_site=True)]
    assert rule_problems(m) == []


def test_a_whole_file_site_is_blocking() -> None:
    """A site claims ONE line enforces the rule. Without a `:line` the operative-line check —
    which is the only deterministic thing standing between a site and a component home — is
    skipped, so the claim is unfalsifiable by construction."""
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(where="src/guard.py", why="somewhere in here")]
    assert any("names a whole file" in p for p in rule_problems(m))


# --- the derivation inputs must exist ---------------------------------------------

def test_rules_on_a_map_whose_components_declare_no_files_is_blocking() -> None:
    """Rot silently zeroes the layer: both committed fixtures have zero component `files`, so a
    rule on such a map renders bare — indistinguishable from a rule nobody enforces."""
    m = make_checkable_model()
    m.components[0].files = []
    assert any("NO component declares `files`" in p for p in rule_problems(m))


def test_a_rule_landing_in_an_unclaimed_file_is_advisory_and_recordable() -> None:
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(where="src/other.py:3", why="elsewhere")]
    assert any("BR1" in w and "no component claims" in w for w in rule_warnings(m))
    m.extras = [ExtraSection(heading="Sweep debt", body="BR1: the guard lives in a vendored file")]
    assert not any("no component claims" in w for w in rule_warnings(m))


# --- the interim security-duplication guard ---------------------------------------

def test_an_access_rule_repeating_a_security_source_is_blocking_and_escapable() -> None:
    m = make_checkable_model()
    m.rules[0].access = True
    m.security = [SecurityRow(surface="Cancel order", who="owner", source="src/guard.py:3")]
    assert any("claimed twice" in p for p in rule_problems(m))
    m.extras = [ExtraSection(heading="Accepted duplications",
                             body="src/guard.py:3: the row ships until the fold")]
    assert not any("claimed twice" in p for p in rule_problems(m))


def test_a_non_access_rule_sharing_a_security_anchor_is_fine() -> None:
    """This repo's own precedent says an anchor is NOT a claim identity — one line can legitimately
    guard two surfaces — so the guard is scoped to `access` rules and exact duplication."""
    m = make_checkable_model()
    m.security = [SecurityRow(surface="Cancel order", who="owner", source="src/guard.py:3")]
    assert rule_problems(m) == []


# --- the sweep canary and DERIVED sweep state -------------------------------------

def make_swept_model() -> ProjectModel:
    """Two decision-sounding steps in TWO components; the rule covers only the first.

    Two components deliberately: with both steps naming C1, a rule enforced in C1 covers both
    STRUCTURALLY (a rule in a component the step names is coverage — see
    `rule_claimed_step_keys`), and the canary would have nothing to report."""
    m = make_checkable_model()
    m.components.append(Component(id="C2", name="Admin", purpose="p", files=["src/admin.py"]))
    m.flows[0].steps = [
        FlowStep(n=1, src="R1", dst="C1", phrase="asks to cancel"),
        FlowStep(n=2, src="C1", dst="E1", phrase="rejects a non-owner", where="src/guard.py:3"),
        FlowStep(n=3, src="C2", dst="E1", phrase="only an admin may override",
                 where="src/admin.py:4")]
    m.edges.append(Edge(src="C2", verb="reads", dst="E1", why="override", where="src/admin.py:4"))
    return m


def test_the_canary_lists_the_unclaimed_decision_and_shrinks_after_a_sweep() -> None:
    m = make_swept_model()
    assert [(container, st.n) for container, st in sweep_debt(m)] == [("UC1", 3)]
    m.rules.append(BusinessRule(id="BR2", statement="Only an admin may override a cancel.",
                                block="BLK1",
                                sites=[RuleSite(where="src/admin.py:4", why="the admin gate")]))
    assert sweep_debt(m) == []


def test_the_canary_shrinks_when_a_step_is_recorded_as_not_a_decision() -> None:
    m = make_swept_model()
    m.extras = [ExtraSection(heading="Sweep debt",
                             body="src/admin.py:4: an override flag, not a product decision")]
    assert sweep_debt(m) == []


def test_sweep_state_is_derived_from_the_canary_not_asserted() -> None:
    """Sweep state is PER RULE and scoped to the rule's own components: BR1 lives in C1, and the
    uncovered decision is in C2, so BR1 is swept while the map still carries debt."""
    m = make_swept_model()
    assert rules_swept(m) == {"BR1": True}
    assert [(c, st.n) for c, st in sweep_debt(m)] == [("UC1", 3)]
    m.rules.append(BusinessRule(id="BR2", statement="Only an admin may override a cancel.",
                                block="BLK1",
                                sites=[RuleSite(where="src/admin.py:4", why="the admin gate")]))
    assert rules_swept(m) == {"BR1": True, "BR2": True} and sweep_debt(m) == []


def test_a_rule_is_unswept_while_decision_shaped_code_in_its_files_is_unclaimed() -> None:
    """The two halves are asymmetric ON PURPOSE. COVERAGE asks which components the step NAMES
    (a rule enforced in one of them decides it). ATTRIBUTION asks which components own the file the
    step is ANCHORED IN. So an uncovered step whose anchor sits in a rule's file holds that rule
    unswept: there is decision-shaped code in the code it governs that nothing claims."""
    m = make_swept_model()
    # C2 holds no rule, and its step is ANCHORED inside C1's file — decision-shaped code in the
    # code BR1 governs, reached by a component nothing claims.
    m.flows[0].steps[2].where = "src/guard.py:9"
    assert rules_swept(m) == {"BR1": False}
    m.rules.append(BusinessRule(id="BR2", statement="Only an admin may override a cancel.",
                                block="BLK1",
                                sites=[RuleSite(where="src/admin.py:4", why="the admin gate")]))
    assert rules_swept(m) == {"BR1": True, "BR2": True}


def test_a_rule_with_no_component_is_never_swept() -> None:
    """There is no territory to have finished sweeping."""
    m = make_swept_model()
    m.rules[0].sites = [RuleSite(where="src/other.py:3", why="elsewhere")]
    assert rules_swept(m)["BR1"] is False


def test_debt_in_another_components_file_does_not_hold_a_rule_unswept() -> None:
    m = make_swept_model()
    m.components.append(Component(id="C2", name="Other", purpose="p", files=["src/other.py"]))
    m.flows[0].steps[2].where = "src/other.py:1"
    assert rules_swept(m)["BR1"] is True


# --- rule identity is content, never the authored id ------------------------------

def test_two_agents_stating_one_rule_are_caught_by_content_not_id() -> None:
    """Ids cannot carry identity: rules are authored one agent per block from disjoint ranges, so
    two agents stating one rule produce two ids and the duplicate-ID check stays silent."""
    m = make_checkable_model()
    m.rules.append(BusinessRule(id="BR2", statement="Only the ORDER'S owner  may cancel it!",
                                block="BLK1",
                                sites=[RuleSite(where="src/guard.py:3", why="same line")]))
    assert any("BR1, BR2 state the same decision" in p for p in rule_problems(m))


def test_the_same_statement_at_different_sites_is_two_rules() -> None:
    m = make_checkable_model()
    m.rules.append(BusinessRule(id="BR2", statement="Only the order's owner may cancel it.",
                                block="BLK1",
                                sites=[RuleSite(where="src/guard.py:4", why="another line")]))
    assert not any("state the same decision" in p for p in rule_problems(m))


# --- lint-fragment shifts the blocking rules left ---------------------------------

def test_lint_fragment_catches_a_bad_site_in_the_authoring_agents_own_turn() -> None:
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(where="src/guard.py", why="a whole file")]
    assert any("names a whole file" in p for p in lint_fragment_problems(m, None))


def test_lint_fragment_does_not_report_whole_map_sweep_debt_on_one_block() -> None:
    """A fragment holds ONE block's rules, so every other block's decisions would read as debt."""
    m = make_swept_model()
    assert not any("sweep" in p.lower() for p in lint_fragment_problems(m, None))


# --- reconciled after the phase-3 review -------------------------------------------

def test_the_canary_counts_a_subflow_step_once_and_labels_it_by_its_container() -> None:
    """`UC9 step 4` is the WRONG row when the step was authored in SF50 — UC9 has its own step 4 —
    and a sub-flow ridden by three use cases was counted three times."""
    m = make_swept_model()
    m.subflows = [SubFlow(id="SF1", name="Override check", steps=[
        FlowStep(n=3, src="C2", dst="E1", phrase="only an admin may override",
                 where="src/admin.py:4")])]
    m.flows[0].steps = [FlowStep(n=1, src="C1", dst="C1", phrase="runs it", subflow="SF1"),
                        FlowStep(n=2, src="C1", dst="E1", phrase="rejects a non-owner",
                                 where="src/guard.py:3")]
    m.flows.append(Flow(uc="UC2", title="Refund", steps=[
        FlowStep(n=1, src="C1", dst="C1", phrase="runs it", subflow="SF1")]))
    m.use_cases.append(UseCase(id="UC2", name="Refund", actors=["R1"]))
    assert [(c, st.n) for c, st in sweep_debt(m)] == [("SF1", 3)]


def test_a_rule_enforced_inside_the_steps_function_claims_that_step() -> None:
    """The authoring contract tells the sweep to anchor the TRUE operative line even when another
    line would join the step. Exact-only claiming would then leave every such step as permanent
    debt, and the UI would show a rule enforcing a step that `validate` calls unclaimed."""
    m = make_swept_model()
    # Both steps name C2, which holds no rule, so STRUCTURAL coverage cannot fire and the anchor
    # strength is what decides. BR1 is enforced in C1, whose file both steps are anchored in.
    m.flows[0].steps[1].src = "C2"
    m.flows[0].steps[1].where = "src/guard.py:5"
    m.flows[0].steps[2].src = "C2"
    m.flows[0].steps[2].where = "src/guard.py:25"        # the second decision, another function
    m.rules[0].sites = [RuleSite(where="src/guard.py:8", why="the real guard, 3 lines down")]
    ext = {"src/guard.py": [(1, 10, "cancel_order", "function"),
                            (20, 30, "override", "function")]}
    assert [(c, st.n) for c, st in sweep_debt(m, ext)] == [("UC1", 3)]   # step 2 is now claimed
    assert [(c, st.n) for c, st in sweep_debt(m)] == [("UC1", 2), ("UC1", 3)]  # exact-only: more debt


def test_a_recorded_suppression_is_reported_never_silent() -> None:
    """A silence you cannot see reads exactly like having no findings — and this escape flips
    `rules_swept`, a DERIVED state."""
    m = make_swept_model()
    m.extras = [ExtraSection(heading="Sweep debt",
                             body="src/admin.py:4: an override flag, not a product decision")]
    warnings = rule_warnings(m)
    assert any("suppressed by a recorded 'Sweep debt' line" in w and "counted as SWEPT" in w
               for w in warnings), warnings


def test_lint_fragment_does_not_fail_a_block_fragment_on_another_fragments_files() -> None:
    """A rules-only fragment carries no components at all — failing it on "NO component declares
    `files`" is a defect the block agent does not own and cannot fix."""
    frag = ProjectModel(title="", goal="")
    frag.blocks = [Group(id="BLK1", name="Order lifecycle", purpose="who may change an order")]
    frag.rules = [BusinessRule(id="BR1", statement="Only the owner may cancel.",
                               sites=[RuleSite(where="src/guard.py:3", why="rejects a non-owner")])]
    assert lint_fragment_problems(frag, None) == []
    # ... and the map-wide gate still fires at the lead's validate
    m = make_checkable_model()
    m.components[0].files = []
    assert any("NO component declares `files`" in p for p in check_rules_model(m)[0])


def test_a_declared_absence_site_survives_a_json_round_trip() -> None:
    """`where: str` with a pattern that rejects "" made `no_call_site` unwritable — the published
    schema said one thing and the model another."""
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(where=None, why="enforced by the type", no_call_site=True)]
    back = load_model(to_canonical_json(m))
    assert back.rules[0].sites[0].where is None and back.rules[0].sites[0].no_call_site
    assert check_rules_model(back)[0] == []


def test_record_accepts_every_heading_the_tools_read() -> None:
    """The bug class the 'Sweep debt' entry fixed, swept: 'Coverage exceptions' and 'Persistence
    exceptions' were read by `validate` and rejected by `coyodex record` — exit 2 in a live build,
    pinned by nothing."""
    src = "\n".join((REPO / "tools" / "coyodex" / f).read_text(encoding="utf-8")
                     for f in ("validate_model.py", "balance_lib.py", "audit_model.py",
                               "anchor_drift.py"))
    read = {h.lower() for h in re.findall(
        r'(?:extras_bodies\(m,|_recorded_ids\(m,|_recorded_line_keys\(m,)\s*"([^"]+)"', src)}
    read |= {h.lower() for h in re.findall(r'_EXCEPTIONS_HEADING\s*=\s*"([^"]+)"', src)}
    known = {h.lower() for h in KNOWN_HEADINGS}
    assert read <= known, f"read by a tool, refused by `coyodex record`: {sorted(read - known)}"


def test_assemble_merges_two_block_agents_stating_one_rule() -> None:
    """Following `_merge_duplicate_messaging`: two agents writing one thing is correct input, and
    blocking it made a live build hand-merge. `validate`'s check stands for the hand-edited map."""
    m = make_checkable_model()
    m.rules.append(BusinessRule(id="BR7", statement="Only the ORDER'S owner  may cancel it!",
                                sites=[RuleSite(where="src/guard.py:3", why="same line")]))
    m.extras = [ExtraSection(heading="Notes", body="see [[BR7]] for the admin case")]
    assert _merge_duplicate_rules(m) == 1
    assert [r.id for r in m.rules] == ["BR1"]
    assert m.extras[0].body == "see [[BR1]] for the admin case"


def test_assemble_keeps_the_same_statement_at_different_sites() -> None:
    m = make_checkable_model()
    m.rules.append(BusinessRule(id="BR7", statement="Only the order's owner may cancel it.",
                                sites=[RuleSite(where="src/guard.py:4", why="another guard")]))
    assert _merge_duplicate_rules(m) == 0


def test_assemble_never_merges_a_rule_with_no_anchored_site() -> None:
    """Two declared-absence rules are not evidence of anything — no site set, no safe identity."""
    m = make_checkable_model()
    m.rules = [BusinessRule(id="BR1", statement="Enforced by the type.",
                            sites=[RuleSite(no_call_site=True)]),
               BusinessRule(id="BR2", statement="Enforced by the type.",
                            sites=[RuleSite(no_call_site=True)])]
    assert _merge_duplicate_rules(m) == 0


# ═══ Phase 4 — the markdown view ══════════════════════════════════════════════════

def make_rendered_model() -> ProjectModel:
    m = make_checkable_model()
    m.components.append(Component(id="C2", name="Order store", purpose="p",
                                  files=["src/guard.py"]))
    m.rules.append(BusinessRule(id="BR2", statement="A cancelled order cannot be cancelled again.",
                                block="BLK1", sites=[
                                    RuleSite(where="src/guard.py:4", why="short-circuits a re-cancel"),
                                    RuleSite(why="the status enum forbids it", no_call_site=True)]))
    m.rules.append(BusinessRule(id="BR3", statement="Only an admin may refund.", access=True,
                                sites=[RuleSite(where="src/nobody.py:9", why="the admin gate")]))
    return m


def t7_section(m: ProjectModel) -> str:
    md = model_to_markdown(m)
    start = md.index("## T7")
    rest = md[start:]
    end = rest.index("\n---")
    return rest[:end]


def test_a_ruleless_map_renders_no_business_logic_section() -> None:
    """Guarded, so nothing churns on the three committed `.md` views."""
    assert "T7" not in model_to_markdown(make_base_model())


def test_all_three_committed_md_views_are_byte_identical() -> None:
    """There is no CI — nothing catches a forgotten regeneration but this."""
    for rel in (".coyodex/project-map", "tests/fixtures/mcpolis-project-map",
                "eval/fixtures/trapdoor/golden/project-map"):
        m = load_model((REPO / f"{rel}.json").read_text(encoding="utf-8"))
        assert (REPO / f"{rel}.md").read_text(encoding="utf-8") == model_to_markdown(m), rel


def test_the_preamble_and_generated_notice_are_untouched() -> None:
    """Touching either churns all three committed `.md` files at once."""
    md = model_to_markdown(make_rendered_model())
    assert md.index("## T7") > md.index("Behavioral layer first")
    assert "Generated with coyodex from `project-map.json`" in md


def test_a_site_renders_every_owner_of_a_shared_file() -> None:
    text = t7_section(make_rendered_model())
    assert "src/guard.py:3](src/guard.py:3) — Guard (C1), Order store (C2)" in text


def test_a_site_in_an_unclaimed_file_renders_as_unverified() -> None:
    assert "*unverified — no component claims this file*" in t7_section(make_rendered_model())


def test_a_declared_absence_site_says_so() -> None:
    assert "*no call site* — enforced by construction" in t7_section(make_rendered_model())


def test_a_site_link_is_labelled_by_its_line_not_its_basename() -> None:
    """A rule is routinely enforced at several lines of one file; a list of identical `guard.py`
    labels hides exactly what the site list exists to show."""
    text = t7_section(make_rendered_model())
    assert "[src/guard.py:3]" in text and "[src/guard.py:4]" in text


def test_rules_group_by_block_with_a_trailing_not_assigned_group() -> None:
    text = t7_section(make_rendered_model())
    assert text.index("### Order lifecycle *(BLK1)*") < text.index("### Not assigned to a block")
    assert text.index("**BR2") < text.index("### Not assigned to a block") < text.index("**BR3")


def test_a_map_with_no_blocks_renders_the_rules_flat() -> None:
    m = make_rendered_model()
    m.blocks = []
    m.rules[0].block = None
    text = t7_section(m)
    assert "###" not in text and "**BR1" in text


def test_the_enforced_at_line_is_derived_not_authored() -> None:
    text = t7_section(make_rendered_model())
    assert "- enforced at: View order (UC1) step 2" in text
    m = make_rendered_model()
    m.rules[0].sites = [RuleSite(where="src/guard.py:4", why="a different line")]
    assert "enforced at" not in t7_section(m).split("**BR2")[0]


def test_the_view_is_a_pure_function_of_the_json() -> None:
    """`_check_view_fresh` compares the committed `.md` to `model_to_markdown(m)`. Folding the
    optional pre-index symbol table in would make the view depend on a file the map does not
    contain, so the markdown shows EXACT step links only — the viewer, which has the table, adds
    the same-function ones."""
    m = make_rendered_model()
    assert model_to_markdown(m) == model_to_markdown(load_model(to_canonical_json(m)))


# --- reconciled after the phase-4 review -------------------------------------------

def make_subflow_rule_model() -> ProjectModel:
    """A rule enforced at a SUB-FLOW's step 2, while the use case has its own step 2 elsewhere."""
    m = make_checkable_model()
    m.subflows = [SubFlow(id="SF1", name="Owner check", steps=[
        FlowStep(n=2, src="C1", dst="E1", phrase="checks the owner", where="src/guard.py:4")])]
    m.flows[0].steps.append(FlowStep(n=3, src="C1", dst="C1", phrase="", subflow="SF1"))
    m.rules[0].sites = [RuleSite(where="src/guard.py:4", why="the owner check")]
    return m


def test_the_enforced_at_line_carries_the_authoring_container() -> None:
    """`n` is unique per container, never per use case: 47 of this repo's 114 anchored steps come
    from a sub-flow and 26 `(uc, n)` pairs name more than one step, so `(UC1) step 2` points at the
    wrong row in T6b — and two different steps render as a byte-identical duplicate."""
    text = t7_section(make_subflow_rule_model())
    assert "- enforced at: View order (UC1) → SF1 step 2" in text


def test_two_distinct_steps_sharing_a_number_render_distinctly() -> None:
    m = make_subflow_rule_model()
    m.flows[0].steps[1].where = "src/guard.py:4"          # UC1's OWN step 2, same anchor
    text = t7_section(m)
    assert "View order (UC1) step 2 · View order (UC1) → SF1 step 2" in text


def test_owners_of_a_shared_file_render_in_element_order() -> None:
    """`C10` sorted before `C2` as a string — the mistake `element_sort_key` exists to prevent."""
    m = make_checkable_model()
    m.components = [Component(id=f"C{i}", name=f"Part {i}", purpose="p", files=["src/guard.py"])
                    for i in (1, 2, 10)]
    assert site_components(m, m.rules[0].sites[0]) == ["C1", "C2", "C10"]


def test_a_contradictory_site_is_rendered_as_contradictory_not_as_a_clean_claim() -> None:
    """`validate` blocks it, but `coyodex render` never runs validate — showing one half and
    dropping the other turns a contradiction into a claim."""
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(where="src/guard.py:3", why="w", no_call_site=True)]
    text = t7_section(m)
    assert "[src/guard.py:3]" in text and "also declares `no_call_site` — contradictory" in text


def test_an_anchorless_site_does_not_render_an_empty_link() -> None:
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(where="", why="lost the anchor")]
    text = t7_section(m)
    assert "[]()" not in text and "*no anchor* — this site claims nothing" in text


def test_a_minted_block_with_no_rules_is_visible() -> None:
    """Blocks are minted at synthesis, BEFORE the rules are authored, so an empty one is a real
    state — and an invisible one reads as a block nobody minted."""
    m = make_checkable_model()
    m.blocks.append(Group(id="BLK2", name="Refunds", purpose="who may get money back"))
    text = t7_section(m)
    assert "### Refunds *(BLK2)*" in text and "*No rules assigned to this block yet.*" in text


def test_a_map_with_blocks_but_no_rules_still_renders_the_forest() -> None:
    m = make_base_model()
    m.blocks = [Group(id="BLK1", name="Order lifecycle", purpose="who may change an order")]
    assert "### Order lifecycle *(BLK1)*" in t7_section(m)


def test_an_authored_confidence_is_rendered_as_authored() -> None:
    m = make_checkable_model()
    m.rules[0].confidence = "inferred"
    assert "**BR1 — Only the order's owner may cancel it.**  *(inferred)*" in t7_section(m)


# ═══ Phase 5 — impact, grounding and the eval ═════════════════════════════════════

def test_every_site_is_its_own_anchor_ref_owned_by_the_rule() -> None:
    m = make_checkable_model()
    m.rules[0].sites.append(RuleSite(where="src/guard.py:4", why="a second line"))
    refs = [a for a in anchor_index(m) if a.kind == "rule_site"]
    assert [(a.eid, a.owner, a.lo) for a in refs] == [("rule:BR1:0", "BR1", 3),
                                                      ("rule:BR1:1", "BR1", 4)]


def test_a_declared_absence_site_indexes_no_anchor() -> None:
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(no_call_site=True, why="by construction")]
    assert not [a for a in anchor_index(m) if a.kind == "rule_site"]


def make_window_repo(td: str) -> Path:
    """One 60-line function, so a change 40 lines from the anchor is INSIDE the enclosing extent and
    well outside the ±3 call-site window."""
    root = Path(td)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "wide.py").write_text(
        "def wide():\n" + "".join(f"    x{i} = {i}\n" for i in range(1, 60)), encoding="utf-8")
    return root


def _resolution_rungs(m: ProjectModel, td: str, changed_line: int) -> dict[str, str]:
    """The direct-hit resolution rung per element, for a one-line edit to `src/wide.py`."""
    root = make_window_repo(td)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run(["git", *cmd], cwd=root, check=True, env=env, capture_output=True)
    m.commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, check=True,
                              capture_output=True, text=True).stdout.strip()
    lines = (root / "src" / "wide.py").read_text(encoding="utf-8").splitlines(keepends=True)
    lines[changed_line - 1] = "    CHANGED = 1\n"
    (root / "src" / "wide.py").write_text("".join(lines), encoding="utf-8")
    core = compute_impact(root, m, {"src/wide.py": [(1, 60, "wide", "function")]},
                          "HEAD", "WORKTREE")
    rank = {"line": 1, "symbol": 2, "file": 3}          # the STRONGEST rung per element: a
    best: dict[str, str] = {}                           # component carries several anchors, and a
    for h in core.hits:                                 # line-less `files` entry always says "file"
        if h.eid not in best or rank[h.resolution] < rank[best[h.eid]]:
            best[h.eid] = h.resolution
    return best


def test_a_site_and_a_security_source_take_the_tight_window_not_the_definition_span() -> None:
    """A call-site anchor names ONE acting line inside a definition, so the enclosing span is the
    wrong neighbourhood: a change 40 lines away would read as a symbol-rung hit on a line it never
    touched. `security` sat outside the window while claiming to be an enforcement point; a rule
    SITE is the same shape, and both are fixed together.

    The COMPONENT `source` on the same line is the control — it points at a definition, so the
    enclosing span IS its neighbourhood and it must still resolve at the symbol rung."""
    assert set(_CALL_SITE_KINDS) == {"edge", "flow_step", "security", "rule_site"}
    m = make_base_model()
    m.components = [Component(id="C1", name="Wide", purpose="p", source="src/wide.py:5",
                              files=["src/wide.py"])]
    m.security = [SecurityRow(surface="S", who="w", source="src/wide.py:5")]
    m.rules = [BusinessRule(id="BR1", statement="Only an owner may act.",
                            sites=[RuleSite(where="src/wide.py:5", why="the guard")])]
    m.flows, m.edges, m.entities = [], [], []
    with tempfile.TemporaryDirectory() as td:
        rungs = _resolution_rungs(m, td, 45)     # 40 lines away: inside `wide`, outside ±3
    assert rungs["security:S"] == "file", rungs
    assert rungs["rule:BR1:0"] == "file", rungs
    assert rungs["C1"] == "symbol", rungs        # the control: a definition anchor keeps its span


def test_a_changed_site_ripples_to_the_rule_its_components_and_its_use_cases() -> None:
    m = make_checkable_model()
    hit = DirectHit("rule:BR1:0", "rule_site", "src/guard.py", "modified", "line", "where",
                    owner="BR1")
    core = ImpactCore(pin="p" * 7, base="b" * 7, target="WORKTREE",
                      files=[ImpactFile(path="src/guard.py", p_path="src/guard.py", status="M",
                                        hits=[hit])])
    reached = set(build_impact_result(m, core, RippleOptions())["impacts"])
    assert {"BR1", "C1", "UC1"} <= reached, sorted(reached)


def test_a_changed_rule_ripples_up_its_block_forest() -> None:
    m = make_checkable_model()
    m.blocks.append(Group(id="BLK2", name="Refunds", parent="BLK1"))
    m.rules[0].block = "BLK2"
    hit = DirectHit("BR1", "rules", "src/guard.py", "modified", "line", "where")
    core = ImpactCore(pin="p" * 7, base="b" * 7, target="WORKTREE",
                      files=[ImpactFile(path="src/guard.py", p_path="src/guard.py", status="M",
                                        hits=[hit])])
    reached = set(build_impact_result(m, core, RippleOptions())["impacts"])
    assert {"BLK2", "BLK1"} <= reached, sorted(reached)


# --- grounding: N sites must not collapse into one verdict ------------------------

def test_each_site_is_its_own_l2_claim_because_the_anchor_is_in_the_claim_string() -> None:
    """`l2_worklist_model` de-duplicates by claim string. Without the anchor, a rule enforced at
    four lines collapses to ONE skeptic verdict — and that verdict then reads as covering all four."""
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(where="src/guard.py:3", why="the owner check"),
                        RuleSite(where="src/guard.py:4", why="the owner check"),
                        RuleSite(where="src/other.py:9", why="the owner check")]
    claims = [w.claim for w in l2_worklist_model(m) if w.theme == "rule"]
    assert len(claims) == 3 and len(set(claims)) == 3
    assert all(s in c for s, c in zip(("src/guard.py:3", "src/guard.py:4", "src/other.py:9"), claims))


def test_the_rule_theme_sits_second_and_the_order_is_pinned() -> None:
    """The theme tier IS the batch order a grounding run works in — `_THEMES` is most-dangerous
    first, and `test_themes_are_closed_and_match_the_worklist_order` pins declaration to emission."""
    assert _THEMES[:2] == ("security", "rule")


def test_a_claims_detail_names_the_components_of_ITS_SITE_not_the_rules_union() -> None:
    """The rule's union would label a site in a file nobody claims with its SIBLING sites'
    components — a component's home passed off as evidence — and would suppress the unverified
    signal exactly when a rule is PARTLY grounded. It would also disagree with the T7 view."""
    m = make_checkable_model()
    m.components.append(Component(id="C2", name="Billing", purpose="p", files=["src/bill.py"]))
    m.rules[0].sites = [RuleSite(where="src/guard.py:3", why="the owner check"),
                        RuleSite(where="src/bill.py:9", why="the billing side"),
                        RuleSite(where="src/nobody.py:1", why="an unclaimed file")]
    details = [w.detail for w in l2_worklist_model(m) if w.theme == "rule"]
    assert details == ["In: Guard (C1)", "In: Billing (C2)",
                       "In: no component claims this file — the site is UNVERIFIED."]


def test_the_grounding_detail_agrees_with_the_markdown_view() -> None:
    m = make_checkable_model()
    m.components.append(Component(id="C2", name="Billing", purpose="p", files=["src/guard.py"]))
    item = next(w for w in l2_worklist_model(m) if w.theme == "rule")
    assert item.detail == "In: Guard (C1), Billing (C2)"
    assert "Guard (C1), Billing (C2)" in t7_section(m)


def test_a_declared_absence_site_raises_no_claim() -> None:
    m = make_checkable_model()
    m.rules[0].sites = [RuleSite(no_call_site=True, why="by construction")]
    assert not [w for w in l2_worklist_model(m) if w.theme == "rule"]


def test_apply_drift_reaches_the_rule_site_writer_and_persists_it() -> None:
    """END TO END, through `fix.main` — the only path an operator uses. Asserting the writer works
    while calling it directly bypasses the dispatch, where the theme was WRITABLE but not
    claim-shaped: every correction came back as an unparseable EDGE claim and was dropped, verbatim
    the `cadence` failure that set is documented as having fixed. And the write gate hand-listed
    three counters, so once a fourth writer existed the correction applied in memory, printed, and
    was never persisted."""
    from coyodex import fix
    from coyodex.audit_model import rule_site_claim
    with tempfile.TemporaryDirectory() as td:
        make_rule_repo(td)
        m = make_checkable_model()
        map_path = Path(td) / "project-map.json"
        map_path.write_text(to_canonical_json(m), encoding="utf-8")
        verdicts = Path(td) / "verdicts.json"
        claim = rule_site_claim(m.rules[0].statement, "src/guard.py:3", "rejects a non-owner")
        verdicts.write_text(json.dumps({"grounding": [
            {"claim": claim, "grounded": True, "evidence": "src/guard.py:30"}]}), encoding="utf-8")
        assert fix.main(["apply-drift", "--map", str(map_path), "--verdicts", str(verdicts)]) == 0
        assert load_model(map_path.read_text(encoding="utf-8")).rules[0].sites[0].where \
            == "src/guard.py:30"


def test_a_skeptic_corrected_site_anchor_is_writable() -> None:
    from coyodex import fix
    from coyodex.audit_model import apply_anchor_corrections, rule_site_claim
    assert "rule" in fix._WRITABLE_THEMES
    m = make_checkable_model()
    claim = rule_site_claim(m.rules[0].statement, "src/guard.py:3", "rejects a non-owner")
    counts, _notes = apply_anchor_corrections(m, [(claim, "src/guard.py:7")])
    assert counts["rule_site"] == 1 and m.rules[0].sites[0].where == "src/guard.py:7"


def test_two_sites_matching_one_claim_are_refused_not_blind_written() -> None:
    m = make_checkable_model()
    from coyodex.audit_model import apply_anchor_corrections, rule_site_claim
    m.rules.append(BusinessRule(id="BR2", statement=m.rules[0].statement, sites=[
        RuleSite(where="src/guard.py:3", why="rejects a non-owner")]))
    claim = rule_site_claim(m.rules[0].statement, "src/guard.py:3", "rejects a non-owner")
    counts, notes = apply_anchor_corrections(m, [(claim, "src/guard.py:7")])
    assert counts["rule_site"] == 0 and any("matches 2 rule sites" in n for n in notes)


# ═══ Phase 6 — the authoring contract ═════════════════════════════════════════════
# The method is the only place an authoring agent reads. A contract stated in code and not in the
# method is a contract nobody follows; one stated in the method and not in code is prose.

MODEL_DOC = (REPO / "method" / "model.md").read_text(encoding="utf-8")


def t7_fanout_block() -> str:
    """The T7 fan-out bullet ALONE — from its own heading to the next list item. The contract has
    to be stated where the block agent reads it, not somewhere else in a 2000-line document."""
    text = (REPO / "method.md").read_text(encoding="utf-8")
    start = text.index("- **T7 Business logic (fan out")
    return text[start:text.index("\n- Test completeness", start)]


def test_the_fanout_states_the_five_load_bearing_authoring_rules() -> None:
    """Each is a measured failure mode, not a style note: the sharp test keeps mechanical
    conditionals out, "nothing unsupported" was the prototype's most frequent error, and "the step
    link is a readout, never a target" is what stops an author anchoring the line that lights up
    the UI instead of the line that acts."""
    low = t7_fanout_block().lower()
    for phrase in ("one rule = one decision",
                   "could a product person have decided otherwise",
                   "reconstructible from the lines its sites point at",
                   "the step link is a readout, never a target",
                   "fusion is preferred to splitting"):
        assert phrase in low, phrase


def test_the_fanout_says_the_derived_quantities_have_no_field() -> None:
    """The central claim has to reach the author, or the first thing they do is ask for a field."""
    assert ("everything else about a rule is derived and there is no field to write it in"
            in t7_fanout_block().lower())
    assert "no field for any of them" in MODEL_DOC.lower()


def test_the_fanout_specifies_the_fragment_the_way_the_trace_fanout_does() -> None:
    """The sub-flow fan-out learned this the expensive way — five live agents wrote `title` for
    `name` because the prompt described the shape instead of showing it. A nested `sites[]` is
    strictly more novel."""
    block = t7_fanout_block()
    assert "```json" in block and '"no_call_site"' in block      # the shape is SHOWN
    assert "BR1–19" in block                                     # its own id range
    assert "build-fragments" in block                            # where it writes
    assert "`method/model.md`" in block                          # where the semantics live


def test_the_fanout_names_access_as_an_authored_field() -> None:
    """`access` is the marker the eval's auth gate and the security fold both read. An agent told
    the field list is complete without it ships every rule `access: false`."""
    block = t7_fanout_block()
    assert '"access"' in block and "who may do what" in block.lower()


def test_the_exit_criterion_does_not_reward_anchoring_the_steps_line() -> None:
    """The criterion is "the worklist is empty", and a step's `where` is the CALLER's line while
    the decision lives in the callee — so requiring an anchor link would make it reachable only by
    a decoy site on the step's own line. The contract has to state the structural form."""
    block = t7_fanout_block().lower()
    assert re.sub(r"\s+", " ", block).count(
        "a rule is enforced in a component the step names") == 1
    assert "decoy" in block


def test_the_method_does_not_oversell_the_canary() -> None:
    low = t7_fanout_block().lower()
    assert "does not prove the sweep was exhaustive" in low


def test_the_method_routes_block_assignment_through_reconcile_after_the_fanout() -> None:
    """"At synthesis" is impossible: a `BRn` does not exist then, and a reconcile naming one fails
    the synthesis assemble with `unknown id`."""
    assert "`block` is NOT in the fragment" in t7_fanout_block()
    assert "assigned by the LEAD after the rule fan-out" in MODEL_DOC
    assert "at synthesis via `reconcile`" not in MODEL_DOC


def test_the_method_documents_both_new_prefixes_and_the_document_shape() -> None:
    assert "| `BR` | Business rule" in MODEL_DOC and "| `BLK` | Block" in MODEL_DOC
    assert '"blocks":' in MODEL_DOC and '"rules":' in MODEL_DOC


def test_a_rule_site_is_in_the_exhaustive_anchor_format_lists() -> None:
    """`method/model.md` and the harvest contract each carry an EXHAUSTIVE anchor list; an anchor
    missing from them is one an agent has no reason to write correctly."""
    contract = (REPO / "method" / "templates" / "harvest-contract.md").read_text(encoding="utf-8")
    assert "`rules[].sites[].where`" in MODEL_DOC and "`rules[].sites[].where`" in contract


def test_the_tier_number_t7_names_exactly_one_thing() -> None:
    """The method used T7 for a Level-2 drill tier while the map document runs T0 → T6b. Two
    different things called T7 in one document is confusion an agent pays for."""
    text = (REPO / "method.md").read_text(encoding="utf-8")
    assert "T7 Component internals" not in text
    assert "T8 Component internals · T9 Config/env vars · T10 Data schema." in text


def test_reconcile_can_actually_generate_the_block_assignment() -> None:
    """The method insists on the GENERATOR ("there is no hand-authoring threshold any more"), so a
    field it cannot emit is a documented dead end."""
    m = make_checkable_model()
    m.rules[0].block = None
    doc, _report = expand(m, [{"ids": ["BR1"], "block": "BLK1"}])
    assert doc == {"set": [{"ids": ["BR1"], "block": "BLK1"}]}
    rec = load_reconcile(json.dumps(doc), "generated")
    assert validate_reconcile(m, rec) == []


def test_reconcile_coverage_reports_rules_with_no_block() -> None:
    m = make_checkable_model()
    m.rules[0].block = None
    assert any("business rule(s) still have no block" in line
               for line in coverage_report(m, {"set": []}))


def test_lint_fragment_refuses_a_block_written_into_a_fragment() -> None:
    """The method says "never in the fragment". Without this the rule is prose: a fragment carrying
    `block` lints clean and assembles with the value intact."""
    m = make_checkable_model()
    assert any("carry `block` in a fragment" in p for p in lint_fragment_problems(m, None))
    m.rules[0].block = None
    assert not any("carry `block`" in p for p in lint_fragment_problems(m, None))


def test_a_block_of_single_site_rules_draws_a_granularity_advisory() -> None:
    """55 one-site rules pass every other check AND maximise the swept count the eval prints, so
    nothing else in the pipeline notices the layer degenerating into a flow-step list."""
    m = make_checkable_model()
    m.rules = [BusinessRule(id=f"BR{i}", statement=f"Decision {i}.", block="BLK1",
                            sites=[RuleSite(where=f"src/guard.py:{i}", why="w")])
               for i in range(1, 7)]
    assert any("nearly all single-site" in w for w in rule_warnings(m))
    m.rules[0].sites.append(RuleSite(where="src/guard.py:9", why="a second place"))
    m.rules[1].sites.append(RuleSite(where="src/guard.py:8", why="a second place"))
    assert not any("nearly all single-site" in w for w in rule_warnings(m))


def test_the_granularity_advisory_is_recordable() -> None:
    m = make_checkable_model()
    m.rules = [BusinessRule(id=f"BR{i}", statement=f"Decision {i}.", block="BLK1",
                            sites=[RuleSite(where=f"src/guard.py:{i}", why="w")])
               for i in range(1, 7)]
    m.extras = [ExtraSection(heading="Balance exceptions",
                             body="BLK1: each guard really is its own decision here")]
    assert not any("nearly all single-site" in w for w in rule_warnings(m))


# ═══ Phase 7 — the viewer ═════════════════════════════════════════════════════════
# The frontend cannot call Python, so the ONLY guard against a second derivation in JS is that the
# transport carries the answer and the JS never recomputes it. These tests hold both halves.

VIEWER = REPO / "tools" / "coyodex" / "viewer"
VIEWER_JS = (VIEWER / "viewer.js").read_text(encoding="utf-8")


def rules_view_of(m: ProjectModel) -> dict:
    """The T7 transport out of the graph. `GraphDict` types the value `object` (every payload in it
    is freeform JSON), so the cast belongs here once rather than at each read."""
    return cast(dict, model_to_graph(m)["rules_view"])


def make_viewer_model() -> ProjectModel:
    m = make_checkable_model()
    m.components.append(Component(id="C2", name="Billing", purpose="p", files=["src/guard.py"]))
    m.rules.append(BusinessRule(id="BR2", statement="A cancelled order cannot be cancelled again.",
                                block="BLK1", access=True, sites=[
                                    RuleSite(where="src/guard.py:4", why="short-circuits"),
                                    RuleSite(why="the status enum forbids it", no_call_site=True)]))
    m.rules.append(BusinessRule(id="BR3", statement="Only an admin may refund.",
                                sites=[RuleSite(where="src/nobody.py:9", why="the admin gate")]))
    return m


def test_the_viewer_payload_equals_the_python_helper() -> None:
    """The `capability_touch` precedent: the transport is the ONE derivation's output, not a
    parallel one. If these ever disagree, the tab is showing something the checks do not."""
    m = make_viewer_model()
    rv = rules_view_of(m)
    owners = component_file_owners(m)
    for r, out in zip(m.rules, rv["rules"]):
        assert out["id"] == r.id
        assert [[c["id"] for c in s["components"]] for s in out["sites"]] == [
            site_components(m, site, owners) if (site.where or "").strip() else []
            for site in r.sites]
        assert [(l["uc"], l["container"], l["n"], l["strength"]) for l in out["steps"]] == [
            (l.uc, l.container, l.n, l.strength) for l in rule_steps(m, r)]
        assert [e["id"] for e in out["entities"]] == rule_entities(m, r)
        assert out["swept"] == rules_swept(m)[r.id]


def test_a_shared_file_reaches_the_browser_with_every_owner() -> None:
    m = make_viewer_model()
    rv = rules_view_of(m)
    site = rv["rules"][0]["sites"][0]
    assert [c["id"] for c in site["components"]] == ["C1", "C2"]


def test_an_unverified_rule_is_stamped_in_the_transport() -> None:
    """A site nobody owns must arrive already marked — a rule that renders bare must not look like
    a rule nobody wrote."""
    rv = rules_view_of(make_viewer_model())
    by_id = {r["id"]: r for r in rv["rules"]}
    assert by_id["BR3"]["unverified"] is True
    assert by_id["BR2"]["unverified"] is False       # its second site is a DECLARED absence
    assert by_id["BR2"]["sites"][1]["declared"] is True


def test_the_two_inversions_key_the_way_the_panes_look_up() -> None:
    rv = rules_view_of(make_viewer_model())
    assert rv["byComponent"]["C1"] == ["BR1", "BR2"]
    assert rv["byComponent"]["C2"] == ["BR1", "BR2"]     # the shared file, both owners
    assert rv["byStep"]["UC1:UC1:2"] == ["BR1"]          # (uc, authoring container, n)


def test_blocks_and_rules_are_graph_nodes() -> None:
    """`test_convert_and_views` requires every defined element to be a node; without this the
    moment a fixture gains rules that test fails."""
    g = model_to_graph(make_viewer_model())
    assert g["nodes"]["BLK1"]["kind"] == "block" and g["nodes"]["BR1"]["kind"] == "rule"


def test_the_bundle_gates_the_tab_on_the_map_having_rules() -> None:
    from coyodex.viewer import gen_viewer
    assert gen_viewer.build_view_bundle(model_to_graph(make_viewer_model()), None,
                                        VIEWER)["hasBusinessRules"] is True
    assert gen_viewer.build_view_bundle(model_to_graph(make_base_model()), None,
                                        VIEWER)["hasBusinessRules"] is False


# --- the JS holds no second derivation --------------------------------------------

def _js_code(text: str) -> str:
    """`text` with line comments stripped — the same discipline `test_viewer_js`'s field-name check
    uses: prose ABOUT a field is not a use of it, and a rule that cannot tell them apart bans
    explaining the design."""
    out = []
    for line in text.splitlines():
        out.append("" if line.lstrip().startswith("//") else line.split("//", 1)[0])
    return "\n".join(out)


def _js_function(name: str) -> str:
    start = VIEWER_JS.index("function " + name + "(")
    return _js_code(VIEWER_JS[start:VIEWER_JS.index("\nfunction ", start + 10)])


def test_the_frontend_never_re_derives_an_owner_or_a_step_link() -> None:
    """The one guard that matters. The three rule-rendering functions may READ `components` /
    `steps` / `swept` off the payload; the moment one of them resolves an owner from a component's
    `files`, or matches a step by comparing anchors, it is a second implementation in a language
    the checks cannot see.

    SCOPE: a substring ban over four tokens, which one level of indirection defeats (`srcCell`
    parses an anchor to build a code LINK, which is not a derivation and is why it is not banned).
    It catches the direct rewrite, not a determined one."""
    for fn in ("renderRules", "decidesHtml", "stepRulesHtml"):
        body = _js_function(fn)
        # Reading a node to check its KIND is how every info-pane function guards; deriving an
        # OWNER from `files`, or a step link by parsing anchors, is the second implementation.
        for shape in (".files", "whereNode(", "parseStepEid(", "COMP_LOOKUP"):
            assert shape not in body, (fn, shape)
    # ...and it DOES read the server-computed answers.
    assert "site.components" in _js_function("renderRules")
    assert "r.swept" in _js_function("renderRules")
    assert "l.strength" in _js_function("renderRules")


def test_the_business_logic_tab_is_wired_at_every_registration_point() -> None:
    """A view that is registered in five of six places renders nothing, or renders and cannot be
    navigated back to. Each of these is one of the six."""
    html = (VIEWER / "viewer.html").read_text(encoding="utf-8")
    assert 'data-view="rules"' in html
    assert "HAS_RULES = !!b.hasBusinessRules" in VIEWER_JS               # applyBundle
    assert "'tests', 'rules'" in VIEWER_JS                              # TEXT_VIEWS
    assert "kind === 'rules'" in VIEWER_JS                              # topView
    assert "if (s.kind === 'rules') return 'Business logic'" in VIEWER_JS  # stateTitle
    assert "if (s.kind === 'rules') return [{ kind: 'rules' }]" in VIEWER_JS  # VIEW_Q trail
    assert "rules: 'What does this product DECIDE" in VIEWER_JS         # the view's question
    assert "if (s.kind === 'rules') { renderRules(s);" in VIEWER_JS     # render
    assert "b.dataset.view === 'rules' && !HAS_RULES" in VIEWER_JS      # the tab gate


def test_same_tab_navigation_carries_the_pane_keys() -> None:
    """`stateKey` and `pushContentPoint` are two hand-written lists of the same fields. A key in
    one and not the other is a navigation that silently no-ops, or a pane that silently resets."""
    key = VIEWER_JS[VIEWER_JS.index("function stateKey(s)"):VIEWER_JS.index("function snapContent")]
    push = VIEWER_JS[VIEWER_JS.index("function pushContentPoint"):VIEWER_JS.index("function go(state")]
    for field in ("store", "entity", "blk", "br"):
        assert f"s.{field}" in key, field
        assert f"{field}: c.{field}" in push, field


def test_the_flow_step_pane_uses_a_new_class_and_keys_by_container() -> None:
    start = VIEWER_JS.index("function flowStepInfoHtml(uc, i, numbered)")
    pane = VIEWER_JS[start:VIEWER_JS.index("\n// One actor's card", start)]
    assert "stepRulesHtml(uc, st)" in pane
    assert "(st.sf || uc)" in pane            # the AUTHORING container, not the use case
    assert 'class="brref"' in pane            # a new class name
    # The same four the viewer-js negative contract names, matched in their RENDERED form.
    for forbidden in ('class="flowpairref"', 'class="endpoints"', "ridesref", 'class="flowref"'):
        assert forbidden not in _js_code(pane), forbidden


def test_the_impact_summary_names_every_bucket_the_ripple_can_produce() -> None:
    """`showImpactSummary` iterates a closed list, so a bucket it cannot name is a row that
    vanishes while the direct/ripple counts still include it."""
    from coyodex.impact_ripple import _KIND_BY_PREFIX, _KIND_BY_SYNTH
    labels = VIEWER_JS[VIEWER_JS.index("const IMP_TYPE_LABEL = {"):]
    labels = labels[:labels.index("};")]
    missing = [k for k in set(_KIND_BY_PREFIX.values()) | set(_KIND_BY_SYNTH.values())
               if f"{k}:" not in labels]
    assert not missing, missing


def test_the_tab_renders_no_internal_field_name() -> None:
    """`no_call_site` is a model field; the reader sees "enforced by construction"."""
    start = VIEWER_JS.index("function renderRules(s)")
    body = VIEWER_JS[start:VIEWER_JS.index("\nfunction ", start + 10)]
    code = _js_code(body)
    for field in ("no_call_site", "rules_view", "byComponent"):
        assert "'" + field not in code and '"' + field not in code, field


# --- reconciled after the phase-7 review -------------------------------------------

def test_the_transport_takes_the_symbol_table_and_the_markdown_view_does_not() -> None:
    """The viewer's finer answer. `model_to_graph(m, extents)` is what makes "inside the same
    function as this step" reachable; the markdown view has no table and stays exact-only, so the
    two views are consistent about what each of them can know."""
    m = make_swept_model()
    m.flows[0].steps[1].src = "C2"                       # no structural coverage; the anchor decides
    m.rules[0].sites = [RuleSite(where="src/guard.py:8", why="3 lines from the step")]
    ext = {"src/guard.py": [(1, 10, "cancel_order", "function")]}
    assert [s["strength"] for s in rules_view_of(m)["rules"][0]["steps"]] == []
    with_ext = cast(dict, model_to_graph(m, ext)["rules_view"])
    assert [(s["uc"], s["n"], s["strength"]) for s in with_ext["rules"][0]["steps"]] \
        == [("UC1", 2, "symbol")]


def test_the_step_chip_carries_the_containers_name_never_its_id() -> None:
    """The viewer shows element NAMES. A sub-flow's `SFn` on screen is an internal id."""
    m = make_checkable_model()
    m.subflows = [SubFlow(id="SF1", name="Owner check", steps=[
        FlowStep(n=2, src="C1", dst="E1", phrase="checks", where="src/guard.py:3")])]
    m.flows[0].steps = [FlowStep(n=1, src="C1", dst="C1", phrase="runs it", subflow="SF1")]
    step = rules_view_of(m)["rules"][0]["steps"][0]
    assert step["container"] == "SF1" and step["containerName"] == "Owner check"
    assert "esc(l.containerName || l.container)" in VIEWER_JS


def test_a_block_is_never_a_files_primary_in_the_browser() -> None:
    """A node carrying a `file` joins `filetree.node_path_index`, where a non-group kind sorts
    FIRST. A block with a `source` then took over the file browser's selection for that file and
    landed the reader on the Dependencies tab instead of the component that owns it. A capability —
    the same never-drawn shape — passes None for exactly this reason."""
    from coyodex.viewer.filetree import node_path_index
    m = make_checkable_model()
    m.blocks[0].source = "src/guard.py:1"
    g = model_to_graph(m)
    assert g["nodes"]["BLK1"].get("file") in (None, "")
    # The primary is the COMPONENT that owns the file, as it was before blocks existed.
    assert node_path_index(g).get("src/guard.py", [])[0] == "C1"
    assert "BLK1" not in node_path_index(g).get("src/guard.py", [])


def test_a_search_hit_on_a_block_or_a_rule_lands_on_the_business_logic_tab() -> None:
    """Every graph node is indexed by the search, so a kind with no `selectTargetFor` case falls
    through to the default and dead-ends on Dependencies, showing nothing."""
    target = VIEWER_JS[VIEWER_JS.index("function selectTargetFor(id)"):
                       VIEWER_JS.index("function selectFromTree(nodeId)")]
    assert "case 'block':" in target and "kind: 'rules', blk: id" in target
    assert "case 'rule':" in target and "blk: n.parent || 'none', br: id" in target


def test_an_impact_row_for_a_rule_site_is_readable_and_clickable() -> None:
    """The synthetic id is `rule:BR1:0`; `impName` returned everything after the first colon, so
    the row read `BR1:0` — and clicking it matched no node and did nothing."""
    assert "function parseRuleSiteEid(id)" in VIEWER_JS
    goto = VIEWER_JS[VIEWER_JS.index("function gotoImpactEid(id)"):]
    assert "const rid = parseRuleSiteEid(id);" in goto[:600]


def test_the_pane_pill_and_the_search_badge_speak_the_readers_language() -> None:
    assert "block: 'decision area', rule: 'business rule'" in VIEWER_JS
    assert "KIND_LABEL = { dep: 'dependency', block: 'decision area', rule: 'business rule' }" \
        in VIEWER_JS


def test_the_rail_nests_child_blocks_under_their_parent() -> None:
    """`blocks[].parent` is in the payload and `validate` supports it, so a flat rail draws a child
    as its parent's sibling — and makes the field dead payload on a public contract."""
    body = _js_function("renderRules")
    assert "kids.set(b.parent || ''" in body and "walk(b.id, depth + 1, seen)" in body


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
