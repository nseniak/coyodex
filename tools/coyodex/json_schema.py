#!/usr/bin/env python3
"""Generate a JSON Schema for `project-map.json`, straight from the model dataclasses.

Documentation and IDE-autocomplete use ONLY — this is NOT wired into `coyodex validate`. Reason:
the existing structural loader (`model._build`/`_check`) already gives path-specific errors a
generic JSON-Schema validator library can't match ("$.components[3].purpose: expected a string,
got int" vs. a typical library's "is not of type 'string'"), and most of the REAL validation here
is semantic — ID references resolve, no hierarchy cycles, anchor formats — which JSON Schema
cannot express at all. So a schema-based validator would need `validate_model.py` to run anyway,
adding a second validation mechanism without removing the first. As pure documentation, though, it
is genuinely useful (IDE autocomplete while hand-inspecting a fragment, an interoperable artifact
for non-Python tooling) — and since it is GENERATED from the dataclasses, it cannot drift out of
sync the way a hand-maintained schema file would.

Regenerate after any model.py change:
    python -m coyodex.json_schema > method/project-map.schema.json
Stdlib-only.
"""
from __future__ import annotations

import json
import types
from dataclasses import MISSING, fields as dc_fields, is_dataclass
from typing import Union, get_args, get_origin, get_type_hints

from coyodex import grammar
from coyodex.model import FORMAT, ID_SHAPE, ProjectModel
from coyodex.anchors import FILE_ANCHOR as _ANCHOR_LINE

_PRIMITIVE = {str: "string", int: "integer", bool: "boolean"}

_ANCHOR_DESC = ("bare `path:line` anchor: a repo-relative file path, optionally followed by "
                "`:line` or `:line-line` — never a markdown link (its label would just be the "
                "basename, fully derivable from the path, so it is never authored).")
_DIR_OR_FILE_DESC = ("either a bare file `path:line` anchor (see `evidence[].file`'s description) "
                      "or a bare directory ref ending in `/`.")
_EXTRA_DESC = ("freeform authored columns — any JSON value, agent-chosen keys. The ONE place with "
               "no fixed meaning: a key `coyodex validate` gives an enforced shape to, or that the "
               "method documents as a convention, graduates to a real field instead and is then "
               "rejected here under its old spelling (this is how `files`/`evidence`/`package`/"
               "`alternative` were promoted).")

# (dataclass name, field name) -> schema overrides, merged onto the structurally-inferred type.
# `description` explains WHY a constraint exists, not just what it is; `pattern`/`enum`/`const`
# encode the constraint itself where one is actually enforced (by `coyodex validate` or the loader).
FIELD_META: dict[tuple[str, str], dict] = {
    ("Role", "kind"): {"description": "human | service, free text (not a closed vocabulary)."},
    ("Role", "drives"): {"description": "the use cases this role drives — free text, ids inside."},
    ("GlossaryRow", "source"): {"description": _DIR_OR_FILE_DESC + " The term's canonical code home "
                               "(where it is defined); null when the concept has no single code home "
                               "(a pure product-level term)."},
    ("HappyStep", "id"): {"pattern": r"^HP\d+$", "description": "this step's position in the "
                           "ordered walk."},
    ("HappyStep", "uc"): {"pattern": r"^UC\d+$", "description": "the use case this step realizes."},
    ("HappyStep", "why"): {"description": "the prerequisite that fixes this step's position — "
                             "why it can't come earlier in the walk."},
    ("Group", "id"): {"pattern": ID_SHAPE.pattern, "description": "`S<n>` in subsystems[], "
                       "`SD<n>` in subdomains[] — same dataclass, two id forests."},
    ("Group", "parent"): {"pattern": ID_SHAPE.pattern, "description": "the enclosing group's id, "
                           "in the SAME forest (an S parents an S, an SD parents an SD), or null "
                           "for top-level."},
    ("Group", "source"): {"description": _DIR_OR_FILE_DESC + " The group's home directory (or a "
                           "representative file)."},
    ("UseCase", "id"): {"pattern": r"^UC\d+$"},
    ("Role", "id"): {"pattern": r"^R\d+$", "description": "a role is a first-class element (`R<n>`), "
                     "referenced by id — a use case's `actors` and a flow's actor steps carry role ids."},
    ("EvidenceItem", "file"): {"pattern": _ANCHOR_LINE.pattern, "description": _ANCHOR_DESC},
    ("EvidenceItem", "why"): {"description": "why this citation supports the claim — what a "
                               "skeptic re-reading `file` should find true."},
    ("Component", "id"): {"pattern": r"^C\d+$"},
    ("Component", "subsystem"): {"pattern": r"^S\d+$", "description": "the owning subsystem's "
                                  "id, or null if ungrouped."},
    ("Component", "entry_point"): {"pattern": _ANCHOR_LINE.pattern,
                                    "description": _ANCHOR_DESC + " Where the component is "
                                    "TRIGGERED — distinct from `source` (where it LIVES)."},
    ("Component", "source"): {"description": _DIR_OR_FILE_DESC + " Where the component LIVES."},
    ("Component", "files"): {"description": "repo-relative file paths this component owns, as a "
                              "plain list — not a count, not a comma-joined string."},
    ("Component", "extra"): {"description": _EXTRA_DESC},
    ("Dep", "id"): {"pattern": r"^D\d+$"},
    ("Dep", "kind"): {"enum": [*grammar.DEP_KINDS, None], "description": "closed Context "
                       "vocabulary; null → inferred from `type`."},
    ("Dep", "where_configured"): {"pattern": _ANCHOR_LINE.pattern, "description": _ANCHOR_DESC},
    ("Dep", "package"): {"description": 'one string: "<name> <version> (<where declared>)".'},
    ("Dep", "alternative"): {"description": "the fallback used instead of this dep, and under "
                              "what circumstance."},
    ("Dep", "extra"): {"description": _EXTRA_DESC},
    ("EntryPoint", "source"): {"pattern": _ANCHOR_LINE.pattern, "description": _ANCHOR_DESC},
    ("EntryPoint", "component"): {"pattern": r"^C\d+$", "description": "the owning component's id."},
    ("EntryPoint", "activation"): {"enum": [*grammar.ACTIVATIONS, ""], "description": "who starts it: "
                                    "'self' (timer/loop/boot/signal/queue consumer — runs with no "
                                    "caller) or 'external' (route/CLI/callback/webhook); '' → inferred "
                                    "from `kind`."},
    ("EntityField", "markers"): {"description": "annotation tokens, not free text: PK / FK→En / "
                                  "unique / ? / []."},
    ("EntityRelation", "verb"): {"description": "contains / has / isA (structural, canonical) or "
                                  "a free association verb."},
    ("EntityRelation", "target"): {"pattern": r"^E\d+$"},
    ("EntityRelation", "keyed_by"): {"description": "storage key name(s) the store uses to relate the "
                                      "two — a lookup/partition key it imposes, NOT a field on EITHER "
                                      "entity's row. Use ONLY when no field backs the link; if a field "
                                      "carries the id (marked FK or a plain same-named column) that is "
                                      "a (reverse) foreign key, not a key. Drawn on the arrow with the "
                                      "«key» marker."},
    ("Entity", "id"): {"pattern": r"^E\d+$"},
    ("Entity", "subdomain"): {"pattern": r"^SD\d+$", "description": "the owning subdomain's id, "
                               "or null if ungrouped."},
    ("Entity", "source"): {"description": _DIR_OR_FILE_DESC + " Must anchor the entity's actual "
                            "type DEFINITION (the `class X`/`@dataclass` line), never a use site."},
    ("FlowStep", "src"): {"description": "an element id, or a Role display name (an actor step)."},
    ("FlowStep", "dst"): {"description": "same shape as `src`."},
    ("FlowStep", "where"): {"pattern": _ANCHOR_LINE.pattern, "description": _ANCHOR_DESC + " THE "
                             "location: this step's own call site — a step is exactly one interaction, "
                             "so its anchor is precise (unlike an edge's `where`, an example). Required "
                             "on element↔element steps unless `no_call_site`."},
    ("FlowStep", "no_call_site"): {"description": "explicit opt-out (mirrors Edge.no_call_site): this "
                                    "step has no single call site — `where` may be null."},
    ("Flow", "uc"): {"pattern": r"^UC\d+$"},
    ("Edge", "where"): {"pattern": _ANCHOR_LINE.pattern, "description": _ANCHOR_DESC + " A verified "
                         "EXAMPLE call site — one line in `src`'s code where it invokes `dst`, possibly "
                         "one of many (a witness grounding the edge, not a catalog of its traffic)."},
    ("Edge", "why"): {"description": "the relationship's rationale — distinct from either "
                       "endpoint's own `purpose`."},
    ("RunRow", "source"): {"pattern": _ANCHOR_LINE.pattern, "description": _ANCHOR_DESC
                            + " Where the run command is defined — the script, Makefile target, or "
                            "config line the action runs."},
    ("SecurityRow", "source"): {"pattern": _ANCHOR_LINE.pattern, "description": _ANCHOR_DESC
                                 + " The auth check in code (the enforcement site)."},
    ("NonEntityType", "source"): {"description": _DIR_OR_FILE_DESC
                                   + " Where the deliberately-unmodelled type is defined."},
    ("ProjectModel", "format"): {"const": FORMAT},
    ("ProjectModel", "commit"): {"description": "short commit sha the map was built at."},
    ("ProjectModel", "committed"): {"description": "YYYY-MM-DD."},
    ("ProjectModel", "built"): {"description": "YYYY-MM-DD HH:MM."},
}


def _schema_for(hint: object, defs: dict[str, dict]) -> dict:
    """A JSON-Schema fragment for one type hint — mirrors `model._check`'s type dispatch (str, int,
    bool, X|None, list[T], dict[str,V], nested dataclass), but DESCRIBES a shape instead of
    validating a value."""
    origin = get_origin(hint)
    if origin is Union or origin is types.UnionType:
        args = [a for a in get_args(hint) if a is not type(None)]
        nullable = len(args) < len(get_args(hint))
        inner = _schema_for(args[0], defs)
        if nullable and "type" in inner:
            t = inner["type"]
            inner = {**inner, "type": [*t, "null"] if isinstance(t, list) else [t, "null"]}
        return inner
    if hint in _PRIMITIVE:
        return {"type": _PRIMITIVE[hint]}
    if origin is list:
        (item_hint,) = get_args(hint)
        return {"type": "array", "items": _schema_for(item_hint, defs)}
    if origin is dict:
        _key_hint, val_hint = get_args(hint)
        if val_hint is object:
            return {"type": "object"}  # `extra`: any JSON value per key — see FIELD_META
        return {"type": "object", "additionalProperties": _schema_for(val_hint, defs)}
    if is_dataclass(hint):
        _ensure_def(hint, defs)  # type: ignore[arg-type]
        return {"$ref": f"#/$defs/{hint.__name__}"}  # type: ignore[union-attr]
    raise TypeError(f"unsupported type in schema generation: {hint!r}")


def _ensure_def(cls: type, defs: dict[str, dict]) -> None:
    """Populate `defs[cls.__name__]` once, recursing into every field's type. The placeholder
    assignment before recursing guards a (currently nonexistent, but cheap to guard) self-reference
    from looping forever."""
    if cls.__name__ in defs:
        return
    defs[cls.__name__] = {}
    hints = get_type_hints(cls)
    props: dict[str, dict] = {}
    required: list[str] = []
    for f in dc_fields(cls):
        prop = _schema_for(hints[f.name], defs)
        meta = FIELD_META.get((cls.__name__, f.name), {})
        prop = {**prop, **{k: v for k, v in meta.items() if k != "description"}}
        if "description" in meta:
            prop["description"] = meta["description"]
        props[f.name] = prop
        if f.default is MISSING and f.default_factory is MISSING:  # type: ignore[misc]
            required.append(f.name)
    defs[cls.__name__] = {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


def generate_schema() -> dict:
    """The whole schema: `ProjectModel`'s shape inlined at the top level, every nested dataclass
    (`Component`, `Dep`, `EvidenceItem`, `Entity`, …) as a reusable `$defs` entry."""
    defs: dict[str, dict] = {}
    _ensure_def(ProjectModel, defs)
    root = defs.pop("ProjectModel")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://coyodex.dev/schemas/project-map.schema.json",
        "title": "coyodex project map",
        "description": "Auto-generated from tools/coyodex/model.py — documentation and IDE-"
                        "autocomplete use only; NOT used by `coyodex validate` (see this module's "
                        "docstring, and method/model.md, for why). Regenerate with "
                        "`python -m coyodex.json_schema > method/project-map.schema.json`.",
        **root,
        "$defs": defs,
    }


def main() -> int:
    print(json.dumps(generate_schema(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
