#!/usr/bin/env python3
"""Tests for the MapProfile's business-logic fields (T7 — the decision layer).

Kept here rather than in `tests/`, so the eval's assertions ride `pytest eval/tests` like every
other eval assertion — the core suite must not need `eval/tools` on its path.

Stdlib-only — no pytest required. Run either way (needs an editable install: `make deps`):
    python3 eval/tests/test_profile_rules.py
    pytest eval/tests/test_profile_rules.py
"""
from __future__ import annotations

from pathlib import Path

from coyodex.model import (
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
    SecurityRow,
    Store,
    UseCase,
    load_model,
)
from coyodex_eval.compare import DEFAULT_BANDS
from coyodex_eval.profile import MapProfile, build_profile_from_model

REPO = Path(__file__).resolve().parents[2]


# --- builders -------------------------------------------------------------------

def make_base_model() -> ProjectModel:
    """A minimal map that validates clean, with NO rules — the un-adopted baseline."""
    m = ProjectModel(title="Demo", goal="A demo.")
    m.roles = [Role(id="R1", name="Andy", kind="human", wants="orders", drives="UC1")]
    m.use_cases = [UseCase(id="UC1", name="Cancel", actors=["R1"])]
    m.happy_path = [HappyStep(id="HP1", title="Cancel", uc="UC1")]
    m.components = [Component(id="C1", name="Guard", purpose="p", source="src/guard.py:1",
                              files=["src/guard.py"])]
    m.deps = [Dep(id="D1", name="Postgres", kind="datastore", type="SQL database")]
    m.entities = [Entity(id="E1", name="Order", store=Store(notes="orders"), meaning="a thing",
                         source="src/guard.py:1",
                         fields=[EntityField(name="id", type="str", markers=["PK"])])]
    m.flows = [Flow(uc="UC1", title="Cancel", steps=[
        FlowStep(n=1, src="R1", dst="C1", phrase="asks to cancel"),
        FlowStep(n=2, src="C1", dst="E1", phrase="rejects a non-owner", where="src/guard.py:3"),
        FlowStep(n=3, src="C1", dst="E1", phrase="only an admin may override",
                 where="src/guard.py:4")])]
    m.edges = [Edge(src="C1", verb="reads", dst="E1", why="show", where="src/guard.py:3"),
               Edge(src="C1", verb="uses", dst="D1", why="query", where="src/guard.py:4")]
    return m


def make_ruled_model() -> ProjectModel:
    m = make_base_model()
    m.blocks = [Group(id="BLK1", name="Order lifecycle", purpose="who may change an order")]
    m.rules = [BusinessRule(id="BR1", statement="Only the order's owner may cancel it.",
                            block="BLK1",
                            sites=[RuleSite(where="src/guard.py:3", why="rejects a non-owner")])]
    return m


# --- the auth-surface inversion --------------------------------------------------

def test_the_auth_surface_union_is_a_no_op_on_every_committed_map() -> None:
    """`auth_surfaces_must_not_drop` is a hard gate with NO tolerance, and phase 8 empties
    `security[]` into rules. Inverting it a phase early is only safe if it changes nothing today."""
    for rel in (".coyodex/project-map", "tests/fixtures/mcpolis-project-map",
                "eval/fixtures/trapdoor/golden/project-map"):
        m = load_model((REPO / f"{rel}.json").read_text(encoding="utf-8"))
        p = build_profile_from_model(m)
        assert p.auth_surfaces == [s.surface for s in m.security if s.surface.strip()], rel


def test_an_access_rule_joins_the_auth_surface_set() -> None:
    m = make_ruled_model()
    m.rules[0].access = True
    assert build_profile_from_model(m).auth_surfaces == ["Only the order's owner may cancel it."]
    m.rules[0].access = False
    assert build_profile_from_model(m).auth_surfaces == []


def test_two_access_rules_stating_one_thing_count_once() -> None:
    """`security_surfaces = len(auth_surfaces)` feeds a hard gate with no tolerance, so one
    duplicate masks one genuinely dropped surface."""
    m = make_ruled_model()
    m.rules[0].access = True
    m.rules.append(BusinessRule(id="BR2", statement="Only the order's owner may cancel it.",
                                access=True, block="BLK1",
                                sites=[RuleSite(where="src/guard.py:4", why="a second guard")]))
    assert build_profile_from_model(m).security_surfaces == 1


def test_a_rule_repeating_a_security_row_counts_once() -> None:
    m = make_ruled_model()
    m.rules[0].access = True
    m.security = [SecurityRow(surface="Only the order's owner may cancel it.", who="owner",
                              source="src/guard.py:3")]
    assert build_profile_from_model(m).security_surfaces == 1


# --- the five derived fields -----------------------------------------------------

def test_the_profile_carries_the_five_derived_rule_fields() -> None:
    m = make_ruled_model()
    p = build_profile_from_model(m)
    assert (p.rules, p.blocks, p.rule_sites) == (1, 1, 1)
    # step 3 ("only an admin may override") is an unclaimed decision inside BR1's component
    assert p.rules_swept == 0 and p.rules_unverified == 0
    m.rules.append(BusinessRule(id="BR2", statement="Only an admin may override a cancel.",
                                block="BLK1",
                                sites=[RuleSite(where="src/guard.py:4", why="the admin gate")]))
    p = build_profile_from_model(m)
    assert (p.rules, p.rule_sites, p.rules_swept) == (2, 2, 2)


def test_the_fields_are_none_on_a_map_that_has_not_adopted_the_layer() -> None:
    """None, not 0: an un-adopted map must stay distinguishable from one whose sweep found
    nothing, and a profile written before the fields existed must still load."""
    p = build_profile_from_model(make_base_model())
    assert (p.rules, p.blocks, p.rule_sites, p.rules_swept, p.rules_unverified) == (
        None, None, None, None, None)
    assert MapProfile.from_json(p.to_json()).rules is None


def test_a_declared_absence_is_not_counted_as_a_grounded_site() -> None:
    m = make_ruled_model()
    m.rules[0].sites.append(RuleSite(why="enforced by the type", no_call_site=True))
    assert build_profile_from_model(m).rule_sites == 1


def test_one_unresolved_site_makes_a_rule_unverified() -> None:
    """Counting only rules where EVERY site fails under-reports the partly-grounded rule, which is
    the interesting one — and disagrees with what the T7 view stamps per site."""
    m = make_ruled_model()
    m.rules[0].sites.append(RuleSite(where="src/nobody.py:9", why="an unclaimed file"))
    assert build_profile_from_model(m).rules_unverified == 1


def test_l2_claims_stays_unbanded_even_though_rule_sites_inflate_it() -> None:
    assert "l2_claims_pct" not in DEFAULT_BANDS and "l2_claims_shrink_pct" not in DEFAULT_BANDS
    assert (build_profile_from_model(make_ruled_model()).l2_claims
            > build_profile_from_model(make_base_model()).l2_claims)


def test_the_rule_fields_are_report_only_by_default() -> None:
    """Adoption-dependent metrics carry no DEFAULT band — one would emit a "skipped, not numeric on
    both sides" note on every comparison of every map without the layer. Same as `capabilities`."""
    for metric in ("rules", "blocks", "rule_sites", "rules_swept", "rules_unverified"):
        assert f"{metric}_pct" not in DEFAULT_BANDS and f"{metric}_shrink_pct" not in DEFAULT_BANDS


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
