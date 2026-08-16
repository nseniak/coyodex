#!/usr/bin/env python3
"""`coyodex scope` — the up-front briefing: WHICH files will be analyzed, and WHAT the map is pinned to.

Two facts decide whether a map can be trusted, and both were previously discoverable only by reading
the method or the code:

  * **What is in scope.** The file set comes from git, so a `.gitignore`d tree is simply absent from
    the map — and absent without a word, which reads exactly like "coyodex looked and found nothing
    there". `.coyodex/.ignore` narrows it further. The user has to be told, once, before the build.
  * **What the pin means.** The map records the commit it describes. When the working tree is dirty
    the map describes code that commit does not contain, so the pin is a promise the repo cannot
    keep — `method.md` already blocks on this, but only at the END, after the whole build (one run
    lost ~2 hours to it). Saying it FIRST turns a late block into an early choice.

Text out, no exit-code signalling: this is a briefing a human reads, and the caller (dispatch) acts
on what it says. Stdlib-only (the `cli.py` dependency firewall); the counts come from the same walk
the pre-index and the validator use, so the briefing can never describe a different tree than the
one that gets mapped.
"""
from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path

from coyodex.ignorefile import IGNORE_REL, ignore_report
from coyodex.preindex_lib import iter_source_files
from coyodex.reporting import shown

# How many dirty paths to name before the `+N more` tail. Enough to recognize the change, short
# enough that the pin paragraph stays readable when someone runs coyodex mid-refactor.
DIRTY_SHOWN = 8


@dataclass
class Pin:
    """What the map would be pinned to right now."""
    sha: str | None            # short sha of HEAD, None when there is no commit (or no git)
    date: str | None           # HEAD's commit date, YYYY-MM-DD
    dirty: tuple[str, ...]     # repo-relative paths changed but not committed (excluding .coyodex/)


def _git(root: Path, *args: str) -> str | None:
    """git stdout, or None when git is unavailable / the command failed (not a repo, no commit yet)."""
    try:
        out = subprocess.run(["git", "-C", str(root), *args],
                             capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def read_pin(root: Path) -> Pin:
    """HEAD + the uncommitted CODE paths.

    coyodex's own `.coyodex/` files are excluded exactly as `method.md`'s pin gate excludes them:
    the map, its view and its reports are always in flux and the workflow commits them itself, so
    counting them would make every run look dirty and train the user to wave the warning through.
    """
    sha = _git(root, "rev-parse", "--short", "HEAD")
    date = _git(root, "show", "-s", "--format=%cs", "HEAD")
    status = _git(root, "status", "--porcelain", "--", ".", ":(exclude).coyodex")
    dirty = tuple(line[3:].strip() for line in (status or "").splitlines() if line.strip())
    return Pin(sha=(sha or "").strip() or None, date=(date or "").strip() or None, dirty=dirty)


def scope_report(root: Path) -> list[str]:
    """The briefing, as lines. Two sections — what gets read, and what the map will claim."""
    walk = iter_source_files(root)
    out: list[str] = ["What coyodex will analyze", ""]
    if walk.used_git:
        out += [
            "  Files come from git: everything git tracks, plus files you created but have not",
            "  added yet. Anything in .gitignore is left out — git decides that, so a .gitignore",
            "  inside a subfolder counts too.",
        ]
    else:
        out += [
            "  This folder is not a git repository, so coyodex reads the files on disk and",
            "  .gitignore is NOT applied — only coyodex's built-in exclusions narrow the tree.",
        ]
    out += [
        "",
        f"  {len(walk.files)} file(s) will be analyzed.",
        f"  {walk.skipped_excluded} file(s) left out by coyodex's built-in list"
        " (node_modules/, dist/, build output, lock files and friends).",
    ]

    # A PREVIOUS MAP sitting in the tree is source as far as the walk is concerned. `.coyodex/` is
    # excluded by name; a hand-made copy beside it is not, and a build that archived its old map by
    # hand — `mv .coyodex .coyodex-archive-<date>` — silently pulled ~59 files of it into the harvest
    # scope (2731 analysed against 2672 after the archive was filed properly). That is the one
    # artifact the method forbids a rebuild from reading, so it cannot be left to the reader to spot
    # in a file count. `coyodex-eval archive` is the supported way to file one.
    strays = sorted(d.name for d in root.iterdir()
                    if d.is_dir() and d.name.startswith(".coyodex") and d.name != ".coyodex")
    if strays:
        out += [
            "",
            f"  WARNING: {len(strays)} coyodex-looking folder(s) beside .coyodex/ are being read as "
            f"SOURCE: {', '.join(strays)}.",
            "  A previous map is not source. If this is an archive, file it with "
            "`coyodex-eval archive` (it lands under .coyodex/dev-rebuilds/, which is excluded);",
            "  otherwise add it to .coyodex/.ignore. Leaving it here maps your own map.",
        ]

    # The ignore file gets its own per-pattern block, never a bare total: it is the one input that
    # can hide a real gap from the checks whose job is finding gaps, so a pattern that removed
    # nothing must be visible as such (same rule, and the same wording, as `validate`'s disclosure).
    if walk.ignore.rules:
        rep = ignore_report(walk.ignore, walk.ignore_hits)
        out.append(f"  {rep.removed} file(s) removed by {IGNORE_REL.as_posix()}:")
        out += [f"    {line}" for line in rep.per_rule]
        if rep.unused:
            out.append(f"    warning: {len(rep.unused)} pattern(s) removed nothing: "
                       f"{shown(list(rep.unused), 5, unit='pattern(s)')}")

    pin = read_pin(root)
    out += ["", "What the map will be pinned to", ""]
    if pin.sha is None:
        out += [
            "  There is no commit here, so the map cannot be pinned to one. Commit your code first",
            "  if you want the map to say which version of the code it describes.",
        ]
        return out

    out.append(f"  The map records the commit it describes: {pin.sha}"
               f"{f' ({pin.date})' if pin.date else ''}.")
    if not pin.dirty:
        out.append("  Your code is committed, so the map and that commit will match.")
        return out
    out += [
        "",
        f"  {len(pin.dirty)} file(s) in your code are changed but not committed:",
        f"    {shown(list(pin.dirty), DIRTY_SHOWN, sep=chr(10) + '    ', unit='file(s)')}",
        "",
        "  coyodex maps what is on disk, so the map WILL describe those changes — but the commit",
        "  it points at does not contain them. The map and its pin would be out of step, and a",
        "  later change analysis, which compares your code against the pin, would report the same",
        "  changes again. Committing first avoids that; continuing is fine too, and the pin is",
        f"  then recorded as {pin.sha}-dirty to say so.",
    ]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="coyodex scope",
        description="Say which files coyodex will analyze and what the map will be pinned to.")
    ap.add_argument("--repo", default=".", help="repo root to describe (default: cwd)")
    args = ap.parse_args(argv)
    print("\n".join(scope_report(Path(args.repo).resolve())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
