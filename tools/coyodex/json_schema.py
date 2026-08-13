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
from coyodex.anchors import FILE_ANCHOR as _ANCHOR_LINE, FILE_LINE_ANCHOR

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
                       "`SD<n>` in subdomains[], `CAP<n>` in capabilities[], `BLK<n>` in blocks[] "
                       "— same dataclass, four id forests."},
    ("Group", "parent"): {"pattern": ID_SHAPE.pattern, "description": "the enclosing group's id, "
                           "in the SAME forest (an S parents an S, an SD an SD, a CAP a CAP, a BLK "
                           "a BLK), or null for top-level."},
    ("Group", "label"): {"enum": ["", *grammar.CAP_LABELS], "description": "CAPABILITY-ONLY: an "
                          "authored judgement about the use cases in this capability — core is the "
                          "product and the Happy Path walks every core capability. Nothing derives "
                          "it, and `validate` blocks it on a subsystem or a subdomain."},
    ("Group", "source"): {"description": _DIR_OR_FILE_DESC + " The group's home directory (or a "
                           "representative file)."},
    ("UseCase", "id"): {"pattern": r"^UC\d+$"},
    ("UseCase", "capability"): {"pattern": r"^CAP\d+$", "description": "the capability this use "
                                "case belongs to, or null. Assigned at synthesis via `reconcile` "
                                "(a `CAP<n>` does not exist when the behavioral fragment is written)."},
    ("UseCase", "entry_points"): {"items": {"pattern": r"^EP\d+$"}, "description": "the TRIGGER "
                                   "arm of entry-point claiming: the front door(s) an actor hits to "
                                   "START this use case. Empty is legitimate — the surface may sit "
                                   "inside a coarse T4 row a sibling already names."},
    ("EntryPoint", "id"): {"pattern": r"^EP\d+$", "description": "MINTED BY `assemble` from content "
                            "(source + trigger + owner + kind), never authored — leave it out of a "
                            "fragment. Change-impact keeps its own content key (`ep:{source}`), "
                            "which is stable across rebuilds where a minted number is not."},
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
    # Enumerated because the dispatch template asks for exactly these two words while the field
    # accepted any string, so a harvest agent could return high/medium/low and `lint-fragment`
    # passed it clean. method.md also listed `confidence` among the STRAY keys to omit while the
    # same template required it — both halves of that contradiction are fixed together.
    ("Group", "confidence"): {"enum": [*grammar.CONFIDENCE_VALUES, ""],
                             "description": "verified = read in the code; inferred = deduced. '' = unstated."},
    ("Component", "confidence"): {"enum": [*grammar.CONFIDENCE_VALUES, ""],
                             "description": "verified = read in the code; inferred = deduced. '' = unstated."},
    ("Dep", "confidence"): {"enum": [*grammar.CONFIDENCE_VALUES, ""],
                             "description": "verified = read in the code; inferred = deduced. '' = unstated."},
    ("TestRow", "confidence"): {"enum": [*grammar.CONFIDENCE_VALUES, ""],
                             "description": "verified = read in the code; inferred = deduced. '' = unstated."},

    ("Dep", "id"): {"pattern": r"^D\d+$"},
    ("Dep", "kind"): {"enum": [*grammar.DEP_KINDS, None], "description": "closed Context "
                       "vocabulary; null → inferred from `type`."},
    ("Dep", "bucket"): {"description": "PURPOSE bucket (seeded-open) grouping the dep within its "
                        "diagram — external systems in Context, in-process code in the Libraries "
                        f"drill. Prefer a seed ({', '.join(grammar.DEP_BUCKET_SEEDS_EXTERNAL)} for "
                        f"external systems; {', '.join(grammar.DEP_BUCKET_SEEDS_LIBRARY)} for "
                        "libraries); mint a new one only when none fits. Empty → inferred from "
                        "`type` + `used_for`."},
    ("Dep", "where_configured"): {"pattern": _ANCHOR_LINE.pattern, "description": _ANCHOR_DESC},
    ("Dep", "package"): {"description": 'one string: "<name> <version> (<where declared>)".'},
    ("Dep", "alternative"): {"description": "the fallback used instead of this dep, and under "
                              "what circumstance."},
    ("Dep", "extra"): {"description": _EXTRA_DESC},
    ("EntryPoint", "source"): {"pattern": _ANCHOR_LINE.pattern, "description": _ANCHOR_DESC},
    ("EntryPoint", "component"): {"pattern": r"^C\d+$", "description": "the owning component's id."},
    ("EntryPoint", "kind"): {"description": "what the entry point IS — a SEEDED-OPEN vocabulary "
                              "(never blocking): prefer a seed "
                              f"({', '.join(grammar.ENTRY_POINT_KINDS)}); mint a project-specific "
                              "kind only when none fits, and reuse the exact spelling on rebuild "
                              "(validate folds known drift like 'http'→'http-route' and nudges the "
                              "rest)."},
    ("EntryPoint", "cadence"): {"description": "WHEN a self-activated entry point runs: a cron "
                                 "expression ('0 3 * * *'), an interval ('every 30s'), 'on-boot', "
                                 "or 'continuous'. Meaningful only when the effective activation "
                                 "is 'self' (a cadence on an external EP draws an advisory)."},
    ("EntryPoint", "cadence_source"): {"pattern": _ANCHOR_LINE.pattern,
                                        "description": "bare path:line anchor to the line "
                                        "DECLARING the schedule (beat/cron config, compose, the "
                                        "loop's sleep) — often a different line than `source`; '' "
                                        "on a set cadence = inferred (advisory)."},
    ("Group", "tech"): {"description": "SUBSYSTEM-ONLY: one honest stack label ('Python/FastAPI', "
                         "'Go', 'Elixir') read off the manifests — not a stack essay. validate "
                         "blocks it on a subdomain (a bounded context has no stack)."},
    ("Group", "tech_source"): {"pattern": _ANCHOR_LINE.pattern,
                                "description": "optional bare path:line anchor to the manifest "
                                "line proving the tech label (go.mod, package.json, "
                                "pyproject.toml)."},
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
    ("MessagingRow", "name"): {"description": "unique channel/queue/topic name — the row's key "
                                "(name-keyed like a deployment unit; nothing points at a channel)."},
    ("MessagingRow", "kind"): {"description": "seeded-open: queue / topic / stream / pubsub / "
                                "job-queue; mint a project-specific kind when none fits."},
    ("MessagingRow", "broker"): {"pattern": r"^D\d+$", "description": "the messaging/datastore dep "
                                  "carrying the channel; '' = in-process."},
    ("MessagingRow", "payload"): {"pattern": r"^E\d+$", "description": "the entity a message "
                                   "carries; '' = untyped/none."},
    ("MessagingRow", "source"): {"pattern": _ANCHOR_LINE.pattern,
                                  "description": "bare path:line anchor to where the channel NAME "
                                  "is declared."},
    ("StateMachine", "states"): {"description": "the declared state names — non-empty, unique; "
                                  "never synthesized (record only a lifecycle the code implements "
                                  "in an enum / status constants / dispatch table)."},
    ("StateMachine", "source"): {"pattern": _ANCHOR_LINE.pattern,
                                  "description": "bare path:line anchor to the line DECLARING the "
                                  "states; '' = inferred (advisory)."},
    ("StateTransition", "on"): {"description": "the trigger label ('connect ok', 'refresh "
                                 "failed'); optional."},
    ("Store", "dep"): {"pattern": r"^D\d+$", "description": "the physical datastore/messaging dep "
                        "holding this entity (a D-id); null for a store with no dep (in-memory, "
                        "in-code registry)."},
    ("Store", "mode"): {"enum": [*grammar.STORE_MODES, ""],
                         "description": "how the entity relates to its store — closed vocabulary, "
                         "exact match: collection (own compartment) / embedded (inside a parent's "
                         "row) / transient / cache / in-code / enum; '' = unstated."},
    ("Store", "container"): {"description": "the compartment inside the dep: collection / table / "
                              "key prefix / bucket / file name."},
    ("Store", "notes"): {"description": "what the shape can't say: TTL, cache tiers, compression."},
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
    ("FlowStep", "subflow"): {"pattern": r"^SF\d+$", "description": "a REFERENCE step: 'runs SFn "
                               "here'. src/dst stay authored (the run's entry/exit endpoints); "
                               "`phrase` may be empty (defaults to the sub-flow's name); the step "
                               "carries no `where`/`no_call_site` of its own. One level only — a "
                               "sub-flow's step may not itself reference a sub-flow."},
    ("Flow", "uc"): {"pattern": r"^UC\d+$"},
    ("SubFlow", "id"): {"pattern": r"^SF\d+$"},
    ("SubFlow", "name"): {"description": "what the shared sequence does — a single verb phrase, "
                           "like a use-case name."},
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
    ("VariantTag", "env"): {"description": "the environment this deployment unit runs in — must name a "
                             "`environments` entry."},
    ("VariantTag", "source"): {"pattern": _ANCHOR_LINE.pattern, "description": _ANCHOR_DESC
                                + " The manifest line that PLACES the unit in this environment (the "
                                "compose `profiles:` line, the overlay/values file, the stage). Empty "
                                "string = INFERRED (no manifest witness): `validate` surfaces it as an "
                                "advisory, never blocks; a CITED source that doesn't resolve IS a hard "
                                "block under `--check-sources`."},
    ("BusinessRule", "id"): {"pattern": r"^BR\d+$"},
    ("BusinessRule", "name"): {"description": "the SHORT title — a few words a reader scans, the way "
                                "a use case has a name beside its trigger\u2192outcome sentence "
                                "(\"Owner-only cancellation\"). Not a shortened statement: name the "
                                "DECISION, then state it in full in `statement`."},
    ("BusinessRule", "statement"): {"description": "ONE product decision, in product language and "
                                     "naming no component — the sharp test is 'could a product "
                                     "person have decided otherwise?'. Two claims joined by 'and' "
                                     "are two rules."},
    ("BusinessRule", "block"): {"pattern": r"^BLK\d+$", "description": "the decision area this rule "
                                 "belongs to, or null. Assigned at synthesis via `reconcile` (a "
                                 "`BLK<n>` does not exist when the rule is authored), exactly as "
                                 "`use_cases[].capability` is."},
    ("BusinessRule", "access"): {"description": "this rule governs WHO MAY DO WHAT — the security "
                                  "marker. The security surface table and the eval's auth coverage "
                                  "read it."},
    ("BusinessRule", "risk"): {"description": "what is AT STAKE if this decision is wrong or "
                                "absent — a judgement, not a derivation. Distinct from a site's "
                                "`why` (what that LINE does): a risk note says what the decision's "
                                "limit costs. Rendered in the security surface table for an "
                                "`access` rule."},
    ("BusinessRule", "confidence"): {"enum": [*grammar.CONFIDENCE_VALUES, ""],
                             "description": "verified = read in the code; inferred = deduced. '' = unstated."},
    ("BusinessRule", "sites"): {"description": "every place the decision is ENFORCED. The rule's "
                                 "components, its use-case steps and whether it has been swept are "
                                 "DERIVED from these — there is no authored field for any of them."},
    ("RuleSite", "where"): {"pattern": FILE_LINE_ANCHOR.pattern, "description": _ANCHOR_DESC
                             + " The OPERATIVE line — the one that acts. A definition header, an "
                             "import, a comment or a blank line is a shape error, not a site, and "
                             "the `:line` is REQUIRED: without it the operative-line check is "
                             "skipped and the claim cannot be falsified. null (with "
                             "`no_call_site`) = enforced by construction, no single line."},
    ("RuleSite", "why"): {"description": "what this line does FOR the rule ('rejects a non-owner "
                           "caller') — reconstructible from the line itself, with no clause added."},
    ("RuleSite", "no_call_site"): {"description": "explicit opt-out (mirrors Edge.no_call_site): "
                                    "this rule is enforced by construction (a type, a schema "
                                    "constraint, a config-wired guard) — `where` may be empty."},
    ("ProjectModel", "format"): {"const": FORMAT},
    ("ProjectModel", "commit"): {"description": "short commit sha the map was built at."},
    ("ProjectModel", "committed"): {"description": "YYYY-MM-DD."},
    ("ProjectModel", "built"): {"description": "YYYY-MM-DD HH:MM."},
}


#: Fields the schema REQUIRES even though the dataclass gives them a default. The two normally
#: coincide — a field with no default is required — but they answer different questions: the default
#: says "can an already-written map still be loaded", the schema says "must new authored content
#: carry this". `BusinessRule.name` needs both answers: a fragment without it is invalid, while a map
#: written before the field existed must still open so the viewer can render it and `validate` can
#: report it. Without this split, adding a required field to the model means old maps cannot be read
#: at all — not even to be told what is missing.
_ALSO_REQUIRED = {("BusinessRule", "name")}


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
        if ((f.default is MISSING and f.default_factory is MISSING)  # type: ignore[misc]
                or (cls.__name__, f.name) in _ALSO_REQUIRED):
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
