#!/usr/bin/env python3
"""The viewer's graph data model + the change-impact report parser.

The graph (`GraphDict`) is what `gen_viewer.build_view_bundle` turns into the viewer's data; it is
produced by `coyodex.views.model_to_graph`, straight from the model. `build_diff` separately parses
the change-impact REPORT, a markdown artifact distinct from the map itself.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

# Shared schema grammar lives in tools/coyodex/grammar.py (one grammar; the table helpers serve
# the change-impact report parser below).
from coyodex.grammar import ID_TOKEN, is_separator_row, iter_pipe_runs, split_cells, strip_fences

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")  # markdown link -> href

# Synthetic id for the default subsystem injected when a map has components but no subsystem of its
# own (see _ensure_default_subsystem). "S0" is a valid subsystem id (prefix "S") and can't collide,
# since the case only fires when no subsystem node exists.
DEFAULT_SUBSYSTEM_ID = "S0"


@dataclass
class Node:
    id: str
    kind: str
    name: str
    file: str | None
    line: int | None
    fields: dict[str, str]
    parent: str | None = None  # the one parent S-id (grouping); None = top-level / ungrouped
    attrs: list[dict[str, str]] = field(default_factory=list)  # entity attributes (T5 cards only)
    dep_kind: str | None = None  # T2 deps only: the Context Kind (datastore/messaging/service/…); see classify_dep
    files: list[str] = field(default_factory=list)  # every repo-relative file this element covers,
                                  # bare (no line anchor), the canonical `source` file first. A
                                  # component's owned files; a group's = union of its members' files;
                                  # an entity's single source file. Drives the code-viewer file
                                  # switcher + the tree footprint highlight.


@dataclass
class Edge:
    src: str
    verb: str
    dst: str
    why: str | None
    where: str | None
    kind: str | None = None       # domain-relation kind (association/composition/…); None = plain edge
    src_card: str | None = None   # cardinality at the source end (domain relations only)
    dst_card: str | None = None   # cardinality at the destination end
    how: str | None = None        # plain-text note: how a field-less domain relation is implemented
    fk_fields: list[str] = field(default_factory=list)  # REAL field(s) backing the relation (drive the
                                  # arrow label) — more than one is a composite key, e.g. (user_id, page_id)
    fk_side: str | None = None    # 'src' = field on the tail (forward), 'dst' = FK on the head (reverse)
    keyed_by: list[str] = field(default_factory=list)  # storage KEY name(s) identifying the target
                                  # (a lookup/partition key the store imposes, not a row field) — drawn
                                  # on the arrow with the «key» marker when no fk_fields back the link


@dataclass
class HappyStep:
    """A Happy Path step = a use-case occurrence: a position (`id`) in the ordered walk that realizes
    a use case (`uc`). It carries no STORY/Touches — those live in the use case's T6 flow; drilling the
    step opens that flow. `why` is the optional prerequisite that fixes this step's position."""
    id: str
    title: str
    uc: str | None = None  # the use case this step realizes (from the required `*(UCn)*` heading tag)
    why: str = ""          # optional `why:` line — the prerequisite that places this step in the walk


class GraphDict(TypedDict):
    commit: str | None
    committed: str | None  # commit date of the pin (None for older maps without the field)
    title: str | None
    goal: str | None
    nodes: dict[str, dict[str, object]]
    edges: list[dict[str, object]]
    happy_path: list[dict[str, object]]
    flows: list[dict[str, object]]  # T6 use-case flows (one per use case): the ordered inside view
    roles: list[dict[str, str]]
    glossary: list[dict[str, str]]  # ubiquitous-language terms: {term, meaning, where} (where = bare
                                    # `path:line`/`path/` anchor, or "" when the term has no code home)


class DiffChange(TypedDict):
    id: str
    change: str
    name: str | None
    kind: str | None
    note: str


class DiffDict(TypedDict):
    base: str | None
    new: str | None
    changes: list[DiffChange]
    new_edges: list[dict[str, str]]


_LINE_OF = re.compile(r"(?:#L|:)(\d+)(?:-L?\d+)?$")  # a trailing anchor's START line, either form


def _line_of(href: str | None) -> int | None:
    if not href:
        return None
    m = _LINE_OF.search(href)
    return int(m.group(1)) if m else None


def _first_id(cell: str) -> str | None:
    m = ID_TOKEN.search(cell)
    return m.group(0) if m else None


def _tables(lines: list[str]) -> list[tuple[list[str], list[list[str]]]]:
    """Group consecutive `|`-prefixed lines into (headers, rows) tables, via the shared
    grammar.iter_pipe_runs grouping — the SAME table model the validator uses, so the parser and the
    gate cannot drift on where a table begins and ends. A run of < 2 lines is not a table; separator
    rows are dropped from the body."""
    tables: list[tuple[list[str], list[list[str]]]] = []
    for _start, block in iter_pipe_runs(lines):
        if len(block) >= 2:
            headers = split_cells(block[0])
            rows = [split_cells(b) for b in block[1:] if not is_separator_row(b)]
            tables.append((headers, rows))
    return tables


SERVICE_HINTS = re.compile(
    r"\b(agent|service|svc|server|system|external|idp|bot|daemon|cron|scheduler|worker|webhook|job)\b", re.I
)


def _role_kind(name: str, explicit: str) -> str:
    """Explicit 'human'/'service' (from a Kind column) wins; else infer 'service' from name hints."""
    if explicit:
        return "service" if explicit.strip().lower().startswith("s") else "human"
    return "service" if SERVICE_HINTS.search(name) else "human"


def _ensure_default_subsystem(nodes: dict[str, Node], title: str | None) -> None:
    """If the map has components but defines NO subsystem, inject one default subsystem (`S0`, named
    after the project) and reparent every component under it. This keeps the viewer uniform: there is
    always a subsystem altitude that holds the component-level view, so the flat per-component map is
    never the only place components live. A map that already groups its components is left untouched;
    a pure domain map (no components) gets nothing."""
    has_subsystem = any(n.kind == "subsystem" for n in nodes.values())
    comp_ids = [nid for nid, n in nodes.items() if n.kind == "component"]
    if has_subsystem or not comp_ids:
        return
    nodes[DEFAULT_SUBSYSTEM_ID] = Node(
        id=DEFAULT_SUBSYSTEM_ID, kind="subsystem", name=title or "Application",
        file=None, line=None,
        fields={"Purpose": "All components — this map defines no subsystem grouping."},
        parent=None,
    )
    for nid in comp_ids:
        nodes[nid].parent = DEFAULT_SUBSYSTEM_ID


DIFF_HDR = re.compile(r"`?(\w+)`?\s*(?:→|->)\s*`?(\w+)`?")


def _col(row: list[str], ci: dict[str, int], key: str) -> str:
    i = ci.get(key, -1)
    return row[i].strip() if 0 <= i < len(row) else ""


def build_diff(md_path: Path) -> DiffDict:
    """Parse a change-impact report into per-element classifications + new edges."""
    text = strip_fences(md_path.read_text(encoding="utf-8"))
    lines = text.splitlines()
    changes: list[DiffChange] = []
    new_edges: list[dict[str, str]] = []
    for headers, rows in _tables(lines):
        hl = [h.lower() for h in headers]
        if "change" in hl:
            ci = {h: i for i, h in enumerate(hl)}
            for row in rows:
                if not row:                          # a header with a short/empty body row — skip it
                    continue
                eid = _first_id(row[0])
                if not eid:
                    continue
                kind = _col(row, ci, "kind").lower()
                changes.append(
                    DiffChange(
                        id=eid,
                        change=_col(row, ci, "change").lower(),
                        name=_col(row, ci, "name") or None,
                        kind=kind or None,
                        note=_col(row, ci, "note"),
                    )
                )
        elif hl[:3] == ["from", "verb", "to"]:
            for row in rows:
                if len(row) < 3:                     # a short body row under from|verb|to — skip it
                    continue
                s, d = _first_id(row[0]), _first_id(row[2])
                if s and d:
                    new_edges.append({"src": s, "verb": row[1], "dst": d})
    base = new = None
    for line in lines:
        if line.lstrip().startswith("#") and ("→" in line or "->" in line):
            m = DIFF_HDR.search(line)
            if m:
                base, new = m.group(1), m.group(2)
                break
    return DiffDict(base=base, new=new, changes=changes, new_edges=new_edges)
