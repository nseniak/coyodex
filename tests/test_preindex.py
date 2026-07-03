#!/usr/bin/env python3
"""Tests for the structural pre-index (coyodex.preindex + coyodex.preindex_lib).

Stdlib-only — no pytest required. Run either way (needs an editable install: `make deps`):
    python3 tests/test_preindex.py
    pytest tests/test_preindex.py

Non-Python symbol tests are gated on the tree-sitter grammar pack being installed
(the `preindex` extra); they assert graceful self-reported coverage (GR3) when it is absent.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from coyodex import preindex, preindex_lib, validate_analysis  # tool #4: compression-coverage check
from coyodex.validate_analysis import _REF_INLINE, _REF_LINK, strip_anchor


# --- builders -------------------------------------------------------------------
def refs_from_markdown(text: str, root: Path) -> set[str]:
    """Repo-relative paths (files AND dirs) a markdown snippet points at — markdown link targets +
    inline paths, kept only when they actually exist under root. Mirrors what the retired v1 map
    reader used to hand `check_compression_coverage`; `compression_coverage_from_refs` is the real
    (kept) entry point, so tests build the ref set directly instead of parsing markdown for it."""
    cands: set[str] = set(_REF_LINK.findall(text)) | set(_REF_INLINE.findall(text))
    rootstr = str(root)
    refs: set[str] = set()
    for c in cands:
        c = strip_anchor(c.strip())
        if c.startswith("file://"):
            c = c[7:]
        if c.startswith(rootstr):
            c = c[len(rootstr):]
        c = c.strip("/")
        if c and not c.startswith(".coyodex") and (root / c).exists():
            refs.add(c)
    return refs


def check_compression_coverage(text: str, root: Path) -> list[str]:
    root = root.resolve()
    return validate_analysis.compression_coverage_from_refs(refs_from_markdown(text, root), root)



def make_temp_repo(files: dict[str, str], git: bool = True) -> Path:
    """Write a throwaway tree; optionally make it a git repo with one commit."""
    root = Path(tempfile.mkdtemp(prefix="coyodex_preindex_"))
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    if git:
        env = ["-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(root), *env, "commit", "-q", "-m", "init"], check=True)
    return root


def find_node(tree: dict, path: str) -> dict | None:
    """Locate a directory node by its repo-relative path in the weight tree."""
    if tree["path"] == path:
        return tree
    for child in tree["children"]:
        hit = find_node(child, path)
        if hit is not None:
            return hit
    return None


def weight_of(root: Path, git: bool = False):
    walk = preindex_lib.iter_source_files(root)
    churn, _ = preindex_lib.git_churn(root, None) if git else ({}, False)
    return preindex.build_weight(walk.files, root, churn, None)


# --- tool #1: weight + churn ----------------------------------------------------
def test_weight_counts_loc_and_files() -> None:
    root = make_temp_repo({"a.py": "x\ny\nz\n", "sub/b.py": "1\n2\n"}, git=False)
    tree, langs = weight_of(root)
    assert tree["loc"] == 5, tree["loc"]
    assert tree["file_count"] == 2, tree["file_count"]
    sub = find_node(tree, "sub")
    assert sub is not None and sub["loc"] == 2, sub
    assert langs.get("python") == 2, langs


def test_weight_excludes_vendored_and_lockfiles() -> None:
    root = make_temp_repo({
        "app.py": "a\n",
        "node_modules/dep/index.js": "junk\n" * 100,
        "package-lock.json": "{}\n" * 100,
    }, git=False)
    tree, _ = weight_of(root)
    assert tree["file_count"] == 1, tree["file_count"]  # only app.py
    assert find_node(tree, "node_modules") is None


def test_weight_churn_unavailable_without_git() -> None:
    root = make_temp_repo({"a.py": "x\n"}, git=False)
    churn, ok = preindex_lib.git_churn(root, None)
    assert ok is False and churn == {}, (ok, churn)


def test_weight_collapsed_plugins_are_visible() -> None:
    """The MEE6 regression in miniature: a plugins/ dir with 8 sibling subunits must show
    as 8 children with real LOC — the mass the collapsed map hid."""
    files = {f"plugins/p{i}/feature.py": f"# plugin {i}\n" + "line\n" * (i + 2)
             for i in range(8)}
    root = make_temp_repo(files, git=False)
    tree, _ = weight_of(root)
    plugins = find_node(tree, "plugins")
    assert plugins is not None, "plugins node missing"
    assert len(plugins["children"]) == 8, len(plugins["children"])
    assert all(c["loc"] > 0 for c in plugins["children"])


# --- tool #3: symbols -----------------------------------------------------------
def test_symbols_all_matches_for_ambiguous_name() -> None:
    root = make_temp_repo({
        "levels/player.py": "class Player:\n    pass\n",
        "economy/player.py": "class Player:\n    pass\n",
    }, git=False)
    walk = preindex_lib.iter_source_files(root)
    syms, _ = preindex.build_symbols(walk.files, root)
    assert len(syms["by_name"]["Player"]) == 2, syms["by_name"]["Player"]
    assert "Player" in syms["ambiguous"]


def test_symbols_kind_and_line() -> None:
    root = make_temp_repo({"m.py": "def foo():\n    pass\n\nclass Bar:\n    pass\n"}, git=False)
    walk = preindex_lib.iter_source_files(root)
    syms, _ = preindex.build_symbols(walk.files, root)
    foo = syms["by_name"]["foo"][0]
    bar = syms["by_name"]["Bar"][0]
    assert foo["kind"] == "function" and foo["line"] == 1, foo
    assert bar["kind"] == "class" and bar["line"] == 4, bar


def test_symbols_parse_failure_recorded_not_silent() -> None:
    root = make_temp_repo({"ok.py": "class Ok:\n    pass\n", "broken.py": "def (:\n"}, git=False)
    walk = preindex_lib.iter_source_files(root)
    syms, meta = preindex.build_symbols(walk.files, root)
    assert "Ok" in syms["by_name"]                      # the good file still parsed
    failed = [f["file"] for f in meta["parse_failures"]]
    assert any(f.endswith("broken.py") for f in failed), meta["parse_failures"]


# --- tool #2: import-edge advisory ----------------------------------------------
def test_imports_reports_named_pair_edge() -> None:
    root = make_temp_repo({
        "pkga/mod.py": "from pkgb import thing\n",
        "pkgb/thing.py": "x = 1\n",
    }, git=False)
    pairs = root / "pairs.json"
    pairs.write_text(json.dumps({"CA": ["pkga"], "CB": ["pkgb"]}))
    walk = preindex_lib.iter_source_files(root)
    imps, _ = preindex.build_imports(walk.files, root, str(pairs))
    edges = [p for p in imps["pairs"] if p["from"] == "CA" and p["to"] == "CB"]
    assert edges and edges[0]["count"] >= 1, imps["pairs"]


def test_imports_dynamic_not_captured_lower_bound() -> None:
    root = make_temp_repo({
        "pkgc/d.py": "__import__('pkgd')\n",
        "pkgd/x.py": "y = 1\n",
    }, git=False)
    pairs = root / "pairs.json"
    pairs.write_text(json.dumps({"CC": ["pkgc"], "CD": ["pkgd"]}))
    walk = preindex_lib.iter_source_files(root)
    imps, _ = preindex.build_imports(walk.files, root, str(pairs))
    dyn = [p for p in imps["pairs"] if p["from"] == "CC" and p["to"] == "CD"]
    assert not dyn, "dynamic __import__ must NOT surface as a static edge (lower-bound)"


# --- GR3: self-reported coverage ------------------------------------------------
def test_coverage_reports_language_without_symbol_extractor() -> None:
    root = make_temp_repo({"a.py": "x\n", "notes.txt": "hello\n"}, git=False)
    walk = preindex_lib.iter_source_files(root)
    _, meta = preindex.build_symbols(walk.files, root)
    assert "text" in meta["languages_seen_without_extractor"], meta


def test_full_run_emits_coverage_block() -> None:
    root = make_temp_repo({"a.py": "class A:\n    pass\n"}, git=True)
    out = root / ".coyodex" / "preindex.json"
    walk = preindex_lib.iter_source_files(root)
    churn, git_ok = preindex_lib.git_churn(root, None)
    weight, _ = preindex.build_weight(walk.files, root, churn, None)
    symbols, sym_meta = preindex.build_symbols(walk.files, root)
    imports, _ = preindex.build_imports(walk.files, root, None)
    doc = {"weight": weight, "symbols": symbols, "imports": imports,
           "coverage": {"git_available": git_ok,
                        "languages_with_symbols": sym_meta["languages_with_symbols"]}}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc))
    loaded = json.loads(out.read_text())
    assert loaded["coverage"]["git_available"] is True
    assert "python" in loaded["coverage"]["languages_with_symbols"]


# --- non-Python (tree-sitter): present if installed, gracefully absent if not ----
def test_non_python_symbols_present_or_self_reported() -> None:
    root = make_temp_repo({"s.js": "class Foo {}\nfunction bar() {}\n"}, git=False)
    walk = preindex_lib.iter_source_files(root)
    syms, meta = preindex.build_symbols(walk.files, root)
    if preindex_lib.ts_available():
        assert "Foo" in syms["by_name"], "tree-sitter installed but JS symbols missing"
    else:
        # GR3: the gap is recorded (a parse failure for s.js), never a silent empty
        failed = [f["file"] for f in meta["parse_failures"]]
        assert any(f.endswith("s.js") for f in failed), meta["parse_failures"]


# --- tool #4: compression-coverage (validator check, re-measures the tree) -------
def make_plugin_repo(n_plugins: int, n_files_each: int = 2) -> Path:
    files = {"core.py": "x\n"}
    for i in range(n_plugins):
        for j in range(n_files_each):
            files[f"plugins/p{i}/f{j}.py"] = "x\n" * 5
    return make_temp_repo(files, git=False)


def test_compression_flags_collapsed_plugins() -> None:
    root = make_plugin_repo(12)
    collapsed = "| **C1** | Plugins | S1 | all ~12 plugins as one box | [plugins/](plugins/) | |\n"
    ws = check_compression_coverage(collapsed, root)
    comp = [w for w in ws if w.startswith("Compression") and "plugins/ holds" in w]
    assert comp, ws
    assert "12 subdirs, measured at validate time" in comp[0], comp[0]  # self-reported denominator


def test_compression_quiet_when_plugins_drilled() -> None:
    root = make_plugin_repo(12)
    drilled = "\n".join(
        f"| **C{i}** | P{i} | S1 | one plugin | [f](plugins/p{i}/f0.py) | |" for i in range(12)
    )
    ws = check_compression_coverage(drilled, root)
    plug = [w for w in ws if "plugins/ holds" in w]
    assert not plug, f"drilled plugins must not warn (GR6 — abstraction is a feature): {plug}"


def test_compression_is_advisory_only_returns_list() -> None:
    # never raises, never blocks — it returns warnings the validator appends to `warnings` (GR6).
    root = make_temp_repo({"a.py": "x\n"}, git=False)
    assert isinstance(check_compression_coverage("", root), list)


def test_validator_does_not_read_preindex_json_gr4() -> None:
    """GR4 tripwire: a poisoned preindex.json present in the tree must NOT change the check's output —
    the validator re-measures and never consumes the generated artifact."""
    root = make_plugin_repo(12)
    collapsed = "| **C1** | Plugins | S1 | one box | [plugins/](plugins/) | |\n"
    before = check_compression_coverage(collapsed, root)
    (root / ".coyodex").mkdir(exist_ok=True)
    (root / ".coyodex" / "preindex.json").write_text(
        json.dumps({"weight": {"path": ".", "children": []}, "LIE": "plugins fully drilled"})
    )
    after = check_compression_coverage(collapsed, root)
    assert before == after, "validator output changed when preindex.json present — GR4 violated"


def test_imports_no_false_positive_on_substring() -> None:
    """H1 regression: a module that merely shares a substring with a target path must NOT produce an
    edge — a lower-bound advisory has no false edges. `import scoreboard` ≠ a dep on `core/`."""
    root = make_temp_repo({
        "scoreui/view.py": "import scoreboard\n",
        "core/x.py": "y = 1\n",
        "scoreboard/s.py": "z = 1\n",
    }, git=False)
    pairs = root / "pairs.json"
    pairs.write_text(json.dumps({"ScoreUI": ["scoreui"], "Core": ["core"]}))
    walk = preindex_lib.iter_source_files(root)
    imps, _ = preindex.build_imports(walk.files, root, str(pairs))
    bogus = [p for p in imps["pairs"] if p["from"] == "ScoreUI" and p["to"] == "Core"]
    assert not bogus, f"substring 'core' in 'scoreboard' must not fabricate an edge: {bogus}"


def test_compression_flags_monorepo_layout() -> None:
    """M2: a fold one level deeper, under a recognized monorepo container root, is still caught."""
    files = {f"packages/app/plugins/p{i}/f.py": "x\n" * 3 for i in range(10)}
    files["packages/app/main.py"] = "x\n"
    root = make_temp_repo(files, git=False)
    m = "| **C1** | Plugins | S1 | one box | [plugins/](packages/app/plugins/) | |\n"
    ws = check_compression_coverage(m, root)
    assert any("packages/app/plugins/ holds" in w for w in ws), ws


def test_compression_skips_leaf_internals_under_ordinary_package() -> None:
    """GR6: deep subdirs of a single mapped component (NOT under a monorepo root) stay abstracted."""
    files = {f"mee6/plugins/achievements/sub{i}/f.py": "x\n" for i in range(10)}
    files["mee6/plugins/achievements/achievements.py"] = "x\n"
    root = make_temp_repo(files, git=False)
    m = "| **C1** | Achievements | S1 | one plugin | [a](mee6/plugins/achievements/achievements.py) | |\n"
    ws = check_compression_coverage(m, root)
    assert not any("achievements/ holds" in w for w in ws), ws


def test_compression_flags_small_unreferenced_fold() -> None:
    """M3: a small-but-fanned fold the map references nothing inside is still surfaced (not silent)."""
    files = {f"services/s{i}/main.py": "x\n" for i in range(10)}
    files["core/x.py"] = "x\n"
    root = make_temp_repo(files, git=False)
    m = "| **C1** | Core | S1 | x | [c](core/x.py) | |\n"  # references nothing under services/
    ws = check_compression_coverage(m, root)
    assert any("services/" in w and "subdirs" in w for w in ws), ws


def test_compression_skips_non_product_dirs() -> None:
    """Item 7: a conventional non-product tree (tests / internal / docs) the map never references must
    NOT trip the absent-module warning — they have their own completeness section / are deliberately
    unmapped — while a genuine unmapped PRODUCT module still surfaces."""
    files = {"core/x.py": "x\n"}
    for i in range(30):
        files[f"tests/t{i}.py"] = "x\n"       # large unreferenced test tree — must be skipped
        files[f"internal/i{i}.py"] = "x\n"    # deliberately-unmapped internal tree — must be skipped
        files[f"billing/b{i}.py"] = "x\n"     # a real unmapped product module — must still surface
    root = make_temp_repo(files, git=False)
    m = "| **C1** | Core | S1 | x | [c](core/x.py) | |\n"  # references only core/
    ws = check_compression_coverage(m, root)
    assert not any("tests/" in w for w in ws), ws
    assert not any("internal/" in w for w in ws), ws
    assert any("billing/" in w for w in ws), ws


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"ok   {fn.__name__}")
        except Exception as e:  # noqa: BLE001 — test runner reports every failure
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
