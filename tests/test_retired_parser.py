#!/usr/bin/env python3
"""Guard for the Phase-3 retirement: the schema-v1 MARKDOWN-MAP PARSE survives only on the
`coyodex convert` path — no other production module may call it.

Source-level check (imports + attribute references), not a runtime one: it fails when someone
re-introduces a markdown-map branch into a tool that must be model-only. The allowed homes are
the modules that ARE the legacy reader: schema_v1 (the grammar), validate_analysis (the v1
validator convert uses to refuse invalid input), convert_md (the migration itself), and
viewer/build_graph (hosts convert's parse_gp/parse_goal plus the change-impact REPORT parser,
which is a current markdown artifact, not a v1 map).

Run either way (needs an editable install: `make deps`):
    python3 tests/test_retired_parser.py
    pytest tests/test_retired_parser.py
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Production sources that must stay free of the v1 map parse.
PRODUCTION_DIRS = (REPO / "tools" / "coyodex", REPO / "eval" / "tools" / "coyodex_eval")

# The legacy reader itself — the only modules allowed to reference the parse surface.
ALLOWED = {"schema_v1.py", "validate_analysis.py", "convert_md.py", "build_graph.py"}

# The v1 markdown-map parse surface: table/fence grammar, the v1 validator entry, the retired
# graph/audit parse functions, and the deleted module's name.
FORBIDDEN = (
    "audit_analysis",
    "validate_map", "collect_defined", "collect_edges", "collect_role_names", "iter_tables",
    "check_compression_coverage",
    "strip_fences", "unterminated_fence_line",
    "iter_domain_cards", "iter_flows", "iter_pipe_runs", "split_cells", "is_separator_row",
    "parse_nodes_edges", "parse_element_nodes", "parse_domain", "parse_roles",
    "parse_gp", "parse_goal",
)


def production_sources() -> list[Path]:
    out: list[Path] = []
    for d in PRODUCTION_DIRS:
        out.extend(p for p in d.rglob("*.py") if "__pycache__" not in p.parts)
    assert out, "expected production sources under tools/ and eval/tools/"
    return out


def test_no_production_module_references_the_v1_map_parse() -> None:
    offenders: list[str] = []
    for path in production_sources():
        if path.name in ALLOWED:
            continue
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            if token in text:
                offenders.append(f"{path.relative_to(REPO)}: references '{token}'")
    assert not offenders, "the v1 map parse leaked outside the convert path:\n" + "\n".join(offenders)


def test_the_retired_modules_and_functions_stay_deleted() -> None:
    assert not (REPO / "tools" / "coyodex" / "audit_analysis.py").exists(), (
        "audit_analysis.py (the v1 markdown audit) was retired in Phase 3 — its shared "
        "vocabulary lives in audit_model.py")
    bg = (REPO / "tools" / "coyodex" / "viewer" / "build_graph.py").read_text(encoding="utf-8")
    for retired in ("def build(", "def parse_nodes_edges(", "def parse_domain(",
                    "def parse_element_nodes(", "def parse_roles("):
        assert retired not in bg, f"build_graph.py regrew the retired v1 map parse: {retired}"


def test_convert_is_the_only_importer_of_the_v1_validator() -> None:
    """`validate_analysis.validate_map` (the whole-map v1 validation) is reachable only through
    `coyodex convert`'s refuse-invalid-input gate."""
    users = [p.name for p in production_sources()
             if p.name not in ("validate_analysis.py",)
             and "validate_map" in p.read_text(encoding="utf-8")]
    assert users == ["convert_md.py"], users


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
