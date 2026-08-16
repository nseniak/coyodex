#!/usr/bin/env python3
"""Plant known-false claims in a batch, and score a skeptic's verdicts against the answer key.

**What this measures, and why the obvious experiment does not.** A retrospective found a Phase-4
pass that refuted 6 of 823 rows with 0 unverifiable, and could not say whether the skeptics were
weak or the map was good. The tempting test — run two prompt wordings on the same batch and compare
refutation rates — cannot answer it: if the second refutes more, that may be the prompt or may be
one agent differing from another, and neither run has a ground truth to be right or wrong about.

So: corrupt claims in ways that are known-false by construction, keep the key, and measure RECALL.
"caught 3 of 10 planted falsehoods" is an absolute number that means something on its own, and
running two contracts over the SAME mutated batch makes the comparison clean because the truth is
fixed. A high score on both is a real answer too — it says the wording is not the problem.

**The shapes are the point.** Random corruption measures nothing a map does: it tests whether a
skeptic can read. These four are what map claims actually get wrong, and they are graded by
difficulty on purpose — a skeptic that only catches `ghost_file` has learnt to check paths, not to
disprove a claim:

* `drifted_anchor` — the statement is true, the line does not enforce it. The commonest real defect.
  **Scored on the EVIDENCE, not the verdict**: the contract tells a skeptic to confirm such a claim
  and return the line it actually found, because refuting a true relationship over a stale anchor is
  the wrong answer and the drift check reconciles it. Scoring it as a refutation marked four
  skeptics 0/3 for following their instructions.
* `negated_clause`  — a two-clause rule with the SECOND clause reversed. Half the sentence still
  matches the code, so a skeptic skimming for the gist confirms it. The most valuable catch.
* `swapped_actor`  — "the owner may" becomes "any member may". A one-word change that inverts an
  access rule, which is why it is planted in an access batch.
* `ghost_file`     — the anchor names a file that does not exist. The easy one, and a floor: a
  skeptic that misses these is not opening anything.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SHAPES = ("drifted_anchor", "negated_clause", "swapped_actor", "ghost_file")

#: Actor swaps that INVERT an access rule while staying grammatical. Applied to the statement, so
#: the claim stays readable and only its meaning moves.
_ACTOR_SWAPS = (
    (r"\bonly the person who\b", "any person who"),
    (r"\bonly the owner\b", "any member"),
    (r"\bnever\b", "always"),
    (r"\bis refused\b", "is allowed"),
    (r"\bmay only\b", "may freely"),
    (r"\bcannot\b", "can"),
    (r"\bis not part of\b", "is part of"),
    (r"\bwill not\b", "will"),
)


@dataclass
class Planted:
    index: int
    shape: str
    original_claim: str
    original_anchor: str
    mutated_claim: str
    mutated_anchor: str


@dataclass
class MutationRun:
    """The mutated batch and its answer key — one object so they cannot drift apart."""
    batch: dict
    planted: list[Planted] = field(default_factory=list)


def _statement(claim: str) -> str | None:
    m = re.search(r"Rule '(.*?)' is enforced at", claim, re.S)
    return m.group(1) if m else None


def _replace_statement(claim: str, new_stmt: str) -> str:
    return re.sub(r"(Rule ')(.*?)(' is enforced at)", lambda m: m.group(1) + new_stmt + m.group(3),
                  claim, count=1, flags=re.S)


def _mutate_one(claim: dict, shape: str, rng: random.Random,
                repo: Path | None = None) -> tuple[dict, str] | None:
    """A mutated copy of `claim`, or None when this shape does not apply to it."""
    out = json.loads(json.dumps(claim))
    text, anchor = out["claim"], out.get("anchor", "")
    stmt = _statement(text)

    if shape == "ghost_file":
        path, _, line = anchor.rpartition(":")
        if not path:
            return None
        ghost = re.sub(r"([^/]+)(\.[a-zA-Z]+)$", r"\1_nonexistent\2", path)
        out["anchor"] = f"{ghost}:{line}"
        out["claim"] = text.replace(anchor, out["anchor"])
        return out, f"anchor now names {ghost}, which does not exist"

    if shape == "drifted_anchor":
        path, _, line = anchor.rpartition(":")
        if not line.isdigit():
            return None
        # A REAL line, and a different one. Offsetting by a constant put every drift past
        # end-of-file, which is a ghost LINE — the same easy shape as `ghost_file` wearing the hard
        # shape's name. It would have made this the wrong experiment: the case that matters is a
        # line that EXISTS and simply is not the one enforcing the rule.
        src = repo / path if repo else None
        if src is None or not src.is_file():
            return None
        lines = src.read_text(encoding="utf-8", errors="replace").splitlines()
        orig = int(line)
        cands = [i for i in range(1, len(lines) + 1)
                 if abs(i - orig) > 15 and lines[i - 1].strip()
                 and not lines[i - 1].lstrip().startswith(("//", "*", "/*", "#"))]
        if not cands:
            return None
        moved = f"{path}:{rng.choice(cands)}"
        out["anchor"] = moved
        out["claim"] = text.replace(anchor, moved)
        return out, f"statement true; anchor moved {anchor} -> {moved}, a real line that does not enforce it"

    if shape == "swapped_actor":
        if not stmt:
            return None
        for pat, repl in _ACTOR_SWAPS:
            if re.search(pat, stmt, re.I):
                new = re.sub(pat, repl, stmt, count=1, flags=re.I)
                out["claim"] = _replace_statement(text, new)
                return out, f"access sense inverted: '{pat}' -> '{repl}'"
        return None

    if shape == "negated_clause":
        if not stmt:
            return None
        # A second clause exists after a semicolon, a comma+conjunction, or an em dash.
        m = re.search(r"^(.*?)([;—]|, (?:and|but|so|while) )(.+)$", stmt, re.S)
        if not m:
            return None
        head, sep, tail = m.groups()
        for pat, repl in _ACTOR_SWAPS:
            if re.search(pat, tail, re.I):
                new_tail = re.sub(pat, repl, tail, count=1, flags=re.I)
                out["claim"] = _replace_statement(text, head + sep + new_tail)
                return out, ("first clause still true, SECOND clause reversed: "
                             f"'{pat}' -> '{repl}' after '{sep.strip()}'")
        return None
    raise ValueError(f"unknown shape {shape}")


def plant(batch: dict, n: int, seed: int = 0, repo: Path | None = None) -> MutationRun:
    """`n` mutations spread across the shapes, on distinct claims."""
    rng = random.Random(seed)
    claims = batch["claims"]
    order = list(range(len(claims)))
    rng.shuffle(order)
    run = MutationRun(batch=json.loads(json.dumps(batch)))
    used: set[int] = set()
    # Round-robin the shapes so no single shape dominates the sample.
    for k in range(n):
        shape = SHAPES[k % len(SHAPES)]
        for i in order:
            if i in used:
                continue
            got = _mutate_one(claims[i], shape, rng, repo)
            if got is None:
                continue
            mutated, _why = got
            run.batch["claims"][i] = mutated
            run.planted.append(Planted(index=i, shape=shape,
                                       original_claim=claims[i]["claim"],
                                       original_anchor=claims[i].get("anchor", ""),
                                       mutated_claim=mutated["claim"],
                                       mutated_anchor=mutated.get("anchor", "")))
            used.add(i)
            break
    return run


def score(planted: list[dict], verdict_rows: list[dict]) -> dict:
    """Detection per shape — and `drifted_anchor` is scored on the EVIDENCE, not the verdict.

    A planted claim is normally CAUGHT when its verdict is not `true`. `unverifiable` counts as
    caught: the claim is false and the skeptic declined to confirm it, which is the honest outcome
    the three-way vocabulary exists for. Confirming a falsehood is the only miss.

    **Drift is the exception, and getting this wrong invalidated the first run of this experiment.**
    The skeptic contract says, in as many words: "If the claim is true but the map's stored anchor
    points somewhere else, still say `true` and give the line YOU found — a drifted anchor does not
    refute a true relationship, and the drift check exists to reconcile exactly that difference."
    So a refutation is the WRONG answer for this shape. Scoring it as a verdict marked four
    skeptics 0/3 for obeying their instructions, and would have been published as evidence that
    they were weak. They were not: all four returned the exact original line in `evidence`.

    A drift is therefore caught when the evidence points somewhere OTHER than the planted anchor —
    the skeptic went and found the real line instead of copying the one it was handed."""
    by_claim = {}
    for r in verdict_rows:
        c = r.get("claim")
        if isinstance(c, str):
            by_claim.setdefault(c, []).append(r)
    per_shape: dict[str, dict[str, int]] = {}
    misses: list[dict] = []
    unvoted = 0
    for p in planted:
        shape = p["shape"]
        bucket = per_shape.setdefault(shape, {"planted": 0, "caught": 0})
        bucket["planted"] += 1
        rows = by_claim.get(p["mutated_claim"], [])
        if not rows:
            unvoted += 1
            continue
        if shape == "drifted_anchor":
            planted_anchor = (p.get("mutated_anchor") or "").strip()
            found = any((r.get("evidence") or "").strip() not in ("", planted_anchor)
                        for r in rows)
            exact = any((r.get("evidence") or "").strip() == (p.get("original_anchor") or "").strip()
                        for r in rows)
            if found:
                bucket["caught"] += 1
                if exact:
                    bucket["exact"] = bucket.get("exact", 0) + 1
            else:
                misses.append({"shape": shape, "claim": p["mutated_claim"][:160],
                               "why": "evidence repeated the planted anchor — it did not look"})
            continue
        confirmed = any(r.get("grounded") is True for r in rows)
        if confirmed:
            misses.append({"shape": shape, "claim": p["mutated_claim"][:160],
                           "why": "confirmed a claim that is false by construction"})
        else:
            bucket["caught"] += 1
    total_p = sum(v["planted"] for v in per_shape.values())
    total_c = sum(v["caught"] for v in per_shape.values())
    return {"planted": total_p, "caught": total_c, "unvoted": unvoted,
            "rate": (total_c / total_p) if total_p else None,
            "per_shape": per_shape, "misses": misses}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="coyodex-eval mutate", description=__doc__)
    sub = ap.add_subparsers(dest="verb", required=True)
    p = sub.add_parser("plant", help="write a mutated batch + answer key")
    p.add_argument("claims"); p.add_argument("--n", type=int, default=10)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--repo", help="repo root; REQUIRED for drifted_anchor")
    p.add_argument("--out", required=True); p.add_argument("--key", required=True)
    s = sub.add_parser("score", help="score verdicts against the answer key")
    s.add_argument("key"); s.add_argument("verdicts", nargs="+")
    s.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    if a.verb == "plant":
        batch = json.loads(Path(a.claims).read_text(encoding="utf-8"))
        run = plant(batch, a.n, a.seed, Path(a.repo) if a.repo else None)
        Path(a.out).write_text(json.dumps(run.batch, indent=1, ensure_ascii=False) + "\n")
        Path(a.key).write_text(json.dumps([vars(x) for x in run.planted], indent=1,
                                          ensure_ascii=False) + "\n")
        print(f"planted {len(run.planted)} mutation(s) in {len(batch['claims'])} claim(s)")
        for x in run.planted:
            print(f"  [{x.shape}] claim {x.index}")
        if len(run.planted) < a.n:
            print(f"note: asked for {a.n}, planted {len(run.planted)} — some shapes did not apply "
                  f"to any remaining claim", file=sys.stderr)
        return 0

    key = json.loads(Path(a.key).read_text(encoding="utf-8"))
    rows: list[dict] = []
    for v in a.verdicts:
        payload = json.loads(Path(v).read_text(encoding="utf-8"))
        rows += payload.get("grounding", payload if isinstance(payload, list) else [])
    result = score(key, rows)
    if a.json:
        print(json.dumps(result, indent=2))
        return 0
    r = result["rate"]
    print(f"DETECTION {result['caught']}/{result['planted']}"
          + (f"  ({r:.0%})" if r is not None else ""))
    for shape in SHAPES:
        b = result["per_shape"].get(shape)
        if b:
            tail = (f"   ({b['exact']} pointed at the exact true line)"
                    if b.get("exact") else "")
            print(f"  {shape:16} {b['caught']}/{b['planted']}{tail}")
    if result["unvoted"]:
        print(f"  {result['unvoted']} planted claim(s) got no verdict at all")
    for m in result["misses"]:
        print(f"  MISSED [{m['shape']}] {m['claim'][:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
