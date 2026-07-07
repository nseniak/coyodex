#!/usr/bin/env python3
"""Tests for `coyodex.json_schema` — the generated (documentation-only) JSON Schema.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_json_schema.py
    pytest tests/test_json_schema.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from coyodex.json_schema import generate_schema
from coyodex.model import ID_ARRAYS

REPO = Path(__file__).resolve().parent.parent
COMMITTED = REPO / "method" / "project-map.schema.json"


def test_committed_schema_is_not_stale():
    """`method/project-map.schema.json` is generated, never hand-edited — this is its 'coyodex
    validate would warn about a stale view' equivalent."""
    current = json.dumps(generate_schema(), indent=2) + "\n"
    assert COMMITTED.read_text(encoding="utf-8") == current, (
        "method/project-map.schema.json is stale — regenerate with "
        "`python -m coyodex.json_schema > method/project-map.schema.json`")


def test_every_ref_resolves_to_a_def():
    schema = generate_schema()
    refs = set(re.findall(r"#/\$defs/(\w+)", json.dumps(schema)))
    assert refs and refs <= set(schema["$defs"])


def test_id_fields_carry_their_arrays_prefix_pattern():
    schema = generate_schema()
    for attr, prefix in ID_ARRAYS.items():
        if attr in ("subsystems", "subdomains"):
            continue  # Group is shared by both forests — see its own pattern/description
        item_def = schema["properties"][attr]["items"]["$ref"].rsplit("/", 1)[-1]
        pattern = schema["$defs"][item_def]["properties"]["id"]["pattern"]
        assert pattern == f"^{prefix}\\d+$", (attr, pattern)


def test_evidence_file_pattern_rejects_a_markdown_link_and_a_retired_hash_anchor():
    schema = generate_schema()
    pattern = re.compile(schema["$defs"]["EvidenceItem"]["properties"]["file"]["pattern"])
    assert pattern.match("src/v.py:12")
    assert pattern.match("src/v.py:12-18")
    assert not pattern.match("[v.py](src/v.py:12)")
    assert not pattern.match("src/v.py#L12")


def test_extra_has_no_fixed_properties():
    """`extra` stays genuinely freeform in the schema — additionalProperties is never restricted."""
    schema = generate_schema()
    comp_extra = schema["$defs"]["Component"]["properties"]["extra"]
    assert "properties" not in comp_extra and "additionalProperties" not in comp_extra


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
