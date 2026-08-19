#!/usr/bin/env python3
"""`coyodex finalize` — the pre-commit read: one command, one verdict, one durable record.

It runs `validate` (`--check-sources --check-coverage`), `audit`, both `anchor-drift` passes and —
when it is given verdicts — `grounding refutations`, and writes `.coyodex/finalize-report.{json,md}`.
It adds no check of its own; every finding here is one those commands already produce.

**It compares nothing against a previous map, deliberately.** An earlier version of this command did,
and that was wrong for the build: in real use a map EVOLVES INCREMENTALLY alongside the code, so a
from-scratch rebuild is a first-run event and there is usually no meaningful predecessor to diff
against. Rebuilding often is a coyodex-DEVELOPER habit, with its own `.coyodex/dev-rebuilds/NNNN/`
convention that users should not adopt — so baseline comparison belongs to the developer's
`/coyodex-retro`, which already does it (`eval/retro/method.md`), and not to anybody's build.

**It is a convenience wrapper, not an enforcement point.** Nothing makes a build run it, and in a
shell pipeline the exit status is the LAST command's — so `coyodex finalize | grep …` returns grep's
0. A live build wrote exactly that shape at the step this command occupies (`validate … | grep -E …;
audit … > /dev/null 2>&1`). A tool cannot fix that by exiting non-zero harder.

What it is actually for, then, is two properties the separate commands do not have:

1. **A record the build cannot erase.** The build above sent `audit` to `/dev/null`, then reported
   "gates clean" to the operator with four warnings and two advisories open. Findings are written to
   a FILE, with whole lists, so `> /dev/null`, `| tail -12` and a summary-from-memory all fail to
   hide them.
2. **An explicit answer to "did every check actually run".** Run the three commands by hand and a
   skipped one looks identical to a clean one. Here a leg that should have run and did not makes the
   verdict INCOMPLETE, which is not a pass and exits non-zero — because "the gate did not run" must
   never read as "the gate passed".

**Exit code.** 0 when nothing blocking was found and every leg ran; 1 for a blocking finding
(exactly what `validate` and `audit` already block on — a schema/reference problem, an L1
contradiction) or for INCOMPLETE. Unapplied anchor drift is reported, never gating: on the map this
came from, all 17 confirmed rows were entry-point cadence claims and `fix apply-drift` cannot apply
one of them, so gating on it would be a false failure with no remedy.

Stdlib-only (the cli.py dependency firewall).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from coyodex.model import ModelError, access_rules, load_model_path

#: Where the durable record goes, next to the map it describes.
REPORT_STEM = "finalize-report"


#: A leg's outcome. The split exists because the first version had none of it and got the most
#: important case wrong: a leg that DID NOT RUN contributed 0 blocking and 0 advisory, so a run whose
#: validate leg errored out (a typo'd `--repo` is enough) reported **CLEAN**, exit 0, on a map with a
#: dangling reference. A report that testifies a gate passed when the gate never ran is worse than no
#: report — it is the exact failure this whole command was written to stop.
RAN = "ran"        # the check executed and its findings are below
FAILED = "failed"  # the check should have run and did not — never reported as a pass


@dataclass
class Leg:
    """One check's outcome. `blocking` decides the exit code; `status` decides whether a verdict of
    CLEAN is even permitted."""

    name: str
    status: str
    blocking: list[str] = field(default_factory=list)
    advisory: list[str] = field(default_factory=list)
    note: str | None = None      # why it did not run, or a one-line summary of what it did

    @property
    def ran(self) -> bool:
        return self.status == RAN


@dataclass
class FinalizeReport:
    map_path: str
    map_sha256: str              # so a STALE report cannot be read as this map's result
    legs: list[Leg]
    verdict: str                 # BLOCKED | INCOMPLETE | ADVISORIES | CLEAN
    advisory_total: int
    blocking_total: int

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def _run_leg(name: str, argv: list[str]) -> tuple[int, str, str]:
    """Run one core subcommand IN THIS PROCESS, capturing its streams."""
    import io
    import contextlib
    out, err = io.StringIO(), io.StringIO()
    code = 2
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            if name == "validate":
                from coyodex import validate_model
                code = validate_model.main(argv)
            elif name == "audit":
                from coyodex import audit_model
                code = audit_model.main(argv)
            elif name == "anchor-drift":
                from coyodex import anchor_drift
                code = anchor_drift.main(argv)
            elif name == "balance":
                from coyodex import balance
                code = balance.main(argv)
            elif name == "grounding":
                from coyodex import grounding
                code = grounding.main(argv)
        except SystemExit as e:                       # a subcommand that argues with its own args
            # `sys.exit("msg")` carries a STRING, so int() would raise inside the handler.
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 2)
    return code, out.getvalue(), err.getvalue()


def _validate_leg(map_path: Path, repo: Path | None) -> Leg:
    argv = [str(map_path), "--check-sources", "--check-coverage", "--json"]
    if repo is not None:
        argv += ["--repo", str(repo)]
    code, out, err = _run_leg("validate", argv)
    try:
        payload = json.loads(out)
    except ValueError:
        return Leg("validate", FAILED, note=f"validate did not return JSON (exit {code}): "
                                               f"{(err or out).strip()[:200]}")
    return Leg("validate", RAN, blocking=list(payload.get("problems") or []),
               advisory=list(payload.get("warnings") or []),
               note=payload.get("checked") or None)


def _audit_leg(map_path: Path, verdicts: list[Path] | None = None) -> Leg:
    code, out, err = _run_leg("audit", [str(map_path), "--json"])
    try:
        payload = json.loads(out)
    except ValueError:
        return Leg("audit", FAILED, note=f"audit did not return JSON (exit {code}): "
                                            f"{(err or out).strip()[:200]}")
    findings = payload.get("findings") or []
    blocking = [f"{f.get('check')}: {f.get('location')} — {f.get('message')}"
                for f in findings if f.get("severity") == "CONTRADICTION"]
    advisory = [f"{f.get('check')}: {f.get('location')} — {f.get('message')}"
                for f in findings if f.get("severity") != "CONTRADICTION"]
    counts = payload.get("theme_counts") or {}
    live_claims = [str(w.get("claim", "")) for w in (payload.get("worklist") or [])
                   if isinstance(w, dict)]
    live_worklist = len(live_claims)
    note = (f"{live_worklist} L2 claims on the grounding worklist"
            + (f" ({', '.join(f'{k}:{v}' for k, v in counts.items())})" if counts else ""))
    stale = _stale_grounding_pin(map_path, live_claims, verdicts or [])
    if stale:
        advisory.append(stale)
    return Leg("audit", RAN, blocking=blocking, advisory=advisory, note=note)


def _recomputed_delta(g: dict, live: set[str], verdicts: list[Path]) -> str | None:
    """Check the record's two delta counts against the verdicts, when they are available.

    The digest proves the record describes THIS map's claim surface. It says nothing about whether
    `claims_superseded` and `claims_added_since` are true — a record can carry a valid digest beside
    two invented numbers, and every other check still passes. That is a poor property for the two
    fields whose only job is honesty.

    ONE-SIDED BOUNDS, not equality, and that distinction is the whole correctness argument. The
    first version demanded that the verdict set exactly match `claims_total`, on the reasoning that
    a partial set would accuse an honest record. True of an equality; false of a bound. For any
    partial set `P` of the true pinned set `T`, and live set `L`:

        P ⊆ T  ⇒  |P \\ L| ≤ |T \\ L|      so `claims_superseded` BELOW |P \\ L| is provably wrong
        P ⊆ T  ⇒  |L \\ P| ≥ |L \\ T|      so `claims_added_since` ABOVE |L \\ P| is provably wrong

    (Brute-forced over 200 000 random configurations: zero counterexamples.) Both hold whatever
    subset of the verdict files `finalize` was handed, so no honest record can be accused — and
    neither bound consults `claims_total`, which is what closes the three escapes the equality
    version left: raising the total by one, setting it to a digit STRING, and the lower-total
    bypass that an earlier commit patched one direction of.
    """
    if not verdicts:
        return None
    try:
        from coyodex.anchor_drift import load_verdicts
        rows, _notes = load_verdicts([str(v) for v in verdicts])
    except BaseException:
        # BaseException on purpose: `load_verdicts` raises SystemExit on a malformed file, which an
        # `except Exception` lets straight through a guard whose entire job is to stand down.
        return None
    pinned = {str(r.get("claim")) for r in rows if isinstance(r, dict) and r.get("claim")}
    if not pinned:
        return None
    at_least_superseded = len(pinned - live)
    at_most_added = len(live - pinned)
    got_superseded = g.get("claims_superseded", 0)
    got_added = g.get("claims_added_since", 0)
    wrong = []
    if isinstance(got_superseded, int) and got_superseded < at_least_superseded:
        wrong.append(f"`claims_superseded` says {got_superseded}, but the verdict files already "
                     f"name {at_least_superseded} pinned claim(s) this map no longer carries")
    if isinstance(got_added, int) and got_added > at_most_added:
        wrong.append(f"`claims_added_since` says {got_added}, but at most {at_most_added} live "
                     f"claim(s) can be new — the rest have verdicts")
    if not wrong:
        return None
    return ("grounding: the record's delta counts contradict the verdict files — "
            + "; ".join(wrong) + ". These are the numbers a reader uses to judge whether the "
            "superseded claims were the refuted ones, so a wrong count is worse than none. Re-run "
            "`coyodex grounding write --worklist <pinned.json> --map <this map> --verdicts <…>`.")


def _stale_grounding_pin(map_path: Path, live_claims: list[str],
                         verdicts: list[Path] | None = None) -> str | None:
    """The map's `grounding` record no longer describes the map's claim surface.

    `grounding write` PINS `claims_total` to the worklist the skeptics were given, and that pin is
    load-bearing: recomputing the split against the finished map yields `refuted 0`, because the
    claims a reconcile deletes are exactly the refuted ones. But reconciling a refutation rewrites
    its claim, so the pinned surface and the shipped one legitimately differ, and for a long time a
    build had no way to say so — the pinned record raised this advisory, re-running against a fresh
    worklist was REFUSED, and explaining it in `note` changed nothing. Three documented escapes, all
    closed. `grounding write --map` is the escape: it records the delta and a DIGEST of the live
    claim set.

    So the check is the digest, not the counts. `claims_total - claims_superseded +
    claims_added_since == live` is a tautology given the writer's own refusals (they force the vote
    set to equal the pinned set), so it closes for every input and proves nothing; and every
    size-based test is blind to a 1-for-1 rewrite, which is the shape a reconcile actually produces.
    A live build shipped `418 of 418 challenged` on a map whose worklist held 415, and quoted the
    418 in its commit message as fact — the digest is what makes that impossible to do silently.

    Falls back to the old count comparison when no digest is stored, so a record written without
    `--map`, or by an older build, behaves exactly as before."""
    try:
        doc = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    g = doc.get("grounding") if isinstance(doc, dict) else None
    if not isinstance(g, dict):
        return None
    # Both sides over the DE-DUPLICATED claim set: `build_record` de-duplicates the pinned side, and
    # two sides counted by different rules measure the rule rather than the map.
    live_set = set(live_claims)
    stored_digest = g.get("live_claims_digest")
    pinned_raw = g.get("claims_total")
    pinned = pinned_raw if isinstance(pinned_raw, int) and pinned_raw > 0 else 0

    # THE DIGEST IS CHECKED FIRST, and never gated on `claims_total`. It used to sit behind an early
    # return for a missing or nonsensical total, so a record could buy silence by CORRUPTING that
    # field: `claims_total` of 0, of -5, or of the string "446" all skipped the digest comparison
    # entirely, even when the digest was provably a different map's. Corrupting a field must never be
    # safer than filling it in — that is the same shape as the bypass fixed one commit earlier, and
    # this is the third time it has appeared in this file's history.
    if isinstance(stored_digest, str) and stored_digest:
        from coyodex.grounding import live_claims_digest
        if live_claims_digest(live_set) == stored_digest:
            # The surface matches. The COUNTS beside it are still unverified — check them when the
            # verdicts are at hand, because a valid digest and two invented numbers coexist happily.
            return _recomputed_delta(g, live_set, verdicts or [])
        superseded = g.get("claims_superseded", 0)
        added = g.get("claims_added_since", 0)
        return (f"grounding: the record's `live_claims_digest` does not match this map's claim "
                f"surface. It was written against a map with {pinned} pinned claim(s), "
                f"{superseded} superseded and {added} added since the pin; this map's audit "
                f"worklist holds {len(live_set)}. Something changed the claims AFTER "
                f"`grounding write` ran — re-run it as the last step before the final assemble:\n"
                f"  coyodex grounding write --worklist <pinned.json> --map {map_path} "
                f"--verdicts <…> --out .coyodex/build-fragments/grounding.json")
    if not pinned:
        # No digest AND no usable `claims_total`: there is nothing here to compare. `validate` owns
        # the malformed-record complaint (negative counts, a split that does not add up); this
        # command reports staleness, and a record with no total is not stale, it is unfinished.
        return None
    if pinned == len(live_set):
        # Counts agree — which proves nothing. A 1-for-1 rewrite (the shape a reconcile actually
        # produces) leaves the count untouched, so this branch is silent EXACTLY where the digest
        # was needed. Say the record cannot be checked, rather than implying it passed.
        return (f"grounding: the record carries no `live_claims_digest`, so nothing here can confirm "
                f"it describes THIS map. The counts agree ({pinned}), but a reconcile that rewrites "
                f"a claim leaves the count unchanged, so agreement is not evidence. Re-run "
                f"`coyodex grounding write --worklist <pinned.json> --map <this map> --verdicts <…>` "
                f"as the last step before the final assemble.")
    return (f"grounding: the record is pinned to a worklist of {pinned} claim(s), but this map's "
            f"audit worklist holds {len(live_set)} — and the record does not say why. Reconciling a "
            f"refutation rewrites its claim, so the two legitimately differ; record the delta with "
            f"`coyodex grounding write --worklist <pinned.json> --map <this map> --verdicts <…>`, "
            f"which stores how many claims were superseded and added and a digest of the live "
            f"surface. Do NOT re-pin against a fresh worklist: the claims a reconcile deletes are "
            f"the refuted ones, so that records `refuted 0`.")


def _drift_leg(map_path: Path, repo: Path, verdicts: list[Path]) -> Leg:
    argv = ["--map", str(map_path), "--repo", str(repo)]
    for v in verdicts:
        argv += ["--verdicts", str(v)]
    code, out, err = _run_leg("anchor-drift", argv)
    text = (out or "") + (err or "")
    rows = [ln.strip()[2:] for ln in text.splitlines() if ln.startswith("  - ")]
    kind = "verdict-based" if verdicts else "shape-only"
    # Carry the COVERAGE line into the report and the gate block. Without it the leg printed
    # "no drifted anchors" off a pass that had seen 31 of 404 claims — the same "the gate did not
    # run reads as the gate passed" sentence this whole command exists to make impossible, in the
    # one artifact meant to be quotable.
    coverage = next((ln.strip().split(" — ")[0] for ln in text.splitlines()
                     if ln.startswith("challenged ")), "")
    # ADVISORY on purpose: `fix apply-drift` handles edge and security anchors only, so on the map
    # this command was written for all 17 confirmed rows were entry-point cadence claims it cannot
    # apply. A gate on a finding with no remedy is a false failure.
    return Leg(f"anchor-drift ({kind})", RAN if code in (0, 1) else FAILED, advisory=rows,
               note=((f"{len(rows)} drifted anchor(s) — reconcile each (fix the `where`, or record "
                      f"why it stands); `fix apply-drift` covers edge + security anchors only"
                      if rows else "no drifted anchors")
                     + (f" · {coverage}" if coverage else "")))


def _refutations_leg(map_path: Path, verdicts: list[Path]) -> Leg:
    """`grounding refutations` — does the shipped map still assert what its own skeptics disproved?

    BLOCKING, unlike anchor drift, and the difference is whether a remedy exists. A drifted anchor
    can be one `fix apply-drift` cannot apply, so gating on it is a false failure with no way out.
    A surviving refutation always has one: correct the claim or drop the row, which is what the
    build contract already requires of every refutation. Until this leg existed nothing looked: a
    live map shipped two refuted edges while this very report said 0 blocking and never used the
    word "refuted", because `validate` reads shape, `audit` reads the map against itself, and the
    `grounding` record reduces the pass to four numbers in which a refutation that was reconciled
    and one that was ignored are the same integer."""
    argv = ["refutations", "--map", str(map_path), "--json"]
    for v in verdicts:
        argv += ["--verdicts", str(v)]
    code, out, err = _run_leg("grounding", argv)
    try:
        payload = json.loads(out)
    except ValueError:
        return Leg("grounding refutations", FAILED,
                   note=f"it did not return JSON (exit {code}): {(err or out).strip()[:200]}")
    surviving = list(payload.get("surviving_refutations") or [])
    stated = list(payload.get("stated_but_unchallenged") or [])
    blocking = [f"{s['claim']} — REFUTED by {s['refuted_by']} skeptic(s) and still in the map, "
                f"unchanged. Correct the claim or drop the row; a reconciled refutation no longer "
                f"resolves here." + (f" Skeptic: {s['note'][:300]}" if s.get("note") else "")
                for s in surviving]
    # ONE advisory line, not one per element. A live map produced 81 of these, and an advisory in
    # this report is contractually "fixed or recorded under the heading its message names" — 81 rows
    # with no heading to record them under is not a finding, it is noise that pushes the ten real
    # advisories off the top. The count is the finding; `by-element` is where the list lives.
    kinds: dict[str, int] = {}
    for e in stated:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    advisory = ([f"{len(stated)} element(s) state a confidence the grounding pass does not support "
                 f"({', '.join(f'{n} {k}' for k, n in sorted(kinds.items()))}). Nothing writes "
                 f"`confidence`, so the label and the votes come from different processes and this "
                 f"is the only place they meet. Run `coyodex grounding by-element --map <this map> "
                 f"--worklist <pinned.json> --verdicts <…>` for the list, then either challenge the "
                 f"elements or say `inferred` where nobody looked."]
                if stated else [])
    return Leg("grounding refutations", RAN if code in (0, 1) else FAILED,
               blocking=blocking, advisory=advisory,
               note=(f"{len(surviving)} refuted claim(s) still in the map, "
                     f"{len(stated)} element(s) stating a confidence the pass does not support"))


#: Where a build keeps the skeptics' verdicts. `finalize` looks here when it was given none, so it
#: can say that a leg it CAN run was not asked for.
_VERDICTS_GLOB = "verify/verdicts-*.json"


def _unasked_verdicts(map_path: Path, verdicts: list[Path]) -> list[Path]:
    """Verdict files sitting beside the map that this run was not given.

    A build ran `finalize … --verdicts <30 files>`, then re-ran it with `--emit-gate-block` and NO
    `--verdicts` purely to emit the block. The second run overwrote the report, so what shipped and
    what the commit message quoted had only the shape-only anchor-drift leg — losing the
    verdict-based leg and, with it, the `challenged N of M worklist claim(s)` coverage line whose
    whole job is to stop "the gate did not run" reading as "the gate passed".

    This cannot be an INCOMPLETE: that verdict is for a leg that FAILED, and a leg nobody asked for
    did not fail. So it is reported as a leg in its own right — visible in the report, in the gate
    block and on stdout — which is the thing the silent version did not do."""
    if verdicts:
        return []
    return sorted(map_path.parent.glob(_VERDICTS_GLOB))


def _unasked_verdicts_leg(found: list[Path]) -> Leg:
    names = ", ".join(p.name for p in found[:3]) + (" …" if len(found) > 3 else "")
    return Leg(name="anchor-drift (verdict-based)", status=RAN, blocking=[], advisory=[
        f"NOT RUN — {len(found)} verdict file(s) sit beside this map ({names}) and this run was "
        f"given none, so the verdict-based anchor-drift leg and its coverage attestation are "
        f"missing from this report. Re-run with `--verdicts <file>` per file; `--verdicts` and "
        f"`--emit-gate-block` combine in ONE invocation."],
               note="the leg was skipped because no --verdicts was passed")


def _balance_leg(map_path: Path) -> Leg:
    """Phase 3.5 left a trace, or it did not happen.

    `method.md` puts a `coyodex balance` pass after the trace and says to reconcile each finding.
    Nothing observed it, so a skipped Phase 3.5 and a passed one read the same: one build ran
    `balance` three times, the next ran it ZERO times, and the only reason nobody noticed is that
    `validate` happened to emit no balance warning. Running it here means the report always says
    what the grouping looks like against the real graph.

    INFORMATIONAL, never advisory and never blocking. `method.md` is explicit that "balance never
    gates and only ever re-groups" — grouping is a free, view-only choice — so a balance finding
    must not move this command's verdict. The leg exists to record the fact, not to add a gate.
    """
    code, out, err = _run_leg("balance", [str(map_path)])
    text = (out or "") + (err or "")
    findings = [ln.strip()[2:] for ln in text.splitlines() if ln.startswith("  - ")]
    if code not in (0, 1):
        return Leg("balance (informational)", FAILED,
                   note="balance could not run, so Phase 3.5 has no trace in this report")
    return Leg("balance (informational)", RAN,
               note=(f"{len(findings)} balance finding(s) — apply a Drilling-deeper operation, or "
                     f"record a why under 'Balance exceptions'; this never gates"
                     if findings else "no balance findings — every diagram reads at target density")
                    + " (informational: grouping is a view-only choice, method.md)")


def build_report(map_path: Path, repo: Path, verdicts: list[Path]) -> FinalizeReport:
    unasked = _unasked_verdicts(map_path, verdicts)
    legs = [
        _validate_leg(map_path, repo),
        _audit_leg(map_path, verdicts),
        _drift_leg(map_path, repo, []),
        *([_drift_leg(map_path, repo, verdicts)] if verdicts else []),
        *([_refutations_leg(map_path, verdicts)] if verdicts else []),
        *([_unasked_verdicts_leg(unasked)] if unasked else []),
        _balance_leg(map_path),
    ]
    blocking = sum(len(l.blocking) for l in legs)
    advisory = sum(len(l.advisory) for l in legs)
    failed = [l for l in legs if l.status == FAILED]
    # ORDER MATTERS, and CLEAN is the narrowest case on purpose: a leg that FAILED means this run does
    # not know whether the map is clean, so it must never say that it is.
    if blocking:
        verdict = "BLOCKED"
    elif failed:
        verdict = "INCOMPLETE"
    elif advisory:
        verdict = "ADVISORIES"
    else:
        verdict = "CLEAN"
    return FinalizeReport(map_path=str(map_path),
                          map_sha256=hashlib.sha256(map_path.read_bytes()).hexdigest(),
                          legs=legs, verdict=verdict,
                          advisory_total=advisory, blocking_total=blocking)


def format_report(r: FinalizeReport) -> str:
    out: list[str] = [f"# coyodex finalize — {r.map_path}", ""]
    out.append(f"**Verdict: {r.verdict}** — {r.blocking_total} blocking, "
               f"{r.advisory_total} advisory.")
    out.append("")
    out.append(f"Map sha256 `{r.map_sha256}` — if this does not match the map you are looking at, this "
               f"report is STALE and describes a different file.")
    unran = [l for l in r.legs if l.status != RAN]
    if unran:
        out.append("")
        out.append("**Checks that did not run** — their silence is not a pass:")
        for l in unran:
            out.append(f"- {l.name} ({l.status}): {l.note}")
    out.append("")
    out.append("An ADVISORY is not a pass. Each one is either fixed or recorded under the extras "
               "heading its message names; \"gates clean\" may only be claimed when this file says "
               "CLEAN.")
    out.append("")
    disp = advisory_disposition(Path(r.map_path), r)
    if disp:
        counts: dict[str, int] = {}
        for d, _h, _a in disp:
            counts[d] = counts.get(d, 0) + 1
        out.append("## Advisory disposition")
        out.append("Each advisory, against what the map actually records. "
                   + " · ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
        out.append("")
        for d, h, a in disp:
            tag = f"**{d}**" if d in ("UNRECORDED", "UNSURE") else d
            out.append(f"- {tag}{f' [{h}]' if h else ''} — {a}")
        out.append("")
        # The UNRECORDED rows are the ones asking to be written, so name the writer beside them.
        # See the same footer in `validate`: sixty advisory strings name a heading and none names
        # the command, and a measured build hand-appended every record instead.
        if any(d in ("UNRECORDED", "UNSURE") for d, _, _ in disp):
            out.append("Write the missing records with `coyodex record --map <the FRAGMENT that "
                       "owns extras> --heading \"<heading>\" --line \"<key>: <why>\"` — it "
                       "shape-checks each line, so one that would silence nothing is refused "
                       "rather than stored. Re-run `finalize` after, never before: records written "
                       "against an earlier run's findings go stale the moment anything is fixed.")
            out.append("")
    for leg in r.legs:
        out.append(f"## {leg.name}")
        if not leg.ran:
            out.append(f"DID NOT RUN ({leg.status}) — {leg.note}")
            out.append("")
            continue
        if leg.note:
            out.append(f"_{leg.note}_")
        for b in leg.blocking:
            out.append(f"- BLOCKING: {b}")
        for a in leg.advisory:
            out.append(f"- advisory: {a}")
        if not leg.blocking and not leg.advisory:
            out.append("- nothing found")
        out.append("")
    return "\n".join(out)


def _shape_line(map_path: Path) -> str:
    """The map's own counts, for the commit message, read from the map the gate block hashes.

    A live commit claimed "416 backbone edges … 33 flows/sub-flows" for a map holding 365 and 36.
    Neither number was invented: both were true earlier in the build, and `fix dedup-edge` dropped
    49 duplicate occurrences after they were written down. Hand-copied shape numbers describe
    whatever state the author last looked at, and the commit message is the artifact a future
    reader trusts most, so these are generated from the same file the sha is taken over."""
    try:
        from coyodex.model import load_model
        m = load_model(map_path.read_text(encoding="utf-8"))
    except Exception as e:
        # NOT a silent None. A gate block that quietly omits the shape sends the author straight
        # back to hand-writing the numbers, which is the defect this line exists to remove.
        return f"Shape: UNAVAILABLE — could not re-read {map_path}: {e}"
    flows = len(m.flows) + len(m.subflows)
    return (f"Shape: {len(m.components)} components in {len(m.subsystems)} subsystems, "
            f"{len(m.entities)} entities in {len(m.subdomains)} subdomains, {len(m.deps)} deps, "
            f"{len(m.use_cases)} use cases, {len(m.edges)} edges, {flows} flows/sub-flows, "
            f"{len(m.entry_points)} entry points, {len(m.rules)} business rules in "
            f"{len(m.blocks)} blocks"
            # The access surface is part of the shape a commit states. It was invisible here for the
            # same reason it was invisible in validate's inventory: the only mention of auth was
            # gated on `security[]`, which the fold empties.
            + (f" ({len(access_rules(m))} access)" if access_rules(m) else "")
            + (f", {len(m.security)} LEGACY security rows" if m.security else "") + ".")


def _grounding_line(map_path: Path) -> str:
    """The map's grounding counts, so the commit cannot quote a friendlier number than the gate.

    A live commit said "all 446 L2 claims challenged" while the gate block it was pasted beside
    said `challenged 440 of 444`. Both came out of the same build minutes apart; the one a reader
    sees forever was the flattering one. Emitting it here removes the choice.

    NAMING THE SURFACE is the second half of that, and it was missing. This line used to say "from
    the map" and quote the PINNED counts, so one commit carries "209 of 209 claim(s) challenged"
    four lines below this same report's "challenged 199 of 209 worklist claim(s)". Both were true —
    209 counts the worklist the skeptics were given, 199 counts the claims the shipped map actually
    carries — and nothing said they measure different sets. The pinned figure stays first, because
    it is what the skeptics did; the live figure follows whenever it disagrees."""
    try:
        from coyodex.model import load_model
        g = load_model(map_path.read_text(encoding="utf-8")).grounding
    except Exception as e:
        return f"Grounding: UNAVAILABLE — could not re-read {map_path}: {e}"
    if g is None:
        return "Grounding: NO RECORD — nothing in this map says what was challenged."
    line = (f"Grounding (pinned worklist): {g.claims_challenged} of {g.claims_total} claim(s) "
            f"challenged — {g.claims_confirmed} confirmed, {g.claims_refuted} refuted, "
            f"{g.claims_unverifiable} unverifiable.")
    live_total = g.claims_total - g.claims_superseded + g.claims_added_since
    if g.claims_live_challenged and g.claims_live_challenged < live_total:
        line += (f"\nGrounding (shipped map): {g.claims_live_challenged} of {live_total} claim(s) "
                 f"have a verdict — {live_total - g.claims_live_challenged} were minted after the "
                 f"worklist was pinned, so no skeptic saw them.")
    elif not g.claims_live_challenged and g.claims_added_since:
        line += (f"\nGrounding (shipped map): at least {g.claims_added_since} claim(s) have NO "
                 f"verdict — minted after the worklist was pinned. This record predates "
                 f"`claims_live_challenged`, so that is a lower bound.")
    return line


#: Ids an advisory names, for matching against what the map recorded.
#:
#: A CANDIDATE id — the shape only. Shape alone cannot settle it: `S3` in "stores artifacts in S3",
#: `C4` in "the C4 container view" (this tool's own vocabulary) and `D3` in "the D3 chart library"
#: are all well-formed ids and none of them is one. So candidates are intersected with the ids the
#: map actually DEFINES, below, which is decisive and free — the model is already loaded.
#:
#: A false id is not cosmetic: it can collide with something the map really did record and flip a
#: genuine unrecorded gap to `recorded`, the one direction this table must never fail in.
#: `EP` is included because entry-point ids are in the records vocabulary and were missing, so an
#: advisory naming only those fell through to the id-less branch.
_ADVISORY_IDS = re.compile(
    r"(?<![A-Za-z0-9])((?:UC|CAP|BLK|SD|SF|EP|HP|BR|C|D|E|R|S)\d+)(?![A-Za-z0-9])")


#: An advisory that REPORTS suppression rather than asking for it. These name a heading and quote
#: the very keys recorded under it, so any "is this recorded?" test answers yes — and the answer is
#: meaningless: they exist BECAUSE something was recorded. Marking them `recorded` filed the whole
#: "a recorded gap is still a gap" family under "handled", which cancelled the disclosure outright.
_DISCLOSURE = re.compile(
    r"suppressed by (?:a )?recorded|counted as (?:CLAIMED|SWEPT)|and NOT re-nudged|"
    r"is NOT re-reported above", re.I)


def advisory_disposition(map_path: Path, report: FinalizeReport) -> list[tuple[str, str, str]]:
    """(disposition, heading-or-'', advisory) for every advisory the gates raised.

    `finalize` already SAYS "each one is either fixed or recorded under the extras heading its
    message names", and then checked nothing — so nine advisories shipped on one map neither fixed
    nor recorded, and no transcript could show it because every read of the list had been narrowed
    by a grep. Both halves are here already: the advisory list, and the map.

    Four dispositions, and the design rule is that **the table never says `recorded` unless it can
    name the key that records it**. The first draft did the opposite — it defaulted to `recorded`
    whenever a heading existed and the advisory carried no id — and so reported "recorded" for an
    advisory whose own text reads "and no granularity record". That is the exact failure this
    function exists to catch, committed by the function itself.

    - `recorded` — the key this advisory is about is present under the heading it names.
    - `UNRECORDED` — the key is absent, and both halves of the key are known, so absence is a fact.
    - `UNSURE` — the heading keys on free text (a path, a bucket name) and this advisory carries no
      id, so the pairing cannot be decided here. Say so; do not guess either way.
    - `disclosure` — the advisory reports what a record silenced. Asking whether it is recorded is
      a category error.
    - `carried (no escape)` — names no heading; can only be fixed."""
    from coyodex import records
    from coyodex.assemble import load_map_or_fragment
    try:
        m, _present = load_map_or_fragment(map_path)
    except Exception:
        return []
    # The id universe: nothing outside it is an id, whatever it looks like.
    from coyodex.model import all_elements
    defined = set(all_elements(m)) | {g.id for g in m.happy_path} | {
        ep.id for ep in m.entry_points if ep.id}
    out: list[tuple[str, str, str]] = []
    for leg in report.legs:
        for a in leg.advisory:
            low = a.lower()
            heading = next((h for h in records.KNOWN_HEADINGS if h.lower() in low), "")
            if _DISCLOSURE.search(a):
                out.append(("disclosure", heading, a))
                continue
            if not heading:
                out.append(("carried (no escape)", "", a))
                continue
            ids = set(_ADVISORY_IDS.findall(a)) & defined
            if heading.lower() == "audit exceptions":
                # PAIRS, not ids. Reading every id under this heading marked a `flow-title UC25`
                # advisory "recorded" on the strength of an unrelated `actor-attribution UC25`
                # line — the family-vs-pair error the heading exists to prevent.
                from coyodex.audit_model import audit_exceptions
                check = a.split(":", 1)[0].strip().lower()
                if ids and check.replace("-", "").isalpha():
                    recorded = {eid for c, eid in audit_exceptions(m) if c.lower() == check}
                    out.append(("recorded" if ids & recorded else "UNRECORDED", heading, a))
                else:
                    out.append(("UNSURE", heading, a))
                continue
            recorded = records.recorded_keys(m, heading)
            if not ids:
                # Free-text key, or an advisory that names none. UNDECIDABLE here — and it must not
                # fall through to `recorded`, which is how "no granularity record" got filed as
                # recorded beside a heading holding unrelated lines.
                out.append(("UNSURE", heading, a))
            elif ids & recorded:
                out.append(("recorded", heading, a))
            else:
                out.append(("UNRECORDED", heading, a))
    return out


def gate_block(report: FinalizeReport, map_sha: str) -> str:
    """A copy-pasteable gate summary for the COMMIT MESSAGE, generated from the report.

    A live build read its own report, quoted the verdict honestly in chat ("that is not a clean
    pass"), and then wrote `validate … clean (1166 anchors resolved), audit reports no
    self-contradiction, anchor-drift clean` into the commit — three false clauses, with an anchor
    count copied from a validate run 32 minutes earlier. Chat is ephemeral; the commit is
    the only record a future reader sees. So the durable half must be generated, not remembered.

    That covers the VERDICT. The two other things a commit reliably gets wrong are the map's shape
    and its grounding coverage, for the same reason and with the same fix — see `_shape_line` and
    `_grounding_line`."""
    lines = [f"Gates: finalize {report.verdict} — {report.blocking_total} blocking, "
             f"{report.advisory_total} advisory (map sha256 {map_sha[:12]}…)."]
    for leg in report.legs:
        if not leg.ran:
            lines.append(f"  {leg.name}: DID NOT RUN ({leg.status})")
            continue
        counts = f"{len(leg.blocking)} blocking, {len(leg.advisory)} advisory"
        lines.append(f"  {leg.name}: {counts}" + (f" — {leg.note}" if leg.note else ""))
    if report.advisory_total:
        lines.append("Advisories are NOT a pass. Some name an extras heading and can be recorded; "
                     "the rest name none (tests/test_method_contract.py KNOWN_NO_ESCAPE) and can only "
                     "be fixed or carried. State which of the two you did — neither is 'clean'.")
    for extra in (_shape_line(Path(report.map_path)), _grounding_line(Path(report.map_path))):
        if extra:
            lines.append(extra)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex finalize [--repo <root>] [--verdicts <file>]... "
              "[--emit-gate-block <file>] "
              "[.coyodex/project-map.json]\n\n"
              "The pre-commit read: validate (--check-sources --check-coverage) + audit +\n"
              "anchor-drift (shape-only, and verdict-based when --verdicts is given). Writes\n"
              ".coyodex/finalize-report.{json,md} and prints one verdict line. It adds no check of\n"
              "its own, and it compares nothing against a previous map — a map evolves with the\n"
              "code, so a build has no predecessor to diff against.\n\n"
              "A CONVENIENCE WRAPPER, not an enforcement point: exit 1 for what validate and audit\n"
              "already block on (schema/reference problems, L1 contradictions), or when a leg that\n"
              "should have run did not (INCOMPLETE — never reported as a pass). Unapplied anchor\n"
              "drift is reported, never gating: apply-drift cannot fix an entry-point cadence\n"
              "anchor, so gating on it would fail a build that has no remedy.\n\n"
              "Read the REPORT FILE, not this stdout: a file survives `> /dev/null` and `| tail`,\n"
              "and it carries whole lists with no `+N more`.")
        return 0
    repo: Path | None = None
    verdicts: list[Path] = []
    gate_block_path: Path | None = None
    positional: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--emit-gate-block":
            i += 1
            if i >= len(argv):
                print("ERROR: --emit-gate-block needs a value", file=sys.stderr)
                return 2
            gate_block_path = Path(argv[i])
        elif a in ("--repo", "--verdicts"):
            i += 1
            if i >= len(argv):
                print(f"ERROR: {a} needs a path", file=sys.stderr)
                return 2
            if a == "--repo":
                repo = Path(argv[i])
            else:
                # VARIADIC, exactly as `grounding` had to become: swallow every following non-flag
                # path. It took one value per flag, so the natural `--verdicts verify/verdicts-*.json`
                # handed it ONE file and let the shell's other nineteen fall through to `positional`,
                # where they were silently ignored — the report then described a pass over one batch
                # as the whole pass. `grounding` failed loudly on the same spelling (`unknown
                # option(s)`); here it failed silently, which is the worse half of the same bug and
                # the one this command exists to make impossible.
                verdicts.append(Path(argv[i]))
                while i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                    i += 1
                    verdicts.append(Path(argv[i]))
        elif a.startswith("-"):
            print(f"ERROR: unknown option '{a}'", file=sys.stderr)
            return 2
        else:
            positional.append(a)
        i += 1
    if len(positional) > 1:
        # One map per run. An extra bare path is a mis-typed option, and swallowing it is how the
        # `--verdicts` glob above went unnoticed for so long: the files landed here and nothing said
        # a word about them.
        print(f"ERROR: finalize takes ONE map path; got {len(positional)} "
              f"({', '.join(positional[:4])}{' …' if len(positional) > 4 else ''}). Pass verdict "
              f"files after --verdicts.", file=sys.stderr)
        return 2
    map_path = Path(positional[0] if positional else ".coyodex/project-map.json")
    if not map_path.exists():
        print(f"ERROR: {map_path} not found", file=sys.stderr)
        return 1
    for v in verdicts:
        if not v.exists():
            print(f"ERROR: --verdicts {v} not found", file=sys.stderr)
            return 1
    if repo is None:
        repo = map_path.resolve().parent.parent
    try:
        load_model_path(map_path)          # fail fast and legibly, before any leg runs
    except ModelError as e:
        print(f"ERROR: {map_path} is not a loadable map: {e}", file=sys.stderr)
        return 1
    # No `set_full_lists` here: every leg that renders a list goes through a `--json` subcommand, and
    # each of those sets and RESETS the mode itself — so a flag set here was cleared by the first leg
    # and did nothing. Whole lists come from the legs' own JSON, which is the honest mechanism.
    report = build_report(map_path, repo, verdicts)
    json_path = map_path.parent / f"{REPORT_STEM}.json"
    md_path = map_path.parent / f"{REPORT_STEM}.md"
    json_path.write_text(report.to_json(), encoding="utf-8")
    md_path.write_text(format_report(report), encoding="utf-8")
    if gate_block_path is not None:
        import hashlib
        sha = hashlib.sha256(map_path.read_bytes()).hexdigest()
        gate_block_path.parent.mkdir(parents=True, exist_ok=True)
        gate_block_path.write_text(gate_block(report, sha) + "\n", encoding="utf-8")
        print(f"finalize: wrote the commit-message gate block to {gate_block_path}")
    # The four artifacts the method says ship with the map, and whether git will actually take them.
    # A live build ran `git check-ignore`, GOT the answer (`.gitignore:85:.coyodex/`), and then issued
    # an un-forced `git add` two turns later that failed — shipping a map whose viewer symbol-search
    # input (`preindex.json`) and provenance were left untracked. Naming the command removes the step
    # where the operator has to remember the `-f`.
    required = [map_path, map_path.with_suffix(".md"),
                map_path.parent / "preindex.json", map_path.parent / "provenance.json"]
    present = [p for p in required if p.exists()]
    missing = [p for p in required if not p.exists()]
    if present:
        print("finalize: commit these with the map — "
              f"git add -f {' '.join(str(p) for p in present)}\n"
              "  (`-f` because a repo whose root .gitignore ignores `.coyodex/` refuses a plain "
              "`git add`, and method.md requires the pre-index and provenance to ship with the map.)")
    if missing:
        # NAME what is absent instead of quietly dropping it from the command. The filter above is
        # right — `git add` on a non-existent path fails — but printing the survivors alone turns a
        # missing artifact into a shorter, still-copyable line. A live build ran finalize before
        # stamping provenance, and the hint it printed would have committed the map WITHOUT it: the
        # exact omission the hint exists to prevent. The operator caught it by hand.
        # NAME THE COMMAND for each, too. Telling a build to "produce them" without saying how
        # cost a live run two extra finalize rounds: it re-ran finalize unchanged, got the identical
        # complaint, and only then went hunting — provenance was, at the time, produced by a script
        # in the coyodex clone that the shipped CLI does not install. It is `coyodex provenance
        # stamp` now, and the hint says so.
        how = {"provenance.json": "coyodex provenance stamp .",
               "preindex.json": "coyodex preindex . --report"}
        print(f"finalize: NOT in that command, because {'it does' if len(missing) == 1 else 'they do'}"
              f" not exist yet — {', '.join(str(p) for p in missing)}. method.md requires the "
              f"pre-index and provenance to ship WITH the map; produce them and re-run finalize "
              f"rather than committing the shorter line above.")
        for p_missing in missing:
            cmd = how.get(p_missing.name)
            if cmd:
                print(f"  {p_missing.name}: {cmd}")
    unran = [f"{l.name} ({l.status})" for l in report.legs if not l.ran]
    print(f"finalize: {report.verdict} — {report.blocking_total} blocking, "
          f"{report.advisory_total} advisory"
          + (f"; DID NOT RUN: {', '.join(unran)}" if unran else "")
          + f". Full findings: {md_path}")
    if report.verdict == "INCOMPLETE":
        print("finalize: INCOMPLETE — a check that should have run did not, so this run does NOT know "
              "whether the map is clean. Fix the cause above and re-run; do not read the absence of "
              "findings as their absence.", file=sys.stderr)
    if report.verdict == "ADVISORIES":
        print("finalize: advisories are not a pass — fix each one or record it under the extras "
              "heading its message names. Quote THIS verdict line when reporting the gates; a build "
              "that says \"gates clean\" with advisories open is the failure this command exists for.",
              file=sys.stderr)
    # INCOMPLETE exits non-zero too: "the gate did not run" must not read as "the gate passed".
    return 1 if (report.blocking_total or report.verdict == "INCOMPLETE") else 0


if __name__ == "__main__":
    raise SystemExit(main())
