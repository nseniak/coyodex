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
from typing import cast

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))            # schema_v1, validate_analysis
sys.path.insert(0, str(TOOLS / "viewer"))  # build_graph

import build_graph  # noqa: E402
import gen_viewer  # noqa: E402
import schema_v1  # noqa: E402
import validate_analysis  # noqa: E402

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


def make_domain_map(cards: str | None = None) -> str:
    """A minimal valid map whose T5 is domain CARDS. `cards` overrides the default two-entity body
    (Order contains LineItem; LineItem uses a bullet-list FIELDS)."""
    body = cards if cards is not None else (
        "**E1 — Order** *(orders collection)*\n"
        "MEANING: a purchase\n"
        "FIELDS: id:ObjectId PK · status:string\n"
        "RELATIONS: contains 1→* E2 LineItem\n"
        "SOURCE: [order.py](order.py#L12)\n\n"
        "**E2 — LineItem**\n"
        "MEANING: a line\n"
        "FIELDS:\n"
        "  - sku: string\n"
        "  - qty: int\n"
        "SOURCE: [order.py](order.py#L58)\n"
    )
    return _VALID_HEAD + "## T5 — Domain model (domain cards)\n\n" + body


def make_gp_map() -> str:
    """A two-step Golden Path: GP1 (UC1, actor Andy) touches C1+C2; GP2 (UC2, actor Adam) touches
    C2+D1. Exercises the GP sequence (actors from UCs) and the per-step induced subgraph."""
    return (
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n"
        "|---|---|---|---|\n"
        "| **UC1** | Submit | Andy | submits -> stored |\n"
        "| **UC2** | Approve | Adam | approves -> done |\n\n"
        "## T1\n"
        "| ID | Component | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|\n"
        "| **C1** | Gateway | x | f | C2 |\n"
        "| **C2** | Engine | x | f | D1 |\n\n"
        "## T2\n"
        "| ID | Name | Type | Used for | Where configured | Conf. |\n"
        "|---|---|---|---|---|---|\n"
        "| **D1** | Cache | store | speed | env | V |\n\n"
        "## Golden Path\n"
        "**GP1 — Submit order** *(UC1)*\n"
        "STORY: Andy submits.\n"
        "UNDER THE HOOD: C1 calls C2.\n"
        "`Touches:` C1, C2\n\n"
        "**GP2 — Approve order** *(UC2)*\n"
        "STORY: Adam approves.\n"
        "`Touches:` C2, D1\n\n"
        "### edges\n"
        "| From | Verb | To | Why | Where |\n"
        "|---|---|---|---|---|\n"
        "| C1 | calls | C2 | reach engine | f |\n"
        "| C2 | reads | D1 | cache | f |\n"
    )


def make_gp_explicit_actor_map(actor_line: str = "Actor: Org admin") -> str:
    """GP1 bundles UC21 (End user) + UC22; without an Actor line the lane derives from the first UC
    = 'End user'. The `Actor:` line overrides it. `actor_line` lets a test inject a bad/blank value
    (mirrors the real mcpolis GP1, where the admin signs in via an end-user sign-in use case)."""
    return (
        "## Roles (actors)\n"
        "| Role | Kind | What they want | Use cases they drive |\n"
        "|---|---|---|---|\n"
        "| **Org admin** | human | manage | UC22 |\n"
        "| **End user** | human | use | UC21, UC22 |\n\n"
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n"
        "|---|---|---|---|\n"
        "| **UC21** | Sign in | End user | a -> b |\n"
        "| **UC22** | Create org | End user / Org admin | a -> b |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | A | x | f |  |\n\n"
        "## Golden Path\n"
        "**GP1 — Admin signs in and creates the org** *(UC21, UC22)*\n"
        + (actor_line + "\n" if actor_line else "")
        + "STORY: x\n`Touches:` C1\n"
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


def test_container_edges_list_crossing_component_edges() -> None:
    # Each inter-subsystem arrow 'A>B' carries the underlying component->component edges (endpoints,
    # names, verb, why) so the viewer lists their meanings in the arrow's hover tooltip.
    ce = gen_viewer.gen_container_edges(parse_map(make_card_map()))
    assert set(ce) == {"S1>S2"}                          # only the crossing direction
    rows = ce["S1>S2"]
    assert {(r["src"], r["dst"]) for r in rows} == {("C1", "C2"), ("C3", "C2")}
    assert {r["srcName"] for r in rows} == {"Front door", "Router"}
    assert all(r["verb"] == "calls" and r["why"] == "reach engine" for r in rows)


def test_render_inlines_edge_card_data() -> None:
    # The self-contained HTML must carry the edge-card diagrams AND the per-arrow component-edge
    # lists for the client to open on click / preview on hover (placeholder fully substituted).
    with tempfile.TemporaryDirectory() as d:
        md = Path(d) / "project-map.md"
        md.write_text(make_card_map(), encoding="utf-8")
        out = Path(d) / "project-map.html"
        r = subprocess.run(
            [sys.executable, str(TOOLS / "viewer" / "render.py"), str(md), str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        html = out.read_text(encoding="utf-8")
        assert "S1>S2" in html and "__CONTAINER_EDGES__" not in html


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
        assert 'rel="icon"' in html   # inline favicon -> no /favicon.ico 404, stays self-contained


# --- domain cards (T5) ----------------------------------------------------------
def test_parse_card_fields_markers() -> None:
    fs = schema_v1.parse_card_fields(["id: ObjectId PK", "email: string unique", "note"])
    assert (fs[0].name, fs[0].type, fs[0].markers) == ("id", "ObjectId", ["PK"])
    assert fs[1].markers == ["unique"]
    assert fs[2].type == ""   # missing type -> empty, so the validator can flag it


def test_parse_card_fields_glued_suffix_markers() -> None:
    """`[]` / `?` glued to the type (no space) must normalize to a bare type + marker, identical to
    the spaced form — else an `E`-typed collection field's box type and its relation arrow label
    both break silently. Regression for OAuthStateSnapshot.access_tokens:E28[]."""
    glued = schema_v1.parse_card_fields(["access_tokens: E28[]", "expires_at: int?", "scopes: string[]"])
    assert (glued[0].type, glued[0].markers) == ("E28", ["[]"])     # entity-typed collection
    assert (glued[1].type, glued[1].markers) == ("int", ["?"])      # nullable scalar
    assert (glued[2].type, glued[2].markers) == ("string", ["[]"])  # scalar collection
    # glued and spaced forms parse identically
    spaced = schema_v1.parse_card_fields(["access_tokens: E28 []"])
    assert (spaced[0].type, spaced[0].markers) == ("E28", ["[]"])
    # a glued marker followed by a normal marker still works
    both = schema_v1.parse_card_fields(["tags: string[] unique"])
    assert (both[0].type, both[0].markers) == ("string", ["[]", "unique"])


def test_glued_collection_relation_is_labelled() -> None:
    """An entity-typed collection field written glued (`tokens:E28[]`) must still BACK its relation,
    so the composition arrow renders its real field name as the label (not blank)."""
    cards = (
        "**E1 — Snapshot** *(s)*\nMEANING: m\n"
        "FIELDS: clients:json · access_tokens:E28[]\n"
        "RELATIONS: contains 1→* E28 StoredAccessToken\nSOURCE: [f](f#L1)\n\n"
        "**E28 — StoredAccessToken**\nMEANING: m\nFIELDS: token:string PK\nSOURCE: [f](f#L2)\n"
    )
    g = parse_map(cards)
    rel = [e for e in g["edges"] if e["src"] == "E1" and e["dst"] == "E28"][0]
    assert rel["fk_field"] == "access_tokens" and rel["fk_side"] == "src"


def test_parse_card_relations_kinds_and_cardinality() -> None:
    rels = schema_v1.parse_card_relations("contains 1→* E2 · isA E9 · uses *→1 E3 · 2..5→* E4")
    assert [(r.verb, r.kind, r.target, r.ok) for r in rels[:3]] == [
        ("contains", "composition", "E2", True),
        ("isA", "inheritance", "E9", True),
        ("uses", "association", "E3", True),
    ]
    assert rels[1].src_card is None and rels[1].dst_card is None  # isA: no cardinality
    assert rels[3].ok is False   # `2..5` is not an allowed cardinality token


def test_parser_domain_cards_nodes_attrs_edges() -> None:
    g = parse_map(make_domain_map())
    e1 = g["nodes"]["E1"]
    assert e1["kind"] == "entity" and e1["name"] == "Order"
    assert cast("dict[str, str]", e1["fields"])["Stored"] == "orders collection"
    attrs1 = cast("list[dict[str, str]]", e1["attrs"])
    assert any(a["name"] == "id" and a["type"] == "ObjectId" and a["markers"] == "PK" for a in attrs1)
    attrs2 = cast("list[dict[str, str]]", g["nodes"]["E2"]["attrs"])
    assert {a["name"] for a in attrs2} == {"sku", "qty"}   # bullet-list FIELDS
    rel = [e for e in g["edges"] if e["src"] == "E1" and e["dst"] == "E2"]
    assert rel and rel[0]["verb"] == "contains" and rel[0]["kind"] == "composition"
    assert rel[0]["src_card"] == "1" and rel[0]["dst_card"] == "*"


def test_gen_domain_mermaid_classdiagram() -> None:
    mm = gen_viewer.gen_domain_mermaid(parse_map(make_domain_map()))
    assert mm.startswith("classDiagram")
    assert 'class E1["Order"]' in mm
    assert "ObjectId id" in mm                          # attribute rendered in the box
    assert 'E1 "1" *-- "*" E2' in mm                    # composition arrow + cardinality
    assert ": contains" not in mm                       # redundant structural verb is not drawn as a label


def test_gen_domain_mermaid_resolves_embedded_entity_type() -> None:
    # a field typed by an entity id (`mode:E2`) renders with the entity's NAME, not the raw id.
    cards = (
        "**E1 — Order** *(s)*\nMEANING: m\nFIELDS: mode:E2 · id:int\nSOURCE: [f](f#L1)\n\n"
        "**E2 — AuthMode**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n"
    )
    mm = gen_viewer.gen_domain_mermaid(parse_map(make_domain_map(cards)))
    assert "AuthMode mode" in mm and "E2 mode" not in mm


def test_gen_domain_mermaid_shows_collection_marker_in_box() -> None:
    # a `[]` (collection) marker is part of the type SHAPE, so it renders in the box member —
    # `StoredRefreshToken[] refresh_tokens`, not a single-valued-looking `StoredRefreshToken …`.
    # `?`/PK/FK stay out of the box (annotations, panel-only).
    cards = (
        "**E1 — Snapshot** *(s)*\nMEANING: m\n"
        "FIELDS: refresh_tokens:E2[] · expires_at:int ? · id:int PK\n"
        "RELATIONS: contains 1→* E2 StoredRefreshToken\nSOURCE: [f](f#L1)\n\n"
        "**E2 — StoredRefreshToken**\nMEANING: m\nFIELDS: token:string\nSOURCE: [f](f#L2)\n"
    )
    mm = gen_viewer.gen_domain_mermaid(parse_map(make_domain_map(cards)))
    assert "StoredRefreshToken[] refresh_tokens" in mm   # collection shown in the box
    assert "int expires_at" in mm and "int? " not in mm  # nullable marker stays out of the box
    assert "int id" in mm                                # PK stays out of the box


def test_gen_domain_mermaid_relation_labels() -> None:
    # forward field -> plain name; reverse FK (FK→E1) -> "↩ field"; the redundant verb is dropped.
    cards = (
        "**E1 — Org** *(s)*\nMEANING: m\nFIELDS: id:string PK · subscription:E3\n"
        "RELATIONS: has 1→* E2 Membership · contains 1→1 E3 Subscription\nSOURCE: [f](f#L1)\n\n"
        "**E2 — Membership**\nMEANING: m\nFIELDS: org_id:string FK→E1 · email:string\nSOURCE: [f](f#L2)\n\n"
        "**E3 — Subscription**\nMEANING: m\nFIELDS: tier:string\nSOURCE: [f](f#L3)\n"
    )
    mm = gen_viewer.gen_domain_mermaid(parse_map(make_domain_map(cards)))
    assert ": subscription" in mm     # forward: E1.subscription typed E3
    assert ": ↩ org_id" in mm          # reverse: E2.org_id FK→E1
    assert ": has" not in mm           # the redundant aggregation verb is not drawn


def test_gen_domain_mermaid_drops_ungrounded_verb() -> None:
    # an association not backed by any field gets NO label — the verb is interpretive, not grounded.
    cards = (
        "**E1 — A** *(s)*\nMEANING: m\nFIELDS: id:int\n"
        "RELATIONS: authorizes *→1 E2\nSOURCE: [f](f#L1)\n\n"
        "**E2 — B**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n"
    )
    mm = gen_viewer.gen_domain_mermaid(parse_map(make_domain_map(cards)))
    assert "authorizes" not in mm     # ungrounded association verb is not drawn as a label


def test_gen_domain_mermaid_forward_fk_label() -> None:
    # A foreign key on the SOURCE (`role:string FK→E2`) labels the arrow with the field name — the
    # symmetric counterpart of the reverse `↩` case, so a marked FK is represented whichever side
    # authored the relation (the asymmetry that left all but one mcpolis FK arrow blank is gone).
    cards = (
        "**E1 — Membership** *(s)*\nMEANING: m\nFIELDS: email:string · role:string FK→E2\n"
        "RELATIONS: assignedRole *→1 E2 RoleDefinition\nSOURCE: [f](f#L1)\n\n"
        "**E2 — RoleDefinition**\nMEANING: m\nFIELDS: name:string\nSOURCE: [f](f#L2)\n"
    )
    mm = gen_viewer.gen_domain_mermaid(parse_map(make_domain_map(cards)))
    assert ": role" in mm                  # forward FK -> the plain field name
    assert "↩" not in mm                   # not a back-reference (the field is on the source/tail)
    assert ": assignedRole" not in mm      # the verb itself is never drawn as the label


def test_fk_targets_token_exact() -> None:
    # `FK→E1` must resolve to exactly {E1} — never match inside `E11` (the substring bug class).
    assert schema_v1.fk_targets("FK→E1") == {"E1"}
    assert schema_v1.fk_targets(["?", "FK->E5"]) == {"E5"}      # ascii arrow + nullable marker
    assert "E1" not in schema_v1.fk_targets("FK→E11")


def test_parse_card_relations_how_note() -> None:
    rels = schema_v1.parse_card_relations(
        "tracks *→1 E3 Token {keyed by (org, upstream)} · contains 1→* E2")
    assert rels[0].how == "keyed by (org, upstream)" and rels[0].target == "E3" and rels[0].ok
    assert rels[1].how is None                                  # no note -> None


def test_parser_domain_edge_carries_backing_and_how() -> None:
    # The resolved backing (fk_field/fk_side) and the authored {how} note ride the serialized edge,
    # so the canvas label and the panel's "Implemented by" line come from one resolution.
    cards = (
        "**E1 — Org** *(s)*\nMEANING: m\nFIELDS: id:string PK\n"
        "RELATIONS: contains 1→* E2 Membership · tracks *→1 E3 Token {keyed by (org, upstream)}\n"
        "SOURCE: [f](f#L1)\n\n"
        "**E2 — Membership**\nMEANING: m\nFIELDS: org_id:string FK→E1\nSOURCE: [f](f#L2)\n\n"
        "**E3 — Token**\nMEANING: m\nFIELDS: value:string\nSOURCE: [f](f#L3)\n"
    )
    g = parse_map(make_domain_map(cards))
    e12 = next(e for e in g["edges"] if e["src"] == "E1" and e["dst"] == "E2")
    assert e12["fk_field"] == "org_id" and e12["fk_side"] == "dst"      # reverse FK on the target
    e13 = next(e for e in g["edges"] if e["src"] == "E1" and e["dst"] == "E3")
    assert e13["fk_field"] is None and e13["how"] == "keyed by (org, upstream)"  # indirect -> how-note


def test_check_entity_sources_flags_synthesized() -> None:
    # --check-sources reads each card's SOURCE file: an entity whose NAME isn't there is synthesized.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / ".coyodex").mkdir()
        (root / "model.py").write_text(
            "class Order:\n    pass\nclass ServiceTokenRecord:\n    pass\nclass Settings:\n    pass\n"
            "user_profile = dict  # a non-CamelCase type alias\n",
            encoding="utf-8",
        )
        map_path = root / ".coyodex" / "project-map.md"
        text = (
            "**E1 — Order** *(s)*\nMEANING: m\nFIELDS: id:int\nSOURCE: [model.py](model.py#L1)\n\n"
            "**E2 — OAuthState** *(s)*\nMEANING: m\nFIELDS: x:int\nSOURCE: [model.py](model.py#L1)\n\n"
            "**E3 — ServiceToken** *(s)*\nMEANING: m\nFIELDS: x:int\nSOURCE: [model.py](model.py#L1)\n\n"
            "**E4 — Settings (app env)** *(s)*\nMEANING: m\nFIELDS: x:int\nSOURCE: [model.py](model.py#L1)\n\n"
            "**E5 — user_profile** *(s)*\nMEANING: m\nFIELDS: x:int\nSOURCE: [model.py](model.py#L1)\n\n"
            "**E6 — ghost_state** *(s)*\nMEANING: m\nFIELDS: x:int\nSOURCE: [model.py](model.py#L1)\n"
        )
        map_path.write_text(text, encoding="utf-8")
        problems = " ".join(validate_analysis.check_entity_sources(text, map_path))
        assert "E2" in problems and "OAuthState" in problems   # absent entirely -> flagged
        assert "E1" not in problems                            # Order defined -> not flagged
        assert "E3" not in problems                            # ServiceToken ⊂ ServiceTokenRecord -> grounded
        assert "E4" not in problems                            # 'Settings (app env)' -> token Settings present
        assert "E5" not in problems                            # snake_case name present -> grounded
        assert "E6" in problems                                # snake_case name absent -> synthesized


def test_check_entity_sources_skips_unresolvable() -> None:
    # template/fixture SOURCE paths don't resolve to real files -> no-op (never false-flag).
    with tempfile.TemporaryDirectory() as d:
        map_path = Path(d) / "project-map.md"
        text = "**E1 — Ghost** *(s)*\nMEANING: m\nFIELDS: id:int\nSOURCE: [x.py](x.py#L1)\n"
        map_path.write_text(text, encoding="utf-8")
        assert validate_analysis.check_entity_sources(text, map_path) == []


def test_validator_domain_cards_clean() -> None:
    code, out = run_validator(make_domain_map())
    assert code == 0, out


def test_validator_flags_malformed_card_heading() -> None:
    # `**E1 — Order** (orders)` (plain parens, not *( )*) silently drops name+store — must fail loud.
    cards = "**E1 — Order** (orders)\nMEANING: m\nFIELDS: id:int\nSOURCE: [f](f#L1)\n"
    code, out = run_validator(make_domain_map(cards))
    assert code == 1 and "heading is malformed" in out, out


def test_validator_flags_untyped_field() -> None:
    cards = "**E1 — Order** *(s)*\nMEANING: m\nFIELDS: id\nSOURCE: [f](f#L1)\n"
    code, out = run_validator(make_domain_map(cards))
    assert code == 1 and "has no type" in out, out


def test_validator_flags_malformed_relation() -> None:
    cards = (
        "**E1 — Order** *(s)*\nMEANING: m\nFIELDS: id:int\n"
        "RELATIONS: contains 2..5→* E2\nSOURCE: [f](f#L1)\n\n"
        "**E2 — Line**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n"
    )
    code, out = run_validator(make_domain_map(cards))
    assert code == 1 and "malformed RELATIONS item" in out, out


def test_validator_flags_both_sided_relation() -> None:
    cards = (
        "**E1 — Order** *(s)*\nMEANING: m\nFIELDS: id:int\n"
        "RELATIONS: contains 1→* E2\nSOURCE: [f](f#L1)\n\n"
        "**E2 — Line**\nMEANING: m\nFIELDS: x:int\n"
        "RELATIONS: partOf *→1 E1\nSOURCE: [f](f#L2)\n"
    )
    code, out = run_validator(make_domain_map(cards))
    assert code == 1 and "declared on both cards" in out, out


def test_validator_flags_duplicate_relation_same_card() -> None:
    cards = (
        "**E1 — Order** *(s)*\nMEANING: m\nFIELDS: id:int\n"
        "RELATIONS: refersTo 1→1 E2 · refersTo 1→1 E2\nSOURCE: [f](f#L1)\n\n"
        "**E2 — Line**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n"
    )
    code, out = run_validator(make_domain_map(cards))
    assert code == 1 and "twice" in out, out


def test_validator_flags_noncanonical_relation_verb() -> None:
    # `composedOf` is a non-canonical alias for composition — the validator demands `contains`.
    cards = (
        "**E1 — Order** *(s)*\nMEANING: m\nFIELDS: id:int\n"
        "RELATIONS: composedOf 1→* E2\nSOURCE: [f](f#L1)\n\n"
        "**E2 — Line**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n"
    )
    code, out = run_validator(make_domain_map(cards))
    assert code == 1 and "non-canonical" in out and "contains" in out, out


def test_validator_flags_undefined_relation_target() -> None:
    cards = "**E1 — Order** *(s)*\nMEANING: m\nFIELDS: id:int\nRELATIONS: contains 1→* E9\nSOURCE: [f](f#L1)\n"
    code, out = run_validator(make_domain_map(cards))
    assert code == 1 and "E9" in out, out


def test_validator_flags_duplicate_card_id() -> None:
    cards = (
        "**E1 — Order** *(s)*\nMEANING: m\nFIELDS: id:int\nSOURCE: [f](f#L1)\n\n"
        "**E1 — Dup**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n"
    )
    code, out = run_validator(make_domain_map(cards))
    assert code == 1 and "Duplicate" in out, out


def test_validator_warns_unbacked_association() -> None:
    # An association with no backing field and no {how} note draws nothing + explains nothing: warn
    # (non-blocking — the build still passes) so the author marks the FK or writes a how-note.
    cards = (
        "**E1 — A** *(s)*\nMEANING: m\nFIELDS: id:int\n"
        "RELATIONS: authorizes *→1 E2\nSOURCE: [f](f#L1)\n\n"
        "**E2 — B**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n"
    )
    code, out = run_validator(make_domain_map(cards))
    assert code == 0, out                                     # advisory only — does not fail the build
    assert "WARNINGS" in out and "not backed by a field" in out, out


def test_validator_how_note_silences_unbacked_warning() -> None:
    # A {how} note is the author's explanation of how a field-less relation is implemented -> no warning.
    cards = (
        "**E1 — A** *(s)*\nMEANING: m\nFIELDS: id:int\n"
        "RELATIONS: authorizes *→1 E2 {linked via an external id map}\nSOURCE: [f](f#L1)\n\n"
        "**E2 — B**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n"
    )
    code, out = run_validator(make_domain_map(cards))
    assert code == 0 and "not backed by a field" not in out, out


def test_validator_forward_fk_not_flagged_unbacked() -> None:
    # A marked forward FK (`role:string FK→E2`) IS a backing field — the completeness nudge stays quiet.
    cards = (
        "**E1 — A** *(s)*\nMEANING: m\nFIELDS: id:int · role:string FK→E2\n"
        "RELATIONS: assignedRole *→1 E2\nSOURCE: [f](f#L1)\n\n"
        "**E2 — B**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n"
    )
    code, out = run_validator(make_domain_map(cards))
    assert code == 0 and "not backed by a field" not in out, out


# --- domain contexts (SD) -------------------------------------------------------
def make_context_map(cards: str | None = None, contexts: str | None = None) -> str:
    """A domain map with a Subdomains (SD) table + `SUBDOMAIN:` lines on the cards. Default: two contexts
    (SD1 Ordering, SD2 Catalog); E1/E2 live in SD1, E4 in SD2; E1 contains E2 (intra-context) and
    refersTo E4 (the one CROSS-context relation), so the tests exercise membership + a crossing edge."""
    ctx = contexts if contexts is not None else (
        "## Subdomains (SD)\n"
        "| ID | Subdomain | Purpose | Parent | Anchor | Conf. |\n"
        "|---|---|---|---|---|---|\n"
        "| **SD1** | Ordering | purchase lifecycle |  | [order.py](order.py#L1) | inferred |\n"
        "| **SD2** | Catalog | products |  | [product.py](product.py#L1) | inferred |\n\n"
    )
    body = cards if cards is not None else (
        "**E1 — Order** *(orders)*\nSUBDOMAIN: SD1\nMEANING: a purchase\n"
        "FIELDS: id:ObjectId PK · product:E4\n"
        "RELATIONS: contains 1→* E2 LineItem · refersTo *→1 E4 Product\nSOURCE: [order.py](order.py#L12)\n\n"
        "**E2 — LineItem**\nSUBDOMAIN: SD1\nMEANING: a line\nFIELDS: sku:string\nSOURCE: [order.py](order.py#L58)\n\n"
        "**E4 — Product**\nSUBDOMAIN: SD2\nMEANING: a product\nFIELDS: name:string\nSOURCE: [product.py](product.py#L9)\n"
    )
    return _VALID_HEAD + ctx + "## T5 — Domain model (domain cards)\n\n" + body


def test_iter_domain_cards_parses_context() -> None:
    by_id = {c.id: c for c in schema_v1.iter_domain_cards(make_context_map().splitlines())}
    assert by_id["E1"].subdomain == "SD1" and by_id["E2"].subdomain == "SD1" and by_id["E4"].subdomain == "SD2"


def test_membership_picks_parent_for_context_rows() -> None:
    # a Subdomains-table row's 'Context' header is its NAME column; its parent pointer is 'parent'.
    assert schema_v1.membership_ids(
        "SD2", ["**SD2**", "Catalog", "x", "SD1"], ["id", "subdomain", "purpose", "parent"]) == ["SD1"]


def test_parser_entity_gets_context_parent_and_context_nodes() -> None:
    g = parse_map(make_context_map())
    assert g["nodes"]["E1"]["parent"] == "SD1" and g["nodes"]["E4"]["parent"] == "SD2"
    ctx = {k: v for k, v in g["nodes"].items() if v["kind"] == "subdomain"}
    assert set(ctx) == {"SD1", "SD2"} and ctx["SD1"]["name"] == "Ordering"


def test_parser_entity_without_context_has_no_parent() -> None:
    # An ungrouped domain model (no Subdomains table, no CONTEXT line) leaves entities parent-less.
    assert parse_map(make_domain_map())["nodes"]["E1"]["parent"] is None


def test_validator_context_map_clean() -> None:
    code, out = run_validator(make_context_map())
    assert code == 0, out


def test_validator_flags_undefined_context() -> None:
    ctx = ("## Subdomains (SD)\n| ID | Subdomain | Purpose | Parent | Anchor | Conf. |\n"
           "|---|---|---|---|---|---|\n| **SD1** | Ordering | x |  | a | V |\n\n")
    cards = "**E1 — Order** *(s)*\nSUBDOMAIN: SD9\nMEANING: m\nFIELDS: id:int\nSOURCE: [f](f#L1)\n"
    code, out = run_validator(_VALID_HEAD + ctx + "## T5\n\n" + cards)
    assert code == 1 and "SD9" in out, out


def test_validator_contexts_guard_fires_on_missing_membership() -> None:
    # A Subdomains table with NO card assigned (no CONTEXT line) is the silent disconnected-boxes case.
    ctx = ("## Subdomains (SD)\n| ID | Subdomain | Purpose | Parent | Anchor | Conf. |\n"
           "|---|---|---|---|---|---|\n| **SD1** | Ordering | x |  | a | V |\n\n")
    cards = "**E1 — Order** *(s)*\nMEANING: m\nFIELDS: id:int\nSOURCE: [f](f#L1)\n"
    code, out = run_validator(_VALID_HEAD + ctx + "## T5\n\n" + cards)
    assert code == 1 and "no entity is assigned" in out, out


def test_validator_warns_ungrouped_entity() -> None:
    # Some entities carry a context, one doesn't -> non-blocking warning, build still passes.
    ctx = ("## Subdomains (SD)\n| ID | Subdomain | Purpose | Parent | Anchor | Conf. |\n"
           "|---|---|---|---|---|---|\n| **SD1** | Ordering | x |  | a | V |\n\n")
    cards = (
        "**E1 — Order** *(s)*\nSUBDOMAIN: SD1\nMEANING: m\nFIELDS: id:int\nSOURCE: [f](f#L1)\n\n"
        "**E2 — Line**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n"
    )
    code, out = run_validator(_VALID_HEAD + ctx + "## T5\n\n" + cards)
    assert code == 0, out
    assert "ungrouped" in out.lower() and "E2" in out, out


def test_validator_catches_context_cycle() -> None:
    ctx = ("## Subdomains (SD)\n| ID | Subdomain | Purpose | Parent | Anchor | Conf. |\n"
           "|---|---|---|---|---|---|\n"
           "| **SD1** | A | x | SD2 | a | V |\n| **SD2** | B | x | SD1 | a | V |\n\n")
    cards = "**E1 — Order** *(s)*\nSUBDOMAIN: SD1\nMEANING: m\nFIELDS: id:int\nSOURCE: [f](f#L1)\n"
    code, out = run_validator(_VALID_HEAD + ctx + "## T5\n\n" + cards)
    assert code == 1 and "cycle" in out.lower(), out


def test_validator_flags_context_parent_wrong_kind() -> None:
    # A Subdomains row whose Parent is a subsystem (S1), not another context — caught by the kind check.
    pre = (
        "## Subsystems\n| ID | Subsystem | Purpose | Parent | Anchor | Conf. |\n"
        "|---|---|---|---|---|---|\n| **S1** | Edge | x |  | a | V |\n\n"
        "## Subdomains (SD)\n| ID | Subdomain | Purpose | Parent | Anchor | Conf. |\n"
        "|---|---|---|---|---|---|\n| **SD1** | A | x | S1 | a | V |\n\n"
        "## T1\n| ID | Component | Subsystem | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|---|\n| **C1** | App | S1 | x | f |  |\n\n"
    )
    cards = "**E1 — Order** *(s)*\nSUBDOMAIN: SD1\nMEANING: m\nFIELDS: id:int\nSOURCE: [f](f#L1)\n"
    code, out = run_validator(_VALID_HEAD + pre + "## T5\n\n" + cards)
    assert code == 1 and "is not a subdomain" in out, out


def test_validator_ignores_prose_cx_without_contexts() -> None:
    # No Subdomains table / CONTEXT line: a stray "SD1" in prose is not treated as a reference (additive).
    md = ("# X\nThe SD1 module is internal.\n"
          "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n"
          "|---|---|---|---|---|\n| **C1** | App | x | f |  |\n")
    code, out = run_validator(md)
    assert code == 0, out


def make_bridge_map() -> str:
    """Subsystems S1/S2 + context SD1 with entity E1; C1 (S1) persists E1, C2 (S2) reads E1. Exercises
    the S→SD bridge: the owning subsystem's card shows an `owns` arrow, the reader's a `reads` arrow."""
    return (
        "## Subsystems (S)\n| ID | Subsystem | Purpose | Parent | Anchor | Conf. |\n"
        "|---|---|---|---|---|---|\n| **S1** | Edge | x |  | a | V |\n| **S2** | Core | x |  | a | V |\n\n"
        "## Subdomains (SD)\n| ID | Subdomain | Purpose | Parent | Anchor | Conf. |\n"
        "|---|---|---|---|---|---|\n| **SD1** | Ordering | x |  | a | V |\n\n"
        "## T1\n| ID | Component | Subsystem | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|---|\n| **C1** | Writer | S1 | x | f |  |\n| **C2** | Reader | S2 | x | f |  |\n\n"
        "## T5\n\n**E1 — Order** *(orders)*\nSUBDOMAIN: SD1\nMEANING: m\nFIELDS: id:int\nSOURCE: [f](f#L1)\n\n"
        "### edges\n| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | persists | E1 | store | f |\n| C2 | reads | E1 | load | f |\n"
    )


def test_has_subdomains() -> None:
    assert gen_viewer.has_subdomains(parse_map(make_context_map())) is True
    assert gen_viewer.has_subdomains(parse_map(make_domain_map())) is False   # domain model, but ungrouped


def test_gen_domain_container_mermaid_boxes_and_crossing_arrow() -> None:
    # The bounded-contexts overview: one box per context labelled by entity count, with a SDa->SDb
    # arrow DERIVED from a crossing E->E relation (E1 in SD1 refersTo E4 in SD2), labelled by count.
    mm = gen_viewer.gen_domain_container_mermaid(parse_map(make_context_map()))
    assert mm.startswith("flowchart")
    assert 'SD1["Ordering (2)"]' in mm and 'SD2["Catalog (1)"]' in mm   # count = #entities in the context
    assert "class SD1 subdomain" in mm
    assert "SD1 -->|1| SD2" in mm                                       # the one crossing relation


def test_gen_domain_container_edges_list_crossing_relations() -> None:
    ce = gen_viewer.gen_domain_container_edges(parse_map(make_context_map()))
    assert set(ce) == {"SD1>SD2"}                                       # only the crossing direction
    rows = ce["SD1>SD2"]
    assert {(r["src"], r["dst"]) for r in rows} == {("E1", "E4")}
    assert rows[0]["srcName"] == "Order" and rows[0]["dstName"] == "Product" and rows[0]["verb"] == "refersTo"


def test_gen_domain_subdomain_card_members_full_neighbours_collapsed() -> None:
    cards = gen_viewer.domain_subdomain_mermaids(parse_map(make_context_map()))
    assert set(cards) == {"SD1", "SD2"}
    cx1 = cards["SD1"]
    assert cx1.startswith("classDiagram")
    assert 'class E1["Order"] {' in cx1 and "ObjectId id" in cx1        # member entity, FULL box
    assert 'class E2["LineItem"] {' in cx1                              # the other member, full
    assert 'class E4["Product"]' in cx1 and 'class E4["Product"] {' not in cx1  # cross-context neighbour, COLLAPSED
    assert 'E1 "1" *-- "*" E2' in cx1                                   # intra-context composition
    assert ": product" in cx1                                          # the cross relation, labelled by its backing field
    # in SD2's card the roles flip: E4 is full, E1 is the collapsed neighbour
    cx2 = cards["SD2"]
    assert 'class E4["Product"] {' in cx2 and 'class E1["Order"] {' not in cx2


def test_subsystem_card_bridges_to_contexts_owns_and_reads() -> None:
    by_sub = gen_viewer.subsystem_component_mermaids(parse_map(make_bridge_map()))
    s1 = by_sub["S1"]
    assert "class SD1 subdomain" in s1 and "C1 -->|owns| SD1" in s1       # persists -> the subsystem OWNS the context
    s2 = by_sub["S2"]
    assert "class SD1 subdomain" in s2 and "C2 -->|reads| SD1" in s2      # reads -> it merely CONSUMES it


def test_subsystem_card_has_no_context_box_without_bridges() -> None:
    # Regression: a map with no C->E edges draws no subdomain box / classDef in the subsystem card.
    s1 = gen_viewer.subsystem_component_mermaids(parse_map(make_card_map()))["S1"]
    assert "subdomain" not in s1


def test_render_inlines_context_data() -> None:
    # The self-contained HTML must carry the contexts overview + per-context cards, every new
    # placeholder substituted, and HAS_CONTEXTS flipped on, so the Domain view leads with the overview.
    with tempfile.TemporaryDirectory() as d:
        md = Path(d) / "project-map.md"
        md.write_text(make_context_map(), encoding="utf-8")
        out = Path(d) / "project-map.html"
        r = subprocess.run(
            [sys.executable, str(TOOLS / "viewer" / "render.py"), str(md), str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        html = out.read_text(encoding="utf-8")
        for ph in ("__MERMAID_DOMAIN_CONTAINER__", "__MERMAID_DOMAIN_SUB__",
                   "__DOMAIN_CONTAINER_EDGES__", "__HAS_SUBDOMAINS__"):
            assert ph not in html, ph
        assert "const HAS_SUBDOMAINS = true;" in html
        assert "Ordering (2)" in html       # the bounded-contexts overview is inlined


def test_render_no_context_data_when_ungrouped() -> None:
    # A domain map with no Subdomains table: HAS_CONTEXTS is false and the flat classDiagram still ships.
    with tempfile.TemporaryDirectory() as d:
        md = Path(d) / "project-map.md"
        md.write_text(make_domain_map(), encoding="utf-8")
        out = Path(d) / "project-map.html"
        r = subprocess.run(
            [sys.executable, str(TOOLS / "viewer" / "render.py"), str(md), str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        html = out.read_text(encoding="utf-8")
        assert "const HAS_SUBDOMAINS = false;" in html and "__HAS_SUBDOMAINS__" not in html


def _two_context_map(cards_extra: str = "") -> str:
    """SD1 (Ordering, has E1) + SD2 (Catalog, EMPTY — no card assigned to it)."""
    ctx = ("## Subdomains (SD)\n| ID | Subdomain | Purpose | Parent | Anchor | Conf. |\n"
           "|---|---|---|---|---|---|\n| **SD1** | Ordering | x |  | a | V |\n| **SD2** | Catalog | x |  | a | V |\n\n")
    cards = "**E1 — Order** *(s)*\nSUBDOMAIN: SD1\nMEANING: m\nFIELDS: id:int\nSOURCE: [f](f#L1)\n" + cards_extra
    return _VALID_HEAD + ctx + "## T5\n\n" + cards


def test_gen_domain_subdomain_card_empty_context_is_valid_mermaid() -> None:
    # A defined-but-empty context must still produce a VALID classDiagram — a body-less `classDiagram`
    # crashes Mermaid on drill (the F1 regression). It carries a self-explaining placeholder instead.
    card = gen_viewer.gen_domain_subdomain_card(parse_map(_two_context_map()), "SD2")
    assert card.startswith("classDiagram") and card.strip() != "classDiagram"   # has a body
    assert "no entities" in card and "Catalog" in card
    # the placeholder id carries no prefix+digits, so the viewer's id bridge skips it (not clickable)
    assert "EmptySubdomain" in card


def test_validator_warns_empty_context() -> None:
    # A leaf context with no member entities -> non-blocking warning (likely a leftover / typo'd id).
    code, out = run_validator(_two_context_map())
    assert code == 0, out                                          # advisory only
    assert "Subdomains with no entities" in out and "SD2" in out, out


def test_validator_no_empty_warning_for_parent_context() -> None:
    # A non-leaf context (parent of another) with no DIRECT entities is NOT empty -> no false warning.
    ctx = ("## Subdomains (SD)\n| ID | Subdomain | Purpose | Parent | Anchor | Conf. |\n"
           "|---|---|---|---|---|---|\n| **SD1** | Domain | x |  | a | V |\n| **SD2** | Ordering | x | SD1 | a | V |\n\n")
    cards = "**E1 — Order** *(s)*\nSUBDOMAIN: SD2\nMEANING: m\nFIELDS: id:int\nSOURCE: [f](f#L1)\n"
    code, out = run_validator(_VALID_HEAD + ctx + "## T5\n\n" + cards)
    assert code == 0, out
    assert "Subdomains with no entities" not in out, out             # SD1 is a parent, not empty


def make_both_groupings_map() -> str:
    """A map with BOTH groupings + the cross-altitude edges that triggered the leak: S1{C1}, S2{C2};
    SD1{E1,E2}, SD2{E3}; a C1->C2 component edge (S→S crossing), C1 persists E1 + C2 persists E3
    (C→E bridge edges), and E1 refersTo E3 (an E→E relation crossing SD1→SD2). The Subsystems overview
    must show ONLY S→S and never a SD box; the Domain overview ONLY SD→SD and never an S box."""
    return (
        "## Subsystems (S)\n| ID | Subsystem | Purpose | Parent | Anchor | Conf. |\n"
        "|---|---|---|---|---|---|\n| **S1** | Edge | x |  | a | V |\n| **S2** | Core | x |  | a | V |\n\n"
        "## Subdomains (SD)\n| ID | Subdomain | Purpose | Parent | Anchor | Conf. |\n"
        "|---|---|---|---|---|---|\n| **SD1** | Ordering | x |  | a | V |\n| **SD2** | Catalog | x |  | a | V |\n\n"
        "## T1\n| ID | Component | Subsystem | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|---|\n| **C1** | Front | S1 | x | f | C2 |\n| **C2** | Core | S2 | x | f |  |\n\n"
        "## T5\n\n"
        "**E1 — Order** *(s)*\nSUBDOMAIN: SD1\nMEANING: m\nFIELDS: id:int · product:E3\n"
        "RELATIONS: contains 1→* E2 Line · refersTo *→1 E3 Product\nSOURCE: [f](f#L1)\n\n"
        "**E2 — Line**\nSUBDOMAIN: SD1\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n\n"
        "**E3 — Product**\nSUBDOMAIN: SD2\nMEANING: m\nFIELDS: y:int\nSOURCE: [f](f#L3)\n\n"
        "### edges\n| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | calls | C2 | reach core | f |\n"
        "| C1 | persists | E1 | store order | f |\n"
        "| C2 | persists | E3 | store product | f |\n"
    )


def test_container_overview_excludes_contexts() -> None:
    # The bug class: with C→E / E→E edges present, the Subsystems overview must NOT pick up entity
    # endpoints (whose top group is a CONTEXT) and invent S→SD / SD→SD arrows that draw bare SD boxes.
    g = parse_map(make_both_groupings_map())
    mm = gen_viewer.gen_container_mermaid(g)
    assert "SD" not in mm                                  # no subdomain box / arrow leaks in
    assert "S1 -->|1| S2" in mm                            # the real S→S crossing (C1->C2), count 1 (not inflated by C→E)
    # the Domain overview is the mirror: contexts only, no subsystem leak
    dmm = gen_viewer.gen_domain_container_mermaid(g)
    assert "SD1 -->|1| SD2" in dmm and "S1" not in dmm and "S2" not in dmm  # SD→SD present, no subsystem box leaks in


def test_container_edges_exclude_contexts() -> None:
    ce = gen_viewer.gen_container_edges(parse_map(make_both_groupings_map()))
    assert set(ce) == {"S1>S2"}                            # only the real subsystem pair, no S>SD keys


def test_edge_cards_exclude_contexts() -> None:
    cards = gen_viewer.edge_card_mermaids(parse_map(make_both_groupings_map()))
    assert set(cards) == {"S1>S2"}                         # no spurious S>SD edge card


# --- C->E ownership nudge --------------------------------------------------------
def make_owner_map(e2_embedded: bool = False) -> str:
    """C1 persists E1 (an owner). E2 has no owner; embedded in E1 (contains) only when e2_embedded."""
    rel = "RELATIONS: contains 1→* E2 Line\n" if e2_embedded else ""
    return (
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | OrderRepo | x | f |  |\n\n"
        "## T5\n\n"
        "**E1 — Order** *(s)*\nMEANING: m\nFIELDS: id:int\n" + rel + "SOURCE: [f](f#L1)\n\n"
        "**E2 — Line**\nMEANING: m\nFIELDS: x:int\nSOURCE: [f](f#L2)\n\n"
        "### edges\n| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | persists | E1 | store | f |\n"
    )


def test_validator_warns_unowned_entity() -> None:
    # E1 has an owner (C1 persists E1); E2 has none and isn't embedded -> non-blocking nudge lists E2.
    code, out = run_validator(make_owner_map())
    assert code == 0, out
    assert "no owning component" in out and "E2" in out, out


def test_validator_no_owner_warning_when_nothing_owned() -> None:
    # No persists/writes C→E edge at all -> the map doesn't author ownership -> silent (don't nag).
    md = make_owner_map().replace("| C1 | persists | E1 | store | f |\n", "")
    code, out = run_validator(md)
    assert code == 0 and "no owning component" not in out, out


def test_validator_embedded_entity_exempt_from_owner_warning() -> None:
    # E2 is embedded in E1 (contains) -> persisted via its container -> not flagged as unowned.
    code, out = run_validator(make_owner_map(e2_embedded=True))
    assert code == 0 and "no owning component" not in out, out


# --- Golden Path (GP) -----------------------------------------------------------
def test_parser_gp_captures_uc_and_touches() -> None:
    g = parse_map(make_gp_map())
    steps = {s["id"]: s for s in g["gp"]}
    assert steps["GP1"]["uc"] == "UC1" and steps["GP2"]["uc"] == "UC2"
    assert steps["GP1"]["touches"] == ["C1", "C2"]
    assert steps["GP2"]["touches"] == ["C2", "D1"]


def test_gen_gp_mermaid_black_box_sequence() -> None:
    # Level 1: a sequenceDiagram whose lifelines are the actors derived from each step's UC, with one
    # message per step. The label is the step TITLE only — no `GPn` id (the viewer pairs by order).
    mm = gen_viewer.gen_gp_mermaid(parse_map(make_gp_map()))
    assert mm.startswith("sequenceDiagram")
    assert "actor GPA0 as Andy" in mm and "actor GPA1 as Adam" in mm  # one lifeline per distinct actor
    assert "participant GPSYS" in mm
    assert "GPA0->>GPSYS: Submit order" in mm
    assert "GPA1->>GPSYS: Approve order" in mm
    assert "GP1" not in mm and "GP2" not in mm  # step ids no longer leak into the message labels


def test_gen_gp_mermaid_actor_fallback_without_uc() -> None:
    # A GP step with no `*(UCn)*` tag falls back to a generic 'Actor' lifeline (no crash).
    md = (
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | A | x | f |  |\n\n"
        "## Golden Path\n**GP1 — Do a thing**\nSTORY: x\n`Touches:` C1\n"
    )
    mm = gen_viewer.gen_gp_mermaid(parse_map(md))
    assert "actor GPA0 as Actor" in mm and "GPA0->>GPSYS: Do a thing" in mm


def test_gp_actors_links_roles_and_steps() -> None:
    # gp_actors mirrors the diagram's participant order/ids and joins each actor to its Roles-table
    # entry (wants + kind) and the steps it drives (stepIdx = the message positions to highlight).
    g = parse_map(make_gp_explicit_actor_map("Actor: Org admin"))
    actors = gen_viewer.gp_actors(g)
    assert len(actors) == 1
    a = actors[0]
    assert a["aid"] == "GPA0" and a["name"] == "Org admin"
    assert a["kind"] == "human" and a["wants"] == "manage"   # joined from the Roles table by name
    assert a["stepIdx"] == [0]
    assert a["steps"] == [{"id": "GP1", "title": "Admin signs in and creates the org"}]


def test_gp_actors_without_matching_role_has_blank_wants() -> None:
    # An actor derived from a UC with no matching Roles row still appears, just without wants/kind;
    # ids follow first-appearance order and stepIdx points at each actor's messages.
    actors = gen_viewer.gp_actors(parse_map(make_gp_map()))
    by_name = {a["name"]: a for a in actors}
    assert by_name["Andy"]["aid"] == "GPA0" and by_name["Adam"]["aid"] == "GPA1"
    assert by_name["Andy"]["wants"] == "" and by_name["Andy"]["kind"] == ""
    assert by_name["Andy"]["stepIdx"] == [0] and by_name["Adam"]["stepIdx"] == [1]


def test_parser_gp_captures_first_uc_of_multi_tag() -> None:
    # A step tagged with several UCs (`*(UC1, UC2)*`) or trailing text (`*(UC3 follow-on)*`) must
    # resolve to its FIRST UC — not fall back to a generic 'Actor' lifeline (the multi-UC regression).
    md = (
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n"
        "|---|---|---|---|\n"
        "| **UC1** | Sign in | Org admin | a -> b |\n"
        "| **UC2** | Create | Org admin | a -> b |\n"
        "| **UC3** | Renew | End user | a -> b |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | A | x | f |  |\n\n"
        "## Golden Path\n"
        "**GP1 — Sign in and create** *(UC1, UC2)*\nSTORY: x\n`Touches:` C1\n\n"
        "**GP2 — Renewal flow** *(UC3 follow-on)*\nSTORY: x\n`Touches:` C1\n"
    )
    g = parse_map(md)
    steps = {s["id"]: s for s in g["gp"]}
    assert steps["GP1"]["uc"] == "UC1"           # first id of the multi-UC tag
    assert steps["GP2"]["uc"] == "UC3"           # trailing text after the id is ignored
    mm = gen_viewer.gen_gp_mermaid(g)
    assert "actor GPA0 as Org admin" in mm and "actor GPA1 as End user" in mm  # real actors...
    assert "as Actor" not in mm                  # ...not the generic fallback


def test_gp_explicit_actor_overrides_first_uc() -> None:
    # An `Actor:` line is the reliable signal for a multi-UC step: it wins over the first UC's actor.
    g = parse_map(make_gp_explicit_actor_map("Actor: Org admin"))
    step = g["gp"][0]
    assert step["actor"] == "Org admin"
    assert gen_viewer._gp_actor(g, step) == "Org admin"      # explicit wins over UC21's 'End user'
    mm = gen_viewer.gen_gp_mermaid(g)
    assert "actor GPA0 as Org admin" in mm and "End user" not in mm


def test_gp_without_actor_falls_back_to_first_uc() -> None:
    g = parse_map(make_gp_explicit_actor_map(""))            # no Actor line
    assert g["gp"][0]["actor"] is None
    assert gen_viewer._gp_actor(g, g["gp"][0]) == "End user"  # falls back to first UC (UC21)


def test_validator_accepts_defined_role_actor() -> None:
    code, out = run_validator(make_gp_explicit_actor_map("Actor: Org admin"))
    assert code == 0, out


def test_validator_rejects_undefined_role_actor() -> None:
    code, out = run_validator(make_gp_explicit_actor_map("Actor: Sysadmin"))
    assert code == 1 and "not a defined Role" in out, out


def test_gen_gp_step_mermaid_induced_subgraph() -> None:
    # Level 2: each step's diagram is the induced subgraph of the nodes it touches + the edges among
    # them — and nothing the step does not touch.
    steps = gen_viewer.gp_step_mermaids(parse_map(make_gp_map()))
    s1 = steps["GP1"]
    assert "flowchart" in s1
    assert "class C1 component" in s1 and "class C2 component" in s1
    assert "C1 -->|calls| C2" in s1                  # the intra-step edge is drawn
    assert "D1" not in s1                            # GP1 does not touch the dep
    s2 = steps["GP2"]
    assert "class C2 component" in s2 and "class D1 dep" in s2
    assert "C2 -->|reads| D1" in s2                  # component->dep edge, with the entity-style classDef present
    assert "C1" not in s2                            # GP2 does not touch C1


def test_validator_gp_map_clean() -> None:
    code, out = run_validator(make_gp_map())
    assert code == 0, out


def test_render_inlines_gp_data() -> None:
    # The self-contained HTML must carry the GP sequence + step diagrams so the client opens them.
    with tempfile.TemporaryDirectory() as d:
        md = Path(d) / "project-map.md"
        md.write_text(make_gp_map(), encoding="utf-8")
        out = Path(d) / "project-map.html"
        r = subprocess.run(
            [sys.executable, str(TOOLS / "viewer" / "render.py"), str(md), str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        html = out.read_text(encoding="utf-8")
        assert "sequenceDiagram" in html and "Submit order" in html


# --- external-dependency Kind (Context library-fold) ----------------------------
def make_dep_kinds_map(kind_d1: str = "datastore", with_kind: bool = True) -> str:
    """A map whose T2 exercises dep Kinds: D1 is explicit (param), the rest inferred from Type. D3
    (library) + D4 (framework) are the in-process deps that fold into the Context 'Libraries' box; the
    others are external systems drawn by name. `with_kind=False` drops the Kind column (heuristic-only)."""
    deps = [
        ("D1", "PostgreSQL", kind_d1, "Relational database", "store", "env"),
        ("D2", "RabbitMQ", "", "Message broker", "queue", "env"),
        ("D3", "pydantic", "", "Validation library", "validate", "dep"),
        ("D4", "React", "", "UI framework", "ui", "dep"),
        ("D5", "Stripe", "", "Payments API (SaaS)", "billing", "env"),
        ("D7", "Docker", "", "Container runtime", "packaging", "dockerfile"),
    ]
    if with_kind:
        hdr = ("| ID | Name | Kind | Type | Used for | Where configured | Conf. |\n"
               "|---|---|---|---|---|---|---|\n")
        rows = "".join(f"| **{i}** | {n} | {k} | {t} | {u} | {w} | V |\n" for i, n, k, t, u, w in deps)
    else:
        hdr = ("| ID | Name | Type | Used for | Where configured | Conf. |\n"
               "|---|---|---|---|---|---|\n")
        rows = "".join(f"| **{i}** | {n} | {t} | {u} | {w} | V |\n" for i, n, _k, t, u, w in deps)
    edges = "".join(f"| C1 | uses | {d[0]} | x | f |\n" for d in deps)
    return (
        "## Roles (actors)\n"
        "| Role | Kind | What they want | Use cases they drive |\n"
        "|---|---|---|---|\n"
        "| **User** | human | use it | UC1 |\n\n"
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n"
        "|---|---|---|---|\n"
        "| **UC1** | Use | User | a -> b |\n\n"
        "## T1\n"
        "| ID | Component | Purpose | Entry point | Depends on |\n"
        "|---|---|---|---|---|\n"
        "| **C1** | App | x | f | D1 |\n\n"
        "## T2 — External dependencies\n" + hdr + rows + "\n"
        "### edges\n"
        "| From | Verb | To | Why | Where |\n"
        "|---|---|---|---|---|\n" + edges
    )


def test_classify_dep_explicit_wins() -> None:
    # A valid explicit Kind cell overrides whatever the Type text would infer (case/space-insensitive).
    assert schema_v1.classify_dep("platform", "Relational database") == "platform"
    assert schema_v1.classify_dep("  Service  ", "a plain library") == "service"


def test_classify_dep_heuristic_per_kind() -> None:
    assert schema_v1.classify_dep("", "Relational database") == "datastore"
    assert schema_v1.classify_dep("", "Redis cache") == "datastore"
    assert schema_v1.classify_dep("", "Message broker") == "messaging"
    assert schema_v1.classify_dep("", "AWS SQS") == "messaging"          # distinctive beats platform 'aws'
    assert schema_v1.classify_dep("", "Payments API (SaaS)") == "service"
    assert schema_v1.classify_dep("", "Observability SaaS") == "service"
    assert schema_v1.classify_dep("", "Container runtime") == "platform"
    assert schema_v1.classify_dep("", "UI framework") == "framework"


def test_classify_dep_falls_back_to_library() -> None:
    # An unrecognised Type — and an INVALID explicit Kind — both fall back to 'library' (folds at Context).
    assert schema_v1.classify_dep("", "some helper utility") == "library"
    assert schema_v1.classify_dep("db", "totally unknown thing") == "library"


def test_parser_sets_dep_kind() -> None:
    g = parse_map(make_dep_kinds_map())
    deps = {k: v for k, v in g["nodes"].items() if v["kind"] == "dep"}
    assert deps["D1"]["dep_kind"] == "datastore"   # explicit
    assert deps["D2"]["dep_kind"] == "messaging"   # inferred
    assert deps["D3"]["dep_kind"] == "library"     # inferred -> folds
    assert deps["D4"]["dep_kind"] == "framework"   # inferred -> folds


def test_folded_libs_are_in_process_kinds_only() -> None:
    libs = gen_viewer.folded_libs(parse_map(make_dep_kinds_map()))
    assert {d["id"] for d in libs} == {"D3", "D4"}             # framework + library only
    assert {d["name"] for d in libs} == {"pydantic", "React"}


def test_context_folds_libraries_shows_systems_by_name() -> None:
    # The Context view draws external SYSTEMS by name and collapses framework/library into one box.
    mm = gen_viewer.gen_context_mermaid(parse_map(make_dep_kinds_map()))
    for ext in ("PostgreSQL", "RabbitMQ", "Stripe", "Docker"):
        assert ext in mm, ext                                 # external systems shown by name
    assert "Libraries (2)" in mm                              # the two in-process deps fold into one box
    assert "pydantic" not in mm and "React" not in mm         # ...and are NOT drawn individually
    assert "SYS -->|bundles| LIBS" in mm                      # the System bundles the fold box


def test_libs_drill_lists_folded_deps() -> None:
    mm = gen_viewer.gen_libs_mermaid(parse_map(make_dep_kinds_map()))
    assert "pydantic" in mm and "React" in mm                 # the drill-down lists every folded dep
    assert "PostgreSQL" not in mm                             # external systems are not in the Libraries view


def test_context_no_libraries_box_when_none_folded() -> None:
    # All-external deps: no fold box drawn, and the Libraries drill diagram is empty (never reached).
    md = make_dep_kinds_map().replace("Validation library", "Search index").replace("UI framework", "Object storage")
    g = parse_map(md)
    assert gen_viewer.folded_libs(g) == []
    assert "Libraries" not in gen_viewer.gen_context_mermaid(g)
    assert gen_viewer.gen_libs_mermaid(g) == ""


def test_validator_dep_kinds_clean_and_invalid() -> None:
    assert run_validator(make_dep_kinds_map())[0] == 0                  # valid explicit + inferred -> OK
    code, out = run_validator(make_dep_kinds_map("nonsense"))
    assert code == 1 and "invalid dependency Kind" in out, out


def test_validator_dep_kind_column_optional() -> None:
    # Dropping the Kind column entirely is a no-op for the validator (Kind is then inferred from Type).
    code, out = run_validator(make_dep_kinds_map(with_kind=False))
    assert code == 0, out
    # ...and the heuristic still classifies, so the fold still happens.
    assert gen_viewer.folded_libs(parse_map(make_dep_kinds_map(with_kind=False)))


def test_render_inlines_libs_fold_data() -> None:
    # The self-contained HTML must carry the Libraries drill diagram + the folded-dep list, fully
    # substituted (no leftover placeholder), so the client can preview/drill the fold box.
    with tempfile.TemporaryDirectory() as d:
        md = Path(d) / "project-map.md"
        md.write_text(make_dep_kinds_map(), encoding="utf-8")
        out = Path(d) / "project-map.html"
        r = subprocess.run(
            [sys.executable, str(TOOLS / "viewer" / "render.py"), str(md), str(out)],
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stdout + r.stderr
        html = out.read_text(encoding="utf-8")
        assert "__MERMAID_LIBS__" not in html and "__FOLDED_LIBS__" not in html
        # the emoji is JSON-escaped (📚) when inlined, so assert on the text after it
        assert "pydantic" in html and "Libraries (2)" in html


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
