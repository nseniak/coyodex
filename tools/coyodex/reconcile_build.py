#!/usr/bin/env python3
"""`coyodex reconcile` — expand path RULES into an explicit `reconcile.json`.

`assemble --reconcile` already applies the synthesis assignments declaratively, but AUTHORING that
file is the part that does not scale: it wants explicit id lists, and on a large map that is hundreds
of ids nobody types. A live 429-component build wrote a throwaway generator script for exactly this,
and the script had the predictable bug — it resolved zero components while reporting 429 assignments,
because nothing checked the ids it emitted against the map.

So this command does the expansion and the checking: rules match elements by SOURCE PATH (the fact a
lead actually knows — "everything under mee6/plugins/ is the Plugins subsystem"), ids are resolved
against a real map, and every rule that matches nothing is reported rather than silently emitting an
empty assignment. Output is an ordinary reconcile file, so `assemble --reconcile` stays the one code
path that writes.

    coyodex reconcile --rules rules.json --map .coyodex/project-map.json \\
                      --out .coyodex/reconcile.json [--dry-run]

rules.json:
    {"rules": [
       {"source_glob": "mee6/plugins/*",   "subsystem": "S12"},
       {"source_glob": "gateway/**",       "runs_in": ["gateway"]},
       {"ids": ["E7", "E8"],               "subdomain": "SD2"},
       {"source_glob": "mee6/memberships/**", "subsystem": "S30", "runs_in": ["api", "worker"]}
    ]}

Later rules win on the same (element, field), so a broad rule can be followed by a narrow override.
Stdlib-only (the cli.py firewall).
"""
from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path

from coyodex.anchors import strip_anchor
from coyodex.model import Component, Dep, Entity, ProjectModel, load_model_path

# field → the element type it may be set on (mirrors reconcile._SET_FIELD_OWNER, which validates
# the emitted file again at assemble time — this is the early, friendlier report).
_FIELD_OWNER: dict[str, type] = {
    "subsystem": Component,
    "runs_in": Component,
    "subdomain": Entity,
    "bucket": Dep,
}


class RuleError(Exception):
    """A malformed rules file — raised before anything is written."""


def _elements(m: ProjectModel) -> list[object]:
    return [*m.components, *m.entities, *m.deps]


def _source_of(el: object) -> str:
    """The element's repo-relative source path, anchor suffix stripped ('' when it has none)."""
    raw = getattr(el, "source", "") or getattr(el, "where_configured", "") or ""
    return strip_anchor(raw).rstrip("/") if raw else ""


def _match_segments(pat: list[str], path: list[str]) -> bool:
    """Segment-wise glob match. `**` consumes zero or more whole segments; every other segment is
    matched by `fnmatch` against ONE path segment (a segment contains no `/`, so `*` cannot cross a
    directory boundary — the shell/.gitignore distinction).

    Written as an explicit walk rather than a translated pattern because the string-surgery version
    of this was wrong in four separate ways at once: `a/*/b` never matched (the tail was measured
    from the FIRST star, so any later segment read as "crossing a boundary"), `a/**/nope` matched
    everything under `a/` (everything after `**` was discarded), a leading `**` matched every path
    in the map, and a trailing `/` matched nothing."""
    if not pat:
        return not path
    head, rest = pat[0], pat[1:]
    if head == "**":
        if not rest:
            return True                                   # trailing ** — everything at/below here
        return any(_match_segments(rest, path[k:]) for k in range(len(path) + 1))
    if not path or not fnmatch.fnmatchcase(path[0], head):
        return False
    return _match_segments(rest, path[1:])


def _matches(pattern: str, path: str) -> bool:
    """Does this element's source path satisfy the rule's glob?

    A wildcard-free pattern additionally matches everything BENEATH it, so `mee6/plugins` and
    `mee6/plugins/` both behave like the directory the author obviously meant."""
    if not path:
        return False
    pat = [s for s in pattern.strip().strip("/").split("/") if s]
    parts = [s for s in path.strip("/").split("/") if s]
    if not pat:
        return False
    if _match_segments(pat, parts):
        return True
    if not any(ch in pattern for ch in "*?"):             # a plain directory prefix
        return len(parts) > len(pat) and parts[:len(pat)] == pat
    return False


def load_rules(path: Path) -> list[dict]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuleError(f"cannot read rules file {path}: {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("rules"), list):
        raise RuleError("rules file must be an object with a 'rules' array")
    for i, r in enumerate(doc["rules"]):
        if not isinstance(r, dict):
            raise RuleError(f"rules[{i}]: expected an object")
        if "source_glob" not in r and "ids" not in r:
            raise RuleError(f"rules[{i}]: needs 'source_glob' or 'ids'")
        assigned = [k for k in r if k in _FIELD_OWNER]
        if not assigned:
            raise RuleError(f"rules[{i}]: assigns nothing "
                            f"(expected one of {', '.join(sorted(_FIELD_OWNER))})")
    return doc["rules"]


def expand(m: ProjectModel, rules: list[dict]) -> tuple[dict, list[str]]:
    """(reconcile document, report lines). Later rules override earlier ones per (element, field)."""
    by_id = {getattr(el, "id"): el for el in _elements(m)}
    assign: dict[str, dict[str, object]] = {}          # element id → {field: value}
    report: list[str] = []
    for i, r in enumerate(rules):
        fields = {k: v for k, v in r.items() if k in _FIELD_OWNER}
        by_id_rule = "ids" in r
        if by_id_rule:
            targets, unknown = [], []
            for eid in r["ids"]:
                (targets if eid in by_id else unknown).append(eid)
            if unknown:
                report.append(f"rules[{i}]: {len(unknown)} id(s) are not in the map: "
                              f"{', '.join(unknown[:8])}{' …' if len(unknown) > 8 else ''}")
        else:
            targets = [getattr(el, "id") for el in _elements(m)
                       if _matches(r["source_glob"], _source_of(el))]
        # A field may only land on its owning element type. A path glob naturally sweeps the
        # entities and deps living in the same directory, so skipping those is the rule working as
        # intended — silent. Naming an id explicitly is different: the author meant THAT element,
        # so a type mismatch there is a mistake worth reporting.
        kept: list[str] = []
        for eid in targets:
            el = by_id[eid]
            bad = [f for f in fields if not isinstance(el, _FIELD_OWNER[f])]
            if bad:
                if by_id_rule:
                    report.append(f"rules[{i}]: {eid} is a {type(el).__name__}, so "
                                  f"{', '.join(bad)} does not apply to it — skipped")
                continue
            assign.setdefault(eid, {}).update(fields)
            kept.append(eid)
        where = r.get("source_glob") or f"{len(r.get('ids', []))} id(s)"
        if not kept:
            report.append(f"rules[{i}]: '{where}' matched NOTHING — wrong path prefix, or the "
                          "elements carry no source anchor")
        else:
            report.append(f"rules[{i}]: '{where}' → {len(kept)} element(s) "
                          f"[{', '.join(sorted(fields))}]")

    # collapse to the compact `set` shape: one entry per distinct field-value combination
    groups: dict[str, list[str]] = {}
    for eid, fields in assign.items():
        groups.setdefault(json.dumps(fields, sort_keys=True), []).append(eid)
    sets = [{"ids": sorted(ids, key=lambda s: (s[0], int(s[1:]) if s[1:].isdigit() else 0)),
             **json.loads(key)} for key, ids in sorted(groups.items())]
    return {"set": sets}, report


def coverage_report(m: ProjectModel, doc: dict) -> list[str]:
    """What the rules did NOT reach — the half a hand-rolled script never prints."""
    touched = {eid for s in doc.get("set", []) for eid in s.get("ids", [])}
    out: list[str] = []
    for label, elements, fieldname in (("component", m.components, "subsystem"),
                                       ("entity", m.entities, "subdomain")):
        missing = [el.id for el in elements
                   if el.id not in touched and not getattr(el, fieldname, None)]
        if missing:
            out.append(f"{len(missing)} {label}(s) still have no {fieldname} and match no rule: "
                       f"{', '.join(missing[:10])}{' …' if len(missing) > 10 else ''}")
    unplaced = [c.id for c in m.components if not c.runs_in and c.id not in touched]
    if unplaced and m.deployment:
        out.append(f"{len(unplaced)} component(s) have no runs_in and match no rule: "
                   f"{', '.join(unplaced[:10])}{' …' if len(unplaced) > 10 else ''}")
    return out


def _arg(argv: list[str], flag: str, default: str | None = None) -> str | None:
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    rules_path = _arg(argv, "--rules")
    map_path = _arg(argv, "--map", ".coyodex/project-map.json") or ".coyodex/project-map.json"
    out_path = _arg(argv, "--out", ".coyodex/reconcile.json") or ".coyodex/reconcile.json"
    dry = "--dry-run" in argv
    if not rules_path:
        print("ERROR: --rules is required", file=sys.stderr)
        return 2
    try:
        rules = load_rules(Path(rules_path))
        m = load_model_path(map_path)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    doc, report = expand(m, rules)
    for line in report:
        print(("  " if "→" in line else "  WARN ") + line, file=sys.stderr)
    for line in coverage_report(m, doc):
        print("  WARN " + line, file=sys.stderr)
    total = sum(len(s["ids"]) for s in doc["set"])
    if total == 0:
        print("ERROR: no element matched any rule — nothing written (check the source_glob "
              "prefixes against the map's anchors)", file=sys.stderr)
        return 1
    if dry:
        print(json.dumps(doc, indent=2))
        print(f"\n(dry run — {total} assignment(s) in {len(doc['set'])} group(s); "
              f"re-run without --dry-run to write {out_path})", file=sys.stderr)
        return 0
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"reconcile -> {out_path}  ({total} assignment(s) in {len(doc['set'])} group(s))")
    print(f"Next: coyodex assemble <fragments…> --out .coyodex --reconcile {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
