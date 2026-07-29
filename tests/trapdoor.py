#!/usr/bin/env python3
"""Shared support for the trapdoor regression layers — the ONE reader of `traps.yaml`.

`eval/fixtures/trapdoor/traps.yaml` is the single source of truth for what the fixture plants.
Every layer reads it through here, so a trap can never be asserted twice under two spellings,
and a trap nobody asserts shows up as a declared gap rather than as silence.

**Why a hand-rolled parser.** coyodex core is deliberately zero-dependency (`pyproject`
`dependencies = []`) and `cli.py` documents a stdlib import firewall; PyYAML is not installed
and adding it for a fixture would be the wrong trade. So `traps.yaml` is written in a small,
explicitly-documented YAML subset and parsed below with the stdlib alone. The subset is:
comments, `key: value` scalars (bare / quoted / true / false / int), nested mappings by
indentation, and lists of mappings (`- key: value` plus indented continuation lines). One line
per value; no block scalars, no anchors, no flow collections. Anything else raises rather than
being silently mis-read — a fixture manifest that parses wrong is worse than one that fails.

Dataclasses, not pydantic: pydantic is not installed either, and `coyodex.model` is built from
frozen dataclasses throughout. Matching the surrounding code wins.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

# --- locations ------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "eval" / "fixtures" / "trapdoor"
TRAPS_YAML = FIXTURE / "traps.yaml"
GOLDEN_MAP = FIXTURE / "golden" / "project-map.json"

LAYERS = ("L1", "L2", "L3", "none")
GROUPS = ("anchors", "overclaims", "messaging", "deployment", "altitude", "domain",
          "environment")


class TrapsError(Exception):
    """`traps.yaml` did not parse, or declared something the schema does not allow."""


# --- the YAML subset ------------------------------------------------------------------

Scalar = str | int | bool
Node = dict[str, "Scalar | Node | list[Node]"]


def _scalar(text: str) -> Scalar:
    """One value. Quoted stays a string verbatim; `true`/`false`/an integer convert."""
    t = text.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "'\"":
        return t[1:-1]
    if t in ("true", "false"):
        return t == "true"
    if t.lstrip("-").isdigit():
        return int(t)
    return t


def _strip_comment(line: str) -> str:
    """Drop a trailing `#` comment, but never one inside a quoted value."""
    quote = ""
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


@dataclass(frozen=True)
class _Line:
    indent: int
    text: str
    lineno: int


def _lines(text: str) -> list[_Line]:
    out: list[_Line] = []
    for n, raw in enumerate(text.splitlines(), 1):
        body = _strip_comment(raw)
        if not body.strip():
            continue
        out.append(_Line(indent=len(body) - len(body.lstrip(" ")), text=body.strip(), lineno=n))
    return out


def _parse_block(lines: list[_Line], i: int, indent: int) -> tuple[Node, int]:
    """A mapping at `indent`. Returns the mapping and the index of the first line past it."""
    node: Node = {}
    while i < len(lines) and lines[i].indent >= indent:
        ln = lines[i]
        if ln.indent > indent:
            raise TrapsError(f"traps.yaml:{ln.lineno}: unexpected indent")
        if ln.text.startswith("- "):
            raise TrapsError(f"traps.yaml:{ln.lineno}: list item where a mapping key was expected")
        if ":" not in ln.text:
            raise TrapsError(f"traps.yaml:{ln.lineno}: not a `key: value` line")
        key, _, rest = ln.text.partition(":")
        key, rest = key.strip(), rest.strip()
        if rest:
            node[key] = _scalar(rest)
            i += 1
            continue
        # An empty value opens either a nested mapping or a list of mappings.
        i += 1
        if i >= len(lines) or lines[i].indent <= indent:
            node[key] = ""
            continue
        if lines[i].text.startswith("- "):
            items, i = _parse_list(lines, i, lines[i].indent)
            node[key] = items
        else:
            child, i = _parse_block(lines, i, lines[i].indent)
            node[key] = child
    return node, i


def _parse_list(lines: list[_Line], i: int, indent: int) -> tuple[list[Node], int]:
    """A list of mappings, each item opening with `- key: value` at `indent`."""
    items: list[Node] = []
    while i < len(lines) and lines[i].indent == indent and lines[i].text.startswith("- "):
        first = lines[i]
        head = first.text[2:].strip()
        if ":" not in head:
            raise TrapsError(f"traps.yaml:{first.lineno}: list item must open with `key: value`")
        key, _, rest = head.partition(":")
        item: Node = {key.strip(): _scalar(rest.strip())}
        i += 1
        child_indent = indent + 2
        while i < len(lines) and lines[i].indent >= child_indent and not lines[i].text.startswith("- "):
            ln = lines[i]
            if ":" not in ln.text:
                raise TrapsError(f"traps.yaml:{ln.lineno}: not a `key: value` line")
            k, _, v = ln.text.partition(":")
            item[k.strip()] = _scalar(v.strip())
            i += 1
        items.append(item)
    return items, i


def parse_traps_yaml(text: str) -> Node:
    """Parse the whole document. Pure, so the subset's semantics are testable with no file."""
    lines = _lines(text)
    if not lines:
        return {}
    node, i = _parse_block(lines, 0, lines[0].indent)
    if i != len(lines):
        raise TrapsError(f"traps.yaml:{lines[i].lineno}: trailing content the subset cannot parse")
    return node


# --- the typed view -------------------------------------------------------------------

@dataclass(frozen=True)
class Trap:
    """One entry from `traps.yaml`, validated."""

    id: str
    group: str
    plants: str
    layer: str
    expect: str
    covered: bool
    where: tuple[str, ...] = ()
    note: str = ""

    @property
    def paths(self) -> tuple[Path, ...]:
        """The fixture paths this trap names, as absolute paths."""
        return tuple(FIXTURE / p for p in self.where)


def _as_str(item: Node, key: str, tid: str, *, required: bool = True) -> str:
    v = item.get(key, "")
    if required and not v:
        raise TrapsError(f"trap {tid or '?'}: missing required field `{key}`")
    if not isinstance(v, str):
        raise TrapsError(f"trap {tid}: `{key}` must be a string, got {type(v).__name__}")
    return v


def load_traps(path: Path = TRAPS_YAML) -> tuple[Trap, ...]:
    """Every declared trap, in file order, with the schema enforced."""
    doc = parse_traps_yaml(path.read_text(encoding="utf-8"))
    raw = doc.get("traps")
    if not isinstance(raw, list):
        raise TrapsError("traps.yaml: no `traps:` list at the top level")
    traps: list[Trap] = []
    seen: set[str] = set()
    for item in raw:
        tid = _as_str(item, "id", "")
        if tid in seen:
            raise TrapsError(f"traps.yaml: duplicate trap id {tid}")
        seen.add(tid)
        group = _as_str(item, "group", tid)
        if group not in GROUPS:
            raise TrapsError(f"trap {tid}: unknown group '{group}' (expected one of {GROUPS})")
        layer = _as_str(item, "layer", tid)
        if layer not in LAYERS:
            raise TrapsError(f"trap {tid}: unknown layer '{layer}' (expected one of {LAYERS})")
        covered = item.get("covered")
        if not isinstance(covered, bool):
            raise TrapsError(f"trap {tid}: `covered` must be true or false")
        where = tuple(s.strip() for s in _as_str(item, "where", tid, required=False).split(",")
                      if s.strip())
        traps.append(Trap(id=tid, group=group, plants=_as_str(item, "plants", tid), layer=layer,
                          expect=_as_str(item, "expect", tid), covered=covered, where=where,
                          note=_as_str(item, "note", tid, required=False)))
    return tuple(traps)


def trap(tid: str) -> Trap:
    """One trap by id. Every L2 test opens with this, so a test can never assert a trap the
    manifest does not declare (and a renamed trap fails loudly instead of silently passing)."""
    for t in load_traps():
        if t.id == tid:
            return t
    raise TrapsError(f"no trap '{tid}' in traps.yaml")


# --- fixture helpers ------------------------------------------------------------------

def fixture_text(rel: str) -> str:
    """The text of one fixture file, by fixture-relative path."""
    return (FIXTURE / rel).read_text(encoding="utf-8")


def fixture_tracked_paths() -> tuple[str, ...]:
    """What `git ls-files` reports from INSIDE the fixture — fixture-relative, which is what
    makes `preindex --root <fixture>` see the fixture as a repo root. Verified, not assumed."""
    out = subprocess.run(["git", "-C", str(FIXTURE), "ls-files"],
                         capture_output=True, text=True, check=False)
    return tuple(line for line in out.stdout.splitlines() if line.strip())


def line_of(rel: str, needle: str) -> int:
    """The 1-based line number of the first line in a fixture file containing `needle`.

    Anchors in the golden map are real line numbers; a test that hard-codes one goes stale the
    moment the fixture is edited. Looking the line up by its content keeps the assertion about
    the CLAIM rather than about a number."""
    for n, line in enumerate(fixture_text(rel).splitlines(), 1):
        if needle in line:
            return n
    raise TrapsError(f"{rel}: no line containing {needle!r}")
