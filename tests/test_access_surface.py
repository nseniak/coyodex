#!/usr/bin/env python3
"""`coyomap access-surface` + `finalize --access-baseline` — a security claim that disappeared.

A from-scratch rebuild is deliberately blind to its predecessor, and that independence is the point.
The cost is that a claim can vanish between two maps of UNCHANGED code with nothing noticing. On the
2026-08-20 argus pair the access-rule statement count held at 21 -> 21, so `auth-surfaces-no-drop`
passed, while `adapters/auth_google.py` — which verifies the Google ID token's signature, issuer and
audience — lost its claim entirely: the previous map carried it as access rule BR21, and none of the
new map's 61 rules mentions a signature, an issuer or an audience.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from coyomap.access_surface import access_files, load_surface, lost_files, write_surface
from coyomap.assemble import load_map_or_fragment


def _map(rules: list[dict[str, object]]) -> dict[str, object]:
    return {"format": "coyomap-map", "title": "t", "goal": "g", "commit": "abc1234",
            "rules": rules}


def _rule(rid: str, statement: str, sites: list[str], access: bool = True) -> dict[str, object]:
    return {"id": rid, "statement": statement, "access": access, "risk": "impersonation",
            "sites": [{"where": w, "why": "enforces it"} for w in sites]}


def _model(doc: dict[str, object]):
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "m.json"
        p.write_text(json.dumps(doc), encoding="utf-8")
        m, _present = load_map_or_fragment(p)
    return m


def test_the_surface_is_files_not_statements() -> None:
    """Statements are LLM prose and drift between builds with no change in meaning; a line moves when
    the code above it moves. A file that lost its coverage is the signal that survives both."""
    m = _model(_map([_rule("BR1", "Only a proven identity", ["a/auth.py:67", "a/auth.py:73"]),
                     _rule("BR2", "Owner scoping", ["b/store.py:18"])]))
    assert access_files(m) == {"a/auth.py": ["BR1"], "b/store.py": ["BR2"]}


def test_a_non_access_rule_is_not_part_of_the_auth_surface() -> None:
    m = _model(_map([_rule("BR1", "A plan cap", ["c/plan.py:9"], access=False)]))
    assert access_files(m) == {}


def test_a_file_that_lost_its_only_access_rule_is_named() -> None:
    before = _model(_map([_rule("BR21", "Only a proven upstream identity", ["a/auth_google.py:67"]),
                          _rule("BR2", "Owner scoping", ["b/store.py:18"])]))
    after = _model(_map([_rule("BR7", "Owner scoping, reworded", ["b/store.py:20"])]))
    assert lost_files(access_files(before), after) == ["a/auth_google.py"]


def test_a_rewording_or_a_moved_line_in_the_same_file_is_not_a_loss() -> None:
    """Two independent LLM builds legitimately reword and re-anchor. Only a whole file going
    unclaimed is reported, or the check would fire on every rebuild and be ignored."""
    before = _model(_map([_rule("BR1", "Only a proven identity", ["a/auth.py:67"])]))
    after = _model(_map([_rule("BR9", "An identity counts only once proven", ["a/auth.py:120"])]))
    assert lost_files(access_files(before), after) == []


def test_a_surface_file_and_a_whole_map_are_both_accepted_as_the_baseline() -> None:
    """Every archive already holds a map; requiring a pre-conversion is the friction that leaves a
    check unrun."""
    doc = _map([_rule("BR1", "Only a proven identity", ["a/auth.py:67"])])
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        map_path = tmp / "m.json"
        map_path.write_text(json.dumps(doc), encoding="utf-8")
        surface_path = tmp / "s.json"
        write_surface(_model(doc), surface_path)
        assert load_surface(map_path) == load_surface(surface_path) == {"a/auth.py": ["BR1"]}
