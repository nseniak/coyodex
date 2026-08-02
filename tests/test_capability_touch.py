#!/usr/bin/env python3
"""Tests for the capability touch primitive (plan/60-capabilities Step 2).

ONE implementation feeds the completeness checks, the viewer transport and the eval profile, so it
is tested once, here, against the committed mcpolis fixture — the same map the design was measured
on. Freezing those numbers is the point: the design's first two revisions each quoted a figure that
turned out to be wrong (a per-USE-CASE histogram reported as per-CAPABILITY, and a per-use-case span
of "7-9 components across 4-5 subsystems" that is really 6-10 across 2-6), and nothing in the repo
would have caught either.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_capability_touch.py
    pytest tests/test_capability_touch.py
"""
from __future__ import annotations

import collections
from pathlib import Path

from coyodex import validate_model as vm
from coyodex.model import (
    Flow,
    FlowStep,
    Group,
    HappyStep,
    ProjectModel,
    SubFlow,
    UseCase,
    load_model,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mcpolis-project-map.json"


def load_fixture() -> ProjectModel:
    return load_model(FIXTURE.read_text(encoding="utf-8"))


def root_subsystem(m: ProjectModel, sid: str | None) -> str | None:
    """A subsystem's top-level ancestor — the altitude the Subsystems overview draws."""
    subs = {s.id: s for s in m.subsystems}
    seen: set[str] = set()
    while sid and sid in subs and subs[sid].parent and sid not in seen:
        seen.add(sid)
        sid = subs[sid].parent
    return sid


def make_subflow_model() -> ProjectModel:
    """Two use cases in two capabilities whose flows BOTH ride one shared sub-flow.

    The fixture has zero sub-flows, so expansion is untestable there — and it is exactly the case
    that would silently under-count: without expansion, C9 is touched by nobody and both
    capabilities look smaller than they are."""
    m = ProjectModel(title="T", goal="g")
    m.capabilities = [Group(id="CAP1", name="Ordering", label="core"),
                      Group(id="CAP2", name="Billing", label="core")]
    m.use_cases = [UseCase(id="UC1", name="Order", capability="CAP1"),
                   UseCase(id="UC2", name="Bill", capability="CAP2")]
    m.subflows = [SubFlow(id="SF1", name="Auth dance",
                          steps=[FlowStep(n=1, src="C9", dst="C8", phrase="verifies")])]
    m.flows = [
        Flow(uc="UC1", title="Order", steps=[
            FlowStep(n=1, src="C1", dst="C2", phrase="places"),
            FlowStep(n=2, src="C2", dst="C2", phrase="runs auth", subflow="SF1")]),
        Flow(uc="UC2", title="Bill", steps=[
            FlowStep(n=1, src="C3", dst="C2", phrase="charges"),
            FlowStep(n=2, src="C3", dst="C3", phrase="runs auth", subflow="SF1")]),
    ]
    return m


# --- the fixture numbers the design was measured on ------------------------------------------

def test_every_fixture_use_case_has_a_capability() -> None:
    m = load_fixture()
    assert len(m.capabilities) == 7
    unassigned = [u.id for u in m.use_cases if not (u.capability or "").strip()]
    assert not unassigned, unassigned
    known = {c.id for c in m.capabilities}
    assert all(u.capability in known for u in m.use_cases)


def test_traced_use_cases_and_their_span() -> None:
    """15 of 25 traced; each traced flow touches 6-10 components across 2-6 top-level subsystems.

    The span matters because it is what the always-dim overlay highlights: a single use case lights
    a small, readable part of the architecture, which is why the finest selection grain reads best."""
    m = load_fixture()
    by_uc = vm.flow_endpoint_ids_by_uc(m)
    assert len(by_uc) == 15
    assert len(m.use_cases) == 25
    comps = {c.id: c for c in m.components}
    spans = []
    for ends in by_uc.values():
        cs = {e for e in ends if e in comps}
        roots = {root_subsystem(m, comps[c].subsystem) for c in cs if comps[c].subsystem}
        spans.append((len(cs), len(roots)))
    assert min(s[0] for s in spans) == 6 and max(s[0] for s in spans) == 10, spans
    assert min(s[1] for s in spans) == 2 and max(s[1] for s in spans) == 6, spans


def test_happy_path_union_is_near_saturated() -> None:
    """The spine's union covers 51 components across 10 of 12 top-level subsystems — so its value
    as a selection is inverted: what it shows is the two subsystems the main walk never reaches."""
    m = load_fixture()
    by_uc = vm.flow_endpoint_ids_by_uc(m)
    union: set[str] = set()
    for step in m.happy_path:
        if step.uc:
            union |= by_uc.get(step.uc, set())
    comps = {c.id: c for c in m.components}
    hit = {e for e in union if e in comps}
    roots = {root_subsystem(m, comps[c].subsystem) for c in hit if comps[c].subsystem}
    tops = [s for s in m.subsystems if not s.parent]
    assert len(hit) == 51, len(hit)
    assert (len(roots), len(tops)) == (10, 12)


def test_an_untraced_capability_keeps_an_empty_element_set() -> None:
    """Secrets & variables has three use cases and none is traced. The empty set must SURVIVE —
    it is the signal that a real part of the product was never traced, and dropping the key would
    make the capability indistinguishable from one that does not exist."""
    m = load_fixture()
    els = vm.capability_elements(m)
    assert set(els) == {c.id for c in m.capabilities}
    empty = [cap for cap, ends in els.items() if not ends]
    assert empty == ["CAP5"], empty


def test_spread_never_reaches_nearly_all_capabilities() -> None:
    """The measurement that killed the derived product/platform split, frozen so it cannot be
    quietly re-assumed: the maximum spread is 4 capabilities of 7. Nothing is touched by "nearly
    all", so no threshold separates machinery from product on this map."""
    m = load_fixture()
    spread = collections.Counter(len(caps) for caps in vm.element_capabilities(m).values())
    assert max(spread) == 4, dict(spread)
    assert len(m.capabilities) == 7


def test_element_capabilities_is_the_inverse_of_capability_elements() -> None:
    m = load_fixture()
    fwd, inv = vm.capability_elements(m), vm.element_capabilities(m)
    for cap, ends in fwd.items():
        for eid in ends:
            assert cap in inv[eid], (cap, eid)
    for eid, caps in inv.items():
        for cap in caps:
            assert eid in fwd[cap], (cap, eid)


def test_the_primitive_covers_more_than_components() -> None:
    """Scope check. An earlier revision restricted this to components, citing "0 of 35 entities are
    flow endpoints" on this fixture — a number that measures the fixture's own missing entity steps
    (validate fires its no-entity-in-any-flow canary here), not a structural fact. The helper takes
    whatever the flows touch; the fixture happens to be component-heavy, and that is a property of
    the map, not a rule."""
    m = load_fixture()
    touched = vm.flow_endpoint_ids(m)
    assert touched, "the fixture has traced flows"
    assert touched == {e for ends in vm.flow_endpoint_ids_by_uc(m).values() for e in ends}


# --- sub-flow expansion (untestable on the fixture: it has none) -------------------------------

def test_shared_subflow_steps_count_for_every_riding_capability() -> None:
    """Machinery extracted into an `SFn` is touched by every flow that rides it. Without expansion
    C9 would belong to no capability at all — the exact under-count a shared auth dance produces."""
    m = make_subflow_model()
    els = vm.capability_elements(m)
    assert "C9" in els["CAP1"] and "C9" in els["CAP2"]
    assert vm.element_capabilities(m)["C9"] == {"CAP1", "CAP2"}
    assert vm.element_capabilities(m)["C1"] == {"CAP1"}       # not shared: only UC1 touches it


def test_a_use_case_with_no_capability_contributes_to_none() -> None:
    """Unassigned is not a silent default. Its elements belong to no capability, so they show up as
    untouched — visible as a gap rather than folded into whichever capability came first."""
    m = make_subflow_model()
    m.use_cases[1].capability = None
    els = vm.capability_elements(m)
    assert els["CAP2"] == set()
    assert "C3" not in vm.element_capabilities(m)             # UC2's own step, now orphaned


def test_a_capability_naming_no_use_cases_is_empty_not_missing() -> None:
    m = make_subflow_model()
    m.capabilities.append(Group(id="CAP3", name="Unused", label="platform"))
    assert vm.capability_elements(m)["CAP3"] == set()


# --- completeness counts: the numbers that replace a wall of advisories -------------------------

def test_completeness_counts_on_the_fixture() -> None:
    """Frozen because every one of these was quoted wrongly at least once during the design.

    `off_spine_in_core_capabilities` is the deliberate give-up made visible: moving the spine check
    to capability altitude means six real use cases — "Remove a team member", "Edit or remove an
    upstream" among them — no longer warn. Counting them is what keeps that a trade rather than a
    silent loss."""
    from coyodex import validate_model as v
    c = v.completeness_counts(load_fixture())
    assert c["use_cases"] == 25 and c["use_cases_traced"] == 15 and c["use_cases_untraced"] == 10
    assert c["capabilities"] == 7 and c["capabilities_untraced"] == 1
    assert c["off_spine_in_core_capabilities"] == 6


# --- the viewer transport (Step 6a): the frontend cannot call Python -----------------------------

def test_graph_carries_the_overlay_data() -> None:
    """`capability_touch`, `capability_lives` and `completeness` ride in the graph because
    `viewer.js` cannot call the Python helper — and a second implementation in JS is exactly the
    drift this repo pays for elsewhere."""
    from coyodex.views import model_to_graph
    m = load_fixture()
    g = model_to_graph(m)
    assert g["capability_touch"] and g["capability_lives"] and g["completeness"]
    # the touch map is the helper's inverse, verbatim
    assert {k: set(v) for k, v in g["capability_touch"].items()} == vm.element_capabilities(m)
    assert g["completeness"] == vm.completeness_counts(m)


def test_where_it_lives_ranks_top_level_subsystems() -> None:
    """Rolled up to the TOP level — the altitude the Subsystems overview draws and the altitude the
    question is asked at. Ranked by how much of each subsystem the capability reaches."""
    from coyodex.views import model_to_graph
    lives = model_to_graph(load_fixture())["capability_lives"]
    gw = lives["CAP4"]                                     # Tool access via gateway
    assert [r["touched"] for r in gw] == sorted((r["touched"] for r in gw), reverse=True)
    by_name = {r["name"]: r for r in gw}
    assert by_name["Gateway (MCP protocol surface)"]["touched"] == 5
    assert by_name["Gateway (MCP protocol surface)"]["total"] == 9
    assert lives["CAP5"] == []                              # untraced capability lives nowhere


def test_use_case_nodes_carry_their_capability_as_parent() -> None:
    """Membership rides the EXISTING parent channel, exactly as a component's parent is its
    subsystem — so grouping by capability needs no second lookup table beside the nodes."""
    from coyodex.views import model_to_graph
    g = model_to_graph(load_fixture())
    assert g["nodes"]["UC1"]["parent"] == "CAP1"
    assert g["nodes"]["CAP1"]["kind"] == "capability"


# --- nested capabilities: a forest, like subsystems and subdomains ------------------------------

def make_nested_model() -> ProjectModel:
    """A parent capability holding NO use case directly — everything lives in its child."""
    m = ProjectModel(title="T", goal="g")
    m.capabilities = [Group(id="CAP1", name="Commerce", label="core"),
                      Group(id="CAP2", name="Ordering", parent="CAP1", label="core")]
    m.use_cases = [UseCase(id="UC1", name="Place order", capability="CAP2")]
    m.flows = [Flow(uc="UC1", title="Order",
                    steps=[FlowStep(n=1, src="C1", dst="C2", phrase="places")])]
    return m


def test_a_parent_capability_inherits_its_childrens_elements() -> None:
    """Reading direct membership only made a parent look empty — its overlay lit nothing and it
    counted as 'untraced', which is the one signal reserved for a part of the product nobody walked."""
    m = make_nested_model()
    els = vm.capability_elements(m)
    assert els["CAP1"] == {"C1", "C2"} == els["CAP2"]
    assert vm.completeness_counts(m)["capabilities_untraced"] == 0


def test_a_parent_capability_is_reached_when_a_child_walks_the_spine() -> None:
    m = make_nested_model()
    m.happy_path = [HappyStep(id="HP1", title="Order", uc="UC1")]
    assert not vm._spine_membership_warnings(m, {"UC1"}, set())


def test_a_cycle_in_the_capability_forest_does_not_hang() -> None:
    """A cycle is validate's problem, not the primitive's — but it must terminate regardless."""
    m = make_nested_model()
    m.capabilities[0].parent = "CAP2"          # CAP1 -> CAP2 -> CAP1
    assert vm.capability_members(m)["CAP1"] == {"UC1"}


def test_the_standalone_runner_is_the_last_block_in_this_file() -> None:
    """The module docstring advertises `python3 tests/test_capability_touch.py`, and that runner
    must see the whole file. It once sat MID-file and, calling `sys.exit()`, never even DEFINED the
    seven tests below it: 10 of 17 ran and it printed "ok". Nothing caught that, because under
    pytest all 17 run.

    Asserted statically rather than by running the file — a subprocess self-check would re-enter
    this same test and recurse forever (it did)."""
    src = Path(__file__).read_text(encoding="utf-8")
    guard = src.index('if __name__ == "__main__":')
    assert "\ndef test_" not in src[guard:], "a test is defined AFTER the runner — it will be skipped"


if __name__ == "__main__":
    # MUST stay at the END of the file. It sat mid-file once, and since it calls sys.exit(),
    # every test defined below it was never even defined under the standalone runner: it ran
    # 10 of 17 and printed "ok". The count is printed now so a silent shortfall is visible.
    import sys
    tests = sorted((n, f) for n, f in globals().items()
                   if n.startswith("test_") and callable(f))
    fails = 0
    for name, fn in tests:
        try:
            fn()
        except AssertionError as e:                       # pragma: no cover - stdlib runner
            fails += 1
            print(f"FAIL {name}: {e}")
    print(f"FAILED ({fails} of {len(tests)})" if fails else f"ok ({len(tests)} tests)")
    sys.exit(1 if fails else 0)
