#!/usr/bin/env python3
"""Schema v1 grammar — the single source of the project-map token/definition rules.

Imported by the validator (``tools/validate_analysis.py``) and the parser
(``tools/viewer/build_graph.py``) so there is ONE grammar, never two that can drift.
Stdlib-only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# IDs by prefix. Multi-letter prefixes (UC, GP) must precede the single-letter ones. `E` (domain
# entity) is a reference token here but is DEFINED in a card heading (DEF_ENTITY below), not a table
# row — so it is intentionally ABSENT from the table-definition patterns that follow.
ID_TOKEN = re.compile(r"\b(?:UC\d+|GP\d+|C\d+|D\d+|E\d+|S\d+)\b")

# A definition is the FIRST cell of a table row, bolded: `| **C1** | ... |`
# — not an inline bold reference in prose. (E is card-defined; see DEF_ENTITY.)
DEF_BOLD = re.compile(r"^\|\s*\*\*(UC\d+|C\d+|D\d+|S\d+)\*\*\s*\|")

# A bold id anywhere in a cell — a parser uses this to find a row's defining id.
DEF_ID_CELL = re.compile(r"\*\*(UC\d+|C\d+|D\d+|S\d+)\*\*")

# A bold id at the START of a first cell but with extra text glued after it — i.e. NOT a clean
# `| **C1** |` definition. Id and name sharing the cell is the most common reason an id reads as
# "undefined"; the validator uses these to name that exact cause. Two glue forms:
#   GLUED_DEF       — name OUTSIDE the bold:  `| **UC1** Search… |`
#   GLUED_DEF_INNER — name INSIDE the bold:   `| **C8 Upstream** |`
GLUED_DEF = re.compile(r"^\|\s*\*\*(UC\d+|C\d+|D\d+|S\d+)\*\*\s+[^|]")
GLUED_DEF_INNER = re.compile(r"^\|\s*\*\*(UC\d+|C\d+|D\d+|S\d+)\s+[^*|]+\*\*")

# Block-heading definitions (NOT table rows): a Golden Path step `**GP1 — ...` and a T5 domain card
# `**E1 — ...` (see method/domain-cards.md). Each DEFINES its id in the heading.
DEF_GP = re.compile(r"^\*\*(GP\d+)\s+—")
DEF_ENTITY = re.compile(r"^\*\*(E\d+)\s+—")

# Grouping: membership is ONE parent pointer carried on the child.
MAX_DEPTH = 3  # max subsystem levels (parent-pointer hops) in any membership chain


def strip_fences(text: str) -> str:
    """Blank out fenced code blocks (``` or ~~~), keeping the line COUNT so reported line numbers
    stay accurate. Both consumers (validator, parser) read tables/IDs from prose; a verbatim
    example inside a code fence (a Mermaid diagram, a shell snippet, a teaching example of a
    *malformed* table) is not live content and must not be parsed as a table or as ID
    definitions/references. Shared here so the two tools strip fences identically — one grammar."""
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out.append("")  # blank the fence marker line too
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def membership_col(headers_lower: list[str], child_id: str) -> int | None:
    """Index of a row's membership column, chosen by the row's OWN id kind (robust to column
    order): a subsystem row's 'Subsystem' header is its *name* column, so its parent pointer is
    'Parent'; a component (or other) row's membership IS the 'Subsystem' column."""
    sub = headers_lower.index("subsystem") if "subsystem" in headers_lower else None
    par = headers_lower.index("parent") if "parent" in headers_lower else None
    return par if child_id.startswith("S") else (sub if sub is not None else par)


def membership_ids(child_id: str, cells: list[str], headers_lower: list[str]) -> list[str]:
    """All id-tokens in a row's membership column ([] if none / no such column). ``len > 1`` is a
    malformed multi-parent cell; the first id is the parent. Shared by validator and parser so the
    membership rule lives in exactly one place."""
    col = membership_col(headers_lower, child_id)
    if col is None or col >= len(cells):
        return []
    return ID_TOKEN.findall(cells[col])


# ---- Domain cards (T5) -------------------------------------------------------------------------
# T5 is authored as per-entity CARDS (blocks), not a table — see method/domain-cards.md. A card's
# heading DEFINES the E id (DEF_ENTITY); FIELDS/RELATIONS/MEANING/SOURCE are labeled lines. This
# grammar is shared by the validator and the parser/renderer so there is ONE source of the format.

# Full heading parse: `**E1 — Order** *(orders collection)*` -> id, name, store(optional).
ENTITY_HEADING = re.compile(r"^\*\*(E\d+)\s+—\s*(.+?)\s*\*\*\s*(?:\*\((.*?)\)\*)?\s*$")

ALLOWED_CARDINALITY = {"1", "*", "0..1", "1..*"}
_CARD = r"\*|\d+|0\.\.1|1\.\.\*"
# One RELATIONS item: `verb [sc→dc] Eid [display]`. Cardinality pair is optional (omit for isA).
RELATION_ITEM = re.compile(rf"^(?P<verb>[\w-]+)(?:\s+(?P<sc>{_CARD})→(?P<dc>{_CARD}))?\s+(?P<tgt>E\d+)\b")

# verb -> classDiagram relationship kind; verbs outside the map render as plain associations.
REL_KIND = {
    "isa": "inheritance", "extends": "inheritance",
    "contains": "composition", "owns": "composition", "composedof": "composition",
    "aggregates": "aggregation", "has": "aggregation",
}

_CARD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")  # markdown link -> href (for SOURCE:)


@dataclass
class CardField:
    name: str
    type: str
    markers: list[str] = field(default_factory=list)


@dataclass
class CardRelation:
    verb: str
    target: str
    src_card: str | None
    dst_card: str | None
    kind: str
    ok: bool          # False = the item did not match the grammar (validator flags, parser skips)
    raw: str


@dataclass
class DomainCard:
    id: str
    name: str
    store: str
    meaning: str
    source: str | None
    fields: list[CardField]
    relations: list[CardRelation]
    line: int  # 1-based heading line, for error messages
    heading_ok: bool = True  # False = heading matched DEF_ENTITY but not the full `**En — Name** *(store)*`


def parse_card_fields(items: list[str]) -> list[CardField]:
    """Parse FIELDS items (`name: type markers`, inline or as `- ` bullets). An empty/missing type
    yields a CardField with ``type=''`` so the validator can flag it."""
    out: list[CardField] = []
    for item in items:
        item = item.strip()
        if item.startswith("- "):
            item = item[2:].strip()
        if not item:
            continue
        name, _, rest = item.partition(":")
        toks = rest.split()
        out.append(CardField(name=name.strip(), type=(toks[0] if toks else ""), markers=toks[1:]))
    return out


def parse_card_relations(spec: str) -> list[CardRelation]:
    """Parse a RELATIONS line value (`verb sc→dc Eid display · …`). A `·`-item that doesn't match the
    grammar yields ``ok=False`` (validator flags it as malformed; parser skips it)."""
    out: list[CardRelation] = []
    for raw in spec.split("·"):
        raw = raw.strip()
        if not raw:
            continue
        m = RELATION_ITEM.match(raw)
        if not m:
            out.append(CardRelation("", "", None, None, "association", False, raw))
            continue
        kind = REL_KIND.get(m.group("verb").lower(), "association")
        out.append(CardRelation(m.group("verb"), m.group("tgt"), m.group("sc"), m.group("dc"),
                                kind, True, raw))
    return out


def iter_domain_cards(lines: list[str]):
    """Yield a DomainCard for each T5 card in `lines`. A card runs from its heading to the next card
    heading, a `---` rule, or a `#` section heading. Shared by the validator and the parser."""
    i, n = 0, len(lines)
    while i < n:
        head = lines[i].strip()
        hm = DEF_ENTITY.match(head)
        if not hm:
            i += 1
            continue
        fm = ENTITY_HEADING.match(head)
        eid = hm.group(1)
        name, store = (fm.group(2).strip(), (fm.group(3) or "").strip()) if fm else (eid, "")
        meaning, source = "", None
        fields_out: list[CardField] = []
        relations: list[CardRelation] = []
        line_no = i + 1
        j = i + 1
        while j < n:
            s = lines[j].strip()
            if DEF_ENTITY.match(s) or s.startswith("---") or s.startswith("#"):
                break
            if s.startswith("MEANING:"):
                meaning = s[len("MEANING:"):].strip()
            elif s.startswith("SOURCE:"):
                lm = _CARD_LINK.search(s)
                source = lm.group(1) if lm else (s[len("SOURCE:"):].strip() or None)
            elif s.startswith("RELATIONS:"):
                relations = parse_card_relations(s[len("RELATIONS:"):])
            elif s.startswith("FIELDS:"):
                items = s[len("FIELDS:"):].split("·")
                k = j + 1
                while k < n and lines[k].strip().startswith("- "):  # consume bullet-list fields
                    items.append(lines[k].strip())
                    k += 1
                fields_out = parse_card_fields(items)
                j = k - 1
            j += 1
        yield DomainCard(eid, name, store, meaning, source, fields_out, relations, line_no,
                         heading_ok=fm is not None)
        i = j
