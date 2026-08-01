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

import re
import sys
from pathlib import Path

from coyodex.anchor_drift import (apply_drift_exceptions, drift_findings, drift_records,
                                  load_verdicts)
from coyodex.audit_model import _claim_text, l2_worklist_model
from coyodex.model import ProjectModel
from coyodex.reconcile import drop_riding, repoint_riding, riding_steps

_EDGE_CLAIM = re.compile(r"^([A-Z]+\d+) (\S+) ([A-Z]+\d+)$")   # `C5 persists E2` — excludes security claims

#: The claim themes `apply-drift` has a writer for: an edge's `where` and a security row's `source`.
#: `security` covers BOTH the auth-surface rows and the `enforces`/`encrypts` edges — `_EDGE_CLAIM`
#: sorts those two apart, so this set alone does not choose the writer.
#:
#: What actually reaches the not-applicable branch is `cadence` and `lifecycle`: those claims are
#: drift-ELIGIBLE (the skeptic is sent to the same declaring line the anchor holds) but have no writer
#: here, so they are re-authored by hand. `persistence` and `messaging` never arrive at all —
#: `anchor_drift._confirmed_drifts` filters them out upstream as report-only.
#:
#: A theme added to `audit_model._THEMES` and not classified here silently becomes "not applicable",
#: which would stop `apply-drift` writing a kind it should write. `tests/test_fix.py` pins the
#: partition against `_THEMES` for exactly that.
_WRITABLE_THEMES = frozenset({"security", "dep-usage", "ownership", "backbone"})


def _security_claim(surface: str, source: str) -> str:
    """Rebuild a security row's L2 grounding claim EXACTLY as `l2_worklist_model` (audit_model.py) —
    the one string a drift record's `claim` is matched back against. Recomputed (never regex-parsed
    off the drift record), so a surface containing the claim's delimiters can't corrupt the match."""
    return f"Auth surface '{surface}' is protected by: {_claim_text(source)}"


def _load(map_path: Path) -> tuple[ProjectModel, frozenset[str] | None]:
    """Load the target, which may be an assembled map OR a build fragment. Returns the fragment's own
    key set (None for a full map) so `_write` can keep a fragment a fragment."""
    from coyodex.assemble import load_map_or_fragment
    return load_map_or_fragment(map_path)


def _write(map_path: Path, m: ProjectModel, present: frozenset[str] | None = None) -> None:
    from coyodex.assemble import dump_preserving
    map_path.write_text(dump_preserving(m, present), encoding="utf-8")
    if present is not None:
        # Deliberately NOT "this edit is durable". An anchor rewrite is — it changes a `where` string
        # in this file, and the next assemble carries it through. A DROP is not, and `drop-edge` on a
        # fragment is refused for that reason (see `_refuse_fragment_drop`): the riding flow step may
        # live in a SIBLING fragment, where `riding_steps` cannot see it, so the tool reports a clean
        # drop and the next assemble re-derives the edge from the surviving step — silently, and with
        # a different verb. Verified: `C1 persists E1` dropped in one fragment came back as
        # `C1 writes E1`. The `--reconcile drop_edges` path sees the whole merged model and warns.
        print(f"note: edited the fragment {map_path.name} in place, preserving its "
              f"{len(present)} top-level section(s). Re-run `lint-fragment` on it, then re-assemble.",
              file=sys.stderr)
        return
    # `fix` edited the ASSEMBLED map. During a build the source of truth is the fragments, and a later
    # `assemble` regenerates the map from them — silently discarding this edit. Both fresh builds hit
    # exactly this (ran `fix drop-edge`, re-assembled, then hand-scripted the same drop into a
    # fragment). Say so: run `fix` only as the FINAL step, after the last assemble.
    print("note: this edited the assembled map in place — if you `assemble` again it is rebuilt from "
          "fragments and THIS edit is lost. Run `fix` as the final step (after the last assemble), or "
          "make structural changes in a fragment + re-assemble.", file=sys.stderr)


def _refuse_fragment_drop(present: frozenset[str] | None, map_path: Path) -> bool:
    """True (and explains) when a DROP was aimed at a fragment, which cannot be done safely here.

    Dropping a `C→E` edge has to heal the flow steps that rode it, or the next `assemble` re-derives
    the edge from the surviving step. `riding_steps` can only see the model it was handed, so in a
    fragment holding edges but not flows it finds nothing, reports a clean drop, and the drop silently
    does not stick. `--reconcile drop_edges` runs against the whole merged model and reports (or heals)
    the riding steps — which is what `method.md` already prescribes for a build-time drop."""
    if present is None:
        return False
    print(f"ERROR: refusing to drop an edge inside the fragment {map_path.name}. A dropped C→E edge "
          f"must heal the flow steps that rode it, and those steps may live in a SIBLING fragment "
          f"this file cannot see — the drop would look clean and then be undone by the next assemble, "
          f"with the edge re-derived under a different verb. Put the drop in the reconcile file, which "
          f"sees the whole merged model:\n"
          f'  {{"drop_edges": [{{"src": "<Cn>", "verb": "<verb>", "dst": "<En>", "drop_steps": true}}]}}\n'
          f"  coyodex assemble <fragments…> --out .coyodex --reconcile .coyodex/reconcile.json\n"
          f"(method.md, 'Where each reconcile lives'.) Anchor fixes — `apply-drift` — ARE safe on a "
          f"fragment and are not refused.", file=sys.stderr)
    return True


def _need(argv: list[str], i: int, flag: str) -> str:
    if i >= len(argv):
        print(f"ERROR: {flag} needs a value", file=sys.stderr)
        raise SystemExit(2)
    return argv[i]


# ── fix apply-drift ────────────────────────────────────────────────────────────────────────────────

def apply_drift(argv: list[str]) -> int:
    map_path = None
    verdicts_paths: list[str] = []
    tolerance = 2
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--map", "--verdicts", "--tolerance", "--repo"):
            i += 1
            val = _need(argv, i, a)
            if a == "--repo":
                # ACCEPTED AND IGNORED. This verb reads the map and the verdicts and needs no repo,
                # but its sibling `anchor-drift` REQUIRES `--repo` and the two are invoked
                # back-to-back on the same inputs. Rejecting it cost a live build a turn on
                # `ERROR: unknown argument '--repo'`, with nothing saying the flag was merely
                # surplus rather than wrong.
                pass
            elif a == "--map":
                map_path = val
            elif a == "--verdicts":
                # REPEATABLE, and it must stay in lockstep with `anchor-drift`. This used to bind a
                # scalar, so fixing only `anchor-drift`'s arity would have been worse than fixing
                # neither: drift would be reported over the union while the corrections were written
                # from one file, with nothing saying the two disagreed. It also silently lost the
                # NOT-APPLICABLE skip report — with >1 file this printed a bare "rewrote nothing".
                verdicts_paths.append(val)
            else:
                tolerance = int(val)
        else:
            print(f"ERROR: unknown argument '{a}'", file=sys.stderr)
            return 2
        i += 1
    if not map_path or not verdicts_paths:
        print("ERROR: --map and --verdicts are required", file=sys.stderr)
        return 2
    m, _present = _load(Path(map_path))
    grounding, notes = load_verdicts(verdicts_paths)
    for n in notes:
        print(n)
    worklist = l2_worklist_model(m)
    # Honour `Drift exceptions` HERE too. Reporting them in `anchor-drift` while the writer stayed
    # blind was worse than having no escape at all: the row vanished from the report and the anchor
    # got overwritten anyway, so the operator lost the warning he was about to be clobbered by.
    kept, exc_notes = apply_drift_exceptions(m, drift_findings(worklist, grounding, tolerance))
    for n in exc_notes:
        print(n, file=sys.stderr)
    keep_claims = {w.claim for w, _d in kept}
    records = [r for r in drift_records(worklist, grounding, tolerance)
               if r["claim"] in keep_claims]
    edges_applied = 0
    sec_applied = 0
    not_applicable: list[tuple[str, str]] = []
    unparseable: list[tuple[str, str]] = []
    for rec in records:
        corrected = rec.get("corrected")
        mo = _EDGE_CLAIM.match(rec["claim"])
        if mo:                                        # an edge claim — rewrite the edge `where`
            src, verb, dst = mo.group(1), mo.group(2).lower(), mo.group(3)
            if not corrected:
                print(f"note: no consensus line for '{rec['claim']}' — left unchanged", file=sys.stderr)
                continue
            matches = [e for e in m.edges
                       if e.src == src and e.verb.strip().lower() == verb and e.dst == dst]
            if len(matches) != 1:                     # 0 (gone) or >1 (same triple, different call sites)
                print(f"WARNING: '{rec['claim']}' matches {len(matches)} edges — skipped (resolve by "
                      f"hand: an ambiguous multi-site edge must not be blind-rewritten).", file=sys.stderr)
                continue
            e = matches[0]
            if e.where != corrected:
                print(f"  {rec['claim']}: where {e.where!r} → {corrected!r}")
                e.where = corrected
                edges_applied += 1
            continue
        # NOT an edge claim. Before assuming it is a security surface, check whether this command can
        # rewrite its kind AT ALL. `apply-drift` writes exactly two things — an edge `where` and a
        # `security[].source` — so a cadence, store, messaging or lifecycle claim has no writer here.
        # It used to fall straight through to the security branch and report "matches 0 security
        # surfaces — skipped (resolve by hand)", which named the wrong kind and implied a row had
        # vanished; on one map that was every single one of its 17 findings, while the summary line
        # then said "no drifted edge or security anchors to rewrite". Both statements were true and
        # together they were misleading.
        theme = rec.get("theme") or "unknown"
        if theme not in _WRITABLE_THEMES:
            not_applicable.append((theme, rec["claim"]))
            continue
        if theme != "security":
            # An EDGE-themed claim that `_EDGE_CLAIM` could not parse. Letting it reach the security
            # writer below reproduces the bug this dispatch exists to kill: `validate` accepts a
            # multi-word verb (`C1 writes to E1`), the regex's `(\S+)` cannot match it, and the
            # operator was told the claim "matches 0 security surfaces". It is not a security claim
            # and there is nothing to look for — say that instead.
            unparseable.append((theme, rec["claim"]))
            continue
        # a security-surface claim — rewrite the drifted `security[].source` anchor. Match by
        # recomputing each row's claim (never regex-parsing the drift record), same multiplicity guard
        # as the edge path: 0 (gone) or >1 (two rows can share a surface) → skip + warn.
        if not corrected:
            print(f"note: no consensus line for '{rec['claim']}' — left unchanged", file=sys.stderr)
            continue
        sec_matches = [s for s in m.security if _security_claim(s.surface, s.source) == rec["claim"]]
        if len(sec_matches) != 1:
            print(f"WARNING: '{rec['claim']}' matches {len(sec_matches)} security surfaces — skipped "
                  f"(resolve by hand).", file=sys.stderr)
            continue
        s = sec_matches[0]
        if s.source != corrected:
            print(f"  {rec['claim']}: source {s.source!r} → {corrected!r}")
            s.source = corrected
            sec_applied += 1
    if unparseable:
        print(f"WARNING: {len(unparseable)} confirmed drift(s) are edge claims this command could not "
              f"parse back to an edge — an edge claim must read `<Id> <verb> <Id>`, and a multi-word "
              f"verb does not. Fix the edge's `where` by hand, or give the verb a single word:",
              file=sys.stderr)
        for kind, claim in unparseable:
            print(f"    [{kind}] {claim}", file=sys.stderr)
    if not_applicable:
        by_kind: dict[str, int] = {}
        for kind, _claim in not_applicable:
            by_kind[kind] = by_kind.get(kind, 0) + 1
        print(f"note: {len(not_applicable)} confirmed drift(s) are of a kind this command cannot "
              f"rewrite ({', '.join(f'{k}: {n}' for k, n in sorted(by_kind.items()))}) — "
              f"`apply-drift` writes only edge `where` and `security[].source`. Re-anchor each by "
              f"hand, or record why it stands; they do NOT go away by re-running this:", file=sys.stderr)
        for kind, claim in not_applicable:
            print(f"    [{kind}] {claim}", file=sys.stderr)
    # The counts ride the LAST line, including the not-applicable one. A live build read this output
    # with `| tail -12`, so a total that is not on the final line is a total the reader never sees.
    stuck = len(not_applicable) + len(unparseable)
    tail = (f" {stuck} drift(s) NOT APPLICABLE to this command (see above) and still unreconciled."
            if stuck else "")
    if edges_applied or sec_applied:
        _write(Path(map_path), m, _present)
        print(f"apply-drift: rewrote {edges_applied} edge `where` and {sec_applied} security anchor(s)."
              f"{tail} Re-run: validate --check-sources → audit → render.")
    else:
        print(f"apply-drift: rewrote nothing — no drifted edge or security anchor to fix.{tail}")
    return 0


# ── fix drop-edge ────────────────────────────────────────────────────────────────────────────────
# The riding-step query + heal (repoint / drop) is shared with `assemble --reconcile drop_edges`
# (coyodex.reconcile) so the two drop paths reconcile flow steps identically.


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
    m, _present = _load(Path(map_path))
    if _refuse_fragment_drop(_present, Path(map_path)):
        return 2
    kept = [e for e in m.edges if not (e.src == src and e.verb.strip().lower() == verb and e.dst == dst)]
    removed = len(m.edges) - len(kept)
    if removed == 0:
        print(f"ERROR: no edge '{src} {verb} {dst}' found", file=sys.stderr)
        return 1
    m.edges = kept
    riding = riding_steps(m, src, dst)
    if new_dst:
        repoint_riding(riding, dst, new_dst)
        print(f"drop-edge: removed {removed} edge(s); re-pointed {len(riding)} riding step(s) "
              f"{dst} → {new_dst}.")
    elif drop_steps:
        drop_riding(m, riding)
        print(f"drop-edge: removed {removed} edge(s) and {len(riding)} riding step(s).")
    else:
        print(f"drop-edge: removed {removed} edge(s).")
        if riding:
            print(f"  {len(riding)} flow step(s) rode this edge and now attribute {src}↔{dst} with no "
                  f"backing edge (validate warns on C↔E; C↔C is silent) — reconcile them:")
            for owner, st in riding:
                print(f"    {owner} step {st.n}: {st.src} → {st.dst}  ({st.phrase or '—'})")
            print("  Re-run with --repoint <newDst> or --drop-steps, or edit the steps by hand.")
    _write(Path(map_path), m, _present)
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
    m, _present = _load(Path(map_path))
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
    _write(Path(map_path), m, _present)
    print(f"dedup-relation: dropped {dropped} relation(s). "
          f"Re-run: validate --check-sources → audit → render.")
    return 0


# ── fix dedup-edge ──────────────────────────────────────────────────────────────────────────────

def _conflicting_edges(m: ProjectModel) -> dict[tuple[str, str, str], list[int]]:
    """(src, verb, dst) triples authored more than once, with the indexes of every occurrence.

    `assemble` already collapses duplicates that share a call site; what is left here declares the
    SAME relationship at DIFFERENT lines, which is a real conflict — one of the anchors is wrong,
    and a duplicate has masked a wrong anchor before."""
    triples: dict[tuple[str, str, str], list[int]] = {}
    for i, e in enumerate(m.edges):
        triples.setdefault((e.src, e.verb, e.dst), []).append(i)
    return {k: v for k, v in triples.items() if len(v) > 1}


def _own_code_rank(anchor: str, repo: Path | None) -> tuple[int, int, str]:
    """Sort key preferring the anchor most likely to be the true call site.

    The heuristic a live build hand-wrote as a 40-line script: prefer a path that exists in the
    repo, then one under a source root over a test or a script, then the shortest path. Reported,
    never applied silently — `--keep` is how a choice becomes an edit."""
    path = anchor.split(":")[0] if anchor else ""
    exists = 0 if (repo and path and (repo / path).exists()) else 1
    is_side = 1 if re.search(r"(^|/)(tests?|scripts?|docs?|examples?)/", path) else 0
    return (exists, is_side, str(len(path)).zfill(4) + path)


def dedup_edge(argv: list[str]) -> int:
    """List, or resolve, the duplicate (src, verb, dst) edges `validate` warns about.

    This existed only as a warning with no tool behind it: `coyodex fix` claims these mechanical
    reconcile edits are "never hand-scripted", but there was no verb for the commonest one. A live
    build hand-wrote a 40-line script to resolve 24 conflicting triples and dropped 29 rows."""
    map_path = None
    repo: Path | None = None
    keeps: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--map", "--repo", "--keep"):
            i += 1
            val = _need(argv, i, a)
            if a == "--map":
                map_path = val
            elif a == "--repo":
                repo = Path(val)
            else:
                keeps.append(val)
        else:
            print(f"ERROR: unknown argument '{a}'", file=sys.stderr)
            return 2
        i += 1
    if not map_path:
        print("ERROR: --map is required", file=sys.stderr)
        return 2
    m, present = _load(Path(map_path))
    conflicts = _conflicting_edges(m)
    if not conflicts:
        print("dedup-edge: no (src, verb, dst) edge is declared more than once.")
        return 0
    if not keeps:
        print(f"{len(conflicts)} edge(s) declared more than once, at DIFFERING call sites. "
              f"Pick the true site for each, then re-run with the --keep token(s):\n")
        for (s, v, d), idxs in sorted(conflicts.items()):
            anchors = [(m.edges[i].where or "(no call site)") for i in idxs]
            best = min(anchors, key=lambda a: _own_code_rank(a, repo))
            print(f"  {s} {v} {d}")
            for anchor in anchors:
                mark = " <- suggested" if anchor == best else ""
                print(f"      {anchor}{mark}")
            print(f"      --keep {s}:{v}:{d}:{best}")
        print("\nEach --keep drops every OTHER occurrence of that triple. The suggestion prefers an "
              "anchor that exists in --repo, outside tests/scripts, with the shortest path — it is "
              "a hint, not a verdict.")
        return 0
    drop_idx: set[int] = set()
    for tok in keeps:
        parts = tok.split(":")
        if len(parts) < 4:
            print(f"ERROR: bad --keep token '{tok}' (want src:verb:dst:path:line)", file=sys.stderr)
            return 2
        s, v, d, anchor = parts[0], parts[1], parts[2], ":".join(parts[3:])
        idxs = conflicts.get((s, v, d))
        if idxs is None:
            print(f"ERROR: '{s} {v} {d}' is not a duplicated edge in this map", file=sys.stderr)
            return 1
        keep = [i for i in idxs if (m.edges[i].where or "(no call site)") == anchor]
        if not keep:
            print(f"ERROR: none of {s} {v} {d}'s occurrences is anchored at '{anchor}'",
                  file=sys.stderr)
            return 1
        drop_idx |= {i for i in idxs if i != keep[0]}
        print(f"  kept {s} {v} {d} at {anchor}")
    m.edges = [e for i, e in enumerate(m.edges) if i not in drop_idx]
    _write(Path(map_path), m, present)
    print(f"dedup-edge: dropped {len(drop_idx)} duplicate occurrence(s). "
          f"Re-run: validate --check-sources → audit → render.")
    return 0


# ── dispatch ─────────────────────────────────────────────────────────────────────────────────────

_VERBS = {"apply-drift": apply_drift, "drop-edge": drop_edge, "dedup-relation": dedup_relation,
          "dedup-edge": dedup_edge}

_USAGE = """usage: coyodex fix <verb> [args...]

Apply a mechanical reconcile edit to .coyodex/project-map.json IN PLACE. Verbs:

  apply-drift --map <map> --verdicts <raw.json>... [--tolerance N]
      Write the grounding skeptics' corrected `where` line into each drifted edge (same verdicts
      `coyodex anchor-drift` reads). Matches the full (src, verb, dst) triple; an ambiguous
      multi-site edge is skipped, not blind-rewritten.

  dedup-edge --map <map> [--repo <root>] [--keep <src:verb:dst:path:line> ...]
      With no --keep, LIST every (src, verb, dst) edge declared more than once at DIFFERING call
      sites — the conflict `validate` warns about — and suggest which anchor is the true one.
      With --keep, drop every other occurrence of that triple.

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
