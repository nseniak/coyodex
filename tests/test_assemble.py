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

from coyodex import assemble
from coyodex.assemble import (_infer_ce_verb, ensure_fragments_ignored, load_fragment,
                              load_fragment_paths, merge_fragments)
from coyodex.model import ModelError, load_model, to_canonical_json

ASSEMBLE = [sys.executable, "-m", "coyodex.assemble"]


# --- C→E verb inference (regression after the verb families moved to grammar — DRY refactor) -------

def test_infer_ce_verb_unchanged_after_grammar_move():
    # The four families now live in grammar; _infer_ce_verb must classify EXACTLY as before.
    assert _infer_ce_verb("upserts the membership document") == "persists"
    assert _infer_ce_verb("updates the counter") == "writes"
    assert _infer_ce_verb("publishes the event") == "emits"
    assert _infer_ce_verb("encrypts the token") == "encrypts"
    assert _infer_ce_verb("reads the user record") == "reads"
    assert _infer_ce_verb("reads the asset metadata") == "reads"   # 'asset' contains 'set' — not a WRITE
    assert _infer_ce_verb("") == "reads"                            # ambiguous → never over-claims ownership


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


def test_strip_actor_edges_removes_role_endpoints_and_reports():
    # A trace agent wrongly emits an actor→component edge (R1 → C1). Edges connect
    # components/deps/entities ONLY — assemble strips it and reports the count.
    roles = json.dumps({"roles": [{"id": "R1", "name": "Admin", "kind": "human"}]})
    edges = json.dumps({"edges": [
        {"src": "R1", "verb": "uses", "dst": "C1", "why": "drives", "where": "src/a.py:1"},
        {"src": "C1", "verb": "uses", "dst": "D1", "why": "query", "where": "src/a.py:3"}]})
    parts = [("r.json", load_fragment(roles, "r.json")),
             ("e.json", load_fragment(edges, "e.json"))]
    stats: dict[str, int] = {}
    model, problems = merge_fragments(parts, stats)
    assert problems == []
    assert [(e.src, e.dst) for e in model.edges] == [("C1", "D1")]
    assert stats["actor_edges_stripped"] == 1


def make_component_fragment(cid: str, name: str, source: str, extra: dict | None = None) -> str:
    comp = {"id": cid, "name": name, "purpose": "does things", "source": source}
    return json.dumps({"components": [comp], **(extra or {})})


def test_component_dedup_merges_same_file_and_repoints_test_targets():
    # The same module harvested by two overlapping slices (same file + name). assemble collapses
    # them to one and RE-POINTS every reference — here a tests[].targets id (the review blocker-1
    # regression: a missed ref would become a dangling-reference validate failure).
    a = make_component_fragment("C1", "RolesManager", "mee6/roles_manager/__init__.py:1")
    b = json.dumps({
        "components": [{"id": "C2", "name": "RolesManager",
                        "purpose": "does things", "source": "mee6/roles_manager/__init__.py:1"}],
        "edges": [{"src": "C2", "verb": "uses", "dst": "D1", "why": "q", "where": "x.py:2"}],
        "tests": [{"targets": ["C2"], "tested": "no", "gap": "untested"}],
        "entry_points": [{"kind": "route", "trigger": "GET /x", "source": "x.py:1", "component": "C2"}],
    })
    parts = [("a.json", load_fragment(a, "a.json")), ("b.json", load_fragment(b, "b.json"))]
    stats: dict[str, int] = {}
    model, problems = merge_fragments(parts, stats)
    assert problems == []
    assert [c.id for c in model.components] == ["C1"]           # C2 merged away
    assert stats["components_merged"] == 1
    assert model.edges[0].src == "C1"                            # edge re-pointed
    assert model.tests[0].targets == ["C1"]                     # tests target re-pointed (blocker 1)
    assert model.entry_points[0].component == "C1"              # owner re-pointed
    # the round-trips through validate with no dangling reference
    assert load_model(to_canonical_json(model)) is not None


def test_component_dedup_skips_directory_anchor_and_empty_source():
    # A shared DIRECTORY anchor is NOT identity (two different components legitimately live under one
    # dir), and an empty source is not identity either (review blocker 2) — neither pair merges.
    dir_a = make_component_fragment("C1", "PluginA", "mee6/plugins/")
    dir_b = make_component_fragment("C2", "PluginB", "mee6/plugins/")
    none_a = json.dumps({"components": [{"id": "C3", "name": "X", "purpose": "p"}]})
    none_b = json.dumps({"components": [{"id": "C4", "name": "X", "purpose": "p"}]})
    parts = [(n, load_fragment(f, n)) for n, f in
             [("a", dir_a), ("b", dir_b), ("c", none_a), ("d", none_b)]]
    stats: dict[str, int] = {}
    model, _problems = merge_fragments(parts, stats)
    assert [c.id for c in model.components] == ["C1", "C2", "C3", "C4"]  # nothing merged
    assert stats["components_merged"] == 0


def test_duplicate_id_across_fragments_is_a_conflict():
    parts = [("a.json", load_fragment(make_harvest_fragment("C1"), "a.json")),
             ("b.json", load_fragment(make_harvest_fragment("C1"), "b.json"))]
    _model, problems = merge_fragments(parts)
    assert any("duplicate id C1" in p and "a.json" in p and "b.json" in p for p in problems)


def test_assemble_collapses_same_edge_same_call_site():
    # Two trace slices emit the SAME relationship at the SAME call site, differing only in the `why`
    # wording (the real duplication pattern) → one row kept (the first `why`).
    a = json.dumps({"edges": [{"src": "C1", "verb": "persists", "dst": "E1",
                               "why": "insert the row", "where": "src/a.py:3"}]})
    b = json.dumps({"edges": [{"src": "C1", "verb": "persists", "dst": "E1",
                               "why": "creates and stores the record", "where": "src/a.py:3"}]})
    parts = [("t1.json", load_fragment(a, "t1.json")), ("t2.json", load_fragment(b, "t2.json"))]
    model, problems = merge_fragments(parts)
    assert problems == []
    assert len(model.edges) == 1 and model.edges[0].why == "insert the row"


def test_assemble_keeps_edges_that_differ_in_anchor():
    # Same (src,verb,dst) but a DIFFERENT where is a real conflict — NOT silently merged; both kept
    # (validate then warns so a human picks the primary call site).
    a = json.dumps({"edges": [{"src": "C1", "verb": "uses", "dst": "D1", "why": "q", "where": "a.py:3"}]})
    b = json.dumps({"edges": [{"src": "C1", "verb": "uses", "dst": "D1", "why": "q", "where": "a.py:9"}]})
    parts = [("a.json", load_fragment(a, "a.json")), ("b.json", load_fragment(b, "b.json"))]
    model, _problems = merge_fragments(parts)
    assert len(model.edges) == 2


def test_assemble_never_merges_no_call_site_edges():
    # A no_call_site edge has no anchor to disambiguate, so a differing `why` may be two DISTINCT
    # couplings (two events on the same pair) — never silently merged; both kept for validate to warn.
    a = json.dumps({"edges": [{"src": "C1", "verb": "notifies", "dst": "C2",
                               "why": "publishes OrderCreated", "no_call_site": True}]})
    b = json.dumps({"edges": [{"src": "C1", "verb": "notifies", "dst": "C2",
                               "why": "publishes OrderCancelled", "no_call_site": True}]})
    parts = [("a.json", load_fragment(a, "a.json")), ("b.json", load_fragment(b, "b.json"))]
    model, _problems = merge_fragments(parts)
    assert len(model.edges) == 2


def test_dep_merge_then_edge_dedup_collapses_repointed_duplicates():
    # dep-merge re-points two edges (C1→D2, C1→D1) onto the SAME survivor dep at the SAME call site;
    # edge-dedup (which runs after) must then collapse the now-identical pair to one.
    d1 = json.dumps({"deps": [{"id": "D1", "name": "stripe", "kind": "saas", "type": "payments"}],
                     "edges": [{"src": "C1", "verb": "uses", "dst": "D1", "why": "charge",
                                "where": "pay.py:5"}]})
    d2 = json.dumps({"deps": [{"id": "D2", "name": "stripe", "kind": "saas", "type": "payments"}],
                     "edges": [{"src": "C1", "verb": "uses", "dst": "D2", "why": "charge",
                                "where": "pay.py:5"}]})
    parts = [("a.json", load_fragment(d1, "a.json")), ("b.json", load_fragment(d2, "b.json"))]
    model, _problems = merge_fragments(parts)
    assert len(model.deps) == 1                       # stripe merged to one dep
    assert len(model.edges) == 1 and model.edges[0].dst == "D1"   # re-pointed pair collapsed


def test_duplicate_deps_merge_by_identity_and_repoint_edges():
    # Two agents discover the SAME external dep (stripe) under different ids; one traces an edge to the
    # second id. Merge collapses them to one dep and re-points the edge to the survivor (C2). No error —
    # multi-slice discovery of the same dep is correct input, not a conflict.
    d1 = '{"deps":[{"id":"D1","name":"stripe"}]}'
    d2 = ('{"deps":[{"id":"D2","name":"Stripe"}],'
          '"edges":[{"src":"C1","verb":"uses","dst":"D2","where":"a.py:1"}]}')
    parts = [("a.json", load_fragment(d1, "a.json")), ("b.json", load_fragment(d2, "b.json"))]
    model, problems = merge_fragments(parts)
    assert problems == []
    assert [d.id for d in model.deps] == ["D1"]      # collapsed to one row
    assert model.edges[0].dst == "D1"                # edge re-pointed to the survivor


def test_distinct_deps_are_not_merged():
    d1 = '{"deps":[{"id":"D1","name":"stripe"}]}'
    d2 = '{"deps":[{"id":"D2","name":"redis"}]}'
    parts = [("a.json", load_fragment(d1, "a.json")), ("b.json", load_fragment(d2, "b.json"))]
    model, _ = merge_fragments(parts)
    assert {d.id for d in model.deps} == {"D1", "D2"}  # different deps stay separate


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
        body = (out / ".gitignore").read_text(encoding="utf-8")
        assert body.splitlines() == list(assemble._GITIGNORE_KEEP)
        assert ensure_fragments_ignored(out) is False  # idempotent


def test_ensure_fragments_ignored_strips_stray_preindex_ignore():
    # preindex.json is a committed artifact — a stray ignore line (older build / hand edit) must be
    # stripped, build-fragments/ kept, and any unrelated lines left intact.
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        (out / ".gitignore").write_text("preindex.json", encoding="utf-8")  # no trailing newline
        assert ensure_fragments_ignored(out) is True
        assert (out / ".gitignore").read_text(encoding="utf-8").splitlines() == \
            list(assemble._GITIGNORE_KEEP)
        # a fuller stray gitignore: preindex stripped, every per-run entry present, others preserved
        (out / ".gitignore").write_text("*.log\nbuild-fragments/\npreindex.json\n", encoding="utf-8")
        assert ensure_fragments_ignored(out) is True
        lines = (out / ".gitignore").read_text(encoding="utf-8").splitlines()
        assert lines[0] == "*.log"                                   # unrelated line preserved
        assert set(assemble._GITIGNORE_KEEP) <= set(lines)           # every per-run artifact ignored
        assert "preindex.json" not in lines                          # the committed artifact is not
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


# --- reconcile (--reconcile: set + drop_edges) ------------------------------------

def make_reconcile_fragment() -> str:
    """A fragment with everything the reconcile directives touch: two components, a subsystem, a dep, an
    entity + subdomain, a deployment unit, one C→D edge, and a C→E flow step with NO backing edge (so
    `_derive_entity_edges` derives one — the target of the drop_edges B1 test)."""
    return json.dumps({
        "title": "Demo", "goal": "g",
        "use_cases": [{"id": "UC1", "name": "Do"}],
        "subsystems": [{"id": "S1", "name": "Core"}],
        "subdomains": [{"id": "SD1", "name": "Sales"}],
        "components": [{"id": "C1", "name": "A", "purpose": "p", "source": "a.py:1"},
                       {"id": "C2", "name": "B", "purpose": "p", "source": "b.py:1"}],
        "deps": [{"id": "D1", "name": "Postgres", "kind": "datastore", "type": "SQL"}],
        "entities": [{"id": "E1", "name": "Order", "source": "order.py:1"}],
        "deployment": [{"unit": "worker"}],
        "edges": [{"src": "C1", "verb": "uses", "dst": "D1", "why": "q", "where": "a.py:2"}],
        "flows": [{"uc": "UC1", "title": "F", "steps": [
            {"n": 1, "src": "C1", "dst": "E1", "phrase": "reads the order", "where": "a.py:5"}]}],
    })


def _assemble_with_reconcile(td: str, reconcile_obj: dict | None
                             ) -> tuple[subprocess.CompletedProcess, Path]:
    frag = Path(td) / "frag.json"
    frag.write_text(make_reconcile_fragment(), encoding="utf-8")
    out = Path(td) / "map"
    args = ASSEMBLE + [str(frag), "--out", str(out)]
    if reconcile_obj is not None:
        rp = Path(td) / "reconcile.json"        # OUTSIDE build-fragments/ (S8) — passed via --reconcile
        rp.write_text(json.dumps(reconcile_obj), encoding="utf-8")
        args += ["--reconcile", str(rp)]
    proc = subprocess.run(args, capture_output=True, text=True)
    return proc, out


def test_reconcile_set_assigns_and_survives_reassemble():
    # The fragment/model-mismatch regression: `set` assignments must re-apply on EVERY assemble (a
    # bespoke patch of the assembled map is discarded by the next assemble).
    rec = {"set": [{"ids": ["C1", "C2"], "subsystem": "S1"},
                   {"ids": ["C1"], "runs_in": ["worker"]},
                   {"ids": ["E1"], "subdomain": "SD1"},
                   {"ids": ["D1"], "bucket": "Data & storage"}]}
    with tempfile.TemporaryDirectory() as td:
        for _ in range(2):                      # assemble TWICE
            proc, out = _assemble_with_reconcile(td, rec)
            assert proc.returncode == 0, proc.stderr
            m = load_model((out / "project-map.json").read_text(encoding="utf-8"))
            assert {c.id: c.subsystem for c in m.components} == {"C1": "S1", "C2": "S1"}
            assert next(c for c in m.components if c.id == "C1").runs_in == ["worker"]
            assert next(e for e in m.entities if e.id == "E1").subdomain == "SD1"
            assert next(d for d in m.deps if d.id == "D1").bucket == "Data & storage"


def test_reconcile_drop_edges_removes_edge_and_heals_riding_step():
    # B1: the C→E edge `_derive_entity_edges` creates from the flow step must be dropped AFTER derivation
    # (not silently re-derived), and its riding step healed so a re-assemble stays stable.
    rec = {"drop_edges": [{"src": "C1", "verb": "reads", "dst": "E1", "drop_steps": True}]}
    with tempfile.TemporaryDirectory() as td:
        for _ in range(2):
            proc, out = _assemble_with_reconcile(td, rec)
            assert proc.returncode == 0, proc.stderr
            m = load_model((out / "project-map.json").read_text(encoding="utf-8"))
            assert not any(e.src == "C1" and e.dst == "E1" for e in m.edges)   # not re-derived
            steps = [s for f in m.flows for s in f.steps]
            assert not any(s.src == "C1" and s.dst == "E1" for s in steps)     # riding step healed


def test_reconcile_rejects_unknown_id_and_wrong_kind_and_bad_parent():
    with tempfile.TemporaryDirectory() as td:
        proc, out = _assemble_with_reconcile(td, {"set": [{"ids": ["C999"], "subsystem": "S1"}]})
        assert proc.returncode == 1 and "unknown id 'C999'" in proc.stderr
        assert not out.exists()                 # nothing written on a bad directive
        proc2, _ = _assemble_with_reconcile(td, {"set": [{"ids": ["E1"], "subsystem": "S1"}]})
        assert proc2.returncode == 1 and "can only be set on a component" in proc2.stderr
        proc3, _ = _assemble_with_reconcile(td, {"set": [{"ids": ["C1"], "subsystem": "SD1"}]})
        assert proc3.returncode == 1 and "is not a subsystem" in proc3.stderr
        proc4, _ = _assemble_with_reconcile(td, {"set": [{"ids": ["C1"], "runs_in": ["ghost"]}]})
        assert proc4.returncode == 1 and "unknown deployment unit" in proc4.stderr


def test_reconcile_zero_match_drop_edges_warns_but_does_not_fail():
    rec = {"drop_edges": [{"src": "C1", "verb": "calls", "dst": "C2"}]}   # no such edge
    with tempfile.TemporaryDirectory() as td:
        proc, out = _assemble_with_reconcile(td, rec)
        assert proc.returncode == 0, proc.stderr        # a stale directive warns, never fails
        assert "matched 0 edges" in proc.stderr
        assert (out / "project-map.json").exists()


def test_reconcile_reports_counts_in_the_summary():
    rec = {"set": [{"ids": ["C1", "C2"], "subsystem": "S1"}]}
    with tempfile.TemporaryDirectory() as td:
        proc, _ = _assemble_with_reconcile(td, rec)
        assert proc.returncode == 0, proc.stderr
        assert "reconcile applied" in proc.stdout and "subsystem: 2" in proc.stdout
        assert "reconcile set subsystem:2" in proc.stdout        # the self-describing digest (WS-T2)


def test_assemble_notes_present_but_unpassed_reconcile_file():
    # S8: a reconcile file present in the out dir but not passed silently reverts assignments — nudge.
    with tempfile.TemporaryDirectory() as td:
        frag = Path(td) / "frag.json"
        frag.write_text(make_reconcile_fragment(), encoding="utf-8")
        out = Path(td) / "map"
        out.mkdir()
        (out / "reconcile.json").write_text('{"set": []}', encoding="utf-8")
        proc = subprocess.run(ASSEMBLE + [str(frag), "--out", str(out)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert "exists but --reconcile was not passed" in proc.stderr


def test_load_reconcile_rejects_malformed_directives():
    from coyodex.reconcile import ReconcileError, load_reconcile
    for bad, needle in (('{"bogus": []}', "unknown top-level key"),
                        ('{"set": [{"subsystem": "S1"}]}', "missing 'ids'"),
                        ('{"set": [{"ids": ["C1"]}]}', "assigns no field"),
                        ('{"drop_edges": [{"src": "C1", "verb": "x", "dst": "C2", '
                         '"drop_steps": true, "repoint": "C3"}]}', "mutually exclusive")):
        try:
            load_reconcile(bad, "reconcile.json")
            raise AssertionError(f"expected ReconcileError for {bad}")
        except ReconcileError as e:
            assert needle in str(e), str(e)


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


def test_grounding_survives_assemble():
    """The Phase-4 coverage record must reach the committed model.

    `grounding` is written as its own fragment by the Phase-4 reconcile. Left out of the singleton
    merge it was silently DROPPED by the only code path that writes a map, so `validate` then
    reported a fully-grounded map as never challenged — and a re-assemble wiped any hand-edit."""
    from coyodex.model import Grounding, ProjectModel
    frag = ProjectModel(grounding=Grounding(claims_total=150, claims_challenged=40,
                                            claims_refuted=7, note="security first"))
    merged, problems = merge_fragments([("verify.json", frag)])
    assert problems == []
    assert merged.grounding is not None
    assert merged.grounding.claims_total == 150
    assert merged.grounding.claims_challenged == 40
    assert merged.grounding.note == "security first"


def test_conflicting_grounding_records_are_reported():
    from coyodex.model import Grounding, ProjectModel
    a = ProjectModel(grounding=Grounding(claims_total=10))
    b = ProjectModel(grounding=Grounding(claims_total=99))
    _, problems = merge_fragments([("a.json", a), ("b.json", b)])
    assert any("grounding" in p for p in problems)


def test_two_agents_writing_the_same_channel_merge_instead_of_failing_the_build():
    """The live failure: two trace prompts embedded the SAME literal example messaging row, both agents
    wrote it, and `assemble` failed the whole build on `Duplicate messaging channel name(s)`. The lead
    hand-scripted the merge and DROPPED three real publishers, because a hand merge picks a survivor
    where a union keeps what both agents actually found."""
    a = ('{"messaging":[{"name":"jobs","broker":"D1","publishers":["C6","C21"],'
         '"consumers":["C96"],"source":"q.py:1"}]}')
    b = '{"messaging":[{"name":"jobs","publishers":["C45"],"consumers":["C45"],"kind":"job-queue"}]}'
    stats: dict[str, int] = {}
    m, problems = merge_fragments([("a.json", load_fragment(a, "a.json")),
                                   ("b.json", load_fragment(b, "b.json"))], stats)
    assert problems == []                              # no CONFLICT: the second row states no broker
    assert len(m.messaging) == 1
    row = m.messaging[0]
    assert row.publishers == ["C6", "C21", "C45"]      # nothing dropped — the hand merge lost these
    assert row.consumers == ["C96", "C45"]
    assert row.broker == "D1" and row.kind == "job-queue"   # each empty field filled from the sibling
    assert stats["messaging_rows_collapsed"] == 1


def test_two_channels_that_merely_share_a_name_are_NOT_collapsed():
    """Identity is `(name, broker)`, not the name alone. Two rows named `jobs` on brokers `D1` and `D9`
    are two channels, and collapsing them would resolve a real conflict by fragment-filename order.
    They stay separate — and `validate` then blocks on the duplicate name, which is correct: the author
    has to rename one."""
    a = '{"messaging":[{"name":"jobs","broker":"D1","publishers":["C1"],"consumers":["C2"]}]}'
    b = '{"messaging":[{"name":"jobs","broker":"D9","publishers":["C3"],"consumers":["C4"]}]}'
    stats: dict[str, int] = {}
    m, _ = merge_fragments([("a.json", load_fragment(a, "a.json")),
                            ("b.json", load_fragment(b, "b.json"))], stats)
    assert len(m.messaging) == 2, [r.broker for r in m.messaging]
    assert stats.get("messaging_rows_collapsed", 0) == 0


def test_a_conflicting_scalar_is_reported_not_guessed():
    """Filling an EMPTY field from a sibling row is a merge; choosing between two different non-empty
    values is a guess decided by filename order. `merge_fragments` already blocks on a singleton stated
    twice with different values; this follows that precedent."""
    a = '{"messaging":[{"name":"jobs","publishers":["C1"],"consumers":["C2"],"payload":"E1"}]}'
    b = '{"messaging":[{"name":"jobs","publishers":["C3"],"consumers":["C4"],"payload":"E9"}]}'
    m, problems = merge_fragments([("a.json", load_fragment(a, "a.json")),
                                   ("b.json", load_fragment(b, "b.json"))], {})
    assert any("different `payload` values" in p for p in problems), problems
    assert m.messaging[0].publishers == ["C1", "C3"]      # participants still union


def test_merging_does_not_mutate_the_input_fragments():
    """`merge_fragments` extends the FRAGMENTS' own lists into the output, so writing through a
    survivor row would edit the caller's objects — and a second merge of the same parts would then
    produce a different map. `_derive_entity_edges` advertises idempotency as a property of this
    module; the merge must not break it."""
    a = '{"messaging":[{"name":"jobs","broker":"D1","publishers":["C1"],"consumers":["C2"]}]}'
    b = '{"messaging":[{"name":"jobs","publishers":["C3"],"consumers":["C4"]}]}'
    parts = [("a.json", load_fragment(a, "a.json")), ("b.json", load_fragment(b, "b.json"))]
    first, _ = merge_fragments(parts, {})
    pubs_first = list(first.messaging[0].publishers)
    assert parts[0][1].messaging[0].publishers == ["C1"], "the input fragment was mutated"
    second, _ = merge_fragments(parts, {})
    assert second.messaging[0].publishers == pubs_first


# --- the fragment-reading loop (`load_fragment_paths`) --------------------------------------------
#
# Extracted from `main()` so `reconcile` reads fragments through the same code. It had NO coverage:
# no test for a missing path, a malformed fragment, an unreadable path, or the verdicts skip — the
# whole error half of the tool's only write path. An independent review flagged that "945 passed"
# said nothing about the loop that moved.


def make_fragment_file(dir_path: Path, name: str, body: dict) -> Path:
    p = dir_path / name
    p.write_text(json.dumps(body), encoding="utf-8")
    return p


def test_every_path_is_attempted_so_one_bad_fragment_does_not_hide_the_next():
    from coyodex.assemble import load_fragment_paths
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        good = make_fragment_file(d, "good.json", {"components": [
            {"id": "C1", "name": "A", "source": "a.py:1"}]})
        broken = d / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        a_dir = d / "adir.json"
        a_dir.mkdir()
        missing = d / "missing.json"
        parts, _notes, errors = load_fragment_paths([broken, a_dir, missing, good])
        # the good one still loaded, and all three failures are reported — not just the first
        assert [label for label, _ in parts] == ["good.json"]
        assert len(errors) == 3, errors
        assert any("broken.json" in e for e in errors)
        assert any("adir.json" in e and "cannot read" in e for e in errors)
        assert any("missing.json" in e and "not found" in e for e in errors)


def test_a_verdicts_file_swept_into_the_glob_is_skipped_with_a_note():
    # was: `_is_verdicts_file` keyed on "shares no ProjectModel field", but `grounding` IS one, so
    # it was unconditionally False — the skip never fired and the build died on a schema error.
    from coyodex.assemble import load_fragment_paths
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        good = make_fragment_file(d, "good.json", {"components": [
            {"id": "C1", "name": "A", "source": "a.py:1"}]})
        verdicts = make_fragment_file(d, "verdicts-security.json", {"grounding": [
            {"claim": "C1 calls C2", "grounded": False, "evidence": "a.py:1"}]})
        parts, notes, errors = load_fragment_paths([verdicts, good])
        assert errors == []
        assert [label for label, _ in parts] == ["good.json"]
        assert len(notes) == 1 and "verdicts-security.json" in notes[0]


def test_the_grounding_fragment_is_NOT_mistaken_for_a_verdicts_file():
    # `grounding write` emits {"grounding": {record}} into build-fragments/ — an object, not a list.
    # Skipping it would silently drop the map's grounding record.
    from coyodex.assemble import load_fragment_paths
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        frag = make_fragment_file(d, "grounding.json", {"grounding": {
            "claims_total": 10, "claims_challenged": 10, "claims_confirmed": 9,
            "claims_refuted": 1, "claims_unverifiable": 0}})
        parts, notes, errors = load_fragment_paths([frag])
        assert errors == [] and notes == []
        assert [label for label, _ in parts] == ["grounding.json"]
        assert parts[0][1].grounding.claims_total == 10


def test_assemble_fails_the_build_and_writes_nothing_when_a_fragment_is_bad():
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        make_fragment_file(d, "good.json", {"components": [
            {"id": "C1", "name": "A", "source": "a.py:1"}]})
        (d / "broken.json").write_text("{not json", encoding="utf-8")
        out = d / "out"
        r = subprocess.run([*ASSEMBLE, str(d / "broken.json"), str(d / "good.json"),
                            "--out", str(out)], capture_output=True, text=True)
        assert r.returncode == 1
        assert "ASSEMBLY FAILED" in r.stderr
        assert not (out / "project-map.json").exists()


def test_a_draft_fragment_is_skipped_by_name():
    """The harvest contract promised the `.draft.json` suffix "keeps a half-written file out of the
    assemble glob". It did not: `*.draft.json` matches `*.json` and nothing looked at the name."""
    from coyodex.assemble import load_fragment_paths
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        good = make_fragment_file(d, "h-a.json", {"components": [
            {"id": "C1", "name": "A", "source": "a.py:1"}]})
        draft = d / "h-b.json.draft.json"
        draft.write_text('{"components": [{"id": "C2", "name":', encoding="utf-8")  # truncated
        parts, notes, errors = load_fragment_paths([draft, good])
        assert errors == []
        assert [label for label, _ in parts] == ["h-a.json"]
        assert len(notes) == 1 and "draft" in notes[0]


# ── one section per heading ──────────────────────────────────────────────────────────────────────

def make_extras_fragment(name: str, heading: str, body: str) -> "tuple[str, ProjectModel]":
    from coyodex.model import ExtraSection, ProjectModel
    m = ProjectModel(title="T", goal="g")
    m.extras.append(ExtraSection(heading=heading, body=body))
    return (name, m)


def test_same_named_extras_sections_are_merged_into_one():
    """A live map shipped five `Entry-point coverage` sections, three `Balance exceptions` and two
    `Coverage exceptions` — one per contributing fragment, simply concatenated."""
    from coyodex.assemble import merge_fragments
    out, problems = merge_fragments([
        make_extras_fragment("a.json", "Entry-point coverage", "- first"),
        make_extras_fragment("b.json", "Entry-point coverage", "- second"),
        make_extras_fragment("c.json", "Balance exceptions", "- other"),
    ])
    headings = [e.heading for e in out.extras]
    assert headings.count("Entry-point coverage") == 1, headings
    body = next(e.body for e in out.extras if e.heading == "Entry-point coverage")
    assert "- first" in body and "- second" in body, "no recorded line may be dropped"
    assert not problems


def test_merging_headings_makes_record_replace_reach_every_line():
    """The write path this actually fixes: `record.append_line` resolves a heading with the FIRST
    matching section, so with the sections split a `--replace` aimed at a line in a later one
    matched nothing and reported "nothing replaced"."""
    from coyodex.assemble import merge_fragments
    from coyodex.record import append_line
    out, _ = merge_fragments([
        make_extras_fragment("a.json", "Balance exceptions", "- alpha: original why"),
        make_extras_fragment("b.json", "Balance exceptions", "- beta: original why"),
    ])
    # the prefix is matched AFTER the bullet is stripped, so it carries no "- "
    changed, message = append_line(out, "Balance exceptions", "- beta: corrected why",
                                   replace_prefix="beta:")
    assert changed, message
    body = next(e.body for e in out.extras if e.heading == "Balance exceptions")
    assert "corrected why" in body and "beta: original why" not in body


def test_a_heading_written_in_another_case_is_the_same_section():
    """Matching reuses `record._resolve_heading` rather than a third implementation, so it is
    case- and outer-space-tolerant (it does NOT normalise interior spacing — that would silently
    accept a heading no check reads)."""
    from coyodex.assemble import merge_fragments
    out, _ = merge_fragments([
        make_extras_fragment("a.json", "Coverage exceptions", "- one"),
        make_extras_fragment("b.json", "  coverage exceptions  ", "- two"),
    ])
    covers = [e for e in out.extras if e.heading.strip().lower() == "coverage exceptions"]
    assert len(covers) == 1, [e.heading for e in out.extras]
    assert covers[0].heading == "Coverage exceptions", "the canonical spelling wins"
    assert "- one" in covers[0].body and "- two" in covers[0].body


def test_the_keep_edges_count_reaches_the_assemble_digest():
    """H1 shipped with no test: `keep_edges` removed 51 edges on a real map and the digest said
    nothing, reproducing the exact silence the directive was added to stop."""
    from coyodex.assemble import _assemble_digest
    from coyodex.model import ProjectModel
    line = _assemble_digest(ProjectModel(title="T", goal="g"), {},
                            {"duplicate_edges_resolved": 51})
    assert "keep_edges 51" in line, line
    # and zero-suppressed like every other op
    assert "keep_edges" not in _assemble_digest(ProjectModel(title="T", goal="g"), {}, {})


def test_assemble_accepts_a_bare_fragment_directory():
    """A directory is what an operator types first, and `assemble` — printed far more often in
    method.md than `reconcile` — died on the reader's raw `[Errno 21] Is a directory`. The expansion
    lives in the shared loader, so both commands agree on what an argument means."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "frags"
        d.mkdir()
        (d / "a.json").write_text(json.dumps({
            "components": [{"id": "C1", "name": "A", "purpose": "p", "source": "a.py:1"}]}),
            encoding="utf-8")
        (d / "b.json").write_text(json.dumps({
            "components": [{"id": "C2", "name": "B", "purpose": "p", "source": "b.py:1"}]}),
            encoding="utf-8")
        by_dir, notes, errors = load_fragment_paths([d])
        by_glob, _n, _e = load_fragment_paths(sorted(d.glob("*.json")))
        assert not errors, errors
        assert [name for name, _ in by_dir] == [name for name, _ in by_glob] == ["a.json", "b.json"]
        assert any("expanded to 2 fragment(s)" in n for n in notes), notes


def test_a_directory_named_json_still_raises_from_assemble():
    """`inner.json/` swept up by the caller's own glob must keep erroring: silently dropping it
    would make the glob form and the bare-directory form disagree about the file set while both
    exit 0."""
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "frags"
        d.mkdir()
        (d / "a.json").write_text(json.dumps({"components": []}), encoding="utf-8")
        (d / "inner.json").mkdir()
        _parts, _notes, errors = load_fragment_paths(sorted(d.glob("*.json")))
        assert any("Is a directory" in e for e in errors), errors


# ── entry-point ids: minted by assemble, never authored (Step 1 of plan/60-capabilities) ──────────

def make_entry_point_slice(cid: str, own_route: str) -> str:
    """One harvest slice. Every slice records the SHARED `/health` route it happened to walk past,
    plus one route of its own — the duplicate-surface case that nothing collapsed before, because
    entry points were the one element family assemble simply concatenated."""
    return json.dumps({
        "components": [{"id": cid, "name": cid, "purpose": "p", "source": f"{cid}.py:1"}],
        "entry_points": [
            {"kind": "HTTP route", "trigger": "GET /health", "source": "app/health.py:10",
             "component": cid, "activation": "external"},
            {"kind": "HTTP route", "trigger": f"GET {own_route}", "source": f"{cid}.py:5",
             "component": cid, "activation": "external"},
        ],
    })


def test_entry_point_ids_are_minted_and_duplicate_surfaces_collapse():
    """Ids are assigned by assemble from content, and the same surface harvested twice becomes ONE
    row — otherwise the completeness check would count a duplicated route as two unclaimed surfaces."""
    with tempfile.TemporaryDirectory() as td:
        a, b = Path(td) / "a.json", Path(td) / "b.json"
        a.write_text(make_entry_point_slice("C1", "/orders"), encoding="utf-8")
        b.write_text(make_entry_point_slice("C2", "/users"), encoding="utf-8")
        out = Path(td) / "map"
        proc = subprocess.run(ASSEMBLE + [str(a), str(b), "--out", str(out)],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        m = load_model((out / "project-map.json").read_text(encoding="utf-8"))
        triggers = [ep.trigger for ep in m.entry_points]
        assert triggers.count("GET /health") == 1, triggers      # collapsed, not concatenated
        assert [ep.id for ep in m.entry_points] == ["EP1", "EP2", "EP3"], triggers
        assert all(ep.id for ep in m.entry_points)


def test_entry_points_without_a_source_are_never_merged():
    """No anchor → not identifiable. Merging on trigger text alone would delete a real surface, so
    an unanchored row keeps its own id (the same rule `_dep_identity` uses for a nameless dep)."""
    with tempfile.TemporaryDirectory() as td:
        frag = Path(td) / "f.json"
        frag.write_text(json.dumps({
            "components": [{"id": "C1", "name": "A", "purpose": "p", "source": "a.py:1"}],
            "entry_points": [{"kind": "CLI", "trigger": "run", "component": "C1"},
                             {"kind": "CLI", "trigger": "run", "component": "C1"}],
        }), encoding="utf-8")
        out = Path(td) / "map"
        proc = subprocess.run(ASSEMBLE + [str(frag), "--out", str(out)],
                             capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        m = load_model((out / "project-map.json").read_text(encoding="utf-8"))
        assert [ep.id for ep in m.entry_points] == ["EP1", "EP2"]


def make_capability_fragment() -> str:
    """A behavioral fragment plus the T4 rows a synthesis-time reconcile will link it to."""
    return json.dumps({
        "title": "Demo", "goal": "g",
        "capabilities": [{"id": "CAP1", "name": "Ordering", "label": "core"},
                         {"id": "CAP2", "name": "Ops", "label": "platform"}],
        "use_cases": [{"id": "UC1", "name": "Place an order"},
                      {"id": "UC2", "name": "Rotate the keys"}],
        "components": [{"id": "C1", "name": "A", "purpose": "p", "source": "a.py:1"}],
        "entry_points": [{"kind": "HTTP route", "trigger": "POST /orders",
                          "source": "a.py:9", "component": "C1", "activation": "external"}],
    })


def test_reconcile_sets_capability_and_entry_points_and_survives_reassemble():
    """The authoring path for both new fields. Neither can be written in the behavioral fragment:
    `CAPn` is assigned at synthesis and `EPn` does not exist until assemble mints it, so reconcile
    is the only mechanism — and it must re-apply on every assemble, like the other set fields."""
    rec = {"set": [{"ids": ["UC1"], "capability": "CAP1", "entry_points": ["EP1"]},
                   {"ids": ["UC2"], "capability": "CAP2"}]}
    with tempfile.TemporaryDirectory() as td:
        frag = Path(td) / "frag.json"
        frag.write_text(make_capability_fragment(), encoding="utf-8")
        rp = Path(td) / "reconcile.json"
        rp.write_text(json.dumps(rec), encoding="utf-8")
        out = Path(td) / "map"
        for _ in range(2):                       # re-assemble: the assignment must not wash out
            proc = subprocess.run(ASSEMBLE + [str(frag), "--out", str(out), "--reconcile", str(rp)],
                                  capture_output=True, text=True)
            assert proc.returncode == 0, proc.stderr
            m = load_model((out / "project-map.json").read_text(encoding="utf-8"))
            by_id = {u.id: u for u in m.use_cases}
            assert by_id["UC1"].capability == "CAP1"
            assert by_id["UC1"].entry_points == ["EP1"]
            assert by_id["UC2"].capability == "CAP2"
            assert by_id["UC2"].entry_points == []


def test_reconcile_rejects_an_unknown_capability_or_entry_point():
    """A typo must fail loudly at apply time. The EP case is the one that bites: ids are minted
    from fragment order, so a stale reconcile file silently pointing at the wrong surface would
    otherwise mis-claim a front door."""
    with tempfile.TemporaryDirectory() as td:
        frag = Path(td) / "frag.json"
        frag.write_text(make_capability_fragment(), encoding="utf-8")
        out = Path(td) / "map"
        for bad, needle in (({"ids": ["UC1"], "capability": "CAP9"}, "not a defined capability"),
                            ({"ids": ["UC1"], "entry_points": ["EP7"]}, "unknown entry point")):
            rp = Path(td) / "reconcile.json"
            rp.write_text(json.dumps({"set": [bad]}), encoding="utf-8")
            proc = subprocess.run(ASSEMBLE + [str(frag), "--out", str(out), "--reconcile", str(rp)],
                                  capture_output=True, text=True)
            assert proc.returncode != 0, proc.stdout
            assert needle in (proc.stdout + proc.stderr), proc.stdout + proc.stderr


def test_reconcile_refuses_capability_on_a_non_use_case():
    """`capability` targets a use case, exactly as `subsystem` targets a component."""
    with tempfile.TemporaryDirectory() as td:
        frag = Path(td) / "frag.json"
        frag.write_text(make_capability_fragment(), encoding="utf-8")
        rp = Path(td) / "reconcile.json"
        rp.write_text(json.dumps({"set": [{"ids": ["C1"], "capability": "CAP1"}]}), encoding="utf-8")
        out = Path(td) / "map"
        proc = subprocess.run(ASSEMBLE + [str(frag), "--out", str(out), "--reconcile", str(rp)],
                              capture_output=True, text=True)
        assert proc.returncode != 0, proc.stdout
        assert "can only be set on a use case" in (proc.stdout + proc.stderr)
