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

from coyodex.model import (
    Component,
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
    NonEntityType,
    ProjectModel,
    Role,
    UseCase,
    to_canonical_json,
)
from coyodex.validate_model import (
    check_anchor_existence_model,
    check_domain_coverage_model,
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
    m.roles = [Role(name="Andy", kind="human", wants="orders", drives="UC1")]
    m.use_cases = [UseCase(id="UC1", name="View order", actor="Andy")]
    m.happy_path = [HappyStep(id="HP1", title="View", uc="UC1")]
    m.components = [Component(id="C1", name="Viewer", purpose="shows",
                              entry_point="src/v.py:1")]
    m.deps = [Dep(id="D1", name="Postgres", kind="datastore", type="SQL database")]
    m.entities = [make_entity()]
    m.flows = [Flow(uc="UC1", title="View order",
                    steps=[FlowStep(n=1, src="Andy", dst="C1", phrase="opens")])]
    m.edges = [Edge(src="C1", verb="reads", dst="E1", why="show", where="src/v.py:5"),
               Edge(src="C1", verb="uses", dst="D1", why="query", where="src/v.py:7")]
    return m


def problems_of(m: ProjectModel) -> list[str]:
    problems, _ = validate_model(m)
    return problems


def warnings_of(m: ProjectModel) -> list[str]:
    _, warnings = validate_model(m)
    return warnings


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
    # A call-site-less edge gives a flow arrow nothing to open — blocking, not a warning.
    m = make_valid_model()
    m.edges[0].where = None
    assert any("no `Where` call-site anchor" in p for p in problems_of(m))


def test_edge_no_call_site_opt_out_allows_missing_where():
    # The explicit opt-out for a genuinely decoupled edge clears the missing-`where` block.
    m = make_valid_model()
    m.edges[0].where = None
    m.edges[0].no_call_site = True
    assert not any("call-site anchor" in p for p in problems_of(m))


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
        assert not any("view" in w.lower() for w in warnings)
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
