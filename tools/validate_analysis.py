#!/usr/bin/env python3
"""Validate project-map.md against the schema-v1 conventions.

Stdlib-only. Checks that the analysis file is a clean machine-parseable source
for diagrams/tooling:

  1. Every element ID (UC/C/D/E/S/GP) is defined exactly once.
  2. Every ID *reference* (Touches lines, traceability tables, edge list,
     Depends-on, Used-in-GP, Subsystem/Parent membership) resolves to a defined ID.
  3. Every Golden Path step (GPn heading) has a `Touches:` line.
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

When an id reads as undefined because its definition row glued extra text into the
ID cell (`| **UC1** Search… |` instead of `| **UC1** | Search… |`), the report names
that specific cause instead of the generic "undefined ID".

Opt-in (reads the analyzed repo's source, not just the map):
  7. --check-sources: each domain card's entity NAME must appear in its SOURCE file — catches
     synthesized entities (a name with no real named type) and wrong anchors.

Exit 0 = clean, 1 = problems found.

Usage:  python3 tools/validate_analysis.py [--check-sources] [.coyodex/project-map.md]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Grammar (regexes, membership rule) lives in schema_v1, shared with the parser — one grammar.
from schema_v1 import (
    DEF_BOLD,
    DEF_ENTITY,
    DEF_GP,
    DEP_KINDS,
    DEEP_NEST_WARN,
    GLUED_DEF,
    GLUED_DEF_INNER,
    ID_TOKEN,
    REL_ALIAS,
    fk_targets,
    is_separator_row,
    iter_domain_cards,
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


def gp_bodies(text: str, gp_order: list[str]) -> list[tuple[str, list[str]]]:
    """(gp_id, body_lines) per GP step — the labeled lines (STORY / Actor / Touches / …) from a GPn
    heading to the NEXT GP heading. Matches the parser's parse_gp step window exactly (build_graph
    reads to the next GP, unbounded), so the validator checks the same span the renderer parses — a
    Touches/Actor line is never validated against a different slice than it is rendered from. One place
    defines the step window, so every GP-body check reads the same lines."""
    lines = text.splitlines()
    heading_idx = {m.group(1): i for i, line in enumerate(lines) if (m := DEF_GP.match(line))}
    out: list[tuple[str, list[str]]] = []
    for gp in gp_order:
        start = heading_idx[gp]
        body: list[str] = []
        for line in lines[start + 1 :]:
            if DEF_GP.match(line):  # same stop condition as parse_gp — to the next GP step
                break
            body.append(line)
        out.append((gp, body))
    return out


def check_gp_touches(text: str, gp_order: list[str]) -> list[str]:
    """Each GPn heading must be followed by a `Touches:` line before the next GP."""
    return [gp for gp, body in gp_bodies(text, gp_order)
            if not any(s.startswith("`Touches:`") or s.startswith("Touches:")
                       for s in (ln.strip() for ln in body))]


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


def check_gp_actors(text: str, gp_order: list[str], role_names: set[str]) -> list[str]:
    """A GP step's optional `Actor:` line must name a defined Role (it sets the diagram's lifeline).
    No-op when no step carries an Actor line; also skipped when the map has no Roles table (nothing
    to resolve against), so the check stays additive."""
    if not role_names:
        return []
    problems: list[str] = []
    for gp, body in gp_bodies(text, gp_order):
        for ln in body:
            s = ln.strip()
            if s.startswith("Actor:"):
                val = re.sub(r"[*`]", "", s[len("Actor:"):]).strip()
                if val and val.lower() not in role_names:
                    problems.append(f"{gp} Actor '{val}' is not a defined Role (Roles table)")
                break
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
                problems.append(f"Domain card {c.id} has a malformed RELATIONS item: '{r.raw}'")
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


def check_entity_sources(text: str, map_path: Path) -> list[str]:
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
    source, a deliberate departure from map-only validation."""
    problems: list[str] = []
    roots = [map_path.resolve().parent, map_path.resolve().parent.parent]
    for c in iter_domain_cards(text.splitlines()):
        if not c.source or not c.heading_ok or c.name == c.id:
            continue  # no anchor, or a malformed heading already flagged — nothing reliable to check
        rel = c.source.split("#", 1)[0]
        src = next((r / rel for r in roots if (r / rel).is_file()), None)
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


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    check_sources = "--check-sources" in sys.argv  # opt-in: read SOURCE files to flag synthesized entities
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

    missing_touches = check_gp_touches(text, gp_order)
    if missing_touches:
        problems.append(f"Golden Path steps missing a Touches: line: {', '.join(missing_touches)}")

    problems.extend(check_gp_actors(text, gp_order, collect_role_names(text)))
    problems.extend(check_roles_kind(text))
    problems.extend(check_dep_kinds(text))
    problems.extend(check_table_runs(text))   # a table split by a comment/blank line (silent row loss)
    problems.extend(check_table_shape(text))
    problems.extend(check_edge_verbs(text))
    domain_problems, domain_warnings = check_domain_cards(text)
    problems.extend(domain_problems)
    warnings.extend(domain_warnings)
    if check_sources:
        problems.extend(check_entity_sources(text, path))

    # Grouping checks — additive, no-op when there is no Subsystem/Parent column or SUBDOMAIN line.
    problems.extend(parent_problems)
    hierarchy_problems, hierarchy_warnings = check_hierarchy(all_parents, defined)
    problems.extend(hierarchy_problems)
    warnings.extend(hierarchy_warnings)
    warnings.extend(check_altitude_hints(text))  # advisory: a component that is really a group
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

    # Summary of the element inventory, by prefix.
    by_prefix: dict[str, list[str]] = {}
    for i in defined:
        m = re.match(r"[A-Z]+", i)
        pre = m.group(0) if m else i
        by_prefix.setdefault(pre, []).append(i)
    inventory = ", ".join(
        f"{pre}:{len(v)}" for pre, v in sorted(by_prefix.items())
    )
    print(f"Inventory — {inventory}")

    if warnings:  # advisory only — printed whether or not the build passes; never changes the exit code
        print("\nVALIDATION WARNINGS (non-blocking):")
        for w in warnings:
            print(f"  - {w}")

    if problems:
        print("\nVALIDATION FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Schema v1: OK — all IDs defined once, all references resolve, every GP step has Touches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
