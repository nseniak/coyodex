#!/usr/bin/env python3
"""coyodex audit — the adversarial pass over a BUILT map (L1 self-contradiction + L2 worklist).

Runs AFTER build / accept, in the invariant ``validate → audit → render``. Where ``validate`` checks
the map is WELL-FORMED (ids resolve, tables shaped, hierarchy sound), ``audit`` checks it is not
SELF-CONTRADICTORY: it makes the map's two layers refute each other — the narrative Golden Path
(step order, actors) versus the mechanism (T6 flows + the backbone edge list). A map is
OVER-DETERMINED: it encodes each precondition twice (once as narrative order, once as which entity a
flow reads vs writes), so the two copies can be checked against each other with no code access at all.

Three tiers were designed (see ``method.md`` "The adversarial pass"):

  L1  self-contradiction  — DETERMINISTIC, no LLM, no code. Implemented here.
  L2  grounding           — fresh-context skeptic sub-agents try to DISPROVE risky "actually-does"
                            claims against the code. The AGENT runs L2 (``method.md`` Phase 4); this
                            module only EMITS the ranked worklist of claims to ground.
  L3  coverage oracle     — code → map enumeration of what SHOULD be mapped; extends
                            ``validate --check-coverage`` (planned, not in this module yet).

Stdlib-only. Reuses the schema-v1 grammar and the validator's edge/table helpers, so audit reads the
map through exactly the same parse the validator and renderer use — never a second, drifting grammar.

Findings are severity-ranked:
  CONTRADICTION — the two layers disagree; a defect by construction (blocks, like a validator error).
  ADVISORY      — a one-sided reading (e.g. a read with no matching create) that is often benign
                  (external / config data) but can be a real coverage gap; hand to L2 or a human.
  WARNING       — a structural smell worth a look (non-blocking).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from coyodex import schema_v1
from coyodex.validate_analysis import collect_edges, collect_role_names, iter_tables

# WRITE = the C→E verbs that ESTABLISH or MUTATE an entity's stored state: `persists` / `writes` /
# `creates`. The method's domain-link vocabulary is `C — persists/writes/reads → E` (method.md), and
# crucially `writes` is used for BOTH creates AND updates — the live mcpolis map models "create the
# admin membership" as a `writes` edge. There is no distinct create verb, so the FIRST write of an
# entity in Golden-Path order is treated as its (possible) create. Because `writes` is create-or-update
# ambiguous, the precedence check is ADVISORY and its message SAYS SO: it flags the ordering and lets a
# human / L2 decide whether the later write is really the create or just an update of an off-path
# entity. (Earlier this set was narrowed to persists/creates, which silently missed real
# ordering bugs modeled with `writes` — see the second audit review, finding F1. `encrypts` is excluded:
# encrypting a stored value is a transform, not an establishment.)
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
# `and`: it usually belongs to an atomic role name ("Research and Development", "Arts and Crafts"), and
# splitting it would let a fragment ("Research") wrongly match and hide a real mismatch (2nd review F3).
_ACTOR_SEP = re.compile(r"\s+or\s+|\s*/\s*|\s*,\s*", re.I)


def _norm_actor(actor: str) -> str:
    """A role name reduced for comparison: markdown emphasis/backticks stripped, lowercased. Matches
    how `collect_role_names` normalises (it strips `*`), so audit and the Roles table agree on names."""
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


@dataclass
class GPStep:
    pos: int             # 0-based position in the walk (document order)
    gp_id: str           # e.g. "GP1"
    uc: str | None       # the use case it realizes (from the `*(UCn)*` tag), or None if untagged
    title: str
    why: str | None      # the `why:` precondition line, or None
    why_refs: list[int] = field(default_factory=list)  # GP numbers cited in the why line


# ── Parsing (all through the shared schema-v1 grammar) ──────────────────────────────────────────────

def parse_golden_path(text: str) -> list[GPStep]:
    """The Golden Path as ordered steps: id, realized use case, title, and the `why:` precondition
    (with any `GPn` numbers it cites). Position is DOCUMENT order — the walk — not the numeric id."""
    lines = text.splitlines()
    steps: list[GPStep] = []
    pos = 0
    for i, line in enumerate(lines):
        dm = schema_v1.DEF_GP.match(line.strip())
        if not dm:
            continue
        head = schema_v1.GP_HEADING.match(line.strip())
        gp_id = dm.group(1)
        title = head.group(2).strip() if head else ""
        tag = schema_v1.GP_UC_TAG.search(line)
        uc = tag.group(1) if tag else None
        why: str | None = None
        why_refs: list[int] = []
        for nxt_raw in lines[i + 1:]:
            nxt = nxt_raw.strip()
            if nxt.startswith(("**GP", "---", "#")):
                break
            wm = re.match(r"^why:\s*(.+)$", nxt)
            if wm:
                captured = wm.group(1).strip()
                why = captured
                why_refs = [int(x) for x in re.findall(r"GP(\d+)", captured)]
                break
            if nxt and not nxt.startswith("<!--"):
                break  # first real content before any why: this step has none
        steps.append(GPStep(pos=pos, gp_id=gp_id, uc=uc, title=title, why=why, why_refs=why_refs))
        pos += 1
    return steps


def collect_use_case_actors(text: str) -> dict[str, str]:
    """Map UCid → its declared Actor from the Use-cases table (header has 'use case' + 'actor').
    Empty when there is no such table, so the actor checks become no-ops."""
    out: dict[str, str] = {}
    for _start, block in iter_tables(text):
        headers = [c.lower() for c in schema_v1.split_cells(block[0])]
        if "actor" not in headers or not any(h.startswith("use case") for h in headers):
            continue
        ai = headers.index("actor")
        for row in block[2:]:
            if schema_v1.is_separator_row(row):
                continue
            cells = schema_v1.split_cells(row)
            if not cells or ai >= len(cells):
                continue
            uc = schema_v1.ID_TOKEN.search(cells[0])
            actor = cells[ai].strip()
            if uc and uc.group(0).startswith("UC") and actor:
                out[uc.group(0)] = actor
        break
    return out


def flow_component_ids(flow: schema_v1.Flow) -> set[str]:
    """The component (`C…`) ids named as either endpoint of a flow's steps."""
    comps: set[str] = set()
    for st in flow.steps:
        if not st.ok:
            continue
        for end, is_id in ((st.src, st.src_is_id), (st.dst, st.dst_is_id)):
            if is_id and end.startswith("C"):
                comps.add(end)
    return comps


def flow_opening_actor(flow: schema_v1.Flow) -> str | None:
    """The role name driving the flow: the first step whose SOURCE is an actor (not an element id)."""
    for st in flow.steps:
        if st.ok and not st.src_is_id and st.src:
            return st.src
    return None


def _entity_names(text: str) -> dict[str, str]:
    return {c.id: c.name for c in schema_v1.iter_domain_cards(text.splitlines())}


def _touch_sets(text: str) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Per use case, the entities its flow WRITES (write-verb C→E edges) and READS (read-verb ones),
    attributed at COMPONENT granularity: a use case whose flow names component C is credited with all
    of C's C→E edges.

    This attribution is LOSSY in BOTH directions and is why the precedence check is ADVISORY, not
    blocking:
      - it OVER-reads: a shared component (say a web app) that reads entity X for one use case leaks
        `reads X` into EVERY use case whose flow merely names it — a read the use case may not do;
      - it can OVER-write the same way; and it MISSES reads routed through a `C→C` dependency (the
        flow names C, C reads another component that reads the entity — no `C→E` edge on C, so the read
        is invisible here). The map records flow↔entity usage only at this component granularity, so a
        tighter attribution is not derivable from the map alone — L2 grounding against the code is."""
    comp_writes: dict[str, set[str]] = {}
    comp_reads: dict[str, set[str]] = {}
    for src, verb, dst in collect_edges(text):
        if not dst.startswith("E"):
            continue
        if verb in WRITE_VERBS:
            comp_writes.setdefault(src, set()).add(dst)
        elif verb in READ_VERBS:
            comp_reads.setdefault(src, set()).add(dst)
    writes: dict[str, set[str]] = {}
    reads: dict[str, set[str]] = {}
    for flow in schema_v1.iter_flows(text.splitlines()):
        c_set = writes.setdefault(flow.uc, set())
        r_set = reads.setdefault(flow.uc, set())
        for comp in flow_component_ids(flow):
            c_set |= comp_writes.get(comp, set())
            r_set |= comp_reads.get(comp, set())
    return writes, reads


# ── L1 checks (deterministic, no code access) ──────────────────────────────────────────────────────

def check_precedence(text: str) -> list[Finding]:
    """read-before-create + read-never-created. Walk the Golden Path in order; an entity a step READS
    should already have been WRITTEN (created) by an earlier (or the same) step. A first write at a
    LATER position is the read-before-create signal; an entity read on the spine but never written on
    it is read-never-created (usually external/config data, sometimes a coverage gap).

    BOTH are ADVISORY, never blocking, for two reasons: (1) `writes` is create-OR-update ambiguous
    (see WRITE_VERBS), so a "first write later" may be a real create-after-read OR just an update of an
    entity created off-path — the message says both; (2) the read/write sets come from lossy
    component-granularity attribution (see `_touch_sets`): reads leak across shared components and
    reads routed through `C→C` dependencies are invisible, so this check has real false positives AND
    false negatives. It is a strong "look here — the two layers may disagree on ordering" pointer for a
    human or L2 to settle, not a fact. (The mcpolis sign-in-before-org bug surfaces here as an
    advisory.) Findings are DEDUPED per entity — reported once, at the earliest offending read — so a
    shared entity read by many steps does not spam one advisory per step."""
    steps = parse_golden_path(text)
    writes, reads = _touch_sets(text)
    ename = _entity_names(text)

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
    reported: set[str] = set()  # per-entity dedup: one finding per entity, at its earliest read
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
                    f"that write creates {e}, {at(fw)} should precede this step (if it only updates an "
                    f"entity created off-path, ignore)."))
            elif fw is None:
                reported.add(e)
                findings.append(Finding(
                    "read-never-created", ADVISORY, loc,
                    f"reads {label(e)} but no Golden-Path step writes or creates it — external / "
                    f"config data, or a coverage gap."))
        written_so_far |= writes.get(uc, set())
    return findings


def check_why_refs(text: str) -> list[Finding]:
    """A `why:` precondition may only cite EARLIER Golden-Path steps. Citing a later step is a direct
    order contradiction; citing a step that does not exist is a dangling reference."""
    steps = parse_golden_path(text)
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


def check_actor_attribution(text: str) -> list[Finding]:
    """ADVISORY: the use case's declared Actor (Use-cases table) vs the role its flow OPENS with (the
    first actor step of the T6 flow) — a hint that the two layers may disagree on who drives the use
    case. Guards against the confirmed false positives:
      - markdown is stripped and a compound Actor cell (`Admin or Manager`) matches any alternative;
      - when a Roles table exists, an opener that is NOT a defined Role is a background/system trigger
        (a scheduler, a webhook) — not an actor mismatch — so it is skipped (the validator flags an
        undefined-role opener on its own).
    No-op when a flow has no opening actor step or the use case has no Actor cell."""
    actors = collect_use_case_actors(text)
    role_names = collect_role_names(text)  # lowercased Roles-table names; empty when there is none
    findings: list[Finding] = []
    for flow in schema_v1.iter_flows(text.splitlines()):
        declared = actors.get(flow.uc)
        opening = flow_opening_actor(flow)
        if not declared or not opening:
            continue
        op = _norm_actor(opening)
        if role_names and op not in {_norm_actor(r) for r in role_names}:
            continue  # opener is not a defined actor → a background/system trigger, not a mismatch
        if op in _actor_alternatives(declared):
            continue  # matches the declared actor (or one of its alternatives)
        findings.append(Finding(
            "actor-attribution", ADVISORY, f"{flow.uc} — {flow.title}",
            f"declared Actor '{declared}' (Use-cases table) differs from the flow's opening "
            f"actor '{opening}'."))
    return findings


def check_whyless_steps(text: str) -> list[Finding]:
    """Once a map uses the `why:` convention at all, every NON-initial step should state its
    precondition. A non-first step with no `why:` is a mild smell (the first step legitimately has
    none). No-op on maps that don't use `why:` lines, so it stays additive."""
    steps = parse_golden_path(text)
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


L1_CHECKS = (check_precedence, check_why_refs, check_actor_attribution, check_whyless_steps)


def audit(text: str) -> list[Finding]:
    """Run every L1 self-contradiction check and return findings, most severe first."""
    findings: list[Finding] = []
    for check in L1_CHECKS:
        findings.extend(check(text))
    findings.sort(key=lambda f: (_SEV_RANK.get(f.severity, 9), f.check, f.location))
    return findings


# ── L2 worklist (the claims a fresh-context skeptic should ground against code) ─────────────────────

@dataclass(frozen=True)
class WorkItem:
    claim: str
    anchor: str | None   # a `file:line` the grounder starts from, if the map gives one
    why_risky: str


def l2_worklist(text: str) -> list[WorkItem]:
    """The ranked list of high-risk "actually-does" claims for L2 grounding. These are NOT checked
    here — they are the worklist the audit hands to fresh-context skeptic sub-agents (method.md Phase
    4), each told to DISPROVE its claim against the code. Highest risk first: security/auth surfaces,
    then policy/encryption edges (the claims whose falsity is most dangerous)."""
    items: list[WorkItem] = []

    # (1) Security & auth table rows — each is an "actually-does" claim with a real risk if false.
    for _start, block in iter_tables(text):
        headers = [c.lower() for c in schema_v1.split_cells(block[0])]
        if not headers or headers[0] != "surface" or "auth check" not in headers:
            continue
        ci = headers.index("auth check")
        for row in block[2:]:
            if schema_v1.is_separator_row(row):
                continue
            cells = schema_v1.split_cells(row)
            if not cells:
                continue
            check_cell = cells[ci] if ci < len(cells) else ""
            items.append(WorkItem(
                claim=f"Auth surface '{cells[0]}' is protected by: {_claim_text(check_cell)}",
                anchor=_anchor(check_cell),
                why_risky="security boundary — a false claim here is an access-control hole."))
        break

    # (2) Policy / encryption backbone edges — enforce & encrypt claims, with their call site.
    for _start, block in iter_tables(text):
        headers = [c.lower() for c in schema_v1.split_cells(block[0])]
        if headers[:3] != ["from", "verb", "to"]:
            continue
        wi = headers.index("where") if "where" in headers else None
        for row in block[2:]:
            if schema_v1.is_separator_row(row):
                continue
            cells = schema_v1.split_cells(row)
            if len(cells) < 3:
                continue
            verb = cells[1].strip().lower()
            if verb not in ("enforces", "encrypts"):
                continue
            src = schema_v1.ID_TOKEN.search(cells[0])
            dst = schema_v1.ID_TOKEN.search(cells[2])
            where = cells[wi] if wi is not None and wi < len(cells) else ""
            items.append(WorkItem(
                claim=f"{src.group(0) if src else cells[0]} {verb} {dst.group(0) if dst else cells[2]}",
                anchor=_anchor(where),
                why_risky=f"'{verb}' is a security-critical relationship — verify the code actually does it."))
    return items


# ── CLI ────────────────────────────────────────────────────────────────────────────────────────────

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
        print("usage: coyodex audit [.coyodex/project-map.md]\n\n"
              "The adversarial pass: L1 deterministic self-contradiction checks + an L2 grounding\n"
              "worklist. Blocks (exit 1) only on a hard contradiction (a `why:` reference that points\n"
              "forward or nowhere); read-before-create and actor-attribution are advisory. Run in the\n"
              "invariant `validate → audit → render`.")
        return 0
    args = [a for a in argv if not a.startswith("-")]
    path = Path(args[0] if args else ".coyodex/project-map.md")
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 1
    raw = path.read_text(encoding="utf-8")
    fence_line = schema_v1.unterminated_fence_line(raw)
    if fence_line is not None:
        print(f"AUDIT SKIPPED: unterminated code fence at line {fence_line} — run `coyodex validate` "
              "first (every table after the fence is dropped from the parse).", file=sys.stderr)
        return 1
    text = schema_v1.strip_fences(raw)
    findings = audit(text)
    worklist = l2_worklist(text)
    print(_format(findings, worklist))
    return 1 if any(f.severity == CONTRADICTION for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
