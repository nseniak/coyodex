#!/usr/bin/env python3
"""Tests for `coyodex score` — the deterministic MapProfile (the eval's reusable heart).

Stdlib-only — no pytest required. Run either way (needs an editable install: `make deps`):
    python3 tests/test_profile.py        # built-in runner (prints pass/fail)
    pytest tests/test_profile.py         # if pytest is installed
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex.convert_md import convert_text
from coyodex.model import ModelError, to_canonical_json
from coyodex_eval.profile import MapProfile, build_profile

SCORE = [sys.executable, "-m", "coyodex_eval.cli", "score"]


def as_model(md: str) -> str:
    """The profiler reads model documents only — the md test notation converts once, like a real map."""
    return to_canonical_json(convert_text(md).model)


# --- builders -------------------------------------------------------------------
def make_counts_map() -> str:
    """A map with KNOWN element counts, so the profile's structural numbers are exact:
    UC 2 · S 1 · SD 1 · C 3 · D 1 · E 2 · edges 3 · GP 3 · flows 2 · auth-surfaces 2."""
    return (
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n"
        "|---|---|---|---|\n"
        "| **UC1** | View order | Andy | opens -> sees |\n"
        "| **UC2** | Create order | Adam | submits -> stored |\n\n"
        "## Subsystems (S)\n"
        "| ID | Subsystem | Members |\n|---|---|---|\n"
        "| **S1** | Ordering | C1, C2 |\n\n"
        "## Subdomains (SD)\n"
        "| ID | Subdomain | Meaning |\n|---|---|---|\n"
        "| **SD1** | Orders | order lifecycle |\n\n"
        "## T1 — Components\n"
        "| ID | Component | Purpose | Entry point | Subsystem | Depends on |\n"
        "|---|---|---|---|---|---|\n"
        "| **C1** | Viewer | show | f | S1 | E1 |\n"
        "| **C2** | Creator | make | f | S1 | E1 |\n"
        "| **C3** | Logger | log | f |  | D1 |\n\n"
        "## T2 — External dependencies\n"
        "| ID | Dependency | Kind | Type |\n|---|---|---|---|\n"
        "| **D1** | Datadog | service | observability |\n\n"
        "## Golden Path\n"
        "**GP1 — Adam creates the order** *(UC2)*\n"
        "**GP2 — Andy views the order** *(UC1)*\n"
        "**GP3 — Logger records it** *(UC1)*\n\n"
        "## T5 — Domain model\n"
        "**E1 — Order** *(orders)*\nMEANING: a customer order\nSOURCE: [order.py](order.py#L1)\nSUBDOMAIN: SD1\n\n"
        "**E2 — Line** *(lines)*\nMEANING: a line item\nSOURCE: [line.py](line.py#L1)\nSUBDOMAIN: SD1\n\n"
        "## T6 — Use-case flows\n"
        "**UC1 — View order**\n1. Andy → C1 : views the order\n\n"
        "**UC2 — Create order**\n1. Adam → C2 : creates the order\n\n"
        "### Security & auth\n"
        "| Surface | Who can reach | Auth check | Risk note |\n"
        "|---|---|---|---|\n"
        "| /api/orders | admins | [require_admin](auth.py#L10) | escalation |\n"
        "| /api/lines | members | [require_login](auth.py#L20) | leak |\n\n"
        "### edges\n"
        "| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | reads | E1 | show it | f#L1 |\n"
        "| C2 | persists | E1 | store it | f#L2 |\n"
        "| C3 | reads | E2 | log it | f#L3 |\n"
    )


def make_roles_then_usecases_map() -> str:
    """A Roles table — whose `Use cases they drive` header ALSO starts with 'use case' — sits BEFORE
    the Use-cases table. This is the layout that made `_use_case_names` return [] (review Finding 1):
    iter_tables emits the Roles table first, so a `startswith('use case')`-only predicate read it."""
    return (
        "## Roles (actors)\n"
        "| Role | Kind | Use cases they drive |\n|---|---|---|\n"
        "| Andy | human | views orders |\n"
        "| Adam | human | creates orders |\n\n"
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n|---|---|---|---|\n"
        "| **UC1** | View order | Andy | opens -> sees |\n"
        "| **UC2** | Create order | Adam | submits -> stored |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | Viewer | x | f |  |\n\n"
        "## Golden Path\n**GP1 — View** *(UC1)*\n\n"
        "## T6 — Use-case flows\n**UC1 — View order**\n1. Andy → C1 : views\n"
    )


def make_broken_map() -> str:
    """References an undefined component C9 — a blocking validation problem (validate_ok is False)."""
    return (
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n|---|---|---|---|\n"
        "| **UC1** | View | Andy | a -> b |\n\n"
        "## T1 — Components\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | Viewer | x | f | C9 |\n\n"
        "## Golden Path\n**GP1 — View** *(UC1)*\n\n"
        "## T6 — Use-case flows\n**UC1 — View**\n1. Andy → C1 : views\n"
    )


def make_backward_whyref_map() -> str:
    """GP1's `why:` cites GP2, which comes after it — a backward reference (audit CONTRADICTION)."""
    return (
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n|---|---|---|---|\n"
        "| **UC1** | A | Andy | a -> b |\n| **UC2** | B | Andy | a -> b |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | A | x | f |  |\n\n"
        "## Golden Path\n"
        "**GP1 — First** *(UC1)*\nwhy: needs the thing from GP2\n"
        "**GP2 — Second** *(UC2)*\nwhy: follows GP1\n\n"
        "## T6 — Use-case flows\n"
        "**UC1 — A**\n1. Andy → C1 : does a\n\n"
        "**UC2 — B**\n1. Andy → C1 : does b\n"
    )


def make_read_before_create_map() -> str:
    """UC1 reads the order before UC2 writes it on the Golden Path — an audit ADVISORY (the
    component-granularity attribution is lossy, so this ordering signal never blocks)."""
    return (
        "## Use cases\n"
        "| ID | Use case | Actor | Trigger → Outcome |\n|---|---|---|---|\n"
        "| **UC1** | View order | Andy | opens -> sees |\n"
        "| **UC2** | Create order | Adam | submits -> stored |\n\n"
        "## T1\n| ID | Component | Purpose | Entry point | Depends on |\n|---|---|---|---|---|\n"
        "| **C1** | Viewer | x | f | E1 |\n| **C2** | Creator | x | f | E1 |\n\n"
        "## Golden Path\n"
        "**GP1 — Andy views the order** *(UC1)*\n**GP2 — Adam creates the order** *(UC2)*\n\n"
        "## T5 — Domain model\n**E1 — Order** *(orders)*\nMEANING: a customer order\nSOURCE: [order.py](order.py#L1)\n\n"
        "## T6 — Use-case flows\n"
        "**UC1 — View order**\n1. Andy → C1 : views the order\n\n"
        "**UC2 — Create order**\n1. Adam → C2 : creates the order\n\n"
        "### edges\n| From | Verb | To | Why | Where |\n|---|---|---|---|---|\n"
        "| C1 | reads | E1 | show it | f#L1 |\n| C2 | persists | E1 | store it | f#L2 |\n"
    )


def run_score(md: str, *extra: str) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(as_model(md))
        path = f.name
    r = subprocess.run([*SCORE, path, *extra], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


# --- structure counts (the deterministic core) ----------------------------------
def test_structure_counts_are_exact() -> None:
    p = build_profile(as_model(make_counts_map()))
    assert (p.use_cases, p.subsystems, p.subdomains, p.components, p.deps, p.entities) == (2, 1, 1, 3, 1, 2), p
    assert (p.edges, p.gp_steps, p.flows, p.security_surfaces) == (3, 3, 2, 2), p


def test_concept_name_sets_are_captured() -> None:
    p = build_profile(as_model(make_counts_map()))
    assert p.auth_surfaces == ["/api/orders", "/api/lines"], p.auth_surfaces
    assert p.use_case_names == ["View order", "Create order"], p.use_case_names
    assert p.entity_names == ["Order", "Line"], p.entity_names


def test_use_case_names_survive_a_roles_table_before_them() -> None:
    """Regression guard (review Finding 1, model edition): a Roles table before the Use-cases table
    must not shadow the use-case NAMES — the model stores them first-class, so they always survive."""
    p = build_profile(as_model(make_roles_then_usecases_map()))
    assert p.use_case_names == ["View order", "Create order"], p.use_case_names


# --- well-formedness (reuses validate_map) --------------------------------------
def test_broken_map_is_not_validate_ok() -> None:
    p = build_profile(as_model(make_broken_map()))
    assert p.validate_ok is False and p.validate_problems > 0, p


def test_markdown_map_is_refused_with_a_convert_first_error() -> None:
    """The retired input: a schema-v1 markdown map raises ModelError (migrate with `coyodex
    convert`), never a silent zero-profile."""
    try:
        build_profile("## Use cases\n| **UC1** | View | Andy | a -> b |\n")
        raise AssertionError("expected ModelError")
    except ModelError as e:
        assert "convert" in str(e)


# --- self-consistency (reuses audit) --------------------------------------------
def test_backward_why_ref_shows_up_as_a_contradiction() -> None:
    p = build_profile(as_model(make_backward_whyref_map()))
    assert p.contradictions == 1, p


def test_read_before_create_shows_up_as_an_advisory() -> None:
    """The current audit rates a read-then-write ordering ADVISORY, not blocking — the profile counts
    it under `advisories`, leaving `contradictions` clean."""
    p = build_profile(as_model(make_read_before_create_map()))
    assert p.advisories >= 1 and p.contradictions == 0, p


def test_l2_claims_counts_security_surfaces() -> None:
    """Each Security & auth row is an L2 claim to ground — the counts_map has two surfaces."""
    p = build_profile(as_model(make_counts_map()))
    assert p.l2_claims >= 2, p


# --- density (P1) ----------------------------------------------------------------
def test_edges_per_component_is_the_density_ratio() -> None:
    p = build_profile(as_model(make_counts_map()))  # 3 edges / 3 components
    assert p.edges_per_component == 1.0, p


def test_density_is_none_when_there_are_no_components() -> None:
    p = build_profile(as_model(
        "## Use cases\n| ID | Use case | Actor | Trigger → Outcome |\n|---|---|---|---|\n"
        "| **UC1** | View | Andy | a -> b |\n"))
    assert p.edges_per_component is None, p


# --- coverage (needs the repo) --------------------------------------------------
def test_coverage_is_none_without_repo_and_int_with_repo() -> None:
    p_no = build_profile(as_model(make_counts_map()))
    assert p_no.coverage_flags is None, p_no
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "order.py").write_text("x = 1\n", encoding="utf-8")
        (Path(d) / "line.py").write_text("y = 2\n", encoding="utf-8")
        p_yes = build_profile(as_model(make_counts_map()), repo_root=Path(d))
    assert isinstance(p_yes.coverage_flags, int), p_yes


# --- serialization round-trip ---------------------------------------------------
def test_profile_json_round_trips() -> None:
    p = build_profile(as_model(make_counts_map()))
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
