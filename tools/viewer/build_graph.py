#!/usr/bin/env python3
"""Parse a schema-v1 project-map.md into a graph JSON (the parser/renderer interface).

Reuses the schema-v1 grammar from tools/schema_v1.py by import — one grammar, shared with the
validator. The JSON it emits is an ephemeral parse result, never a hand-maintained second source.

Usage:  python3 build_graph.py [fixture/project-map.md] [build/graph.json]
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TypedDict

# Shared schema-v1 grammar lives in tools/schema_v1.py (one grammar for validator + parser). This
# file sits in tools/viewer/, so put the sibling tools/ dir on the path to import it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema_v1 import (  # noqa: E402
    DEF_GP,
    DEF_ID_CELL,
    ID_TOKEN,
    classify_dep,
    fk_targets,
    iter_domain_cards,
    membership_col,
    membership_ids,
    resolve_backing,
    strip_fences,
)

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")  # markdown link -> href
COMMIT = re.compile(r"\*\*Commit:\*\*\s*`([^`]+)`")
COMMITTED = re.compile(r"\*\*Committed:\*\*\s*`([^`]+)`")  # commit date of the pinned commit

# `SD` must resolve to "subdomain" (a cluster of T5 entities); `_kind_of` extracts the full alpha
# prefix, so "SD" is looked up whole and never collides with the single-letter "S" (subsystem).
KIND_BY_PREFIX = {"C": "component", "D": "dep", "E": "entity", "UC": "usecase", "S": "subsystem",
                  "SD": "subdomain"}


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
    fk_field: str | None = None   # the REAL field that backs the relation (drives the arrow label)
    fk_side: str | None = None    # 'src' = field on the tail (forward), 'dst' = FK on the head (reverse)


@dataclass
class GPStep:
    id: str
    title: str
    story: str
    under_the_hood: str
    touches: list[str] = field(default_factory=list)
    uc: str | None = None  # the use case the step realizes (from the `*(UCn)*` heading tag); fallback actor source
    actor: str | None = None  # explicit driving role from an `Actor:` line; overrides the UC-derived actor


class GraphDict(TypedDict):
    commit: str | None
    committed: str | None  # commit date of the pin (None for older maps without the field)
    title: str | None
    goal: str | None
    nodes: dict[str, dict[str, object]]
    edges: list[dict[str, object]]
    gp: list[dict[str, object]]
    roles: list[dict[str, str]]


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


def _cells(line: str) -> list[str]:
    """Split a markdown table row into trimmed cell strings."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_separator(line: str) -> bool:
    return bool(re.fullmatch(r"[\s|:-]+", line.strip())) and "-" in line


def _kind_of(node_id: str) -> str:
    m = re.match(r"[A-Z]+", node_id)
    return KIND_BY_PREFIX.get(m.group(0) if m else "", "unknown")


def _first_link(cells: list[str]) -> str | None:
    for c in cells:
        m = LINK.search(c)
        if m:
            return m.group(1)
    return None


def _line_of(href: str | None) -> int | None:
    if not href:
        return None
    m = re.search(r"#L(\d+)$", href) or re.search(r":(\d+)$", href)
    return int(m.group(1)) if m else None


def _first_id(cell: str) -> str | None:
    m = ID_TOKEN.search(cell)
    return m.group(0) if m else None


def _tables(lines: list[str]) -> list[tuple[list[str], list[list[str]]]]:
    """Group consecutive `|`-prefixed lines into (headers, rows) tables."""
    tables: list[tuple[list[str], list[list[str]]]] = []
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            block: list[str] = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                block.append(lines[i])
                i += 1
            if len(block) >= 2:
                headers = _cells(block[0])
                rows = [_cells(b) for b in block[1:] if not _is_separator(b)]
                tables.append((headers, rows))
        else:
            i += 1
    return tables


def parse_nodes_edges(tables: list[tuple[list[str], list[list[str]]]]) -> tuple[dict[str, Node], list[Edge]]:
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for headers, rows in tables:
        hl = [h.lower() for h in headers]
        is_edge_table = hl[:3] == ["from", "verb", "to"]
        ci = {h: i for i, h in enumerate(hl)}
        for row in rows:
            if is_edge_table:
                src, dst = _first_id(_col(row, ci, "from")), _first_id(_col(row, ci, "to"))
                if src and dst:
                    verb = _col(row, ci, "verb")
                    key = (src, verb, dst)
                    if key not in seen_edges:
                        seen_edges.add(key)
                        where_cell = _col(row, ci, "where")
                        where = _first_link([where_cell]) or where_cell or None
                        edges.append(Edge(src, verb, dst, _col(row, ci, "why") or None, where))
                continue
            if not row:
                continue
            m = DEF_ID_CELL.search(row[0])
            if not m:
                continue
            node_id = m.group(1)
            # Display name = the row's second cell, UNLESS that cell is the membership column
            # (some layouts drop the separate name column and put Subsystem at index 1) or is a
            # bare id — then fall back to the id, so a component is never mislabeled as its subsystem.
            cand = row[1].strip() if len(row) > 1 else ""
            name = cand if (cand and membership_col(hl, node_id) != 1
                            and not re.fullmatch(r"(?:UC|GP|C|D|E|S)\d+", cand)) else node_id
            href = _first_link(row)
            fields = {h: row[idx] for idx, h in enumerate(headers) if idx < len(row) and idx != 0}
            _parents = membership_ids(node_id, row, hl)
            node_kind = _kind_of(node_id)
            # T2 deps carry a Context Kind: an explicit (optional) `Kind` cell, else inferred from the
            # `Type` text. Looked up case-insensitively so a `Kind`/`Type` header in any case resolves.
            dep_kind: str | None = None
            if node_kind == "dep":
                fl = {k.lower(): v for k, v in fields.items()}
                dep_kind = classify_dep(fl.get("kind", ""), fl.get("type", ""))
            nodes[node_id] = Node(
                id=node_id,
                kind=node_kind,
                name=name,
                file=href,
                line=_line_of(href),
                fields=fields,
                parent=_parents[0] if _parents else None,
                dep_kind=dep_kind,
            )
    return nodes, edges


def parse_gp(lines: list[str]) -> list[GPStep]:
    steps: list[GPStep] = []
    i = 0
    while i < len(lines):
        m = DEF_GP.match(lines[i])
        if not m:
            i += 1
            continue
        gp_id = m.group(1)
        # First UC in the heading tag -> the step's (primary) use case. The tag may list several
        # (`*(UC21, UC22)*`) or carry trailing text (`*(UC16 follow-on)*`); take the first id so a
        # multi-UC step still resolves to a real actor instead of falling back to a generic one.
        uc_m = re.search(r"UC\d+", lines[i])
        uc = uc_m.group(0) if uc_m else None
        title = lines[i].split("—", 1)[1].strip() if "—" in lines[i] else ""
        title = re.sub(r"\*\*|\*\([^)]*\)\*?", "", title).strip().rstrip("*").strip()
        story = under = ""
        actor: str | None = None
        touches: list[str] = []
        j = i + 1
        while j < len(lines) and not DEF_GP.match(lines[j]):
            s = lines[j].strip()
            if s.startswith("STORY:"):
                story = s[len("STORY:"):].strip()
            elif s.startswith("UNDER THE HOOD:"):
                under = s[len("UNDER THE HOOD:"):].strip()
            elif s.startswith("Actor:"):
                actor = s[len("Actor:"):].strip() or None
            elif s.startswith("`Touches:`") or s.startswith("Touches:"):
                touches = ID_TOKEN.findall(s)
            j += 1
        steps.append(GPStep(id=gp_id, title=title, story=story, under_the_hood=under,
                            touches=touches, uc=uc, actor=actor))
        i = j
    return steps


def parse_domain(lines: list[str]) -> tuple[dict[str, Node], list[Edge]]:
    """T5 domain cards -> entity nodes (with `attrs`) + their typed relation edges (with `kind` +
    cardinality). Uses the shared `iter_domain_cards` grammar; malformed relations are skipped (the
    validator is what flags them)."""
    nodes: dict[str, Node] = {}
    edges: list[Edge] = []
    for card in iter_domain_cards(lines):
        meta: dict[str, str] = {}
        if card.meaning:
            meta["Meaning"] = card.meaning
        if card.store:
            meta["Stored"] = card.store
        attrs = [{"name": f.name, "type": f.type, "markers": " ".join(f.markers)} for f in card.fields]
        # `card.subdomain` (the card's `SUBDOMAIN:` line, a `SD` id) is the entity's one parent
        # subdomain — the domain-model analog of a component's `Subsystem`. Carried on `Node.parent` so
        # the same parent-pointer machinery (top-ancestor walk, derived membership) works for entities.
        nodes[card.id] = Node(id=card.id, kind="entity", name=card.name, file=card.source,
                              line=_line_of(card.source), fields=meta, attrs=attrs,
                              parent=card.subdomain)
        for r in card.relations:
            if r.ok:
                edges.append(Edge(card.id, r.verb, r.target, None, None, kind=r.kind,
                                  src_card=r.src_card, dst_card=r.dst_card, how=r.how))
    # Second pass (all entity nodes now exist, so forward references resolve): for each relation, find
    # the REAL field that backs it — the single resolution that drives both the arrow label and the
    # panel's "Implemented by" line. `isA` is a pure type relation, never field-backed, so skip it.
    for e in edges:
        # `e.src` is always a card id (added to `nodes` above); only `e.dst` can dangle (undefined
        # target — the validator flags it), so guard the dst lookup.
        if e.kind and e.kind != "inheritance" and e.dst in nodes:
            e.fk_field, e.fk_side = resolve_backing(
                e.src, e.dst, _backing_fields(nodes[e.src]), _backing_fields(nodes[e.dst]))
    return nodes, edges


def _backing_fields(node: Node) -> list[tuple[str, str, set[str]]]:
    """A node's entity attributes as `(name, type, fk_targets)` triples for `resolve_backing`."""
    return [(a.get("name", ""), a.get("type", ""), fk_targets(a.get("markers", ""))) for a in node.attrs]


SERVICE_HINTS = re.compile(
    r"\b(agent|service|svc|server|system|external|idp|bot|daemon|cron|scheduler|worker|webhook|job)\b", re.I
)


def _role_kind(name: str, explicit: str) -> str:
    """Explicit 'human'/'service' (from a Kind column) wins; else infer 'service' from name hints."""
    if explicit:
        return "service" if explicit.strip().lower().startswith("s") else "human"
    return "service" if SERVICE_HINTS.search(name) else "human"


def parse_roles(tables: list[tuple[list[str], list[list[str]]]]) -> list[dict[str, str]]:
    """Roles (actors) for the C4 context view: the first table whose first header is 'Role'.
    Reads the required 'Kind' column (human/service); for maps that predate it, falls back to
    inferring the kind from the role name."""
    roles: list[dict[str, str]] = []
    for headers, rows in tables:
        hl = [h.strip().lower() for h in headers]
        if not hl or hl[0] != "role":
            continue
        kind_idx = hl.index("kind") if "kind" in hl else -1
        wants_idx = next((i for i, h in enumerate(hl) if "want" in h), 1)
        for row in rows:
            name = re.sub(r"\*+", "", row[0]).strip()
            if not name:
                continue
            wants = row[wants_idx].strip() if 0 <= wants_idx < len(row) else ""
            explicit = row[kind_idx].strip() if 0 <= kind_idx < len(row) else ""
            roles.append({"name": name, "wants": wants, "kind": _role_kind(name, explicit)})
        break
    return roles


GOAL_HDR = re.compile(r"^##\s+T0\b[^\n]*$", re.M)  # the "## T0 — Goal …" heading


def parse_goal(text: str) -> str | None:
    """The T0 — Goal prose: the system's overall functionality, surfaced as the System node's overview.
    Captures everything between the T0 heading and the next `## ` heading (or `---` rule)."""
    m = GOAL_HDR.search(text)
    if not m:
        return None
    rest = text[m.end():]
    stop = re.search(r"^(?:##\s|---\s*$)", rest, re.M)
    body = (rest[:stop.start()] if stop else rest).strip()
    return body or None


def build(md_path: Path) -> GraphDict:
    # Ignore fenced code blocks (Mermaid / shell / teaching examples) — they are not live content.
    text = strip_fences(md_path.read_text(encoding="utf-8"))
    lines = text.splitlines()
    tables = _tables(lines)
    nodes, edges = parse_nodes_edges(tables)
    dnodes, dedges = parse_domain(lines)  # T5 domain cards (entities + their relations)
    nodes.update(dnodes)
    edges.extend(dedges)
    gp = parse_gp(lines)
    commit_m = COMMIT.search(text)
    committed_m = COMMITTED.search(text)
    title_m = re.search(r"^#\s+(.+?)\s*$", text, re.M)
    title = title_m.group(1).strip() if title_m else None
    if title and " — " in title:
        title = title.split(" — ")[0].strip()
    return {
        "commit": commit_m.group(1) if commit_m else None,
        "committed": committed_m.group(1) if committed_m else None,
        "title": title,
        "goal": parse_goal(text),
        "nodes": {nid: asdict(n) for nid, n in nodes.items()},
        "edges": [asdict(e) for e in edges],
        "gp": [asdict(g) for g in gp],
        "roles": parse_roles(tables),
    }


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


def main() -> int:
    md = Path(sys.argv[1] if len(sys.argv) > 1 else "fixture/project-map.md")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "build/graph.json")
    if not md.exists():
        print(f"ERROR: {md} not found", file=sys.stderr)
        return 1
    graph = build(md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    print(
        f"Parsed {len(graph['nodes'])} nodes, {len(graph['edges'])} edges, "
        f"{len(graph['gp'])} GP steps -> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
