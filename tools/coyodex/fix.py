#!/usr/bin/env python3
"""`coyodex fix` — the mechanical reconcile edits the method's Phase-3/4 reconcile needs, applied to
the stored model IN PLACE so they are never hand-scripted (a hand script that matched edges by
endpoints-only once swapped a paired `persists`/`reads` edge — the class this command exists to kill).

Three verbs, each loading `project-map.json`, mutating the dataclass tree, and writing it back through
the one canonical serializer (validity guaranteed by the serializer, never by hand):

  fix apply-drift   — write the grounding skeptics' corrected `where` line into each drifted edge
                      (consumes the same verdicts `coyodex anchor-drift` reads). Matches on the FULL
                      `(src, verb, dst)` triple, so paired edges sharing endpoints never swap.
  fix drop-edge     — remove a refuted backbone edge and surface (or heal) the flow steps that rode it.
  fix dedup-relation — resolve the blocking "relation declared on both cards" / "declared twice"
                      domain-card duplicates by dropping ONE human-chosen occurrence (never silent —
                      a wrong drop deletes a real domain fact).

After any fix, re-run the invariant: validate --check-sources → audit → render. Stdlib-only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from coyodex.anchor_drift import drift_records
from coyodex.audit_model import l2_worklist_model
from coyodex.model import FlowStep, ProjectModel, load_model_path, to_canonical_json

_EDGE_CLAIM = re.compile(r"^([A-Z]+\d+) (\S+) ([A-Z]+\d+)$")   # `C5 persists E2` — excludes security claims


def _write(map_path: Path, m: ProjectModel) -> None:
    map_path.write_text(to_canonical_json(m), encoding="utf-8")
    # `fix` edits the ASSEMBLED map. During a build the source of truth is the fragments, and a later
    # `assemble` regenerates the map from them — silently discarding this edit. Both fresh builds hit
    # exactly this (ran `fix drop-edge`, re-assembled, then hand-scripted the same drop into a
    # fragment). Say so: run `fix` only as the FINAL step, after the last assemble.
    print("note: this edited the assembled map in place — if you `assemble` again it is rebuilt from "
          "fragments and THIS edit is lost. Run `fix` as the final step (after the last assemble), or "
          "make structural changes in a fragment + re-assemble.", file=sys.stderr)


def _need(argv: list[str], i: int, flag: str) -> str:
    if i >= len(argv):
        print(f"ERROR: {flag} needs a value", file=sys.stderr)
        raise SystemExit(2)
    return argv[i]


# ── fix apply-drift ────────────────────────────────────────────────────────────────────────────────

def apply_drift(argv: list[str]) -> int:
    map_path = verdicts_path = None
    tolerance = 2
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--map", "--verdicts", "--tolerance"):
            i += 1
            val = _need(argv, i, a)
            if a == "--map":
                map_path = val
            elif a == "--verdicts":
                verdicts_path = val
            else:
                tolerance = int(val)
        else:
            print(f"ERROR: unknown argument '{a}'", file=sys.stderr)
            return 2
        i += 1
    if not map_path or not verdicts_path:
        print("ERROR: --map and --verdicts are required", file=sys.stderr)
        return 2
    m = load_model_path(map_path)
    grounding = json.loads(Path(verdicts_path).read_text(encoding="utf-8")).get("grounding", [])
    records = drift_records(l2_worklist_model(m), grounding, tolerance)
    applied = 0
    for rec in records:
        mo = _EDGE_CLAIM.match(rec["claim"])
        if not mo:                                    # a security-surface claim, not an edge — skip
            continue
        src, verb, dst = mo.group(1), mo.group(2).lower(), mo.group(3)
        corrected = rec.get("corrected")
        if not corrected:
            print(f"note: no consensus line for '{rec['claim']}' — left unchanged", file=sys.stderr)
            continue
        matches = [e for e in m.edges
                   if e.src == src and e.verb.strip().lower() == verb and e.dst == dst]
        if len(matches) != 1:                         # 0 (gone) or >1 (same triple, different call sites)
            print(f"WARNING: '{rec['claim']}' matches {len(matches)} edges — skipped (resolve by hand: "
                  f"an ambiguous multi-site edge must not be blind-rewritten).", file=sys.stderr)
            continue
        e = matches[0]
        if e.where != corrected:
            print(f"  {rec['claim']}: where {e.where!r} → {corrected!r}")
            e.where = corrected
            applied += 1
    if applied:
        _write(Path(map_path), m)
        print(f"apply-drift: rewrote {applied} edge `where` anchor(s). "
              f"Re-run: validate --check-sources → audit → render.")
    else:
        print("apply-drift: no drifted edge anchors to rewrite.")
    return 0


# ── fix drop-edge ────────────────────────────────────────────────────────────────────────────────

def _riding_steps(m: ProjectModel, src: str, dst: str) -> list[tuple[str, FlowStep]]:
    """Every flow / sub-flow step whose endpoints are the dropped edge's pair (undirected — a
    return-direction step rides the same edge), tagged with its flow/sub-flow id for reporting."""
    out: list[tuple[str, FlowStep]] = []
    pair = frozenset((src, dst))
    for f in m.flows:
        for st in f.steps:
            if not st.subflow and frozenset((st.src, st.dst)) == pair:
                out.append((f.uc, st))
    for sf in m.subflows:
        for st in sf.steps:
            if not st.subflow and frozenset((st.src, st.dst)) == pair:
                out.append((sf.id, st))
    return out


def drop_edge(argv: list[str]) -> int:
    map_path = new_dst = None
    drop_steps = False
    positionals: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--map":
            i += 1
            map_path = _need(argv, i, a)
        elif a == "--repoint":
            i += 1
            new_dst = _need(argv, i, a)
        elif a == "--drop-steps":
            drop_steps = True
        elif a.startswith("-"):
            print(f"ERROR: unknown option '{a}'", file=sys.stderr)
            return 2
        else:
            positionals.append(a)
        i += 1
    if not map_path or len(positionals) != 3:
        print("ERROR: usage: fix drop-edge --map <map> <src> <verb> <dst> "
              "[--drop-steps | --repoint <newDst>]", file=sys.stderr)
        return 2
    if drop_steps and new_dst:
        print("ERROR: --drop-steps and --repoint are mutually exclusive", file=sys.stderr)
        return 2
    src, verb, dst = positionals[0], positionals[1].lower(), positionals[2]
    m = load_model_path(map_path)
    kept = [e for e in m.edges if not (e.src == src and e.verb.strip().lower() == verb and e.dst == dst)]
    removed = len(m.edges) - len(kept)
    if removed == 0:
        print(f"ERROR: no edge '{src} {verb} {dst}' found", file=sys.stderr)
        return 1
    m.edges = kept
    riding = _riding_steps(m, src, dst)
    if new_dst:
        for _owner, st in riding:
            if st.src == dst:
                st.src = new_dst
            if st.dst == dst:
                st.dst = new_dst
        print(f"drop-edge: removed {removed} edge(s); re-pointed {len(riding)} riding step(s) "
              f"{dst} → {new_dst}.")
    elif drop_steps:
        drop_ids = {id(st) for _o, st in riding}
        for f in m.flows:
            f.steps = [st for st in f.steps if id(st) not in drop_ids]
        for sf in m.subflows:
            sf.steps = [st for st in sf.steps if id(st) not in drop_ids]
        print(f"drop-edge: removed {removed} edge(s) and {len(riding)} riding step(s).")
    else:
        print(f"drop-edge: removed {removed} edge(s).")
        if riding:
            print(f"  {len(riding)} flow step(s) rode this edge and now attribute {src}↔{dst} with no "
                  f"backing edge (validate warns on C↔E; C↔C is silent) — reconcile them:")
            for owner, st in riding:
                print(f"    {owner} step {st.n}: {st.src} → {st.dst}  ({st.phrase or '—'})")
            print("  Re-run with --repoint <newDst> or --drop-steps, or edit the steps by hand.")
    _write(Path(map_path), m)
    print("Re-run: validate --check-sources → audit → render.")
    return 0


# ── fix dedup-relation ───────────────────────────────────────────────────────────────────────────

def _duplicate_relations(m: ProjectModel) -> tuple[list[str], list[str]]:
    """The blocking domain-card duplicates the validator flags, as (same_card, reciprocal) drop-token
    lists. A token is `En:verb:Em` — the relation to drop ONE occurrence of. Mirrors
    `validate_model._check_domain_cards` / `check_domain_relations`."""
    same_card: list[str] = []
    directed: dict[tuple[str, str], list[tuple[str, str]]] = {}   # (a,b) → [(verb, token)]
    for e in m.entities:
        seen: set[tuple[str, str]] = set()
        for r in e.relations:
            key = (r.verb, r.target)
            if key in seen:
                same_card.append(f"{e.id}:{r.verb}:{r.target}")
            seen.add(key)
            directed.setdefault((e.id, r.target), []).append((r.verb, f"{e.id}:{r.verb}:{r.target}"))
    reciprocal: list[str] = []
    for (a, b), items in directed.items():
        if a < b and (b, a) in directed:
            # both sides authored the pair — offer to drop EITHER side (list the a→b side's token(s))
            reciprocal.extend(tok for _verb, tok in items)
    return same_card, reciprocal


def dedup_relation(argv: list[str]) -> int:
    map_path = None
    drops: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--map":
            i += 1
            map_path = _need(argv, i, a)
        elif a == "--drop":
            i += 1
            drops.append(_need(argv, i, a))
        else:
            print(f"ERROR: unknown argument '{a}'", file=sys.stderr)
            return 2
        i += 1
    if not map_path:
        print("ERROR: --map is required", file=sys.stderr)
        return 2
    m = load_model_path(map_path)
    if not drops:
        same_card, reciprocal = _duplicate_relations(m)
        if not same_card and not reciprocal:
            print("dedup-relation: no blocking duplicate relations.")
            return 0
        if same_card:
            print("Same-card duplicates (relation declared twice on one card) — drop one occurrence:")
            for tok in same_card:
                print(f"  --drop {tok}")
        if reciprocal:
            print("Reciprocal (declared on BOTH cards) — keep one side, drop the other:")
            for tok in reciprocal:
                print(f"  --drop {tok}")
        print("\nRe-run with the chosen --drop token(s). Each drops ONE occurrence.")
        return 0
    dropped = 0
    for tok in drops:
        parts = tok.split(":")
        if len(parts) != 3:
            print(f"ERROR: bad --drop token '{tok}' (want En:verb:Em)", file=sys.stderr)
            return 2
        eid, verb, target = parts
        ent = next((e for e in m.entities if e.id == eid), None)
        if ent is None:
            print(f"ERROR: no entity '{eid}'", file=sys.stderr)
            return 1
        idx = next((k for k, r in enumerate(ent.relations)
                    if r.verb.lower() == verb.lower() and r.target == target), None)
        if idx is None:
            print(f"ERROR: no relation '{verb} → {target}' on {eid}", file=sys.stderr)
            return 1
        del ent.relations[idx]                       # ONE occurrence
        dropped += 1
        print(f"  dropped {eid}: {verb} → {target}")
    _write(Path(map_path), m)
    print(f"dedup-relation: dropped {dropped} relation(s). "
          f"Re-run: validate --check-sources → audit → render.")
    return 0


# ── dispatch ─────────────────────────────────────────────────────────────────────────────────────

_VERBS = {"apply-drift": apply_drift, "drop-edge": drop_edge, "dedup-relation": dedup_relation}

_USAGE = """usage: coyodex fix <verb> [args...]

Apply a mechanical reconcile edit to .coyodex/project-map.json IN PLACE. Verbs:

  apply-drift --map <map> --verdicts <raw.json> [--tolerance N]
      Write the grounding skeptics' corrected `where` line into each drifted edge (same verdicts
      `coyodex anchor-drift` reads). Matches the full (src, verb, dst) triple; an ambiguous
      multi-site edge is skipped, not blind-rewritten.

  drop-edge --map <map> <src> <verb> <dst> [--drop-steps | --repoint <newDst>]
      Remove a refuted backbone edge. By default it REPORTS the flow steps that rode it (for a
      hand reconcile); --drop-steps removes them, --repoint <newDst> re-points them.

  dedup-relation --map <map> [--drop <En:verb:Em> ...]
      With no --drop, LIST the blocking "declared on both cards" / "declared twice" domain-card
      duplicates and the token to resolve each. With --drop, remove ONE chosen occurrence.

After any fix, re-run the invariant: validate --check-sources → audit → render."""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(_USAGE)
        return 0 if argv and argv[0] in ("-h", "--help") else 2
    verb, rest = argv[0], argv[1:]
    fn = _VERBS.get(verb)
    if fn is None:
        print(f"coyodex fix: unknown verb '{verb}'\n", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    return fn(rest)


if __name__ == "__main__":
    raise SystemExit(main())
