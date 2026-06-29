#!/usr/bin/env python3
"""coyodex structural pre-index — sizes and locates the codebase BEFORE the structural harvest.

Emits ``.coyodex/preindex.json`` with four products (see internal/docs/scaling-to-large-codebases.md,
finding G1):

  1. weight  — a directory tree with LOC, file count and git churn (all languages). The signal that
               turns "65 plugins" into "65 plugins = X% of the tree, all alive" -> drill, don't collapse.
  2. symbols — class/function definitions -> file:line + kind, ALL matches (ambiguity surfaced).
  3. imports — for component pairs the agent already NAMED (--pairs), the import edges between them,
               a lower-bound cross-check (absence != no-dependency).
  4. coverage— what the tool could NOT see (GR3): unparsed = unknown, never empty.

This is an ADVISORY INPUT the build agent reconciles (accept/reject/abstract) — never rows copied
into the map verbatim (GR2). Weight is a hint to where to look, never a decision to drill (GR5). The
validator never reads this file; it re-measures (GR4).

Usage:
  python3 tools/preindex.py [--root .] [--out .coyodex/preindex.json] [--since <rev|date>]
                            [--pairs pairs.json] [--max-depth N]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from preindex_lib import (
    SYMBOL_LANGS,
    ImportRef,
    Symbol,
    count_loc,
    git_churn,
    imports_for,
    iter_source_files,
    lang_of,
    symbols_for,
    ts_available,
)


def _arg(flag: str, default: str | None = None) -> str | None:
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


# --------------------------------------------------------------------------------------
# 1. weight tree (directory-level; files aggregated, not listed, so the artifact stays small)
# --------------------------------------------------------------------------------------

def build_weight(files: list[Path], root: Path, churn: dict[str, int],
                 max_depth: int | None) -> tuple[dict, dict[str, int]]:
    """Nested directory tree, each node carrying aggregated loc/file_count/churn + lang mix.
    Also returns per-language file counts (for the coverage block)."""
    root = root.resolve()
    tree: dict = {"path": ".", "loc": 0, "file_count": 0, "churn": 0,
                  "lang": None, "langs": {}, "children": {}}
    lang_counts: dict[str, int] = {}

    for f in files:
        rel = f.relative_to(root)
        loc = count_loc(f)
        lang = lang_of(f) or "other"
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        c = churn.get(str(rel), 0)
        parts = rel.parts[:-1]  # directory chain (exclude the filename)
        if max_depth is not None:
            parts = parts[:max_depth]
        node = tree
        node["loc"] += loc
        node["file_count"] += 1
        node["churn"] += c
        node["langs"][lang] = node["langs"].get(lang, 0) + 1
        cur = root
        for part in parts:
            cur = cur / part
            child = node["children"].get(part)
            if child is None:
                child = {"path": str(cur.relative_to(root)), "loc": 0, "file_count": 0,
                         "churn": 0, "lang": None, "langs": {}, "children": {}}
                node["children"][part] = child
            child["loc"] += loc
            child["file_count"] += 1
            child["churn"] += c
            child["langs"][lang] = child["langs"].get(lang, 0) + 1
            node = child

    return _finalize_weight(tree), lang_counts


def _finalize_weight(node: dict) -> dict:
    """Turn children dicts into lists sorted by LOC desc (heaviest first = the scoping signal),
    and set each node's dominant language."""
    children = [_finalize_weight(c) for c in node["children"].values()]
    children.sort(key=lambda n: n["loc"], reverse=True)
    node["children"] = children
    if node["langs"]:
        node["lang"] = max(node["langs"].items(), key=lambda kv: kv[1])[0]
    return node


# --------------------------------------------------------------------------------------
# 2 + 3. symbols and imports
# --------------------------------------------------------------------------------------

def build_symbols(files: list[Path], root: Path) -> tuple[dict, dict]:
    root = root.resolve()
    by_name: dict[str, list[dict]] = {}
    parsed = 0
    failures: list[dict] = []
    langs_with: set[str] = set()
    langs_without: dict[str, int] = {}

    for f in files:
        lang = lang_of(f)
        if lang is None:
            continue
        rel = str(f.relative_to(root))
        if lang not in SYMBOL_LANGS:
            langs_without[lang] = langs_without.get(lang, 0) + 1
            continue
        try:
            syms: list[Symbol] = symbols_for(f, rel, lang)
        except Exception as exc:
            failures.append({"file": rel, "lang": lang, "error": f"{type(exc).__name__}: {exc}"})
            continue
        parsed += 1
        langs_with.add(lang)
        for s in syms:
            by_name.setdefault(s.name, []).append({"file": s.file, "line": s.line, "kind": s.kind})

    ambiguous = sorted(n for n, defs in by_name.items() if len(defs) > 1)
    meta = {
        "files_parsed": parsed,
        "parse_failures": failures,
        "languages_with_symbols": sorted(langs_with),
        "languages_seen_without_extractor": dict(sorted(langs_without.items())),
    }
    return {"by_name": by_name, "ambiguous": ambiguous}, meta


def _matches_target(module: str, target_prefixes: list[str]) -> bool:
    """Lower-bound match: does an import's module text reference one of the target's paths, on
    PATH-SEGMENT boundaries? A lower bound must produce no false edges (only false negatives), so
    matching is boundary-only — exact, prefix (the module lives *under* the target path), or the
    target appearing as a whole segment-run inside the module path. Raw-substring matches are
    deliberately excluded, so `core` does NOT match `scoreboard` and `api` does NOT match `rapidjson`."""
    norm = module.replace(".", "/").strip().strip("/")
    bounded = f"/{norm}/"
    for pre in target_prefixes:
        p = pre.strip().strip("/")
        if not p:
            continue
        if norm == p or norm.startswith(p + "/") or f"/{p}/" in bounded:
            return True
    return False


def build_imports(files: list[Path], root: Path, pairs_path: str | None) -> tuple[dict, dict]:
    root = root.resolve()
    semantics = "lower-bound; absence != no-dependency (dynamic/string/plugin loading is invisible)"
    if not pairs_path:
        return ({"mode": "pairs", "semantics": semantics, "pairs": [],
                 "note": "no --pairs given; rerun with named component->path mapping to get edges"},
                {"pairs_checked": 0, "files_scanned": 0, "parse_failures": []})

    mapping: dict[str, list[str]] = json.loads(Path(pairs_path).read_text())
    # index imports per file once
    file_imports: dict[str, list[ImportRef]] = {}
    failures: list[dict] = []
    scanned = 0
    for f in files:
        lang = lang_of(f)
        if lang is None or lang not in SYMBOL_LANGS:
            continue
        rel = str(f.relative_to(root))
        try:
            file_imports[rel] = imports_for(f, rel, lang)
            scanned += 1
        except Exception as exc:
            failures.append({"file": rel, "error": f"{type(exc).__name__}: {exc}"})

    def files_under(prefixes: list[str]) -> list[str]:
        pres = [p.strip().strip("/") for p in prefixes]
        return [rel for rel in file_imports
                if any(rel == p or rel.startswith(p + "/") for p in pres)]

    pairs_out: list[dict] = []
    comps = list(mapping.items())
    for a_id, a_paths in comps:
        a_files = files_under(a_paths)
        for b_id, b_paths in comps:
            if a_id == b_id:
                continue
            edges: list[dict] = []
            for rel in a_files:
                for imp in file_imports[rel]:
                    if _matches_target(imp.module, b_paths):
                        edges.append({"file": imp.file, "line": imp.line, "imported": imp.module})
            if edges:
                pairs_out.append({"from": a_id, "to": b_id, "count": len(edges),
                                  "import_edges": edges[:25]})

    return ({"mode": "pairs", "semantics": semantics, "pairs": pairs_out},
            {"pairs_checked": len(pairs_out), "files_scanned": scanned, "parse_failures": failures})


# --------------------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------------------

def main() -> int:
    root = Path(_arg("--root", ".") or ".").resolve()
    out_path = Path(_arg("--out", str(root / ".coyodex" / "preindex.json")) or "")
    since = _arg("--since")
    pairs_path = _arg("--pairs")
    md = _arg("--max-depth")
    max_depth = int(md) if md else None

    walk = iter_source_files(root)
    churn, git_ok = git_churn(root, since)
    weight, lang_counts = build_weight(walk.files, root, churn, max_depth)
    symbols, sym_meta = build_symbols(walk.files, root)
    imports, imp_meta = build_imports(walk.files, root, pairs_path)

    ts_ok = ts_available()
    coverage = {
        "files_total_walked": len(walk.files) + walk.skipped_excluded,
        "files_counted": len(walk.files),
        "files_skipped_excluded": walk.skipped_excluded,
        "languages_seen": dict(sorted(lang_counts.items(), key=lambda kv: -kv[1])),
        "languages_with_symbols": sym_meta["languages_with_symbols"],
        "languages_seen_without_extractor": sym_meta["languages_seen_without_extractor"],
        "symbol_files_parsed": sym_meta["files_parsed"],
        "symbol_parse_failures": sym_meta["parse_failures"][:50],
        "symbol_parse_failure_count": len(sym_meta["parse_failures"]),
        "import_pairs_checked": imp_meta["pairs_checked"],
        "git_available": git_ok,
        "tree_sitter_available": ts_ok,
        "used_git_ls_files": walk.used_git,
        "note": ("Unparsed regions are UNKNOWN, not empty — read them. Symbol/import data is deep "
                 "for Python (ast); other languages need the tree-sitter grammar pack. "
                 "Weight is a hint to where to look, never a decision to drill (GR5)."),
    }

    doc = {
        "tool": "coyodex preindex",
        "root": str(root),
        "weight": weight,
        "symbols": symbols,
        "imports": imports,
        "coverage": coverage,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2))

    # one-line human summary to stderr (GR1 reminder + GR3 coverage at a glance)
    top = weight["children"][:5]
    sys.stderr.write(
        f"preindex -> {out_path}\n"
        f"  {coverage['files_counted']} files, {weight['loc']} LOC; "
        f"git={'yes' if git_ok else 'NO'}, tree-sitter={'yes' if ts_ok else 'NO'}\n"
        f"  heaviest top-level: " + ", ".join(f"{c['path']}({c['loc']})" for c in top) + "\n"
        f"  symbols: {sym_meta['files_parsed']} files parsed, "
        f"{len(symbols['ambiguous'])} ambiguous names; "
        f"languages without symbols: {list(coverage['languages_seen_without_extractor'])}\n"
        "  NOTE: draft the behavioral layer BEFORE using this (GR1); reconcile every item, "
        "never copy verbatim (GR2).\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
