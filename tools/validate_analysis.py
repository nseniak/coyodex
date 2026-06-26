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
     cycles; nesting depth <= MAX_DEPTH.
  5. Table shape: every row of a markdown table (header / separator / data)
     carries the same column count — catches the malformed-separator / dropped-cell
     class that silently breaks parsing and diagram rendering.
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
    GLUED_DEF,
    GLUED_DEF_INNER,
    ID_TOKEN,
    MAX_DEPTH,
    REL_ALIAS,
    fk_targets,
    iter_domain_cards,
    membership_ids,
    resolve_backing,
    strip_fences,
)


def is_separator_row(row: str) -> bool:
    """A markdown table separator like ``|---|:--:|`` — dashes/colons/pipes/space only."""
    return "-" in row and bool(re.fullmatch(r"[\s|:\-]+", row.strip()))


def split_cells(row: str) -> list[str]:
    r"""Stripped cells of a table row. Escaped pipes (``\|`` — the schema's sanctioned way to put a
    literal pipe inside a cell) are neutralised first so they don't read as column separators."""
    return [c.strip() for c in row.replace(r"\|", "").strip().strip("|").split("|")]


def n_columns(row: str) -> int:
    """Cell count of a table row."""
    return len(split_cells(row))


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
    """(gp_id, body_lines) per GP step — the labeled lines (STORY / Actor / Touches / …) between a
    GPn heading and the next GP (capped at an 8-line window). One place defines the step window, so
    every GP-body check reads the same slice."""
    lines = text.splitlines()
    heading_idx = {m.group(1): i for i, line in enumerate(lines) if (m := DEF_GP.match(line))}
    out: list[tuple[str, list[str]]] = []
    for gp in gp_order:
        start = heading_idx[gp]
        body: list[str] = []
        for line in lines[start + 1 : start + 8]:
            if DEF_GP.match(line):
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
    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        block: list[str] = []
        while i < n and lines[i].lstrip().startswith("|"):
            block.append(lines[i])
            i += 1
        if len(block) < 2 or not is_separator_row(block[1]):
            continue
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
    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        block: list[str] = []
        while i < n and lines[i].lstrip().startswith("|"):
            block.append(lines[i])
            i += 1
        if len(block) < 2 or not is_separator_row(block[1]):
            continue  # not a real table
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
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        block: list[str] = []
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            block.append(lines[i])
            i += 1
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


def collect_context_membership(text: str) -> dict[str, str]:
    """child entity id -> its `CX` context id, from each domain card's `CONTEXT:` line. The
    domain-model analog of the table-based component->subsystem membership, but carried on the card
    (cards are blocks, not table rows), so it is collected here rather than in collect_parents. No-op
    (returns ``{}``) when no card carries a CONTEXT line, so ungrouped domain models are unaffected."""
    return {c.id: c.context for c in iter_domain_cards(text.splitlines()) if c.context}


def _expected_parent_prefix(child: str) -> str:
    """The id-prefix a child's parent must have: entities (`E`) and contexts (`CX`) nest under a
    context (`CX`); components (`C`) and subsystems (`S`) nest under a subsystem (`S`)."""
    return "CX" if child.startswith(("E", "CX")) else "S"


def check_hierarchy(parents: dict[str, str], defined: set[str]) -> list[str]:
    """Parent must be the right KIND for the child (component/subsystem -> `S`; entity/context ->
    `CX`) and defined; no nesting cycles; depth <= MAX_DEPTH. The two forests (component->S and
    entity->CX) share one walk — their id spaces are disjoint, so a chain never crosses between them."""
    problems: list[str] = []
    for child, par in parents.items():
        pfx = _expected_parent_prefix(child)
        if not par.startswith(pfx):
            kind = "context (CX…)" if pfx == "CX" else "subsystem (S…)"
            problems.append(f"{child} parent {par} is not a {kind}")
        elif par not in defined:
            problems.append(f"{child} parent {par} is undefined")
    # Walk only well-formed (right-kind) pointers, so a wrong-type parent reported above does not
    # also surface as a spurious "cycle" line.
    valid = {c: p for c, p in parents.items() if p.startswith(_expected_parent_prefix(c))}
    for start in valid:
        chain, cur, depth = [start], start, 0
        while cur in valid:
            cur = valid[cur]
            depth += 1
            if cur in chain:
                problems.append(f"Nesting cycle: {' -> '.join(chain)} -> {cur}")
                break
            chain.append(cur)
            if depth > MAX_DEPTH:
                problems.append(f"Nesting exceeds depth {MAX_DEPTH}: {' -> '.join(chain)}")
                break
    return problems


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


def check_table_shape(text: str) -> list[str]:
    """Every row of a markdown table must have the header's column count. A table = a run of
    `|`-lines whose 2nd line is a separator; non-table pipe content is skipped (no false
    positives). Catches malformed separators and dropped/extra cells that break parsing.
    Note: a block with NO separator row is treated as non-table and skipped — so a *deleted*
    separator is not caught here (markdown wouldn't render it as a table either); the check
    catches a dropped/added cell in an otherwise-well-formed table. Run on fence-free text."""
    problems: list[str] = []
    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        start = i
        block: list[str] = []
        while i < n and lines[i].lstrip().startswith("|"):
            block.append(lines[i])
            i += 1
        if len(block) < 2 or not is_separator_row(block[1]):
            continue  # not a real table (no separator on the 2nd line)
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
    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        if not lines[i].lstrip().startswith("|"):
            i += 1
            continue
        start = i
        block: list[str] = []
        while i < n and lines[i].lstrip().startswith("|"):
            block.append(lines[i])
            i += 1
        if len(block) < 2 or not is_separator_row(block[1]):
            continue  # not a real table
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


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    check_sources = "--check-sources" in sys.argv  # opt-in: read SOURCE files to flag synthesized entities
    path = Path(args[0] if args else ".coyodex/project-map.md")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    # Parse from fence-free text: verbatim examples inside ``` code fences (Mermaid, shell, a
    # teaching example of a malformed table) are not live content — don't read them as tables,
    # definitions, or references.
    text = strip_fences(path.read_text(encoding="utf-8"))

    defined_counts, gp_order = collect_defined(text)
    defined = set(defined_counts)
    referenced = collect_referenced(text)
    parents, parent_problems = collect_parents(text)            # table memberships: C->S, S->S, CX->CX
    context_parents = collect_context_membership(text)          # card memberships: E->CX
    all_parents = {**parents, **context_parents}                # one forest set for the hierarchy walk
    # Grouping (subsystems) / contexts are "present" only if their element is defined OR some
    # membership points at one. When absent, stray S-/CX-tokens (prose "S3" / AWS S3) are ignored, so
    # an ungrouped map stays byte-for-byte additive. Checked by the parent KIND, never the child id —
    # a context id `CX1` starts with "C" but is not a component.
    grouping_present = any(i.startswith("S") for i in defined) or any(p.startswith("S") for p in all_parents.values())
    contexts_present = any(i.startswith("CX") for i in defined) or any(p.startswith("CX") for p in all_parents.values())

    problems: list[str] = []
    warnings: list[str] = []

    duplicates = sorted(i for i, n in defined_counts.items() if n > 1 and not i.startswith("GP"))
    if duplicates:
        problems.append(f"Duplicate element definitions: {', '.join(duplicates)}")

    def _suppress_ref(r: str) -> bool:
        if r.startswith("CX"):  # checked before "S"/"C": CX is its own prefix
            return not contexts_present
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
    problems.extend(check_table_shape(text))
    problems.extend(check_edge_verbs(text))
    domain_problems, domain_warnings = check_domain_cards(text)
    problems.extend(domain_problems)
    warnings.extend(domain_warnings)
    if check_sources:
        problems.extend(check_entity_sources(text, path))

    # Grouping checks — additive, no-op when there is no Subsystem/Parent column or CONTEXT line.
    problems.extend(parent_problems)
    problems.extend(check_hierarchy(all_parents, defined))

    def _is_component(i: str) -> bool:  # a component id, never a context (`CX1` also starts with "C")
        return i.startswith("C") and not i.startswith("CX")

    # Loud guard against silent grouping failures: a Subsystems table with NO component actually
    # assigned is almost always a missing/unreadable membership column (which renders disconnected
    # subsystem boxes), not an intentional choice. Fail rather than pass green.
    if (any(i.startswith("S") for i in defined) and any(_is_component(i) for i in defined)
            and not any(_is_component(c) and p.startswith("S") for c, p in all_parents.items())):
        problems.append(
            "Subsystems (S) defined but no component is assigned to one — the T1 'Subsystem' "
            "membership column is missing or unreadable"
        )
    # Same guard for the domain model: a Contexts table with NO entity assigned is almost always
    # missing `CONTEXT:` lines (disconnected context boxes), not an intentional choice.
    entities_defined = any(i.startswith("E") for i in defined)
    if (any(i.startswith("CX") for i in defined) and entities_defined
            and not any(c.startswith("E") for c in context_parents)):
        problems.append(
            "Contexts (CX) defined but no entity is assigned to one — a domain card's `CONTEXT:` "
            "line is missing"
        )
    # Non-blocking nudge: once SOME entities carry a context, list any that don't — they render
    # ungrouped / top-level (valid), like an ungrouped component.
    if contexts_present and any(c.startswith("E") for c in context_parents):
        ungrouped = sorted(i for i in defined if i.startswith("E") and i not in context_parents)
        if ungrouped:
            warnings.append(f"Entities with no CONTEXT (ungrouped / top-level): {', '.join(ungrouped)}")
    # Non-blocking nudge: a LEAF context with no member entities (not assigned any entity, and not a
    # parent of another context) is empty — its per-context diagram shows only a placeholder. Usually a
    # leftover or a typo'd `CONTEXT:` id. (Non-leaf parent contexts legitimately have no direct members.)
    assigned_cx = set(context_parents.values())
    parent_cx = {p for c, p in all_parents.items() if c.startswith("CX")}
    empty_cx = sorted(i for i in defined if i.startswith("CX") and i not in assigned_cx and i not in parent_cx)
    if empty_cx:
        warnings.append(f"Contexts with no entities: {', '.join(empty_cx)}")

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
