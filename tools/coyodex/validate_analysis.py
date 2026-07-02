#!/usr/bin/env python3
"""Validate project-map.md against the schema-v1 conventions.

Stdlib-only. Checks that the analysis file is a clean machine-parseable source
for diagrams/tooling:

  1. Every element ID (UC/C/D/E/S/GP) is defined exactly once.
  2. Every ID *reference* (T6 flow steps, GP `*(UCn)*` tags, edge list,
     Depends-on, Subsystem/Parent membership) resolves to a defined ID.
  3. Every Golden Path step (GPn heading) names its use case (`*(UCn)*` tag), and every T6 flow
     step is a well-formed `from → to` whose endpoints resolve (an element ID, or a Role for an actor).
  4. Grouping, when present (no-op when absent): every Subsystem/Parent value
     resolves to a defined `S`; at most one parent per element; no nesting
     cycles. (Nesting depth is unbounded — deep chains only WARN, never block.)
  5. Table shape: every row of a markdown table (header / separator / data)
     carries the same column count — catches the malformed-separator / dropped-cell
     class that silently breaks parsing and diagram rendering.
  5b. Table runs: no table is SPLIT by an injected non-pipe line (HTML comment, blank
     line, stray prose). A table is one contiguous run of `|`-lines for both the parser
     and the renderer, so a comment between the separator and the rows breaks it into an
     empty table + a detached row block — the renderer silently drops the orphaned rows
     and every other check skips them. This flags the split itself (the only check that
     can see what would silently vanish from the render).
  6. Edge verbs: every edge row (From + To id) carries a non-empty Verb — a blank one
     renders as `src -->|| dst`, dropping the Mermaid label and desyncing the viewer.
  6b. Edge `Where` (WARN): the call-site `Where` is a source location (a `[file](path#Lnnn)` link
     or a bare `path:line`), not empty/prose — a flow arrow opens it, so a bad one is a dead link.

When an id reads as undefined because its definition row glued extra text into the
ID cell (`| **UC1** Search… |` instead of `| **UC1** | Search… |`), the report names
that specific cause instead of the generic "undefined ID".

Opt-in (reads the analyzed repo's source/tree, not just the map):
  7. --check-sources: each domain card's entity NAME must appear in its SOURCE file — catches
     synthesized entities (a name with no real named type) and wrong anchors. Also WARNs on any
     drill-to-code anchor (edge `Where`, node anchor, card SOURCE) that doesn't resolve to a real
     file/dir in the repo — a moved / renamed / mistyped path.
  8. --check-coverage: re-walk the repo tree and WARN on map-fidelity gaps the referential checks
     cannot see — peer-level compression (many sibling source subdirs folded into ~one box, the
     65-plugins-as-one-component failure) and significant directories the map never references.
     Advisory only (intentional abstraction is a feature); it re-measures the tree and never reads
     the pre-index JSON, so generation and verification stay independent.
  8b. --check-coverage also flags an UNDER-HARVESTED DOMAIN MODEL — the thin-domain regression a
     directory-sliced harvest produces when no agent owns the T5 card slice: (a) entity cards with
     ZERO E↔E relation when a material share of the model is so isolated (a sparse class graph), and
     (b) named Python types in the entities' own source dirs that no entity card represents (a
     re-measurement via stdlib `ast`, never the pre-index JSON). Both are advisory.

Exit 0 = clean, 1 = problems found.

Usage:  coyodex validate [--check-sources] [--check-coverage] [--repo <root>] [.coyodex/project-map.md]

`--repo <root>` points the repo-reading checks (anchors, sources, coverage) at the analyzed repo's
root, for a map that is NOT sitting in its repo's own `.coyodex/` (e.g. an eval's deep run dir).
Anchors are repo-root-relative, so without it those checks resolve against the map's dir and its
parent — correct in-repo, wrong anywhere else. The old roots remain as fallback, so in-repo runs are
unchanged.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# Grammar (regexes, membership rule) lives in schema_v1, shared with the parser — one grammar.
from coyodex.schema_v1 import (
    ALLOWED_CARDINALITY,
    DEF_BOLD,
    DEF_ENTITY,
    DEF_GP,
    DEF_ID_CELL,
    DEP_KINDS,
    DEEP_NEST_WARN,
    GLUED_DEF,
    GLUED_DEF_INNER,
    GP_UC_TAG,
    ID_TOKEN,
    REL_ALIAS,
    fk_targets,
    is_separator_row,
    iter_domain_cards,
    iter_flows,
    iter_pipe_runs,
    membership_ids,
    resolve_backing,
    split_cells,
    strip_fences,
    unterminated_fence_line,
)


def n_columns(row: str) -> int:
    """Cell count of a table row."""
    return len(split_cells(row))


def iter_tables(text: str) -> list[tuple[int, list[str]]]:
    """Each WELL-FORMED table — a ``|``-run of >= 2 lines whose 2nd line is a separator — as
    ``(start_index, block_lines)``. Built on the shared ``schema_v1.iter_pipe_runs`` grouping, so every
    table check sees tables the same way the parser/renderer does. A lone row or a separator-less block
    is skipped here (it is not a renderable table); that split-table case is reported by
    ``check_table_runs`` instead, so skipping it here never hides a silent loss. Run on fence-free text."""
    return [(start, block) for start, block in iter_pipe_runs(text.splitlines())
            if len(block) >= 2 and is_separator_row(block[1])]


def collect_defined(text: str) -> tuple[dict[str, int], list[str]]:
    """Return {id: count} for defined ids, plus an ordered list of GP headings."""
    counts: dict[str, int] = {}
    gp_order: list[str] = []
    for line in text.splitlines():
        m = DEF_BOLD.match(line)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
        m = DEF_GP.match(line)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
            gp_order.append(m.group(1))
        m = DEF_ENTITY.match(line)  # T5 domain cards define E ids in their heading, not a table row
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts, gp_order


def collect_referenced(text: str) -> set[str]:
    return set(ID_TOKEN.findall(text))


def check_gp_use_cases(text: str, gp_order: list[str]) -> list[str]:
    """Each Golden Path step must name the use case it realizes via a `*(UCn)*` tag — the step IS that
    use case, and its detail lives in the use case's T6 flow. (That the named use case resolves to a
    definition is handled by the global undefined-reference check.) Returns the GP ids missing a tag."""
    lines = text.splitlines()
    heading = {m.group(1): line for line in lines if (m := DEF_GP.match(line))}
    return [gp for gp in gp_order if not GP_UC_TAG.search(heading.get(gp, ""))]


def collect_role_names(text: str) -> set[str]:
    """Lowercased role display-names from the Roles table (first column, bold-stripped). Empty when
    there is no Roles table — so the Actor check below is a no-op on maps without one."""
    names: set[str] = set()
    for _start, block in iter_tables(text):
        headers = [c.lower() for c in split_cells(block[0])]
        if not headers or headers[0] != "role":
            continue
        for row in block[2:]:
            if is_separator_row(row):
                continue
            cells = split_cells(row)
            name = re.sub(r"\*+", "", cells[0]).strip() if cells else ""
            if name:
                names.add(name.lower())
        break
    return names


def check_flow_steps(text: str, role_names: set[str]) -> list[str]:
    """T6 flow problems the global id-resolution check can't see: a use case with more than ONE flow
    block (the renderer keys flows by use case, so a second would silently overwrite the first — and a
    stray `**UCn — …**` line in prose parses as a flow), a step that is not a well-formed `from → to`
    interaction, and an ACTOR endpoint (a Role name, not an element ID) that doesn't resolve to a
    defined Role. Element-ID endpoints are covered by the global undefined-reference check; the Role
    check is skipped when the map has no Roles table, so this stays additive."""
    problems: list[str] = []
    flows = list(iter_flows(text.splitlines()))
    counts: dict[str, int] = {}
    for f in flows:
        counts[f.uc] = counts.get(f.uc, 0) + 1
    dups = sorted(uc for uc, c in counts.items() if c > 1)
    if dups:
        problems.append("Use cases with more than one T6 flow block (each use case has exactly one "
                        f"flow): {', '.join(dups)}")
    for flow in flows:
        for st in flow.steps:
            tag = f"{flow.uc} flow step {st.n}"
            if not st.ok:
                problems.append(f"{tag} is not a `from → to` interaction: '{st.src}'")
                continue
            if role_names:
                for end, is_id in ((st.src, st.src_is_id), (st.dst, st.dst_is_id)):
                    if not is_id and end and end.lower() not in role_names:
                        problems.append(f"{tag}: actor '{end}' is not a defined Role")
    return problems


def check_roles_kind(text: str) -> list[str]:
    """If a Roles table exists (header's first cell is 'Role'), it must carry a 'Kind' column.
    No-op when there is no Roles table, so the check is additive."""
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.lower() for c in split_cells(s)]
        if cells and cells[0] == "role":  # the Roles table header row
            if "kind" not in cells:
                return ["Roles table is missing the required 'Kind' column (human/service)"]
            return []
    return []


def check_dep_kinds(text: str) -> list[str]:
    """If the T2 dependencies table carries the optional `Kind` column, every non-empty value must be
    one of DEP_KINDS (datastore/messaging/service/platform/framework/library) — it drives how the C4
    Context view treats the dep (external system drawn by name vs in-process lib folded away). No-op
    when no D-defining table has a Kind column (Kind is then inferred from Type). Scoped to rows that
    define a `D` id, so the Roles table's own human/service `Kind` column is never inspected."""
    problems: list[str] = []
    for _start, block in iter_tables(text):
        headers = [c.lower() for c in split_cells(block[0])]
        if "kind" not in headers:
            continue
        kcol = headers.index("kind")
        for row in block[2:]:
            if is_separator_row(row):
                continue
            cm = DEF_BOLD.match(row)
            if not cm or not cm.group(1).startswith("D"):
                continue  # only T2 dep rows — never the Roles table's human/service Kind
            cells = split_cells(row)
            raw = cells[kcol].strip() if kcol < len(cells) else ""
            if raw and raw.lower() not in DEP_KINDS:
                problems.append(
                    f"{cm.group(1)} has an invalid dependency Kind '{raw}' — "
                    f"use one of: {', '.join(DEP_KINDS)}"
                )
    return problems


def collect_parents(text: str) -> tuple[dict[str, str], list[str]]:
    """child_id -> parent_id from the membership column (Subsystem/Parent), via the shared
    schema_v1 rule. Returns the mapping plus problems for multi-parent cells. No-op (returns
    ``({}, [])``) when no such column exists, so ungrouped maps are unaffected.
    """
    parents: dict[str, str] = {}
    problems: list[str] = []
    # iter_pipe_runs (not iter_tables): a membership table is found by its header, and rows are read
    # via DEF_BOLD + separators skipped inline — so this does NOT require a separator on line 2 (the
    # historical behavior; check_table_runs is what flags a genuinely separator-less block).
    for _start, block in iter_pipe_runs(text.splitlines()):
        if len(block) < 2:
            continue
        headers = [c.lower() for c in split_cells(block[0])]
        if "subsystem" not in headers and "parent" not in headers:
            continue
        for row in block[1:]:
            if is_separator_row(row):
                continue  # separator row
            cm = DEF_BOLD.match(row)
            if not cm:
                continue
            child = cm.group(1)
            cells = split_cells(row)
            ids = membership_ids(child, cells, headers)
            if len(ids) > 1:
                problems.append(f"{child} has multiple parents: {', '.join(ids)}")
            elif ids:
                parents[child] = ids[0]
    return parents, problems


def collect_subdomain_membership(text: str) -> dict[str, str]:
    """child entity id -> its `SD` subdomain id, from each domain card's `SUBDOMAIN:` line. The
    domain-model analog of the table-based component->subsystem membership, but carried on the card
    (cards are blocks, not table rows), so it is collected here rather than in collect_parents. No-op
    (returns ``{}``) when no card carries a SUBDOMAIN line, so ungrouped domain models are unaffected."""
    return {c.id: c.subdomain for c in iter_domain_cards(text.splitlines()) if c.subdomain}


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


def check_altitude_hints(text: str) -> list[str]:
    """Advisory (non-blocking): a T1 component whose **Purpose** lists many sub-units — `>= _ALTITUDE_MIN`
    bare lowercase identifier names like `twitch, youtube, reddit, …` — is usually a GROUP wearing a
    component's hat. Suggest promoting it to a subsystem so its members get their own drill level. Only
    the Purpose cell is inspected (found from the T1 header), so a `Depends on` cell — IDs *or*
    snake_case dep names — never trips it; bare-identifier matching also skips prose (multi-word
    clauses)."""
    out: list[str] = []
    purpose_col: int | None = None  # index of the 'Purpose' cell in the current table, or None outside one
    for line in text.splitlines():
        cells = line.split("|")
        if len(cells) > 2 and any(c.strip().lower() == "purpose" for c in cells):  # a table header with a Purpose column
            purpose_col = next(i for i, c in enumerate(cells) if c.strip().lower() == "purpose")
            continue
        if not line.lstrip().startswith("|"):  # left the table (blank line / prose / heading)
            purpose_col = None
            continue
        m = re.match(r"\|\s*\*\*(C\d+)\*\*\s*\|", line)  # a component DEFINITION row (id alone in cell 1)
        if not m or purpose_col is None or purpose_col >= len(cells):
            continue
        n = sum(1 for s in (seg.strip() for seg in cells[purpose_col].split(",")) if _LIST_ITEM.match(s))
        if n >= _ALTITUDE_MIN:
            out.append(f"Component {m.group(1)} lists {n} sub-units in its Purpose — if these are real "
                       f"units, consider promoting {m.group(1)} to a subsystem (its members then get "
                       f"their own drill level)")
    return out


_COMPRESSION_MIN = 8      # this many sibling source subdirs folded into ~one box reads as lost signal
_ABSENT_MIN_FILES = 25    # a top-level dir this large with nothing referenced is a likely unmapped module
# Conventional NON-PRODUCT directory basenames an absent-module warning must not nag about: test trees
# have their own Test-completeness section, and `internal/`/`docs/`-style dirs are deliberately unmapped.
# (Some are also walk-excluded already; listed here so the skip is explicit and self-documenting.)
_NON_PRODUCT_DIRS = frozenset({
    "tests", "test", "e2e", "internal", "docs", "__pycache__", "node_modules", ".git",
})
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


def _map_referenced_paths(text: str, root: Path) -> set[str]:
    """Repo-relative paths (files AND dirs) the map points at — markdown link targets + inline paths,
    kept only when they actually exist under root."""
    cands: set[str] = set(_REF_LINK.findall(text)) | set(_REF_INLINE.findall(text))
    rootstr = str(root)
    refs: set[str] = set()
    for c in cands:
        c = c.split("#", 1)[0].strip()
        if c.startswith("file://"):
            c = c[7:]
        if c.startswith(rootstr):
            c = c[len(rootstr):]
        c = c.strip("/")
        if c and not c.startswith(".coyodex") and (root / c).exists():
            refs.add(c)
    return refs


def check_compression_coverage(text: str, root: Path) -> list[str]:
    """Advisory (non-blocking, opt-in via --check-coverage): the map-fidelity counterpart to the
    referential checks. Flags two *lost-signal* shapes by RE-MEASURING the repo tree (never reading
    the pre-index's JSON — GR4):
      - peer-level COMPRESSION — a top/second-level directory whose many sibling source subdirs are
        folded into ~one map box (the 65-plugins-as-one-component failure). Only top/second level,
        because a leaf component's internal subdirs are SUPPOSED to be abstracted (GR6).
      - significant ABSENT modules — a top-level dir with many source files that the map never
        references at all.
    Both self-report their denominator. Intentional abstraction is a feature, so this only ever
    WARNS, never blocks (GR6)."""
    root = root.resolve()
    return compression_coverage_from_refs(_map_referenced_paths(text, root), root)


def compression_coverage_from_refs(refs: set[str], root: Path) -> list[str]:
    """The coverage measurement itself, from an already-extracted set of repo-relative referenced
    paths — shared by the markdown path above and the schema-v2 model path (`validate_model`), so
    the two pipelines measure compression/absence identically."""
    # Local import: keep the CORE GATE independent of the advisory pre-index module — the validator
    # imports nothing from it at load time, only this opt-in check pulls the shared (stdlib) walk
    # helper. Reuses CODE, never the pre-index's JSON DATA (GR4: generation != verification).
    from coyodex.preindex_lib import iter_source_files

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

    out: list[str] = []
    flagged: set[str] = set()
    for dpath, subs in sorted(dir_children.items()):
        n = len(subs)
        if dpath == "." or not _fold_depth_ok(dpath) or n < _COMPRESSION_MIN or not covered_under(dpath):
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
                or dpath.rsplit("/", 1)[-1] in _NON_PRODUCT_DIRS):  # skip test / internal / docs trees
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


def find_glued_ids(text: str) -> set[str]:
    """IDs whose definition row glued the name into the ID cell — either outside the bold
    (`| **UC1** Search… |`) or inside it (`| **C8 Upstream** |`). Such a row is not a clean
    definition, so the id reads as undefined elsewhere — this lets the report name the real
    cause instead of the generic 'undefined ID'."""
    out: set[str] = set()
    for line in text.splitlines():
        for pat in (GLUED_DEF, GLUED_DEF_INNER):
            m = pat.match(line)
            if m:
                out.add(m.group(1))
    return out


# An ID-SHAPED token with a TRAILING suffix: a legal prefix + digits + extra word chars (`S12a`, `C3b`,
# `SD2x`). The schema's IDs are prefix+digits ONLY, so ID_TOKEN needs a word boundary right after the
# digits — such a token matches NO id and is silently ignored. Multi-letter prefixes (`UC/GP/SD`) lead
# the alternation so `SD2x` is read as `SD`+`2x`, never `S`+`D2x`.
MALFORMED_ID = re.compile(r"\b(?:UC|GP|SD|C|D|E|S)\d+[A-Za-z_]\w*\b")
_BOLD_CELL = re.compile(r"\*\*\s*([^*|]+?)\s*\*\*")  # a `**…**` cell's inner text


def check_malformed_ids(text: str) -> list[str]:
    """Flag an ID-shaped token with a trailing suffix (`S12a`) sitting in an ID POSITION — a table
    row's first bold cell (a definition) or a `Subsystem` / `Parent` membership cell. Schema IDs are a
    prefix + digits ONLY, so `S12a` matches no id and is SILENTLY dropped: the definition creates no
    node, and every membership cell pointing at it resolves to no parent (the real mcpolis failure — a
    frontend split into `S12a..S12e` sub-subsystems left `S12` an empty box with 27 orphaned
    components). Scanned only in ID positions, never prose, so an `E2E` / `S3` token in a sentence is
    never flagged. Blocks the build — a malformed id is never intentional and loses data with no other
    trace (it is invisible even to the undefined-reference check, which never sees it as a token)."""
    defined_at: dict[str, int] = {}           # malformed token -> 1-based definition line
    referenced_by: dict[str, list[str]] = {}  # malformed token -> ids whose membership cell points at it
    for start, block in iter_pipe_runs(text.splitlines()):
        if not block:
            continue
        headers = [c.lower() for c in split_cells(block[0])]
        member_cols = [headers.index(h) for h in ("subsystem", "parent") if h in headers]
        # Only an ID-DEFINING table (some row's first cell is a VALID id) can hold a malformed id
        # definition. A Glossary / Roles table has bold TERMS in its first cell (`**E2B**`, `**Sandbox**`)
        # that are not ids — never scan those for a malformed-id definition (the E2B false-positive).
        is_id_table = any(DEF_BOLD.match(r) for r in block)
        for offset, row in enumerate(block):
            if is_separator_row(row):
                continue
            cells = split_cells(row)
            if not cells:
                continue
            # (a) definition position: the WHOLE first cell is `**<token>**`, in an id-defining table
            fm = _BOLD_CELL.fullmatch(cells[0].strip())
            if is_id_table and fm and MALFORMED_ID.fullmatch(fm.group(1).strip()):
                defined_at.setdefault(fm.group(1).strip(), start + offset + 1)
            # (b) membership position: a Subsystem / Parent cell value (skipped when the column is a
            # subsystem row's own NAME — a name never matches the prefix+digits shape anyway)
            cm = DEF_BOLD.match(row)
            child = cm.group(1) if cm else (fm.group(1).strip() if fm else "?")
            for ci in member_cols:
                if ci < len(cells):
                    for tok in MALFORMED_ID.findall(cells[ci]):
                        referenced_by.setdefault(tok, []).append(child)
    problems: list[str] = []
    for tok in sorted(set(defined_at) | set(referenced_by)):
        where: list[str] = []
        if tok in defined_at:
            where.append(f"defined at line {defined_at[tok]}")
        refs = referenced_by.get(tok, [])
        if refs:
            shown = ", ".join(refs[:8]) + (f", +{len(refs) - 8} more" if len(refs) > 8 else "")
            where.append(f"referenced by {shown}")
        pm = re.match(r"UC|GP|SD|C|D|E|S", tok)
        prefix = pm.group(0) if pm else tok
        problems.append(
            f"Malformed ID '{tok}' ({'; '.join(where)}): schema IDs are a prefix + digits only "
            f"(e.g. {prefix}13, not {tok}) — this token matches no ID, so it is silently ignored (its "
            f"definition defines nothing; a membership cell pointing at it gets no parent). Use a "
            f"numeric ID and nest via the Parent column, not a letter suffix."
        )
    return problems


def check_table_runs(text: str) -> list[str]:
    """Catch a table SILENTLY SPLIT by an injected non-pipe line (HTML comment, blank line, stray
    prose). The parser and every table check model a markdown table as ONE contiguous run of `|`-lines
    (see schema_v1.iter_pipe_runs). A comment/blank line between the separator and the rows — or
    between two rows — breaks that run into a header+separator with no rows and a detached `|`-block.
    The renderer then
    draws nothing for the orphaned rows, AND the shape/edge/membership checks skip the orphan (its
    block has no separator on line 2), so the loss is invisible: the ids still appear in prose, so the
    undefined-reference check stays green. This lint flags the break itself, so the gate sees exactly
    what would break the render:
      - a single stray `|` line (a lone orphaned row);
      - a multi-line `|` block whose 2nd line is NOT a separator (detached rows / missing separator);
      - a well-formed header+separator table with ZERO data rows (its rows were split away).
    Run on fence-free text. Zero hits on a well-formed map (every run is header + separator + rows)."""
    problems: list[str] = []
    for start, block in iter_pipe_runs(text.splitlines()):
        ln = start + 1
        if len(block) == 1:
            problems.append(
                f"Detached table row at line {ln}: a lone `|` line that is not part of any table "
                f"(`{block[0].strip()[:50]}`) — a comment/blank line likely split it from its table, "
                f"so the renderer drops it"
            )
        elif not is_separator_row(block[1]):
            problems.append(
                f"Detached table rows at line {ln}: a {len(block)}-line `|` block with no separator on "
                f"its 2nd line — its header+separator was split off (HTML comment / blank line between "
                f"the separator and the rows?), so the renderer silently drops all {len(block)} rows"
            )
        elif not [b for b in block[2:] if not is_separator_row(b)]:
            problems.append(
                f"Empty table at line {ln}: header `{block[0].strip()[:50]}` has a separator but ZERO "
                f"data rows — its rows were split away (HTML comment / blank line after the separator?), "
                f"so the renderer draws nothing for this table"
            )
    return problems


def check_table_shape(text: str) -> list[str]:
    """Every row of a markdown table must have the header's column count. A table = a run of
    `|`-lines whose 2nd line is a separator; non-table pipe content is skipped here (the split-table
    case those skipped blocks represent is caught by check_table_runs instead). Catches malformed
    separators and dropped/extra cells that break parsing. Run on fence-free text."""
    problems: list[str] = []
    for start, block in iter_tables(text):
        expected = n_columns(block[0])
        for offset, row in enumerate(block[1:], start=1):
            got = n_columns(row)
            if got != expected:
                what = "separator" if offset == 1 else "row"
                problems.append(
                    f"Table at line {start + 1}: {what} (line {start + offset + 1}) has "
                    f"{got} columns, header has {expected}"
                )
    return problems


def check_edge_verbs(text: str) -> list[str]:
    """Every edge row (one with a From and a To id) must carry a non-empty Verb. A blank Verb
    renders as ``src -->|| dst``: Mermaid drops the edge's label element, which silently misaligns
    the viewer's positional path/label pairing for every later edge in that diagram. Only edge
    tables (header starts From | Verb | To) are inspected, so the check is additive."""
    problems: list[str] = []
    for start, block in iter_tables(text):
        headers = [c.lower() for c in split_cells(block[0])]
        if headers[:3] != ["from", "verb", "to"]:
            continue
        ci = {h: idx for idx, h in enumerate(headers)}
        for offset, row in enumerate(block[2:], start=2):
            if is_separator_row(row):
                continue
            cells = split_cells(row)
            src = ID_TOKEN.search(cells[ci["from"]]) if ci["from"] < len(cells) else None
            dst = ID_TOKEN.search(cells[ci["to"]]) if ci["to"] < len(cells) else None
            if not (src and dst):  # not an edge row (matches what the parser would graph)
                continue
            verb = cells[ci["verb"]].strip() if ci["verb"] < len(cells) else ""
            if not verb:
                problems.append(
                    f"Edge table at line {start + 1}: row (line {start + offset + 1}) "
                    f"{src.group(0)} → {dst.group(0)} has an empty Verb"
                )
    return problems


# A `Where` / anchor cell should be a SOURCE LOCATION (the call site a flow arrow opens). These tell a
# file reference from prose / an off-repo URL.
_LINK_HREF = re.compile(r"\[[^\]]*\]\(([^)]+)\)")        # markdown link -> href
_BARE_PATH = re.compile(r"^\S+\.\w+(?:[:#]L?\d+)?$")      # bare `path.ext` (+ optional :line / #Lnnn)
_URL_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)  # http(s):// etc. — off-repo, not a local file


def _where_href(cell: str) -> str | None:
    """The file href a `Where` / anchor cell points to: a markdown link's target, or the cell itself
    when it is a bare `path.ext[:line]` token. None for an empty / prose / off-repo-URL cell."""
    cell = cell.strip()
    if not cell:
        return None
    m = _LINK_HREF.search(cell)
    if m:
        href = m.group(1).strip()
        return href if href and not _URL_SCHEME.match(href) else None
    return cell if _BARE_PATH.match(cell) else None


def check_edge_where(text: str) -> list[str]:
    """WARN when a backbone edge's `Where` is not a source location — empty, prose, or an off-repo URL
    rather than a `[file](path#Lnnn)` call-site link (or a bare `path:line`). `Where` is the line a flow
    arrow opens, so a bad one is a dead drill-to-code link. Advisory, not blocking (an *inferred* edge
    may lack a precise site; older maps shouldn't break). No-op when an edge table has no `Where`
    column."""
    out: list[str] = []
    for start, block in iter_tables(text):
        headers = [c.lower() for c in split_cells(block[0])]
        if headers[:3] != ["from", "verb", "to"] or "where" not in headers:
            continue
        ci = {h: idx for idx, h in enumerate(headers)}
        for offset, row in enumerate(block[2:], start=2):
            if is_separator_row(row):
                continue
            cells = split_cells(row)
            src = ID_TOKEN.search(cells[ci["from"]]) if ci["from"] < len(cells) else None
            dst = ID_TOKEN.search(cells[ci["to"]]) if ci["to"] < len(cells) else None
            if not (src and dst):
                continue
            where = cells[ci["where"]] if ci["where"] < len(cells) else ""
            if _where_href(where) is None:
                out.append(f"{src.group(0)} → {dst.group(0)} (line {start + offset + 1}): `Where` is not "
                           f"a source location (use a `[file](path#Lnnn)` call-site link)")
    return out


def _anchor_hrefs(text: str) -> list[tuple[str, str]]:
    """(label, href) for every drill-to-code anchor: each backbone edge's `Where`, each table-definition
    row's first link (node files/dirs), and each domain card's SOURCE. Off-repo URLs excluded."""
    out: list[tuple[str, str]] = []
    for _start, block in iter_tables(text):
        headers = [c.lower() for c in split_cells(block[0])]
        ci = {h: idx for idx, h in enumerate(headers)}
        is_edge = headers[:3] == ["from", "verb", "to"]
        for row in block[2:]:
            if is_separator_row(row):
                continue
            cells = split_cells(row)
            if is_edge and "where" in ci:
                src = ID_TOKEN.search(cells[ci["from"]]) if ci["from"] < len(cells) else None
                dst = ID_TOKEN.search(cells[ci["to"]]) if ci["to"] < len(cells) else None
                href = _where_href(cells[ci["where"]]) if ci["where"] < len(cells) else None
                if src and dst and href:
                    out.append((f"{src.group(0)} → {dst.group(0)} `Where`", href))
            elif not is_edge and cells:
                dm = DEF_ID_CELL.search(cells[0])
                lm = _LINK_HREF.search(" ".join(cells))
                if dm and lm and not _URL_SCHEME.match(lm.group(1).strip()):
                    out.append((dm.group(1), lm.group(1).strip()))
    for c in iter_domain_cards(text.splitlines()):
        if c.source and not _URL_SCHEME.match(c.source):
            out.append((c.id, c.source))
    return out


def _source_roots(map_path: Path, repo_root: Path | None = None) -> list[Path]:
    """The roots a map's SOURCE / anchor paths resolve against. By default the map's own dir and its
    parent (the repo root for a `.coyodex/` map). An explicit `repo_root` (the `--repo` flag) is tried
    FIRST — a map validated from outside its repo (e.g. an eval's deep run dir) resolves its
    repo-root-relative anchors against the real tree; the map-derived roots stay as fallback so
    in-repo behavior is unchanged. Shared by every repo-reading check so this resolution rule lives in
    one place (and survives the JSON move — the rule is about anchors, not the markdown)."""
    base = map_path.resolve().parent
    roots = [base, base.parent]
    if repo_root is not None:
        roots.insert(0, repo_root.resolve())
    return roots


def _resolve_source_file(source: str, roots: list[Path]) -> Path | None:
    """The real file a card's SOURCE points at — its `#Lnnn` anchor stripped, resolved against
    `roots`. None when it doesn't resolve (a placeholder, or a run outside the repo), so a repo-reading
    check skips it instead of false-flagging."""
    rel = source.split("#", 1)[0]
    return next((r / rel for r in roots if (r / rel).is_file()), None)


def check_anchor_existence(text: str, map_path: Path, repo_root: Path | None = None) -> list[str]:
    """WARN on a drill-to-code anchor whose path doesn't resolve to a real file/dir in the repo — a
    moved / renamed / mistyped `file:line` (an edge `Where`, a node anchor, a card SOURCE). Opt-in
    (`--check-sources`): it reads the analyzed repo, so run it on a real `.coyodex/` map, not a template
    (where every path is a placeholder); pass `repo_root` (`--repo`) when the map is validated from
    outside its repo. Advisory — never blocks."""
    roots = _source_roots(map_path, repo_root)
    out: list[str] = []
    for label, href in _anchor_hrefs(text):
        rel = re.sub(r":\d+$", "", href.split("#", 1)[0])   # drop a #Lnnn anchor and a :line suffix
        is_dir = rel.endswith("/")
        rel = rel.rstrip("/")
        if not rel:
            continue
        ok = any((r / rel).is_dir() if is_dir else (r / rel).is_file() for r in roots)
        if not ok:
            out.append(f"{label}: '{href}' does not resolve to a {'directory' if is_dir else 'file'} "
                       f"in the repo")
    return out


def check_domain_cards(text: str) -> tuple[list[str], list[str]]:
    """T5 domain-card checks (no-op when there are no cards): each card has MEANING / SOURCE /
    FIELDS; every field has a type; every RELATIONS item is well-formed; a relation pair is declared
    on one side only. Card-id uniqueness and target resolution ride the generic duplicate / undefined
    reference checks in main(). See method/domain-cards.md.

    Returns ``(problems, warnings)``. Problems fail the build; warnings are advisory — currently the
    completeness nudge: an *association* with no backing field and no `{how}` note draws nothing on
    the canvas and explains nothing in the panel, so it tells the reader nothing about how the link
    is implemented. Author wants either an `FK→` marker on the implementing field or a `{how}` note."""
    problems: list[str] = []
    warnings: list[str] = []
    directed: set[tuple[str, str]] = set()
    cards = list(iter_domain_cards(text.splitlines()))
    # (name, type, fk_targets) per card id — so a relation's backing can be resolved across both cards.
    backing: dict[str, list[tuple[str, str, set[str]]]] = {
        c.id: [(f.name, f.type, fk_targets(f.markers)) for f in c.fields] for c in cards
    }
    for c in cards:
        # A heading that matches `**En —` but not the full shape silently drops the name + store
        # (they fall back to the id) — catch it loudly instead of rendering `E1 · E1`.
        if not c.heading_ok:
            problems.append(f"Domain card {c.id} heading is malformed — expected `**{c.id} — Name** *(store)*`")
        if not c.meaning:
            problems.append(f"Domain card {c.id} is missing a MEANING line")
        if not c.source:
            problems.append(f"Domain card {c.id} is missing a SOURCE link")
        if not c.fields:
            problems.append(f"Domain card {c.id} has no FIELDS")
        for f in c.fields:
            if not f.type:
                problems.append(f"Domain card {c.id} field '{f.name}' has no type")
        seen_pairs: set[tuple[str, str]] = set()
        for r in c.relations:
            if not r.ok:
                msg = f"Domain card {c.id} has a malformed RELATIONS item: '{r.raw}'"
                # The common trap: a LONE cardinality token (`contains 0..1 E2`). Cardinality is a
                # PAIR `sc→dc` (both sides or neither), so a single token leaves no `→` and the item
                # fails to parse. Name that exact cause, mirroring the alias-error hint style.
                if ("→" not in r.raw and "->" not in r.raw
                        and any(tok in ALLOWED_CARDINALITY for tok in r.raw.split())):
                    msg += (" — cardinality must be a pair `sc→dc`, e.g. `contains 1→0..1 E12` "
                            "(not a single token)")
                problems.append(msg)
                continue
            if r.verb.lower() in REL_ALIAS:
                problems.append(
                    f"Domain card {c.id}: relation verb '{r.verb}' is a non-canonical alias — "
                    f"use '{REL_ALIAS[r.verb.lower()]}'"
                )
            if (r.verb, r.target) in seen_pairs:
                problems.append(f"Domain card {c.id} declares the relation '{r.verb} … {r.target}' twice")
            seen_pairs.add((r.verb, r.target))
            directed.add((c.id, r.target))
            # Completeness nudge — only for associations (a structural marker / embedding already
            # conveys composition/aggregation/inheritance). A defined target is required to judge it.
            if r.kind == "association" and r.target in backing and not r.how:
                name, _side = resolve_backing(c.id, r.target, backing[c.id], backing[r.target])
                if name is None:
                    warnings.append(
                        f"Domain card {c.id}: relation '{r.verb} … {r.target}' is not backed by a field "
                        f"and has no {{…}} note — mark the implementing field `FK→{r.target}` "
                        f"(or `FK→{c.id}` on {r.target}), or add a `{{how}}` note explaining the link"
                    )
    for a, b in directed:
        if a < b and (b, a) in directed:
            problems.append(
                f"Relation between {a} and {b} is declared on both cards — author it on one side only"
            )
    return problems, warnings


def check_entity_sources(text: str, map_path: Path, repo_root: Path | None = None) -> list[str]:
    """Flag a domain card whose entity name has NO identifier token present in its SOURCE file — a
    strong signal it's synthesized (no real named type) or anchored to the wrong file. Tokens are any
    identifier-shaped run (CamelCase, snake_case, or lowercase — not just CamelCase), matched
    case-insensitively by *substring*, not whole-word, on purpose: it must tolerate an abbreviated
    card name (`ServiceToken` ⊂ `class ServiceTokenRecord`), a compound card (`DiscoveredResource /
    DiscoveredPrompt` — either token suffices), a descriptive suffix (`Settings (app env)` →
    `class Settings`), and a non-CamelCase name (`oauth_state`), while still catching a name that
    appears nowhere (`OAuthState`). The SOURCE path is resolved against the map's dir and its parent
    (the repo root for a `.coyodex/` map); a card whose file can't be resolved is skipped, so this
    stays safe on templates/fixtures. Opt-in (`--check-sources`) — it reads the analyzed repo's
    source, a deliberate departure from map-only validation. `repo_root` (`--repo`) is tried first
    when given (a map validated from outside its repo)."""
    problems: list[str] = []
    roots = _source_roots(map_path, repo_root)
    for c in iter_domain_cards(text.splitlines()):
        if not c.source or not c.heading_ok or c.name == c.id:
            continue  # no anchor, or a malformed heading already flagged — nothing reliable to check
        rel = c.source.split("#", 1)[0]
        src = _resolve_source_file(c.source, roots)
        if src is None:
            continue  # file not resolvable (placeholder / run outside the repo) — skip, don't false-flag
        try:
            code = src.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        tokens = re.findall(r"[A-Za-z_]\w{2,}", c.name)  # identifier tokens (CamelCase / snake_case / lowercase)
        if tokens and not any(tok.lower() in code for tok in tokens):
            problems.append(
                f"Domain card {c.id} '{c.name}' is not defined in its SOURCE ({rel}) — likely "
                f"synthesized or a wrong anchor; entities must be real named types"
            )
    return problems


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
    substring match `check_entity_sources` uses to ground an entity in its file, run in reverse: an
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


def check_domain_coverage(text: str, map_path: Path, repo_root: Path | None = None) -> list[str]:
    """Advisory (non-blocking, opt-in via --check-coverage): independently catch an UNDER-HARVESTED
    domain model — the thin-domain regression a directory-sliced harvest produces when no agent owns
    the T5 card slice — regardless of how the map was produced. Two sub-checks:

      (a) Relation-isolated entities (map-only): entity cards with ZERO E↔E relation (neither a
          RELATIONS line they declare nor one targeting them). A sparse class graph shows up here
          directly; warn when a material share of the model is isolated.
      (b) Domain-type coverage vs the real code (repo read, the independent re-measurement): the
          named Python types in the entities' OWN source dirs that no entity card represents. Types
          are re-extracted with stdlib `ast` (top-level ClassDef — dataclasses/enums are ClassDefs
          too); NON-ENTITY types (plumbing suffixes like `*Repository`, `ABC`/`Protocol` bases — see
          `_is_non_entity_type`) are excluded before counting, so a repository/provider-heavy dir is
          not read as an under-modelled domain; non-`.py` files are skipped (full multi-language symbol
          extraction is the pre-index's job, not this stdlib check), and like every coverage check it
          re-measures the tree and never reads the pre-index JSON (GR4). A no-op when no SOURCE file
          resolves (a template / a map run outside its repo / sources under a backup dir); pass
          `repo_root` (`--repo`) when the map is validated from outside its repo.

    No-op when the map has no domain cards."""
    cards = list(iter_domain_cards(text.splitlines()))
    if not cards:
        return []
    out: list[str] = []

    # (a) Relation-isolated entities — the undirected set of E-ids touched by ANY ok relation.
    related: set[str] = set()
    for c in cards:
        for r in c.relations:
            if r.ok:
                related.add(c.id)
                related.add(r.target)
    ids = [c.id for c in cards]
    isolated = [i for i in ids if i not in related]
    n = len(ids)
    if (n >= _ISOLATED_MIN_ENTITIES and len(isolated) >= _ISOLATED_MIN
            and len(isolated) > _ISOLATED_FRACTION * n):
        out.append(
            f"Isolated entities: {len(isolated)} of {n} entity cards have NO E↔E relation "
            f"({round(100 * len(isolated) / n)}% of the domain model) — a sparse class graph is the "
            f"signature of an under-harvested domain model (did one T5 harvest agent author per-entity "
            f"RELATIONS?): {', '.join(isolated[:_COVERAGE_SAMPLE])}"
            + (f", +{len(isolated) - _COVERAGE_SAMPLE} more" if len(isolated) > _COVERAGE_SAMPLE else "")
        )

    # (b) Domain-type coverage — re-extract named types from the .py files in the entities' source
    # dirs and compare to the entity names. STDLIB ONLY: Python types via `ast`; non-Python files in a
    # domain dir are skipped here (the pre-index does multi-language symbol extraction, this does not).
    roots = _source_roots(map_path, repo_root)
    domain_dirs: set[Path] = set()
    for c in cards:
        if c.source:
            src = _resolve_source_file(c.source, roots)
            if src is not None:
                domain_dirs.add(src.parent)
    types: dict[str, Path] = {}  # type name -> first file it was seen in
    for d in sorted(domain_dirs):
        for f in sorted(d.glob("*.py")):
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
            except (OSError, SyntaxError, ValueError):
                continue  # an unreadable / unparseable file is not counted (never a silent miscount)
            for node in tree.body:  # top-level ClassDefs only (a nested helper class is not an entity)
                if isinstance(node, ast.ClassDef) and not _is_non_entity_type(node):
                    types.setdefault(node.name, f)
    if types:
        entity_names = [c.name for c in cards if c.name != c.id]
        uncovered = sorted(t for t in types if not _type_covered(t, entity_names))
        if len(uncovered) >= _UNCOVERED_MIN and len(uncovered) >= _UNCOVERED_FRACTION * len(types):
            shown = ", ".join(uncovered[:_COVERAGE_SAMPLE]) + (
                f", +{len(uncovered) - _COVERAGE_SAMPLE} more" if len(uncovered) > _COVERAGE_SAMPLE else "")
            out.append(
                f"Under-harvested domain model: {len(uncovered)} of {len(types)} named types in the "
                f"entities' source dirs have no entity card (possible under-harvested domain model; "
                f"Python types only, measured at validate time): {shown}"
            )
    return out


def collect_edges(text: str) -> list[tuple[str, str, str]]:
    """All `(src_id, verb_lower, dst_id)` from the backbone edge tables (header `From | Verb | To`).
    Shared by the completeness nudges (C→E ownership, orphan deps). Empty when there is no edge list."""
    out: list[tuple[str, str, str]] = []
    for _start, block in iter_tables(text):
        headers = [c.lower() for c in split_cells(block[0])]
        if headers[:3] != ["from", "verb", "to"]:
            continue
        ci = {h: idx for idx, h in enumerate(headers)}
        for row in block[2:]:
            if is_separator_row(row):
                continue
            cells = split_cells(row)
            src = ID_TOKEN.search(cells[ci["from"]]) if ci["from"] < len(cells) else None
            dst = ID_TOKEN.search(cells[ci["to"]]) if ci["to"] < len(cells) else None
            verb = cells[ci["verb"]].strip().lower() if ci["verb"] < len(cells) else ""
            if src and dst:
                out.append((src.group(0), verb, dst.group(0)))
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # --repo <root>: resolve anchors + coverage against this repo root (a map validated from outside
    # its repo). Parsed FIRST — its VALUE is a bare path that must not be read as the map argument.
    repo_root: Path | None = None
    if "--repo" in argv:
        i = argv.index("--repo")
        if i + 1 >= len(argv):
            print("ERROR: --repo needs a path (the analyzed repo's root)", file=sys.stderr)
            return 2
        repo_root = Path(argv[i + 1])
        del argv[i:i + 2]
        if not repo_root.is_dir():
            print(f"ERROR: --repo {repo_root} is not a directory", file=sys.stderr)
            return 2
    args = [a for a in argv if not a.startswith("-")]
    check_sources = "--check-sources" in argv  # opt-in: read SOURCE files to flag synthesized entities
    check_coverage = "--check-coverage" in argv  # opt-in: re-walk the repo to flag map-fidelity gaps
    path = Path(args[0] if args else ".coyodex/project-map.md")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    raw = path.read_text(encoding="utf-8")
    # Fail fast on an unterminated code fence: strip_fences would blank everything after it, so EVERY
    # downstream check runs on truncated text and silently misses the swallowed half of the map. Report
    # just this — no other finding is trustworthy until the fence is closed.
    fence_line = unterminated_fence_line(raw)
    if fence_line is not None:
        print("\nVALIDATION FAILED:")
        print(f"  - Unterminated code fence opened at line {fence_line} (``` or ~~~) — it has no "
              "closing fence, so every table, definition, and GP step after it is treated as code "
              "and silently dropped from the parse and the diagram. Close the fence.")
        return 1
    # Parse from fence-free text: verbatim examples inside ``` code fences (Mermaid, shell, a
    # teaching example of a malformed table) are not live content — don't read them as tables,
    # definitions, or references.
    text = strip_fences(raw)
    problems, warnings = validate_map(
        text, path, check_sources=check_sources, check_coverage=check_coverage, repo_root=repo_root)
    _print_report(text, problems, warnings)
    return 1 if problems else 0


def _print_report(text: str, problems: list[str], warnings: list[str]) -> None:
    """Print the element inventory, advisory warnings, and the PASS/FAIL verdict for `coyodex validate`.
    Presentation only — it reads the (problems, warnings) `validate_map` produced and runs no checks."""
    defined_counts, _ = collect_defined(text)
    by_prefix: dict[str, list[str]] = {}
    for i in set(defined_counts):
        m = re.match(r"[A-Z]+", i)
        pre = m.group(0) if m else i
        by_prefix.setdefault(pre, []).append(i)
    inventory = ", ".join(f"{pre}:{len(v)}" for pre, v in sorted(by_prefix.items()))
    print(f"Inventory — {inventory}")
    if warnings:
        print("\nVALIDATION WARNINGS (non-blocking):")
        for w in warnings:
            print(f"  - {w}")
    if problems:
        print("\nVALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        return
    print("Schema v1: OK — all IDs defined once, all references resolve, every GP step names a use "
          "case, every flow step well-formed.")


def validate_map(text: str, map_path: Path | None = None, *, check_sources: bool = False,
                 check_coverage: bool = False,
                 repo_root: Path | None = None) -> tuple[list[str], list[str]]:
    """Run every schema-v1 check over already-fence-stripped map `text` and return (problems, warnings):
    blocking `problems` mean the map is NOT well-formed; `warnings` are advisory. This is the shared
    orchestration the CLI `main` formats and the eval profiler scores — one implementation, one parse,
    so validation and scoring can never drift. `map_path` is needed only for the file-reading opt-ins
    (`check_sources`, `check_coverage`); pass it whenever either is set. `repo_root` (the `--repo`
    flag) makes anchors + coverage resolve against that repo root FIRST — for a map validated from
    outside its repo (an eval run dir); omitted, behavior is unchanged (map dir + its parent)."""
    if (check_sources or check_coverage) and map_path is None:
        raise ValueError("map_path is required when check_sources or check_coverage is set")
    defined_counts, gp_order = collect_defined(text)
    defined = set(defined_counts)
    referenced = collect_referenced(text)
    parents, parent_problems = collect_parents(text)            # table memberships: C->S, S->S, SD->SD
    subdomain_parents = collect_subdomain_membership(text)      # card memberships: E->SD
    all_parents = {**parents, **subdomain_parents}              # one forest set for the hierarchy walk
    # Grouping (subsystems) / subdomains are "present" only if their element is defined OR some
    # membership points at one. When absent, stray S-/SD-tokens (prose "S3" / AWS S3) are ignored, so
    # an ungrouped map stays byte-for-byte additive. `SD` starts with `S`, so subsystem checks use
    # _is_subsystem_id to exclude subdomains — never a bare `startswith("S")` (it would catch `SD` too).
    grouping_present = (any(_is_subsystem_id(i) for i in defined)
                        or any(_is_subsystem_id(p) for p in all_parents.values()))
    subdomains_present = (any(i.startswith("SD") for i in defined)
                          or any(p.startswith("SD") for p in all_parents.values()))

    problems: list[str] = []
    warnings: list[str] = []

    duplicates = sorted(i for i, n in defined_counts.items() if n > 1 and not i.startswith("GP"))
    if duplicates:
        problems.append(f"Duplicate element definitions: {', '.join(duplicates)}")

    def _suppress_ref(r: str) -> bool:
        if r.startswith("SD"):  # checked BEFORE "S": a subdomain id starts with "S"
            return not subdomains_present
        if r.startswith("S"):
            return not grouping_present
        return False
    ref_to_check = {r for r in referenced if not _suppress_ref(r)}
    unresolved = sorted(ref_to_check - defined)
    if unresolved:
        glued = find_glued_ids(text)
        glued_unresolved = [u for u in unresolved if u in glued]
        truly_undefined = [u for u in unresolved if u not in glued]
        if glued_unresolved:
            problems.append(
                "Definition rows with text glued into the ID cell — put the ID alone in the "
                f"first cell (e.g. `| **UC1** | name… |`): {', '.join(glued_unresolved)}"
            )
        if truly_undefined:
            problems.append(f"References to undefined IDs: {', '.join(truly_undefined)}")

    missing_uc = check_gp_use_cases(text, gp_order)
    if missing_uc:
        problems.append(f"Golden Path steps missing a `*(UCn)*` use-case tag: {', '.join(missing_uc)}")

    problems.extend(check_flow_steps(text, collect_role_names(text)))
    problems.extend(check_roles_kind(text))
    problems.extend(check_dep_kinds(text))
    problems.extend(check_malformed_ids(text))  # an id-shaped token with a suffix (`S12a`) — silently dropped
    problems.extend(check_table_runs(text))   # a table split by a comment/blank line (silent row loss)
    problems.extend(check_table_shape(text))
    problems.extend(check_edge_verbs(text))
    warnings.extend(check_edge_where(text))   # advisory: an edge `Where` that isn't a source location
    domain_problems, domain_warnings = check_domain_cards(text)
    problems.extend(domain_problems)
    warnings.extend(domain_warnings)
    if check_sources:
        assert map_path is not None  # guaranteed by the guard above when check_sources is set
        problems.extend(check_entity_sources(text, map_path, repo_root))
        warnings.extend(check_anchor_existence(text, map_path, repo_root))  # advisory: anchors that don't resolve to a real file/dir

    # Grouping checks — additive, no-op when there is no Subsystem/Parent column or SUBDOMAIN line.
    problems.extend(parent_problems)
    hierarchy_problems, hierarchy_warnings = check_hierarchy(all_parents, defined)
    problems.extend(hierarchy_problems)
    warnings.extend(hierarchy_warnings)
    warnings.extend(check_altitude_hints(text))  # advisory: a component that is really a group
    if check_coverage:  # opt-in map-fidelity: peer-level compression + absent modules (re-measured, GR4)
        assert map_path is not None  # guaranteed by the guard above when check_coverage is set
        # The tree to re-walk: the explicit --repo root when given, else the map's grandparent (the
        # repo root for an in-repo `.coyodex/` map — the historical behavior, unchanged without --repo).
        walk_root = repo_root if repo_root is not None else map_path.resolve().parent.parent
        warnings.extend(check_compression_coverage(text, walk_root))
        warnings.extend(check_domain_coverage(text, map_path, repo_root))  # under-harvested domain model (item 2)
    # Non-blocking nudge: a group whose ONLY child is another group of the same kind is a redundant
    # nesting level (it adds depth without grouping anything). Only nested maps can trigger it, so flat
    # maps stay silent.
    child_count: dict[str, int] = {}
    only_child: dict[str, str] = {}
    for c, p in all_parents.items():
        child_count[p] = child_count.get(p, 0) + 1
        only_child[p] = c  # used only when count==1, where it is the single child
    redundant = sorted(
        p for p, n in child_count.items() if n == 1
        and ((_is_subsystem_id(p) and _is_subsystem_id(only_child[p]))
             or (p.startswith("SD") and only_child[p].startswith("SD")))
    )
    if redundant:
        warnings.append("Groups whose only child is another group of the same kind (redundant nesting "
                        f"level): {', '.join(redundant)}")

    def _is_component(i: str) -> bool:  # a component id (no other prefix starts with "C" now)
        return i.startswith("C")

    # Loud guard against silent grouping failures: a Subsystems table with NO component actually
    # assigned is almost always a missing/unreadable membership column (which renders disconnected
    # subsystem boxes), not an intentional choice. Fail rather than pass green. (`SD` starts with `S`,
    # so subsystem membership is tested with _is_subsystem_id, never a bare `startswith("S")`.)
    if (any(_is_subsystem_id(i) for i in defined) and any(_is_component(i) for i in defined)
            and not any(_is_component(c) and _is_subsystem_id(p) for c, p in all_parents.items())):
        problems.append(
            "Subsystems (S) defined but no component is assigned to one — the T1 'Subsystem' "
            "membership column is missing or unreadable"
        )
    # Non-blocking nudge: a LEAF subsystem with no members (no component assigned, and not the parent
    # of another subsystem) is empty — its box renders with nothing inside. Usually a membership that
    # pointed at a malformed / typo'd id (the `S12a` class flagged above) or a leftover. Mirrors the
    # "Subdomains with no entities" nudge. Gated on SOME subsystem having a component, so the all-
    # ungrouped case (already the blocking guard above) is not double-reported.
    assigned_s = {p for c, p in all_parents.items() if _is_component(c) and _is_subsystem_id(p)}
    if assigned_s:
        parent_s = {p for c, p in all_parents.items() if _is_subsystem_id(c) and _is_subsystem_id(p)}
        empty_s = sorted(i for i in defined if _is_subsystem_id(i) and i not in assigned_s and i not in parent_s)
        if empty_s:
            warnings.append("Subsystems with no members (empty box — no component assigned, no child "
                            f"subsystem): {', '.join(empty_s)}")
    # Same guard for the domain model: a Subdomains table with NO entity assigned is almost always
    # missing `SUBDOMAIN:` lines (disconnected subdomain boxes), not an intentional choice.
    entities_defined = any(i.startswith("E") for i in defined)
    if (any(i.startswith("SD") for i in defined) and entities_defined
            and not any(c.startswith("E") for c in subdomain_parents)):
        problems.append(
            "Subdomains (SD) defined but no entity is assigned to one — a domain card's `SUBDOMAIN:` "
            "line is missing"
        )
    # Non-blocking nudge: once SOME entities carry a subdomain, list any that don't — they render
    # ungrouped / top-level (valid), like an ungrouped component.
    if subdomains_present and any(c.startswith("E") for c in subdomain_parents):
        ungrouped = sorted(i for i in defined if i.startswith("E") and i not in subdomain_parents)
        if ungrouped:
            warnings.append(f"Entities with no SUBDOMAIN (ungrouped / top-level): {', '.join(ungrouped)}")
    # Non-blocking nudge: a LEAF subdomain with no member entities (not assigned any entity, and not a
    # parent of another subdomain) is empty — its diagram shows only a placeholder. Usually a leftover
    # or a typo'd `SUBDOMAIN:` id. (Non-leaf parent subdomains legitimately have no direct members.)
    assigned_sd = set(subdomain_parents.values())
    parent_sd = {p for c, p in all_parents.items() if c.startswith("SD")}
    empty_sd = sorted(i for i in defined if i.startswith("SD") and i not in assigned_sd and i not in parent_sd)
    if empty_sd:
        warnings.append(f"Subdomains with no entities: {', '.join(empty_sd)}")
    edges = collect_edges(text)
    # Non-blocking nudge: once SOME entity has an owning component (a `persists`/`writes` C→E edge), the
    # map is authoring structural ownership — so list aggregate-root entities that still have none, the
    # owners the trace likely missed. Embedded value objects (the target of a contains/has relation,
    # persisted via their container) are exempt. Silent when no C→E ownership is authored at all.
    owned = {d for s, v, d in edges if s.startswith("C") and d.startswith("E") and v in ("persists", "writes")}
    if owned and entities_defined:
        embedded = {r.target for c in iter_domain_cards(text.splitlines())
                    for r in c.relations if r.ok and r.kind in ("composition", "aggregation")}
        unowned = sorted(i for i in defined if i.startswith("E") and i not in owned and i not in embedded)
        if unowned:
            shown = ", ".join(unowned[:12]) + (f", +{len(unowned) - 12} more" if len(unowned) > 12 else "")
            warnings.append(f"Entities with no owning component (no persists/writes C→E edge): {shown}")
    # Non-blocking nudge: a defined external dep (T2) with NO incoming edge is an *un-traced* `C→D`, not
    # an unused dependency — the symptom of a thin edge trace (the C→E-dilution regression). Only fires
    # when the map has an edge list at all, so a map that hasn't traced edges yet isn't nagged.
    if edges:
        targets = {d for _, _, d in edges}
        orphan_deps = sorted(i for i in defined if i.startswith("D") and i not in targets)
        if orphan_deps:
            shown = ", ".join(orphan_deps[:12]) + (f", +{len(orphan_deps) - 12} more" if len(orphan_deps) > 12 else "")
            warnings.append(f"External deps with no incoming edge (un-traced — which component uses each?): {shown}")

    return problems, warnings


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
