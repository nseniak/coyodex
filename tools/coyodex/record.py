#!/usr/bin/env python3
"""`coyodex record` — append a recorded exception under an extras heading.

Every advisory family in this tool names an extras heading an operator may write a `<id>: <why>`
line under, and there was no command to write one. So every record was a bespoke string append:

    python3 - <<'PY'
    d = json.load(open('.coyodex/build-fragments/behavioral.json'))
    for x in d['extras']:
        if x['heading'] == 'Balance exceptions':
            x['body'] += "\\nUC5: the two clauses are one goal, ..."
    json.dump(d, open(...,'w'), indent=2)
    PY

One live build did that SIX times against one file. Nothing checked the heading was one the tools
actually read, nothing checked the line's shape, nothing de-duplicated, and nothing protected the
body from the stale-paragraph problem — that build wrote a fourteen-component paragraph, then had to
find-and-replace its own text two turns later with a fragile `body.find(...)` + `assert`.

    coyodex record --map <map-or-fragment> --heading "Balance exceptions" \\
                   --line "UC5: the two clauses are one goal — <why>" [--replace <prefix>]

`--line` REPEATS, and `--lines-from <file|->` reads one per line (blank lines and `#` comments
skipped). One process, one write. Reading only the first `--line` is why a build with 57 records to
make spawned 57 processes — twenty of them re-typing long prose after the first attempt failed — for
what are independent appends under one heading:

    coyodex record --heading "Entry-point coverage" \\
                   --line "http-route: partial — <why>" \\
                   --line "ui-route: complete — <why>"
    coyodex record --heading "Entry-point coverage" --lines-from coverage.txt

Every line is shape-checked BEFORE anything is written, so a bad one in a batch of twenty leaves the
fragment untouched rather than holding half a batch. `--replace` corrects one record, so it refuses
to combine with a batch.

One reason may answer SEVERAL elements — write them as one comma-separated list rather than the
same sentence once per id (live maps grew 66 lines holding 15 distinct reasons that way):

    coyodex record --heading "Unclaimed surfaces" \\
                   --line "C101, C148, C186: an operator surface in our own back office"

Writes the FRAGMENT when given one, so the next `assemble` carries the record through; writing the
assembled map instead is the edit the next assemble discards.

Stdlib-only (the cli.py firewall).
"""
from __future__ import annotations

import sys
from pathlib import Path

from coyodex import records
from coyodex.model import ExtraSection, ProjectModel

USAGE = __doc__

#: The headings the tools actually read, and which of them are the map's own build record — one
#: registry, in `records`, shared with the readers and with the views that decide where a section
#: renders. Recording under anything else is a note to nobody: the check that was supposed to be
#: silenced keeps firing, and the operator believes it was handled.
KNOWN_HEADINGS = records.KNOWN_HEADINGS



def _resolve_heading(heading: str) -> tuple[str, str | None]:
    """`(canonical heading, complaint)`. Matching is the same case/space-tolerant rule the readers
    use, so a record written here is a record they will find."""
    want = heading.strip().lower()
    for known in KNOWN_HEADINGS:
        if known.strip().lower() == want:
            return known, None
    return heading.strip(), (
        f"'{heading}' is not a heading any check reads, so a line under it silences nothing. "
        f"Known: {', '.join(KNOWN_HEADINGS)}")


def append_line(m: ProjectModel, heading: str, line: str,
                replace_prefix: str = "") -> tuple[bool, str]:
    """Append (or replace) one recorded line. Returns `(changed, message)`.

    `replace_prefix` rewrites the existing line that starts with it — the supported way to correct a
    record whose facts moved, instead of a hand-rolled `body.find()` + slice."""
    line = line.strip()
    section = next((x for x in m.extras if x.heading.strip().lower() == heading.strip().lower()),
                   None)
    if section is None:
        section = ExtraSection(heading=heading, body="")
        m.extras.append(section)
    lines = [ln for ln in section.body.splitlines()]
    if replace_prefix:
        hit = next((i for i, ln in enumerate(lines)
                    if ln.strip().lstrip("-* ").startswith(replace_prefix)), None)
        if hit is None:
            return False, (f"no existing line under '{heading}' starts with "
                           f"'{replace_prefix}' — nothing replaced")
        old = lines[hit]
        lines[hit] = line
        section.body = "\n".join(lines).strip() + "\n"
        return True, f"replaced under '{heading}':\n  - {old.strip()}\n  + {line}"
    if any(ln.strip() == line for ln in lines):
        return False, f"already recorded under '{heading}' — nothing to do"
    lines.append(line)
    section.body = "\n".join(ln for ln in lines if ln.strip()).strip() + "\n"
    return True, f"recorded under '{heading}': {line}"


def _arg(argv: list[str], flag: str, default: str = "") -> str:
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def _all_args(argv: list[str], flag: str) -> list[str]:
    """EVERY value given to `flag`, in order — not just the first.

    `_arg` reads one, and this command takes one record per process as a result: a build that had 57
    lines to record spawned 57 processes, twenty of them re-typing long prose after a failed first
    attempt. The lines are independent appends under one heading, so there was never a reason for
    them to be separate runs."""
    out: list[str] = []
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            out.append(argv[i + 1])
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or "-h" in argv or "--help" in argv:
        print(USAGE)
        return 0
    map_path = _arg(argv, "--map", ".coyodex/project-map.json")
    heading = _arg(argv, "--heading")
    lines = _all_args(argv, "--line")
    from_file = _arg(argv, "--lines-from")
    replace = _arg(argv, "--replace")
    # The TARGET is checked before the payload. A build ran 21 well-formed `record` calls in one turn
    # and every one failed with `cannot read … extras.json — no such file`, because no fan-out agent
    # owns creating that fragment; the build worked around it with `echo '{"extras": []}' >`, which is
    # the hand-rolled write this command exists to replace. Probing the failure with a malformed line
    # reported the ARGUMENT complaint first and hid the real cause entirely.
    path = Path(map_path)
    seed_extras = False
    if not path.exists():
        # Seeded, not blindly created: only an `extras.json` inside an existing directory, which is
        # the one file a build is told to record into and the one nothing else creates. Any other
        # missing path is a typo, and silently creating it would hide the typo — the direction that
        # costs an operator an hour.
        if path.name == "extras.json" and path.parent.is_dir():
            # Deferred until the arguments are known good: seeding here left a stray
            # `{"extras": []}` fragment behind every time a call exited 2 on a malformed --line.
            seed_extras = True
        else:
            print(f"ERROR: cannot read {path} — no such file. (An `extras.json` in an existing "
                  f"directory is seeded automatically; any other path must exist.)", file=sys.stderr)
            return 2
    if from_file:
        if replace:
            # --replace corrects ONE record by prefix; a file of lines has no single target, and
            # guessing which one it meant is the kind of silent mis-write this command exists to
            # prevent.
            print("ERROR: --replace corrects one record and --lines-from carries many — do the "
                  "replacement in its own call.", file=sys.stderr)
            return 2
        src = Path("/dev/stdin") if from_file == "-" else Path(from_file)
        try:
            text = sys.stdin.read() if from_file == "-" else src.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: cannot read --lines-from {from_file}: {exc}", file=sys.stderr)
            return 2
        # Blank lines and `#` comments dropped, so the file a lead pastes together can be annotated.
        lines += [ln.strip() for ln in text.splitlines()
                  if ln.strip() and not ln.lstrip().startswith("#")]
    if not heading or not lines:
        print("ERROR: --heading and at least one --line (or --lines-from) are required",
              file=sys.stderr)
        return 2
    if replace and len(lines) > 1:
        print(f"ERROR: --replace corrects one record; {len(lines)} --line values were given.",
              file=sys.stderr)
        return 2
    # A key with no why is a dismissal, not a record — the rule every escape family already states.
    # Checked for EVERY line before anything is written: a partial append would leave the fragment
    # holding some of a batch, and the caller cannot tell which without re-reading it.
    for bad in [ln for ln in lines if ":" not in ln or not ln.split(":", 1)[1].strip()]:
        print(f"ERROR: a record is `<id or claim>: <why>` — '{bad}' states no why. A key alone is "
              f"a dismissal, and the point of recording is that the reason survives.", file=sys.stderr)
        return 2
    canonical, complaint = _resolve_heading(heading)
    if complaint:
        print(f"ERROR: {complaint}", file=sys.stderr)
        return 2
    if seed_extras:
        path.write_text('{\n  "extras": []\n}\n', encoding="utf-8")
        print(f"note: seeded {path} — nothing else creates the extras fragment, and a record had "
              f"nowhere to go.")
    from coyodex.assemble import dump_preserving, load_map_or_fragment
    try:
        m, present = load_map_or_fragment(path)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    any_changed = False
    for ln in lines:
        changed, message = append_line(m, canonical, ln, replace)
        print(message)
        any_changed = any_changed or changed
    if not any_changed:
        return 1 if replace else 0
    # ONE write for the whole batch. Writing per line would leave the file half-updated if a later
    # line failed, and would rewrite the fragment N times for N records.
    path.write_text(dump_preserving(m, present), encoding="utf-8")
    if present is None:
        print(f"wrote {path} — note this is the ASSEMBLED map, so the next `assemble` discards it. "
              f"Record against the FRAGMENT that owns the extras section to make it durable.")
    else:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
