"""Tests for `coyodex lint-fragment` — the per-fragment self-check (B1)."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyodex import lint_fragment
from coyodex.assemble import load_fragment
from coyodex.model import ProjectModel


def make_fragment(obj: dict) -> ProjectModel:
    """A partial model built from a fragment dict, exactly as `assemble`/`lint-fragment` load it."""
    return load_fragment(json.dumps(obj), "frag")


def make_fragment_file(tmp: Path, name: str, obj: dict) -> Path:
    p = tmp / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_lint_reports_anchor_and_extra_in_one_pass():
    # A bad anchor AND a forbidden `loc` extra both surface from a single lint (not one-at-a-time).
    m = make_fragment({"components": [{"id": "C1", "name": "X", "source": "[bad](x/)",
                                       "extra": {"loc": 5}}]})
    problems = lint_fragment.lint_fragment_problems(m, None)
    assert any("not a valid anchor" in p for p in problems)
    assert any("loc" in p for p in problems)


def test_lint_clean_fragment_has_no_problems():
    m = make_fragment({"components": [{"id": "C1", "name": "X", "source": "src/x.py:3"}]})
    assert lint_fragment.lint_fragment_problems(m, None) == []


def test_lint_catches_keyed_by_misuse_in_fragment():
    # shift-left: the keyed_by-vs-field misuse is caught in the authoring agent's own lint, not only
    # a phase later at the lead's validate.
    m = make_fragment({"entities": [
        {"id": "E1", "name": "Membership", "meaning": "m", "source": "src/m.py:1",
         "fields": [{"name": "role", "type": "string"}],
         "relations": [{"verb": "assignedRole", "target": "E2", "keyed_by": ["role"]}]}]})
    problems = lint_fragment.lint_fragment_problems(m, None)
    assert any("which is a declared field" in p for p in problems)


def test_lint_catches_no_call_site_with_where_in_fragment():
    # shift-left: an edge that sets both `no_call_site` and a `where` is caught at lint (was a
    # validate-only warning before).
    m = make_fragment({"edges": [
        {"src": "C1", "verb": "uses", "dst": "C2", "where": "a.py:3", "no_call_site": True}]})
    problems = lint_fragment.lint_fragment_problems(m, None)
    assert any("no_call_site" in p and "Where" in p for p in problems)


def test_lint_surfaces_fk_heuristic_as_nonfatal_warning():
    # the by-name-FK heuristic is advisory: it appears in lint WARNINGS (nudge the agent) but is NOT
    # a blocking problem (it reads prose, so it must never fail the lint).
    m = make_fragment({"entities": [
        {"id": "E1", "name": "Membership", "meaning": "m", "source": "src/m.py:1",
         "fields": [{"name": "role", "type": "string"}],
         "relations": [{"verb": "grantsRole", "target": "E2",
                        "how": "role string names a RoleDefinition key"}]},
        {"id": "E2", "name": "RoleDefinition", "meaning": "m", "source": "src/r.py:1",
         "fields": [{"name": "id", "type": "str", "markers": ["PK"]}]}]})
    assert any("FK→E2" in w for w in lint_fragment.lint_fragment_warnings(m))
    assert not any("FK→E2" in p for p in lint_fragment.lint_fragment_problems(m, None))


def test_fragment_rejects_malformed_ids_at_load():
    # 'S1a' used to pass fragment lint and die at the LEAD's validate — the exact shift-left failure
    # this module exists to prevent; the id-shape rule now runs at load_fragment too
    try:
        make_fragment({"subsystems": [{"id": "S1a", "name": "Nested"}]})
        raise AssertionError("expected ModelError")
    except lint_fragment.ModelError as e:
        assert "S1a" in str(e) and "valid S-id" in str(e)


def test_lint_flags_unknown_prefix_target():
    # 'SEC1' is id-shaped but its prefix is outside the vocabulary — it can never resolve, so it is
    # a fragment bug, catchable without the whole map
    m = make_fragment({"tests": [{"targets": ["SEC1"], "label": "auth", "tested": "no"}]})
    assert any("SEC1" in p and "unknown id prefix" in p
               for p in lint_fragment.lint_fragment_problems(m, None))


def test_lint_unknown_references_against_ids_universe():
    # with --ids (the lead's legend), an INVENTED id dies in the authoring agent's own turn
    m = make_fragment({"tests": [{"targets": ["C112", "C111"], "label": "x", "tested": "no"}]})
    problems = lint_fragment.lint_unknown_references(m, {"C111"})
    assert len(problems) == 1 and "C112" in problems[0] and "C111" not in problems[0]
    assert lint_fragment.lint_unknown_references(m, {"C111", "C112"}) == []


def test_lint_granularity_warnings_are_nonfatal():
    # A 16-step flow is a granularity ADVISORY — it must ride the non-failing warnings path, never
    # fail the fragment (a long flow may be the lead's call, not the authoring agent's bug).
    steps = [{"n": i, "src": "C1", "dst": "C1", "phrase": f"s{i}", "no_call_site": True}
             for i in range(1, 17)]
    m = make_fragment({"use_cases": [{"id": "UC1", "name": "Do the thing"}],
                       "components": [{"id": "C1", "name": "X"}],
                       "flows": [{"uc": "UC1", "title": "Do", "steps": steps}]})
    assert not any("band" in p for p in lint_fragment.lint_fragment_problems(m, None))
    assert any("over the ≤15 band" in w for w in lint_fragment.lint_fragment_warnings(m))


def test_lint_invalid_activation_is_a_fragment_problem():
    # Row-local vocabulary check: a truthy near-miss would silently reroute the row through the
    # kind heuristic in every consumer — it dies in the authoring agent's own turn.
    m = make_fragment({"entry_points": [{"kind": "http", "trigger": "GET /x",
                                         "source": "src/a.py:1", "component": "C1",
                                         "activation": "External"}]})
    assert any("invalid activation 'External'" in p
               for p in lint_fragment.lint_fragment_problems(m, None))


def test_lint_completeness_family_never_fires_per_fragment():
    # The use-case/HP completeness advisories are WHOLE-MAP signals (T4 ↔ flows ↔ HP) — a T4
    # harvest fragment has entry points but no flows, so neither the warnings nor the problems
    # path may say anything about unclaimed surfaces.
    m = make_fragment({"entry_points": [{"kind": "http", "trigger": "GET /x",
                                         "source": "src/a.py:1", "component": "C1",
                                         "activation": "external"}]})
    # asserted EMPTY, not substring-matched: any leak of the whole-map family into the fragment
    # paths must fail this test regardless of the warnings' wording
    assert lint_fragment.lint_fragment_problems(m, None) == []
    assert lint_fragment.lint_fragment_warnings(m) == []


def test_lint_extensionless_anchor_is_accepted():
    # A2: an extensionless ops file with a line is a valid anchor, so lint must not reject it.
    m = make_fragment({"deps": [{"id": "D1", "name": "img", "where_configured": "Dockerfile:1"}]})
    assert lint_fragment.lint_fragment_problems(m, None) == []


def test_lint_repo_flag_flags_missing_file():
    # With --repo, a wrong prefix / stale path is caught at the SOURCE (the anchor's file must exist).
    m = make_fragment({"components": [{"id": "C1", "name": "X", "source": "nope/x.py:3"}]})
    with tempfile.TemporaryDirectory() as td:
        problems = lint_fragment.lint_fragment_problems(m, Path(td))
    assert any("does not resolve" in p or "not" in p.lower() for p in problems)


def test_lint_repo_flag_passes_when_file_exists():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "src").mkdir()
        (root / "src" / "x.py").write_text("x = 1\n", encoding="utf-8")
        m = make_fragment({"components": [{"id": "C1", "name": "X", "source": "src/x.py:1"}]})
        assert lint_fragment.lint_fragment_problems(m, root) == []


def test_lint_cli_exit_codes():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        good = make_fragment_file(tmp, "good.json", {"components": [{"id": "C1", "name": "X",
                                                                     "source": "a/b.py:1"}]})
        bad = make_fragment_file(tmp, "bad.json", {"deps": [{"id": "D1", "name": "r",
                                                             "where_configured": None}]})
        assert lint_fragment.main([str(good)]) == 0
        assert lint_fragment.main([str(bad)]) == 1  # schema error → non-zero
