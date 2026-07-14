"""Unified-diff row parsing (`coyodex.viewer.diffmap`) — what remains of the old diff viewer's
pure core after the impact explorer superseded its projection layer. Explicit builders, no fixtures.
"""
from __future__ import annotations

from coyodex.viewer.diffmap import DiffRow, parse_unified_diff


# --- parse_unified_diff ---------------------------------------------------------
def test_parse_unified_diff_line_numbers_and_ops() -> None:
    text = (
        "diff --git a/f.py b/f.py\n"
        "index 111..222 100644\n"
        "--- a/f.py\n"
        "+++ b/f.py\n"
        "@@ -1,3 +1,3 @@\n"
        " a\n"
        "-b\n"
        "+B\n"
        " c\n"
    )
    rows = parse_unified_diff(text)
    assert [(r.op, r.old_ln, r.new_ln, r.text) for r in rows] == [
        ("hunk", None, None, "@@ -1,3 +1,3 @@"),
        ("ctx", 1, 1, "a"),
        ("del", 2, None, "b"),
        ("add", None, 2, "B"),
        ("ctx", 3, 3, "c"),
    ]


def test_parse_unified_diff_added_file_all_adds() -> None:
    text = "--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,2 @@\n+one\n+two\n"
    rows = parse_unified_diff(text)
    assert [(r.op, r.new_ln) for r in rows if r.op == "add"] == [("add", 1), ("add", 2)]


def test_parse_unified_diff_preamble_skipped_and_no_newline_marker() -> None:
    text = "@@ -1,1 +1,1 @@\n-old\n+new\n\\ No newline at end of file\n"
    rows = parse_unified_diff(text)
    assert [r.op for r in rows] == ["hunk", "del", "add"]   # the "\ No newline" marker dropped


def test_parse_unified_diff_empty_before_first_hunk() -> None:
    assert parse_unified_diff("diff --git a/x b/x\nindex 1..2\n") == []


if __name__ == "__main__":
    import sys

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
    sys.exit(0)
