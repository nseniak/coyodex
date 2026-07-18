"""`coyodex anchor-drift` — the deterministic Layer-2 check that an edge's stored `where` anchor points
at the line the operation actually happens on.

It rides the Phase-4 grounding skeptics (who already read the call-site): for every CONFIRMED claim
(majority `grounded=True`) it compares the stored anchor to the line the skeptics reported, and prints a
drift worklist for the lead to reconcile by fixing `where`. The LLM only OBSERVES (reports a line); this
check JUDGES drift deterministically — honoring "verbs / the LLM may prioritize, never gate". No
auto-fix, non-gating (informational, like the L2 worklist). Stdlib-only (the cli.py firewall).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from coyodex.anchors import DriftResult, anchor_drift, parse_anchor
from coyodex.audit_model import WorkItem, l2_worklist_model
from coyodex.model import load_model

_DEFAULT_TOLERANCE = 2


def consensus_evidence(stored: str | None, reported: list[str]) -> str | None:
    """The single reported `path:line` at the consensus (median) line — the value a drifted `where`
    should take. Mirrors `anchor_drift`'s median selection (same-file group when the stored anchor
    parses, else all reported locs) so `--json`, the human report, and `fix apply-drift` never
    disagree on WHICH line the skeptics settled on."""
    locs = [(r.strip(), parse_anchor(r)) for r in reported]
    parsed = [(txt, loc) for txt, loc in locs if loc is not None and loc.lo is not None]
    if not parsed:
        return None
    s = parse_anchor(stored) if stored else None
    if s is not None and s.lo is not None:
        base = s.path.rsplit("/", 1)[-1]
        same = [(txt, loc) for txt, loc in parsed if loc.path.rsplit("/", 1)[-1] == base]
        group = same if same else parsed
    else:
        group = parsed
    group_sorted = sorted(group, key=lambda t: t[1].lo)  # type: ignore[arg-type,return-value]
    return group_sorted[len(group_sorted) // 2][0]


def _confirmed_drifts(worklist: list[WorkItem], grounding: list[dict],
                      tolerance: int) -> list[tuple[WorkItem, DriftResult, list[str]]]:
    """(work-item, drift, grounded-evidence) for every CONFIRMED claim whose stored anchor drifts from
    the skeptics' reported line. Confirmed = a strict majority of that claim's votes have
    `grounded=True`. The grounded-evidence list is carried out so a consumer can recover the corrected
    `path:line` without re-tallying votes."""
    votes: dict[str, list[dict]] = defaultdict(list)
    for v in grounding:
        claim = v.get("claim")
        if isinstance(claim, str):
            votes[claim].append(v)
    out: list[tuple[WorkItem, DriftResult, list[str]]] = []
    for w in worklist:
        vs = votes.get(w.claim, [])
        grounded = [v for v in vs if v.get("grounded") is True]
        if not vs or len(grounded) * 2 <= len(vs):   # no votes, or not a strict majority confirmed
            continue
        reported = [str(v.get("evidence", "")) for v in grounded if v.get("evidence")]
        d = anchor_drift(w.anchor, reported, tolerance)
        if d is not None and d.drifted:
            out.append((w, d, reported))
    return out


def drift_findings(worklist: list[WorkItem], grounding: list[dict],
                   tolerance: int) -> list[tuple[WorkItem, DriftResult]]:
    """(work-item, drift) for every CONFIRMED claim whose stored anchor drifts (the human report's
    view — evidence dropped)."""
    return [(w, d) for w, d, _ev in _confirmed_drifts(worklist, grounding, tolerance)]


def drift_records(worklist: list[WorkItem], grounding: list[dict], tolerance: int) -> list[dict]:
    """Machine-readable drift findings for `--json` and `fix apply-drift`: one dict per confirmed
    drifted claim with the corrected `path:line` already computed. `fix apply-drift` matches `claim`
    back to its edge and writes `corrected` into the map's `where`."""
    return [{
        "claim": w.claim,
        "stored": d.stored,
        "corrected": consensus_evidence(d.stored, ev),
        "same_file": d.same_file,
        "distance": d.distance,
    } for w, d, ev in _confirmed_drifts(worklist, grounding, tolerance)]


def _format(findings: list[tuple[WorkItem, DriftResult]], tolerance: int) -> str:
    if not findings:
        return f"anchor-drift: no drift among confirmed claims (tolerance={tolerance})."
    lines = [f"anchor-drift: {len(findings)} confirmed claim(s) whose `where` drifts "
             f"(tolerance={tolerance}) — fix each map `where`, the LLM only reported the line:"]
    for w, d in findings:
        found = "a different file" if not d.same_file else f"line {d.reported} ({d.distance} off)"
        lines.append(f"  - {w.claim}: stored [{d.stored}] — skeptics found {found}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex anchor-drift --map <map.json> --verdicts <raw.json> "
              "[--repo <root>] [--tolerance N] [--json]\n\n"
              "Deterministic Layer-2 anchor-drift over the grounding skeptics' verdicts: for each\n"
              "CONFIRMED claim, flag when the stored `where` differs from the line the skeptics found.\n"
              "Informational (non-gating); the lead reconciles by fixing the map's `where` — or feeds\n"
              "`--json` straight into `coyodex fix apply-drift` to write the corrections.")
        return 0
    map_path = verdicts_path = None
    tolerance = _DEFAULT_TOLERANCE
    as_json = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True
        elif a in ("--map", "--verdicts", "--repo", "--tolerance"):
            i += 1
            if i >= len(argv):
                print(f"ERROR: {a} needs a value", file=sys.stderr)
                return 2
            if a == "--map":
                map_path = argv[i]
            elif a == "--verdicts":
                verdicts_path = argv[i]
            elif a == "--tolerance":
                tolerance = int(argv[i])
            # --repo is accepted for signature parity; drift is a line comparison, no repo needed
        else:
            print(f"ERROR: unknown argument '{a}'", file=sys.stderr)
            return 2
        i += 1
    if not map_path or not verdicts_path:
        print("ERROR: --map and --verdicts are required", file=sys.stderr)
        return 2
    m = load_model(Path(map_path).read_text(encoding="utf-8"))
    worklist = l2_worklist_model(m)
    grounding = json.loads(Path(verdicts_path).read_text(encoding="utf-8")).get("grounding", [])
    if as_json:
        print(json.dumps({"findings": drift_records(worklist, grounding, tolerance)}, indent=2))
    else:
        print(_format(drift_findings(worklist, grounding, tolerance), tolerance))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
