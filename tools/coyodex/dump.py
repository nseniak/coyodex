#!/usr/bin/env python3
"""`coyodex dump` — emit the parsed model, or one of a small FIXED set of slices, as JSON.

The model IS the data, so this is a reader, not a query language: the slice surface is
deliberately tiny and fixed (Phase-3 brief) —

  (whole)          the canonical model JSON (what `load_model` parsed, re-serialized)
  --id <ID>        resolve an id → its kind, display name, canonical source, and members
  --record <ID>    the element's full stored record, verbatim
  --edges <ID>     the backbone edges into / out of a node
  --members <ID>   a subsystem's / subdomain's member records (components + child subsystems,
                   entities + child subdomains)

It complements reading the map — ad-hoc lookups, change-impact spelunking, orchestration glue —
and never replaces the whole-map read the rubric judge needs. Stdlib-only, read-only.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

from coyodex.model import (
    Component,
    Entity,
    Group,
    ModelError,
    ProjectModel,
    all_elements,
    load_model,
    to_canonical_json,
)

_PREFIX = re.compile(r"^[A-Z]+")
_KIND = {"UC": "use_case", "HP": "happy_path_step", "S": "subsystem", "C": "component",
         "D": "dep", "SD": "subdomain", "E": "entity"}
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _kind_of(eid: str) -> str:
    m = _PREFIX.match(eid)
    return _KIND.get(m.group(0), "unknown") if m else "unknown"


def _href(cell: str | None) -> str | None:
    """A cell's anchor: the md-link href when the cell is a link, else the cell itself."""
    if not cell:
        return None
    hit = _MD_LINK.search(cell)
    return hit.group(1).strip() if hit else cell.strip() or None


def _group_member_ids(m: ProjectModel, gid: str) -> list[str]:
    """A group's DERIVED members (membership is single-source on the child): a subsystem holds its
    components + child subsystems; a subdomain holds its entities + child subdomains."""
    if gid.startswith("SD"):
        return ([e.id for e in m.entities if e.subdomain == gid]
                + [sd.id for sd in m.subdomains if sd.parent == gid])
    return ([c.id for c in m.components if c.subsystem == gid]
            + [s.id for s in m.subsystems if s.parent == gid])


def resolve_id(m: ProjectModel, eid: str) -> dict[str, object] | None:
    """The `--id` slice: kind + display name + canonical source + members. Members are the
    group's derived children; for a component, its member entry points (every T4 row naming it —
    the same set the self-describing L2 claims carry)."""
    el = all_elements(m).get(eid)
    if el is None:
        return None
    kind = _kind_of(eid)
    name: str | None = getattr(el, "name", None) or getattr(el, "title", None)
    source: str | None = None
    members: list[object] = []
    if isinstance(el, Component):
        source = el.source or _href(el.entry_point)
        members = [{"trigger": ep.trigger, "source": ep.source}
                   for ep in m.entry_points if ep.component == eid]
    elif isinstance(el, Group):
        source = _href(el.source)
        members = list(_group_member_ids(m, eid))
    elif isinstance(el, Entity):
        source = el.source
    return {"id": eid, "kind": kind, "name": name, "source": source, "members": members}


def record_of(m: ProjectModel, eid: str) -> dict[str, object] | None:
    """The `--record` slice: the element's full stored record, verbatim."""
    el = all_elements(m).get(eid)
    return None if el is None else asdict(el)  # type: ignore[call-overload]


def edges_of(m: ProjectModel, eid: str) -> dict[str, list[dict[str, object]]]:
    """The `--edges` slice: full backbone-edge records into / out of a node (authored rows,
    document order — duplicates preserved as authored)."""
    return {"in": [asdict(e) for e in m.edges if e.dst == eid],
            "out": [asdict(e) for e in m.edges if e.src == eid]}


def members_of(m: ProjectModel, gid: str) -> list[dict[str, object]]:
    """The `--members` slice: a group's member RECORDS (where `--id` gives their ids)."""
    elements = all_elements(m)
    return [asdict(elements[i]) for i in _group_member_ids(m, gid) if i in elements]  # type: ignore[call-overload]


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────

_USAGE = """usage: coyodex dump [<project-map.json>] [--id <ID> | --record <ID> | --edges <ID> | --members <Sn|SDn>]

Emit the parsed model as JSON — whole (no flag), or one FIXED slice:
  --id <ID>       resolve an id: kind, display name, canonical source, members
                  (a group's children; a component's member entry points)
  --record <ID>   the element's full stored record
  --edges <ID>    the backbone edges into/out of a node: {"in": [...], "out": [...]}
  --members <ID>  a subsystem's / subdomain's member records
Read-only; complements reading the map, never replaces the whole-map read."""

_SLICES = ("--id", "--record", "--edges", "--members")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print(_USAGE)
        return 0
    slices: list[tuple[str, str]] = []
    positional: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in _SLICES:
            i += 1
            if i >= len(argv):
                print(f"ERROR: {a} needs an element ID", file=sys.stderr)
                return 2
            slices.append((a, argv[i]))
        elif a.startswith("-"):
            print(f"ERROR: unknown option '{a}'\n{_USAGE}", file=sys.stderr)
            return 2
        else:
            positional.append(a)
        i += 1
    if len(slices) > 1:
        print("ERROR: give at most ONE slice flag (--id/--record/--edges/--members)",
              file=sys.stderr)
        return 2
    path = Path(positional[0] if positional else ".coyodex/project-map.json")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    try:
        m = load_model(path.read_text(encoding="utf-8"))
    except ModelError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    if not slices:
        sys.stdout.write(to_canonical_json(m))
        return 0
    flag, eid = slices[0]
    if flag == "--edges":
        out: object = edges_of(m, eid)
    elif flag == "--members":
        if _kind_of(eid) not in ("subsystem", "subdomain"):
            print(f"ERROR: --members takes a subsystem (Sn) or subdomain (SDn) id, got '{eid}'",
                  file=sys.stderr)
            return 2
        if eid not in all_elements(m):
            print(f"ERROR: {eid} is not defined in the map", file=sys.stderr)
            return 1
        out = members_of(m, eid)
    else:
        out = resolve_id(m, eid) if flag == "--id" else record_of(m, eid)
        if out is None:
            print(f"ERROR: {eid} is not defined in the map", file=sys.stderr)
            return 1
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
