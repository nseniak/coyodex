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
    balance_warnings,
    cc_pairs,
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
from coyodex.model import Component, Edge, Entity, ExtraSection, Group, ProjectModel
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
    assert len(ws) == 1 and "no subsystems" in ws[0] and "capability" in ws[0]


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
