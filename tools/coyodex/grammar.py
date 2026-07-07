#!/usr/bin/env python3
"""Shared token/grammar helpers used across the coyodex pipeline: the id vocabulary, the dependency
Kind classifier, the markdown table-splitting grammar (used by the change-impact report parser in
`viewer/build_graph.py`), and the domain-relation vocabulary (`views.py` derives graph edges and
flow steps straight from the model, reusing this vocabulary rather than a second one). Stdlib-only.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

# IDs by prefix. Multi-letter prefixes (UC, GP, SD) must precede the single-letter ones (so `SD1`
# never reads as `S` + stray text).
ID_TOKEN = re.compile(r"\b(?:UC\d+|GP\d+|SD\d+|C\d+|D\d+|E\d+|S\d+)\b")

# Grouping: membership is ONE parent pointer carried on the child.
# Nesting depth is ADVISORY, not capped: the viewer renders arbitrary depth, and the cycle check (not a
# depth limit) is what guarantees the membership walk terminates. The validator only *warns* when a
# chain is deeper than this, as a gentle "is each level pulling its weight?" nudge.
DEEP_NEST_WARN = 5  # warn (non-blocking) when a membership chain is deeper than this many parent hops

# External-dependency Kind — a closed vocabulary that drives how the C4 Context view treats a dep.
# The first four are EXTERNAL SYSTEMS the project talks to across a boundary (drawn at Context, by
# name); framework + library are in-process code deps that FOLD into one collapsed "Libraries" box.
# Authored in an OPTIONAL T2 `Kind` column; when absent, classify_dep() infers it from `Type`.
DEP_KINDS = ("datastore", "messaging", "service", "platform", "framework", "library")
DEP_KINDS_FOLDED = ("framework", "library")                          # in-process — fold into "Libraries"

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
    `Kind` column is the accurate path; this heuristic is the fallback when it's absent."""
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
    stay accurate. A verbatim example inside a code fence (a Mermaid diagram, a shell snippet) is
    not live content and must not be parsed as a table."""
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


_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")  # a column separator: a `|` NOT preceded by a backslash


def split_cells(row: str) -> list[str]:
    r"""Stripped cells of a markdown table row. An escaped pipe (``\|`` — the schema's sanctioned way
    to put a literal pipe inside a cell) is NOT a column separator: the row is split only on UNescaped
    pipes, and each cell's ``\|`` is then restored to a literal ``|``."""
    core = row.strip()
    core = core[1:] if core.startswith("|") else core      # drop the one leading table delimiter…
    core = core[:-1] if core.endswith("|") else core        # …and the one trailing delimiter
    return [c.replace(r"\|", "|").strip() for c in _UNESCAPED_PIPE.split(core)]


def is_separator_row(line: str) -> bool:
    r"""A markdown table separator row like ``|---|:--:|`` — dashes / colons / pipes / spaces only,
    with at least one dash."""
    return "-" in line and bool(re.fullmatch(r"[\s|:\-]+", line.strip()))


def iter_pipe_runs(lines: list[str]) -> list[tuple[int, list[str]]]:
    """Each maximal run of ``|``-prefixed lines as ``(start_index, block_lines)`` (0-based start).

    This is the table grouping the change-impact report parser (`viewer/build_graph.build_diff`)
    reads: a markdown table is a contiguous run of ``|``-lines, so ANY non-pipe line inside it (a
    blank line, stray prose, an HTML comment) breaks the run into two. Run on fence-free text
    (``strip_fences``) so a ``|`` row inside a code fence is never grouped as a table."""
    out: list[tuple[int, list[str]]] = []
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
        out.append((start, block))
    return out


# ── Domain-relation vocabulary ────────────────────────────────────────────────────────────────────
# `views.py` derives every domain-relation edge and its arrow-backing straight from the
# model (`Entity.relations`, `EntityField.markers`) — this vocabulary (verb -> relationship kind,
# the canonical-vs-alias verb map, and the FK-marker/backing-resolution helpers) is what it reuses,
# so there is still ONE place that decides what a relation verb means.

# Each structural kind has ONE canonical verb (association is free-form — any other verb).
CANONICAL_VERB = {"composition": "contains", "aggregation": "has", "inheritance": "isA"}
# verb -> classDiagram relationship kind; verbs outside the map render as plain associations.
REL_KIND = {
    "contains": "composition", "owns": "composition", "composedof": "composition",
    "has": "aggregation", "aggregates": "aggregation",
    "isa": "inheritance", "extends": "inheritance",
}
# non-canonical structural verb -> the canonical verb to use instead (drives the validator hint).
REL_ALIAS = {v: CANONICAL_VERB[k] for v, k in REL_KIND.items() if v != CANONICAL_VERB[k].lower()}

# A field's `FK→Ex` / `FK->Ex` marker, captured as a whole id token (so `FK→E1` never matches `E11`).
FK_MARKER = re.compile(r"FK(?:→|->)(E\d+)")


def fk_targets(markers: Iterable[str] | str) -> set[str]:
    """Entity ids a field points at via an `FK→Ex` / `FK->Ex` marker — matched as a whole id token
    (so `FK→E1` never matches `E11`). Accepts a marker list (``EntityField.markers``) or a
    space-joined string."""
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


# ── T6 use-case flows ─────────────────────────────────────────────────────────────────────────────
# `views.py` builds a Flow/FlowStep per use case straight from the model's `Flow`/`FlowStep`
# records (not from a markdown parse); `is_step_id` classifies each endpoint (an element ID vs a Role
# display name) so the viewer knows whether a step is a backbone reference or an actor interaction.
_STEP_ENDPOINT_ID = re.compile(r"^(?:UC\d+|SD\d+|C\d+|D\d+|E\d+|S\d+)$")


def is_step_id(token: str) -> bool:
    """True if `token` is an element ID (C/D/E/UC/S/SD); False -> treat it as a Role display name."""
    return bool(_STEP_ENDPOINT_ID.match(token.strip()))


@dataclass
class FlowStep:
    n: int               # the step number as written
    src: str             # an element ID (C/D/E/…) or a Role display name
    dst: str             # same
    src_is_id: bool      # True -> src is an element ID; False -> a Role name (actor step)
    dst_is_id: bool
    phrase: str = ""     # authored inline phrase (after ": ") — e.g. the actor's action
    note: str = ""       # flow-specific note (after "· ")
    ok: bool = True      # False -> the line could not be split into `from → to`


@dataclass
class Flow:
    uc: str              # the use case this flow realizes (its UC id, DEFINED in the Use-cases table)
    title: str
    steps: list[FlowStep]
    line_no: int
