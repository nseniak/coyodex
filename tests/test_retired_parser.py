#!/usr/bin/env python3
"""Guard: the schema-v1 markdown-MAP parse (the full grammar/validator the retired `coyodex convert`
command depended on) must stay fully deleted — not just confined to one file, since there is no
longer any legitimate reader of it anywhere in production.

`schema_v1.py` and `validate_analysis.py` still exist (they host grammar/helpers the CURRENT
schema-v2 pipeline reuses directly: table-splitting for the change-impact report parser, anchor
resolution, hierarchy/coverage/granularity advisories) — this guard checks that the v1-map-ONLY
surface never regrows inside them or anywhere else.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_retired_parser.py
    pytest tests/test_retired_parser.py
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Production sources that must stay free of the v1 map parse.
PRODUCTION_DIRS = (REPO / "tools" / "coyodex", REPO / "eval" / "tools" / "coyodex_eval")

# The v1 markdown-map parse surface: the schema-v1 grammar's card/flow/definition-table constructs,
# the whole-map validator, the retired graph/audit parse functions, and the deleted modules' names.
# NOTHING in production may reference any of these — the whole surface is gone, not just isolated.
FORBIDDEN = (
    "audit_analysis", "convert_md", "convert_text",
    "validate_map", "collect_defined", "collect_referenced", "collect_edges", "collect_parents",
    "collect_subdomain_membership", "collect_role_names", "iter_tables", "check_compression_coverage",
    "check_gp_use_cases", "check_flow_steps", "check_roles_kind", "check_dep_kinds",
    "check_altitude_hints", "check_malformed_ids", "check_table_runs", "check_table_shape",
    "check_edge_verbs", "check_edge_where", "check_anchor_existence", "check_domain_cards",
    "check_entity_sources", "check_domain_coverage", "find_glued_ids", "_map_referenced_paths",
    "iter_domain_cards", "iter_flows", "parse_card_fields", "parse_card_relations",
    "parse_flow_step", "parse_gp", "parse_goal",
    "DEF_BOLD", "DEF_ID_CELL", "DEF_GP", "DEF_ENTITY", "GLUED_DEF", "GLUED_DEF_INNER",
    "GP_HEADING", "GP_UC_TAG", "ENTITY_HEADING", "SUBDOMAIN_ID", "RELATION_ITEM", "REL_HOW",
    "ALLOWED_CARDINALITY", "FLOW_HEADING", "FLOW_STEP", "membership_col", "membership_ids",
    "unterminated_fence_line",
)


def production_sources() -> list[Path]:
    out: list[Path] = []
    for d in PRODUCTION_DIRS:
        out.extend(p for p in d.rglob("*.py") if "__pycache__" not in p.parts)
    assert out, "expected production sources under tools/ and eval/tools/"
    return out


def test_no_production_module_references_the_v1_map_parse() -> None:
    """Word-boundary match — a v2-native function that merely SHARES a name fragment (e.g.
    `check_domain_coverage_model`) must not false-positive against the retired `check_domain_coverage`."""
    offenders: list[str] = []
    for path in production_sources():
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            if re.search(rf"\b{re.escape(token)}\b", text):
                offenders.append(f"{path.relative_to(REPO)}: references '{token}'")
    assert not offenders, "the v1 map parse regrew:\n" + "\n".join(offenders)


def test_the_retired_modules_and_files_stay_deleted() -> None:
    for retired in ("tools/coyodex/audit_analysis.py", "tools/coyodex/convert_md.py"):
        assert not (REPO / retired).exists(), f"{retired} was retired — it must stay deleted"
    bg = (REPO / "tools" / "coyodex" / "viewer" / "build_graph.py").read_text(encoding="utf-8")
    for retired in ("def build(", "def parse_nodes_edges(", "def parse_domain(",
                    "def parse_element_nodes(", "def parse_roles("):
        assert retired not in bg, f"build_graph.py regrew the retired v1 map parse: {retired}"


def test_no_command_dispatches_to_convert() -> None:
    cli_src = (REPO / "tools" / "coyodex" / "cli.py").read_text(encoding="utf-8")
    assert '"convert"' not in cli_src, "the retired `coyodex convert` command must stay removed"


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
