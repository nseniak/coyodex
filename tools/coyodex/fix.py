#!/usr/bin/env python3
"""`coyodex fix` — the mechanical reconcile edits the method's Phase-3/4 reconcile needs, applied to
the stored model IN PLACE so they are never hand-scripted (a hand script that matched edges by
endpoints-only once swapped a paired `persists`/`reads` edge — the class this command exists to kill).

Each verb loads `project-map.json`, mutates the dataclass tree, and writes it back through the one
canonical serializer (validity guaranteed by the serializer, never by hand):

  fix apply-drift   — write the grounding skeptics' corrected `where` line into each drifted edge
                      (consumes the same verdicts `coyodex anchor-drift` reads). Matches on the FULL
                      `(src, verb, dst)` triple, so paired edges sharing endpoints never swap.
  fix drop-edge     — remove a refuted backbone edge and surface (or heal) the flow steps that rode it.
  fix dedup-relation — resolve the blocking "relation declared on both cards" / "declared twice"
                      domain-card duplicates by dropping ONE human-chosen occurrence (never silent —
                      a wrong drop deletes a real domain fact).
  fix security-row  — rewrite a REFUTED security surface's text (and/or anchor), selected exactly.
                      0 or >1 matches is a refusal, not a "first match": the hand script this
                      replaces matched a substring, hit two rows, and clobbered a CONFIRMED claim.
  fix dedup-security — drop security rows authored twice under the same surface (two fragments
                      harvesting one auth check). Rows merely SHARING an anchor are reported, never
                      dropped — that is legal, and treating it as duplication is how the clobber
                      above got mistaken for a de-duplication.

After any fix, re-run the invariant: validate --check-sources → audit → render. Stdlib-only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from coyodex import subverb_help
from coyodex.anchor_drift import (apply_drift_exceptions, drift_findings, drift_records,
                                  load_verdicts)
from coyodex.audit_model import (EDGE_CLAIM as _EDGE_CLAIM, apply_anchor_corrections,
                                 l2_worklist_model, security_claim as _security_claim)
from coyodex.model import ProjectModel
from coyodex.reconcile import drop_riding, repoint_riding, riding_steps

#: The listing's display text for an edge carrying no anchor. Never a value to RECORD.
_NO_CALL_SITE = "(no call site)"

#: The claim themes `apply-drift` has a writer for: an edge's `where` and a security row's `source`.
#: `security` covers BOTH the auth-surface rows and the `enforces`/`encrypts` edges — `_EDGE_CLAIM`
#: sorts those two apart, so this set alone does not choose the writer.
#:
#: What reaches the not-applicable branch is `lifecycle`: those claims are drift-ELIGIBLE (the
#: skeptic is sent to the same declaring line the anchor holds) but have no writer here, so they are
#: re-authored by hand. `cadence` used to be in that bucket and no longer is — a live build had five
#: cadence drifts refused and hand-typed them back through a bespoke script. `persistence` and `messaging` never arrive at all —
#: `anchor_drift._confirmed_drifts` filters them out upstream as report-only.
#:
#: A theme added to `audit_model._THEMES` and not classified here silently becomes "not applicable",
#: which would stop `apply-drift` writing a kind it should write. `tests/test_fix.py` pins the
#: partition against `_THEMES` for exactly that.
_WRITABLE_THEMES = frozenset({"security", "dep-usage", "ownership", "backbone", "cadence"})


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
    to_reconcile: str | None = None
    tolerance = 2
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--map", "--verdicts", "--tolerance", "--repo", "--to-reconcile"):
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
            elif a == "--to-reconcile":
                to_reconcile = val
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
    not_applicable: list[tuple[str, str]] = []
    unparseable: list[tuple[str, str]] = []
    corrections: list[tuple[str, str]] = []
    for rec in records:
        claim = rec["claim"]
        theme = rec.get("theme") or "unknown"
        # Partition BEFORE writing. `apply_anchor_corrections` dispatches on the claim's shape, so
        # everything it cannot place comes back as "matches nothing" — true, and useless to a reader
        # holding a cadence claim. The theme says which kind the claim IS, so an unwritable kind and
        # a malformed edge claim get their own accurate message here.
        if _EDGE_CLAIM.match(claim):
            corrections.append((claim, rec.get("corrected") or ""))
            continue
        if theme not in _WRITABLE_THEMES:
            not_applicable.append((theme, claim))
            continue
        if theme not in ("security", "cadence"):
            # An EDGE-themed claim that `_EDGE_CLAIM` could not parse. Letting it reach the security
            # writer reproduces the bug this dispatch exists to kill: `validate` accepts a multi-word
            # verb (`C1 writes to E1`), the regex's `(\S+)` cannot match it, and the operator was
            # told the claim "matches 0 security surfaces". It is not a security claim and there is
            # nothing to look for — say that instead.
            unparseable.append((theme, claim))
            continue
        corrections.append((claim, rec.get("corrected") or ""))
    _report_stuck(unparseable, not_applicable)
    if to_reconcile:
        # DURABLE. Writing anchors into the ASSEMBLED map is exactly what the note below warns
        # about, and a live build walked into it: 14 anchors corrected here, the map re-assembled to
        # pick up a fragment edit, and all 14 silently reverted — then re-typed by hand, from the
        # human-readable listing, into two bespoke python scripts. `set_anchors` is read by
        # `assemble --reconcile`, so the correction survives every rebuild.
        return _anchors_to_reconcile(Path(to_reconcile), corrections, not_applicable, unparseable)
    counts, notes = apply_anchor_corrections(m, corrections)
    for n in notes:
        # An applied rewrite is indented and is the RESULT (stdout); a skip is a warning (stderr).
        print(n, file=sys.stdout if n.startswith("  ") else sys.stderr)
    edges_applied, sec_applied, cadence_applied = counts["edge"], counts["security"], counts["cadence"]
    stuck = len(not_applicable) + len(unparseable)
    # The counts ride the LAST line, including the not-applicable one. A live build read this output
    # with `| tail -12`, so a total that is not on the final line is a total the reader never sees.
    tail = (f" {stuck} drift(s) NOT APPLICABLE to this command (named above) and still "
            f"unreconciled." if stuck else "")
    if edges_applied or sec_applied or cadence_applied:
        _write(Path(map_path), m, _present)
        print(f"apply-drift: rewrote {edges_applied} edge `where`, {sec_applied} security anchor(s) "
              f"and {cadence_applied} cadence anchor(s).{tail} "
              f"Re-run: validate --check-sources → audit → render.")
    else:
        print(f"apply-drift: rewrote nothing — no drifted edge, security or cadence anchor to "
              f"fix.{tail}")
    return 0


def _report_stuck(unparseable: list[tuple[str, str]],
                  not_applicable: list[tuple[str, str]]) -> None:
    """Name every drift this command cannot write, BEFORE either write path returns.

    It used to run only on the in-place path, so `--to-reconcile` ended with
    "N drift(s) NOT APPLICABLE to this command (see above)" and nothing above — the claims needing
    a hand re-anchor were counted and never named."""
    if unparseable:
        print(f"WARNING: {len(unparseable)} confirmed drift(s) are edge claims this command could "
              f"not parse back to an edge — an edge claim must read `<Id> <verb> <Id>`, and a "
              f"multi-word verb does not. Fix the edge's `where` by hand, or give the verb a single "
              f"word:", file=sys.stderr)
        for kind, claim in unparseable:
            print(f"    [{kind}] {claim}", file=sys.stderr)
    if not_applicable:
        by_kind: dict[str, int] = {}
        for kind, _claim in not_applicable:
            by_kind[kind] = by_kind.get(kind, 0) + 1
        print(f"note: {len(not_applicable)} confirmed drift(s) are of a kind this command cannot "
              f"rewrite ({', '.join(f'{k}: {n}' for k, n in sorted(by_kind.items()))}) — "
              f"`apply-drift` writes an edge `where`, a `security[].source` and an entry point's "
              f"`cadence_source`. Re-anchor each by hand, or record why it stands; they do NOT go "
              f"away by re-running this:", file=sys.stderr)
        for kind, claim in not_applicable:
            print(f"    [{kind}] {claim}", file=sys.stderr)


def _anchors_to_reconcile(rec_path: Path, corrections: list[tuple[str, str]],
                          not_applicable: list[tuple[str, str]],
                          unparseable: list[tuple[str, str]]) -> int:
    """Record the corrected anchors as `set_anchors` in the reconcile file instead of editing the map.

    Keyed by CLAIM, which is what a verdict carries and what `apply_anchor_corrections` matches on,
    so the durable record and the in-place edit cannot drift apart. Re-recording the same claim with
    a different anchor UPDATES it and says so — silently discarding a changed mind is how a durable
    record ends up asserting what the artifact does not do."""
    try:
        doc = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.exists() else {}
    except ValueError as e:
        print(f"ERROR: {rec_path} is not valid JSON ({e})", file=sys.stderr)
        return 2
    existing = doc.get("set_anchors") or []
    by_claim = {a.get("claim"): a for a in existing if isinstance(a, dict)}
    added = updated = 0
    for claim, corrected in corrections:
        if not corrected:
            print(f"  SKIPPED (no corrected line): {claim}", file=sys.stderr)
            continue
        prior = by_claim.get(claim)
        if prior is None:
            new = {"claim": claim, "corrected": corrected}
            existing.append(new)
            by_claim[claim] = new
            added += 1
            print(f"  recorded {claim} → {corrected}")
        elif prior.get("corrected") != corrected:
            print(f"  UPDATED {claim}: {prior.get('corrected')} -> {corrected}")
            prior["corrected"] = corrected
            updated += 1
    stuck = len(not_applicable) + len(unparseable)
    stuck_tail = (f" {stuck} drift(s) NOT APPLICABLE to this command (named above) and still "
                  f"unreconciled." if stuck else "")
    if not added and not updated and "set_anchors" not in doc:
        # Nothing to record and no prior key: writing would re-serialise (and reformat) a committed
        # artifact to say nothing. The stuck count still rides the last line — it is the half of the
        # result that is not "nothing happened".
        print(f"apply-drift: no anchor correction to record — the reconcile file was not "
              f"touched.{stuck_tail}")
        return 0
    doc["set_anchors"] = existing
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    # indent=2 + ensure_ascii=False, matching `dedup-edge --to-reconcile`; two writers of one file
    # that disagree on formatting churn it on every alternating run (a claim holding an em dash
    # came out `\u2014`-escaped by one and literal by the other).
    rec_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"apply-drift: recorded {added} new and {updated} updated anchor correction(s) in "
          f"{rec_path} — the MAP was not edited. Re-run `assemble … --reconcile {rec_path}` to "
          f"apply them, then validate --check-sources → audit → render.{stuck_tail}")
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
    to_reconcile: str | None = None
    as_json = False
    accept_suggested = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True
        elif a == "--accept-suggested":
            accept_suggested = True
        elif a in ("--map", "--repo", "--keep", "--to-reconcile"):
            i += 1
            val = _need(argv, i, a)
            if a == "--map":
                map_path = val
            elif a == "--repo":
                repo = Path(val)
            elif a == "--to-reconcile":
                to_reconcile = val
            else:
                keeps.append(val)
        else:
            print(f"ERROR: unknown argument '{a}'", file=sys.stderr)
            return 2
        i += 1
    if not map_path:
        print("ERROR: --map is required", file=sys.stderr)
        return 2
    # These three express DIFFERENT intents and silently overrode each other. `--json
    # --accept-suggested` printed the listing, wrote nothing and exited 0 — a script asking to apply
    # and report got a no-op that looked like success. `--keep X --accept-suggested` threw away the
    # operator's explicit choice in favour of the blanket one, which is the wrong direction for a
    # flag whose whole point is that a wrong drop is unrecoverable. Refuse instead of guessing.
    if accept_suggested and as_json:
        print("ERROR: --json lists without writing; --accept-suggested writes. Pick one: run "
              "--json to review, then --accept-suggested to apply.", file=sys.stderr)
        return 2
    if accept_suggested and keeps:
        print("ERROR: --accept-suggested takes the suggestion for EVERY conflict, which would "
              "override the --keep token(s) you named. Pass one or the other.", file=sys.stderr)
        return 2
    # `--to-reconcile` names an OUTPUT, so a run that reaches neither write path silently produced
    # nothing while exiting 0. Both no-write paths below return early — the listing (no `--keep`,
    # no `--accept-suggested`) at "pick the true site for each", and `--json` — and each ignored the
    # flag on the way out. A live build ran `dedup-edge --map … --repo … --to-reconcile <file>`,
    # got exit 0 and a full listing, and the file was untouched; it only noticed because it read the
    # file back afterwards. A build that trusted the exit code would ship a map whose fragments
    # re-assemble to a different edge count — the exact failure `--to-reconcile` exists to prevent.
    # Refuse rather than guess: implying `--accept-suggested` would apply a blanket choice nobody
    # asked for, and a wrong drop is unrecoverable.
    if to_reconcile and as_json:
        print("ERROR: --json lists without writing; --to-reconcile writes. Pick one: run --json to "
              "review, then re-run with --to-reconcile plus --keep or --accept-suggested.",
              file=sys.stderr)
        return 2
    m, present = _load(Path(map_path))
    conflicts = _conflicting_edges(m)
    if not conflicts:
        if as_json:
            print(json.dumps({"conflicts": []}, indent=1))
        else:
            print("dedup-edge: no (src, verb, dst) edge is declared more than once.")
        return 0
    # AFTER the no-conflicts return, deliberately. Placed above it, this refusal failed the healthy
    # end state: a map with nothing to de-duplicate exited 2, so a pipeline that runs the dedup step
    # unconditionally — which is what a durable-decision step should do — broke precisely when the
    # map was correct, and the message pushed the operator toward `--accept-suggested` on a map with
    # nothing to accept.
    if to_reconcile and not keeps and not accept_suggested:
        print(f"ERROR: --to-reconcile needs a decision to record, and none was given — nothing was "
              f"written, and {len(conflicts)} conflict(s) are still unresolved. Re-run with "
              f"--accept-suggested to take every suggestion, or with the --keep token(s) for the "
              f"conflicts you chose. Run without --to-reconcile to see the listing first.",
              file=sys.stderr)
        return 2
    # The suggestion ranking's first term is "exists under --repo"; with no --repo it is constant for
    # every candidate and the sort silently degrades to shortest-path. A live build passed --repo to
    # the listing it discarded and omitted it from the listing it applied, with nothing saying so.
    ranked = {(s, v, d): (
        [(m.edges[i].where or "(no call site)") for i in idxs],
        min([(m.edges[i].where or "(no call site)") for i in idxs],
            key=lambda a: _own_code_rank(a, repo)))
        for (s, v, d), idxs in sorted(conflicts.items())}
    if as_json:
        print(json.dumps({
            "repo_ranked": repo is not None,
            "conflicts": [{"src": s, "verb": v, "dst": d, "anchors": anchors,
                           "suggested": best, "keep_token": f"{s}:{v}:{d}:{best}"}
                          for (s, v, d), (anchors, best) in ranked.items()],
        }, indent=1))
        return 0
    if accept_suggested:
        keeps = [f"{s}:{v}:{d}:{best}" for (s, v, d), (_a, best) in ranked.items()]
        print(f"dedup-edge: accepting the suggested anchor for all {len(keeps)} conflict(s)"
              f"{'' if repo else ' — WITHOUT --repo, so suggestions are ranked by path length only'}.")
    if not keeps:
        print(f"{len(conflicts)} edge(s) declared more than once, at DIFFERING call sites. "
              f"Pick the true site for each, then re-run with the --keep token(s) — or "
              f"`--accept-suggested` to take every suggestion below:\n")
        for (s, v, d), (anchors, best) in ranked.items():
            print(f"  {s} {v} {d}")
            for anchor in anchors:
                mark = " <- suggested" if anchor == best else ""
                print(f"      {anchor}{mark}")
            print(f"      --keep {s}:{v}:{d}:{best}")
        print("\nEach --keep drops every OTHER occurrence of that triple. The suggestion prefers an "
              "anchor that exists in --repo, outside tests/scripts, with the shortest path — it is "
              "a hint, not a verdict.")
        if repo is None:
            print("NOTE: no --repo was given, so the 'exists in the repo' term is constant and the "
                  "suggestions are ranked by path length alone. Pass --repo for a real ranking.")
        print("Machine-readable: re-run with --json rather than parsing the lines above.")
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
        if not to_reconcile:
            # Only when this run actually edits the map. Printing it up here made `--to-reconcile`
            # announce `kept … at (no call site)` for a token it then silently skipped — the very
            # "assert what the artifact does not support" shape the skip was added to stop.
            print(f"  kept {s} {v} {d} at {anchor}")
    if to_reconcile:
        # DURABLE. Writing the decision into the assembled map is what made a shipped map
        # irreproducible from its own fragments: 365 edges committed, 416 on re-assemble, the
        # difference being 49 duplicates the next assemble silently restored. `keep_edges` is read
        # by `assemble --reconcile`, so the choice survives every rebuild.
        rec_path = Path(to_reconcile)
        try:
            doc = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.exists() else {}
        except ValueError as e:
            print(f"ERROR: {rec_path} is not valid JSON ({e})", file=sys.stderr)
            return 2
        existing = doc.get("keep_edges") or []
        by_triple = {(k.get("src"), k.get("verb"), k.get("dst")): k for k in existing
                     if isinstance(k, dict)}
        added = updated = skipped = 0
        for tok in keeps:
            parts = tok.split(":")
            s_, v_, d_, anchor = parts[0], parts[1], parts[2], ":".join(parts[3:])
            if anchor == _NO_CALL_SITE:
                # The listing's DISPLAY placeholder for an edge with no anchor. `apply_reconcile`
                # matches against the stored `where`, which is "" for such an edge, so recording the
                # placeholder produces a directive that can never match — a permanent no-op warning
                # "none of ... is anchored at '(no call site)'" on every assemble, phrased as drift
                # rather than as the tool bug it is. `--accept-suggested` walks into it whenever the
                # placeholder sorts first.
                print(f"  SKIPPED {s_} {v_} {d_}: its suggested winner has no call site, and a "
                      f"keep_edges directive matches on the anchor. Give it an anchor in the "
                      f"fragment, or pass an explicit --keep naming another occurrence.",
                      file=sys.stderr)
                skipped += 1
                continue
            print(f"  kept {s_} {v_} {d_} at {anchor}")
            prior = by_triple.get((s_, v_, d_))
            if prior is None:
                new = {"src": s_, "verb": v_, "dst": d_, "where": anchor}
                existing.append(new)
                by_triple[(s_, v_, d_)] = new
                added += 1
            elif prior.get("where") != anchor:
                # Changing your mind was silently discarded while the tool printed `kept ... at
                # <new anchor>` — a durable record asserting what the artifact does not support,
                # which is the pattern this whole series is about.
                print(f"  UPDATED {s_} {v_} {d_}: {prior.get('where')} -> {anchor}")
                prior["where"] = anchor
                updated += 1
        doc["keep_edges"] = existing
        rec_path.parent.mkdir(parents=True, exist_ok=True)
        rec_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if skipped:
            print(f"  {skipped} conflict(s) were NOT recorded (see above) — they are still "
                  f"duplicated in the map.")
        print(f"dedup-edge: recorded {added} new and updated {updated} keep_edges directive(s) in "
              f"{rec_path} ({len(existing)} total). Re-run assemble WITH --reconcile {rec_path}; the map is "
              f"not edited here, so the decision survives every rebuild.")
        # Non-zero when a requested conflict went unrecorded: exit 0 with nothing written is the
        # shape a script reads as success.
        return 1 if skipped and not (added or updated) else 0
    m.edges = [e for i, e in enumerate(m.edges) if i not in drop_idx]
    _write(Path(map_path), m, present)
    print(f"dedup-edge: dropped {len(drop_idx)} duplicate occurrence(s) from the assembled map — "
          f"the next assemble REBUILDS from fragments and restores them. Use --to-reconcile "
          f"<file> to make this durable. Re-run: validate --check-sources → audit → render.")
    return 0


# ── fix security-row ─────────────────────────────────────────────────────────────────────────────
# The Phase-4 writer for a REFUTED security surface. `apply-drift` rewrites a security row's
# `source` when the skeptics agree the anchor moved; it has no answer to the other half of the
# refutation — "that anchor guards nothing, the real gate is elsewhere and your surface/risk text is
# wrong". A live build had to hand-roll that edit, selected the row with
# `'admin' in surface.lower() and source.startswith(…)`, matched TWO rows, and overwrote a CONFIRMED
# claim with the refuted one's replacement text. Nothing caught it but `grounding report`.
#
# So the selector here is EXACT and the multiplicity guard is a refusal, never a "first match":
# every one of `--claim` / `--surface` / `--at` must resolve to exactly one row or the command
# prints the candidates and writes nothing.


def _row_claims(m: ProjectModel) -> list[tuple[int, str]]:
    """Every security row as `(index, its L2 grounding claim)` — the same string
    `l2_worklist_model` pins and a skeptic verdict carries back."""
    return [(i, _security_claim(s.surface, s.source)) for i, s in enumerate(m.security)]


def _select_security_rows(m: ProjectModel, claim: str | None, surface: str | None,
                          at: str | None) -> list[int]:
    """Indexes of the rows matching the given selector(s). Every comparison is EXACT and every
    selector given must hold (they intersect), so `--surface X --at path:line` disambiguates two
    rows sharing a surface without anyone having to invent a regex."""
    idxs = list(range(len(m.security)))
    if claim is not None:
        by_claim = {i for i, c in _row_claims(m) if c == claim}
        idxs = [i for i in idxs if i in by_claim]
    if surface is not None:
        idxs = [i for i in idxs if m.security[i].surface == surface]
    if at is not None:
        idxs = [i for i in idxs if m.security[i].source == at]
    return idxs


def security_row(argv: list[str]) -> int:
    """Rewrite ONE security row's text, selected exactly, or list the rows when no selector is given."""
    map_path = None
    claim = surface = at = None
    sets: dict[str, str] = {}
    as_json = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True
        elif a in ("--map", "--claim", "--surface", "--at",
                   "--set-surface", "--set-risk", "--set-source", "--set-who"):
            i += 1
            val = _need(argv, i, a)
            if a == "--map":
                map_path = val
            elif a == "--claim":
                claim = val
            elif a == "--surface":
                surface = val
            elif a == "--at":
                at = val
            else:
                sets[a[len("--set-"):]] = val
        else:
            print(f"ERROR: unknown argument '{a}'", file=sys.stderr)
            return 2
        i += 1
    if not map_path:
        print("ERROR: --map is required", file=sys.stderr)
        return 2
    m, present = _load(Path(map_path))
    if not m.security:
        print("security-row: this map holds no security rows.")
        return 0
    selectors = {"--claim": claim, "--surface": surface, "--at": at}
    given = {k: v for k, v in selectors.items() if v is not None}
    if not given:
        if sets:
            print("ERROR: --set-* needs a row to write to. Pass --claim (exact L2 claim), "
                  "--surface (exact surface text) or --at <path:line>. Run without --set-* to "
                  "list the rows and their claims.", file=sys.stderr)
            return 2
        rows = [{"index": i, "surface": s.surface, "source": s.source, "who": s.who,
                 "risk": s.risk, "claim": c}
                for (i, c), s in zip(_row_claims(m), m.security)]
        if as_json:
            print(json.dumps({"security": rows}, indent=1))
        else:
            print(f"{len(rows)} security row(s). Select one with --claim / --surface / --at:")
            for r in rows:
                print(f"  [{r['index']}] {r['surface']}\n        at {r['source'] or _NO_CALL_SITE}")
        return 0
    idxs = _select_security_rows(m, claim, surface, at)
    if len(idxs) != 1:
        # The refusal IS the feature. A substring-matching hand script silently took both rows here.
        print(f"ERROR: that selector matches {len(idxs)} security row(s); exactly one is required, "
              f"and nothing was written.", file=sys.stderr)
        for i2 in idxs:
            s = m.security[i2]
            print(f"    [{i2}] surface={s.surface!r} at={s.source!r}", file=sys.stderr)
        if len(idxs) > 1:
            unused = [flag for flag, val in selectors.items() if val is None]
            print(f"Narrow it with {' or '.join(unused)}." if unused else
                  "Every selector is already given and they still match more than one row, so the "
                  "rows are indistinguishable by text.", file=sys.stderr)
            print("If the rows are true duplicates, resolve them with `coyodex fix dedup-security`.",
                  file=sys.stderr)
        return 2
    if not sets:
        s = m.security[idxs[0]]
        print(f"[{idxs[0]}] surface: {s.surface!r}\n     source: {s.source!r}\n"
              f"     who:     {s.who!r}\n     risk:    {s.risk!r}\n"
              f"     claim:   {_security_claim(s.surface, s.source)!r}")
        print("Pass --set-surface / --set-risk / --set-source / --set-who to rewrite it.")
        return 0
    s = m.security[idxs[0]]
    if "surface" in sets and not sets["surface"].strip():
        # The surface IS the row's identity: it keys `dedup-security`, the impact graph's
        # `security:<surface>` reference and the L2 grounding claim. An unset shell variable in
        # `--set-surface "$NEW"` would otherwise anonymise a security row, and no gate catches it.
        print("ERROR: --set-surface cannot be empty — the surface is the row's identity (it keys "
              "dedup-security, the impact reference and the L2 claim). Nothing written.",
              file=sys.stderr)
        return 2
    changed = 0
    for fieldname, val in sets.items():
        before = getattr(s, fieldname)
        if before == val:
            continue
        print(f"  [{idxs[0]}] {fieldname}: {before!r} → {val!r}")
        setattr(s, fieldname, val)
        changed += 1
    if not changed:
        print("security-row: every --set-* value already matched — nothing written.")
        return 0
    _write(Path(map_path), m, present)
    # A rewritten `surface` or `source` CHANGES the row's L2 claim, so the grounding record now
    # pins a claim string that no longer exists. Say it here: the build that hit this learned it
    # from `finalize`, several turns and one re-assemble later.
    if "surface" in sets or "source" in sets:
        print("note: this row's L2 claim changed, so the pinned grounding record no longer names "
              "it. Re-run `coyodex grounding write` (its --keep-note preserves the note) after the "
              "final assemble.")
    print(f"security-row: rewrote {changed} field(s) on 1 row. "
          f"Re-run: validate --check-sources → audit → render.")
    return 0


# ── fix dedup-security ───────────────────────────────────────────────────────────────────────────


def _duplicate_surfaces(m: ProjectModel) -> dict[str, list[int]]:
    """Security rows whose SURFACE text is identical, keyed by that surface.

    Two fragments harvesting the same auth check is the ordinary cause (one build had `fe-pages`
    and `fe-shared` both claiming the same sidebar gate). Identity is the surface, not the anchor:
    two different surfaces legitimately share one anchor, and treating that as a duplicate is what
    a hand script did just before it deleted a real claim."""
    by_surface: dict[str, list[int]] = {}
    for i, s in enumerate(m.security):
        by_surface.setdefault(s.surface, []).append(i)
    return {k: v for k, v in sorted(by_surface.items()) if len(v) > 1}


def _shared_anchors(m: ProjectModel) -> dict[str, list[int]]:
    """Rows sharing one `source` anchor under DIFFERENT surfaces — reported, never dropped."""
    by_anchor: dict[str, list[int]] = {}
    for i, s in enumerate(m.security):
        if s.source:
            by_anchor.setdefault(s.source, []).append(i)
    return {k: v for k, v in sorted(by_anchor.items())
            if len({m.security[i].surface for i in v}) > 1}


def _fullness(s) -> int:
    """How much a row actually says — the tiebreak when two duplicates differ only in detail."""
    return sum(1 for v in (s.who, s.risk, s.source) if v)


def dedup_security(argv: list[str]) -> int:
    """List, or resolve, security rows authored twice under the same surface."""
    map_path = None
    repo: Path | None = None
    keeps: list[str] = []
    as_json = False
    accept_suggested = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True
        elif a == "--accept-suggested":
            accept_suggested = True
        elif a in ("--map", "--repo", "--keep"):
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
    # Same exclusivity as `dedup-edge`, for the same reason: a run that both lists and writes
    # silently did neither.
    if as_json and (accept_suggested or keeps):
        print("ERROR: --json lists without writing; --accept-suggested and --keep write. Pick one: "
              "run --json to review, then re-run with the decision.", file=sys.stderr)
        return 2
    if accept_suggested and keeps:
        print("ERROR: --accept-suggested takes the suggestion for EVERY duplicate, which would "
              "override the --keep token(s) you named. Pass one or the other.", file=sys.stderr)
        return 2
    m, present = _load(Path(map_path))
    dups = _duplicate_surfaces(m)
    shared = _shared_anchors(m)
    ranked = {surface: min(idxs, key=lambda i2: (-_fullness(m.security[i2]),
                                                 _own_code_rank(m.security[i2].source, repo)))
              for surface, idxs in dups.items()}
    if as_json:
        print(json.dumps({
            "duplicate_surfaces": [
                {"surface": surface, "anchors": [m.security[i2].source for i2 in idxs],
                 "suggested": m.security[ranked[surface]].source,
                 "keep_token": f"{surface}::{m.security[ranked[surface]].source}"}
                for surface, idxs in dups.items()],
            "shared_anchors": [
                {"source": src, "surfaces": [m.security[i2].surface for i2 in idxs]}
                for src, idxs in shared.items()],
        }, indent=1))
        return 0
    if shared:
        # Not a defect and never dropped here — but it is the shape that hid a clobbered claim, so
        # it is printed every run, including the clean one.
        print(f"note: {len(shared)} anchor(s) carry MORE THAN ONE surface. That is legal (one line "
              f"can guard two things) and nothing below touches them; edit one with "
              f"`fix security-row --at <path:line> --surface <exact text>`:")
        for src, idxs in shared.items():
            print(f"    {src}")
            for i2 in idxs:
                print(f"      · {m.security[i2].surface}")
    if not dups:
        print("dedup-security: no security surface is authored more than once.")
        return 0
    if not keeps and not accept_suggested:
        print(f"{len(dups)} security surface(s) authored more than once. Keep one anchor per "
              f"surface, then re-run with the token(s):")
        for surface, idxs in dups.items():
            print(f"  {surface}")
            for i2 in idxs:
                s = m.security[i2]
                mark = " (suggested)" if i2 == ranked[surface] else ""
                print(f"      · {s.source or _NO_CALL_SITE}{mark}  risk={s.risk or '—'!r}")
            print(f"      --keep '{surface}::{m.security[ranked[surface]].source}'")
        if not repo:
            print("Pass --repo <root> so the suggestion can prefer an anchor that exists in the "
                  "repo; without it, ranking falls back to path length.")
        return 0
    # DECISIONS are (surface, anchor) pairs. `--accept-suggested` builds them directly; a `--keep`
    # token is RESOLVED against the real candidates rather than split on "::". Splitting was a bug
    # of exactly the kind this command exists to prevent: with a surface named `A::B` present,
    # `partition("::")` read the token the tool itself had printed as surface `A`, and dropped a row
    # belonging to a different surface while reporting success.
    decisions: list[tuple[str, str]] = []
    if accept_suggested:
        decisions = [(surface, m.security[ranked[surface]].source) for surface in dups]
        print(f"dedup-security: accepting the suggested anchor for all {len(decisions)} duplicate(s)"
              f"{'' if repo else ' — WITHOUT --repo, so suggestions are ranked by path length only'}.")
    for token in keeps:
        candidates = [(surface, m.security[i2].source) for surface, idxs in dups.items()
                      for i2 in idxs if token == f"{surface}::{m.security[i2].source}"]
        uniq = sorted(set(candidates))
        if not uniq:
            print(f"ERROR: --keep token {token!r} names no duplicate row. Run without --keep to "
                  f"see the tokens — nothing written.", file=sys.stderr)
            return 2
        if len(uniq) > 1:
            print(f"ERROR: --keep token {token!r} is ambiguous — it reads as "
                  + " and as ".join(f"surface {s!r} at {a!r}" for s, a in uniq)
                  + ". A surface containing '::' cannot be named by a token; resolve these rows by "
                    "hand. Nothing written.", file=sys.stderr)
            return 2
        decisions.append(uniq[0])
    drop: set[int] = set()
    for surface, anchor in decisions:
        idxs = dups.get(surface)
        if not idxs:
            print(f"ERROR: {surface!r} is not authored more than once — nothing written.",
                  file=sys.stderr)
            return 2
        keep_idx = [i2 for i2 in idxs if m.security[i2].source == anchor]
        if not keep_idx:
            print(f"ERROR: {anchor!r} is not one of the anchors for {surface!r} — nothing written.",
                  file=sys.stderr)
            return 2
        if len(keep_idx) > 1:
            # The ORDINARY duplicate: two fragments harvested one auth check, so the rows share the
            # surface AND the anchor. Refusing here made the command unable to resolve the very case
            # it exists for, and the advisory that sends the operator here had no other answer than
            # the hand script this replaces. Rows that are byte-identical are not a choice; rows
            # that differ elsewhere still are.
            rows = [m.security[i2] for i2 in keep_idx]
            first = rows[0]
            identical = all((r.surface, r.source, r.who, r.risk)
                            == (first.surface, first.source, first.who, first.risk) for r in rows)
            if not identical:
                print(f"ERROR: {len(keep_idx)} rows for {surface!r} share the anchor {anchor!r} but "
                      f"differ in `who`/`risk`, so which one survives IS a decision — resolve them "
                      f"with `fix security-row`. Nothing written.", file=sys.stderr)
                for i2 in keep_idx:
                    s = m.security[i2]
                    print(f"    [{i2}] who={s.who!r} risk={s.risk!r}", file=sys.stderr)
                return 2
            print(f"  {len(keep_idx)} identical rows for {surface!r} at {anchor!r} — keeping one.")
        drop.update(i2 for i2 in idxs if i2 != keep_idx[0])
    for i2 in sorted(drop):
        s = m.security[i2]
        print(f"  dropping duplicate: {s.surface} at {s.source or _NO_CALL_SITE}")
    m.security = [s for i2, s in enumerate(m.security) if i2 not in drop]
    _write(Path(map_path), m, present)
    print(f"dedup-security: dropped {len(drop)} duplicate row(s), {len(m.security)} remain. "
          f"Re-run: validate --check-sources → audit → render.")
    return 0


# ── dispatch ─────────────────────────────────────────────────────────────────────────────────────

_VERBS = {"apply-drift": apply_drift, "drop-edge": drop_edge, "dedup-relation": dedup_relation,
          "dedup-edge": dedup_edge, "security-row": security_row,
          "dedup-security": dedup_security}

_USAGE = """usage: coyodex fix <verb> [args...]

Apply a mechanical reconcile edit to .coyodex/project-map.json IN PLACE. Verbs:

  apply-drift --map <map> --verdicts <raw.json>... [--tolerance N] [--to-reconcile <file>]
      Write the grounding skeptics' corrected anchor into each drifted element: an edge `where`, a
      `security[].source`, or an entry point's `cadence_source`. Same verdicts `coyodex
      anchor-drift` reads. Matches the full (src, verb, dst) triple (or the row's exact L2 claim);
      an ambiguous multi-site target is skipped, not blind-rewritten.
      --to-reconcile records the corrections as `set_anchors` in the reconcile file INSTEAD of
      editing the map, so `assemble --reconcile` re-applies them on every rebuild. Without it the
      edit is lost at the next assemble — a live build corrected 14 anchors, re-assembled for one
      fragment edit, lost all 14, and re-typed them by hand.

  dedup-edge --map <map> [--repo <root>] [--json]
             (--accept-suggested | --keep <src:verb:dst:path:line> ...) [--to-reconcile <file>]
      With neither --keep nor --accept-suggested, LIST every (src, verb, dst) edge declared more
      than once at DIFFERING call sites — the conflict `validate` warns about — and suggest which
      anchor is the true one. With --keep, drop every other occurrence of that triple.
      --accept-suggested takes the suggestion for EVERY conflict, which is what harvesting the
      printed --keep lines through a shell was trying to do (and got wrong twice: zsh does not
      word-split an unquoted expansion, and the surrounding prose also contains "--keep ").
      --json emits the same listing as data; parse that, never the lines above.
      --to-reconcile writes the choices as `keep_edges` into the reconcile file INSTEAD of editing
      the map, so `assemble --reconcile` re-applies them on every rebuild. Without it the edit is
      lost at the next assemble — a shipped map carried 365 edges while its own fragments
      re-assembled to 416.
      THE THREE MODES ARE EXCLUSIVE, and mixing them is refused rather than guessed at:
        · --to-reconcile NEEDS a decision — pass --accept-suggested or --keep. On its own it used
          to print the listing, write nothing, and exit 0, which reads as success.
        · --json lists, --accept-suggested and --to-reconcile write. Never both.
        · --accept-suggested overrides every --keep you named. Pass one or the other.
      A map with no duplicate edges is not an error: it prints so and exits 0 whatever the flags.
      Pass --repo, or the "exists in the repo" rank term is constant and suggestions fall back to
      shortest-path.

  drop-edge --map <map> <src> <verb> <dst> [--drop-steps | --repoint <newDst>]
      Remove a refuted backbone edge. By default it REPORTS the flow steps that rode it (for a
      hand reconcile); --drop-steps removes them, --repoint <newDst> re-points them.

  dedup-relation --map <map> [--drop <En:verb:Em> ...]
      With no --drop, LIST the blocking "declared on both cards" / "declared twice" domain-card
      duplicates and the token to resolve each. With --drop, remove ONE chosen occurrence.

  security-row --map <map> [--claim <exact claim> | --surface <exact text> | --at <path:line>]
               [--set-surface T] [--set-risk T] [--set-source path:line] [--set-who T] [--json]
      The writer for a REFUTED security surface — when the skeptics say the anchor guards nothing
      and the surface/risk text is wrong. `apply-drift` only moves a row's `source`; this rewrites
      the text too. With no selector it LISTS every row with its exact L2 claim; with a selector
      and no --set-* it prints that one row.
      EVERY selector is an exact match and they intersect, and a selector resolving to 0 or >1 rows
      is REFUSED with the candidates printed — nothing is written. That refusal is the whole point:
      the hand script this replaces matched `'admin' in surface.lower()`, hit two rows, and
      overwrote a CONFIRMED claim with the refuted one's text. Two rows sharing an anchor is legal,
      so disambiguate with --at plus --surface, or use --claim (unique per row).

  dedup-security --map <map> [--repo <root>] [--json] [--accept-suggested | --keep <surface::anchor> ...]
      Resolve security rows authored more than once under the SAME surface (two fragments
      harvesting one auth check). Identity is the surface, never the anchor — two different
      surfaces sharing one anchor is legal and is reported, not dropped.
      With neither --keep nor --accept-suggested it LISTS the duplicates and suggests which anchor
      to keep (pass --repo, or the "exists in the repo" rank term is constant and the suggestion
      degrades to shortest-path). --json emits the same listing as data.
      Rows that are byte-identical are not a choice — one is kept. Rows sharing surface AND anchor
      but differing in `who`/`risk` ARE a choice, and are refused: use `security-row`.

NOTE — `security-row` and `dedup-security` edit the ASSEMBLED map and have no `--to-reconcile`
form, so their edit is DISCARDED by the next `assemble` (every write prints that warning). Run them
after the last assemble, or make the same change in the owning fragment. `apply-drift` is the one
verb here with a durable form.

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
    # Above the per-verb parsers on purpose: each one treats an unknown flag as a usage error, so
    # all four answered `ERROR: unknown argument '--help'`. See subverb_help.
    helped = subverb_help.handle(_USAGE, verb, rest)
    if helped is not None:
        return helped
    return fn(rest)


if __name__ == "__main__":
    raise SystemExit(main())
