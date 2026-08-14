#!/usr/bin/env python3
"""What changed between two maps, ROW BY ROW.

Nothing could answer that. `coyodex-eval compare` compares aggregate COUNTS, and a count cannot see a
row moving between two arrays: a retrospective read `auth surfaces 39 -> 21`, got a REGRESSED verdict,
and needed an hour of hand-reading to establish that the surfaces had been re-expressed as business
rules rather than lost. The assemble digest is the only other before/after signal, it is one line, and
three of its eight counters were not being printed at all.

SCOPE — and this is a real limit, not caution. This compares two assembles of the SAME work: an old
map against the new one you just produced, a map before a `fix` against the map after. It is NOT a
comparison of two independent builds. Two LLM builds of one repo do not agree on numbering and do not
agree on wording, so "the same row" across them can only be decided by matching text — which is the
fragility this whole family of commands exists to remove. `coyodex-eval compare` plus the judge layer
own that question, deliberately, and `compare.py` says so where it emits name-level set differences as
an informational note and never as a gate.

MATCHING. Rows with an authored id (`model.ID_ARRAYS`) match by id. Edges match by
`(src, verb, dst, where)` — they carry no id. Entry points match by their CONTENT identity, the same
`(source, trigger, component, kind)` tuple `assemble._entry_point_identity` uses, because their ids
are minted and re-sorted: changing one anchor moved 22 of 104 EP ids on a real map, and matching those
by id would report a fifth of them as replaced when nothing about them changed.

Stdlib-only.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from coyodex.model import ID_ARRAYS, ModelError, load_model

USAGE = """usage: coyodex diff <old-map> <new-map> [--json] [--only <array>]

What changed between two maps, row by row: rows ADDED, rows DROPPED, and rows CHANGED with the
fields that moved. Read-only; writes nothing.

  --json          the same result as data — parse this, never the text
  --only <array>  restrict to one array (rules, components, edges, entry_points, …)

SCOPE: two assembles of the SAME work — an old map vs the new one, or before vs after a `fix`.
NOT two independent builds: they do not agree on numbering or wording, and matching those by text
is the fragility these commands exist to remove. Use `coyodex-eval compare` for that.
"""

#: Arrays compared by CONTENT identity rather than by id, and the fields that form that identity.
#: Entry-point ids are minted by `assemble._mint_entry_point_ids` and re-sorted on every assemble, so
#: an id match reports a fifth of them as replaced when only one anchor moved.
_CONTENT_KEYED: dict[str, tuple[str, ...]] = {
    "edges": ("src", "verb", "dst", "where"),
    "entry_points": ("source", "trigger", "component", "kind"),
}

#: Arrays with neither an id nor a stable content identity worth diffing row-wise. Reported as a
#: count delta only, so the output never implies a precision it does not have.
_COUNT_ONLY: frozenset[str] = frozenset({"extras", "glossary", "run_commands", "tests"})


@dataclass
class ArrayDiff:
    """One array's changes. Empty arrays are dropped before display, never rendered as zeros."""
    array: str
    added: list[str] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)
    changed: list[tuple[str, list[str]]] = field(default_factory=list)   # (key, fields that moved)
    count_before: int = 0
    count_after: int = 0
    #: Identities held by more than one row on either side. Named rather than silently paired: with a
    #: repeated key there is no honest 1:1 match, so those rows are reported by multiplicity only.
    key_collisions: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.added or self.dropped or self.changed
                    or self.count_before != self.count_after)

    def as_json(self) -> dict[str, Any]:
        return {"array": self.array, "added": self.added, "dropped": self.dropped,
                "changed": [{"key": k, "fields": f} for k, f in self.changed],
                "count_before": self.count_before, "count_after": self.count_after,
                "key_collisions": self.key_collisions}


def _key_of(array: str, row: dict[str, Any]) -> str | None:
    """The identity this row is matched on, or None when it has none."""
    if array in _CONTENT_KEYED:
        parts = [" ".join(str(row.get(f) or "").split()).lower() for f in _CONTENT_KEYED[array]]
        return " · ".join(parts) if any(parts) else None
    rid = row.get("id")
    return rid if isinstance(rid, str) and rid else None


def _grouped(array: str, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Rows by identity, KEEPING every row that shares one. See `diff_arrays` for why."""
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        key = _key_of(array, r)
        if key:
            out.setdefault(key, []).append(r)
    return out


def _rows(doc: dict[str, Any], array: str) -> list[dict[str, Any]]:
    value = doc.get(array)
    return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []


def diff_arrays(before: dict[str, Any], after: dict[str, Any],
                only: str | None = None) -> list[ArrayDiff]:
    """Every array's row-level changes, in a stable order. Both documents are raw parsed JSON, so a
    field the model does not know about is still compared — a diff that only saw modelled fields
    would go quiet exactly on the extras a build hand-writes."""
    arrays = sorted({k for k, v in (*before.items(), *after.items()) if isinstance(v, list)})
    out: list[ArrayDiff] = []
    for array in arrays:
        if only and array != only:
            continue
        rows_b, rows_a = _rows(before, array), _rows(after, array)
        d = ArrayDiff(array=array, count_before=len(rows_b), count_after=len(rows_a))
        if array in _COUNT_ONLY or (array not in ID_ARRAYS and array not in _CONTENT_KEYED):
            if not d.empty:
                out.append(d)
            continue
        # Grouped, not a dict comprehension. A comprehension keeps the LAST row per key, so two rows
        # sharing an identity silently vanished: `assemble` deliberately keeps two no-call-site edges
        # on one (src, verb, dst) so a differing `why` can tell two couplings apart, and the real
        # argus / mcpolis / mio maps carry 2 / 3 / 3 of them. Deleting one was then reported as ZERO
        # row-level changes under a line claiming edges carry no identity to match on — a false
        # explanation on top of a missed deletion.
        by_b, by_a = _grouped(array, rows_b), _grouped(array, rows_a)
        collisions = sorted(k for k in {*by_b, *by_a}
                            if len(by_b.get(k, ())) > 1 or len(by_a.get(k, ())) > 1)
        # Multiplicity IS the signal when a key repeats: n before, m after → the difference is
        # reported as added or dropped rather than paired up and compared field-by-field.
        for key in sorted(set(by_b) | set(by_a)):
            n_b, n_a = len(by_b.get(key, ())), len(by_a.get(key, ()))
            d.added += [key] * max(0, n_a - n_b)
            d.dropped += [key] * max(0, n_b - n_a)
        d.added.sort()
        d.dropped.sort()
        d.key_collisions = collisions
        # For a content-keyed array the `id` is DERIVED, not authored, so a change in it is not a
        # change in the row. Reporting it would reintroduce the noise content-keying removes: an
        # anchor edit re-sorts the minted entry-point range, and every EP would read as `[id]`
        # changed while the surfaces themselves were untouched.
        ignore = {"id"} if array in _CONTENT_KEYED else set()
        for key in sorted(set(by_a) & set(by_b)):
            # Field-by-field only where BOTH sides hold exactly one row for the key. With a repeated
            # key there is no honest pairing, so the multiplicity above is the whole answer.
            if len(by_a[key]) != 1 or len(by_b[key]) != 1:
                continue
            row_a, row_b = by_a[key][0], by_b[key][0]
            moved = sorted({f for f in ({*row_a, *row_b} - ignore)
                            if row_a.get(f) != row_b.get(f)})
            if moved:
                d.changed.append((key, moved))
        if not d.empty:
            out.append(d)
    return out


def format_diff(diffs: list[ArrayDiff], before_label: str, after_label: str) -> str:
    lines = [f"map diff — {before_label} → {after_label}"]
    if not diffs:
        lines.append("  no row changed.")
        return "\n".join(lines)
    for d in diffs:
        delta = d.count_after - d.count_before
        head = f"  {d.array}: {d.count_before} → {d.count_after}"
        lines.append(head + (f" ({delta:+d})" if delta else ""))
        for key in d.dropped:
            lines.append(f"    - {key}")
        for key in d.added:
            lines.append(f"    + {key}")
        for key, fields_moved in d.changed:
            lines.append(f"    ~ {key}  [{', '.join(fields_moved)}]")
        for key in d.key_collisions:
            lines.append(f"    ! {key}  (identity held by more than one row — reported by count, "
                         f"not paired)")
        if not (d.added or d.dropped or d.changed or d.key_collisions) and delta:
            # A count moved with no row-level detail: the array is one this command only counts.
            lines.append(f"    (counted only — {d.array} rows carry no stable identity to match on)")
    return "\n".join(lines)


def _read(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ModelError(f"{path}: not a map object")
    load_model(json.dumps(doc))       # refuse a malformed map rather than diff nonsense
    return doc


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if args else 2
    only = None
    as_json = False
    positional: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--only":
            i += 1
            if i >= len(args):
                print("ERROR: --only needs an array name", file=sys.stderr)
                return 2
            only = args[i]
            if only.startswith("--"):
                # `--only --json` used to set only="--json" AND emit JSON, because the output mode was
                # read off the raw argv rather than a parsed flag.
                print(f"ERROR: --only was given '{only}', which is another flag", file=sys.stderr)
                return 2
        elif a == "--json":
            as_json = True
        elif a.startswith("-"):
            print(f"ERROR: unknown option '{a}'\n", file=sys.stderr)
            print(USAGE, file=sys.stderr)
            return 2
        else:
            positional.append(a)
        i += 1
    if len(positional) != 2:
        print("ERROR: give exactly two map paths — the old one and the new one\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    old, new = Path(positional[0]), Path(positional[1])
    for p in (old, new):
        if not p.is_file():
            print(f"ERROR: {p} not found", file=sys.stderr)
            return 2
    try:
        before, after = _read(old), _read(new)
    except (ModelError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("       (A map an OLDER coyodex wrote will fail here, and that is the scope working: "
              "this command compares two assembles of the same work, not two builds. For an "
              "archived map use `coyodex-eval score` + `compare`, which tolerate the older schema "
              "read-only.)", file=sys.stderr)
        return 2
    if only is not None:
        known = sorted({k for k, v in (*before.items(), *after.items()) if isinstance(v, list)})
        if only not in known:
            # `--only edge` (the obvious typo for `edges`) used to print "no row changed" and exit 0,
            # so a reader got a clean answer to a question that was never asked.
            print(f"ERROR: --only '{only}' is not an array in either map. Known: "
                  f"{', '.join(known)}", file=sys.stderr)
            return 2
    diffs = diff_arrays(before, after, only)
    if as_json:
        print(json.dumps({"kind": "coyodex-map-diff", "version": 1,
                          "before": str(old), "after": str(new),
                          "arrays": [d.as_json() for d in diffs]}, indent=2, ensure_ascii=False))
    else:
        print(format_diff(diffs, str(old), str(new)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
