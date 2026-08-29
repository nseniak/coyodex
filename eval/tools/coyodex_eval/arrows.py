"""`coyodex-eval arrows` — which relations a rebuild LOST, and whether the code still makes them.

**Why this exists.** A rebuild of the trapdoor fixture dropped 24 arrows. Twenty-two of them were
things the code demonstrably still does, including all eight `plugin handler -> analytics service`
edges the fixture plants as trap O3. Every instrument the project had said the build was fine:

  * `coyodex validate` and `coyodex audit` passed — a map missing a true relation is still
    well-formed and still self-consistent. Neither ever compares against a previous map.
  * `coyodex-eval run` reported DRIFT, not REGRESSED. Its edge band is a 30% shrink and the loss
    came in at 27.4%, so the gate that exists for exactly this did not fire. The bands that DID
    fire were on counts like 4 -> 2, which move on any honest rebuild.
  * `coyodex diff` says in its own docstring that it compares two assembles of the SAME work and
    is NOT for two independent builds, because their ids and wording never agree.

So the loss was found by a person deciding to match arrows by source FILE and then reading the code
for each one. That is the procedure this module makes deterministic, free, and repeatable.

**How it decides, and why it can.** Every edge carries a `where` anchor naming its call site. When
both maps describe the SAME commit — which is the only case this command judges — that anchor is
still exact. So a lost arrow whose anchor still points at a real, operative line is a lost TRUTH,
not a corrected overclaim. The command refuses to judge when the two maps pin different commits,
because then a moved line means nothing.

**What it deliberately does not do.** No model, no network, no map mutation. It reports; the caller
gates. And it names its own blind spot rather than hiding it: an arrow that legitimately moved to a
different pair of files (a component was split) reads as lost here, which is why `regrouped` is
reported separately and why the exit code counts only `lost-truth`.

**It errs toward flagging, and the margin is measured.** `lost-truth` means "the recorded call site
is still live, operative code", which is a LOWER bar than "the code still makes exactly this
relation": a line can be operative and be about something else. On the run this was written from it
called 24 of 24 lost arrows a lost truth where a careful human read said 22, because two arrows ended
at an entity whose file also holds other entities and the file-level match cannot separate them. That
direction is the right one for this instrument — a false alarm costs one read, and a false silence
ships a map that dropped eight true relations while every other gate stayed green.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from coyodex.anchors import non_operative_reason, parse_anchor

#: Verdicts, most serious first. `lost-truth` is the only one that sets a non-zero exit.
LOST_TRUTH = "lost-truth"
CORRECT_DROP = "correct-drop"
REGROUPED = "regrouped"
UNJUDGEABLE = "unjudgeable"


@dataclass(frozen=True)
class Arrow:
    """One relation, addressed the only way that survives a rebuild: by the FILES its ends live in.

    Ids are minted per build and names are re-worded per build, so neither can match across two
    independent builds. The file pair can."""
    src_file: str
    dst_file: str
    verb: str
    where: str
    why: str

    @property
    def pair(self) -> tuple[str, str]:
        return (self.src_file, self.dst_file)


@dataclass(frozen=True)
class Verdict:
    arrow: Arrow
    verdict: str
    reason: str


def _row_file(row: dict[str, Any]) -> str:
    """Where a box's own source anchor says it lives, path only."""
    raw = row.get("source") or row.get("where") or ""
    loc = parse_anchor(str(raw)) if raw else None
    return loc.path if loc else ""


def box_files(model: dict[str, Any]) -> dict[str, str]:
    """id -> source file, over every array in the map that carries ids."""
    out: dict[str, str] = {}
    for rows in model.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                out[row["id"]] = _row_file(row)
    return out


def arrows(model: dict[str, Any]) -> tuple[Arrow, ...]:
    """Every `src`/`dst` row in the map, resolved to the files its two ends live in.

    A dependency box has no source file of its own, so its end resolves to the empty string and the
    pair is keyed by the source file alone. That is deliberate: the eight plugin edges this command
    was written for all point at one such box."""
    files = box_files(model)
    out: list[Arrow] = []
    for rows in model.values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            src, dst = row.get("src"), row.get("dst")
            if not isinstance(src, str) or not isinstance(dst, str):
                continue
            src_file = files.get(src, "")
            if not src_file:
                continue          # an arrow whose own source is unknown cannot be matched by file
            out.append(Arrow(src_file=src_file, dst_file=files.get(dst, ""), verb=str(row.get("verb", "")),
                             where=str(row.get("where", "")), why=str(row.get("why", ""))))
    return tuple(out)


def judge_one(arrow: Arrow, repo: Path, present_pairs: set[tuple[str, str]]) -> Verdict:
    """Did the code stop doing this, or did the map lose it?"""
    if arrow.pair in present_pairs:
        return Verdict(arrow, REGROUPED, "the new map still connects these two files, by another arrow")
    loc = parse_anchor(arrow.where) if arrow.where else None
    if loc is None or not loc.path:
        return Verdict(arrow, UNJUDGEABLE, "the old arrow carries no usable call-site anchor")
    path = repo / loc.path
    if not path.is_file():
        return Verdict(arrow, CORRECT_DROP, f"{loc.path} is gone from the tree")
    if loc.lo is None:
        return Verdict(arrow, UNJUDGEABLE, f"{loc.path} has no line, so the call site cannot be re-read")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if loc.lo > len(lines):
        return Verdict(arrow, CORRECT_DROP, f"{loc.path} no longer has line {loc.lo}")
    line = lines[loc.lo - 1]
    why_not = non_operative_reason(line)
    if why_not:
        return Verdict(arrow, CORRECT_DROP, f"{arrow.where} is now {why_not}")
    return Verdict(arrow, LOST_TRUTH, f"{arrow.where} still reads: {line.strip()[:70]}")


def compare(baseline: dict[str, Any], candidate: dict[str, Any], repo: Path) -> tuple[Verdict, ...]:
    old, new = arrows(baseline), arrows(candidate)
    present = {a.pair for a in new}
    old_pairs: dict[tuple[str, str], Arrow] = {}
    for a in old:
        old_pairs.setdefault(a.pair, a)
    return tuple(judge_one(a, repo, present) for pair, a in old_pairs.items() if pair not in present)


#: Paths whose movement between two pins says nothing about the CODE. The map and its artifacts are
#: the output being compared, so committing them is exactly what makes the two pins differ.
_NOT_SOURCE = (".coyodex/", ".gitignore", ".claude/")


def _pin(model: dict[str, Any]) -> str:
    """The commit a map is pinned to, without the `-dirty` marker. A dirty pin still names the
    commit the code was AT, which is what a source comparison needs."""
    return str(model.get("commit", "")).removesuffix("-dirty").strip()


def source_unchanged(baseline: dict[str, Any], candidate: dict[str, Any],
                     repo: Path) -> tuple[bool, str]:
    """Did the CODE move between the two maps' pins?

    The first version of this compared the two pin STRINGS and refused whenever they differed. On
    its first real use it refused a pair whose pins differed only because the FIRST map had been
    committed in between: `git diff` over the two pins touched seven files, every one of them under
    `.coyodex/`, and not one source file. A check that cannot tell "the code changed" from "we
    committed the last answer" would refuse every honest before/after pair this command exists for.

    So the question is asked of the tree, not of the label. Either pin being unreadable is reported
    as unknown rather than assumed either way."""
    a, b = _pin(baseline), _pin(candidate)
    if not a or not b:
        return (False, "one of the maps records no commit pin")
    if a == b:
        return (True, f"both maps pin {a}")
    try:
        proc = subprocess.run(["git", "-C", str(repo), "diff", "--name-only", a, b],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return (False, f"git could not compare {a}..{b}: {exc}")
    if proc.returncode != 0:
        return (False, f"git could not compare {a}..{b}: {proc.stderr.strip()[:120]}")
    moved = [ln for ln in proc.stdout.splitlines()
             if ln.strip() and not any(ln.startswith(p) for p in _NOT_SOURCE)]
    if moved:
        return (False, f"{len(moved)} source file(s) changed between {a} and {b}, "
                       f"first: {moved[0]}")
    return (True, f"{a}..{b} moved no source file, only build artifacts")


def report(verdicts: tuple[Verdict, ...], n_old: int, n_new: int) -> str:
    buckets: dict[str, list[Verdict]] = {}
    for v in verdicts:
        buckets.setdefault(v.verdict, []).append(v)
    lines = [f"ARROWS  baseline {n_old}  candidate {n_new}  lost {len(verdicts)}"]
    for name, head in ((LOST_TRUTH, "the code still does it, the map no longer says so"),
                       (CORRECT_DROP, "the code no longer does it"),
                       (REGROUPED, "still connected another way"),
                       (UNJUDGEABLE, "no usable anchor to re-read")):
        got = buckets.get(name, [])
        lines.append(f"  {len(got):3d}  {name:13s} {head}")
    worst = buckets.get(LOST_TRUTH, [])
    if worst:
        lines.append("")
        lines.append(f"LOST TRUTH ({len(worst)}) — each of these is a relation the code makes and the map dropped:")
        for v in worst:
            dst = v.arrow.dst_file or "(a dependency)"
            lines.append(f"  {v.arrow.src_file} --{v.arrow.verb}-> {dst}")
            lines.append(f"      {v.reason}")
    return "\n".join(lines) + "\n"


_USAGE = """usage: coyodex-eval arrows <baseline-map> <candidate-map> --repo <repo> [--json]

Which relations the candidate map LOST against its baseline, and for each whether the code still
makes it. Matches by the SOURCE FILE of each end, because ids and wording never agree across two
independent builds.

Judges only when both maps pin the SAME commit: a lost arrow is called a lost truth because its
recorded call site can be re-read, and that is only sound when the code did not move.

Exit 1 when any arrow is `lost-truth`. Reports; changes nothing.
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or "-h" in args or "--help" in args:
        print(_USAGE)
        return 0 if args else 2
    parser = argparse.ArgumentParser(prog="coyodex-eval arrows", add_help=False)
    parser.add_argument("baseline")
    parser.add_argument("candidate")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--allow-different-commits", action="store_true",
                        help="judge anyway; every verdict is then advisory")
    try:
        ns = parser.parse_args(args)
    except SystemExit:
        print(_USAGE, file=sys.stderr)
        return 2
    try:
        baseline = json.loads(Path(ns.baseline).read_text(encoding="utf-8"))
        candidate = json.loads(Path(ns.candidate).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    repo = Path(ns.repo).expanduser().resolve()
    ok, why = source_unchanged(baseline, candidate, repo)
    if not ok and not ns.allow_different_commits:
        print(f"ERROR: {why}. A moved line would then mean nothing, so this refuses rather than "
              f"guessing. Re-run with --allow-different-commits to see advisory verdicts.",
              file=sys.stderr)
        return 2
    verdicts = compare(baseline, candidate, repo)
    if ns.json:
        print(json.dumps({"baseline_arrows": len(arrows(baseline)),
                          "candidate_arrows": len(arrows(candidate)),
                          "same_source": ok, "source_note": why,
                          "lost": [{"src": v.arrow.src_file, "dst": v.arrow.dst_file,
                                    "verb": v.arrow.verb, "where": v.arrow.where,
                                    "verdict": v.verdict, "reason": v.reason} for v in verdicts]},
                         indent=2))
    else:
        sys.stdout.write(report(verdicts, len(arrows(baseline)), len(arrows(candidate))))
    return 1 if any(v.verdict == LOST_TRUTH for v in verdicts) else 0


if __name__ == "__main__":
    raise SystemExit(main())
