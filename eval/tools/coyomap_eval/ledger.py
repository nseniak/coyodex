#!/usr/bin/env python3
"""`coyomap-eval ledger` — cross-examine a retro ledger against the git history it cites.

A finding's `landed` flag is set BY HAND, and it is the one input the carry-forward depends on:
`eval/retro/method.md` combines `decision`, `landed` and `observed vs prior` into the verdict that
decides whether a row goes quiet or comes back. Nothing has ever checked it.

The failure this exists to catch, measured on the session that wrote it. An operator answered 40
rows of the 2026-08-26_2158 mcpolis ledger and, in the same session, FIXED seven of them. All seven
kept `landed: false`. Every one would have been re-proposed by the next retrospective, each
carrying its `retros_open` count up by one — the exact shape that ledger had 24 instances of, added
to it four messages after the operator finished cataloguing them. Setting forty flags by hand and
getting seven wrong is not carelessness; it is what hand-maintained state does.

The check is possible because a row that landed already records WHERE: `landed_in` opens with the
commit sha. So the two halves of the row can be asked to agree with the repository:

  * a row that says it is OPEN while the commit it names is MERGED — the stale-open case above, and
    the expensive one, because it silently re-proposes work already done;
  * a row that says it LANDED while the commit it names is absent from this clone — either the fix
    is unmerged, or the sha is wrong, and both mean the row's claim cannot be trusted.

It is a CROSS-EXAMINATION, not a gate on truth: a row with no `landed_in` cannot be checked at all,
and the count of those is printed rather than left implied. A ledger where nothing is checkable
reports zero problems, which must not read like a clean one.

The commits live in the COYOMAP clone, and the ledger lives under the MAPPED project's
`.coyomap-eval/`, so `--repo` names the former and defaults to `$COYOMAP_HOME`.

Stdlib-only.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

USAGE = """usage: coyomap-eval ledger <findings.json> [--repo <coyomap clone>] [--json]

Cross-examine a retro ledger against the git history it cites. A row that landed records the commit
in `landed_in`; this asks git whether that commit is in the branch, and reports the rows whose two
halves disagree.

  --repo <dir>   the coyomap clone holding the fix commits (default: $COYOMAP_HOME, else the clone
                 this command is running from)
  --json         machine-readable

Exit 1 when a row claims to be OPEN while the commit it names is merged — that row will be
re-proposed by the next retrospective, and the work is already done."""

#: A `landed_in` opens with the sha: `bd10157 (grounding write prints NOTE FACTS)` or
#: `5569348 — <what it did>`. Seven characters is what every row in the corpus uses; more is
#: accepted because `git rev-parse --short` lengthens as a repo grows.
_SHA = re.compile(r"^\s*([0-9a-f]{7,40})\b")


@dataclass
class LedgerReport:
    """Rows whose two halves disagree with the repository, and what could not be asked.

    A dataclass rather than a pair of lists: both are empty on the happy path, so a swapped return
    would read as correct behaviour — the same reason `VerdictLint` and `FragmentLoad` exist."""
    stale_open: list[tuple[str, str, str]] = field(default_factory=list)
    unverifiable: list[tuple[str, str, str]] = field(default_factory=list)
    rows_total: int = 0
    rows_with_commit: int = 0
    rows_open: int = 0
    rows_landed: int = 0

    @property
    def uncheckable(self) -> int:
        """Rows carrying no commit — this command has no opinion about them, and says so."""
        return self.rows_total - self.rows_with_commit


def _commit_exists(repo: Path, sha: str) -> bool:
    """Is `sha` a commit reachable from HEAD in `repo`?

    `--is-ancestor` and not `cat-file -e`: a commit that exists in the object store but sits on an
    abandoned branch is not a fix that shipped, and reading it as one recreates the failure this
    command exists to catch, in the other direction."""
    try:
        r = subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, "HEAD"],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def _sha_of(row: dict) -> str:
    m = _SHA.match(str(row.get("landed_in") or ""))
    return m.group(1) if m else ""


def check(findings: list[dict], repo: Path) -> LedgerReport:
    """Ask the repository whether each row's `landed` half matches the commit it names."""
    out = LedgerReport(rows_total=len(findings))
    for row in findings:
        landed = bool(row.get("landed"))
        out.rows_landed += landed
        out.rows_open += not landed
        sha = _sha_of(row)
        if not sha:
            continue
        out.rows_with_commit += 1
        merged = _commit_exists(repo, sha)
        title = str(row.get("title") or "")[:70]
        if merged and not landed:
            out.stale_open.append((str(row.get("id")), sha, title))
        elif landed and not merged:
            out.unverifiable.append((str(row.get("id")), sha, title))
    return out


def _default_repo() -> Path:
    home = os.environ.get("COYOMAP_HOME")
    return Path(home) if home else Path(__file__).resolve().parents[3]


def format_report(r: LedgerReport, repo: Path) -> str:
    lines = [f"LEDGER — {r.rows_total} row(s): {r.rows_landed} landed, {r.rows_open} open. "
             f"{r.rows_with_commit} name a commit and were checked against {repo}."]
    if r.uncheckable:
        # Say what could NOT be asked. A ledger where nothing is checkable reports zero problems,
        # and zero problems is exactly what a clean one reports.
        lines.append(f"  {r.uncheckable} row(s) name no commit in `landed_in`, so this says nothing "
                     f"about them — a clean result here is not a clean ledger.")
    for rid, sha, title in r.stale_open:
        lines.append(f"  STALE-OPEN {rid}: says `landed: false`, but {sha} — the commit it names — "
                     f"is merged. The next retro re-proposes work already done. ({title})")
    for rid, sha, title in r.unverifiable:
        lines.append(f"  UNVERIFIABLE {rid}: says it landed in {sha}, which is not in this branch. "
                     f"Either the fix is unmerged or the sha is wrong. ({title})")
    if not r.stale_open and not r.unverifiable and r.rows_with_commit:
        lines.append("  every row that names a commit agrees with the branch.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 2
    path: Path | None = None
    repo = _default_repo()
    as_json = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True
        elif a == "--repo":
            i += 1
            if i >= len(argv):
                print("ERROR: --repo needs a directory", file=sys.stderr)
                return 2
            repo = Path(argv[i])
        elif a.startswith("-"):
            print(f"ERROR: unknown argument '{a}'", file=sys.stderr)
            return 2
        elif path is None:
            path = Path(a)
        else:
            print("ERROR: one findings.json at a time", file=sys.stderr)
            return 2
        i += 1
    if path is None:
        print("ERROR: a findings.json is required", file=sys.stderr)
        return 2
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"ERROR: {path} could not be read as a ledger ({e})", file=sys.stderr)
        return 2
    # A bare LIST (one retro wrote its rows without the envelope) must reach the message below,
    # not an `AttributeError` two lines short of it.
    rows = doc.get("findings") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        print(f"ERROR: {path} has no `findings` list — is it a retro ledger?", file=sys.stderr)
        return 2
    report = check(rows, repo)
    if as_json:
        print(json.dumps({
            "rows_total": report.rows_total, "rows_landed": report.rows_landed,
            "rows_open": report.rows_open, "rows_with_commit": report.rows_with_commit,
            "uncheckable": report.uncheckable,
            "stale_open": [{"id": i, "commit": s, "title": t} for i, s, t in report.stale_open],
            "unverifiable": [{"id": i, "commit": s, "title": t} for i, s, t in report.unverifiable],
        }, indent=2, ensure_ascii=False))
    else:
        print(format_report(report, repo))
    return 1 if report.stale_open else 0


if __name__ == "__main__":
    raise SystemExit(main())
