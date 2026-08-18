#!/usr/bin/env python3
"""`coyodex provenance` — record WHICH session built the map, and WHEN.

`finalize` refuses to bless a commit whose `.coyodex/provenance.json` is missing, and the file was
produced only by `tools/map_backup.py` — a script in the coyodex clone that the SHIPPED CLI does
not install. So a build that had done everything right hit a gate demanding an artifact no
`coyodex` command could make: one live build ran `finalize`, was told to produce provenance,
re-ran `finalize` without it, got the identical complaint, and only then went looking for the
script. That is the whole reason this module exists as a command.

The model lives here and `map_backup.py` imports it, so the stamp the CLI writes and the stamp the
backup tool reads can never drift into two shapes of the same file. Stdlib-only.
"""
from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from coyodex import subverb_help

COYODEX_SUBDIR = ".coyodex"
PROVENANCE_NAME = "provenance.json"
PROVENANCE_SCHEMA = "coyodex-provenance/v1"
SESSION_ENV = "CLAUDE_CODE_SESSION_ID"


@dataclasses.dataclass
class SessionEntry:
    session_id: str
    built_at: str                     # local wall-clock, minute precision: "YYYY-MM-DD HH:MM"
    mode: str                         # build | accept | rebuild
    code_commit: str | None = None    # short sha of the analyzed repo at build time
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
        schema = raw.get("schema")
        return Provenance(
            project=project if isinstance(project, str) else "",
            repo_path=repo_path if isinstance(repo_path, str) else "",
            sessions=sessions,
            schema=schema if isinstance(schema, str) else PROVENANCE_SCHEMA,
        )


def git_value(repo: Path, *args: str) -> str | None:
    try:
        # TIMEOUT, and a wide except: this runs inside `assemble`, immediately before the map is
        # written. A `git` that blocks — a credential prompt, a stalled filesystem, a hook — used
        # to lose the whole assembly rather than the one optional value it was fetching. No git
        # answer is ever worth more than the work already done.
        out = subprocess.run(["git", "-C", str(repo), *args],
                             capture_output=True, text=True, check=True, timeout=5,
                             stdin=subprocess.DEVNULL,
                             env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"})
    except (subprocess.SubprocessError, OSError):
        return None
    return out.stdout.strip() or None


def now_minute() -> str:
    """Local wall-clock, minute precision. Build time per the user's choice."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def stamp(repo: Path, mode: str = "build", session_id: str | None = None,
          built_at: str | None = None) -> tuple[Path, SessionEntry, list[str]]:
    """Write (or refresh) this session's entry in `<repo>/.coyodex/provenance.json`.

    Returns the path, the entry written, and any warnings. A CORRUPT file is rewritten from
    scratch with a warning rather than refused: the stamp is the repair."""
    warnings: list[str] = []
    coyodex_dir = repo / COYODEX_SUBDIR
    if not coyodex_dir.is_dir():
        raise FileNotFoundError(f"no {COYODEX_SUBDIR}/ directory under {repo}")
    sid = session_id or os.environ.get(SESSION_ENV)
    if not sid:
        raise ValueError(f"no session id: set ${SESSION_ENV} (present inside a Claude Code "
                         f"session) or pass --session-id")
    entry = SessionEntry(
        session_id=sid,
        built_at=built_at or now_minute(),
        mode=mode,
        code_commit=git_value(repo, "rev-parse", "--short", "HEAD"),
        code_committed=git_value(repo, "show", "-s", "--format=%cs", "HEAD"),
    )
    path = coyodex_dir / PROVENANCE_NAME
    try:
        prov = Provenance.load(path)
    except ValueError as exc:
        warnings.append(f"warning: {exc}; rewriting from scratch")
        prov = None
    if prov is None:
        prov = Provenance(project=repo.name, repo_path=str(repo))
    prov.project = prov.project or repo.name
    prov.repo_path = str(repo)          # keep fresh in case the repo moved
    prov.upsert(entry)
    path.write_text(prov.to_json(), encoding="utf-8")
    return path, entry, warnings


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────

_MODES = ("build", "accept", "rebuild")

USAGE = """usage: coyodex provenance stamp [<repo>] [--mode build|accept|rebuild]
                                [--session-id <id>] [--built-at 'YYYY-MM-DD HH:MM']
                                [--update-header <header-fragment.json>]
       coyodex provenance show [<repo>]

stamp   Record this session's id + minute-precise build time in <repo>/.coyodex/provenance.json —
        the file `finalize` requires before a map is committed. <repo> defaults to the current
        directory. The session id comes from $CLAUDE_CODE_SESSION_ID unless --session-id overrides
        it.

        --update-header <header-fragment.json>
                WRITE the stamped minute straight into that fragment's `built`, so the header and
                provenance cannot disagree. USE THIS. Without it the only way to close the loop is
                to read `built_at=...` off stdout and hand-write it back, and hand-writing it is a
                map write in the middle of the one closing sequence: builds did it with a
                `python3 - <<'PY'` heredoc that json-loads the fragment, sets one string and dumps
                it back. This flag exists because of that, and a build still hand-rolled it the day
                after it shipped: this help told the reader to carry the minute across by hand and
                named no alternative, so the alternative went unfound.

        Prints `built_at=YYYY-MM-DD HH:MM` on stdout either way, so a caller that needs the value
        for something else still has it.
        Re-stamping the SAME session updates its entry rather than appending a second one.

show    Print the recorded sessions, newest last."""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 2
    verb, rest = argv[0], argv[1:]
    if verb not in ("stamp", "show"):
        print(f"coyodex provenance: unknown verb '{verb}'\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    helped = subverb_help.handle(USAGE, verb, rest)
    if helped is not None:
        return helped
    repo_arg = None
    mode = "build"
    session_id = built_at = header_path = None
    i = 0
    while i < len(rest):
        a = rest[i]
        if a in ("--mode", "--session-id", "--built-at", "--update-header"):
            i += 1
            if i >= len(rest):
                print(f"ERROR: {a} needs a value", file=sys.stderr)
                return 2
            if a == "--mode":
                mode = rest[i]
            elif a == "--session-id":
                session_id = rest[i]
            elif a == "--update-header":
                header_path = rest[i]
            else:
                built_at = rest[i]
        elif a.startswith("-"):
            print(f"ERROR: unknown option '{a}'\n{USAGE}", file=sys.stderr)
            return 2
        else:
            repo_arg = a
        i += 1
    repo = Path(repo_arg or ".").resolve()
    if verb == "show":
        path = repo / COYODEX_SUBDIR / PROVENANCE_NAME
        try:
            prov = Provenance.load(path)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if prov is None:
            print(f"{path} does not exist — this map is un-stamped. Run `coyodex provenance stamp`.")
            return 1
        print(f"{prov.project} ({prov.repo_path}) — {len(prov.sessions)} session(s)")
        for s in prov.sessions:
            print(f"  {s.built_at}  {s.mode:<8} {s.session_id}"
                  f"{f'  code {s.code_commit}' if s.code_commit else ''}")
        return 0
    if mode not in _MODES:
        print(f"ERROR: --mode must be one of {', '.join(_MODES)}", file=sys.stderr)
        return 2
    try:
        path, entry, warnings = stamp(repo, mode=mode, session_id=session_id, built_at=built_at)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for w in warnings:
        print(f"coyodex provenance: {w}", file=sys.stderr)
    if header_path is not None:
        rc = _write_header_built(Path(header_path), entry.built_at)
        if rc:
            return rc
    # stdout carries the one value the build must copy verbatim; the human line goes to stderr, so
    # `built_at=$(coyodex provenance stamp)` is a usable idiom.
    print(f"built_at={entry.built_at}")
    print(f"stamped {path} (session {entry.session_id}, mode {entry.mode})", file=sys.stderr)
    return 0


def _write_header_built(header: Path, built_at: str) -> int:
    """Put `built_at` in the header fragment's `built`. Returns a non-zero exit on failure.

    The alternative, and what builds actually did, is a `python3 - <<'PY'` heredoc that json-loads
    the fragment, sets one string and dumps it back — a hand-written map write in the middle of the
    one sequence, for a value the tool had just printed. It is a two-line edit, which is exactly why
    it should not be hand-rolled: the failure mode is a header and a provenance file that disagree,
    and nothing downstream compares them."""
    try:
        data = json.loads(header.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"ERROR: --update-header {header}: {exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"ERROR: --update-header {header} is not JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print(f"ERROR: --update-header {header} is not a fragment object", file=sys.stderr)
        return 2
    was = data.get("built")
    data["built"] = built_at
    header.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"header {header.name}: built {was!r} -> {built_at!r}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
