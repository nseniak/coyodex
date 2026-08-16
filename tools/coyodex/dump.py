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
         "D": "dep", "SD": "subdomain", "E": "entity", "R": "role", "CAP": "capability",
         "EP": "entry_point", "BLK": "block", "BR": "business_rule"}
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
    components + child subsystems; a subdomain holds its entities + child subdomains; a capability
    holds its use cases + child capabilities; a block holds its business rules + child blocks."""
    if gid.startswith("SD"):
        return ([e.id for e in m.entities if e.subdomain == gid]
                + [sd.id for sd in m.subdomains if sd.parent == gid])
    if gid.startswith("CAP"):
        return ([u.id for u in m.use_cases if u.capability == gid]
                + [c.id for c in m.capabilities if c.parent == gid])
    if gid.startswith("BLK"):
        return ([r.id for r in m.rules if r.block == gid]
                + [b.id for b in m.blocks if b.parent == gid])
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
    # A rule carries both: `name` is its title, `statement` the decision in full. The fallback is
    # what a map built before `name` existed still answers with, instead of `"name": null`.
    name: str | None = (getattr(el, "name", None) or getattr(el, "title", None)
                        or getattr(el, "statement", None))
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


def legend_of(m: ProjectModel) -> list[dict[str, object]]:
    """The `--legend` slice: every element as `id · name · kind · subsystem/subdomain · source`.

    The id universe a fan-out has to share. Every build re-invents it — one hand-wrote a 25-line
    python walk of `project-map.json` to produce the frozen legend it then handed to eleven trace
    agents, in the same turn as a contract telling them "use `coyodex dump`, don't hand-parse it".
    The tool asked for the discipline it did not supply."""
    out: list[dict[str, object]] = []
    for c in m.components:
        out.append({"id": c.id, "name": c.name, "kind": "component",
                    "parent": c.subsystem or "", "source": _href(c.source) or ""})
    for d in m.deps:
        out.append({"id": d.id, "name": d.name, "kind": "dep", "parent": d.bucket or "",
                    "source": ""})
    for e in m.entities:
        out.append({"id": e.id, "name": e.name, "kind": "entity", "parent": e.subdomain or "",
                    "source": _href(e.source) or ""})
    for g in m.subsystems:
        out.append({"id": g.id, "name": g.name, "kind": "subsystem", "parent": g.parent or "",
                    "source": _href(g.source) or ""})
    for g in m.subdomains:
        out.append({"id": g.id, "name": g.name, "kind": "subdomain", "parent": g.parent or "",
                    "source": _href(g.source) or ""})
    for uc in m.use_cases:
        out.append({"id": uc.id, "name": uc.name, "kind": "use_case", "parent": "", "source": ""})
    for sf in m.subflows:
        out.append({"id": sf.id, "name": sf.name, "kind": "sub_flow", "parent": "", "source": ""})
    for r in m.roles:
        out.append({"id": r.id, "name": r.name, "kind": "role", "parent": "", "source": ""})
    for cap in m.capabilities:
        # `parent`/`source` like every other group row: a nested capability was invisible to every
        # sub-agent handed this legend, because these two cells were hard-coded empty.
        out.append({"id": cap.id, "name": cap.name, "kind": "capability",
                    "parent": cap.parent or "", "source": _href(cap.source) or ""})
    for blk in m.blocks:
        out.append({"id": blk.id, "name": blk.name, "kind": "block", "parent": blk.parent or "",
                    "source": _href(blk.source) or ""})
    for br in m.rules:
        out.append({"id": br.id, "name": br.name or br.statement, "kind": "business_rule",
                    "parent": br.block or "", "source": ""})
    return out


def counts_of(m: ProjectModel) -> dict[str, int]:
    """The `--counts` slice: how many rows each array holds.

    `assemble` prints C/D/E and `validate` prints its own inventory line, and neither covers every
    array — so builds keep answering "how big is this map?" with a throwaway `python -c` that walks
    the JSON. Three separate live turns did exactly that, one of them two turns after `assemble`
    had printed half the same numbers."""
    counts: dict[str, int] = {}
    for name, value in vars(m).items():
        if isinstance(value, list):
            counts[name] = len(value)
    return counts


def members_of(m: ProjectModel, gid: str) -> list[dict[str, object]]:
    """The `--members` slice: a group's member RECORDS (where `--id` gives their ids)."""
    elements = all_elements(m)
    return [asdict(elements[i]) for i in _group_member_ids(m, gid) if i in elements]  # type: ignore[call-overload]


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────

_USAGE = """usage: coyodex dump [<project-map.json> | --map <project-map.json>]
                    [--id <ID> | --record <ID> | --edges <ID> | --members <Sn|SDn|CAPn|BLKn>
                     | --legend | --counts]

Emit the parsed model as JSON — whole (no flag), or one FIXED slice:
  --id <ID>       resolve an id: kind, display name, canonical source, members
                  (a group's children; a component's member entry points)
  --record <ID>   the element's full stored record
  --edges <ID>    the backbone edges into/out of a node: {"in": [...], "out": [...]}
  --members <ID>  a group's member records (subsystem / subdomain / capability / block)
  --legend        every element as id · name · kind · parent · source — the shared id universe a
                  fan-out needs (builds kept hand-writing this walk and handing it to sub-agents)
  --counts        how many rows each array holds — the whole inventory, not assemble's C/D/E subset
The map is positional, and `--map <path>` is accepted as the same thing: its siblings disagree
about which spelling they take, and a contract handed to 13 sub-agents told every one of them to
write `dump --map ...`, which used to exit 2 on stderr — read through a `2>/dev/null` as "this id
has no record".
Reads an assembled map OR a build FRAGMENT, so it works during Phases 1-3 as well as after
assembly (the help never said so, and a build spent a turn on `dump --help` finding out).
Read-only; complements reading the map, never replaces the whole-map read."""

_SLICES = ("--id", "--record", "--edges", "--members")
#: Slices that take no argument — they describe the WHOLE map, not one element.
_WHOLE_MAP_SLICES = ("--legend", "--counts")


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
        if a in _WHOLE_MAP_SLICES:
            slices.append((a, ""))
        elif a in _SLICES:
            i += 1
            if i >= len(argv):
                print(f"ERROR: {a} needs an element ID", file=sys.stderr)
                return 2
            slices.append((a, argv[i]))
        elif a == "--map":
            i += 1
            if i >= len(argv):
                print("ERROR: --map needs a path", file=sys.stderr)
                return 2
            positional.append(argv[i])
        elif a.startswith("-"):
            print(f"ERROR: unknown option '{a}'\n{_USAGE}", file=sys.stderr)
            return 2
        else:
            positional.append(a)
        i += 1
    if len(slices) > 1:
        print("ERROR: give at most ONE slice flag "
              "(--id/--record/--edges/--members/--legend/--counts)", file=sys.stderr)
        return 2
    if len(positional) > 1:
        print(f"ERROR: give ONE map path, got {len(positional)}: {', '.join(positional)}",
              file=sys.stderr)
        return 2
    path = Path(positional[0] if positional else ".coyodex/project-map.json")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    try:
        # Accepts a build FRAGMENT as well as an assembled map — a fragment is exactly what a build
        # needs to look inside during Phases 1-3, and having no read path for one is why a live build
        # inspected its own fragments with `python3 - <<'EOF'` heredocs instead of this command.
        from coyodex.assemble import load_map_or_fragment
        m, _present = load_map_or_fragment(path)
    except ModelError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    if not slices:
        sys.stdout.write(to_canonical_json(m))
        return 0
    flag, eid = slices[0]
    if flag == "--legend":
        out: object = legend_of(m)
    elif flag == "--counts":
        out = counts_of(m)
    elif flag == "--edges":
        out: object = edges_of(m, eid)
    elif flag == "--members":
        if _kind_of(eid) not in ("subsystem", "subdomain", "capability", "block"):
            print("ERROR: --members takes a group id — a subsystem (Sn), subdomain (SDn), "
                  f"capability (CAPn) or block (BLKn), got '{eid}'", file=sys.stderr)
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
