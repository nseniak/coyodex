#!/usr/bin/env python3
"""`coyodex audit` for a model map — L1 self-contradiction + the L2 grounding worklist.

The adversarial pass reads model FIELDS directly: the Happy Path's narrative order vs. the
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

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from coyodex import balance_lib, prose, records, grammar
from coyodex.anchors import FILEREF as _FILEREF
from coyodex.model import (
    ProjectModel,
    RuleSite,
    expanded_flow_steps,
    group_forests,
    load_model,
)
from coyodex.reporting import reset_full_lists, set_full_lists, shown as _shown

# ── the audit vocabulary (shared with the eval, which imports it from here) ──────────────────────

# WRITE = the C→E verbs that ESTABLISH or MUTATE an entity's stored state: `persists` / `writes` /
# `creates`. Crucially `writes` is used for BOTH creates AND updates (there is no distinct create
# verb), so the FIRST write of an entity in Happy-Path order is treated as its (possible) create,
# and the precedence check stays ADVISORY — its message says both readings. `encrypts` is excluded:
# encrypting a stored value is a transform, not an establishment.
WRITE_VERBS = frozenset({"persists", "writes", "creates"})
READ_VERBS = frozenset({"reads"})

CONTRADICTION = "CONTRADICTION"
ADVISORY = "ADVISORY"
WARNING = "WARNING"
_SEV_RANK = {CONTRADICTION: 0, ADVISORY: 1, WARNING: 2}

_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")  # markdown link → (label, href)
# `_FILEREF` (the bare `path#Lnnn`/`file:line` finder) now lives in coyodex.anchors — imported above.


def _anchor(cell: str) -> str | None:
    """A drill-to-code anchor from a cell: the markdown-link href if present, else a bare file ref."""
    m = _LINK.search(cell)
    if m:
        return m.group(2)
    fm = _FILEREF.search(cell)
    return fm.group(0) if fm else None


# (Actor cells are role-id lists now; the old string-splitting helpers `_ACTOR_SEP` / `_norm_actor` /
# `_actor_alternatives` are gone — `check_actor_attribution` does deterministic id-set membership.)


def _claim_text(cell: str) -> str:
    """Cell text with any markdown link reduced to plain words: the link's label when the cell is
    link-only (so a claim reads 'protected by: require_admin', not the raw `[..](..)`)."""
    stripped = _LINK.sub("", cell).strip()
    if stripped:
        return stripped
    m = _LINK.search(cell)
    return m.group(1) if m else cell


# ── claim identity, and the one writer that acts on it ────────────────────────────────────────────
# A CLAIM string is the only handle a skeptic verdict carries back, so it is the handle every
# anchor-correction path uses. These recompute it from the model (never regex-parse it off a
# verdict), and `apply_anchor_corrections` is the single writer both `fix apply-drift` and
# `assemble --reconcile set_anchors` go through — the second exists because the first wrote only
# into the assembled map, so a live build's 19 corrected anchors were discarded by the next
# assemble and re-typed by hand from the human-readable listing.

EDGE_CLAIM = re.compile(r"^([A-Z]+\d+) (\S+) ([A-Z]+\d+)$")   # `C5 persists E2`


def security_claim(surface: str, source: str) -> str:
    """A LEGACY security row's L2 claim, EXACTLY as `l2_worklist_model` builds it.

    Rules with `access: true` are the storage for auth surfaces now, and their claims come from
    `rule_site_claim`. This stays for maps built before the fold, which are not migrated — they are
    rebuilt (see the release note). It is the same shape either way: a surface, and the line that
    protects it."""
    return f"Auth surface '{surface}' is protected by: {_claim_text(source)}"


def rule_site_claim(statement: str, where: str, why: str) -> str:
    """A rule site's L2 claim, EXACTLY as `l2_worklist_model` builds it.

    THE ANCHOR IS PART OF THE CLAIM STRING. `l2_worklist_model` de-duplicates by claim, so a rule
    enforced at four lines would collapse to ONE skeptic verdict without it — and the collapsed
    verdict would then read as covering all four. The `why` rides along because that is the specific
    thing a skeptic re-reading the line has to find true."""
    detail = f" — {_claim_text(why)}" if (why or "").strip() else ""
    return f"Rule '{statement}' is enforced at {where}{detail}"


def cadence_claim(kind: str, trigger: str, cadence: str) -> str:
    """An entry point's cadence claim, EXACTLY as `l2_worklist_model` builds it."""
    return f"Entry point [{kind}] {trigger} runs on cadence '{cadence}'"


def lifecycle_claim(el_id: str, name: str, states: "Sequence[str]",
                    transitions: "Sequence[object]") -> str:
    """An element's lifecycle claim, EXACTLY as `l2_worklist_model` builds it.

    Extracted so the worklist and `apply_anchor_corrections` cannot drift apart. The rule-site claim
    was once built in one place and re-derived in the other; the two wordings diverged and every rule
    correction was reported as an unparseable EDGE claim and dropped."""
    return (f"{el_id} ({name}) has states [{', '.join(states)}]"
            + (f" with {len(transitions)} transition(s)" if transitions else ""))


def apply_anchor_corrections(m: ProjectModel,
                             corrections: list[tuple[str, str]]) -> tuple[dict[str, int], list[str]]:
    """Write each `(claim, corrected anchor)` onto the element its claim identifies.

    Five kinds, matched by recomputing every candidate's claim: an edge's `where`, a security
    row's `source`, an entry point's `cadence_source`, a business rule SITE's `where`, and an
    element's `states.source`. Returns
    per-kind counts and the notes to print. A claim matching 0 or >1 elements is NEVER blind-written — it is reported and skipped,
    the same multiplicity rule `fix security-row` enforces, and for the same reason: two rows can
    share a surface, two edges can share a triple, and picking "the first" is how a hand script
    overwrote a claim nobody meant to touch.

    RESOLVE EVERYTHING FIRST, THEN WRITE. A single pass that matched against the model it was
    mutating made the result depend on worklist order: correcting `S@a.py:1 -> b.py:2` and
    `S@b.py:2 -> c.py:3` in one order applied both, and in the other order the second correction
    re-matched the row the first had just moved, saw two candidates, skipped — and left two
    byte-identical security rows behind. Same inputs, two different maps. Two corrections that land
    on ONE element are refused for the same reason: whichever won would be an accident of order."""
    counts = {"edge": 0, "security": 0, "cadence": 0, "rule_site": 0, "lifecycle": 0}
    notes: list[str] = []
    # Pass 1 — resolve every claim against the UNTOUCHED model.
    # (claim, corrected, kind, index, sub-index). `sub` is -1 for the flat arrays and the SITE
    # index for a rule, whose target is two levels deep. Both are only ever used to address the
    # same element again — and the pair is what the contested-target check is keyed on.
    resolved: list[tuple[str, str, str, int, int]] = []
    for claim, corrected in corrections:
        if not corrected:
            notes.append(f"note: no corrected line for '{claim}' — left unchanged")
            continue
        mo = EDGE_CLAIM.match(claim)
        if mo:
            src, verb, dst = mo.group(1), mo.group(2).lower(), mo.group(3)
            hits = [i for i, e in enumerate(m.edges)
                    if e.src == src and e.verb.strip().lower() == verb and e.dst == dst]
            if len(hits) != 1:
                notes.append(f"WARNING: '{claim}' matches {len(hits)} edges — skipped (resolve "
                             f"by hand: an ambiguous multi-site edge must not be blind-rewritten).")
                continue
            resolved.append((claim, corrected, "edge", hits[0], -1))
            continue
        sec = [i for i, s in enumerate(m.security)
               if security_claim(s.surface, s.source) == claim]
        if sec:
            if len(sec) != 1:
                notes.append(f"WARNING: '{claim}' matches {len(sec)} security surfaces — skipped "
                             f"(resolve by hand).")
                continue
            resolved.append((claim, corrected, "security", sec[0], -1))
            continue
        sites = [(ri, si) for ri, br in enumerate(m.rules)
                 for si, site in enumerate(br.sites)
                 if (site.where or "").strip()
                 and rule_site_claim(br.statement, (site.where or "").strip(), site.why) == claim]
        if sites:
            if len(sites) != 1:
                notes.append(f"WARNING: '{claim}' matches {len(sites)} rule sites — skipped "
                             f"(resolve by hand).")
                continue
            resolved.append((claim, corrected, "rule_site", sites[0][0], sites[0][1]))
            continue
        eps = [i for i, ep in enumerate(m.entry_points)
               if (ep.cadence or "").strip()
               and cadence_claim(ep.kind, ep.trigger, ep.cadence) == claim]
        if eps:
            if len(eps) != 1:
                notes.append(f"WARNING: '{claim}' matches {len(eps)} entry points — skipped "
                             f"(resolve by hand).")
                continue
            resolved.append((claim, corrected, "cadence", eps[0], -1))
            continue
        # Lifecycle LAST among the claim-shaped kinds: its target is `states.source` on either an
        # entity or a component, so `sub` carries WHICH list rather than a nested index. The theme
        # was drift-ELIGIBLE (the skeptic is sent to the declaring enum, the same line the anchor
        # holds) with no writer here, so every confirmed lifecycle drift was re-authored by hand —
        # verbatim the `cadence` gap that this same function was extended to close.
        life = [(i, which)
                for which, seq in ((0, m.entities), (1, m.components))
                for i, el in enumerate(seq)
                if (sm := getattr(el, "states", None)) is not None and sm.states
                and (sm.source or "").strip()
                and lifecycle_claim(el.id, el.name, sm.states, sm.transitions) == claim]
        if life:
            if len(life) != 1:
                notes.append(f"WARNING: '{claim}' matches {len(life)} lifecycles — skipped "
                             f"(resolve by hand).")
                continue
            resolved.append((claim, corrected, "lifecycle", life[0][0], life[0][1]))
            continue
        notes.append(f"WARNING: '{claim}' matches no edge, security surface, rule site, "
                     f"cadenced entry point or lifecycle in this map — skipped (the claim may "
                     f"have been rewritten since).")
    # Two corrections resolving to ONE element cannot both be honoured; order must not decide.
    # Keyed on the CORRECTED value, not the claim: the same claim listed twice with two different
    # anchors is the same conflict wearing one name, and comparing claims missed it entirely.
    seen: dict[tuple[str, int, int], str] = {}
    contested: set[tuple[str, int, int]] = set()
    for _claim, corrected, kind, idx, sub in resolved:
        prior = seen.get((kind, idx, sub))
        if prior is not None and prior != corrected:
            contested.add((kind, idx, sub))
        seen.setdefault((kind, idx, sub), corrected)
    # Pass 2 — write.
    for claim, corrected, kind, idx, sub in resolved:
        if (kind, idx, sub) in contested:
            notes.append(f"WARNING: '{claim}' and another correction both resolve to the same "
                         f"{kind} — skipped BOTH (whichever won would be an accident of order; "
                         f"resolve by hand).")
            continue
        if kind == "edge":
            e = m.edges[idx]
            if e.where != corrected:
                notes.append(f"  {claim}: where {e.where!r} → {corrected!r}")
                e.where = corrected
                counts["edge"] += 1
        elif kind == "security":
            s = m.security[idx]
            if s.source != corrected:
                notes.append(f"  {claim}: source {s.source!r} → {corrected!r}")
                s.source = corrected
                counts["security"] += 1
        elif kind == "rule_site":
            site = m.rules[idx].sites[sub]
            if site.where != corrected:
                notes.append(f"  {claim}: where {site.where!r} → {corrected!r}")
                site.where = corrected
                counts["rule_site"] += 1
        elif kind == "lifecycle":
            el = (m.entities if sub == 0 else m.components)[idx]
            sm = getattr(el, "states", None)
            if sm is not None and sm.source != corrected:
                notes.append(f"  {claim}: states.source {sm.source!r} → {corrected!r}")
                sm.source = corrected
                counts["lifecycle"] += 1
        else:
            ep = m.entry_points[idx]
            if ep.cadence_source != corrected:
                notes.append(f"  {claim}: cadence_source {ep.cadence_source!r} → {corrected!r}")
                ep.cadence_source = corrected
                counts["cadence"] += 1
    return counts, notes


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
    # Whether `anchor-drift` may NUDGE this item's anchor when the skeptics report a different line.
    # Default True: for a call-site claim (an edge) the anchor IS meant to be the acting line, so a
    # reported line that differs is drift to correct. FALSE for claims whose anchor deliberately
    # points somewhere the operation does NOT happen — a store claim is anchored at the entity's
    # TYPE DEFINITION by contract, so the skeptics' WRITE site is not drift, and moving the anchor
    # there would corrupt the domain card. Such claims are still grounded and still refutable;
    # only the anchor nudge (`anchor-drift` → `fix apply-drift`) is suppressed. Report-only.
    drift_eligible: bool = True
    # Which KIND of claim this is, recorded at the site that builds it — never re-derived by parsing
    # `claim` afterwards. method.md tells a lead to batch the Phase-4 skeptics "by theme/risk", and
    # until now the payload carried no such field: a live build read `audit --json`, printed the keys,
    # found nothing to group by, and fell back to sequential chunks of 40 in worklist order. The
    # ranking saved its first batch (all security) but batches 2-10 were arbitrary slices of a list.
    # Values are a closed set, `_THEMES`, so a consumer can group without string-matching prose.
    theme: str = "backbone"


#: The closed set of `WorkItem.theme` values, most-dangerous-first AND in the order
#: `l2_worklist_model` emits them — so a consumer that batches in worklist order also batches by
#: risk, and one that iterates `_THEMES` gets the same sequence. Both halves are pinned by
#: `test_themes_are_closed_and_match_the_worklist_order`, which reads the `theme=` literals out of
#: this module's own source: a new claim kind carrying an unlisted theme, or appended in the wrong
#: tier, fails there. (An earlier version claimed a pin that did not exist, and `backbone` — the
#: largest, lowest-risk bucket — really was emitted 4th of 8.)
_THEMES: tuple[str, ...] = (
    "security",       # auth surfaces + enforces/encrypts edges: a false claim is an access-control hole
    "rule",           # a business rule's enforcement SITE — the product decision layer. Second only
                      # to security: a rule states what the product decides, and an unchallenged one
                      # reads as a fact about the business rather than a guess about a line.
    "dep-usage",      # C→D: does this component really reach that external system
    "ownership",      # C→E: persists/writes/reads — mis-wires the subsystem→subdomain bridge
    "persistence",    # store rows: what is persisted where
    "messaging",      # channel participant lists: the async half of the system
    "lifecycle",      # state machines: rot fastest
    "cadence",        # when code runs
    "backbone",       # every other edge
)

_ENTRY_POINTS_SHOWN = 6  # cap the member entry points listed in a component's claim detail


@dataclass
class HPStep:
    pos: int
    hp_id: str
    uc: str | None
    title: str
    why: str | None
    why_refs: list[int] = field(default_factory=list)
    why_uc_refs: list[str] = field(default_factory=list)


def happy_path_steps(m: ProjectModel) -> list[HPStep]:
    steps: list[HPStep] = []
    for pos, g in enumerate(m.happy_path):
        refs = [int(x) for x in re.findall(r"\bHP(\d+)\b", g.why or "")]
        # A `why:` may cite the prerequisite USE CASE instead of a walk position. `HPn` is "just its
        # position in the walk", so INSERTING a step silently invalidates every later `HPn` citation
        # — a live build hit exactly that (adding a missing first step turned a valid `why:` into a
        # forward reference, a BLOCKING audit failure found after the final assemble). A `UCn`
        # citation names what the step depends on, not where it happens to sit, so it survives.
        uc_refs = sorted(set(re.findall(r"\bUC\d+\b", g.why or "")))
        steps.append(HPStep(pos=pos, hp_id=g.id, uc=g.uc, title=g.title, why=g.why,
                            why_refs=refs, why_uc_refs=uc_refs))
    return steps


def _flow_component_ids(m: ProjectModel, f) -> set[str]:
    comps: set[str] = set()
    for st in expanded_flow_steps(m, f):  # sub-flow content counts as the referencing flow's own
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
        for comp in _flow_component_ids(m, f):
            w |= comp_writes.get(comp, set())
            r |= comp_reads.get(comp, set())
    return writes, reads


# ── L1 checks ────────────────────────────────────────────────────────────────────────────────────

def check_precedence(m: ProjectModel) -> list[Finding]:
    steps = happy_path_steps(m)
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
        return f"HP{pos + 1}" + (f" ({s.uc})" if s and s.uc else "")

    findings: list[Finding] = []
    written_so_far: set[str] = set()
    reported: set[str] = set()
    for st in steps:
        uc = st.uc or ""
        loc = f"HP{st.pos + 1} ({uc}) — {st.title}" if uc else f"HP{st.pos + 1} — {st.title}"
        for e in sorted(reads.get(uc, set())):
            if e in written_so_far or e in writes.get(uc, set()) or e in reported:
                continue
            fw = first_write.get(e)
            if fw is not None and fw > st.pos:
                reported.add(e)
                findings.append(Finding(
                    "read-before-create", ADVISORY, loc,
                    f"reads {label(e)} but the Happy Path first WRITES it later, at {at(fw)}; if "
                    f"that write creates {e}, {at(fw)} should precede this step (if it only updates "
                    f"an entity created off-path, ignore). "
                    f"Record 'read-before-create <id>: <why>' under an 'Audit exceptions' extras heading if this is deliberate."))
            elif fw is None:
                reported.add(e)
                findings.append(Finding(
                    "read-never-created", ADVISORY, loc,
                    f"reads {label(e)} but no Happy-Path step writes or creates it — external / "
                    f"config data, or a coverage gap. "
                    f"Record 'read-never-created <id>: <why>' under an 'Audit exceptions' extras heading if this is deliberate."))
        written_so_far |= writes.get(uc, set())
    return findings


_CITE_UC_HINT = ("  Citing the prerequisite USE CASE (`UCn`) instead of the position survives a "
                 "later insertion; `HPn` does not.")


def check_why_refs(m: ProjectModel) -> list[Finding]:
    steps = happy_path_steps(m)
    pos_of = {st.hp_id: st.pos for st in steps}
    # every walk position each use case occupies (a UC may appear at several)
    uc_positions: dict[str, list[int]] = {}
    for st in steps:
        if st.uc:
            uc_positions.setdefault(st.uc, []).append(st.pos)
    known_ucs = {u.id for u in m.use_cases}
    findings: list[Finding] = []
    for st in steps:
        loc = f"HP{st.pos + 1} ({st.uc}) — {st.title}" if st.uc else f"HP{st.pos + 1} — {st.title}"
        for ref in st.why_refs:
            ref_id = f"HP{ref}"
            if ref_id not in pos_of:
                findings.append(Finding(
                    "dangling-why-ref", CONTRADICTION, loc,
                    f"`why:` cites {ref_id}, which is not a Happy-Path step." + _CITE_UC_HINT))
            elif pos_of[ref_id] > st.pos:
                findings.append(Finding(
                    "backward-why-ref", CONTRADICTION, loc,
                    f"`why:` cites {ref_id}, which comes AFTER this step in the walk."
                    + _CITE_UC_HINT))
        for uc_ref in st.why_uc_refs:
            if uc_ref == st.uc:
                continue                                  # a step naming its own use case
            if uc_ref not in known_ucs:
                findings.append(Finding(
                    "dangling-why-ref", CONTRADICTION, loc,
                    f"`why:` cites {uc_ref}, which is not a use case in this map."))
            elif uc_ref not in uc_positions:
                # a real prerequisite the walk does not carry — legitimate (an off-spine use case),
                # but it IS a decision, so surface it the way the spine-coverage rule does.
                findings.append(Finding(
                    "offspine-why-ref", ADVISORY, loc,
                    f"`why:` cites {uc_ref}, which has no Happy-Path position — confirm the "
                    f"prerequisite is reachable off-spine, or give it a step. "
                    f"Record 'offspine-why-ref <id>: <why>' under an 'Audit exceptions' extras heading if this is deliberate."))
            elif min(uc_positions[uc_ref]) > st.pos:
                # ADVISORY, unlike the `HPn` form. `HPn` in a `why:` can only be a position
                # citation, but a use-case id appears in prose for other reasons ("the same guard
                # UC3 uses", "unlike UC7, this step does not persist"), and nothing distinguishes
                # those from a prerequisite. Blocking here would fail a build on a sentence.
                findings.append(Finding(
                    "forward-uc-why-ref", ADVISORY, loc,
                    f"`why:` names {uc_ref}, whose every walk position comes AFTER this step — if "
                    "that is the prerequisite, the order is wrong; if the sentence merely mentions "
                    "it, reword so the citation is unambiguous. "
                    "Record 'forward-uc-why-ref <id>: <why>' under an 'Audit exceptions' extras heading if this is deliberate."))
    return findings


def check_flow_title(m: ProjectModel) -> list[Finding]:
    """A use case's NAME against its own flow's TITLE — the half of a late rename that gets left
    behind.

    Sibling of `check_actor_attribution`: same shape, same heading, same failure. A live map had
    two use cases repointed and renamed near the end of a build without re-tracing; the actor half
    fired here and was recorded, while the stale title went unnoticed by anything.

    High precision, measured before it was written: across three live maps the name and the title
    agree 39/40, 26/27 and everywhere else, and BOTH exceptions were exactly this defect. A
    deliberately different title is legitimate — it just has to be said out loud."""
    uc_name = {u.id: u.name for u in m.use_cases}
    findings: list[Finding] = []
    for f in m.flows:
        name = uc_name.get(f.uc)
        if not name or not f.title:
            continue
        if name.strip().lower() == f.title.strip().lower():
            continue
        findings.append(Finding(
            "flow-title", ADVISORY, f"{f.uc} — {name}",
            f"the use case is named '{name}' but its flow is titled '{f.title}' — a renamed use "
            f"case whose flow was never re-traced, or a deliberate difference. "
            f"Record 'flow-title <id>: <why>' under an 'Audit exceptions' extras heading if this is deliberate."))
    return findings


def check_actor_attribution(m: ProjectModel) -> list[Finding]:
    """The Use-cases table's declared actors vs the flow's opening actor — now a deterministic id-set
    membership test (no string matching): both sides are role ids, so a mismatch is unambiguous."""
    declared_by_uc = {u.id: set(u.actors) for u in m.use_cases if u.actors}
    role_ids = {r.id for r in m.roles}
    role_name = {r.id: r.name for r in m.roles}
    findings: list[Finding] = []
    for f in m.flows:
        declared = declared_by_uc.get(f.uc)
        opening = _flow_opening_actor(f)  # the opening actor step's endpoint — a role id
        if not declared or not opening or not grammar.is_role_id(opening):
            continue
        if role_ids and opening not in role_ids:
            continue  # opener is not a defined role → a background/system trigger, not a mismatch
        if opening in declared:
            continue
        shown = ", ".join(f"{a} ({role_name.get(a, a)})" for a in sorted(declared))
        findings.append(Finding(
            "actor-attribution", ADVISORY, f"{f.uc} — {f.title}",
            f"declared actors [{shown}] (Use-cases table) do not include the flow's opening actor "
            f"{opening} ({role_name.get(opening, opening)}). "
            f"Record 'actor-attribution <id>: <why>' under an 'Audit exceptions' extras heading if this is deliberate."))
    return findings


def check_whyless_steps(m: ProjectModel) -> list[Finding]:
    steps = happy_path_steps(m)
    if not any(st.why for st in steps):
        return []
    findings: list[Finding] = []
    for st in steps:
        if st.pos > 0 and st.why is None:
            loc = f"HP{st.pos + 1} ({st.uc}) — {st.title}" if st.uc else f"HP{st.pos + 1} — {st.title}"
            findings.append(Finding(
                "why-less-step", WARNING, loc,
                "declares no `why:` precondition while other steps do; state its prerequisite, or "
                "confirm it is a valid entry point."))
    return findings


# A description written as a static-wiring dependency ("A needs B to …") instead of a runtime action
# ("A POSTs …"). Reads wrong on the diagram, where the label should say what happens, not what depends
# on what. Kept tight to avoid noise — "used to" is intentionally excluded (usually a valid action).
_DEPENDENCY_PHRASING = re.compile(r"\b(needs?|requires?|depends?\s+on|dependent\s+on|must\s+have)\b", re.I)


def check_dependency_phrasing(m: ProjectModel) -> list[Finding]:
    """Flow-step and edge descriptions should read as actions, not dependency remarks. Advisory: it
    catches the "the page needs the client to POST" shape and asks for "POSTs … through the client"."""
    findings: list[Finding] = []
    # sub-flow steps get the same phrasing audit, located by their OWN container (each fires once)
    for label, steps in ([(f"{f.uc} flow step", f.steps) for f in m.flows]
                         + [(f"{sf.id} step", sf.steps) for sf in m.subflows]):
        for st in steps:
            if st.phrase and _DEPENDENCY_PHRASING.search(st.phrase):
                findings.append(Finding(
                    "dependency-phrasing", ADVISORY, f"{label} {st.n}",
                    f"step text reads as a dependency, not an action: \"{st.phrase}\". "
                    "Reword as what the source does (e.g. \"POSTs … through …\"). "
                    "Record 'dependency-phrasing <id>: <why>' under an 'Audit exceptions' extras heading if this is deliberate."))
    for e in m.edges:
        if e.why and _DEPENDENCY_PHRASING.search(e.why):
            findings.append(Finding(
                "dependency-phrasing", ADVISORY, f"edge {e.src} → {e.dst}",
                f"`Why` reads as a dependency, not an action: \"{e.why}\". "
                "Reword as what the source does (e.g. \"POSTs … through …\"). "
                "Record 'dependency-phrasing <id>: <why>' under an 'Audit exceptions' extras heading if this is deliberate."))
    return findings


#: The extras heading that answers an audit advisory. Read through `balance_lib.extras_bodies`, the
#: one heading reader every escape family shares, so matching can never drift between them.
AUDIT_EXCEPTIONS_HEADING = "Audit exceptions"

#: A recorded line: `<check-name> <Id>[, <Id>…]: <why>`. Line-leading and per-FINDING on purpose —
#: the CHECK is always named, so a record can never silence a whole family the way the `runs-in`
#: literal once did (`validate_model._RUNS_IN_FAMILY`), where one word silenced every advisory in
#: its family and the operator's justification covered exactly one of them. Several ids MAY share
#: one line when one reason genuinely answers all of them (`read-never-created HP1, HP4: <why>`);
#: the check name still scopes every id on it. A `why` is required — an id alone is a dismissal.
_AUDIT_FAMILY = re.compile(r"^\s*(?:[-*]\s+)?\**\s*([a-z][a-z-]+)\s+(?=[A-Z])")


def audit_exceptions(m: ProjectModel) -> set[tuple[str, str]]:
    """`(check-name, id)` pairs the operator has durably justified under 'Audit exceptions'.

    This exists because `audit` read NO extras heading at all: every one of its advisory families —
    `read-never-created`, `read-before-create`, `actor-attribution`, `dependency-phrasing`, the two
    off-spine `why:`-ref families — was permanently unanswerable. An operator who judged a finding
    acceptable had nowhere to say so, so it re-fired at every audit forever and got waved through:
    the "advisory waved through" failure the method names in its own words. A live map carried two
    `read-never-created` advisories through its whole build for exactly this reason."""
    out: set[tuple[str, str]] = set()
    for line in records.lines(m, AUDIT_EXCEPTIONS_HEADING):
        hit = _AUDIT_FAMILY.match(line)
        if not hit:
            continue
        for eid in records.keys_on_line(line[hit.end():], records.ANY_ID_KEY, r"(?:\s*[:—-])"):
            out.add((hit.group(1).lower(), eid))
    return out


def _recordable_id(location: str) -> str | None:
    """The element id an operator records a finding against — the FIRST id in its `location`.

    `search`, not `match`: most locations lead with the id (`UC3 — Place an order`), but the
    dependency-phrasing edge form is `edge C1 → C2`, and anchoring on a leading id would have left
    that family permanently unrecordable — the same gap this whole escape exists to close.

    Where a location names two ids the first is used, so recording `dependency-phrasing C1` covers
    that check on edges OUT of C1. That is broader than one finding and far narrower than a family;
    the suppression count names every pair it dropped, so an over-broad line is visible rather than
    silent."""
    hit = re.search(r"\b([A-Z]+\d+)\b", location)
    return hit.group(1) if hit else None


def audit_model(m: ProjectModel) -> list[Finding]:
    findings: list[Finding] = []
    for check in (check_precedence, check_why_refs, check_actor_attribution, check_flow_title,
                  check_whyless_steps,
                  check_dependency_phrasing):
        findings.extend(check(m))
    findings.sort(key=lambda f: (_SEV_RANK.get(f.severity, 9), f.check, f.location))
    return _apply_audit_exceptions(m, findings)


def _apply_audit_exceptions(m: ProjectModel, findings: list[Finding]) -> list[Finding]:
    """Drop the ADVISORY findings the operator recorded — and say, in a finding, what was dropped.

    Suppression is only ever applied here, at one exit, and it is never silent. That is the whole
    lesson of `validate_model._RUNS_IN_FAMILY`: a recorded exception that removes findings without
    leaving a trace is indistinguishable from having none, and on two live maps a record written about
    one thing silently swallowed unrelated findings. CONTRADICTIONS are never suppressible — those are
    self-inconsistencies in the map, not judgement calls."""
    recorded = audit_exceptions(m)
    if not recorded:
        return findings
    kept: list[Finding] = []
    silenced: list[str] = []
    for f in findings:
        eid = _recordable_id(f.location)
        if f.severity == ADVISORY and eid and (f.check, eid) in recorded:
            silenced.append(f"{f.check} {eid}")
            continue
        kept.append(f)
    if silenced:
        kept.append(Finding(
            "recorded-exceptions", WARNING, f"'{AUDIT_EXCEPTIONS_HEADING}' extras heading",
            f"{len(silenced)} advisory/advisories suppressed by recorded exception(s): "
            f"{', '.join(sorted(silenced))}. Each was judged acceptable by an operator and is NOT "
            f"re-reported above; re-read them by validating a copy with the line removed. A recorded "
            f"line silences exactly one (check, id) pair — never a whole family."))
    unused = sorted(f"{c} {i}" for c, i in recorded
                    if f"{c} {i}" not in silenced)
    if unused:
        kept.append(Finding(
            "recorded-exceptions", WARNING, f"'{AUDIT_EXCEPTIONS_HEADING}' extras heading",
            f"{len(unused)} recorded exception(s) matched no finding: {', '.join(unused)} — the "
            f"advisory was fixed, the id moved, or the check name is misspelled. A line that silences "
            f"nothing reads as a decision the operator never had to make."))
    return kept


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
        h = href(ep.source)
        members.setdefault(ep.component, []).append(
            f"{ep.trigger} ({h})" if h else ep.trigger)

    out: dict[str, str] = {}
    for c in m.components:
        desc = f"{c.id} = {c.name}" if c.name and c.name != c.id else c.id
        home = c.source or href(c.entry_point)
        if home:
            desc += f" ({home})"
        eps = members.get(c.id, [])
        if eps:
            # Through the shared helper, so `audit --json` widens it. 73 of 398 worklist items on a
            # live map carried a truncated `detail`, in the very payload the method tells a build to
            # batch its skeptics from — and `detail` exists to let a fresh-context skeptic find the
            # code with no map file, which a clipped member list defeats.
            desc += f"; entry points: {_shown(eps, _ENTRY_POINTS_SHOWN, sep='; ')}"
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
    for g in group_forests(m):
        desc = f"{g.id} = {g.name}" if g.name else g.id
        h = href(g.source)
        if h:
            desc += f" ({h})"
        out[g.id] = desc
    return out


def _rule_site_detail(m: ProjectModel, site: RuleSite,
                      owners: dict[str, list[str]]) -> str | None:
    """The self-describing context a rule-site claim carries: the components THIS SITE resolves to,
    so a skeptic knows whose code the line is in.

    Per SITE, never per rule. The rule's union would label a site in a file nobody claims with the
    components of its sibling sites — a component's home passed off as evidence, and it would
    suppress the "unverified" signal exactly when a rule is PARTLY grounded, which is when it
    matters. It would also disagree with the markdown view about the same fact.

    DERIVED — `site_components`, the one implementation, never a second walk of `Component.files`.
    `owners` is the prebuilt index: rebuilding it per site made it 76% of `l2_worklist_model`."""
    # LOCAL import, the documented circular-import exception: `validate_model` imports
    # `l2_worklist_model` from this module, so the dependency can only run the other way at call
    # time. Re-deriving the owners here instead is the one thing the design forbids.
    from coyodex.validate_model import site_components
    comps = site_components(m, site, owners)
    if not comps:
        return "In: no component claims this file — the site is UNVERIFIED."
    names = {c.id: c.name for c in m.components}
    return "In: " + ", ".join(f"{names.get(c, c)} ({c})" for c in comps)


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
            claim=security_claim(s.surface, s.source),
            anchor=_anchor(s.source), theme="security",
            why_risky="security boundary — a false claim here is an access-control hole."))
    # An `access: true` rule IS an auth surface — that is what the T7 fold made it — so its sites
    # carry the `security` theme and are ordered with the other security claims. Before this, every
    # rule site was themed `rule` and `m.security` was empty by design, so the theme the audit orders
    # FIRST was permanently empty and "the riskiest batch" meant only "the batch that sorted first".
    # Measured on two real builds: one sent its three-skeptic majority vote to a batch holding 6
    # access claims of 40 while two 40/40 batches got a single skeptic each.
    access_items: list[WorkItem] = []
    rule_items: list[WorkItem] = []
    if m.rules:
        from coyodex.validate_model import component_file_owners   # same circular-import exception
        owners = component_file_owners(m)
        for br in m.rules:
            for site in br.sites:
                where = (site.where or "").strip()
                if not where:
                    continue    # a declared absence claims no line — nothing for a skeptic to read
                target = access_items if br.access else rule_items
                target.append(WorkItem(
                    claim=rule_site_claim(br.statement, where, site.why),
                    anchor=_anchor(where),
                    theme="security" if br.access else "rule", drift_eligible=True,
                    detail=_rule_site_detail(m, site, owners),
                    why_risky=("an ACCESS decision and the line that enforces it — a false claim "
                               "here is an access-control hole.") if br.access else
                              ("a product DECISION and the line that enforces it — a false claim "
                               "here reads as a fact about the business, and the map's decision "
                               "layer is the part a reader trusts most.")))
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
                claim=claim, anchor=anchor, detail=detail, theme="security",
                why_risky=f"'{verb}' is a security-critical relationship — verify the code actually does it."))
        elif e.dst.startswith("D"):
            if e.dst in folded:
                continue  # explicit framework/library — a false 'uses <lib>' edge is benign
            dep_items.append(WorkItem(
                claim=claim, anchor=anchor, detail=detail, theme="dep-usage",
                why_risky=(f"external-dependency data-flow edge — no deterministic gate reads "
                           f"{e.src}'s code to confirm it reaches {e.dst}; ground the call site "
                           f"against the code (the audit→Elastic false-edge class).")))
        elif e.dst.startswith("E"):
            entity_items.append(WorkItem(
                claim=claim, anchor=anchor, detail=detail, theme="ownership",
                why_risky=(f"domain-model ownership edge — verify {e.src}'s code actually "
                           f"'{verb}' {e.dst}; a wrong persists/writes/reads mis-wires the "
                           f"subsystem→subdomain bridge.")))
        else:
            other_items.append(WorkItem(
                claim=claim, anchor=anchor, detail=detail,
                why_risky=(f"backbone edge — no deterministic gate confirms {e.src}'s code "
                           f"'{verb}' {e.dst}; ground the call site against the code.")))
    # The rule tier goes HERE — after the edge loop, which also appends `security`-themed items to
    # `items`. Emitting it where the rules are built (before that loop) interleaves
    # security · rule · security and breaks the `_THEMES` declared-order == emission-order contract.
    # Same reason `dep_items` is collected and extended rather than appended in place.
    # `access_items` are `security`-themed, so they must land BEFORE the `rule` tier for the same
    # reason: appending them where they are built would interleave the two themes. On the two real
    # maps that mistake produces 24 and 22 alternating security/rule groups.
    items.extend(access_items)
    items.extend(rule_items)
    items.extend(dep_items)
    items.extend(entity_items)
    # `other_items` (theme "backbone") is appended LAST, at the end of this function — not here. It is
    # the largest bucket (194 of 398 on a live map) and the lowest-risk one, and appending it here put
    # it 4th in a worklist whose documented contract is most-dangerous-first, ahead of persistence,
    # lifecycle and cadence. A consumer batching in worklist order then spent its first batches on
    # generic backbone edges while the store rows waited.
    # Structured-store claims (WS-A1): "En is stored in Dn container 'x'" is a claim a skeptic can
    # refute by reading the entity's repository/type — a wrong dep or container silently mis-answers
    # the canonical "what is persisted where?" question. Anchor = the entity's own source (the type
    # definition is where the storage wiring is discoverable from). Drift is REPORT-ONLY: a refuted
    # store claim is re-authored, never anchor-nudged — `drift_eligible=False` makes that contract
    # a property of the claim, so `anchor-drift` cannot mistake the skeptics' WRITE site for drift.
    # The reason is that the skeptic is sent to a DIFFERENT KIND OF LINE than the anchor (the write
    # site vs the type definition), so a difference is not evidence of anything.
    # NOT because `fix apply-drift` would rewrite it: an earlier version of this comment claimed
    # that and it was false. `fix._EDGE_CLAIM` only matches `<Id> <verb> <Id>`, so a store claim
    # falls through to the security branch, matches 0 surfaces and writes nothing — verified
    # byte-for-byte. The harm this prevents is report noise drowning the true drifts, which is
    # real (8 of 8 findings on a live map) but narrower than "corruption".
    for en in m.entities:
        st = en.store
        if st is not None and st.dep:
            where = f"{st.dep} container '{st.container}'" if st.container else st.dep
            mode = f" ({st.mode})" if st.mode else ""
            items.append(WorkItem(
                claim=f"{en.id} ({en.name}) is stored in {where}{mode}",
                anchor=_anchor(en.source or ""),
                drift_eligible=False, theme="persistence",
                why_risky=("the persistence inventory hangs on this row — a wrong dep/container "
                           "mis-answers 'what is persisted where?' for every reader.")))
    # Messaging-channel claims (WS-A5): "C12 publishes to 'JOB_QUEUE' on D3; C30 consumes" is a
    # wiring claim a skeptic refutes by reading the enqueue/consume sites — a wrong participant
    # list silently mis-draws the async half of the system. Anchor = the channel's declaring line.
    # Drift REPORT-ONLY (a refuted row is re-authored).
    for mr in m.messaging:
        pubs = ", ".join(mr.publishers) or "nobody"
        cons = ", ".join(mr.consumers) or "nobody"
        on = f" on {mr.broker}" if mr.broker else ""
        items.append(WorkItem(
            claim=f"Channel '{mr.name}'{on}: {pubs} publish(es); {cons} consume(s)",
            anchor=_anchor(mr.source),
            drift_eligible=False, theme="messaging",
            why_risky=("the async catalog hangs on this row — verify the enqueue/consume call "
                       "sites actually name this channel.")))
    # State-machine claims (WS-A3): states rot fast — the enum gains a member, the dispatch grows
    # a branch, and the map's lifecycle silently lies. Each recorded machine is a prime skeptic
    # target, anchored at its declaring line (else the element's own source).
    # Drift-eligible WHEN the machine cites its own `source`. This one is NOT the store/messaging
    # case: there the skeptic is sent to a call site, a different kind of line from the anchor, so a
    # difference is not drift. Here the skeptic is sent to *the declaring enum/constants* — the same
    # line the anchor points at — so a difference IS drift, and it is the ONLY line-level check these
    # anchors have: `check_state_sources_model` reads the whole file text, so a declaration that
    # moves WITHIN its file is invisible to it. Suppressing this hid a real 26-line move.
    # Without `sm.source` the anchor falls back to the element's own line, which never declared the
    # states — that fallback stays ineligible, on the same different-kind-of-line reasoning.
    for el in (*m.entities, *m.components):
        sm = getattr(el, "states", None)
        if sm is not None and sm.states:
            src = sm.source or getattr(el, "source", "") or ""
            items.append(WorkItem(
                claim=lifecycle_claim(el.id, el.name, sm.states, sm.transitions),
                anchor=_anchor(src),
                drift_eligible=bool((sm.source or "").strip()), theme="lifecycle",
                why_risky=("lifecycles rot first — verify the declaring enum/constants still "
                           "list exactly these states and transitions.")))
    # Cadence claims (WS-A2): a recorded schedule is a claim about WHEN code runs, and schedules
    # drift in real life (an interval tuned in config, a cron moved) — so each anchored cadence is
    # a skeptic target. Anchor = the declaring line (`cadence_source`), falling back to the entry
    # point's own source. Drift-eligible only when `cadence_source` is CITED: the skeptic is then
    # sent to the declaring line, the same kind of line the anchor points at, so a difference is
    # real drift (a cron moved inside its file). An INFERRED cadence anchors the EP's own line,
    # which never declared the schedule — different kind of line, so drift there is noise.
    # (`fix apply-drift` has no cadence writer either way, so a confirmed drift is re-authored by
    # hand; that limits the REMEDY, it does not make the REPORT wrong.)
    for ep in m.entry_points:
        if (ep.cadence or "").strip():
            # An INFERRED cadence (no declaring anchor) still deserves a skeptic, but the honest
            # instruction differs: the fallback anchor is the EP's own line, which never declared
            # the schedule — send the skeptic hunting, don't imply the line says it (review #5).
            cited = bool((ep.cadence_source or "").strip())
            items.append(WorkItem(
                claim=cadence_claim(ep.kind, ep.trigger, ep.cadence),
                anchor=_anchor(ep.cadence_source if cited else ep.source),
                drift_eligible=cited, theme="cadence",
                why_risky=("a schedule is config-tuned and drifts silently — verify the declaring "
                           "line still says this cadence." if cited else
                           "cadence is INFERRED (no declaring anchor) — find the line that "
                           "actually declares the schedule and check the value.")))
    # LAST, so the order matches `_THEMES` — see the note where the other tiers are extended.
    items.extend(other_items)
    seen: set[str] = set()
    unique: list[WorkItem] = []
    for it in items:
        if it.claim not in seen:
            seen.add(it.claim)
            unique.append(it)
    return unique


# ── CLI ──────────────────────────────────────────────────────────────────────────────────────────

def _format(findings: list[Finding], worklist: list[WorkItem], verbose: bool = False) -> str:
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
        risk_note = "" if verbose else " (per-claim rationale under --verbose)"
        out.append(f"L2 grounding worklist ({len(worklist)} claims to disprove against the code — "
                   f"group by theme/risk and farm to fresh-context skeptics, method.md Phase 4){risk_note}:")
        # Signpost the machine-readable payload AT THE POINT OF USE. method.md says to batch from
        # `--json` and "never regex-parse the human report", but a live build still paged this text
        # with `head -45` + `sed -n '45,90p'` — the option is only discoverable in the method doc,
        # not where the list is actually read.
        out.append(f"  (batching these? read `coyodex audit --json` — {{findings, worklist, "
                   f"themes, theme_counts}} as "
                   "JSON — never parse this text)")
        for i, w in enumerate(worklist, 1):
            anchor = f"  [{w.anchor}]" if w.anchor else ""
            out.append(f"  {i}. {w.claim}{anchor}")
            if w.detail:  # G1: the claim carries its endpoints' names + files — no map needed
                out.append(f"     who: {w.detail}")
            if verbose:  # the near-identical per-category rationale — collapsed by default (A3)
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
    """Thin wrapper: whole-list mode is process-wide, so reset it on every exit path."""
    try:
        return _run(argv)
    finally:
        reset_full_lists()


BATCH_SCHEMA = "coyodex/theme-batch/v1"


def _opt_value(argv: list[str], flag: str) -> str | None:
    """The value given to `flag`, or None. A value that LOOKS like a flag is not a value.

    `--batches --cap 40` used to bind `--cap` as the output directory and silently write the batch
    files into a directory called `--cap`. Accepting-and-misreading is the failure mode with no
    visible symptom, which `test_every_command_refuses_an_unknown_option` exists to prevent."""
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv) and not argv[i + 1].startswith("-"):
            return argv[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


def write_theme_batches(worklist: list[WorkItem], out_dir: Path, cap: int) -> list[tuple[str, int]]:
    """One file per theme (split at `cap` claims), each claim carrying its ANCHOR and `detail`.

    This exists because the batching step was hand-scripted on every build, and the hand-script threw
    away the fields the skeptics needed. A live build wrote `f.write(c['claim'])` and nothing else, so
    360 of 408 dispatched claims arrived as bare `C140 calls C78` — no file, no line, no component
    name — while the skeptic prompt told them the claim would end with `the path:line anchor the map
    recorded, in square brackets` and demanded it back verbatim. The tool had the anchor for 400 of
    404 items all along.

    Not a quality claim: on that build the anchored theme refuted at 1.8% and the unanchored ones at
    1.7%, so this is hygiene — the prompt stops lying to the agent — not a measured grounding gain."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Clear our OWN previous output first. Two runs at different caps left the smaller run's extra
    # files behind, so a `claims-*.json` glob dispatched 207 claims for a 184-claim worklist — 23
    # duplicated, while the tool printed the honest total. That is the stale-glob hazard that blocked
    # a `--verdicts` glob in the first place; leaving it here would just move it.
    for stale in out_dir.glob("claims-*.json"):
        stale.unlink()
    by_theme: dict[str, list[WorkItem]] = {}
    for w in worklist:
        by_theme.setdefault(w.theme, []).append(w)
    written: list[tuple[str, int]] = []
    for theme in _THEMES:                      # most-dangerous-first, so batch 1 is the risky one
        items = by_theme.get(theme, [])
        if not items:
            continue
        chunks = [items[i:i + cap] for i in range(0, len(items), cap)] or [[]]
        for n, chunk in enumerate(chunks, 1):
            name = f"claims-{theme}.json" if len(chunks) == 1 else f"claims-{theme}-{n}.json"
            payload = {
                "schema": BATCH_SCHEMA,
                "theme": theme,
                "claims": [{"claim": w.claim, "anchor": w.anchor, "detail": w.detail,
                            "why_risky": w.why_risky} for w in chunk],
            }
            (out_dir / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
            written.append((name, len(chunk)))
    return written


PROSE_BATCH_SCHEMA = "coyodex/prose-batch/v1"


def write_prose_batches(m: ProjectModel, out_dir: Path, cap: int) -> list[tuple[str, int]]:
    """One batch file per `cap` reader-facing prose fields, for the cheap read fan-out.

    Sits beside `write_theme_batches` because it is the same move: the tool cuts the work and states
    the rules, an agent judges, and nothing in `audit` itself calls a model — so two runs of `audit`
    on one map still print the same thing.

    Its own stale files are cleared for the same reason the claim batches clear theirs: two runs at
    different caps once left the smaller run's extra files behind and a glob dispatched 23 duplicate
    claims while the tool printed the honest total."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("prose-*.json"):
        stale.unlink()
    written: list[tuple[str, int]] = []
    for n, chunk in enumerate(prose.batch_fields(prose.iter_prose_fields(m), cap), 1):
        name = f"prose-{n}.json"
        payload = {
            "schema": PROSE_BATCH_SCHEMA,
            "prompt_version": prose.READ_PROMPT_VERSION,
            "instructions": prose.build_read_prompt(),
            "fields": [{"where": where, "text": text} for where, text in chunk],
        }
        (out_dir / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
        written.append((name, len(chunk)))
    return written


def _run(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "-h" in argv or "--help" in argv:
        print("usage: coyodex audit [.coyodex/project-map.json] [--verbose] [--json]\n\n"
              "The adversarial pass over a model map: L1 deterministic self-contradiction\n"
              "checks + the L2 grounding worklist. Blocks (exit 1) only on a hard contradiction.\n"
              "--verbose adds each worklist claim's `risk:` rationale (collapsed by default).\n"
              "--json emits {findings, worklist, themes, theme_counts} as machine-readable JSON.\n"
              "--batches <dir> [--cap N] writes one Phase-4 claims file per theme (default cap 40),\n"
              "  most-dangerous-first, each claim carrying its anchor + detail so the skeptics are\n"
              "  not handed a bare `C1 calls C2`. Not build-fragments/ — assemble globs that.\n"
              "  Each worklist item carries `theme` (a closed, most-dangerous-first set) and\n"
              "  `drift_eligible`; `theme_counts` sizes each group. Batch the Phase-4 skeptics\n"
              "  BY THEME — the shape the Phase-4\n"
              "skeptic-batching workflow consumes (no more regex-parsing the human report).")
        return 0
    verbose = "--verbose" in argv
    as_json = "--json" in argv
    batches_out = _opt_value(argv, "--batches")
    cap_raw = _opt_value(argv, "--cap")
    for flag, val in (("--batches", batches_out), ("--cap", cap_raw)):
        if flag in argv and val is None:
            print(f"ERROR: {flag} needs a value (a value starting with '-' is not one)",
                  file=sys.stderr)
            return 2
    # Reject unknown options rather than ignoring them. `--jsonn` used to produce the human report and
    # exit 0: a build asking for JSON silently got prose, with no signal that its flag was a typo.
    # Every sibling command already refuses; these two were the exceptions.
    _known = ("--verbose", "--json", "--batches", "--cap")
    unknown = [a for a in argv if a.startswith("-") and a not in _known
               and not any(a.startswith(k + "=") for k in _known)]
    if unknown:
        print(f"ERROR: unknown option(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    if as_json:
        set_full_lists(True)   # whole `detail` member lists; reset by main()'s finally
    # Skip each value-taking flag's VALUE. `args = [a for a in argv if not a.startswith("-")]` was
    # safe while every flag was valueless; with `--batches <dir>` it took the directory as the map
    # path and reported `AUDIT SKIPPED: [Errno 21] Is a directory` — an error about the wrong thing.
    args: list[str] = []
    skip = False
    for a in argv:
        if skip:
            skip = False
            continue
        if a in ("--batches", "--cap"):
            skip = True
            continue
        if not a.startswith("-"):
            args.append(a)
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
    if batches_out is not None:
        out_dir = Path(batches_out)
        # `build-fragments/` is where `assemble` globs. A batch file dropped there is not a fragment
        # and hard-stops the build's most expensive step with `theme: unknown field / ASSEMBLY
        # FAILED`, and it is the obvious place to point this. Refuse by name rather than let the
        # build discover it at assemble time.
        if out_dir.name == "build-fragments" or out_dir.parent.name == "build-fragments":
            print(f"ERROR: refusing --batches {out_dir} — `assemble` globs build-fragments/ and a "
                  f"theme-batch file is not a fragment; it would fail the assemble. Use "
                  f".coyodex/verify/ (where the verdicts live).", file=sys.stderr)
            return 2
        try:
            cap = int(cap_raw) if cap_raw else 40
        except ValueError:
            print(f"ERROR: --cap must be an integer, got '{cap_raw}'", file=sys.stderr)
            return 2
        if cap < 1:
            print("ERROR: --cap must be >= 1", file=sys.stderr)
            return 2
        blocking = [f for f in findings if f.severity == CONTRADICTION]
        if blocking:
            # Batching a contradicting map would dispatch skeptics against a model the audit already
            # rejects, and the old code printed a success line while returning 1 — output and exit
            # status disagreeing is the exact failure this change set exists to remove.
            print(f"ERROR: refusing to write batches — audit found {len(blocking)} blocking "
                  f"contradiction(s). Fix them first; run `coyodex audit <map>` to see them.",
                  file=sys.stderr)
            return 1
        written = write_theme_batches(worklist, out_dir, cap)
        for name, n in written:
            print(f"{name}: {n} claim(s)")
        print(f"wrote {len(written)} theme batch(es) to {out_dir} — {len(worklist)} claim(s) total, "
              f"each carrying its anchor and detail")
        # The read fan-out rides the same flag: one command cuts both kinds of work, so a lead
        # cannot dispatch the skeptics and silently skip the read. Its findings are ADVICE about how
        # the map READS, never about whether it is true, so they never gate anything.
        prose_written = write_prose_batches(m, out_dir, cap)
        for name, n in prose_written:
            print(f"{name}: {n} prose field(s)")
        n_fields = sum(n for _name, n in prose_written)
        print(f"wrote {len(prose_written)} prose batch(es) to {out_dir} — {n_fields} field(s) "
              f"total, each carrying the two rules a counter cannot judge")
        return 0
    if as_json:
        print(json.dumps({
            # `where` mirrors `location`, and BOTH ship. The text report prints `where: …`, so a
            # reader who saw the human output and then reached for `--json` wrote `f.get("where")`,
            # matched nothing, printed an empty result and spent the next turn re-doing the same
            # extraction by grepping the text. Renaming the key instead would break anything that
            # already reads `location`, which is why the old name stays.
            "findings": [{"check": f.check, "severity": f.severity, "location": f.location,
                          "where": f.location,
                          "message": f.message} for f in findings],
            # `theme` is what a Phase-4 batcher groups on (method.md: "group by theme/risk"); the
            # ordered `themes` list saves the consumer from hard-coding the risk order, and the
            # per-theme counts let it size batches without walking the worklist twice.
            "worklist": [{"claim": w.claim, "anchor": w.anchor, "detail": w.detail,
                          "why_risky": w.why_risky, "theme": w.theme,
                          "drift_eligible": w.drift_eligible} for w in worklist],
            "themes": list(_THEMES),
            "theme_counts": {t: sum(1 for w in worklist if w.theme == t) for t in _THEMES
                             if any(w.theme == t for w in worklist)},
        }, indent=1, ensure_ascii=False))
    else:
        print(_format(findings, worklist, verbose=verbose))
    return 1 if any(f.severity == CONTRADICTION for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
