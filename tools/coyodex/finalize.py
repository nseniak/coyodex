#!/usr/bin/env python3
"""`coyodex finalize` — the one command a build runs before it commits.

**It is a convenience wrapper, not an enforcement point.** That distinction is the whole design, and
the docstring says it first because an earlier draft of this command claimed to be the latter and
could not be. Nothing makes a build run `finalize`, and in a shell pipeline the exit status is the
LAST command's — so `coyodex finalize | grep …` returns grep's 0. A live build wrote exactly that
shape at the step this command occupies (`validate … | grep -E …; audit … > /dev/null 2>&1`). A tool
cannot fix that by exiting non-zero harder.

What it DOES fix is the two failures that are about running the checks at all:

1. **`compare` never runs during a build.** On the run this came from, the map's security table went
   from 103 rows to 19 and every gate passed: `validate` was clean, `audit` was clean, `balance` was
   clean. `coyodex-eval compare` DID catch it (`[FAIL] auth-surfaces-no-drop: auth surfaces 103 ->
   19`) — nobody ran it, because it is an eval command and the build's finalize sequence is
   `validate → audit → render`. Folding a baseline comparison into the pre-commit step is the only
   thing that would have surfaced that collapse while the build could still act on it.
2. **The output does not survive how it is read.** Every finding here is also written to
   `.coyodex/finalize-report.json` + `.md`. A file cannot be erased by `> /dev/null`, cut by
   `| tail -12`, or summarised away — and the report is written with whole lists (`--json`
   semantics), so no id hides behind a `+N more`.

**Exit code.** 0 when nothing BLOCKING was found, 1 when something was. "Blocking" means exactly what
`validate` and `audit` already block on — a schema/reference problem, or an L1 contradiction. It does
NOT include the advisory families, the `compare` verdict, or unapplied anchor drift:

  - `compare`'s gates are *relative eval regression* gates. A map whose security-table granularity
    legitimately coarsens (a deliberate choice the method now asks builds to record) would be walled
    out by a build it cannot pass. Reported loudly, never gating.
  - unapplied anchor drift would fail the map this command was written for: all 17 of its confirmed
    drift rows are entry-point cadence claims, and `fix apply-drift` cannot apply a single one.
    Gating on a finding with no remedy is a false failure, not a gate.

**Why it shells out to `coyodex-eval`.** `compare` and `score` live in the `coyodex_eval` package, and
`pyproject.toml` states the invariant plainly: the eval depends on the core, and *the core has no
reference back to it*. Importing it here would invert that, so this runs the sibling CLI as a
subprocess instead of re-implementing a subset of its logic (which would be the same duplication that
put a hand-written reconcile in every build). If `coyodex-eval` is not on PATH the comparison degrades
to a skip that says so.

Stdlib-only (the cli.py dependency firewall).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from coyodex.model import ModelError, load_model_path

#: Where the durable record goes, next to the map it describes.
REPORT_STEM = "finalize-report"


#: A leg's outcome. The three-way split exists because the first version had two and got the most
#: important case wrong: a leg that DID NOT RUN contributed 0 blocking and 0 advisory, so a run whose
#: validate leg errored out (a typo'd `--repo` is enough) reported **CLEAN**, exit 0, on a map with a
#: dangling reference. A report that testifies a gate passed when the gate never ran is worse than no
#: report — it is the exact failure this whole command was written to stop.
RAN = "ran"                  # the check executed and its findings are below
UNAVAILABLE = "unavailable"  # legitimately not possible here (no baseline on a first build) — benign
FAILED = "failed"            # the check should have run and did not — never reported as a pass


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
    baseline: str | None
    baseline_source: str | None
    legs: list[Leg]
    verdict: str                 # BLOCKED | INCOMPLETE | ADVISORIES | CLEAN
    advisory_total: int
    blocking_total: int
    compare_verdict: str | None = None   # PASS | DRIFT | REGRESSED — surfaced in the headline

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def find_baseline(map_path: Path, repo: Path) -> tuple[Path | None, str | None, str | None]:
    """The previous map to compare against: `(path, source, note)`.

    Prefers the COMMITTED previous version (`git show HEAD:<rel>`), written to a temp file. That is
    the durable one: `.coyodex/.old-ignore*/` comes from an operator-only backup script, so it is
    absent on a first build, a fresh clone, or CI — exactly when a coverage-drop check matters most.
    The archive is the fallback for a working tree whose map is not committed yet."""
    rel = None
    if shutil.which("git"):
        # `git show HEAD:<path>` resolves against the repository TOP LEVEL, not the cwd, so a project
        # mapped below the git root needs its prefix — without it the lookup always failed there and
        # the preference for the committed baseline silently never applied.
        top = subprocess.run(["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True)
        if top.returncode == 0 and top.stdout.strip():
            try:
                rel = map_path.resolve().relative_to(Path(top.stdout.strip()).resolve())
            except ValueError:
                rel = None
    if rel is not None:
        r = subprocess.run(["git", "-C", str(repo), "show", f"HEAD:{rel.as_posix()}"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            tmp = map_path.parent / f".{REPORT_STEM}-baseline.json"
            tmp.write_text(r.stdout, encoding="utf-8")
            return tmp, f"git HEAD:{rel.as_posix()}", None
    def _archive_rank(p: Path) -> int:
        """`.old-ignore` → 0, `.old-ignore-12` → 12. Sorting on the name's LENGTH (the first version)
        picked the wrong archive in 28 of 40 trials, and `Path.glob` is unordered, so same-length names
        — `.old-ignore-10/-11/-12`, today's reality — resolved in filesystem order. A wrong baseline
        does not fail loudly; it produces a confident verdict about the wrong comparison."""
        tail = p.parent.name.removeprefix(".old-ignore").lstrip("-")
        return int(tail) if tail.isdigit() else 0

    archives = sorted(map_path.parent.glob(".old-ignore*/project-map.json"), key=_archive_rank)
    if archives:
        return archives[-1], str(archives[-1]), None
    return None, None, ("no baseline found — neither a committed previous map (git HEAD) nor a "
                        ".coyodex/.old-ignore*/ archive. A coverage drop against the last map cannot "
                        "be detected on this run; that is the check that would have caught a security "
                        "table going from 103 rows to 19 with every other gate green.")


def _find_eval() -> str | None:
    """The `coyodex-eval` console script, looked for NEXT TO THE RUNNING INTERPRETER before PATH.

    PATH alone is the wrong first guess for the normal invocation: the method tells builds to run
    `«COYODEX_HOME»/.venv/bin/coyodex` by absolute path, and a venv reached that way is not on PATH —
    so `shutil.which` returned None and the comparison leg silently skipped in exactly the case it was
    written for. Sibling console scripts share the interpreter's directory, which is what makes this
    reliable."""
    sibling = Path(sys.executable).parent / "coyodex-eval"
    if sibling.is_file():
        return str(sibling)
    return shutil.which("coyodex-eval")


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


def _compare_leg(map_path: Path, baseline: Path | None, baseline_source: str | None,
                 note: str | None, repo: Path) -> Leg:
    if baseline is None:
        return Leg("compare (vs previous map)", UNAVAILABLE, note=note)
    exe = _find_eval()
    if exe is None:
        return Leg("compare (vs previous map)", UNAVAILABLE,
                   note="`coyodex-eval` was not found next to this interpreter or on PATH, so the "
                        "baseline comparison was skipped. It lives in a separate package on purpose "
                        "(the core must not depend on the eval); install it to enable the "
                        "coverage-drop check.")
    profiles: list[Path] = []
    try:
        for tag, m in (("baseline", baseline), ("candidate", map_path)):
            prof = map_path.parent / f".{REPORT_STEM}-{tag}-profile.json"
            r = subprocess.run([exe, "score", str(m), "--repo", str(repo), "--json"],
                               capture_output=True, text=True)
            if r.returncode != 0 or not r.stdout.strip():
                return Leg("compare (vs previous map)", FAILED,
                           note=f"`coyodex-eval score` failed on the {tag} map (exit {r.returncode}): "
                                f"{(r.stderr or r.stdout).strip()[:200]}")
            prof.write_text(r.stdout, encoding="utf-8")
            profiles.append(prof)
        # `--json`, not the human report. Scraping stdout for three line prefixes threw away the whole
        # `Notes:` section — which is where the NAMES of the dropped auth surfaces live (84 of them on
        # the collapse this leg exists to catch), plus every "gate skipped" line. Keeping the count and
        # discarding the content is the elision `coyodex.reporting` was written to end.
        r = subprocess.run([exe, "compare", str(profiles[0]), str(profiles[1]), "--json"],
                           capture_output=True, text=True)
        # 0 PASS, 1 REGRESSED, 2 DRIFT are all real verdicts; anything else is a crash. Not checking
        # this reported a crashed compare as "ran, nothing found" — the one check the command is for.
        if r.returncode not in (0, 1, 2):
            return Leg("compare (vs previous map)", FAILED,
                       note=f"`coyodex-eval compare` crashed (exit {r.returncode}): "
                            f"{(r.stderr or r.stdout).strip()[:300]}")
        try:
            delta = json.loads(r.stdout)
        except ValueError:
            return Leg("compare (vs previous map)", FAILED,
                       note=f"`coyodex-eval compare` did not return JSON (exit {r.returncode}): "
                            f"{(r.stderr or r.stdout).strip()[:200]}")
        rows: list[str] = [f"Comparison verdict: {delta.get('verdict')}"]
        for g in delta.get("gates") or []:
            if not g.get("passed", True):
                rows.append(f"[FAIL] {g.get('name')}: {g.get('detail')}")
        for b in delta.get("bands") or []:
            if b.get("breached"):
                rows.append(f"[DRIFT] {b.get('metric')}: {b.get('detail')}")
        gr = delta.get("granularity")
        if isinstance(gr, dict) and gr.get("breached"):
            rows.append(f"[DRIFT] granularity: {gr.get('detail')}")
        for n in delta.get("notes") or []:
            rows.append(f"note: {n}")
        return Leg("compare (vs previous map)", RAN, advisory=rows,
                   note=(f"baseline: {baseline_source}. `compare`'s gates are RELATIVE "
                         f"eval-regression gates, reported here and never gating a build — a "
                         f"deliberate granularity change would otherwise wall the build out. Read "
                         f"them: this is the check that catches a coverage collapse every other gate "
                         f"passes."))
    finally:
        for prof in profiles:
            prof.unlink(missing_ok=True)


def build_report(map_path: Path, repo: Path, verdicts: list[Path]) -> FinalizeReport:
    baseline, source, note = find_baseline(map_path, repo)
    try:
        legs = [
            _validate_leg(map_path, repo),
            _audit_leg(map_path),
            _drift_leg(map_path, repo, []),
            *([_drift_leg(map_path, repo, verdicts)] if verdicts else []),
            _compare_leg(map_path, baseline, source, note, repo),
        ]
    finally:
        # In a `finally`, so an exception in any leg cannot leave an ~800 KB copy of the previous map
        # sitting beside the real one.
        if baseline is not None and baseline.name.startswith(f".{REPORT_STEM}-baseline"):
            baseline.unlink(missing_ok=True)
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
    cmp_leg = next((l for l in legs if l.name.startswith("compare")), None)
    cmp_verdict = None
    if cmp_leg is not None and cmp_leg.status == RAN:
        for row in cmp_leg.advisory:
            if row.startswith("Comparison verdict: "):
                cmp_verdict = row.split(": ", 1)[1].strip()
    return FinalizeReport(map_path=str(map_path),
                          map_sha256=hashlib.sha256(map_path.read_bytes()).hexdigest(),
                          baseline=str(baseline) if baseline else None,
                          baseline_source=source, legs=legs, verdict=verdict,
                          advisory_total=advisory, blocking_total=blocking,
                          compare_verdict=cmp_verdict)


def format_report(r: FinalizeReport) -> str:
    out: list[str] = [f"# coyodex finalize — {r.map_path}", ""]
    out.append(f"**Verdict: {r.verdict}** — {r.blocking_total} blocking, {r.advisory_total} advisory"
               + (f"; compare says {r.compare_verdict}" if r.compare_verdict else "") + ".")
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
              "anchor-drift (shape-only, and verdict-based when --verdicts is given) + a comparison\n"
              "against the previous map. Writes .coyodex/finalize-report.{json,md} and prints one\n"
              "verdict line.\n\n"
              "A CONVENIENCE WRAPPER, not an enforcement point: exit 1 only for what validate and\n"
              "audit already block on (schema/reference problems, L1 contradictions). The compare\n"
              "verdict and unapplied anchor drift are reported, never gating — compare's gates are\n"
              "relative eval-regression gates, and apply-drift cannot fix an entry-point cadence\n"
              "anchor, so gating on either would fail builds that have no remedy.\n\n"
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
          + (f"; compare says {report.compare_verdict}" if report.compare_verdict else "")
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
