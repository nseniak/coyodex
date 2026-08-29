#!/usr/bin/env python3
"""`coyodex context` — one claims batch, with the code and the map records already beside it.

**Why this exists.** A Phase-4 skeptic is handed 40 claims and a repository, and it spends its run
finding things: opening the anchor, hunting the real call site, dumping an element's record. Every
file it opens joins its context, and every later turn re-reads all of it. Measured across eight
skeptic agents on one build: **52-62% of each one's bill was re-reading its own accumulated
context**, against 12-18% for everything it wrote. The lever is not a cheaper model. It is handing
the skeptic what it was going to go and fetch.

So this verb fetches it once, deterministically, for the whole batch: per claim, the map record of
every element the claim names, and the lines around the claim's own anchor. One file, one read.

**What it must never do is hide a fault.** Two of them, both of which a bundle could paper over:

  * **A file that is not in the repo is SAID so, loudly.** The skeptic contract calls an anchor
    whose file is absent `false`, not drift — and a bundle that silently omitted the missing file
    would destroy exactly that verdict. A planted batch of 24 such anchors was confirmed by eight
    skeptics out of eight before the contract said it plainly; a quiet bundle would put that back.
  * **The bundle is a STARTING POINT, never the evidence.** It says so in its own header. A skeptic
    still opens what it needs; the point is that it does not have to open everything to begin.

Deterministic, stdlib-only, read-only. No model, no network, and it never writes into the map.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from coyodex.anchors import parse_anchor
from coyodex.dump import record_of
from coyodex.model import ID_SHAPE, load_model

#: How many lines either side of an anchor to quote. Twenty is the width the retro proposed, and it
#: is a whole small function or the head of a large one.
DEFAULT_LINES = 20

#: An id as it appears inside a claim's prose (`C120 calls C241`, `Rule 'x' is enforced at ...`).
_ID = re.compile(r"\b([A-Z]{1,4}\d+)\b")


def ids_in(text: str) -> list[str]:
    """Every id-shaped token in a claim, in first-appearance order, de-duplicated."""
    seen: dict[str, None] = {}
    for token in _ID.findall(text or ""):
        if ID_SHAPE.match(token):
            seen.setdefault(token, None)
    return list(seen)


def code_slice(repo: Path, anchor: str, lines: int) -> tuple[str, list[str]]:
    """`(status, numbered lines)` around an anchor.

    `status` is one of `ok`, `no-file`, `no-line`, `unreadable`, `not-an-anchor`. It is returned
    rather than folded into the text because `no-file` is a VERDICT the skeptic owes, not a gap in
    this file's output."""
    loc = parse_anchor(anchor or "")
    if loc is None:
        return "not-an-anchor", []
    path = repo / loc.path
    if not path.is_file():
        return "no-file", []
    try:
        body = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "unreadable", []
    if loc.lo is None:
        return "no-line", []
    lo = max(1, loc.lo - lines)
    hi = min(len(body), (loc.hi or loc.lo) + lines)
    if loc.lo > len(body):
        return "no-line", []
    width = len(str(hi))
    marked = range(loc.lo, (loc.hi or loc.lo) + 1)
    return "ok", [f"{'>' if n in marked else ' '} {n:>{width}}  {body[n - 1]}"
                  for n in range(lo, hi + 1)]


def bundle(claims: list[dict[str, Any]], model: Any, repo: Path,
           lines: int = DEFAULT_LINES) -> str:
    """The whole batch as one readable document."""
    out: list[str] = [
        "# Evidence bundle",
        "",
        "One entry per claim in your batch: the map record of every element the claim names, and",
        "the code around the claim's own anchor. It is gathered for you so you do not have to go",
        "and find it.",
        "",
        "**This is a STARTING POINT, not the evidence.** It is a mechanical slice: it cannot know",
        "what a claim really turns on. Open whatever else you need, and say in your `note` what you",
        "read. A claim settled only by what is quoted here, when the quoted lines do not settle it,",
        "is a fabricated confirmation.",
        "",
        f"Anchors are quoted with {lines} lines either side. The claim's own line(s) are marked `>`.",
        "",
        "**An anchor whose FILE IS NOT IN THE REPO is marked below.** That is a `false` verdict, not",
        "a missing slice: the map is citing evidence that was never there, and no drift check",
        "reconciles a filename. Do not go looking for a similarly-named file and confirm against it.",
        "",
    ]
    missing = 0
    for i, claim in enumerate(claims):
        text = str(claim.get("claim", ""))
        anchor = str(claim.get("anchor", ""))
        out += ["---", "", f"## Claim {i}", "", f"`{text}`", "", f"**Anchor**: `{anchor}`", ""]
        detail = claim.get("detail")
        if isinstance(detail, str) and detail.strip():
            out += ["**Detail as the map states it**:", "", detail.strip(), ""]

        records = [(eid, record_of(model, eid)) for eid in ids_in(f"{text} {detail or ''}")]
        found = [(eid, rec) for eid, rec in records if rec is not None]
        if found:
            out.append("**Map records for the elements this claim names**:")
            out.append("")
            out.append("```json")
            out.append(json.dumps({eid: rec for eid, rec in found}, indent=2, ensure_ascii=False))
            out.append("```")
            out.append("")

        status, body = code_slice(repo, anchor, lines)
        if status == "ok":
            out += ["**The code at that anchor**:", "", "```", *body, "```", ""]
        elif status == "no-file":
            missing += 1
            out += [f"**THE FILE `{parse_anchor(anchor).path if parse_anchor(anchor) else anchor}`"  # type: ignore[union-attr]
                    f" IS NOT IN THE REPO.**", "",
                    "The map cites evidence that is not there. Per your contract that is `false`,",
                    "not drift. Put the missing path in your `note`.", ""]
        elif status == "no-line":
            out += ["**The file exists; the anchor's line is past its end.** Read the file and say",
                    "what you find.", ""]
        elif status == "unreadable":
            out += ["**The file could not be read as text.** Say so rather than guessing.", ""]
        else:
            out += ["**The anchor is not a `path:line`,** so nothing could be quoted.", ""]
    if missing:
        out += ["---", "", f"**{missing} anchor(s) in this batch name a file that is not in the "
                           f"repo.** Each is a `false`.", ""]
    return "\n".join(out) + "\n"


USAGE = """\
usage: coyodex context --map <project-map.json> --repo <root> --claims <claims.json>
                       [--out <file>] [--lines N]

One claims batch with its evidence already beside it: per claim, the map record of every element
it names, and the code around its anchor.

A skeptic spends its run fetching exactly this, and every file it opens joins a context that every
later turn re-reads. Measured across eight skeptic agents: 52-62% of each one's bill was re-reading
its own accumulated context, against 12-18% for everything it wrote.

  --lines N   lines either side of the anchor (default 20)
  --out FILE  write there instead of stdout

An anchor whose FILE is absent is marked as such, never quietly skipped: the skeptic contract calls
that `false`, and a bundle that hid it would destroy the verdict it exists to support.

Read-only and deterministic. No model, no network, and it never writes into the map.
"""


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or "-h" in args or "--help" in args:
        print(USAGE)
        return 0 if args else 2
    parser = argparse.ArgumentParser(prog="coyodex context", add_help=False)
    parser.add_argument("--map", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--claims", required=True)
    parser.add_argument("--out")
    parser.add_argument("--lines", type=int, default=DEFAULT_LINES)
    try:
        ns = parser.parse_args(args)
    except SystemExit:
        print(USAGE, file=sys.stderr)
        return 2
    if ns.lines < 0:
        print("ERROR: --lines takes a non-negative number of lines", file=sys.stderr)
        return 2
    try:
        raw = json.loads(Path(ns.claims).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: --claims {ns.claims}: {exc}", file=sys.stderr)
        return 2
    claims = raw.get("claims") if isinstance(raw, dict) else raw
    if not isinstance(claims, list):
        print(f"ERROR: {ns.claims} holds no `claims` list", file=sys.stderr)
        return 2
    try:
        model = load_model(Path(ns.map).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR: --map {ns.map}: {exc}", file=sys.stderr)
        return 2
    text = bundle([c for c in claims if isinstance(c, dict)], model, Path(ns.repo), ns.lines)
    if ns.out:
        Path(ns.out).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.out).write_text(text, encoding="utf-8")
        print(f"wrote {len(claims)} claim(s) -> {ns.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
