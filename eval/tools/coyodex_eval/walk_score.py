#!/usr/bin/env python3
"""`coyodex-eval walk-score` — score a partial run of the front-door walk against a gold answer.

A walk run takes a map whose ways in have no story and adjudicates each one: it becomes a NEW use
case, is NAMED on an existing use case, is RECORDED with a reason, or a flow step now RUNS it. The
gold, written BEFORE the agent runs, lists the outcomes acceptable for each way in. The first two
runs of the walk were scored by a throwaway script in a scratchpad; the third would have been too,
and a scorer nobody commits is a scorer that drifts from the checks it should share.

Reads two ASSEMBLED maps, before and after, and nothing else: a use case's `entry_points` and the
records are applied there, so neither the fragments nor the reconcile file need reading. Every
classification comes from the validator's own helpers (`triggered_entry_point_ids`,
`step_anchored_entry_point_ids`, the records reader) — never a second implementation.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from coyodex import records
from coyodex import validate_model as vm
from coyodex.model import ProjectModel, load_model

USAGE = """usage: coyodex-eval walk-score <before> <after> --gold <gold.json> [--json]

<before> and <after> are a map file or a `.coyodex/` directory. The gold is `{"EPn": [outcome, ...]}`:
the outcomes acceptable for each way in — `new` (named by a use case the before map did not have),
`named` (named on a use case it did have), `recorded` (an 'Unclaimed surfaces' or 'Interface
exceptions' line for the way in, its interface or its component appeared), `run` (a flow step now
sits at its line). Every gold way in is classified and compared. Exit 1 when any way in lands
outside its gold or is left untouched, so a partial run can be gated on it.

  --gold <file>  the gold table (required)
  --json         machine-readable"""

OUTCOMES = ("new", "named", "recorded", "run")
RECORD_HEADINGS = ("unclaimed surfaces", "interface exceptions")


@dataclass
class WayInVerdict:
    way_in: str
    interface: str      # the interface id, or "" when the way in belongs to none
    gold: list[str]
    outcome: str        # one of OUTCOMES, or "untouched"
    detail: str         # the use case id, or the recorded reason
    verdict: str        # "ok" | "wrong" | "untouched"


@dataclass
class NewUseCase:
    id: str
    name: str
    actors: list[str]
    capability: str
    ways_in: list[str]


@dataclass
class WalkScore:
    new_use_cases: list[NewUseCase]
    named_on_existing: dict[str, list[str]]    # existing use case id -> the ways in it gained
    recorded: dict[str, str]                   # key (EPn / In / Cn) -> why, keys the before map lacked
    verdicts: list[WayInVerdict]
    coverage_line: str                         # the after map's own coverage line

    def tally(self) -> dict[str, int]:
        t = {"ok": 0, "wrong": 0, "untouched": 0}
        for v in self.verdicts:
            t[v.verdict] += 1
        return t


def load_map(arg: str) -> ProjectModel:
    p = Path(arg)
    if p.is_dir():
        p = p / "project-map.json"
    return load_model(p.read_text(encoding="utf-8"))


def record_reasons(m: ProjectModel) -> dict[str, str]:
    """Every adjudication key under the headings a way in can be recorded under, with its why.
    Keys come from the shared line reader; the why is what follows the keys' colon."""
    out: dict[str, str] = {}
    for heading in RECORD_HEADINGS:
        for line in records.lines(m, heading):
            keys = records.keys_on_line(line)
            if not keys:
                continue
            why = line.split(":", 1)[1].strip() if ":" in line else ""
            for k in keys:
                out[k] = why
    return out


def _named_by(m: ProjectModel) -> dict[str, str]:
    """way in -> the use case naming it (the trigger arm, per way in)."""
    return {ep: u.id for u in m.use_cases for ep in u.entry_points if ep.strip()}


def score(before: ProjectModel, after: ProjectModel, gold: dict[str, list[str]]) -> WalkScore:
    before_ucs = {u.id for u in before.use_cases}
    before_named, after_named = _named_by(before), _named_by(after)
    before_run, after_run = vm.step_anchored_entry_point_ids(before), vm.step_anchored_entry_point_ids(after)
    before_rec, after_rec = record_reasons(before), record_reasons(after)
    iface_of = {ep: i.id for i in after.interfaces for ep in i.ways_in}
    comp_of = {ep.id: ep.component.strip() for ep in after.entry_points if ep.id}

    new_ucs = [NewUseCase(id=u.id, name=u.name, actors=list(u.actors),
                          capability=(u.capability or "").strip(),
                          ways_in=[e for e in u.entry_points if e.strip()])
               for u in after.use_cases if u.id not in before_ucs]
    gained: dict[str, list[str]] = {}
    for u in after.use_cases:
        if u.id in before_ucs:
            had = {e for b in before.use_cases if b.id == u.id for e in b.entry_points}
            more = [e for e in u.entry_points if e.strip() and e not in had]
            if more:
                gained[u.id] = more
    recorded = {k: why for k, why in after_rec.items() if k not in before_rec}

    def classify(ep: str) -> tuple[str, str]:
        uc = after_named.get(ep)
        if uc and before_named.get(ep) != uc:
            return ("new" if uc not in before_ucs else "named", uc)
        if ep in after_run and ep not in before_run:
            return ("run", "")
        for key in (ep, iface_of.get(ep, ""), comp_of.get(ep, "")):
            if key and key in recorded:
                return ("recorded", recorded[key])
        return ("untouched", "")

    verdicts: list[WayInVerdict] = []
    for ep, accepted in gold.items():
        outcome, detail = classify(ep)
        verdict = ("untouched" if outcome == "untouched"
                   else "ok" if outcome in accepted else "wrong")
        verdicts.append(WayInVerdict(way_in=ep, interface=iface_of.get(ep, ""), gold=list(accepted),
                                     outcome=outcome, detail=detail, verdict=verdict))
    return WalkScore(new_use_cases=new_ucs, named_on_existing=gained, recorded=recorded,
                     verdicts=verdicts, coverage_line=vm._entry_point_coverage_line(after))


def render(s: WalkScore) -> str:
    out: list[str] = [f"New use cases: {len(s.new_use_cases)}"]
    for u in s.new_use_cases:
        out.append(f"  {u.id:6} {u.name!r}  actors={','.join(u.actors) or '-'}  "
                   f"capability={u.capability or '-'}  ways in={','.join(u.ways_in) or '-'}")
    if s.named_on_existing:
        out.append("Ways in named on existing use cases:")
        for uid, eps in s.named_on_existing.items():
            out.append(f"  {uid:6} +{','.join(eps)}")
    if s.recorded:
        out.append("Recorded:")
        for k, why in s.recorded.items():
            out.append(f"  {k:6} {why[:100]}")
    if s.verdicts:
        out.append("Per way in (gold vs actual):")
        for v in s.verdicts:
            got = f"{v.outcome}:{v.detail[:40]}" if v.detail else v.outcome
            out.append(f"  {v.way_in:6} {v.interface or '-':4} gold={'|'.join(v.gold):22} "
                       f"got={got:48} {v.verdict.upper() if v.verdict != 'ok' else 'ok'}")
        t = s.tally()
        out.append(f"Tally: {t['ok']} ok, {t['wrong']} wrong, {t['untouched']} untouched of {len(s.verdicts)}")
    else:
        out.append("No gold rows: nothing to compare (the gold table is empty).")
    if s.coverage_line:
        out.append(s.coverage_line)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 2
    maps: list[str] = []
    gold_path: Path | None = None
    as_json = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True
        elif a == "--gold":
            i += 1
            if i >= len(argv):
                print("ERROR: --gold needs a file", file=sys.stderr)
                return 2
            gold_path = Path(argv[i])
        elif a.startswith("-"):
            print(f"ERROR: unknown argument '{a}'", file=sys.stderr)
            return 2
        else:
            maps.append(a)
        i += 1
    if len(maps) != 2 or gold_path is None:
        print("ERROR: walk-score needs <before> <after> and --gold <file>", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    raw = json.loads(gold_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        print("ERROR: the gold is an object {\"EPn\": [outcomes]}", file=sys.stderr)
        return 2
    gold: dict[str, list[str]] = {}
    for k, v in raw.items():
        outcomes = [str(x) for x in (v if isinstance(v, list) else [v])]
        bad = [x for x in outcomes if x not in OUTCOMES]
        if bad:
            print(f"ERROR: {k}: unknown outcome(s) {bad}; use {OUTCOMES}", file=sys.stderr)
            return 2
        gold[str(k)] = outcomes
    s = score(load_map(maps[0]), load_map(maps[1]), gold)
    if as_json:
        print(json.dumps({**asdict(s), "tally": s.tally()}, indent=2))
    else:
        print(render(s))
    t = s.tally()
    return 1 if (t["wrong"] or t["untouched"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
