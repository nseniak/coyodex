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
