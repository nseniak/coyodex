#!/usr/bin/env python3
"""Tests for `coyodex.validate_model` — the semantic checks over a model, including the
v2-only behaviors: the deployment_linked orphan-dep exemption, the non_entity_types under-harvest
marker, and the generated-view freshness check.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_validate_model.py
    pytest tests/test_validate_model.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from coyodex import grammar
from coyodex.model import (
    Component,
    DeploymentRow,
    Dep,
    Edge,
    Entity,
    EntityField,
    EntityRelation,
    EntryPoint,
    EvidenceItem,
    Flow,
    FlowStep,
    GlossaryRow,
    HappyStep,
    Group,
    ExtraSection,
    NonEntityType,
    ProjectModel,
    Role,
    SecurityRow,
    SubFlow,
    UseCase,
    to_canonical_json,
)
from coyodex.validate_model import (
    _anchor_pairs,
    check_anchor_existence_model,
    check_domain_coverage_model,
    check_domain_relations,
    validate_model,
)
from coyodex.views import model_to_markdown


# --- builders -------------------------------------------------------------------

def make_entity(eid: str = "E1", name: str = "Order", source: str | None = "src/order.py:1",
                relations: list[EntityRelation] | None = None) -> Entity:
    return Entity(id=eid, name=name, store="orders", meaning="a thing", source=source,
                  fields=[EntityField(name="id", type="str", markers=["PK"])],
                  relations=relations or [])


def make_valid_model() -> ProjectModel:
    m = ProjectModel(title="Demo", goal="A demo.")
    m.roles = [Role(id="R1", name="Andy", kind="human", wants="orders", drives="UC1")]
    m.use_cases = [UseCase(id="UC1", name="View order", actors=["R1"])]
    m.happy_path = [HappyStep(id="HP1", title="View", uc="UC1")]
    m.components = [Component(id="C1", name="Viewer", purpose="shows",
                              entry_point="src/v.py:1")]
    m.deps = [Dep(id="D1", name="Postgres", kind="datastore", type="SQL database")]
    m.entities = [make_entity()]
    m.flows = [Flow(uc="UC1", title="View order",
                    steps=[FlowStep(n=1, src="R1", dst="C1", phrase="opens")])]
    m.edges = [Edge(src="C1", verb="reads", dst="E1", why="show", where="src/v.py:5"),
               Edge(src="C1", verb="uses", dst="D1", why="query", where="src/v.py:7")]
    return m


def problems_of(m: ProjectModel) -> list[str]:
    problems, _ = validate_model(m)
    return problems


def warnings_of(m: ProjectModel) -> list[str]:
    _, warnings = validate_model(m)
    return warnings


# --- dependency purpose buckets ---------------------------------------------------

def test_bucket_cap_exceeded_is_advisory_not_gating() -> None:
    # More than the soft cap of distinct buckets among external systems -> an advisory warning, NOT a
    # gate (an integration-heavy product legitimately spans many purposes — e.g. mee6 needs 9).
    m = make_valid_model()
    m.deps = [Dep(id=f"D{i}", name=f"S{i}", kind="service", type="api", bucket=f"Bucket {i}")
              for i in range(grammar.DEP_BUCKET_CAP + 2)]
    assert any("Many purpose buckets among external systems" in w for w in warnings_of(m))
    assert not any("purpose buckets" in p for p in problems_of(m))


def test_bucket_non_seed_is_an_advisory_nudge_not_a_gate() -> None:
    m = make_valid_model()
    m.deps = [Dep(id="D1", name="Postgres", kind="datastore", type="SQL", bucket="Datastores")]
    assert not any("Datastores" in p for p in problems_of(m))                      # not gating
    assert any("Datastores" in w and "not a seed" in w for w in warnings_of(m))    # one nudge, aggregated


def test_bucket_seed_spelling_passes_clean() -> None:
    m = make_valid_model()
    m.deps = [Dep(id="D1", name="Postgres", kind="datastore", type="SQL", bucket="Data & storage")]
    assert not any("bucket" in w.lower() for w in warnings_of(m))


# --- clean baseline ---------------------------------------------------------------

def test_valid_model_has_no_problems():
    assert problems_of(make_valid_model()) == []


# --- referential + shape -----------------------------------------------------------

def test_undefined_reference_is_flagged():
    m = make_valid_model()
    m.edges.append(Edge(src="C1", verb="uses", dst="C9"))
    assert any("undefined IDs" in p and "C9" in p for p in problems_of(m))


def test_stray_s_token_suppressed_without_grouping():
    m = make_valid_model()
    m.goal = "Files are stored in AWS S3 buckets."  # no subsystems defined → S3 must not flag
    assert problems_of(m) == []


def test_prose_id_token_is_not_a_reference():
    # An id-shaped token in PROSE (the PKCE value "S256", "AWS S3", a "D3" library) is a domain string,
    # not a cross-reference — even when grouping exists. The old whole-document scan false-positived here
    # (and a build once "fixed" it by corrupting "S256" to "S-256"); references now come only from typed
    # id fields + `[[ID]]` markers.
    m = make_valid_model()
    m.subsystems = [Group(id="S1", name="Core", purpose="all")]
    m.components[0].subsystem = "S1"
    m.goal = "Auth uses S256 (PKCE); files sit in AWS S3; charts use the D3 lib."
    assert not any("S256" in p or "S3" in p or "D3" in p for p in problems_of(m))


def test_bracket_marker_reference_is_resolved():
    # A deliberate in-prose cross-reference uses the `[[ID]]` marker, which IS resolved.
    m = make_valid_model()
    m.components[0].purpose = "Delegates to [[C9]] for the heavy lifting."
    assert any("undefined IDs" in p and "C9" in p for p in problems_of(m))


def test_empty_actors_blocks_when_roles_defined():
    # Loud guard (the anti-silent-no-op): with roles defined, a use case that names NO actor FAILS
    # validate — so the actor-attribution audit can never silently have nothing to compare.
    m = make_valid_model()
    m.use_cases[0].actors = []
    assert any("no actor" in p and "UC1" in p for p in problems_of(m))


def test_empty_actors_allowed_when_no_roles():
    # A roles-less map legitimately has no actors and no role-id references — the guard does not fire.
    m = make_valid_model()
    m.roles = []
    m.use_cases[0].actors = []
    m.flows[0].steps = [FlowStep(n=1, src="C1", dst="E1", phrase="reads",
                                 where="src/v.py:5")]  # no actor step / role ref
    assert not any("no actor" in p for p in problems_of(m))


def test_duplicate_ids_flagged():
    m = make_valid_model()
    m.components.append(Component(id="C1", name="Again"))
    assert any("Duplicate element definitions" in p and "C1" in p for p in problems_of(m))


def test_suffixed_pointer_is_flagged():
    m = make_valid_model()
    m.subsystems = [Group(id="S1", name="Core", purpose="all")]
    m.components[0].subsystem = "S12a"
    assert any("S12a" in p and "not a valid schema ID" in p for p in problems_of(m))


def test_hierarchy_cycle_and_wrong_kind_parent():
    m = make_valid_model()
    m.subsystems = [Group(id="S1", name="A", parent="S2"), Group(id="S2", name="B", parent="S1")]
    m.components[0].subsystem = "S1"
    probs = problems_of(m)
    assert any("cycle" in p.lower() for p in probs)
    m2 = make_valid_model()
    m2.subsystems = [Group(id="S1", name="A")]
    m2.subdomains = [Group(id="SD1", name="Dom")]
    m2.entities[0].subdomain = "SD1"
    m2.components[0].subsystem = "SD1"  # a component under a SUBDOMAIN is the wrong kind
    assert any("not a subsystem" in p for p in problems_of(m2))


# --- element checks ------------------------------------------------------------------

def test_gp_step_without_uc_is_flagged():
    m = make_valid_model()
    m.happy_path[0].uc = None
    assert any("Happy Path steps missing" in p for p in problems_of(m))


def test_unknown_flow_actor_is_flagged():
    m = make_valid_model()
    m.flows[0].steps[0].src = "Zoe"
    assert any("actor 'Zoe' is not a defined Role" in p for p in problems_of(m))


def test_duplicate_flow_per_use_case_is_flagged():
    m = make_valid_model()
    m.flows.append(Flow(uc="UC1", title="Again", steps=[]))
    assert any("more than one T6 flow" in p for p in problems_of(m))


def test_flow_step_without_action_text_is_flagged():
    # Every step must carry its own action text; it is no longer derived from the backbone edge.
    m = make_valid_model()
    m.flows[0].steps[0].phrase = ""
    assert any("has no action text" in p for p in problems_of(m))


def test_invalid_dep_kind_is_flagged():
    m = make_valid_model()
    m.deps[0].kind = "databaze"
    assert any("invalid dependency Kind" in p for p in problems_of(m))


def test_empty_edge_verb_is_flagged():
    m = make_valid_model()
    m.edges[0].verb = "  "
    assert any("empty Verb" in p for p in problems_of(m))


def test_edge_where_prose_is_a_blocking_problem():
    # A present-but-malformed `where` (prose, not a `path:line`) is blocked by the anchor-format gate.
    m = make_valid_model()
    m.edges[0].where = "somewhere in the code"
    assert any("where" in p and "not a valid" in p for p in problems_of(m))


def test_extensionless_file_anchor_is_valid():
    # An extensionless ops file carrying a line (`Dockerfile:1`, `Makefile:6-9`) is a valid file anchor —
    # file-ness is not decided by "has a dot". Format must not reject these real run/build anchors.
    for anchor in ("Dockerfile:1", "Makefile:6-9"):
        m = make_valid_model()
        m.edges[0].where = anchor
        assert not any("not a valid" in p and "where" in p.lower() for p in problems_of(m)), anchor


def test_edge_missing_where_is_a_blocking_problem():
    # An edge's `where` is its witness (an EXAMPLE call site grounding the claim) — still required.
    m = make_valid_model()
    m.edges[0].where = None
    assert any("no `Where` anchor" in p and "EXAMPLE call site" in p for p in problems_of(m))


def test_edge_no_call_site_opt_out_allows_missing_where():
    # The explicit opt-out for a genuinely decoupled edge clears the missing-`where` block.
    m = make_valid_model()
    m.edges[0].where = None
    m.edges[0].no_call_site = True
    assert not any("no `Where` anchor" in p for p in problems_of(m))


# --- flow-step anchors (`where` is THE location — one step, one call site) ---------


def make_element_step_flow() -> Flow:
    # An element↔element step with its own precise call site — the shape the anchor rules target.
    return Flow(uc="UC1", title="View order",
                steps=[FlowStep(n=1, src="C1", dst="E1", phrase="reads", where="src/v.py:5")])


def test_element_step_missing_where_is_a_blocking_problem():
    m = make_valid_model()
    m.flows = [make_element_step_flow()]
    m.flows[0].steps[0].where = None
    assert any("UC1 flow step 1" in p and "no `where` call-site anchor" in p for p in problems_of(m))


def test_element_step_no_call_site_opt_out_allows_missing_where():
    m = make_valid_model()
    m.flows = [make_element_step_flow()]
    m.flows[0].steps[0].where = None
    m.flows[0].steps[0].no_call_site = True
    assert not any("no `where` call-site anchor" in p for p in problems_of(m))


def test_actor_step_needs_no_where():
    # An actor step (a Role endpoint) is a human action — no call site is demanded.
    m = make_valid_model()  # its only step is R1 → C1 with no `where`
    assert not any("no `where` call-site anchor" in p for p in problems_of(m))


def test_step_where_prose_is_a_blocking_problem():
    # A present-but-malformed step `where` is blocked by the anchor-format gate, like every anchor.
    m = make_valid_model()
    m.flows = [make_element_step_flow()]
    m.flows[0].steps[0].where = "somewhere in the code"
    assert any("flow step 1 where" in p and "not a valid" in p for p in problems_of(m))


def test_step_where_with_no_call_site_is_a_warning():
    # Contradictory intent (`where` + `no_call_site`) is advisory, mirroring the edge rule.
    m = make_valid_model()
    m.flows = [make_element_step_flow()]
    m.flows[0].steps[0].no_call_site = True
    assert any("`no_call_site` is set but a `where` is present" in w for w in warnings_of(m))


def test_duplicate_step_n_is_a_blocking_problem():
    # `step:<uc>:<n>` is the impact engine's synthetic id — `n` must be unique within a flow.
    m = make_valid_model()
    m.flows = [Flow(uc="UC1", title="View order",
                    steps=[FlowStep(n=1, src="C1", dst="E1", phrase="reads", where="src/v.py:5"),
                           FlowStep(n=1, src="C1", dst="D1", phrase="queries", where="src/v.py:7")])]
    assert any("duplicate step number 1" in p for p in problems_of(m))


# --- sub-flows (named shared step sequences) ----------------------------------------


def make_subflow(sid: str = "SF1") -> SubFlow:
    return SubFlow(id=sid, name="Persist the order",
                   steps=[FlowStep(n=1, src="C1", dst="E1", phrase="writes", where="src/v.py:5"),
                          FlowStep(n=2, src="C1", dst="D1", phrase="notifies", where="src/v.py:7")])


def make_ref_step(n: int = 2) -> FlowStep:
    return FlowStep(n=n, src="C1", dst="D1", subflow="SF1")


def make_model_with_subflow() -> ProjectModel:
    # two flows referencing SF1, so the <2-references advisory stays quiet
    m = make_valid_model()
    m.use_cases.append(UseCase(id="UC2", name="Audit order", actors=["R1"]))
    m.subflows = [make_subflow()]
    m.flows = [Flow(uc="UC1", title="View order",
                    steps=[FlowStep(n=1, src="R1", dst="C1", phrase="opens"), make_ref_step()]),
               Flow(uc="UC2", title="Audit order",
                    steps=[FlowStep(n=1, src="R1", dst="C1", phrase="asks"), make_ref_step()])]
    return m


def test_subflow_model_is_clean():
    assert problems_of(make_model_with_subflow()) == []


def test_unresolved_subflow_reference_is_flagged():
    m = make_model_with_subflow()
    m.flows[0].steps[1].subflow = "SF9"
    assert any("undefined sub-flow 'SF9'" in p for p in problems_of(m))


def test_nested_subflow_reference_is_flagged():
    m = make_model_with_subflow()
    m.subflows[0].steps[0].subflow = "SF1"
    assert any("may not reference a sub-flow" in p for p in problems_of(m))


def test_reference_step_with_own_where_is_flagged():
    m = make_model_with_subflow()
    m.flows[0].steps[1].where = "src/v.py:9"
    assert any("carries no location of its own" in p for p in problems_of(m))


def test_reference_step_phrase_is_optional():
    # already empty in make_ref_step — the phrase-required rule must not fire on a reference
    assert not any("no action text" in p for p in problems_of(make_model_with_subflow()))


def test_subflow_steps_obey_step_rules():
    # a sub-flow's element↔element step without `where` blocks, exactly like a flow's step
    m = make_model_with_subflow()
    m.subflows[0].steps[0].where = None
    assert any("SF1 step 1" in p and "no `where` call-site anchor" in p for p in problems_of(m))
    m2 = make_model_with_subflow()
    m2.subflows[0].steps[0].where = "prose, not an anchor"
    assert any("SF1 step 1 where" in p and "not a valid" in p for p in problems_of(m2))


def test_subflow_step_dangling_endpoint_is_flagged():
    # sub-flow steps are ordinary steps — a dangling element endpoint must resolve like a flow's
    m = make_model_with_subflow()
    m.subflows[0].steps[0].dst = "C99"
    assert any("undefined IDs" in p and "C99" in p for p in problems_of(m))


def test_dangling_subflow_prose_ref_is_never_suppressed():
    # `[[SF9]]` in prose dangles even when the map has no grouping (the S-family additivity
    # suppression must not swallow SF refs)
    m = make_valid_model()
    m.components[0].purpose = "Runs the shared sequence [[SF9]] on every write."
    assert any("undefined IDs" in p and "SF9" in p for p in problems_of(m))


def test_empty_flow_warns_under_band():
    m = make_valid_model()
    m.flows[0].steps = []
    assert any("only 0 step(s)" in w for w in warnings_of(m))


def test_subflow_referenced_once_is_an_advisory():
    m = make_model_with_subflow()
    m.flows[1].steps = [FlowStep(n=1, src="R1", dst="C1", phrase="asks")]  # drop UC2's reference
    assert any("referenced by 1 flow(s)" in w for w in warnings_of(m))
    assert not any("referenced by" in w for w in warnings_of(make_model_with_subflow()))


# --- granularity advisories (band, fused names, literal duplication) ----------------


def make_long_flow(n_steps: int, uc: str = "UC1") -> Flow:
    return Flow(uc=uc, title="View order",
                steps=[FlowStep(n=i, src="C1", dst="E1", phrase=f"does thing {i}",
                                where=f"src/v.py:{i}") for i in range(1, n_steps + 1)])


def test_flow_over_band_warns_and_exception_silences():
    m = make_valid_model()
    m.flows = [make_long_flow(16)]
    assert any("16 steps" in w and "band" in w for w in warnings_of(m))
    m.extras = [ExtraSection(heading="Balance exceptions",
                             body="UC1: OAuth is protocol-imposed; one goal, wire grain kept.")]
    assert not any("16 steps" in w for w in warnings_of(m))


def test_under_band_flow_warns():
    m = make_valid_model()  # its only flow has 1 step
    assert any("only 1 step(s)" in w for w in warnings_of(m))


def test_fused_use_case_name_warns():
    m = make_valid_model()
    m.use_cases[0].name = "Sign in and create an organization"
    assert any("joins two clauses with 'and'" in w for w in warnings_of(m))


def test_shared_run_detector_finds_literal_duplication():
    m = make_valid_model()
    m.use_cases.append(UseCase(id="UC2", name="Audit order", actors=["R1"]))
    shared = [FlowStep(n=i, src="C1", dst=("E1" if i % 2 else "D1"), phrase=f"s{i}",
                       where=f"src/v.py:{i}") for i in range(1, 5)]  # 4 identical hops
    m.flows = [Flow(uc="UC1", title="a", steps=shared),
               Flow(uc="UC2", title="b",
                    steps=[FlowStep(n=0, src="R1", dst="C1", phrase="opens"), *shared])]
    assert any("share a run of 4 identical steps" in w for w in warnings_of(m))


def test_shared_run_with_different_wheres_is_quiet():
    # endpoint-only matching called "stores X" and "loads Y" duplicates (seen on a live map) —
    # steps are identical only when src, dst AND grounding match
    m = make_valid_model()
    m.use_cases.append(UseCase(id="UC2", name="Audit order", actors=["R1"]))
    mk = lambda base: [FlowStep(n=i, src="C1", dst=("E1" if i % 2 else "D1"), phrase=f"s{i}",
                                where=f"src/{base}.py:{i}") for i in range(1, 5)]
    m.flows = [Flow(uc="UC1", title="a", steps=mk("a")),
               Flow(uc="UC2", title="b", steps=mk("b"))]  # same endpoints, different call sites
    assert not any("identical steps" in w for w in warnings_of(m))


def test_shared_run_through_actor_step_is_quiet():
    # a run containing an actor step is unextractable by rule (sub-flows can't hold actor
    # endpoints) — "extract a sub-flow" would be impossible advice, so the run must not report
    m = make_valid_model()
    m.use_cases.append(UseCase(id="UC2", name="Audit order", actors=["R1"]))
    shared = [FlowStep(n=1, src="R1", dst="C1", phrase="asks"),
              FlowStep(n=2, src="C1", dst="E1", phrase="reads", where="src/v.py:2"),
              FlowStep(n=3, src="R1", dst="C1", phrase="asks again"),
              FlowStep(n=4, src="C1", dst="D1", phrase="queries", where="src/v.py:4")]
    m.flows = [Flow(uc="UC1", title="a", steps=list(shared)),
               Flow(uc="UC2", title="b", steps=list(shared))]  # identical, but actor-interleaved
    assert not any("identical steps" in w for w in warnings_of(m))


def test_accepted_duplication_heading_silences_the_pair():
    m = make_valid_model()
    m.use_cases.append(UseCase(id="UC2", name="Audit order", actors=["R1"]))
    shared = [FlowStep(n=i, src="C1", dst=("E1" if i % 2 else "D1"), phrase=f"s{i}",
                       where=f"src/v.py:{i}") for i in range(1, 5)]
    m.flows = [Flow(uc="UC1", title="a", steps=shared),
               Flow(uc="UC2", title="b", steps=list(shared))]
    assert any("identical steps" in w for w in warnings_of(m))
    m.extras = [ExtraSection(heading="Accepted duplications",
                             body="UC1 & UC2: the UI-kickoff prefix is deliberate, not machinery.")]
    assert not any("identical steps" in w for w in warnings_of(m))


def test_altitude_nudge_silenced_by_component_exception():
    m = make_valid_model()
    m.components[0].purpose = "ports, adapters, stores, loaders, mappers, codecs"  # 6 bare sub-units
    assert any("consider promoting C1" in w for w in warnings_of(m))
    m.extras = [ExtraSection(heading="Balance exceptions",
                             body="C1: a legitimate family roster, not hidden subsystems.")]
    assert not any("consider promoting C1" in w for w in warnings_of(m))


def test_short_shared_run_is_quiet():
    m = make_valid_model()
    m.use_cases.append(UseCase(id="UC2", name="Audit order", actors=["R1"]))
    shared = [FlowStep(n=i, src="C1", dst=("E1" if i % 2 else "D1"), phrase=f"s{i}",
                       where=f"src/v.py:{i}") for i in range(1, 4)]  # only 3 hops
    m.flows = [Flow(uc="UC1", title="a", steps=shared),
               Flow(uc="UC2", title="b", steps=list(shared))]
    assert not any("identical steps" in w for w in warnings_of(m))


# --- use-case & Happy-Path completeness (front-door verification's teeth) -----------


def make_entry_point(component: str = "C1", activation: str = "external",
                     kind: str = "http", trigger: str = "GET /orders") -> EntryPoint:
    return EntryPoint(kind=kind, trigger=trigger, source="src/v.py:1",
                      component=component, activation=activation)


def test_claimed_external_entry_point_is_quiet():
    m = make_valid_model()  # its flow's step R1 → C1 claims C1
    m.entry_points = [make_entry_point("C1")]
    assert not any("unclaimed" in w for w in warnings_of(m))


def test_unclaimed_external_entry_point_warns_grouped_per_component():
    m = make_valid_model()
    m.components.append(Component(id="C2", name="Debug routes", purpose="ops"))
    m.entry_points = [make_entry_point("C2", trigger="GET /debug/a"),
                      make_entry_point("C2", trigger="GET /debug/b")]
    hits = [w for w in warnings_of(m) if "unclaimed by any use case" in w]
    assert len(hits) == 1  # grouped per component, not per entry point
    assert "C2" in hits[0] and "2 externally-activated" in hits[0]
    assert "/debug/a" in hits[0] and "/debug/b" in hits[0]


def test_self_activated_entry_point_is_exempt():
    m = make_valid_model()
    m.components.append(Component(id="C2", name="Worker", purpose="background"))
    m.entry_points = [make_entry_point("C2", activation="self", kind="background loop",
                                       trigger="interval tick")]
    assert not any("unclaimed" in w for w in warnings_of(m))


def test_invalid_activation_falls_back_to_kind_inference():
    # A truthy near-miss ('mounted' on an http-ish kind) must not silently exempt the row — the
    # effective activation comes from the kind heuristic, so the coverage check still sees it.
    m = make_valid_model()
    m.components.append(Component(id="C2", name="Demo mount", purpose="demo"))
    m.entry_points = [make_entry_point("C2", activation="mounted", kind="http")]
    assert any("unclaimed" in w and "C2" in w for w in warnings_of(m))
    assert any("invalid activation 'mounted'" in p for p in problems_of(m))  # and it BLOCKS


def test_component_claimed_only_via_subflow_is_quiet():
    m = make_valid_model()
    m.components.append(Component(id="C2", name="OAuth dance", purpose="auth"))
    m.subflows = [SubFlow(id="SF1", name="OAuth dance",
                          steps=[FlowStep(n=1, src="C1", dst="C2", phrase="redirects",
                                          where="src/v.py:9")])]
    m.flows[0].steps.append(FlowStep(n=2, src="C1", dst="C1", subflow="SF1"))
    m.entry_points = [make_entry_point("C2", trigger="GET /oauth/callback")]
    assert not any("unclaimed" in w for w in warnings_of(m))


def test_unclaimed_surfaces_heading_silences_the_component():
    m = make_valid_model()
    m.components.append(Component(id="C2", name="Debug routes", purpose="ops"))
    m.entry_points = [make_entry_point("C2", trigger="GET /debug")]
    assert any("unclaimed" in w for w in warnings_of(m))
    m.extras = [ExtraSection(heading="Unclaimed surfaces",
                             body="C2: superadmin debug surface — deliberate, no use case.")]
    assert not any("unclaimed" in w for w in warnings_of(m))


def test_unclaimed_surfaces_record_is_read_from_line_starts_only():
    # Prose that merely MENTIONS a component id mid-sentence, or a sentence that STARTS with the
    # id but runs on with no separator, must not silence it — only a line-leading `Cn: <why>`
    # record counts (live 'Happy Path coverage' bodies carry such prose).
    m = make_valid_model()
    m.components.append(Component(id="C2", name="Debug routes", purpose="ops"))
    m.entry_points = [make_entry_point("C2", trigger="GET /debug")]
    for prose in ("The debug router (see C2) is under review.",
                  "C2 is under review.",           # line-leading but separator-less prose
                  "* C2 mentioned in passing"):
        m.extras = [ExtraSection(heading="Unclaimed surfaces", body=prose)]
        assert any("unclaimed" in w and "C2" in w for w in warnings_of(m)), prose


def test_hp_coverage_record_paren_form_is_read():
    # The tolerated record shape a live map already uses: "UCn (its name) — why", no colon.
    m = make_valid_model()
    m.use_cases.append(UseCase(id="UC2", name="Side flow", actors=["R1"]))
    m.flows.append(Flow(uc="UC2", title="Side",
                        steps=[FlowStep(n=1, src="R1", dst="C1", phrase="opens")]))
    m.extras = [ExtraSection(heading="Happy Path coverage",
                             body="UC2 (Side flow) is intentionally off the spine — demo ops.")]
    assert not any("off the Happy-Path spine" in w for w in warnings_of(m))


def test_external_entry_point_with_no_component_warns():
    m = make_valid_model()
    m.entry_points = [make_entry_point(component="  ", trigger="GET /orphan")]
    assert any("owned by no component" in w for w in warnings_of(m))


def test_entry_surface_check_is_silent_without_flows():
    # Additivity: an untraced map is "not yet traced", not "all unclaimed".
    m = make_valid_model()
    m.flows = []
    m.components.append(Component(id="C2", name="Debug routes", purpose="ops"))
    m.entry_points = [make_entry_point("C2", trigger="GET /debug")]
    assert not any("unclaimed" in w for w in warnings_of(m))


def test_use_case_without_flow_warns_once_tracing_began():
    m = make_valid_model()
    m.use_cases.append(UseCase(id="UC2", name="Ghost feature", actors=["R1"]))
    m.happy_path.append(HappyStep(id="HP2", title="Ghost", uc="UC2"))  # on-spine, still untraced
    assert any("UC2" in w and "has no T6 flow" in w for w in warnings_of(m))
    m.flows = []  # no tracing yet → the phantom signal stays quiet for every use case
    assert not any("has no T6 flow" in w for w in warnings_of(m))


def test_role_driving_nothing_warns_unless_it_lives_in_a_flow():
    m = make_valid_model()
    m.roles.append(Role(id="R2", name="Approver", kind="human", wants="", drives=""))
    assert any("R2" in w and "drives no use case and appears in no flow" in w
               for w in warnings_of(m))
    # a role can legitimately live mid-flow only (an approver) without driving any use case
    m.flows[0].steps.append(FlowStep(n=2, src="C1", dst="R2", phrase="notifies"))
    assert not any("drives no use case and appears in no flow" in w for w in warnings_of(m))


def test_role_with_no_on_spine_use_case_warns_and_record_silences():
    m = make_valid_model()
    m.roles.append(Role(id="R2", name="Operator", kind="human", wants="", drives="UC2"))
    m.use_cases.append(UseCase(id="UC2", name="Step into an org", actors=["R2"]))
    m.flows.append(Flow(uc="UC2", title="Step in",
                        steps=[FlowStep(n=1, src="R2", dst="C1", phrase="enters")]))
    warns = warnings_of(m)
    assert any("R2" in w and "drives no on-spine use case" in w for w in warns)
    assert any("UC2" in w and "off the Happy-Path spine and unrecorded" in w for w in warns)
    m.extras = [ExtraSection(heading="Happy Path coverage",
                             body="R2: ops-only role, off the walk by design.\n"
                                  "UC2: demo-operations side flow, not the product walk.")]
    warns = warnings_of(m)
    assert not any("drives no on-spine use case" in w for w in warns)
    assert not any("off the Happy-Path spine" in w for w in warns)


def test_hp_coverage_checks_are_silent_without_a_happy_path():
    m = make_valid_model()
    m.happy_path = []
    m.use_cases.append(UseCase(id="UC2", name="Side flow", actors=["R1"]))
    m.flows.append(Flow(uc="UC2", title="Side",
                        steps=[FlowStep(n=1, src="R1", dst="C1", phrase="opens")]))
    warns = warnings_of(m)
    assert not any("off the Happy-Path spine" in w for w in warns)
    assert not any("on-spine use case" in w for w in warns)


# --- entity-in-flows completeness (the canary + the unbacked-entity-step advisory) ---


def test_entity_flow_canary_fires_and_escape_silences():
    m = make_valid_model()  # has entities + a flow, but no entity step
    assert any("No flow step touches any entity" in w for w in warnings_of(m))
    m.extras = [ExtraSection(heading="Balance exceptions",
                             body="entity-flows: pure orchestration layer, no domain reads/writes.")]
    assert not any("No flow step touches any entity" in w for w in warnings_of(m))


def test_entity_step_silences_the_canary():
    m = make_valid_model()
    m.flows[0].steps.append(FlowStep(n=2, src="C1", dst="E1", phrase="reads the order",
                                     where="src/v.py:5"))  # rides the C1 reads E1 edge
    warns = warnings_of(m)
    assert not any("No flow step touches any entity" in w for w in warns)
    assert not any("claims entity use" in w for w in warns)  # edge-backed → quiet


def test_entity_step_only_in_subflow_silences_the_canary():
    m = make_valid_model()
    m.subflows = [SubFlow(id="SF1", name="Persist pipeline",
                          steps=[FlowStep(n=1, src="C1", dst="E1", phrase="writes",
                                          where="src/v.py:5")])]
    m.flows[0].steps.append(FlowStep(n=2, src="C1", dst="C1", subflow="SF1"))
    assert not any("No flow step touches any entity" in w for w in warnings_of(m))


def test_canary_is_silent_without_entities_or_without_flows():
    m = make_valid_model()
    m.entities = []
    m.edges = [e for e in m.edges if not e.dst.startswith("E")]
    assert not any("No flow step touches any entity" in w for w in warnings_of(m))
    m = make_valid_model()
    m.flows = []
    assert not any("No flow step touches any entity" in w for w in warnings_of(m))


def test_unbacked_entity_step_warns():
    m = make_valid_model()
    m.edges = [Edge(src="C1", verb="uses", dst="D1", why="query", where="src/v.py:7")]
    m.flows[0].steps.append(FlowStep(n=2, src="C1", dst="E1", phrase="reads the order",
                                     where="src/v.py:5"))  # no C1↔E1 edge backs it now
    assert any("UC1 flow step 2" in w and "claims entity use the backbone doesn't" in w
               for w in warnings_of(m))


def test_return_direction_entity_step_matches_the_edge_undirected():
    m = make_valid_model()  # C1 reads E1 edge present
    m.flows[0].steps.append(FlowStep(n=2, src="E1", dst="C1", phrase="returns the loaded order",
                                     no_call_site=True))
    assert not any("claims entity use" in w for w in warnings_of(m))


def test_display_name_actor_step_is_not_flagged_as_unbacked():
    # A roles-less map may use Role DISPLAY NAMES as actor endpoints ("End user → C1") — an actor
    # name starting with E (End user, Engineer) must not read as an entity endpoint.
    m = make_valid_model()
    m.roles = []
    m.use_cases[0].actors = []
    m.flows[0].steps = [FlowStep(n=1, src="End user", dst="C1", phrase="opens the order")]
    assert not any("claims entity use" in w for w in warnings_of(m))


def test_cc_step_without_edge_is_not_flagged_as_unbacked():
    # C↔C return-direction steps legitimately match no backbone edge — only C+E pairs are checked.
    m = make_valid_model()
    m.components.append(Component(id="C2", name="Helper", purpose="helps"))
    m.flows[0].steps.append(FlowStep(n=2, src="C2", dst="C1", phrase="returns the result",
                                     no_call_site=True))
    assert not any("claims entity use" in w for w in warnings_of(m))


def test_entity_step_still_demands_a_where():
    # guard: the element↔element `where` rule applies to C→E steps unchanged
    m = make_valid_model()
    m.flows[0].steps.append(FlowStep(n=2, src="C1", dst="E1", phrase="reads the order"))
    assert any("UC1 flow step 2" in p and "no `where` call-site anchor" in p
               for p in problems_of(m))


# --- entry-point row validity (activation vocabulary + owning-component reference) ---


def test_valid_and_empty_activations_are_clean():
    m = make_valid_model()
    m.entry_points = [make_entry_point("C1", activation="external"),
                      make_entry_point("C1", activation="self", kind="cron"),
                      make_entry_point("C1", activation="")]
    assert not any("activation" in p for p in problems_of(m))


def test_near_miss_activation_is_a_blocking_problem():
    # 'External' would silently reroute through the kind heuristic in every consumer — blocked,
    # EXACT match (unlike the case-folded dep-Kind check).
    m = make_valid_model()
    m.entry_points = [make_entry_point("C1", activation="External")]
    assert any("invalid activation 'External'" in p for p in problems_of(m))


def test_dangling_entry_point_component_is_flagged():
    m = make_valid_model()
    m.entry_points = [make_entry_point("C9")]
    assert any("undefined IDs" in p and "C9" in p for p in problems_of(m))


def test_entry_point_component_must_be_a_c_id():
    m = make_valid_model()
    m.subsystems = [Group(id="S1", name="Core", purpose="all")]
    m.components[0].subsystem = "S1"
    m.entry_points = [make_entry_point("S1")]
    assert any("component 'S1' is not a C id" in p for p in problems_of(m))


def test_empty_entry_point_component_is_not_a_shape_problem():
    m = make_valid_model()
    m.entry_points = [make_entry_point(component="")]
    assert not any("is not a C id" in p or "undefined IDs" in p for p in problems_of(m))


def test_padded_entry_point_component_is_a_shape_problem():
    # ' C1' resolves under the strip-tolerant semantic checks but detaches in the viewer (exact
    # string keying) and violates the published `^C\d+$` schema — the padding itself is the error.
    m = make_valid_model()
    m.entry_points = [make_entry_point(component="C1 ")]
    assert any("component 'C1 ' is not a C id" in p for p in problems_of(m))


def test_edge_no_call_site_with_where_warns():
    # Claiming no call site while also giving one is contradictory — advisory.
    m = make_valid_model()
    m.edges[0].no_call_site = True  # edges[0].where is a valid anchor from make_valid_model
    assert any("no_call_site` is set but a `Where` is present" in w for w in warnings_of(m))


def test_domain_card_completeness_and_relations():
    m = make_valid_model()
    m.entities = [Entity(id="E1", name="Order",
                         relations=[EntityRelation(verb="owns", target="E1"),
                                    EntityRelation(verb="has", target="E1",
                                                   src_card="1", dst_card=None)])]
    probs = problems_of(m)
    assert any("missing a MEANING" in p for p in probs)
    assert any("missing a SOURCE" in p for p in probs)
    assert any("has no FIELDS" in p for p in probs)
    assert any("non-canonical alias" in p for p in probs)          # owns → contains
    assert any("half-stated cardinality" in p for p in probs)


def make_keyed_relation(keyed_by: list[str], verb: str = "attachedTo") -> EntityRelation:
    return EntityRelation(verb=verb, target="E2", src_card="*", dst_card="1", keyed_by=keyed_by)


def test_keyed_by_alone_is_clean_and_quiets_fieldless_nudge():
    # a field-less association whose key lives in `keyed_by` (not a `{how}` note) must NOT trip the
    # "not backed by a field and has no note" warning, and must raise no problems.
    m = make_valid_model()
    m.entities = [make_entity("E1", "Order", relations=[make_keyed_relation(["parent_id"])]),
                  make_entity("E2", "Parent")]
    assert not any("keyed_by" in p for p in problems_of(m))
    assert not any("not backed by a field" in w for w in warnings_of(m))


def test_keyed_by_naming_a_declared_source_field_is_rejected():
    # the key IS a plain (unmarked) field on the source row → it's a foreign key, not a storage key.
    # This is the `Membership.role` misuse class the FK-marker XOR rule alone would miss.
    e1 = Entity(id="E1", name="Membership", store="x", meaning="a thing", source="src/o.py:1",
                fields=[EntityField(name="id", type="str", markers=["PK"]),
                        EntityField(name="role", type="string", markers=[])],
                relations=[EntityRelation(verb="assignedRole", target="E2", src_card="*",
                                          dst_card="1", keyed_by=["role"])])
    m = make_valid_model()
    m.entities = [e1, make_entity("E2", "RoleDefinition")]
    assert any("which is a declared field" in p and "role" in p for p in problems_of(m))


def test_keyed_by_naming_a_declared_target_field_is_rejected():
    # the key matches a field on the TARGET row → a reverse FK; still not a storage key.
    e2 = Entity(id="E2", name="Child", store="x", meaning="a thing", source="src/c.py:1",
                fields=[EntityField(name="id", type="str", markers=["PK"]),
                        EntityField(name="parent_id", type="str", markers=[])])
    m = make_valid_model()
    m.entities = [make_entity("E1", "Parent", relations=[make_keyed_relation(["parent_id"], "has")]),
                  e2]
    assert any("which is a declared field" in p for p in problems_of(m))


def test_keyed_by_with_differently_named_backing_fk_is_rejected():
    # a real FK field (a DIFFERENT name than the key) backs the relation → the XOR rule catches it.
    e1 = Entity(id="E1", name="Order", store="orders", meaning="a thing", source="src/o.py:1",
                fields=[EntityField(name="id", type="str", markers=["PK"]),
                        EntityField(name="parent", type="E2", markers=[])],   # typed by the target
                relations=[make_keyed_relation(["some_store_key"])])
    m = make_valid_model()
    m.entities = [e1, make_entity("E2", "Parent")]
    assert any("already backs it" in p and "keyed_by" in p for p in problems_of(m))


def test_keyed_by_empty_entry_is_rejected():
    m = make_valid_model()
    m.entities = [make_entity("E1", "Order", relations=[make_keyed_relation([" "])]),
                  make_entity("E2", "Parent")]
    assert any("empty `keyed_by` entry" in p for p in problems_of(m))


def test_validate_warns_on_duplicate_edges_with_differing_anchors():
    # After assemble's exact-dedup, a remaining (src,verb,dst) duplicate differs in where/why — a real
    # conflict the lead must reconcile; validate names it (non-blocking warning).
    m = make_valid_model()
    m.edges = [Edge(src="C1", verb="uses", dst="D1", why="q", where="a.py:3"),
               Edge(src="C1", verb="uses", dst="D1", why="q", where="a.py:9")]
    assert any("declared 2 times" in w for w in warnings_of(m))


def make_fk_heuristic_entities() -> list[Entity]:
    # a field-less association whose {how} note names a plain source field (the role→RoleDefinition
    # class): no FK marker, no keyed_by — a by-name FK hidden behind prose.
    e1 = make_entity("E1", "Membership")
    e1.fields.append(EntityField(name="role", type="string", markers=[]))
    e1.relations.append(EntityRelation(verb="grantsRole", target="E2", src_card="*", dst_card="1",
                                        how="role string names a RoleDefinition key"))
    return [e1, make_entity("E2", "RoleDefinition")]


def test_fk_heuristic_warns_when_note_names_a_source_field():
    m = make_valid_model()
    m.entities = make_fk_heuristic_entities()
    assert any("FK→E2" in w and "role" in w for w in warnings_of(m))
    assert not any("FK→E2" in p for p in problems_of(m))    # a warning, never a blocking problem


def test_fk_heuristic_guard_skips_when_target_absent():
    # at lint a fragment may hold the source but not the FK target — the r.target-in-backing guard
    # must keep the heuristic from false-firing on an entity-typed relation resolved cross-fragment.
    src_only = [make_fk_heuristic_entities()[0]]        # E1 only, no E2
    _problems, warnings = check_domain_relations(src_only)
    assert not any("FK→" in w for w in warnings)


def test_deployment_linked_dep_that_is_a_call_target_warns():
    m = make_valid_model()
    m.deps[0].deployment_linked = True                  # D1 marked deploy-only …
    m.edges = [Edge(src="C1", verb="uses", dst="D1", why="q", where="a.py:3")]  # … but is a call target
    assert any("deployment_linked" in w and "call target" in w for w in warnings_of(m))


def test_security_anchor_is_collected_for_existence_check():
    m = make_valid_model()
    m.security = [SecurityRow(surface="/admin", who="admin",
                              source="[require_admin](backend/auth.py#L70)")]
    pairs = _anchor_pairs(m)
    assert any(lbl.startswith("security") and href == "backend/auth.py#L70" for lbl, href in pairs)


# --- v2-only behaviors ----------------------------------------------------------------

def test_orphan_dep_warns_unless_deployment_linked():
    m = make_valid_model()
    m.deps.append(Dep(id="D2", name="nginx", kind="platform", type="reverse proxy"))
    assert any("D2" in w and "no incoming edge" in w for w in warnings_of(m))
    m.deps[1].deployment_linked = True
    assert not any("D2" in w and "no incoming edge" in w for w in warnings_of(m))


def test_non_entity_marker_quiets_under_harvest():
    with tempfile.TemporaryDirectory() as td:
        domain = Path(td) / "domain"
        domain.mkdir()
        classes = "\n\n".join(f"class Thing{i}:\n    pass" for i in range(12))
        (domain / "things.py").write_text(classes, encoding="utf-8")
        (domain / "order.py").write_text("class Order:\n    pass\n", encoding="utf-8")
        m = make_valid_model()
        m.entities = [make_entity(source="domain/order.py:1")]
        roots = [Path(td)]
        warnings = check_domain_coverage_model(m, roots)
        assert any("Under-harvested" in w for w in warnings)
        m.non_entity_types = [NonEntityType(name=f"Thing{i}", why="generated plumbing")
                              for i in range(12)]
        assert not any("Under-harvested" in w for w in check_domain_coverage_model(m, roots))


def test_stale_view_warns_and_fresh_view_does_not():
    m = make_valid_model()
    with tempfile.TemporaryDirectory() as td:
        model_path = Path(td) / "project-map.json"
        model_path.write_text(to_canonical_json(m), encoding="utf-8")
        _, warnings = validate_model(m, model_path)
        assert any("view missing" in w for w in warnings)
        (Path(td) / "project-map.md").write_text(model_to_markdown(m), encoding="utf-8")
        _, warnings = validate_model(m, model_path)
        # specifically the STALENESS warnings — other advisories may mention "View order" (a title)
        assert not any("view missing" in w or "GENERATED file" in w for w in warnings)
        (Path(td) / "project-map.md").write_text("# hand-edited\n", encoding="utf-8")
        _, warnings = validate_model(m, model_path)
        assert any("GENERATED file" in w for w in warnings)


def test_check_sources_flags_synthesized_entity():
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "src"
        src.mkdir()
        (src / "order.py").write_text("class Order:\n    pass\n", encoding="utf-8")
        m = make_valid_model()
        m.entities = [make_entity(name="PhantomConcept", source="src/order.py:1")]
        problems, _ = validate_model(m, repo_root=Path(td), check_sources=True)
        assert any("PhantomConcept" in p and "not defined in its SOURCE" in p for p in problems)
        m.entities = [make_entity(name="Order", source="src/order.py:1")]
        problems, _ = validate_model(m, repo_root=Path(td), check_sources=True)
        assert not any("not defined in its SOURCE" in p for p in problems)


def test_check_sources_blocks_on_dead_anchor():
    # B3: a nonexistent-file anchor (wrong repo-root prefix / stale path) is a BLOCKING problem now,
    # not a warning — so a bad prefix can never reach the committed map with `validate` all-green.
    with tempfile.TemporaryDirectory() as td:
        m = make_valid_model()
        m.entities[0].source = "src/nowhere.py:1"
        problems, _ = validate_model(m, repo_root=Path(td), check_sources=True)
        assert any("does not resolve" in p for p in problems)


# --- anchor syntax gate: `path#Lnnn` is retired, `path:line`/`path:line-line` is mandatory ---

def test_legacy_hash_anchor_is_a_blocking_problem():
    m = make_valid_model()
    m.entities[0].source = "src/order.py#L1"
    assert any("source" in p and "not a valid" in p for p in problems_of(m))


# --- glossary `where`: a nullable file-OR-directory source anchor, like entities[].source ---

def test_glossary_where_accepts_bare_file_dir_and_null():
    m = make_valid_model()
    m.glossary = [GlossaryRow(term="Order", meaning="a thing", source="src/order.py:12"),
                  GlossaryRow(term="Domain", meaning="the dir", source="src/domain/"),
                  GlossaryRow(term="Product", meaning="no code home", source=None)]
    assert problems_of(m) == []


def test_glossary_where_rejects_markdown_link():
    m = make_valid_model()
    m.glossary = [GlossaryRow(term="Order", meaning="a thing",
                              source="[order.py](src/order.py:12)")]
    assert any("glossary 'Order' source" in p and "not a valid" in p for p in problems_of(m))


def test_glossary_where_dead_anchor_blocks_with_check_sources():
    with tempfile.TemporaryDirectory() as td:
        m = make_valid_model()
        m.glossary = [GlossaryRow(term="Ghost", meaning="gone", source="src/nowhere.py:1")]
        problems, _ = validate_model(m, repo_root=Path(td), check_sources=True)
        assert any("glossary 'Ghost'" in p and "does not resolve" in p for p in problems)


def test_extensionless_edge_where_existence_is_verified():
    # A2 + B3: an extensionless edge anchor (`Dockerfile:1`) is format-valid AND its existence is
    # actually checked (the `_where_href`/`_BARE_PATH` path used to skip extensionless files silently).
    from coyodex.model import Edge, ProjectModel
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
        ok = ProjectModel(edges=[Edge(src="C1", verb="uses", dst="C2", where="Dockerfile:1")])
        assert check_anchor_existence_model(ok, [root]) == []                 # exists → clean
        bad = ProjectModel(edges=[Edge(src="C1", verb="uses", dst="C2", where="Nope.file:1")])
        assert any("does not resolve" in p for p in check_anchor_existence_model(bad, [root]))


def test_colon_range_anchor_is_not_flagged():
    m = make_valid_model()
    m.entities[0].source = "src/order.py:1-9"
    assert problems_of(m) == []


# --- anchor format gate: entry_point / where_configured / edges.where / entry_points.source ---
# must be bare `path:line`, never a markdown link (the label was always just the file's basename).

def test_component_entry_point_md_link_is_a_blocking_problem():
    m = make_valid_model()
    m.components[0].entry_point = "[v.py](src/v.py:1)"
    assert any("entry_point" in p and "not a valid" in p for p in problems_of(m))


def test_dep_where_configured_md_link_is_a_blocking_problem():
    m = make_valid_model()
    m.deps[0].where_configured = "[cfg.py](cfg.py:1)"
    assert any("where_configured" in p and "not a valid" in p for p in problems_of(m))


def test_edge_where_md_link_is_a_blocking_problem():
    m = make_valid_model()
    m.edges[0].where = "[v.py](src/v.py:5)"
    assert any("where" in p and "not a valid" in p for p in problems_of(m))


def test_entry_point_entity_md_link_is_a_blocking_problem():
    m = make_valid_model()
    m.entry_points = [EntryPoint(kind="http", trigger="GET /x", source="[api.py](src/api.py:1)",
                                 component="C1")]
    assert any("source" in p and "not a valid" in p for p in problems_of(m))


# --- group source: a bare file-OR-directory anchor, like components[].source (no markdown link) ---

def test_group_source_accepts_bare_dir_and_file():
    m = make_valid_model()
    m.subsystems = [Group(id="S1", name="Core", purpose="all", source="src/core/")]
    m.components[0].subsystem = "S1"
    m.subdomains = [Group(id="SD1", name="Dom", purpose="d", source="src/order.py:1")]
    m.entities[0].subdomain = "SD1"
    assert not any("source" in p and "not a valid" in p for p in problems_of(m))


def test_group_source_rejects_markdown_link():
    m = make_valid_model()
    m.subsystems = [Group(id="S1", name="Core", purpose="all", source="[core](src/core/)")]
    m.components[0].subsystem = "S1"
    assert any("S1 source" in p and "not a valid" in p for p in problems_of(m))


# --- files / evidence / package / alternative: real fields, not `extra` columns ---

def test_component_files_and_evidence_round_trip_clean():
    m = make_valid_model()
    m.components[0].files = ["src/v.py", "src/helpers.py"]
    m.components[0].evidence = [EvidenceItem(file="src/v.py:12", why="the entry point")]
    assert problems_of(m) == []


def test_evidence_file_must_be_a_bare_path_line_anchor():
    m = make_valid_model()
    m.components[0].evidence = [EvidenceItem(file="[v.py](src/v.py:12)", why="a link, not bare")]
    assert any("evidence[0].file" in p and "not a valid" in p for p in problems_of(m))
    m.components[0].evidence = [EvidenceItem(file="src/v.py#L12", why="the retired form")]
    assert any("evidence[0].file" in p and "not a valid" in p for p in problems_of(m))


def test_evidence_why_must_be_non_empty():
    m = make_valid_model()
    m.components[0].evidence = [EvidenceItem(file="src/v.py:12", why="  ")]
    assert any("evidence[0].why" in p and "non-empty" in p for p in problems_of(m))


def test_dep_package_and_alternative_round_trip_clean():
    m = make_valid_model()
    m.deps[0].package = "motor ^3.7.0 (pyproject.toml)"
    m.deps[0].alternative = "file-backed storage in standalone mode"
    assert problems_of(m) == []


# --- `extra`: a promoted name (files/evidence/package/alternative, or an old spelling) is retired ---

def test_extra_files_count_and_members_are_retired_in_favor_of_the_files_field():
    m = make_valid_model()
    m.components[0].extra = {"files_count": 3}
    assert any("extra.files_count" in p and "top-level `files`" in p for p in problems_of(m))
    m.components[0].extra = {"members": ["a.py"]}
    assert any("extra.members" in p and "top-level `files`" in p for p in problems_of(m))
    m.components[0].extra = {"files": ["a.py"]}
    assert any("extra.files" in p and "top-level `files`" in p for p in problems_of(m))


def test_extra_evidence_is_retired_in_favor_of_the_evidence_field():
    m = make_valid_model()
    m.components[0].extra = {"evidence": [{"file": "policy.py:1", "why": "the reason"}]}
    assert any("extra.evidence" in p and "top-level `evidence`" in p for p in problems_of(m))


def test_extra_sdk_and_client_library_are_retired_in_favor_of_the_package_field():
    m = make_valid_model()
    m.deps[0].extra = {"sdk": "e2b ^2.20.0"}
    assert any("extra.sdk" in p and "top-level `package`" in p for p in problems_of(m))
    m.deps[0].extra = {"client_library": "motor ^3.7.0"}
    assert any("extra.client_library" in p and "top-level `package`" in p for p in problems_of(m))


def test_extra_standalone_alternative_is_retired_in_favor_of_the_alternative_field():
    m = make_valid_model()
    m.deps[0].extra = {"standalone_alternative": "dev_stub"}
    assert any("extra.standalone_alternative" in p and "top-level `alternative`" in p
              for p in problems_of(m))


def test_extra_loc_is_forbidden():
    m = make_valid_model()
    m.components[0].extra = {"loc": 1692}
    assert any("extra.loc" in p and "compute it" in p for p in problems_of(m))


def test_extra_deployment_flavored_key_is_advisory_only():
    m = make_valid_model()
    m.components[0].extra = {"sticky_sessions": "hash $http_mcp_session_id"}
    assert problems_of(m) == []
    assert any("extra.sticky_sessions" in w and "Deployment or Config" in w
              for w in warnings_of(m))


# --- granularity advisory (opt-in via check_coverage; re-computed from the tree — GR4) ---

def make_subsystem_shaped_repo(td: str, n_units: int = 9) -> Path:
    """A tree whose code-derived expectation E is n_units + 1 (n small unit dirs + a core dir)."""
    root = Path(td)
    for i in range(n_units):
        sub = root / "plugins" / f"p{i}"
        sub.mkdir(parents=True)
        for j in range(3):
            (sub / f"f{j}.py").write_text("x\n" * 100, encoding="utf-8")
    core = root / "core"
    core.mkdir()
    (core / "a.py").write_text("x\n" * 60, encoding="utf-8")
    return root


def test_granularity_advisory_fires_through_check_coverage():
    """A 1-component map over a tree expecting ~10 leaves draws the granularity nudge."""
    m = make_valid_model()  # 1 component
    with tempfile.TemporaryDirectory() as td:
        root = make_subsystem_shaped_repo(td)
        _, warnings = validate_model(m, repo_root=root, check_coverage=True)
    assert any(w.startswith("Granularity:") for w in warnings), warnings


def test_granularity_advisory_silent_within_band():
    """A component count inside E's ±40% band stays silent — the anchor nudges, it never nags."""
    m = make_valid_model()
    m.components = [Component(id=f"C{i}", name=f"Unit {i}", purpose="one unit",
                              entry_point="src/v.py:1") for i in range(1, 11)]  # 10 ≈ E
    m.edges = []  # the demo edges/flows reference C1 only — drop them so the model stays valid
    m.flows = []
    with tempfile.TemporaryDirectory() as td:
        root = make_subsystem_shaped_repo(td)
        _, warnings = validate_model(m, repo_root=root, check_coverage=True)
    assert not any(w.startswith("Granularity:") for w in warnings), warnings


# --- Coverage exceptions (per-directory suppression of the --check-coverage wall) ---

def test_recorded_coverage_dirs_reads_line_leading_dirs():
    from coyodex.validate_model import _recorded_coverage_dirs
    m = make_valid_model()
    m.extras = [ExtraSection(heading="Coverage exceptions",
                             body="plugins/: coarse altitude\n  foo/bar/: generated\nprose plugins/x mid-line")]
    assert _recorded_coverage_dirs(m) == {"plugins", "foo/bar"}   # trailing slash normalized; prose ignored


def test_compression_coverage_exception_is_boundary_aware():
    from coyodex.validate_analysis import compression_coverage_from_refs
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for base in ("plugins", "plugins_legacy"):   # a NAME-PREFIX sibling, not a path child
            for i in range(10):                       # ≥ _COMPRESSION_MIN (8) sibling subdirs
                sub = root / base / f"p{i}"
                sub.mkdir(parents=True)
                (sub / "a.py").write_text("x\n", encoding="utf-8")
        refs = {"plugins/p0", "plugins_legacy/p0"}    # the map references one subdir under each
        base = compression_coverage_from_refs(refs, root)
        assert any(w.startswith("Compression: plugins/") for w in base)
        assert any(w.startswith("Compression: plugins_legacy/") for w in base)
        skipped = compression_coverage_from_refs(refs, root, frozenset({"plugins"}))
        assert not any(w.startswith("Compression: plugins/") for w in skipped)     # recorded → silent
        assert any(w.startswith("Compression: plugins_legacy/") for w in skipped)  # sibling still warns


def test_coverage_exception_drops_recorded_domain_dir_from_denominator():
    with tempfile.TemporaryDirectory() as td:
        for d, cover, extra in (("folded", "Order", "T"), ("kept", "Member", "K")):
            p = Path(td) / d
            p.mkdir()
            (p / f"{cover.lower()}.py").write_text(f"class {cover}:\n    pass\n", encoding="utf-8")
            (p / "more.py").write_text("\n\n".join(f"class {extra}{i}:\n    pass" for i in range(12)),
                                       encoding="utf-8")
        m = make_valid_model()
        m.entities = [make_entity(eid="E1", name="Order", source="folded/order.py:1"),
                      make_entity(eid="E2", name="Member", source="kept/member.py:1")]
        roots = [Path(td)]
        assert any("Under-harvested" in w for w in check_domain_coverage_model(m, roots))
        skipped = check_domain_coverage_model(m, roots, frozenset({"folded"}))
        msg = [w for w in skipped if "Under-harvested" in w]
        assert msg                                      # 'kept' still warns
        assert not any("T0" in w for w in msg)          # folded types dropped from denominator + list


def test_coverage_exception_silences_unclaimed_surface_by_dir():
    from coyodex.validate_model import _completeness_warnings
    m = make_valid_model()
    m.components.append(Component(id="C2", name="Plugin", purpose="a plugin",
                                  source="plugins/achievements/plugin.py:1"))
    m.entry_points = [EntryPoint(kind="command", trigger="!achieve", source="plugins/achievements/plugin.py:5",
                                 component="C2", activation="external")]  # C2 is in no flow → unclaimed
    assert any(w.startswith("C2 ") and "unclaimed" in w for w in _completeness_warnings(m))
    m.extras = [ExtraSection(heading="Coverage exceptions", body="plugins/: representative at coarse altitude")]
    assert not any(w.startswith("C2 ") for w in _completeness_warnings(m))


# --- Deployment / runs_in ------------------------------------------------------

def test_runs_in_must_resolve_to_a_deployment_unit():
    m = make_valid_model()
    m.deployment = [DeploymentRow(unit="bot"), DeploymentRow(unit="worker")]
    m.components[0].runs_in = ["worker"]
    assert problems_of(m) == []                                   # a real unit → clean
    m.components[0].runs_in = ["ghost"]
    assert any("C1 runs_in names unknown deployment unit" in p and "ghost" in p for p in problems_of(m))


def test_entry_point_runs_in_also_checked():
    m = make_valid_model()
    m.deployment = [DeploymentRow(unit="worker")]
    m.entry_points = [EntryPoint(kind="worker", trigger="loop", source="w.py:1", component="C1",
                                 activation="self", runs_in=["nope"])]
    assert any("entry_points[0] runs_in names unknown deployment unit" in p for p in problems_of(m))


def test_duplicate_deployment_unit_blocks():
    m = make_valid_model()
    m.deployment = [DeploymentRow(unit="bot"), DeploymentRow(unit="bot")]
    assert any("Duplicate deployment unit name" in p and "bot" in p for p in problems_of(m))


def test_unplaced_self_thread_is_advised_only_once_runs_in_is_used():
    m = make_valid_model()
    m.deployment = [DeploymentRow(unit="worker")]
    m.entry_points = [EntryPoint(kind="cron", trigger="orphan loop", source="o.py:1", component="C1",
                                 activation="self")]  # C1 has no runs_in → this thread is unplaced
    # runs_in nowhere used yet → silent (un-adopted, not a gap)
    assert not any("Unplaced" in w for w in warnings_of(m))
    # once ANY runs_in is set, the un-hosted self thread is surfaced
    m.deployment.append(DeploymentRow(unit="bot"))
    m.components[0].runs_in = ["bot"]  # C1 now runs in bot → the C1-owned loop is placed, so add a second unplaced one
    m.entry_points.append(EntryPoint(kind="cron", trigger="really orphan", source="o2.py:1",
                                     component="C99", activation="self"))  # C99 undefined-owner → no host
    assert any("Unplaced" in w and "self-started" in w for w in warnings_of(m))


# --- Deployment quality warnings (WS2) -----------------------------------------

def test_formula_filled_runs_in_is_flagged_but_a_true_monolith_is_not():
    m = make_valid_model()
    # one unit blankets EVERY component while another unit hosts nothing + no entry point placed
    m.deployment = [DeploymentRow(unit="standalone"), DeploymentRow(unit="worker")]
    m.components[0].runs_in = ["standalone"]
    assert any("formula-filled" in w for w in warnings_of(m))
    # a legit all-in-one app (single unit hosting everything, no empty peer) must NOT nag
    m.deployment = [DeploymentRow(unit="standalone")]
    assert not any("formula-filled" in w for w in warnings_of(m))
    # the recorded `runs-in` exception silences the family even with the empty peer back
    m.deployment = [DeploymentRow(unit="standalone"), DeploymentRow(unit="worker")]
    m.extras = [ExtraSection(heading="Balance exceptions", body="runs-in")]
    assert not any("formula-filled" in w for w in warnings_of(m))


def test_formula_fill_silent_on_grounded_dual_deployment():
    # F1 regression: a legitimately grounded map where every component runs in an all-in-one unit PLUS
    # a real split unit (standalone + backend/frontend), and the only EMPTY units are infra, must NOT
    # be called formula-filled — the spread across real units and the infra-only emptiness are grounding.
    m = make_valid_model()
    m.components = [Component(id="C1", name="A", purpose="p", entry_point="a.py:1"),
                   Component(id="C2", name="B", purpose="p", entry_point="b.py:1")]
    m.edges = []
    m.flows = []
    m.deps = [Dep(id="D1", name="MongoDB", kind="datastore", type="db")]
    m.deployment = [DeploymentRow(unit="standalone"), DeploymentRow(unit="backend"),
                    DeploymentRow(unit="frontend"), DeploymentRow(unit="mongo")]  # mongo = empty INFRA
    m.components[0].runs_in = ["standalone", "backend"]
    m.components[1].runs_in = ["standalone", "frontend"]
    assert not any("formula-filled" in w for w in warnings_of(m))   # spread → grounded, stays quiet


def test_unlinked_deployment_unit_is_flagged_unless_it_matches_a_dep():
    m = make_valid_model()                                    # dep D1 = "Postgres" (datastore)
    m.deployment = [DeploymentRow(unit="worker"), DeploymentRow(unit="ghosttown")]
    m.components[0].runs_in = ["worker"]                      # adoption present; ghosttown hosts nothing
    assert any("ghosttown" in w and "run no traced component" in w for w in warnings_of(m))
    # a no-host unit whose NAME matches a system dep is that dep's box, not a gap → not flagged
    m.deployment = [DeploymentRow(unit="worker"), DeploymentRow(unit="postgres")]
    assert not any("postgres" in w and "run no traced component" in w for w in warnings_of(m))


def test_ambiguous_thread_host_is_flagged():
    m = make_valid_model()
    m.deployment = [DeploymentRow(unit="bot"), DeploymentRow(unit="worker")]
    m.components[0].runs_in = ["bot", "worker"]               # C1 runs in TWO units
    m.entry_points = [EntryPoint(kind="cron", trigger="loop", source="o.py:1", component="C1",
                                 activation="self")]          # no own runs_in → host is ambiguous
    assert any("ambiguous" in w for w in warnings_of(m))
    m.entry_points[0].runs_in = ["bot"]                       # pinning its own host resolves it
    assert not any("ambiguous" in w for w in warnings_of(m))


def test_non_atomic_unit_name_is_flagged_but_a_spaced_name_is_not():
    m = make_valid_model()
    m.deployment = [DeploymentRow(unit="mongo-test / redis-test")]  # a separator → two units in one row
    assert any("non-atomic" in w for w in warnings_of(m))
    m.deployment = [DeploymentRow(unit="api worker")]              # spaces, no separator → legit
    assert not any("non-atomic" in w for w in warnings_of(m))


# --- deployment environments (C1) ----------------------------------------------

def test_deployment_variant_must_name_a_declared_environment():
    m = make_valid_model()
    m.environments = ["standalone", "cloud"]
    m.deployment = [DeploymentRow(unit="backend", variants=["cloud"])]
    assert problems_of(m) == []                                   # a declared env → clean
    m.deployment = [DeploymentRow(unit="backend", variants=["ghost"])]
    assert any("undeclared environment" in p and "ghost" in p for p in problems_of(m))
    # a variant with NO environments declared at all is also flagged (can't gate to an unnamed env)
    m.environments = []
    assert any("no `environments` are declared" in p for p in problems_of(m))


def test_environments_absent_is_silent_but_declared_untagged_advises():
    m = make_valid_model()
    m.deployment = [DeploymentRow(unit="app")]                    # no environments, no variants
    assert not any("environment" in w.lower() for w in warnings_of(m))   # un-adopted → silent
    m.environments = ["dev", "prod"]                             # declared but nothing tagged
    assert any("environment(s) declared but no deployment unit is tagged" in w for w in warnings_of(m))


# --- Orphan-dep nudge scoped to system deps (WS6) ------------------------------

def test_orphan_dep_nudge_skips_folded_library_kinds():
    m = make_valid_model()
    # a library dep with no incoming edge folds into Libraries → must NOT nudge for a missing call site
    m.deps.append(Dep(id="D2", name="pydantic", kind="library", type="validation"))
    assert not any("no incoming edge" in w and "D2" in w for w in warnings_of(m))
    # a SYSTEM dep (datastore) with no incoming edge still nudges — it needs a real call site
    m.deps.append(Dep(id="D3", name="Redis", kind="datastore", type="cache"))
    assert any("no incoming edge" in w and "D3" in w for w in warnings_of(m))


# --- File-level harvest coverage (WS4) -----------------------------------------

def test_file_level_coverage_flags_loose_py_with_the_exclusions():
    from coyodex.validate_analysis import file_level_coverage
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "adapters").mkdir()
        (root / "adapters" / "a.py").write_text("x\n", encoding="utf-8")        # referenced
        (root / "adapters" / "loose.py").write_text("x\n", encoding="utf-8")    # the loose gap
        (root / "adapters" / "README.md").write_text("d\n", encoding="utf-8")   # not code → excluded (2)
        (root / "adapters" / "__init__.py").write_text("\n", encoding="utf-8")  # package marker → excluded (4)
        (root / "tests").mkdir()
        (root / "tests" / "t.py").write_text("x\n", encoding="utf-8")           # non-product → excluded (3)
        (root / ".coyodex-eval").mkdir()
        (root / ".coyodex-eval" / "e.py").write_text("x\n", encoding="utf-8")   # coyodex artifact → excluded (3)
        refs = {"adapters/a.py"}
        out = file_level_coverage(refs, root)
        assert any("loose.py" in w for w in out)
        assert not any("README" in w for w in out)
        assert not any("__init__.py" in w for w in out)        # package marker not flagged
        assert not any("tests/t.py" in w for w in out)
        assert not any(".coyodex-eval" in w for w in out)      # coyodex's own output not flagged
        assert any("adapters/ (1)" in w for w in out)          # GROUPED by directory with a count
        # exclusion 1: a referenced DIRECTORY covers its whole subtree
        assert not file_level_coverage({"adapters"}, root)
        # a 'Coverage exceptions' recorded dir suppresses it too
        assert not file_level_coverage(refs, root, frozenset({"adapters"}))


def test_file_level_coverage_groups_root_files_under_root_label():
    from coyodex.validate_analysis import file_level_coverage
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "loose1.py").write_text("x\n", encoding="utf-8")
        (root / "loose2.py").write_text("x\n", encoding="utf-8")
        out = file_level_coverage(set(), root)
        assert any("(root)/ (2): loose1.py, loose2.py" in w for w in out)   # both root files on one line


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
