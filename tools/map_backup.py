#!/usr/bin/env python3
"""Provenance stamping + deterministic backup for a repo's `.coyodex/` map.

Two subcommands:

  stamp   Called by the coyodex BUILD (and accept) flow. Records the session id
          of the conversation that produced the map plus the minute-precise build
          time into `<repo>/.coyodex/provenance.json` (committed, machine-readable).
          Idempotent per session: re-stamping the same session updates its entry.

  backup  Called by the user, later, from any session. Reads the stamped
          provenance, then bundles the map files + the exact conversation
          transcript(s) into `<coyodex-home>/map-backups/<project>-<build-time>/`.
          By default it MOVES the `.coyodex` files out of the source repo; `--keep`
          copies instead. Transcripts are always COPIED (they live in Claude Code's
          live store and must not be moved).

Standalone by design — stdlib only, no third-party imports — so it keeps working
even when the project venv is broken. That is why it uses dataclasses/json rather
than the pydantic models used elsewhere in this repo.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------

COYODEX_HOME = Path(__file__).resolve().parents[1]  # tools/map_backup.py -> repo root
MAP_BACKUPS_DIR = COYODEX_HOME / "map-backups"
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"

COYODEX_SUBDIR = ".coyodex"
PROVENANCE_NAME = "provenance.json"
MAP_MD_NAME = "project-map.md"
PROVENANCE_SCHEMA = "coyodex-provenance/v1"
SESSION_ENV = "CLAUDE_CODE_SESSION_ID"


# ---------------------------------------------------------------------------
# Provenance model (stdlib dataclasses; see module docstring for why not pydantic)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SessionEntry:
    session_id: str
    built_at: str  # local wall-clock, minute precision: "YYYY-MM-DD HH:MM"
    mode: str  # build | accept | rebuild
    code_commit: str | None = None  # short sha of the analyzed repo at build time
    code_committed: str | None = None  # that commit's date, YYYY-MM-DD

    @staticmethod
    def from_dict(d: dict[str, object]) -> "SessionEntry":
        def s(key: str) -> str:
            v = d.get(key)
            return v if isinstance(v, str) else ""

        def opt(key: str) -> str | None:
            v = d.get(key)
            return v if isinstance(v, str) else None

        return SessionEntry(
            session_id=s("session_id"),
            built_at=s("built_at"),
            mode=s("mode") or "build",
            code_commit=opt("code_commit"),
            code_committed=opt("code_committed"),
        )


@dataclasses.dataclass
class Provenance:
    project: str
    repo_path: str
    sessions: list[SessionEntry] = dataclasses.field(default_factory=list)
    schema: str = PROVENANCE_SCHEMA

    def latest(self) -> SessionEntry | None:
        return self.sessions[-1] if self.sessions else None

    def upsert(self, entry: SessionEntry) -> None:
        """Add the entry, or update the existing entry for the same session id."""
        for i, existing in enumerate(self.sessions):
            if existing.session_id == entry.session_id:
                self.sessions[i] = entry
                return
        self.sessions.append(entry)

    def to_json(self) -> str:
        payload: dict[str, object] = {
            "schema": self.schema,
            "project": self.project,
            "repo_path": self.repo_path,
            "sessions": [dataclasses.asdict(s) for s in self.sessions],
        }
        return json.dumps(payload, indent=2) + "\n"

    @staticmethod
    def load(path: Path) -> "Provenance | None":
        """Parse provenance.json. Raises ValueError on a corrupt/non-object file."""
        if not path.is_file():
            return None
        try:
            raw: object = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"{path} is not readable JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"{path} does not contain a JSON object")
        sessions_raw = raw.get("sessions")
        sessions: list[SessionEntry] = []
        if isinstance(sessions_raw, list):
            for item in sessions_raw:
                if isinstance(item, dict):
                    sessions.append(SessionEntry.from_dict(item))
        project = raw.get("project")
        repo_path = raw.get("repo_path")
        return Provenance(
            project=project if isinstance(project, str) else "",
            repo_path=repo_path if isinstance(repo_path, str) else "",
            sessions=sessions,
            schema=raw.get("schema")
            if isinstance(raw.get("schema"), str)
            else PROVENANCE_SCHEMA,  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _run_git(repo: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    value = out.stdout.strip()
    return value or None


def _now_minute() -> str:
    """Local wall-clock, minute precision. Build time per the user's choice."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _compact(built_at: str) -> str:
    """'2026-07-01 06:30' -> '2026-07-01_0630' (filesystem-safe folder label)."""
    return built_at.replace(" ", "_").replace(":", "")


def _map_mtime_minute(coyodex_dir: Path) -> str | None:
    """Minute-precise mtime of the map file, for un-stamped maps.

    Gives an un-stamped backup a *deterministic* folder timestamp tied to when the
    map was last written, rather than the wall-clock at backup time.
    """
    map_file = coyodex_dir / MAP_MD_NAME
    if not map_file.is_file():
        return None
    return datetime.fromtimestamp(map_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def _resolve_coyodex_dir(repo: Path) -> Path:
    coyodex_dir = repo / COYODEX_SUBDIR
    if not coyodex_dir.is_dir():
        _die(f"no {COYODEX_SUBDIR}/ directory under {repo}")
    return coyodex_dir


def _die(msg: str) -> "None":
    print(f"map_backup: error: {msg}", file=sys.stderr)
    raise SystemExit(2)


def _unique_dir(base: Path) -> Path:
    """Avoid clobbering a same-minute backup: base, base_2, base_3, ..."""
    if not base.exists():
        return base
    n = 2
    while True:
        candidate = base.parent / f"{base.name}_{n}"
        if not candidate.exists():
            return candidate
        n += 1


# ---------------------------------------------------------------------------
# Transcript discove1ry
# ---------------------------------------------------------------------------


def _find_transcript_paths(session_id: str) -> list[Path]:
    """Locate a session's transcript file (+ sidechain folder) by UUID.

    A session id is globally unique, so we glob for `<id>.jsonl` and `<id>/`
    across every project dir rather than reconstructing the path-encoding rule.
    """
    if not CLAUDE_PROJECTS.is_dir():
        return []
    found: list[Path] = []
    for p in CLAUDE_PROJECTS.glob(f"*/{session_id}.jsonl"):
        found.append(p)
    for d in CLAUDE_PROJECTS.glob(f"*/{session_id}"):
        if d.is_dir():
            found.append(d)
    return found


_WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}
_MAP_BASENAMES = {MAP_MD_NAME, "project-map.html"}


def _cwd_of_transcript(jsonl: Path) -> str | None:
    """Read the `cwd` field recorded in a transcript (Claude Code stamps it per entry)."""
    try:
        with jsonl.open(encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    cwd = obj.get("cwd")
                    if isinstance(cwd, str) and cwd:
                        return cwd
    except OSError:
        return None
    return None


def _find_project_dir(repo: Path) -> Path | None:
    """Locate the ~/.claude/projects dir holding `repo`'s transcripts.

    Fast path: the '/'->'-' name encoding (correct for the common case). Fallback:
    match the recorded `cwd` inside each project dir's transcripts, so we do not
    depend on the exact punctuation-encoding rule (a wrong guess would otherwise
    silently find nothing).
    """
    if not CLAUDE_PROJECTS.is_dir():
        return None
    fast = CLAUDE_PROJECTS / str(repo).replace("/", "-")
    if fast.is_dir():
        return fast
    target = str(repo)
    for candidate in sorted(CLAUDE_PROJECTS.iterdir()):
        if not candidate.is_dir():
            continue
        for jsonl in candidate.glob("*.jsonl"):
            if _cwd_of_transcript(jsonl) == target:
                return candidate
            break  # one probe per dir is enough (all share the same cwd)
    return None


def _line_wrote_map(obj: object) -> bool:
    """True if this transcript entry is a Write/Edit/MultiEdit of a project-map file.

    Parses the tool_use block and checks its `file_path` basename — so a turn that
    writes some *other* file while merely mentioning 'project-map.md' in prose does
    NOT match (the old substring test did).
    """
    if not isinstance(obj, dict):
        return False
    message = obj.get("message")
    if not isinstance(message, dict):
        return False
    content = message.get("content")
    if not isinstance(content, list):
        return False
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_use" or block.get("name") not in _WRITE_TOOLS:
            continue
        tool_input = block.get("input")
        if not isinstance(tool_input, dict):
            continue
        file_path = tool_input.get("file_path")
        if isinstance(file_path, str) and Path(file_path).name in _MAP_BASENAMES:
            return True
    return False


def _search_transcripts_that_wrote_map(repo: Path) -> list[str]:
    """Fallback for un-stamped maps: session ids whose transcript wrote project-map.*.

    Precise: a transcript qualifies only if it contains a Write/Edit/MultiEdit
    tool_use whose file_path IS a project-map file. Returns session ids (jsonl
    stem), newest first.
    """
    proj_dir = _find_project_dir(repo)
    if proj_dir is None:
        return []
    hits: list[tuple[float, str]] = []
    for jsonl in proj_dir.glob("*.jsonl"):
        try:
            with jsonl.open(encoding="utf-8", errors="ignore") as fh:
                wrote = any(
                    _line_wrote_map(_safe_json(line))
                    for line in fh
                    if _maybe_map_line(line)
                )
        except OSError:
            continue
        if wrote:
            hits.append((jsonl.stat().st_mtime, jsonl.stem))
    hits.sort(reverse=True)
    return [session_id for _, session_id in hits]


def _maybe_map_line(line: str) -> bool:
    """Cheap pre-filter: only JSON-parse lines that could name a map file."""
    return MAP_MD_NAME in line or "project-map.html" in line


def _safe_json(line: str) -> object:
    """Parse a JSONL line, returning None instead of raising on malformed input."""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _copy_transcripts(
    session_ids: list[str], dest: Path, dry_run: bool
) -> tuple[list[str], int]:
    """Copy each session's transcript (+ sidechain dir) into dest.

    Returns (progress notes, number of sessions whose transcript was actually
    found on disk). The count drives the move-guard: never delete the source when
    zero conversations were bundled.
    """
    notes: list[str] = []
    bundled = 0
    for session_id in session_ids:
        paths = _find_transcript_paths(session_id)
        if not paths:
            notes.append(f"  ! transcript not found on disk for session {session_id}")
            continue
        bundled += 1
        for src in paths:
            target = dest / src.name
            if dry_run:
                notes.append(f"  would copy {src} -> {target}")
                continue
            if src.is_dir():
                shutil.copytree(src, target, dirs_exist_ok=True)
            else:
                shutil.copy2(src, target)
            notes.append(f"  copied {src.name}")
    return notes, bundled


# ---------------------------------------------------------------------------
# stamp
# ---------------------------------------------------------------------------


def cmd_stamp(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    coyodex_dir = _resolve_coyodex_dir(repo)

    session_id = args.session_id or os.environ.get(SESSION_ENV)
    if not session_id:
        _die(
            f"no session id: set ${SESSION_ENV} (present inside a Claude Code session) "
            f"or pass --session-id"
        )
    assert session_id is not None  # for the type checker; _die never returns

    built_at = args.built_at or _now_minute()
    entry = SessionEntry(
        session_id=session_id,
        built_at=built_at,
        mode=args.mode,
        code_commit=_run_git(repo, "rev-parse", "--short", "HEAD"),
        code_committed=_run_git(repo, "show", "-s", "--format=%cs", "HEAD"),
    )

    prov_path = coyodex_dir / PROVENANCE_NAME
    try:
        prov = Provenance.load(prov_path)
    except ValueError as exc:
        # Corrupt file: warn and start fresh so this stamp repairs it.
        print(f"map_backup: warning: {exc}; rewriting from scratch", file=sys.stderr)
        prov = None
    if prov is None:
        prov = Provenance(project=repo.name, repo_path=str(repo))
    # keep project/repo_path fresh in case the repo moved
    prov.project = prov.project or repo.name
    prov.repo_path = str(repo)
    prov.upsert(entry)
    prov_path.write_text(prov.to_json(), encoding="utf-8")

    # Emit the timestamp so the build can copy it verbatim into the map header
    # (the "Built:" cell), keeping header and provenance in lock-step to the minute.
    print(f"built_at={built_at}")
    print(
        f"stamped {prov_path} (session {session_id}, mode {args.mode})", file=sys.stderr
    )
    return 0


# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------


def cmd_backup(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    coyodex_dir = _resolve_coyodex_dir(repo)
    dry_run: bool = args.dry_run
    keep: bool = args.keep

    try:
        prov = Provenance.load(coyodex_dir / PROVENANCE_NAME)
    except ValueError as exc:
        _die(f"{exc}; fix or delete it, or re-stamp the map, then retry")
        return 2  # unreachable; keeps the type checker happy

    # Resolve project name, folder timestamp, and the session ids to bundle.
    if prov and prov.latest():
        latest = prov.latest()
        assert latest is not None
        project = prov.project or repo.name
        built_at = latest.built_at or _map_mtime_minute(coyodex_dir) or _now_minute()
        session_ids = [s.session_id for s in prov.sessions]
        prov_note = (
            f"provenance: {len(session_ids)} session(s), latest built {built_at}"
        )
    else:
        project = repo.name
        # No stamp: pin the folder to when the map was written (deterministic across
        # re-runs) rather than to the wall-clock at backup time.
        built_at = _map_mtime_minute(coyodex_dir) or _now_minute()
        session_ids = []
        prov_note = "provenance: none (un-stamped map)"

    # No stamped sessions -> optionally recover them by scanning transcripts.
    searched = False
    if not session_ids and args.search:
        session_ids = _search_transcripts_that_wrote_map(repo)
        searched = True
        prov_note += (
            f"; --search found {len(session_ids)} transcript(s) that wrote the map"
        )

    # Which sessions actually have a transcript on disk? Resolve this UP FRONT so a
    # refused MOVE never creates a half-made backup dir (that dir would also be left
    # behind as litter and force a `_2` suffix on the eventual good run).
    resolvable = [s for s in session_ids if _find_transcript_paths(s)]
    bundled = len(resolvable)

    action = "MOVE" if not keep else "COPY"
    dest_base = MAP_BACKUPS_DIR / f"{project}-{_compact(built_at)}"
    print(f"backup: {action} {coyodex_dir}  ->  {dest_base}")
    print(f"  {prov_note}")

    # A MOVE with no conversation defeats the feature *and* deletes the source. Refuse
    # it before creating anything. (COPY is always safe — it leaves the source intact.)
    if not keep and bundled == 0 and not args.allow_no_conversation:
        hint = "" if searched else " — add --search to recover it"
        print(f"  MOVE refused: no conversation to bundle{hint}.")
        print(
            "  Nothing was created; the source was left in place. Re-run with --search, "
            "or with --keep / --allow-no-conversation to proceed anyway."
        )
        return 3

    if dry_run:
        dest = _unique_dir(dest_base)
        print("  [dry-run] would create:")
        print(f"    {dest / 'map'}/        <- {COYODEX_SUBDIR}/ files ({action.lower()})")
        notes, _ = _copy_transcripts(session_ids, dest / "conversation", dry_run=True)
        print(f"    {dest / 'conversation'}/      <- {bundled} conversation transcript(s)")
        for note in notes:
            print(note)
        if bundled == 0:
            print("  ! no conversation would be bundled (map-only copy)")
        print(
            f"  [dry-run] source {COYODEX_SUBDIR}/ would be "
            f"{'left in place' if keep else 'REMOVED from ' + str(repo)}"
        )
        return 0

    dest = _unique_dir(dest_base)
    dest.mkdir(parents=True, exist_ok=False)

    # 1) Copy the map files first (copy-then-delete, so a mid-run failure loses nothing).
    #    symlinks=True: copy links verbatim instead of crashing on a dangling one.
    shutil.copytree(coyodex_dir, dest / "map", symlinks=True)
    print(f"  copied {COYODEX_SUBDIR}/ -> {dest / 'map'}/")

    # 2) Copy the conversation transcript(s).
    (dest / "conversation").mkdir(parents=True, exist_ok=True)
    notes, bundled = _copy_transcripts(session_ids, dest / "conversation", dry_run=False)
    for note in notes:
        print(note)
    if bundled == 0:
        print("  ! no conversation bundled (map-only copy)")

    # 3) Manifest.
    manifest: dict[str, object] = {
        "schema": "coyodex-map-backup/v1",
        "project": project,
        "source_repo": str(repo),
        "built_at": built_at,
        "backup_run_at": _now_minute(),
        "action": "moved" if not keep else "copied",
        "search_fallback_used": searched,
        "sessions": [dataclasses.asdict(s) for s in prov.sessions] if prov else [],
        "bundled_session_ids": resolvable,
    }
    (dest / "backup-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    # 4) Move => remove the source now that the copy is safely in place.
    if not keep:
        _remove_source(coyodex_dir)
        print(
            f"  removed {coyodex_dir} (moved out; the source repo now shows it deleted)"
        )

    print(f"backup complete: {dest}")
    return 0


def _remove_source(coyodex_dir: Path) -> None:
    """Remove the source .coyodex after its copy is safely in the backup.

    Handles the case where .coyodex is itself a symlink (rmtree would raise on it).
    """
    if coyodex_dir.is_symlink():
        coyodex_dir.unlink()
    else:
        shutil.rmtree(coyodex_dir)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="map_backup",
        description="Stamp provenance into, and back up, a repo's .coyodex/ map.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_stamp = sub.add_parser(
        "stamp",
        help="record session id + minute-precise build time into provenance.json",
    )
    p_stamp.add_argument(
        "repo", help="path to the analyzed repo (the one holding .coyodex/)"
    )
    p_stamp.add_argument(
        "--mode",
        choices=["build", "accept", "rebuild"],
        default="build",
        help="what produced this stamp (default: build)",
    )
    p_stamp.add_argument(
        "--session-id",
        default=None,
        help=f"override the session id (default: ${SESSION_ENV})",
    )
    p_stamp.add_argument(
        "--built-at",
        default=None,
        help="override the build time 'YYYY-MM-DD HH:MM' so the header cell and the "
        "stamp share one minute (default: now, local)",
    )
    p_stamp.set_defaults(func=cmd_stamp)

    p_backup = sub.add_parser(
        "backup", help="bundle the map files + conversation into map-backups/"
    )
    p_backup.add_argument(
        "repo", help="path to the analyzed repo (the one holding .coyodex/)"
    )
    p_backup.add_argument(
        "--keep",
        action="store_true",
        help="copy the map files instead of moving them (leave the source repo intact)",
    )
    p_backup.add_argument(
        "--search",
        action="store_true",
        help="if the map has no stamped sessions, recover them by scanning transcripts",
    )
    p_backup.add_argument(
        "--allow-no-conversation",
        action="store_true",
        help="permit a MOVE (source deletion) even when no conversation was bundled",
    )
    p_backup.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would happen; change nothing",
    )
    p_backup.set_defaults(func=cmd_backup)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
