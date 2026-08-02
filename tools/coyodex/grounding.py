#!/usr/bin/env python3
"""`coyodex grounding write` — derive the map's `grounding` record from the verdict files.

The four counts are the one thing `validate` BLOCKS on (`confirmed + refuted + unverifiable ==
challenged`), and until now nothing produced them: every build hand-wrote the block from a throwaway
tally. On a live build that record shipped asserting work that had not happened — "Roughly 20 further
anchors were confirmed-but-drifted **and corrected**", written 18 seconds before `anchor-drift
--verdicts` first ran (which found 23, not the guessed 20) and 29 before `fix apply-drift`, the tool
that actually does the correcting, ran at all — plus an
internal contradiction ("three skeptics split … two confirmed and two refuted" is four skeptics).
A hand-written honesty record is a contradiction in terms.

THE SNAPSHOT PROBLEM, which is why `--worklist` is required rather than re-derived. The normal build
order is: audit → skeptics → apply the refutations → the map shrinks. So by the time the record is
written, a fresh `audit` no longer matches the verdicts: on a live map the worklist had fallen to 404
while 408 claims had been challenged. Recomputing `claims_total` from the current map therefore emits
`claims_challenged (408) exceeds claims_total (404)` — a BLOCKING map, produced by the command meant
to stop the record lying. Counting only verdicts that still match the live worklist is worse: the
refuted claims are exactly the ones the fixes deleted, so it yields `confirmed 396 / refuted 0`, a
record asserting nothing was ever refuted. Both were reproduced. The worklist must be PINNED — the
`audit --json` captured before the fixes — and this command refuses anything else.

Stdlib-only (the cli.py firewall).
"""
from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

from coyodex import subverb_help
from coyodex.anchor_drift import load_verdicts

USAGE = """usage: coyodex grounding write  --worklist <audit.json> --verdicts <raw.json>... \\
                               [--out <fragment.json>] [--note <text>] [--json]
                               [--map <project-map.json>]
coyodex grounding report --worklist <audit.json> --verdicts <raw.json>... [--map <map>] [--json]
       coyodex grounding report --worklist <audit.json> --verdicts <raw.json>... [--json]

`report` prints WHICH claims were refuted, tied, unverifiable or unvoted — the reconcile worklist
`write` computes and then reduces to four counts. A TIE is listed apart from a stated
`unverifiable`: the first needs a human decision, the second is a skeptic saying the code cannot
answer, and the counts cannot tell them apart.

Derive the `grounding` block from the skeptics' verdict files and the PINNED audit worklist they
were drawn from (`coyodex audit <map> --json > audit.json`, captured BEFORE the refutations were
applied). Writes a `{"grounding": {...}}` build fragment, or prints it with --json.

It REFUSES rather than guess:
  - a verdict whose claim is not in the pinned worklist  -> the worklist is the wrong snapshot
  - a worklist claim with no verdict at all              -> the pass did not challenge everything
Both are the "gate did not run" failure wearing a different hat."""


def _verdict_bucket(rows: list[dict]) -> str:
    """One claim's outcome from its votes: strict majority confirmed, else refuted, else unverifiable.

    `unverifiable` is the honest third outcome and it is NOT a rounding bucket: a claim reaches it
    only when a skeptic said so. Folding it into either of the others is what makes the record lie —
    and on a live build it read 0 of 408 because every batch prompt ended by telling the skeptics to
    "default to refuted on doubt", so the third verdict was never reachable in practice."""
    grounded = sum(1 for r in rows if r.get("grounded") is True)
    refuted = sum(1 for r in rows if r.get("grounded") is False)
    unver = sum(1 for r in rows if isinstance(r.get("grounded"), str)
                and str(r.get("grounded")).lower() == "unverifiable")
    if grounded * 2 > len(rows):
        return "confirmed"
    if refuted * 2 > len(rows):
        return "refuted"
    if unver:
        return "unverifiable"
    # A tie with no explicit `unverifiable` vote is not settled by the code either — say so rather
    # than silently crediting one side, which is the whole failure this record exists to prevent.
    return "unverifiable"


def live_claims_digest(claims: "Iterable[str]") -> str:
    """sha256 over the sorted, DE-DUPLICATED claim set — the shipped map's claim surface, as one
    value a later gate can recompute.

    This is the only part of the record that is proof rather than explanation. The count-based
    fields cannot catch a 1-for-1 rewrite (k claims replaced by k others leaves every size
    unchanged), and a reconcile that rewrites a claim IS 1-for-1 by construction — 4 of the 6
    superseded claims on the build this was written for were exactly that shape. De-duplicated
    because `build_record` de-duplicates the pinned side, and two sides counted by different rules
    is how a check ends up measuring the rule instead of the map."""
    import hashlib
    # JSON-encoded, not newline-joined: a separator that can appear inside a claim makes the digest
    # ambiguous, and `["a\nb"]` hashed identically to `["a", "b"]`. No claim carries a newline
    # today, which is exactly why this is worth removing now rather than after one does.
    payload = json.dumps(sorted(set(claims)), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_record(worklist_claims: list[str], grounding_rows: list[dict],
                 note: str = "", live_claims: "list[str] | None" = None,
                 ) -> tuple[dict[str, object], list[str]]:
    """The `grounding` block, plus the refusals that must stop it being written.

    `live_claims` is the worklist of the ASSEMBLED map, when the caller passed `--map`. It is what
    lets the record state how the pinned surface and the shipped one differ, instead of leaving a
    build to argue with a staleness advisory that had no legal answer."""
    votes: dict[str, list[dict]] = {}
    for r in grounding_rows:
        claim = r.get("claim")
        if isinstance(claim, str):
            votes.setdefault(claim, []).append(r)
    # De-duplicate while preserving order: a claim repeated in the worklist must not be counted twice.
    seen_claims: set[str] = set()
    worklist_claims = [c for c in worklist_claims
                       if not (c in seen_claims or seen_claims.add(c))]
    pinned = set(worklist_claims)
    errors: list[str] = []
    bad = sorted({str(r.get("grounded")) for rows in votes.values() for r in rows
                  if not (r.get("grounded") is True or r.get("grounded") is False
                          or (isinstance(r.get("grounded"), str)
                              and str(r.get("grounded")).lower() == "unverifiable"))})
    if bad:
        errors.append(
            f"{len(bad)} unrecognised `grounded` value(s) in the verdict files: {', '.join(bad)} — "
            f"the vocabulary is true / false / \"unverifiable\". Bucketing an unknown value would fold "
            f"it into a verdict nobody gave, which is the failure this record exists to prevent.")
    orphans = sorted(c for c in votes if c not in pinned)
    if orphans:
        errors.append(
            f"{len(orphans)} verdict claim(s) are not in the pinned worklist — the --worklist file is "
            f"a DIFFERENT snapshot from the one the skeptics were given (it was probably re-derived "
            f"after the refutations were applied). Capture `audit --json` BEFORE the fixes. "
            f"First: {orphans[0][:100]}")
    unvoted = [c for c in worklist_claims if c not in votes]
    if unvoted:
        errors.append(
            f"{len(unvoted)} worklist claim(s) have NO verdict — this pass did not challenge the "
            f"whole surface, so `claims_challenged` would overstate it. Ground them, or challenge a "
            f"smaller worklist deliberately. First: {unvoted[0][:100]}")
    counts = {"confirmed": 0, "refuted": 0, "unverifiable": 0}
    for claim in worklist_claims:
        rows = votes.get(claim)
        if rows:
            counts[_verdict_bucket(rows)] += 1
    record: dict[str, object] = {
        "claims_total": len(worklist_claims),
        "claims_challenged": len(worklist_claims) - len(unvoted),
        "claims_confirmed": counts["confirmed"],
        "claims_refuted": counts["refuted"],
        "claims_unverifiable": counts["unverifiable"],
    }
    if live_claims is not None:
        live = set(live_claims)
        # SIZES, and explicitly not a proof: `total - superseded + added_since == live` is a
        # tautology given the two refusals above (they force `votes` == `pinned`), so it closes for
        # every input and can never fail. It is here to tell a reader WHAT moved; the digest is what
        # tells a gate whether anything moved.
        record["claims_superseded"] = len(pinned - live)
        record["claims_added_since"] = len(live - pinned)
        record["live_claims_digest"] = live_claims_digest(live)
    if note:
        record["note"] = note
    return record, errors


def format_report(worklist_claims: list[str], grounding_rows: list[dict],
                  as_json: bool = False, live_claims: list[str] | None = None) -> str:
    """WHICH claims landed in each bucket — the half `write` computes and then throws away.

    `write` resolves every claim to confirmed / refuted / unverifiable and emits only the four
    counts, so a build that needs the actual worklist (every refutation has to be reconciled, and a
    tie has to be adjudicated) has nothing to read. A live build hand-wrote a 12-line vote
    aggregator one turn after `write` had parsed the same 14 files.

    A TIE is called out separately from a stated `unverifiable`. `_verdict_bucket` files both under
    `unverifiable`, which is right for the count but wrong for the reader: a tie is two skeptics
    disagreeing and needs a human decision, while an `unverifiable` verdict is a skeptic saying the
    code cannot answer. A live build's grounding note described its four unverifiables as one kind
    when two were the other."""
    votes: dict[str, list[dict]] = {}
    for r in grounding_rows:
        claim = r.get("claim")
        if isinstance(claim, str):
            votes.setdefault(claim, []).append(r)
    buckets: dict[str, list[dict[str, object]]] = {
        "refuted": [], "unverifiable": [], "tied": [], "unvoted": [], "confirmed": [],
        "superseded": []}
    # SUPERSEDED — pinned claims the reconcile rewrote or removed, so the shipped map no longer
    # carries them. The record states how MANY; until now nothing could say WHICH, and the whole
    # design rests on those being the refuted ones. A superseded claim that was CONFIRMED is the
    # interesting case: it means the build overrode a verdict three skeptics agreed on.
    live = set(live_claims) if live_claims is not None else None
    for claim in worklist_claims:
        rows = votes.get(claim)
        if not rows:
            buckets["unvoted"].append({"claim": claim})
            continue
        bucket = _verdict_bucket(rows)
        grounded = sum(1 for r in rows if r.get("grounded") is True)
        refuted = sum(1 for r in rows if r.get("grounded") is False)
        stated = any(isinstance(r.get("grounded"), str) for r in rows)
        if bucket == "unverifiable" and not stated:
            bucket = "tied"
        if live is not None and claim not in live:
            buckets["superseded"].append({
                "claim": claim, "verdict": bucket, "votes": len(rows),
                "for": grounded, "against": refuted,
                "notes": [str(r.get("note", "")) for r in rows if r.get("note")]})
        buckets[bucket].append({
            "claim": claim, "votes": len(rows), "for": grounded, "against": refuted,
            "evidence": [str(r.get("evidence", "")) for r in rows if r.get("evidence")],
            "skeptics": sorted({str(r.get("skeptic", "")) for r in rows if r.get("skeptic")}),
            "notes": [str(r.get("note", "")) for r in rows if r.get("note")],
        })
    if as_json:
        return json.dumps(buckets, indent=2, ensure_ascii=False)
    out: list[str] = []
    if live is not None:
        sup = buckets["superseded"]
        out.append(f"\nSUPERSEDED ({len(sup)}) — pinned claims the shipped map no longer carries.")
        if not sup:
            out.append("  (none — the pinned worklist and the shipped map hold the same claims)")
        for row in sup:
            mark = "" if row["verdict"] == "refuted" else f"   <- was {str(row['verdict']).upper()}"
            out.append(f"  * {row['claim']}{mark}")
        overridden = [r for r in sup if r["verdict"] != "refuted"]
        if overridden:
            out.append(f"  {len(overridden)} of these were NOT refuted — the build rewrote a claim "
                       f"the skeptics had settled. That is a decision, not a fix; say so in "
                       f"`grounding.note`.")
    for name, label in (("refuted", "REFUTED — reconcile each into the map"),
                        ("tied", "TIED — the skeptics split; adjudicate against the code"),
                        ("unverifiable", "UNVERIFIABLE — a skeptic said the code cannot answer"),
                        ("unvoted", "NO VERDICT — not challenged")):
        if not buckets[name]:
            continue
        out.append(f"\n{label} ({len(buckets[name])}):")
        for row in buckets[name]:
            out.append(f"  * {row['claim']}")
            raw_skeptics = row.get("skeptics")
            skeptics = [str(s) for s in raw_skeptics] if isinstance(raw_skeptics, list) else []
            if row.get("votes"):
                out.append(f"      {row['for']} for / {row['against']} against"
                           + (f"  [{', '.join(skeptics)}]" if skeptics else ""))
            raw_notes = row.get("notes")
            for n in (raw_notes if isinstance(raw_notes, list) else [])[:2]:
                out.append(f"      {str(n)[:160]}")
    out.append(f"\nconfirmed: {len(buckets['confirmed'])} of {len(worklist_claims)} claim(s)")
    return "\n".join(out).lstrip("\n")


def _worklist_claims(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("worklist", payload if isinstance(payload, list) else [])
    return [str(i.get("claim", "")) for i in items if isinstance(i, dict)]


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    verb, rest = argv[0], argv[1:]
    if verb not in ("write", "report"):
        print(f"ERROR: unknown verb '{verb}' (expected `write` or `report`)\n\n{USAGE}",
              file=sys.stderr)
        return 2
    # Same hole `coyodex fix` had: the option loop below rejects `--help` as an unknown option.
    helped = subverb_help.handle(USAGE, verb, rest)
    if helped is not None:
        return helped
    worklist_path = out_path = map_path = None
    verdicts: list[str] = []
    note = ""
    as_json = False
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--json":
            as_json = True
        elif a in ("--worklist", "--verdicts", "--out", "--note", "--map"):
            i += 1
            if i >= len(rest):
                print(f"ERROR: {a} needs a value", file=sys.stderr)
                return 2
            if a == "--worklist":
                worklist_path = rest[i]
            elif a == "--map":
                map_path = rest[i]
            elif a == "--verdicts":
                verdicts.append(rest[i])
            elif a == "--out":
                out_path = rest[i]
            else:
                note = rest[i]
        else:
            print(f"ERROR: unknown option(s): {a}", file=sys.stderr)
            return 2
        i += 1
    if not worklist_path or not verdicts:
        print(f"ERROR: --worklist and at least one --verdicts are required\n\n{USAGE}",
              file=sys.stderr)
        return 2
    claims = _worklist_claims(Path(worklist_path))
    if not claims:
        print(f"ERROR: {worklist_path} holds no worklist claims — pass `coyodex audit <map> --json`",
              file=sys.stderr)
        return 2
    rows, notes = load_verdicts(verdicts)
    for n in notes:
        print(n, file=sys.stderr)
    live_claims = None
    if map_path:
        # The LIVE claim surface, read from the assembled map this record describes. Not a second
        # captured file: a file goes stale between capture and write, and the whole defect here is a
        # record describing a surface that moved.
        try:
            from coyodex.audit_model import l2_worklist_model
            from coyodex.model import load_model
            live_model = load_model(Path(map_path).read_text(encoding="utf-8"))
            live_claims = [w.claim for w in l2_worklist_model(live_model)]
        except Exception as e:
            print(f"ERROR: --map {map_path} could not be read as a map ({e})", file=sys.stderr)
            return 2
    if verb == "report":
        print(format_report(claims, rows, as_json=as_json, live_claims=live_claims))
        return 0
    record, errors = build_record(claims, rows, note, live_claims=live_claims)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print("REFUSED: the record would misstate what was challenged; nothing was written.",
              file=sys.stderr)
        return 1
    payload = {"grounding": record}
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {out_path}: {record['claims_challenged']} of {record['claims_total']} claim(s) "
              f"challenged — {record['claims_confirmed']} confirmed, {record['claims_refuted']} "
              f"refuted, {record['claims_unverifiable']} unverifiable"
              + (f" · vs the live map: {record['claims_superseded']} superseded, "
                 f"{record['claims_added_since']} added since the pin" if live_claims is not None
                 else " · no --map, so the record does not state how the live map differs"))
    elif as_json:
        print(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
