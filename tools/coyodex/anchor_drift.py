"""`coyodex anchor-drift` — the deterministic Layer-2 check that an edge's stored `where` anchor points
at the line the operation actually happens on.

It rides the Phase-4 grounding skeptics (who already read the call-site): for every CONFIRMED claim
(majority `grounded=True`) it compares the stored anchor to the line the skeptics reported, and prints a
drift worklist for the lead to reconcile by fixing `where`. The LLM only OBSERVES (reports a line); this
check JUDGES drift deterministically — honoring "verbs / the LLM may prioritize, never gate". No
auto-fix, non-gating (informational, like the L2 worklist). Stdlib-only (the cli.py firewall).
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from coyodex import reporting
from coyodex.anchors import DriftResult, anchor_drift, parse_anchor
from coyodex.audit_model import WorkItem, l2_worklist_model
from coyodex.model import ProjectModel, load_model
from coyodex.validate_analysis import _source_roots
from coyodex.validate_model import check_operative_lines_model

_DEFAULT_TOLERANCE = 2


def consensus_evidence(stored: str | None, reported: list[str]) -> str | None:
    """The single reported `path:line` at the consensus (median) line — the value a drifted `where`
    should take. Mirrors `anchor_drift`'s median selection (same-file group when the stored anchor
    parses, else all reported locs) so `--json`, the human report, and `fix apply-drift` never
    disagree on WHICH line the skeptics settled on."""
    locs = [(r.strip(), parse_anchor(r)) for r in reported]
    parsed = [(txt, loc) for txt, loc in locs if loc is not None and loc.lo is not None]
    if not parsed:
        return None
    s = parse_anchor(stored) if stored else None
    if s is not None and s.lo is not None:
        base = s.path.rsplit("/", 1)[-1]
        same = [(txt, loc) for txt, loc in parsed if loc.path.rsplit("/", 1)[-1] == base]
        group = same if same else parsed
    else:
        group = parsed
    group_sorted = sorted(group, key=lambda t: t[1].lo)  # type: ignore[arg-type,return-value]
    return group_sorted[len(group_sorted) // 2][0]


def _confirmed_drifts(worklist: list[WorkItem], grounding: list[dict],
                      tolerance: int) -> list[tuple[WorkItem, DriftResult, list[str]]]:
    """(work-item, drift, grounded-evidence) for every CONFIRMED claim whose stored anchor drifts from
    the skeptics' reported line. Confirmed = a strict majority of that claim's votes have
    `grounded=True`. The grounded-evidence list is carried out so a consumer can recover the corrected
    `path:line` without re-tallying votes.

    Claims the worklist marks `drift_eligible=False` are skipped outright. Their anchor deliberately
    points where the operation does NOT happen — a store claim is anchored at the entity's TYPE
    DEFINITION by the domain-card contract, so the WRITE line a skeptic reports is not drift, and
    nudging the anchor onto it would corrupt the card. Those rows are REPORT-ONLY: a refuted one is
    re-authored by hand, never auto-moved. This is a property of the claim, never a text match on
    its wording. REFUTATION is untouched — only the anchor nudge is suppressed."""
    # NO DEDUPE, deliberately, and the reasoning is worth keeping because a plausible fix was tried
    # and reverted. The tally is a STRICT MAJORITY and always was: a review claimed a split vote was
    # "decided by file-sort order", which is false — 1-grounded/1-refuted is a tie and is not
    # confirmed, in either order (brute-forced over every permutation up to 3-3).
    #
    # The narrow risk that remains is real: a build passes both an aggregate verdicts file and the
    # per-batch ones, so one skeptic's row can arrive twice, and duplicating ONE side of a tie would
    # manufacture a majority. Collapsing identical `(claim, grounded, evidence)` triples looks like the
    # fix and is worse in two ways. Refutations carry NO evidence line by convention, so every
    # refutation of a claim collapses to a single vote — turning a genuine 2-2 tie into 2-1 CONFIRMED,
    # which is exactly the failure it was meant to prevent, running the other way. And two independent
    # skeptics that agree on the same line are indistinguishable from one row seen twice: on this
    # repo's own recorded build, `verdicts1.json` and `verdicts1b.json` are two independent reads of
    # the security batch that agree exactly on 37 of 40 claims, and deduping left 396 of 399 claims
    # with a single vote — gutting the majority this function exists to compute.
    #
    # A correct fix needs a per-VOTE identity (which skeptic/batch produced the row) that the verdicts
    # format does not carry. That is a format change, not a tally change.
    votes: dict[str, list[dict]] = defaultdict(list)
    for v in grounding:
        claim = v.get("claim")
        if isinstance(claim, str):
            votes[claim].append(v)
    out: list[tuple[WorkItem, DriftResult, list[str]]] = []
    for w in worklist:
        if not w.drift_eligible:   # report-only claim: grounded/refuted still counts, drift does not
            continue
        vs = votes.get(w.claim, [])
        grounded = [v for v in vs if v.get("grounded") is True]
        if not vs or len(grounded) * 2 <= len(vs):   # no votes, or not a strict majority confirmed
            continue
        reported = [str(v.get("evidence", "")) for v in grounded if v.get("evidence")]
        d = anchor_drift(w.anchor, reported, tolerance)
        if d is not None and d.drifted:
            out.append((w, d, reported))
    return out


def drift_findings(worklist: list[WorkItem], grounding: list[dict],
                   tolerance: int) -> list[tuple[WorkItem, DriftResult]]:
    """(work-item, drift) for every CONFIRMED claim whose stored anchor drifts (the human report's
    view — evidence dropped)."""
    return [(w, d) for w, d, _ev in _confirmed_drifts(worklist, grounding, tolerance)]


def drift_records(worklist: list[WorkItem], grounding: list[dict], tolerance: int) -> list[dict]:
    """Machine-readable drift findings for `--json` and `fix apply-drift`: one dict per confirmed
    drifted claim with the corrected `path:line` already computed. `fix apply-drift` matches `claim`
    back to its edge and writes `corrected` into the map's `where`."""
    return [{
        "claim": w.claim,
        # The claim KIND, carried through so a consumer does not have to guess it back out of the
        # claim string. `fix apply-drift` can only rewrite two kinds; without this it fell through to
        # its security branch for everything else and told the operator that an entry-point cadence
        # claim "matches 0 security surfaces" — 17 times on one map.
        # NOT `drift_eligible`: `_confirmed_drifts` filters ineligible claims out before records are
        # built, so the field could only ever be `true` — dead payload on a public contract.
        "theme": w.theme,
        "stored": d.stored,
        "corrected": consensus_evidence(d.stored, ev),
        "same_file": d.same_file,
        "distance": d.distance,
    } for w, d, ev in _confirmed_drifts(worklist, grounding, tolerance)]


DRIFT_EXCEPTIONS_HEADING = "Drift exceptions"

#: A recorded line: ``anchor-drift `<the claim, verbatim>`: <why>``. The key is the WHOLE claim inside
#: backticks, not its leading id, and that is the entire point. Keying on the first `[A-Z]+\d+` looked
#: tidier and was a family escape in disguise: backbone claims read `C140 calls C78`, so `anchor-drift
#: C140` silenced every drift finding on every outgoing edge of C140 — reproduced at 3-for-1. The
#: sibling escape this is modelled on states the rule it broke: a recorded line "silences exactly one
#: (check, id) pair — never a family" (method.md). A `why` is required; a key alone is a dismissal.
#:
#: The delimiter is CAPTURED and back-referenced, and the key is `.+` rather than a "contains no
#: quote" class. The class was `[^`'\"]+`, so a key holding any quote character could not parse — and
#: every cadence claim is phrased ``runs on cadence '<x>'``, which made the whole cadence family
#: permanently un-recordable. It failed silently, too: a line that does not parse contributes no key,
#: `apply_drift_exceptions` early-returns on the empty set, and the "matched no finding" diagnostic
#: never runs, so the operator watched the row re-fire with nothing said about why. A live build
#: recorded two exceptions in the exact format the report prints, then had to read this file to find
#: out they could never work.
#:
#: The key is LAZY. It was greedy, reasoned as "binds the LAST delimiter that a `: <why>` follows, so
#: a key containing the delimiter still parses" — and that reasoning is what broke it, because a WHY
#: may contain the delimiter too. A live record read:
#:
#:   anchor-drift `Auth surface '…/public' is protected by: org_routes.py:271`: the stored anchor is
#:   right. Line 271 is `return {"exists": True, …}` — the statement that LIMITS what it discloses…
#:
#: Greedy bound the closing backtick of the code quote in the WHY (followed by ` — `, an accepted
#: separator), so the key swallowed 90 characters of prose, matched no finding, and `fix apply-drift`
#: then overwrote the very anchor the record existed to defend. The line PARSED, so the malformed
#: diagnostic stayed silent and three turns went into finding out why.
#:
#: Lazy takes the first delimiter followed by `: <why>`, which is the record's own shape. A key
#: containing the delimiter still parses — lazy backtracks FORWARD until the rest of the pattern
#: matches — so nothing the greedy form bought is lost. Verified against all seven records of a live
#: map (identical keys) and against the failing line above (only lazy recovers the true key).
#:
#: KNOWN RESIDUAL, deliberately not chased: a key holding the delimiter IMMEDIATELY followed by the
#: separator — ``anchor-drift `Entry point [cron] `refresh_tokens`: hourly sweep …`: verified.`` —
#: truncates at the inner backtick, and the line still parses, so it fails as silently as the bug
#: above. Narrowing the separator class to `:` alone was considered and rejected: it truncates that
#: same case identically (measured), so it buys nothing here, and over 444 real claims × 4 realistic
#: why-shapes BOTH lazy forms scored zero wrong keys. There is no regex that reads an unescaped,
#: unbalanced delimiter correctly. The real fix is for `apply_drift_exceptions` to report a recorded
#: key that matches no finding — which it already does — and for the reader to check that count.
_DRIFT_RECORD = re.compile(r"^\s*(?:[-*]\s+)?\**\s*anchor-drift\s+([`'\"])(.+?)\1\s*[:—-]\s*\S")

#: A line that opens like a record but does not parse. Reported, never skipped: a silently-dropped
#: exception is indistinguishable from one that matched nothing, which is how the bug above hid.
_DRIFT_RECORD_ATTEMPT = re.compile(r"^\s*(?:[-*]\s+)?\**\s*anchor-drift\b")


def drift_exceptions(m: ProjectModel) -> tuple[set[str], list[str]]:
    """`(recorded claim keys, lines that tried to be a record and failed to parse)`.

    Claims whose drift the operator has durably judged a false alarm, keyed by the claim itself.

    Drift was the one advisory family with no escape ANYWHERE. `validate`'s families each either
    name a recordable heading or sit in `tests/test_method_contract.KNOWN_NO_ESCAPE` with a stated
    reason ("always fixable at the point it fires"); drift is neither. It is genuinely a judgement
    call — the skeptics report a line, and the stored anchor can still be the right one when they
    read a sibling file — so "fix it" is not always the answer and there was nowhere to say so. On a
    live map a state-machine anchor was hand-verified, dismissed in chat, and shipped unrecorded,
    so the row will re-fire on every future run."""
    from coyodex import records
    out: set[str] = set()
    malformed: list[str] = []
    # The line ITERATION is shared (`records.lines`); the KEY shape is this family's own — a whole
    # quoted claim, not an id list — for the reason its regex note gives at length: keying on the
    # claim's leading id silenced every drift finding on every edge out of that element.
    for line in records.lines(m, DRIFT_EXCEPTIONS_HEADING):
        hit = _DRIFT_RECORD.match(line)
        if hit:
            out.add(hit.group(2))
        elif _DRIFT_RECORD_ATTEMPT.match(line):
            malformed.append(line.strip())
    return out, malformed


def _drift_key(claim: str) -> str:
    """The key a drift finding is recorded against: the claim itself, verbatim.

    Exact, so one recorded line answers exactly one finding. The report prints the key to copy, so
    the operator never has to derive it."""
    return claim.strip()


def apply_drift_exceptions(m: ProjectModel,
                           findings: list[tuple[WorkItem, DriftResult]],
                           ) -> tuple[list[tuple[WorkItem, DriftResult]], list[str]]:
    """Drop drift rows the operator recorded as ``anchor-drift `<claim>` `` — and say which.

    Drift is the one advisory family that named NO extras heading at all, so an operator who had
    read the code and judged the stored anchor correct had nowhere to write it down: the row
    re-fired on every future run. On a live map exactly this happened — a state-machine anchor was
    hand-verified, dismissed in chat, and shipped unrecorded."""
    recorded, malformed = drift_exceptions(m)
    # A malformed line is reported even when nothing else was recorded — the early return used to
    # swallow it, which is exactly how an un-parseable key looked identical to no key at all.
    if not recorded and not malformed:
        return findings, []
    kept: list[tuple[WorkItem, DriftResult]] = []
    silenced: list[str] = []
    for w, d in findings:
        key = _drift_key(w.claim)
        if key in recorded:
            silenced.append(key)
            continue
        kept.append((w, d))
    notes: list[str] = []
    if malformed:
        notes.append(f"{len(malformed)} line(s) under the '{DRIFT_EXCEPTIONS_HEADING}' heading open "
                     f"with `anchor-drift` but do not parse, so they silence NOTHING: "
                     f"{'; '.join(reporting.clip(ln, 60) for ln in malformed)}. The form is "
                     f"``anchor-drift `<the claim, verbatim>`: <why>`` — the claim inside a matched "
                     f"pair of delimiters, then a colon, then a non-empty why.")
    if silenced:
        notes.append(f"{len(silenced)} drift finding(s) suppressed by recorded exception(s) under a "
                     f"'{DRIFT_EXCEPTIONS_HEADING}' extras heading: "
                     f"{', '.join('anchor-drift `' + reporting.clip(k, 48) + '`' for k in sorted(silenced))}.")
    dead = sorted(k for k in recorded if k not in silenced)
    if dead:
        notes.append(f"{len(dead)} recorded drift exception(s) matched no finding: "
                     f"{', '.join('anchor-drift `' + reporting.clip(k, 48) + '`' for k in dead)} — the "
                     f"anchor was fixed or the claim changed. A line that silences nothing reads as a decision "
                     f"the operator never had to make.")
    return kept, notes


def _format(findings: list[tuple[WorkItem, DriftResult]], tolerance: int) -> str:
    if not findings:
        return f"anchor-drift: no drift among confirmed claims (tolerance={tolerance})."
    lines = [f"anchor-drift: {len(findings)} confirmed claim(s) whose `where` drifts "
             f"(tolerance={tolerance}) — fix each map `where`, the LLM only reported the line. Fix "
             f"it, or record ``anchor-drift `<the claim, verbatim>`: <why>`` under a "
             f"'{DRIFT_EXCEPTIONS_HEADING}' extras heading if the stored anchor is right:"]
    for w, d in findings:
        found = "a different file" if not d.same_file else f"line {d.reported} ({d.distance} off)"
        lines.append(f"  - {w.claim}: stored [{d.stored}] — skeptics found {found}")
    return "\n".join(lines)


def shape_findings(m: ProjectModel, roots: list[Path]) -> list[str]:
    """The verdicts-FREE drift pass: call-site anchors pointing at a line that cannot act.

    `--verdicts` mode needs a file only the Phase-4 skeptics produce, so a SERIAL build (no
    skeptics) could not run this check at all — and the lead then hand-scripted the corrections,
    which method.md explicitly forbids. This mode needs no verdicts and no LLM: it re-uses the
    same deterministic classifier `validate --check-sources` runs, so serial and parallel builds
    get the same floor. It finds SHAPE drift only (a `def` header can never be the acting line);
    finding the TRUE line still needs the skeptics."""
    return check_operative_lines_model(m, roots)


def load_verdicts(paths: list[str]) -> tuple[list[dict], list[str]]:
    """Every verdict row across every `--verdicts` file, plus notes about the input itself.

    `--verdicts` used to bind a SCALAR (`verdicts_path = argv[i]`), so passing the 13 per-batch
    files a themed Phase-4 fan-out produces read only the LAST one and reported a clean pass over
    9% of the evidence — while `finalize` printed that the leg had run. "The gate did not run" read
    exactly like "the gate passed", which is the one thing `finalize` exists to prevent. Accumulating
    is the fix; the notes below make the remaining hazard visible instead of silent.

    Overlap is REPORTED, never refused and never deduped. Two independent skeptics that agree on the
    same line are indistinguishable from one row seen twice — in a recorded mcpolis build,
    `verdicts1.json` and `verdicts1b.json` are two independent reads of one batch agreeing exactly on
    37 of 40 claims (they differ on three anchors, not on any verdict). Refusing would break that N-skeptic majority workflow; deduping would collapse a
    genuine 2-2 tie into 2-1 CONFIRMED (refutations carry no evidence line, so they collapse hardest).
    `_confirmed_drifts` documents why the real fix is a per-VOTE identity the verdicts format does
    not carry — a format change, not a tally change.

    A row may now carry a `skeptic` id, and that resolves the ambiguity at the source: two rows from
    DIFFERENT skeptics are two votes and are never a duplicate, while the same skeptic id arriving
    twice is the aggregate-plus-parts mistake. Without the field the old ambiguous note stands, but
    it no longer leads with the wrong diagnosis — the method PRESCRIBES a two-skeptic read of the
    security claims, so agreement between two files is the intended state, and a live build was told
    to "drop one" for doing exactly what it was asked to do."""
    rows: list[dict] = []
    seen: dict[tuple[str, object, str, str], str] = {}
    dupes: list[str] = []
    notes: list[str] = []
    any_skeptic_ids = False
    for p in paths:
        try:
            payload = json.loads(Path(p).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise SystemExit(f"ERROR: --verdicts {p} not found")
        except json.JSONDecodeError as e:
            raise SystemExit(f"ERROR: --verdicts {p} is not valid JSON ({e})")
        loaded = payload.get("grounding", []) if isinstance(payload, dict) else payload
        if not isinstance(loaded, list):
            raise SystemExit(f"ERROR: --verdicts {p}: `grounding` must be a list of verdict rows, "
                             f"got {type(loaded).__name__}")
        loaded = [r for r in loaded if isinstance(r, dict)]
        for r in loaded:
            skeptic = str(r.get("skeptic", ""))
            any_skeptic_ids = any_skeptic_ids or bool(skeptic)
            key = (str(r.get("claim", "")), r.get("grounded"), str(r.get("evidence", "")), skeptic)
            first = seen.get(key)
            if first is not None and first != p:
                dupes.append(f"{Path(first).name} + {Path(p).name}")
            else:
                seen.setdefault(key, p)
        rows.extend(loaded)
    if dupes and any_skeptic_ids:
        pairs = ", ".join(sorted(set(dupes)))
        notes.append(f"note: {len(dupes)} row(s) carry the SAME `skeptic` id in more than one input "
                     f"file ({pairs}) — that is one vote counted twice, not two skeptics agreeing. "
                     f"Drop the aggregate or drop its parts.")
    elif dupes:
        pairs = ", ".join(sorted(set(dupes)))
        notes.append(f"note: {len(dupes)} identical (claim, verdict, evidence) row(s) appear in more "
                     f"than one input file ({pairs}). Two readings, and the rows cannot tell them "
                     f"apart: independent skeptics agreeing (the method PRESCRIBES a double read of "
                     f"the security claims, so this is the intended state), or one aggregate passed "
                     f"alongside its own parts (a row counted twice can turn a tie into a majority). "
                     f"Give each row a `skeptic` id and this note answers itself.")
    return rows, notes


def coverage_note(worklist: list[WorkItem], grounding: list[dict]) -> str:
    """`challenged N of M` — the number that makes "the gate did not run" legible.

    Accumulation alone still passes silently when a build forgets one of thirteen files: a run over
    a third of the claims prints the same "no drift" line as a run over all of them. Naming the
    unvoted claims is what turns that into something an operator can see."""
    voted = {str(r.get("claim", "")) for r in grounding}
    missing = [w.claim for w in worklist if w.claim not in voted]
    head = f"challenged {len(worklist) - len(missing)} of {len(worklist)} worklist claim(s)"
    if not missing:
        return head + " — every claim has a verdict."
    return (f"{head} — {len(missing)} claim(s) have NO verdict and were not examined by this "
            f"pass: {reporting.shown([reporting.clip(c, 48) for c in missing], 5)}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex anchor-drift --map <map.json> [--verdicts <raw.json>]... "
              "[--repo <root>] [--tolerance N] [--json]\n\n"
              "Deterministic Layer-2 anchor-drift. WITH --verdicts: for each CONFIRMED claim, flag\n"
              "when the stored `where` differs from the line the skeptics found (feed `--json` into\n"
              "`coyodex fix apply-drift` to write the corrections). `--verdicts` is REPEATABLE and\n"
              "every file is read — pass the per-batch files directly, no hand-merge needed.\n"
              "WITHOUT --verdicts: the shape-only pass — call-site anchors pointing at a line that\n"
              "cannot be the acting statement (a `def` header, an import, a comment). Needs no\n"
              "skeptics, so a SERIAL build gets the same grounding floor as a parallel one.\n"
              "Informational (non-gating) either way.")
        return 0
    map_path = repo_root = None
    verdicts_paths: list[str] = []
    tolerance = _DEFAULT_TOLERANCE
    as_json = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True
        elif a in ("--map", "--verdicts", "--repo", "--tolerance"):
            i += 1
            if i >= len(argv):
                print(f"ERROR: {a} needs a value", file=sys.stderr)
                return 2
            if a == "--map":
                map_path = argv[i]
            elif a == "--verdicts":
                verdicts_paths.append(argv[i])
            elif a == "--tolerance":
                tolerance = int(argv[i])
            elif a == "--repo":
                repo_root = argv[i]   # only the shape-only pass reads code; verdicts mode ignores it
        else:
            print(f"ERROR: unknown argument '{a}'", file=sys.stderr)
            return 2
        i += 1
    if not map_path:
        print("ERROR: --map is required", file=sys.stderr)
        return 2
    m = load_model(Path(map_path).read_text(encoding="utf-8"))
    if not verdicts_paths:
        # No verdicts → the shape-only pass, so a serial build still gets a grounding floor.
        roots = _source_roots(Path(map_path).resolve(),
                              Path(repo_root).resolve() if repo_root else None)
        found = shape_findings(m, roots)
        if as_json:
            print(json.dumps({"mode": "shape-only", "findings": found}, indent=2))
        else:
            head = (f"Shape-only anchor drift ({len(found)} finding(s)) — no verdicts given.\n"
                    "Each anchor below points at a line that cannot be the acting statement.\n"
                    "Fix the `where` (or set no_call_site). For the TRUE call site, run the "
                    "Phase-4 skeptics and re-run with --verdicts.\n")
            print(head + "\n".join(f"  - {f}" for f in found) if found else
                  "Shape-only anchor drift: no findings — every call-site anchor points at a "
                  "line that can act.")
        return 0
    worklist = l2_worklist_model(m)
    grounding, notes = load_verdicts(verdicts_paths)
    coverage = coverage_note(worklist, grounding)
    if as_json:
        print(json.dumps({"findings": drift_records(worklist, grounding, tolerance),
                          "coverage": coverage, "notes": notes}, indent=2))
    else:
        for n in notes:
            # stderr: the build that motivated this ran `anchor-drift … | head -35`, and a warning
            # about the INPUT is exactly what a pipe must not eat.
            print(n, file=sys.stderr)
        print(coverage)
        kept, exc_notes = apply_drift_exceptions(m, drift_findings(worklist, grounding, tolerance))
        for n in exc_notes:
            print(n)
        print(_format(kept, tolerance))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
