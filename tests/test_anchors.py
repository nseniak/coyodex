"""Tests for `coyodex.anchors` — anchor format, parsing, and the drift comparator (Phase A2 + G)."""
from __future__ import annotations

from coyodex.anchors import anchor_drift, is_anchor, is_file_anchor, parse_anchor


def test_file_anchor_accepts_dotted_and_extensionless_with_line():
    for good in ("a/b.py", "a/b.py:12", "a/b.py:12-18", "Dockerfile:1", "Makefile:6-9"):
        assert is_file_anchor(good), good
    for bad in ("Dockerfile", "a/dir/", "just prose here"):
        assert not is_file_anchor(bad), bad


def test_is_anchor_allows_directory():
    assert is_anchor("src/dir/") and not is_file_anchor("src/dir/")


def test_parse_anchor_forms():
    assert parse_anchor("a/b.py:70") == parse_anchor("a/b.py#L70")  # both → lo=hi=70
    assert (parse_anchor("a/b.py:70").lo, parse_anchor("a/b.py:70").hi) == (70, 70)
    r = parse_anchor("a/b.py:70-75")
    assert (r.lo, r.hi) == (70, 75)
    assert parse_anchor("a/b.py#L70-L75").hi == 75
    assert parse_anchor("a/b.py").lo is None          # a bare path has no line
    assert parse_anchor("somewhere in the code") is None  # prose


def test_drift_same_file_within_and_over_tolerance():
    # the mcpolis case: stored 245, skeptics found 243 → drift at tol 0, none at tol 2.
    assert anchor_drift("org_service.py:245", ["org_service.py:243"], 0).drifted is True
    assert anchor_drift("org_service.py:245", ["org_service.py:243"], 2).drifted is False


def test_drift_different_file_is_always_drift():
    d = anchor_drift("a.py:10", ["b.py:10"], 5)
    assert d.drifted is True and d.same_file is False and d.distance is None


def test_drift_uses_median_of_reported_lines():
    d = anchor_drift("a.py:10", ["a.py:20", "a.py:21", "a.py:22"], 2)
    assert d.reported == 21 and d.distance == 11 and d.drifted is True


def test_drift_range_containment_is_not_drift():
    # a stored line-line range: a reported line INSIDE it (or within tolerance of it) is no drift.
    assert anchor_drift("a.py:10-20", ["a.py:15"], 0).drifted is False
    assert anchor_drift("a.py:10-20", ["a.py:25"], 2).drifted is True  # 5 past the top bound


def test_drift_not_comparable_returns_none():
    assert anchor_drift(None, ["a.py:1"], 2) is None            # no stored anchor
    assert anchor_drift("a.py", ["a.py:1"], 2) is None          # stored has no line
    assert anchor_drift("a.py:1", ["prose only"], 2) is None    # no parseable reported line
    assert anchor_drift("a.py:1", [], 2) is None                # no evidence
