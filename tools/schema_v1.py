#!/usr/bin/env python3
"""Schema v1 grammar — the single source of the project-map token/definition rules.

Imported by the validator (``tools/validate_analysis.py``) and the parser
(``tools/viewer/build_graph.py``) so there is ONE grammar, never two that can drift.
Stdlib-only.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
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

# External-dependency Kind — a closed vocabulary that drives how the C4 Context view treats a dep.
# The first four are EXTERNAL SYSTEMS the project talks to across a boundary (drawn at Context, by
# name); framework + library are in-process code deps that FOLD into one collapsed "Libraries" box.
# Authored in an OPTIONAL T2 `Kind` column; when absent, classify_dep() infers it from `Type`.
DEP_KINDS = ("datastore", "messaging", "service", "platform", "framework", "library")
DEP_KINDS_SHOWN = ("datastore", "messaging", "service", "platform")  # external systems — drawn at Context
DEP_KINDS_FOLDED = ("framework", "library")                          # in-process — fold into "Libraries"
# Display label per shown Kind, used for any per-kind grouping/headers in the viewer.
DEP_KIND_LABEL = {"datastore": "Datastores", "messaging": "Messaging",
                  "service": "External services", "platform": "Platform"}

# Keyword signatures for the heuristic fallback, in PRIORITY order (first hit wins). Distinctive
# categories precede broad ones so a multi-signal Type lands right: "AWS SQS" -> messaging (not
# platform), "AWS S3 object storage" -> datastore (not platform). Matched case-insensitively as
# substrings of the `Type` text. framework vs library need not be precise — both fold at Context.
_DEP_KIND_SIGNATURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("messaging", ("queue", "broker", "message", "pub/sub", "pubsub", "pub-sub", "kafka", "rabbitmq",
                   "rabbit", "amqp", "sqs", "sns", "nats", "event bus", "event stream", "kinesis",
                   "mqtt", "celery")),
    ("datastore", ("database", "datastore", "data store", "sql", "postgres", "mysql", "mariadb",
                   "sqlite", "mongo", "redis", "cache", "memcache", "elasticsearch", "opensearch",
                   "search index", "object storage", "blob storage", "bucket", "dynamodb",
                   "cassandra", "warehouse", "bigquery", "snowflake", "neo4j", "key-value",
                   "kv store", "vector store", "vector db")),
    ("service", ("api", "saas", "third-party", "third party", "external service", "webhook", "idp",
                 "identity provider", "oauth", "openid", "sso", "auth provider", "auth0", "okta",
                 "payment", "stripe", "billing", "email", "smtp", "sendgrid", "mailgun", "sms",
                 "twilio", "llm", "openai", "anthropic", "observability", "monitoring", "telemetry",
                 "metrics", "tracing", "sentry", "datadog", "analytics", "geocoding")),
    ("platform", ("cloud", "aws", "gcp", "azure", "kubernetes", "k8s", "docker", "container",
                  "cdn", "secrets manager", "vault", "infrastructure", "serverless",
                  "load balancer", "reverse proxy", "nginx", "terraform", "runtime")),
    ("framework", ("framework", "orm", "fastapi", "flask", "django", "express", "react", "vue",
                   "angular", "svelte", "spring", "rails", "laravel", "sqlalchemy", "prisma",
                   "next.js", "nextjs")),
)


def classify_dep(kind_cell: str, type_cell: str) -> str:
    """The dep's Kind (one of DEP_KINDS): an explicit, valid `Kind` cell wins; else infer from the
    free-text `Type`. Falls back to 'library' (folds into the Context 'Libraries' box) when nothing
    matches, so an un-tagged, unrecognised dep declutters rather than crowding Context. The authored
    `Kind` column is the accurate path; this heuristic is the no-re-map fallback for older maps."""
    explicit = (kind_cell or "").strip().lower()
    if explicit in DEP_KINDS:
        return explicit
    t = (type_cell or "").lower()
    for kind, needles in _DEP_KIND_SIGNATURES:
        if any(needle in t for needle in needles):
            return kind
    return "library"


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
# Optional trailing `{how}` note on a RELATIONS item — a plain-text explanation of how an
# indirect / field-less relation is implemented (e.g. `… E20 {keyed by (org, upstream) in the store}`).
REL_HOW = re.compile(r"\{(?P<how>[^}]*)\}\s*$")
# A field's `FK→Ex` / `FK->Ex` marker, captured as a whole id token (so `FK→E1` never matches `E11`).
FK_MARKER = re.compile(r"FK(?:→|->)(E\d+)")

# Each structural kind has ONE canonical verb (association is free-form — any other verb).
CANONICAL_VERB = {"composition": "contains", "aggregation": "has", "inheritance": "isA"}
# verb -> classDiagram relationship kind; verbs outside the map render as plain associations.
# Aliases are still recognised (so an un-canonicalised map renders with the right marker) but the
# validator rejects them in favour of the canonical verb — see REL_ALIAS.
REL_KIND = {
    "contains": "composition", "owns": "composition", "composedof": "composition",
    "has": "aggregation", "aggregates": "aggregation",
    "isa": "inheritance", "extends": "inheritance",
}
# non-canonical structural verb -> the canonical verb to use instead (drives the validator hint).
REL_ALIAS = {v: CANONICAL_VERB[k] for v, k in REL_KIND.items() if v != CANONICAL_VERB[k].lower()}

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
    how: str | None = None  # plain-text `{how}` note: how a field-less relation is implemented


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


def _split_glued_markers(typ: str) -> tuple[str, list[str]]:
    """Peel collection `[]` and nullable `?` markers glued to the type token into the marker list.
    Authors may write a marker spaced (`access_tokens:E28 []`) or glued (`access_tokens:E28[]`); both
    must normalize to type=`E28` + marker `[]`. A glued marker otherwise leaves the type as `E28[]`,
    which silently fails to resolve to the entity's name in the box AND fails the relation-backing
    match (so the arrow renders unlabelled) — with no validator error. Returns (bare_type, markers)."""
    glued: list[str] = []
    while True:
        if typ.endswith("[]"):
            glued.insert(0, "[]")
            typ = typ[:-2]
        elif typ.endswith("?"):
            glued.insert(0, "?")
            typ = typ[:-1]
        else:
            return typ, glued


def parse_card_fields(items: list[str]) -> list[CardField]:
    """Parse FIELDS items (`name: type markers`, inline or as `- ` bullets). An empty/missing type
    yields a CardField with ``type=''`` so the validator can flag it. Markers (`PK`/`FK→Ex`/`unique`/
    `?`/`[]`) may be space-separated OR glued to the type (`E28[]`); both normalize identically."""
    out: list[CardField] = []
    for item in items:
        item = item.strip()
        if item.startswith("- "):
            item = item[2:].strip()
        if not item:
            continue
        name, _, rest = item.partition(":")
        toks = rest.split()
        typ, glued = _split_glued_markers(toks[0] if toks else "")
        out.append(CardField(name=name.strip(), type=typ, markers=glued + toks[1:]))
    return out


def parse_card_relations(spec: str) -> list[CardRelation]:
    """Parse a RELATIONS line value (`verb sc→dc Eid display [{how}] · …`). A single trailing `{…}` is
    peeled off as the relation's how-note (a `·` may not appear inside it — it is the item separator;
    a `·` inside braces splits the item, and the trailing fragment is then flagged ``ok=False``). A
    `·`-item that doesn't match the grammar yields ``ok=False`` (validator flags it; parser skips it)."""
    out: list[CardRelation] = []
    for raw in spec.split("·"):
        raw = raw.strip()
        if not raw:
            continue
        how: str | None = None
        hm = REL_HOW.search(raw)
        if hm:
            how = hm.group("how").strip() or None
            raw = raw[: hm.start()].strip()  # peel `{how}` before matching the grammar
        m = RELATION_ITEM.match(raw)
        if not m:
            out.append(CardRelation("", "", None, None, "association", False, raw, how=how))
            continue
        kind = REL_KIND.get(m.group("verb").lower(), "association")
        out.append(CardRelation(m.group("verb"), m.group("tgt"), m.group("sc"), m.group("dc"),
                                kind, True, raw, how=how))
    return out


def fk_targets(markers: Iterable[str] | str) -> set[str]:
    """Entity ids a field points at via an `FK→Ex` / `FK->Ex` marker — matched as a whole id token
    (so `FK→E1` never matches `E11`). Accepts the marker list (``CardField.markers``) or a
    space-joined string (the ``markers`` on a parsed ``Node.attrs`` entry)."""
    text = markers if isinstance(markers, str) else " ".join(markers)
    return set(FK_MARKER.findall(text))


def resolve_backing(
    src: str, dst: str,
    src_fields: list[tuple[str, str, set[str]]],
    dst_fields: list[tuple[str, str, set[str]]],
) -> tuple[str | None, str | None]:
    """Which REAL field implements a domain relation `src --> dst`, and on which side. Each field is a
    `(name, type, fk_targets)` triple. Forward (the field lives on the source / arrow-tail) wins over
    reverse, mirroring how the relation is authored on the source card:
      - a SOURCE field typed by the target (`subscription:E15`) or marked `FK→dst` -> (name, 'src');
      - else a TARGET field marked `FK→src` (the back-reference) -> (name, 'dst');
      - else (None, None) — no field backs it (indirect / key-composition; carry a `{how}` note).
    When several fields qualify (e.g. two source fields typed by the same target), the FIRST in
    declaration order wins — arbitrary, but never wrong (every candidate points at the target).
    The canvas label and the panel's "Implemented by" line both derive from this one resolution."""
    for name, typ, fks in src_fields:
        if typ == dst or dst in fks:
            return name, "src"
    for name, _typ, fks in dst_fields:
        if src in fks:
            return name, "dst"
    return None, None


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
