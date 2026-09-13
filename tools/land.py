#!/usr/bin/env python3
"""Land a worktree branch on main: merge main in, run the gates, fast-forward main — and again if
main moved meanwhile. FOR SOMEONE WORKING ON COYOMAP in a git worktree, not for users.

Run it with `make land` from inside the worktree. The order is the one that keeps every conflict
inside the checkout nobody else is typing in:

  1. `git merge main` INTO the worktree branch. A conflict stops here with the files named:
     resolve, commit, run again. The merge is left in place, never aborted.
  2. The full gates on the merge result — a COMMITTED tree, because the checks that read the
     working tree fail on a mid-merge one.
  3. `git merge --ff-only <branch>` run FROM the main checkout, so its ref, index and files move
     together. Moving the ref alone (`update-ref`) leaves that folder's files behind, and its
     `git status` then shows the landed work as deletions.
  4. Main moved while the gates ran? Six minutes is long enough: it moved twice on 2026-09-12,
     once into the very file being landed. Back to step 1, bounded by --attempts.

Usage: land.py [--target main] [--attempts 3] [--gates "<shell command>"]
  --gates replaces the gate command (the tests pass `true`); the default is `make gates` with the
  main checkout's venv and this worktree's tools on PYTHONPATH, which is what a worktree needs.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

VIEWER_DIR = "tools/coyomap/viewer/"


class LandError(Exception):
    """Why landing stopped, and the exit code that says so: 1 preflight, 2 conflict, 3 gates,
    4 the main checkout refused the fast-forward, 5 main kept moving."""

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def git_out(*args: str, cwd: Path) -> str:
    done = git(*args, cwd=cwd)
    if done.returncode != 0:
        raise LandError(f"git {' '.join(args)} failed: {done.stderr.strip()}", 1)
    return done.stdout.strip()


def main_checkout(repo: Path) -> Path:
    """The first entry of `git worktree list` is the main worktree: the folder this one branched from."""
    first = git_out("worktree", "list", "--porcelain", cwd=repo).splitlines()[0]
    if not first.startswith("worktree "):
        raise LandError(f"cannot read the worktree list: {first!r}", 1)
    return Path(first[len("worktree "):])


def preflight(repo: Path, target: str) -> tuple[str, Path]:
    """The branch to land and the main checkout to land it in — or the reason nothing can start."""
    branch = git_out("branch", "--show-current", cwd=repo)
    if not branch:
        raise LandError("not on a branch (detached HEAD)", 1)
    if branch == target:
        raise LandError(f"on {target} itself; land runs from a worktree branch", 1)
    if git_out("status", "--porcelain", cwd=repo):
        raise LandError("this worktree has uncommitted changes; commit them first", 1)
    main = main_checkout(repo)
    if main.resolve() == repo.resolve():
        raise LandError("this is the main checkout, not a worktree", 1)
    if git_out("branch", "--show-current", cwd=main) != target:
        raise LandError(f"the main checkout is not on {target}", 4)
    return branch, main


def merge_target_in(repo: Path, target: str) -> bool:
    """Merge the target into the branch. True when HEAD moved. A conflict stops with the files
    named and the merge left in place for the person to resolve."""
    before = git_out("rev-parse", "HEAD", cwd=repo)
    done = git("merge", "--no-edit", target, cwd=repo)
    if done.returncode != 0:
        conflicted = git_out("diff", "--name-only", "--diff-filter=U", cwd=repo).splitlines()
        detail = "\n  ".join(conflicted) if conflicted else done.stderr.strip()
        raise LandError(f"merging {target} in stopped on conflicts — resolve them in this worktree, "
                        f"commit, and run again:\n  {detail}", 2)
    return git_out("rev-parse", "HEAD", cwd=repo) != before


def run_gates(repo: Path, main: Path, command: str | None) -> None:
    """The gates on the tree as it stands, output streamed. The exit code decides, never the banner."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(repo / "tools"), str(repo / "eval" / "tools")])
    cmd = command or f"make gates VENV={main / '.venv'}"
    print(f"gates: {cmd}", flush=True)
    done = subprocess.run(cmd, cwd=repo, shell=True, env=env)
    if done.returncode != 0:
        raise LandError(f"gates failed (exit {done.returncode}); nothing landed", 3)


def target_moved(repo: Path, target: str) -> bool:
    """Has the target gained commits this branch does not hold?"""
    return git("merge-base", "--is-ancestor", target, "HEAD", cwd=repo).returncode != 0


def fast_forward(main: Path, branch: str) -> bool:
    """Run from the main checkout so ref, index and files move together. False when the target
    moved on since the check (try again); any other refusal stops landing."""
    done = git("merge", "--ff-only", branch, cwd=main)
    if done.returncode == 0:
        return True
    if "fast-forward" in done.stderr.lower():
        return False
    raise LandError(f"the main checkout refused the fast-forward: {done.stderr.strip()}", 4)


def land(repo: Path, target: str, attempts: int, gates_command: str | None) -> int:
    branch, main = preflight(repo, target)
    for attempt in range(1, attempts + 1):
        moved = merge_target_in(repo, target)
        print(f"[{attempt}] {target} merged into {branch}: "
              f"{'a new merge commit' if moved else 'already up to date'}", flush=True)
        run_gates(repo, main, gates_command)
        if target_moved(repo, target):
            print(f"[{attempt}] {target} moved while the gates ran; merging it in again", flush=True)
            continue
        old_target = git_out("rev-parse", target, cwd=repo)
        if not fast_forward(main, branch):
            print(f"[{attempt}] {target} moved between the gates and the fast-forward; again", flush=True)
            continue
        head = git_out("rev-parse", "--short", "HEAD", cwd=repo)
        print(f"landed: {target} is at {head} — ref, index and files together", flush=True)
        changed = git_out("diff", "--name-only", f"{old_target}..HEAD", cwd=repo).splitlines()
        if any(f.startswith(VIEWER_DIR) for f in changed):
            print("viewer files landed: the dev server keeps the viewer.js it started with — restart it",
                  flush=True)
        return 0
    raise LandError(f"{target} kept moving through {attempts} attempt(s); nothing landed", 5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", default="main", help="the branch to land on (default: main)")
    parser.add_argument("--attempts", type=int, default=3, help="how often to retry when the target moves")
    parser.add_argument("--gates", default=None, help="shell command to run as the gates (default: make gates)")
    args = parser.parse_args(argv)
    try:
        return land(Path.cwd(), args.target, args.attempts, args.gates)
    except LandError as exc:
        print(f"land: {exc}", file=sys.stderr, flush=True)
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main())
