#!/usr/bin/env python3
"""Tests for `coyodex assemble` — structured-row fragments → the canonical model.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_assemble.py
    pytest tests/test_assemble.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex.assemble import ensure_fragments_ignored, load_fragment, merge_fragments
from coyodex.model import ModelError, load_model, to_canonical_json

ASSEMBLE = [sys.executable, "-m", "coyodex.assemble"]


# --- builders -------------------------------------------------------------------

def make_header_fragment() -> str:
    return json.dumps({"title": "Demo", "goal": "A demo.", "commit": "abc1234"})


def make_harvest_fragment(cid: str = "C1") -> str:
    return json.dumps({
        "components": [{"id": cid, "name": f"Component {cid}", "purpose": "does things"}],
        "deps": [] if cid != "C1" else [{"id": "D1", "name": "Postgres", "kind": "datastore",
                                         "type": "SQL database"}],
    })


def make_trace_fragment() -> str:
    return json.dumps({
        "edges": [{"src": "C1", "verb": "uses", "dst": "D1", "why": "query",
                   "where": "src/a.py:3"}],
    })


# --- merge ----------------------------------------------------------------------

def test_merge_concatenates_arrays_and_takes_singletons():
    parts = [("header.json", load_fragment(make_header_fragment(), "header.json")),
             ("h1.json", load_fragment(make_harvest_fragment("C1"), "h1.json")),
             ("h2.json", load_fragment(make_harvest_fragment("C2"), "h2.json")),
             ("t1.json", load_fragment(make_trace_fragment(), "t1.json"))]
    model, problems = merge_fragments(parts)
    assert problems == []
    assert model.title == "Demo" and model.commit == "abc1234"
    assert [c.id for c in model.components] == ["C1", "C2"]
    assert len(model.edges) == 1 and model.edges[0].dst == "D1"


def test_duplicate_id_across_fragments_is_a_conflict():
    parts = [("a.json", load_fragment(make_harvest_fragment("C1"), "a.json")),
             ("b.json", load_fragment(make_harvest_fragment("C1"), "b.json"))]
    _model, problems = merge_fragments(parts)
    assert any("duplicate id C1" in p and "a.json" in p and "b.json" in p for p in problems)


def test_conflicting_singletons_are_a_conflict():
    a = load_fragment(json.dumps({"title": "One"}), "a.json")
    b = load_fragment(json.dumps({"title": "Two"}), "b.json")
    _model, problems = merge_fragments([("a.json", a), ("b.json", b)])
    assert any("'title'" in p for p in problems)


def test_malformed_fragment_fails_alone_with_its_path():
    try:
        load_fragment(json.dumps({"components": [{"id": "C1"}]}), "h.json")  # name missing
        raise AssertionError("expected ModelError")
    except ModelError as e:
        assert "h.json" in str(e)


# --- extra accepts natural JSON values --------------------------------------------

def test_extra_accepts_natural_json_values():
    frag = json.dumps({"components": [{"id": "C1", "name": "X", "extra": {
        "Ports": [8080, 8443], "Replicas": 3, "HA": True, "Note": "plain text"}}]})
    m = load_fragment(frag, "h.json")
    assert m.components[0].extra["Ports"] == [8080, 8443]
    assert m.components[0].extra["Replicas"] == 3
    # the canonical serializer round-trips the values unchanged
    m2 = load_model(to_canonical_json(merge_fragments([("h.json", m)])[0]))
    assert m2.components[0].extra == m.components[0].extra


def test_extra_non_string_values_render_as_compact_json_in_the_md_view():
    from coyodex.views import model_to_markdown
    frag = json.dumps({"title": "T", "components": [
        {"id": "C1", "name": "X", "extra": {"Ports": [8080, 8443]}}]})
    model, problems = merge_fragments([("h.json", load_fragment(frag, "h.json"))])
    assert problems == []
    md = model_to_markdown(model)
    assert "[8080, 8443]" in md, md


# --- files / evidence / package / alternative: real fields, rendered as their own T1/T2 columns ---

def test_component_files_and_evidence_render_as_their_own_t1_columns():
    from coyodex.views import model_to_markdown
    frag = json.dumps({"title": "T", "components": [
        {"id": "C1", "name": "X", "files": ["src/v.py", "src/helpers.py"],
         "evidence": [{"file": "src/v.py:12", "why": "the entry point"}]}]})
    model, problems = merge_fragments([("h.json", load_fragment(frag, "h.json"))])
    assert problems == []
    md = model_to_markdown(model)
    assert "| Files |" in md and "Evidence |" in md, md
    assert "src/v.py · src/helpers.py" in md
    assert "[v.py](src/v.py:12) — the entry point" in md


def test_dep_package_and_alternative_render_as_their_own_t2_columns():
    from coyodex.views import model_to_markdown
    frag = json.dumps({"title": "T", "deps": [
        {"id": "D1", "name": "MongoDB", "package": "motor ^3.7.0 (pyproject.toml)",
         "alternative": "file-backed storage in standalone mode"}]})
    model, problems = merge_fragments([("h.json", load_fragment(frag, "h.json"))])
    assert problems == []
    md = model_to_markdown(model)
    assert "| Package |" in md and "Alternative |" in md, md
    assert "motor ^3.7.0 (pyproject.toml)" in md
    assert "file-backed storage in standalone mode" in md


def test_files_and_evidence_columns_absent_when_unused():
    from coyodex.views import model_to_markdown
    frag = json.dumps({"title": "T", "components": [{"id": "C1", "name": "X"}]})
    model, problems = merge_fragments([("h.json", load_fragment(frag, "h.json"))])
    assert problems == []
    md = model_to_markdown(model)
    assert "| Files |" not in md and "| Evidence |" not in md, md


# --- anchors are not fixed up ------------------------------------------------------
# `assemble` no longer normalizes anchor drift (a markdown-linked anchor, a missing directory
# slash, a retired `#Lnnn` suffix) — a fragment's fields pass through unchanged, and
# `coyodex validate`'s `_check_anchor_format` (tests/test_validate_model.py) is what rejects a
# wrong shape. These guard that no silent fix-up regrows here.

def test_component_anchor_passes_through_unchanged():
    frag = {"components": [{"id": "C1", "name": "X", "source": "[app.py](backend/app.py#L10)"}]}
    model, problems = merge_fragments([("f.json", load_fragment(json.dumps(frag), "f.json"))])
    assert problems == []
    assert model.components[0].source == "[app.py](backend/app.py#L10)"


def test_edge_where_passes_through_unchanged():
    frag = {"components": [{"id": "C1", "name": "X"}, {"id": "C2", "name": "Y"}],
            "edges": [{"src": "C1", "verb": "uses", "dst": "C2",
                      "where": "[app.py](backend/app.py#L20)"}]}
    model, problems = merge_fragments([("f.json", load_fragment(json.dumps(frag), "f.json"))])
    assert problems == []
    assert model.edges[0].where == "[app.py](backend/app.py#L20)"


# --- the build-fragments gitignore -------------------------------------------------

def test_ensure_fragments_ignored_creates_appends_and_is_idempotent():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        assert ensure_fragments_ignored(out) is True
        assert (out / ".gitignore").read_text(encoding="utf-8") == "build-fragments/\n"
        assert ensure_fragments_ignored(out) is False  # idempotent


def test_ensure_fragments_ignored_strips_stray_preindex_ignore():
    # preindex.json is a committed artifact — a stray ignore line (older build / hand edit) must be
    # stripped, build-fragments/ kept, and any unrelated lines left intact.
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        (out / ".gitignore").write_text("preindex.json", encoding="utf-8")  # no trailing newline
        assert ensure_fragments_ignored(out) is True
        assert (out / ".gitignore").read_text(encoding="utf-8") == "build-fragments/\n"
        # a fuller stray gitignore: preindex stripped, build-fragments kept, other lines preserved
        (out / ".gitignore").write_text("*.log\nbuild-fragments/\npreindex.json\n", encoding="utf-8")
        assert ensure_fragments_ignored(out) is True
        assert (out / ".gitignore").read_text(encoding="utf-8") == "*.log\nbuild-fragments/\n"
        assert ensure_fragments_ignored(out) is False  # now stable


def test_assemble_cli_writes_the_fragments_gitignore():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "h.json"
        p.write_text(make_harvest_fragment("C1"), encoding="utf-8")
        out = Path(td) / "map"
        proc = subprocess.run(ASSEMBLE + [str(p), "--out", str(out)],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert "build-fragments/" in (out / ".gitignore").read_text(encoding="utf-8")


# --- CLI end-to-end ---------------------------------------------------------------

def test_assemble_cli_writes_canonical_map_and_views():
    with tempfile.TemporaryDirectory() as td:
        frags = []
        for name, content in (("header.json", make_header_fragment()),
                              ("h1.json", make_harvest_fragment("C1")),
                              ("t1.json", make_trace_fragment())):
            p = Path(td) / name
            p.write_text(content, encoding="utf-8")
            frags.append(str(p))
        out = Path(td) / "map"
        proc = subprocess.run(ASSEMBLE + frags + ["--out", str(out)],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        model = load_model((out / "project-map.json").read_text(encoding="utf-8"))
        assert model.title == "Demo" and [c.id for c in model.components] == ["C1"]
        # The interactive viewer is served by `coyodex serve`, not baked, so assembly writes json + md
        # (the committed views) and no HTML file.
        assert (out / "project-map.md").exists() and not (out / "project-map.html").exists()


def test_assemble_cli_fails_on_duplicate_ids_and_writes_nothing():
    with tempfile.TemporaryDirectory() as td:
        p1, p2 = Path(td) / "a.json", Path(td) / "b.json"
        p1.write_text(make_harvest_fragment("C1"), encoding="utf-8")
        p2.write_text(make_harvest_fragment("C1"), encoding="utf-8")
        out = Path(td) / "map"
        proc = subprocess.run(ASSEMBLE + [str(p1), str(p2), "--out", str(out)],
                              capture_output=True, text=True)
        assert proc.returncode == 1
        assert "duplicate id C1" in proc.stderr
        assert not out.exists()


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
