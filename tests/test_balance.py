#!/usr/bin/env python3
"""Tests for `coyodex.balance_lib` — the diagram-balance advisories (fan-out bands, homogeneity
exemption, single-child wrappers, the "Balance exceptions" extras escape hatch), the C→C graph
machinery (modularity, quotient graph, signal check), and the deterministic greedy split.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_balance.py
    pytest tests/test_balance.py
"""
from __future__ import annotations

from coyodex.balance_lib import (
    _exceptions,
    balance_warnings,
    cc_pairs,
    fanout_band,
    fanout_summary,
    is_homogeneous,
    modularity,
    name_seed,
    nesting_depth,
    next_free_group_id,
    propose_split,
    subgraph_signal,
    subsystem_children,
)
from coyodex.model import Component, Edge, Entity, ExtraSection, Group, ProjectModel, Store
from coyodex.validate_model import validate_model


# --- builders -------------------------------------------------------------------

def make_component(cid: str, sub: str | None = None, source: str | None = None,
                   name: str | None = None, purpose: str = "") -> Component:
    return Component(id=cid, name=name or f"Comp {cid}", subsystem=sub,
                     purpose=purpose, source=source)


def make_model(n_components: int = 0, subsystem: str | None = None) -> ProjectModel:
    m = ProjectModel(title="Demo", goal="A demo.")
    if subsystem:
        m.subsystems = [Group(id=subsystem, name="The box")]
    m.components = [make_component(f"C{i}", subsystem) for i in range(1, n_components + 1)]
    return m


def make_grouped_model(sizes: dict[str, int]) -> ProjectModel:
    """One top-level subsystem per key, holding `sizes[key]` components."""
    m = ProjectModel(title="Demo", goal="A demo.")
    cid = 0
    for sid, n in sizes.items():
        m.subsystems.append(Group(id=sid, name=f"Box {sid}"))
        for _ in range(n):
            cid += 1
            m.components.append(make_component(f"C{cid}", sid))
    return m


def make_two_cluster_model() -> ProjectModel:
    """Six components in one dense subsystem: two triangles joined by one bridge edge —
    the textbook two-community graph (plus filler to trip the density threshold)."""
    m = ProjectModel(title="Demo", goal="A demo.")
    m.subsystems = [Group(id="S1", name="Dense")]
    m.components = [make_component(f"C{i}", "S1", source=f"src/{'a' if i <= 3 else 'b'}/f{i}.py:1")
                    for i in range(1, 7)]
    tri_a = [("C1", "C2"), ("C2", "C3"), ("C1", "C3")]
    tri_b = [("C4", "C5"), ("C5", "C6"), ("C4", "C6")]
    bridge = [("C3", "C4")]
    m.edges = [Edge(src=a, verb="uses", dst=b, where="src/x.py:1")
               for a, b in tri_a + tri_b + bridge]
    return m


# --- the always-on advisory: small maps -----------------------------------------

def test_small_flat_map_is_silent() -> None:
    m = make_model(n_components=12)                    # no subsystems, ≤15
    assert balance_warnings(m) == []


def test_large_flat_map_gets_one_grouping_nudge() -> None:
    m = make_model(n_components=20)                    # no subsystems, >15
    ws = balance_warnings(m)
    # "product area", not "capability": the word now names the use-case grouping, and the subsystem
    # axis was renamed so the two senses can never blur (plan/60-capabilities).
    assert len(ws) == 1 and "no subsystems" in ws[0] and "product area" in ws[0]


# --- root rules ------------------------------------------------------------------

def test_sparse_root_warns_on_large_grouped_map() -> None:
    m = make_grouped_model({"S1": 10, "S2": 10})       # root fan-out 2, 20 components
    ws = balance_warnings(m)
    assert any("root diagram shows only 2" in w for w in ws)


def test_sparse_root_silent_on_small_grouped_map() -> None:
    m = make_grouped_model({"S1": 5, "S2": 5})         # 10 components < 15
    assert not any("root" in w for w in balance_warnings(m))


def test_dense_root_warns() -> None:
    m = make_grouped_model({f"S{i}": 2 for i in range(1, 15)})   # root fan-out 14
    ws = balance_warnings(m)
    assert any("root diagram shows 14" in w for w in ws)


# --- per-subsystem rules -----------------------------------------------------------

def test_midtree_two_children_is_normal() -> None:
    m = make_grouped_model({"S1": 2, "S2": 6, "S3": 6})
    assert not any("S1" in w for w in balance_warnings(m))


def test_soft_tier_10_to_12_stays_out_of_validate() -> None:
    m = make_grouped_model({"S1": 11, "S2": 5, "S3": 5})
    assert not any("S1 " in w for w in balance_warnings(m))


def test_dense_subsystem_warns_above_12() -> None:
    m = make_grouped_model({"S1": 13, "S2": 5, "S3": 5})
    ws = balance_warnings(m)
    assert any("S1" in w and "13 children" in w for w in ws)


def test_single_child_wrapper_warns() -> None:
    m = make_grouped_model({"S1": 1, "S2": 6, "S3": 6})
    ws = balance_warnings(m)
    assert any("S1" in w and "single component" in w for w in ws)


def test_single_child_subsystem_of_subsystem_left_to_redundant_nesting_check() -> None:
    m = make_grouped_model({"S2": 6, "S3": 6})
    m.subsystems.append(Group(id="S1", name="Wrapper"))
    m.subsystems.append(Group(id="S4", name="Inner", parent="S1"))
    m.components += [make_component(f"C{90 + i}", "S4") for i in range(4)]
    assert not any("S1" in w and "single" in w for w in balance_warnings(m))


# --- homogeneity ---------------------------------------------------------------------

def make_family_model(n: int, shared_dir: bool = True, shared_token: bool = False) -> ProjectModel:
    m = make_grouped_model({"S2": 6, "S3": 6})
    m.subsystems.append(Group(id="S1", name="Stores"))
    for i in range(n):
        src = f"src/repos/f{i}.py:1" if shared_dir else f"src/d{i}/f.py:1"
        name = f"Widget {i} repository" if shared_token else f"Widget {i} thing{i}"
        m.components.append(Component(id=f"C{50 + i}", name=name, subsystem="S1", source=src))
    return m


def test_homogeneous_family_by_dir_exempt_at_13() -> None:
    m = make_family_model(13, shared_dir=True)
    assert not any("S1" in w for w in balance_warnings(m))


def test_homogeneous_family_by_name_token_exempt_at_13() -> None:
    m = make_family_model(13, shared_dir=False, shared_token=True)
    assert not any("S1" in w for w in balance_warnings(m))


def test_homogeneous_family_still_warns_above_15() -> None:
    m = make_family_model(16, shared_dir=True)
    ws = balance_warnings(m)
    assert any("S1" in w and "homogeneous family" in w for w in ws)


def test_heterogeneous_13_warns() -> None:
    m = make_family_model(13, shared_dir=False, shared_token=False)
    ws = balance_warnings(m)
    assert any("S1" in w and "13 children" in w for w in ws)


# --- the extras escape hatch ------------------------------------------------------------

def test_balance_exceptions_extras_silences_named_diagrams() -> None:
    m = make_grouped_model({"S1": 13, "S2": 10})       # S1 dense + root sparse (23 comps, 2 boxes)
    assert len(balance_warnings(m)) == 2
    m.extras = [ExtraSection(heading="Balance exceptions",
                             body="root: two-part product by design. S1: legacy family.")]
    assert balance_warnings(m) == []


def make_exceptions_model(body: str) -> ProjectModel:
    """A bare model carrying one 'Balance exceptions' extras block with the given body."""
    m = ProjectModel(title="Demo", goal="A demo.")
    m.extras = [ExtraSection(heading="Balance exceptions", body=body)]
    return m


def test_a_literal_named_mid_prose_never_silences_its_advisory() -> None:
    """Adversarial-review finding #3: `runs-in`, `granularity` and `entity-flows` used to be read
    by an anywhere-in-body scan, so a justification that merely MENTIONED one switched off a whole
    advisory family. `runs-in` was the worst case — it now silences every deployment check."""
    assert sorted(_exceptions(make_exceptions_model(
        "C5: grouped by capability. The runs-in tagging was audited separately..."))) == ["C5"]
    assert sorted(_exceptions(make_exceptions_model(
        "S1: fine. We reviewed granularity and entity-flows during the walkthrough."))) == ["S1"]
    # the literals already on the line-leading discipline behaved correctly and still do
    assert sorted(_exceptions(make_exceptions_model(
        "C7: this is fine; the channel-payload question was answered offline."))) == ["C7"]


def test_every_literal_records_when_it_leads_its_line() -> None:
    for literal in ("cadence", "channel-ends", "channel-payload", "entity-flows",
                    "entity-relations", "granularity", "isolated", "messaging", "runs-in",
                    "store"):
        m = make_exceptions_model(f"{literal}: the operator's reason.")
        assert _exceptions(m) == {literal}, literal


def test_the_recording_forms_a_live_map_uses_all_read() -> None:
    assert _exceptions(make_exceptions_model("granularity: 36 components against ~11.")) \
        == {"granularity"}
    assert _exceptions(make_exceptions_model("- runs-in: the Mongo units run no first-party code.")) \
        == {"runs-in"}
    assert _exceptions(make_exceptions_model("* entity-flows: a pure proxy, no domain layer.")) \
        == {"entity-flows"}
    assert _exceptions(make_exceptions_model("**store** — this project has no database.")) \
        == {"store"}
    assert _exceptions(make_exceptions_model("cadence - the loops are genuinely continuous")) \
        == {"cadence"}
    assert _exceptions(make_exceptions_model("isolated (developer CLIs that drive from outside)")) \
        == {"isolated"}
    assert _exceptions(make_exceptions_model("runs-in")) == {"runs-in"}   # alone on its line


def test_a_hyphenated_compound_at_line_start_is_not_a_record() -> None:
    """Adversarial-review finding #8: a bare `-` counted as a separator, so a compound word
    starting with a literal recorded that literal — and hyphenated literals made it plausible."""
    assert _exceptions(make_exceptions_model("store-front redesign: see ticket 44")) == set()
    assert _exceptions(make_exceptions_model("isolated-network deploys: nothing to do")) == set()
    assert _exceptions(make_exceptions_model("channel-payload-review-2026: ...")) == set()


def test_a_literal_buried_in_a_multi_line_justification_stays_quiet() -> None:
    body = ("granularity: 36 components against a code-derived expectation of ~11.\n"
            "The runs-in tagging and the entity-flows question were both settled offline,\n"
            "and the store layout is unchanged.")
    assert _exceptions(make_exceptions_model(body)) == {"granularity"}


def test_ids_still_read_anywhere_in_the_body() -> None:
    """Ids are not words, so prose cannot mint one by accident — and a live map records five
    sub-flows on one comma-separated line, of which only the first leads the line."""
    m = make_exceptions_model("SF40, SF41, SF52, SF70, SF71: each is referenced once.")
    assert _exceptions(m) == {"SF40", "SF41", "SF52", "SF70", "SF71"}
    assert _exceptions(make_exceptions_model("C93: one flat catalog file. S6: two members.")) \
        == {"C93", "S6"}


# --- SD forest mirror ----------------------------------------------------------------------

def test_sd_forest_gets_the_same_rules() -> None:
    m = ProjectModel(title="Demo", goal="A demo.")
    m.subdomains = [Group(id="SD1", name="Core"), Group(id="SD2", name="Aux")]
    m.entities = [Entity(id=f"E{i}", name=f"Ent {i}", subdomain="SD1" if i <= 14 else "SD2",
                         meaning="x", source=f"src/d{i}/e{i}.py:1") for i in range(1, 17)]
    ws = balance_warnings(m)
    assert any("SD1" in w and "14 children" in w for w in ws)


# --- graph machinery ----------------------------------------------------------------------

def test_cc_pairs_dedup_and_scope() -> None:
    m = make_two_cluster_model()
    m.edges.append(Edge(src="C2", verb="calls", dst="C1", where="src/y.py:1"))   # reverse dup
    m.edges.append(Edge(src="C1", verb="uses", dst="D1", where="src/z.py:1"))    # C→D excluded
    assert len(cc_pairs(m)) == 7


def test_modularity_hand_computed() -> None:
    m = make_two_cluster_model()
    part = {f"C{i}": ("A" if i <= 3 else "B") for i in range(1, 7)}
    coverage, q = modularity(cc_pairs(m), part)
    assert abs(coverage - 6 / 7) < 1e-9            # 6 intra of 7 pairs
    # Newman Q, m=7: A: e=3/7, d=7/14 → 3/7-(7/14)^2 ; B symmetric → 2*(3/7-0.25)
    assert abs(q - 2 * (3 / 7 - 0.25)) < 1e-9


def test_greedy_split_finds_the_two_clusters_and_is_deterministic() -> None:
    m = make_two_cluster_model()
    first = propose_split(m, "S1")
    second = propose_split(m, "S1")
    assert [p.members for p in first] == [p.members for p in second]
    groups = sorted(sorted(mid for mid, _ in p.members) for p in first)
    assert groups == [["C1", "C2", "C3"], ["C4", "C5", "C6"]]


def test_split_declines_on_sparse_signal() -> None:
    m = make_grouped_model({"S1": 13})                 # 13 children, zero C→C pairs
    assert subgraph_signal(m, "S1") == "sparse"
    assert propose_split(m, "S1") == []


def test_split_declines_on_star_graph() -> None:
    m = ProjectModel(title="Demo", goal="A demo.")
    m.subsystems = [Group(id="S1", name="Star")]
    m.components = [make_component(f"C{i}", "S1", source=f"src/d{i}/f.py:1", name=f"N{i} x{i}")
                    for i in range(1, 11)]
    m.edges = [Edge(src="C1", verb="uses", dst=f"C{i}", where="src/x.py:1") for i in range(2, 11)]
    assert subgraph_signal(m, "S1") == "star"
    assert propose_split(m, "S1") == []


def test_quotient_split_on_subsystem_children_never_singleton() -> None:
    m = ProjectModel(title="Demo", goal="A demo.")
    m.subsystems = [Group(id="S1", name="Root box")]
    m.subsystems += [Group(id=f"S{i}", name=f"Area {i}", parent="S1") for i in range(2, 8)]
    cid = 0
    for i in range(2, 8):
        for _ in range(2):
            cid += 1
            m.components.append(make_component(f"C{cid}", f"S{i}", source=f"src/a{i}/f{cid}.py:1"))
    # two 3-subsystem cliques at the component level (via one representative each)
    def rep(sub_index: int) -> str:
        return f"C{(sub_index - 2) * 2 + 1}"
    pairs = [(2, 3), (3, 4), (2, 4), (5, 6), (6, 7), (5, 7), (4, 5)]
    m.edges = [Edge(src=rep(a), verb="uses", dst=rep(b), where="src/x.py:1") for a, b in pairs]
    proposals = propose_split(m, "S1")
    assert proposals, "quotient graph must yield a proposal for S-children diagrams"
    assert all(len(p.members) >= 2 for p in proposals)
    assert all(mid.startswith("S") for p in proposals for mid, _ in p.members)


# --- naming ------------------------------------------------------------------------------------

def test_name_seed_prefers_discriminating_dir() -> None:
    m = ProjectModel(title="Demo", goal="A demo.")
    m.components = [make_component("C1", source="src/auth/gate.py:1"),
                    make_component("C2", source="src/auth/token.py:1")]
    name, basis = name_seed(m, ["C1", "C2"])
    assert (name, basis) == ("Auth", "dir")


def test_name_seed_rejects_non_discriminating_parent_prefix() -> None:
    m = ProjectModel(title="Demo", goal="A demo.")
    m.components = [make_component("C1", source="src/pkg/a.py:1", purpose="verifies gateway tokens"),
                    make_component("C2", source="src/pkg/b.py:1", purpose="mints gateway tokens")]
    name, basis = name_seed(m, ["C1", "C2"], parent_lcp=["src", "pkg"])
    assert basis == "purpose" and name.lower() in ("gateway", "tokens")


def test_name_seed_unnamed_fallback() -> None:
    m = ProjectModel(title="Demo", goal="A demo.")
    m.components = [make_component("C1"), make_component("C2")]
    assert name_seed(m, ["C1", "C2"]) == ("(name me)", "unnamed")


def test_next_free_group_id() -> None:
    m = make_grouped_model({"S1": 2, "S7": 2})
    assert next_free_group_id(m) == "S8"
    assert next_free_group_id(m, "SD") == "SD1"


# --- summary + trees ------------------------------------------------------------------------------

def test_nesting_depth_and_children() -> None:
    m = make_grouped_model({"S1": 3})
    m.subsystems.append(Group(id="S2", name="Child", parent="S1"))
    m.subsystems.append(Group(id="S3", name="Grandchild", parent="S2"))
    assert nesting_depth(m) == 3
    kids = subsystem_children(m)
    assert kids[None] == ["S1"] and "S2" in kids["S1"] and kids["S2"] == ["S3"]


def test_fanout_summary_values() -> None:
    m = make_grouped_model({"S1": 4, "S2": 13})
    root, biggest, in_band, depth = fanout_summary(m)
    assert (root, biggest, depth) == (2, 13, 1)
    assert in_band == round(1 / 3, 3)                  # only S1 of {root, S1, S2}; lib rounds to 3dp


def test_fanout_summary_empty_model() -> None:
    assert fanout_summary(ProjectModel(title="x", goal="y")) == (None, None, None, 0)


# --- validate integration -------------------------------------------------------------------------

def test_balance_lands_in_warnings_never_problems() -> None:
    m = make_grouped_model({"S1": 13, "S2": 10})
    problems, warnings = validate_model(m)
    assert not any("Balance:" in p for p in problems)
    assert any("Balance:" in w for w in warnings)


def test_homogeneity_helper_direct() -> None:
    m = make_family_model(6, shared_dir=True)
    fam = [c.id for c in m.components if c.subsystem == "S1"]
    assert is_homogeneous(m, fam)
    assert not is_homogeneous(m, fam[:1])              # a single child is never a family
    assert not is_homogeneous(m, [fam[0], "S2"])       # mixed kinds


def _run_all() -> None:
    import sys
    mod = sys.modules[__name__]
    tests = [v for k, v in vars(mod).items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
    print(f"ok — {len(tests)} tests")


if __name__ == "__main__":
    _run_all()


# ── the retro finding: the headline and the verdict contradicted each other ───────────────────────

def test_the_band_headline_and_the_verdict_cannot_contradict_each_other():
    """A live report printed "diagrams in the 3–9 band: 14/15" six lines above "No balance findings
    — every diagram reads at target density." Both were true under their own rule: the band is a
    MEASUREMENT and the findings list is a POLICY that only treats sparse as an anti-pattern at the
    root. The reader had no way to see that, so the report now names the gap."""
    from coyodex import balance
    m = make_grouped_model({"S1": 5, "S2": 5, "S3": 2})   # S3 is thin, non-root → no finding
    text = balance._report(m)
    assert "No balance findings" in text
    assert "every diagram reads at target density" not in text, (
        "that claim is false while a diagram sits below the band")
    assert "S3" in text and "NOT a finding" in text
    assert "sparse counts only at the root" in text


def test_the_report_and_the_eval_metric_share_one_band_definition():
    """They were computed twice and had drifted in two ways — the exempt test AND the denominator
    (the report counted childless subsystems, the profile skipped them). A shared boolean would
    have fixed only the first, so `fanout_band` returns the whole fraction."""
    from coyodex import balance
    from coyodex.balance_lib import fanout_band, fanout_summary
    m = make_grouped_model({"S1": 5, "S2": 5, "S3": 2})
    m.subsystems.append(Group(id="S9", name="empty on purpose"))
    in_band, total = fanout_band(m)
    assert f"{in_band}/{total}" in balance._report(m)
    _root, _mx, pct, _d = fanout_summary(m)
    assert pct == round(in_band / total, 3), "one number, or the two reports disagree again"


def make_subsystem_model(sizes: dict[str, int], homogeneous: set[str] | None = None) -> ProjectModel:
    """Subsystems of the given sizes; those in `homogeneous` get all their files in one directory."""
    homogeneous = homogeneous or set()
    m = ProjectModel(title="T", goal="g")
    i = 0
    for sid, n in sizes.items():
        m.subsystems.append(Group(id=sid, name=f"Box {sid}"))
        for _ in range(n):
            i += 1
            src = f"pkg/same/f{i}.py:1" if sid in homogeneous else f"src/{sid}/d{i}/f{i}.py:1"
            m.components.append(Component(id=f"C{i}", name=f"C{i}", subsystem=sid, source=src))
    return m


def test_the_out_of_band_line_uses_the_shared_predicate_not_a_second_one():
    """The first cut of the "below the band" line tested `n < FANOUT_LO` by hand. It disagreed with
    the shared rule on a 2-child HOMOGENEOUS subsystem — which the band counts as in-band — so the
    report printed "4/4 diagrams in band" directly above "1 below the band". That is the same
    contradiction the shared measurement was introduced to remove, two lines apart."""
    from coyodex import balance
    m = make_subsystem_model({"S1": 5, "S2": 5, "S3": 2}, homogeneous={"S3"})
    text = balance._report(m)
    in_band, total = fanout_band(m)
    assert f"{in_band}/{total}" in text
    assert "below the band" not in text, "a diagram the band counts IN cannot also be reported out"


def test_a_real_finding_is_never_labelled_not_a_finding():
    """SINGLE-CHILD is in `flagged`. The hand-rolled predicate did not exclude flagged rows, so the
    header called a live finding "NOT a finding" while the per-diagram row showed it flagged."""
    from coyodex import balance
    m = make_subsystem_model({"S1": 5, "S2": 5, "S3": 1})
    text = balance._report(m)
    assert "SINGLE-CHILD" in text
    thin_line = next((l for l in text.splitlines() if "NOT a finding" in l), "")
    assert "S3" not in thin_line, f"S3 is flagged; it must not be listed as not-a-finding: {thin_line}"


def test_an_empty_subsystem_is_described_as_empty_not_as_sparse():
    """"Below the band" misdescribes a diagram with no children at all."""
    from coyodex import balance
    m = make_subsystem_model({"S1": 5, "S2": 5, "S3": 4})
    m.subsystems.append(Group(id="S9", name="declared but never filled"))
    text = balance._report(m)
    assert "1 declared with no children at all: S9" in text
    assert "S9" not in next((l for l in text.splitlines() if "below the band" in l), "")


def test_the_seam_list_is_stable_across_processes():
    """The busiest-seam list sorted on weight alone, so equal-weight seams arrived in the iteration
    order of a SET of frozensets — and Python randomises string hashing per process. Five identical
    runs of `coyodex balance` on one map printed three different top-6 lists.

    That makes a gate a build reads and quotes non-reproducible, and it puts spurious churn into
    every before/after map comparison, which is what the eval harness is for. Sorting on
    (-weight, name) settles ties by name instead.

    Run in SUBPROCESSES on purpose: within one process the hash seed is fixed, so an in-process
    loop cannot catch this class at all.
    """
    import subprocess, sys, json, tempfile, os
    from coyodex import balance
    m = make_subsystem_model({"S1": 4, "S2": 4, "S3": 4, "S4": 4})
    # Equal-weight cross-subsystem seams are what tie; build several by hand.
    from coyodex.model import to_canonical_json
    members = {s.id: [c.id for c in m.components if c.subsystem == s.id] for s in m.subsystems}
    for a, b in (("S1", "S2"), ("S1", "S3"), ("S2", "S3"), ("S1", "S4"), ("S2", "S4"), ("S3", "S4")):
        m.edges.append(Edge(src=members[a][0], dst=members[b][0], verb="calls"))
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "m.json")
        with open(p, "w") as fh:
            fh.write(to_canonical_json(m))
        seen = set()
        for seed in ("0", "1", "2", "3", "4"):
            env = {**os.environ, "PYTHONHASHSEED": seed}
            out = subprocess.run([sys.executable, "-c",
                                  "import sys;from coyodex.balance import main;sys.exit(main([sys.argv[1]]))",
                                  p], capture_output=True, text=True, env=env)
            seam = [l for l in out.stdout.splitlines() if "↔" in l]
            seen.add(tuple(seam))
        assert len(seen) == 1, f"balance is not reproducible across hash seeds: {len(seen)} distinct outputs"


def test_the_domain_forest_gets_its_own_fanout_table():
    """`validate` advises on subdomain fan-out and ends the advisory with "(`coyodex balance`
    proposes splits)". `balance` rendered only the subsystem forest, so that sentence pointed the
    reader at a tool that could not answer it — and on a live map the four dense domain diagrams
    (13, 23, 22 and 27 children) were filtered out of the build's view and never addressed."""
    from coyodex import balance
    from coyodex.model import Entity, Group
    m = make_subsystem_model({"S1": 5, "S2": 5})
    m.subdomains = [Group(id="SD1", name="Wide"), Group(id="SD2", name="Narrow")]
    # Spread across directories on purpose: a same-directory family is HOMOGENEOUS and the tool
    # exempts it from the density flag, correctly. A test that missed that would be asserting the
    # exemption is broken rather than that the table works.
    for i in range(16):
        m.entities.append(Entity(id=f"E{i}", name=f"Ent{i}", source=f"pkg{i}/x.py:1",
                                 meaning="m", subdomain="SD1" if i < 14 else "SD2",
                                 store=Store(dep="D1", container=f"c{i}", mode="collection")))
    text = balance._report(m)
    assert "Per-subdomain fan-out" in text, "the domain forest must get a table"
    sd_line = next(l for l in text.splitlines() if l.strip().startswith("SD1"))
    assert "14" in sd_line and "DENSE" in sd_line, sd_line
    assert any(l.strip().startswith("SD2") for l in text.splitlines()), \
        "every subdomain gets a row, not only the flagged ones"


def test_a_map_with_no_subdomains_gets_no_domain_table():
    """Silence, not an empty heading — most maps of small repos have no domain forest at all."""
    from coyodex import balance
    m = make_subsystem_model({"S1": 5, "S2": 5})
    m.subdomains = []
    assert "Per-subdomain fan-out" not in balance._report(m)


def test_map_is_accepted_as_a_named_flag_too():
    """`record`, `anchor-drift` and every `fix` verb take `--map`; `balance` took only a positional,
    so a build that had just run `record --map …` wrote `balance --map …` and got exit 2. The
    spelling a caller reaches for should not depend on which subcommand it is."""
    import json as _json
    import tempfile as _tempfile
    from pathlib import Path as _Path

    from coyodex.balance import main as _main
    from coyodex.model import FORMAT as _FORMAT
    with _tempfile.TemporaryDirectory() as td:
        p = _Path(td) / "m.json"
        p.write_text(_json.dumps({
            "format": _FORMAT, "title": "t", "goal": "g",
            "components": [{"id": "C1", "name": "A", "purpose": "p", "subsystem": "S1"}],
            "subsystems": [{"id": "S1", "name": "One", "purpose": "p"}],
        }), encoding="utf-8")
        assert _main(["--map", str(p)]) == _main([str(p)])
