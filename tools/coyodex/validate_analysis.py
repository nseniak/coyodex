#!/usr/bin/env python3
"""Shared helpers behind `coyodex validate`'s semantic checks (`tools/coyodex/validate_model.py`):
  - `check_hierarchy` — grouping/nesting: right-kind parent, defined, no cycles, deep-nest advisory.
  - anchor/source resolution — `strip_anchor`, `_where_href`, `_source_roots`, `_resolve_source_file`.
  - coverage/granularity advisories — `compression_coverage_from_refs` (peer-level compression +
    absent modules, re-measuring the repo tree) and `granularity_advisory` (component count vs the
    code-derived expectation E), plus the domain-coverage building blocks (`_is_non_entity_type`,
    `_type_covered`, the `_ISOLATED_*`/`_UNCOVERED_*` thresholds) and the altitude-hint building
    blocks (`_LIST_ITEM`, `_ALTITUDE_MIN`) `validate_model.py` runs against `ProjectModel` fields.
Stdlib-only.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

# Grammar (regexes, membership rule) lives in grammar, shared with the parser — one grammar.
from coyodex.anchors import FILE_ANCHOR as _BARE_PATH, LINE_ANCHOR, strip_anchor
from coyodex.grammar import DEEP_NEST_WARN


def _is_subsystem_id(i: str) -> bool:  # an `S` id, never a subdomain (`SD1` also starts with "S")
    return i.startswith("S") and not i.startswith("SD")


def _expected_parent_kind(child: str) -> str:
    """The KIND a child's parent must be: entities (`E`) and subdomains (`SD`) nest under a SUBDOMAIN;
    components (`C`) and subsystems (`S`) nest under a SUBSYSTEM."""
    return "subdomain" if child.startswith(("E", "SD")) else "subsystem"


def _is_parent_kind(par: str, kind: str) -> bool:  # par's id-prefix matches the expected parent kind
    return par.startswith("SD") if kind == "subdomain" else _is_subsystem_id(par)


def check_hierarchy(parents: dict[str, str], defined: set[str]) -> tuple[list[str], list[str]]:
    """Returns ``(problems, warnings)``. Parent must be the right KIND for the child
    (component/subsystem -> `S`; entity/subdomain -> `SD`) and defined, with no nesting cycles — all
    BLOCKING. Nesting deeper than `DEEP_NEST_WARN` is a non-blocking ADVISORY: arbitrary depth is allowed
    (the viewer renders it), and the cycle check — not a depth cap — is what makes the walk terminate.
    The two forests (component->S and entity->SD) share one walk — their id spaces are disjoint, so a
    chain never crosses between them. The kind check is EXACT, not a bare prefix test: `SD` starts with
    `S`, so a component pointed at a subdomain must still be flagged."""
    problems: list[str] = []
    for child, par in parents.items():
        want = _expected_parent_kind(child)
        if not _is_parent_kind(par, want):
            label = "subdomain (SD…)" if want == "subdomain" else "subsystem (S…)"
            problems.append(f"{child} parent {par} is not a {label}")
        elif par not in defined:
            problems.append(f"{child} parent {par} is undefined")
    # Walk only well-formed (right-kind) pointers, so a wrong-type parent reported above does not
    # also surface as a spurious "cycle" line.
    valid = {c: p for c, p in parents.items() if _is_parent_kind(p, _expected_parent_kind(c))}
    deep: set[str] = set()
    for start in valid:
        chain, cur, depth = [start], start, 0
        while cur in valid:
            cur = valid[cur]
            depth += 1
            if cur in chain:
                problems.append(f"Nesting cycle: {' -> '.join(chain)} -> {cur}")
                break
            chain.append(cur)
            if depth > DEEP_NEST_WARN:
                deep.add(" -> ".join(chain))  # the over-deep chain (top → leaf), deduped across walks
                break
    warnings = [f"Deep nesting (> {DEEP_NEST_WARN} levels) — is each level pulling its weight? {d}"
                for d in sorted(deep)]
    return problems, warnings


_LIST_ITEM = re.compile(r"^[a-z][a-z0-9_]+$")  # a bare lowercase identifier — a likely sub-unit (dir/module) name
_ALTITUDE_MIN = 6  # this many bare-identifier items in one cell reads as a list of sub-units, not a purpose


_COMPRESSION_MIN = 8      # this many sibling source subdirs folded into ~one box reads as lost signal
_ABSENT_MIN_FILES = 25    # a top-level dir this large with nothing referenced is a likely unmapped module
# The conventional NON-PRODUCT directory basenames (test trees, internal/docs) live in
# `preindex_lib.NON_PRODUCT_DIRS` — one list shared with the granularity expectation E; pulled via
# the same local import the coverage check already uses (the core gate stays import-independent).
_REF_LINK = re.compile(r"\]\(([^)\s#]+)")                         # markdown link target ](path...)
_REF_INLINE = re.compile(r"(?<![\w/])((?:[\w.\-]+/)+[\w.\-]+)")   # inline a/b/c path
# Monorepo container roots — under these, a fold one level deeper is still an altitude decision
# (`packages/app/plugins`), so look one level further. Under an ordinary package it is not, so a leaf
# component's internal subdirs (`mee6/plugins/achievements/`) stay abstracted (GR6).
_MONOREPO_ROOTS = {"packages", "apps", "services", "libs", "modules", "projects", "workspaces", "crates"}


def _fold_depth_ok(dpath: str) -> bool:
    """Inspect folds at the top/second level — one deeper under a recognized monorepo container."""
    first = dpath.split("/", 1)[0]
    return dpath.count("/") <= (2 if first in _MONOREPO_ROOTS else 1)


def compression_coverage_from_refs(refs: set[str], root: Path,
                                   skip_dirs: frozenset[str] = frozenset()) -> list[str]:
    """Advisory (non-blocking, opt-in via --check-coverage): the map-fidelity counterpart to the
    referential checks, from an already-extracted set of repo-relative referenced paths. Flags two
    *lost-signal* shapes by RE-MEASURING the repo tree (never reading the pre-index's JSON — GR4):
      - peer-level COMPRESSION — a top/second-level directory whose many sibling source subdirs are
        folded into ~one map box (the 65-plugins-as-one-component failure). Only top/second level,
        because a leaf component's internal subdirs are SUPPOSED to be abstracted (GR6).
      - significant ABSENT modules — a top-level dir with many source files that the map never
        references at all.
    Both self-report their denominator. Intentional abstraction is a feature, so this only ever
    WARNS, never blocks (GR6)."""
    # Local import: keep the CORE GATE independent of the advisory pre-index module — the validator
    # imports nothing from it at load time, only this opt-in check pulls the shared (stdlib) walk
    # helper. Reuses CODE, never the pre-index's JSON DATA (GR4: generation != verification).
    from coyodex.preindex_lib import NON_PRODUCT_DIRS, iter_source_files

    root = root.resolve()
    walk = iter_source_files(root)
    dir_children: dict[str, set[str]] = {}
    dir_filecount: dict[str, int] = {}
    for f in walk.files:
        parts = f.relative_to(root).parts
        for i in range(len(parts)):
            dpath = "/".join(parts[:i]) if i else "."
            dir_filecount[dpath] = dir_filecount.get(dpath, 0) + 1
            if i + 1 < len(parts):
                dir_children.setdefault(dpath, set()).add("/".join(parts[:i + 1]))

    def covered_under(prefix: str) -> bool:
        return any(r == prefix or r.startswith(prefix + "/") for r in refs)

    def recorded(dpath: str) -> bool:
        # a 'Coverage exceptions' dir silences this dpath if it is AT OR UNDER the recorded dir
        # (boundary-aware, same rule as covered_under): the operator's conscious coarse-altitude fold.
        return any(dpath == d or dpath.startswith(d + "/") for d in skip_dirs)

    out: list[str] = []
    flagged: set[str] = set()
    for dpath, subs in sorted(dir_children.items()):
        n = len(subs)
        if (dpath == "." or not _fold_depth_ok(dpath) or n < _COMPRESSION_MIN
                or not covered_under(dpath) or recorded(dpath)):
            continue
        covered_subs = sum(1 for s in subs if covered_under(s))
        if covered_subs * 4 < n:  # the map individually represents fewer than ~a quarter of the peers
            flagged.add(dpath)
            out.append(
                f"Compression: {dpath}/ holds {n} sibling source subdirs but the map references paths "
                f"in only {covered_subs} of them — up to {n - covered_subs} peer modules folded into "
                f"~one box; if distinct, drill {dpath}/ into a subsystem ({n} subdirs, measured at "
                f"validate time)"
            )
    # Absent / under-referenced: a dir the map never references that is either large (>= _ABSENT_MIN_FILES
    # files) OR has many sibling subdirs (>= _COMPRESSION_MIN) — the latter catches a small-but-fanned
    # fold the compression pass skips because the map references nothing inside it.
    absent: list[tuple[int, str]] = []
    for dpath, fc in dir_filecount.items():
        if (dpath == "." or not _fold_depth_ok(dpath) or dpath in flagged or covered_under(dpath)
                or recorded(dpath)
                or dpath.rsplit("/", 1)[-1] in NON_PRODUCT_DIRS):  # skip test / internal / docs trees
            continue
        n_subs = len(dir_children.get(dpath, ()))
        if fc >= _ABSENT_MIN_FILES or n_subs >= _COMPRESSION_MIN:
            absent.append((fc, dpath))
    for fc, dpath in sorted(absent, reverse=True)[:8]:
        n_subs = len(dir_children.get(dpath, ()))
        out.append(
            f"Coverage: {dpath}/ ({fc} source files, {n_subs} subdirs) has no path referenced in the "
            f"map — likely an unmapped module (measured at validate time)"
        )
    return out


def granularity_advisory(n_components: int, root: Path) -> list[str]:
    """Advisory (non-blocking, opt-in via --check-coverage): the map's COMPONENT (leaf) count vs the
    code-derived granularity expectation E — the leaf anchor (one component ≈ one ≤10-file/≤3-kLOC
    module-sized unit; see method.md). Fires only when the count sits OUTSIDE the generous ±40% band;
    silent within it. Like every coverage check it RE-COMPUTES E from the tree (shared code in
    `preindex_lib`, never the pre-index's JSON — GR4). Never checks the subsystem count — nesting is
    the builder's free output; only the leaf decision is anchored."""
    # Local import, same rule as the coverage check above: the core gate stays import-independent of
    # the pre-index module; this opt-in check reuses its CODE, never its generated DATA (GR4).
    from coyodex.preindex_lib import (
        GRANULARITY_BAND_PCT,
        GRANULARITY_FILE_CAP,
        GRANULARITY_LOC_CAP,
        expected_components,
        granularity_band,
    )

    if n_components <= 0:
        return []
    tree = expected_components(root.resolve())
    if tree.expected <= 0:
        return []  # no component-forming source measured — nothing to anchor against
    lo, hi = granularity_band(tree.expected)
    if lo <= n_components <= hi:
        return []
    if n_components < lo:
        hint = ("possibly folding subsystem-shaped dirs into single components — consider promoting "
                "them to subsystems")
    else:
        hint = "possibly splitting module-sized units too fine — consider merging cohesive siblings"
    return [
        f"Granularity: {n_components} components vs a code-derived ~{tree.expected} "
        f"(band {lo}–{hi} at ±{GRANULARITY_BAND_PCT:.0%}; a component ≈ ≤{GRANULARITY_FILE_CAP} files / "
        f"≤{GRANULARITY_LOC_CAP} LOC) — {hint}. This is a rough zoom anchor, NOT a verdict: a "
        f"deliberately high-altitude map of a large repo, or a very modular clean-architecture repo, "
        f"legitimately sits outside the band — ignore if the chosen altitude is intentional."
    ]


# A `Where` / anchor cell is a SOURCE LOCATION (the call site a flow arrow opens): a file ref with an
# optional `:line`/`:line-line` (extension optional — `Dockerfile:1` is valid), shared from
# `coyodex.anchors` so format lives in one place. A markdown link is not a valid `Where`/anchor shape —
# `_check_anchor_format` (validate_model.py) rejects it rather than this function extracting its href.
# `strip_anchor` / `_LINE_ANCHOR` live in `coyodex.anchors` (one anchor home); re-exported here so the
# existing `from coyodex.validate_analysis import strip_anchor` importers keep working.
_LINE_ANCHOR = LINE_ANCHOR


def _where_href(cell: str) -> str | None:
    """The file location a `Where` / anchor cell points to: the cell itself when it is a bare
    `path.ext[:line]` token. None for an empty / prose / non-anchor-shaped cell."""
    cell = cell.strip()
    if not cell:
        return None
    return cell if _BARE_PATH.match(cell) else None


def _source_roots(map_path: Path, repo_root: Path | None = None) -> list[Path]:
    """The roots a map's SOURCE / anchor paths resolve against. By default the map's own dir and its
    parent (the repo root for a `.coyodex/` map). An explicit `repo_root` (the `--repo` flag) is tried
    FIRST — a map validated from outside its repo (e.g. an eval's deep run dir) resolves its
    repo-root-relative anchors against the real tree; the map-derived roots stay as fallback so
    in-repo behavior is unchanged. Shared by every repo-reading check so this resolution rule lives in
    one place."""
    base = map_path.resolve().parent
    roots = [base, base.parent]
    if repo_root is not None:
        roots.insert(0, repo_root.resolve())
    return roots


def _resolve_source_file(source: str, roots: list[Path]) -> Path | None:
    """The real file a card's SOURCE points at — its line anchor stripped, resolved against
    `roots`. None when it doesn't resolve (a placeholder, or a run outside the repo), so a repo-reading
    check skips it instead of false-flagging."""
    rel = strip_anchor(source)
    return next((r / rel for r in roots if (r / rel).is_file()), None)


# NON-ENTITY types the under-harvest count must exclude (V2): infrastructure / plumbing classes that
# legitimately live in a domain dir but are not domain entities, so no entity card should represent
# them. Matched by NAME SUFFIX (a `UserRepository` is persistence machinery, not a second User) and by
# BASE (an `ABC` / `Protocol` subclass is an interface contract, not a stored thing). Without this
# filter a repository/provider-heavy domain dir reads as "62 unmodelled types" when the model is fine.
_NON_ENTITY_SUFFIXES = ("Repository", "Store", "Provider", "Protocol", "Error", "Exception",
                        "Middleware")
_NON_ENTITY_BASES = frozenset({"ABC", "Protocol"})


def _base_name(base: ast.expr) -> str | None:
    """The bare class name of a base expression: `ABC` -> 'ABC', `abc.ABC` -> 'ABC',
    `Protocol[T]` -> 'Protocol'. None for anything else (a call, a computed base)."""
    if isinstance(base, ast.Subscript):  # Protocol[T] / Generic[T] — look at the subscripted name
        base = base.value
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _is_non_entity_type(node: ast.ClassDef) -> bool:
    """True for a class the domain-coverage count should skip: a plumbing suffix in its name, or an
    `ABC` / `Protocol` base (an abstract contract is not an entity)."""
    if node.name.endswith(_NON_ENTITY_SUFFIXES):
        return True
    return any(_base_name(b) in _NON_ENTITY_BASES for b in node.bases)


def _type_covered(type_name: str, entity_names: list[str]) -> bool:
    """True if a code type is represented by some entity card — the same lenient, case-insensitive
    substring match the entity-sources check uses to ground an entity in its file, run in reverse: an
    entity's identifier token appears in the type name, or the type name appears in the entity name.
    Tolerant on purpose (an abbreviated / compound / suffixed card name still counts as covering)."""
    t = type_name.lower()
    for name in entity_names:
        low = name.lower()
        if t in low or low in t:
            return True
        if any(tok.lower() in t for tok in re.findall(r"[A-Za-z_]\w{2,}", name)):
            return True
    return False


# Domain-model coverage thresholds (advisory). Calibrated against the two real mcpolis runs so the
# thin-domain regression (the new run: 8/33 entities isolated, 62/103 source-dir types unmodelled)
# warns while the richer run (6/37 isolated) stays quiet — see method retrospective. They are not a
# blocking gate; intentional abstraction is allowed (GR6), so an over-trip is a nudge, never a failure.
_ISOLATED_FRACTION = 0.20  # warn when MORE than this share of entity cards have zero E↔E relations
_ISOLATED_MIN = 3          # …and at least this many are isolated (floor — quiets tiny/young models)
_ISOLATED_MIN_ENTITIES = 5  # …and the model has at least this many entities at all
_UNCOVERED_FRACTION = 0.40  # warn when AT LEAST this share of source-dir types have no entity card
_UNCOVERED_MIN = 10         # …and at least this many are uncovered (floor — a strong signal only)
_COVERAGE_SAMPLE = 12       # cap the entity / type list in a warning so it stays readable
