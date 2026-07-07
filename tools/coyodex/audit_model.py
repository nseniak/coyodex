#!/usr/bin/env python3
"""`coyodex audit` for a model map — L1 self-contradiction + the L2 grounding worklist.

The adversarial pass reads model FIELDS directly: the Golden Path's narrative order vs. the
mechanism (T6 flows + backbone edges), then the ranked worklist of "actually-does" claims for
fresh-context skeptics.

The worklist's self-describing `detail` avoids the false-refutation class where a skeptic reduces
an endpoint to one arbitrary file:
  - a COMPONENT endpoint is described by its canonical anchor AND its member entry points (every T4
    row naming it) — an umbrella component ("Event stream — in-process + Redis") is never reduced
    to one arbitrary file, which is what got true edges refuted;
  - a DEP endpoint is described as an EXTERNAL SYSTEM ("D4 = Google OAuth (service: Google OAuth
    2.0 endpoints)") — its Kind + Type, never a code anchor, so a component reaching the real
    external service can't be refuted because the dep was anchored at a local wrapper module.

Severity model, ranking, and the verbs-prioritize-never-gate principle are stable. Stdlib-only. The
audit vocabulary — severities, verb sets, Finding/WorkItem, the report formatter — lives here.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from coyodex import grammar
from coyodex.model import ProjectModel, load_model

# ── the audit vocabulary (shared with the eval, which imports it from here) ──────────────────────

# WRITE = the C→E verbs that ESTABLISH or MUTATE an entity's stored state: `persists` / `writes` /
# `creates`. Crucially `writes` is used for BOTH creates AND updates (there is no distinct create
# verb), so the FIRST write of an entity in Golden-Path order is treated as its (possible) create,
# and the precedence check stays ADVISORY — its message says both readings. `encrypts` is excluded:
# encrypting a stored value is a transform, not an establishment.
WRITE_VERBS = frozenset({"persists", "writes", "creates"})
READ_VERBS = frozenset({"reads"})

CONTRADICTION = "CONTRADICTION"
ADVISORY = "ADVISORY"
WARNING = "WARNING"
_SEV_RANK = {CONTRADICTION: 0, ADVISORY: 1, WARNING: 2}

_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")  # markdown link → (label, href)
_FILEREF = re.compile(r"[\w./-]+(?:#L\d+|:\d+)")  # a bare `path#Lnnn` / `file:line` drill anchor


def _anchor(cell: str) -> str | None:
    """A drill-to-code anchor from a cell: the markdown-link href if present, else a bare file ref."""
    m = _LINK.search(cell)
    if m:
        return m.group(2)
    fm = _FILEREF.search(cell)
    return fm.group(0) if fm else None


# Split a compound Actor cell into alternatives on UNAMBIGUOUS separators (`or`, `/`, `,`). NOT on
# `and`: it usually belongs to an atomic role name ("Research and Development"), and splitting it
# would let a fragment ("Research") wrongly match and hide a real mismatch.
_ACTOR_SEP = re.compile(r"\s+or\s+|\s*/\s*|\s*,\s*", re.I)


def _norm_actor(actor: str) -> str:
    """A role name reduced for comparison: markdown emphasis/backticks stripped, lowercased."""
    return re.sub(r"[*`]", "", actor).strip().lower()


def _actor_alternatives(cell: str) -> set[str]:
    """The normalised roles a compound Actor cell allows: `Admin or Manager` → {admin, manager}."""
    return {_norm_actor(p) for p in _ACTOR_SEP.split(cell) if p.strip()}


def _claim_text(cell: str) -> str:
    """Cell text with any markdown link reduced to plain words: the link's label when the cell is
    link-only (so a claim reads 'protected by: require_admin', not the raw `[..](..)`)."""
    stripped = _LINK.sub("", cell).strip()
    if stripped:
        return stripped
    m = _LINK.search(cell)
    return m.group(1) if m else cell


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    location: str
    message: str


@dataclass(frozen=True)
class WorkItem:
    claim: str
    anchor: str | None   # a `file:line` the grounder starts from, if the map gives one
    why_risky: str
    # Self-describing context (G1): each endpoint's display name + source anchor(s), read straight
    # from the model — so a fresh-context skeptic given only this item can find the code with NO
    # map file. The short `claim` stays the stable key; `detail` is additive.
    detail: str | None = None


_ENTRY_POINTS_SHOWN = 6  # cap the member entry points listed in a component's claim detail


@dataclass
class GPStep:
    pos: int
    gp_id: str
    uc: str | None
    title: str
    why: str | None
    why_refs: list[int] = field(default_factory=list)


def golden_path_steps(m: ProjectModel) -> list[GPStep]:
    steps: list[GPStep] = []
    for pos, g in enumerate(m.golden_path):
        refs = [int(x) for x in re.findall(r"GP(\d+)", g.why or "")]
        steps.append(GPStep(pos=pos, gp_id=g.id, uc=g.uc, title=g.title, why=g.why, why_refs=refs))
    return steps


def _flow_component_ids(f) -> set[str]:
    comps: set[str] = set()
    for st in f.steps:
        for end in (st.src, st.dst):
            if grammar.is_step_id(end) and end.startswith("C"):
                comps.add(end)
    return comps


def _flow_opening_actor(f) -> str | None:
    for st in f.steps:
        if st.src and not grammar.is_step_id(st.src):
            return st.src
    return None


def _touch_sets(m: ProjectModel) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Per use case, the entities its flow WRITES / READS at component granularity — the same lossy
    attribution the audit has always used. It is LOSSY in both directions — a shared component
    leaks its C→E edges into every flow that names it, and reads routed through a C→C dependency
    are invisible — which is why the precedence check stays ADVISORY, never blocking."""
    comp_writes: dict[str, set[str]] = {}
    comp_reads: dict[str, set[str]] = {}
    for e in m.edges:
        if not e.dst.startswith("E"):
            continue
        verb = e.verb.strip().lower()
        if verb in WRITE_VERBS:
            comp_writes.setdefault(e.src, set()).add(e.dst)
        elif verb in READ_VERBS:
            comp_reads.setdefault(e.src, set()).add(e.dst)
    writes: dict[str, set[str]] = {}
    reads: dict[str, set[str]] = {}
    for f in m.flows:
        w = writes.setdefault(f.uc, set())
        r = reads.setdefault(f.uc, set())
        for comp in _flow_component_ids(f):
            w |= comp_writes.get(comp, set())
            r |= comp_reads.get(comp, set())
    return writes, reads


# ── L1 checks ────────────────────────────────────────────────────────────────────────────────────

def check_precedence(m: ProjectModel) -> list[Finding]:
    steps = golden_path_steps(m)
    writes, reads = _touch_sets(m)
    ename = {e.id: e.name for e in m.entities}

    first_write: dict[str, int] = {}
    for st in steps:
        for e in writes.get(st.uc or "", set()):
            first_write.setdefault(e, st.pos)

    def label(e: str) -> str:
        return f"{e} ({ename[e]})" if e in ename else e

    def at(pos: int) -> str:
        s = next((s for s in steps if s.pos == pos), None)
        return f"GP{pos + 1}" + (f" ({s.uc})" if s and s.uc else "")

    findings: list[Finding] = []
    written_so_far: set[str] = set()
    reported: set[str] = set()
    for st in steps:
        uc = st.uc or ""
        loc = f"GP{st.pos + 1} ({uc}) — {st.title}" if uc else f"GP{st.pos + 1} — {st.title}"
        for e in sorted(reads.get(uc, set())):
            if e in written_so_far or e in writes.get(uc, set()) or e in reported:
                continue
            fw = first_write.get(e)
            if fw is not None and fw > st.pos:
                reported.add(e)
                findings.append(Finding(
                    "read-before-create", ADVISORY, loc,
                    f"reads {label(e)} but the Golden Path first WRITES it later, at {at(fw)}; if "
                    f"that write creates {e}, {at(fw)} should precede this step (if it only updates "
                    f"an entity created off-path, ignore)."))
            elif fw is None:
                reported.add(e)
                findings.append(Finding(
                    "read-never-created", ADVISORY, loc,
                    f"reads {label(e)} but no Golden-Path step writes or creates it — external / "
                    f"config data, or a coverage gap."))
        written_so_far |= writes.get(uc, set())
    return findings


def check_why_refs(m: ProjectModel) -> list[Finding]:
    steps = golden_path_steps(m)
    pos_of = {st.gp_id: st.pos for st in steps}
    findings: list[Finding] = []
    for st in steps:
        loc = f"GP{st.pos + 1} ({st.uc}) — {st.title}" if st.uc else f"GP{st.pos + 1} — {st.title}"
        for ref in st.why_refs:
            ref_id = f"GP{ref}"
            if ref_id not in pos_of:
                findings.append(Finding(
                    "dangling-why-ref", CONTRADICTION, loc,
                    f"`why:` cites {ref_id}, which is not a Golden-Path step."))
            elif pos_of[ref_id] > st.pos:
                findings.append(Finding(
                    "backward-why-ref", CONTRADICTION, loc,
                    f"`why:` cites {ref_id}, which comes AFTER this step in the walk."))
    return findings


def check_actor_attribution(m: ProjectModel) -> list[Finding]:
    actors = {u.id: u.actor for u in m.use_cases if u.actor}
    role_names = {r.name.lower() for r in m.roles}
    findings: list[Finding] = []
    for f in m.flows:
        declared = actors.get(f.uc)
        opening = _flow_opening_actor(f)
        if not declared or not opening:
            continue
        op = _norm_actor(opening)
        if role_names and op not in {_norm_actor(r) for r in role_names}:
            continue  # opener is not a defined actor → a background/system trigger, not a mismatch
        if op in _actor_alternatives(declared):
            continue
        findings.append(Finding(
            "actor-attribution", ADVISORY, f"{f.uc} — {f.title}",
            f"declared Actor '{declared}' (Use-cases table) differs from the flow's opening "
            f"actor '{opening}'."))
    return findings


def check_whyless_steps(m: ProjectModel) -> list[Finding]:
    steps = golden_path_steps(m)
    if not any(st.why for st in steps):
        return []
    findings: list[Finding] = []
    for st in steps:
        if st.pos > 0 and st.why is None:
            loc = f"GP{st.pos + 1} ({st.uc}) — {st.title}" if st.uc else f"GP{st.pos + 1} — {st.title}"
            findings.append(Finding(
                "why-less-step", WARNING, loc,
                "declares no `why:` precondition while other steps do; state its prerequisite, or "
                "confirm it is a valid entry point."))
    return findings


def audit_model(m: ProjectModel) -> list[Finding]:
    findings: list[Finding] = []
    for check in (check_precedence, check_why_refs, check_actor_attribution, check_whyless_steps):
        findings.extend(check(m))
    findings.sort(key=lambda f: (_SEV_RANK.get(f.severity, 9), f.check, f.location))
    return findings


# ── L2 worklist ──────────────────────────────────────────────────────────────────────────────────

def _endpoint_detail(m: ProjectModel) -> dict[str, str]:
    """id → self-describing endpoint text. Components carry their canonical anchor + member entry
    points; deps read as external systems (kind: type) — the F2 fix (see the module docstring)."""
    link = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

    def href(cell: str | None) -> str | None:
        if not cell:
            return None
        hit = link.search(cell)
        return hit.group(2) if hit else cell

    members: dict[str, list[str]] = {}
    for ep in m.entry_points:
        h = href(ep.entity)
        members.setdefault(ep.component, []).append(
            f"{ep.trigger} ({h})" if h else ep.trigger)

    out: dict[str, str] = {}
    for c in m.components:
        desc = f"{c.id} = {c.name}" if c.name and c.name != c.id else c.id
        home = c.anchor or href(c.entry_point)
        if home:
            desc += f" ({home})"
        eps = members.get(c.id, [])
        if eps:
            shown = "; ".join(eps[:_ENTRY_POINTS_SHOWN])
            more = f"; +{len(eps) - _ENTRY_POINTS_SHOWN} more" if len(eps) > _ENTRY_POINTS_SHOWN else ""
            desc += f"; entry points: {shown}{more}"
        out[c.id] = desc
    for d in m.deps:
        kind = grammar.classify_dep(d.kind or "", d.type)
        system = d.type or d.name
        out[d.id] = (f"{d.id} = {d.name} ({kind}: {system} — an external system, not a code "
                     f"module)")
    for e in m.entities:
        desc = f"{e.id} = {e.name}" if e.name and e.name != e.id else e.id
        if e.source:
            desc += f" ({e.source})"
        out[e.id] = desc
    for u in m.use_cases:
        out[u.id] = f"{u.id} = {u.name}" if u.name else u.id
    for g in (*m.subsystems, *m.subdomains):
        desc = f"{g.id} = {g.name}" if g.name else g.id
        h = href(g.anchor)
        if h:
            desc += f" ({h})"
        out[g.id] = desc
    return out


def _edge_detail(src: str, dst: str, described: dict[str, str]) -> str | None:
    parts: list[str] = []
    if src in described:
        parts.append(f"From: {described[src]}")
    if dst in described:
        parts.append(f"To: {described[dst]}")
    return "; ".join(parts) if parts else None


def l2_worklist_model(m: ProjectModel) -> list[WorkItem]:
    """The ranked grounding worklist over the whole backbone — same tiers as the markdown audit
    (security surfaces + enforce/encrypt edges → C→D → C→E → the rest), same explicit-fold-only
    skip for framework/library deps, deduplicated by claim string."""
    described = _endpoint_detail(m)
    folded = {d.id for d in m.deps
              if (d.kind or "").strip().lower() in grammar.DEP_KINDS_FOLDED}
    items: list[WorkItem] = []
    for s in m.security:
        items.append(WorkItem(
            claim=f"Auth surface '{s.surface}' is protected by: {_claim_text(s.check)}",
            anchor=_anchor(s.check),
            why_risky="security boundary — a false claim here is an access-control hole."))
    dep_items: list[WorkItem] = []
    entity_items: list[WorkItem] = []
    other_items: list[WorkItem] = []
    for e in m.edges:
        verb = e.verb.strip().lower()
        claim = f"{e.src} {verb} {e.dst}"
        anchor = _anchor(e.where or "")
        detail = _edge_detail(e.src, e.dst, described)
        if verb in ("enforces", "encrypts"):
            items.append(WorkItem(
                claim=claim, anchor=anchor, detail=detail,
                why_risky=f"'{verb}' is a security-critical relationship — verify the code actually does it."))
        elif e.dst.startswith("D"):
            if e.dst in folded:
                continue  # explicit framework/library — a false 'uses <lib>' edge is benign
            dep_items.append(WorkItem(
                claim=claim, anchor=anchor, detail=detail,
                why_risky=(f"external-dependency data-flow edge — no deterministic gate reads "
                           f"{e.src}'s code to confirm it reaches {e.dst}; ground the call site "
                           f"against the code (the audit→Elastic false-edge class).")))
        elif e.dst.startswith("E"):
            entity_items.append(WorkItem(
                claim=claim, anchor=anchor, detail=detail,
                why_risky=(f"domain-model ownership edge — verify {e.src}'s code actually "
                           f"'{verb}' {e.dst}; a wrong persists/writes/reads mis-wires the "
                           f"subsystem→subdomain bridge.")))
        else:
            other_items.append(WorkItem(
                claim=claim, anchor=anchor, detail=detail,
                why_risky=(f"backbone edge — no deterministic gate confirms {e.src}'s code "
                           f"'{verb}' {e.dst}; ground the call site against the code.")))
    items.extend(dep_items)
    items.extend(entity_items)
    items.extend(other_items)
    seen: set[str] = set()
    unique: list[WorkItem] = []
    for it in items:
        if it.claim not in seen:
            seen.add(it.claim)
            unique.append(it)
    return unique


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────

def _format(findings: list[Finding], worklist: list[WorkItem]) -> str:
    out: list[str] = []
    contradictions = [f for f in findings if f.severity == CONTRADICTION]
    if not findings:
        out.append("L1 self-contradiction: none found.")
    else:
        out.append(f"L1 self-contradiction findings ({len(findings)}):")
        for i, f in enumerate(findings, 1):
            out.append(f"\n[{i}] {f.severity} — {f.check}")
            out.append(f"    where: {f.location}")
            out.append(f"    issue: {f.message}")
    out.append("")
    if worklist:
        out.append(f"L2 grounding worklist ({len(worklist)} claims to disprove against the code — "
                   "farm each to a fresh-context skeptic, method.md Phase 4):")
        for i, w in enumerate(worklist, 1):
            anchor = f"  [{w.anchor}]" if w.anchor else ""
            out.append(f"  {i}. {w.claim}{anchor}")
            if w.detail:  # G1: the claim carries its endpoints' names + files — no map needed
                out.append(f"     who: {w.detail}")
            out.append(f"     risk: {w.why_risky}")
    else:
        out.append("L2 grounding worklist: no high-risk claims detected to ground.")
    advisories = sum(1 for f in findings if f.severity in (ADVISORY, WARNING))
    tail = (f" {advisories} advisory/warning(s) to reconcile (non-blocking)." if advisories else "")
    if contradictions:
        out.append(f"\nAUDIT FAILED: {len(contradictions)} blocking contradiction(s) — fix before "
                   f"rendering.{tail}")
    else:
        out.append(f"\nAUDIT PASSED (L1): no blocking contradictions.{tail} "
                   "Reconcile advisories and run L2 grounding on the worklist above.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex audit [.coyodex/project-map.json]\n\n"
              "The adversarial pass over a model map: L1 deterministic self-contradiction\n"
              "checks + the L2 grounding worklist. Blocks (exit 1) only on a hard contradiction.")
        return 0
    args = [a for a in argv if not a.startswith("-")]
    path = Path(args[0] if args else ".coyodex/project-map.json")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    try:
        m = load_model(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"AUDIT SKIPPED: {e} — run `coyodex validate` first.", file=sys.stderr)
        return 1
    findings = audit_model(m)
    worklist = l2_worklist_model(m)
    print(_format(findings, worklist))
    return 1 if any(f.severity == CONTRADICTION for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
