#!/usr/bin/env python3
"""Tests for the operative-line anchor check — the deterministic half of Phase-4 anchor grounding.

`--check-sources` only ever proved an anchor RESOLVES. Nothing proved the line could be the
statement the anchor claims fires there, so a `def`-header anchor passed every gate. On a live
self-map 70 of ~150 backbone anchors (47%) sat on a definition header — 4 of its 6 security anchors
included — with all gates green.

Run either way (needs an editable install: `make deps`):
    python3 tests/test_operative_lines.py
    pytest tests/test_operative_lines.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from coyodex.anchors import non_operative_reason
from coyodex.model import (
    Edge,
    Flow,
    FlowStep,
    ProjectModel,
    SecurityRow,
)
from coyodex.validate_model import call_site_anchors, check_operative_lines_model


def make_repo(files: dict[str, str], tmp: str) -> Path:
    """Write `{relative path: contents}` under a temp root and return it."""
    root = Path(tmp)
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def make_edge_model(where: str, verb: str = "calls") -> ProjectModel:
    return ProjectModel(edges=[Edge(src="C1", verb=verb, dst="C2", where=where)])


# --------------------------------------------------------------------------------------
# the line classifier
# --------------------------------------------------------------------------------------

def test_definition_headers_and_noise_are_not_operative():
    assert non_operative_reason("def handle(req):") == "a Python function header"
    assert non_operative_reason("    async def handle(req):") == "a Python function header"
    assert non_operative_reason("class Repo(Base):") == "a class header"
    assert non_operative_reason("func main() {") == "a Go function header"
    assert non_operative_reason("pub async fn run() {") == "a Rust function header"
    assert non_operative_reason("export default function App() {") == "a function header"
    assert non_operative_reason("from x import y") == "an import line"
    assert non_operative_reason("import os") == "an import line"
    assert non_operative_reason("const fs = require('fs')") == "an import line"
    assert non_operative_reason("# a comment") == "a comment"
    assert non_operative_reason("// a comment") == "a comment"
    assert non_operative_reason('"""docstring') == "a docstring delimiter"
    assert non_operative_reason("   ") == "a blank line"


def test_real_statements_are_operative():
    # the shapes that DO act — none of these may be flagged, or the check becomes noise.
    for line in ('    self.db.save(org)',
                 '    if not user.is_admin: raise Forbidden()',
                 '@app.post("/orgs")',                    # a decorator IS a legitimate route site
                 '    return client.get(url)',
                 '    repo.upsert({"_id": org.id})',
                 '}',
                 '#!/usr/bin/env python3'):
        assert non_operative_reason(line) is None, line


# --------------------------------------------------------------------------------------
# which anchors the check covers
# --------------------------------------------------------------------------------------

def test_only_call_site_anchors_are_collected():
    m = ProjectModel(
        edges=[Edge(src="C1", verb="calls", dst="C2", where="a.py:2")],
        flows=[Flow(uc="UC1", title="t", steps=[FlowStep(n=1, src="C1", dst="C2",
                                                         phrase="p", where="a.py:3")])],
        security=[SecurityRow(surface="s", who="w", source="a.py:4")],
    )
    labels = [lbl for lbl, _ in call_site_anchors(m)]
    assert any("edge" in lbl for lbl in labels)
    assert any("flow step" in lbl for lbl in labels)
    assert any("security" in lbl for lbl in labels)
    assert len(labels) == 3


def test_extends_and_implements_anchor_their_class_header_legitimately():
    # `class Sub(Base):` IS the operative statement for an inheritance edge — flagging it would
    # fire on every correctly-anchored `extends` row in a plugin-heavy repo (19 on a live map).
    for verb in ("extends", "implements"):
        m = make_edge_model("a.py:1", verb=verb)
        assert call_site_anchors(m) == []


def test_definition_source_anchors_are_not_call_sites():
    # a component/entity `source` is SUPPOSED to point at a definition — it makes no "acts here"
    # claim, so the check must not reach it.
    from coyodex.model import Component, Entity
    m = ProjectModel(components=[Component(id="C1", name="A", purpose="p", source="a.py:1")],
                     entities=[Entity(id="E1", name="Org", meaning="m", source="a.py:1")])
    assert call_site_anchors(m) == []


# --------------------------------------------------------------------------------------
# the check end to end
# --------------------------------------------------------------------------------------

def test_flags_a_def_header_anchor():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo({"a.py": "import os\ndef handle():\n    db.save(x)\n"}, tmp)
        out = check_operative_lines_model(make_edge_model("a.py:2"), [root])
        assert len(out) == 1
        assert "a Python function header" in out[0]
        assert "no_call_site" in out[0]                     # names the escape hatch


def test_accepts_the_operative_line():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo({"a.py": "import os\ndef handle():\n    db.save(x)\n"}, tmp)
        assert check_operative_lines_model(make_edge_model("a.py:3"), [root]) == []


def test_flags_a_drifted_security_anchor():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo({"g.py": "def require_admin(u):\n    if not u.admin:\n        raise E\n"}, tmp)
        m = ProjectModel(security=[SecurityRow(surface="admin", who="staff", source="g.py:1")])
        out = check_operative_lines_model(m, [root])
        assert len(out) == 1 and "security 'admin'" in out[0]


def test_prose_files_are_skipped():
    # a leading `#` in markdown is a heading, not a comment — "operative statement" has no meaning.
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo({"doc.md": "# Title\ntext\n"}, tmp)
        assert check_operative_lines_model(make_edge_model("doc.md:1"), [root]) == []


def test_whole_file_and_missing_anchors_are_ignored():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo({"a.py": "def f():\n    pass\n"}, tmp)
        assert check_operative_lines_model(make_edge_model("a.py"), [root]) == []      # no line
        assert check_operative_lines_model(make_edge_model("gone.py:1"), [root]) == []  # existence
        assert check_operative_lines_model(make_edge_model("a.py:999"), [root]) == []  # past EOF


def test_check_is_advisory_not_blocking():
    # the relationship is usually REAL and only its `where` drifted, so a hit must never fail a
    # build: it lands in warnings, and `validate` still exits 0.
    from coyodex.validate_model import validate_model
    with tempfile.TemporaryDirectory() as tmp:
        root = make_repo({"a.py": "def handle():\n    pass\n"}, tmp)
        m = make_edge_model("a.py:1")
        problems, warnings = validate_model(m, repo_root=root, check_sources=True)[:2]
        assert not any("points at" in p for p in problems)
        assert any("points at" in w for w in warnings)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))


def test_attribute_syntax_is_not_a_comment():
    # `#[...]` is Rust/PHP's decorator, the exact analog of `@app.post(...)` — which this check
    # deliberately accepts. A live map flagged a real Rust route site (`#[tokio::main]`) as "a
    # comment" before this carve-out.
    for line in ("#[tokio::main]", '#[get("/users")]', "#[Route('/x')]",
                 "#include <stdio.h>", "#define MAX 10", "#pragma once"):
        assert non_operative_reason(line) is None, line
    assert non_operative_reason("# an ordinary comment") == "a comment"
    assert non_operative_reason("#!/usr/bin/env python3") is None
