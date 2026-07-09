#!/usr/bin/env python3
"""The canonical map model (JSON source). See method/model.md.

`.coyodex/project-map.json` is the committed source of truth; the markdown map and the HTML
diagram are generated views. This module is the model's single definition: the typed dataclasses,
the DETERMINISTIC serializer (same model → byte-identical JSON, so the committed file diffs
cleanly), and the structural loader (`load_model`), which validates shape/types field-by-field and
reports the exact path of a violation — the "schema validation" half of `coyodex validate`.

Stdlib-only, like every core tool. Semantic checks (IDs resolve, hierarchy sound, code anchors
exist) are NOT here — they are `validate_model.py`'s job; this module only guarantees that a loaded
object IS a well-typed model.
"""
from __future__ import annotations

import json
import re
import types
from dataclasses import dataclass, field, fields
from typing import Union, get_args, get_origin, get_type_hints

FORMAT = "coyodex-map"

# Each element array's required id prefix — structural (a `Cn` in `deps` is a shape error, caught at
# load), while uniqueness/resolution stay semantic (validate_model).
ID_SHAPE = re.compile(r"^(UC|GP|SD|C|D|E|S)\d+$")


class ModelError(ValueError):
    """A structural violation in a model document, carrying the JSON path of the offending value."""


# ── the model ────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Role:
    name: str
    kind: str = ""            # human | service (free text preserved; the viewer normalizes)
    wants: str = ""
    drives: str = ""          # the "Use cases they drive" cell (UC ids inside)


@dataclass
class GlossaryRow:
    term: str
    meaning: str = ""
    source: str | None = None  # the term's canonical code home: a bare `path:line` or `path/`
                               # anchor (like Component.source / Entity.source), or None when the
                               # concept has no single code home (a pure product-level term)


@dataclass
class UseCase:
    id: str
    name: str
    actor: str = ""
    trigger_outcome: str = ""


@dataclass
class GoldenStep:
    id: str                   # GPn — the position in the walk
    title: str
    uc: str | None = None     # the use case this step realizes (required by validate)
    why: str | None = None    # the prerequisite that fixes this step's position


@dataclass
class Group:
    """A subsystem (S) or subdomain (SD) — same shape, two forests."""
    id: str
    name: str
    purpose: str = ""
    parent: str | None = None
    source: str | None = None  # bare path anchor to the group's home: a file `path:line`, or a
                               # directory ref ending in `/` (like Component.source / Entity.source)
    confidence: str = ""


@dataclass
class EvidenceItem:
    """One citation grounding a claim the map makes about the element carrying it — a
    fresh-context skeptic re-reads `file` and checks whether `why` still holds."""
    file: str                        # bare path:line anchor
    why: str


@dataclass
class Component:
    id: str
    name: str
    subsystem: str | None = None
    purpose: str = ""
    entry_point: str | None = None   # md link cell
    depends_on: str = ""             # the coarse derived summary text (edge list is the source)
    source: str | None = None        # v2: the canonical source anchor — where the component LIVES
    confidence: str = ""
    files: list[str] = field(default_factory=list)       # repo-relative paths this component owns
    evidence: list[EvidenceItem] = field(default_factory=list)
    extra: dict[str, object] = field(default_factory=dict)  # non-standard authored columns, by
    # header; values are any JSON value (agents return lists/numbers/bools naturally — the views
    # render non-string values as compact JSON). A key `coyodex validate` gives a fixed shape to
    # (or the method otherwise defines) does not belong here — it graduates to a real field instead.


@dataclass
class Dep:
    id: str
    name: str
    kind: str | None = None          # closed Context vocabulary; None → inferred from `type`
    type: str = ""
    used_for: str = ""
    where_configured: str = ""
    confidence: str = ""
    deployment_linked: bool = False  # v2: wired at deployment level only — no code call site
    package: str = ""                # "<name> <version> (<where declared>)"
    alternative: str = ""            # the fallback used instead, and when
    evidence: list[EvidenceItem] = field(default_factory=list)
    extra: dict[str, object] = field(default_factory=dict)  # any JSON values, like Component.extra


@dataclass
class RunRow:                        # T3
    action: str
    command: str = ""
    source: str = ""


@dataclass
class EntryPoint:                    # T4
    kind: str
    trigger: str = ""
    source: str = ""                 # md link to the code entity — where the entry point LIVES
    component: str = ""              # the owning C id


@dataclass
class EntityField:
    name: str
    type: str = ""
    markers: list[str] = field(default_factory=list)  # PK / FK→En / unique / ? / []


@dataclass
class EntityRelation:
    verb: str                        # contains / has / isA / free association verb
    target: str                      # En
    src_card: str | None = None      # cardinality pair — both or neither
    dst_card: str | None = None
    display: str = ""                # optional display text after the target id
    how: str | None = None           # plain-text note: how a field-less relation is implemented


@dataclass
class Entity:                        # a T5 domain card
    id: str
    name: str
    store: str = ""
    meaning: str = ""
    subdomain: str | None = None
    source: str | None = None        # path:line anchoring the real named type
    fields: list[EntityField] = field(default_factory=list)
    relations: list[EntityRelation] = field(default_factory=list)


@dataclass
class NonEntityType:
    """v2: an explicit plumbing marker — a named type in the domain dirs that is deliberately NOT an
    entity, so the under-harvest coverage check must not count it as unmodelled."""
    name: str
    source: str | None = None
    why: str = ""


@dataclass
class FlowStep:
    n: int
    src: str                         # an element ID or a Role display name (actor step)
    dst: str
    phrase: str = ""                 # authored inline phrase (actor steps)
    note: str = ""                   # flow-specific note


@dataclass
class Flow:                          # T6 — the inside view of one use case
    uc: str
    title: str
    steps: list[FlowStep] = field(default_factory=list)


@dataclass
class Edge:                          # one backbone edge (C↔C, C↔D, C→E)
    src: str
    verb: str
    dst: str
    why: str | None = None
    where: str | None = None         # the call site in src's code (md link)


@dataclass
class DeploymentRow:
    unit: str
    runs_on: str = ""
    exposed_as: str = ""
    config_source: str = ""


@dataclass
class ObservabilityRow:
    signal: str
    where_emitted: str = ""
    where_viewed: str = ""
    alerts: str = ""


@dataclass
class SecurityRow:
    surface: str
    who: str = ""
    source: str = ""                 # md link to the auth check — an L2 grounding claim
    risk: str = ""


@dataclass
class ConfigRow:
    key: str
    purpose: str = ""
    default: str = ""
    per_env: str = ""


@dataclass
class TestRow:
    target: str
    tested: str = ""
    tests: str = ""
    gap: str = ""
    confidence: str = ""


@dataclass
class ExtraSection:
    """An unrecognized authored section, preserved verbatim so a converted map loses no content."""
    heading: str
    body: str = ""


@dataclass
class ProjectModel:
    """The whole map. Field order IS the canonical JSON key order (the serializer relies on it)."""
    format: str = FORMAT
    title: str = ""
    goal: str = ""
    commit: str | None = None
    committed: str | None = None
    built: str | None = None
    roles: list[Role] = field(default_factory=list)
    glossary: list[GlossaryRow] = field(default_factory=list)
    use_cases: list[UseCase] = field(default_factory=list)
    golden_path: list[GoldenStep] = field(default_factory=list)
    subsystems: list[Group] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    deps: list[Dep] = field(default_factory=list)
    run_commands: list[RunRow] = field(default_factory=list)
    entry_points: list[EntryPoint] = field(default_factory=list)
    subdomains: list[Group] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    non_entity_types: list[NonEntityType] = field(default_factory=list)
    flows: list[Flow] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    deployment: list[DeploymentRow] = field(default_factory=list)
    observability: list[ObservabilityRow] = field(default_factory=list)
    security: list[SecurityRow] = field(default_factory=list)
    config: list[ConfigRow] = field(default_factory=list)
    tests_note: str = ""
    tests: list[TestRow] = field(default_factory=list)
    extras: list[ExtraSection] = field(default_factory=list)


# The element arrays that DEFINE ids, with each one's required prefix. `S` must not match `SD` (both
# start with "S"), so validation matches the WHOLE id against ID_SHAPE and then the exact prefix.
ID_ARRAYS: dict[str, str] = {
    "use_cases": "UC", "golden_path": "GP", "subsystems": "S", "components": "C",
    "deps": "D", "subdomains": "SD", "entities": "E",
}


def all_elements(m: ProjectModel) -> dict[str, object]:
    """Every DEFINED element keyed by id, in document order (later duplicates keep the first —
    duplicate ids are a validate_model problem, not a load problem)."""
    out: dict[str, object] = {}
    for attr in ID_ARRAYS:
        for el in getattr(m, attr):
            out.setdefault(el.id, el)
    return out


# ── deterministic serializer ─────────────────────────────────────────────────────────────────────

def _plain(value: object) -> object:
    """A dataclass tree as plain JSON values, keys in dataclass field order (deterministic).
    `extra` dicts are emitted with sorted keys so authored-column order can never wobble a diff."""
    if hasattr(value, "__dataclass_fields__"):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}  # type: ignore[arg-type]
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(value[k]) for k in sorted(value)}
    return value


def to_canonical_json(m: ProjectModel) -> str:
    """The one serialization: fixed key order, indent=2, no ASCII-escaping, trailing newline.
    Same model → byte-identical output, so the committed source diffs cleanly."""
    return json.dumps(_plain(m), indent=2, ensure_ascii=False) + "\n"


# ── structural loader (the schema-validation half of `coyodex validate`) ─────────────────────────

def _check(value: object, hint: object, path: str) -> object:
    """Validate `value` against a type hint, returning the built (dataclass-ified) value.
    Handles exactly the shapes the model uses: str, int, bool, X|None, list[T], dict[str,str],
    and nested dataclasses. Raises ModelError with the JSON path of the first violation."""
    origin = get_origin(hint)
    if origin is Union or origin is types.UnionType:  # only `X | None` appears in the model
        args = [a for a in get_args(hint) if a is not type(None)]
        if value is None:
            return None
        return _check(value, args[0], path)
    if hint is str:
        if not isinstance(value, str):
            raise ModelError(f"{path}: expected a string, got {type(value).__name__}")
        return value
    if hint is int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ModelError(f"{path}: expected an integer, got {type(value).__name__}")
        return value
    if hint is bool:
        if not isinstance(value, bool):
            raise ModelError(f"{path}: expected a boolean, got {type(value).__name__}")
        return value
    if origin is list:
        if not isinstance(value, list):
            raise ModelError(f"{path}: expected an array, got {type(value).__name__}")
        (item_hint,) = get_args(hint)
        return [_check(v, item_hint, f"{path}[{i}]") for i, v in enumerate(value)]
    if origin is dict:
        if not isinstance(value, dict):
            raise ModelError(f"{path}: expected an object, got {type(value).__name__}")
        _key_hint, val_hint = get_args(hint)
        if val_hint is object:  # `extra`: any JSON value is welcome (str/number/bool/null/list/dict)
            return {str(k): _check_json_value(v, f"{path}.{k}") for k, v in value.items()}
        return {str(k): _check(v, val_hint, f"{path}.{k}") for k, v in value.items()}
    if hasattr(hint, "__dataclass_fields__"):
        return _build(value, hint, path)  # type: ignore[arg-type]
    raise ModelError(f"{path}: unsupported schema type {hint!r}")  # unreachable on the fixed model


def _check_json_value(value: object, path: str) -> object:
    """Any JSON value, validated recursively (dict keys coerced to str). Defensive: everything the
    loader sees came out of json.loads, but fragments built in-process must obey the same shape."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_check_json_value(v, f"{path}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, dict):
        return {str(k): _check_json_value(v, f"{path}.{k}") for k, v in value.items()}
    raise ModelError(f"{path}: not a JSON value ({type(value).__name__})")


def _build(data: object, cls: type, path: str):
    if not isinstance(data, dict):
        raise ModelError(f"{path}: expected an object, got {type(data).__name__}")
    hints = get_type_hints(cls)
    kwargs: dict[str, object] = {}
    known = {f.name for f in fields(cls)}
    for key in data:
        if key not in known:
            raise ModelError(f"{path}.{key}: unknown field")
    for f in fields(cls):
        if f.name in data:
            kwargs[f.name] = _check(data[f.name], hints[f.name], f"{path}.{f.name}")
        # an absent field takes its dataclass default; a missing REQUIRED field (no default)
        # surfaces as the TypeError below, reported with this path
    try:
        return cls(**kwargs)  # missing REQUIRED fields (no default) raise TypeError
    except TypeError as e:
        raise ModelError(f"{path}: {e}") from e


def load_model(text: str) -> ProjectModel:
    """Parse + structurally validate a project-map.json document. Raises ModelError on any shape
    violation (bad JSON, wrong type, unknown field, missing required field, wrong id prefix)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ModelError(f"not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ModelError("top level: expected an object")
    fmt = data.get("format")
    if fmt != FORMAT:
        raise ModelError(f"format: expected '{FORMAT}', got {fmt!r}")
    m = _build(data, ProjectModel, "$")
    for attr, prefix in ID_ARRAYS.items():
        for i, el in enumerate(getattr(m, attr)):
            eid = el.id
            good = bool(ID_SHAPE.match(eid)) and re.match(r"[A-Z]+", eid).group(0) == prefix  # type: ignore[union-attr]
            if not good:
                raise ModelError(f"$.{attr}[{i}].id: '{eid}' is not a valid {prefix}-id "
                                 f"(a schema id is the prefix + digits only, e.g. {prefix}3)")
    return m


def load_model_path(path) -> ProjectModel:
    """`load_model` from a file path (the common CLI entry)."""
    from pathlib import Path
    return load_model(Path(path).read_text(encoding="utf-8"))
