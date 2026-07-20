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

# IDs by prefix. Multi-letter prefixes (UC, HP, SD, SF) must precede the single-letter ones (so `SD1`
# never reads as `S` + stray text).
ID_TOKEN = re.compile(r"\b(?:UC\d+|HP\d+|SD\d+|SF\d+|C\d+|D\d+|E\d+|S\d+)\b")

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
# The EXTERNAL (system) dep kinds — everything the project talks to across a boundary. A deployment
# unit that hosts no code but name-matches one of these is that dep's own box, not a real process.
DEP_KINDS_SYSTEM = tuple(k for k in DEP_KINDS if k not in DEP_KINDS_FOLDED)  # datastore/messaging/service/platform


# A deployment `Unit` is ONE process; these separators signal two+ units crammed into one row (a
# non-atomic name). Shared by the atomic-name check and the dep-match guard below.
UNIT_NAME_SEPARATORS = (" / ", ",", " & ")


def is_atomic_unit_name(name: str) -> bool:
    """A unit name denotes exactly one process (no separator crammed two together)."""
    return not any(sep in name for sep in UNIT_NAME_SEPARATORS)


def _norm_alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def unit_name_matches_dep(unit_name: str, dep_name: str) -> bool:
    """True when a deployment-unit name and a dependency name denote the SAME infra: case-insensitive
    containment of the alphanumeric-normalized names, either direction (`"mongo"`↔`"MongoDB"` matches).
    A NON-ATOMIC unit name (a `"mongo-test / redis-test"` compound) denotes no single dep and matches
    NOTHING — it is left to flag as untraced (and as a non-atomic name), never silently treated as
    infra. This guard is load-bearing: without it the compound normalizes to one blob that DOES contain
    a short dep token like `"redis"`, wrongly suppressing the real gap the check exists to surface."""
    if not is_atomic_unit_name(unit_name):
        return False
    u = _norm_alnum(unit_name)
    d = _norm_alnum(dep_name)
    if not u or not d:
        return False
    return u in d or d in u

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


# ── Dependency PURPOSE bucket — the seeded-open grouping axis ─────────────────────────────────────
# Unlike DEP_KINDS (a CLOSED, structural axis: how you talk to the dep + whether it folds), a bucket
# is a PURPOSE axis (what the dep does for the product) and is SEEDED-OPEN: the analysis reuses a seed
# when one fits and may MINT a new bucket when none does. `Kind` still decides shown-vs-folded; the
# bucket only GROUPS deps WITHIN each of the two diagrams — external systems in the Context view,
# in-process code in the Libraries drill — so the two seed lists lean external vs. code respectively.
DEP_BUCKET_SEEDS_EXTERNAL = (
    "Data & storage", "Identity & access", "Observability", "Messaging & delivery",
    "AI & ML", "Infrastructure & runtime", "Integrations",
)
DEP_BUCKET_SEEDS_LIBRARY = (
    "Web framework / server", "Frontend / UI", "Data drivers", "Service SDKs",
    "Validation / models", "Logging", "Crypto / security",
)
DEP_BUCKET_SEEDS = DEP_BUCKET_SEEDS_EXTERNAL + DEP_BUCKET_SEEDS_LIBRARY
# The catch-all each diagram falls back to when no seed fits (external's is itself a seed, drawn last).
DEP_BUCKET_CATCHALL_EXTERNAL = "Integrations"
DEP_BUCKET_CATCHALL_LIBRARY = "Other"
# Per-DIAGRAM cap (checked separately for externals vs libraries — they are two diagrams): a nudge to
# keep the grouping legible instead of proliferating one-item buckets.
DEP_BUCKET_CAP = 8
# When the CATCH-ALL bucket ('Integrations' / 'Other') alone holds more than this many deps, it has
# stopped meaning "no specific purpose" and become a dumping ground — the mirror of DEP_BUCKET_CAP
# (that guards against too-many buckets; this against one bucket swallowing everything). A large
# catch-all means real sub-purposes (Payments, Social, …) are hiding and should be split out.
DEP_BUCKET_CATCHALL_SPLIT_AT = 6
# A Context (external) bucket with THIS MANY OR MORE members collapses into a single drillable count
# box instead of an inline cluster — so an integration-heavy product doesn't render every name at the
# top altitude. Set just above the largest bucket a small map produces (mcpolis peaks at 4), so small
# maps stay fully expanded and only genuinely large buckets fold.
DEP_BUCKET_FOLD_AT = 5

# The external catch-all is already a seed; the LIBRARY catch-all is not, so add it explicitly —
# otherwise a mis-cased "other" would escape folding and render a duplicate look-alike catch-all cluster.
_BUCKET_CANON = {b.lower(): b for b in (*DEP_BUCKET_SEEDS, DEP_BUCKET_CATCHALL_LIBRARY)}


def canonical_bucket(name: str) -> str:
    """Fold a bucket to its seed's canonical spelling when it matches one case-insensitively (kills
    the case / trailing-whitespace drift deterministically); a minted (non-seed) bucket is returned
    trimmed, exactly as authored. The single normalizer every reader routes through."""
    s = (name or "").strip()
    return _BUCKET_CANON.get(s.lower(), s)


# Keyword signatures for the heuristic used ONLY when a dep carries no authored bucket — priority
# order, first hit wins, matched against the `type` + `used_for` text. The authored `Bucket` is the
# accurate path; this just keeps an un-tagged dep grouped somewhere sane instead of all-catch-all.
_BUCKET_SIGNATURES_EXTERNAL: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Identity & access", ("oauth", "openid", "sso", "idp", "identity", "auth provider", "auth0",
                           "okta", "secrets manager", "vault", "keycloak")),
    ("Observability", ("observability", "monitoring", "telemetry", "metrics", "tracing", "sentry",
                       "datadog", "analytics", "mixpanel", "apm", "log store", "log forward",
                       "feature flag", "unleash", "statsd")),
    ("Messaging & delivery", ("email", "smtp", "sendgrid", "mailgun", "mailchimp", "mailjet", "sms",
                              "twilio", "push notification", "notification")),
    ("AI & ML", ("llm", "openai", "anthropic", "claude", "inference", "speech", "text-to-speech",
                 "tts", "image generation", "embedding", " ml ", "machine learning")),
    ("Data & storage", ("database", "datastore", "data store", "sql", "postgres", "mysql", "mongo",
                        "redis", "cache", "object storage", "blob storage", "warehouse",
                        "elasticsearch", "dynamodb", "s3", "key-value", "vector db")),
    ("Infrastructure & runtime", ("docker", "container", "kubernetes", "k8s", "nginx",
                                  "reverse proxy", "cdn", "sandbox", "load balancer", "serverless",
                                  "cloud runtime")),
)
_BUCKET_SIGNATURES_LIBRARY: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Frontend / UI", ("react", "vue", "angular", "svelte", "vite", "tailwind", "frontend",
                       " ui ", "spa", "router", "css")),
    ("Data drivers", ("driver", "motor", "pymongo", "sqlalchemy", "orm", "coredis", "redis client",
                      "prisma", "database driver", "asyncpg")),
    ("Web framework / server", ("framework", "fastapi", "flask", "django", "express", "starlette",
                                "uvicorn", "asgi", "wsgi", "rails", "spring", "gunicorn")),
    ("Validation / models", ("pydantic", "validation", "serialization", "marshmallow", "schema")),
    ("Logging", ("structlog", "logging", "logger")),
    ("Crypto / security", ("crypto", "cryptograph", "encryption", "jwt", "hashing", "security")),
    ("Service SDKs", ("sdk", "api client", "protocol", "client library")),
)


def classify_bucket(is_library: bool, type_cell: str, used_for: str) -> str:
    """The dep's purpose bucket when none is authored: infer from `type` + `used_for`, falling back
    to the diagram's catch-all. `is_library` picks the code seeds vs. the external seeds so a folded
    dep never lands in an external bucket (and vice-versa)."""
    hay = f" {type_cell} {used_for} ".lower()
    sigs = _BUCKET_SIGNATURES_LIBRARY if is_library else _BUCKET_SIGNATURES_EXTERNAL
    for bucket, needles in sigs:
        if any(n in hay for n in needles):
            return bucket
    return DEP_BUCKET_CATCHALL_LIBRARY if is_library else DEP_BUCKET_CATCHALL_EXTERNAL


def resolve_bucket(is_library: bool, authored: str, type_cell: str, used_for: str) -> str:
    """The dep's FINAL bucket: the authored one (canonicalized) or the heuristic fallback. The single
    resolver both the markdown/panel view and the diagram grouping call, so a dep's shown bucket and
    the cluster it groups into never disagree."""
    if (authored or "").strip():
        return canonical_bucket(authored)
    return classify_bucket(is_library, type_cell, used_for)


def order_buckets(names: Iterable[str], is_library: bool) -> list[str]:
    """The buckets present, in the DETERMINISTIC diagram order: seeds first (in seed order), then
    minted buckets alphabetically, then the catch-all last. Canonicalizes + de-dups on the way in."""
    seeds = DEP_BUCKET_SEEDS_LIBRARY if is_library else DEP_BUCKET_SEEDS_EXTERNAL
    catchall = DEP_BUCKET_CATCHALL_LIBRARY if is_library else DEP_BUCKET_CATCHALL_EXTERNAL
    present = list(dict.fromkeys(canonical_bucket(n) for n in names if (n or "").strip()))
    seed_order = [b for b in seeds if b in present and b != catchall]
    minted = sorted(b for b in present if b not in seeds and b != catchall)
    tail = [catchall] if catchall in present else []
    return seed_order + minted + tail


# An entry point's ACTIVATION — a closed vocabulary describing WHO starts it. "self" = the system
# starts it with no outside caller (a scheduled/cron job, a while-True or interval loop, a
# background worker/thread, a queue/stream consumer, a boot/startup hook, an OS signal handler);
# "external" = something outside asks (an HTTP route, a CLI invocation, a callback, a webhook).
# Authored in an OPTIONAL T4 `activation` column; when absent, classify_activation() infers it from
# `kind`. Lets a reader answer "what runs with no user?" at a glance.
ACTIVATIONS = ("self", "external")

# Keyword signatures for a SELF-starting entry point, matched case-insensitively as substrings of
# the free-text `kind`. Deliberately excludes "webhook" (an external caller invokes it).
_SELF_START_SIGNATURES = ("background", "loop", "cron", "schedul", "timer", "tick", "interval",
                          "poll", "boot", "startup", "start-up", "on_event", "lifespan", "signal",
                          "sigterm", "sighup", "atexit", "shutdown", "daemon", "worker", "consumer",
                          "subscrib", "queue", "listener", "watch")


def classify_activation(kind: str) -> str:
    """The entry point's activation (one of ACTIVATIONS): "self" if it starts itself
    (timer/loop/boot/signal/queue consumer), else "external" (route/CLI/callback/webhook — something
    outside asks). Heuristic over the free-text `kind`; the authored `activation` column is the
    accurate path and this is the fallback when it's absent. Unrecognised → "external" (the common
    case, and the safe default)."""
    k = (kind or "").lower()
    return "self" if any(s in k for s in _SELF_START_SIGNATURES) else "external"


def effective_activation(activation: str, kind: str) -> str:
    """The activation a consumer should act on: the authored value when it is a member of the closed
    vocabulary (EXACT match — `validate` blocks anything else, because a near-miss like "External" or
    "mounted" is truthy and would otherwise silently reroute the entry point through the kind
    heuristic), else `classify_activation(kind)`. The one rule shared by the viewer, the entry-surface
    coverage advisory, and the eval profile — so they can never classify the same row differently."""
    return activation if activation in ACTIVATIONS else classify_activation(kind)


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

# ── Backbone edge verb → ROLE ──────────────────────────────────────────────────────────────────────
# The verb families that decide what a backbone edge MEANS — the ONE place backbone-verb meaning is
# decided (like REL_KIND / CANONICAL_VERB above for entity relations). `assemble._infer_ce_verb` reads
# the persist/write/emit/encrypt families to derive a C→E edge's verb; `edge_role` reads all of them
# (plus the read + call families) to derive a dependency's ROLE from its incoming C→D verbs. Moving
# them here keeps the fix landing once — a new verb is added in a single place, never copied.
#
# The persist/write/emit/encrypt families keep the EXACT membership they had in assemble.py so the C→E
# derivation cannot regress; the read + call families are additions for the role classification.
PERSIST_VERBS = frozenset("persist persists store stores stored upsert upserts save saves saved "
                          "insert inserts inserted".split())
WRITE_VERBS = frozenset("write writes wrote update updates updated create creates created delete "
                        "deletes deleted remove removes removed append appends set sets put puts "
                        "record records add adds modify modifies increment decrement".split())
EMIT_VERBS = frozenset("emit emits emitted publish publishes dispatch dispatches broadcast "
                       "broadcasts enqueue enqueues".split())
ENCRYPT_VERBS = frozenset("encrypt encrypts encrypted decrypt decrypts".split())
# A READ of a data store — `queries`/`fetches` map here, NOT to service: "queries the database" /
# "fetches the record" are the standard way to describe a store read, so a `queries` edge on a SQL dep
# derives 'datastore'. (`_infer_ce_verb` still DEFAULTS ambiguous phrases to `reads`; this set only
# drives `edge_role`, so it never changes that derivation.)
READ_VERBS = frozenset("read reads queries query fetch fetches get gets load loads lookup lookups "
                       "select selects scan scans".split())
# An unambiguous SERVICE call — reserved for genuine call verbs (NOT queries/fetches, which are reads).
CALL_VERBS = frozenset("call calls called request requests requested invoke invokes invoked".split())
# Generic / ROLELESS verbs — a C→D edge using one names no role (the thing the WS2 nudge flags).
# `edge_role` maps every one of these (and any unrecognized verb) to None.
GENERIC_VERBS = frozenset("uses use used integrates integrate integrated connects connect connected "
                          "accesses access accessed talks talk".split())


def edge_role(verb: str) -> str | None:
    """The ROLE a backbone edge's verb reveals: 'datastore' (persist/write/read families — a query IS a
    read), 'messaging' (emit family), 'service' (call family ONLY), 'security' (encrypt family), or None
    for a generic/roleless verb (`uses`/`connects`/…) or any unrecognized verb — the None case is what
    the C→D role nudge flags. A dependency's role SET is the union of its incoming C→D edges' roles
    (`dep_roles`), so a dual-role dep (Redis as bus + store) is captured by its two real verbs, not a
    stored field."""
    v = (verb or "").strip().lower()
    if v in PERSIST_VERBS or v in WRITE_VERBS or v in READ_VERBS:
        return "datastore"
    if v in EMIT_VERBS:
        return "messaging"
    if v in CALL_VERBS:
        return "service"
    if v in ENCRYPT_VERBS:
        return "security"
    return None


def dep_roles(verbs: Iterable[str]) -> set[str]:
    """The role SET a dependency plays, DERIVED from the verbs of its incoming C→D edges: each verb's
    `edge_role`, minus the roleless None. `[publishes, writes]` → `{messaging, datastore}` ('bus ·
    store'); no C→D edges → empty set (renders no role tag). Purely derived, so it can never drift from
    the edges (no parallel stored field)."""
    return {r for r in (edge_role(v) for v in verbs) if r is not None}


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
) -> tuple[list[str], str | None]:
    """Which REAL field(s) implement a domain relation `src --> dst`, and on which side. Each field is
    a `(name, type, fk_targets)` triple. Forward (the field lives on the source / arrow-tail) wins over
    reverse, mirroring how the relation is authored on the source card:
      - SOURCE fields typed by the target (`subscription:E15`) or marked `FK→dst` -> (names, 'src');
      - else TARGET fields marked `FK→src` (the back-reference) -> (names, 'dst');
      - else ([], None) — no field backs it (indirect / key-composition; carry a `{how}` note).
    ALL qualifying fields on the winning side are returned, in declaration order — a composite key
    (e.g. Snapshot's (user_id, page_id) both `FK→TrackedPage`) yields both, so the label shows the
    whole key instead of arbitrarily keeping just the first field. The canvas label and the panel's
    "Implemented by" line both derive from this one resolution."""
    fwd = [name for name, typ, fks in src_fields if typ == dst or dst in fks]
    if fwd:
        return fwd, "src"
    rev = [name for name, _typ, fks in dst_fields if src in fks]
    if rev:
        return rev, "dst"
    return [], None


# ── T6 use-case flows ─────────────────────────────────────────────────────────────────────────────
# `views.py` builds a Flow/FlowStep per use case straight from the model's `Flow`/`FlowStep`
# records (not from a markdown parse); `is_step_id` classifies each endpoint (an element ID vs a Role
# display name) so the viewer knows whether a step is a backbone reference or an actor interaction.
_STEP_ENDPOINT_ID = re.compile(r"^(?:UC\d+|SD\d+|C\d+|D\d+|E\d+|S\d+)$")


def is_step_id(token: str) -> bool:
    """True if `token` is a BACKBONE element ID (C/D/E/UC/S/SD); False -> an actor step (a role).
    Deliberately does NOT match a role id `R\\d+`: `_flow_opening_actor` finds the actor step by
    `not is_step_id(src)`, so teaching this `R` would skip every actor step and silently blank the
    actor-attribution check. A role id is classified by `is_role_id`, separately."""
    return bool(_STEP_ENDPOINT_ID.match(token.strip()))


_ROLE_ID = re.compile(r"^R\d+$")


def is_role_id(token: str) -> bool:
    """True if `token` is a Role id (`R1`, `R2`, …) — the id an actor step / use-case actor references."""
    return bool(_ROLE_ID.match(token.strip()))


@dataclass
class FlowStep:
    n: int               # the step number as written
    src: str             # an element ID (C/D/E/…) or a Role display name
    dst: str             # same
    src_is_id: bool      # True -> src is an element ID; False -> a Role name (actor step)
    dst_is_id: bool
    phrase: str = ""     # authored inline phrase (after ": ") — e.g. the actor's action
    note: str = ""       # flow-specific note (after "· ")
    where: str | None = None  # THE location: the step's own call site (`path:line`), if authored
    subflow: str | None = None  # a reference step: "runs SFn here" (see model.FlowStep.subflow)
    ok: bool = True      # False -> the line could not be split into `from → to`


@dataclass
class Flow:
    uc: str              # the use case this flow realizes (its UC id, DEFINED in the Use-cases table)
    title: str
    steps: list[FlowStep]
    line_no: int
