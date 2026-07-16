#!/usr/bin/env python3
"""Diagram balance — the fan-out advisories and the regroup-proposal engine.

Every rendered diagram shows a node's IMMEDIATE children (the viewer draws exactly
`_components_of` + `_child_subsystems`), so each screen should carry a readable number of
boxes: target 5±2. This module computes, from the model alone (stdlib-only, zero I/O):

  * `balance_warnings` — the always-on advisory warnings `coyodex validate` appends
    (never problems: balance NEVER gates; it only ever re-groups, and re-grouping is a
    view-only edit — membership on the child, member lists derived).
  * the C→C graph machinery (`cc_pairs`, `quotient_pairs`, `modularity`,
    `inter_group_matrix`) and the deterministic greedy split proposer (`propose_split`)
    that `coyodex balance` renders as Direct-map-change suggestions.

Scoping rules (from the adversarial review of the design):
  * Modularity (Q) is a SPLIT-context number, never a top-cut score — a tech-tier root
    cut scores near-perfect Q while being the least informative top screen.
  * Sparse (<3) warns at the ROOT only; mid-tree 2-child subsystems are normal.
  * Homogeneous screens (a family of same-kind siblings — 11 repositories) are exempt
    up to `FANOUT_HOMOG_HI` and never receive a modularity proposal ("list-shaped").
  * A justified exception recorded in the model's `extras` under the heading
    "Balance exceptions" silences the named diagrams durably.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from coyodex.model import ProjectModel

# ── the bands (named constants so calibration is one edit) ───────────────────────────────────────

FANOUT_LO = 3            # below → sparse (root only)
FANOUT_TARGET = 5        # the 5±2 target the method text states
FANOUT_SOFT_HI = 9       # above → soft tier (reported by `coyodex balance` only)
FANOUT_HARD_HI = 12      # above → validate warning
FANOUT_HOMOG_HI = 15     # homogeneous families are exempt up to here
SUBSYSTEMS_RECOMMENDED_ABOVE = 15  # mirrors method.md "recommended above ~15 components"

_EXCEPTIONS_HEADING = "balance exceptions"
_ROOT = "<root>"

_STOPWORDS = frozenset(
    "the a an and or of for to in on with via per by from into over its their our this that "
    "component components service services module modules code file files".split())


# ── immediate-children maps (the diagrams) ───────────────────────────────────────────────────────

def subsystem_children(m: ProjectModel) -> dict[str | None, list[str]]:
    """Diagram id -> immediate children (None = the root diagram). Children of the root are the
    top-level subsystems plus any ungrouped components; children of an S are its child subsystems
    plus its direct member components — exactly what the viewer draws."""
    out: dict[str | None, list[str]] = {None: []}
    for s in m.subsystems:
        out.setdefault(s.id, [])
        out.setdefault(s.parent, []).append(s.id) if s.parent else out[None].append(s.id)
    for c in m.components:
        if c.subsystem:
            out.setdefault(c.subsystem, []).append(c.id)
        else:
            out[None].append(c.id)
    return out


def subdomain_children(m: ProjectModel) -> dict[str | None, list[str]]:
    """The SD-forest mirror of `subsystem_children` (entities as leaves)."""
    out: dict[str | None, list[str]] = {None: []}
    for sd in m.subdomains:
        out.setdefault(sd.id, [])
        out.setdefault(sd.parent, []).append(sd.id) if sd.parent else out[None].append(sd.id)
    for e in m.entities:
        if e.subdomain:
            out.setdefault(e.subdomain, []).append(e.id)
        else:
            out[None].append(e.id)
    return out


def nesting_depth(m: ProjectModel) -> int:
    """Grouping levels in the S forest (flat subsystems = 1, one nested tier = 2, …; none = 0)."""
    parent = {s.id: s.parent for s in m.subsystems}
    best = 0
    for sid in parent:
        depth, cur = 1, parent.get(sid)
        seen = {sid}
        while cur and cur not in seen:   # cycle-safe (cycles are a validate problem, not ours)
            seen.add(cur)
            depth += 1
            cur = parent.get(cur)
        best = max(best, depth)
    return best


# ── homogeneity (deterministic, model-only) ──────────────────────────────────────────────────────

def _container_dir(m: ProjectModel, elem_id: str) -> str | None:
    """The element's container directory: a file anchor's dir; a `path/` anchor's own path."""
    src: str | None = None
    files: list[str] = []
    for c in m.components:
        if c.id == elem_id:
            src, files = c.source, c.files
            break
    else:
        for grp in (*m.subsystems, *m.subdomains):
            if grp.id == elem_id:
                src = grp.source
                break
        else:
            for e in m.entities:
                if e.id == elem_id:
                    src = e.source
                    break
    if not src and files:
        src = files[0]
    if not src:
        return None
    if src.endswith("/"):
        return src.rstrip("/")
    path = src.rsplit(":", 1)[0] if re.search(r":\d", src) else src
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _name_token(m: ProjectModel, elem_id: str) -> str | None:
    """The element's final name token, lowercased ('Audit log repository' -> 'repository')."""
    for arr in (m.components, m.subsystems, m.subdomains, m.entities):
        for el in arr:
            if el.id == elem_id:
                tokens = re.findall(r"[A-Za-z0-9]+", el.name)
                return tokens[-1].lower() if tokens else None
    return None


def _kind(elem_id: str) -> str:
    return "SD" if elem_id.startswith("SD") else elem_id[0]


def is_homogeneous(m: ProjectModel, children: list[str]) -> bool:
    """All children the same kind AND ≥2/3 share a container directory or a final name token —
    a list-shaped family (11 repositories) that reads fine dense."""
    if len(children) < 2 or len({_kind(c) for c in children}) != 1:
        return False
    threshold = math.ceil(len(children) * 2 / 3)
    dirs = Counter(d for c in children if (d := _container_dir(m, c)) is not None)
    if dirs and dirs.most_common(1)[0][1] >= threshold:
        return True
    tokens = Counter(t for c in children if (t := _name_token(m, c)) is not None)
    return bool(tokens) and tokens.most_common(1)[0][1] >= threshold


# ── the always-on advisory (validate hook) ───────────────────────────────────────────────────────

def extras_bodies(m: ProjectModel, heading: str) -> list[str]:
    """The bodies of every extras section under the given machine-read heading (case-insensitive,
    whitespace-tolerant) — the one reader all recorded-exception headings share ('Balance
    exceptions', 'Accepted duplications', 'Unclaimed surfaces', 'Happy Path coverage'), so heading
    matching can never drift between the escape families."""
    want = heading.strip().lower()
    return [x.body for x in m.extras if x.heading.strip().lower() == want]


def _exceptions(m: ProjectModel) -> set[str]:
    """Ids the operator has durably justified ('root', 'S7', 'UC5', 'C18', 'granularity', …) in an
    extras block headed 'Balance exceptions'. Diagram ids silence fan-out warnings here; UC/SF ids
    silence the flow-length band; C ids silence the promote-to-subsystem altitude nudge; the
    literal `granularity` silences the component-count-vs-E advisory; the literal `entity-flows`
    silences the no-entity-in-any-flow canary (a map whose flows legitimately touch no entity —
    a pure proxy with no domain layer traced). All consumed only as skip-sets, so the families
    can't cross-silence anything. Without a machine-readable escape a justified advisory re-fires
    forever — and worse, invites rewording prose to dodge a heuristic."""
    out: set[str] = set()
    for body in extras_bodies(m, _EXCEPTIONS_HEADING):
        out.update(re.findall(r"\b(?:root|granularity|entity-flows|SD\d+|SF\d+|UC\d+|C\d+|S\d+)\b",
                              body))
    return out


def _name_of(m: ProjectModel, gid: str) -> str:
    for grp in (*m.subsystems, *m.subdomains):
        if grp.id == gid:
            return grp.name
    return gid


def _forest_warnings(m: ProjectModel, children: dict[str | None, list[str]],
                     groups_exist: bool, n_leaves: int, leaf_word: str, leaf_singular: str,
                     group_word: str, skip: set[str]) -> list[str]:
    out: list[str] = []
    root_kids = children.get(None, [])
    if not groups_exist:
        if n_leaves > SUBSYSTEMS_RECOMMENDED_ABOVE and "root" not in skip:
            out.append(f"Balance: {n_leaves} {leaf_word} with no {group_word} — the root diagram "
                       f"shows all of them ungrouped; {group_word} are recommended above "
                       f"~{SUBSYSTEMS_RECOMMENDED_ABOVE} (cluster by capability, target 5±2 "
                       f"boxes per diagram)")
        return out

    # Root: the one diagram where SPARSE is an anti-pattern (the first screen must inform).
    n_root = len(root_kids)
    if "root" not in skip:
        if n_root < FANOUT_LO and n_leaves >= SUBSYSTEMS_RECOMMENDED_ABOVE:
            out.append(f"Balance: the root diagram shows only {n_root} top-level boxes for "
                       f"{n_leaves} {leaf_word} — a sparse (often tech-tier) root wastes the first "
                       f"screen; lead with capability groups (target 5±2)")
        elif n_root > FANOUT_HARD_HI and not (
                is_homogeneous(m, root_kids) and n_root <= FANOUT_HOMOG_HI):
            out.append(f"Balance: the root diagram shows {n_root} top-level boxes (target 5±2) — "
                       f"group them into fewer capability {group_word}")

    for gid, kids in children.items():
        if gid is None or gid in skip or not kids:
            continue  # root handled above; empty boxes have their own warning
        n = len(kids)
        if n == 1 and not kids[0].startswith(("S", "SD")):
            out.append(f"Balance: {gid} ({_name_of(m, gid)}) wraps a single {leaf_singular} "
                       f"({kids[0]}) — a one-child level isn't pulling its weight; inline it or "
                       f"grow the group")
        elif n > FANOUT_HARD_HI:
            if is_homogeneous(m, kids):
                if n > FANOUT_HOMOG_HI:
                    out.append(f"Balance: {gid} ({_name_of(m, gid)}) shows {n} children — dense "
                               f"even for a homogeneous family; split it by name/directory family")
            else:
                out.append(f"Balance: {gid} ({_name_of(m, gid)}) shows {n} children (target 5±2) "
                           f"— group them into child {group_word} (`coyodex balance` proposes "
                           f"splits)")
    return sorted(out)


def balance_warnings(m: ProjectModel) -> list[str]:
    """The advisory fan-out warnings for both forests. Warnings only — balance never blocks."""
    skip = _exceptions(m)
    out = _forest_warnings(m, subsystem_children(m), bool(m.subsystems), len(m.components),
                           "components", "component", "subsystems", skip)
    out += _forest_warnings(m, subdomain_children(m), bool(m.subdomains), len(m.entities),
                            "entities", "entity", "subdomains", skip)
    return out


# ── the C→C graph (split proposals; `coyodex balance` only) ──────────────────────────────────────

def cc_pairs(m: ProjectModel) -> set[frozenset[str]]:
    """Deduped undirected component↔component pairs (C→D / C→E excluded, self-loops dropped)."""
    return {frozenset((e.src, e.dst)) for e in m.edges
            if e.src.startswith("C") and e.dst.startswith("C") and e.src != e.dst}


def _subtree_leaves(m: ProjectModel, sid: str) -> set[str]:
    """Every component under `sid` at any depth."""
    kids: dict[str, list[str]] = {}
    for s in m.subsystems:
        if s.parent:
            kids.setdefault(s.parent, []).append(s.id)
    comps: dict[str, list[str]] = {}
    for c in m.components:
        if c.subsystem:
            comps.setdefault(c.subsystem, []).append(c.id)
    out: set[str] = set()
    stack = [sid]
    while stack:
        cur = stack.pop()
        out.update(comps.get(cur, []))
        stack.extend(kids.get(cur, []))
    return out


def partition_at(m: ProjectModel, level: str = "leaf") -> dict[str, str]:
    """Component id -> group key: its immediate subsystem ('leaf') or its top-level ancestor
    ('top'); ungrouped components map to the synthetic root group."""
    parent = {s.id: s.parent for s in m.subsystems}
    out: dict[str, str] = {}
    for c in m.components:
        g = c.subsystem or _ROOT
        if level == "top" and g != _ROOT:
            seen = {g}
            while (p := parent.get(g)) and p not in seen:
                seen.add(p)
                g = p
        out[c.id] = g
    return out


def modularity(pairs: set[frozenset[str]] | dict[frozenset[str], int],
               partition: dict[str, str]) -> tuple[float, float]:
    """(coverage, Newman Q) of a partition over an undirected (optionally weighted) pair graph.
    Coverage = intra-group weight share (the explainable number); Q additionally discounts what
    a random cut would score. Pairs with an endpoint outside the partition are ignored."""
    weights = pairs if isinstance(pairs, dict) else {p: 1 for p in pairs}
    m_total = 0
    intra: Counter[str] = Counter()
    degree: Counter[str] = Counter()
    for pair, w in weights.items():
        a, b = sorted(pair)
        if a not in partition or b not in partition:
            continue
        m_total += w
        degree[partition[a]] += w
        degree[partition[b]] += w
        if partition[a] == partition[b]:
            intra[partition[a]] += w
    if m_total == 0:
        return 0.0, 0.0
    coverage = sum(intra.values()) / m_total
    q = sum(intra[g] / m_total - (degree[g] / (2 * m_total)) ** 2 for g in degree)
    return coverage, q


def inter_group_matrix(pairs: set[frozenset[str]] | dict[frozenset[str], int],
                       partition: dict[str, str]) -> dict[tuple[str, str], int]:
    """(group, group) -> pair weight, groups sorted within the key; (g, g) rows are intra."""
    weights = pairs if isinstance(pairs, dict) else {p: 1 for p in pairs}
    out: Counter[tuple[str, str]] = Counter()
    for pair, w in weights.items():
        a, b = sorted(pair)
        if a in partition and b in partition:
            ga, gb = sorted((partition[a], partition[b]))
            out[(ga, gb)] += w
    return dict(out)


def _diagram_graph(m: ProjectModel, sid: str | None) -> tuple[list[str], dict[frozenset[str], int]]:
    """The graph a diagram's split proposal runs on: nodes = the diagram's immediate children;
    pairs = C→C pairs projected onto them. A child SUBSYSTEM absorbs its whole subtree's
    components (the quotient graph), so S-children diagrams get proposals too."""
    children = subsystem_children(m).get(sid, [])
    rep: dict[str, str] = {}
    for ch in children:
        if ch.startswith("S"):
            for leaf in _subtree_leaves(m, ch):
                rep[leaf] = ch
        else:
            rep[ch] = ch
    weights: Counter[frozenset[str]] = Counter()
    for pair in cc_pairs(m):
        a, b = sorted(pair)
        if a in rep and b in rep and rep[a] != rep[b]:
            weights[frozenset((rep[a], rep[b]))] += 1
    return children, dict(weights)


def subgraph_signal(m: ProjectModel, sid: str | None) -> str:
    """Whether a diagram's internal graph carries enough signal for a modularity split:
    'homogeneous' | 'sparse' (pair weight < n/2) | 'star' (one hub carries >½ the weight) | 'ok'."""
    children, weights = _diagram_graph(m, sid)
    if is_homogeneous(m, children):
        return "homogeneous"
    total = sum(weights.values())
    if total < len(children) / 2:
        return "sparse"
    incident: Counter[str] = Counter()
    for pair, w in weights.items():
        for node in pair:
            incident[node] += w
    if incident and incident.most_common(1)[0][1] > total / 2:
        return "star"
    return "ok"


# ── the greedy split (deterministic CNM) ─────────────────────────────────────────────────────────

@dataclass
class Proposal:
    """One suggested child group for an over-dense diagram."""
    name: str
    name_basis: str                       # "dir" | "purpose" | "unnamed"
    members: list[tuple[str, str]] = field(default_factory=list)   # (id, display name)


def _segmentwise_lcp(paths: list[str]) -> list[str]:
    """Longest common directory prefix, SEGMENT-wise (never string-wise)."""
    if not paths:
        return []
    split = [p.split("/") for p in paths]
    out: list[str] = []
    for segs in zip(*split):
        if len(set(segs)) == 1:
            out.append(segs[0])
        else:
            break
    return out


def _display_name(m: ProjectModel, elem_id: str) -> str:
    for arr in (m.components, m.subsystems, m.subdomains, m.entities):
        for el in arr:
            if el.id == elem_id:
                return el.name
    return elem_id


def name_seed(m: ProjectModel, member_ids: list[str],
              parent_lcp: list[str] | None = None) -> tuple[str, str]:
    """(seed name, basis). Dir first (last segment of the members' segment-wise LCP), the most
    frequent non-stopword purpose token second, '(name me)' last. A dir seed must extend BEYOND
    `parent_lcp` (the diagram's own common prefix) — the shared package dir discriminates
    nothing, so it falls through to the purpose words."""
    dirs = [d for c in member_ids if (d := _container_dir(m, c))]
    lcp = _segmentwise_lcp(dirs) if len(dirs) == len(member_ids) and dirs else []
    if lcp and lcp[-1] and len(lcp) > len(parent_lcp or []):
        return lcp[-1].replace("_", " ").replace("-", " ").title(), "dir"
    purposes: list[str] = []
    for el in (*m.components, *m.subsystems):   # quotient members are subsystems
        if el.id in member_ids and el.purpose:
            purposes.append(el.purpose)
    tokens = Counter(t for p in purposes for t in re.findall(r"[a-z0-9]+", p.lower())
                     if t not in _STOPWORDS and len(t) > 2)
    if tokens:
        return tokens.most_common(1)[0][0].title(), "purpose"
    return "(name me)", "unnamed"


def _dedup_names(m: ProjectModel, proposals: list[Proposal]) -> None:
    """Sibling proposals with colliding seeds get a discriminating member-token suffix."""
    by_name: dict[str, list[Proposal]] = {}
    for p in proposals:
        by_name.setdefault(p.name, []).append(p)
    for clashing in (v for v in by_name.values() if len(v) > 1):
        for p in clashing:
            tokens = Counter(t for _, disp in p.members
                             for t in re.findall(r"[a-z0-9]+", disp.lower())
                             if t not in _STOPWORDS and len(t) > 2)
            others = {t for q in clashing if q is not p for _, disp in q.members
                      for t in re.findall(r"[a-z0-9]+", disp.lower())}
            distinct = [t for t, _ in tokens.most_common() if t not in others]
            p.name = f"{p.name} — {distinct[0].title()}" if distinct else f"{p.name} (name me)"


def propose_split(m: ProjectModel, sid: str | None) -> list[Proposal]:
    """Deterministic greedy-modularity (CNM) split of an over-dense diagram's children.
    Returns [] when the subgraph carries no signal (`subgraph_signal` != 'ok') or the merge
    collapses to a single group — the caller prints the 'list-shaped' message instead.
    Never returns a group of size 1 (a singleton wrap would itself warn)."""
    if subgraph_signal(m, sid) != "ok":
        return []
    children, weights = _diagram_graph(m, sid)
    groups: dict[str, list[str]] = {ch: [ch] for ch in children}
    member_of: dict[str, str] = {ch: ch for ch in children}

    def q_of() -> float:
        return modularity(weights, member_of)[1]

    current_q = q_of()
    while len(groups) > 1:
        best: tuple[float, str, str] | None = None
        for pair in weights:
            a, b = sorted(pair)
            ga, gb = member_of[a], member_of[b]
            if ga == gb or len(groups[ga]) + len(groups[gb]) > FANOUT_SOFT_HI:
                continue
            ga, gb = sorted((ga, gb))
            trial = dict(member_of)
            for node in groups[gb]:
                trial[node] = ga
            delta = modularity(weights, trial)[1] - current_q
            cand = (delta, ga, gb)
            if best is None or cand[0] > best[0] or (cand[0] == best[0] and cand[1:] < best[1:]):
                best = cand
        if best is None or best[0] <= 0:
            break
        _, ga, gb = best
        for node in groups.pop(gb):
            member_of[node] = ga
            groups[ga].append(node)
        current_q = q_of()

    # Attach edge-less / singleton leftovers by dir-prefix affinity (never propose a 1-box group).
    multi = {g: sorted(mem) for g, mem in groups.items() if len(mem) > 1}
    if not multi or len(multi) == 1 and len(next(iter(multi.values()))) == len(children):
        return []
    singles = sorted(ch for g, mem in groups.items() if len(mem) == 1 for ch in mem)
    for ch in singles:
        ch_dir = _container_dir(m, ch) or ""
        def affinity(gmem: list[str]) -> int:
            return max((len(_segmentwise_lcp([ch_dir, _container_dir(m, o) or ""]))
                        for o in gmem), default=0)
        target = max(sorted(multi), key=lambda g: (affinity(multi[g]), -len(multi[g])))
        multi[target].append(ch)
    parent_lcp = _segmentwise_lcp([d for c in children if (d := _container_dir(m, c))])
    proposals = [Proposal(*name_seed(m, mem, parent_lcp),
                          members=[(c, _display_name(m, c)) for c in mem])
                 for _, mem in sorted(multi.items())]
    _dedup_names(m, proposals)
    return proposals


def fanout_summary(m: ProjectModel) -> tuple[int | None, int | None, float | None, int]:
    """(root_fanout, max_fanout, in_band_pct, nesting_depth) over the S-forest diagrams — the
    eval profile's report-only balance fields. A diagram is in-band when its fan-out sits in
    [FANOUT_LO, FANOUT_SOFT_HI] or it is an exempt homogeneous family (≤ FANOUT_HOMOG_HI)."""
    if not m.components and not m.subsystems:
        return None, None, None, 0
    children = subsystem_children(m)
    fans: list[tuple[list[str], int]] = []
    for sid in (None, *(s.id for s in m.subsystems)):
        kids = children.get(sid, [])
        if kids or sid is None:
            fans.append((kids, len(kids)))
    in_band = sum(1 for kids, n in fans
                  if FANOUT_LO <= n <= FANOUT_SOFT_HI
                  or (n <= FANOUT_HOMOG_HI and is_homogeneous(m, kids)))
    return (len(children.get(None, [])),
            max(n for _, n in fans),
            round(in_band / len(fans), 3),
            nesting_depth(m))


def next_free_group_id(m: ProjectModel, prefix: str = "S") -> str:
    """The next unused numeric id for the given group prefix ('S' or 'SD')."""
    arr = m.subdomains if prefix == "SD" else m.subsystems
    pat = re.compile(rf"^{prefix}(\d+)$")
    used = [int(match.group(1)) for g in arr if (match := pat.match(g.id))]
    return f"{prefix}{max(used, default=0) + 1}"
