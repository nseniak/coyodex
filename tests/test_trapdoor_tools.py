#!/usr/bin/env python3
"""L2 — the tools run against the trapdoor fixture and its golden map.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_trapdoor_tools.py
    pytest tests/test_trapdoor_tools.py

**What this layer adds over the 894 tests that came before it.** Those build a synthetic model
in memory (`make_deploy_model()` and friends) and assert what a function returns. That is the
right shape for logic, and it leaves three holes this file closes:

  1. `coyodex preindex --report` had ZERO tests among the 894 — not one invocation. The
     `--root`-is-ignored defect lived there undisturbed.
  2. No test fed an "E is stored in D" claim into `anchor-drift`. That claim shape is exactly
     where the store false-positive lives: on one live map 9 of 13 drift findings were it, and
     the lead hand-wrote a filter script to strip them.
  3. Every fixture was a toy. Here the input is a REAL tree (`eval/fixtures/trapdoor/`) and a
     REAL assembled map of it (`golden/project-map.json`), so a check that only works on
     three hand-made rows fails honestly.

Every test opens by resolving its trap from `traps.yaml` — the one source of truth — so a test
can never assert a trap the manifest does not declare, and a renamed trap fails loudly instead
of quietly passing against nothing.

**Design gaps are FLAGGED, not fixed.** Where the current behaviour is *specified* by an
existing test rather than missed by it, the test below pins the behaviour and says so in its
docstring. `test_infra_role_band_prefers_the_edge_verb_over_the_declared_dep_kind` is the
example: it documents a real design gap and deliberately asserts today's answer.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex import anchor_drift as ad
from coyodex import preindex
from coyodex.audit_model import l2_worklist_model
from coyodex.model import ProjectModel, load_model
from coyodex.preindex_lib import expected_components, iter_source_files
from coyodex.validate_model import validate_model
from coyodex.views import model_to_graph

from trapdoor import FIXTURE, GOLDEN_MAP, fixture_text, fixture_tracked_paths, line_of, trap


# --- builders -------------------------------------------------------------------------

def make_golden_model() -> ProjectModel:
    """The frozen golden map — a real `coyodex assemble` output over the real fixture tree."""
    return load_model(GOLDEN_MAP.read_text(encoding="utf-8"))


def make_golden_warnings() -> list[str]:
    """Every advisory `validate --check-sources` raises on the golden map, against the real tree."""
    _problems, warnings = validate_model(make_golden_model(), GOLDEN_MAP, check_sources=True,
                                         repo_root=FIXTURE)
    return warnings


def make_preindex(tmp: Path, root: Path = FIXTURE) -> Path:
    """Build a real pre-index of a real tree and return the artifact path."""
    out = tmp / "preindex.json"
    assert preindex.main(["--root", str(root), "--out", str(out)]) == 0
    return out


def make_vote(claim: str, grounded: bool, evidence: str) -> dict[str, object]:
    """One grounding skeptic's verdict, in the shape `anchor-drift --verdicts` consumes."""
    return {"claim": claim, "grounded": grounded, "evidence": evidence}


def make_store_claim(model: ProjectModel, entity_id: str) -> tuple[str, str]:
    """(claim text, stored anchor) for the audit worklist's "En is stored in Dn" item.

    The claim shape no test had ever fed into `anchor-drift`. Resolved from the real worklist
    rather than hand-typed, so a change to the claim wording fails here instead of silently
    making the drift check unreachable."""
    for item in l2_worklist_model(model):
        if item.claim.startswith(f"{entity_id} (") and " is stored in " in item.claim:
            return item.claim, item.anchor or ""
    raise AssertionError(f"no 'is stored in' worklist claim for {entity_id}")


def make_model_without_edge(src: str, verb: str, dst: str) -> ProjectModel:
    """The golden map minus one backbone edge — the cheap way to ask 'what does validate say
    when this edge is missing?' without hand-building a second map."""
    doc = json.loads(GOLDEN_MAP.read_text(encoding="utf-8"))
    doc["edges"] = [e for e in doc["edges"]
                    if not (e["src"] == src and e["verb"] == verb and e["dst"] == dst)]
    return load_model(json.dumps(doc))


def warnings_of(model: ProjectModel) -> list[str]:
    _problems, warnings = validate_model(model)
    return warnings


def has_warning(warnings: list[str], *needles: str) -> bool:
    return any(all(n in w for n in needles) for w in warnings)


# --- the fixture is intact -------------------------------------------------------------

def test_the_fixture_is_tracked_so_the_walk_can_see_it():
    """`iter_source_files` prefers `git ls-files`; an untracked fixture file is INVISIBLE to
    every measurement in this file. Assert the whole fixture is tracked, and that git reports
    it fixture-relative (which is what lets `--root <fixture>` treat it as a repo root)."""
    tracked = fixture_tracked_paths()
    assert "traps.yaml" in tracked and "src/auth/gate.py" in tracked, tracked[:10]
    assert not any(p.startswith("eval/") for p in tracked), (
        "git reported repo-relative paths from inside the fixture — every --root measurement "
        f"here would be reading the wrong tree: {[p for p in tracked if p.startswith('eval/')][:3]}")


def test_every_trap_names_paths_that_exist():
    """A trap whose `where` has gone stale asserts nothing. Cheapest possible guard on the
    manifest, and the reason `traps.yaml` carries paths at all."""
    from trapdoor import load_traps
    missing = [f"{t.id}: {p}" for t in load_traps() for p in t.paths if not p.exists()]
    assert not missing, "traps.yaml names paths that do not exist:\n  " + "\n  ".join(missing)


def test_every_trap_marked_covered_is_actually_asserted_by_a_test():
    """The manifest claims coverage; this proves it. A trap that says `covered: true` must be
    named by a test in its declared layer — either through `trap("Xn")` here, or by id in the
    L1 file. Without this, the coverage table in the hand-off is a promise nobody checked, and
    a deleted test turns into silent coverage loss.

    The converse is checked too: a test that resolves a trap the manifest marks `covered: false`
    means the manifest is stale."""
    from trapdoor import load_traps
    l2_src = Path(__file__).read_text(encoding="utf-8")
    l1_src = (Path(__file__).parent / "test_method_contract.py").read_text(encoding="utf-8")
    unasserted: list[str] = []
    stale: list[str] = []
    for t in load_traps():
        asserted = (f'trap("{t.id}")' in l2_src) or (f"trap {t.id} " in l1_src)
        if t.covered and not asserted:
            unasserted.append(f"{t.id} ({t.layer}) claims coverage but no test names it")
        if not t.covered and asserted:
            stale.append(f"{t.id} is asserted but the manifest says covered: false")
    assert not unasserted and not stale, "\n  ".join(unasserted + stale)


def test_the_golden_map_has_no_blocking_problems():
    """The golden map is a real assemble output and must stay gate-clean, or every assertion
    below is measuring a broken map instead of a trapped one. Its WARNINGS are the traps."""
    problems, _warnings = validate_model(make_golden_model(), GOLDEN_MAP, check_sources=True,
                                         repo_root=FIXTURE)
    assert problems == [], "golden map has blocking validate problems:\n  " + "\n  ".join(problems)


# --- preindex --report: zero tests among the 894 --------------------------------------

def test_preindex_report_prints_the_weight_tree_and_per_slice_e(capsys=None):
    """`--report` is the hand-off the method tells every build to use instead of hand-parsing
    the JSON — and it had no test at all. This one runs it end to end on the real fixture."""
    with tempfile.TemporaryDirectory() as td:
        artifact = make_preindex(Path(td))
        out = _capture(lambda: preindex.main(["--report", "--in", str(artifact)]))
    assert "WEIGHT TREE" in out and "GRANULARITY" in out and "COVERAGE" in out
    assert "per-directory E" in out
    assert "src" in out and "web" in out


def test_preindex_report_errors_cleanly_when_there_is_no_pre_index():
    with tempfile.TemporaryDirectory() as td:
        code = preindex.main(["--report", "--in", str(Path(td) / "nope.json")])
    assert code == 2


def test_preindex_report_rejects_a_non_integer_depth():
    with tempfile.TemporaryDirectory() as td:
        artifact = make_preindex(Path(td))
        assert preindex.main(["--report", "--in", str(artifact), "--depth", "deep"]) == 2


def test_preindex_report_ignores_root_and_reports_the_cwd_repo():
    """THE DEFECT, pinned. `--report` reads `--in` (default `.coyodex/preindex.json`, resolved
    against the CWD) and never looks at `--root`, so pointing it at another repo silently
    reports the current one under the other repo's name.

    This test asserts TODAY'S behaviour so the bug is visible and cannot regress unnoticed; the
    static twin in test_method_contract.py states it as a contract violation. The fix belongs to
    the maintainer, not to this suite — see tools/coyodex/preindex.py:302 (`report()` reads
    `--in`) against tools/coyodex/preindex.py:398 (`main()` reads `--root`)."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        other = tmp / "other-repo" / ".coyodex"
        other.mkdir(parents=True)
        (other / "preindex.json").write_text(json.dumps({
            "root": "/other-repo", "weight": {"path": ".", "loc": 1, "file_count": 1, "churn": 0,
                                              "lang": "python", "children": []},
            "granularity": {"expected_components": 999, "band": [1, 2], "per_dir": {}},
            "coverage": {}, "symbols": {}}))
        cwd = tmp / "cwd-repo" / ".coyodex"
        cwd.mkdir(parents=True)
        (cwd / "preindex.json").write_text(json.dumps({
            "root": "/cwd-repo", "weight": {"path": ".", "loc": 2, "file_count": 2, "churn": 0,
                                            "lang": "python", "children": []},
            "granularity": {"expected_components": 7, "band": [4, 10], "per_dir": {}},
            "coverage": {}, "symbols": {}}))
        here = Path.cwd()
        try:
            import os
            os.chdir(tmp / "cwd-repo")
            out = _capture(lambda: preindex.main(["--report", "--root", str(tmp / "other-repo")]))
        finally:
            import os
            os.chdir(here)
    assert "/cwd-repo" in out, out[:400]
    assert "E=7" in out, "the CWD's own pre-index was reported"
    assert "/other-repo" not in out and "E=999" not in out, (
        "if this now fails, --report has learned to honour --root — good; delete this test and "
        "flip the contract assertion in test_method_contract.py")


def test_preindex_report_names_the_ignore_patterns_when_a_tree_was_narrowed():
    """The ignore file is the one input both the pre-index and the coverage check read, so
    `--report` must NAME the patterns, not just count them. Exercised on a real narrowed tree."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        repo = tmp / "repo"
        (repo / "src").mkdir(parents=True)
        (repo / "junk").mkdir(parents=True)
        (repo / "src" / "a.py").write_text("def a():\n    return 1\n")
        (repo / "junk" / "b.py").write_text("def b():\n    return 2\n")
        (repo / ".coyodex").mkdir()
        (repo / ".coyodex" / ".ignore").write_text("junk/\n")
        artifact = make_preindex(tmp, root=repo)
        out = _capture(lambda: preindex.main(["--report", "--in", str(artifact)]))
    assert "IGNORED BY .coyodex/.ignore" in out and "junk/" in out


# --- A: anchors ------------------------------------------------------------------------

def test_a1_an_auth_anchor_on_the_def_header_is_flagged_and_the_raise_line_is_not():
    """A1 — the enforcing statement sits ~30 lines below the header. Both anchors RESOLVE, so
    existence checking cannot tell them apart; only the operative-line classifier can."""
    t = trap("A1")
    assert t.layer == "L2"
    header = line_of("src/auth/gate.py", "def require_write(")
    raising = line_of("src/auth/gate.py", "raise AuthError(")
    assert raising - header > 20, "the trap needs real distance between header and enforcement"

    doc = json.loads(GOLDEN_MAP.read_text(encoding="utf-8"))
    doc["security"][0]["source"] = f"src/auth/gate.py:{header}"
    drifted = load_model(json.dumps(doc))
    _p, w = validate_model(drifted, GOLDEN_MAP, check_sources=True, repo_root=FIXTURE)
    assert has_warning(w, "src/auth/gate.py", "function header"), w

    honest = make_golden_model()          # golden already anchors the `raise`
    _p2, w2 = validate_model(honest, GOLDEN_MAP, check_sources=True, repo_root=FIXTURE)
    assert not has_warning(w2, f"src/auth/gate.py:{raising}"), w2


def test_a2_a_prose_lifecycle_passes_the_state_source_check_because_the_names_are_in_the_file():
    """A2 — five states described in a DOCSTRING, five declared in an enum.

    A DESIGN GAP, found by this fixture and flagged not fixed. `check_state_sources_model`
    verifies that each state NAME APPEARS in the cited file. A docstring paragraph naming the
    phases contains all five names, so an entirely invented lifecycle cited at that docstring
    passes `--check-sources` clean. The method says the `source` must point at "the enum /
    constants / dispatch block that DECLARES the states, never a docstring or a class header"
    (method.md:800) — but nothing mechanical enforces the *declares* half, only the *appears*
    half. That is precisely why the Phase-4 skeptics refuted 5 of ~11 machines on a live build
    and the deterministic pass did not.

    Both halves are pinned: the gap (prose passes) and the working half (a name that is not in
    the file at all is caught)."""
    trap("A2")
    prose = fixture_text("src/lifecycle/escalation.py")
    assert all(s in prose for s in ("dormant", "warming", "hot", "held", "abandoned"))
    assert "class TicketState" in fixture_text("src/lifecycle/states.py")
    assert "enum" not in prose.split('"""', 2)[2], "the prose lifecycle must have no declaration"

    def states_warnings(names: list[str], source: str) -> list[str]:
        doc = json.loads(GOLDEN_MAP.read_text(encoding="utf-8"))
        for ent in doc["entities"]:
            if ent["id"] == "E1":
                ent["states"] = {"states": names,
                                 "transitions": [{"src": names[0], "dst": names[1]}],
                                 "source": source}
        _p, w = validate_model(load_model(json.dumps(doc)), GOLDEN_MAP, check_sources=True,
                               repo_root=FIXTURE)
        return w

    docstring_line = line_of("src/lifecycle/escalation.py", "The escalation lifecycle runs")
    invented = states_warnings(["dormant", "warming", "hot", "held", "abandoned"],
                               f"src/lifecycle/escalation.py:{docstring_line}")
    assert not has_warning(invented, "do not appear in the cited source"), (
        "if this now fails the check has learned to require a DECLARATION, not a mention — "
        "good; update this docstring and flip the assertion")

    fabricated = states_warnings(["dormant", "smouldering", "combusting"],
                                 f"src/lifecycle/escalation.py:{docstring_line}")
    assert has_warning(fabricated, "do not appear in the cited source"), fabricated


def test_a3_a_store_claim_grounded_at_the_class_definition_reads_as_drift():
    """A3 — THE STORE FALSE POSITIVE, and the claim shape no test had ever exercised.

    The entity is DEFINED in `src/domain/models.py` and WRITTEN in `src/store/ticket_repo.py`.
    A skeptic asked "where is Ticket stored?" reports the definition (the only place the type
    appears by name), so `anchor-drift` compares a definition line against a write line and
    calls it drift — even though nothing about the map is wrong. On one live map 9 of 13 drift
    findings were this class, and the lead hand-wrote a filter script to strip them.

    Note what the drift record says: `same_file` is False. Different files is the tell that
    separates this class from a real intra-file anchor slip, and it is the discriminator any
    future filter should key on rather than being re-derived by hand."""
    trap("A3")
    model = make_golden_model()
    claim, stored = make_store_claim(model, "E1")
    assert "is stored in" in claim and "src/domain/models.py" in stored

    write_line = line_of("src/store/ticket_repo.py", "self._tickets.replace_one(")
    def_line = line_of("src/domain/models.py", "class Ticket:")

    # The skeptics report the DEFINITION — the honest answer to "where is this type?".
    verdicts = [make_vote(claim, True, f"src/domain/models.py:{def_line}")] * 2
    assert ad.drift_findings(l2_worklist_model(model), verdicts, tolerance=2) == [], (
        "a claim anchored at the definition and grounded at the definition is NOT drift")

    # Now the same claim with the write site stored — the shape a map gets when the store
    # claim is anchored at the operative write instead of the type.
    doc = json.loads(GOLDEN_MAP.read_text(encoding="utf-8"))
    for ent in doc["entities"]:
        if ent["id"] == "E1":
            ent["source"] = f"src/store/ticket_repo.py:{write_line}"
    moved = load_model(json.dumps(doc))
    claim2, _ = make_store_claim(moved, "E1")
    records = ad.drift_records(l2_worklist_model(moved),
                              [make_vote(claim2, True, f"src/domain/models.py:{def_line}")] * 2,
                              tolerance=2)
    assert len(records) == 1, records
    assert records[0]["same_file"] is False, (
        "the store false positive is a CROSS-FILE drift; `same_file` is the discriminator a "
        "filter should use instead of being re-derived per map")
    assert records[0]["corrected"] == f"src/domain/models.py:{def_line}"


def test_a4_an_edge_anchored_at_an_import_is_flagged():
    """A4 — an import line reads like a call site. It resolves, so only the operative-line
    classifier catches it."""
    trap("A4")
    imp = line_of("src/api/passthrough_controller.py", "from src.clients.analytics_factory import")
    doc = json.loads(GOLDEN_MAP.read_text(encoding="utf-8"))
    for e in doc["edges"]:
        if e["src"] == "C1" and e["dst"] == "C3":
            e["where"] = f"src/api/passthrough_controller.py:{imp}"
    _p, w = validate_model(load_model(json.dumps(doc)), GOLDEN_MAP, check_sources=True,
                           repo_root=FIXTURE)
    assert has_warning(w, "src/api/passthrough_controller.py", "import"), w


# --- O: overclaims ---------------------------------------------------------------------

def test_o1_the_datastore_edge_belongs_to_the_component_holding_the_operative_line():
    """O1 — transitive attribution. The controller forwards; the repository writes. The map
    must attribute the store edge where the operative line lives."""
    trap("O1")
    model = make_golden_model()
    store_writers = {e.src for e in model.edges if e.dst == "D1"}
    assert store_writers == {"C4"}, store_writers
    assert "replace_one" not in fixture_text("src/api/passthrough_controller.py")
    assert "replace_one" in fixture_text("src/store/ticket_repo.py")


def test_o2_the_ownership_edge_is_the_repositorys_not_the_controllers():
    """O2 — the write controller calls `.save()` and so LOOKS like the system of record."""
    trap("O2")
    model = make_golden_model()
    owners = {e.src for e in model.edges
              if e.dst == "E1" and e.verb.lower() in ("persists", "writes")}
    assert owners == {"C4"}, owners
    assert ".save(" in fixture_text("src/api/record_controller.py"), "the temptation is real"


def test_o3_the_client_factory_emits_nothing_the_plugins_do():
    """O3 — constructs != persists. The factory builds handles; the plugins send."""
    trap("O3")
    model = make_golden_model()
    emitters = {e.src for e in model.edges if e.dst == "D4" and e.verb.lower() == "emits"}
    assert "C12" not in emitters, "the factory must not carry its callers' traffic"
    assert emitters and all(c.startswith("C") for c in emitters)
    assert "enqueue" not in fixture_text("src/clients/analytics_factory.py").split("def build_")[1]


def test_o4_a_dead_import_backs_no_edge():
    """O4 — two types imported and never used. No edge may rest on them."""
    trap("O4")
    text = fixture_text("src/clients/dead_import.py")
    assert "import ErrorClient" in text or "ErrorClient" in text
    body = text.split("RETRY_HEADER", 1)[1]
    assert "ErrorClient" not in body and "TicketState" not in body, (
        "the import is supposed to be dead; if the fixture started using it the trap is gone")
    model = make_golden_model()
    assert not any(e.src == "C13" and e.dst == "D5" for e in model.edges)


# --- M: messaging ----------------------------------------------------------------------

def test_m1_a_channel_with_publishers_and_no_consumers_warns_and_a_consumed_one_does_not():
    trap("M1")
    w = make_golden_warnings()
    assert has_warning(w, "ticket.state.changed", "no consumers recorded"), w
    assert has_warning(w, "escalation.paged", "no consumers recorded"), w
    assert not has_warning(w, "ticket.comment.added", "no consumers recorded"), w


def test_m2_the_tree_really_holds_both_spellings_of_one_channel():
    """M2 — the catalog must carry ONE row for a channel the code names two ways. The map is
    right today; this pins the TREE so the trap cannot silently disappear from the fixture."""
    trap("M2")
    assert '"ticket.state.changed"' in fixture_text("src/messaging/publisher.py")
    assert '"ticket-state-changed"' in fixture_text("src/plugins/p03/handler.py")
    names = [row.name for row in make_golden_model().messaging]
    assert names.count("ticket.state.changed") == 1
    assert "ticket-state-changed" not in names, (
        "the hyphenated spelling is the SAME channel; a second row is the duplicated-row defect")


def test_m3_a_catalog_with_no_payload_on_any_channel_warns():
    """M3 — every channel body here is an ad-hoc dict, so `payload` is honestly empty. validate
    still warns, and there is NO recordable escape for it (the L1 audit carries that finding)."""
    trap("M3")
    assert not any(row.payload for row in make_golden_model().messaging)
    assert has_warning(make_golden_warnings(), "names a `payload`"), make_golden_warnings()


def test_m4_a_publisher_with_no_backbone_edge_to_the_broker_is_reported():
    """M4 — the publisher reaches the broker through an injected transport, so it names no
    broker library and the `C -> broker` edge is easy to forget. Without it the component is
    drawn wired to nothing however well its purpose describes the traffic."""
    trap("M4")
    assert "Transport" in fixture_text("src/messaging/publisher.py")
    assert not has_warning(make_golden_warnings(), "carry no backbone edge")
    stripped = make_model_without_edge("C8", "emits", "D2")
    assert has_warning(warnings_of(stripped), "carry no backbone edge", "C8"), warnings_of(stripped)


# --- D: deployment ---------------------------------------------------------------------

def test_d1_a_base_class_untagged_where_its_subclass_runs_is_not_reported_today():
    """D1 — a base class not tagged to run where its subclass runs.

    A DESIGN GAP, flagged not fixed. `_inheritance_runs_in_warnings` skips the pair when the
    BASE has no `runs_in` at all (tools/coyodex/validate_model.py:1224 — `if not src or not dst:
    continue`), so it fires on a partially-tagged base and stays silent on a completely untagged
    one. The completely-untagged case is the one a build actually produces: the subclass owns a
    directory and gets tagged, the abstract base sits in a shared module and is forgotten.

    This test asserts BOTH: today's silence on the untagged base, and the warning on the
    partially-tagged one — so the gap is visible and the working half cannot regress."""
    trap("D1")
    model = make_golden_model()
    base = next(c for c in model.components if c.id == "C10")
    child = next(c for c in model.components if c.id == "C11")
    assert base.runs_in == [] and child.runs_in == ["worker"]
    assert not has_warning(warnings_of(model), "is extended by"), (
        "if this now fails the gap is closed — good; update the docstring and drop this half")

    doc = json.loads(GOLDEN_MAP.read_text(encoding="utf-8"))
    for c in doc["components"]:
        if c["id"] == "C10":
            c["runs_in"] = ["api"]        # tagged somewhere, but not where the subclass runs
    partial = warnings_of(load_model(json.dumps(doc)))
    assert has_warning(partial, "C10", "not tagged to run there"), partial


def test_d2_untagged_units_alongside_tagged_ones_are_reported_as_a_claim():
    """D2 — `api` and `worker` carry no compose profile, so they claim EVERY environment by
    omission. The mixed state is what validate must surface: all-or-nothing checks cannot see it."""
    trap("D2")
    text = fixture_text("docker-compose.yml")
    assert 'profiles: ["dev"]' in text and "\n  api:" in text
    assert has_warning(make_golden_warnings(), "carry no `variants` while others do"), \
        make_golden_warnings()


def test_d3_the_three_profile_environment_axis_survives_into_the_map():
    """D3 — a real dev/cloud/standalone axis. Flattening it loses information a live build lost."""
    trap("D3")
    model = make_golden_model()
    assert sorted(model.environments) == ["cloud", "dev", "standalone"]
    tagged = {d.unit: [v.env for v in d.variants] for d in model.deployment if d.variants}
    assert tagged == {"web-dev": ["dev"], "standalone": ["standalone"]}, tagged
    for row in model.deployment:
        for v in row.variants:
            assert v.source, f"{row.unit}/{v.env} is an inferred tag dressed as a fact"


def test_d4_a_baked_asset_is_a_unit_only_where_it_runs_as_a_process():
    """D4 — `Dockerfile.standalone` builds the frontend and COPYs the bundle in. The bundle is
    SERVED BY that unit, never RUN AS one, so the frontend is a unit in `dev` alone."""
    trap("D4")
    dockerfile = fixture_text("Dockerfile.standalone")
    assert "npm run build" in dockerfile and "COPY --from=web" in dockerfile
    model = make_golden_model()
    frontend = [d for d in model.deployment if d.unit == "web-dev"]
    assert len(frontend) == 1 and [v.env for v in frontend[0].variants] == ["dev"]
    assert not any(d.unit.startswith("web") and any(v.env in ("cloud", "standalone")
                                                    for v in d.variants)
                   for d in model.deployment), "the baked bundle became its own process box"


def test_d5_an_infra_unit_sharing_a_dependency_name_is_not_an_unlinked_unit():
    """D5 — the compose service `search` and the dependency `OpenSearch` are the same thing.
    The unit hosts no code, so it must render through its dependency box; validate must not
    report it as an unlinked unit, and it must not appear as a process box."""
    trap("D5")
    assert "\n  search:" in fixture_text("docker-compose.yml")
    model = make_golden_model()
    assert "search" not in {d.unit for d in model.deployment}, (
        "infra the app merely talks to is a dependency, not a deployment[] process box")
    assert any(d.name == "OpenSearch" for d in model.deps)
    assert not has_warning(make_golden_warnings(), "run no traced component")


def test_d6_one_runs_in_record_masks_the_whole_deployment_family_but_reports_the_count():
    """D6 — the `runs-in` literal silences unit naming, formula-fill, unlinked units, thread
    hosts AND variant tagging together, while the justification behind it usually covers one.

    The safe behaviour is what this pins: the detail goes, the COUNT stays. Suppression you
    cannot see is indistinguishable from having no findings."""
    trap("D6")
    before = [w for w in make_golden_warnings() if "variants" in w or "runs_in" in w]
    assert before, "the fixture must actually trip the deployment family for this to mean anything"

    doc = json.loads(GOLDEN_MAP.read_text(encoding="utf-8"))
    for extra in doc["extras"]:
        if extra["heading"] == "Balance exceptions":
            extra["body"] += "\n- runs-in: the api and worker units are genuinely ungated."
    after = warnings_of(load_model(json.dumps(doc)))
    assert has_warning(after, "suppressed by the recorded `runs-in` exception"), after
    assert not has_warning(after, "carry no `variants` while others do"), (
        "the family really is silenced wholesale — which is the risk the count exists to expose")


# --- G: altitude -----------------------------------------------------------------------

def test_g1_the_file_cap_binds_on_the_file_per_component_frontend():
    """G1 — 14 tiny .tsx files. The FILE ceiling fires long before the LOC ceiling, so E counts
    many small files as unit-sized mass and lands above the honest altitude. `--report` must
    say WHICH cap bound E and print the median file size; three of four live builds disagreed
    with E by 2-4x with no way to see why."""
    trap("G1")
    tsx = sorted((FIXTURE / "web" / "src" / "components").glob("*.tsx"))
    assert len(tsx) >= 14
    with tempfile.TemporaryDirectory() as td:
        artifact = make_preindex(Path(td))
        doc = json.loads(artifact.read_text())
        out = _capture(lambda: preindex.main(["--report", "--in", str(artifact)]))
    gran = doc["granularity"]
    assert gran["bound_by"] == "file-count", gran
    assert gran["median_file_loc"] < 80, gran
    assert "bound by file-count" in out and "median file" in out
    assert "the honest altitude to sit BELOW E here" in out


def test_g2_the_oversized_flat_folder_expects_more_than_one_component():
    """G2 — 12 files, >3 kLOC, no subdirectory. The leaf rule says SPLIT into cohesive groups."""
    trap("G2")
    flat = FIXTURE / "src" / "flatpack"
    files = sorted(p for p in flat.iterdir() if p.suffix == ".py" and p.name != "__init__.py")
    assert len(files) == 12 and not any(p.is_dir() for p in flat.iterdir())
    loc = sum(len(p.read_text().splitlines()) for p in files)
    assert loc > 3000, f"the LOC cap must actually bind: {loc}"
    with tempfile.TemporaryDirectory() as td:
        doc = json.loads(make_preindex(Path(td)).read_text())
    assert doc["granularity"]["per_dir"].get("src/flatpack", 0) > 1, doc["granularity"]["per_dir"]
    members = [c.id for c in make_golden_model().components if c.subsystem == "S5"]
    assert len(members) > 1, "the golden map folded the flat folder into one box"


def test_g3_the_generated_dir_collapses_and_the_fold_is_recorded():
    """G3 — ~900 LOC of machine-emitted code. Collapsing is correct AND must be recorded, or
    the folded-subdir / unreferenced-dir warnings fire forever."""
    trap("G3")
    gen = FIXTURE / "src" / "generated"
    loc = sum(len(p.read_text().splitlines()) for p in gen.glob("*.py"))
    assert 700 < loc < 1200, loc
    assert "@generated" in fixture_text("src/generated/pb_ticket.py")
    boxes = [c.id for c in make_golden_model().components
             if (c.source or "").startswith("src/generated")]
    assert len(boxes) == 1, boxes
    recorded = [x.body for x in make_golden_model().extras
                if x.heading.lower() == "coverage exceptions"]
    assert recorded and "src/generated/" in recorded[0]


def test_g4_eight_same_shaped_plugin_dirs_draw_no_fan_out_warning():
    """G4 — the homogeneous-family case. Eight same-kind siblings on one screen read as a list;
    splitting them into artificial sub-groups to hit a number is the wrong answer."""
    trap("G4")
    dirs = sorted(p for p in (FIXTURE / "src" / "plugins").iterdir() if p.is_dir())
    assert len(dirs) == 8 and all((p / "handler.py").exists() for p in dirs)
    model = make_golden_model()
    assert len([c for c in model.components if c.subsystem == "S3"]) == 8
    assert not has_warning(make_golden_warnings(), "S3", "fan-out"), make_golden_warnings()


def test_g5_a_two_box_tech_tier_root_is_reported_as_sparse():
    """G5 — the tree offers exactly two top-level source dirs, which tempt a `Backend`/`Frontend`
    root. The golden map groups by capability instead; a variant that takes the bait must warn."""
    trap("G5")
    tops = {p.name for p in FIXTURE.iterdir() if p.is_dir() and not p.name.startswith(".")}
    assert {"src", "web"} <= tops
    roots = [s.id for s in make_golden_model().subsystems if not s.parent]
    assert len(roots) >= 3, f"the golden root is capability-grouped, not tech-tiered: {roots}"
    assert not has_warning(make_golden_warnings(), "root", "sparse")

    doc = json.loads(GOLDEN_MAP.read_text(encoding="utf-8"))
    doc["subsystems"] = [
        {"id": "S1", "name": "Backend", "purpose": "everything server-side", "source": "src/"},
        {"id": "S6", "name": "Frontend", "purpose": "everything browser-side", "source": "web/"},
    ]
    for c in doc["components"]:
        c["subsystem"] = "S6" if c["source"].startswith("web/") else "S1"
    tiered = warnings_of(load_model(json.dumps(doc)))
    assert has_warning(tiered, "root"), tiered


# --- P: domain -------------------------------------------------------------------------

def test_p2_a_container_no_entity_names_is_reported_once_a_store_is_structured():
    """P2 — the repository writes a `search_index` container no entity records as its store.
    Adoption-gated on `store.dep`, which the golden map sets, so the rule engages."""
    trap("P2")
    assert "_search_index" in fixture_text("src/store/ticket_repo.py")
    w = make_golden_warnings()
    assert has_warning(w, "C4 writes into D3"), w
    assert has_warning(w, "Persistence exceptions"), "the escape must be named in the message"


def test_p3_entity_relations_are_authored_not_derived_from_c_to_e_edges():
    """P3 — a map with C->E edges but no authored E<->E relations leaves the domain disconnected.
    `validate --check-coverage` counts isolated entities, and that advisory has no escape (the
    L1 audit carries the finding)."""
    trap("P3")
    model = make_golden_model()
    assert any(r.target == "E2" for e in model.entities if e.id == "E1" for r in e.relations)

    doc = json.loads(GOLDEN_MAP.read_text(encoding="utf-8"))
    for ent in doc["entities"]:
        ent["relations"] = []
    stripped = load_model(json.dumps(doc))
    _p, w = validate_model(stripped, GOLDEN_MAP, check_coverage=True, repo_root=FIXTURE)
    assert has_warning(w, "Isolated entities"), w


# --- E: environment --------------------------------------------------------------------

def test_e1_the_checked_in_defaults_file_is_ordinary_readable_tracked_source():
    """E1 — `config.default.env` is committed, non-secret, and the source of truth for the key
    list. A live build refused it as a "secret file" on the filename alone and shipped a thin
    Config table. Nothing structural stops a build from reading it; assert exactly that."""
    trap("E1")
    assert "config.default.env" in fixture_tracked_paths()
    text = fixture_text("config.default.env")
    assert "__injected_at_deploy__" in text, "the file must contain no real credential"
    keys = {ln.split("=", 1)[0] for ln in text.splitlines()
            if "=" in ln and not ln.startswith("#")}
    mapped = {row.key for row in make_golden_model().config}
    assert keys & mapped, f"the map records none of the file's keys: {sorted(keys)[:5]}"


def test_e2_a_doc_that_merely_mentions_a_dotenv_filename_accesses_no_such_file():
    """E2 — the runbook NAMES `.env.production` while asking nobody to open it. A guard that
    matches command TEXT rather than file access trips on the sentence; the tree proves there
    is nothing to access. (Self-inflicted during the study: a grep pattern carrying the same
    filename tripped the guard.)"""
    trap("E2")
    assert ".env.production" in fixture_text("docs/runbook.md")
    assert not (FIXTURE / ".env.production").exists()
    assert not any(p.startswith(".env") for p in fixture_tracked_paths())
    walked = iter_source_files(FIXTURE).files
    assert not any(p.name.startswith(".env") for p in walked)


# --- specified-not-missed: design gaps this suite FLAGS ---------------------------------

def test_infra_role_band_prefers_the_edge_verb_over_the_declared_dep_kind():
    """A DESIGN GAP, deliberately pinned rather than fixed.

    A dependency's role in the Deployment view's infrastructure band is DERIVED from the union
    of its incoming `C->D` verbs, not from its declared `kind`. So a `kind: service` dep reached
    with `emits` bands under Message bus, while an otherwise identical `kind: service` dep
    reached with `calls` lands under Service — the Mixpanel/Sentry split observed on a live map.

    That is specified behaviour: `tests/test_gen_deployment.py:49`
    (`test_infra_band_dual_role_goes_to_bus_and_roleless_falls_back`) asserts the verb wins and
    the declared kind is only a fallback. It is still a gap — an observability SaaS reached with
    `emits` is not a message bus — so this test states it against a REAL map instead of a
    three-row toy, and says plainly that the answer below is today's, not the right one."""
    model = make_golden_model()
    analytics = next(d for d in model.deps if d.id == "D4")
    assert analytics.kind == "service"
    roles = model_to_graph(model)["nodes"]["D4"]["roles"]
    assert roles == ["messaging"], (
        "today the `emits` verb overrides the declared `service` kind; if this now returns "
        "['service'] the design gap has been closed and the docstring above is stale")


def test_the_component_count_sits_inside_the_code_derived_band():
    """The whole-repo granularity anchor, re-computed from the real tree (GR4) rather than read
    back out of the pre-index. A map far outside the band is under- or over-split."""
    model = make_golden_model()
    tree = expected_components(FIXTURE)
    lo = int(tree.expected * 0.6)
    hi = int(tree.expected * 1.4) + 1
    assert lo <= len(model.components) <= hi, (
        f"{len(model.components)} components against E={tree.expected} (band {lo}-{hi})")


# --- harness --------------------------------------------------------------------------

def _capture(fn) -> str:
    """Run a CLI main() and return everything it printed. Stdlib only; no pytest fixture (the
    house style forbids them), so the redirect is explicit and local."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        fn()
    return buf.getvalue()


def _main() -> int:
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {fn.__name__}\n  {str(exc)[:600]}\n")
    print(f"{len(fns) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_main())
