#!/usr/bin/env python3
"""Derived: everything the map already knows about each FEATURE, gathered from where it is stored.

A feature (a capability) is a LABEL today. Its use cases carry it, and nothing else does — so
"what does Billing & credits do, decide, know and run on?" is answered by reading four other views
and joining them by hand. This module does that join once, from the stored map, and stores nothing.

DERIVED, NEVER AUTHORED, for the same reason a rule's components and sweep state are derived: an
authored "this feature touches these entities" is unfalsifiable, and a hand-assigned list rendered
as derived was the rules prototype's most damaging failure — it looked correct on every screen.

THE RULE JOIN IS REUSED, NOT REINVENTED. `validate_model.rule_steps` already answers "which
use-case steps does this rule\'s sites reach", with the exact-line and same-function strengths the
Rules view renders. This module walks from those steps to the use case to its feature. A second
implementation would drift from the Rules view, and the two screens would then disagree about what
one rule governs.

The obvious join — through the COMPONENT holding the site — was measured and rejected. On two live
maps (Meerbot 61 rules, mcpolis 66) it reached 92-98% of rules and named a single feature for only
10-28% of them, because a component is shared and a rule smears across most of the product. The
step join reaches about half the rules and names one feature four times out of five.

WHAT DOES NOT JOIN IS A FINDING, not a hole to paper over. The unjoined rules on both maps are the
DEEPEST logic in each product (`policy_engine.py`, `settings_resolver.py`, `reader_runner.py`): a
flow step anchors at the call BETWEEN two components, a rule anchors INSIDE the decision function one
level down, so the two are recorded at different depths and never meet. `Coverage.rules_unjoined`
carries that count so a reader is told, rather than shown a feature's rules as if they were all of
them.

Stdlib-only (the cli.py firewall). Everything it needs already exists: `expanded_flow_steps` (so
content inside a sub-flow is never invisible), `rule_steps` + `anchored_flow_steps` for the join,
`impact_git.load_map_extents` for the pre-index table, and `parse_anchor` for a site's file.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from coyodex.anchors import parse_anchor
from coyodex.impact_git import Extents
from coyodex.model import ProjectModel, expanded_flow_steps
from coyodex.validate_model import anchored_flow_steps, capability_audience, rule_steps


@dataclass(frozen=True)
class FeatureFacts:
    """One feature, with every part of the map that belongs to it.

    Ids, not objects: the caller already holds the model and renders names from it, and a list of
    ids serialises into the viewer bundle unchanged."""
    id: str
    name: str
    purpose: str = ""
    # `happy_path` is deliberately NOT carried: it is an authoring decision the Coverage rule reads,
    # and no view draws it, so shipping it would be a field nothing consumes.
    audience: list[str] = field(default_factory=list)        # user and/or internal — DERIVED from the
                                                             # roles driving its use cases, never
                                                             # authored, so the two cannot disagree.
                                                             # A SET: a surface both sides act in
                                                             # honestly carries both words
    roles: list[str] = field(default_factory=list)           # who drives its use cases
    use_cases: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)    # how you reach it
    rules: list[str] = field(default_factory=list)           # what it decides (function join)
    entities: list[str] = field(default_factory=list)        # what it knows about
    components: list[str] = field(default_factory=list)      # what implements it


@dataclass(frozen=True)
class Coverage:
    """How much of the map the feature layer accounts for. Every number is a count of named things,
    so a reader can always ask which ones."""
    components_total: int = 0
    components_in_a_flow: int = 0          # a use-case walk passes through it
    components_in_a_rule: int = 0          # a decision is enforced in it
    components_unreached: list[str] = field(default_factory=list)   # neither — named, not counted
    rules_total: int = 0
    rules_joined: int = 0
    rules_unjoined: int = 0                # enforced where no use-case walk passes
    entry_points_total: int = 0
    entry_points_named: int = 0            # named by some use case
    use_cases_total: int = 0
    use_cases_without_feature: int = 0


@dataclass(frozen=True)
class FeatureIndex:
    """The whole derivation. `rule_join_uses_extents` is the honesty flag the pages depend on.

    Without the pre-index table the join still runs, but only an EXACT line match links a rule to a
    step, so a feature's rule list is a floor rather than an answer. A page that does not say so
    reports a partial list as the whole one. This mirrors `rule_steps`' own degradation rather than
    inventing a second silence."""
    features: list[FeatureFacts] = field(default_factory=list)
    component_features: dict[str, list[str]] = field(default_factory=dict)
    rule_features: dict[str, list[str]] = field(default_factory=dict)
    role_features: dict[str, dict[str, int]] = field(default_factory=dict)  # role -> feat -> UCs
    unassigned_use_cases: list[str] = field(default_factory=list)
    coverage: Coverage = field(default_factory=Coverage)
    rule_join_uses_extents: bool = False


def _sorted_ids(ids: "set[str]") -> list[str]:
    """Ids in id order (`C9` before `C10`), so a rendered list never reads as shuffled."""
    def key(i: str) -> tuple[str, int, str]:
        head = i.rstrip("0123456789")
        tail = i[len(head):]
        return (head, int(tail) if tail else 0, i)
    return sorted(ids, key=key)


def build_index(m: ProjectModel, extents: Extents | None = None) -> FeatureIndex:
    """Join every part of the map onto the feature it belongs to.

    `extents` is the pre-index symbol table, from `impact_git.load_map_extents(<map path>)`. Without
    it the rule join finds exact-line links only, and `rule_join_uses_extents` says so."""
    caps = {c.id: c for c in m.capabilities}
    uc_by_id = {u.id: u for u in m.use_cases}
    # use case -> feature, and the ones that belong to none. A map with no capabilities at all is
    # not a defect here: it is the pre-feature shape, and every field below simply comes back empty.
    uc_cap = {u.id: u.capability for u in m.use_cases if u.capability in caps}
    unassigned = [u.id for u in m.use_cases if u.id not in uc_cap]

    roles = {r.id for r in m.roles}
    comp_ids = {c.id for c in m.components}
    ent_ids = {e.id for e in m.entities}

    feat_roles: dict[str, set[str]] = {c: set() for c in caps}
    feat_ucs: dict[str, set[str]] = {c: set() for c in caps}
    feat_eps: dict[str, set[str]] = {c: set() for c in caps}
    feat_ents: dict[str, set[str]] = {c: set() for c in caps}
    feat_comps: dict[str, set[str]] = {c: set() for c in caps}
    role_feat: dict[str, dict[str, int]] = {}

    for u in m.use_cases:
        cap = uc_cap.get(u.id)
        if cap is None:
            continue
        feat_ucs[cap].add(u.id)
        feat_eps[cap].update(u.entry_points or ())
        for a in u.actors or ():
            if a in roles:
                feat_roles[cap].add(a)
                role_feat.setdefault(a, {})
                role_feat[a][cap] = role_feat[a].get(cap, 0) + 1

    # What a feature touches, from the steps of its use cases' flows. Sub-flows are EXPANDED, so a
    # feature whose work happens inside a shared sequence still owns what that sequence touches.
    comp_in_flow: set[str] = set()
    for f in m.flows:
        cap = uc_cap.get(f.uc)
        for st in expanded_flow_steps(m, f):
            for side in (st.src, st.dst):
                if side in comp_ids:
                    comp_in_flow.add(side)
                    if cap:
                        feat_comps[cap].add(side)
                elif side in ent_ids and cap:
                    feat_ents[cap].add(side)

    # The rule join, through `rule_steps` — the SAME reader the Rules view uses, so the two screens
    # cannot disagree about what one rule governs. A rule reaches a feature when one of its sites
    # reaches a step of one of that feature's use cases.
    rule_feats: dict[str, set[str]] = {}
    # A map with no capabilities cannot join a rule to one. Reporting every rule as "unjoined" there
    # would read as a gap rather than as the pre-feature shape the map actually has.
    can_join = bool(caps)
    if can_join:
        steps = anchored_flow_steps(m)
        for r in m.rules:
            hit = {uc_cap[link.uc] for link in rule_steps(m, r, extents, steps)
                   if link.uc in uc_cap}
            if hit:
                rule_feats[r.id] = hit

    # A rule's own component reach is NOT a feature join (it smears) — but it IS how a component
    # earns "a decision is enforced here", which the coverage line counts.
    # EVERY owner of a file, never the first. `components[].files` is not required to be disjoint
    # and carries no line ranges: measured across five maps, coyodex's own is only 72.7% unique, with
    # 5 files claimed by 2-5 components each. Picking one silently is the failure the rules design
    # exists to prevent, and here it would UNDER-count the components a decision is enforced in.
    file_owners: dict[str, list[str]] = {}
    for c in m.components:
        for fp in c.files or ():
            file_owners.setdefault(fp, []).append(c.id)
    comp_in_rule: set[str] = set()
    for r in m.rules:
        for site in r.sites:
            loc = parse_anchor((site.where or "").strip())
            if loc is not None:
                comp_in_rule.update(file_owners.get(loc.path) or ())

    audience = capability_audience(m)
    features = [
        FeatureFacts(
            id=c.id, name=c.name, purpose=c.purpose,
            audience=audience.get(c.id) or [],
            roles=_sorted_ids(feat_roles[c.id]),
            use_cases=_sorted_ids(feat_ucs[c.id]),
            entry_points=_sorted_ids(feat_eps[c.id]),
            rules=_sorted_ids({rid for rid, hits in rule_feats.items() if c.id in hits}),
            entities=_sorted_ids(feat_ents[c.id]),
            components=_sorted_ids(feat_comps[c.id]),
        )
        for c in m.capabilities
    ]

    comp_feats: dict[str, list[str]] = {}
    for f in features:
        for cid in f.components:
            comp_feats.setdefault(cid, []).append(f.id)

    named_eps = {e for u in m.use_cases for e in (u.entry_points or ())}
    unreached = _sorted_ids({c.id for c in m.components} - comp_in_flow - comp_in_rule)
    coverage = Coverage(
        components_total=len(m.components),
        components_in_a_flow=len(comp_in_flow),
        components_in_a_rule=len(comp_in_rule),
        components_unreached=unreached,
        rules_total=len(m.rules),
        rules_joined=len(rule_feats),
        rules_unjoined=(len(m.rules) - len(rule_feats)) if can_join else 0,
        entry_points_total=len(m.entry_points),
        entry_points_named=len({e.id for e in m.entry_points if e.id and e.id in named_eps}),
        use_cases_total=len(m.use_cases),
        use_cases_without_feature=len(unassigned),
    )
    return FeatureIndex(
        features=features,
        component_features={k: _sorted_ids(set(v)) for k, v in comp_feats.items()},
        rule_features={k: _sorted_ids(v) for k, v in rule_feats.items()},
        role_features=role_feat,
        unassigned_use_cases=_sorted_ids(set(unassigned)),
        coverage=coverage,
        rule_join_uses_extents=bool(extents),
    )


def as_bundle(ix: FeatureIndex) -> dict[str, object]:
    """The index in the viewer's own vocabulary (camelCase), ready to ship in the view bundle.

    A flat, id-keyed shape on purpose: the frontend already holds the model's names and renders them
    itself, so shipping objects here would put a second copy of every name in the payload and let
    the two drift."""
    return {
        "features": [
            {"id": f.id, "name": f.name, "purpose": f.purpose,
             "audience": f.audience,
             "roles": f.roles, "useCases": f.use_cases, "entryPoints": f.entry_points,
             "rules": f.rules, "entities": f.entities, "components": f.components}
            for f in ix.features],
        "componentFeatures": ix.component_features,
        "ruleFeatures": ix.rule_features,
        "roleFeatures": ix.role_features,
        "unassignedUseCases": ix.unassigned_use_cases,
        "ruleJoinUsesExtents": ix.rule_join_uses_extents,
        "coverage": {
            "componentsTotal": ix.coverage.components_total,
            "componentsInAFlow": ix.coverage.components_in_a_flow,
            "componentsInARule": ix.coverage.components_in_a_rule,
            "componentsUnreached": ix.coverage.components_unreached,
            "rulesTotal": ix.coverage.rules_total,
            "rulesJoined": ix.coverage.rules_joined,
            "rulesUnjoined": ix.coverage.rules_unjoined,
            "entryPointsTotal": ix.coverage.entry_points_total,
            "entryPointsNamed": ix.coverage.entry_points_named,
            "useCasesTotal": ix.coverage.use_cases_total,
            "useCasesWithoutFeature": ix.coverage.use_cases_without_feature,
        },
    }
