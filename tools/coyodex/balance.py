#!/usr/bin/env python3
"""`coyodex balance` — the diagram-balance report + advisory regroup proposals.

Where `validate` only WARNS on out-of-band diagrams, this command shows the whole picture
(every diagram's fan-out incl. the 10–12 soft tier that validate stays quiet on, the
inter-subsystem C→C matrix, coverage/Q of the current cut) and, for each over-dense
non-exempt diagram, proposes a split:

  * component-children diagrams → a deterministic greedy-modularity (CNM) partition;
  * subsystem-children diagrams → the same on the QUOTIENT graph (C→C pairs aggregated
    onto each child's subtree);
  * homogeneous / sparse / star-shaped subgraphs → a "list-shaped" message instead —
    modularity has no signal there and a forced split would be noise.

Every proposal prints as a Direct-map-change block (exact field edits, the next free S id
precomputed). Proposals are STARTING POINTS for judgment, not ready-to-apply facts — and
coverage/Q are split-context numbers only: a capability-first ROOT legitimately scores a
low top-cut Q (modularity rewards tech-tier cuts; do not "fix" a capability root to please
the metric). Advisory tool: exit 0 always. Stdlib-only.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from coyodex import balance_lib
from coyodex.model import ModelError, ProjectModel, load_model


def _fanout_rows(m: ProjectModel) -> list[tuple[str, str, int, str]]:
    """(diagram id, name, fan-out, flag) for every S-forest diagram, root first."""
    children = balance_lib.subsystem_children(m)
    names = {s.id: s.name for s in m.subsystems}
    rows: list[tuple[str, str, int, str]] = []
    order: list[str | None] = [None] + [s.id for s in m.subsystems]
    for sid in order:
        kids = children.get(sid, [])
        n = len(kids)
        homog = balance_lib.is_homogeneous(m, kids)
        if sid is None:
            flag = ("SPARSE" if n < balance_lib.FANOUT_LO
                    and len(m.components) >= balance_lib.SUBSYSTEMS_RECOMMENDED_ABOVE else
                    "DENSE" if n > balance_lib.FANOUT_HARD_HI and not (
                        homog and n <= balance_lib.FANOUT_HOMOG_HI) else
                    "soft" if n > balance_lib.FANOUT_SOFT_HI else "ok")
            rows.append(("root", "(top-level diagram)", n, flag))
            continue
        if n == 1 and not kids[0].startswith(("S", "SD")):
            flag = "SINGLE-CHILD"
        elif n > balance_lib.FANOUT_HOMOG_HI and homog:
            flag = "DENSE (homogeneous family)"
        elif n > balance_lib.FANOUT_HARD_HI:
            flag = "exempt (homogeneous)" if homog else "DENSE"
        elif n > balance_lib.FANOUT_SOFT_HI:
            flag = "exempt (homogeneous)" if homog else "soft (10–12)"
        else:
            flag = "ok" if n else "empty"
        rows.append((sid, names.get(sid, sid), n, flag))
    return rows


def _proposal_blocks(m: ProjectModel, sid: str | None, out: list[str],
                     next_id: int | None = None) -> int:
    """Append one diagram's proposal block; returns the next unused numeric S id so ids stay
    unique ACROSS blocks (each block may be applied independently or together)."""
    if next_id is None:
        next_id = int(balance_lib.next_free_group_id(m, "S")[1:])
    label = "root" if sid is None else sid
    signal = balance_lib.subgraph_signal(m, sid)
    if signal != "ok":
        out.append(f"  {label}: list-shaped ({signal}) — modularity has no signal here; accept "
                   f"the dense screen as a family, or split it by name/directory family yourself.")
        return next_id
    proposals = balance_lib.propose_split(m, sid)
    if not proposals:
        out.append(f"  {label}: no split found (the merge collapses to one group) — judgment call.")
        return next_id
    children, weights = balance_lib._diagram_graph(m, sid)
    before = balance_lib.modularity(weights, {c: "all" for c in children})
    member_of = {mem_id: p.name for p in proposals for mem_id, _ in p.members}
    after = balance_lib.modularity(weights, member_of)
    out.append(f"  {label}: {len(proposals)} proposed groups "
               f"(coverage {before[0]:.2f}→{after[0]:.2f}, Q {before[1]:.2f}→{after[1]:.2f} — "
               f"split-context numbers only). STARTING POINT, not ready-to-apply:")
    parent_note = "omit `parent`" if sid is None else f'"parent": "{sid}"'
    for p in proposals:
        gid = f"S{next_id}"
        next_id += 1
        out.append(f"    ▸ {gid} — {p.name}  [{p.name_basis}]")
        out.append(f"      Direct map change: add subsystems row {{\"id\": \"{gid}\", "
                   f"\"name\": \"{p.name}\", {parent_note}}} (omit `source` unless the group has "
                   f"one directory home — never fabricate an anchor); then set on each member:")
        for mem_id, mem_name in p.members:
            key = "parent" if mem_id.startswith("S") else "subsystem"
            out.append(f"        {mem_id} ({mem_name}) → \"{key}\": \"{gid}\"")
    out.append("      Do not invent members not listed here. Apply via a Direct map change, then "
               "re-run validate → audit → render.")
    return next_id


def _report(m: ProjectModel) -> str:
    n = len(m.components)
    depth = balance_lib.nesting_depth(m)
    lo_ideal = math.log(n) / math.log(6) if n > 1 else 0.0
    hi_ideal = math.log(n) / math.log(3) if n > 1 else 0.0
    rows = _fanout_rows(m)
    flagged = [r for r in rows if r[3] not in ("ok", "empty") and not r[3].startswith("exempt")]
    in_band = sum(1 for r in rows if balance_lib.FANOUT_LO <= r[2] <= balance_lib.FANOUT_SOFT_HI
                  or r[3].startswith("exempt"))

    out: list[str] = []
    out.append(f"Balance report — {n} components, {len(m.subsystems)} subsystems, "
               f"grouping depth {depth} (ideal ≈ {lo_ideal:.1f}–{hi_ideal:.1f} levels at "
               f"fan-out 3–6)")
    out.append(f"  diagrams in the 3–9 band (incl. exemptions): {in_band}/{len(rows)}")
    out.append("")
    out.append("Per-diagram fan-out (target 5±2):")
    for sid, name, fan, flag in rows:
        marker = "" if flag in ("ok", "empty") else f"   ← {flag}"
        out.append(f"  {sid:>5}  {fan:>3}  {name}{marker}")

    pairs = balance_lib.cc_pairs(m)
    if m.subsystems and pairs:
        top = balance_lib.partition_at(m, "top")
        cov, _q = balance_lib.modularity(pairs, top)
        matrix = balance_lib.inter_group_matrix(pairs, top)
        cross = sorted(((k, v) for k, v in matrix.items() if k[0] != k[1]),
                       key=lambda kv: -kv[1])
        out.append("")
        out.append(f"C→C graph: {len(pairs)} pairs across {n} components; top-cut intra-group "
                   f"share {cov:.2f}. (No Q here on purpose — modularity rewards tech-tier cuts; "
                   f"a capability root legitimately scores lower.)")
        if cross:
            out.append("  busiest cross-subsystem seams:")
            for (a, b), w in cross[:6]:
                out.append(f"    {a} ↔ {b}: {w} pairs")

    dense = [r[0] for r in rows if r[3].startswith(("DENSE", "SPARSE")) or r[3] == "soft (10–12)"]
    dense_diagrams = [None if d == "root" else d for d in dense
                      if d == "root" or any(s.id == d for s in m.subsystems)]
    over_dense = [d for d in dense_diagrams
                  if len(balance_lib.subsystem_children(m).get(d, [])) > balance_lib.FANOUT_SOFT_HI]
    if over_dense:
        out.append("")
        out.append("Split proposals (over-dense diagrams):")
        next_id: int | None = None
        for d in over_dense:
            next_id = _proposal_blocks(m, d, out, next_id)
    if not flagged:
        out.append("")
        out.append("No balance findings — every diagram reads at target density.")
    return "\n".join(out)


def _json_report(m: ProjectModel) -> str:
    rows = _fanout_rows(m)
    pairs = balance_lib.cc_pairs(m)
    return json.dumps({
        "components": len(m.components),
        "subsystems": len(m.subsystems),
        "nesting_depth": balance_lib.nesting_depth(m),
        "cc_pairs": len(pairs),
        "diagrams": [{"id": sid, "name": name, "fanout": fan, "flag": flag}
                     for sid, name, fan, flag in rows],
    }, indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex balance [--focus <Sn>] [--json] [.coyodex/project-map.json]\n\n"
              "Report per-diagram fan-out (target 5±2), the inter-subsystem C→C matrix, and\n"
              "advisory split proposals for over-dense diagrams. Advisory only — exit 0 always;\n"
              "apply accepted proposals via a Direct map change (validate → audit → render).")
        return 0
    as_json = "--json" in argv
    focus: str | None = None
    if "--focus" in argv:
        i = argv.index("--focus")
        if i + 1 >= len(argv):
            print("ERROR: --focus needs a subsystem id (e.g. S7)", file=sys.stderr)
            return 2
        focus = argv[i + 1]
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("-")]
    path = Path(args[0] if args else ".coyodex/project-map.json")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    try:
        m = load_model(path.read_text(encoding="utf-8"))
    except ModelError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    if focus is not None:
        if not any(s.id == focus for s in m.subsystems):
            print(f"ERROR: no subsystem {focus} in the map", file=sys.stderr)
            return 2
        out: list[str] = [f"Split proposal for {focus}:"]
        _proposal_blocks(m, focus, out)
        print("\n".join(out))
        return 0
    print(_json_report(m) if as_json else _report(m))
    return 0
