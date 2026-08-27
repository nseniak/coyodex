#!/usr/bin/env python3
"""`coyodex ship` — the build's closing sequence as ONE command.

`method.md` closes a build with a numbered sequence (anchor-drift → apply-drift → assemble →
grounding report → grounding write → assemble → provenance stamp → assemble → lint the header →
validate → audit → render → finalize). Every step is deterministic given its inputs, and the two
judgement points are OUTSIDE the steps: reconciling the refutations (before), and writing the
grounding note (between report and write). Run by hand, the sequence has been re-done on real
builds — `finalize` run twice with the second run overwriting the report, the grounding record
written twice, a hand-scripted header edit landing as the build's last write.

So this command runs the mechanical tail and stops where judgement is needed:

  without --note-file   PREPARE: anchor-drift → apply-drift --to-reconcile → assemble →
                        grounding report. Then STOP: read the report, write the note.
  with --note-file      FINISH: the same three (idempotent), then grounding write → assemble →
                        provenance stamp --update-header → assemble → lint-fragment header →
                        validate --check-sources → audit → render → finalize --emit-gate-block.

A failed step STOPS the run and names itself — a skipped step must never read as a clean one.
Every step is the ordinary subcommand with its documented flags, invoked in-process; `ship` adds
no check and writes nothing of its own.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

USAGE = """usage: coyodex ship <repo> [--note-file <path>] [--partial] [--keep-note]
                    [--access-baseline <map-or-surface.json>]
                    [--worklist <audit.json>] [--reconcile <file>]
                    [--verdicts <raw.json>]... [--fragments <dir>]

The closing sequence of a build (method.md's numbered list) as one command.
Defaults, all under <repo>/.coyodex/: the map at project-map.json, fragments at
build-fragments/*.json, the reconcile file at reconcile.json, the pinned worklist at
verify/worklist.json, verdicts at verify/verdicts-*.json, the gate block written to
verify/gate-block.md.

Two phases, split where the ONE judgement input sits:
  no --note-file : anchor-drift, apply-drift --to-reconcile, assemble, grounding report —
                   then stop, so the note is written FROM the report.
  --note-file    : the full tail through finalize. --partial / --keep-note forward to
                   `grounding write`; --access-baseline forwards to `finalize`.
"""

#: The subcommand names a Step may use — the same names `coyodex <cmd>` dispatches on.
Runner = Callable[[list[str]], int]


@dataclass(frozen=True)
class Step:
    title: str
    argv: tuple[str, ...]  # argv[0] is the subcommand name


@dataclass(frozen=True)
class ShipInputs:
    repo: Path
    out: Path                 # <repo>/.coyodex
    map_path: Path
    fragments: tuple[Path, ...]
    reconcile: Path | None    # None = no reconcile.json on disk (assemble runs without it)
    worklist: Path
    verdicts: tuple[Path, ...]
    header: Path
    md: Path
    gate_block: Path
    note_file: Path | None
    partial: bool
    keep_note: bool
    access_baseline: Path | None


def derive_inputs(repo: Path,
                  note_file: Path | None = None,
                  partial: bool = False,
                  keep_note: bool = False,
                  access_baseline: Path | None = None,
                  worklist: Path | None = None,
                  reconcile: Path | None = None,
                  verdicts: tuple[Path, ...] | None = None,
                  fragments_dir: Path | None = None) -> ShipInputs | str:
    """Resolve every path the sequence needs, or return an error string saying what is missing.

    Globs are sorted, matching the shell's lexicographic `*.json` — fragment ARGUMENT ORDER decides
    dedup survivors, so it must be stable across the repeated assembles.
    """
    out = repo / ".coyodex"
    frag_dir = fragments_dir if fragments_dir is not None else out / "build-fragments"
    if not frag_dir.is_dir():
        return f"no fragments directory at {frag_dir} — nothing to assemble; ship is the BUILD closer"
    frags = tuple(sorted(p for p in frag_dir.glob("*.json") if not p.name.endswith(".draft.json")))
    if not frags:
        return f"no fragments in {frag_dir} — nothing to assemble"
    wl = worklist if worklist is not None else out / "verify" / "worklist.json"
    if not wl.is_file():
        return (f"no pinned worklist at {wl} — capture it BEFORE reconciling refutations "
                "(coyodex audit <map> --json > .coyodex/verify/worklist.json), or pass --worklist")
    vd = verdicts if verdicts else tuple(sorted((out / "verify").glob("verdicts-*.json")))
    if not vd:
        return (f"no verdicts files under {out / 'verify'} — the Phase-4 skeptics' output is a "
                "required input; pass --verdicts, or run the sequence by hand for a map with no "
                "claim surface")
    rec = reconcile if reconcile is not None else out / "reconcile.json"
    rec_final: Path | None = rec if rec.is_file() else None
    return ShipInputs(
        repo=repo, out=out, map_path=out / "project-map.json", fragments=frags,
        reconcile=rec_final, worklist=wl, verdicts=vd,
        header=frag_dir / "header.json", md=out / "project-map.md",
        gate_block=out / "verify" / "gate-block.md",
        note_file=note_file, partial=partial, keep_note=keep_note,
        access_baseline=access_baseline)


def _assemble_step(s: ShipInputs, title: str) -> Step:
    argv: list[str] = ["assemble", *map(str, s.fragments), "--out", str(s.out)]
    if s.reconcile is not None:
        argv += ["--reconcile", str(s.reconcile)]
    return Step(title, tuple(argv))


def _verdict_flags(s: ShipInputs) -> list[str]:
    flags: list[str] = []
    for v in s.verdicts:
        flags += ["--verdicts", str(v)]
    return flags


def build_plan(s: ShipInputs) -> list[Step]:
    """The method's closing list, steps 2-12, cut at the note. Step numbers cite method.md."""
    prepare = [
        Step("anchor-drift (step 2 — what drifted)",
             ("anchor-drift", "--map", str(s.map_path), *_verdict_flags(s))),
        Step("fix apply-drift --to-reconcile (step 3 — record the corrections)",
             ("fix", "apply-drift", "--map", str(s.map_path), *_verdict_flags(s),
              "--to-reconcile", str(s.reconcile if s.reconcile is not None
                                    else s.out / "reconcile.json"))),
        _assemble_step(s, "assemble (step 4 — last structural assemble)"),
        Step("grounding report (step 5 — what the note is written from)",
             ("grounding", "report", "--worklist", str(s.worklist), *_verdict_flags(s),
              "--map", str(s.map_path))),
    ]
    if s.note_file is None:
        return prepare
    write_argv: list[str] = ["grounding", "write", "--worklist", str(s.worklist),
                             *_verdict_flags(s), "--map", str(s.map_path),
                             "--note-file", str(s.note_file),
                             "--out", str(s.header.parent / "grounding.json")]
    if s.partial:
        write_argv.append("--partial")
    if s.keep_note:
        write_argv.append("--keep-note")
    finalize_argv: list[str] = ["finalize", str(s.map_path), "--repo", str(s.repo),
                                *_verdict_flags(s), "--emit-gate-block", str(s.gate_block)]
    if s.access_baseline is not None:
        finalize_argv += ["--access-baseline", str(s.access_baseline)]
    # prepare[:-1]: the report leg is for writing the note; with the note in hand it is finalize's
    # and grounding write's own reads that matter, and `report` would only repeat what was read.
    return prepare[:3] + [
        Step("grounding write (step 6 — the record, measured against the map)", tuple(write_argv)),
        _assemble_step(s, "assemble (step 7 — carries the record in)"),
        Step("provenance stamp (step 8 — stamps and fills `built`)",
             ("provenance", "stamp", str(s.repo), "--mode", "build",
              "--update-header", str(s.header))),
        _assemble_step(s, "assemble (step 9 — the filled header reaches the map)"),
        Step("lint-fragment header (step 10 — the one hand-authored fragment)",
             ("lint-fragment", str(s.header))),
        Step("validate --check-sources (step 11a)",
             ("validate", str(s.map_path), "--check-sources", "--repo", str(s.repo))),
        Step("audit (step 11b)", ("audit", str(s.map_path))),
        Step("render (step 11c)", ("render", str(s.map_path), str(s.md))),
        Step("finalize (step 12 — one run, both flags)", tuple(finalize_argv)),
    ]


def default_runner(argv: list[str]) -> int:
    """Dispatch one step to its subcommand main(), lazily — the same firewall as cli.py."""
    cmd, rest = argv[0], argv[1:]
    if cmd == "anchor-drift":
        from coyodex import anchor_drift
        return anchor_drift.main(rest)
    if cmd == "fix":
        from coyodex import fix
        return fix.main(rest)
    if cmd == "assemble":
        from coyodex import assemble
        return assemble.main(rest)
    if cmd == "grounding":
        from coyodex import grounding
        return grounding.main(rest)
    if cmd == "provenance":
        from coyodex import provenance
        return provenance.main(rest)
    if cmd == "lint-fragment":
        from coyodex import lint_fragment
        return lint_fragment.main(rest)
    if cmd == "validate":
        from coyodex import validate_model
        return validate_model.main(rest)
    if cmd == "audit":
        from coyodex import audit_model
        return audit_model.main(rest)
    if cmd == "render":
        from coyodex.viewer import render
        return render.main(rest)
    if cmd == "finalize":
        from coyodex import finalize
        return finalize.main(rest)
    print(f"ship: unknown step subcommand '{cmd}'", file=sys.stderr)
    return 2


def run_plan(steps: list[Step], runner: Runner) -> int:
    """Run the steps in order; STOP at the first non-zero exit, naming the step.

    A skipped step must never read as a clean one, so the failure line says which steps did NOT
    run — the exact information three hand-run sequences lost on real builds.
    """
    for i, step in enumerate(steps):
        print(f"\n=== ship [{i + 1}/{len(steps)}] {step.title}")
        print("    " + " ".join(step.argv))
        rc = runner(list(step.argv))
        if rc != 0:
            remaining = [s.title for s in steps[i + 1:]]
            print(f"\nSHIP STOPPED at [{i + 1}/{len(steps)}] {step.title} (exit {rc}).",
                  file=sys.stderr)
            if remaining:
                print("NOT RUN: " + " · ".join(remaining), file=sys.stderr)
            print("Fix the step's own report, then re-run ship — every step is safe to repeat.",
                  file=sys.stderr)
            return rc
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    repo: Path | None = None
    note_file: Path | None = None
    partial = keep_note = False
    access_baseline: Path | None = None
    worklist: Path | None = None
    reconcile: Path | None = None
    fragments_dir: Path | None = None
    verdicts: list[Path] = []
    it = iter(args)
    for a in it:
        if a == "--note-file":
            note_file = Path(next(it, ""))
        elif a == "--partial":
            partial = True
        elif a == "--keep-note":
            keep_note = True
        elif a == "--access-baseline":
            access_baseline = Path(next(it, ""))
        elif a == "--worklist":
            worklist = Path(next(it, ""))
        elif a == "--reconcile":
            reconcile = Path(next(it, ""))
        elif a == "--fragments":
            fragments_dir = Path(next(it, ""))
        elif a == "--verdicts":
            verdicts.append(Path(next(it, "")))
        elif a.startswith("-"):
            print(f"ship: unknown option '{a}'\n{USAGE}", file=sys.stderr)
            return 2
        elif repo is None:
            repo = Path(a)
        else:
            print(f"ship: unexpected argument '{a}'\n{USAGE}", file=sys.stderr)
            return 2
    if repo is None:
        print(f"ship: <repo> is required\n{USAGE}", file=sys.stderr)
        return 2
    if note_file is not None and not note_file.is_file():
        print(f"ship: --note-file {note_file} does not exist — write the note first "
              "(the grounding report from the prepare phase is what it is written from)",
              file=sys.stderr)
        return 2
    inputs = derive_inputs(repo, note_file=note_file, partial=partial, keep_note=keep_note,
                           access_baseline=access_baseline, worklist=worklist,
                           reconcile=reconcile,
                           verdicts=tuple(verdicts) if verdicts else None,
                           fragments_dir=fragments_dir)
    if isinstance(inputs, str):
        print(f"ship: {inputs}", file=sys.stderr)
        return 2
    if inputs.reconcile is None:
        print("ship: note — no reconcile.json found; assemble runs WITHOUT --reconcile. If the "
              "build authored one elsewhere, stop and pass --reconcile: an assemble without it "
              "silently reverts every assignment.")
    rc = run_plan(build_plan(inputs), default_runner)
    if rc != 0:
        return rc
    if inputs.note_file is None:
        print("\nSHIP PREPARED — the grounding report above is the reconcile worklist. Read it "
              "whole, write the grounding note to a file, then re-run:\n"
              f"  coyodex ship {inputs.repo} --note-file <path> [--partial]")
    else:
        print("\nSHIP COMPLETE — quote finalize's verdict line in the commit message "
              f"(gate block at {inputs.gate_block}), then commit the map, the .md, the pre-index "
              "and provenance. finalize printed the exact `git add -f` line.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
