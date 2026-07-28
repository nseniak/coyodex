#!/usr/bin/env python3
"""Tests for `coyodex reconcile` — expanding path rules into an explicit reconcile.json.

The failure this command exists to prevent: a live 429-component build hand-wrote a generator
script that reported "components=0 assigned=429" — it emitted assignments for ids that were not in
the map, and nothing checked. Every test here is about that class: ids resolved against a real map,
and anything that matched nothing said out loud.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_reconcile_build.py
    pytest tests/test_reconcile_build.py
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyodex.model import Component, Dep, DeploymentRow, Entity, Group, ProjectModel
from coyodex.reconcile_build import RuleError, coverage_report, expand, load_rules


def make_map() -> ProjectModel:
    m = ProjectModel(title="Demo", goal="g")
    m.subsystems = [Group(id="S1", name="Plugins"), Group(id="S2", name="Web")]
    m.subdomains = [Group(id="SD1", name="Billing")]
    m.components = [
        Component(id="C1", name="PluginA", source="app/plugins/a.py:1"),
        Component(id="C2", name="PluginB", source="app/plugins/b.py:1"),
        Component(id="C3", name="Deep", source="app/plugins/nested/deep.py:1"),
        Component(id="C4", name="Web", source="web/main.py:1"),
    ]
    m.entities = [Entity(id="E1", name="Invoice", meaning="m", source="app/plugins/models.py:3")]
    m.deps = [Dep(id="D1", name="Redis", type="broker")]
    m.deployment = [DeploymentRow(unit="api"), DeploymentRow(unit="worker")]
    return m


def write_rules(rules: list[dict], tmp: str) -> Path:
    p = Path(tmp) / "rules.json"
    p.write_text(json.dumps({"rules": rules}), encoding="utf-8")
    return p


# --------------------------------------------------------------------------------------
# rule shape
# --------------------------------------------------------------------------------------

def test_rules_must_select_and_assign_something():
    with tempfile.TemporaryDirectory() as tmp:
        for bad in ([{"subsystem": "S1"}],                 # selects nothing
                    [{"source_glob": "app/**"}]):          # assigns nothing
            try:
                load_rules(write_rules(bad, tmp))
                raise AssertionError(f"expected RuleError for {bad}")
            except RuleError:
                pass


# --------------------------------------------------------------------------------------
# matching
# --------------------------------------------------------------------------------------

def test_single_star_does_not_cross_a_directory_boundary():
    # `app/plugins/*` must NOT swallow `app/plugins/nested/deep.py` — fnmatch alone would, silently
    # over-assigning a whole subtree to one subsystem.
    doc, _ = expand(make_map(), [{"source_glob": "app/plugins/*", "subsystem": "S1"}])
    assert [s["ids"] for s in doc["set"]] == [["C1", "C2"]]


def test_double_star_is_the_recursive_form():
    doc, _ = expand(make_map(), [{"source_glob": "app/plugins/**", "subsystem": "S1"}])
    assert doc["set"][0]["ids"] == ["C1", "C2", "C3"]


def test_a_glob_silently_skips_elements_the_field_cannot_apply_to():
    # `app/plugins/**` also matches entity E1; `subsystem` is a component field, so E1 is skipped —
    # that is the rule working, not a problem worth a warning.
    doc, report = expand(make_map(), [{"source_glob": "app/plugins/**", "subsystem": "S1"}])
    assert "E1" not in doc["set"][0]["ids"]
    assert not [line for line in report if "E1" in line]


def test_naming_a_wrong_typed_id_explicitly_is_reported():
    _, report = expand(make_map(), [{"ids": ["E1"], "subsystem": "S1"}])
    assert any("E1" in line and "does not apply" in line for line in report)


# --------------------------------------------------------------------------------------
# the bug this command exists to prevent
# --------------------------------------------------------------------------------------

def test_ids_absent_from_the_map_are_reported_not_emitted():
    doc, report = expand(make_map(), [{"ids": ["C1", "C999"], "runs_in": ["api"]}])
    assert doc["set"][0]["ids"] == ["C1"]                       # C999 never reaches the file
    assert any("C999" in line for line in report)


def test_a_rule_that_matches_nothing_is_reported():
    doc, report = expand(make_map(), [{"source_glob": "nope/**", "subsystem": "S1"}])
    assert doc["set"] == []
    assert any("matched NOTHING" in line for line in report)


# --------------------------------------------------------------------------------------
# assignment semantics
# --------------------------------------------------------------------------------------

def test_later_rules_override_earlier_ones_per_field():
    doc, _ = expand(make_map(), [
        {"source_glob": "app/plugins/**", "subsystem": "S1"},
        {"ids": ["C2"], "subsystem": "S2"},                     # narrow override after a broad rule
    ])
    by_id = {eid: s["subsystem"] for s in doc["set"] for eid in s["ids"]}
    assert by_id == {"C1": "S1", "C2": "S2", "C3": "S1"}


def test_multiple_fields_on_one_rule_group_together():
    doc, _ = expand(make_map(), [{"source_glob": "app/plugins/*",
                                  "subsystem": "S1", "runs_in": ["api", "worker"]}])
    assert len(doc["set"]) == 1
    assert doc["set"][0]["subsystem"] == "S1"
    assert doc["set"][0]["runs_in"] == ["api", "worker"]


def test_output_feeds_assemble_reconcile_unchanged():
    # the emitted document must be exactly what `assemble --reconcile` already consumes.
    from coyodex.reconcile import load_reconcile
    with tempfile.TemporaryDirectory() as tmp:
        doc, _ = expand(make_map(), [{"source_glob": "app/plugins/*", "subsystem": "S1"}])
        p = Path(tmp) / "reconcile.json"
        p.write_text(json.dumps(doc), encoding="utf-8")
        load_reconcile(p.read_text(), "reconcile.json")          # raises if the shape is wrong


# --------------------------------------------------------------------------------------
# what the rules did NOT reach
# --------------------------------------------------------------------------------------

def test_coverage_report_names_the_elements_left_unassigned():
    m = make_map()
    doc, _ = expand(m, [{"source_glob": "app/plugins/*", "subsystem": "S1"}])
    lines = coverage_report(m, doc)
    assert any("C4" in line and "subsystem" in line for line in lines)   # web/ matched no rule
    assert any("E1" in line and "subdomain" in line for line in lines)
    assert any("runs_in" in line for line in lines)                      # deployment[] exists


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))


# --------------------------------------------------------------------------------------
# glob semantics — every case below was a REAL defect in the first hand-rolled matcher
# --------------------------------------------------------------------------------------

def test_star_outside_the_last_segment_matches():
    # was: any `*` before the final segment matched NOTHING, while blaming the user's path prefix.
    from coyodex.reconcile_build import _matches
    assert _matches("a/*/b", "a/x/b")
    assert not _matches("a/*/b", "a/b")
    assert not _matches("a/*/b", "a/x/y/b")


def test_double_star_does_not_discard_what_follows_it():
    # was: everything after `**` was dropped, so `a/**/nope` matched every path under `a/`.
    from coyodex.reconcile_build import _matches
    assert _matches("a/**/b", "a/x/y/b")
    assert _matches("a/**/b", "a/b")
    assert not _matches("a/**/nope", "a/x/y/b")


def test_leading_double_star_still_constrains_the_tail():
    # was: a leading `**` matched EVERY path, silently reassigning a whole map.
    from coyodex.reconcile_build import _matches
    assert _matches("**/*.md", "README.md")
    assert _matches("**/*.md", "a/b/c.md")
    assert not _matches("**/*.md", "a/b/c.py")


def test_a_trailing_slash_behaves_like_the_directory():
    # was: a trailing `/` matched nothing at all.
    from coyodex.reconcile_build import _matches
    assert _matches("app/plugins/", "app/plugins/a.py")
    assert _matches("app/plugins", "app/plugins/a.py")
    assert not _matches("app/plugins", "app/pluginsX/a.py")


def test_a_leading_double_star_rule_cannot_sweep_the_whole_map():
    # the end-to-end shape of the same bug: `**/*.md` must not reassign every component.
    doc, _ = expand(make_map(), [{"source_glob": "**/*.md", "subsystem": "S1"}])
    assert doc["set"] == []
