"""Impact ripple layer (M2) — pinned semantics on a hand-built model + the api/impact endpoint.

The model wires every relation the rules use: membership chain (C1→S1→S0), a flow whose steps
touch C1/E1/D1, a Happy-Path step, C→E ownership + reads, a C↔C call edge, an E↔E card relation,
and one flow step matching no backbone edge (the map-quality warning). Ripple assertions pin the
design's semantics: rules fire ONCE from direct hits, data ripple does not chain, opt-in rules stay
off by default, and the strength lattice upgrades a territory-direct group hit from a member ripple.
Explicit make_* builders, no fixtures/classes. Design: internal/docs/impact-and-update-design.md.
"""
from __future__ import annotations

import http.client
import json
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from coyodex.impact_git import ImpactCore, ImpactFile
from coyodex.impact_lib import DirectHit
from coyodex.impact_ripple import (
    R_BEHAVIORAL,
    R_CALLGRAPH,
    R_DATA,
    R_STRUCTURAL,
    RippleOptions,
    build_impact_result,
    type_of,
)
from coyodex.model import (
    Component,
    Dep,
    Edge,
    Entity,
    EntityRelation,
    Flow,
    FlowStep,
    Group,
    HappyStep,
    ProjectModel,
    SubFlow,
    UseCase,
)
from coyodex.viewer.recents import RecentsStore
from coyodex.viewer.serve import Handler, build_projects

from test_impact import EXTENTS, GUILD_V1, commit, make_model


# --- builders -------------------------------------------------------------------

def make_ripple_model() -> ProjectModel:
    return ProjectModel(
        title="t", commit="abc1234",
        subsystems=[Group(id="S0", name="Root"), Group(id="S1", name="Svc", parent="S0")],
        subdomains=[Group(id="SD1", name="Core")],
        components=[Component(id="C1", name="A", subsystem="S1"),
                    Component(id="C2", name="B", subsystem="S1"),
                    Component(id="C3", name="Far")],
        deps=[Dep(id="D1", name="Store")],
        entities=[Entity(id="E1", name="Guild", subdomain="SD1",
                         relations=[EntityRelation(verb="has", target="E2")]),
                  Entity(id="E2", name="Member", subdomain="SD1")],
        use_cases=[UseCase(id="UC1", name="Do a thing"), UseCase(id="UC2", name="Other")],
        happy_path=[HappyStep(id="HP1", title="Do a thing", uc="UC1")],
        flows=[Flow(uc="UC1", title="t", steps=[
                   FlowStep(n=1, src="Member", dst="C1", phrase="asks"),
                   FlowStep(n=2, src="C1", dst="E1", phrase="stores"),
                   FlowStep(n=3, src="C1", dst="D1", phrase="notifies")]),  # no C1→D1 edge → warning
               Flow(uc="UC2", title="t2", steps=[
                   FlowStep(n=1, src="Member", dst="C3", phrase="pings")])],
        edges=[Edge(src="C1", verb="persists", dst="E1", where="a.py:5"),
               Edge(src="C2", verb="reads", dst="E1", where="b.py:5"),
               Edge(src="C1", verb="calls", dst="C2", where="a.py:9")],
    )


def make_core(hits: list[DirectHit], path: str = "a.py") -> ImpactCore:
    return ImpactCore(pin="p" * 7, base="b" * 7, target="WORKTREE",
                      files=[ImpactFile(path=path, p_path=path, status="M", hits=hits)])


def make_hit(eid: str, kind: str, resolution: str = "symbol", change: str = "modified",
             territory: bool = False, owner: str | None = None) -> DirectHit:
    return DirectHit(eid, kind, "a.py", change, resolution, "source",
                     owner=owner, territory=territory)


def impact_of(result: dict, eid: str) -> dict:
    assert eid in result["impacts"], f"{eid} not impacted: {sorted(result['impacts'])}"
    return result["impacts"][eid]


# --- the rules, one by one ---------------------------------------------------------

def test_component_hit_ripples_structure_behavior_data() -> None:
    r = build_impact_result(make_ripple_model(), make_core([make_hit("C1", "component")]))
    assert impact_of(r, "S1")["strength"] == R_STRUCTURAL and impact_of(r, "S1")["distance"] == 1
    assert impact_of(r, "S0")["strength"] == R_STRUCTURAL          # parent chain walks up
    assert impact_of(r, "UC1")["strength"] == R_BEHAVIORAL
    assert impact_of(r, "HP1")["via"][-1] == {"from": "UC1", "relation": "happy-path"}
    assert impact_of(r, "E1")["strength"] == R_DATA                # persists → on by default
    assert "C2" not in r["impacts"]                                # call-graph off by default
    assert "UC2" not in r["impacts"]                               # other flows untouched


def test_data_ripple_does_not_chain() -> None:
    # C1 → E1 (data). E1's other relations (E2, readers) must NOT re-fire from the rippled E1.
    r = build_impact_result(make_ripple_model(), make_core([make_hit("C1", "component")]),
                            RippleOptions(reads=True, entity_graph=True))
    assert "E2" not in r["impacts"]                                # rippled E1 never re-fires


def test_entity_hit_reverse_data_and_subdomain() -> None:
    r = build_impact_result(make_ripple_model(), make_core([make_hit("E1", "entity")]))
    assert impact_of(r, "SD1")["strength"] == R_STRUCTURAL
    assert impact_of(r, "C1")["via"] == [{"from": "E1", "relation": "persisted-by"}]
    assert "C2" not in r["impacts"]                                # reads → opt-in
    assert "E2" not in r["impacts"]                                # entity graph → opt-in
    r2 = build_impact_result(make_ripple_model(), make_core([make_hit("E1", "entity")]),
                             RippleOptions(reads=True, entity_graph=True))
    assert impact_of(r2, "C2")["strength"] == R_DATA
    assert impact_of(r2, "E2")["strength"] == R_DATA


def test_edge_hit_endpoints_and_pair_flows() -> None:
    r = build_impact_result(make_ripple_model(),
                            make_core([make_hit("edge:C1>persists>E1", "edge", "line")]))
    assert impact_of(r, "C1")["via"] == [{"from": "edge:C1>persists>E1", "relation": "edge-endpoint"}]
    assert impact_of(r, "E1")["cause"] == "ripple"
    assert impact_of(r, "UC1")["via"][0]["relation"] == "flow-pair"  # step 2 matches the pair


def test_step_hit_ripples_endpoints_and_its_use_case_only() -> None:
    # A directly-hit flow step (its own `where` changed) ripples to its two element endpoints and
    # to exactly ITS use case + HP steps — no pair-level over-approximation like the edge branch.
    r = build_impact_result(make_ripple_model(),
                            make_core([make_hit("step:UC1:2", "flow_step", "line")]))
    assert impact_of(r, "C1")["via"] == [{"from": "step:UC1:2", "relation": "step-endpoint"}]
    assert impact_of(r, "E1")["cause"] == "ripple"
    assert impact_of(r, "UC1")["strength"] == R_BEHAVIORAL
    assert impact_of(r, "UC1")["via"][0]["relation"] == "flow-step"
    assert impact_of(r, "HP1")["via"][-1] == {"from": "UC1", "relation": "happy-path"}
    assert "UC2" not in r["impacts"]                    # other flows untouched
    assert type_of("step:UC1:2") == "flow_steps"
    assert "step:UC1:2" in r["byType"]["flow_steps"]


def make_subflow_ripple_model() -> ProjectModel:
    """make_ripple_model + one sub-flow (touching C2, which no flow names directly) referenced by
    BOTH use cases."""
    m = make_ripple_model()
    m.subflows = [SubFlow(id="SF1", name="Persist",
                          steps=[FlowStep(n=1, src="C2", dst="E1", phrase="writes",
                                          where="sf.py:5")])]
    m.flows[0].steps.append(FlowStep(n=4, src="C1", dst="E1", subflow="SF1"))
    m.flows[1].steps.append(FlowStep(n=2, src="C3", dst="E1", subflow="SF1"))
    return m


def test_subflow_step_hit_ripples_every_referencing_use_case() -> None:
    r = build_impact_result(make_subflow_ripple_model(),
                            make_core([make_hit("step:SF1:1", "flow_step", "line")]))
    assert impact_of(r, "C2")["via"] == [{"from": "step:SF1:1", "relation": "step-endpoint"}]
    assert impact_of(r, "UC1")["via"][0]["relation"] == "flow-step"
    assert impact_of(r, "UC2")["via"][0]["relation"] == "flow-step"   # both referencing UCs reached
    assert impact_of(r, "HP1")["via"][-1] == {"from": "UC1", "relation": "happy-path"}
    assert type_of("step:SF1:1") == "flow_steps"


def test_component_touched_only_inside_subflow_ripples_behaviorally() -> None:
    # C2 appears in NO flow directly — only in SF1's steps. Hitting C2 must still reach both
    # referencing use cases (the _Maps expansion), or sub-flow content would be impact-invisible.
    r = build_impact_result(make_subflow_ripple_model(),
                            make_core([make_hit("C2", "component")]))
    assert impact_of(r, "UC1")["strength"] == R_BEHAVIORAL
    assert impact_of(r, "UC2")["strength"] == R_BEHAVIORAL


def test_step_hit_with_actor_endpoint_skips_the_role() -> None:
    # An actor step ("Member" → C1): the Role has no graph node, so only the element endpoint ripples.
    r = build_impact_result(make_ripple_model(),
                            make_core([make_hit("step:UC1:1", "flow_step", "line")]))
    assert impact_of(r, "C1")["via"] == [{"from": "step:UC1:1", "relation": "step-endpoint"}]
    assert "Member" not in r["impacts"]
    assert impact_of(r, "UC1")["via"][0]["relation"] == "flow-step"


def test_entry_point_hit_routes_via_component() -> None:
    r = build_impact_result(make_ripple_model(),
                            make_core([make_hit("ep:a.py:3", "entry_point", owner="C1")]))
    assert impact_of(r, "C1")["via"] == [{"from": "ep:a.py:3", "relation": "entry-point"}]
    assert impact_of(r, "UC1")["via"][0] == {"from": "ep:a.py:3", "relation": "entry-point"}


def test_callgraph_opt_in_depth_and_decay() -> None:
    r = build_impact_result(make_ripple_model(), make_core([make_hit("C1", "component")]),
                            RippleOptions(callgraph=True, callgraph_depth=1))
    assert impact_of(r, "C2")["strength"] == R_CALLGRAPH and impact_of(r, "C2")["distance"] == 1
    assert "C3" not in r["impacts"]                                # unlinked; depth capped anyway


def test_territory_direct_group_upgraded_by_member_ripple() -> None:
    hits = [make_hit("C1", "component"),
            make_hit("S1", "group", resolution="file", territory=True)]
    r = build_impact_result(make_ripple_model(), make_core(hits))
    s1 = impact_of(r, "S1")
    assert s1["cause"] == "direct"                                 # the territory hit stays visible
    assert s1["strength"] == R_STRUCTURAL                          # ...but strength = member ripple


def test_change_severity_consolidation_and_file_scope() -> None:
    core = ImpactCore(pin="p" * 7, base="b" * 7, target="WORKTREE", files=[
        ImpactFile(path="a.py", p_path="a.py", status="M",
                   hits=[make_hit("C1", "component", change="modified")]),
        ImpactFile(path="c.py", p_path="c.py", status="D",
                   hits=[make_hit("C1", "component", resolution="file", change="deleted")])])
    r = build_impact_result(make_ripple_model(), core)
    assert impact_of(r, "C1")["change"] == "deleted"               # severity: deleted > modified
    assert sorted(impact_of(r, "C1")["files"]) == ["a.py", "c.py"]
    scoped = build_impact_result(make_ripple_model(), core, file_scope="a.py")
    assert scoped["impacts"]["C1"]["change"] == "modified"         # the other file is out of scope
    assert [f["path"] for f in scoped["files"]] == ["a.py"]


def test_unmatched_flow_step_warning_and_counts() -> None:
    r = build_impact_result(make_ripple_model(), make_core([make_hit("C1", "component")]))
    assert any("no backbone edge" in w for w in r["warnings"])
    assert r["counts"]["direct"] == 1 and r["counts"]["ripple"] >= 4
    assert r["byType"]["components"] == ["C1"]
    assert type_of("edge:C1>x>E1") == "edges" and type_of("SD3") == "subdomains"


# --- the endpoint (golden git fixture over HTTP) --------------------------------------

def test_api_impact_endpoint_end_to_end() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        pin = commit(root, {"svc/guild.py": GUILD_V1, "README.md": "hi\n"}, msg="pin")
        model = make_model(pin)
        # a flow step anchored in the edit's call-site window — the API must surface the step hit
        model.use_cases = [UseCase(id="UC1", name="Do")]
        model.flows = [Flow(uc="UC1", title="Do", steps=[
            FlowStep(n=2, src="C1", dst="D1", phrase="stores", where="svc/guild.py:8")])]
        from coyodex.model import to_canonical_json
        (root / ".coyodex").mkdir()
        (root / ".coyodex" / "project-map.json").write_text(to_canonical_json(model),
                                                            encoding="utf-8")
        (root / ".coyodex" / "preindex.json").write_text(
            json.dumps({"symbols": {"extents": {
                p: [list(e) for e in rows] for p, rows in EXTENTS.items()}}}),
            encoding="utf-8")
        (root / "svc/guild.py").write_text(GUILD_V1.replace("self.name = None", "self.name = ''"),
                                           encoding="utf-8")

        projects = build_projects([str(root)])
        slug = next(iter(projects))
        Handler.store = RecentsStore()
        Handler.projects = projects
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
            conn.request("GET", f"/p/{slug}/api/impact?target=WORKTREE")
            resp = conn.getresponse()
            assert resp.status == 200
            payload = json.loads(resp.read())
            assert payload["impacts"]["E1"]["resolution"] == "symbol"
            assert payload["impacts"]["E1"]["cause"] == "direct"
            assert payload["impacts"]["step:UC1:2"]["cause"] == "direct"   # step hit over the API
            assert "step:UC1:2" in payload["byType"]["flow_steps"]
            assert payload["spec"]["target"] == "WORKTREE"
            # bad ref → 400, not a 500/crash
            conn.request("GET", f"/p/{slug}/api/impact?base=--upload-pack=x")
            assert conn.getresponse().status == 400
        finally:
            httpd.shutdown()
