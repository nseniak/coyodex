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


def test_lint_roleless_cd_verb_is_a_warning_not_a_problem():
    # T7 (load-bearing): a roleless C→D verb (`uses`) surfaces in lint WARNINGS (nudge the agent) and
    # must NOT be a blocking problem — else a legitimately-generic verb would FAIL the fragment lint.
    m = make_fragment({"deps": [{"id": "D1", "name": "Redis", "kind": "messaging", "type": "broker"}],
                       "edges": [{"src": "C1", "verb": "uses", "dst": "D1", "where": "a.py:3"}]})
    assert any("name no role" in w and "C1 uses D1" in w for w in lint_fragment.lint_fragment_warnings(m))
    assert not any("name no role" in p for p in lint_fragment.lint_fragment_problems(m, None))


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


def test_lint_does_not_flag_uc_ref_when_legend_omits_the_uc_namespace():
    # A trace fragment authors flows whose `uc` points at a use case defined in the BEHAVIORAL fragment.
    # A reduced trace legend lists only element ids (C/E/D), so the `uc` value must NOT false-positive:
    # a namespace the legend doesn't cover can't be adjudicated (mirrors the actor/roles gate).
    m = make_fragment({"components": [{"id": "C1", "name": "X"}],
                       "flows": [{"uc": "UC13", "title": "Do", "steps": [
                           {"n": 1, "src": "C1", "dst": "C1", "phrase": "s", "no_call_site": True}]}]})
    assert lint_fragment.lint_unknown_references(m, {"C1", "D1", "E1"}) == []   # UC absent → not flagged


def test_lint_flags_invented_uc_when_legend_covers_the_uc_namespace():
    # When the legend DOES contain UC ids (e.g. the full assembled map), an INVENTED UC is still caught.
    m = make_fragment({"components": [{"id": "C1", "name": "X"}],
                       "flows": [{"uc": "UC99", "title": "Do", "steps": [
                           {"n": 1, "src": "C1", "dst": "C1", "phrase": "s", "no_call_site": True}]}]})
    problems = lint_fragment.lint_unknown_references(m, {"C1", "UC1", "UC2"})   # UC namespace present
    assert len(problems) == 1 and "UC99" in problems[0]


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
    # path may say anything about unclaimed surfaces. (Kind is the CANONICAL spelling here: the
    # row-local kind-drift nudge legitimately rides the warnings channel and is tested separately.)
    m = make_fragment({"entry_points": [{"kind": "http-route", "trigger": "GET /x",
                                         "source": "src/a.py:1", "component": "C1",
                                         "activation": "external"}]})
    # asserted EMPTY, not substring-matched: any leak of the whole-map family into the fragment
    # paths must fail this test regardless of the warnings' wording
    assert lint_fragment.lint_fragment_problems(m, None) == []
    assert lint_fragment.lint_fragment_warnings(m) == []


def test_lint_kind_drift_nudge_fires_per_fragment_as_warning():
    # WS-A8: the alias-spelling nudge is row-local, so the authoring agent hears it in its own
    # turn — on the ADVISORY channel (seeded-open vocabulary: a spelling must never fail a fragment).
    m = make_fragment({"entry_points": [{"kind": "http", "trigger": "GET /x",
                                         "source": "src/a.py:1", "component": "C1",
                                         "activation": "external"}]})
    assert lint_fragment.lint_fragment_problems(m, None) == []
    assert any("drift spelling" in w and "http-route" in w
               for w in lint_fragment.lint_fragment_warnings(m))
    # the whole-map per-kind COVERAGE contract stays out of the fragment paths
    assert not any("Entry-point coverage" in w for w in lint_fragment.lint_fragment_warnings(m))


def test_fragment_subflow_title_alias_is_accepted():
    # Rebuild finding M-B1: trace agents write `subflows[].title` by analogy with the flow shape —
    # the fragment loader now aliases it to `name` instead of failing `unknown field`.
    m = make_fragment({"subflows": [{"id": "SF1", "title": "Shared dispatch",
                                     "steps": [{"n": 1, "src": "C1", "dst": "C2",
                                                "phrase": "dispatches", "where": "src/a.py:3"}]}]})
    assert m.subflows[0].name == "Shared dispatch"
    assert not any("unknown field" in p for p in lint_fragment.lint_fragment_problems(m, None))


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


def test_expect_is_silent_inside_the_band_and_speaks_outside_it():
    """`--expect N` is the dispatched component budget, checked at the AGENT's own lint.

    Advisory and opt-in: it fires only when the lead passes a budget, so a fragment linted without
    one is unaffected (`lint_fragment_warnings` is asserted empty for a correct harvest fragment
    elsewhere, and this must not break that). The band is wide because the budget is a pre-read
    estimate; what it catches is the systematic overshoot — on a live build nine slices dispatched
    with budgets summing to ~55 delivered 86, every slice over, and nothing noticed until the lead's
    granularity advisory after assembly."""
    m = make_fragment({"components": [
        {"id": f"C{i}", "name": f"C{i}", "purpose": "p", "entry_point": f"src/c{i}.py:1"}
        for i in range(1, 13)]})
    assert lint_fragment._budget_warnings(m, None) == []      # opt-in: no budget, no opinion
    assert lint_fragment._budget_warnings(m, 10) == []        # 12 vs 10 is inside 0.5x-1.5x
    assert lint_fragment._budget_warnings(m, 12) == []
    over = lint_fragment._budget_warnings(m, 5)               # 2.4x
    assert len(over) == 1 and "2.4x" in over[0] and "over" in over[0]
    under = lint_fragment._budget_warnings(m, 40)             # 0.3x
    assert len(under) == 1 and "under" in under[0]


def test_expect_says_nothing_about_a_fragment_that_defines_no_component():
    """A trace fragment carries flows and edges, not components. Comparing 0 against a budget would
    fire on every one of them — the budget belongs to the harvest slices that were given one."""
    m = make_fragment({"edges": [{"src": "C1", "verb": "calls", "dst": "C2", "why": "w",
                                  "where": "src/a.py:1"}]})
    assert lint_fragment._budget_warnings(m, 8) == []


def test_an_unreadable_path_is_not_reported_as_a_rule_violation():
    """`ERROR: … not found` used to be followed by "LINT FAILED: fix the rows above", sending the
    agent hunting for a violation in a file nobody opened. A live build lost two turns to it."""
    import subprocess
    import sys
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sys.executable, "-m", "coyodex.lint_fragment",
                            str(Path(tmp) / "nope.json")], capture_output=True, text=True)
        assert r.returncode == 2, "a missing file is not a lint failure (exit 1)"
        assert "cannot read" in r.stderr
        assert "LINT DID NOT RUN" in r.stderr
        assert "LINT FAILED" not in r.stderr


# --- domain-card shape, shifted left ---------------------------------------------
# The per-card shape rules (meaning / source / fields / field types) ran only on the ASSEMBLED map,
# so a T5 fragment linted clean and then failed the lead's `validate` a phase later — eight cards
# at once on a live build, and seven turns of sed/awk/python to recover.


def make_card(**over) -> dict:
    card = {"id": "E1", "name": "Thing", "meaning": "a thing", "source": "a.py:1",
            "fields": [{"name": "id", "type": "str"}]}
    card.update(over)
    return card


def test_a_field_less_domain_card_now_fails_the_fragment_lint():
    m = make_fragment({"entities": [make_card(fields=[])]})
    problems = lint_fragment.lint_fragment_problems(m, None)
    assert any("has no FIELDS" in p for p in problems)


def test_an_enum_card_is_exempt_from_the_fields_rule():
    """`store.mode == "enum"` says the card describes a closed value set, which has members, not
    typed fields. Requiring fields there taught a live build to hand-inject the enum members into
    `fields` to get past the gate — the tool teaching the map to lie."""
    m = make_fragment({"entities": [make_card(fields=[], store={"mode": "enum"})]})
    assert not any("has no FIELDS" in p for p in lint_fragment.lint_fragment_problems(m, None))


def test_a_meaning_less_card_fails_the_fragment_lint():
    m = make_fragment({"entities": [make_card(meaning="")]})
    assert any("missing a MEANING" in p for p in lint_fragment.lint_fragment_problems(m, None))


def make_access_rule_fragment(risk: str = "") -> dict:
    """One `access: true` rule with an anchored operative site — the shape a T7 block agent writes."""
    return {"rules": [{"id": "BR1", "statement": "Only a signed-in user may read a ticket.",
                       "access": True, "risk": risk,
                       "sites": [{"where": "src/auth/gate.py:22",
                                  "why": "rejects an anonymous caller"}]}]}


def test_an_access_rule_with_no_risk_is_advised():
    """method.md requires an auth surface to state what is at stake as its `risk`, and before the T7
    fold every security row carried one. After it, two consecutive real builds shipped maps where NOT
    ONE access rule of 47 and 44 had a risk — the rendered Security & auth table's Risk column was
    blank on every row — and no gate anywhere said so."""
    warnings = lint_fragment.lint_fragment_warnings(make_fragment(make_access_rule_fragment()))
    hits = [w for w in warnings if "empty `risk`" in w]
    assert len(hits) == 1, warnings
    assert "BR1" in hits[0]


def test_an_access_rule_that_states_its_risk_is_not_advised():
    warnings = lint_fragment.lint_fragment_warnings(
        make_fragment(make_access_rule_fragment(risk="anyone could read any ticket")))
    assert not [w for w in warnings if "empty `risk`" in w], warnings


def test_a_non_access_rule_with_no_risk_is_not_advised():
    """`risk` is required of an ACCESS surface, not of every business rule — advising on all of them
    would fire on the whole decision layer of every map."""
    frag = make_access_rule_fragment()
    frag["rules"][0]["access"] = False
    assert not [w for w in lint_fragment.lint_fragment_warnings(make_fragment(frag)) if "empty `risk`" in w]
