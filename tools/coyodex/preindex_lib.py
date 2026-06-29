#!/usr/bin/env python3
"""Shared helpers for the coyodex structural pre-index.

Two consumers, sharing CODE but never DATA (guardrail GR4 — generation != verification):
  - ``preindex.py`` runs the full walk + symbol/import extraction and writes
    ``.coyodex/preindex.json`` (the structural input the build agent reconciles).
  - ``validate_analysis.py`` reuses ONLY the walk/LOC helpers here for its
    compression-coverage check; it re-measures the tree itself and never reads the
    generated JSON. So the validator stays independent of the pre-index.

Language scope (a deliberate, scoped exception to the "Python side is stdlib-only" rule —
confined to the pre-index): the directory tree, LOC and git churn are language-agnostic and
need only stdlib + git. Symbols and imports are deep for Python via stdlib ``ast``; other
languages go through tree-sitter when the grammar pack is installed. When tree-sitter is
absent or a grammar is missing, the affected files are reported as uncovered (GR3) — never
silently counted as empty.
"""
from __future__ import annotations

import ast
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------------------
# Language detection
# --------------------------------------------------------------------------------------

# extension (no dot, lowercased) -> language name (tree-sitter grammar name where applicable)
LANG_BY_EXT: dict[str, str] = {
    "py": "python", "pyi": "python",
    "js": "javascript", "jsx": "javascript", "mjs": "javascript", "cjs": "javascript",
    "ts": "typescript", "tsx": "tsx",
    "go": "go",
    "rs": "rust",
    "java": "java",
    "rb": "ruby",
    "ex": "elixir", "exs": "elixir",
    "c": "c", "h": "c",
    "cc": "cpp", "cpp": "cpp", "cxx": "cpp", "hpp": "cpp", "hh": "cpp",
    "cs": "c_sharp",
    "php": "php",
    "swift": "swift",
    "kt": "kotlin", "kts": "kotlin",
    "scala": "scala",
    "sh": "bash", "bash": "bash",
    # text-ish (counted for LOC/weight, no symbol extraction)
    "md": "markdown", "rst": "text", "txt": "text",
    "json": "json", "yaml": "yaml", "yml": "yaml", "toml": "toml",
    "html": "html", "css": "css", "scss": "css", "sql": "sql",
}

# Languages we extract symbols/imports for via tree-sitter (python is handled by ast).
TS_DEF_TYPES: dict[str, dict[str, str]] = {
    "javascript": {"class_declaration": "class", "function_declaration": "function",
                   "generator_function_declaration": "function", "method_definition": "method"},
    "typescript": {"class_declaration": "class", "abstract_class_declaration": "class",
                   "function_declaration": "function", "method_definition": "method",
                   "interface_declaration": "interface", "enum_declaration": "enum",
                   "type_alias_declaration": "type"},
    "go": {"function_declaration": "function", "method_declaration": "method",
           "type_spec": "type"},
    "rust": {"function_item": "function", "struct_item": "struct", "enum_item": "enum",
             "trait_item": "trait", "mod_item": "module"},
    "java": {"class_declaration": "class", "interface_declaration": "interface",
             "method_declaration": "method", "enum_declaration": "enum"},
    "ruby": {"class": "class", "module": "module", "method": "method",
             "singleton_method": "method"},
    "c": {"function_definition": "function", "struct_specifier": "struct"},
    "cpp": {"function_definition": "function", "class_specifier": "class",
            "struct_specifier": "struct"},
    "c_sharp": {"class_declaration": "class", "method_declaration": "method",
                "interface_declaration": "interface", "struct_declaration": "struct"},
    "php": {"class_declaration": "class", "function_definition": "function",
            "method_declaration": "method", "interface_declaration": "interface"},
}
# tsx shares typescript's node types
TS_DEF_TYPES["tsx"] = TS_DEF_TYPES["typescript"]

TS_IMPORT_TYPES: dict[str, set[str]] = {
    "javascript": {"import_statement"},
    "typescript": {"import_statement"},
    "tsx": {"import_statement"},
    "go": {"import_spec"},
    "rust": {"use_declaration"},
    "java": {"import_declaration"},
    "ruby": {"call"},  # require/require_relative — filtered to those names below
    "c": {"preproc_include"},
    "cpp": {"preproc_include"},
    "c_sharp": {"using_directive"},
    "php": {"namespace_use_declaration"},
}

# --------------------------------------------------------------------------------------
# Excludes (generated / vendored / lockfiles) — weight should reflect authored code
# --------------------------------------------------------------------------------------

DEFAULT_EXCLUDE_DIRS: set[str] = {
    ".git", ".hg", ".svn", "node_modules", "bower_components", "vendor", "third_party",
    "dist", "build", "out", "target", ".next", ".nuxt", ".svelte-kit",
    "__pycache__", ".venv", "venv", "env", ".tox", ".mypy_cache", ".pytest_cache",
    ".gradle", ".idea", ".vscode", "coverage", ".coyodex",
}
DEFAULT_EXCLUDE_SUFFIXES: tuple[str, ...] = (
    ".min.js", ".min.css", ".map", ".lock", ".lock.json",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".pdf", ".zip", ".gz", ".tar", ".woff", ".woff2", ".ttf", ".eot",
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".class", ".o", ".a",
)
DEFAULT_EXCLUDE_NAMES: set[str] = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock",
    "Cargo.lock", "composer.lock", "go.sum", ".DS_Store",
}


def lang_of(path: Path) -> str | None:
    return LANG_BY_EXT.get(path.suffix.lstrip(".").lower())


def _excluded(rel: Path) -> bool:
    if any(part in DEFAULT_EXCLUDE_DIRS for part in rel.parts):
        return True
    if rel.name in DEFAULT_EXCLUDE_NAMES:
        return True
    return rel.name.lower().endswith(DEFAULT_EXCLUDE_SUFFIXES)


@dataclass
class WalkResult:
    files: list[Path]            # absolute paths of counted source files
    root: Path
    used_git: bool               # True if the tracked-file set came from `git ls-files`
    skipped_excluded: int        # files dropped by the exclude rules


def iter_source_files(root: Path) -> WalkResult:
    """Enumerate authored source files under ``root``.

    Prefers ``git ls-files`` (honors .gitignore, so generated output never inflates weight);
    falls back to an ``os.walk`` with the default exclude list when ``root`` is not a git repo.
    The exclude rules apply in both modes, so the file set is the same shape either way.
    """
    root = root.resolve()
    used_git = False
    rels: list[Path]
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True, text=True, timeout=120,
        )
        if out.returncode == 0 and out.stdout:
            rels = [Path(p) for p in out.stdout.split("\0") if p]
            used_git = True
        else:
            rels = _walk_rels(root)
    except (OSError, subprocess.SubprocessError):
        rels = _walk_rels(root)

    files: list[Path] = []
    skipped = 0
    for rel in rels:
        if _excluded(rel):
            skipped += 1
            continue
        files.append(root / rel)
    return WalkResult(files=files, root=root, used_git=used_git, skipped_excluded=skipped)


def _walk_rels(root: Path) -> list[Path]:
    import os
    rels: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_EXCLUDE_DIRS]
        for fn in filenames:
            abs_p = Path(dirpath) / fn
            try:
                rels.append(abs_p.relative_to(root))
            except ValueError:
                continue
    return rels


def count_loc(path: Path) -> int:
    """Newline count of a text file; 0 for unreadable/binary files."""
    try:
        with path.open("rb") as fh:
            data = fh.read()
        if b"\0" in data[:4096]:  # crude binary guard
            return 0
        return data.count(b"\n")
    except OSError:
        return 0


def git_churn(root: Path, since: str | None) -> tuple[dict[str, int], bool]:
    """Map of repo-relative path -> number of commits touching it (optionally since a rev/date).

    One ``git log --numstat`` pass (not per-file ``--follow``), so cost is bounded by history
    length, not file count. Returns ({}, False) when ``root`` is not a git repo.
    """
    cmd = ["git", "-C", str(root), "log", "--numstat", "--format=%x00", "--no-renames"]
    if since:
        cmd.append(f"--since={since}")
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.SubprocessError):
        return {}, False
    if out.returncode != 0:
        return {}, False
    churn: dict[str, int] = {}
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line or line == "\0" or line.startswith("\0"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        path = parts[2]
        churn[path] = churn.get(path, 0) + 1
    return churn, True


# --------------------------------------------------------------------------------------
# Symbols & imports
# --------------------------------------------------------------------------------------

@dataclass
class Symbol:
    name: str
    kind: str
    file: str   # repo-relative
    line: int


@dataclass
class ImportRef:
    file: str   # repo-relative
    line: int
    module: str  # raw imported module/path text (lower-bound matching uses substring)


def py_symbols(path: Path, rel: str) -> list[Symbol]:
    """Top-level + nested class/function definitions in a Python file, via stdlib ast."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        raise
    out: list[Symbol] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            out.append(Symbol(node.name, "class", rel, node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(Symbol(node.name, "function", rel, node.lineno))
    return out


def py_imports(path: Path, rel: str) -> list[ImportRef]:
    """Import targets in a Python file, via stdlib ast. Dynamic imports are NOT captured
    (they land nowhere) — that is the 'lower-bound' honesty of the advisory."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        raise
    out: list[ImportRef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(ImportRef(rel, node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            mod = ("." * (node.level or 0)) + (node.module or "")
            out.append(ImportRef(rel, node.lineno, mod))
    return out


# ---- tree-sitter path (optional; only loaded when needed) ----

_TS_PARSERS: dict[str, Any] = {}  # cached tree-sitter parsers (typed Any: no top-level ts import)
_TS_IMPORT_ERROR: str | None = None


def ts_available() -> bool:
    return _ts_get_parser("python") is not None or _try_import_ts()


def _try_import_ts() -> bool:
    global _TS_IMPORT_ERROR
    try:
        import tree_sitter_language_pack  # noqa: F401
        return True
    except Exception as exc:  # pragma: no cover - environment dependent
        _TS_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
        return False


def _ts_get_parser(lang: str) -> Any:
    # Build the parser the documented way (tree_sitter.Parser(get_language(...))). The pack's own
    # get_parser() returns an incompatible wrapper on some tree-sitter builds (root_node unusable),
    # so we go through get_language + the stdlib-style Parser, which is stable across 0.21–0.25.
    if lang in _TS_PARSERS:
        return _TS_PARSERS[lang]
    parser = None
    try:
        from tree_sitter import Parser
        from tree_sitter_language_pack import get_language
        parser = Parser(get_language(lang))
    except Exception:
        parser = None
    _TS_PARSERS[lang] = parser
    return parser


def _node_text(src: bytes, node) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _node_name(src: bytes, node) -> str | None:
    field = node.child_by_field_name("name")
    if field is not None:
        return _node_text(src, field)
    for child in node.children:
        if child.type in ("identifier", "type_identifier", "field_identifier",
                           "constant", "name"):
            return _node_text(src, child)
    return None


def ts_symbols(path: Path, rel: str, lang: str) -> list[Symbol]:
    """Class/function-like definitions for a non-Python language via tree-sitter.
    Raises if the parser/grammar is unavailable so the caller records it under coverage."""
    def_types = TS_DEF_TYPES.get(lang)
    if def_types is None:
        raise LookupError(f"no symbol extractor for language {lang!r}")
    parser = _ts_get_parser(lang)
    if parser is None:
        raise LookupError(f"tree-sitter grammar for {lang!r} unavailable")
    src = path.read_bytes()
    tree = parser.parse(src)
    out: list[Symbol] = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        kind = def_types.get(node.type)
        if kind is not None:
            name = _node_name(src, node)
            if name:
                out.append(Symbol(name, kind, rel, node.start_point[0] + 1))
        stack.extend(node.children)
    return out


def ts_imports(path: Path, rel: str, lang: str) -> list[ImportRef]:
    """Import statements for a non-Python language via tree-sitter (raw module text)."""
    imp_types = TS_IMPORT_TYPES.get(lang)
    if imp_types is None:
        raise LookupError(f"no import extractor for language {lang!r}")
    parser = _ts_get_parser(lang)
    if parser is None:
        raise LookupError(f"tree-sitter grammar for {lang!r} unavailable")
    src = path.read_bytes()
    tree = parser.parse(src)
    out: list[ImportRef] = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in imp_types:
            text = _node_text(src, node).strip()
            if lang == "ruby":
                # only require / require_relative calls
                if not text.startswith(("require", "load")):
                    stack.extend(node.children)
                    continue
            out.append(ImportRef(rel, node.start_point[0] + 1, text))
        stack.extend(node.children)
    return out


def symbols_for(path: Path, rel: str, lang: str) -> list[Symbol]:
    """Dispatch to the right extractor. Raises on unsupported/failed parse (caller records it)."""
    if lang == "python":
        return py_symbols(path, rel)
    return ts_symbols(path, rel, lang)


def imports_for(path: Path, rel: str, lang: str) -> list[ImportRef]:
    if lang == "python":
        return py_imports(path, rel)
    return ts_imports(path, rel, lang)


SYMBOL_LANGS: set[str] = {"python", *TS_DEF_TYPES.keys()}
