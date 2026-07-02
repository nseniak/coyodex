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

from coyodex.assemble import (ensure_fragments_ignored, load_fragment, merge_fragments,
                              normalize_anchors)
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


# --- anchor normalization ----------------------------------------------------------

def make_anchored_model(component_anchor: str | None = None, group_anchor: str | None = None,
                        entity_source: str | None = None):
    frag: dict[str, object] = {"components": [{"id": "C1", "name": "X"}]}
    if component_anchor is not None:
        frag = {"components": [{"id": "C1", "name": "X", "anchor": component_anchor}]}
    if group_anchor is not None:
        frag["subsystems"] = [{"id": "S1", "name": "Core", "anchor": group_anchor}]
    if entity_source is not None:
        frag["entities"] = [{"id": "E1", "name": "Thing", "source": entity_source}]
    model, problems = merge_fragments([("f.json", load_fragment(json.dumps(frag), "f.json"))])
    assert problems == []
    return model


def test_component_md_link_anchor_is_reduced_to_its_bare_href():
    m = make_anchored_model(component_anchor="[app.py](backend/app.py#L10)")
    notes = normalize_anchors(m, None)
    assert m.components[0].anchor == "backend/app.py#L10"
    assert any("C1" in n for n in notes)


def test_entity_md_link_source_is_reduced_to_its_bare_href():
    m = make_anchored_model(entity_source="[user.py](domain/user.py#L5)")
    normalize_anchors(m, None)
    assert m.entities[0].source == "domain/user.py#L5"


def test_bare_group_anchor_is_wrapped_into_a_link():
    m = make_anchored_model(group_anchor="backend/core/")
    normalize_anchors(m, None)
    assert m.subsystems[0].anchor == "[core](backend/core/)"


def test_authored_group_link_label_is_kept():
    m = make_anchored_model(group_anchor="[Core services](backend/core/)")
    notes = normalize_anchors(m, None)
    assert m.subsystems[0].anchor == "[Core services](backend/core/)" and notes == []


def test_directory_anchor_gets_a_trailing_slash_when_the_repo_shows_a_dir():
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "backend").mkdir()
        m = make_anchored_model(component_anchor="backend")
        normalize_anchors(m, Path(td))
        assert m.components[0].anchor == "backend/"
        # a file-like anchor (has #Lnnn) is never slashed
        m2 = make_anchored_model(component_anchor="backend#L1")
        normalize_anchors(m2, Path(td))
        assert m2.components[0].anchor == "backend#L1"


# --- the build-fragments gitignore -------------------------------------------------

def test_ensure_fragments_ignored_creates_appends_and_is_idempotent():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        assert ensure_fragments_ignored(out) is True
        assert (out / ".gitignore").read_text(encoding="utf-8") == "build-fragments/\n"
        assert ensure_fragments_ignored(out) is False  # idempotent
        (out / ".gitignore").write_text("preindex.json", encoding="utf-8")  # no trailing newline
        assert ensure_fragments_ignored(out) is True
        assert (out / ".gitignore").read_text(encoding="utf-8") == "preindex.json\nbuild-fragments/\n"


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
        assert (out / "project-map.md").exists() and (out / "project-map.html").exists()


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
