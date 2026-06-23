#!/usr/bin/env python3
"""Tests for the schema-v1 grammar, the parser, and the validator's grouping checks.

Stdlib-only — no pytest required. Run either way:
    python3 tools/tests/test_grouping.py        # built-in runner (prints pass/fail)
    pytest tools/tests/test_grouping.py         # if pytest is installed
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))            # schema_v1, validate_analysis
sys.path.insert(0, str(TOOLS / "viewer"))  # build_graph

import build_graph  # noqa: E402
import gen_viewer  # noqa: E402
import schema_v1  # noqa: E402

VALIDATOR = TOOLS / "validate_analysis.py"


# --- builders -------------------------------------------------------------------
def make_grouped_map(layout: str = "proper") -> str:
    """A two-subsystem grouped map. layout='proper' has an ID + Component(name) column;
    layout='agent' drops them (id in col 0, Subsystem at index 1) — the regression case."""
    s_table = (
        "## Subsystems (S)\n"
        "| ID | Subsystem | Purpose | Parent | Anchor | Conf. |\n"
        "|---|---|---|---|---|---|\n"
        "| **S1** | Edge | x |  | a | V |\n"
        "| **S2** | Core | x |  | a | V |\n\n"
    )
    if layout == "agent":
        t1 = (
            "## T1\n"
            "| Component | Subsystem | Purpose | Entry point | Depends on |\n"
            "|---|---|---|---|---|\n"
            "| **C1** | S1 | x | f | C2 |\n"
            "| **C2** | S2 | x | f |  |\n\n"
        )
    else:
        t1 = (
            "## T1\n"
            "| ID | Component | Subsystem | Purpose | Entry point | Depends on |\n"
            "|---|---|---|---|---|---|\n"
            "| **C1** | Front door | S1 | x | f | C2 |\n"
            "| **C2** | Engine | S2 | x | f |  |\n\n"
        )
    edges = (
        "### edges\n"
        "| From | Verb | To | Why | Where |\n"
        "|---|---|---|---|---|\n"
        "| C1 | uses | C2 | reach engine | f |\n"
    )
    return s_table + t1 + edges


def make_card_map() -> str:
    """A grouped map exercising the card generators: S1 has two components wired internally
    (C1->C3), both cross into S2's component C2, and C2 touches a dep D1. Lets the tests assert
    a subsystem card keeps internal wiring + deps, while an edge card keeps ONLY the cross edges."""
    return (
        "## Subsystems (S)\n"
        "| ID | Subsystem | Purpose | Parent | Anchor | Conf. |\n"
        "|---|---|---|---|---|---|\n"
        "| **S1** | Edge | front | | a | V |\n"
        "| **S2** | Core | brains | | a | V |\n\n"
        "## Dependencies\n"
        "| ID | Dependency | Purpose | Anchor |\n"
        "|---|---|---|---|\n"
        "| **D1** | Cache | speed | f |\n\n"
        "## T1\n"
        "| ID | Component | Subsystem | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|---|\n"
        "| **C1** | Front door | S1 | x | f | C2 |\n"
        "| **C3** | Router | S1 | x | f | C2 |\n"
        "| **C2** | Engine | S2 | x | f | D1 |\n\n"
        "### edges\n"
        "| From | Verb | To | Why | Where |\n"
        "|---|---|---|---|---|\n"
        "| C1 | calls | C2 | reach engine | f |\n"
        "| C1 | routes | C3 | dispatch | f |\n"
        "| C3 | calls | C2 | reach engine | f |\n"
        "| C2 | reads | D1 | cache | f |\n"
    )


def make_empty_verb_map() -> str:
    """An edge row with a blank Verb cell — renders as `C1 -->|| C2`, which can drop the Mermaid
    label and desync the viewer's positional path/label zip. The validator must reject it."""
    return (
        "## T1\n"
        "| ID | Component | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|\n"
        "| **C1** | A | x | f | C2 |\n"
        "| **C2** | B | x | f |  |\n\n"
        "### edges\n"
        "| From | Verb | To | Why | Where |\n"
        "|---|---|---|---|---|\n"
        "| C1 |  | C2 | reason | f |\n"
    )


def make_ungrouped_map() -> str:
    """No S table; prose mentions AWS S3/S4 (must not be treated as references)."""
    return (
        "# X\nUses AWS S3 and S4 buckets.\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|\n| **C1** | App | x | f |  |\n"
    )


def make_guard_map() -> str:
    """S table present but T1 has no membership column — the silent-failure case."""
    return (
        "## Subsystems\n| ID | Subsystem | Purpose | Parent | Anchor | Conf. |\n"
        "|---|---|---|---|---|---|\n| **S1** | A | x |  | a | V |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|\n| **C1** | App | x | f |  |\n"
    )


def make_cycle_map() -> str:
    return (
        "## S\n| ID | Subsystem | Purpose | Parent | Anchor | Conf. |\n"
        "|---|---|---|---|---|---|\n| **S1** | A | x | S2 | a | V |\n| **S2** | B | x | S1 | a | V |\n\n"
        "## T1\n| ID | Component | Subsystem | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|---|\n| **C1** | x | S1 | p | f |  |\n"
    )


def make_glued_id_map() -> str:
    """A Use-cases definition row with the id glued to the name (`| **UC1** Search… |`) — the
    real regression from the mercatus build: the id reads as undefined, not actually missing."""
    return (
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n"
        "|---|---|---|---|\n"
        "| **UC1** Search a product | Shopper | types -> list |\n\n"
        "## Golden Path\n"
        "**GP1 — Search** *(UC1)*\n"
        "STORY: x\n"
        "`Touches:` UC1\n"
    )


def make_bad_columns_map() -> str:
    """T1 whose separator has one more column than the header — the malformed-separator class."""
    return (
        "## T1\n"
        "| ID | Component | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|---|\n"  # 6 separator cols vs 5 header cols
        "| **C1** | App | x | f |  |\n"
    )


_VALID_HEAD = (
    "## Use cases\n"
    "| ID | Use case | Actor | Trigger → Outcome |\n"
    "|---|---|---|---|\n"
    "| **UC1** | Search | Shopper | types -> list |\n\n"
    "## Golden Path\n"
    "**GP1 — Search** *(UC1)*\n"
    "STORY: x\n"
    "`Touches:` UC1\n\n"
)


def make_fenced_ragged_table_map() -> str:
    """A valid map plus a fenced block whose example table is ragged — must NOT be parsed."""
    return _VALID_HEAD + (
        "## Example output\n"
        "```\n"
        "| Name | Score |\n"
        "|---|---|\n"
        "| alice | 10 | extra |\n"   # 3 cols vs 2 — but it's inside a fence
        "```\n"
    )


def make_fenced_dup_def_map() -> str:
    """C1 defined once for real, shown a 2nd time inside a fence — not a duplicate (bug class)."""
    return (
        "## T1\n"
        "| ID | Component | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|\n"
        "| **C1** | App | x | f |  |\n\n"
        "## How a row looks\n"
        "```\n"
        "| **C1** | App | x | f |  |\n"  # verbatim example, must be ignored
        "```\n"
    )


def make_escaped_pipe_map() -> str:
    r"""A cell uses the schema-sanctioned ``\|`` escape — must not inflate the column count."""
    return (
        "## T3\n"
        "| Action | Command | Source |\n"
        "|---|---|---|\n"
        "| grep | `a \\| b` | [f](f) |\n"
    )


def make_glued_inner_map() -> str:
    """Id and name share the bold (`**C8 Upstream**`) — the glued hint must still fire."""
    return (
        "## T1\n"
        "| ID | Component | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|\n"
        "| **C1** | App | x | f | C8 |\n\n"
        "## Notes\n"
        "The upstream is C8.\n"
        "| **C8 Upstream** | the upstream | x | f |  |\n"
    )


def make_fenced_node_map() -> str:
    """A real C1 plus a fenced example mentioning C9 — the parser must not graph C9."""
    return (
        "## T1\n| ID | Component | Subsystem | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|---|\n| **C1** | Real | S1 | x | f |  |\n\n"
        "## S\n| ID | Subsystem | Purpose | Parent | Anchor | Conf. |\n"
        "|---|---|---|---|---|---|\n| **S1** | A | x |  | a | V |\n\n"
        "## Example\n```\n| **C9** | Fake | S1 | x | f |  |\n```\n"
    )


def run_validator(md: str) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(md)
        path = f.name
    r = subprocess.run([sys.executable, str(VALIDATOR), path], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def parse_map(md: str) -> build_graph.GraphDict:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(md)
        path = f.name
    return build_graph.build(Path(path))


# --- grammar (schema_v1) --------------------------------------------------------
def test_membership_picks_subsystem_for_components_any_position() -> None:
    # 'subsystem' is the membership column for a component wherever it sits.
    assert schema_v1.membership_ids("C1", ["**C1**", "S1", "x"], ["component", "subsystem", "purpose"]) == ["S1"]
    assert schema_v1.membership_ids("C1", ["**C1**", "Name", "S1"], ["id", "component", "subsystem"]) == ["S1"]


def test_membership_picks_parent_for_subsystem_rows() -> None:
    # a subsystem row's 'subsystem' header is its NAME column; its pointer is 'parent'.
    assert schema_v1.membership_ids("S2", ["**S2**", "Core", "x", "S1"], ["id", "subsystem", "purpose", "parent"]) == ["S1"]


def test_membership_flags_multiparent() -> None:
    assert schema_v1.membership_ids("C8", ["**C8**", "S1, S2"], ["component", "subsystem"]) == ["S1", "S2"]


# --- parser (build_graph) -------------------------------------------------------
def test_parser_proper_layout_names_and_parents() -> None:
    g = parse_map(make_grouped_map("proper"))
    comps = {k: v for k, v in g["nodes"].items() if v["kind"] == "component"}
    assert comps["C1"]["name"] == "Front door"
    assert comps["C1"]["parent"] == "S1" and comps["C2"]["parent"] == "S2"


def test_parser_agent_layout_reads_membership_and_falls_back_name() -> None:
    g = parse_map(make_grouped_map("agent"))  # no name col, Subsystem at index 1
    comps = {k: v for k, v in g["nodes"].items() if v["kind"] == "component"}
    assert comps["C1"]["parent"] == "S1"   # membership still read (the bug we fixed)
    assert comps["C1"]["name"] == "C1"     # falls back to id, never the subsystem "S1"


def test_parser_subsystem_nodes_and_edges() -> None:
    g = parse_map(make_grouped_map("agent"))
    assert {k for k, v in g["nodes"].items() if v["kind"] == "subsystem"} == {"S1", "S2"}
    assert any(e["src"] == "C1" and e["dst"] == "C2" for e in g["edges"])


# --- card generators (gen_viewer) -----------------------------------------------
def test_subsystem_card_keeps_internal_wiring_and_deps() -> None:
    # Q1=B: a subsystem card shows the subsystem's own components, their internal edges, and the
    # deps they touch — but never a sibling subsystem's component.
    by_sub = gen_viewer.subsystem_component_mermaids(parse_map(make_card_map()))
    s1 = by_sub["S1"]
    assert "subgraph S1[" in s1                         # the subsystem reads as a labelled frame
    assert "C1" in s1 and "C3" in s1                    # both S1 components present
    assert "C1 -->|routes| C3" in s1                    # internal wiring kept
    assert "class S2 subsystem" in s1                   # the neighbour S2 drawn as a collapsed box
    assert "C1 --> S2" in s1 and "C3 --> S2" in s1      # cross arrows: component -> neighbour box (no label)
    assert "C2" not in s1                               # the sibling's component itself is NOT drawn
    s2 = by_sub["S2"]
    assert "subgraph S2[" in s2
    assert "C2" in s2 and "D1" in s2                    # Q1=B keeps the dep the component touches
    assert "C2 -->|reads| D1" in s2                     # ...with its component->dep edge
    assert "class S1 subsystem" in s2                   # the neighbour S1 box
    assert "S1 --> C2" in s2                            # inbound cross arrow: neighbour box -> member


def test_edge_card_has_both_subsystems_and_only_cross_edges() -> None:
    # Q2=A: an edge card frames BOTH subsystems with ALL their components, but draws ONLY the
    # A->B component edges — no internal edges, no deps, no other-subsystem edges.
    g = parse_map(make_card_map())
    cards = gen_viewer.edge_card_mermaids(g)
    assert set(cards) == {"S1>S2"}                      # only the direction that actually crosses
    card = cards["S1>S2"]
    assert "subgraph S1[" in card and "subgraph S2[" in card
    assert "C1" in card and "C3" in card and "C2" in card   # all components of both (Q2=A)
    assert "C1 -->|calls| C2" in card and "C3 -->|calls| C2" in card  # the cross edges
    assert "routes" not in card                         # internal S1 edge dropped
    assert "D1" not in card                             # no deps in an edge card


def test_render_inlines_edge_card_data() -> None:
    # The self-contained HTML must carry the edge-card diagrams for the client to open on click.
    with tempfile.TemporaryDirectory() as d:
        md = Path(d) / "project-map.md"
        md.write_text(make_card_map(), encoding="utf-8")
        out = Path(d) / "project-map.html"
        r = subprocess.run(
            [sys.executable, str(TOOLS / "viewer" / "render.py"), str(md), str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        assert "S1>S2" in out.read_text(encoding="utf-8")


# --- validator (end-to-end via the CLI) -----------------------------------------
def test_validator_grouped_ok_both_layouts() -> None:
    for layout in ("proper", "agent"):
        code, out = run_validator(make_grouped_map(layout))
        assert code == 0, f"{layout}: {out}"


def test_validator_ungrouped_and_prose_s3_ok() -> None:
    code, out = run_validator(make_ungrouped_map())
    assert code == 0, out


def test_validator_guard_fires_on_missing_membership() -> None:
    code, out = run_validator(make_guard_map())
    assert code == 1 and "no component is assigned" in out, out


def test_validator_catches_cycle() -> None:
    code, out = run_validator(make_cycle_map())
    assert code == 1 and "cycle" in out.lower(), out


def test_validator_hints_glued_id_cell() -> None:
    # The undefined id is reported as a glued-ID-cell mistake, not a generic "undefined ID".
    code, out = run_validator(make_glued_id_map())
    assert code == 1, out
    assert "glued into the ID cell" in out, out
    assert "References to undefined IDs" not in out, out  # not the generic message


def test_validator_catches_column_mismatch() -> None:
    code, out = run_validator(make_bad_columns_map())
    assert code == 1 and "columns" in out, out


def test_validator_rejects_empty_verb() -> None:
    # A blank Verb cell would render as `C1 -->|| C2` and desync the viewer's edge zip.
    code, out = run_validator(make_empty_verb_map())
    assert code == 1 and "empty Verb" in out, out


def test_validator_clean_maps_pass_table_shape() -> None:
    # The known-good maps must stay shape-clean (regression guard for false positives).
    for md in (make_grouped_map("proper"), make_grouped_map("agent"), make_ungrouped_map()):
        code, out = run_validator(md)
        assert code == 0, out


def test_validator_ignores_ragged_table_in_fence() -> None:
    # A ragged example table inside a ``` fence must not trigger a column-count failure.
    code, out = run_validator(make_fenced_ragged_table_map())
    assert code == 0, out


def test_validator_ignores_definition_in_fence() -> None:
    # A definition row shown verbatim inside a fence is not a real (duplicate) definition.
    code, out = run_validator(make_fenced_dup_def_map())
    assert code == 0, out


def test_validator_allows_escaped_pipe_in_cell() -> None:
    # `\|` is the schema's sanctioned literal pipe; it must not count as a column separator.
    code, out = run_validator(make_escaped_pipe_map())
    assert code == 0, out


def test_validator_hints_glued_id_inside_bold() -> None:
    code, out = run_validator(make_glued_inner_map())
    assert code == 1, out
    assert "glued into the ID cell" in out, out


def test_parser_ignores_fenced_nodes() -> None:
    # The graph parser must also skip fenced examples — no phantom C9 node from the example.
    g = parse_map(make_fenced_node_map())
    assert "C1" in g["nodes"] and "C9" not in g["nodes"], list(g["nodes"])


def test_template_validates_clean() -> None:
    # The template is what the agent copies to start a map, so it must stay schema-correct
    # (resolvable refs, ID-alone cells, consistent columns). Guards against template drift.
    template = TOOLS.parent / "method" / "templates" / "project-map.template.md"
    code, out = run_validator(template.read_text(encoding="utf-8"))
    assert code == 0, out


def test_render_produces_self_contained_html() -> None:
    # render.py: map -> HTML in one step, with the pinned+SRI libs inlined.
    with tempfile.TemporaryDirectory() as d:
        md = Path(d) / "project-map.md"
        md.write_text(make_grouped_map("proper"), encoding="utf-8")
        out = Path(d) / "project-map.html"
        r = subprocess.run(
            [sys.executable, str(TOOLS / "viewer" / "render.py"), str(md), str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        html = out.read_text(encoding="utf-8")
        assert 'integrity="sha384-' in html and "Front door" in html


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"ok   {fn.__name__}")
        except Exception as e:  # noqa: BLE001 — test runner reports every failure
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
