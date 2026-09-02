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
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from coyodex import subverb_help
from coyodex.anchor_drift import load_verdicts
from coyodex.audit_model import ClaimTarget, l2_worklist_model, resolve_claim
from coyodex.model import ModelError, ProjectModel, load_model, resolve_map_path

USAGE = """usage: coyodex grounding lint   --verdicts <raw.json>... [--agent-transcripts <dir>]
       coyodex grounding write  --worklist <audit.json> --verdicts <raw.json>... \\
                               [--out <fragment.json>] [--json] [--partial]
                               [--note <text> | --note-file <path> | --keep-note]
                               [--note-cites-other-runs] [--map <project-map.json>]
coyodex grounding report --worklist <audit.json> --verdicts <raw.json>... [--map <map>] [--json]
       coyodex grounding report --worklist <audit.json> --verdicts <raw.json>... [--json]
       coyodex grounding by-element --worklist <audit.json> --verdicts <raw.json>... \\
                               --map <project-map.json> [--kind <kind>] [--json]

`by-element` says what the pass did to each ELEMENT, beside the confidence its author typed.
Nothing in the tooling ever writes `confidence`, so an element challenged three times and confirmed
unanimously still reads exactly as the harvesting agent left it. This resolves every pinned claim
back onto the element that makes it and prints both, flagging each element whose stated label the
votes do not support. Derived on every run from the worklist and the verdicts; it stores nothing.
`--kind` narrows to one of rule_site / description / edge / cadence / lifecycle / security.

`refutations` is the GATE half, and needs no worklist: it walks the verdicts against the live map
and exits 1 when a claim the skeptics REFUTED is still in it, word for word. Every refutation is
supposed to be reconciled, and a reconciled claim no longer resolves, so a survivor is one nobody
acted on. It also lists the elements whose stated confidence the votes do not support (advisory).

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
  - a --note whose numbers contradict this record        -> the note was written against another run
Both of the first two are the "gate did not run" failure wearing a different hat.

`--note-cites-other-runs` is the escape for the third: it says the figures in the note are about
OTHER runs, or are scoped to one theme rather than the whole pass. The refusal then becomes a
warning. Pass it to `coyodex ship` too, which forwards it — without that, the refusal stops the
prescribed closing sequence at step 6 of 12.

The note: `--note` takes it inline, `--note-file` reads it from a file, `--keep-note` reuses the
note already in `--out`. The last two exist because a re-run (the ordinary case — the record is
re-measured after a late fix) had to re-supply the whole note, and a live build did that through a
nested `$(python -c …)` re-extracting ~1900 characters back through the shell. It survived; a note
containing a quote or a backtick would not have.

--partial: record a DELIBERATE partial pass — the second refusal is lifted, `claims_total` keeps the
FULL pinned surface and `claims_challenged` says how far you got. Needs a --note naming what was
prioritized, and is refused when the pass turns out to be complete after all. Do NOT instead shrink
the --worklist file to what you challenged: that makes `claims_total` the reduced size, so the real
surface survives only in prose and a 319-of-1608 pass ships looking complete."""


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
    #
    # It stays `unverifiable` rather than a bucket of its own, and a 2026-08-29 retro finding that
    # said otherwise was withdrawn after being checked: over the SAME 32 verdict files the record
    # and `grounding report` agree exactly (8 refuted, 0 tied, 0 unverifiable). The finding compared
    # a report over 38 files with a record built from 32. What is true is smaller and is the reason
    # this comment exists: `format_report` prints `tied` where the record says `unverifiable`, so
    # the two vocabularies differ for one claim shape. Splitting them would hide an unresolved tie
    # from every reader who checks `claims_unverifiable`, which is worse than the mismatch.
    return "unverifiable"


def multi_vote_agreement(rows: list[dict]) -> tuple[int, int, int]:
    """`(multi-voted claims, verdict disagreements, evidence-anchor disagreements)`.

    A claim voted by more than one skeptic is the only place unanimity is a MEANINGFUL word, and it
    is the word notes reach for: "the three security voters agreed on every anchor". Nothing
    computed it, so the sentence was written from impression. On the 2026-09-01 argus map the note
    said ZERO anchor disagreements and 2 of 80 triple-voted claims disagree.

    Two different disagreements, deliberately counted apart:

    * **verdict** — the voters did not return the same `grounded` value. The record's buckets fold
      these into a majority and the disagreement disappears.
    * **evidence anchor** — the voters agreed on the verdict but cited DIFFERENT `path:line`s.
      Harmless on its face and the reason to count it: it is the one signal that two readers who
      agree were not looking at the same thing.

    Rows carrying no `evidence` are skipped for the anchor test rather than counted as agreeing —
    an absent citation is not a matching one."""
    votes: dict[str, list[dict]] = {}
    for r in rows:
        claim = r.get("claim")
        if isinstance(claim, str):
            votes.setdefault(claim, []).append(r)
    multi = 0
    verdict_disagree = 0
    anchor_disagree = 0
    for claim_rows in votes.values():
        voters = {str(r.get("skeptic", "")) for r in claim_rows if r.get("skeptic")}
        # `or`, not `and`. Voters are read OFF the rows, so `len(rows) < 2` already implies
        # `len(voters) < 2` and the `and` form reduced to "fewer than two rows" — counting a
        # single skeptic's RE-VOTE of one claim, and a pair of rows carrying no `skeptic` field at
        # all, as multi-voted. Both then produced anchor "disagreements" between one reader and
        # itself. Unanimity is a fact about two or more READERS; two rows is not the same thing.
        if len(claim_rows) < 2 or len(voters) < 2:
            continue
        multi += 1
        grounded = {str(r.get("grounded")).lower() for r in claim_rows}
        if len(grounded) > 1:
            verdict_disagree += 1
        anchors = {str(r.get("evidence", "")).strip() for r in claim_rows
                   if str(r.get("evidence", "")).strip()}
        if len(anchors) > 1:
            anchor_disagree += 1
    return multi, verdict_disagree, anchor_disagree


def note_facts_block(worklist_claims: list[str], rows: list[dict], record: dict[str, object],
                     live_claims: "list[str] | None") -> str:
    """THE NUMBERS A NOTE WILL CITE, COMPUTED, so nobody retypes one from an earlier view.

    `--note` is free prose in a permanent record and in the commit message, and nothing checked it.
    One shipped note said "Eighteen fresh-context skeptics" about a build that dispatched 17 and
    produced 20 verdict labels: the 18 was read off a `grounding lint` line printed while one
    verdict file was still being written, then carried forward. The same note said "Four superseded
    claims had been CONFIRMED" where the report counts 11, leaving seven deliberate overrides of
    settled claims undisclosed. Every number was available at the moment the note was written.

    A FUNCTION rather than an inline print, because `_note_contradictions` now REFUSES rather than
    warns: the operator whose note is rejected needs these numbers in the same breath, and they
    used to be printed only on the success path, after the refusal had already returned."""
    buckets = json.loads(format_report(worklist_claims, rows, as_json=True, live_claims=live_claims))
    sup_confirmed = sum(1 for r in buckets["superseded"] if r.get("verdict") == "confirmed")
    labels = sorted({str(r.get("skeptic", "")) for r in rows if r.get("skeptic")})
    # REDUNDANT ROWS, spelled out, because the note has to state it and the arithmetic is the kind
    # nobody re-does. A three-voted theme produces three rows per claim; "136 redundant rows" was
    # published in a shipped map and in the operator report for a pass whose four security batches
    # held 136 CLAIMS and 408 rows — 272 redundant. The note's author had the row count here and the
    # claim count nowhere, so it quoted the number it could see.
    # Both sides count the SAME rows: a row with no claim is excluded from each, or it would inflate
    # `redundant` by one while belonging to neither side of the subtraction.
    claimed_rows = [r for r in rows if r.get("claim")]
    voted = len({str(r.get("claim")) for r in claimed_rows})
    redundant = max(0, len(claimed_rows) - voted)
    # The multi-vote agreement, for the same reason the redundant count is here: notes assert
    # unanimity ("the three security voters agreed on every anchor") and nothing computed it, so the
    # sentence came from impression and was wrong on a shipped map.
    multi, verdict_dis, anchor_dis = multi_vote_agreement(rows)
    return (f"  NOTE FACTS — quote these, do not retype them from an earlier run:\n"
            f"    verdict rows {len(rows)} over {voted} distinct claim(s) — "
            f"{redundant} row(s) that added no new claim (usually a re-vote)\n"
            f"    distinct skeptic labels {len(labels)} "
            f"(a label is not an agent: one agent may carry several batches)\n"
            f"    confirmed {record['claims_confirmed']} · refuted {record['claims_refuted']} · "
            f"unverifiable {record['claims_unverifiable']} · tied {len(buckets['tied'])}\n"
            f"    multi-voted claims {multi} · verdict disagreements {verdict_dis} · "
            f"evidence-anchor disagreements {anchor_dis} "
            f"(unanimity is only a fact about the multi-voted ones)"
            + (f"\n    superseded {record['claims_superseded']}, of which {sup_confirmed} "
               f"had been CONFIRMED — each is a settled verdict the build overrode, and a note "
               f"that does not say so hides it" if live_claims is not None else ""))


_REDUNDANT_IN_NOTE = re.compile(r"(\d[\d,]*)\s+redundant\s+rows?", re.I)

#: The note stating how many claims arrived AFTER the worklist was pinned. Third arithmetic shape,
#: same failure as the other two: the 2026-09-02 mcpolis note said "9 post-pin claims" where its own
#: record — and its own NEXT SENTENCE — said 13. Words and digits both, since notes write either.
_ADDED_SINCE_IN_NOTE = re.compile(
    r"\b(\d[\d,]*|no|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen)"
    r"\s+(?:new\s+|post-pin\s+|added\s+)claims?\b", re.I)

#: The words `_ADDED_SINCE_IN_NOTE` accepts, to their value.
_WORD_NUMBERS = {"no": 0, "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
                 "twelve": 12, "thirteen": 13}

#: A note stating a disagreement COUNT: "0 verdict disagreements", "zero evidence-anchor
#: disagreements", "anchor disagreements: 2".
_AGREEMENT_IN_NOTE = re.compile(
    r"\b(?:(\d[\d,]*|no|zero)\s+(verdict|evidence[- ]anchor|anchor)\s+disagreements?"
    r"|(verdict|evidence[- ]anchor|anchor)\s+disagreements?\s*[:=]\s*(\d[\d,]*))", re.I)

#: A note ASSERTING unanimity in words rather than a number — which is how the defect actually
#: shipped: "the three security voters agreed on every anchor". A count regex could not see it, and
#: a build that phrases its assurance this way is making exactly the claim that was wrong.
#: Read as "0 disagreements of BOTH kinds", which is what the sentence means.
_UNANIMITY_IN_NOTE = re.compile(
    r"\b(?:agreed\s+on\s+every\s+anchor"
    r"|unanimous(?:ly)?(?:\s+\w+){0,3}\s+(?:anchor|evidence|verdict)"
    r"|(?:cited|read)\s+the\s+same\s+(?:anchor|evidence|line)"
    r"|(?:every|all)\s+(?:multi|triple|double)-voted\s+claims?\s+agreed)", re.I)
_COVERAGE_IN_NOTE = re.compile(r"(\d[\d,]*)\s+of\s+(?:those\s+|the\s+)?(\d[\d,]*)\s+"
                               r"(?:carry|have)\s+no\s+verdict", re.I)


def _note_contradictions(note: str, rows: list[dict], record: dict[str, object],
                         live_claims: "list[str] | None") -> list[str]:
    """Numbers the note states that its OWN record contradicts.

    `--note` is free prose in a permanent record and in the commit message, and nothing checked it.
    Two shapes recur and both shipped on the 2026-08-29 mcpolis map:

    * **the redundant-row count.** "483 verdict rows over 161 redundant rows" — 161 is the CLAIM
      count; 483 - 161 = 322 rows were redundant. The identical error ("136 redundant rows" for 272)
      was found by the previous retrospective, marked fixed, and recurred, because the fix printed
      the number in `NOTE FACTS` without refusing a note that disagrees with it.
    * **the shipped-map coverage pair.** The note said "16 of those 696 carry no verdict" while its
      own record said 22 of 702 — it had been written against an earlier pass and re-pasted.

    Only these two shapes, and only when the note states them: a general prose checker is not
    possible and a guessy one would refuse honest notes. Both fixes are one word."""
    problems: list[str] = []
    claimed_rows = [r for r in rows if r.get("claim")]
    redundant = max(0, len(claimed_rows) - len({str(r.get("claim")) for r in claimed_rows}))
    # ANY occurrence may match, and one that does clears the note. A good note cites other builds'
    # figures for comparison — the real one said "over 160, 40 and 100 redundant rows" about three
    # earlier passes — and refusing those would refuse the most honest notes written.
    stated_redundant = [int(m.group(1).replace(",", "")) for m in _REDUNDANT_IN_NOTE.finditer(note or "")]
    if stated_redundant and redundant not in stated_redundant:
        quoted = ", ".join(f"'{n} redundant rows'" for n in stated_redundant)
        problems.append(
            f"the note states {quoted} and this pass has {redundant} — none of them. A three-voted "
            f"theme produces one row per voter, so the redundant count is rows minus DISTINCT "
            f"claims ({len(claimed_rows)} - {len(claimed_rows) - redundant}). Quote the "
            f"`NOTE FACTS` line rather than the claim count; other builds' figures are fine "
            f"alongside this pass's.")
    live_done = record.get("claims_live_challenged")
    if live_claims is not None and isinstance(live_done, int):
        live_total = len(set(live_claims))
        pairs = [(int(m.group(1).replace(",", "")), int(m.group(2).replace(",", "")), m.group(0))
                 for m in _COVERAGE_IN_NOTE.finditer(note or "")]
        if pairs and (live_total - live_done, live_total) not in [(a, b) for a, b, _ in pairs]:
            quoted = ", ".join(f"'{t}'" for _a, _b, t in pairs)
            problems.append(
                f"the note states {quoted} and this record says {live_total - live_done} of "
                f"{live_total} — none of them. The note was written against an earlier pass; "
                f"requote it from this run.")
    # THE POST-PIN COUNT, the third arithmetic shape. `claims_added_since` is the claims the map
    # gained after the skeptics were given their worklist, so it is exactly the number a reader
    # needs to know how much of the shipped map went unchallenged — and a note that understates it
    # understates that. Blocking with the other two: it is a stated number about THIS pass, and the
    # record beside it holds the right one.
    added = record.get("claims_added_since")
    if isinstance(added, int):
        stated_added = [
            (_WORD_NUMBERS.get(m.group(1).lower(), None)
             if not m.group(1)[:1].isdigit() else int(m.group(1).replace(",", "")), m.group(0))
            for m in _ADDED_SINCE_IN_NOTE.finditer(note or "")]
        values = [v for v, _t in stated_added if v is not None]
        if values and added not in values:
            quoted = ", ".join(f"'{t}'" for _v, t in stated_added)
            problems.append(
                f"the note states {quoted} and this record says {added} claim(s) added since the "
                f"pin. Those are the claims no skeptic saw, so understating them understates how "
                f"much of the shipped map went unchallenged; requote it from this run.")
    return problems


def _agreement_contradictions(note: str, rows: list[dict]) -> list[str]:
    """The multi-vote agreement the note asserts, against what this pass actually did.

    ADVISORY, deliberately, where the two shapes above are blocking. The difference is what a regex
    can know. "483 verdict rows over 161 redundant rows" is arithmetic: the number is stated, it is
    about this pass, and it is wrong. An agreement claim is an ASSURANCE, and it shipped in words —
    "the three security voters agreed on every anchor" — on a map where 2 of 80 triple-voted claims
    disagree. Reading that reliably is a language problem, not a pattern problem: the count form
    misses every word form, the word form guesses at scope, and both fire on an honest sentence
    about an earlier run or one theme. Blocking on a guess would refuse correct notes, which is a
    worse failure than the one being caught — the `NOTE FACTS` line already prints the true triple
    right beside the author.

    So this WARNS, loudly, with the real numbers. What is blocking is the arithmetic."""
    multi, verdict_dis, anchor_dis = multi_vote_agreement(rows)
    text = note or ""
    stated: dict[str, list[tuple[int, str]]] = {"verdict": [], "anchor": []}
    for m in _AGREEMENT_IN_NOTE.finditer(text):
        raw = (m.group(1) or m.group(4) or "").lower()
        which_raw = (m.group(2) or m.group(3) or "").lower()
        value = 0 if raw in ("no", "zero") else int(raw.replace(",", ""))
        which = "verdict" if which_raw == "verdict" else "anchor"
        stated[which].append((value, m.group(0)))
    # A worded assurance means zero of BOTH kinds, which is what the sentence claims.
    for m in _UNANIMITY_IN_NOTE.finditer(text):
        stated["verdict"].append((0, m.group(0)))
        stated["anchor"].append((0, m.group(0)))
    out: list[str] = []
    for which, actual in (("verdict", verdict_dis), ("anchor", anchor_dis)):
        claimed = stated[which]
        # ANY occurrence clears it, exactly as the redundant-row check allows: a note that compares
        # this pass with an earlier one legitimately states both numbers.
        if claimed and actual not in [v for v, _t in claimed]:
            quoted = ", ".join(f"'{t}'" for _v, t in dict.fromkeys(claimed))
            label = "verdict" if which == "verdict" else "evidence-anchor"
            out.append(
                f"the note states {quoted} and this pass has {actual} {label} disagreement(s). "
                f"Over {multi} multi-voted claim(s): {verdict_dis} where the voters returned "
                f"different verdicts, {anchor_dis} where they agreed but cited different anchors. "
                f"If the note is about another run or one theme, it is fine as it stands; if it is "
                f"about THIS pass, quote the `NOTE FACTS` line.")
    return out


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
                 partial: bool = False,
                 ) -> tuple[dict[str, object], list[str]]:
    """The `grounding` block, plus the refusals that must stop it being written.

    `live_claims` is the worklist of the ASSEMBLED map, when the caller passed `--map`. It is what
    lets the record state how the pinned surface and the shipped one differ, instead of leaving a
    build to argue with a staleness advisory that had no legal answer.

    `partial` is the operator asserting that challenging only part of the worklist was DELIBERATE.
    The counts never needed it — `claims_challenged` has always subtracted the unvoted — so what it
    buys is the distinction the tool cannot make on its own: a ranked worklist worked top-down until
    the budget ran out looks exactly like a batch of skeptics that died on the way home."""
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
    # An unvoted claim has TWO causes that look identical from here: a pass that deliberately
    # challenged the top slice of a ranked worklist, and a pass whose skeptics silently died or that
    # was handed the wrong snapshot. The second is the failure this whole record exists to catch, so
    # the refusal stands by default and `partial` is the operator saying which one it is.
    #
    # It is NOT an accuracy problem: `claims_challenged` below already subtracts the unvoted, so the
    # counts were always right for a partial pass — the refusal guarded intent, not arithmetic. The
    # documented workaround (cut the pinned worklist down to what you challenged) is strictly worse:
    # it makes `claims_total` the reduced size, so the real surface survives only in free-text prose
    # where no gate can read it, and a 319-of-1608 pass ships looking like a complete pass over a
    # small map.
    unvoted = [c for c in worklist_claims if c not in votes]
    if unvoted and not partial:
        errors.append(
            f"{len(unvoted)} worklist claim(s) have NO verdict — this pass did not challenge the "
            f"whole surface. Ground them, or pass `--partial` to record a DELIBERATE partial pass "
            f"(`claims_total` then keeps the full surface and `claims_challenged` states how far you "
            f"got; a `--note` saying what was prioritized is required). First: {unvoted[0][:100]}")
    if partial and not unvoted:
        errors.append(
            "`--partial` was passed but every worklist claim has a verdict — this was a COMPLETE "
            "pass. Drop the flag: a record that calls itself partial when it is not understates a "
            "finished verification, and the next reader cannot tell which it was.")
    if partial and not note.strip():
        errors.append(
            "`--partial` needs a `--note` saying which claims were prioritized and out of what — "
            "the counts alone say how many were challenged, never why those ones, and an unexplained "
            "partial pass is indistinguishable from an abandoned one.")
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
        # SIZES, and explicitly not a proof: `total - superseded + added_since == live` closes for
        # every COMPLETE pass, because the orphan and unvoted refusals force `votes` == `pinned`
        # there. Under `--partial` the unvoted refusal is lifted, so the identity stops being a
        # tautology and starts measuring something. Either way it tells a reader WHAT moved; the
        # digest is what tells a gate whether anything moved.
        record["claims_superseded"] = len(pinned - live)
        record["claims_added_since"] = len(live - pinned)
        # COVERAGE OF THE SHIPPED MAP, which none of the counts above states. Every one of them is
        # pinned to the worklist the skeptics were given, so a build that rewords a claim after the
        # vote keeps `claims_challenged == claims_total` while the map it ships carries claims
        # nobody challenged. One did: 209 of 209 in the record, in the rendered view and in the
        # commit message, against 199 live claims with a verdict. Measured against `votes`, not
        # derived, because the derivation `total - superseded` only holds when every pinned claim
        # was voted — which `--partial` exists to allow it not to be.
        record["claims_live_challenged"] = sum(1 for c in live if c in votes)
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
    # De-duplicated exactly as `build_record` does (and for the same reason). Without it this
    # report listed a repeated claim twice and counted it twice, so it disagreed with the record it
    # exists to explain — first by listing FEWER than the record counted, then, once that was fixed,
    # by listing MORE.
    _seen: set[str] = set()
    worklist_claims = [c for c in worklist_claims
                       if not (c in _seen or _seen.add(c))]
    buckets: dict[str, list[dict[str, object]]] = {
        "refuted": [], "unverifiable": [], "tied": [], "unvoted": [], "confirmed": [],
        "superseded": [], "refuted_not_superseded": []}
    # SUPERSEDED — pinned claims the reconcile rewrote or removed, so the shipped map no longer
    # carries them. The record states how MANY; until now nothing could say WHICH, and the whole
    # design rests on those being the refuted ones. A superseded claim that was CONFIRMED is the
    # interesting case: it means the build overrode a verdict three skeptics agreed on.
    live = set(live_claims) if live_claims is not None else None
    for claim in worklist_claims:
        rows = votes.get(claim)
        if not rows:
            buckets["unvoted"].append({"claim": claim})
            if live is not None and claim not in live:
                # BEFORE the continue: an unvoted claim can be superseded too, and skipping it made
                # the report list FEWER than `write --map` counted — silently, in the very tool the
                # record points a reader at to see WHICH.
                buckets["superseded"].append({"claim": claim, "verdict": "unvoted", "votes": 0,
                                              "for": 0, "against": 0, "notes": []})
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
        row = {
            "claim": claim, "votes": len(rows), "for": grounded, "against": refuted,
            "evidence": [str(r.get("evidence", "")) for r in rows if r.get("evidence")],
            "skeptics": sorted({str(r.get("skeptic", "")) for r in rows if r.get("skeptic")}),
            "notes": [str(r.get("note", "")) for r in rows if r.get("note")],
        }
        buckets[bucket].append(row)
        # A refutation whose claim TEXT did not change is invisible to `claims_superseded` and to
        # the digest. Bucketed here rather than derived in the text renderer, so `--json` — which
        # this codebase tells readers to prefer over parsing the lines — carries it too.
        if live is not None and bucket == "refuted" and claim in live:
            buckets["refuted_not_superseded"].append(row)
    if as_json:
        return json.dumps(buckets, indent=2, ensure_ascii=False)
    out: list[str] = []
    # A SUMMARY LINE FIRST, AND THE CRITICAL COUNT AGAIN LAST. This report is read through a pipe,
    # and two opposite narrowings hid two ends of one section on the same build: `| tail -40`
    # started inside the refuted list and cut the `REFUTED BUT NOT SUPERSEDED` header off the top,
    # then `| head -30` ended after the third of its five bullets. The lead fixed the three it
    # could see, said so, and two refuted claims shipped in the map. Neither narrowing was wrong to
    # attempt: the report runs hundreds of lines. So the number a reader must not miss is stated at
    # BOTH ends, which is the same rule `lint-fragment` already follows for its verdict.
    still_live_n = len(buckets["refuted_not_superseded"])
    out.append(
        f"GROUNDING REPORT — {len(buckets['refuted'])} refuted, {len(buckets['tied'])} tied, "
        f"{len(buckets['unverifiable'])} unverifiable, {len(buckets['unvoted'])} unvoted"
        + (f", {len(buckets['superseded'])} superseded" if live is not None else "")
        + (f" · {still_live_n} REFUTED CLAIM(S) STILL IN THE MAP" if still_live_n else ""))
    if live is not None:
        sup = buckets["superseded"]
        out.append(f"\nSUPERSEDED ({len(sup)}) — pinned claims the shipped map no longer carries.")
        if not sup:
            out.append("  (none — the pinned worklist and the shipped map hold the same claims)")
        for row in sup:
            split = (f" [{row['for']} for / {row['against']} against]"
                     if row.get("votes") else "")
            mark = "" if row["verdict"] == "refuted" else f"   <- was {str(row['verdict']).upper()}"
            out.append(f"  * {row['claim']}{mark}{split}")
        # Only a CONFIRMED verdict was settled. A tie is by definition unsettled — this report's
        # own next section calls it "the skeptics split; adjudicate against the code" — and an
        # unverifiable verdict says the code could not answer. Calling all three "settled"
        # over-claimed on two of them.
        overridden = [r for r in sup if r["verdict"] == "confirmed"]
        unsettled = [r for r in sup if r["verdict"] in ("tied", "unverifiable", "unvoted")]
        if overridden:
            n = len(overridden)
            out.append(f"  {n} of these {'was' if n == 1 else 'were'} CONFIRMED — the build rewrote "
                       f"a claim the skeptics had settled. That is a decision, not a fix; say so in "
                       f"`grounding.note`.")
        if unsettled:
            n = len(unsettled)
            out.append(f"  {n} {'was' if n == 1 else 'were'} never settled (tied / unverifiable / "
                       f"unvoted) — removing the claim ended the question rather than answering it.")
        # The OTHER direction, and the one no number watches. `claims_superseded` counts pinned
        # claims the shipped map no longer carries, and the design reads that as "the refutations
        # landed". But a refutation can be reconciled WITHOUT changing the claim's rendered text: on
        # a live build, `E35 (UpstreamState) has states […] with 10 transition(s)` was refuted, the
        # wrong transition was corrected in the map, and the claim string — which names a COUNT, not
        # the transitions — came out identical. So 5 refutations produced 4 superseded, and the
        # digest cannot witness that fifth fix at all: a build that "corrected" it by doing nothing
        # would produce the same digest. Name them, so the reader checks the map instead of the count.
        still_live = buckets["refuted_not_superseded"]
        if still_live:
            # Its OWN section. Nested under `SUPERSEDED (N)` it made the heading's count disagree
            # with the bullets below it, and on a map where nothing was superseded it printed
            # "(none — the pinned worklist and the shipped map hold the same claims)" immediately
            # above a list of claims — two lines that contradict each other, told apart only by
            # indentation.
            n = len(still_live)
            out.append(f"\nREFUTED BUT NOT SUPERSEDED ({n}) — the map still carries "
                       f"{'this claim' if n == 1 else 'these claims'} verbatim, so neither "
                       f"`claims_superseded` nor the digest can witness the fix. Either the "
                       f"reconcile changed something the claim text does not name (check the map by "
                       f"hand), or it has not been applied:")
            for row in still_live:
                out.append(f"  * {row['claim']}")
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
    # ADDED SINCE THE PIN — the claims the SHIPPED map carries that the pinned worklist never
    # held. `write` prints how MANY ("37 added since the pin") and nothing could say WHICH, so a
    # build hand-diffed `audit --json` against the worklist in python, then hand-edited the pinned
    # file itself to extend it — against the rule that the pin is not re-derived. Listing them
    # here is the read half of that job, and it is the half that needed no hand script.
    if live is not None:
        pinned = set(worklist_claims)
        added = [c for c in dict.fromkeys(live_claims or []) if c not in pinned]
        if added:
            out.append(f"\nADDED SINCE THE PIN ({len(added)}) — in the shipped map, never in the "
                       f"pinned worklist, so no skeptic saw them. Challenge them, or say in the "
                       f"note why they were not re-challenged; `claims_challenged` counts the pin "
                       f"and will keep reading as full coverage either way:")
            for c in added:
                out.append(f"  * {c}")
    out.append(f"\nconfirmed: {len(buckets['confirmed'])} of {len(worklist_claims)} claim(s)")
    # The trailer half of the both-ends rule above: a `| tail -N` reader gets this even when the
    # section itself scrolled off the top. Only printed when it is non-zero, so a clean run does
    # not end on a scary-looking line.
    if still_live_n:
        out.append(f"\nSTILL IN THE MAP: {still_live_n} refuted claim(s) the map carries verbatim "
                   f"— see REFUTED BUT NOT SUPERSEDED above, and fix the map before shipping it: "
                   + ", ".join(str(r["claim"])[:60] for r in buckets["refuted_not_superseded"][:5])
                   + (" …" if still_live_n > 5 else ""))
    return "\n".join(out).lstrip("\n")


# ── per-element checks: what the grounding pass actually did to each element ──────────────────────


@dataclass(frozen=True)
class ElementCheck:
    """One element of the map, beside what the skeptics did to the claims it makes.

    Some kinds carry an AUTHORED `confidence` — `verified` or `inferred` — written once by the agent
    that harvested the element. NOTHING in the tooling ever writes that field. So a pass that
    challenged an element three times with three different lenses and confirmed it unanimously
    leaves the label exactly as the author typed it, and a reader cannot tell a claim three skeptics
    proved from one nobody looked at. On a live map every business rule read `inferred` after each
    of its sites had been confirmed; on another, every rule read `verified` because the author said
    so and no reader could see which of them a skeptic had actually opened.

    This row is the missing half: `stated` is what the author claimed, the four counts are what the
    pass did. DERIVED, never stored — recomputed from the pinned worklist and the committed verdict
    files whenever it is asked for, so it cannot drift from them and no agent can author it."""
    element_id: str
    kind: str
    label: str
    stated: str = ""
    confirmed: int = 0
    refuted: int = 0
    unverifiable: int = 0
    unvoted: int = 0

    @property
    def claims(self) -> int:
        return self.confirmed + self.refuted + self.unverifiable + self.unvoted

    @property
    def status(self) -> str:
        """One word for the whole element. A single refutation OUTRANKS any number of confirmations:
        the element makes several claims, one of them is wrong, and that is the fact a reader has to
        see first. `part-checked` is kept apart from `confirmed` for the same reason the record keeps
        a tie apart from an `unverifiable` — "some of it was checked" is not "it was checked"."""
        if self.refuted:
            return "refuted"
        if self.unverifiable:
            return "unverifiable"
        if not self.confirmed:
            return "unchecked"
        return "part-checked" if self.unvoted else "confirmed"

    @property
    def disagrees(self) -> bool:
        """The pair a reader is here for: an authored label the pass does not support.

        `verified` on an element no skeptic confirmed, or `inferred` on one they all did. Both are
        the same defect — the label and the evidence were written by different processes and nothing
        ever compared them."""
        if self.stated == "verified":
            return self.status != "confirmed"
        if self.stated == "inferred":
            return self.status == "confirmed"
        return False


def _stated_confidence(m: ProjectModel, t: ClaimTarget) -> str:
    """The element's AUTHORED confidence, or "" for a kind that carries none.

    An edge and a cadenced entry point have no `confidence` field at all, so "" here means "the map
    never asked the author", which is different from an author who left it blank — but the two are
    indistinguishable in the stored map, so the report says `-` for both rather than inventing a
    distinction the data does not hold."""
    seq: object
    if t.kind == "rule_site":
        seq = m.rules
    elif t.kind == "description":
        seq = m.components
    elif t.kind == "lifecycle":
        seq = m.entities if t.sub == 0 else m.components
    elif t.kind == "security":
        seq = m.security
    else:
        return ""
    el = seq[t.idx]  # type: ignore[index]
    return str(getattr(el, "confidence", "") or "")


def _checkable_elements(m: ProjectModel) -> "list[tuple[tuple[str, int, int], ClaimTarget]]":
    """Every element the L2 worklist COULD have made a claim about, whether or not it did.

    Seeded into the tally with zero votes so an element nobody challenged appears as `unchecked`
    instead of being absent. Absence is the false negative this whole report exists to remove: a
    rule missing from the table reads exactly like a rule that passed, and on a live map two rules
    the author had labelled `verified` carried no pinned claim at all — neither would have appeared.

    The kinds and their conditions mirror `l2_worklist_model` exactly; an element the worklist would
    skip (a rule with no anchored site, an entity with no store) is not listed as unchecked here,
    because nothing was ever going to check it and saying otherwise would invent a gap."""
    out: "list[tuple[tuple[str, int, int], ClaimTarget]]" = []
    for i, e in enumerate(m.edges):
        out.append((("edge", i, -1), ClaimTarget("edge", i, -1, "", f"{e.src} {e.verb} {e.dst}")))
    for i, sec in enumerate(m.security):
        out.append((("security", i, -1), ClaimTarget("security", i, -1, "", sec.surface)))
    for i, br in enumerate(m.rules):
        if any((st.where or "").strip() for st in br.sites):
            out.append((("rule_site", i, -1),
                        ClaimTarget("rule_site", i, 0, br.id, br.name or br.statement)))
    for i, ep in enumerate(m.entry_points):
        if (ep.cadence or "").strip():
            out.append((("cadence", i, -1),
                        ClaimTarget("cadence", i, -1, getattr(ep, "id", "") or "",
                                    f"[{ep.kind}] {ep.trigger}")))
    for which, seq in ((0, m.entities), (1, m.components)):
        for i, el in enumerate(seq):
            sm = getattr(el, "states", None)
            if sm is not None and sm.states and (sm.source or "").strip():
                out.append((("lifecycle", i, which),
                            ClaimTarget("lifecycle", i, which, el.id, el.name)))
    for i, en in enumerate(m.entities):
        st = en.store
        if st is not None and st.dep:
            out.append((("store", i, -1), ClaimTarget("store", i, -1, en.id, en.name)))
    for i, mr in enumerate(m.messaging):
        out.append((("messaging", i, -1), ClaimTarget("messaging", i, -1, "", mr.name)))
    for i, c in enumerate(m.components):
        if (c.purpose or "").strip():
            out.append((("description", i, -1), ClaimTarget("description", i, -1, c.id, c.name)))
    return out


def element_checks(m: ProjectModel, worklist_claims: list[str],
                   grounding_rows: list[dict]) -> tuple[list[ElementCheck], list[str]]:
    """Fold the pinned worklist and the skeptics' votes onto the elements they judged.

    Returns the rows plus the claims that named no single element — an unresolved claim is REPORTED,
    never dropped, because a growing unresolved list is how a reader learns the worklist and the map
    have drifted apart (the pinned worklist is a snapshot, and a claim rewritten since resolves to
    nothing).

    The worklist is de-duplicated exactly as `build_record` and `format_report` do, and for the same
    reason: a repeated claim counted twice would make this report disagree with the record it exists
    to explain."""
    votes: dict[str, list[dict]] = {}
    for r in grounding_rows:
        claim = r.get("claim")
        if isinstance(claim, str):
            votes.setdefault(claim, []).append(r)
    seen_claims: set[str] = set()
    claims = [c for c in worklist_claims if not (c in seen_claims or seen_claims.add(c))]
    tally: dict[tuple[str, int, int], dict[str, int]] = {}
    naming: dict[tuple[str, int, int], ClaimTarget] = {}
    for key, target in _checkable_elements(m):
        naming[key] = target
        tally[key] = {"confirmed": 0, "refuted": 0, "unverifiable": 0, "unvoted": 0}
    unresolved: list[str] = []
    for claim in claims:
        target = resolve_claim(m, claim).target
        if target is None:
            unresolved.append(claim)
            continue
        # ONE ROW PER ELEMENT, not per claim site. A rule with three sites makes three claims and
        # is still one rule; keying on the site index printed the same rule three times and a reader
        # counting rows would have over-counted the map. `lifecycle` keeps its `sub` because there it
        # selects WHICH list the index is into (entities vs components), not a part of one element.
        key = (target.kind, target.idx, target.sub if target.kind == "lifecycle" else -1)
        naming.setdefault(key, target)
        counts = tally.setdefault(key, {"confirmed": 0, "refuted": 0,
                                        "unverifiable": 0, "unvoted": 0})
        rows = votes.get(claim)
        counts["unvoted" if not rows else _verdict_bucket(rows)] += 1
    out = [ElementCheck(element_id=naming[k].element_id, kind=naming[k].kind,
                        label=naming[k].label, stated=_stated_confidence(m, naming[k]),
                        confirmed=c["confirmed"], refuted=c["refuted"],
                        unverifiable=c["unverifiable"], unvoted=c["unvoted"])
           for k, c in tally.items()]
    # Worst first — a refuted element is the one a reader must act on, and an element whose stated
    # label the pass does not support is the next. Then by kind and id, so a re-run reads the same.
    order = {"refuted": 0, "unverifiable": 1, "unchecked": 2, "part-checked": 3, "confirmed": 4}
    out.sort(key=lambda r: (order[r.status], not r.disagrees, r.kind, r.element_id, r.label))
    return out, unresolved


def format_element_checks(rows: list[ElementCheck], unresolved: list[str],
                          as_json: bool = False, only_kind: str = "") -> str:
    """The report: every element the pass touched, its authored label, and what the votes said."""
    if only_kind:
        rows = [r for r in rows if r.kind == only_kind]
    if as_json:
        return json.dumps({
            "elements": [{"id": r.element_id, "kind": r.kind, "label": r.label,
                          "stated": r.stated, "status": r.status, "disagrees": r.disagrees,
                          "claims": r.claims, "confirmed": r.confirmed, "refuted": r.refuted,
                          "unverifiable": r.unverifiable, "unvoted": r.unvoted} for r in rows],
            "unresolved_claims": unresolved,
        }, indent=2, ensure_ascii=False)
    lines: list[str] = []
    disagreeing = [r for r in rows if r.disagrees]
    # "checkable", not "carry a pinned claim": the table now seeds every element the worklist COULD
    # have claimed, so the count includes the ones it never did — which is the point.
    lines.append(f"{len(rows)} checkable element(s) · "
                 f"{sum(1 for r in rows if r.status == 'confirmed')} confirmed, "
                 f"{sum(1 for r in rows if r.status == 'part-checked')} part-checked, "
                 f"{sum(1 for r in rows if r.status == 'refuted')} refuted, "
                 f"{sum(1 for r in rows if r.status == 'unverifiable')} unverifiable, "
                 f"{sum(1 for r in rows if r.status == 'unchecked')} unchecked")
    if disagreeing:
        lines.append(f"{len(disagreeing)} element(s) state a confidence the pass does not support "
                     f"— the authored label and the votes were written by different processes and "
                     f"nothing ever compared them:")
    lines.append("")
    lines.append(f"{'id':<7} {'kind':<12} {'stated':<9} {'checked':<13} {'votes':<24} label")
    for r in rows:
        votes = (f"{r.confirmed}✓ {r.refuted}✗ {r.unverifiable}? {r.unvoted}– "
                 f"of {r.claims}")
        flag = "  <- disagrees" if r.disagrees else ""
        lines.append(f"{r.element_id or '-':<7} {r.kind:<12} {r.stated or '-':<9} "
                     f"{r.status:<13} {votes:<24} {r.label[:46]}{flag}")
    if unresolved:
        lines.append("")
        lines.append(f"{len(unresolved)} pinned claim(s) name no single element in this map — the "
                     f"claim was rewritten after the worklist was pinned, or two elements make it:")
        for c in unresolved[:20]:
            lines.append(f"  - {c[:110]}")
        if len(unresolved) > 20:
            lines.append(f"  ... and {len(unresolved) - 20} more")
    return "\n".join(lines)


@dataclass(frozen=True)
class SurvivingRefutation:
    """A claim the skeptics REFUTED that the shipped map still makes, word for word.

    The build contract is that every refutation is reconciled: the claim is corrected, or the row is
    dropped. Either way the wording changes, so the pinned claim no longer resolves against the live
    map — that is what `claims_superseded` counts. A refuted claim that still resolves to a live
    element is therefore one nobody acted on, and no gate could see it: `validate` checks shape,
    `audit` checks the map against itself, and the `grounding` record reduces the whole pass to four
    numbers in which a refutation and a reconciliation look identical. A live map shipped two of
    these while its finalize report said 0 blocking and never used the word "refuted".

    THERE IS DELIBERATELY NO RECORDED ESCAPE for this. Every escape in this tool was added after a
    real false alarm, and there is not one yet: a lead who reads a refutation and disagrees is
    expected to RE-AUTHOR the claim, which supersedes it and removes it from here by itself. Add the
    heading when a real map produces a survivor that should stay, not before."""
    claim: str
    element_id: str
    kind: str
    label: str
    refuted_by: int
    note: str = ""


def surviving_refutations(m: ProjectModel,
                          grounding_rows: list[dict]) -> list[SurvivingRefutation]:
    """The refutations the shipped map still carries.

    Walks the VERDICTS, not the worklist: a refuted claim the reconcile dropped is absent from the
    live map and must not be looked for, while one the reconcile never touched is exactly what this
    finds. The pinned worklist is not needed and is not asked for, so this runs anywhere the map and
    the verdict files are — which is what lets `finalize` include it without a captured snapshot."""
    votes: dict[str, list[dict]] = {}
    for r in grounding_rows:
        claim = r.get("claim")
        if isinstance(claim, str):
            votes.setdefault(claim, []).append(r)
    out: list[SurvivingRefutation] = []
    for claim, rows in votes.items():
        if _verdict_bucket(rows) != "refuted":
            continue
        target = resolve_claim(m, claim).target
        if target is None:
            continue          # reconciled: the live map no longer makes this claim
        note = next((str(r.get("note") or "") for r in rows if r.get("grounded") is False), "")
        out.append(SurvivingRefutation(
            claim=claim, element_id=target.element_id, kind=target.kind, label=target.label,
            refuted_by=sum(1 for r in rows if r.get("grounded") is False), note=note))
    out.sort(key=lambda s: (s.kind, s.element_id, s.claim))
    return out


def _access_rule_ids(m: ProjectModel) -> set[str]:
    """Ids of the rules the map marks `access: true` — the ones whose stated confidence is a claim
    about who may do what, not about how something works."""
    return {br.id for br in m.rules if getattr(br, "access", False) and br.id}


def _rules_voted_under_any_anchor(m: ProjectModel, grounding_rows: list[dict]) -> set[str]:
    """Rule ids a skeptic voted on, matched by STATEMENT rather than by the anchored claim string.

    `element_checks` pairs a vote to an element by exact claim text, and a rule-site claim embeds the
    `file:line` and the site's `why` (see `rule_site_claim`). So moving an anchor one line, or
    rewording a `why`, orphans every vote the rule ever had and the element reads `unchecked` — as if
    nobody had looked. That is fine for an advisory about wording. It is not fine for a gate: an
    adversarial review moved ONE anchor on a confirmed access rule of a real map and the rule went
    straight to BLOCKING under a message reading "NO skeptic ever voted on it", which was false. 50
    of that map's 56 access rules sit in the state where that could happen, and `fix apply-drift` —
    the method's own remedy for a drifted anchor — is documented as moving exactly these anchors.

    The statement is the part of the claim that does NOT move when an anchor is corrected, so it is
    what tells "nobody challenged this rule" from "the rule was challenged and then re-anchored"."""
    claims = " \u0000 ".join(str(r.get("claim") or "") for r in grounding_rows)
    return {br.id for br in m.rules
            if br.id and (br.statement or "").strip() and (br.statement or "").strip() in claims}


def format_refutations(surviving: list[SurvivingRefutation],
                       disagreeing: list[ElementCheck], as_json: bool = False,
                       m: ProjectModel | None = None,
                       grounding_rows: list[dict] | None = None) -> str:
    """The gate's report: what the map still asserts against its own skeptics.

    `access` rides on each unchallenged element because the caller has to tell two cases apart that
    read identically here. A component description stating `verified` with no vote is a prose
    overstatement. An ACCESS rule stating `verified` with no vote is the map telling a reader that
    someone checked who may do what, when nobody did — and a shipped mcpolis map carried exactly
    two, `A sign-in return must carry an unforged ticket` and `Live updates never cross
    organizations`, both authored after the worklist was pinned so no skeptic ever saw them, both
    labelled `verified` by the hand that wrote them."""
    access = _access_rule_ids(m) if m else set()
    voted = _rules_voted_under_any_anchor(m, grounding_rows or []) if m else set()
    if as_json:
        return json.dumps({
            "surviving_refutations": [
                {"claim": s.claim, "id": s.element_id, "kind": s.kind, "label": s.label,
                 "refuted_by": s.refuted_by, "note": s.note} for s in surviving],
            "stated_but_unchallenged": [
                {"id": e.element_id, "kind": e.kind, "label": e.label, "stated": e.stated,
                 "status": e.status, "access": e.element_id in access,
                 "voted_under_any_anchor": e.element_id in voted} for e in disagreeing],
        }, indent=2, ensure_ascii=False)
    lines: list[str] = []
    if surviving:
        lines.append(f"{len(surviving)} REFUTED claim(s) are still in this map, unchanged. The "
                     f"build contract is that every refutation is reconciled — corrected, or "
                     f"dropped — and a reconciled claim no longer resolves here at all:")
        for s in surviving:
            lines.append(f"  - {s.claim}   [{s.kind}{' ' + s.element_id if s.element_id else ''}, "
                         f"refuted by {s.refuted_by}]")
            if s.note:
                lines.append(f"      skeptic: {s.note[:200]}")
    else:
        lines.append("No refuted claim survives in this map.")
    if disagreeing:
        lines.append("")
        lines.append(f"{len(disagreeing)} element(s) state a confidence the pass does not support. "
                     f"The label and the votes are written by different processes and nothing else "
                     f"compares them (`coyodex grounding by-element` lists them in full):")
        for e in disagreeing[:15]:
            lines.append(f"  - {e.element_id or '-':<7} {e.kind:<12} says {e.stated}, "
                         f"pass says {e.status} — {e.label[:44]}")
        if len(disagreeing) > 15:
            lines.append(f"  ... and {len(disagreeing) - 15} more")
    return "\n".join(lines)


def worklist_is_behavioural(path: Path) -> bool:
    """Was this pinned worklist captured with `audit --with-behavioural`?

    Read off the items' own `theme`, not a new file field: `audit --json` already writes the theme
    per item, and the behavioural tier is the only producer of `behaviour`. Deriving it means an
    existing worklist file answers the question with no migration.

    WHY IT HAS TO BE ASKED. The live claim surface below is recomputed from the assembled map, and
    it used to be recomputed at the DEFAULT tier always. So a build that pinned a behavioural
    worklist got every behaviour claim back as `superseded` — 489 of them on the map this was
    written from — and `live_claims_digest` described a different surface from the one that was
    pinned. That made the tier unusable in practice, which is why 1,049 rows of the 2026-09-02
    mcpolis map were outside the worklist "by construction". The two surfaces must be computed the
    same way or the record is about neither."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    items = payload if isinstance(payload, list) else payload.get("worklist", [])
    return any(isinstance(i, dict) and str(i.get("theme", "")) == "behaviour" for i in items)


def _worklist_claims(path: Path) -> list[str]:
    """Claims from a worklist file, in either shape it legitimately arrives in.

    A BARE LIST is what `coyodex audit --json | jq .worklist` produces, and it is the obvious way
    to hand this command its input. The list case was already intended — the `isinstance` test was
    written — but it sat inside the default argument of `.get()`, so reaching it required the
    attribute access that had already raised. The guard could never run, and the one input shape it
    existed for was the one that crashed with a traceback."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload if isinstance(payload, list) else payload.get("worklist", [])
    return [str(i.get("claim", "")) for i in items if isinstance(i, dict)]


@dataclass
class VerdictLint:
    """The lint's answer. A dataclass, not a `(list, list)` tuple — both are empty on the happy
    path, so a swapped pair reads as correct behaviour and no test can tell the difference. Same
    reason `assemble.FragmentLoad` exists."""
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def lint_verdicts(paths: list[str], agent_dir: Path | None = None) -> VerdictLint:
    """Shape check over raw verdict files, WITHOUT needing a worklist or a map.

    `grounding write` already refuses a malformed record — but it runs at the very end of a build,
    and the skeptic that produced the bad file finished a hundred turns earlier. One live build
    shipped 40 rows whose `grounded` was the STRING `"true"`; the refusal came at the last step and
    cost four turns of hand-repair on the critical path. The same check, runnable the moment a
    skeptic returns, costs nothing and fails where the fix is cheap.

    With `--agent-transcripts <dir>` it also answers a question no shape check can: is the file a
    row cites one this agent ever touched. The incident behind it: one skeptic settled 40 claims in
    95 seconds from a single directory-wide grep and generated every row from a script, each `note`
    opening `Read <file>:` for files it never opened.

    WHAT IT CATCHES, stated narrowly on purpose. A citation of a file that appears NOWHERE in the
    transcript is a hard problem — that is a path the agent could not have learned. A citation of a
    file the transcript only ever PRINTED, in a grep result or a listing, is a note and not a
    failure: reading the matching lines out of a grep result is legitimate verification, so
    grep-only is a shape, not proof.

    WHAT IT DOES NOT CATCH, so nobody reads a clean run as more than it is: the incident above would
    pass this as a note. Its tell was 40 claims in 95 seconds off one grep — a RATE, not a missing
    path — and a rate is not something this command can see. Do not treat `VERDICTS OK` as evidence
    that a pass was honest.
    """
    out = VerdictLint()
    rows, load_notes = load_verdicts(paths)
    out.notes += load_notes
    if not rows:
        out.problems.append("no verdict rows found in " + ", ".join(paths))
        return out

    bad = sorted({f"{r.get('grounded')!r}" for r in rows
                  if not (r.get("grounded") is True or r.get("grounded") is False
                          or (isinstance(r.get("grounded"), str)
                              and r.get("grounded", "").lower() == "unverifiable"))})
    if bad:
        out.problems.append(
            f"{len(bad)} unrecognised `grounded` value(s): {', '.join(bad)}. The vocabulary is the "
            f"JSON booleans true / false, or the string \"unverifiable\" — `\"true\"` quoted is the "
            f"one that has actually shipped, and a skeptic's own self-check cannot see it because "
            f"printing str(value) renders 'true' either way.")

    for field in ("claim", "evidence", "skeptic"):
        missing = sum(1 for r in rows if not str(r.get(field) or "").strip())
        if missing:
            out.problems.append(f"{missing} row(s) have no `{field}` — "
                            + {"claim": "the record pairs rows to claims by that exact string",
                               "evidence": "a verdict with no line is an opinion",
                               "skeptic": "it is what tells two independent votes from one file "
                                          "passed in twice"}[field])

    if agent_dir is not None:
        evidence = _fabricated_evidence(rows, agent_dir)
        # The weak half says of itself that it is not proof, so it rides as a NOTE. A signal that
        # fails the lint is a signal an agent must clear, and the only way to clear this one is to
        # re-read files it may have read already — which teaches the next agent to route its reading
        # around the check rather than to look again.
        out.problems += evidence.problems
        out.notes += evidence.notes
    return out


#: A note asserting the skeptic opened something — the claim this check tests against the record of
#: what it actually opened.
_CLAIMS_A_READ = re.compile(r"\bread\s+([\w./-]+\.[A-Za-z0-9]+)", re.I)


#: The file extensions a map anchors into. An explicit list, because `evidence` also carries
#: SYMBOL references — `ServiceTokenService.mint`, `MongoOAuthStateRepository.save` — which are
#: `Word.word` and match any "token dot token" rule. Reading eleven of those as unopened files was
#: the first thing this widening did.
_SOURCE_SUFFIXES = (
    "py", "pyi", "js", "jsx", "ts", "tsx", "mjs", "cjs", "go", "rs", "rb", "java", "kt", "kts",
    "swift", "c", "h", "cc", "cpp", "hpp", "cs", "php", "scala", "clj", "ex", "exs", "erl", "lua",
    "sh", "bash", "zsh", "sql", "html", "css", "scss", "vue", "svelte", "json", "yaml", "yml",
    "toml", "ini", "cfg", "conf", "env", "md", "txt", "proto", "graphql", "tf", "dockerfile")

#: Extensionless files a map really anchors into. Across three real maps these are 60 anchors the
#: suffix list alone could not reach — `Makefile` 43 times on one of them — and a build file is
#: where a fabricated claim is least likely to be noticed.
_EXTENSIONLESS = ("makefile", "dockerfile", "procfile", "rakefile", "gemfile", "justfile",
                  "commit-msg", "pre-commit", "pre-push", "codeowners")

#: A bare `path:line` — the shape every verdict row's `evidence` field carries.
_EVIDENCE_PATH = re.compile(
    r"((?:[\w./-]+\.(?:" + "|".join(_SOURCE_SUFFIXES) + r")"
    r"|(?:[\w./-]*/)?(?:" + "|".join(_EXTENSIONLESS) + r")))(?::\d+)?$", re.I)


def _claimed_files(row: dict) -> set[str]:
    """Every file this row asserts the skeptic looked at.

    Two sources, and the second is what took this check from 2 % of rows to nearly all of them. The
    NOTE half was here first and only matches prose of the shape `read <file>.<ext>`; on a measured
    build that was 20 of 1000 rows, because most notes cite their anchor in `evidence` instead and
    describe the reading in words. `evidence` is a bare `path:line` on every row, and citing a file
    you never opened is precisely the shape this check exists to catch — the skeptic that settled 40
    claims in 95 seconds from one directory-wide grep put a real-looking anchor on every one."""
    out = {_norm_path(m) for m in _CLAIMS_A_READ.findall(str(row.get("note") or ""))
           if m.rsplit(".", 1)[-1].lower() in _SOURCE_SUFFIXES
           or m.rsplit("/", 1)[-1].lower() in _EXTENSIONLESS}
    ev = _EVIDENCE_PATH.match(str(row.get("evidence") or "").strip())
    if ev:
        out.add(_norm_path(ev.group(1)))
    return {f for f in out if f}


def _read_claim_coverage(rows: list[dict]) -> tuple[int, int]:
    """`(rows, rows the evidence check can actually test)`."""
    return len(rows), sum(1 for r in rows if _claimed_files(r))


#: Suffixes a per-agent transcript is written under. `.jsonl` is the settled convention; `.output`
#: is what the harness names in the dispatch result it hands the LEAD — same JSONL, different
#: extension — and pointing this flag at that directory failed outright. The flag was suggested by
#: the tool twice on one build and used zero times, because the only path the lead had been given
#: was the one that does not work.
_AGENT_TRANSCRIPT_GLOBS = ("*.jsonl", "*.output")


def _records(path: Path) -> list[dict[str, object]]:
    """The agent-transcript RECORDS in one file — dicts only.

    A JSONL line is not guaranteed to decode to an object. `<session>/tasks/` mixes the per-agent
    transcripts with the stdout of every BACKGROUND BASH call the lead made, under the same
    `.output` suffix, and that stdout is whatever the command printed: a pretty-printed JSON file
    whose lines decode to `{`-fragments, or a bare number that decodes to an `int`. Callers used to
    go straight to `rec.get(...)`, so one such line aborted the whole pass with
    `AttributeError: 'int' object has no attribute 'get'` — measured on a real build, where it
    killed the fabricated-evidence check for all 1,085 verdict rows and the build shipped a
    `grounding.note` saying the check could not run at all.
    """
    out: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _is_agent_transcript(path: Path) -> bool:
    """Does this file look like ONE agent's turn log, rather than some command's stdout?

    Every line of an agent transcript is a JSON OBJECT. Background-Bash output under the same
    `.output` suffix is whatever the command printed, and on the measured build that included bare
    scalars — which is what crashed the pass — and pretty-printed JSON, whose lines mostly do not
    parse at all. So the test is: at least one object, and no line that parses to something else.

    An EMPTY-looking transcript still counts, because "this agent opened nothing" and "there are no
    agent transcripts here" are different answers and only the second should raise the
    wrong-directory error.

    Dropping the stdout captures matters beyond the crash: every path token they print would land in
    the LOOSE `_mentioned_files` set, which decides whether a cited file counts as "named
    somewhere". A claims batch printed by a background command would vouch for rows no agent read.
    """
    objects = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            objects += 1
        else:
            return False
    return objects > 0


def _agent_transcript_files(agent_dir: Path) -> list[Path]:
    """Every per-agent transcript under `agent_dir`, whichever suffix the harness used.

    Files that parse but are not agent transcripts are dropped — see `_is_agent_transcript`."""
    seen: dict[Path, None] = {}
    for pattern in _AGENT_TRANSCRIPT_GLOBS:
        for f in sorted(agent_dir.glob(pattern)):
            resolved = f.resolve()
            if resolved in seen:
                continue
            if _is_agent_transcript(resolved):
                seen.setdefault(resolved, None)
    return sorted(seen)


#: A tool call that really opens a file, and where the path sits in its input. `Read` is the direct
#: one; the shell verbs are how a skeptic reads a range without loading a whole file.
#: `Grep` and `Glob` open nothing themselves, but a skeptic that greps a file and reads the matching
#: lines out of the RESULT has verified the claim — and accusing it of fabrication is the expensive
#: mistake here. They count as opening their `path`, which is why the strong set is the one that
#: FAILS the lint and the loose set only notes.
_FILE_READING_TOOLS = ("Read", "NotebookRead", "Grep", "Glob")
_SHELL_READERS = re.compile(r"\b(?:cat|sed|head|tail|less|awk|grep|rg|nl|wc)\b")


def _shell_read_operands(command: str) -> set[str]:
    """Paths a shell command READS, as operands — never as a pattern or a redirect target.

    `grep -rn "src/auth_token.py" docs/` names a path inside its PATTERN and opens nothing. Taking
    every path-shaped token out of the command string turned that into a self-service whitelist: one
    grep laundered an arbitrary file list into "actually opened", and the row cleared without even a
    note. Quoted spans and everything after a redirect are dropped, and only the verbs that read a
    file are considered at all."""
    if not _SHELL_READERS.search(command):
        return set()
    body = re.sub(r"'[^']*'|\"[^\"]*\"", " ", command)      # a pattern is quoted; an operand rarely is
    body = re.split(r"[>]", body)[0]                        # a redirect target is written, not read
    out: set[str] = set()
    for tok in body.split():
        if tok.startswith("-"):
            continue
        if re.fullmatch(r"[\w./-]+\.[A-Za-z0-9]+", tok) or tok.rsplit("/", 1)[-1].lower() in _EXTENSIONLESS:
            out.add(_norm_path(tok))
    return out


def _opened_files(files: list[Path]) -> set[str]:
    """Paths the agent's transcript shows it ACTUALLY opening — file-reading tool calls only.

    The permissive set below (every filename-shaped token anywhere in the transcript) is what this
    check used to test against, and it is close to useless: measured on one skeptic transcript from
    a real build it held 477 names where the agent had opened 17 files. A directory-wide `grep`
    prints hundreds of paths into the transcript, and a grep is exactly what the fabricating skeptic
    this check was written for used. So the two sets are kept apart: a claim outside BOTH is a hard
    finding, and a claim inside the loose set but outside this one is the weaker signal, reported as
    such rather than silently folded into "no findings"."""
    out: set[str] = set()
    for f in files:
        for rec in _records(f):
            msg = rec.get("message")
            for c in ((msg if isinstance(msg, dict) else {}).get("content") or []):
                if not isinstance(c, dict) or c.get("type") != "tool_use":
                    continue
                inp = c.get("input") or {}
                if c.get("name") in _FILE_READING_TOOLS:
                    for key in ("file_path", "path", "notebook_path"):
                        if str(inp.get(key) or "").strip():
                            out.add(_norm_path(str(inp[key])))
                elif c.get("name") == "Bash":
                    out |= _shell_read_operands(str(inp.get("command") or ""))
    return {p for p in out if p}


def _norm_path(p: str) -> str:
    """One normaliser, used on BOTH sides. `lstrip("./")` was the first version and it is a
    character-class strip, not a prefix strip: it turned `.github/dependabot.yml` into
    `github/dependabot.yml` while the transcript kept `/.github/`, so the two could never match. The
    single finding the widened check produced on a real 1000-row pass was that false accusation, and
    one of the three real maps carries 104 dot-directory anchors."""
    return p.strip().removeprefix("./").rstrip("/")


def _mentioned_files(files: list[Path]) -> set[str]:
    """Every path the transcript NAMES anywhere — including in a tool result a grep printed.

    Decoded from the JSON, not scanned off raw lines. A JSONL record holds `\n` as a two-character
    escape, so a line-wise regex reads `\nsrc/pkg/mod.py` as a token beginning `nsrc/`: measured on
    one real transcript, 10 of 477 tokens were real paths mangled that way. It decided outcomes — the
    same 40 fabricated rows exited 1 or 0 depending on whether the grep output happened to be
    indented."""
    out: set[str] = set()
    for f in files:
        for rec in _records(f):
            text = (json.dumps(rec, ensure_ascii=False)
                    .replace("\\n", "\n").replace("\\t", "\t"))
            for m in re.finditer(r"[\w./-]+\.[A-Za-z0-9]+", text):
                out.add(_norm_path(m.group(0)))
            for m in re.finditer(r"(?:[\w./-]*/)?(?:" + "|".join(_EXTENSIONLESS) + r")\b", text,
                                 re.I):
                out.add(_norm_path(m.group(0)))
    return {p for p in out if p}


def _resolves(claimed: str, pool: set[str]) -> bool:
    """Is `claimed` one of `pool`?

    SYMMETRIC, because the sides disagree about absoluteness in both directions: a transcript may
    hold `/repo/a/b.py` where a verdict cites `a/b.py`, and a verdict may cite an absolute path
    where the transcript holds the relative one.

    A bare BASENAME never matches on suffix alone. `config.py` would otherwise resolve against
    `vendor/thirdparty/junk/config.py` and clear a row that cited a file nobody opened — the check
    would report clean on exactly the shape it exists to catch. A one-segment claim must match
    whole."""
    c = _norm_path(claimed)
    if not c:
        return False
    normed = {_norm_path(p) for p in pool}
    if c in normed:
        return True
    if "/" in c:
        return any(p.endswith("/" + c) or c.endswith("/" + p) for p in normed)
    # A one-segment claim (`config.py`, `Makefile`) matches on basename ONLY when the pool holds
    # exactly one file with that name. Two candidates and the claim cannot say which was read; zero
    # is a genuine miss. Matching any suffix would clear a row that cited `config.py` against a
    # `vendor/thirdparty/junk/config.py` nobody opened — clean on the shape this exists to catch.
    same_name = {p for p in normed if p.rsplit("/", 1)[-1] == c}
    return len(same_name) == 1


def _fabricated_evidence(rows: list[dict], agent_dir: Path) -> VerdictLint:
    """What the transcript says about files a row CITES but the agent never opened.

    A `VerdictLint`, not a `(list, list)` pair, for the reason that class already exists: both slots
    are empty on the happy path, so a swapped return reads as correct behaviour and no test can tell
    the difference. `tests/test_cli_contract` refuses the positional shape by name."""
    files = _agent_transcript_files(agent_dir)
    opened = _opened_files(files)
    mentioned = _mentioned_files(files)
    if not files:
        # Name the directory that DOES work. The lead is handed
        # `<session>/tasks/<id>.output` at dispatch and has to guess that the readable copies live
        # in `<session>/subagents/`; "holds no .jsonl" told it neither.
        sibling = agent_dir.parent / "subagents"
        hint = (f" Did you mean {sibling}? That is where this harness keeps the readable per-agent "
                f"files; the `tasks/` directory a dispatch result names holds the same JSONL under "
                f"a different suffix." if sibling.is_dir() and sibling != agent_dir else "")
        return VerdictLint(problems=[
            f"--agent-transcripts {agent_dir} holds no per-agent transcript "
            f"({' or '.join(_AGENT_TRANSCRIPT_GLOBS)}) — nothing to check evidence against.{hint}"])
    claimed: dict[str, int] = {}
    for r in rows:
        for hit in _claimed_files(r):
            claimed[hit] = claimed.get(hit, 0) + 1
    # A file in EITHER set is not a ghost. Testing `mentioned` alone accused two real, opened files
    # on a live pass: `mentioned` is built from path-shaped tokens with a dot in them, so
    # `Makefile` — which the agent had genuinely opened with `Read` — never entered it.
    ghosts = sorted(f for f in claimed if not _resolves(f, mentioned | opened))
    unopened = sorted(f for f in claimed
                      if f not in ghosts and not _resolves(f, opened))
    found = VerdictLint()
    if ghosts:
        found.problems.append(
            f"{len(ghosts)} file(s) are cited as evidence but appear NOWHERE in the "
            f"{len(files)} transcript(s) given: {', '.join(ghosts[:8])}"
            f"{' …' if len(ghosts) > 8 else ''}. A cited anchor is a statement about your own work; "
            f"{sum(claimed[g] for g in ghosts)} row(s) rest on one. Pass the transcripts of EVERY "
            f"skeptic in the pass — rows are pooled across all of them, so a missing transcript "
            f"reads exactly like a fabricated citation.")
    if unopened:
        found.notes.append(
            f"{len(unopened)} file(s) are cited as evidence and appear in the transcript only as "
            f"TEXT — printed by a grep or a listing — never as a file this agent opened: "
            f"{', '.join(unopened[:8])}{' …' if len(unopened) > 8 else ''}. Weaker than the line "
            f"above and not proof of anything: a skeptic may read a range through a shell verb this "
            f"cannot see. It is the shape the fabricating pass had — 40 claims settled in 95 seconds "
            f"off one directory-wide grep — so {sum(claimed[u] for u in unopened)} row(s) are worth "
            f"a second look.")
    return found


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    verb, rest = argv[0], argv[1:]
    if verb not in ("write", "report", "lint", "by-element", "refutations"):
        print(f"ERROR: unknown verb '{verb}' (expected `write`, `report`, `by-element`, "
              f"`refutations` or `lint`)\n\n{USAGE}",
              file=sys.stderr)
        return 2
    # Same hole `coyodex fix` had: the option loop below rejects `--help` as an unknown option.
    helped = subverb_help.handle(USAGE, verb, rest)
    if helped is not None:
        return helped
    worklist_path = out_path = map_path = agent_dir = None
    expect: list[str] = []
    verdicts: list[str] = []
    note = ""
    note_file: str | None = None
    keep_note = False
    as_json = False
    partial = False
    note_cites_other_runs = False
    only_kind = ""
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "--agent-transcripts":
            i += 1
            if i >= len(rest):
                print("ERROR: --agent-transcripts needs a directory", file=sys.stderr)
                return 2
            agent_dir = rest[i]
        elif a == "--json":
            as_json = True
        elif a == "--partial":
            partial = True
        elif a == "--keep-note":
            keep_note = True
        elif a == "--note-cites-other-runs":
            note_cites_other_runs = True
        elif a in ("--worklist", "--verdicts", "--out", "--note", "--note-file", "--map",
                   "--kind"):
            i += 1
            if i >= len(rest):
                print(f"ERROR: {a} needs a value", file=sys.stderr)
                return 2
            if a == "--worklist":
                worklist_path = rest[i]
            elif a == "--map":
                map_path = rest[i]
            elif a == "--kind":
                only_kind = rest[i]
            elif a == "--verdicts":
                # VARIADIC, as the usage line has always said (`--verdicts <raw.json>...`): swallow
                # every following non-flag path, not just one. It took exactly one value, so the
                # documented spelling `--verdicts a.json b.json` died on
                # `unknown option(s): b.json` — while `write` and `report` are routinely handed
                # thirty files, and a build that trusted the usage line got an error instead of a
                # run. All three verbs share this loop, so all three were wrong together.
                verdicts.append(rest[i])
                while i + 1 < len(rest) and not rest[i + 1].startswith("-"):
                    i += 1
                    verdicts.append(rest[i])
            elif a == "--out":
                out_path = rest[i]
            elif a == "--note-file":
                note_file = rest[i]
            else:
                note = rest[i]
        elif a == "--expect":
            i += 1
            expect += [x for x in rest[i].split(",") if x.strip()] if i < len(rest) else []
        else:
            return subverb_help.usage_error(USAGE, verb, f"unknown option(s): {a}")
        i += 1
    if verb == "lint":
        # LINT NEEDS ONLY THE VERDICTS. Requiring a worklist and a map here would put it at the end
        # of the build again, which is the whole thing it exists to move earlier.
        if not verdicts:
            print("ERROR: grounding lint needs at least one --verdicts <file>", file=sys.stderr)
            return 2
        # `--expect` NAMES THE BATCHES THAT MUST HAVE LANDED. Without it this command lints the
        # files that happen to exist and cannot see a batch that produced none, so a fan-out whose
        # last skeptic was still writing linted clean: one live run printed
        # `VERDICTS OK — 18 file(s) well-formed` while a nineteenth was seconds from landing, and
        # five verdict-consuming commands then ran against the incomplete set and were redone.
        # A missing file is the one failure a reader cannot spot by eye, because nothing is there.
        if expect:
            have = {Path(v).stem.replace("verdicts-", "") for v in verdicts}
            missing = [b for b in (x.strip() for x in expect) if b and b not in have]
            if missing:
                print(f"VERDICTS INCOMPLETE — {len(missing)} expected batch(es) have no verdicts "
                      f"file: {', '.join(missing)}", file=sys.stderr)
                print("The fan-out has not finished, or an agent returned without writing. Do NOT "
                      "run anchor-drift, apply-drift or grounding write yet: each consumes the "
                      "verdict set and would have to be redone.", file=sys.stderr)
                return 1
        lint = lint_verdicts(verdicts, Path(agent_dir) if agent_dir else None)
        problems = lint.problems
        for n in lint.notes:
            print(n, file=sys.stderr)
        if problems:
            print(f"VERDICTS FAILED — {len(problems)} problem(s)", file=sys.stderr)
            for pr in problems:
                print(f"  - {pr}", file=sys.stderr)
            print("Fix these before `grounding write`; it refuses the same shapes at the END of "
                  "the build, where the skeptic that produced them is a hundred turns gone.",
                  file=sys.stderr)
            return 1
        # SAY WHAT WAS CHECKED, not just that nothing failed. With `--agent-transcripts` this
        # printed the same "well-formed" line as without it, so a run that tested 16 of 949 rows
        # and a run that tested none were indistinguishable — and the operator read the silence as
        # a clean bill of health on the whole pass. The evidence check can only speak about a note
        # that NAMES a file it read; that number belongs on screen beside the verdict.
        lint_rows, _ = load_verdicts(verdicts)
        rows_total, rows_testable = _read_claim_coverage(lint_rows)
        print(f"VERDICTS OK — {len(verdicts)} file(s) well-formed, {rows_total} verdict row(s)"
              + ("; pass --agent-transcripts <dir> to also check that every note claiming a read "
                 "is backed by the agent's transcript" if not agent_dir else
                 f"; evidence check covered {rows_testable} of {rows_total} row(s) — every row "
                 f"citing a file, in `evidence` or in a `read <file>` note. A row anchored on a "
                 f"SYMBOL, or on a filename this does not recognise, cannot be tested this way"))
        return 0

    if verb == "refutations":
        # NO --worklist. This walks the verdicts against the LIVE map, so it needs no pinned
        # snapshot — which is what lets `finalize` run it with the verdict files a build already
        # has, at the point where a captured worklist may be several reconciles out of date.
        if not map_path or not verdicts:
            print(f"ERROR: grounding refutations needs --map and at least one --verdicts",
                  file=sys.stderr)
            return 2
        try:
            live = load_model(resolve_map_path(map_path).read_text(encoding="utf-8"))
        except (OSError, ModelError) as e:
            print(f"ERROR: --map {map_path} could not be read as a map ({e})", file=sys.stderr)
            return 2
        rows, notes = load_verdicts(verdicts)
        for n in notes:
            print(n, file=sys.stderr)
        surviving = surviving_refutations(live, rows)
        # DEFAULT tier here, deliberately, unlike `write` above. This surface feeds the advisory
        # confidence cross-check only — the refutation GATE beside it walks the verdicts directly
        # and is unaffected — and a behaviour claim resolves onto a flow or a crossing, which carry
        # no `confidence` field at all. Widening it would add rows whose stated label is `-` to a
        # list whose whole subject is the stated label.
        checks, _unresolved = element_checks(live, [w.claim for w in l2_worklist_model(live)], rows)
        print(format_refutations(surviving, [c for c in checks if c.disagrees],
                                 as_json=as_json, m=live, grounding_rows=rows))
        # BLOCKING on a survivor, ADVISORY on a label the pass does not support. The second is a
        # judgement about wording; the first is the map asserting something its own skeptics
        # disproved, which is the one shape here that makes the map wrong rather than unclear.
        return 1 if surviving else 0

    if verb == "by-element" and not worklist_path and verdicts:
        # `--worklist` OPTIONAL here, and only here. `finalize`'s advisory prints a count and then
        # names this command as where the list lives — but `finalize` reaches the count through
        # `grounding refutations`, which walks the LIVE map on purpose ("a captured worklist may be
        # several reconciles out of date"), while this verb required the PINNED file. On the
        # 2026-08-29 mcpolis map the two answered 1 and 7 about the same map, because six elements
        # had been reworded after the pin: measured against the pinned text their votes no longer
        # pair, measured against the live text they do. Neither number is wrong and the remedy could
        # not reproduce the finding it was offered for. With no `--worklist`, this now asks
        # `finalize`'s question; with one, it asks "what did the SKEPTICS see", which is the other
        # honest question and is why the flag stays.
        pass
    elif not worklist_path or not verdicts:
        print(f"ERROR: --worklist and at least one --verdicts are required\n\n{USAGE}",
              file=sys.stderr)
        return 2
    # `--note` is required for a real record, and a re-run therefore had to re-supply a note that
    # already existed. A live build did it through a nested `$(python -c …)` that re-extracted a
    # ~1900-character note out of the previous fragment and pushed it back through the shell — it
    # survived, but a note containing a quote or a backtick would not have. Two ways out that never
    # touch the shell: read it from a file, or keep the one already in `--out`.
    if keep_note and (note_file or note):
        other = "--note-file" if note_file else "--note"
        print(f"ERROR: --keep-note reuses the note already in --out; {other} supplies a new one. "
              f"Pick one — silently discarding the note you typed is worse than refusing.",
              file=sys.stderr)
        return 2
    if note_file:
        try:
            note = Path(note_file).read_text(encoding="utf-8").strip()
        except OSError as e:
            print(f"ERROR: --note-file {note_file} could not be read ({e})", file=sys.stderr)
            return 2
        if not note:
            print(f"ERROR: --note-file {note_file} is empty", file=sys.stderr)
            return 2
    if keep_note:
        if not out_path:
            print("ERROR: --keep-note reads the note from the existing --out fragment, so --out is "
                  "required.", file=sys.stderr)
            return 2
        prior = Path(out_path)
        existing = ""
        if prior.exists():
            try:
                doc = json.loads(prior.read_text(encoding="utf-8"))
                existing = str((doc.get("grounding") or {}).get("note") or "")
            except ValueError as e:
                print(f"ERROR: {out_path} is not valid JSON ({e})", file=sys.stderr)
                return 2
        if not existing:
            print(f"ERROR: --keep-note found no note in {out_path} — pass --note or --note-file "
                  f"for the first write.", file=sys.stderr)
            return 2
        note = existing
        print(f"note: reusing the {len(existing)}-character note already in {out_path}.",
              file=sys.stderr)
    claims = _worklist_claims(Path(worklist_path)) if worklist_path else []
    if not claims and worklist_path:
        print(f"ERROR: {worklist_path} holds no worklist claims — pass `coyodex audit <map> --json`",
              file=sys.stderr)
        return 2
    rows, notes = load_verdicts(verdicts)
    for n in notes:
        print(n, file=sys.stderr)
    live_claims = None
    live_model = None
    if verb == "by-element" and not map_path:
        # by-element resolves each claim back onto an ELEMENT, so it cannot run without the map the
        # claims are about. Refusing beats reporting an empty table that reads like "nothing was
        # checked" — the exact false-negative shape this command exists to expose.
        print("ERROR: grounding by-element needs --map <project-map.json> — it resolves each "
              "pinned claim back onto the element that makes it.", file=sys.stderr)
        return 2
    if map_path:
        # The LIVE claim surface, read from the assembled map this record describes. Not a second
        # captured file: a file goes stale between capture and write, and the whole defect here is a
        # record describing a surface that moved.
        try:
            live_model = load_model(resolve_map_path(map_path).read_text(encoding="utf-8"))
            # AT THE PINNED WORKLIST'S OWN TIER. Computing the live surface at the default tier
            # while the pin was behavioural reports every behaviour claim as superseded and makes
            # the digest describe a surface nobody pinned.
            behavioural = bool(worklist_path) and worklist_is_behavioural(Path(worklist_path))
            live_claims = [w.claim
                           for w in l2_worklist_model(live_model, behavioural=behavioural)]
        except Exception as e:
            print(f"ERROR: --map {map_path} could not be read as a map ({e})", file=sys.stderr)
            return 2
    if verb == "by-element":
        assert live_model is not None   # guarded above: --map is required for this verb
        # With no `--worklist` the surface is the LIVE map's, which `--map` guarantees is populated.
        surface = claims if worklist_path else (live_claims or [])
        checks, unresolved = element_checks(live_model, surface, rows)
        print(format_element_checks(checks, unresolved, as_json=as_json,
                                    only_kind=only_kind))
        return 0
    if verb == "report":
        print(format_report(claims, rows, as_json=as_json, live_claims=live_claims))
        return 0
    record, errors = build_record(claims, rows, note, live_claims=live_claims, partial=partial)
    # REFUSE, having been a warning and having failed as one. This used to warn, on the argument
    # that prose has more shapes than a regex — a note citing only EARLIER builds' figures states a
    # number this pass does not have and is honest. That case is already covered by the "any
    # occurrence clears it" rule inside each check: a note that also quotes this pass passes. What
    # the warning did not cover is the case it was built for. The redundant-row error was found by
    # one retrospective, marked fixed by printing the right number, and shipped again on the next
    # map; the anchor-unanimity claim then shipped on a third. A warning on stderr, inside a build
    # that prints thousands of lines, is not seen.
    #
    # The note is a PERMANENT record and goes into the commit message, so a wrong number here
    # outlives every other artifact of the run, and the fix in each message is one word. That is the
    # bar for blocking: silent, durable, and cheap to correct.
    # The agreement claim warns and never refuses — see `_agreement_contradictions` for why a regex
    # may not block on an assurance. Printed first, so it is not buried under a refusal.
    for line in _agreement_contradictions(note, rows):
        print(f"WARNING: {line}", file=sys.stderr)
    note_faults = _note_contradictions(note, rows, record, live_claims)
    if note_faults and note_cites_other_runs:
        # The operator has ASSERTED that the numbers in the note are about other runs, or are
        # theme-scoped. Warn and continue — the same escape `--partial` is, for the same reason:
        # the tool cannot read which pass a sentence is about, and the operator can.
        for line in note_faults:
            print(f"WARNING: {line}", file=sys.stderr)
        print(note_facts_block(claims, rows, record, live_claims), file=sys.stderr)
    elif note_faults:
        errors = list(errors) + [
            f"the `--note` contradicts this pass's own numbers. {line}" for line in note_faults]
        errors.append(
            "If the numbers in the note are about OTHER runs, or are scoped to one theme rather "
            "than the whole pass, pass `--note-cites-other-runs` to say so and this becomes a "
            "warning.")
        # The numbers to fix it with, in the same breath as the refusal. Without this the operator
        # is told the note is wrong and not what right would be, and the next attempt is a guess.
        print(note_facts_block(claims, rows, record, live_claims), file=sys.stderr)
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
        # SAY IT AT THE MOMENT IT HAPPENS. The line above is the pinned pass and reads as complete
        # even when the shipped map is not; a build that saw only that line wrote "All 209 claims
        # were challenged" into a permanent note. `anchor-drift` had already said 199 of 209 ten
        # turns earlier, and nothing tied the two together.
        # THE NUMBERS A NOTE WILL CITE, COMPUTED, so nobody retypes one from an earlier view.
        #
        # `--note` is free prose in a permanent record and in the commit message, and nothing
        # checks it. One shipped note said "Eighteen fresh-context skeptics" about a build that
        # dispatched 17 and produced 20 verdict labels: the 18 was read off a `grounding lint`
        # line printed while one verdict file was still being written, then carried forward. The
        # same note said "Four superseded claims had been CONFIRMED" where this report counts 11,
        # leaving seven deliberate overrides of settled claims undisclosed. Both numbers were
        # available here, at the moment the note was written.
        print(note_facts_block(claims, rows, record, live_claims))
        live_done = record.get("claims_live_challenged")
        if live_claims is not None and isinstance(live_done, int):
            live_total = len(set(live_claims))
            if live_done < live_total:
                print(f"  NOTE: the SHIPPED map carries {live_total} claim(s), of which "
                      f"{live_done} have a verdict — {live_total - live_done} do NOT. They were "
                      f"minted after the worklist was pinned, so no skeptic saw them. Challenge "
                      f"them, or say so in `--note`: `claims_challenged` counts the pinned "
                      f"worklist and will keep reading as full coverage.")
    elif as_json:
        print(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
