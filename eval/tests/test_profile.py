#!/usr/bin/env python3
"""Tests for `coyodex score` — the deterministic MapProfile (the eval's reusable heart).

Fixtures are JSON model documents (generated once from the retired md test notation
at the Phase-3 boundary — see git history for the original markdown shorthand).

Stdlib-only — no pytest required. Run either way (needs an editable install: `make deps`):
    python3 tests/test_profile.py        # built-in runner (prints pass/fail)
    pytest tests/test_profile.py         # if pytest is installed
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex.model import ModelError
from coyodex_eval.profile import MapProfile, build_profile

SCORE = [sys.executable, "-m", "coyodex_eval.cli", "score"]


# --- fixtures (JSON model documents) -----------------------------------
def make_counts_map() -> str:
    """A map with KNOWN element counts, so the profile's structural numbers are exact:
    UC 2 · S 1 · SD 1 · C 3 · D 1 · E 2 · edges 3 · GP 3 · flows 2 · auth-surfaces 2."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "View order",
      "actor": "Andy",
      "trigger_outcome": "opens -> sees"
    },
    {
      "id": "UC2",
      "name": "Create order",
      "actor": "Adam",
      "trigger_outcome": "submits -> stored"
    }
  ],
  "golden_path": [
    {
      "id": "GP1",
      "title": "Adam creates the order",
      "uc": "UC2",
      "why": null
    },
    {
      "id": "GP2",
      "title": "Andy views the order",
      "uc": "UC1",
      "why": null
    },
    {
      "id": "GP3",
      "title": "Logger records it",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [
    {
      "id": "S1",
      "name": "Ordering",
      "purpose": "",
      "parent": null,
      "source": null,
      "confidence": ""
    }
  ],
  "components": [
    {
      "id": "C1",
      "name": "Viewer",
      "subsystem": "S1",
      "purpose": "show",
      "entry_point": "f",
      "depends_on": "E1",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C2",
      "name": "Creator",
      "subsystem": "S1",
      "purpose": "make",
      "entry_point": "f",
      "depends_on": "E1",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C3",
      "name": "Logger",
      "subsystem": null,
      "purpose": "log",
      "entry_point": "f",
      "depends_on": "D1",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [
    {
      "id": "D1",
      "name": "Datadog",
      "kind": "service",
      "type": "observability",
      "used_for": "",
      "where_configured": "",
      "confidence": "",
      "deployment_linked": false,
      "extra": {}
    }
  ],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [
    {
      "id": "SD1",
      "name": "Orders",
      "purpose": "",
      "parent": null,
      "source": null,
      "confidence": ""
    }
  ],
  "entities": [
    {
      "id": "E1",
      "name": "Order",
      "store": "orders",
      "meaning": "a customer order",
      "subdomain": "SD1",
      "source": "order.py:1",
      "fields": [],
      "relations": []
    },
    {
      "id": "E2",
      "name": "Line",
      "store": "lines",
      "meaning": "a line item",
      "subdomain": "SD1",
      "source": "line.py:1",
      "fields": [],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [
    {
      "uc": "UC1",
      "title": "View order",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "views the order",
          "note": ""
        }
      ]
    },
    {
      "uc": "UC2",
      "title": "Create order",
      "steps": [
        {
          "n": 1,
          "src": "Adam",
          "dst": "C2",
          "phrase": "creates the order",
          "note": ""
        }
      ]
    }
  ],
  "edges": [
    {
      "src": "C1",
      "verb": "reads",
      "dst": "E1",
      "why": "show it",
      "where": "f#L1"
    },
    {
      "src": "C2",
      "verb": "persists",
      "dst": "E1",
      "why": "store it",
      "where": "f#L2"
    },
    {
      "src": "C3",
      "verb": "reads",
      "dst": "E2",
      "why": "log it",
      "where": "f#L3"
    }
  ],
  "deployment": [],
  "observability": [],
  "security": [
    {
      "surface": "/api/orders",
      "who": "admins",
      "source": "[require_admin](auth.py#L10)",
      "risk": "escalation"
    },
    {
      "surface": "/api/lines",
      "who": "members",
      "source": "[require_login](auth.py#L20)",
      "risk": "leak"
    }
  ],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_roles_then_usecases_map() -> str:
    """A Roles table — whose `Use cases they drive` header ALSO starts with 'use case' — sits BEFORE
    the Use-cases table. This is the layout that made `_use_case_names` return [] (review Finding 1):
    iter_tables emits the Roles table first, so a `startswith('use case')`-only predicate read it."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [
    {
      "name": "Andy",
      "kind": "human",
      "wants": "",
      "drives": "views orders"
    },
    {
      "name": "Adam",
      "kind": "human",
      "wants": "",
      "drives": "creates orders"
    }
  ],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "View order",
      "actor": "Andy",
      "trigger_outcome": "opens -> sees"
    },
    {
      "id": "UC2",
      "name": "Create order",
      "actor": "Adam",
      "trigger_outcome": "submits -> stored"
    }
  ],
  "golden_path": [
    {
      "id": "GP1",
      "title": "View",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "Viewer",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [],
  "non_entity_types": [],
  "flows": [
    {
      "uc": "UC1",
      "title": "View order",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "views",
          "note": ""
        }
      ]
    }
  ],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_broken_map() -> str:
    """References an undefined component C9 — a blocking validation problem (validate_ok is False)."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "View",
      "actor": "Andy",
      "trigger_outcome": "a -> b"
    }
  ],
  "golden_path": [
    {
      "id": "GP1",
      "title": "View",
      "uc": "UC1",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "Viewer",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "C9",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [],
  "non_entity_types": [],
  "flows": [
    {
      "uc": "UC1",
      "title": "View",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "views",
          "note": ""
        }
      ]
    }
  ],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_backward_whyref_map() -> str:
    """GP1's `why:` cites GP2, which comes after it — a backward reference (audit CONTRADICTION)."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "A",
      "actor": "Andy",
      "trigger_outcome": "a -> b"
    },
    {
      "id": "UC2",
      "name": "B",
      "actor": "Andy",
      "trigger_outcome": "a -> b"
    }
  ],
  "golden_path": [
    {
      "id": "GP1",
      "title": "First",
      "uc": "UC1",
      "why": "needs the thing from GP2"
    },
    {
      "id": "GP2",
      "title": "Second",
      "uc": "UC2",
      "why": "follows GP1"
    }
  ],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "A",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [],
  "non_entity_types": [],
  "flows": [
    {
      "uc": "UC1",
      "title": "A",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "does a",
          "note": ""
        }
      ]
    },
    {
      "uc": "UC2",
      "title": "B",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "does b",
          "note": ""
        }
      ]
    }
  ],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_read_before_create_map() -> str:
    """UC1 reads the order before UC2 writes it on the Golden Path — an audit ADVISORY (the
    component-granularity attribution is lossy, so this ordering signal never blocks)."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "View order",
      "actor": "Andy",
      "trigger_outcome": "opens -> sees"
    },
    {
      "id": "UC2",
      "name": "Create order",
      "actor": "Adam",
      "trigger_outcome": "submits -> stored"
    }
  ],
  "golden_path": [
    {
      "id": "GP1",
      "title": "Andy views the order",
      "uc": "UC1",
      "why": null
    },
    {
      "id": "GP2",
      "title": "Adam creates the order",
      "uc": "UC2",
      "why": null
    }
  ],
  "subsystems": [],
  "components": [
    {
      "id": "C1",
      "name": "Viewer",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "E1",
      "source": null,
      "confidence": "",
      "extra": {}
    },
    {
      "id": "C2",
      "name": "Creator",
      "subsystem": null,
      "purpose": "x",
      "entry_point": "f",
      "depends_on": "E1",
      "source": null,
      "confidence": "",
      "extra": {}
    }
  ],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [
    {
      "id": "E1",
      "name": "Order",
      "store": "orders",
      "meaning": "a customer order",
      "subdomain": null,
      "source": "order.py:1",
      "fields": [],
      "relations": []
    }
  ],
  "non_entity_types": [],
  "flows": [
    {
      "uc": "UC1",
      "title": "View order",
      "steps": [
        {
          "n": 1,
          "src": "Andy",
          "dst": "C1",
          "phrase": "views the order",
          "note": ""
        }
      ]
    },
    {
      "uc": "UC2",
      "title": "Create order",
      "steps": [
        {
          "n": 1,
          "src": "Adam",
          "dst": "C2",
          "phrase": "creates the order",
          "note": ""
        }
      ]
    }
  ],
  "edges": [
    {
      "src": "C1",
      "verb": "reads",
      "dst": "E1",
      "why": "show it",
      "where": "f#L1"
    },
    {
      "src": "C2",
      "verb": "persists",
      "dst": "E1",
      "why": "store it",
      "where": "f#L2"
    }
  ],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def make_single_use_case_map() -> str:
    """A single use case, no components — used where the profile must show density as None."""
    return """{
  "format": "coyodex-map",
  "title": "",
  "goal": "",
  "commit": null,
  "committed": null,
  "built": null,
  "roles": [],
  "glossary": [],
  "use_cases": [
    {
      "id": "UC1",
      "name": "View",
      "actor": "Andy",
      "trigger_outcome": "a -> b"
    }
  ],
  "golden_path": [],
  "subsystems": [],
  "components": [],
  "deps": [],
  "run_commands": [],
  "entry_points": [],
  "subdomains": [],
  "entities": [],
  "non_entity_types": [],
  "flows": [],
  "edges": [],
  "deployment": [],
  "observability": [],
  "security": [],
  "config": [],
  "tests_note": "",
  "tests": [],
  "extras": []
}"""


def run_score(map_text: str, *extra: str) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(map_text)
        path = f.name
    r = subprocess.run([*SCORE, path, *extra], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


# --- structure counts (the deterministic core) ----------------------------------
def test_structure_counts_are_exact() -> None:
    p = build_profile(make_counts_map())
    assert (p.use_cases, p.subsystems, p.subdomains, p.components, p.deps, p.entities) == (2, 1, 1, 3, 1, 2), p
    assert (p.edges, p.gp_steps, p.flows, p.security_surfaces) == (3, 3, 2, 2), p


def test_concept_name_sets_are_captured() -> None:
    p = build_profile(make_counts_map())
    assert p.auth_surfaces == ["/api/orders", "/api/lines"], p.auth_surfaces
    assert p.use_case_names == ["View order", "Create order"], p.use_case_names
    assert p.entity_names == ["Order", "Line"], p.entity_names


def test_use_case_names_survive_a_roles_table_before_them() -> None:
    """Regression guard (review Finding 1, model edition): a Roles table before the Use-cases table
    must not shadow the use-case NAMES — the model stores them first-class, so they always survive."""
    p = build_profile(make_roles_then_usecases_map())
    assert p.use_case_names == ["View order", "Create order"], p.use_case_names


# --- well-formedness (reuses validate_model) ------------------------------------
def test_broken_map_is_not_validate_ok() -> None:
    p = build_profile(make_broken_map())
    assert p.validate_ok is False and p.validate_problems > 0, p


def test_markdown_map_is_refused() -> None:
    """A non-model document raises ModelError (a normal JSON parse failure), never a silent
    zero-profile."""
    try:
        build_profile("## Use cases\n| **UC1** | View | Andy | a -> b |\n")
        raise AssertionError("expected ModelError")
    except ModelError as e:
        assert "not valid JSON" in str(e)


# --- self-consistency (reuses audit) --------------------------------------------
def test_backward_why_ref_shows_up_as_a_contradiction() -> None:
    p = build_profile(make_backward_whyref_map())
    assert p.contradictions == 1, p


def test_read_before_create_shows_up_as_an_advisory() -> None:
    """The current audit rates a read-then-write ordering ADVISORY, not blocking — the profile counts
    it under `advisories`, leaving `contradictions` clean."""
    p = build_profile(make_read_before_create_map())
    assert p.advisories >= 1 and p.contradictions == 0, p


def test_l2_claims_counts_security_surfaces() -> None:
    """Each Security & auth row is an L2 claim to ground — the counts_map has two surfaces."""
    p = build_profile(make_counts_map())
    assert p.l2_claims >= 2, p


# --- density (P1) ----------------------------------------------------------------
def test_edges_per_component_is_the_density_ratio() -> None:
    p = build_profile(make_counts_map())  # 3 edges / 3 components
    assert p.edges_per_component == 1.0, p


def test_density_is_none_when_there_are_no_components() -> None:
    p = build_profile(make_single_use_case_map())
    assert p.edges_per_component is None, p


# --- coverage (needs the repo) --------------------------------------------------
def test_coverage_is_none_without_repo_and_int_with_repo() -> None:
    p_no = build_profile(make_counts_map())
    assert p_no.coverage_flags is None, p_no
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "order.py").write_text("x = 1\n", encoding="utf-8")
        (Path(d) / "line.py").write_text("y = 2\n", encoding="utf-8")
        p_yes = build_profile(make_counts_map(), repo_root=Path(d))
    assert isinstance(p_yes.coverage_flags, int), p_yes


# --- granularity (the code-derived expectation E, needs the repo) ----------------
def test_granularity_expected_is_none_without_repo_and_e_with_repo() -> None:
    p_no = build_profile(make_counts_map())
    assert p_no.granularity_expected is None, p_no
    with tempfile.TemporaryDirectory() as d:
        # a subsystem-shaped tree with a known E: 6 small plugin dirs + a small core dir → 7
        for i in range(6):
            sub = Path(d) / "plugins" / f"p{i}"
            sub.mkdir(parents=True)
            for j in range(3):
                (sub / f"f{j}.py").write_text("x\n" * 100, encoding="utf-8")
        core = Path(d) / "core"
        core.mkdir()
        (core / "a.py").write_text("x\n" * 60, encoding="utf-8")
        p_yes = build_profile(make_counts_map(), repo_root=Path(d))
    assert p_yes.granularity_expected == 7, p_yes.granularity_expected


def test_granularity_expected_is_none_on_a_tree_with_no_source() -> None:
    """A repo with no component-forming source anchors nothing — None, not a fake 0/1 gate."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "README.md").write_text("docs only\n" * 50, encoding="utf-8")
        p = build_profile(make_counts_map(), repo_root=Path(d))
    assert p.granularity_expected is None, p.granularity_expected


# --- serialization round-trip ---------------------------------------------------
def test_profile_json_round_trips() -> None:
    p = build_profile(make_counts_map())
    assert MapProfile.from_json(p.to_json()) == p


# --- CLI ------------------------------------------------------------------------
def test_score_cli_prints_profile_and_exits_zero() -> None:
    code, out = run_score(make_counts_map())
    assert code == 0, out
    assert "Map profile" in out and "structure" in out, out


def test_score_cli_json_is_parseable() -> None:
    code, out = run_score(make_counts_map(), "--json")
    assert code == 0, out
    assert MapProfile.from_json(out).use_cases == 2, out


def test_score_cli_missing_file_errors() -> None:
    r = subprocess.run([*SCORE, "/no/such/map.md"], capture_output=True, text=True)
    assert r.returncode == 1 and "not found" in (r.stdout + r.stderr)


# --- built-in runner ------------------------------------------------------------
def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_run())
