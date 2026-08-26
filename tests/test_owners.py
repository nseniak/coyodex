#!/usr/bin/env python3
"""`owners` — which FEATURE a data area exists for — and the derived touches that cross-examine it.

The design's whole point is that the authored answer and the derived evidence are DIFFERENT
questions, so the tests come in pairs: one holding what the checks say, and one MUTATION holding
what they must NOT say. The mutations are the load-bearing half — every derivation of ownership was
tried on three live maps and each looked plausible while being wrong, so a check that fires on
"the owner is not the first feature to touch the area" would re-import exactly that mistake.

Run either way: `python3 tests/test_owners.py` or `pytest tests/test_owners.py`.
"""
from __future__ import annotations

from coyodex.areas import build_areas
from coyodex.model import (
    Entity,
    ExtraSection,
    Flow,
    FlowStep,
    Group,
    ProjectModel,
    Role,
    Store,
    UseCase,
    entity_owners,
    load_model,
    subdomain_owners,
    to_canonical_json,
)
from coyodex.validate_model import validate_model


# --- builders -------------------------------------------------------------------

def make_saved(eid: str, name: str, subdomain: str, mode: str = "collection") -> Entity:
    return Entity(id=eid, name=name, subdomain=subdomain, source=f"src/{eid.lower()}.py:1",
                  meaning="a saved thing", store=Store(dep="D1", container=name.lower(), mode=mode))


def make_map() -> ProjectModel:
    """Two features, two data areas, and walks that reach both — the smallest map that can be
    cross-examined. CAP1's walk writes the Pages area and reads one Snapshot record; CAP2's walk
    lives in the Snapshots area. Deliberately shaped like the argus case the design was measured
    on: the snapshot is FIRST touched by the tracking feature, and exists for the change one."""
    m = ProjectModel(title="Demo", goal="A demo.")
    m.roles = [Role(id="R1", name="Owner", kind="human", audience="user", wants="pages",
                    drives="UC1")]
    m.capabilities = [Group(id="CAP1", name="Page tracking", purpose="follows a page",
                            happy_path="expected"),
                      Group(id="CAP2", name="Change detection", purpose="says what moved",
                            happy_path="expected")]
    m.subdomains = [Group(id="SD1", name="Tracked pages", purpose="what is watched"),
                    Group(id="SD2", name="Snapshots and change", purpose="what it looked like")]
    m.use_cases = [UseCase(id="UC1", name="Track a page", actors=["R1"], capability="CAP1"),
                   UseCase(id="UC2", name="Diff a page", actors=["R1"], capability="CAP2")]
    m.entities = [make_saved("E1", "Page", "SD1"),
                  make_saved("E2", "Snapshot", "SD2"),
                  make_saved("E3", "Change", "SD2"),
                  Entity(id="E4", name="FetchRequest", subdomain="SD1", meaning="a call shape",
                         source="src/req.py:1", store=Store(mode="transient"))]
    m.flows = [
        Flow(uc="UC1", title="Track a page", steps=[
            FlowStep(n=1, src="R1", dst="E1", phrase="names the page"),
            FlowStep(n=2, src="E1", dst="E2", phrase="takes the first snapshot"),
            FlowStep(n=3, src="E1", dst="E4", phrase="builds the call")]),
        Flow(uc="UC2", title="Diff a page", steps=[
            FlowStep(n=1, src="R1", dst="E2", phrase="asks what moved"),
            FlowStep(n=2, src="E2", dst="E3", phrase="records the change")]),
    ]
    return m


def area(m: ProjectModel, sid: str):
    return next(a for a in build_areas(m) if a.id == sid)


def problems_of(m: ProjectModel) -> list[str]:
    return validate_model(m)[0]


def warnings_of(m: ProjectModel) -> list[str]:
    return validate_model(m)[1]


def owner_warnings(m: ProjectModel) -> list[str]:
    return [w for w in warnings_of(m)
            if "`owners`" in w or "listed as shared" in w or "names owner(s)" in w]


# --- the derived half: what a feature TOUCHES ------------------------------------

def test_only_saved_records_make_an_area() -> None:
    # E4 is a call shape (`transient`), so it is not a record anyone can own — and SD1 is an area
    # only because of E1. A sub-domain of pure plumbing draws no box and gets asked no question.
    a = area(make_map(), "SD1")
    assert a.entities == ["E1"], a.entities


def test_touches_count_sides_and_name_the_records() -> None:
    m = make_map()
    snapshots = area(m, "SD2")
    counts = {t.feature: t.touches for t in snapshots.touched_by}
    # CAP1 touches E2 once (step 2's dst); CAP2 touches E2 twice and E3 once.
    assert counts == {"CAP2": 3, "CAP1": 1}, counts
    assert next(t for t in snapshots.touched_by if t.feature == "CAP2").entities == ["E2", "E3"]


def test_areas_order_follows_the_owning_features_story_position() -> None:
    m = make_map()
    m.subdomains[0].owners = ["CAP2"]        # Tracked pages authored to the LATER feature
    m.subdomains[1].owners = ["CAP1"]
    assert [a.id for a in build_areas(m, ["CAP1", "CAP2"])] == ["SD2", "SD1"]


def test_a_shared_area_sorts_after_the_owned_ones() -> None:
    m = make_map()
    m.subdomains[1].owners = ["CAP1", "CAP2"]
    m.subdomains[0].owners = ["CAP2"]
    assert [a.id for a in build_areas(m, ["CAP1", "CAP2"])] == ["SD1", "SD2"]


# --- inheritance ----------------------------------------------------------------

def test_an_entity_inherits_its_areas_owner() -> None:
    m = make_map()
    m.subdomains[1].owners = ["CAP2"]
    assert entity_owners(m)["E2"] == ["CAP2"]


def test_an_entity_override_beats_the_area() -> None:
    m = make_map()
    m.subdomains[1].owners = ["CAP2"]
    m.entities[1].owners = ["CAP1"]          # the AuditEntry case: written by another feature
    assert entity_owners(m)["E2"] == ["CAP1"]
    assert entity_owners(m)["E3"] == ["CAP2"]


def test_a_child_area_inherits_from_its_parent() -> None:
    m = make_map()
    m.subdomains[0].owners = ["CAP1"]
    m.subdomains[1].parent = "SD1"
    assert subdomain_owners(m)["SD2"] == ["CAP1"]
    assert area(m, "SD2").owners == ["CAP1"]


def test_nobody_decided_is_absent_not_empty() -> None:
    m = make_map()
    assert subdomain_owners(m) == {}
    assert entity_owners(m) == {}


# --- shape errors ---------------------------------------------------------------

def test_owners_on_the_wrong_forest_is_blocking() -> None:
    m = make_map()
    m.capabilities[0].owners = ["CAP2"]
    m.subsystems = [Group(id="S1", name="Gateway", purpose="fronts", owners=["CAP1"])]
    said = [p for p in problems_of(m) if "owners" in p]
    assert any("CAP1 carries `owners`" in p and "capability" in p for p in said), said
    assert any("S1 carries `owners`" in p and "subsystem" in p for p in said), said


def test_an_owner_that_is_not_a_capability_is_blocking() -> None:
    m = make_map()
    m.subdomains[0].owners = ["E1"]
    assert any("SD1 lists owner 'E1'" in p for p in problems_of(m))


def test_the_same_feature_listed_twice_is_blocking() -> None:
    m = make_map()
    m.subdomains[0].owners = ["CAP1", "CAP1"]
    assert any("SD1 lists owner 'CAP1' twice" in p for p in problems_of(m))


def test_an_empty_list_is_blocking_because_absent_already_means_undecided() -> None:
    m = make_map()
    m.subdomains[0].owners = []
    assert any("SD1 has an empty `owners` list" in p for p in problems_of(m))


def test_an_entity_override_is_policed_the_same_way() -> None:
    m = make_map()
    m.entities[1].owners = ["CAP9"]
    assert any("E2 lists owner 'CAP9'" in p for p in problems_of(m))


def test_a_good_map_has_no_owner_problem() -> None:
    m = make_map()
    m.subdomains[0].owners = ["CAP1"]
    m.subdomains[1].owners = ["CAP2"]
    assert [p for p in problems_of(m) if "owner" in p] == []


# --- the advisories, each with the mutation that must stay quiet -----------------

def test_missing_asks_for_a_decision_on_every_area_holding_records() -> None:
    said = owner_warnings(make_map())
    assert any("SD1 (Tracked pages)" in w and "no `owners`" in w for w in said), said
    assert any("SD2 (Snapshots and change)" in w and "no `owners`" in w for w in said), said


def test_missing_goes_quiet_once_the_decision_is_authored() -> None:
    m = make_map()
    m.subdomains[0].owners = ["CAP1"]
    m.subdomains[1].owners = ["CAP2"]
    assert [w for w in owner_warnings(m) if "no `owners`" in w] == []


def test_an_owner_the_walks_never_reach_is_reported_as_ungrounded() -> None:
    m = make_map()
    m.subdomains[0].owners = ["CAP2"]        # CAP2's walk never touches E1
    m.subdomains[1].owners = ["CAP2"]
    said = [w for w in owner_warnings(m) if "touch none of its saved records" in w]
    assert any("SD1 (Tracked pages)" in w and "CAP2 (Change detection)" in w for w in said), said


def test_an_owner_that_is_not_the_first_toucher_is_deliberately_not_reported() -> None:
    # THE mutation this design exists for. CAP1's walk touches the snapshot FIRST and CAP1 makes a
    # third of the touches, yet the area exists for CAP2. Reporting that disagreement would be the
    # derivation the measurements ruled out; the check must stay silent.
    m = make_map()
    m.subdomains[0].owners = ["CAP1"]
    m.subdomains[1].owners = ["CAP2"]
    assert owner_warnings(m) == []


def test_a_shared_area_whose_records_partition_cleanly_is_reported() -> None:
    m = make_map()
    m.subdomains[0].owners = ["CAP1"]
    # CAP1 reaches only E2, CAP2 only E3 — two areas glued together.
    m.flows[1].steps = [FlowStep(n=1, src="R1", dst="E3", phrase="asks what moved")]
    m.subdomains[1].owners = ["CAP1", "CAP2"]
    said = [w for w in owner_warnings(m) if "partition cleanly" in w]
    assert any("SD2 (Snapshots and change)" in w for w in said), said


def test_a_genuinely_shared_record_keeps_split_quiet() -> None:
    # Both listed owners reach E2. A record several features write is what sharing LOOKS like, and
    # it is what keeps a shared core (mcpolis's organization row, written by 7 features) quiet.
    m = make_map()
    m.subdomains[0].owners = ["CAP1"]
    m.subdomains[1].owners = ["CAP1", "CAP2"]
    m.flows[0].steps.append(FlowStep(n=4, src="E1", dst="E3", phrase="notes the change"))
    assert [w for w in owner_warnings(m) if "partition cleanly" in w] == []


def test_one_listed_owner_holding_nearly_every_touch_is_reported() -> None:
    m = make_map()
    m.subdomains[0].owners = ["CAP1"]
    # CAP2 reaches the area once, CAP1 nine times: a list that is nearly a formality.
    m.flows[0].steps += [FlowStep(n=i, src="E1", dst="E2", phrase="snapshots again")
                         for i in range(4, 13)]
    m.flows[1].steps = [FlowStep(n=1, src="R1", dst="E3", phrase="asks what moved")]
    m.subdomains[1].owners = ["CAP1", "CAP2"]
    said = [w for w in owner_warnings(m) if "consider a single owner" in w]
    assert any("SD2 (Snapshots and change)" in w and "Page tracking" in w for w in said), said


def test_an_even_share_keeps_dominance_quiet() -> None:
    m = make_map()
    m.subdomains[0].owners = ["CAP1"]
    m.subdomains[1].owners = ["CAP1", "CAP2"]
    assert [w for w in owner_warnings(m) if "consider a single owner" in w] == []


def test_an_override_repeating_the_area_is_reported_as_redundant() -> None:
    m = make_map()
    m.subdomains[0].owners = ["CAP1"]
    m.subdomains[1].owners = ["CAP2"]
    m.entities[1].owners = ["CAP2"]
    assert any("E2 (Snapshot) overrides `owners`" in w for w in owner_warnings(m))


def test_an_override_that_differs_stays_quiet() -> None:
    m = make_map()
    m.subdomains[0].owners = ["CAP1"]
    m.subdomains[1].owners = ["CAP2"]
    m.entities[1].owners = ["CAP1"]
    assert [w for w in owner_warnings(m) if "overrides `owners`" in w] == []


def test_a_recorded_line_silences_the_advisory() -> None:
    m = make_map()
    m.subdomains[1].owners = ["CAP2"]
    m.extras = [ExtraSection(heading="Ownership exceptions",
                             body="SD1: the pages are a shared reference table, not a feature's.")]
    said = owner_warnings(m)
    assert [w for w in said if w.startswith("SD1 ")] == [], said


# --- the map still loads --------------------------------------------------------

def test_owners_round_trips_through_the_loader() -> None:
    m = make_map()
    m.subdomains[0].owners = ["CAP1"]
    m.entities[1].owners = ["CAP1"]
    back = load_model(to_canonical_json(m))
    assert back.subdomains[0].owners == ["CAP1"]
    assert back.entities[1].owners == ["CAP1"]
    assert back.subdomains[1].owners is None      # absent stays absent, never coerced to []


def test_a_map_written_before_the_field_existed_still_loads() -> None:
    m = load_model(to_canonical_json(make_map()))
    assert all(g.owners is None for g in m.subdomains)
    assert all(e.owners is None for e in m.entities)


if __name__ == "__main__":
    import sys
    mod = sys.modules[__name__]
    for _name in [n for n in dir(mod) if n.startswith("test_")]:
        getattr(mod, _name)()
        print("ok", _name)
