#!/usr/bin/env python3
"""`coyodex.features` — the feature-led derivation: what belongs to each feature, from the stored map.

The pin that matters most is the RULE JOIN. The obvious join (through the component holding the
site) reaches 92-98% of rules on live maps and names a single feature for 10-28% of them, because a
component is shared. The join here goes through the enclosing FUNCTION: half the rules, but a single
clean answer four times out of five. These tests hold that choice in place, and hold the honesty
flags that say what did NOT join.

Run either way: `python3 tests/test_features.py` or `pytest tests/test_features.py`.
"""
from __future__ import annotations

import json
from pathlib import Path

from coyodex.features import as_bundle, build_index
from coyodex.model import FORMAT, load_model


# --- builders -------------------------------------------------------------------

def make_map(*, capability_on_uc: str | None = "CAP1", rules: list[dict] | None = None,
             files_c1: list[str] | None = None, files_c2: list[str] | None = None,
             steps: list[dict] | None = None, subflows: list[dict] | None = None,
             entry_points: list[str] | None = None) -> dict:
    """One feature, one use case, two components, one entity — the smallest map that can join."""
    return {
        "format": FORMAT, "title": "T", "goal": "G",
        "roles": [{"id": "R1", "name": "User", "kind": "human", "audience": "user",
                   "wants": "x", "drives": "UC1"},
                  {"id": "R2", "name": "Admin", "kind": "human", "audience": "user",
                   "wants": "y", "drives": "UC1"}],
        "capabilities": [{"id": "CAP1", "name": "Billing", "purpose": "takes the money",
                          "happy_path": "expected"}],
        "use_cases": [{"id": "UC1", "name": "Pay", "actors": ["R1", "R2"],
                       "capability": capability_on_uc,
                       "entry_points": entry_points if entry_points is not None else ["EP1"]}],
        "happy_path": [{"id": "HP1", "title": "Pay", "uc": "UC1"}],
        "entry_points": [{"id": "EP1", "kind": "http-route", "trigger": "POST /pay",
                          "source": "src/a.py:1", "component": "C1"},
                         {"id": "EP2", "kind": "cli", "trigger": "pay",
                          "source": "src/b.py:1", "component": "C2"}],
        "components": [
            {"id": "C1", "name": "Front", "purpose": "takes the ask", "entry_point": "src/a.py:1",
             "files": files_c1 if files_c1 is not None else ["src/a.py"]},
            {"id": "C2", "name": "Back", "purpose": "answers it", "entry_point": "src/b.py:1",
             "files": files_c2 if files_c2 is not None else ["src/b.py"]},
            {"id": "C3", "name": "Lonely", "purpose": "nothing reaches it",
             "entry_point": "src/c.py:1", "files": ["src/c.py"]}],
        "entities": [{"id": "E1", "name": "Payment", "meaning": "money moved",
                      "source": "src/a.py:1"}],
        "edges": [{"src": "C1", "verb": "calls", "dst": "C2", "why": "to answer",
                   "where": "src/a.py:12"}],
        "flows": [{"uc": "UC1", "title": "Pay", "steps": steps if steps is not None else [
            {"n": 1, "src": "R1", "dst": "C1", "phrase": "asks"},
            {"n": 2, "src": "C1", "dst": "C2", "phrase": "forwards", "where": "src/a.py:12"},
            {"n": 3, "src": "C2", "dst": "E1", "phrase": "records", "where": "src/b.py:22"},
            {"n": 4, "src": "C1", "dst": "R1", "phrase": "answers"}]}],
        "subflows": subflows or [],
        "blocks": [{"id": "BLK1", "name": "Money"}],
        "rules": rules if rules is not None else [
            {"id": "BR1", "name": "Card required", "statement": "A payment needs a card.",
             "block": "BLK1", "confidence": "verified",
             "sites": [{"where": "src/a.py:14", "why": "refuses without one"}]}],
    }


#: The pre-index symbol table, as `impact_git.load_map_extents` returns it. One function spans lines
#: 10-20 of a.py, another 30-40. Step 2 (a.py:12) and rule BR1 (a.py:14) both land in the first, so
#: they join by SYMBOL; anything outside it does not.
EXTENTS = {
    "src/a.py": [(10, 20, "pay", "function"), (30, 40, "refund", "function")],
    "src/b.py": [(20, 30, "record", "function")]}


def feature(ix, fid: str = "CAP1"):
    hits = [f for f in ix.features if f.id == fid]
    assert len(hits) == 1, f"expected one feature {fid}"
    return hits[0]


def index_of(doc: dict, extents: dict | None = EXTENTS):
    return build_index(load_model(json.dumps(doc)), extents)


# --- what a feature gathers ------------------------------------------------------

def test_a_feature_gathers_the_roles_use_cases_and_ways_in_of_its_use_cases():
    f = feature(index_of(make_map()))
    assert (f.roles, f.use_cases, f.entry_points) == (["R1", "R2"], ["UC1"], ["EP1"])
    assert (f.name, f.purpose) == ("Billing", "takes the money")


def test_a_feature_carries_its_derived_audience_and_not_its_walk_expectation():
    """`audience` is derived and drawn; `happy_path` is authored and NOT drawn — it is an authoring
    decision the Coverage rule reads, and a reader of the map has no use for it, so no view carries
    it and the bundle does not ship it."""
    ix = index_of(make_map())
    assert feature(ix).audience == ["user"]
    features = as_bundle(ix)["features"]
    assert isinstance(features, list)
    bundled = features[0]
    assert bundled["audience"] == ["user"]
    assert "happyPath" not in bundled and not hasattr(feature(ix), "happy_path")


def test_a_feature_gathers_the_components_and_entities_its_flow_touches():
    f = feature(index_of(make_map()))
    assert f.components == ["C1", "C2"]      # C3 is on no flow
    assert f.entities == ["E1"]


def test_content_inside_a_sub_flow_belongs_to_the_feature_that_calls_it():
    """Sub-flows are shared machinery referenced by a step. Without expanding them a feature's real
    work is invisible exactly where several features share it."""
    doc = make_map(
        steps=[{"n": 1, "src": "R1", "dst": "C1", "phrase": "asks"},
               {"n": 2, "src": "C1", "dst": "C2", "phrase": "", "subflow": "SF1"}],
        subflows=[{"id": "SF1", "title": "store it",
                   "steps": [{"n": 1, "src": "C2", "dst": "E1", "phrase": "records",
                              "where": "src/b.py:22"}]}])
    assert feature(index_of(doc)).entities == ["E1"]


def test_a_use_case_with_no_feature_is_reported_rather_than_dropped():
    ix = index_of(make_map(capability_on_uc=None))
    assert ix.unassigned_use_cases == ["UC1"]
    assert ix.coverage.use_cases_without_feature == 1
    assert feature(ix).use_cases == []


# --- the rule join ---------------------------------------------------------------

def test_a_rule_enforced_in_the_same_function_as_a_step_joins_to_that_feature():
    ix = index_of(make_map())
    assert feature(ix).rules == ["BR1"]
    assert ix.rule_features == {"BR1": ["CAP1"]}
    assert ix.coverage.rules_joined == 1 and ix.coverage.rules_unjoined == 0


def test_a_rule_in_another_function_of_the_same_file_does_not_join():
    """THE choice this module exists for. `src/a.py:34` is in `refund`, and no step of this feature
    goes there. Joining it anyway is the component-level join, which on live maps reached 92-98% of
    rules and named a single feature for 10-28% of them."""
    doc = make_map(rules=[{"id": "BR1", "name": "Card required",
                           "statement": "A payment needs a card.", "block": "BLK1",
                           "sites": [{"where": "src/a.py:34", "why": "in the refund path"}]}])
    ix = index_of(doc)
    assert feature(ix).rules == []
    assert (ix.coverage.rules_joined, ix.coverage.rules_unjoined) == (0, 1)


def test_an_unjoined_rule_is_counted_so_a_feature_page_cannot_imply_it_has_them_all():
    """A page showing only the joined rules would say a feature decides two things when it decides
    three. The count is what lets it say so."""
    doc = make_map(rules=[
        {"id": "BR1", "name": "In", "statement": "A payment needs a card.", "block": "BLK1",
         "sites": [{"where": "src/a.py:14", "why": "here"}]},
        {"id": "BR2", "name": "Out", "statement": "A refund needs a reason.", "block": "BLK1",
         "sites": [{"where": "src/a.py:34", "why": "elsewhere"}]}])
    ix = index_of(doc)
    assert feature(ix).rules == ["BR1"]
    assert (ix.coverage.rules_joined, ix.coverage.rules_unjoined) == (1, 1)


def test_without_the_preindex_only_an_exact_line_match_links_a_rule():
    """The degradation is `rule_steps`' own, not a second silence: with no symbol table a site links
    to a step only when they name the SAME line. On the three live maps that is the difference
    between 43 rules joined and 13, so a page that does not say which it is reports a floor as an
    answer."""
    ix = index_of(make_map(), extents=None)       # site a.py:14, step a.py:12 — same function only
    assert ix.rule_join_uses_extents is False
    assert feature(ix).rules == []
    assert ix.coverage.rules_unjoined == 1


def test_an_exact_line_match_still_links_without_the_preindex():
    doc = make_map(rules=[{"id": "BR1", "name": "Card required",
                           "statement": "A payment needs a card.", "block": "BLK1",
                           "sites": [{"where": "src/a.py:12", "why": "on the step's own line"}]}])
    ix = index_of(doc, extents=None)
    assert feature(ix).rules == ["BR1"] and ix.rule_join_uses_extents is False


def test_a_map_with_no_features_cannot_join_and_reports_no_gap():
    """coyodex's own map records no capabilities. Reporting its 14 rules as unjoined would read as a
    defect rather than as the pre-feature shape the map has."""
    doc = make_map()
    doc["capabilities"] = []
    doc["use_cases"][0]["capability"] = None
    ix = index_of(doc)
    assert ix.features == []
    assert (ix.coverage.rules_joined, ix.coverage.rules_unjoined) == (0, 0)


# --- coverage --------------------------------------------------------------------

def test_coverage_names_the_components_no_feature_and_no_rule_reaches():
    c = index_of(make_map()).coverage
    assert c.components_total == 3
    assert c.components_in_a_flow == 2 and c.components_in_a_rule == 1
    assert c.components_unreached == ["C3"]


def test_every_owner_of_a_shared_file_counts_as_enforcing_the_rule():
    """`components[].files` is not disjoint: on coyodex's own map 5 files are claimed by 2-5
    components each. Crediting the first owner silently would under-count where a decision lives."""
    c = index_of(make_map(files_c1=["src/a.py"], files_c2=["src/a.py", "src/b.py"])).coverage
    assert c.components_in_a_rule == 2      # BR1's site is in a.py, which C1 and C2 both claim


def test_coverage_counts_the_ways_in_that_no_use_case_names():
    c = index_of(make_map()).coverage
    assert c.entry_points_total == 2 and c.entry_points_named == 1     # EP2 is named by nobody


# --- the inverse views -----------------------------------------------------------

def test_a_component_knows_which_features_it_serves():
    ix = index_of(make_map())
    assert ix.component_features == {"C1": ["CAP1"], "C2": ["CAP1"]}
    assert "C3" not in ix.component_features


def test_the_role_grid_counts_use_cases_per_role_per_feature():
    ix = index_of(make_map())
    assert ix.role_features == {"R1": {"CAP1": 1}, "R2": {"CAP1": 1}}


def test_ids_come_back_in_id_order_not_string_order():
    """`C9` before `C10`. A rendered list sorted as strings reads as shuffled."""
    doc = make_map()
    doc["components"] += [{"id": f"C{i}", "name": f"N{i}", "purpose": "p",
                           "entry_point": "src/a.py:1", "files": []} for i in (9, 10)]
    doc["flows"][0]["steps"] += [
        {"n": 5, "src": "C1", "dst": "C10", "phrase": "then", "where": "src/a.py:15"},
        {"n": 6, "src": "C1", "dst": "C9", "phrase": "then", "where": "src/a.py:16"}]
    assert feature(index_of(doc)).components == ["C1", "C2", "C9", "C10"]


# --- the story (the tripartite Features diagram's data) ----------------------------

def make_story_map() -> dict:
    """Two on-path features touched out of authoring order, one excluded, one authored but never
    walked; three roles, the third driving nothing on the walk. The smallest map where every
    derived order can come out wrong."""
    doc = make_map()
    doc["roles"] += [{"id": "R3", "name": "Auditor", "kind": "human", "audience": "internal",
                      "wants": "z", "drives": "UC4"}]
    doc["capabilities"] = [
        {"id": "CAP1", "name": "Billing", "purpose": "takes the money", "happy_path": "expected"},
        {"id": "CAP2", "name": "Signup", "purpose": "opens the account", "happy_path": "expected"},
        {"id": "CAP3", "name": "Marketing", "purpose": "draws people in", "happy_path": "excluded"},
        {"id": "CAP4", "name": "Cleanup", "purpose": "sweeps up", "happy_path": "expected"}]
    doc["use_cases"] = [
        {"id": "UC1", "name": "Pay", "actors": ["R1", "R2"], "capability": "CAP1",
         "entry_points": []},
        {"id": "UC2", "name": "Sign up", "actors": ["R1"], "capability": "CAP2",
         "entry_points": []},
        {"id": "UC3", "name": "Read the ADS page", "actors": ["R1"], "capability": "CAP3",
         "entry_points": []},
        {"id": "UC4", "name": "Audit the books", "actors": ["R3"], "capability": "CAP1",
         "entry_points": []},
        {"id": "UC5", "name": "Refund", "actors": ["R2"], "capability": "CAP1",
         "entry_points": []}]
    # The walk touches Signup FIRST, then Billing twice — Billing must appear once, at its first.
    doc["happy_path"] = [{"id": "HP1", "title": "Open the account", "uc": "UC2"},
                         {"id": "HP2", "title": "Pay", "uc": "UC1"},
                         {"id": "HP3", "title": "Refund", "uc": "UC5"}]
    doc["flows"] = []
    doc["rules"] = []
    return doc


def story_of(doc: dict):
    return index_of(doc).story


def test_the_spine_orders_on_path_features_by_first_touch_once_each():
    st = story_of(make_story_map())
    assert st.spine == ["CAP2", "CAP1"]        # Signup first (HP1); Billing once, at HP2 not HP3


def test_features_the_walk_never_touches_go_off_the_story():
    """`excluded` features and an `expected` one no step reaches both sit off the walk — the
    diagram draws what the walk DOES, and the unreached-but-expected gap is validate's finding."""
    assert story_of(make_story_map()).off == ["CAP3", "CAP4"]


def test_the_cast_orders_actors_by_first_driven_step_then_map_order():
    st = story_of(make_story_map())
    assert st.cast == ["R1", "R2", "R3"]       # R1 drives HP1, R2 HP2; R3 drives no step -> last


def test_edges_are_distinct_actor_feature_pairs_with_the_pairs_first_step():
    st = story_of(make_story_map())
    by = {(e.actor, e.feature): e for e in st.edges}
    assert set(by) == {("R1", "CAP1"), ("R1", "CAP2"), ("R1", "CAP3"),
                       ("R2", "CAP1"), ("R3", "CAP1")}
    assert by[("R2", "CAP1")].step == "HP2"    # UC1 at HP2, not UC5 at HP3
    assert by[("R1", "CAP3")].step is None     # the walk never exercises the pair
    assert by[("R3", "CAP1")].step is None     # UC4 is on no step


def test_a_fallback_label_is_the_pairs_first_use_case_as_a_verb_phrase():
    st = story_of(make_story_map())
    by = {(e.actor, e.feature): e for e in st.edges}
    assert by[("R1", "CAP1")].label == "pay" and by[("R1", "CAP1")].authored is False
    assert by[("R1", "CAP2")].label == "sign up"
    assert by[("R2", "CAP1")].label == "pay"   # first use case of the PAIR, in map order


def test_a_fallback_label_keeps_a_leading_acronym():
    doc = make_story_map()
    doc["use_cases"][2]["name"] = "ADS reading"
    st = story_of(doc)
    by = {(e.actor, e.feature): e for e in st.edges}
    assert by[("R1", "CAP3")].label == "ADS reading"


def test_an_authored_stake_wins_over_the_fallback():
    doc = make_story_map()
    doc["capabilities"][0]["stakes"] = [{"actor": "R2", "stake": "settles and refunds"}]
    st = story_of(doc)
    by = {(e.actor, e.feature): e for e in st.edges}
    assert by[("R2", "CAP1")].label == "settles and refunds"
    assert by[("R2", "CAP1")].authored is True
    assert by[("R1", "CAP1")].label == "pay"   # the OTHER actor still falls back


def test_a_map_with_no_walk_has_no_spine_and_everything_off():
    """The viewer draws no diagram then (its guard reads the empty spine); the classification must
    still be coherent rather than crash."""
    doc = make_story_map()
    doc["happy_path"] = []
    st = story_of(doc)
    assert st.spine == [] and st.off == ["CAP1", "CAP2", "CAP3", "CAP4"]
    assert st.cast == ["R1", "R2", "R3"]                    # map order, nobody appears first


def test_a_walk_step_naming_a_missing_use_case_is_skipped_not_fatal():
    """A dangling `uc` is validate's finding; the derivation must not crash on it or let it shift
    the orders."""
    doc = make_story_map()
    doc["happy_path"].insert(0, {"id": "HP9", "title": "Ghost", "uc": "UC99"})
    st = story_of(doc)
    assert st.spine == ["CAP2", "CAP1"] and st.cast == ["R1", "R2", "R3"]


def test_the_story_ships_in_the_bundle():
    b = as_bundle(index_of(make_story_map()))
    st = b["story"]
    assert isinstance(st, dict)
    assert sorted(st) == ["cast", "column", "edges", "off", "spine"]
    assert st["spine"] == ["CAP2", "CAP1"]
    assert st["column"] == ["CAP2", "CAP1", "CAP3", "CAP4"]
    e = next(x for x in st["edges"] if (x["actor"], x["feature"]) == ("R2", "CAP1"))
    assert (e["label"], e["authored"], e["step"]) == ("pay", False, "HP2")


# --- the one story column: off-walk features interleave at an anchor or the fallback -------------

def test_the_column_is_the_spine_with_off_features_at_the_derived_fallback():
    """No anchors authored: Marketing's only actor (R1) last drives HP2, whose feature is Billing,
    so Marketing reads after Billing; Cleanup has no use cases, so no actors, so it falls to the
    end. The spine's own order never moves."""
    st = story_of(make_story_map())
    assert st.column == ["CAP2", "CAP1", "CAP3", "CAP4"]


def test_an_authored_before_anchor_beats_the_fallback():
    """The lead-in case the anchor exists for: a marketing feature belongs BEFORE the first step,
    and the fallback (the actor's last step) puts it after."""
    doc = make_story_map()
    doc["capabilities"][2]["story"] = {"place": "before", "feature": "CAP2"}
    assert story_of(doc).column == ["CAP3", "CAP2", "CAP1", "CAP4"]


def test_an_authored_after_anchor_places_beside_the_named_feature():
    doc = make_story_map()
    doc["capabilities"][3]["story"] = {"place": "after", "feature": "CAP2"}
    assert story_of(doc).column == ["CAP2", "CAP4", "CAP1", "CAP3"]


def test_an_anchor_may_name_another_off_feature_and_a_cycle_falls_back():
    doc = make_story_map()
    # CAP4 hangs off CAP3, which hangs off the spine: both resolve, in chain order.
    doc["capabilities"][2]["story"] = {"place": "before", "feature": "CAP2"}
    doc["capabilities"][3]["story"] = {"place": "after", "feature": "CAP3"}
    assert story_of(doc).column == ["CAP3", "CAP4", "CAP2", "CAP1"]
    # A cycle cannot fully resolve, and it never recurses: the member reached first with the cycle
    # closed behind it (Cleanup, whose anchor IS the cycle) takes its non-anchor placement (the
    # end), and the other's anchor then holds against that — "Marketing after Cleanup" survives.
    doc["capabilities"][2]["story"] = {"place": "after", "feature": "CAP4"}
    assert story_of(doc).column == ["CAP2", "CAP1", "CAP4", "CAP3"]


def test_a_dangling_or_self_anchor_is_ignored_by_the_derivation():
    """Resolution must not crash on what validate flags; the feature simply keeps its fallback."""
    doc = make_story_map()
    doc["capabilities"][2]["story"] = {"place": "after", "feature": "CAP99"}
    doc["capabilities"][3]["story"] = {"place": "before", "feature": "CAP4"}
    assert story_of(doc).column == ["CAP2", "CAP1", "CAP3", "CAP4"]


def test_two_features_anchored_to_the_same_spot_keep_map_order():
    doc = make_story_map()
    doc["capabilities"][2]["story"] = {"place": "after", "feature": "CAP1"}
    doc["capabilities"][3]["story"] = {"place": "after", "feature": "CAP1"}
    assert story_of(doc).column == ["CAP2", "CAP1", "CAP3", "CAP4"]


def test_a_map_with_no_walk_columns_in_map_order():
    doc = make_story_map()
    doc["happy_path"] = []
    assert story_of(doc).column == ["CAP1", "CAP2", "CAP3", "CAP4"]


# --- the view bundle ---------------------------------------------------------------

def test_the_view_bundle_carries_the_feature_block_in_the_viewers_vocabulary():
    """The frontend reads `applyBundle` keys, so a rename here is a silent blank screen there. This
    pins the shape, and that the whole bundle still serialises."""
    from coyodex.viewer.gen_viewer import build_view_bundle
    from coyodex.views import model_to_graph
    m = load_model(json.dumps(make_map()))
    b = build_view_bundle(model_to_graph(m, EXTENTS), None, Path("."), model=m, extents=EXTENTS)
    f = b["features"]
    assert sorted(f) == ["componentFeatures", "coverage", "features", "roleFeatures",
                         "ruleFeatures", "ruleJoinUsesExtents", "story", "unassignedUseCases"]
    assert f["features"][0]["useCases"] == ["UC1"]        # camelCase, not use_cases
    assert f["coverage"]["componentsUnreached"] == ["C3"]
    json.dumps(b)                                          # the bundle is served as JSON


def test_a_bundle_built_without_a_readable_map_still_renders_the_rest():
    """`build_view_bundle` runs per request. A map folder it cannot read must cost the feature block,
    never the whole view."""
    from coyodex.viewer.gen_viewer import build_view_bundle
    from coyodex.views import model_to_graph
    m = load_model(json.dumps(make_map()))
    b = build_view_bundle(model_to_graph(m, EXTENTS), None, Path("/nonexistent-map-dir"))
    assert b["features"] == {} and b["graph"]


if __name__ == "__main__":     # pragma: no cover
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
