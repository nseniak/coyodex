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

from coyodex import grammar

FORMAT = "coyodex-map"

# Each element array's required id prefix — structural (a `Cn` in `deps` is a shape error, caught at
# load), while uniqueness/resolution stay semantic (validate_model).
ID_SHAPE = re.compile(r"^(UC|HP|SD|SF|C|D|E|S|R)\d+$")


class ModelError(ValueError):
    """A structural violation in a model document, carrying the JSON path of the offending value."""


# ── the model ────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Role:
    id: str                   # Rn — a role is a first-class element, referenced by id (not by name)
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
    actors: list[str] = field(default_factory=list)  # the role ids that drive this use case (was a
                                                     # single free-text `actor` name in the pre-role-id format)
    trigger_outcome: str = ""


@dataclass
class HappyStep:
    id: str                   # HPn — the position in the walk
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
    runs_in: list[str] = field(default_factory=list)     # deployment unit name(s) whose PROCESS runs this
                                     # component's code — a runtime placement (the C4 instance link),
                                     # powering the Deployment view. Verified for a satellite (own dir/
                                     # image), inferred for the shared monolith; empty = untraced. Each
                                     # value must resolve to a `deployment[].unit` (validate).
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
    bucket: str = ""                 # PURPOSE bucket (seeded-open) — groups the dep within its diagram
                                     # (Context externals / Libraries drill); "" → inferred from type+used_for
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
    source: str = ""                 # bare `path:line` anchor: where the command is defined (script /
                                     # Makefile target / config line) — not a markdown link, not prose


@dataclass
class EntryPoint:                    # T4
    kind: str
    trigger: str = ""
    source: str = ""                 # md link to the code entity — where the entry point LIVES
    component: str = ""              # the owning C id
    activation: str = ""             # "self" | "external" (grammar.ACTIVATIONS); "" → inferred from kind
    runs_in: list[str] = field(default_factory=list)  # the PRECISE host unit(s) of a self-started thread
                                     # (a loop's exact process, since its component may run in several);
                                     # empty → falls back to the owning component's runs_in in the
                                     # Deployment view. Each value must resolve to a `deployment[].unit`.


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
    keyed_by: list[str] = field(default_factory=list)  # storage KEY name(s) the store uses to relate
                                     # the two — a lookup/partition key it imposes, NOT a field on
                                     # EITHER entity's row (e.g. a per-parent store keyed by
                                     # `parent_id`). Distinct from a real FK field (`fk_fields`): if a
                                     # field carries the id, that is a (reverse) FK, not a key. Drawn
                                     # on the arrow with the «key» marker, never in the field box.


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
    source: str | None = None        # bare `path:line` anchor (or a `path/` dir) to where the type is
                                     # defined — same shape as entity.source, not a markdown link
    why: str = ""


@dataclass
class FlowStep:
    n: int
    src: str                         # an element ID or a Role display name (actor step)
    dst: str
    phrase: str = ""                 # authored inline action text (required on every step — `validate`;
                                     # EXEMPT on a sub-flow reference step, where it defaults to the
                                     # sub-flow's name)
    note: str = ""                   # flow-specific note
    where: str | None = None         # THE location: bare `path:line` of this step's own call site —
                                     # unlike an edge's `where` (an example among possibly many), a step
                                     # is exactly one interaction, so its anchor is precise. Required on
                                     # element↔element steps (`validate` blocks) unless `no_call_site`;
                                     # optional on actor steps (a human action has no call site).
    no_call_site: bool = False       # opt-out, mirroring Edge.no_call_site: this step has no single
                                     # call site (event-driven / config-wired) — `where` may be null.
    subflow: str | None = None       # a REFERENCE step: "runs SFn here". src/dst stay authored (the
                                     # run's entry/exit endpoints — every unexpanded consumer keeps
                                     # working); the step carries NO where/no_call_site of its own
                                     # (its location IS the sub-flow's steps' anchors — `validate`
                                     # blocks a contradiction). One level only: a sub-flow's step may
                                     # not itself reference a sub-flow.


@dataclass
class Flow:                          # T6 — the inside view of one use case
    uc: str
    title: str
    steps: list[FlowStep] = field(default_factory=list)


@dataclass
class SubFlow:
    """A named, reusable step sequence (an "include" fragment): machinery shared by ≥2 use-case
    flows — an OAuth dance, an event fan-out — defined ONCE and referenced by a FlowStep whose
    `subflow` names it. Steps are ordinary FlowSteps under all the ordinary rules (phrase, anchors,
    unique `n`); nesting is forbidden (one level). Extracting a shared run keeps every flow that
    rides it at the same depth — the alternative is each flow retelling it at whatever grain its
    author happened to pick."""
    id: str                          # SFn
    name: str
    steps: list[FlowStep] = field(default_factory=list)


@dataclass
class Edge:                          # one backbone edge (C↔C, C↔D, C→E)
    src: str
    verb: str
    dst: str
    why: str | None = None
    where: str | None = None         # the call site: bare `path:line` in src's code where it invokes dst
    no_call_site: bool = False       # opt-out: this relationship has no single call site (event-driven /
                                     # shared-state / config-wired coupling) — `where` may be null. Without
                                     # it, a missing `where` is a blocking `validate` error, not a warning.


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
    source: str = ""                 # bare `path:line` anchor to the auth check in code — an L2
                                     # grounding claim (was a markdown link; now a bare anchor)
    risk: str = ""


@dataclass
class ConfigRow:
    key: str
    purpose: str = ""
    default: str = ""
    per_env: str = ""


@dataclass
class TestRow:
    """One row of the test-completeness gap table. `targets` names the element ids this row assesses
    (explicit, not parsed out of prose), `tests` cites the exercising suites/files as `{file, why}`
    evidence (bare anchors, so the viewer renders them as clickable code links)."""
    targets: list[str]                                        # element ids assessed, e.g. ["C48", "C49"]
    tested: str = ""                                          # yes / partial / no
    label: str = ""                                           # optional display text (grouping / journey name)
    tests: list[EvidenceItem] = field(default_factory=list)   # exercising suites: {file: bare anchor, why: what it covers}
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
    happy_path: list[HappyStep] = field(default_factory=list)
    subsystems: list[Group] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    deps: list[Dep] = field(default_factory=list)
    run_commands: list[RunRow] = field(default_factory=list)
    entry_points: list[EntryPoint] = field(default_factory=list)
    subdomains: list[Group] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    non_entity_types: list[NonEntityType] = field(default_factory=list)
    flows: list[Flow] = field(default_factory=list)
    subflows: list[SubFlow] = field(default_factory=list)
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
    "use_cases": "UC", "happy_path": "HP", "subsystems": "S", "components": "C",
    "deps": "D", "subdomains": "SD", "entities": "E", "roles": "R", "subflows": "SF",
}


def expanded_flow_steps(m: ProjectModel, f: Flow) -> list[FlowStep]:
    """The flow's steps with each sub-flow REFERENCE step replaced inline by the referenced
    sub-flow's steps — the model-level analog of the viewer's graph-level expansion
    (gen_viewer.expanded_steps). Consumers that reason about "what this flow touches" (impact
    ripple, the model audit) walk THIS, so content inside a sub-flow is never invisible.
    An unresolved or empty reference degrades to the bare reference step."""
    sfs = {sf.id: sf for sf in m.subflows}
    out: list[FlowStep] = []
    for st in f.steps:
        sf = sfs.get(st.subflow or "")
        if sf is None or not sf.steps:
            out.append(st)
        else:
            out.extend(sf.steps)
    return out


def all_elements(m: ProjectModel) -> dict[str, object]:
    """Every DEFINED element keyed by id, in document order (later duplicates keep the first —
    duplicate ids are a validate_model problem, not a load problem)."""
    out: dict[str, object] = {}
    for attr in ID_ARRAYS:
        for el in getattr(m, attr):
            out.setdefault(el.id, el)
    return out


# ── element-id remap (the mutable twin of validate_model._referenced_ids) ─────────────────────────

_BRACKET_REF = re.compile(r"\[\[([^\]]+)\]\]")


def _map_strings(value: object, fn) -> None:
    """Apply `fn` to every `str` in a dataclass / list / dict tree, in place."""
    if hasattr(value, "__dataclass_fields__"):
        for f in fields(value):  # type: ignore[arg-type]
            v = getattr(value, f.name)
            if isinstance(v, str):
                setattr(value, f.name, fn(v))
            else:
                _map_strings(v, fn)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            if isinstance(v, str):
                value[i] = fn(v)
            else:
                _map_strings(v, fn)
    elif isinstance(value, dict):
        for k in list(value.keys()):
            v = value[k]
            if isinstance(v, str):
                value[k] = fn(v)
            else:
                _map_strings(v, fn)


def _remap_str_ids(text: str, remap: dict[str, str]) -> str:
    """Rewrite whole id TOKENS in a dedicated id-bearing string field (an FK marker `FK→E7`, an
    entity-typed field `auth:E7`, a role's `drives` cell) — never arbitrary prose."""
    if not text:
        return text
    return grammar.ID_TOKEN.sub(lambda mo: remap.get(mo.group(0), mo.group(0)), text)


def remap_element_ids(m: ProjectModel, remap: dict[str, str]) -> None:
    """Rewrite every REFERENCE to a remapped element id, in place — the mutable twin of
    `validate_model._referenced_ids`. When a merge collapses one element id into another (assemble's
    cross-slice component dedup, or a `fix` verb), the merged-away id must not survive anywhere it was
    referenced, or `validate` blocks on a dangling reference. This rewrites references ONLY; it never
    touches an element's own defining `id` (the caller drops the merged-away definition). Kept
    field-for-field in step with `_referenced_ids` so the read and the write can't drift — a regression
    test (`test_remap_covers_referenced_ids`) fails if a new reference site is added to one and not the
    other."""
    if not remap:
        return

    def r(x: str) -> str:
        return remap.get(x, x)

    for g in m.happy_path:
        if g.uc:
            g.uc = r(g.uc)
    for steps in [f.steps for f in m.flows] + [sf.steps for sf in m.subflows]:
        for st in steps:
            st.src = r(st.src)
            st.dst = r(st.dst)
            if st.subflow:
                st.subflow = r(st.subflow)
    for e in m.edges:
        e.src = r(e.src)
        e.dst = r(e.dst)
    for ep in m.entry_points:
        comp = ep.component.strip()
        if comp in remap:
            ep.component = remap[comp]
    for en in m.entities:
        if en.subdomain:
            en.subdomain = r(en.subdomain)
        for rel in en.relations:
            if rel.target:
                rel.target = r(rel.target)
        for fld in en.fields:
            fld.type = _remap_str_ids(fld.type, remap)
            fld.markers = [_remap_str_ids(mk, remap) for mk in fld.markers]
    for role in m.roles:
        role.drives = _remap_str_ids(role.drives, remap)
    for tr in m.tests:
        tr.targets = [r(t) for t in tr.targets]

    def _brackets(s: str) -> str:
        return _BRACKET_REF.sub(
            lambda mo: f"[[{remap[mo.group(1).strip()]}]]" if mo.group(1).strip() in remap else mo.group(0),
            s,
        )

    _map_strings(m, _brackets)


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
