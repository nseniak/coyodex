#!/usr/bin/env python3
"""`coyodex finalize` — the pre-commit read: one command, one verdict, one durable record.

It runs `validate` (`--check-sources --check-coverage`), `audit`, and both `anchor-drift` passes, and
writes `.coyodex/finalize-report.{json,md}`. It adds no check of its own; every finding here is one
those commands already produce.

**It compares nothing against a previous map, deliberately.** An earlier version of this command did,
and that was wrong for the build: in real use a map EVOLVES INCREMENTALLY alongside the code, so a
from-scratch rebuild is a first-run event and there is usually no meaningful predecessor to diff
against. Rebuilding often is a coyodex-DEVELOPER habit, with its own `.coyodex/.old-ignore-N`
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
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from coyodex.model import ModelError, load_model_path

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


def _audit_leg(map_path: Path) -> Leg:
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
    note = (f"{len(payload.get('worklist') or [])} L2 claims on the grounding worklist"
            + (f" ({', '.join(f'{k}:{v}' for k, v in counts.items())})" if counts else ""))
    return Leg("audit", RAN, blocking=blocking, advisory=advisory, note=note)


def _drift_leg(map_path: Path, repo: Path, verdicts: list[Path]) -> Leg:
    argv = ["--map", str(map_path), "--repo", str(repo)]
    for v in verdicts:
        argv += ["--verdicts", str(v)]
    code, out, err = _run_leg("anchor-drift", argv)
    text = (out or "") + (err or "")
    rows = [ln.strip()[2:] for ln in text.splitlines() if ln.startswith("  - ")]
    kind = "verdict-based" if verdicts else "shape-only"
    # ADVISORY on purpose: `fix apply-drift` handles edge and security anchors only, so on the map
    # this command was written for all 17 confirmed rows were entry-point cadence claims it cannot
    # apply. A gate on a finding with no remedy is a false failure.
    return Leg(f"anchor-drift ({kind})", RAN if code in (0, 1) else FAILED, advisory=rows,
               note=(f"{len(rows)} drifted anchor(s) — reconcile each (fix the `where`, or record why "
                     f"it stands); `fix apply-drift` covers edge + security anchors only"
                     if rows else "no drifted anchors"))


def build_report(map_path: Path, repo: Path, verdicts: list[Path]) -> FinalizeReport:
    legs = [
        _validate_leg(map_path, repo),
        _audit_leg(map_path),
        _drift_leg(map_path, repo, []),
        *([_drift_leg(map_path, repo, verdicts)] if verdicts else []),
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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex finalize [--repo <root>] [--verdicts <file>]... "
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
    positional: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--repo", "--verdicts"):
            i += 1
            if i >= len(argv):
                print(f"ERROR: {a} needs a path", file=sys.stderr)
                return 2
            if a == "--repo":
                repo = Path(argv[i])
            else:
                verdicts.append(Path(argv[i]))
        elif a.startswith("-"):
            print(f"ERROR: unknown option '{a}'", file=sys.stderr)
            return 2
        else:
            positional.append(a)
        i += 1
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
