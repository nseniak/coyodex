#!/usr/bin/env python3
"""Archive a repo's coyodex map into `.coyodex/dev-rebuilds/NNNN/`, clearing the way for a rebuild.

**A COYODEX-DEVELOPER convention, not something a user should adopt** — hence the `dev-` prefix, on
disk where it cannot be missed. A user's map EVOLVES INCREMENTALLY alongside their code: a from-scratch
rebuild is a first-run event for them, so they never accumulate previous maps. Rebuilding over and over
is what someone changing coyodex itself does, and these snapshots are the baselines `/coyodex-retro`
and `/coyodex-eval` (both developer commands) compare a fresh map against. No production code path
reads this directory.

WHY THIS EXISTS. `method/dispatch.md` decides Build vs Analyze by looking for
`.coyodex/project-map.json` **in the working tree** — "a deleted working-tree file is a deliberate
signal to start from scratch", and it forbids recovering the old map from git. So a from-scratch
rebuild means getting the current map out of the way first, and the only safe way to do that is to
MOVE it, never delete it: the old map is the baseline you diff the new one against, and it holds
curation (recorded exceptions, adjudications, Phase-4 corrections) that a rebuild must re-derive.

Doing it by hand is how the archives already in the wild got their shape — one live repo has ten of
them — and hand-moving is exactly where a stray `rm` or a clobbered directory costs a whole build.

WHAT MOVES. Everything in `.coyodex/` except `dev-rebuilds/` itself and the two files that are
DECLARATIONS ABOUT THE REPO rather than build output — `.gitignore` (coyodex writes it, and the next
assemble expects it) and `.ignore` (which code the map is not meant to describe). That is
deliberately a denylist, not a list of known filenames: a future artifact should be archived by
default rather than silently left behind to confuse the next build.

WHY `.ignore` STAYS. It is scope, not output. `iter_source_files` honours it, so it decides which
files feed the coverage check AND the code-derived component expectation E. Archiving it away
silently rescopes the tree for the next build and for every later scoring of ANY map: measured on
this repo, moving `.ignore` aside took E from 14 to 37 (+164%), which flipped the current map's
granularity band from DRIFT (36 vs 14) to PASS (36 vs 37) with no change to the map or the code.
The eval compares an archived map against a current one, so a rescope between the two is exactly
the confound its same-code guard exists to prevent — and the guard cannot see it, because it
excludes `.coyodex/` wholesale. Keeping the file in place removes the trap instead of documenting it.

    coyodex-eval archive <repo-root> [--dry-run]

WHY IT IS A `coyodex-eval` SUBCOMMAND. It was a loose script under `eval/scripts/`, invoked by an
absolute path that every caller had to spell out — the shape that makes a tool easy to hand-roll
around instead. `coyodex-eval` is the developer-only CLI (`eval/` is the developer-only tree, and
the `/coyodex-eval` and `/coyodex-retro` skills say so), so this belongs beside `retro-precheck`
and `process`: discoverable from `coyodex-eval --help`, and reachable without knowing a path.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

#: The container for every archived map. NESTED, so `.coyodex/` holds one entry instead of the dozen
#: sibling dot-directories the flat `.old-ignore*` convention accumulated.
ARCHIVE_DIR = "dev-rebuilds"
#: Zero-padded, so a lexical sort IS a numeric sort. The flat convention was unpadded, which made
#: `-9` sort after `-10` as text; the docstring below warned about it and a consumer still got it
#: wrong (a baseline picker sorted on name length and chose the wrong archive in 28 of 40 trials).
#: Padding removes the trap instead of documenting it.
ARCHIVE_WIDTH = 4
# Kept in place: `.gitignore` is coyodex's own (it ignores build-fragments/ and the archives),
# `.ignore` is the repo's analysis-scope declaration and moving it rescopes E and coverage for every
# later build and score (see WHY `.ignore` STAYS above), and archiving the archive container would
# nest it one inside the next on every run.
KEEP = {".gitignore", ".ignore", ARCHIVE_DIR}


def next_archive_dir(coyodex: Path) -> Path:
    """The next archive: `dev-rebuilds/0001`, `0002`, … — zero-padded so any sort is right.

    ALWAYS highest + 1, never the smallest free number. Filling a gap left by a manual delete keeps
    the names dense but destroys what the number is for: with `0001`, `0002`, `0003` on disk, deleting
    `0002` and archiving again would put the NEWEST map in `0002`, between two older ones. The common
    cleanup — pruning the OLDEST archives — is worse still: the next map would land in `0001`, the name
    that reads as "the first one", so the sequence reads exactly backwards. Monotonic numbering means
    the number always encodes recency and cannot lie. The cost is a cosmetic gap after a delete, which
    is a far better failure than a wrong order."""
    container = coyodex / ARCHIVE_DIR
    highest = 0
    if container.is_dir():
        for p in container.iterdir():
            if p.is_dir() and p.name.isdigit():   # ignore any hand-named sibling ("broken", "keep")
                highest = max(highest, int(p.name))
    return container / f"{highest + 1:0{ARCHIVE_WIDTH}d}"


def movable_entries(coyodex: Path) -> list[Path]:
    """Everything that should be archived, sorted for a stable report."""
    return sorted((p for p in coyodex.iterdir() if p.name not in KEEP), key=lambda p: p.name)


def archive(root: Path, dry_run: bool = False) -> tuple[Path | None, list[Path]]:
    """Move the map aside. Returns `(archive dir, entries moved)`; `(None, [])` when there is
    nothing to archive, which is not an error — it is the state a fresh build wants."""
    coyodex = root / ".coyodex"
    if not coyodex.is_dir():
        raise FileNotFoundError(f"no .coyodex/ directory under {root}")
    entries = movable_entries(coyodex)
    if not entries:
        return None, []
    dest = next_archive_dir(coyodex)
    if dry_run:
        return dest, entries
    dest.mkdir(parents=True)   # `dev-rebuilds/` may not exist yet
    moved: list[Path] = []
    try:
        for p in entries:
            shutil.move(str(p), str(dest / p.name))
            moved.append(p)
    except OSError:
        # Put back what already moved, so a failure half-way leaves the map usable rather than
        # split across two directories with no record of which half is which.
        for p in moved:
            shutil.move(str(dest / p.name), str(p))
        dest.rmdir()
        if not any((dest.parent).iterdir()):      # we created the container on this run — undo that too
            dest.parent.rmdir()
        raise
    return dest, entries


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="coyodex-eval archive",
        description="Move a repo's coyodex map into .coyodex/dev-rebuilds/NNNN/ so the next run "
                    "builds from scratch (dispatch.md reads the WORKING TREE to choose the mode).")
    ap.add_argument("root", type=Path, help="the mapped repo's root directory")
    ap.add_argument("--dry-run", action="store_true", help="show what would move, write nothing")
    args = ap.parse_args(argv)

    root: Path = args.root.expanduser().resolve()
    try:
        dest, entries = archive(root, dry_run=args.dry_run)
    except (FileNotFoundError, OSError) as exc:
        print(f"archive: {exc}", file=sys.stderr)
        return 1

    if dest is None:
        print(f"archive: nothing to archive in {root / '.coyodex'} "
              "(already clear — a build here starts from scratch)")
        return 0
    verb = "would move" if args.dry_run else "moved"
    rel = dest.relative_to(root)
    print(f"archive: {verb} {len(entries)} entry/entries -> {rel}/")
    for p in entries:
        # After a real move the source path is gone, so ask the side that now holds it.
        landed = p if args.dry_run else dest / p.name
        print(f"  {p.name}{'/' if landed.is_dir() else ''}")
    if not args.dry_run:
        print("\nThe working tree now has no project-map.json, so `/coyodex` will BUILD.\n"
              f"The previous map is intact in {rel}/ — keep it: it is the baseline the new map is "
              "compared against, and it holds curation a rebuild has to re-derive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
